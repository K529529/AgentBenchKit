import json
from pathlib import Path

from agentbenchkit.benchmarks.micro_swe import load_tasks
from agentbenchkit.core.models import CredentialRef, ModelSpec
from agentbenchkit.core.protocols import ProcessResult
from agentbenchkit.harnesses.codex import CodexHarness
from agentbenchkit.runtime.settings import AgentSettings


def test_codex_public_protocol_and_missing_capabilities() -> None:
    harness = CodexHarness("codex", docker=True)
    native = [
        {"type": "turn.started"},
        {"type": "item.started", "item": {"id": "i1", "type": "command_execution"}},
        {
            "type": "item.completed",
            "item": {"id": "i1", "type": "command_execution", "exit_code": 0},
        },
        {"type": "item.completed", "item": {"id": "i2", "type": "agent_message", "text": "done"}},
        {"type": "turn.completed", "usage": {"input_tokens": 50, "output_tokens": 10}},
    ]
    events = [event for row in native if (event := harness.decode(json.dumps(row))) is not None]
    assert events[1]["kind"] == "tool_started"
    assert events[2]["kind"] == "tool_finished"
    result = harness.result(ProcessResult(returncode=0, duration_ms=1), events)
    assert result.outcome == "COMPLETED" and result.final_answer == "done"
    assert harness.result(ProcessResult(returncode=1, duration_ms=1), events).outcome == "UNKNOWN"
    assert not harness.capabilities.model_input
    argv = harness.command(load_tasks()[0]).argv
    assert "--ephemeral" in argv and "--ignore-rules" in argv
    assert "danger-full-access" in argv


def test_auth_is_only_in_memory_not_configuration(tmp_path: Path) -> None:
    auth = tmp_path / "source.json"
    auth.write_text(
        json.dumps(
            {
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": "synthetic-access",
                    "refresh_token": "synthetic-refresh",
                },
            }
        )
    )
    settings = AgentSettings(
        CodexHarness("codex", docker=True),
        ModelSpec(
            model_id="model",
            provider_id="openai_chatgpt",
            credential=CredentialRef(kind="chatgpt_login"),
        ),
        auth_file=auth,
    )
    home = tmp_path / "home"
    env = settings.prepare(home)
    assert "ABK_MEMORY_HOME" in env
    assert not list(home.rglob("*.json"))
    manifest = json.dumps(settings.manifest())
    assert "synthetic-access" not in manifest
    assert settings.redactor.text("synthetic-access") == "[REDACTED]"
