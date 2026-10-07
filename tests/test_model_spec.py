import json
import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from agentbenchkit.cli import app
from agentbenchkit.core.models import CredentialRef, HarnessOptions, ModelSpec, ResolvedManifest
from agentbenchkit.harnesses.codex import CodexHarness
from agentbenchkit.harnesses.nexus import NexusHarness
from agentbenchkit.runtime.settings import AgentSettings, load_model


def model(**changes: object) -> ModelSpec:
    return ModelSpec.model_validate(
        {
            "model_id": "shared-model",
            "provider_id": "test-provider",
            "base_url": "https://provider.example/v1",
            "context_window": 32768,
            "reasoning_effort": "low",
            "credential": {"env_var": "ABK_TEST_KEY"},
            **changes,
        }
    )


def test_same_public_model_maps_to_both_native_configs() -> None:
    requested = model()
    nexus = NexusHarness("nexus").native_config(requested, HarnessOptions())
    codex = CodexHarness("codex", docker=True).native_config(requested, HarnessOptions())
    a, b = tomllib.loads(nexus.config_toml), tomllib.loads(codex.config_toml)
    assert a["model"]["name"] == b["model"] == requested.model_id
    assert a["model"]["base_url"] == b["model_providers"]["abk_provider"]["base_url"]
    assert b["model_providers"]["abk_provider"]["env_key"] == "ABK_TEST_KEY"
    assert b["model_providers"]["abk_provider"]["wire_api"] == "responses"
    assert nexus.wire_api == "chat_completions"
    assert requested.max_output_tokens is None
    assert nexus.effective_model.max_output_tokens == 8192
    assert codex.effective_model.max_output_tokens is None
    assert ModelSpec.model_validate_json(requested.model_dump_json()) == requested
    assert "ModelSpec" in str(ResolvedManifest.model_fields["model"].annotation)


@pytest.mark.parametrize("field,value", [("temperature", 0.5), ("top_p", 0.9), ("seed", 42)])
def test_unrepresentable_controls_rejected_before_credentials(field: str, value: object) -> None:
    for harness in (NexusHarness("nexus"), CodexHarness("codex", docker=True)):
        with pytest.raises(ValueError, match=field):
            AgentSettings(harness, model(**{field: value}))


@pytest.mark.parametrize("field", ["max_output_tokens", "request_timeout_seconds"])
def test_codex_never_silently_drops_requested_limits(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        AgentSettings(CodexHarness("codex"), model(**{field: 100}))


def test_shared_settings_use_only_isolated_native_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ABK_TEST_KEY", "synthetic-secret-value")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "user-personal-config"))
    for harness in (NexusHarness("nexus"), CodexHarness("codex", docker=True)):
        settings = AgentSettings(harness, model())
        home = tmp_path / harness.name
        env = settings.prepare(home)
        assert env["HOME"] == str(home)
        assert env["ABK_TEST_KEY"] == "synthetic-secret-value"
        if harness.name == "codex":
            assert env["CODEX_HOME"] == str(home / ".codex")
        assert "synthetic-secret-value" not in json.dumps(settings.manifest())
        assert all(
            "synthetic-secret-value" not in p.read_text() for p in home.rglob("*.*") if p.is_file()
        )


def test_api_configuration_must_be_explicit_and_secret_free(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        model(base_url=None)
    with pytest.raises(ValidationError):
        model(base_url="https://user:secret@provider.example/v1")
    with pytest.raises(ValidationError):
        model(api_key="must-not-be-inline")
    path = tmp_path / "model.json"
    path.write_text(model().model_dump_json())
    assert load_model(path) == model()


def test_chatgpt_is_smoke_only_and_requires_docker() -> None:
    spec = ModelSpec(
        model_id="test",
        provider_id="openai_chatgpt",
        credential=CredentialRef(kind="chatgpt_login"),
    )
    with pytest.raises(ValueError, match="Docker"):
        CodexHarness("codex").native_config(spec, HarnessOptions())
    with pytest.raises(ValueError, match="API-key"):
        NexusHarness("nexus").native_config(spec, HarnessOptions())
    native = CodexHarness("codex", docker=True).native_config(spec, HarnessOptions())
    assert native.controls["evaluation_class"] == "subscription_smoke"
    assert native.wire_api == "chatgpt"


def test_cli_reports_unsupported_fields_without_model_calls(tmp_path: Path) -> None:
    path = tmp_path / "model.json"
    path.write_text(model(max_output_tokens=512).model_dump_json())
    result = CliRunner().invoke(app, ["run", "micro_swe", "codex", "--model-config", str(path)])
    assert result.exit_code == 2
    assert "max_output_tokens" in result.output
    result = CliRunner().invoke(
        app,
        ["run", "micro_swe", "codex", "--model-config", str(path), "--reasoning-effort", "high"],
    )
    assert result.exit_code == 2 and "cannot be mixed" in result.output
