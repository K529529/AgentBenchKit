"""Separate observed credit quantities; none is a monetary cost estimate."""

import math
from typing import Any

from agentbenchkit.core.events import Event


def number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


def account(usage: Any) -> dict[str, float] | None:
    if not isinstance(usage, dict):
        return None
    result = {}
    for key in ("userQuota", "addOnQuota", "orgResourcePackage"):
        bucket = usage.get(key)
        if bucket is None:
            continue
        if not isinstance(bucket, dict) or bucket.get("unit", "credits") != "credits":
            return None
        value = number(bucket.get("remaining"))
        if value is None:
            return None
        result[key] = value
    return result or None


def credit_metrics(events: list[Event], terminal: dict[str, Any]) -> dict[str, Any]:
    requests: dict[str, dict[str, Any]] = {}
    snapshots: dict[str, dict[str, float] | None] = {}
    for event in events:
        native = event.attributes.get("native")
        if not isinstance(native, dict):
            continue
        data = native.get("data")
        if not isinstance(data, dict):
            continue
        if native.get("kind") == "model_finished":
            usage = data.get("usage")
            request = data.get("request_id")
            if isinstance(request, str) and request and isinstance(usage, dict):
                requests[request] = dict(usage)
        elif native.get("kind") == "usage_snapshot" and data.get("phase") in ("before", "after"):
            snapshots[str(data["phase"])] = account(data.get("usage"))
    values = [number(usage.get("credits")) for usage in requests.values()]
    reported = None
    if values and all(v is not None for v in values):
        reported = sum(v for v in values if v is not None)
    elif not requests and terminal.get("observed_request_count", 0):
        reported = number(terminal.get("reported_request_credits"))
    before, after = snapshots.get("before"), snapshots.get("after")
    delta = (
        sum(before.values()) - sum(after.values())
        if before and after and before.keys() == after.keys()
        else None
    )
    flags = [u.get("billable") for u in requests.values()]
    return {
        "reported_request_credits": reported,
        "sdk_session_credits": number(terminal.get("total_credits")),
        "observed_account_delta": delta,
        "request_billable_flags": {
            "true": sum(f is True for f in flags),
            "false": sum(f is False for f in flags),
            "unavailable": sum(not isinstance(f, bool) for f in flags),
        }
        if requests
        else None,
        "credit_request_count": len(requests) if requests else None,
        "credits_note": (
            "Request Credits are SDK-reported observations, not provider charges. "
            "Account delta is before minus after across matching observed quota buckets; "
            "it may include other account activity. Legacy credits aliases SDK session Credits."
        ),
    }
