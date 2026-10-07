import json
from pathlib import Path

from test_runtime import ControlledHarness

from agentbenchkit.benchmarks.micro_swe import MicroSweAdapter
from agentbenchkit.core.models import TaskSpec, VerificationResult
from agentbenchkit.core.protocols import BenchmarkAdapter, Environment
from agentbenchkit.core.status import Verdict
from agentbenchkit.runtime.runner import evaluate
from agentbenchkit.storage.artifacts import Redactor


async def test_adapter_owns_preparation_collection_and_correctness(tmp_path: Path) -> None:
    calls: list[str] = []

    class ExternalAdapter(MicroSweAdapter):
        name = "external-contract-v1"

        async def prepare(self, task: TaskSpec, workspace: Path) -> None:
            calls.append("prepare")
            await super().prepare(task, workspace)

        async def collect(
            self, task: TaskSpec, workspace: Path, destination: Path, redactor: Redactor
        ) -> None:
            calls.append("collect")
            await super().collect(task, workspace, destination, redactor)

        async def verify(
            self, task: TaskSpec, candidate_dir: Path, directory: Path,
            environment: Environment | None,
        ) -> VerificationResult:
            calls.append("verify")
            assert (candidate_dir.parent / "candidate_manifest.json").is_file()
            # A completed Agent must not override the benchmark's independent verdict.
            return VerificationResult(status=Verdict.FAIL, reason="external evaluator verdict")

    adapter: BenchmarkAdapter = ExternalAdapter()
    run = await evaluate(
        adapter.load_tasks(("clamp",)), ControlledHarness(True), tmp_path, benchmark=adapter
    )
    assert calls == ["prepare", "collect", "verify"]
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["benchmark"] == "external-contract-v1"
    sample = json.loads(next(run.glob("tasks/*/*/sample.json")).read_text())
    assert sample["execution_status"] == "FINISHED"
    assert sample["agent_outcome"] == "COMPLETED"
    assert sample["candidate_pass"] is False
    assert sample["sample_success"] is False
