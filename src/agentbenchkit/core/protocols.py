"""External adapters describe commands; environments own process execution."""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from pydantic import JsonValue

from agentbenchkit.core.models import (
    AgentResult,
    Capabilities,
    CommandSpec,
    Contract,
    HarnessOptions,
    ModelSpec,
    NativeAgentConfig,
    PhaseBudgets,
    TaskSpec,
    VerificationResult,
)
from agentbenchkit.storage.artifacts import Redactor


class StartupError(RuntimeError):
    """Infrastructure failed before the Agent generation opportunity began."""


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

    def native_config(self, model: ModelSpec, options: HarnessOptions) -> NativeAgentConfig: ...

    def version_command(self) -> CommandSpec: ...

    def command(self, task: TaskSpec) -> CommandSpec: ...

    def decode(self, line: str) -> dict[str, JsonValue] | None: ...

    def result(self, process: ProcessResult, events: list[dict[str, JsonValue]]) -> AgentResult: ...


class BenchmarkAdapter(Protocol):
    """Benchmark-owned task materialization and independent correctness semantics.

    Runtime owns deadlines, process execution, stop/freeze ordering and cleanup.
    Implementations must never expose protected evaluator inputs to the Agent.
    """

    name: str

    def load_tasks(
        self, selected: tuple[str, ...] = (), budgets: PhaseBudgets | None = None
    ) -> Sequence[TaskSpec]: ...

    def task_manifest(self, task: TaskSpec) -> dict[str, JsonValue]: ...

    async def prepare(
        self, task: TaskSpec, workspace: Path, evidence: Path
    ) -> Environment | None: ...

    async def collect(
        self, task: TaskSpec, workspace: Path, destination: Path, redactor: Redactor
    ) -> None: ...

    async def verify(
        self,
        task: TaskSpec,
        candidate_dir: Path,
        directory: Path,
        environment: Environment | None,
    ) -> VerificationResult: ...


class Verifier(Protocol):
    async def verify(self, task: TaskSpec, candidate: Path) -> VerificationResult: ...
