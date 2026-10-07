import json
import sys
from pathlib import Path

import pytest

from agentbenchkit.benchmarks.micro_swe import load_tasks
from agentbenchkit.core.models import CommandSpec, LocalTaskSpec, TaskSpec
from agentbenchkit.harnesses.nexus import NexusHarness
from agentbenchkit.runtime.runner import evaluate


class ControlledHarness(NexusHarness):
    name = "controlled-fixture"

    def __init__(self, repair: bool) -> None:
        super().__init__(Path(sys.executable))
        self.repair = repair

    def command(self, task: TaskSpec) -> CommandSpec:
        script = "import json,shutil; "
        if self.repair:
            assert isinstance(task, LocalTaskSpec)
            script += f"shutil.copytree({str(task.reference_candidate)!r},'.',dirs_exist_ok=True); "
        script += "print(json.dumps({'kind':'run_finished','data':{'outcome':'completed'}}))"
        return CommandSpec(argv=(sys.executable, "-c", script))


@pytest.mark.parametrize("repair", [False, True])
async def test_full_controlled_pipeline_keeps_completion_separate(
    repair: bool,
    tmp_path: Path,
) -> None:
    run_dir = await evaluate(
        load_tasks(("clamp", "stable_unique")), ControlledHarness(repair), tmp_path
    )
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["samples_planned"] == 2
    assert summary["end_to_end_success_rate"] == int(repair)
    assert summary["coverage_rate"] == 1
    for sample_path in run_dir.glob("tasks/*/*/sample.json"):
        sample = json.loads(sample_path.read_text())
        assert sample["agent_outcome"] == "COMPLETED"
        assert sample["candidate_pass"] is repair
        assert sample["sample_success"] is repair
        assert sample["cleanup_status"] == "COMPLETED"
        assert list(sample_path.parent.glob("executions/*/trajectory.jsonl"))
    assert not list((run_dir / "work").glob("*"))
