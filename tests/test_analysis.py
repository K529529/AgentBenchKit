import json
from pathlib import Path

from test_runtime import ControlledHarness

from agentbenchkit.analysis.compare import compare
from agentbenchkit.analysis.replay import evidence_hash, metrics, replay
from agentbenchkit.benchmarks.micro_swe import load_tasks
from agentbenchkit.runtime.runner import evaluate


async def test_replay_is_versioned_and_does_not_change_evidence(tmp_path: Path) -> None:
    directory = await evaluate(load_tasks(("clamp",)), ControlledHarness(False), tmp_path)
    before = evidence_hash(directory)
    first, second = replay(tmp_path, directory.name), replay(tmp_path, directory.name)
    assert first != second and first.exists() and second.exists()
    a, b = json.loads(first.read_text()), json.loads(second.read_text())
    assert a["input_evidence_hash"] == b["input_evidence_hash"] == before
    assert evidence_hash(directory) == before
    failure = a["samples"][0]["failure"]
    assert "TEST_FAILURE" in failure["observations"]
    assert "NO_MUTATION" in failure["observations"]
    assert failure["suspected_owner"] == "AGENT"
    assert failure["confidence"] < 1
    assert failure["evidence_refs"]


def test_unobserved_metrics_are_null_not_zero() -> None:
    result = metrics([], {"tool_calls": False, "model_usage": False}, False)
    for key in ("tool_calls", "steps", "model_calls", "input_tokens", "output_tokens", "cost"):
        assert result[key] is None


async def test_compare_surfaces_confounds_and_observed_change(tmp_path: Path) -> None:
    tasks = load_tasks(("clamp",))
    first = await evaluate(tasks, ControlledHarness(False), tmp_path)
    second = await evaluate(tasks, ControlledHarness(True), tmp_path)
    result = compare(tmp_path, first.name, second.name)
    assert result["tasks"]["clamp"]["status"] == "IMPROVED"
    manifest_path = second / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["concurrency"] = 2
    manifest_path.write_text(json.dumps(manifest))
    result = compare(tmp_path, first.name, second.name)
    assert "concurrency" in result["comparability_warnings"]
    assert result["tasks"]["clamp"]["status"] == "INCONCLUSIVE"


async def test_compare_model_conditions_and_smoke_cannot_be_waived(tmp_path: Path) -> None:
    from test_model_spec import model

    tasks = load_tasks(("clamp",))
    first = await evaluate(tasks, ControlledHarness(True), tmp_path)
    second = await evaluate(tasks, ControlledHarness(True), tmp_path)
    for directory in (first, second):
        path = directory / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["model"] = model().model_dump()
        manifest["requested_model"] = model().model_dump()
        manifest["agent_config"] = {"evaluation_class": "subscription_smoke"}
        if directory == second:
            manifest["model"]["model_id"] = "different-model"
        path.write_text(json.dumps(manifest))
    result = compare(tmp_path, first.name, second.name, ("model",))
    assert "model" in result["changed_conditions"]
    assert not result["formal_comparable"]
    assert any("not an explicit API" in item for item in result["comparability_warnings"])
    assert any("unspecified controls" in item for item in result["comparability_warnings"])


async def test_missing_sample_keeps_planned_denominator_and_compare_unknown(tmp_path: Path) -> None:
    directory = await evaluate(load_tasks(("clamp",)), ControlledHarness(True), tmp_path)
    next(directory.glob("tasks/*/*/sample.json")).unlink()
    result = json.loads(replay(tmp_path, directory.name).read_text())
    assert result["status"] == "PARTIAL"
    assert result["summary"]["samples_planned"] == 1
    assert result["samples"][0]["sample_success"] is None
    compared = compare(tmp_path, directory.name, directory.name)
    assert compared["tasks"]["clamp"]["status"] == "INCONCLUSIVE"
