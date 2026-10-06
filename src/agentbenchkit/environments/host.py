"""Trusted host execution with bounded output and process-tree termination."""

import asyncio
import codecs
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from agentbenchkit.core.models import CommandSpec
from agentbenchkit.core.protocols import OutputSink, ProcessResult
from agentbenchkit.environments.windows_job import WindowsJob
from agentbenchkit.storage.artifacts import write_json

# Do not inherit unrelated model keys, user config overrides, or Python startup hooks.
BASE_ENV = (
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "TEMP",
    "TMP",
    "LANG",
    "LC_ALL",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
)
WINDOWS_GATE = (
    "import subprocess,sys; "
    "token=sys.stdin.buffer.read(1); "
    "sys.exit(subprocess.call(sys.argv[1:],stdin=subprocess.DEVNULL) if token==b'x' else 125)"
)


def clean_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    result = {key: value for key, value in os.environ.items() if key.upper() in BASE_ENV}
    result.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    result.update(extra or {})
    return result


def process_start(pid: int) -> str | None:
    try:
        return Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()[19]
    except (FileNotFoundError, ProcessLookupError):
        # A fast child may be reaped between spawn completion and this read.
        return None


class HostSession:
    def __init__(self, workspace: Path, output_limit: int = 2_000_000) -> None:
        self.workspace = workspace.resolve()
        self.output_limit = output_limit
        self.process: asyncio.subprocess.Process | None = None
        self.job: WindowsJob | None = None

    async def stop(self) -> bool:
        process = self.process
        if process is None:
            return True
        try:
            if self.job is not None:
                self.job.close()
                self.job = None
            elif sys.platform != "win32":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.returncode is None:
                process.kill()
            if process.returncode is None:
                await asyncio.wait_for(process.wait(), 5)
            return True
        except (OSError, TimeoutError):
            return False

    async def close(self) -> None:
        if not await self.stop():
            raise RuntimeError("host process cleanup incomplete")

    async def execute(
        self,
        command: CommandSpec,
        sink: OutputSink,
        env: dict[str, str] | None = None,
    ) -> ProcessResult:
        cwd = (self.workspace / command.cwd).resolve()
        if not cwd.is_relative_to(self.workspace):
            raise ValueError("command cwd escapes workspace")
        argv = list(command.argv)
        started = time.monotonic()
        timed_out = False
        cancelled = False
        truncated = False
        readers: list[asyncio.Task[None]] = []
        process: asyncio.subprocess.Process | None = None

        async def drain(stream: asyncio.StreamReader, name: str) -> None:
            nonlocal truncated
            count = 0
            decoder = codecs.getincrementaldecoder("utf-8")("replace")
            while block := await stream.read(16384):
                remaining = max(0, self.output_limit - count)
                count += len(block)
                if len(block) > remaining:
                    truncated = True
                text = decoder.decode(block[:remaining])
                if text:
                    await sink(name, text)
            tail = decoder.decode(b"", final=True)
            if tail:
                await sink(name, tail)

        spawn_argv = (
            [sys.executable, "-c", WINDOWS_GATE, *argv] if sys.platform == "win32" else argv
        )
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW
        spawn = asyncio.create_task(
            asyncio.create_subprocess_exec(
                *spawn_argv,
                cwd=cwd,
                env=clean_environment(env),
                stdin=asyncio.subprocess.PIPE
                if sys.platform == "win32"
                else asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=creation_flags,
                start_new_session=sys.platform != "win32",
            )
        )
        try:
            # Cancellation during spawn still adopts the process before cleanup.
            try:
                process = await asyncio.shield(spawn)
            except asyncio.CancelledError:
                process = await spawn
                self.process = process
                raise
            self.process = process
            if sys.platform != "win32":
                start = await asyncio.to_thread(process_start, process.pid)
                if start is not None:
                    write_json(
                        self.workspace.parent / "host-resource.json",
                        {"pid": process.pid, "start": start},
                    )
            if sys.platform == "win32":
                self.job = WindowsJob(process.pid)
                assert process.stdin is not None
                process.stdin.write(b"x")
                await process.stdin.drain()
                process.stdin.close()
            assert process.stdout is not None and process.stderr is not None
            readers = [
                asyncio.create_task(drain(process.stdout, "stdout")),
                asyncio.create_task(drain(process.stderr, "stderr")),
            ]
            async with asyncio.timeout(command.timeout_seconds):
                # Reading concurrently avoids pipe deadlocks. Exit may precede descendant EOF.
                # Process.wait also waits for inherited pipe handles held by descendants.
                while process.returncode is None:  # noqa: ASYNC110
                    await asyncio.sleep(0.01)
                await self.stop()
                await asyncio.gather(*readers)
        except TimeoutError:
            timed_out = True
        except asyncio.CancelledError:
            cancelled = True
        finally:
            stopped = await self.stop()
            if readers:
                try:
                    await asyncio.wait_for(asyncio.gather(*readers), 5)
                except (TimeoutError, asyncio.CancelledError):
                    for reader in readers:
                        reader.cancel()
                    await asyncio.gather(*readers, return_exceptions=True)
                    stopped = False
        return ProcessResult(
            returncode=process.returncode if process else None,
            duration_ms=(time.monotonic() - started) * 1000,
            timed_out=timed_out,
            cancelled=cancelled,
            cleanup_complete=stopped,
            output_truncated=truncated,
        )


class HostProcessEnvironment:
    async def create(self, workspace: Path, execution_id: str) -> HostSession:
        await asyncio.to_thread(workspace.mkdir, parents=True, exist_ok=True)
        return HostSession(workspace)
