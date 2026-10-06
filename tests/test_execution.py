import asyncio
import json
import sys
from pathlib import Path

from agentbenchkit.core.models import CommandSpec
from agentbenchkit.environments.host import HostSession
from agentbenchkit.storage.artifacts import Redactor, StreamRedactor, write_json


async def discard(stream: str, text: str) -> None:
    pass


async def test_process_drains_both_streams_and_bounds_output(tmp_path: Path) -> None:
    session = HostSession(tmp_path, output_limit=100)
    output = {"stdout": "", "stderr": ""}

    async def sink(stream: str, text: str) -> None:
        output[stream] += text

    result = await session.execute(
        CommandSpec(
            argv=(
                sys.executable,
                "-c",
                "import sys; print('x'*200000); print('y'*200000,file=sys.stderr)",
            )
        ),
        sink,
    )
    assert result.returncode == 0
    assert result.cleanup_complete
    assert result.output_truncated
    assert len(output["stdout"]) <= 100 and len(output["stderr"]) <= 100


async def test_timeout_kills_background_writer(tmp_path: Path) -> None:
    marker = tmp_path / "heartbeat"
    child = (
        "import pathlib,time\n"
        "p=pathlib.Path('heartbeat')\n"
        "while True:\n"
        " p.write_text(str(time.monotonic()))\n"
        " time.sleep(0.02)\n"
    )
    script = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(30)"
    )
    session = HostSession(tmp_path)
    result = await session.execute(
        CommandSpec(argv=(sys.executable, "-c", script), timeout_seconds=0.8), discard
    )
    assert result.timed_out and result.cleanup_complete
    assert marker.exists()
    before = marker.read_text()
    await asyncio.sleep(0.15)
    assert marker.read_text() == before


async def test_cancellation_stops_process(tmp_path: Path) -> None:
    started = asyncio.Event()

    async def sink(stream: str, text: str) -> None:
        if "ready" in text:
            started.set()

    session = HostSession(tmp_path)
    task = asyncio.create_task(
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
    await asyncio.wait_for(started.wait(), 5)
    task.cancel()
    result = await task
    assert result.cancelled and result.cleanup_complete
    assert session.process is not None and session.process.returncode is not None


async def test_normal_parent_exit_also_stops_background_writer(tmp_path: Path) -> None:
    child = (
        "import pathlib,time\n"
        "p=pathlib.Path('heartbeat')\n"
        "while True:\n"
        " p.write_text(str(time.monotonic()))\n"
        " time.sleep(0.02)\n"
    )
    wait_code = "while not pathlib.Path('heartbeat').exists():\n time.sleep(0.01)"
    script = (
        "import subprocess,sys,time,pathlib; "
        f"subprocess.Popen([sys.executable,'-c',{child!r}]); "
        f"exec({wait_code!r})"
    )
    result = await HostSession(tmp_path).execute(
        CommandSpec(argv=(sys.executable, "-c", script), timeout_seconds=3), discard
    )
    assert result.returncode == 0 and not result.timed_out and result.cleanup_complete
    marker = tmp_path / "heartbeat"
    before = marker.read_text()
    await asyncio.sleep(0.15)
    assert marker.read_text() == before


def test_secrets_split_at_every_boundary_are_redacted(tmp_path: Path) -> None:
    secret = "synthetic-secret-value"
    for split in range(1, len(secret)):
        stream = StreamRedactor(Redactor((secret,)))
        result = stream.feed("prefix:" + secret[:split])
        result += stream.feed(secret[split:] + ":suffix")
        result += stream.feed("", final=True)
        assert result == "prefix:[REDACTED]:suffix"
    path = tmp_path / "record.json"
    write_json(path, {"value": secret, "protocol_data": {"private": True}}, Redactor((secret,)))
    assert json.loads(path.read_text()) == {"value": "[REDACTED]"}
