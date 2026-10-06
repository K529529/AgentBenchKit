"""Public CLI adapter for Nexus v0.2.0; no Agent source changes."""

import json
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from agentbenchkit.core.models import AgentResult, Capabilities, CommandSpec, TaskSpec
from agentbenchkit.core.protocols import ProcessResult
from agentbenchkit.core.status import AgentOutcome

NEXUS_COMMIT = "677fc997dcdc2f369fa8d4a667d400de99e35f84"


class NexusHarness:
    name = "nexus"
    capabilities = Capabilities(
        final_answer=True,
        tool_calls=True,
        tool_results=True,
        model_usage=True,
        model_output="partial",
        native_call_ids=True,
    )

    def __init__(self, executable: Path | str) -> None:
        self.executable = executable.resolve() if isinstance(executable, Path) else executable

    def version_command(self) -> CommandSpec:
        return CommandSpec(argv=(str(self.executable), "--version"), timeout_seconds=15)

    def command(self, task: TaskSpec) -> CommandSpec:
        return CommandSpec(
            argv=(str(self.executable), "exec", task.prompt, "--json"),
            timeout_seconds=task.timeouts.agent,
        )

    def decode(self, line: str) -> dict[str, JsonValue] | None:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
            return None
        return cast(dict[str, JsonValue], value)

    def result(self, process: ProcessResult, events: list[dict[str, JsonValue]]) -> AgentResult:
        final = next((e for e in reversed(events) if e.get("kind") == "run_finished"), None)
        if final is None:
            return AgentResult(returncode=process.returncode)
        data = final.get("data")
        if not isinstance(data, dict):
            return AgentResult(returncode=process.returncode)
        mapping = {
            "completed": AgentOutcome.COMPLETED,
            "failed": AgentOutcome.FAILED,
            "limited": AgentOutcome.LIMITED,
            "aborted": AgentOutcome.ABORTED,
        }
        outcome = mapping.get(str(data.get("outcome")), AgentOutcome.UNKNOWN)
        expected_exit = {
            AgentOutcome.COMPLETED: 0,
            AgentOutcome.FAILED: 1,
            AgentOutcome.LIMITED: 3,
            AgentOutcome.ABORTED: 130,
        }
        if not process.timed_out and not process.cancelled:
            if process.returncode != expected_exit.get(outcome):
                outcome = AgentOutcome.UNKNOWN
        final_text = data.get("final_text")
        return AgentResult(
            outcome=outcome,
            returncode=process.returncode,
            final_answer=final_text if isinstance(final_text, str) else None,
        )
