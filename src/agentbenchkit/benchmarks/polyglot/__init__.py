"""225 Polyglot tasks with one Agent execution and official Aider test semantics."""

import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from agentbenchkit.core.models import CommandSpec, PhaseBudgets, TaskSpec, VerificationResult
from agentbenchkit.core.protocols import Environment
from agentbenchkit.core.status import Verdict
from agentbenchkit.environments.docker import DockerEnvironment, DockerLimits
from agentbenchkit.storage.artifacts import Redactor, write_json
from agentbenchkit.verification.repository import freeze_repository, verified_patch

REVISION = "7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f"
EVALUATOR = "5dc9490bb35f9729ef2c95d00a19ccd30c26339c"
JEST_VERSION = "29.7.0"
CATALOG = Path(__file__).with_name("catalog.json")


def checked_checkout(path: Path, revision: str) -> None:
    observed = subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()
    dirty = subprocess.check_output(["git", "-C", str(path), "status", "--porcelain"], text=True)
    if observed != revision or dirty:
        raise ValueError("official checkout must be clean and exactly pinned")


def copy_solutions(source: Path, destination: Path, names: list[str]) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        src = source / name
        if src.is_symlink() or not src.resolve().is_relative_to(source.resolve()):
            raise ValueError("solution files must be regular files inside the workspace")
        if src.exists():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)


class PolyglotAdapter:
    name = "aider-polyglot-single-run"

    def __init__(
        self,
        dataset: Path | None = None,
        source: Path | None = None,
        agent_image: str | None = None,
    ) -> None:
        self.dataset, self.source, self.agent_image = dataset, source, agent_image
        self.image_id: str | None = None
        self.rows = {r["task_id"]: r for r in json.loads(CATALOG.read_text(encoding="utf-8"))}

    def load_tasks(
        self, selected: tuple[str, ...] = (), budgets: PhaseBudgets | None = None
    ) -> list[TaskSpec]:
        if len(selected) != len(set(selected)) or set(selected) - self.rows.keys():
            raise ValueError("duplicate or unknown Polyglot task IDs")
        return [
            TaskSpec(
                task_id=key,
                prompt=self.rows[key]["prompt"],
                baseline_revision=REVISION,
                timeouts=budgets or PhaseBudgets(prepare=120, agent=600, collect=60, verify=300),
                task_type="exercise",
                tags=(self.rows[key]["language"],),
                metadata={
                    "dataset_revision": REVISION,
                    "evaluator_commit": EVALUATOR,
                    "evaluation_protocol": "single-agent-run-hidden-tests",
                    "verifier_network": "bridge",
                    "official_two_round_comparable": False,
                    "evaluation_notice": (
                        "Single Agent execution with hidden tests; not directly comparable "
                        "with official Aider two-round scores."
                    ),
                    "solution_files": self.rows[key]["solution_files"],
                    "language": self.rows[key]["language"],
                },
            )
            for key in selected or tuple(self.rows)
        ]

    def resolve_image(self) -> str:
        if self.image_id:
            return self.image_id
        if not self.agent_image:
            raise ValueError(
                "Polyglot requires an image containing the official test toolchains and Agent"
            )
        image = json.loads(
            subprocess.check_output(
                ["docker", "image", "inspect", self.agent_image], text=True, timeout=30
            )
        )[0]
        if (image["Config"].get("Labels") or {}).get("agentbenchkit.aider.commit") != EVALUATOR:
            raise ValueError("Polyglot image must declare the pinned official Aider commit")
        if (image["Config"].get("Labels") or {}).get("agentbenchkit.polyglot.jest") != JEST_VERSION:
            raise ValueError("Polyglot image must pin Jest 29.7.0 to match the dataset")
        self.image_id = str(image["Id"])
        return self.image_id

    def task_manifest(self, task: TaskSpec) -> dict[str, JsonValue]:
        row = self.rows[task.task_id]
        fingerprint = hashlib.sha256(
            json.dumps(row["files_sha256"], sort_keys=True).encode()
        ).hexdigest()
        return {
            **task.model_dump(mode="json"),
            "fixture_hash": fingerprint,
            "verifier_hash": EVALUATOR,
            "metadata": {**task.metadata, "inference_image_id": self.resolve_image()},
        }

    def exercise(self, task: TaskSpec) -> tuple[Path, dict[str, Any]]:
        if not self.dataset or not self.source:
            raise ValueError("Polyglot requires pinned dataset and official Aider checkouts")
        checked_checkout(self.dataset, REVISION)
        checked_checkout(self.source, EVALUATOR)
        row = self.rows[task.task_id]
        folder = self.dataset / row["path"]
        observed = {
            p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*")
            if p.is_file()
        }
        if observed != row["files_sha256"]:
            raise ValueError("exercise content differs from pinned Polyglot data")
        return folder, row

    def materialize(self, task: TaskSpec, target: Path, include_tests: bool) -> dict[str, Any]:
        folder, row = self.exercise(task)
        excluded = set(row["example_files"])
        if not include_tests:
            excluded.update(row["test_files"])
        target.mkdir(parents=True, exist_ok=False)
        for name in row["files_sha256"]:
            if name in excluded or name.startswith((".meta/", ".docs/")):
                continue
            dest = target / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(folder / name, dest)
        return row

    async def prepare(self, task: TaskSpec, workspace: Path, evidence: Path) -> Environment | None:
        if sys.platform == "win32":
            raise ValueError("Polyglot execution requires Linux/WSL")
        row = await asyncio.to_thread(self.materialize, task, workspace, False)
        await asyncio.to_thread(
            copy_solutions, workspace, workspace.parent / "baseline", row["solution_files"]
        )
        write_json(
            evidence / "preparation.json",
            {
                "protocol": "single-agent-run-hidden-tests",
                "solution_files": row["solution_files"],
                "hidden_test_files": row["test_files"],
                "dataset_revision": REVISION,
            },
        )
        return DockerEnvironment(
            self.resolve_image(),
            limits=DockerLimits(
                memory_mb=4096, cpus=2, pids=512, readonly=False, python="/opt/abk/bin/python"
            ),
        )

    async def collect(
        self, task: TaskSpec, workspace: Path, destination: Path, redactor: Redactor
    ) -> None:
        selected = workspace.parent / "selected-solution"
        copy_solutions(workspace, selected, self.rows[task.task_id]["solution_files"])
        freeze_repository(
            workspace.parent / "baseline",
            selected,
            destination,
            workspace.parent / "collector",
            redactor,
        )

    async def verify(
        self, task: TaskSpec, candidate_dir: Path, directory: Path, environment: Environment | None
    ) -> VerificationResult:
        verified_patch(candidate_dir)
        row = self.rows[task.task_id]
        workspace, protected = directory / "workspace", directory / "protected"
        testdir = workspace / row["path"]
        await asyncio.to_thread(self.materialize, task, testdir, True)
        manifest = json.loads(
            (candidate_dir.parent / "candidate_manifest.json").read_text(encoding="utf-8")
        )
        allowed = set(row["solution_files"])
        for name in manifest["changed"] + manifest["deleted"]:
            if name not in allowed:
                raise ValueError("candidate changes a protected Polyglot file")
        for name in manifest["deleted"]:
            (testdir / name).unlink(missing_ok=True)
        for item in manifest["files"]:
            if item["path"] not in allowed:
                raise ValueError("candidate changes a protected Polyglot file")
            if item["symlink"]:
                raise ValueError("Polyglot solution symlinks are not supported")
            target = testdir / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate_dir / item["path"], target)
        assert self.source and self.dataset
        protected.mkdir(parents=True)
        shutil.copy2(self.source / "benchmark/benchmark.py", protected / "benchmark.py")
        shutil.copy2(Path(__file__).with_name("worker.py"), protected / "worker.py")
        for name in row["test_files"]:
            original = protected / "original" / row["path"] / name
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.dataset / row["path"] / name, original)
        spec = {
            "path": row["path"],
            "test_files": row["test_files"],
            "benchmark_sha256": hashlib.sha256(
                (protected / "benchmark.py").read_bytes()
            ).hexdigest(),
            "scripts_sha256": {
                name: hashlib.sha256((self.source / "benchmark" / name).read_bytes()).hexdigest()
                for name in ("npm-test.sh", "cpp-test.sh")
            },
        }
        write_json(protected / "input.json", spec)
        output = directory / "output"
        evidence = candidate_dir.parent / "verify"
        evidence.mkdir(exist_ok=True)
        environment = DockerEnvironment(
            self.resolve_image(),
            verification=True,
            limits=DockerLimits(
                memory_mb=4096,
                cpus=2,
                pids=512,
                readonly=False,
                workspace_readonly=False,
                verification_network="bridge",
                python="/opt/abk/bin/python",
            ),
        )
        write_json(evidence / "environment.json", await environment.resolve())
        session = await environment.create(workspace, directory.name)
        try:
            with (
                (evidence / "stdout.log").open("w", encoding="utf-8") as out,
                (evidence / "stderr.log").open("w", encoding="utf-8") as err,
            ):

                async def sink(stream: str, text: str) -> None:
                    (out if stream == "stdout" else err).write(text)

                process = await session.execute(
                    CommandSpec(
                        argv=("/opt/abk/bin/python", "/protected/worker.py"),
                        timeout_seconds=task.timeouts.verify,
                    ),
                    sink,
                    {
                        "HOME": "/tmp/abk-home",
                        "RUSTUP_HOME": "/root/.rustup",
                        "CARGO_HOME": "/tmp/abk-home/.cargo",
                    },
                )
            write_json(evidence / "process.json", process.model_dump())
            if (
                process.returncode
                or process.timed_out
                or not process.cleanup_complete
                or not (output / "report.json").exists()
            ):
                return VerificationResult(
                    status=Verdict.ERROR, reason="official Polyglot test process incomplete"
                )
            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            shutil.copytree(output, evidence / "official")
            return VerificationResult(
                status=Verdict.PASS if report["passed"] else Verdict.FAIL,
                checks={"official_report": report},
                stdout_ref="verify/stdout.log",
                stderr_ref="verify/stderr.log",
                reason="official Aider run_unit_tests single-round outcome",
            )
        finally:
            try:
                await session.close()
            except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
                record = {"status": "ERROR", "reason": str(exc)}
                write_json(directory / "cleanup.json", record)
                write_json(evidence / "cleanup.json", record)
