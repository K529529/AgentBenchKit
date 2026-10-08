"""Codex public non-interactive JSONL adapter, without source instrumentation."""

import json
from pathlib import Path
from typing import Any, cast

from pydantic import JsonValue

from agentbenchkit.core.models import (
    AgentResult,
    Capabilities,
    CommandSpec,
    HarnessOptions,
    ModelSpec,
    NativeAgentConfig,
    TaskSpec,
)
from agentbenchkit.core.protocols import ProcessResult
from agentbenchkit.core.status import AgentOutcome
from agentbenchkit.harnesses.config import toml_config


class CodexHarness:
    name = "codex"
    capabilities = Capabilities(
        final_answer=True,
        tool_calls=True,
        tool_results=True,
        model_usage=True,
        model_output="partial",
        native_call_ids=True,
    )

    def __init__(self, executable: Path | str, docker: bool = False) -> None:
        self.executable = str(executable.resolve()) if isinstance(executable, Path) else executable
        self.docker = docker

    def native_config(self, model: ModelSpec, options: HarnessOptions) -> NativeAgentConfig:
        if model.credential.kind not in {"api_key", "chatgpt_login"}:
            raise ValueError("Codex requires API-key or ChatGPT authentication")
        unsupported = [
            name
            for name in (
                "temperature",
                "top_p",
                "seed",
                "max_output_tokens",
                "request_timeout_seconds",
            )
            if getattr(model, name) is not None
        ]
        if unsupported:
            raise ValueError(
                f"Codex CLI cannot configure these equivalent controls: {', '.join(unsupported)}"
            )
        if options != HarnessOptions():
            raise ValueError("Codex does not support Nexus-specific loop/transport options")
        if model.credential.kind == "chatgpt_login" and not self.docker:
            raise ValueError("ChatGPT smoke authentication requires Docker tmpfs")
        if model.credential.kind == "chatgpt_login" and model.provider_id != "openai_chatgpt":
            raise ValueError("ChatGPT login requires provider_id=openai_chatgpt")
        native: dict[str, Any] = {
            "model": model.model_id,
            "model_context_window": model.context_window,
            "model_reasoning_effort": model.reasoning_effort,
            "approval_policy": "never",
            "web_search": "disabled",
            "cli_auth_credentials_store": "file",
        }
        api = model.credential.kind == "api_key"
        if api:
            native.update(
                model_provider="abk_provider",
                model_providers={
                    "abk_provider": {
                        "name": model.provider_id,
                        "base_url": model.base_url,
                        "env_key": model.credential.env_var,
                        "wire_api": "responses",
                        "requires_openai_auth": False,
                    }
                },
            )
        return NativeAgentConfig(
            config_directory=".codex",
            effective_model=model,
            credential_env=model.credential.env_var if api else None,
            config_home_env="CODEX_HOME",
            credential_file=None if api else "auth.json",
            wire_api="responses" if api else "chatgpt",
            config_toml=toml_config(native),
            controls={
                "mcp_servers": [],
                "skills": [],
                "tools": None,
                "config_home": "isolated",
                "evaluation_class": "explicit_api" if api else "subscription_smoke",
                "sandbox": "external_docker" if self.docker else "workspace-write",
            },
        )

    def version_command(self) -> CommandSpec:
        return CommandSpec(argv=(self.executable, "--version"), timeout_seconds=15)

    def command(self, task: TaskSpec) -> CommandSpec:
        argv = (
            self.executable,
            "exec",
            "--json",
            "--ephemeral",
            "--skip-git-repo-check",
            "--ignore-rules",
            "--color",
            "never",
            "-c",
            'approval_policy="never"',
            "-c",
            'web_search="disabled"',
            "--sandbox",
            "danger-full-access" if self.docker else "workspace-write",
            task.prompt,
        )
        return CommandSpec(argv=argv, timeout_seconds=task.timeouts.agent)

    def decode(self, line: str) -> dict[str, JsonValue] | None:
        try:
            native = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(native, dict) or not isinstance(native.get("type"), str):
            return None
        event_type = native["type"]
        kind = {
            "turn.started": "run_started",
            "turn.completed": "run_finished",
            "turn.failed": "run_finished",
        }.get(event_type, event_type)
        data: dict[str, JsonValue] = {}
        if event_type in {"turn.completed", "turn.failed"}:
            data = {
                "outcome": "completed" if event_type == "turn.completed" else "failed",
                "usage": native.get("usage"),
            }
        item = native.get("item")
        if isinstance(item, dict) and item.get("type") in {
            "command_execution",
            "file_change",
            "mcp_tool_call",
            "web_search",
        }:
            if event_type in {"item.started", "item.completed"}:
                kind = "tool_started" if event_type == "item.started" else "tool_finished"
                data = {
                    "call_id": item.get("id"),
                    "tool": item.get("type"),
                    "status": item.get("status"),
                    "exit_code": item.get("exit_code"),
                }
        return {"kind": kind, "data": data, "codex": cast(dict[str, JsonValue], native)}

    def result(self, process: ProcessResult, events: list[dict[str, JsonValue]]) -> AgentResult:
        final = next((e for e in reversed(events) if e.get("kind") == "run_finished"), None)
        data = final.get("data") if final else None
        outcome = AgentOutcome.UNKNOWN
        if isinstance(data, dict):
            if data.get("outcome") == "completed" and process.returncode == 0:
                outcome = AgentOutcome.COMPLETED
            elif data.get("outcome") == "failed":
                outcome = AgentOutcome.FAILED
        answers = []
        for event in events:
            native = event.get("codex")
            if isinstance(native, dict) and native.get("type") == "item.completed":
                item = native.get("item")
                if isinstance(item, dict) and item.get("type") == "agent_message":
                    answers.append(str(item.get("text", "")))
        return AgentResult(
            outcome=outcome,
            returncode=process.returncode,
            final_answer=answers[-1] if answers else None,
        )
