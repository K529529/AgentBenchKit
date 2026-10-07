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
