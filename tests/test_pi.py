import base64
import gzip
import io
import json
import tomllib
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import JsonValue

from agentbenchkit.core.models import CredentialRef, HarnessOptions, ModelSpec
from agentbenchkit.core.protocols import ProcessResult
from agentbenchkit.harnesses.pi import PiHarness


def events(*rows: dict[str, JsonValue]) -> list[dict[str, JsonValue]]:
    harness = PiHarness()
    return [e for row in rows if (e := harness.decode(json.dumps(row))) is not None]


def message(reason: str = "stop") -> dict[str, JsonValue]:
    return {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "stopReason": reason,
            "content": [{"type": "text", "text": "done"}],
            "usage": {"input": 10, "output": 3, "cacheRead": 5, "cacheWrite": 0, "totalTokens": 18},
        },
    }


def test_terminal_requires_settlement_and_usage_is_not_double_counted() -> None:
    h = PiHarness()
    rows = events(message(), {"type": "agent_end", "messages": [message()["message"]]})
    assert h.result(ProcessResult(returncode=0, duration_ms=1), rows).outcome == "UNKNOWN"
    rows += events({"type": "agent_settled", "aborted": False})
    result = h.result(ProcessResult(returncode=0, duration_ms=1), rows)
    assert result.outcome == "COMPLETED"
    assert result.final_answer == "done"
    assert result.reported_usage["total_tokens"] == 18
    assert h.result(ProcessResult(returncode=1, duration_ms=1), rows).outcome == "UNKNOWN"
    assert (
        h.result(ProcessResult(returncode=0, duration_ms=1, output_truncated=True), rows).outcome
        == "UNKNOWN"
    )


@pytest.mark.parametrize(
    "reason,expected", [("error", "UNKNOWN"), ("length", "LIMITED"), ("toolUse", "UNKNOWN")]
)
def test_provider_error_is_not_agent_failure(reason: str, expected: str) -> None:
    assert (
        PiHarness()
        .result(
            ProcessResult(returncode=0, duration_ms=1),
            events(message(reason), {"type": "agent_settled", "aborted": False}),
        )
        .outcome
        == expected
    )


def test_timeout_cancel_and_tool_identity() -> None:
    h = PiHarness()
    assert (
        h.result(ProcessResult(returncode=None, duration_ms=1, timed_out=True), []).outcome
        == "LIMITED"
    )
    assert (
        h.result(ProcessResult(returncode=None, duration_ms=1, cancelled=True), []).outcome
        == "ABORTED"
    )
    row = h.decode(
        '{"type":"tool_execution_end","toolCallId":"c1","toolName":"bash","isError":true}'
    )
    assert row and row["kind"] == "tool_finished"
    assert row["data"] == {"call_id": "c1", "name": "bash", "arguments": None, "is_error": True}
    assert h.decode("not json") is None
    assert h.decode("[]") is None


def test_config_explicit_limits_and_no_credential_value() -> None:
    model = ModelSpec(
        model_id="deepseek-flash",
        provider_id="deepseek",
        base_url="https://api.deepseek.com",
        credential=CredentialRef(env_var="DS_KEY"),
        context_window=1000000,
        max_output_tokens=8192,
        reasoning_effort="off",
    )
    native = PiHarness().native_config(model, HarnessOptions())
    config = tomllib.loads(native.config_toml)
    assert config["model"]["credential"]["env_var"] == "DS_KEY"
    assert native.config_home_env == "PI_CODING_AGENT_DIR"
    with pytest.raises(ValueError, match="step/credit"):
        PiHarness().native_config(model, HarnessOptions(max_steps=10))


def test_worker_public_files_and_exec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from agentbenchkit.harnesses import pi_worker

    home = tmp_path / "agent-home"
    home.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(home))
    model = ModelSpec(
        model_id="deepseek-flash",
        provider_id="deepseek",
        base_url="https://api.deepseek.com",
        credential=CredentialRef(env_var="DS_KEY"),
        context_window=1000000,
        max_output_tokens=8192,
        reasoning_effort="off",
    )
    (home / "config.toml").write_text(
        PiHarness().native_config(model, HarnessOptions()).config_toml
    )
    monkeypatch.setattr(
        "agentbenchkit.harnesses.pi_worker.subprocess.check_output", lambda *a, **kw: "1.4.0\n"
    )
    calls: list[list[str]] = []
    child = Mock()
    child.stdout = io.StringIO(
        '{"type":"agent_start"}\n{"type":"turn_start"}\n'
        + json.dumps(message())
        + '\n{"type":"agent_settled","aborted":false}\n'
    )
    child.wait.return_value = 0
    child.poll.return_value = 0

    def popen(argv: list[str], **kwargs: object) -> Mock:
        calls.append(argv)
        return child

    monkeypatch.setattr("agentbenchkit.harnesses.pi_worker.subprocess.Popen", popen)
    with pytest.raises(SystemExit) as finished:
        pi_worker.launch("literal task with spaces")
    assert finished.value.code == 0
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    terminal = next(e for e in records if e["type"] == "agent_settled")
    assert terminal["abk_summary"]["usage"]["total_tokens"] == 18
    assert terminal["abk_summary"]["model_calls"] == 1
    decoded = PiHarness().decode(json.dumps(terminal))
    assert decoded and decoded["data"] == terminal["abk_summary"]
    archived = "".join(
        gzip.decompress(base64.b64decode(e["data"])).decode("utf-8")
        for e in records
        if e["type"] == "abk_native_archive"
    )
    assert archived == (home / "native-events.jsonl").read_text()
    assert (home / "native-events.jsonl").read_text().startswith('{"type":"agent_start"}')
    models = json.loads((home / "models.json").read_text())
    provider = models["providers"]["deepseek"]
    assert provider["apiKey"] == "$DS_KEY"
    assert provider["models"][0]["maxTokens"] == 8192
    assert provider["models"][0]["samplingParams"]["thinking"] == {"type": "disabled"}
    assert calls[0][-2:] == ["--", "literal task with spaces"]
    assert "--no-extensions" in calls[0] and "--no-context-files" in calls[0]
    assert json.loads((home / "settings.json").read_text())["cacheWarming"] == "off"
    (workspace / ".pi").mkdir()
    with pytest.raises(ValueError, match="isolation review"):
        pi_worker.launch("task")
    monkeypatch.setattr(
        "agentbenchkit.harnesses.pi_worker.subprocess.check_output", lambda *a, **kw: "1.3.0\n"
    )
    with pytest.raises(ValueError, match="version mismatch"):
        pi_worker.launch("task")
