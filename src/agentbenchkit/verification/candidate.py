"""Freeze complete text candidates independently of Git tracking state."""

import difflib
import hashlib
import json
import shutil
import stat
from pathlib import Path

from pydantic import Field

from agentbenchkit.core.models import Contract
from agentbenchkit.storage.artifacts import write_json

IGNORED = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
MAX_FILE_BYTES = 2_000_000
MAX_TOTAL_BYTES = 20_000_000


class FileEntry(Contract):
    path: str
    sha256: str
    executable: bool


class Candidate(Contract):
    baseline_hash: str
    candidate_hash: str
    files: tuple[FileEntry, ...]
    deleted: tuple[str, ...]
    changed: tuple[str, ...]
    schema_version: int = Field(default=1, ge=1)


def inventory(root: Path) -> dict[str, FileEntry]:
    result: dict[str, FileEntry] = {}
    total = 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in IGNORED for part in relative.parts):
            continue
        if path.is_symlink() or path.is_junction():
            raise ValueError("candidate symlinks/junctions are unsupported")
        if not path.is_file():
            continue
        size = path.stat().st_size
        total += size
        if size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise ValueError("candidate exceeds V0 artifact size limits")
        data = path.read_bytes()
        if b"\x00" in data:
            raise ValueError("binary candidate files are unsupported in V0")
        data.decode("utf-8")
        name = relative.as_posix()
        result[name] = FileEntry(
            path=name,
            sha256=hashlib.sha256(data).hexdigest(),
            executable=bool(path.stat().st_mode & stat.S_IXUSR),
        )
    return result


def tree_hash(files: dict[str, FileEntry]) -> str:
    data = json.dumps([v.model_dump() for _, v in sorted(files.items())], sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()


def collect(baseline: Path, workspace: Path, destination: Path) -> Candidate:
    before, after = inventory(baseline), inventory(workspace)
    destination.mkdir(parents=True, exist_ok=False)
    for name in after:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workspace / name, target)
    if inventory(destination) != after:
        raise ValueError("candidate changed during freeze")
    candidate = Candidate(
        baseline_hash=tree_hash(before),
        candidate_hash=tree_hash(after),
        files=tuple(after.values()),
        deleted=tuple(sorted(before.keys() - after.keys())),
        changed=tuple(name for name in after if before.get(name) != after[name]),
    )
    patch: list[str] = []
    for name in sorted(set(candidate.changed) | set(candidate.deleted)):
        old = (
            (baseline / name).read_text(encoding="utf-8").splitlines(keepends=True)
            if name in before
            else []
        )
        new = (
            (workspace / name).read_text(encoding="utf-8").splitlines(keepends=True)
            if name in after
            else []
        )
        patch.extend(difflib.unified_diff(old, new, fromfile="a/" + name, tofile="b/" + name))
    (destination.parent / "patch.diff").write_text("".join(patch), encoding="utf-8")
    write_json(destination.parent / "candidate_manifest.json", candidate.model_dump())
    return candidate


def restore(baseline: Path, candidate_dir: Path, manifest: Candidate, destination: Path) -> None:
    if tree_hash(inventory(baseline)) != manifest.baseline_hash:
        raise ValueError("baseline hash mismatch")
    candidate_files = inventory(candidate_dir)
    if tree_hash(candidate_files) != manifest.candidate_hash:
        raise ValueError("candidate hash mismatch")
    if {entry.path: entry for entry in manifest.files} != candidate_files:
        raise ValueError("candidate manifest does not match files")
    baseline_files = inventory(baseline)
    if set(manifest.deleted) != baseline_files.keys() - candidate_files.keys():
        raise ValueError("invalid deletion manifest")
    shutil.copytree(baseline, destination)
    for name in manifest.deleted:
        (destination / name).unlink()
    for name in candidate_files:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate_dir / name, target)
    if inventory(destination) != candidate_files:
        raise ValueError("restored workspace differs from frozen candidate")
