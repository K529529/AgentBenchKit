"""Run a frozen, sequential FeatureBench plan; launched independently by tmux."""

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentbenchkit.analysis.replay import replay
from agentbenchkit.benchmarks.featurebench import FeatureBenchAdapter
from agentbenchkit.core.models import PhaseBudgets, SampleResult
from agentbenchkit.environments.docker import DockerEnvironment, DockerLimits
from agentbenchkit.harnesses.nexus import NexusHarness
from agentbenchkit.runtime.runner import evaluate
from agentbenchkit.runtime.settings import AgentSettings
from agentbenchkit.storage.artifacts import write_json


def check_plan(plan: dict[str, Any], repository: Path) -> None:
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()
    if commit != plan["abk_commit"]:
        raise ValueError("ABK commit differs from frozen plan")
    if subprocess.check_output(["git", "diff", "HEAD", "--name-only"], cwd=repository):
        raise ValueError("tracked ABK changes after freeze")
    for name, expected in plan["file_hashes"].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"frozen file changed: {name}")
    if len(plan["benchmark"]["task_ids"]) != 16:
        raise ValueError("formal plan must contain exactly 16 tasks")
    for reference, identity in plan["images"].items():
        image = json.loads(subprocess.check_output(["docker", "image", "inspect", identity]))[0]
        labels = image["Config"]["Labels"]
        if (
            image["Id"] != identity
            or labels["agentbenchkit.benchmark.base"] != reference
            or labels["agentbenchkit.nexus.commit"] != plan["nexus_commit"]
            or labels["agentbenchkit.nexus.archive-sha256"] != plan["nexus_archive_sha256"]
        ):
            raise ValueError("image identity differs from frozen source/base")


async def run(plan: dict[str, Any], group: str, output: Path) -> None:
    if shutil.disk_usage(output).free < 30 * 1024**3:
        raise RuntimeError("less than 30 GiB available before start")
    harness = NexusHarness("/opt/abk/bin/nexus")
    model, options = harness.import_model(Path(plan["configs"][group]))
    settings = AgentSettings(harness, model, options)
    benchmark = plan["benchmark"]
    adapter = FeatureBenchAdapter(
        dataset=Path(benchmark["dataset"]),
        source=Path(benchmark["official_source"]),
        evaluator_python=benchmark["evaluator_python"],
        image_pins=benchmark["image_pins"],
        agent_images=plan["images"],
    )
    tasks = adapter.load_tasks(tuple(benchmark["task_ids"]), PhaseBudgets(**plan["budgets"]))
    assert options.nexus_config["multi_agent"]["enabled"] == (group == "multi")
    assert options.nexus_config["security"]["mode"] == "local"
    # Validate evaluator/data before allocating any model call.
    adapter.row(tasks[0])
    source = Path(benchmark["official_source"])
    official = (
        await asyncio.to_thread(
            subprocess.check_output, ["git", "rev-parse", "HEAD"], cwd=source, text=True
        )
    ).strip()
    if official != tasks[0].metadata["evaluator_commit"] or await asyncio.to_thread(
        subprocess.check_output, ["git", "status", "--porcelain"], cwd=source
    ):
        raise ValueError("official evaluator is not the clean pinned revision")
    limits = DockerLimits(
        memory_mb=8192, cpus=4, pids=512, readonly=False, python="/opt/abk/bin/python"
    )
    environment = DockerEnvironment(next(iter(plan["images"].values())), limits=limits)
    stopping: list[str] = []

    def progress(sample: SampleResult, finished: int, total: int) -> None:
        print(
            json.dumps(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "finished": finished,
                    "total": total,
                    "sample": sample.model_dump(mode="json"),
                }
            ),
            flush=True,
        )
        if (
            sample.startup_retries_exhausted
            or sample.cleanup_status == "ERROR"
            or (sample.execution_status == "ERROR" and sample.agent_outcome == "UNKNOWN")
        ):
            stopping.append("shared startup/cleanup failure; no further model calls")
            raise RuntimeError(stopping[-1])

    evaluation = asyncio.create_task(
        evaluate(
            tasks,
            harness,
            output / "runs",
            samples=1,
            settings=settings,
            k=1,
            environment=environment,
            concurrency=1,
            startup_retries=0,
            benchmark=adapter,
            progress=progress,
        )
    )
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: (output / "STOP").touch())

    async def guard() -> None:
        while not evaluation.done():
            reason = None
            if (output / "STOP").exists():
                reason = "user stop requested"
            elif shutil.disk_usage(output).free < 10 * 1024**3:
                reason = "less than 10 GiB free"
            for mount in ("/mnt/c", "/mnt/d"):
                if (
                    await asyncio.to_thread(Path(mount).exists)
                    and shutil.disk_usage(mount).free < 5 * 1024**3
                ):
                    reason = f"host volume below 5 GiB: {mount}"
            for path in (output / "runs").glob("*/tasks/*/*/executions/*/stdout.log"):
                for line in path.read_text(errors="replace").splitlines():
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    data = event.get("data", {})
                    if event.get("kind") == "subagent_event":
                        data = data.get("data", {})
                    if data.get("status_code") in {401, 403} or data.get("error") in {
                        "model_auth",
                        "authentication",
                        "invalid_api_key",
                        "model_http_401",
                        "model_http_403",
                    }:
                        reason = "model authentication failure"
            if reason:
                stopping.append(reason)
                write_json(output / "stop-reason.json", {"reason": reason})
                evaluation.cancel()
                return
            await asyncio.sleep(3)

    watcher = asyncio.create_task(guard())
    try:
        directory = await evaluation
        write_json(output / "run.json", {"run_id": directory.name, "directory": str(directory)})
        replay(output / "runs", directory.name)
        if stopping:
            raise RuntimeError(stopping[-1])
    finally:
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--group", choices=("single", "multi"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--credential-file", type=Path, required=True)
    args = parser.parse_args()
    material = json.loads(args.credential_file.read_text())
    args.credential_file.unlink()
    # The launcher sends only credential references required by these frozen configs.
    os.environ.update(material)
    plan = json.loads(args.plan.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    write_json(
        args.output / "process.json",
        {
            "pid": os.getpid(),
            "python": sys.executable,
            "cwd": str(Path.cwd()),
            "group": args.group,
            "started_at": datetime.now(UTC).isoformat(),
        },
    )
    code = 1
    try:
        check_plan(plan, Path(__file__).resolve().parents[1])
        os.environ["PATH"] = plan["docker_wrapper_directory"] + ":" + os.environ["PATH"]
        write_json(args.output / "frozen-plan.json", plan)
        asyncio.run(run(plan, args.group, args.output))
        code = 0
    finally:
        write_json(
            args.output / "exit.json",
            {
                "exit_code": code,
                "finished_at": datetime.now(UTC).isoformat(),
                "status": "COMPLETED" if code == 0 else "STOPPED_OR_FAILED",
            },
        )
    raise SystemExit(code)


if __name__ == "__main__":
    main()
