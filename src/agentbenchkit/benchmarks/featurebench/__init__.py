"""FeatureBench v1.1 Fast discovery and pinned official evaluator integration."""

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
from agentbenchkit.environments.docker import DockerEnvironment, DockerLimits, docker
from agentbenchkit.storage.artifacts import Redactor, write_json
from agentbenchkit.verification.repository import freeze_repository, verified_patch

REVISION = "76b4a4566e04f4bcc13c35125d4f301791efa736"
EVALUATOR = "8d4e347ec57546685c5a87e8676bf575db022ea6"
CATALOG = Path(__file__).with_name("catalog.json")


class FeatureBenchAdapter:
    name = "featurebench-v1.1-fast"

    def __init__(
        self,
        dataset: Path | None = None,
        source: Path | None = None,
        evaluator_python: str = sys.executable,
        agent_image: str | None = None,
        image_pins: dict[str, str] | None = None,
        agent_images: dict[str, str] | None = None,
    ) -> None:
        self.dataset = dataset
        self.source = source
        self.python = evaluator_python
        self.agent_image = agent_image
        self.agent_images = agent_images or {}
        self.resolved_images: dict[str, str] = {}
        self.image_pins = image_pins or {}
        pinned = {
            r["image_name"]: r["image_pin"] for r in json.loads(CATALOG.read_text(encoding="utf-8"))
        }
        if any(pinned.get(name) != value for name, value in self.image_pins.items()):
            raise ValueError("image pins differ from the frozen Fast v1.1 catalog")

    def load_tasks(
        self, selected: tuple[str, ...] = (), budgets: PhaseBudgets | None = None
    ) -> list[TaskSpec]:
        rows = json.loads(CATALOG.read_text(encoding="utf-8"))
        ids = {row["instance_id"] for row in rows}
        if len(selected) != len(set(selected)) or set(selected) - ids:
            raise ValueError("duplicate or unknown FeatureBench task IDs")
        if selected:
            lookup = {row["instance_id"]: row for row in rows}
            rows = [lookup[task_id] for task_id in selected]
        return [
            TaskSpec(
                task_id=row["instance_id"],
                prompt=row["problem_statement"],
                baseline_revision=row["base_commit"],
                timeouts=budgets or PhaseBudgets(prepare=1800, agent=900, collect=180, verify=1800),
                task_type="feature",
                tags=("python", "lv1", row["repo"]),
                metadata={
                    "dataset_revision": REVISION,
                    "evaluator_commit": EVALUATOR,
                    "image": self.image_pins.get(row["image_name"], row["image_pin"]),
                    "row_sha256": row["row_sha256"],
                    "repo": row["repo"],
                },
            )
            for row in rows
            if not selected or row["instance_id"] in selected
        ]

    def agent_image_for(self, task: TaskSpec) -> str | None:
        return self.agent_images.get(str(task.metadata["image"]), self.agent_image)

    def task_manifest(self, task: TaskSpec) -> dict[str, JsonValue]:
        reference = self.agent_image_for(task)
        if reference and reference not in self.resolved_images:
            image = json.loads(
                subprocess.check_output(
                    ["docker", "image", "inspect", reference], timeout=30, text=True
                )
            )[0]
            self.resolved_images[reference] = str(image["Id"])
        return {
            **task.model_dump(mode="json"),
            "fixture_hash": task.metadata["row_sha256"],
            "verifier_hash": EVALUATOR,
            "metadata": {
                **task.metadata,
                "inference_image_id": self.resolved_images.get(reference or ""),
            },
        }

    def row(self, task: TaskSpec) -> dict[str, Any]:
        if not self.dataset or not self.source or not self.agent_image_for(task):
            raise ValueError(
                "FeatureBench execution requires dataset, official source and agent image"
            )
        raw = self.dataset.read_bytes()
        rows = json.loads(raw)
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        expected = {item["instance_id"]: item["row_sha256"] for item in catalog}
        observed = {
            item["instance_id"]: hashlib.sha256(
                json.dumps(item, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            for item in rows
        }
        if len(rows) != 100 or observed != expected:
            raise ValueError("FeatureBench content differs from frozen v1.1 Fast data")
        row: dict[str, Any] = next(r for r in rows if r["instance_id"] == task.task_id)
        row["level"] = 1
        row["image_name"] = task.metadata["image"]
        return row

    async def worker(self, spec: dict[str, Any], directory: Path, seconds: float) -> None:
        await run_worker(
            self.python, Path(__file__).with_name("worker.py"), spec, directory, seconds
        )

    async def prepare(self, task: TaskSpec, workspace: Path, evidence: Path) -> Environment | None:
        if sys.platform == "win32":
            raise ValueError(
                "FeatureBench execution requires Linux/WSL; Windows discovery is supported"
            )
        row = self.row(task)
        image = self.agent_image_for(task)
        assert self.source and image
        work = workspace.parent
        work.mkdir(parents=True, exist_ok=True)
        name = "abk-fb-" + work.name
        snapshot = "abk-prepared-" + work.name
        write_json(work / "docker-resource.json", {"name": name, "workspace": str(workspace)})
        write_json(
            work / "docker-image-resource.json",
            {
                "name": snapshot,
                "workspace": str(workspace),
            },
        )
        try:
            await self.worker(
                {
                    "mode": "prepare",
                    "row": row,
                    "source": str(self.source.resolve()),
                    "commit": EVALUATOR,
                    "agent_image": self.resolved_images.get(image, image),
                    "container": name,
                    "snapshot": snapshot,
                    "workspace": str(await asyncio.to_thread(workspace.resolve)),
                },
                work / "prepare",
                task.timeouts.prepare,
            )
        except BaseException:
            try:
                await docker("rm", "--force", name)
            except RuntimeError:
                pass
            raise
        finally:
            if (work / "prepare").exists():
                shutil.copytree(work / "prepare", evidence)
        return DockerEnvironment(
            snapshot,
            limits=DockerLimits(
                memory_mb=8192,
                cpus=4,
                pids=512,
                readonly=False,
                workdir="/testbed",
                python="/opt/abk/bin/python",
            ),
            ephemeral=True,
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
        self,
        task: TaskSpec,
        candidate_dir: Path,
        directory: Path,
        environment: Environment | None,
    ) -> VerificationResult:
        row = self.row(task)
        assert self.source
        patch = verified_patch(candidate_dir)
        evidence = candidate_dir.parent / "verify"
        evidence.mkdir(exist_ok=True)
        run_label = "abk-" + hashlib.sha256(str(directory).encode()).hexdigest()[:24]
        write_json(
            directory / "docker-group-resource.json",
            {
                "execution": run_label,
                "workspace": str(directory),
            },
        )
        try:
            await self.worker(
                {
                    "mode": "verify",
                    "run_label": run_label,
                    "resource_workspace": str(directory),
                    "row": row,
                    "source": str(self.source.resolve()),
                    "commit": EVALUATOR,
                    "patch": patch,
                    "timeout": int(task.timeouts.verify),
                },
                evidence,
                task.timeouts.verify,
            )
            data = json.loads((evidence / "result.json").read_text(encoding="utf-8"))
            return official_verdict(task.task_id, data)
        except (OSError, ValueError, RuntimeError) as exc:
            return VerificationResult(status=Verdict.ERROR, reason=str(exc))
        finally:
            try:
                leftovers = await docker(
                    "ps", "-aq", "--filter", "label=featurebench.run=" + run_label
                )
                for container_id in leftovers.splitlines():
                    await docker("rm", "--force", container_id)
            except (OSError, RuntimeError, TimeoutError) as exc:
                write_json(evidence / "cleanup.json", {"status": "ERROR", "reason": str(exc)})
            # Runtime's existing cleanup/error channel remains independent of correctness.
            await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
            for name in ("stdout.log", "stderr.log", "cleanup.json"):
                if (evidence / name).exists():
                    shutil.copy2(evidence / name, directory / name)


def official_verdict(task_id: str, data: dict[str, Any]) -> VerificationResult:
    reports = data.get("report")
    report = reports.get(task_id) if isinstance(reports, dict) else None
    if not isinstance(report, dict):
        return VerificationResult(
            status=Verdict.ERROR, reason="official report missing or malformed"
        )
    if (
        data.get("completed") is not True
        or data.get("error")
        or report.get("error")
        or type(report.get("resolved")) is not bool
        or report.get("featurebench_eval_completed") is not True
    ):
        return VerificationResult(status=Verdict.ERROR, reason="official evaluation incomplete")
    return VerificationResult(
        status=Verdict.PASS if report["resolved"] else Verdict.FAIL,
        checks={"official_report": report},
        stdout_ref="verify/stdout.log",
        stderr_ref="verify/stderr.log",
        reason="pinned official FeatureBench resolved verdict",
    )
