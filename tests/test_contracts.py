from itertools import product

import pytest
from pydantic import ValidationError

from agentbenchkit.core.events import Event
from agentbenchkit.core.metrics import summarize, task_pass_at_k
from agentbenchkit.core.models import CommandSpec, SampleResult
from agentbenchkit.core.status import AgentOutcome as A
from agentbenchkit.core.status import AuxiliaryStatus as X
from agentbenchkit.core.status import ExecutionStatus as E
from agentbenchkit.core.status import Verdict as V


def sample(
    execution: E = E.FINISHED,
    agent: A = A.COMPLETED,
    verdict: V = V.PASS,
    *,
    sid: str = "s1",
    task: str = "task",
    frozen: bool = True,
) -> SampleResult:
    return SampleResult(
        sample_id=sid,
        task_id=task,
        execution_status=execution,
        agent_outcome=agent,
        verifier_status=verdict,
        candidate_frozen=frozen,
    )


@pytest.mark.parametrize(
    ("verdict", "expected"), [(V.PASS, True), (V.FAIL, False), (V.ERROR, None), (V.NOT_RUN, None)]
)
def test_normal_completion(verdict: V, expected: bool | None) -> None:
    result = sample(verdict=verdict)
    assert result.candidate_pass is expected
    assert result.sample_success is expected


@pytest.mark.parametrize(("execution", "verdict"), list(product([E.TIMED_OUT, E.CANCELLED], V)))
def test_execution_violation_precedes_verifier_error(execution: E, verdict: V) -> None:
    assert sample(execution=execution, verdict=verdict).sample_success is False


@pytest.mark.parametrize(("outcome", "verdict"), list(product([A.FAILED, A.LIMITED, A.ABORTED], V)))
def test_agent_failure_does_not_become_unknown(outcome: A, verdict: V) -> None:
    assert sample(agent=outcome, verdict=verdict).sample_success is False


@pytest.mark.parametrize("execution", [E.ERROR, E.INTERRUPTED, E.RUNNING, E.COLLECTING])
def test_framework_uncertainty_cannot_become_pass(execution: E) -> None:
    assert sample(execution=execution).sample_success is None


def test_unfrozen_candidate_cannot_be_success() -> None:
    assert sample(frozen=False).sample_success is None


def test_exhausted_startup_is_false_without_blame_on_agent() -> None:
    result = sample(E.ERROR, A.UNKNOWN, V.NOT_RUN, frozen=False).model_copy(
        update={"startup_retries_exhausted": True}
    )
    assert result.sample_success is False
    assert result.agent_outcome == A.UNKNOWN
    assert result.candidate_pass is None


@pytest.mark.parametrize(("cleanup", "analysis"), list(product(X, X)))
def test_auxiliary_states_do_not_rewrite_success(cleanup: X, analysis: X) -> None:
    result = sample().model_copy(update={"cleanup_status": cleanup, "analysis_status": analysis})
    assert result.sample_success is True


def test_timeout_pass_is_candidate_only() -> None:
    result = summarize([sample(), sample(E.TIMED_OUT, sid="s2")])
    assert result.end_to_end_success_rate == 0.5
    assert result.candidate_pass_rate == 1.0
    assert result.coverage_rate == 1.0
    assert result.pass_at_k == 0.5


def test_inconclusive_sample_does_not_shrink_denominator() -> None:
    result = summarize([sample(), sample(verdict=V.ERROR, sid="s2")])
    assert result.samples_planned == 2
    assert result.end_to_end_success_rate == 0.5
    assert result.candidate_pass_rate == 1
    assert result.coverage_rate == 0.5
    assert result.pass_at_k is None
    assert result.per_task["task"].reason == "inconclusive_sample"


def test_pass_at_k_estimator() -> None:
    items = [sample(sid=str(i), verdict=V.PASS if i < 2 else V.FAIL) for i in range(4)]
    assert task_pass_at_k(items, 2).value == pytest.approx(5 / 6)
    assert task_pass_at_k(items, 4).value == 1
    assert task_pass_at_k(items, 5).value is None


def test_aggregate_is_task_macro_mean_not_sample_weighted() -> None:
    items = [sample(sid=str(i), task="large") for i in range(3)]
    items += [sample(sid="f", task="small", verdict=V.FAIL)]
    items += [sample(sid="u", task="unknown", verdict=V.ERROR)]
    result = summarize(items)
    assert result.pass_at_k == 0.5
    assert result.tasks_with_valid_pass_at_k == 2
    assert result.tasks_excluded_from_pass_at_k == 1
    assert result.tasks_planned == 3


def test_zero_denominators_and_invalid_k() -> None:
    result = summarize([])
    assert result.end_to_end_success_rate is None
    assert result.candidate_pass_rate is None
    assert result.coverage_rate is None
    assert result.pass_at_k is None
    with pytest.raises(ValueError):
        summarize([], 0)


def test_physical_retry_cannot_count_as_extra_logical_sample() -> None:
    with pytest.raises(ValueError, match="unique"):
        summarize([sample(), sample()])


def test_nullable_event_fields_and_required_identity() -> None:
    event = Event(
        event_id="e",
        run_id="r",
        task_id="t",
        sample_id="s",
        physical_execution_id="p",
        seq=1,
        timestamp="2026-10-07T00:00:00Z",
        source="harness",
        type="agent_started",
    )
    assert event.duration_ms is None
    assert event.native_call_id is None
    with pytest.raises(ValidationError):
        Event.model_validate({**event.model_dump(), "seq": 0})


@pytest.mark.parametrize("cwd", ["../escape", "nested/../../escape", r"nested\..\escape"])
def test_command_cannot_escape_workspace(cwd: str) -> None:
    with pytest.raises(ValidationError):
        CommandSpec(argv=("python", "test.py"), cwd=cwd)
