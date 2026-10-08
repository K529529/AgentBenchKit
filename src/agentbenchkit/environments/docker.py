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
from typing import Any, Literal

from pydantic import Field

from agentbenchkit.core.models import CommandSpec, Contract
from agentbenchkit.core.protocols import OutputSink, ProcessResult, StartupError
from agentbenchkit.storage.artifacts import write_json

BOOTSTRAP = """import json,os,pathlib,sys
spec=json.loads(sys.stdin.readline())
material=spec['env'].pop('ABK_MEMORY_HOME',None)
if material:
    settings=json.loads(material)
    home=pathlib.Path('/agent-private/home')
    home.mkdir(mode=0o700)
    config=home/settings['directory']
    config.mkdir(mode=0o700)
    (config/'config.toml').write_text(settings['config'],encoding='utf-8')
    target=config/settings['credential_file']
    target.write_text(settings['auth'],encoding='utf-8')
    target.chmod(0o600)
os.chdir(spec['cwd'])
os.environ.update(spec['env'])
os.execvp(spec['argv'][0],spec['argv'])
"""


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


class DockerLimits(Contract):
    memory_mb: int = Field(default=512, ge=128)
    cpus: int = Field(default=1, ge=1)
    pids: int = Field(default=128, ge=32)
    readonly: bool = True
    workspace_readonly: bool | None = None
    verification_network: Literal["none", "bridge"] = "none"
    workdir: str = "/workspace"
    python: str = "python"


class DockerSession:
    def __init__(
        self,
        workspace: Path,
        image: str,
        verification: bool = False,
        limits: DockerLimits | None = None,
    ) -> None:
        self.limits = limits or DockerLimits()
        self.workspace = workspace.resolve()
        self.image = image
        self.verification = verification
        self.name: str | None = None
        self.paths = {str(self.workspace): self.limits.workdir}
        self.output_limit = 2_000_000
        self.remove_image_on_close = False

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

    async def _close_container(self) -> None:
        if not await self.stop():
            raise RuntimeError("Docker stop not confirmed")
        if self.name:
            await docker("rm", self.name)
            self.name = None

    async def close(self) -> None:
        await self._close_container()
        if self.remove_image_on_close:
            await docker("image", "rm", self.image)
            self.remove_image_on_close = False

    def translate(self, value: str) -> str:
        for source, destination in sorted(self.paths.items(), key=lambda pair: -len(pair[0])):
            if value == source or value.startswith((source + "/", source + "\\")):
                return destination + value[len(source) :].replace("\\", "/")
        return value

    async def prepare(self) -> None:
        await self._close_container()
        name = "abk-" + uuid.uuid4().hex
        network = self.limits.verification_network if self.verification else "bridge"
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
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            str(self.limits.pids),
            "--memory",
            f"{self.limits.memory_mb}m",
            "--cpus",
            str(self.limits.cpus),
            "--network",
            network,
            "--user",
            user,
            "--tmpfs",
            "/tmp:rw,nosuid,size=128m,mode=1777",
            "--tmpfs",
            "/agent-private:rw,nosuid,size=64m,mode=1777",
            "--log-driver",
            "none",
        ]
        if self.limits.readonly:
            args.append("--read-only")
        workspace_readonly = (
            self.verification
            if self.limits.workspace_readonly is None
            else self.limits.workspace_readonly
        )
        mounts = [(self.workspace, self.limits.workdir, workspace_readonly)]
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
        args.extend(
            [
                "--workdir",
                self.limits.workdir,
                "--entrypoint",
                self.limits.python,
                self.image,
                "-c",
                BOOTSTRAP,
            ]
        )
        write_json(
            self.workspace.parent / "docker-resource.json",
            {"name": name, "workspace": str(self.workspace)},
        )
        creation = asyncio.create_task(docker(*args))
        try:
            await asyncio.shield(creation)
        except asyncio.CancelledError:
            # Docker may create the resource after its CLI caller is cancelled.
            # Adopt the completed create before unwinding the Environment factory.
            try:
                await creation
            except (OSError, RuntimeError, TimeoutError):
                pass
            else:
                self.name = name
                await self.close()
            raise
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
    def __init__(
        self,
        image: str,
        verification: bool = False,
        limits: DockerLimits | None = None,
        ephemeral: bool = False,
    ) -> None:
        self.image = image
        self.verification = verification
        self.limits = limits or DockerLimits()
        self.ephemeral = ephemeral

    async def resolve(self) -> dict[str, Any]:
        data = json.loads(await docker("image", "inspect", self.image))[0]
        self.image = data["Id"]
        return {
            "provider": "docker",
            "image_id": self.image,
            "image_digests": data["RepoDigests"],
            "image_labels": data["Config"].get("Labels") or {},
            "os": data["Os"],
            "architecture": data["Architecture"],
            "shell": "/bin/sh",
            "network": self.limits.verification_network if self.verification else "bridge",
            "verifier_network": self.limits.verification_network,
            "cpus": self.limits.cpus,
            "memory_mb": self.limits.memory_mb,
            "pids_limit": self.limits.pids,
            "root_filesystem": "read_only" if self.limits.readonly else "writable",
            "workspace_read_only": self.verification
            if self.limits.workspace_readonly is None
            else self.limits.workspace_readonly,
            "workdir": self.limits.workdir,
            "bootstrap_python": self.limits.python,
        }

    async def create(self, workspace: Path, execution_id: str) -> DockerSession:
        await asyncio.to_thread(workspace.mkdir, parents=True, exist_ok=True)
        session = DockerSession(workspace, self.image, self.verification, self.limits)
        try:
            await session.prepare()
        except BaseException:
            if self.ephemeral:
                await docker("image", "rm", self.image)
            raise
        session.remove_image_on_close = self.ephemeral
        return session
