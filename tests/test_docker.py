"""Explicit opt-in integration tests against a real local Docker daemon."""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from agentbenchkit.benchmarks.micro_swe import load_tasks
from agentbenchkit.core.models import CommandSpec
from agentbenchkit.core.status import Verdict
from agentbenchkit.environments.docker import DockerEnvironment, DockerSession, docker
from agentbenchkit.verification.candidate import collect
from agentbenchkit.verification.verifier import verify_candidate

pytestmark = pytest.mark.skipif(
    os.environ.get("ABK_TEST_DOCKER") != "1", reason="set ABK_TEST_DOCKER=1 for real Docker tests"
)


async def test_docker_secret_stdin_and_restrictions(tmp_path: Path) -> None:
    session = DockerSession(tmp_path, "python:3.12-slim")
    output = []

    async def sink(stream: str, text: str) -> None:
        output.append(text)

    try:
        result = await session.execute(
            CommandSpec(
                argv=(
                    sys.executable,
                    "-c",
                    "import os,pathlib; assert os.environ['EVAL_TEST_KEY']=='synthetic-only'; "
                    "pathlib.Path('new.py').write_text('answer=42'); print('inside')",
                )
            ),
            sink,
            {"EVAL_TEST_KEY": "synthetic-only"},
        )
        assert result.returncode == 0 and result.cleanup_complete
        assert (tmp_path / "new.py").read_text() == "answer=42"
        assert "inside" in "".join(output)
        assert session.name
        data = json.loads(await docker("inspect", session.name))[0]
        assert "synthetic-only" not in json.dumps(data)
        assert data["HostConfig"]["ReadonlyRootfs"]
        assert not data["State"]["Running"]
    finally:
        await session.close()


async def test_docker_timeout_freezes_background_writes(tmp_path: Path) -> None:
    session = DockerSession(tmp_path, "python:3.12-slim")

    async def sink(stream: str, text: str) -> None:
        pass

    script = (
        "import pathlib,time\nwhile True:\n"
        " pathlib.Path('beat').write_text(str(time.time()))\n time.sleep(.02)"
    )
    try:
        result = await session.execute(
            CommandSpec(argv=(sys.executable, "-c", script), timeout_seconds=2), sink
        )
        assert result.timed_out and result.cleanup_complete
        before = (tmp_path / "beat").read_text()
        await asyncio.sleep(0.15)
        assert before == (tmp_path / "beat").read_text()
    finally:
        await session.close()


@pytest.mark.parametrize("reference", [False, True])
async def test_fresh_docker_verification(tmp_path: Path, reference: bool) -> None:
    for task in load_tasks():
        folder = tmp_path / task.task_id
        manifest = collect(
            task.fixture,
            task.reference_candidate if reference else task.fixture,
            folder / "candidate",
        )
        result = await verify_candidate(
            task,
            folder / "candidate",
            manifest,
            folder / "verify",
            DockerEnvironment("python:3.12-slim", verification=True),
        )
        assert result.status == (Verdict.PASS if reference else Verdict.FAIL), result.reason


async def test_verifier_mount_is_readonly_and_has_no_model_key(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    assets = tmp_path / "protected"
    assets.mkdir()
    (assets / "owned.txt").write_text("evaluator")
    session = DockerSession(workspace, "python:3.12-slim", verification=True)

    async def sink(stream: str, text: str) -> None:
        pass

    script = (
        "import os,pathlib; assert 'DASHSCOPE_API_KEY' not in os.environ; "
        "pathlib.Path('/protected/owned.txt').write_text('tampered')"
    )
    try:
        result = await session.execute(CommandSpec(argv=(sys.executable, "-c", script)), sink)
        assert result.returncode != 0
        assert (assets / "owned.txt").read_text() == "evaluator"
        assert session.name
        data = json.loads(await docker("inspect", session.name))[0]
        assert data["HostConfig"]["NetworkMode"] == "none"
    finally:
        await session.close()


async def test_cancel_stops_real_container(tmp_path: Path) -> None:
    ready = asyncio.Event()
    session = DockerSession(tmp_path, "python:3.12-slim")

    async def sink(stream: str, text: str) -> None:
        if "ready" in text:
            ready.set()

    future = asyncio.create_task(
        session.execute(
            CommandSpec(
                argv=(
                    sys.executable,
                    "-c",
                    "import time; print('ready',flush=True); time.sleep(30)",
                )
            ),
            sink,
        )
    )
    try:
        await asyncio.wait_for(ready.wait(), 10)
        future.cancel()
        result = await future
        assert result.cancelled and result.cleanup_complete
        assert session.name
        assert await docker("inspect", "--format", "{{.State.Running}}", session.name) == "false"
    finally:
        await session.close()


async def test_auth_cache_uses_tmpfs_only(tmp_path: Path) -> None:
    session = DockerSession(tmp_path, "python:3.12-slim")

    async def sink(stream: str, text: str) -> None:
        pass

    script = (
        "import pathlib,os; "
        "auth=pathlib.Path('/agent-private/home/.codex/auth.json'); "
        "assert auth.read_text()=='synthetic-auth'; "
        "assert 'ABK_MEMORY_HOME' not in os.environ"
    )
    try:
        result = await session.execute(
            CommandSpec(argv=(sys.executable, "-c", script)),
            sink,
            {
                "ABK_MEMORY_HOME": json.dumps(
                    {
                        "directory": ".codex",
                        "config": 'model="test"',
                        "credential_file": "auth.json",
                        "auth": "synthetic-auth",
                    }
                )
            },
        )
        assert result.returncode == 0
        assert session.name
        data = json.loads(await docker("inspect", session.name))[0]
        assert "synthetic-auth" not in json.dumps(data)
        assert "/tmp" in data["HostConfig"]["Tmpfs"]
        assert not await asyncio.to_thread(lambda: list(tmp_path.rglob("auth.json")))
    finally:
        await session.close()
