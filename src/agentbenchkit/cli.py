"""Command-line entry points for local coding-agent evaluation."""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from agentbenchkit import __version__
from agentbenchkit.analysis.compare import compare as compare_runs
from agentbenchkit.analysis.judge import judge_sample
from agentbenchkit.analysis.replay import replay as replay_run
from agentbenchkit.benchmarks.micro_swe import load_tasks
from agentbenchkit.core.models import (
    CredentialRef,
    HarnessOptions,
    ModelSpec,
    PhaseBudgets,
    SampleResult,
)
from agentbenchkit.core.protocols import Harness
from agentbenchkit.core.status import Verdict
from agentbenchkit.environments.docker import DockerEnvironment
from agentbenchkit.harnesses.codex import CodexHarness
from agentbenchkit.harnesses.nexus import NexusHarness
from agentbenchkit.runtime.recovery import recover
from agentbenchkit.runtime.runner import evaluate
from agentbenchkit.runtime.settings import AgentSettings, load_model
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
        "harnesses": ["nexus", "codex"],
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
    codex_executable: Annotated[Path | None, typer.Option()] = None,
    model: Annotated[str | None, typer.Option("--model", "--codex-model")] = None,
    model_config: Annotated[Path | None, typer.Option()] = None,
    provider: Annotated[str | None, typer.Option()] = None,
    base_url: Annotated[str | None, typer.Option()] = None,
    codex_auth: Annotated[Path | None, typer.Option()] = None,
    key_env: Annotated[str | None, typer.Option()] = None,
    reasoning_effort: Annotated[str | None, typer.Option()] = None,
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
    """Evaluate an external Agent with fresh workspaces and independent verification."""
    if (
        benchmark != "micro_swe"
        or harness not in {"nexus", "codex"}
        or env not in {"host_process", "docker"}
    ):
        raise typer.BadParameter("choose micro_swe, nexus or codex, host_process or docker")
    binary = nexus_executable or Path(shutil.which("nexus") or "nexus")
    config = nexus_config or Path.home() / ".nexus" / "config.toml"
    try:
        adapter: Harness
        if harness == "nexus":
            adapter = NexusHarness(binary if env == "host_process" else "nexus")
        else:
            codex_binary = codex_executable or Path(shutil.which("codex") or "codex")
            adapter = CodexHarness(
                codex_binary if env == "host_process" else "codex", docker=env == "docker"
            )
        options = HarnessOptions()
        if model_config:
            if any(
                value is not None
                for value in (model, provider, base_url, nexus_config, key_env, reasoning_effort)
            ):
                raise ValueError("--model-config cannot be mixed with native/model source options")
            spec = load_model(model_config)
        elif harness == "nexus":
            if any(
                value is not None
                for value in (model, provider, base_url, key_env, reasoning_effort)
            ):
                raise ValueError("use --model-config for explicit Nexus Model/Provider conditions")
            spec, options = NexusHarness.import_model(config)
        else:
            if not model:
                raise ValueError("provide --model-config or an explicit --model")
            if codex_auth is not None:
                if provider is not None or base_url is not None:
                    raise ValueError("ChatGPT smoke cannot override provider or endpoint")
                spec = ModelSpec(
                    model_id=model,
                    provider_id="openai_chatgpt",
                    credential=CredentialRef(kind="chatgpt_login"),
                    reasoning_effort=reasoning_effort or "low",
                )
            else:
                if not provider or not base_url:
                    raise ValueError("API evaluation requires explicit --provider and --base-url")
                spec = ModelSpec(
                    model_id=model,
                    provider_id=provider,
                    base_url=base_url,
                    credential=CredentialRef(env_var=key_env or "OPENAI_API_KEY"),
                    reasoning_effort=reasoning_effort or "low",
                )
        if max_steps is not None:
            options = options.model_copy(update={"max_steps": max_steps})
        settings = AgentSettings(adapter, spec, options, auth_file=codex_auth)
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
        typer.echo(f"Running {len(tasks)} task(s), {samples} sample(s) each with {harness}.")

        def progress(result: SampleResult, done: int, total: int) -> None:
            typer.echo(
                f"[{done}/{total}] {result.task_id}: {result.execution_status} / "
                f"{result.agent_outcome} / verifier={result.verifier_status}"
            )

        result_dir = asyncio.run(
            evaluate(
                tasks,
                adapter,
                output,
                samples,
                settings,
                k,
                DockerEnvironment(docker_image) if env == "docker" else None,
                concurrency,
                startup_retries,
                progress,
            )
        )
    except (OSError, ValueError, RuntimeError) as exc:
        # Configuration messages must never contain credential values.
        if isinstance(exc, ValidationError):
            safe = "; ".join(
                f"{'.'.join(str(part) for part in error['loc']) or 'configuration'}: "
                f"{error['type']}"
                for error in exc.errors(include_input=False)
            )
        elif "settings" in locals():
            safe = settings.redactor.text(str(exc))
        elif type(exc) is ValueError:
            safe = str(exc)  # Adapter errors contain field names, never supplied values.
        else:
            safe = type(exc).__name__
        typer.echo(f"Evaluation error: {safe}", err=True)
        raise typer.Exit(2) from None
    typer.echo(f"Run: {result_dir.name}")
    typer.echo(f"Report: {result_dir / 'summary.md'}")
    summary = json.loads((result_dir / "summary.json").read_text(encoding="utf-8"))
    typer.echo(f"Success: {summary['samples_successful']}/{summary['samples_planned']}")
    if summary["samples_with_valid_verdict"] < summary["samples_planned"]:
        raise typer.Exit(2)


@app.command("view")
def view(
    run_id: Annotated[str | None, typer.Argument()] = None,
    output: Annotated[Path, typer.Option()] = Path(".agentbenchkit/results"),
    port: Annotated[int, typer.Option(min=1024, max=65535)] = 8765,
) -> None:
    """Serve local read-only evidence on 127.0.0.1."""
    import uvicorn

    from agentbenchkit.storage.index import resolve_run
    from agentbenchkit.viewer.app import create_app

    if run_id:
        resolve_run(output, run_id)
    path = f"/runs/{run_id}" if run_id else "/"
    typer.echo(f"Viewer: http://127.0.0.1:{port}{path}")
    uvicorn.run(create_app(output), host="127.0.0.1", port=port, log_level="warning")


@app.command("judge")
def judge_command(
    run_id: str,
    sample_id: str,
    model: Annotated[str, typer.Option()],
    endpoint: Annotated[str, typer.Option()],
    key_env: Annotated[str, typer.Option()],
    max_completion_tokens: Annotated[int, typer.Option(min=1)] = 2000,
    reasoning_effort: Annotated[str | None, typer.Option()] = None,
    output: Annotated[Path, typer.Option()] = Path(".agentbenchkit/results"),
) -> None:
    """Optionally score quality with a separate model request and versioned output."""
    target = judge_sample(
        output,
        run_id,
        sample_id,
        model,
        endpoint,
        key_env,
        max_completion_tokens=max_completion_tokens,
        reasoning_effort=reasoning_effort,
    )
    typer.echo(str(target))
    result = json.loads(target.read_text(encoding="utf-8"))
    if result["judge_status"] == "ERROR":
        typer.echo(
            json.dumps(
                result.get("error_details", {"message": result.get("error")}), ensure_ascii=False
            ),
            err=True,
        )
        raise typer.Exit(2)


@app.command("replay")
def replay_command(
    run_id: str, output: Annotated[Path, typer.Option()] = Path(".agentbenchkit/results")
) -> None:
    """Create a new analysis ID from saved evidence, preserving previous analyses."""
    typer.echo(str(replay_run(output, run_id)))


@app.command("compare")
def compare_command(
    baseline: str,
    candidate: str,
    output: Annotated[Path, typer.Option()] = Path(".agentbenchkit/results"),
    expect: Annotated[list[str] | None, typer.Option("--expect")] = None,
) -> None:
    """Compare manifest conditions before interpreting observed score changes."""
    typer.echo(
        json.dumps(
            compare_runs(output, baseline, candidate, tuple(expect or ())),
            ensure_ascii=False,
            indent=2,
        )
    )


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
