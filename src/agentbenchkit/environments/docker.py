"""Whole-process Docker execution; credentials travel only through bootstrap stdin."""

import asyncio
import codecs
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from agentbenchkit.core.models import CommandSpec
from agentbenchkit.core.protocols import OutputSink, ProcessResult, StartupError
from agentbenchkit.storage.artifacts import write_json

BOOTSTRAP = (
    "import json,os,sys; spec=json.loads(sys.stdin.readline()); "
    "os.chdir(spec['cwd']); os.environ.update(spec['env']); os.execvp(spec['argv'][0],spec['argv'])"
)


async def docker(*args: str, deadline_seconds: float = 30) -> str:
    process = await asyncio.create_subprocess_exec(
        "docker", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), deadline_seconds)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode:
        raise RuntimeError(f"Docker {args[0]} failed: {stderr.decode('utf-8', 'replace')[:1000]}")
    return stdout.decode("utf-8").strip()


class DockerSession:
    def __init__(self, workspace: Path, image: str, verification: bool = False) -> None:
        self.workspace = workspace.resolve()
        self.image = image
        self.verification = verification
        self.name: str | None = None
        self.paths = {str(self.workspace): "/workspace"}
        self.output_limit = 2_000_000

    async def stop(self) -> bool:
        if self.name is None:
            return True
        try:
            state = json.loads(await docker("inspect", "--format", "{{json .State}}", self.name))
            if state["Running"]:
                await docker("kill", self.name)
                await docker("wait", self.name)
            state = json.loads(await docker("inspect", "--format", "{{json .State}}", self.name))
            return not state["Running"]
        except (OSError, ValueError, RuntimeError, TimeoutError):
            return False

    async def close(self) -> None:
        if not await self.stop():
            raise RuntimeError("Docker stop not confirmed")
        if self.name:
            await docker("rm", self.name)
            self.name = None

    def translate(self, value: str) -> str:
        for source, destination in sorted(self.paths.items(), key=lambda pair: -len(pair[0])):
            if value == source or value.startswith((source + "/", source + "\\")):
                return destination + value[len(source) :].replace("\\", "/")
        return value

    async def prepare(self) -> None:
        await self.close()
        name = "abk-" + uuid.uuid4().hex
        network = "none" if self.verification else "bridge"
        user = "1000"
        if sys.platform != "win32":
            user = str(os.getuid())
        args = [
            "create",
            "--name",
            name,
            "--label",
            "agentbenchkit.managed=true",
            "--label",
            "agentbenchkit.workspace=" + hashlib.sha256(str(self.workspace).encode()).hexdigest(),
            "--init",
            "--interactive",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "128",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--network",
            network,
            "--user",
            user,
            "--tmpfs",
            "/tmp:rw,nosuid,size=128m,mode=1777",
            "--log-driver",
            "none",
        ]
        mounts = [(self.workspace, "/workspace", self.verification)]
        if self.verification:
            assets = self.workspace.parent / "protected"
            output = self.workspace.parent / "output"
            output.mkdir(exist_ok=True)
            mounts.extend([(assets, "/protected", True), (output, "/output", False)])
        else:
            home = self.workspace.parent / "agent_home"
            if home.exists():
                mounts.append((home, "/agent-home", False))
        for source, destination, readonly in mounts:
            if "," in str(source):
                raise ValueError("Docker mount paths must not contain commas")
            self.paths[str(source.resolve())] = destination
            args.extend(
                [
                    "--mount",
                    f"type=bind,source={source},target={destination}"
                    + (",readonly" if readonly else ""),
                ]
            )
        args.extend(["--workdir", "/workspace", self.image, "python", "-c", BOOTSTRAP])
        write_json(
            self.workspace.parent / "docker-resource.json",
            {"name": name, "workspace": str(self.workspace)},
        )
        try:
            await docker(*args)
        except (OSError, RuntimeError, TimeoutError) as exc:
            raise StartupError(str(exc)) from exc
        self.name = name

    async def execute(
        self, command: CommandSpec, sink: OutputSink, env: dict[str, str] | None = None
    ) -> ProcessResult:
        if self.name is None:
            await self.prepare()
        else:
            state = json.loads(await docker("inspect", "--format", "{{json .State}}", self.name))
            if state["Status"] != "created":
                await self.prepare()
        assert self.name is not None
        name = self.name
        cwd = (self.workspace / command.cwd).resolve()
        if not cwd.is_relative_to(self.workspace):
            raise ValueError("command cwd escapes workspace")
        argv = [self.translate(arg) for arg in command.argv]
        if command.argv[0] == sys.executable:
            argv[0] = "python"
        child_env = {key: self.translate(value) for key, value in (env or {}).items()}
        child_env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
        payload = (
            json.dumps({"argv": argv, "env": child_env, "cwd": self.translate(str(cwd))}).encode()
            + b"\n"
        )
        started = time.monotonic()
        timed_out = cancelled = truncated = False
        process = await asyncio.create_subprocess_exec(
            "docker",
            "start",
            "--attach",
            "--interactive",
            name,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert process.stdin and process.stdout and process.stderr

        async def drain(stream: asyncio.StreamReader, label: str) -> None:
            nonlocal truncated
            count = 0
            decoder = codecs.getincrementaldecoder("utf-8")("replace")
            while block := await stream.read(16384):
                remaining = max(0, self.output_limit - count)
                count += len(block)
                truncated |= len(block) > remaining
                text = decoder.decode(block[:remaining])
                if text:
                    await sink(label, text)
            tail = decoder.decode(b"", final=True)
            if tail:
                await sink(label, tail)

        readers = [
            asyncio.create_task(drain(process.stdout, "stdout")),
            asyncio.create_task(drain(process.stderr, "stderr")),
        ]
        try:
            async with asyncio.timeout(command.timeout_seconds):
                process.stdin.write(payload)
                await process.stdin.drain()
                process.stdin.close()
                await process.wait()
                await asyncio.gather(*readers)
        except TimeoutError:
            timed_out = True
        except asyncio.CancelledError:
            cancelled = True
        finally:
            stopped = await self.stop()
            if process.returncode is None:
                process.kill()
            await process.wait()
            await asyncio.gather(*readers, return_exceptions=True)
        state = json.loads(await docker("inspect", "--format", "{{json .State}}", name))
        return ProcessResult(
            returncode=state["ExitCode"],
            duration_ms=(time.monotonic() - started) * 1000,
            timed_out=timed_out,
            cancelled=cancelled,
            cleanup_complete=stopped,
            output_truncated=truncated,
        )


class DockerEnvironment:
    def __init__(self, image: str, verification: bool = False) -> None:
        self.image = image
        self.verification = verification

    async def resolve(self) -> dict[str, Any]:
        data = json.loads(await docker("image", "inspect", self.image))[0]
        self.image = data["Id"]
        return {
            "provider": "docker",
            "image_id": self.image,
            "image_digests": data["RepoDigests"],
            "network": "bridge",
            "verifier_network": "none",
            "cpus": 1,
            "memory_mb": 512,
            "pids_limit": 128,
            "root_filesystem": "read_only",
        }

    async def create(self, workspace: Path, execution_id: str) -> DockerSession:
        await asyncio.to_thread(workspace.mkdir, parents=True, exist_ok=True)
        session = DockerSession(workspace, self.image, self.verification)
        await session.prepare()
        return session
