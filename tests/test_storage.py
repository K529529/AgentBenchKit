import asyncio
import json
from pathlib import Path

import pytest
from test_runtime import ControlledHarness

from agentbenchkit.benchmarks.micro_swe import load_tasks
from agentbenchkit.core.events import Event
from agentbenchkit.runtime.runner import evaluate
from agentbenchkit.storage.index import connect, list_runs, rebuild, resolve_run
from agentbenchkit.storage.trajectory import read_events


async def test_index_is_rebuildable_from_evidence(tmp_path: Path) -> None:
    directory = await evaluate(load_tasks(("clamp",)), ControlledHarness(True), tmp_path)
    before = list_runs(tmp_path)
    db = connect(tmp_path)
    with db:
        db.execute("DELETE FROM runs")
        db.execute("DELETE FROM samples")
    db.close()
    assert rebuild(tmp_path) == 1
    assert list_runs(tmp_path) == before
    assert resolve_run(tmp_path, directory.name) == directory
    for name in ("../outside", "..", "a/b", "a\\b"):
        with pytest.raises(ValueError):
            resolve_run(tmp_path, name)
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["harness"]["reported_version"].startswith("Python")
    assert manifest["framework"]["source_hash"]
    assert manifest["tasks"][0]["verifier_hash"]


def test_only_truncated_final_jsonl_line_is_tolerated(tmp_path: Path) -> None:
    path = tmp_path / "trajectory.jsonl"
    event = Event(
        event_id="e",
        run_id="r",
        task_id="t",
        sample_id="s",
        physical_execution_id="x",
        seq=1,
        timestamp="now",
        source="test",
        type="event",
    )
    path.write_text(event.model_dump_json() + '\n{"seq":', encoding="utf-8")
    events, incomplete = read_events(path)
    assert len(events) == 1 and incomplete
    path.write_text('{"broken":\n' + event.model_dump_json() + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        read_events(path)


async def test_corrupt_database_rebuild_keeps_source_evidence(tmp_path: Path) -> None:
    directory = await evaluate(load_tasks(("clamp",)), ControlledHarness(True), tmp_path)
    source = (directory / "manifest.json").read_bytes()
    (tmp_path / "index.sqlite3").write_bytes(b"not a sqlite database")
    assert rebuild(tmp_path) == 1
    assert list_runs(tmp_path)[0]["run_id"] == directory.name
    assert (directory / "manifest.json").read_bytes() == source
    assert await asyncio.to_thread(lambda: list(tmp_path.glob("index.sqlite3.corrupt-*")))
