"""SWE-bench Lite: pinned data, official v4.1.0 test specification and grading."""

import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from agentbenchkit.benchmarks.worker import run_worker
from agentbenchkit.core.models import PhaseBudgets, TaskSpec, VerificationResult
from agentbenchkit.core.protocols import Environment
from agentbenchkit.core.status import Verdict
from agentbenchkit.environments.docker import DockerEnvironment, DockerLimits
from agentbenchkit.storage.artifacts import Redactor, write_json
from agentbenchkit.verification.repository import freeze_repository, verified_patch

REVISION = "6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2"
EVALUATOR = "726c5461e2ef52d83cf1ea2107870a8bb3328d57"
CATALOG = Path(__file__).with_name("catalog.json")


class SweBenchAdapter:
    name = "swe-bench-lite"

    def __init__(
        self,
        dataset: Path | None = None,
        source: Path | None = None,
        evaluator_python: str = sys.executable,
        agent_image: str | None = None,
        image_pins: dict[str, str] | None = None,
        agent_images: dict[str, str] | None = None,
    ) -> None:
        self.dataset, self.source, self.python = dataset, source, evaluator_python
        self.agent_image = agent_image
        self.image_pins, self.agent_images = image_pins or {}, agent_images or {}
        self.images: dict[str, tuple[str, str]] = {}

    def load_tasks(
        self, selected: tuple[str, ...] = (), budgets: PhaseBudgets | None = None
    ) -> list[TaskSpec]:
        rows = json.loads(CATALOG.read_text(encoding="utf-8"))
        lookup = {row["instance_id"]: row for row in rows}
        if len(selected) != len(set(selected)) or set(selected) - lookup.keys():
            raise ValueError("duplicate or unknown SWE-bench Lite task IDs")
        if selected:
            rows = [lookup[key] for key in selected]
        return [
            TaskSpec(
                task_id=r["instance_id"],
                prompt=r["problem_statement"],
                baseline_revision=r["base_commit"],
                timeouts=budgets or PhaseBudgets(prepare=600, agent=900, collect=180, verify=1800),
                tags=("python", r["repo"]),
                metadata={
                    "dataset_revision": REVISION,
                    "evaluator_commit": EVALUATOR,
                    "repo": r["repo"],
                    "row_sha256": r["row_sha256"],
                    "image_name": r["image_name"],
                },
            )
            for r in rows
        ]

    def resolve_images(self, task: TaskSpec) -> tuple[str, str]:
        if task.task_id in self.images:
            return self.images[task.task_id]
        image_name = str(task.metadata["image_name"])
        reference = self.agent_images.get(image_name, self.agent_image)
        if not reference:
            raise ValueError("SWE-bench execution requires a derived agent image")
        image = json.loads(
            subprocess.check_output(
                ["docker", "image", "inspect", reference], text=True, timeout=30
            )
        )[0]
        base = (image["Config"].get("Labels") or {}).get("agentbenchkit.benchmark.base", "")
        repository = image_name.removesuffix(":latest")
        if not base.startswith(repository + "@sha256:") or len(base.rsplit(":", 1)[-1]) != 64:
            raise ValueError("agent image must declare this task's immutable official base")
        if image_name in self.image_pins and self.image_pins[image_name] != base:
            raise ValueError("official image does not match configured digest")
        self.images[task.task_id] = (str(image["Id"]), str(base))
        return self.images[task.task_id]

    def task_manifest(self, task: TaskSpec) -> dict[str, JsonValue]:
        agent, official = self.resolve_images(task)
        return {
            **task.model_dump(mode="json"),
            "fixture_hash": task.metadata["row_sha256"],
            "verifier_hash": EVALUATOR,
            "metadata": {**task.metadata, "inference_image_id": agent, "image": official},
        }

    def row(self, task: TaskSpec) -> dict[str, Any]:
        if not self.dataset or not self.source:
            raise ValueError("SWE-bench execution requires pinned dataset and official source")
        rows = json.loads(self.dataset.read_text(encoding="utf-8"))
        expected = {
            r["instance_id"]: r["row_sha256"]
            for r in json.loads(CATALOG.read_text(encoding="utf-8"))
        }
        observed = {
            r["instance_id"]: hashlib.sha256(
                json.dumps(r, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            for r in rows
        }
        if len(rows) != 300 or observed != expected:
            raise ValueError("SWE-bench Lite content differs from pinned dataset")
        row: dict[str, Any] = next(r for r in rows if r["instance_id"] == task.task_id)
        return row

    async def worker(self, spec: dict[str, Any], evidence: Path, seconds: float) -> None:
        await run_worker(
            self.python, Path(__file__).with_name("worker.py"), spec, evidence, seconds
        )

    async def prepare(self, task: TaskSpec, workspace: Path, evidence: Path) -> Environment | None:
        if sys.platform == "win32":
            raise ValueError("SWE-bench execution requires Linux/WSL")
        row = self.row(task)
        agent, official = self.resolve_images(task)
        name = "abk-swe-" + workspace.parent.name
        write_json(
            workspace.parent / "docker-resource.json", {"name": name, "workspace": str(workspace)}
        )
        assert self.source
        spec = {
            "mode": "prepare",
            "source": str(self.source.resolve()),
            "commit": EVALUATOR,
            "row": row,
            "agent_image": agent,
            "official_image": official,
            "container": name,
            "workspace": str(workspace),
            "resource_workspace": str(workspace.parent / "prepare"),
        }
        await self.worker(spec, evidence, task.timeouts.prepare)
        return DockerEnvironment(
            agent,
            limits=DockerLimits(
                memory_mb=4096,
                cpus=2,
                pids=512,
                readonly=False,
                workdir="/testbed",
                python="/opt/abk/bin/python",
            ),
        )

    async def collect(
        self, task: TaskSpec, workspace: Path, destination: Path, redactor: Redactor
    ) -> None:
        freeze_repository(
            workspace.parent / "baseline",
            workspace,
            destination,
            workspace.parent / "collector",
            redactor,
        )

    async def verify(
        self, task: TaskSpec, candidate_dir: Path, directory: Path, environment: Environment | None
    ) -> VerificationResult:
        assert self.source
        _, official = self.resolve_images(task)
        evidence = candidate_dir.parent / "verify"
        label = "abk-" + hashlib.sha256(str(directory).encode()).hexdigest()[:24]
        write_json(
            directory / "docker-group-resource.json",
            {"execution": label, "workspace": str(directory)},
        )
        spec = {
            "mode": "verify",
            "source": str(self.source.resolve()),
            "commit": EVALUATOR,
            "row": self.row(task),
            "official_image": official,
            "run_label": label,
            "resource_workspace": str(directory),
            "patch": verified_patch(candidate_dir),
            "timeout": int(task.timeouts.verify),
        }
        try:
            await self.worker(spec, evidence, task.timeouts.verify)
            return official_verdict(
                task.task_id, json.loads((evidence / "result.json").read_text(encoding="utf-8"))
            )
        except (OSError, ValueError, RuntimeError) as exc:
            return VerificationResult(status=Verdict.ERROR, reason=str(exc))
        finally:
            await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
            for name in ("stdout.log", "stderr.log"):
                if (evidence / name).exists():
                    shutil.copy2(evidence / name, directory / name)


def official_verdict(task_id: str, data: dict[str, Any]) -> VerificationResult:
    reports = data.get("report")
    report = reports.get(task_id) if isinstance(reports, dict) else None
    if (
        data.get("completed") is not True
        or not isinstance(report, dict)
        or type(report.get("resolved")) is not bool
    ):
        return VerificationResult(
            status=Verdict.ERROR, reason="official SWE-bench evaluation incomplete"
        )
    return VerificationResult(
        status=Verdict.PASS if report["resolved"] else Verdict.FAIL,
        checks={"official_report": report},
        stdout_ref="verify/stdout.log",
        stderr_ref="verify/stderr.log",
        reason="pinned official SWE-bench resolved verdict",
    )
