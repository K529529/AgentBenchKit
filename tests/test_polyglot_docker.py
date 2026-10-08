"""Opt-in free controls: official tests/reference solutions, never model calls."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from test_polyglot_isolation import gold_agent_view

from agentbenchkit.benchmarks.polyglot import PolyglotAdapter
from agentbenchkit.benchmarks.polyglot.isolation import documentation, sha
from agentbenchkit.runtime.recovery import cleanup_resources
from agentbenchkit.storage.artifacts import Redactor

pytestmark = pytest.mark.skipif(
    os.environ.get("ABK_TEST_POLYGLOT_DOCKER") != "1" or sys.platform == "win32",
    reason="opt-in Linux Docker controls; no inference",
)
ROOT = Path(__file__).resolve().parents[1]
IMAGE = os.environ.get("ABK_POLYGLOT_IMAGE", "abk-polyglot-nexus:v0.2.0")


def cargo(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--user",
            str(os.getuid()) if hasattr(os, "getuid") else "1000",
            "--memory=2g",
            "--cpus=2",
            "--mount",
            f"type=bind,src={workspace},dst=/testbed",
            "--workdir",
            "/testbed",
            "--entrypoint",
            "cargo",
            IMAGE,
            *args,
        ],
        text=True,
        capture_output=True,
        timeout=120,
    )


@pytest.mark.parametrize(
    "task_id",
    [
        "rust--react",
        "rust--doubly-linked-list",
        "python--affine-cipher",
        "javascript--affine-cipher",
    ],
)
@pytest.mark.parametrize("variant", ["starter", "gold"])
async def test_official_free_controls(tmp_path: Path, task_id: str, variant: str) -> None:
    adapter = PolyglotAdapter(
        ROOT / ".agentbenchkit/upstream/polyglot-linux",
        ROOT / ".agentbenchkit/upstream/aider-linux",
        IMAGE,
    )
    task = adapter.load_tasks((task_id,))[0]
    row = adapter.rows[task_id]
    workspace = tmp_path / "work/workspace"
    await adapter.prepare(task, workspace, tmp_path / "prepare")
    assert adapter.dataset is not None
    pristine = adapter.dataset / row["path"]
    if variant == "gold":
        gold = (pristine / row["example_files"][0]).read_bytes()
        target = workspace / row["solution_files"][0]
        target.write_bytes(gold_agent_view(gold) if task_id == "rust--react" else gold)
    if task_id.startswith("rust--"):
        build = cargo(workspace, "check", "--offline")
        (tmp_path / "agent-build.log").write_text(build.stdout + build.stderr)
        assert build.returncode == 0, build.stderr
        assert b"```compile_fail" not in (workspace / "src/lib.rs").read_bytes()
    if task_id == "rust--doubly-linked-list":
        # A changed helper must never enter the solution candidate.
        (workspace / "src/pre_implemented.rs").write_text("malicious helper change")
    candidate = tmp_path / "sample/candidate"
    await adapter.collect(task, workspace, candidate, Redactor())
    manifest = json.loads((candidate.parent / "candidate_manifest.json").read_text())
    assert set(manifest["changed"]) <= set(row["solution_files"])
    try:
        result = await adapter.verify(task, candidate, tmp_path / "work/verify", None)
        assert result.status == ("PASS" if variant == "gold" else "FAIL"), result
        canonical = tmp_path / "work/verify/workspace" / row["path"]
        if task_id == "rust--react":
            assert documentation((canonical / "src/lib.rs").read_bytes()) == documentation(
                (pristine / "src/lib.rs").read_bytes()
            )
            if variant == "gold":
                tested = cargo(canonical, "test", "--offline", "--doc")
                (tmp_path / "react-doctests.log").write_text(tested.stdout + tested.stderr)
                assert tested.returncode == 0 and "2 passed" in tested.stdout
                # Deliberately collapse InputCellId into ComputeCellId: both
                # original compile_fail examples must now fail (they compile).
                bad = tmp_path / "bad-react"
                shutil.copytree(canonical, bad, ignore=shutil.ignore_patterns("target"))
                source = (bad / "src/lib.rs").read_bytes()
                from agentbenchkit.benchmarks.polyglot.isolation import rust_tree

                nodes = rust_tree(source).named_children
                item = next(
                    n
                    for n in nodes
                    if n.type == "struct_item"
                    and (name := n.child_by_field_name("name")) is not None
                    and name.text == b"InputCellId"
                )
                attr = nodes[nodes.index(item) - 1]
                source = (
                    source[: attr.start_byte]
                    + b"pub use ComputeCellId as InputCellId;"
                    + source[item.end_byte :]
                )
                (bad / "src/lib.rs").write_bytes(source)
                rejected = cargo(bad, "test", "--offline", "--doc")
                (tmp_path / "react-negative-doctests.log").write_text(
                    rejected.stdout + rejected.stderr
                )
                assert rejected.returncode != 0 and "2 failed" in rejected.stdout
        elif task_id == "rust--doubly-linked-list":
            helper = "src/pre_implemented.rs"
            assert sha((canonical / helper).read_bytes()) == row["files_sha256"][helper]
            if variant == "gold":
                tested = cargo(canonical, "test", "--offline", "--features", "advanced")
                (tmp_path / "doubly-advanced.log").write_text(tested.stdout + tested.stderr)
                assert tested.returncode == 0, tested.stdout + tested.stderr
                assert "2 passed" in tested.stdout and "compile fail" in tested.stdout
    finally:
        assert not await cleanup_resources(tmp_path / "work")
