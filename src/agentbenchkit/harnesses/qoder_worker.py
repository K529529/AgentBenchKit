"""Thin public Qoder SDK driver with observable account Credits and bounded execution."""

import argparse
import asyncio
import contextlib
import dataclasses
import importlib
import importlib.metadata
import json
import os
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Any


def emit(kind: str, data: dict[str, Any] | None = None, **native: Any) -> None:
    print(json.dumps({"kind": kind, "data": data or {}, **native}, ensure_ascii=False), flush=True)


def safe_usage(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result = {
        k: value[k] for k in ("userType", "totalUsagePercentage", "isQuotaExceeded") if k in value
    }
    for name in ("userQuota", "addOnQuota", "orgResourcePackage"):
        bucket = value.get(name)
        if isinstance(bucket, dict):
            result[name] = {
                k: bucket[k] for k in ("total", "used", "remaining", "cap", "unit") if k in bucket
            }
    if isinstance(value.get("session"), dict):
        result["session"] = value["session"]
    return result


def remaining(value: dict[str, Any]) -> float | None:
    buckets = [
        value[name]
        for name in ("userQuota", "addOnQuota", "orgResourcePackage")
        if isinstance(value.get(name), dict) and "remaining" in value[name]
    ]
    return sum(float(b["remaining"]) for b in buckets) if buckets else None


def limit_reason(before: dict[str, Any], now: dict[str, Any], limit: float) -> str | None:
    session = now.get("session", {})
    credits = session.get("total_credits") if isinstance(session, dict) else None
    if isinstance(credits, (int, float)) and credits >= limit:
        return "session_credits_limit"
    initial, current = remaining(before), remaining(now)
    if initial is not None and current is not None and initial - current >= limit:
        return "account_credits_drop_limit"
    if now.get("isQuotaExceeded"):
        return "account_quota_exceeded"
    return None


def token_usage(usage: dict[str, Any]) -> dict[str, Any]:
    keys = ("input_tokens", "output_tokens", "cache_read_input_tokens")
    # The managed CLI has returned all-zero placeholders for real inference.
    known = any(usage.get(key, 0) for key in keys)
    return {
        "input_tokens": usage.get("input_tokens") if known else None,
        "output_tokens": usage.get("output_tokens") if known else None,
        "cached_input_tokens": usage.get("cache_read_input_tokens") if known else None,
    }


async def run(prompt: str | None) -> None:
    sdk = importlib.import_module("qodercn_agent_sdk")
    home = Path(os.environ["QODERCN_CONFIG_DIR"])
    config = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
    model, runtime = config["model"], config["runtime"]
    extras = {"no-session-persistence": None, "max-model-request-retries": "0"}
    for key, flag in (
        ("max_output_tokens", "max-output-tokens"),
        ("reasoning_effort", "reasoning-effort"),
        ("context_window", "context-window"),
    ):
        if key in model:
            extras[flag] = str(model[key])
    options = sdk.QoderAgentOptions(
        cli_path=config["cli"]["path"],
        auth=sdk.qodercli_auth(),
        cwd=str(Path.cwd()),
        model=model["id"],
        max_turns=runtime["max_turns"],
        permission_mode="bypass_permissions",
        strict_mcp_config=True,
        setting_sources=[],
        skills=[],
        extra_args=extras,
    )
    # A separate no-query SDK connection keeps account polling independent of
    # the inference stream: this CLI can return None for in-session queries.
    async with sdk.QoderSDKClient(options) as client, sdk.QoderSDKClient(options) as observer:
        before = safe_usage(await observer.get_usage_info())
        emit("usage_snapshot", {"phase": "before", "usage": before})
        if remaining(before) is None:
            raise RuntimeError("account Credits unavailable before inference")
        if not prompt:
            return
        reason: str | None = limit_reason(before, before, runtime["max_credits"])
        if reason:
            emit("run_finished", {"outcome": "limited", "reason": reason})
            return
        emit(
            "run_started",
            {
                "requested_model": model["id"],
                "sdk_version": importlib.metadata.version("qodercn-agent-sdk"),
            },
        )

        async def monitor() -> None:
            nonlocal reason
            while True:
                await asyncio.sleep(10)
                try:
                    now = safe_usage(await asyncio.wait_for(observer.get_usage_info(), 15))
                    if remaining(now) is None:
                        raise RuntimeError("account Credits unavailable during inference")
                    emit("usage_snapshot", {"phase": "during", "usage": now})
                    observed = limit_reason(before, now, runtime["max_credits"])
                    if observed and not reason:
                        reason = observed
                        emit("budget_limit", {"reason": reason})
                        await client.interrupt()
                except Exception as exc:
                    emit("usage_unavailable", {"error_type": type(exc).__name__})
                    if not reason:
                        reason = "usage_monitor_unavailable"
                        await client.interrupt()

        await client.query(prompt)
        monitoring = asyncio.create_task(monitor())
        requests: dict[str, float] = {}
        final: dict[str, Any] | None = None
        try:
            async for message in client.receive_response():
                name = type(message).__name__
                raw = dataclasses.asdict(message)
                emit("sdk_message", {"message_type": name}, qoder=raw)
                if isinstance(message, sdk.AssistantMessage):
                    usage = message.usage or {}
                    # Streaming message IDs and billing request IDs differ. Only
                    # explicit request IDs identify charge observations.
                    request_id = usage.get("request_id")
                    if isinstance(request_id, str) and request_id:
                        emit(
                            "model_finished",
                            {"model": message.model, "usage": usage, "request_id": request_id},
                        )
                    for block in message.content:
                        if isinstance(block, sdk.ToolUseBlock):
                            emit(
                                "tool_started",
                                {"call_id": block.id, "name": block.name, "arguments": block.input},
                            )
                    credit = usage.get("credits")
                    if isinstance(credit, (int, float)) and not reason:
                        if isinstance(request_id, str) and request_id:
                            requests[request_id] = credit
                        if not reason and credit >= runtime["max_request_credits"]:
                            reason = "single_request_credits_limit"
                        elif not reason and sum(requests.values()) >= runtime["max_credits"]:
                            reason = "reported_request_credits_limit"
                        if reason:
                            emit(
                                "budget_limit",
                                {
                                    "reason": reason,
                                    "request_credits": credit,
                                    "reported_credits": sum(requests.values()),
                                },
                            )
                            await client.interrupt()
                elif isinstance(message, sdk.UserMessage) and isinstance(message.content, list):
                    for block in message.content:
                        if isinstance(block, sdk.ToolResultBlock):
                            emit(
                                "tool_finished",
                                {
                                    "call_id": block.tool_use_id,
                                    "is_error": block.is_error,
                                    "content": block.content,
                                },
                            )
                elif isinstance(message, sdk.ResultMessage):
                    final = raw
        finally:
            monitoring.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await monitoring
        after = safe_usage(await observer.get_usage_info())
        emit("usage_snapshot", {"phase": "after", "usage": after})
        reason = reason or limit_reason(before, after, runtime["max_credits"])
        if final is None:
            emit(
                "run_finished",
                {
                    "outcome": "limited" if reason else "failed",
                    "reason": reason or "missing_sdk_result",
                },
            )
            return
        turn_limited = final.get("subtype") == "error_max_turns"
        outcome = (
            "limited"
            if reason or turn_limited
            else ("failed" if final["is_error"] else "completed")
        )
        usage = final.get("usage") or {}
        emit(
            "run_finished",
            {
                "outcome": outcome,
                "reason": reason,
                "final_text": final.get("result"),
                "steps": final["num_turns"],
                "model_calls": None,
                "observed_request_count": len(requests),
                "reported_request_credits": sum(requests.values()),
                "total_credits": final.get("total_credits"),
                "usage": token_usage(usage),
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--cli", default="qoderclicn")
    parser.add_argument("--prompt")
    args = parser.parse_args()
    if args.version:
        # The public CLI writes its config directory even for --version.
        with tempfile.TemporaryDirectory(prefix="abk-qoder-version-") as folder:
            version = subprocess.check_output(
                [args.cli, "--version"],
                text=True,
                timeout=15,
                env={**os.environ, "QODERCN_CONFIG_DIR": folder},
            ).strip()
        print(f"QoderCN {version}; SDK {importlib.metadata.version('qodercn-agent-sdk')}")
        return
    try:
        asyncio.run(run(args.prompt))
    except Exception as exc:
        emit(
            "run_finished",
            {"outcome": "failed", "reason": "SDK driver error", "error_type": type(exc).__name__},
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
