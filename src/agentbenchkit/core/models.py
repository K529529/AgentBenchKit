"""Small typed contracts; runtime evidence is independent from derived scores."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from agentbenchkit.core.status import AgentOutcome, AuxiliaryStatus, ExecutionStatus, Verdict


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CredentialRef(Contract):
    kind: Literal["api_key", "chatgpt_login", "qoder_login"] = "api_key"
    env_var: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")

    @model_validator(mode="after")
    def valid_reference(self) -> "CredentialRef":
        if (self.kind == "api_key") != (self.env_var is not None):
            raise ValueError("API keys require env_var; account login must not specify env_var")
        return self


class ModelSpec(Contract):
    """Agent-independent model identity and requested generation/connection conditions.

    Null means unspecified/unobservable, never a universal provider default.
    Secrets are represented only by references. Harnesses must reject unsupported
    requested fields and return their actual effective configuration separately.
    """

    schema_version: Literal[1] = 1
    model_id: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    base_url: str | None = None
    credential: CredentialRef
    context_window: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    reasoning_effort: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    top_p: float | None = Field(default=None, gt=0, le=1, allow_inf_nan=False)
    seed: int | None = None
    request_timeout_seconds: int | None = Field(default=None, gt=0, le=600)

    @model_validator(mode="after")
    def validate_connection(self) -> "ModelSpec":
        if self.credential.kind == "api_key" and self.base_url is None:
            raise ValueError("API model connections require an explicit base_url")
        if self.credential.kind != "api_key" and self.base_url is not None:
            raise ValueError("Account login endpoint is managed; do not claim an API base_url")
        if self.base_url is not None:
            parsed = urlsplit(self.base_url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("base_url must be HTTP(S), without credentials/query/fragment")
        return self


class HarnessOptions(Contract):
    """Agent-loop options, deliberately separate from model connection settings."""

    max_steps: int | None = Field(default=None, gt=0)
    max_credits: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    include_usage: bool = True
    output_token_parameter: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"


class NativeAgentConfig(Contract):
    config_directory: str = Field(pattern=r"^\.[A-Za-z0-9_-]+$")
    config_toml: str
    credential_env: str | None = None
    config_home_env: str | None = None
    credential_file: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.-]+$")
    credential_files: tuple[str, ...] = ()
    effective_model: ModelSpec
    wire_api: Literal["chat_completions", "responses", "chatgpt", "qoder_managed"]
    controls: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("credential_files")
    @classmethod
    def safe_private_paths(cls, names: tuple[str, ...]) -> tuple[str, ...]:
        for name in names:
            if (
                not name
                or "\\" in name
                or ":" in name
                or any(part in {"", ".", ".."} for part in name.split("/"))
            ):
                raise ValueError("private credential paths must stay inside config home")
        return names


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
    baseline_revision: str
    setup: tuple[CommandSpec, ...] = ()
    timeouts: PhaseBudgets = PhaseBudgets()
    task_type: str = "bug_fix"
    tags: tuple[str, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class LocalTaskSpec(TaskSpec):
    """Tasks backed by bundled fixtures and a local verifier command."""

    fixture: Path
    verification: CommandSpec
    protected_assets: Path
    reference_candidate: Path


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
    schema_version: Literal[2] = 2
    run_id: str
    created_at: str
    framework_version: str
    framework: dict[str, JsonValue]
    benchmark: str
    harness: dict[str, JsonValue]
    environment: dict[str, JsonValue]
    model: ModelSpec | None
    requested_model: ModelSpec | None
    agent_config: dict[str, JsonValue]
    tasks: tuple[dict[str, JsonValue], ...]
    samples_per_task: int = Field(ge=1)
    concurrency: int = Field(ge=1)
    startup_retries: int = Field(ge=0)
    k: int = Field(ge=1)
    trajectory_schema_version: Literal[1] = 1
    analyzers: dict[str, JsonValue] = Field(default_factory=dict)
    judge: dict[str, JsonValue] = Field(default_factory=dict)
