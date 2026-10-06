"""External adapters describe commands; environments own process execution."""

from pathlib import Path
from typing import Protocol

from pydantic import JsonValue

from agentbenchkit.core.models import (
    AgentResult,
    Capabilities,
    CommandSpec,
    Contract,
    TaskSpec,
    VerificationResult,
)


class ProcessResult(Contract):
    returncode: int | None
    duration_ms: float
    timed_out: bool = False
    cancelled: bool = False
    cleanup_complete: bool = True
    output_truncated: bool = False


class OutputSink(Protocol):
    async def __call__(self, stream: str, text: str) -> None: ...


class ExecutionSession(Protocol):
    workspace: Path

    async def execute(
        self,
        command: CommandSpec,
        sink: OutputSink,
        env: dict[str, str] | None = None,
    ) -> ProcessResult: ...

    async def stop(self) -> bool: ...

    async def close(self) -> None: ...


class Environment(Protocol):
    async def create(self, workspace: Path, execution_id: str) -> ExecutionSession: ...


class Harness(Protocol):
    name: str
    capabilities: Capabilities

    def command(self, task: TaskSpec) -> CommandSpec: ...

    def decode(self, line: str) -> dict[str, JsonValue] | None: ...

    def result(self, process: ProcessResult, events: list[dict[str, JsonValue]]) -> AgentResult: ...


class BenchmarkAdapter(Protocol):
    def load_tasks(self) -> list[TaskSpec]: ...


class Verifier(Protocol):
    async def verify(self, task: TaskSpec, candidate: Path) -> VerificationResult: ...
