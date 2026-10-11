"""Run the public graph callable used by sh-agent CLI; no agent monkey-patching.

Copied as a standalone driver into the separate sh-agent environment. Optional
imports are dynamic so ABK does not depend on the evaluated agent's dependencies.
"""
import argparse
import contextlib
import importlib
import importlib.metadata
import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

OUTPUT = sys.stdout


def emit(kind: str, data: dict[str, Any], **native: Any) -> None:
    print(json.dumps({"kind": kind, "data": {**data, **native}}, ensure_ascii=False,
                     default=str), file=OUTPUT, flush=True)


def run(prompt: str) -> int:
    config = tomllib.loads(
        (Path(os.environ["ABK_SH_AGENT_CONFIG"]) / "config.toml").read_text(encoding="utf-8")
    )["model"]
    os.environ["OPENAI_API_KEY"] = os.environ[config["credential_env"]]
    os.environ["OPENAI_BASE_URL"] = config["base_url"]
    settings = importlib.import_module("code_agent.config")
    # Configuration belongs in the image, using the upstream documented YAML file.
    # Reject a mismatch instead of silently changing the evaluated model at runtime.
    if settings.get_setting("model", "chat_model") != config["id"]:
        raise ValueError("installed sh-agent model differs from manifest")
    if settings.get_setting("agent", "model_temperature") != config["temperature"]:
        raise ValueError("installed sh-agent temperature differs from manifest")
    callbacks = importlib.import_module("langchain_core.callbacks")
    messages = importlib.import_module("langchain_core.messages")

    class Observe(callbacks.BaseCallbackHandler):  # type: ignore[misc, name-defined]
        def on_chat_model_start(self, serialized: Any, messages: Any, **kw: Any) -> None:
            emit("model_started", {"model": config["id"]}, call_id=str(kw["run_id"]))

        def on_llm_end(self, response: Any, **kw: Any) -> None:
            generations = response.generations
            message = generations[0][0].message if generations and generations[0] else None
            usage = getattr(message, "usage_metadata", None) or {}
            emit("model_finished", {
                "usage": {"input_tokens": usage.get("input_tokens"),
                          "output_tokens": usage.get("output_tokens")},
                "response_metadata": getattr(message, "response_metadata", {}),
                "text": getattr(message, "content", None),
            }, call_id=str(kw["run_id"]))

        def on_llm_error(self, error: BaseException, **kw: Any) -> None:
            emit("model_finished", {"error": str(error)}, call_id=str(kw["run_id"]))

        def on_tool_start(self, serialized: Any, input_str: str, **kw: Any) -> None:
            emit("tool_started", {"name": serialized.get("name"), "arguments": input_str},
                 call_id=str(kw["run_id"]))

        def on_tool_end(self, output: Any, **kw: Any) -> None:
            emit("tool_finished", {"output": str(output)}, call_id=str(kw["run_id"]))

        def on_tool_error(self, error: BaseException, **kw: Any) -> None:
            emit("tool_finished", {"error": str(error)}, call_id=str(kw["run_id"]))

    graph = importlib.import_module("code_agent.graph").compile_graph(with_checkpoint=False)
    # Same single-turn state as code_agent.cli.main, with a fresh session per task.
    state = {
        "messages": [messages.HumanMessage(content=prompt)], "user_request": prompt,
        "workspace_dir": str(Path.cwd()), "task_plan": "", "current_agent": "supervisor",
        "exploration_result": None, "relevant_files": None, "code_changes": None,
        "review_feedback": None, "review_approved": False, "test_result": None,
        "test_passed": False, "retry_count": 0,
        "max_retries": settings.get_setting("agent", "max_review_retries"),
        "final_response": None, "task_complete": False,
    }
    emit("run_started", {"model": config["id"], "checkpoint": False})
    final: dict[str, Any] = {}
    for chunk in graph.stream(state, {"callbacks": [Observe()]}, stream_mode="values"):
        final = chunk
    complete = final.get("task_complete") is True
    emit("run_finished", {"outcome": "completed" if complete else "failed",
                          "final_text": final.get("final_response")})
    return 0 if complete else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--prompt")
    args = parser.parse_args()
    if args.version:
        dependencies = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
        model_class = importlib.import_module("langchain_openai").ChatOpenAI
        print(json.dumps({"sh_agent_commit": os.environ.get("ABK_SH_AGENT_COMMIT"),
                          "dependencies": dependencies,
                          "native_max_retries": model_class.model_fields["max_retries"].default},
                         default=str))
        return 0
    if args.prompt is None:
        parser.error("--prompt is required")
    try:
        with contextlib.redirect_stdout(sys.stderr):
            return run(args.prompt)
    except Exception as exc:
        emit("run_finished", {"outcome": "failed", "error_type": type(exc).__name__,
                              "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


