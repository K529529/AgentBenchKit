import asyncio
import json
from pathlib import Path

import pytest
from test_runtime import ControlledHarness

from agentbenchkit.benchmarks.micro_swe import load_tasks
from agentbenchkit.core.models import SampleResult
from agentbenchkit.core.protocols import StartupError
from agentbenchkit.core.status import ExecutionStatus
from agentbenchkit.environments.host import HostProcessEnvironment, HostSession
from agentbenchkit.runtime.recovery import RunLease, recover
from agentbenchkit.runtime.runner import evaluate, evaluate_sample
from agentbenchkit.storage.artifacts import write_json


class FlakyEnvironment(HostProcessEnvironment):
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    async def create(self, workspace: Path, execution_id: str) -> HostSession:
        self.calls += 1
        if self.calls <= self.failures:
            raise StartupError("injected infrastructure failure")
        return await super().create(workspace, execution_id)


@pytest.mark.parametrize("failures,expected", [(1, True), (9, False)])
async def test_startup_retries_preserve_physical_executions(
    tmp_path: Path, failures: int, expected: bool
) -> None:
    task = load_tasks()[0]
    env = FlakyEnvironment(failures)
    result = await evaluate_sample(
        "run", task, "sample", ControlledHarness(True), tmp_path, environment=env, startup_retries=1
    )
    assert result.sample_success is expected
    executions = await asyncio.to_thread(
        lambda: list(tmp_path.glob("tasks/*/*/executions/*/execution.json"))
    )
    assert len(executions) == 2
    records = [json.loads(p.read_text()) for p in executions]
    assert sum(r["agent_started"] for r in records) == int(expected)
    assert len({r["physical_execution_id"] for r in records}) == 2


async def test_cleanup_fault_preserves_verified_success(tmp_path: Path) -> None:
    class BrokenCleanup(HostSession):
        async def close(self) -> None:
            await super().close()
            raise RuntimeError("injected post-verification cleanup failure")

    class Provider(HostProcessEnvironment):
        async def create(self, workspace: Path, execution_id: str) -> HostSession:
            return BrokenCleanup(workspace)

    result = await evaluate_sample(
        "run", load_tasks()[0], "sample", ControlledHarness(True), tmp_path, environment=Provider()
    )
    assert result.sample_success is True
    assert result.cleanup_status == "ERROR"


async def test_cancellation_preserves_planned_denominator(tmp_path: Path) -> None:
    started = asyncio.Event()

    class SlowProvider(HostProcessEnvironment):
        async def create(self, workspace: Path, execution_id: str) -> HostSession:
            started.set()
            await asyncio.sleep(30)
            return HostSession(workspace)

    future = asyncio.create_task(
        evaluate(
            load_tasks(("clamp", "stable_unique")),
            ControlledHarness(True),
            tmp_path,
            samples=3,
            concurrency=2,
            environment=SlowProvider(),
        )
    )
    await started.wait()
    future.cancel()
    directory = await future
    summary = json.loads((directory / "summary.json").read_text())
    assert summary["samples_planned"] == 6
    assert summary["samples_successful"] == 0
    assert len(list(directory.glob("tasks/*/*/sample.json"))) == 6


async def test_recovery_respects_live_lease_and_marks_abandoned(tmp_path: Path) -> None:
    run = tmp_path / "abandoned"
    run.mkdir()
    item = SampleResult(
        sample_id="sample", task_id="task", execution_status=ExecutionStatus.PENDING
    )
    write_json(run / "manifest.json", {"k": 1})
    write_json(run / "plan.json", [item.model_dump()])
    write_json(run / "run_state.json", {"status": "RUNNING"})
    lease = RunLease(run)
    assert lease.acquire()
    assert await recover(tmp_path) == []
    lease.close()
    assert await recover(tmp_path) == ["abandoned"]
    sample = json.loads((run / "tasks/task/sample/sample.json").read_text())
    assert sample["execution_status"] == "INTERRUPTED"
    assert sample["sample_success"] is None
    assert json.loads((run / "summary.json").read_text())["samples_planned"] == 1


async def test_no_hidden_retry_after_agent_started(tmp_path: Path) -> None:
    import sys

    from agentbenchkit.core.models import CommandSpec, TaskSpec

    class BrokenHarness(ControlledHarness):
        def command(self, task: TaskSpec) -> CommandSpec:
            return CommandSpec(argv=(sys.executable, "-c", "raise RuntimeError('agent failure')"))

    result = await evaluate_sample(
        "run", load_tasks()[0], "sample", BrokenHarness(False), tmp_path, startup_retries=3
    )
    assert result.sample_success is None  # missing protocol outcome, not fabricated FAILED
    executions = await asyncio.to_thread(
        lambda: list(tmp_path.glob("tasks/*/*/executions/*/execution.json"))
    )
    assert len(executions) == 1


async def test_bounded_concurrency(tmp_path: Path) -> None:
    active = peak = 0

    class Counted(HostProcessEnvironment):
        async def create(self, workspace: Path, execution_id: str) -> HostSession:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.05)
            active -= 1
            return HostSession(workspace)

    await evaluate(
        load_tasks(("clamp", "stable_unique")),
        ControlledHarness(False),
        tmp_path,
        samples=3,
        concurrency=2,
        environment=Counted(),
    )
    assert peak == 2


async def test_prepare_timeout_exhausts_before_agent(tmp_path: Path) -> None:
    class Slow(HostProcessEnvironment):
        async def create(self, workspace: Path, execution_id: str) -> HostSession:
            await asyncio.sleep(30)
            return HostSession(workspace)

    task = load_tasks()[0]
    task = task.model_copy(update={"timeouts": task.timeouts.model_copy(update={"prepare": 0.02})})
    result = await evaluate_sample(
        "run",
        task,
        "sample",
        ControlledHarness(True),
        tmp_path,
        environment=Slow(),
        startup_retries=0,
    )
    assert result.startup_retries_exhausted
    assert result.sample_success is False
    assert result.agent_outcome == "UNKNOWN"


async def test_recovery_overrides_stale_startup_result_when_retry_was_running(
    tmp_path: Path,
) -> None:
    run = tmp_path / "retry-interrupted"
    item = SampleResult(
        sample_id="sample", task_id="task", execution_status=ExecutionStatus.PENDING
    )
    write_json(run / "manifest.json", {"k": 1})
    write_json(run / "plan.json", [item.model_dump()])
    write_json(run / "run_state.json", {"status": "RUNNING"})
    folder = run / "tasks/task/sample"
    write_json(
        folder / "sample.json",
        item.model_copy(update={"execution_status": ExecutionStatus.ERROR}).model_dump(),
    )
    write_json(folder / "executions/retry/execution.json", {"execution_status": "RUNNING"})
    assert await recover(tmp_path) == [run.name]
    assert json.loads((folder / "sample.json").read_text())["execution_status"] == "INTERRUPTED"


async def test_cancel_during_docker_create_adopts_and_removes_resource(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agentbenchkit.environments import docker as module

    entered, finish = asyncio.Event(), asyncio.Event()
    commands = []

    async def fake_docker(*args: str, **kwargs: object) -> str:
        commands.append(args[0])
        if args[0] == "create":
            entered.set()
            await finish.wait()
        if args[0] == "inspect":
            return '{"Running":false}'
        return ""

    monkeypatch.setattr(module, "docker", fake_docker)
    session = module.DockerSession(tmp_path, "test-image")
    pending = asyncio.create_task(session.prepare())
    await entered.wait()
    pending.cancel()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert "rm" in commands and session.name is None
