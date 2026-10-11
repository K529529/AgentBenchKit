"""Experimental external adapter for sh-agent's unchanged Python graph entry point."""
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

SH_AGENT_COMMIT = "26130e96732c51d83a7ece1d06325216831ee028"


class ShAgentHarness:
    name = "sh-agent"
    capabilities = Capabilities(
        final_answer=True, tool_calls=True, tool_results=True,
        model_output="partial", native_call_ids=True,
    )

    def __init__(
        self, python: str = "/opt/sh-agent-venv/bin/python",
        worker: str = "/opt/abk-sh-agent-worker.py",
    ) -> None:
        self.python, self.worker = python, worker

    def native_config(self, model: ModelSpec, options: HarnessOptions) -> NativeAgentConfig:
        if model.credential.kind != "api_key":
            raise ValueError("sh-agent requires an API key")
        unsupported = [key for key in (
            "context_window", "max_output_tokens", "reasoning_effort", "top_p",
            "seed", "request_timeout_seconds",
        ) if getattr(model, key) is not None]
        if unsupported:
            raise ValueError("sh-agent cannot enforce: " + ", ".join(unsupported))
        if options.max_steps is not None or options.max_credits is not None:
            raise ValueError("sh-agent has no public model-call or Credits budget setting")
        if options.output_token_parameter != "max_tokens" or not options.include_usage:
            raise ValueError("sh-agent does not expose these transport controls")
        effective = model.model_copy(update={
            "temperature": 0.1 if model.temperature is None else model.temperature,
        })
        return NativeAgentConfig(
            config_directory=".sh-agent", config_home_env="ABK_SH_AGENT_CONFIG",
            credential_env=model.credential.env_var, effective_model=effective,
            wire_api="chat_completions",
            config_toml=toml_config({"model": {
                "id": effective.model_id, "base_url": effective.base_url,
                "credential_env": effective.credential.env_var,
                "temperature": effective.temperature,
            }}),
            controls={
                "source_commit": SH_AGENT_COMMIT,
                "entry_point": "code_agent.graph.compile_graph (upstream CLI entry point)",
                "checkpoint": False,
                "model_usage": "unavailable unless upstream emits usage",
                "model_retries": "unchanged dependency default; recorded by version probe",
                "model_call_limit": None, "output_token_limit": None,
                "termination_budget": "ABK agent wall-clock timeout",
            },
        )

    def version_command(self) -> CommandSpec:
        return CommandSpec(argv=(self.python, self.worker, "--version"), timeout_seconds=30)

    def command(self, task: TaskSpec) -> CommandSpec:
        return CommandSpec(
            argv=(self.python, self.worker, "--prompt", task.prompt),
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
        outcome = {"completed": AgentOutcome.COMPLETED, "failed": AgentOutcome.FAILED}.get(
            str(data.get("outcome")), AgentOutcome.UNKNOWN,
        )
        expected = {AgentOutcome.COMPLETED: 0, AgentOutcome.FAILED: 1}.get(outcome)
        if process.timed_out or process.cancelled or process.returncode != expected:
            outcome = AgentOutcome.UNKNOWN
        answer = data.get("final_text")
        return AgentResult(
            outcome=outcome, returncode=process.returncode,
            final_answer=answer if isinstance(answer, str) else None,
        )
