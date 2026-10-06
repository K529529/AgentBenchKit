"""OS-held run leases and conservative recovery of abandoned executions."""

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import BinaryIO

from agentbenchkit.core.metrics import summarize
from agentbenchkit.core.models import SampleResult
from agentbenchkit.core.status import ExecutionStatus
from agentbenchkit.environments.docker import docker
from agentbenchkit.storage.artifacts import write_json

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


class RunLease:
    def __init__(self, directory: Path) -> None:
        self.path = directory / "owner.lock"
        self.stream: BinaryIO | None = None

    def acquire(self) -> bool:
        self.stream = self.path.open("a+b")
        self.stream.seek(0, 2)
        if self.stream.tell() == 0:
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if sys.platform == "win32":
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            self.stream.close()
            self.stream = None
            return False

    def close(self) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None


def load_sample(path: Path) -> SampleResult:
    data = json.loads(path.read_text(encoding="utf-8"))
    return SampleResult.model_validate(
        {k: v for k, v in data.items() if k in SampleResult.model_fields}
    )


async def recover(output: Path) -> list[str]:
    recovered = []
    for manifest_path in sorted(
        await asyncio.to_thread(lambda: list(output.glob("*/manifest.json")))
    ):
        directory = manifest_path.parent
        state_path = directory / "run_state.json"
        if not state_path.exists():
            continue  # pre-recovery-schema historical evidence
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state["status"] != "RUNNING":
            continue
        lease = RunLease(directory)
        if not lease.acquire():
            continue  # a live runner owns the evidence and resources
        try:
            errors = []
            work = directory / "work"
            for resource in work.glob("**/docker-resource.json"):
                data = json.loads(resource.read_text(encoding="utf-8"))
                name = data["name"]
                if not name.startswith("abk-"):
                    errors.append("unexpected Docker resource name")
                    continue
                try:
                    ids = await docker(
                        "ps",
                        "-aq",
                        "--filter",
                        f"name=^/{name}$",
                        "--filter",
                        "label=agentbenchkit.managed=true",
                    )
                    if ids:
                        details = json.loads(await docker("inspect", name))[0]
                        identity = hashlib.sha256(data["workspace"].encode()).hexdigest()
                        if details["Config"]["Labels"].get("agentbenchkit.workspace") != identity:
                            raise ValueError("container ownership does not match recovery record")
                        await docker("rm", "--force", name)
                except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
                    errors.append(str(exc))
            if sys.platform != "win32":
                for resource in work.glob("**/host-resource.json"):
                    data = json.loads(resource.read_text(encoding="utf-8"))
                    proc = Path(f"/proc/{data['pid']}/stat")
                    if (
                        await asyncio.to_thread(proc.exists)
                        and (await asyncio.to_thread(proc.read_text)).split(") ", 1)[1].split()[19]
                        == data["start"]
                    ):
                        import signal

                        os.killpg(data["pid"], signal.SIGKILL)
            plan = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
            results = []
            for item in plan:
                sample_dir = directory / "tasks" / item["task_id"] / item["sample_id"]
                result_path = sample_dir / "sample.json"
                if result_path.exists():
                    result = load_sample(result_path)
                else:
                    result = SampleResult.model_validate(item).model_copy(
                        update={"execution_status": ExecutionStatus.INTERRUPTED}
                    )
                    write_json(
                        result_path,
                        {**result.model_dump(), "candidate_pass": None, "sample_success": None},
                    )
                results.append(result)
                for execution in sample_dir.glob("executions/*/execution.json"):
                    data = json.loads(execution.read_text(encoding="utf-8"))
                    if "finished_at" not in data:
                        data["execution_status"] = "INTERRUPTED"
                        data["recovery_reason"] = "runner lease released before final checkpoint"
                        write_json(execution, data)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            write_json(directory / "summary.json", summarize(results, manifest["k"]).model_dump())
            write_json(state_path, {"status": "INTERRUPTED", "cleanup_errors": errors})
            recovered.append(directory.name)
        finally:
            lease.close()
    return recovered
