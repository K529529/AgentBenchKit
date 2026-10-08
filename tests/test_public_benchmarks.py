import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentbenchkit.benchmarks.featurebench import FeatureBenchAdapter, official_verdict
from agentbenchkit.benchmarks.registry import make_config
from agentbenchkit.cli import app
from agentbenchkit.storage.artifacts import Redactor
from agentbenchkit.verification.repository import freeze_repository, verified_patch


def test_featurebench_full_discovery_and_frozen_selection() -> None:
    tasks = FeatureBenchAdapter().load_tasks()
    assert len(tasks) == len({t.task_id for t in tasks}) == 100
    assert all(t.task_id.endswith(".lv1") for t in tasks)
    assert "fixture" not in tasks[0].model_dump()
    with pytest.raises(ValueError, match="image pins"):
        FeatureBenchAdapter(image_pins={"unknown": "mutable:latest"})
    with pytest.raises(ValueError):
        FeatureBenchAdapter().load_tasks(("missing",))
    config = make_config("featurebench", (), all_tasks=True)
    assert len(config.task_ids) == 100
    frozen = make_config(
        "featurebench", (), evalset=Path("examples/evalsets/featurebench-fast-evalset-v1.json")
    )
    assert len(frozen.task_ids) == 16
    source = json.loads(
        Path("examples/evalsets/featurebench-fast-evalset-v1.json").read_text(encoding="utf-8")
    )
    assert frozen.task_ids == tuple(source["task_ids"])
    assert len(frozen.image_pins) == 8
    assert all("@sha256:" in value for value in frozen.image_pins.values())
    assert len(FeatureBenchAdapter(image_pins=frozen.image_pins).load_tasks(frozen.task_ids)) == 16


def test_public_config_generation_never_runs_tasks(tmp_path: Path) -> None:
    target = tmp_path / "plan.json"
    result = CliRunner().invoke(
        app, ["make-config", "featurebench", "--all-tasks", "--output", str(target)]
    )
    assert result.exit_code == 0, result.output
    assert len(json.loads(target.read_text())["task_ids"]) == 100
    assert (
        CliRunner()
        .invoke(app, ["make-config", "featurebench", "--output", str(tmp_path / "empty.json")])
        .exit_code
        != 0
    )


@pytest.mark.parametrize("resolved,expected", [(True, "PASS"), (False, "FAIL")])
def test_only_completed_official_verdict_is_authoritative(resolved: bool, expected: str) -> None:
    data = {
        "completed": True,
        "report": {
            "task": {
                "resolved": resolved,
                "featurebench_eval_completed": True,
                "tests_status": {"FAIL_TO_PASS": {"success": [], "failure": []}},
            }
        },
    }
    # Do not re-grade upstream's test lists or reinterpret its resolved field.
    assert official_verdict("task", data).status == expected
    data["completed"] = False
    assert official_verdict("task", data).status == "ERROR"
    assert official_verdict("task", {}).status == "ERROR"


def test_repository_patch_includes_untracked_binary_and_deletion(tmp_path: Path) -> None:
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (before / "gone.py").write_text("old=1\n")
    (before / "changed.py").write_text("x=1\n")
    (after / "changed.py").write_text("x=2\n")
    (after / "new.bin").write_bytes(b"\x00binary\x00")
    # Candidate-owned Git metadata is deliberately not consulted.
    (after / ".git").mkdir()
    (after / ".git/config").write_text("invalid malicious config")
    dest = tmp_path / "sample/candidate"
    freeze_repository(before, after, dest, tmp_path / "collector", Redactor())
    patch = verified_patch(dest)
    assert "GIT binary patch" in patch and "+x=2" in patch
    manifest = json.loads((dest.parent / "candidate_manifest.json").read_text())
    assert manifest["deleted"] == ["gone.py"]
    assert set(manifest["changed"]) == {"new.bin", "changed.py"}
    (dest / "new.bin").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        verified_patch(dest)


def test_repository_credentials_refused_before_freeze(tmp_path: Path) -> None:
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (after / "leak.bin").write_bytes(b"\x00synthetic-key")
    dest = tmp_path / "sample/candidate"
    with pytest.raises(ValueError, match="credential"):
        freeze_repository(before, after, dest, tmp_path / "collector", Redactor(("synthetic-key",)))
    assert not dest.exists()


def test_swe_lite_discovery_selection_and_official_results() -> None:
    from agentbenchkit.benchmarks.swebench import SweBenchAdapter
    from agentbenchkit.benchmarks.swebench import official_verdict as swe_verdict

    tasks = SweBenchAdapter().load_tasks()
    assert len(tasks) == len({t.task_id for t in tasks}) == 300
    assert len(make_config("swe-bench-lite", (), all_tasks=True).task_ids) == 300
    ids = (tasks[-1].task_id, tasks[0].task_id)
    assert tuple(t.task_id for t in SweBenchAdapter().load_tasks(ids)) == ids
    with pytest.raises(ValueError):
        SweBenchAdapter().load_tasks(("unknown",))
    assert (
        swe_verdict("x", {"completed": True, "report": {"x": {"resolved": False}}}).status == "FAIL"
    )
    assert (
        swe_verdict("x", {"completed": True, "report": {"x": {"resolved": True}}}).status == "PASS"
    )
    for report in (None, "bad", {}, {"x": {"resolved": "yes"}}):
        assert swe_verdict("x", {"completed": True, "report": report}).status == "ERROR"
    assert (
        swe_verdict("x", {"completed": False, "report": {"x": {"resolved": True}}}).status
        == "ERROR"
    )


def test_polyglot_full_catalog_and_single_round_conditions() -> None:
    from collections import Counter

    from agentbenchkit.benchmarks.polyglot import PolyglotAdapter

    tasks = PolyglotAdapter().load_tasks()
    assert len(tasks) == len({t.task_id for t in tasks}) == 225
    assert Counter(t.tags[0] for t in tasks) == {
        "cpp": 26,
        "go": 39,
        "java": 47,
        "javascript": 49,
        "python": 34,
        "rust": 30,
    }
    assert all(t.metadata["official_two_round_comparable"] is False for t in tasks)
    assert len(make_config("aider-polyglot", (), all_tasks=True).task_ids) == 225
    with pytest.raises(ValueError):
        PolyglotAdapter().load_tasks(("unknown",))


def test_polyglot_hides_tests_and_reference_but_restores_verifier_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agentbenchkit.benchmarks.polyglot import PolyglotAdapter

    original = tmp_path / "original"
    original.mkdir()
    files = {
        "solution.py": "pass",
        "official_test.py": "assert False",
        "build.cfg": "trusted",
        ".meta/example.py": "gold",
        ".docs/instructions.md": "prompt",
    }
    for name, content in files.items():
        p = original / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    adapter = PolyglotAdapter()
    task = adapter.load_tasks()[0]
    from agentbenchkit.benchmarks.polyglot.isolation import VISIBILITY

    monkeypatch.setitem(
        VISIBILITY,
        task.task_id,
        {"support_files": ["build.cfg"]},
    )
    row = {
        "solution_files": ["solution.py"],
        "example_files": [".meta/example.py"],
        "test_files": ["official_test.py"],
        "files_sha256": files,
    }
    monkeypatch.setattr(adapter, "exercise", lambda task: (original, row))
    agent, verifier = tmp_path / "agent", tmp_path / "verifier"
    adapter.materialize(task, agent, False)
    adapter.materialize(task, verifier, True)
    assert {p.name for p in agent.iterdir()} == {"solution.py", "build.cfg"}
    assert (verifier / "official_test.py").read_text() == "assert False"
    assert not (verifier / ".meta").exists()


def test_polyglot_official_function_loader_does_not_import_agent_clients(tmp_path: Path) -> None:
    from agentbenchkit.benchmarks.polyglot.worker import official_functions

    source = tmp_path / "upstream.py"
    source.write_text(
        "raise RuntimeError('model stack must not import')\n"
        "def run_unit_tests():\n return 'official failure'\n"
        "def cleanup_test_output(value):\n return value\n"
    )
    assert official_functions(source)["run_unit_tests"]() == "official failure"


@pytest.mark.asyncio
async def test_polyglot_candidate_excludes_build_and_test_edits(tmp_path: Path) -> None:
    from agentbenchkit.benchmarks.polyglot import PolyglotAdapter
    from agentbenchkit.storage.artifacts import Redactor
    from agentbenchkit.verification.repository import verified_patch

    adapter = PolyglotAdapter()
    task = adapter.load_tasks(("python--affine-cipher",))[0]
    baseline, workspace = tmp_path / "baseline", tmp_path / "workspace"
    baseline.mkdir()
    workspace.mkdir()
    name = adapter.rows[task.task_id]["solution_files"][0]
    (baseline / name).write_text("pass\n")
    (workspace / name).write_text("answer = 42\n")
    (workspace / "official_test.py").write_text("assert True\n")
    (workspace / "build.cfg").write_text("malicious\n")
    candidate = tmp_path / "sample/candidate"
    await adapter.collect(task, workspace, candidate, Redactor())
    patch = verified_patch(candidate)
    assert "+answer = 42" in patch
    assert "official_test.py" not in patch and "build.cfg" not in patch


@pytest.mark.parametrize("jest", [None, "30.5.2", "29.7.0"])
def test_polyglot_refuses_incompatible_jest_image(
    monkeypatch: pytest.MonkeyPatch, jest: str | None
) -> None:
    from agentbenchkit.benchmarks.polyglot import EVALUATOR, PolyglotAdapter

    labels = {"agentbenchkit.aider.commit": EVALUATOR}
    if jest:
        labels["agentbenchkit.polyglot.jest"] = jest
    image = [{"Id": "sha256:fixed", "Config": {"Labels": labels}}]
    monkeypatch.setattr("subprocess.check_output", lambda *args, **kwargs: json.dumps(image))
    adapter = PolyglotAdapter(agent_image="test-image")
    if jest == "29.7.0":
        assert adapter.resolve_image() == "sha256:fixed"
    else:
        with pytest.raises(ValueError, match="Jest 29.7.0"):
            adapter.resolve_image()


def test_frozen_featurebench_evalset_bytes() -> None:
    import hashlib

    path = Path("examples/evalsets/featurebench-fast-evalset-v1.json")
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "41956101f6380708b8e6939e146d1d98ed94e0463c54e326eecea54dbf827bfc"
    )
