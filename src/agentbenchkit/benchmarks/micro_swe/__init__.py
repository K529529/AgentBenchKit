"""Small standard-library Python fixtures with independently owned checks."""

import sys
from pathlib import Path

from agentbenchkit.core.models import CommandSpec, PhaseBudgets, TaskSpec
from agentbenchkit.verification.candidate import inventory, tree_hash

ASSETS = Path(__file__).parent / "assets"
TASKS = {
    "clamp": "Fix bounds.py: clamp(value, lower, upper) must return value within the inclusive "
    "bounds. If lower > upper, raise ValueError. Preserve the public function signature.",
    "stable_unique": "Create sequence_tools.py exporting stable_unique(items), which returns a "
    "new list of distinct hashable items in first-occurrence order. Accept any "
    "iterable. Do not mutate input. Equal items should appear only once.",
}


def load_tasks(
    selected: tuple[str, ...] = (), budgets: PhaseBudgets | None = None
) -> list[TaskSpec]:
    unknown = set(selected) - TASKS.keys()
    if unknown:
        raise ValueError(f"unknown micro_swe task: {sorted(unknown)}")
    result = []
    for task_id, prompt in TASKS.items():
        if selected and task_id not in selected:
            continue
        asset = ASSETS / task_id
        fixture = asset / "fixture"
        result.append(
            TaskSpec(
                task_id=task_id,
                prompt=prompt,
                fixture=fixture,
                baseline_revision=tree_hash(inventory(fixture)),
                verification=CommandSpec(
                    argv=(sys.executable, "-I", "{verifier}/check.py", "{workspace}", "{report}")
                ),
                protected_assets=asset / "verifier",
                reference_candidate=asset / "reference",
                timeouts=budgets or PhaseBudgets(),
                metadata={"minimum_tests": 4, "verifier_version": "micro_swe-v1"},
            )
        )
    return result
