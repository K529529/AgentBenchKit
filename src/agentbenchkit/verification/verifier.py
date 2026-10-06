"""Reconstruct a fresh workspace and run evaluator-owned checks."""

import json
import shutil
import time
from pathlib import Path

from agentbenchkit.core.models import CommandSpec, TaskSpec, VerificationResult
from agentbenchkit.core.protocols import Environment
from agentbenchkit.core.status import Verdict
from agentbenchkit.environments.host import HostProcessEnvironment
from agentbenchkit.storage.artifacts import Redactor, StreamRedactor
from agentbenchkit.verification.candidate import Candidate, restore


async def verify_candidate(
    task: TaskSpec,
    candidate_dir: Path,
    manifest: Candidate,
    directory: Path,
    environment: Environment | None = None,
) -> VerificationResult:
    started = time.monotonic()
    workspace = directory / "workspace"
    assets = directory / "protected"
    report_path = directory / "output" / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    session = None
    try:
        restore(task.fixture, candidate_dir, manifest, workspace)
        shutil.copytree(task.protected_assets, assets)
        provider = environment or HostProcessEnvironment()
        session = await provider.create(workspace, directory.name + "-verify")
        argv = tuple(
            arg.replace("{verifier}", str(assets.resolve()))
            .replace("{workspace}", str(workspace.resolve()))
            .replace("{report}", str(report_path.resolve()))
            for arg in task.verification.argv
        )
        command = CommandSpec(
            argv=argv, cwd=task.verification.cwd, timeout_seconds=task.timeouts.verify
        )
        redactors = {name: StreamRedactor(Redactor()) for name in ("stdout", "stderr")}
        with (
            (directory / "stdout.log").open("w", encoding="utf-8") as stdout,
            (directory / "stderr.log").open("w", encoding="utf-8") as stderr,
        ):

            async def sink(stream: str, text: str) -> None:
                target = stdout if stream == "stdout" else stderr
                target.write(redactors[stream].feed(text))
                target.flush()

            process = await session.execute(command, sink)
            for name, target in (("stdout", stdout), ("stderr", stderr)):
                target.write(redactors[name].feed("", final=True))
        if process.timed_out or process.cancelled or not process.cleanup_complete:
            raise ValueError("verifier execution did not complete reliably")
        if not report_path.exists():
            raise ValueError("verifier report missing")
        data = json.loads(report_path.read_text(encoding="utf-8"))
        fields = ("executed", "failed", "skipped")
        if not isinstance(data, dict) or any(type(data.get(k)) is not int for k in fields):
            raise ValueError("invalid verifier report")
        executed, failed, skipped = (data[k] for k in fields)
        minimum = task.metadata.get("minimum_tests", 1)
        if not isinstance(minimum, int):
            raise ValueError("invalid minimum_tests")
        if executed < minimum or failed < 0 or skipped < 0 or failed + skipped > executed:
            raise ValueError("invalid or insufficient test execution")
        if skipped:
            raise ValueError("unexpected skipped tests")
        expected_exit = 0 if failed == 0 else 1
        if process.returncode != expected_exit:
            raise ValueError("verifier exit code conflicts with structured result")
        return VerificationResult(
            status=Verdict.PASS if failed == 0 else Verdict.FAIL,
            exit_code=process.returncode,
            tests_discovered=executed,
            tests_executed=executed,
            tests_passed=executed - failed,
            tests_failed=failed,
            tests_skipped=skipped,
            stdout_ref="verify/stdout.log",
            stderr_ref="verify/stderr.log",
            duration_ms=(time.monotonic() - started) * 1000,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        return VerificationResult(
            status=Verdict.ERROR, reason=str(exc), duration_ms=(time.monotonic() - started) * 1000
        )
    finally:
        if session is not None:
            await session.close()
