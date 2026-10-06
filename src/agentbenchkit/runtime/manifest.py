"""Capture observed Agent identity and declared conditions without model requests."""

import asyncio
import hashlib
import platform
import shutil
from pathlib import Path
from typing import Any

from agentbenchkit.core.protocols import Environment, Harness
from agentbenchkit.environments.docker import DockerEnvironment
from agentbenchkit.environments.host import HostProcessEnvironment


async def agent_identity(
    harness: Harness, environment: Environment | None, directory: Path
) -> dict[str, Any]:
    workspace = directory / "identity" / "workspace"
    workspace.mkdir(parents=True)
    provider = (
        environment if isinstance(environment, DockerEnvironment) else HostProcessEnvironment()
    )
    session = await provider.create(workspace, "identity")
    output: list[str] = []

    async def sink(stream: str, text: str) -> None:
        if stream == "stdout":
            output.append(text)

    try:
        process = await session.execute(harness.version_command(), sink)
        if process.returncode != 0 or not process.cleanup_complete:
            raise RuntimeError("Agent version probe failed")
        identity = {
            "reported_version": "".join(output).strip()[:1000],
            "executable": harness.version_command().argv[0],
            "source_commit": None,
            "harness_version": "1",
        }
        executable = Path(harness.version_command().argv[0])
        if not isinstance(environment, DockerEnvironment) and await asyncio.to_thread(
            executable.is_file
        ):
            identity["executable_sha256"] = hashlib.sha256(
                await asyncio.to_thread(executable.read_bytes)
            ).hexdigest()
        return identity
    finally:
        await session.close()
        await asyncio.to_thread(shutil.rmtree, workspace.parent)


def runtime_identity() -> dict[str, Any]:
    package = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(package.rglob("*.py")):
        digest.update(path.relative_to(package).as_posix().encode())
        digest.update(path.read_bytes())
    return {
        "source_hash": digest.hexdigest(),
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
