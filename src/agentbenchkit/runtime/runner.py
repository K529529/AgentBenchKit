"""First real vertical slice. Evidence survives Agent and verifier failures."""

import asyncio
import platform
import shutil
import time
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from agentbenchkit import __version__
from agentbenchkit.benchmarks.micro_swe import MicroSweAdapter
from agentbenchkit.core.events import Event
from agentbenchkit.core.metrics import summarize
from agentbenchkit.core.models import ResolvedManifest, SampleResult, TaskSpec, VerificationResult
from agentbenchkit.core.protocols import BenchmarkAdapter, Environment, Harness, StartupError
from agentbenchkit.core.status import AgentOutcome, AuxiliaryStatus, ExecutionStatus, Verdict
from agentbenchkit.environments.docker import DockerEnvironment
from agentbenchkit.environments.host import HostProcessEnvironment
from agentbenchkit.runtime.manifest import agent_identity, runtime_identity
from agentbenchkit.runtime.recovery import RunLease, cleanup_resources, recover
from agentbenchkit.runtime.settings import AgentSettings
from agentbenchkit.storage.artifacts import Redactor, StreamRedactor, write_json
from agentbenchkit.storage.index import index_run

NORMALIZED = {
    "run_started": "agent_started",
    "run_finished": "agent_finished",
    "model_started": "model_call_started",
    "model_finished": "model_call_finished",
    "tool_started": "tool_call_started",
    "tool_finished": "tool_call_finished",
}


def now() -> str:
    return datetime.now(UTC).isoformat()


def remove_work(path: Path, root: Path) -> None:
    resolved = path.resolve()
    if resolved == root.resolve() or not resolved.is_relative_to(root.resolve()):
        raise ValueError("refusing cleanup outside the run work directory")
    if path.is_symlink() or path.is_junction():
        raise ValueError("refusing cleanup of a linked workspace")
    shutil.rmtree(path)


async def evaluate_attempt(
    run_id: str,
    task: TaskSpec,
    sample_id: str,
    harness: Harness,
    run_dir: Path,
    settings: AgentSettings | None = None,
    environment: Environment | None = None,
    final_attempt: bool = True,
    benchmark: BenchmarkAdapter | None = None,
) -> tuple[SampleResult, bool]:
    benchmark = benchmark or MicroSweAdapter()
    sample_dir = run_dir / "tasks" / task.task_id / sample_id
    execution_id = uuid.uuid4().hex
    execution_dir = sample_dir / "executions" / execution_id
    execution_dir.mkdir(parents=True)
    work_root = run_dir / "work"
    work = work_root / execution_id
    workspace = work / "workspace"
    redactor = settings.redactor if settings else Redactor()
    outcome = AgentOutcome.UNKNOWN
    status = ExecutionStatus.PREPARING
    cleanup = AuxiliaryStatus.NOT_RUN
    frozen = False
    verification = VerificationResult()
    errors: list[str] = []
    session = None
    started = time.monotonic()
    native_events: list[dict[str, JsonValue]] = []
    process_data: dict[str, Any] = {}
    seq = 0
    deadline_phase: str | None = None
    phase = "PREPARE"
    startup_failure = False
    agent_started = False
    verifier_cleanup_error = False

    def budget(seconds: float) -> float:
        remaining = seconds
        if task.timeouts.overall is not None:
            remaining = min(remaining, task.timeouts.overall - (time.monotonic() - started))
        if remaining <= 0:
            raise TimeoutError(f"overall deadline reached during {phase}")
        return remaining

    def checkpoint() -> None:
        write_json(
            execution_dir / "execution.json",
            {
                "physical_execution_id": execution_id,
                "sample_id": sample_id,
                "task_id": task.task_id,
                "run_id": run_id,
                "execution_status": status,
                "started_at": start_time,
                "errors": errors,
                "phase": phase,
                "agent_started": agent_started,
            },
            redactor,
        )

    start_time = now()
    checkpoint()
    try:
        async with asyncio.timeout(budget(task.timeouts.prepare)):
            prepared_environment = await benchmark.prepare(
                task, workspace, execution_dir / "prepare"
            )
            env = settings.prepare(work / "agent_home") if settings else {}
            provider = prepared_environment or environment or HostProcessEnvironment()
            if isinstance(provider, DockerEnvironment):
                write_json(execution_dir / "environment.json", await provider.resolve(), redactor)
            session = await provider.create(workspace, execution_id)
            setup_streams = {name: StreamRedactor(redactor) for name in ("stdout", "stderr")}

            async def setup_sink(stream: str, text: str) -> None:
                with (execution_dir / f"setup-{stream}.log").open("a", encoding="utf-8") as log:
                    log.write(setup_streams[stream].feed(text))

            for command in task.setup:
                setup_streams = {name: StreamRedactor(redactor) for name in ("stdout", "stderr")}
                setup_result = await session.execute(command, setup_sink)
                for name, stream_redactor in setup_streams.items():
                    with (execution_dir / f"setup-{name}.log").open("a", encoding="utf-8") as log:
                        log.write(stream_redactor.feed("", final=True))
                if setup_result.returncode != 0 or setup_result.timed_out:
                    raise StartupError("fixture setup failed")
        phase = "AGENT"
        command = harness.command(task).model_copy(
            update={"timeout_seconds": budget(task.timeouts.agent)}
        )
        agent_started = True
        status = ExecutionStatus.RUNNING
        checkpoint()
        streams = {name: StreamRedactor(redactor) for name in ("stdout", "stderr")}
        line_buffer = ""
        parse_errors = 0
        with (
            (execution_dir / "stdout.log").open("w", encoding="utf-8") as stdout,
            (execution_dir / "stderr.log").open("w", encoding="utf-8") as stderr,
            (execution_dir / "trajectory.jsonl").open("w", encoding="utf-8") as trajectory,
        ):

            def parse_line(line: str) -> None:
                nonlocal seq, parse_errors
                if not line.strip():
                    return
                native = harness.decode(line)
                if native is None:
                    parse_errors += 1
                    return
                clean = redactor.value(native)
                native_events.append(clean)
                kind = str(native.get("kind", "native_event"))
                if kind in {"assistant_delta", "tool_output_delta"}:
                    return
                seq += 1
                data = clean.get("data", {})
                event = Event(
                    event_id=f"{execution_id}:{seq}",
                    run_id=run_id,
                    task_id=task.task_id,
                    sample_id=sample_id,
                    physical_execution_id=execution_id,
                    seq=seq,
                    timestamp=str(native.get("timestamp", now())),
                    source=harness.name,
                    type=NORMALIZED.get(kind, kind),
                    attributes={"native": clean},
                    native_call_id=str(data["call_id"])
                    if isinstance(data, dict) and data.get("call_id") is not None
                    else None,
                )
                trajectory.write(event.model_dump_json() + "\n")
                trajectory.flush()

            async def sink(stream: str, text: str) -> None:
                nonlocal line_buffer
                safe = streams[stream].feed(text)
                target = stdout if stream == "stdout" else stderr
                target.write(safe)
                target.flush()
                if stream == "stdout":
                    line_buffer += safe
                    while "\n" in line_buffer:
                        line, line_buffer = line_buffer.split("\n", 1)
                        parse_line(line)

            process = await session.execute(command, sink, env)
            for name, target in (("stdout", stdout), ("stderr", stderr)):
                remainder = streams[name].feed("", final=True)
                target.write(remainder)
                if name == "stdout":
                    line_buffer += remainder
            for line in line_buffer.splitlines():
                parse_line(line)
        process_data = process.model_dump()
        agent_result = harness.result(process, native_events)
        outcome = agent_result.outcome
        if process.timed_out:
            deadline_phase = "AGENT"
            status = ExecutionStatus.TIMED_OUT
        elif process.cancelled:
            status = ExecutionStatus.CANCELLED
        elif outcome == AgentOutcome.UNKNOWN or parse_errors:
            status = ExecutionStatus.ERROR
            errors.append("harness protocol incomplete or invalid")
        else:
            status = ExecutionStatus.FINISHED
        if not process.cleanup_complete:
            raise RuntimeError("Agent stop not confirmed; candidate cannot be frozen")
        phase = "COLLECT"
        checkpoint()
        collect_started = time.monotonic()
        collect_budget = budget(task.timeouts.collect)
        await benchmark.collect(task, workspace, sample_dir / "candidate", redactor)
        frozen = True
        if time.monotonic() - collect_started > collect_budget:
            raise TimeoutError("candidate collection deadline exceeded")
        phase = "VERIFY"
        checkpoint()
        verify_task = task.model_copy(
            update={
                "timeouts": task.timeouts.model_copy(
                    update={"verify": budget(task.timeouts.verify)}
                )
            }
        )
        async with asyncio.timeout(budget(task.timeouts.verify)):
            verification = await benchmark.verify(
                verify_task,
                sample_dir / "candidate",
                work / "verify",
                environment,
            )
        verifier_cleanup_error = (work / "verify" / "cleanup.json").exists()
        for name in ("stdout.log", "stderr.log", "cleanup.json"):
            source = work / "verify" / name
            if source.exists():
                dest = sample_dir / "verify" / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
    except asyncio.CancelledError:
        errors.append(f"cancelled during {phase}")
        if phase in {"PREPARE", "AGENT", "COLLECT"}:
            status = ExecutionStatus.CANCELLED
        else:
            verification = VerificationResult(status=Verdict.ERROR, reason="verification cancelled")
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        if isinstance(exc, TimeoutError):
            deadline_phase = phase
        startup_failure = phase == "PREPARE" and isinstance(exc, (StartupError, TimeoutError))
        errors.append(redactor.text(str(exc)))
        if status not in {ExecutionStatus.TIMED_OUT, ExecutionStatus.CANCELLED}:
            status = ExecutionStatus.ERROR
    finally:
        verifier_cleanup_error |= (work / "verify" / "cleanup.json").exists()
        try:
            async with asyncio.timeout(task.timeouts.cleanup):
                if session is not None:
                    await session.close()
                if work.exists():
                    resource_errors = await cleanup_resources(work)
                    if resource_errors:
                        raise RuntimeError("; ".join(resource_errors))
                    remove_work(work, work_root)
            cleanup = AuxiliaryStatus.ERROR if verifier_cleanup_error else AuxiliaryStatus.COMPLETED
        except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
            cleanup = AuxiliaryStatus.ERROR
            errors.append(redactor.text(str(exc)))
    result = SampleResult(
        sample_id=sample_id,
        task_id=task.task_id,
        execution_status=status,
        agent_outcome=outcome,
        verifier_status=verification.status,
        candidate_frozen=frozen,
        cleanup_status=cleanup,
        startup_retries_exhausted=startup_failure
        and (final_attempt or cleanup != AuxiliaryStatus.COMPLETED),
    )
    write_json(sample_dir / "verifier.json", verification.model_dump(), redactor)
    write_json(
        sample_dir / "sample.json",
        {
            **result.model_dump(),
            "candidate_pass": result.candidate_pass,
            "sample_success": result.sample_success,
        },
        redactor,
    )
    write_json(
        execution_dir / "execution.json",
        {
            "physical_execution_id": execution_id,
            "sample_id": sample_id,
            "run_id": run_id,
            "task_id": task.task_id,
            "started_at": start_time,
            "finished_at": now(),
            "execution_status": status,
            "agent_outcome": outcome,
            "cleanup_status": cleanup,
            "duration_ms": (time.monotonic() - started) * 1000,
            "process": process_data,
            "phase": phase,
            "agent_started": agent_started,
            "startup_failure": startup_failure,
            "deadline_phase": deadline_phase,
            "errors": errors,
        },
        redactor,
    )
    return result, startup_failure and cleanup == AuxiliaryStatus.COMPLETED


async def evaluate_sample(
    run_id: str,
    task: TaskSpec,
    sample_id: str,
    harness: Harness,
    run_dir: Path,
    settings: AgentSettings | None = None,
    environment: Environment | None = None,
    startup_retries: int = 1,
    benchmark: BenchmarkAdapter | None = None,
) -> SampleResult:
    for attempt in range(startup_retries + 1):
        result, retryable = await evaluate_attempt(
            run_id,
            task,
            sample_id,
            harness,
            run_dir,
            settings,
            environment,
            final_attempt=attempt == startup_retries,
            benchmark=benchmark,
        )
        if not retryable:
            return result
    return result


async def evaluate(
    tasks: Sequence[TaskSpec],
    harness: Harness,
    output: Path,
    samples: int = 1,
    settings: AgentSettings | None = None,
    k: int = 1,
    environment: Environment | None = None,
    concurrency: int = 1,
    startup_retries: int = 1,
    progress: Callable[[SampleResult, int, int], None] | None = None,
    benchmark: BenchmarkAdapter | None = None,
) -> Path:
    if not tasks or samples < 1 or k < 1 or concurrency < 1 or startup_retries < 0:
        raise ValueError("tasks, samples and k must be positive")
    benchmark = benchmark or MicroSweAdapter()
    await recover(output)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = (await asyncio.to_thread(output.resolve)) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    task_manifests = [benchmark.task_manifest(task) for task in tasks]
    environment_manifest = (
        await environment.resolve()
        if isinstance(environment, DockerEnvironment)
        else {
            "provider": "host_process",
            "os": platform.platform(),
            "isolation": "trusted-local-only",
            "network": "host",
        }
    )
    identity = await agent_identity(harness, environment, run_dir / "work")
    write_json(
        run_dir / "manifest.json",
        ResolvedManifest.model_validate(
            {
                "schema_version": 2,
                "run_id": run_id,
                "created_at": now(),
                "framework_version": __version__,
                "framework": runtime_identity(),
                "trajectory_schema_version": 1,
                "analyzers": {"rules": "2", "metrics": "1", "repeated_tool_calls": "1"},
                "judge": {"enabled": False},
                "benchmark": benchmark.name,
                "tasks": task_manifests,
                "harness": {
                    "name": harness.name,
                    "capabilities": harness.capabilities.model_dump(),
                    **identity,
                },
                "environment": environment_manifest,
                "model": settings.model.model_dump() if settings else None,
                "requested_model": settings.requested_model.model_dump() if settings else None,
                "agent_config": settings.manifest() if settings else {},
                "samples_per_task": samples,
                "concurrency": concurrency,
                "startup_retries": startup_retries,
                "k": k,
            }
        ).model_dump(mode="json"),
        settings.redactor if settings else None,
    )
    planned = [
        SampleResult(
            sample_id=f"sample-{task.task_id}-{index + 1}",
            task_id=task.task_id,
            execution_status=ExecutionStatus.PENDING,
        )
        for task in tasks
        for index in range(samples)
    ]
    write_json(run_dir / "plan.json", [item.model_dump() for item in planned])
    lease = RunLease(run_dir)
    if not lease.acquire():
        raise RuntimeError("cannot acquire new run lease")
    try:
        write_json(run_dir / "run_state.json", {"status": "RUNNING"})
        results = {item.sample_id: item for item in planned}
        write_json(run_dir / "summary.json", summarize(results.values(), k).model_dump())
        semaphore = asyncio.Semaphore(concurrency)
        task_map = {task.task_id: task for task in tasks}

        async def worker(item: SampleResult) -> None:
            try:
                async with semaphore:
                    result = await evaluate_sample(
                        run_id,
                        task_map[item.task_id],
                        item.sample_id,
                        harness,
                        run_dir,
                        settings,
                        environment,
                        startup_retries,
                        benchmark,
                    )
            except asyncio.CancelledError:
                result = item.model_copy(update={"execution_status": ExecutionStatus.CANCELLED})
                write_json(
                    run_dir / "tasks" / item.task_id / item.sample_id / "sample.json",
                    {**result.model_dump(), "sample_success": False, "candidate_pass": None},
                )
            results[item.sample_id] = result
            if progress is not None:
                finished = sum(
                    value.execution_status != ExecutionStatus.PENDING for value in results.values()
                )
                progress(result, finished, len(planned))
            write_json(run_dir / "summary.json", summarize(results.values(), k).model_dump())

        workers = [asyncio.create_task(worker(item)) for item in planned]
        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            for worker_task in workers:
                worker_task.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
        except BaseException:
            for worker_task in workers:
                worker_task.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            raise
        write_json(run_dir / "run_state.json", {"status": "FINISHED"})
    finally:
        lease.close()
    result_list = list(results.values())
    summary = summarize(result_list, k)
    write_json(run_dir / "summary.json", summary.model_dump())
    lines = [
        f"# Run {run_id}",
        "",
        f"Harness: {harness.name}",
        f"Environment: {environment_manifest['provider']}",
        "",
        "| Task | Execution | Agent | Verifier | Candidate pass | Sample success |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for result in result_list:
        lines.append(
            f"| {result.task_id} | {result.execution_status} | {result.agent_outcome} | "
            f"{result.verifier_status} | {result.candidate_pass} | {result.sample_success} |"
        )
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    await asyncio.to_thread(index_run, output, run_id)
    return run_dir
