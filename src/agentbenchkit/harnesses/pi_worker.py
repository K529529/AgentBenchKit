"""Translate isolated ABK settings to public Pi files, then replace this process."""

import argparse
import base64
import gzip
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

from agentbenchkit.core.protocols import ProcessResult
from agentbenchkit.harnesses.pi import PI_VERSION, PiHarness
from agentbenchkit.storage.artifacts import Redactor


def launch(prompt: str) -> None:
    home = Path(os.environ["PI_CODING_AGENT_DIR"])
    config = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
    cli, model = config["cli"]["path"], config["model"]
    version = subprocess.check_output([cli, "--version"], text=True, timeout=20).strip()
    if version != PI_VERSION:
        raise ValueError(f"Pi version mismatch: expected {PI_VERSION}, observed {version}")
    # Fail closed on project configuration: it can override isolated user settings.
    if (Path.cwd() / ".pi").exists():
        raise ValueError("project .pi configuration requires explicit isolation review")
    definition: dict[str, Any] = {
        "id": model["model_id"],
        "name": model["model_id"],
        "input": ["text"],
        "reasoning": model.get("reasoning_effort", "off") != "off",
        "contextWindow": model["context_window"],
        "maxTokens": model["max_output_tokens"],
        "compat": {
            "supportsStore": False,
            "supportsDeveloperRole": False,
            "maxTokensField": config["runtime"]["output_token_parameter"],
        },
    }
    sampling = {key: model[key] for key in ("temperature", "top_p") if key in model}
    if sampling:
        definition["samplingParams"] = sampling
    if model["provider_id"] == "deepseek":
        if model.get("reasoning_effort", "off") == "off":
            definition.setdefault("samplingParams", {})["thinking"] = {"type": "disabled"}
        definition["compat"].update(
            thinkingFormat="deepseek", requiresReasoningContentOnAssistantMessages=True
        )
    provider = {
        "baseUrl": model["base_url"],
        "api": "openai-completions",
        "apiKey": "$" + model["credential"]["env_var"],
        "models": [definition],
    }
    (home / "models.json").write_text(json.dumps({"providers": {model["provider_id"]: provider}}))
    (home / "settings.json").write_text(
        json.dumps(
            {
                "retry": {"enabled": False},
                "compaction": {"enabled": False},
                "cacheWarming": "off",
            }
        )
    )
    argv = [
        cli,
        "--mode",
        "json",
        "--print",
        "--no-session",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--provider",
        model["provider_id"],
        "--model",
        model["model_id"],
        "--thinking",
        model.get("reasoning_effort", "off"),
        "--",
        prompt,
    ]
    # Preserve redacted native JSONL, but avoid flooding the bounded transport with
    # streaming deltas and duplicate agent_end message arrays. Final messages carry usage.
    key = os.environ.get(model["credential"]["env_var"], "")
    redactor = Redactor((key,) if key else ())
    archive: list[str] = []
    archive_size = 0
    messages: list[dict[str, Any]] = []
    turns = 0

    def flush_archive() -> None:
        if archive:
            payload = gzip.compress("".join(archive).encode("utf-8"), mtime=0)
            print(
                json.dumps(
                    {
                        "type": "abk_native_archive",
                        "encoding": "gzip+base64",
                        "data": base64.b64encode(payload).decode("ascii"),
                    }
                ),
                flush=True,
            )
            archive.clear()

    with (home / "native-events.jsonl").open("w", encoding="utf-8") as evidence:
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, text=True, encoding="utf-8")
        assert process.stdout is not None
        try:
            for line in process.stdout:
                clean = redactor.text(line)
                archive.append(clean)
                archive_size += len(clean)
                if archive_size >= 32768:
                    flush_archive()
                    archive_size = 0
                evidence.write(clean)
                evidence.flush()
                try:
                    event = json.loads(clean)
                except json.JSONDecodeError:
                    print(clean, end="", flush=True)
                    continue
                if isinstance(event, dict):
                    message = event.get("message")
                    if event.get("type") == "turn_start":
                        turns += 1
                    if (
                        event.get("type") == "message_end"
                        and isinstance(message, dict)
                        and message.get("role") == "assistant"
                    ):
                        messages.append({"pi": event})
                    if event.get("type") == "agent_settled":
                        usage = (
                            PiHarness()
                            .result(ProcessResult(returncode=0, duration_ms=0), messages)
                            .reported_usage
                        )
                        event["abk_summary"] = {
                            "usage": usage,
                            "steps": turns,
                            "model_calls": len(messages),
                        }
                        clean = json.dumps(event, ensure_ascii=False) + "\n"
                if not isinstance(event, dict) or event.get("type") not in {
                    "message_update",
                    "tool_execution_update",
                    "agent_end",
                }:
                    print(clean, end="", flush=True)
            code = process.wait()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            flush_archive()
            evidence.flush()
            os.fsync(evidence.fileno())
    sys.exit(code)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True)
    launch(parser.parse_args().prompt)
