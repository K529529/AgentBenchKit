"""Runnable Harness composition example using the real Nexus v0.2.0 public CLI.

This is a teaching adapter, not a third supported Agent or a plugin registration.
It deliberately reuses the tested Nexus mapping instead of inventing a CLI/schema.
See docs/adding-a-harness.md before adapting it to a different Agent.
"""

import argparse
import asyncio
import shutil
from pathlib import Path

from pydantic import JsonValue

from agentbenchkit.benchmarks.micro_swe import load_tasks
from agentbenchkit.core.models import (
    AgentResult,
    CommandSpec,
    HarnessOptions,
    ModelSpec,
    NativeAgentConfig,
    TaskSpec,
)
from agentbenchkit.core.protocols import Harness, ProcessResult
from agentbenchkit.environments.docker import DockerEnvironment
from agentbenchkit.harnesses.nexus import NexusHarness
from agentbenchkit.runtime.runner import evaluate
from agentbenchkit.runtime.settings import AgentSettings, load_model


class CustomNexusHarness:
    # The evaluated Agent really is Nexus. Keep its provenance and analyzer support.
    name = "nexus"
    capabilities = NexusHarness.capabilities

    def __init__(self, executable: Path | str) -> None:
        self.adapter = NexusHarness(executable)

    def native_config(self, model: ModelSpec, options: HarnessOptions) -> NativeAgentConfig:
        # Converts the shared ModelSpec; rejects unsupported fields; never reads a key.
        return self.adapter.native_config(model, options)

    def version_command(self) -> CommandSpec:
        # Public `nexus --version`; Environment, not Harness, executes it.
        return self.adapter.version_command()

    def command(self, task: TaskSpec) -> CommandSpec:
        # Public `nexus exec <prompt> --json`; argv, no shell interpolation.
        return self.adapter.command(task)

    def decode(self, line: str) -> dict[str, JsonValue] | None:
        # Actual Nexus public JSONL -> kind/data envelope; Runtime builds Event IDs.
        return self.adapter.decode(line)

    def result(self, process: ProcessResult, events: list[dict[str, JsonValue]]) -> AgentResult:
        # Uses the native terminal outcome plus exit code, never guesses correctness.
        return self.adapter.result(process, events)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--env", choices=("host_process", "docker"), default="docker")
    parser.add_argument("--executable", default="nexus")
    parser.add_argument("--docker-image", default="agentbenchkit-nexus:v0.2.0")
    parser.add_argument("--output", type=Path, default=Path(".agentbenchkit/results"))
    args = parser.parse_args()
    executable: Path | str = args.executable
    if args.env == "host_process":
        executable = Path(shutil.which(args.executable) or args.executable)
        print("HostProcess: trusted local execution; no filesystem sandbox.")
    # Structural typing checks all five methods against the real Protocol.
    harness: Harness = CustomNexusHarness(executable)
    settings = AgentSettings(harness, load_model(args.model_config), HarnessOptions())
    run_dir = asyncio.run(
        evaluate(
            tasks=load_tasks(("clamp",)),
            harness=harness,
            output=args.output,
            settings=settings,
            environment=DockerEnvironment(args.docker_image) if args.env == "docker" else None,
        )
    )
    print(f"Run: {run_dir.name}")
    print(f"Report: {run_dir / 'summary.md'}")


if __name__ == "__main__":
    main()
