"""Bounded evaluator subprocesses with evidence and recoverable process ownership."""

import asyncio
from pathlib import Path
from typing import Any

from agentbenchkit.core.models import CommandSpec
from agentbenchkit.environments.host import HostSession
from agentbenchkit.storage.artifacts import write_json


async def run_worker(
    python: str, script: Path, spec: dict[str, Any], directory: Path, seconds: float
) -> None:
    await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
    write_json(directory / "input.json", spec)
    process_workspace = Path(spec.get("resource_workspace", str(directory)))
    await asyncio.to_thread(process_workspace.mkdir, parents=True, exist_ok=True)
    session = HostSession(process_workspace)
    try:
        with (
            (directory / "stdout.log").open("w", encoding="utf-8") as out,
            (directory / "stderr.log").open("w", encoding="utf-8") as err,
        ):

            async def sink(stream: str, text: str) -> None:
                (out if stream == "stdout" else err).write(text)

            process = await session.execute(
                CommandSpec(
                    argv=(
                        python,
                        str(await asyncio.to_thread(script.resolve)),
                        str((directory / "input.json").resolve()),
                    ),
                    timeout_seconds=seconds,
                ),
                sink,
            )
        write_json(directory / "process.json", process.model_dump())
        if process.returncode != 0 or process.timed_out or not process.cleanup_complete:
            raise RuntimeError("official benchmark worker failed; see preserved logs")
    finally:
        await session.close()
