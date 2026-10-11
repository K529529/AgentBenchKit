"""The experimental harness must not silently change model or completion semantics."""
import pytest
from pydantic import JsonValue

from agentbenchkit.core.models import CredentialRef, HarnessOptions, ModelSpec
from agentbenchkit.core.protocols import ProcessResult
from agentbenchkit.core.status import AgentOutcome
from agentbenchkit.harnesses.sh_agent import ShAgentHarness


def model(**updates: object) -> ModelSpec:
    values = dict(model_id="deepseek-v4.1-flash", provider_id="test",
                  base_url="https://example.test/v1",
                  credential=CredentialRef(env_var="TEST_API_KEY"))
    values.update(updates)
    return ModelSpec.model_validate(values)


@pytest.mark.parametrize("field,value", [
    ("context_window", 1000000), ("max_output_tokens", 8192), ("reasoning_effort", "low"),
    ("request_timeout_seconds", 120), ("top_p", 0.9), ("seed", 1),
])
def test_rejects_unsupported_controls(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field):
        ShAgentHarness().native_config(model(**{field: value}), HarnessOptions())


def test_preserves_zero_temperature_and_credential_reference() -> None:
    native = ShAgentHarness().native_config(model(temperature=0), HarnessOptions())
    assert native.effective_model.temperature == 0
    assert native.credential_env == "TEST_API_KEY"
    assert native.controls["model_call_limit"] is None


@pytest.mark.parametrize("options", [HarnessOptions(max_steps=40), HarnessOptions(max_credits=1)])
def test_rejects_false_budget_claims(options: HarnessOptions) -> None:
    with pytest.raises(ValueError):
        ShAgentHarness().native_config(model(), options)


def test_exit_conflict_and_missing_terminal_are_not_success() -> None:
    harness = ShAgentHarness()
    events: list[dict[str, JsonValue]] = [
        {"kind": "run_finished", "data": {"outcome": "completed"}}
    ]
    process = ProcessResult(returncode=1, duration_ms=1)
    assert harness.result(process, events).outcome == AgentOutcome.UNKNOWN
    assert harness.result(process, []).outcome == AgentOutcome.UNKNOWN
    assert harness.result(ProcessResult(returncode=0, duration_ms=1), events).outcome == (
        AgentOutcome.COMPLETED
    )


def test_native_exception_is_failed_not_verifier_fail() -> None:
    event = ShAgentHarness().decode(
        '{"kind":"run_finished","data":{"outcome":"failed","error":"history"}}'
    )
    assert event is not None
    result = ShAgentHarness().result(ProcessResult(returncode=1, duration_ms=1), [event])
    assert result.outcome == AgentOutcome.FAILED


