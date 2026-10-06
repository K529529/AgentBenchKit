import shutil
from pathlib import Path

import pytest

from agentbenchkit.benchmarks.micro_swe import load_tasks
from agentbenchkit.core.models import TaskSpec
from agentbenchkit.core.status import Verdict
from agentbenchkit.verification.candidate import collect, inventory, restore
from agentbenchkit.verification.verifier import verify_candidate


@pytest.mark.parametrize("task", load_tasks(), ids=lambda task: task.task_id)
@pytest.mark.parametrize("reference", [False, True])
async def test_fixture_positive_and_negative_controls(
    task: TaskSpec,
    reference: bool,
    tmp_path: Path,
) -> None:
    source = task.reference_candidate if reference else task.fixture
    workspace = tmp_path / "agent"
    shutil.copytree(source, workspace)
    manifest = collect(task.fixture, workspace, tmp_path / "candidate")
    result = await verify_candidate(task, tmp_path / "candidate", manifest, tmp_path / "verify")
    assert result.status == (Verdict.PASS if reference else Verdict.FAIL), result
    assert result.tests_executed == 5


def test_candidate_preserves_new_deleted_renamed_files(tmp_path: Path) -> None:
    baseline = tmp_path / "base"
    baseline.mkdir()
    (baseline / "old.py").write_text("x = 1\n")
    workspace = tmp_path / "work"
    shutil.copytree(baseline, workspace)
    (workspace / "old.py").rename(workspace / "renamed.py")
    (workspace / "new.py").write_text("y = 2\n")
    candidate = collect(baseline, workspace, tmp_path / "candidate")
    assert candidate.deleted == ("old.py",)
    assert set(candidate.changed) == {"new.py", "renamed.py"}
    restore(baseline, tmp_path / "candidate", candidate, tmp_path / "restored")
    assert inventory(workspace) == inventory(tmp_path / "restored")


def test_mutated_frozen_candidate_is_rejected(tmp_path: Path) -> None:
    task = load_tasks()[0]
    candidate = collect(task.fixture, task.reference_candidate, tmp_path / "candidate")
    (tmp_path / "candidate" / "bounds.py").write_text("tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        restore(task.fixture, tmp_path / "candidate", candidate, tmp_path / "restored")


async def test_candidate_local_checker_does_not_replace_verifier(tmp_path: Path) -> None:
    task = load_tasks()[0]
    workspace = tmp_path / "agent"
    shutil.copytree(task.fixture, workspace)
    (workspace / "check.py").write_text("raise SystemExit(0)\n")
    candidate = collect(task.fixture, workspace, tmp_path / "candidate")
    result = await verify_candidate(task, tmp_path / "candidate", candidate, tmp_path / "verify")
    assert result.status == Verdict.FAIL


async def test_missing_verifier_report_is_error(tmp_path: Path) -> None:
    task = load_tasks()[0]
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "check.py").write_text("raise SystemExit(0)\n")
    task = task.model_copy(update={"protected_assets": broken})
    candidate = collect(task.fixture, task.reference_candidate, tmp_path / "candidate")
    result = await verify_candidate(task, tmp_path / "candidate", candidate, tmp_path / "verify")
    assert result.status == Verdict.ERROR
