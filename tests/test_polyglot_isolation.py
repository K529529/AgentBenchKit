"""Contracts against the pinned 225-task dataset, with no Agent/model execution."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agentbenchkit.benchmarks.polyglot import REVISION, PolyglotAdapter, copy_solutions
from agentbenchkit.benchmarks.polyglot.isolation import (
    REGIONS,
    VISIBILITY,
    anchor,
    documentation,
    is_doc,
    mask,
    restore_react,
    sha,
    visible_files,
)
from agentbenchkit.storage.artifacts import Redactor
from agentbenchkit.verification.repository import freeze_repository, verified_patch


@pytest.fixture(scope="module")
def dataset() -> Path:
    path = Path(os.environ.get("ABK_POLYGLOT_DATASET", ".agentbenchkit/upstream/polyglot-linux"))
    if not path.is_dir():
        pytest.skip("pinned Polyglot dataset required; CI checks out the fixed revision")
    assert (
        subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
        == REVISION
    )
    for row in PolyglotAdapter().rows.values():
        folder = path / row["path"]
        assert {
            p.relative_to(folder).as_posix(): sha(p.read_bytes())
            for p in folder.rglob("*")
            if p.is_file()
        } == row["files_sha256"]
    return path


@pytest.fixture
def adapter(dataset: Path, monkeypatch: pytest.MonkeyPatch) -> PolyglotAdapter:
    adapter = PolyglotAdapter()
    # File hashes and Git revision are checked by dataset(); evaluator is not
    # needed for materialization. No fake contents substitute for official data.
    monkeypatch.setattr(
        adapter,
        "exercise",
        lambda task: (dataset / adapter.rows[task.task_id]["path"], adapter.rows[task.task_id]),
    )
    return adapter


def test_all_225_materializations_and_scope(adapter: PolyglotAdapter, tmp_path: Path) -> None:
    assert set(VISIBILITY) == adapter.rows.keys()
    undeclared_tests = set()
    approaches = set()
    for task in adapter.load_tasks():
        row = adapter.rows[task.task_id]
        agent, canonical = tmp_path / task.task_id / "agent", tmp_path / task.task_id / "canonical"
        adapter.materialize(task, agent, False)
        adapter.materialize(task, canonical, True)
        observed = {p.relative_to(agent).as_posix() for p in agent.rglob("*") if p.is_file()}
        assert observed == visible_files(task.task_id, row)
        assert set(row["solution_files"]) <= observed
        assert not observed & set(row["test_files"] + row["example_files"])
        for name in row["files_sha256"]:
            reference = name.startswith((".meta/", ".docs/", ".approaches/", ".articles/"))
            extra_test = name.endswith("_test.go") or name.startswith(
                ("src/test/", "tests/", "benches/")
            )
            if name.startswith((".approaches/", ".articles/")):
                approaches.add(task.task_id)
            if reference or extra_test:
                assert name not in observed
            if extra_test and name not in row["test_files"] and not reference:
                undeclared_tests.add((task.task_id, name))
            if not name.startswith((".meta/", ".docs/")) and name not in row["example_files"]:
                assert sha((canonical / name).read_bytes()) == row["files_sha256"][name]
        for name in observed:
            if (task.task_id, name) not in REGIONS:
                assert sha((agent / name).read_bytes()) == row["files_sha256"][name]
            else:
                assert b"```compile_fail" not in (agent / name).read_bytes()
        selected = tmp_path / task.task_id / "selected"
        copy_solutions(agent, selected, row["solution_files"])
        assert {
            p.relative_to(selected).as_posix() for p in selected.rglob("*") if p.is_file()
        } == set(row["solution_files"])
    assert len(approaches) == 11
    assert len(undeclared_tests) == 37
    assert len({task for task, _ in undeclared_tests}) == 24


def test_special_assets_are_problem_inputs(adapter: PolyglotAdapter, tmp_path: Path) -> None:
    for task_id, required in {
        "go--counter": {"impl1.go", "impl2.go", "impl3.go", "impl4.go", "interface.go", "maker.go"},
        "javascript--grep": {
            "data/iliad.txt",
            "data/midsummer-night.txt",
            "data/paradise-lost.txt",
        },
        "java--satellite": {"src/main/java/Node.java", "src/main/java/Tree.java"},
    }.items():
        task = adapter.load_tasks((task_id,))[0]
        target = tmp_path / task_id
        adapter.materialize(task, target, False)
        assert all((target / name).is_file() for name in required)
    assert not (tmp_path / "go--counter/counter_test.go").exists()
    assert not (tmp_path / "java--satellite/src/test").exists()


def react_sources(dataset: Path) -> tuple[bytes, bytes]:
    folder = dataset / "rust/exercises/practice/react"
    pristine = (folder / "src/lib.rs").read_bytes()
    return pristine, mask("rust--react", "src/lib.rs", pristine, sha(pristine))


def gold_agent_view(source: bytes) -> bytes:
    # Test control only: strip the official doc block from the reference impl.
    # Production never makes a reference implementation Agent-visible.
    _, nodes = anchor(source)
    for node in reversed([n for n in nodes if is_doc(n)][2:]):
        source = source[: node.start_byte] + source[node.end_byte :]
    return source


def test_react_roundtrip_preserves_canonical_docs_and_implementation(dataset: Path) -> None:
    pristine, agent = react_sources(dataset)
    assert b"```compile_fail" not in agent
    assert b"should not be mutually assignable" in agent
    assert restore_react(pristine, agent) == pristine
    gold = (dataset / "rust/exercises/practice/react/.meta/example.rs").read_bytes()
    candidate = gold_agent_view(gold)
    assert b"```compile_fail" not in candidate
    assert restore_react(pristine, candidate) == gold
    # Candidate Markdown cannot wrap/hide the restored block.
    injected = candidate.replace(b"/// Values", b"/// ```ignore\n/// Values")
    restored = restore_react(pristine, injected)
    assert documentation(restored) == documentation(pristine)
    assert b"```ignore" not in documentation(restored)
    assert b"HashMap" in restored


@pytest.mark.parametrize(
    "attack", ["delete", "duplicate", "nested", "private", "cfg", "doc", "crate", "macro", "syntax"]
)
def test_react_fails_closed_on_structure_changes(dataset: Path, attack: str) -> None:
    pristine, agent = react_sources(dataset)
    variations = {
        "delete": agent.replace(
            b"pub struct ComputeCellId();", b"pub type ComputeCellId = InputCellId;"
        ),
        "duplicate": agent + b"\npub struct ComputeCellId;\n",
        "nested": b"mod nested {\n" + agent + b"\n}",
        "private": agent.replace(b"pub struct ComputeCellId", b"struct ComputeCellId"),
        "cfg": agent.replace(
            b"pub struct ComputeCellId", b"#[cfg(any())]\npub struct ComputeCellId"
        ),
        "doc": agent.replace(
            b"pub struct ComputeCellId", b"#[doc(hidden)]\npub struct ComputeCellId"
        ),
        "crate": b"#![cfg(any())]\n" + agent,
        "macro": agent.replace(
            b"pub struct ComputeCellId", b"#[derive(Evil)]\npub struct ComputeCellId"
        ),
        "syntax": agent + b" { ",
    }
    with pytest.raises(ValueError):
        restore_react(pristine, variations[attack])


def test_doubly_only_masks_known_doc_regions(dataset: Path) -> None:
    path = dataset / "rust/exercises/practice/doubly-linked-list/src/pre_implemented.rs"
    pristine = path.read_bytes()
    masked = mask("rust--doubly-linked-list", "src/pre_implemented.rs", pristine, sha(pristine))
    assert b"```compile_fail" not in masked
    assert b"pub struct IllegalSend" in masked and b"pub struct IllegalSync" in masked
    assert (
        masked.split(b"// These are tests")[0] == pristine.split(b"// These are tests")[0]
    )
    assert mask("rust--other", "src/pre_implemented.rs", pristine, sha(pristine)) == pristine
    with pytest.raises(ValueError, match="hash"):
        mask("rust--doubly-linked-list", "src/pre_implemented.rs", pristine + b"\n", sha(pristine))


async def test_frozen_react_candidate_restores_tests_and_excludes_support(
    adapter: PolyglotAdapter,
    dataset: Path,
    tmp_path: Path,
) -> None:
    task = adapter.load_tasks(("rust--react",))[0]
    row = adapter.rows[task.task_id]
    workspace = tmp_path / "workspace"
    adapter.materialize(task, workspace, False)
    copy_solutions(workspace, tmp_path / "baseline", row["solution_files"])
    gold = (dataset / row["path"] / ".meta/example.rs").read_bytes()
    (workspace / "src/lib.rs").write_bytes(gold_agent_view(gold))
    (workspace / "tests").mkdir()
    (workspace / "tests/react.rs").write_text("tampered")
    candidate = tmp_path / "sample/candidate"
    await adapter.collect(task, workspace, candidate, Redactor())
    patch = verified_patch(candidate)
    assert "compile_fail" not in patch and "tampered" not in patch
    canonical = tmp_path / "canonical"
    adapter.materialize(task, canonical, True)
    adapter.apply_candidate(task, candidate, canonical, tmp_path)
    assert (canonical / "src/lib.rs").read_bytes() == gold
    assert sha((canonical / "tests/react.rs").read_bytes()) == row["files_sha256"]["tests/react.rs"]
    assert json.loads((tmp_path / "embedded-test-restoration.json").read_text())[
        "candidate_sha256"
    ] == sha((candidate / "src/lib.rs").read_bytes())


@pytest.mark.parametrize("name", ["src/lib.rs", "Cargo.toml"])
def test_react_rejects_deleted_test_host_or_changed_test_manifest(
    adapter: PolyglotAdapter,
    tmp_path: Path,
    name: str,
) -> None:
    task = adapter.load_tasks(("rust--react",))[0]
    baseline, workspace, canonical = [tmp_path / n for n in ("baseline", "workspace", "canonical")]
    adapter.materialize(task, baseline, False)
    shutil.copytree(baseline, workspace)
    if name == "src/lib.rs":
        (workspace / name).unlink()
    else:
        (workspace / name).write_text(
            '[package]\nname="react"\nversion="0.0.0"\n[lib]\ndoctest=false\n'
        )
    candidate = tmp_path / "sample/candidate"
    freeze_repository(baseline, workspace, candidate, tmp_path / "scratch", Redactor())
    adapter.materialize(task, canonical, True)
    with pytest.raises(ValueError, match="protected"):
        adapter.apply_candidate(task, candidate, canonical, tmp_path)


@pytest.mark.parametrize("visibility", ["pub(crate)", "pub(super)", "pub(in crate)", "crate", ""])
def test_react_rejects_restricted_or_private_visibility(dataset: Path, visibility: str) -> None:
    pristine, agent = react_sources(dataset)
    candidate = agent.replace(
        b"pub struct ComputeCellId", f"{visibility} struct ComputeCellId".encode()
    )
    with pytest.raises(ValueError):
        restore_react(pristine, candidate)
