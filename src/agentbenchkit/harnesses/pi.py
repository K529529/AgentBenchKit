"""Pinned Pi public JSON CLI adapter; process ownership remains with the environment."""

import json
from typing import cast

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

PI_VERSION = "1.4.0"


class PiHarness:
    name = "pi"
    capabilities = Capabilities(
        final_answer=True,
        tool_calls=True,
        tool_results=True,
        model_usage=True,
        model_output="partial",
        native_call_ids=True,
    )

    def __init__(self, python: str = "/opt/abk/bin/python", executable: str = "pi") -> None:
        self.python, self.executable = python, executable

    def native_config(self, model: ModelSpec, options: HarnessOptions) -> NativeAgentConfig:
        if model.credential.kind != "api_key":
            raise ValueError("PiHarness requires explicit API credentials")
        if not model.context_window or not model.max_output_tokens:
            raise ValueError("Pi requires explicit context_window and max_output_tokens")
        if model.seed is not None or model.request_timeout_seconds is not None:
            raise ValueError("Pi CLI cannot enforce seed or per-request timeout; use phase budgets")
        if options.max_steps is not None or options.max_credits is not None:
            raise ValueError("Pi CLI has no public step/credit limit; use --agent-timeout")
        if not options.include_usage:
            raise ValueError("Pi usage observation cannot be disabled")
        if model.reasoning_effort not in {
            None,
            "off",
            "minimal",
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        }:
            raise ValueError("unsupported Pi thinking level")
        controls: dict[str, JsonValue] = {
            "pi_version": PI_VERSION,
            "retry": False,
            "compaction": False,
            "extensions": False,
            "skills": False,
            "context_files": False,
            "session_persistence": False,
            "budget": "environment wall-clock timeout",
            "output_token_parameter": options.output_token_parameter,
        }
        return NativeAgentConfig(
            config_directory=".pi",
            config_home_env="PI_CODING_AGENT_DIR",
            credential_env=model.credential.env_var,
            effective_model=model,
            wire_api="chat_completions",
            controls=controls,
            config_toml=toml_config(
                {
                    "cli": {"path": self.executable, "version": PI_VERSION},
                    "model": model.model_dump(mode="json", exclude_none=True),
                    "runtime": controls,
                }
            ),
        )

    def version_command(self) -> CommandSpec:
        return CommandSpec(argv=(self.executable, "--version"), timeout_seconds=20)

    def command(self, task: TaskSpec) -> CommandSpec:
        return CommandSpec(
            argv=(self.python, "-m", "agentbenchkit.harnesses.pi_worker", "--prompt", task.prompt),
            timeout_seconds=task.timeouts.agent,
        )

    def decode(self, line: str) -> dict[str, JsonValue] | None:
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(raw, dict) or not isinstance(raw.get("type"), str):
            return None
        kind = {
            "agent_start": "run_started",
            "agent_settled": "run_finished",
            "message_update": "assistant_delta",
            "tool_execution_update": "tool_output_delta",
            "tool_execution_start": "tool_started",
            "tool_execution_end": "tool_finished",
        }.get(raw["type"], raw["type"])
        data: dict[str, JsonValue] = {}
        if raw["type"].startswith("tool_execution_"):
            data = {
                "call_id": raw.get("toolCallId"),
                "name": raw.get("toolName"),
                "arguments": raw.get("args"),
                "is_error": raw.get("isError"),
            }
        if raw["type"] == "agent_settled" and isinstance(raw.get("abk_summary"), dict):
            data = cast(dict[str, JsonValue], raw["abk_summary"])
        message = raw.get("message")
        if isinstance(message, dict) and message.get("role") == "assistant":
            if raw["type"] == "message_start":
                kind = "model_started"
            elif raw["type"] == "message_end":
                kind = "model_finished"
                data = {
                    "model": message.get("model"),
                    "provider": message.get("provider"),
                    "usage": message.get("usage"),
                    "stop_reason": message.get("stopReason"),
                }
        return {"kind": kind, "data": data, "pi": cast(dict[str, JsonValue], raw)}

    def result(self, process: ProcessResult, events: list[dict[str, JsonValue]]) -> AgentResult:
        native = [e["pi"] for e in events if isinstance(e.get("pi"), dict)]
        messages = [
            e["message"]
            for e in native
            if isinstance(e, dict)
            and e.get("type") == "message_end"
            and isinstance(e.get("message"), dict)
        ]
        assistants = [m for m in messages if isinstance(m, dict) and m.get("role") == "assistant"]
        last = assistants[-1] if assistants else {}
        settled = next(
            (
                e
                for e in reversed(native)
                if isinstance(e, dict) and e.get("type") == "agent_settled"
            ),
            {},
        )
        outcome = AgentOutcome.UNKNOWN
        if process.cancelled or (isinstance(settled, dict) and settled.get("aborted") is True):
            outcome = AgentOutcome.ABORTED
        elif process.timed_out:
            outcome = AgentOutcome.LIMITED
        elif settled and process.returncode == 0 and not process.output_truncated:
            # Provider/API errors are protocol/infrastructure errors, not solving failures.
            if last.get("stopReason") == "stop":
                outcome = AgentOutcome.COMPLETED
            elif last.get("stopReason") == "length":
                outcome = AgentOutcome.LIMITED
        usage: dict[str, int | None] = {}
        for target, source in (
            ("input_tokens", "input"),
            ("output_tokens", "output"),
            ("cached_input_tokens", "cacheRead"),
            ("cache_write_tokens", "cacheWrite"),
            ("total_tokens", "totalTokens"),
        ):
            values = [
                cast(dict[str, JsonValue], m["usage"]).get(source)
                for m in assistants
                if isinstance(m.get("usage"), dict)
            ]
            usage[target] = (
                sum(cast(list[int], values))
                if values
                and len(values) == len(assistants)
                and all(isinstance(v, int) and not isinstance(v, bool) for v in values)
                else None
            )
        content = last.get("content", [])
        answer = (
            "\n".join(
                str(b["text"]) for b in content if isinstance(b, dict) and b.get("type") == "text"
            )
            if isinstance(content, list)
            else ""
        )
        return AgentResult(
            outcome=outcome,
            returncode=process.returncode,
            final_answer=answer or None,
            reported_usage=usage,
        )
