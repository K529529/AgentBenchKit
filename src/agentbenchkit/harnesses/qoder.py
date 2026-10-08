"""Qoder CN via its public SDK; the evaluated CLI remains unchanged."""

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


class QoderHarness:
    name = "qoder"
    capabilities = Capabilities(
        final_answer=True,
        tool_calls=True,
        tool_results=True,
        model_usage=True,
        model_output="partial",
        native_call_ids=True,
    )

    def __init__(
        self, python: str = "/opt/abk/bin/python", cli: str = "qoderclicn", docker: bool = True
    ) -> None:
        self.python, self.cli, self.docker = python, cli, docker

    def native_config(self, model: ModelSpec, options: HarnessOptions) -> NativeAgentConfig:
        if not self.docker:
            raise ValueError("Qoder account credentials require Docker tmpfs")
        if model.credential.kind != "qoder_login" or model.provider_id != "qoder_cn":
            raise ValueError("Qoder CN requires qoder_login and provider_id=qoder_cn")
        unsupported = [
            name
            for name in ("temperature", "top_p", "seed", "request_timeout_seconds")
            if getattr(model, name) is not None
        ]
        if unsupported:
            raise ValueError(
                "Qoder SDK cannot enforce these model controls: " + ", ".join(unsupported)
            )
        if not options.include_usage or options.output_token_parameter != "max_tokens":
            raise ValueError(
                "Qoder requires observable usage; API token parameter is not configurable"
            )
        controls: dict[str, JsonValue] = {
            "max_turns": options.max_steps or 20,
            "max_credits": options.max_credits or 5.0,
            "max_request_credits": 2.0,
            "mcp_servers": [],
            "skills": [],
            "setting_sources": [],
            "config_format": "ABK public SDK launch TOML",
            "credit_limit_semantics": "interrupt on observed usage; in-flight overshoot possible",
        }
        return NativeAgentConfig(
            config_directory=".qoder-cn",
            config_home_env="QODERCN_CONFIG_DIR",
            credential_files=(".auth/user", ".auth/machine_id"),
            effective_model=model,
            wire_api="qoder_managed",
            controls=controls,
            config_toml=toml_config(
                {
                    "cli": {"path": self.cli},
                    "runtime": controls,
                    "model": {
                        "id": model.model_id,
                        "reasoning_effort": model.reasoning_effort,
                        "max_output_tokens": model.max_output_tokens,
                        "context_window": model.context_window,
                    },
                }
            ),
        )

    def version_command(self) -> CommandSpec:
        return CommandSpec(
            argv=(
                self.python,
                "-m",
                "agentbenchkit.harnesses.qoder_worker",
                "--version",
                "--cli",
                self.cli,
            ),
            timeout_seconds=20,
        )

    def command(self, task: TaskSpec) -> CommandSpec:
        return CommandSpec(
            argv=(
                self.python,
                "-m",
                "agentbenchkit.harnesses.qoder_worker",
                "--prompt",
                task.prompt,
            ),
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
        final = next((e for e in reversed(events) if e.get("kind") == "run_finished"), {})
        data = final.get("data")
        data = data if isinstance(data, dict) else {}
        outcome = {
            "completed": AgentOutcome.COMPLETED,
            "failed": AgentOutcome.FAILED,
            "limited": AgentOutcome.LIMITED,
            "aborted": AgentOutcome.ABORTED,
        }.get(str(data.get("outcome")), AgentOutcome.UNKNOWN)
        if outcome == AgentOutcome.COMPLETED and process.returncode != 0:
            outcome = AgentOutcome.FAILED
        answer = data.get("final_text")
        return AgentResult(
            outcome=outcome,
            returncode=process.returncode,
            final_answer=answer if isinstance(answer, str) else None,
        )
