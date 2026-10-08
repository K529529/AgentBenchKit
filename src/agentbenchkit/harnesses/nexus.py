"""Public CLI adapter for Nexus v0.2.0; no Agent source changes."""

import json
import tomllib
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from pydantic import JsonValue

from agentbenchkit.core.models import (
    AgentResult,
    Capabilities,
    CommandSpec,
    CredentialRef,
    HarnessOptions,
    ModelSpec,
    NativeAgentConfig,
    TaskSpec,
)
from agentbenchkit.core.protocols import ProcessResult
from agentbenchkit.core.status import AgentOutcome
from agentbenchkit.harnesses.config import toml_config

NEXUS_COMMIT = "677fc997dcdc2f369fa8d4a667d400de99e35f84"


class NexusHarness:
    name = "nexus"
    capabilities = Capabilities(
        final_answer=True,
        tool_calls=True,
        tool_results=True,
        model_usage=True,
        model_output="partial",
        native_call_ids=True,
    )

    def __init__(self, executable: Path | str) -> None:
        self.executable = executable.resolve() if isinstance(executable, Path) else executable

    @staticmethod
    def import_model(source: Path) -> tuple[ModelSpec, HarnessOptions]:
        with source.open("rb") as stream:
            config = tomllib.load(stream)
        native = config["model"]
        allowed = {
            "name",
            "base_url",
            "api_key_env",
            "context_window",
            "max_output_tokens",
            "reasoning_effort",
            "include_usage",
            "request_timeout_seconds",
            "output_token_parameter",
        }
        if native.keys() - allowed:
            raise ValueError("unsupported Nexus model fields; refusing silent loss")
        endpoint = native.get("base_url", "https://api.openai.com/v1")
        spec = ModelSpec(
            model_id=native["name"],
            provider_id=urlsplit(endpoint).hostname or "unknown",
            base_url=endpoint,
            credential=CredentialRef(env_var=native.get("api_key_env", "NEXUS_MODEL_API_KEY")),
            context_window=native.get("context_window"),
            max_output_tokens=native.get("max_output_tokens", 8192),
            reasoning_effort=native.get("reasoning_effort"),
            request_timeout_seconds=native.get("request_timeout_seconds", 120),
        )
        options = HarnessOptions(
            max_steps=config.get("runtime", {}).get("max_steps", 40),
            include_usage=native.get("include_usage", True),
            output_token_parameter=native.get("output_token_parameter", "max_tokens"),
        )
        return spec, options

    def native_config(self, model: ModelSpec, options: HarnessOptions) -> NativeAgentConfig:
        if options.max_credits is not None:
            raise ValueError("Nexus does not expose Qoder Credits limits")
        if model.credential.kind != "api_key":
            raise ValueError("Nexus requires API-key authentication")
        unsupported = [
            name for name in ("temperature", "top_p", "seed") if getattr(model, name) is not None
        ]
        if unsupported:
            raise ValueError(f"Nexus v0.2.0 cannot configure: {', '.join(unsupported)}")
        if model.context_window is None:
            raise ValueError("Nexus requires an explicit context_window")
        effective = model.model_copy(
            update={
                "max_output_tokens": model.max_output_tokens or 8192,
                "request_timeout_seconds": model.request_timeout_seconds or 120,
            }
        )
        assert effective.max_output_tokens is not None
        if model.context_window <= effective.max_output_tokens + 1024:
            raise ValueError("Nexus context_window must exceed max_output_tokens + 1024")
        native = {
            "name": effective.model_id,
            "base_url": effective.base_url,
            "api_key_env": effective.credential.env_var,
            "context_window": effective.context_window,
            "max_output_tokens": effective.max_output_tokens,
            "reasoning_effort": effective.reasoning_effort,
            "request_timeout_seconds": effective.request_timeout_seconds,
            "include_usage": options.include_usage,
            "output_token_parameter": options.output_token_parameter,
        }
        controls: dict[str, JsonValue] = {
            "max_steps": options.max_steps or 40,
            "include_usage": options.include_usage,
            "output_token_parameter": options.output_token_parameter,
            "mcp_servers": [],
            "skills": [],
            "tools": None,
        }
        return NativeAgentConfig(
            config_directory=".nexus",
            effective_model=effective,
            credential_env=model.credential.env_var,
            wire_api="chat_completions",
            controls=controls,
            config_toml=toml_config(
                {"model": native, "runtime": {"max_steps": options.max_steps or 40}}
            ),
        )

    def version_command(self) -> CommandSpec:
        return CommandSpec(argv=(str(self.executable), "--version"), timeout_seconds=15)

    def command(self, task: TaskSpec) -> CommandSpec:
        return CommandSpec(
            argv=(str(self.executable), "exec", task.prompt, "--json"),
            timeout_seconds=task.timeouts.agent,
        )

    def decode(self, line: str) -> dict[str, JsonValue] | None:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
            return None
        return cast(dict[str, JsonValue], value)

    def result(self, process: ProcessResult, events: list[dict[str, JsonValue]]) -> AgentResult:
        final = next((e for e in reversed(events) if e.get("kind") == "run_finished"), None)
        if final is None:
            return AgentResult(returncode=process.returncode)
        data = final.get("data")
        if not isinstance(data, dict):
            return AgentResult(returncode=process.returncode)
        mapping = {
            "completed": AgentOutcome.COMPLETED,
            "failed": AgentOutcome.FAILED,
            "limited": AgentOutcome.LIMITED,
            "aborted": AgentOutcome.ABORTED,
        }
        outcome = mapping.get(str(data.get("outcome")), AgentOutcome.UNKNOWN)
        expected_exit = {
            AgentOutcome.COMPLETED: 0,
            AgentOutcome.FAILED: 1,
            AgentOutcome.LIMITED: 3,
            AgentOutcome.ABORTED: 130,
        }
        if not process.timed_out and not process.cancelled:
            if process.returncode != expected_exit.get(outcome):
                outcome = AgentOutcome.UNKNOWN
        final_text = data.get("final_text")
        return AgentResult(
            outcome=outcome,
            returncode=process.returncode,
            final_answer=final_text if isinstance(final_text, str) else None,
        )
