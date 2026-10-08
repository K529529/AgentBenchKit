import asyncio
import base64
import dataclasses
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agentbenchkit.core.models import CredentialRef, HarnessOptions, ModelSpec
from agentbenchkit.core.protocols import ProcessResult
from agentbenchkit.harnesses.qoder import QoderHarness
from agentbenchkit.harnesses.qoder_worker import limit_reason, safe_usage
from agentbenchkit.runtime.settings import AgentSettings


def qoder_model() -> ModelSpec:
    return ModelSpec(
        model_id="Qwen3.8-Flash",
        provider_id="qoder_cn",
        credential=CredentialRef(kind="qoder_login"),
        max_output_tokens=16384,
        reasoning_effort="low",
    )


def test_qoder_private_files_never_persist_in_workspace(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / ".auth").mkdir(parents=True)
    (source / ".auth/user").write_bytes(b"\x00opaque-login-cache")
    (source / ".auth/machine_id").write_text("synthetic-machine")
    settings = AgentSettings(QoderHarness(), qoder_model(), auth_file=source)
    home = tmp_path / "home"
    env = settings.prepare(home)
    private = json.loads(env["ABK_MEMORY_HOME"])
    assert base64.b64decode(private["files"][".auth/user"]) == b"\x00opaque-login-cache"
    assert not (home / ".qoder-cn/.auth").exists()
    assert "opaque-login-cache" not in json.dumps(settings.manifest())
    assert settings.redactor.text("synthetic-machine") == "[REDACTED]"
    assert env["QODERCN_CONFIG_DIR"] == "/agent-private/home/.qoder-cn"
    assert settings.manifest()["evaluation_class"] == "subscription_smoke"


def test_qoder_rejects_unsupported_controls_and_host_credentials() -> None:
    with pytest.raises(ValueError, match="tmpfs"):
        QoderHarness(docker=False).native_config(qoder_model(), HarnessOptions())
    with pytest.raises(ValueError, match="temperature"):
        QoderHarness().native_config(
            qoder_model().model_copy(update={"temperature": 0.2}), HarnessOptions()
        )
    with pytest.raises(ValueError, match="endpoint"):
        ModelSpec(**{**qoder_model().model_dump(), "base_url": "https://example.com"})
    native = QoderHarness().native_config(qoder_model(), HarnessOptions(max_credits=3))
    assert native.controls["max_credits"] == 3
    with pytest.raises(ValueError, match="private credential paths"):
        type(native)(**{**native.model_dump(), "credential_files": ["../escape"]})


def test_qoder_result_never_equates_process_exit_with_completion() -> None:
    harness = QoderHarness()
    process = ProcessResult(returncode=0, duration_ms=1)
    assert harness.result(process, []).outcome == "UNKNOWN"
    event = harness.decode('{"kind":"run_finished","data":{"outcome":"limited"}}')
    assert event is not None
    assert harness.result(process, [event]).outcome == "LIMITED"
    event = harness.decode('{"kind":"run_finished","data":{"outcome":"completed"}}')
    assert event is not None
    assert harness.result(process.model_copy(update={"returncode": 1}), [event]).outcome == "FAILED"


def test_credits_monitor_and_account_privacy() -> None:
    before = {"addOnQuota": {"remaining": 390}}
    assert (
        limit_reason(before, {"addOnQuota": {"remaining": 385}}, 5) == "account_credits_drop_limit"
    )
    assert limit_reason(before, {"session": {"total_credits": 5}}, 5) == "session_credits_limit"
    assert limit_reason(before, {"session": {"total_credits": 0}}, 5) is None
    assert limit_reason(before, {"isQuotaExceeded": True}, 5) == "account_quota_exceeded"
    observed = safe_usage({"userId": "private-id", "accessToken": "secret", **before})
    assert observed == before


def test_version_probe_uses_disposable_config(monkeypatch: pytest.MonkeyPatch) -> None:
    from agentbenchkit.harnesses import qoder_worker

    observed = []

    def version(argv: list[str], **kwargs: object) -> str:
        environment = kwargs["env"]
        assert isinstance(environment, dict)
        path = Path(environment["QODERCN_CONFIG_DIR"])
        assert path.is_dir()
        (path / "probe-state").write_text("synthetic")
        observed.append(path)
        return "1.1.65"

    monkeypatch.setattr("sys.argv", ["worker", "--version"])
    monkeypatch.setattr("subprocess.check_output", version)
    monkeypatch.setattr("importlib.metadata.version", lambda name: "1.0.15")
    qoder_worker.main()
    assert observed and not observed[0].exists()


@pytest.mark.parametrize("mode", ["request_limit", "empty_poll", "empty_initial"])
async def test_sdk_driver_separates_observer_and_bounds_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    from agentbenchkit.harnesses import qoder_worker

    @dataclasses.dataclass
    class Assistant:
        content: list[Any]
        model: str
        usage: dict[str, Any]

    @dataclasses.dataclass
    class Result:
        subtype: str = "success"
        is_error: bool = False
        num_turns: int = 2
        usage: dict[str, Any] = dataclasses.field(
            default_factory=lambda: {"input_tokens": 0, "output_tokens": 0}
        )
        total_credits: float = 5.1

    clients: list[Any] = []
    events: list[dict[str, Any]] = []
    original_sleep = asyncio.sleep

    async def fast_sleep(seconds: float) -> None:
        await original_sleep(0)

    class Client:
        def __init__(self, options: Any) -> None:
            self.index = len(clients)
            self.queried = self.interrupted = False
            self.polls = 0
            clients.append(self)

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def get_usage_info(self) -> Any:
            assert self.index == 1 and not self.queried
            self.polls += 1
            if mode == "empty_initial" or (mode == "empty_poll" and self.polls > 1):
                return None
            return {"addOnQuota": {"remaining": 390}}

        async def query(self, prompt: str) -> None:
            assert self.index == 0
            self.queried = True

        async def interrupt(self) -> None:
            self.interrupted = True

        async def receive_response(self) -> Any:
            if mode == "request_limit":
                # Duplicate delivery must not charge/count the same request twice.
                for request in ("a", "a", "b", "c"):
                    yield Assistant([], "Qwen3.8-Flash", {"request_id": request, "credits": 1.7})
            else:
                for _ in range(100):
                    if self.interrupted:
                        break
                    await original_sleep(0)
                assert self.interrupted
            yield Result()

    sdk = SimpleNamespace(
        QoderSDKClient=Client,
        QoderAgentOptions=lambda **kwargs: kwargs,
        qodercli_auth=lambda: None,
        AssistantMessage=Assistant,
        ResultMessage=Result,
        UserMessage=type("UserMessage", (), {}),
        ToolUseBlock=type("ToolUseBlock", (), {}),
        ToolResultBlock=type("ToolResultBlock", (), {}),
    )
    original_import = importlib.import_module
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name, *args: sdk if name == "qodercn_agent_sdk" else original_import(name, *args),
    )
    monkeypatch.setattr("importlib.metadata.version", lambda name: "1.0.15")
    monkeypatch.setattr("asyncio.sleep", fast_sleep)
    monkeypatch.setattr(
        qoder_worker,
        "emit",
        lambda kind, data=None, **kw: events.append({"kind": kind, "data": data, **kw}),
    )
    monkeypatch.setenv("QODERCN_CONFIG_DIR", str(tmp_path))
    (tmp_path / "config.toml").write_text(
        QoderHarness().native_config(qoder_model(), HarnessOptions()).config_toml
    )
    if mode == "empty_initial":
        with pytest.raises(RuntimeError, match="before inference"):
            await qoder_worker.run("task")
        assert not any(client.queried for client in clients)
        return
    await qoder_worker.run("task")
    assert clients[0].queried and clients[0].interrupted
    assert not clients[1].queried
    terminal = next(e["data"] for e in reversed(events) if e["kind"] == "run_finished")
    assert terminal["outcome"] == "limited"
    assert terminal["model_calls"] is None
    assert terminal["usage"]["input_tokens"] is None
    if mode == "request_limit":
        assert terminal["observed_request_count"] == 3
        assert terminal["reported_request_credits"] == pytest.approx(5.1)
    else:
        assert terminal["reason"] == "usage_monitor_unavailable"
