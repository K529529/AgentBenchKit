import hashlib
import tomllib
import zipfile
from pathlib import Path

import pytest
from pydantic import JsonValue

from agentbenchkit.benchmarks.images import build
from agentbenchkit.core.protocols import ProcessResult
from agentbenchkit.harnesses.nexus import NexusHarness
from agentbenchkit.harnesses.nexus_evidence import archive_sessions, statistics
from agentbenchkit.runtime.settings import AgentSettings
from agentbenchkit.storage.artifacts import Redactor


def test_native_roundtrip_and_compaction_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config.toml"
    config.write_text("""[model]
name="m"
provider="openai"
base_url="https://example.test/v1"
api_key_env="TEST_MAIN"
context_window=100000
[compaction_model]
name="compact"
api_key_env="TEST_COMPACT"
[runtime]
max_steps=50
response_language="en"
[security]
mode="local"
[multi_agent]
enabled=false
allowNestedSubagents=false
max_agents=3
[multi_agent.roles.scout]
reasoning_effort="low"
[memory]
enabled=false
[mcp.servers]
[web]
enabled=false
[tracing]
enabled=false
""")
    monkeypatch.setenv("TEST_MAIN", "main-secret")
    monkeypatch.setenv("TEST_COMPACT", "compact-secret")
    harness = NexusHarness("nexus")
    model, options = harness.import_model(config)
    settings = AgentSettings(harness, model, options)
    actual = tomllib.loads(settings.native.config_toml)
    expected = tomllib.loads(config.read_text())
    for name in expected.keys() - {"model"}:
        assert actual[name] == expected[name]
    assert actual["model"]["provider"] == "openai"
    env = settings.prepare(tmp_path / "isolated")
    assert env["TEST_COMPACT"] == "compact-secret"
    assert settings.redactor.text("compact-secret main-secret") == "[REDACTED] [REDACTED]"
    config.write_text(config.read_text() + "\n[unsupported]\nx=1\n")
    with pytest.raises(ValueError, match="sections"):
        harness.import_model(config)


def event(kind: str, data: dict[str, JsonValue], child: bool = False) -> dict[str, JsonValue]:
    if child:
        return {"kind": "subagent_event", "data": {"agent_id": "child", "kind": kind, "data": data}}
    return {"kind": kind, "data": data}


def test_tree_attempts_snapshots_cache_and_root_outcome() -> None:
    usage: dict[str, JsonValue] = {
        "input_tokens": 10,
        "output_tokens": 2,
        "total_tokens": 12,
        "cached_input_tokens": 8,
    }
    events = [
        event("model_started", {"request_id": "r"}),
        event("model_finished", {"request_id": "r", "usage": usage}),
        event("model_started", {"request_id": "c", "purpose": "compaction"}, True),
        event("model_finished", {"request_id": "c", "usage": usage}, True),
        event("compaction_usage", {"reported_input_tokens": 10}, True),
        event("run_finished", {"outcome": "completed", "final_text": "ROOT"}),
        event("run_finished", {"outcome": "failed", "agent_id": "child"}),
        event("run_finished", {"outcome": "failed", "usage": usage}, True),
    ]
    events.append(events[3])
    stats = statistics(events)
    assert stats["total_tokens"] == 24
    assert stats["cached_input_tokens"] == 16
    assert stats["agent_count"] == 2 and stats["delegated"] is True
    result = NexusHarness("nexus").result(ProcessResult(returncode=0, duration_ms=1), events)
    assert result.final_answer == "ROOT" and result.outcome == "COMPLETED"
    events.append(event("model_started", {"request_id": "unfinished"}, True))
    assert statistics(events)["total_tokens"] is None
    assert statistics(events)["total_tokens_known"] == 24


def test_archive_preserves_only_sessions_and_redacts(tmp_path: Path) -> None:
    home = tmp_path / "home"
    source = home / ".nexus/sessions/root/child.jsonl"
    source.parent.mkdir(parents=True)
    source.write_text('{"key":"secret-value"}\n')
    (home / "credentials").write_text("secret-value")
    dest = tmp_path / "evidence"
    archive_sessions(home, dest, Redactor(("secret-value",)))
    assert "secret-value" not in (dest / "root/child.jsonl").read_text()
    assert not (dest / "credentials").exists()
    assert (dest / "manifest.json").exists()


def test_image_rejects_mismatched_source_before_docker(tmp_path: Path) -> None:
    uv = tmp_path / "uv"
    uv.write_bytes(b"\x7fELF")
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.comment = b"a" * 40
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="commit"):
        build("official@sha256:" + "a" * 64, "tag", uv, archive, "b" * 40, digest)


async def test_runner_archives_before_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_runtime import ControlledHarness

    from agentbenchkit.benchmarks.micro_swe import MicroSweAdapter
    from agentbenchkit.runtime import runner

    original = runner.remove_work
    checked = []

    def remove(path: Path, root: Path) -> None:
        archived = list(root.parent.glob("tasks/*/*/executions/*/nexus-sessions/manifest.json"))
        assert archived, "archive must exist before workspace deletion"
        checked.append(True)
        original(path, root)

    class Adapter(MicroSweAdapter):
        async def prepare(self, task: object, workspace: Path, evidence: Path) -> None:
            await super().prepare(task, workspace, evidence)  # type: ignore[arg-type]
            log = workspace.parent / "agent_home/.nexus/sessions/root/run.jsonl"
            log.parent.mkdir(parents=True)
            log.write_text('{"event":"root and child logs"}\n')

    monkeypatch.setattr(runner, "remove_work", remove)
    harness = ControlledHarness(True)
    harness.name = "nexus"
    adapter = Adapter()
    await runner.evaluate(adapter.load_tasks(("clamp",)), harness, tmp_path, benchmark=adapter)
    assert checked == [True]
