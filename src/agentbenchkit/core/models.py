"""Small typed contracts; runtime evidence is independent from derived scores."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from agentbenchkit.core.status import AgentOutcome, AuxiliaryStatus, ExecutionStatus, Verdict


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CommandSpec(Contract):
    form: Literal["argv"] = "argv"
    argv: tuple[str, ...] = Field(min_length=1)
    cwd: str = "."
    shell: None = None
    timeout_seconds: float = Field(default=60, gt=0)

    @field_validator("cwd")
    @classmethod
    def relative_cwd(cls, value: str) -> str:
        if Path(value).is_absolute() or ".." in value.replace("\\", "/").split("/"):
            raise ValueError("command cwd must stay within the workspace")
        return value


class PhaseBudgets(Contract):
    prepare: float = Field(default=120, gt=0)
    agent: float = Field(default=120, gt=0)
    collect: float = Field(default=30, gt=0)
    verify: float = Field(default=60, gt=0)
    analysis: float = Field(default=60, gt=0)
    cleanup: float = Field(default=15, gt=0)
    overall: float | None = Field(default=None, gt=0)


class TaskSpec(Contract):
    task_id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
    prompt: str = Field(min_length=1)
    fixture: Path
    baseline_revision: str
    setup: tuple[CommandSpec, ...] = ()
    verification: CommandSpec
    protected_assets: Path
    reference_candidate: Path
    timeouts: PhaseBudgets = PhaseBudgets()
    task_type: str = "bug_fix"
    tags: tuple[str, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class Capabilities(Contract):
    final_answer: bool = False
    tool_calls: bool = False
    tool_results: bool = False
    model_usage: bool = False
    model_input: bool = False
    model_output: Literal["available", "partial", "unavailable"] = "unavailable"
    native_call_ids: bool = False
    patch: bool = True
    file_reads: bool = False


class AgentResult(Contract):
    outcome: AgentOutcome = AgentOutcome.UNKNOWN
    returncode: int | None = None
    final_answer: str | None = None
    reported_usage: dict[str, int | None] = Field(default_factory=dict)


class VerificationResult(Contract):
    status: Verdict = Verdict.NOT_RUN
    exit_code: int | None = None
    tests_discovered: int | None = None
    tests_executed: int | None = None
    tests_passed: int | None = None
    tests_failed: int | None = None
    tests_skipped: int | None = None
    checks: dict[str, JsonValue] = Field(default_factory=dict)
    stdout_ref: str | None = None
    stderr_ref: str | None = None
    duration_ms: float | None = None
    reason: str | None = None


class SampleResult(Contract):
    sample_id: str
    task_id: str
    execution_status: ExecutionStatus
    agent_outcome: AgentOutcome = AgentOutcome.UNKNOWN
    verifier_status: Verdict = Verdict.NOT_RUN
    analysis_status: AuxiliaryStatus = AuxiliaryStatus.NOT_RUN
    cleanup_status: AuxiliaryStatus = AuxiliaryStatus.NOT_RUN
    candidate_frozen: bool = False
    startup_retries_exhausted: bool = False

    @property
    def candidate_pass(self) -> bool | None:
        return {Verdict.PASS: True, Verdict.FAIL: False}.get(self.verifier_status)

    @property
    def sample_success(self) -> bool | None:
        # Confirmed execution violations take precedence over later verifier errors.
        if self.execution_status in {ExecutionStatus.TIMED_OUT, ExecutionStatus.CANCELLED}:
            return False
        if self.agent_outcome in {AgentOutcome.FAILED, AgentOutcome.LIMITED, AgentOutcome.ABORTED}:
            return False
        if self.startup_retries_exhausted:
            return False
        if (
            self.execution_status != ExecutionStatus.FINISHED
            or self.agent_outcome != AgentOutcome.COMPLETED
            or not self.candidate_frozen
        ):
            return None
        return self.candidate_pass


class ResolvedManifest(Contract):
    schema_version: Literal[1] = 1
    run_id: str
    created_at: str
    framework_version: str
    benchmark: dict[str, JsonValue]
    harness: dict[str, JsonValue]
    environment: dict[str, JsonValue]
    model: dict[str, JsonValue]
    tasks: tuple[dict[str, JsonValue], ...]
    samples_per_task: int = Field(ge=1)
    concurrency: int = Field(ge=1)
    phase_budgets: PhaseBudgets
    trajectory_schema_version: Literal[1] = 1
    analyzers: dict[str, JsonValue] = Field(default_factory=dict)
    judge: dict[str, JsonValue] = Field(default_factory=dict)
