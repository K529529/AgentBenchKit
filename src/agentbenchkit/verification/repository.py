"""Git patches derived with an evaluator-owned index, never the Agent's Git state."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from agentbenchkit.storage.artifacts import Redactor, write_json

# Only execution caches and Git internals are excluded, never source/test files.
IGNORED = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv"}


def copy_repository(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, symlinks=True, ignore=shutil.ignore_patterns(*IGNORED))


def git(directory: Path, *args: str) -> bytes:
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    for key in list(env):
        if key.startswith("GIT_") and key not in {"GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL"}:
            del env[key]
    return subprocess.check_output(
        [
            "git",
            "-c",
            "core.autocrlf=false",
            "-c",
            "core.hooksPath=" + os.devnull,
            "-c",
            "core.filemode=true",
            *args,
        ],
        cwd=directory,
        env=env,
        stderr=subprocess.PIPE,
        timeout=120,
    )


def freeze_repository(
    baseline: Path, workspace: Path, destination: Path, scratch: Path, redactor: Redactor
) -> None:
    """Include new/deleted/renamed files and modes; preserve binary patch data.

    Reject linked files escaping the repository and credentials before writing
    evidence. Use a fresh Git index/config to exclude Agent-installed Git hooks.
    """
    for path in workspace.rglob("*"):
        relative = path.relative_to(workspace)
        if any(part in IGNORED for part in relative.parts):
            continue
        if path.is_symlink():
            if not path.resolve().is_relative_to(workspace.resolve()):
                raise ValueError("candidate symlink escapes repository")
            data = os.readlink(path).encode()
        elif path.is_file():
            if path.stat().st_size > 50_000_000:
                raise ValueError("candidate file exceeds 50 MB artifact limit")
            data = path.read_bytes()
        else:
            continue
        if any(secret.encode() in data for secret in redactor.secrets):
            raise ValueError("candidate contains a credential; refusing persistence")
    copy_repository(baseline, scratch)
    git(scratch, "init", "--quiet")
    git(scratch, "add", "--all", "--force", ".")
    tree = git(scratch, "write-tree").decode().strip()
    for path in scratch.iterdir():
        if path.name == ".git":
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    for path in workspace.iterdir():
        if path.name in IGNORED:
            continue
        dest = scratch / path.name
        if path.is_symlink():
            dest.symlink_to(os.readlink(path))
        elif path.is_dir():
            copy_repository(path, dest)
        else:
            shutil.copy2(path, dest)
    git(scratch, "add", "--all", "--force", ".")
    candidate_tree = git(scratch, "write-tree").decode().strip()
    patch = git(scratch, "diff", "--cached", "--binary", "--full-index", "--no-renames", tree)
    statuses = git(scratch, "diff", "--cached", "--name-status", "--no-renames", "-z", tree)
    entries = statuses.decode("utf-8").strip("\0").split("\0") if statuses else []
    changed: list[str] = []
    deleted: list[str] = []
    for status, name in zip(entries[::2], entries[1::2], strict=True):
        (deleted if status == "D" else changed).append(name)
    destination.mkdir(parents=True, exist_ok=False)
    files = []
    for name in changed:
        source = scratch / name
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        data = os.readlink(source).encode() if source.is_symlink() else source.read_bytes()
        target.write_bytes(data)
        files.append(
            {
                "path": name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "symlink": source.is_symlink(),
                "mode": source.lstat().st_mode,
            }
        )
    (destination.parent / "patch.diff").write_bytes(patch)
    write_json(
        destination.parent / "candidate_manifest.json",
        {
            "schema_version": 2,
            "format": "git_patch",
            "baseline_hash": tree,
            "candidate_hash": hashlib.sha256(patch).hexdigest(),
            "candidate_tree": candidate_tree,
            "files": files,
            "changed": changed,
            "deleted": deleted,
        },
    )


def verified_patch(candidate_dir: Path) -> str:
    patch = (candidate_dir.parent / "patch.diff").read_bytes()
    manifest_path = candidate_dir.parent / "candidate_manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if hashlib.sha256(patch).hexdigest() != data["candidate_hash"]:
        raise ValueError("frozen patch hash mismatch")
    for item in data["files"]:
        path = (candidate_dir / item["path"]).resolve()
        if not path.is_relative_to(candidate_dir.resolve()):
            raise ValueError("candidate manifest path escapes directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("frozen candidate file hash mismatch")
    return patch.decode("utf-8")
