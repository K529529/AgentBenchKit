"""Command-line entry points for local coding-agent evaluation."""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Annotated

import typer

from agentbenchkit import __version__
from agentbenchkit.benchmarks.micro_swe import load_tasks
from agentbenchkit.core.models import PhaseBudgets
from agentbenchkit.core.status import Verdict
from agentbenchkit.environments.docker import DockerEnvironment
from agentbenchkit.harnesses.nexus import NexusHarness
from agentbenchkit.runtime.recovery import recover
from agentbenchkit.runtime.runner import evaluate
from agentbenchkit.runtime.settings import NexusSettings
from agentbenchkit.storage.index import list_runs, rebuild
from agentbenchkit.verification.candidate import collect
from agentbenchkit.verification.verifier import verify_candidate

app = typer.Typer(no_args_is_help=True, help="Local coding-agent evaluation and evidence.")


@app.callback()
def main() -> None:
    """Local coding-agent evaluation and evidence."""


@app.command()
def version() -> None:
    """Print the AgentBenchKit version."""
    typer.echo(__version__)


@app.command("list")
def list_components(kind: str) -> None:
    """List currently implemented benchmarks, harnesses or environments."""
    values = {
        "benchmarks": ["micro_swe"],
        "harnesses": ["nexus"],
        "envs": ["host_process", "docker"],
    }
    if kind not in values:
        raise typer.BadParameter("choose benchmarks, harnesses, or envs")
    typer.echo("\n".join(values[kind]))


@app.command()
def run(
    benchmark: str,
    harness: str,
    env: Annotated[str, typer.Option()] = "host_process",
    samples: Annotated[int, typer.Option(min=1)] = 1,
    task: Annotated[list[str] | None, typer.Option("--task")] = None,
    output: Annotated[Path, typer.Option()] = Path(".agentbenchkit/results"),
    nexus_executable: Annotated[Path | None, typer.Option()] = None,
    nexus_config: Annotated[Path | None, typer.Option()] = None,
    agent_timeout: Annotated[float, typer.Option(min=1)] = 120,
    max_steps: Annotated[int | None, typer.Option(min=1)] = None,
    prepare_timeout: Annotated[float, typer.Option(min=1)] = 120,
    verify_timeout: Annotated[float, typer.Option(min=1)] = 60,
    overall_timeout: Annotated[float | None, typer.Option(min=1)] = None,
    k: Annotated[int, typer.Option(min=1)] = 1,
    concurrency: Annotated[int, typer.Option(min=1, max=16)] = 1,
    startup_retries: Annotated[int, typer.Option(min=0, max=3)] = 1,
    docker_image: Annotated[str, typer.Option()] = "agentbenchkit-nexus:v0.2.0",
) -> None:
    """Evaluate real Nexus with fresh workspaces and independent verification."""
    if benchmark != "micro_swe" or harness != "nexus" or env not in {"host_process", "docker"}:
        raise typer.BadParameter("choose micro_swe / nexus / host_process or docker")
    binary = nexus_executable or Path(shutil.which("nexus") or "nexus")
    config = nexus_config or Path.home() / ".nexus" / "config.toml"
    try:
        settings = NexusSettings(config, max_steps)
        tasks = load_tasks(
            tuple(task or ()),
            PhaseBudgets(
                agent=agent_timeout,
                prepare=prepare_timeout,
                verify=verify_timeout,
                overall=overall_timeout,
            ),
        )
        if env == "host_process":
            typer.echo("HostProcess: trusted local execution; no filesystem sandbox.")
        typer.echo(f"Running {len(tasks)} task(s), {samples} sample(s) each with Nexus.")
        result_dir = asyncio.run(
            evaluate(
                tasks,
                NexusHarness(binary if env == "host_process" else "nexus"),
                output,
                samples,
                settings,
                k,
                DockerEnvironment(docker_image) if env == "docker" else None,
                concurrency,
                startup_retries,
            )
        )
    except (OSError, ValueError, RuntimeError) as exc:
        # Configuration messages must never contain credential values.
        safe = settings.redactor.text(str(exc)) if "settings" in locals() else type(exc).__name__
        typer.echo(f"Evaluation error: {safe}", err=True)
        raise typer.Exit(2) from None
    typer.echo(f"Run: {result_dir.name}")
    typer.echo(f"Report: {result_dir / 'summary.md'}")
    summary = json.loads((result_dir / "summary.json").read_text(encoding="utf-8"))
    typer.echo(f"Success: {summary['samples_successful']}/{summary['samples_planned']}")
    if summary["samples_with_valid_verdict"] < summary["samples_planned"]:
        raise typer.Exit(2)


@app.command("rebuild-index")
def rebuild_index(output: Annotated[Path, typer.Option()] = Path(".agentbenchkit/results")) -> None:
    """Rebuild disposable query data from persisted filesystem evidence."""
    typer.echo(f"Indexed {rebuild(output)} runs")


@app.command("runs")
def runs(output: Annotated[Path, typer.Option()] = Path(".agentbenchkit/results")) -> None:
    """List indexed local runs."""
    for row in list_runs(output):
        typer.echo(f"{row['run_id']}  {row['harness']}  {row['environment']}")


@app.command("recover")
def recover_runs(output: Annotated[Path, typer.Option()] = Path(".agentbenchkit/results")) -> None:
    """Mark abandoned runs interrupted and stop their recorded resources."""
    for run_id in asyncio.run(recover(output)):
        typer.echo(f"Recovered: {run_id}")


@app.command("validate-benchmark")
def validate_benchmark() -> None:
    """Check no-op and reference candidates without any model requests."""

    async def validate(root: Path) -> bool:
        success = True
        for task in load_tasks():
            for label, source, expected in (
                ("no-op", task.fixture, Verdict.FAIL),
                ("reference", task.reference_candidate, Verdict.PASS),
            ):
                case = root / task.task_id / label
                candidate = collect(task.fixture, source, case / "candidate")
                result = await verify_candidate(
                    task, case / "candidate", candidate, case / "verify"
                )
                typer.echo(f"{task.task_id}: {label}: {result.status}")
                success &= result.status == expected
        return success

    base = Path(".agentbenchkit/validation").resolve()
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base) as temporary:
        target = Path(temporary).resolve()
        if not target.is_relative_to(base) or target == base:
            raise RuntimeError("invalid validation directory")
        passed = asyncio.run(validate(target))
    if not passed:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
