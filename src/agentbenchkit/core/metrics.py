"""Fixed V0 statistical semantics. Missing observations are never zero."""

from collections import defaultdict
from collections.abc import Iterable
from math import comb

from agentbenchkit.core.models import Contract, SampleResult


class TaskPassAtK(Contract):
    value: float | None
    reason: str | None = None


class Summary(Contract):
    samples_planned: int
    samples_successful: int
    samples_with_valid_verdict: int
    end_to_end_success_rate: float | None
    candidate_pass_rate: float | None
    coverage_rate: float | None
    tasks_planned: int
    tasks_with_valid_pass_at_k: int
    tasks_excluded_from_pass_at_k: int
    pass_at_k: float | None
    per_task: dict[str, TaskPassAtK]
    k: int


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def task_pass_at_k(samples: list[SampleResult], k: int) -> TaskPassAtK:
    if k < 1:
        raise ValueError("k must be positive")
    n = len(samples)
    if n < k:
        return TaskPassAtK(value=None, reason="planned_samples_less_than_k")
    if any(sample.sample_success is None for sample in samples):
        return TaskPassAtK(value=None, reason="inconclusive_sample")
    c = sum(sample.sample_success is True for sample in samples)
    return TaskPassAtK(value=1 - (comb(n - c, k) / comb(n, k) if n - c >= k else 0))


def summarize(samples: Iterable[SampleResult], k: int = 1) -> Summary:
    if k < 1:
        raise ValueError("k must be positive")
    items = list(samples)
    if len({s.sample_id for s in items}) != len(items):
        raise ValueError("logical sample IDs must be unique; physical retries are not samples")
    groups: dict[str, list[SampleResult]] = defaultdict(list)
    for sample in items:
        groups[sample.task_id].append(sample)
    per_task = {task: task_pass_at_k(group, k) for task, group in groups.items()}
    valid_values = [item.value for item in per_task.values() if item.value is not None]
    successful = sum(s.sample_success is True for s in items)
    covered = sum(s.candidate_pass is not None for s in items)
    correct = sum(s.candidate_pass is True for s in items)
    return Summary(
        samples_planned=len(items),
        samples_successful=successful,
        samples_with_valid_verdict=covered,
        end_to_end_success_rate=ratio(successful, len(items)),
        candidate_pass_rate=ratio(correct, covered),
        coverage_rate=ratio(covered, len(items)),
        tasks_planned=len(groups),
        tasks_with_valid_pass_at_k=len(valid_values),
        tasks_excluded_from_pass_at_k=len(groups) - len(valid_values),
        pass_at_k=sum(valid_values) / len(valid_values) if valid_values else None,
        per_task=per_task,
        k=k,
    )
