"""Small standard-library Python fixtures with independently owned checks."""

import json
import shutil
import sys
from pathlib import Path

from pydantic import JsonValue

from agentbenchkit.core.models import (
    CommandSpec,
    LocalTaskSpec,
    PhaseBudgets,
    TaskSpec,
    VerificationResult,
)
from agentbenchkit.core.protocols import Environment
from agentbenchkit.environments.docker import DockerEnvironment
from agentbenchkit.storage.artifacts import Redactor
from agentbenchkit.verification.candidate import Candidate, collect, inventory, tree_hash
from agentbenchkit.verification.verifier import verify_candidate

ASSETS = Path(__file__).parent / "assets"
TASKS = {
    "clamp": "Fix bounds.py: clamp(value, lower, upper) must return value within the inclusive "
    "bounds. If lower > upper, raise ValueError. Preserve the public function signature.",
    "stable_unique": "Create sequence_tools.py exporting stable_unique(items), which returns a "
    "new list of distinct hashable items in first-occurrence order. Accept any "
    "iterable. Do not mutate input. Equal items should appear only once.",
}

EXTRA_TASKS = json.loads((ASSETS / "tasks.json").read_text(encoding="utf-8"))
TASKS.update({key: value["prompt"] for key, value in EXTRA_TASKS.items()})


def load_tasks(
    selected: tuple[str, ...] = (), budgets: PhaseBudgets | None = None
) -> list[LocalTaskSpec]:
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
            LocalTaskSpec(
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
                task_type=EXTRA_TASKS.get(task_id, {}).get("task_type", "bug_fix"),
                metadata={"minimum_tests": 4, "verifier_version": "micro_swe-v1"},
            )
        )
    return result


class MicroSweAdapter:
    name = "micro_swe-v1"

    def load_tasks(
        self, selected: tuple[str, ...] = (), budgets: PhaseBudgets | None = None
    ) -> list[LocalTaskSpec]:
        return load_tasks(selected, budgets)

    def task_manifest(self, task: TaskSpec) -> dict[str, JsonValue]:
        assert isinstance(task, LocalTaskSpec)
        return {
            **task.model_dump(mode="json"),
            "fixture_hash": tree_hash(inventory(task.fixture)),
            "verifier_hash": tree_hash(inventory(task.protected_assets)),
        }

    async def prepare(self, task: TaskSpec, workspace: Path, evidence: Path) -> Environment | None:
        assert isinstance(task, LocalTaskSpec)
        shutil.copytree(task.fixture, workspace)
        return None

    async def collect(
        self, task: TaskSpec, workspace: Path, destination: Path, redactor: Redactor
    ) -> None:
        assert isinstance(task, LocalTaskSpec)
        for entry in inventory(workspace).values():
            text = (workspace / entry.path).read_text(encoding="utf-8")
            if any(secret in text for secret in redactor.secrets):
                raise RuntimeError("candidate contains a credential; refusing persistence")
        collect(task.fixture, workspace, destination)

    async def verify(
        self,
        task: TaskSpec,
        candidate_dir: Path,
        directory: Path,
        environment: Environment | None,
    ) -> VerificationResult:
        assert isinstance(task, LocalTaskSpec)
        candidate = Candidate.model_validate_json(
            (candidate_dir.parent / "candidate_manifest.json").read_text(encoding="utf-8")
        )
        return await verify_candidate(
            task,
            candidate_dir,
            candidate,
            directory,
            DockerEnvironment(environment.image, verification=True)
            if isinstance(environment, DockerEnvironment)
            else None,
        )
