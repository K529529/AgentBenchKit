"""Repeated public inputs are observations, never proof of waste or stagnation."""

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from agentbenchkit.core.events import Event

VERSION = "repeated-tool-calls-v1"
TOOL_EVENTS = {"tool_call_started", "tool_call_finished"}


@dataclass(frozen=True)
class Signature:
    tool: str
    arguments: str
    scope: str


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("ambiguous duplicate JSON key")
        result[key] = value
    return result


def signature(event: Event) -> Signature | None:
    native = event.attributes.get("native")
    if not isinstance(native, dict):
        return None
    data = native.get("data")
    if event.source == "nexus" and isinstance(data, dict):
        name, raw = data.get("name"), data.get("arguments_json")
        if not isinstance(name, str) or not name or not isinstance(raw, str):
            return None
        try:
            args = json.loads(raw, object_pairs_hook=unique_object)
        except (ValueError, RecursionError):
            return None
        if not isinstance(args, dict):
            return None
        scope = "published_arguments"
    elif event.source == "codex":
        codex = native.get("codex")
        item = codex.get("item") if isinstance(codex, dict) else None
        if not isinstance(item, dict) or item.get("type") != "command_execution":
            return None  # file_change is output evidence, not complete input arguments.
        command = item.get("command")
        if not isinstance(command, str) or not command:
            return None
        name, args, scope = "command_execution", {"command": command}, "published_command"
        # Include public execution context when present, without inventing defaults.
        for key in ("cwd", "workdir", "shell"):
            if key in item:
                args[key] = item[key]
    else:
        return None
    try:
        canonical = json.dumps(args, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, RecursionError):
        return None
    if "[REDACTED]" in canonical or "[REDACTED]" in name:
        return None  # Redaction can collapse different inputs to the same text.
    return Signature(name, canonical, scope)


def repeated_tool_calls(
    events: list[Event], trajectory_ref: str, trajectory_complete: bool
) -> dict[str, Any]:
    calls: dict[tuple[str, ...], list[Event]] = defaultdict(list)
    positions: dict[tuple[str, ...], int] = {}
    unidentified = position = 0
    for event in events:
        if event.type not in TOOL_EVENTS:
            continue
        if not event.native_call_id:
            unidentified += 1
            position += 1  # Unknown calls cannot make two known calls consecutive.
            continue
        key = (
            event.run_id,
            event.sample_id,
            event.physical_execution_id,
            event.source,
            event.native_call_id,
        )
        if key not in calls:
            positions[key] = position
            position += 1
        calls[key].append(event)

    groups: dict[tuple[tuple[str, ...], Signature], list[tuple[int, Event]]] = defaultdict(list)
    eligible = 0
    for call_key, records in calls.items():
        inputs = [(event, signature(event)) for event in records]
        known = {value for _, value in inputs if value is not None}
        if len(known) != 1:
            continue  # Missing/ambiguous inputs are unavailable, not an empty {}.
        value = next(iter(known))
        representative = next(event for event, candidate in inputs if candidate == value)
        groups[(call_key[:-1], value)].append((positions[call_key], representative))
        eligible += 1

    observations = []
    for (identity, value), occurrences in groups.items():
        if len(occurrences) < 2:
            continue
        streak = longest = 1
        patterns = set()
        for (previous, _), (current, _) in zip(occurrences, occurrences[1:], strict=False):
            adjacent = current == previous + 1
            patterns.add("consecutive_observed_calls" if adjacent else "nonconsecutive_calls")
            streak = streak + 1 if adjacent else 1
            longest = max(longest, streak)
        evidence = [event for _, event in occurrences]
        steps = []
        for event in evidence:
            native = event.attributes.get("native")
            data = native.get("data") if isinstance(native, dict) else None
            step = data.get("step") if isinstance(data, dict) else None
            steps.append(step if type(step) is int else None)
        observations.append(
            {
                "observation": "REPEATED_TOOL_CALL",
                "source": identity[-1],
                "physical_execution_id": identity[-2],
                "tool": value.tool,
                "match_scope": value.scope,
                "input_fingerprint": hashlib.sha256(value.arguments.encode()).hexdigest(),
                "occurrences": len(evidence),
                "repeat_count": len(evidence) - 1,
                "patterns": sorted(patterns),
                "max_consecutive_observed": longest,
                "steps": steps,
                "call_ids": [event.native_call_id for event in evidence],
                "evidence_refs": [f"{trajectory_ref}#{event.event_id}" for event in evidence],
            }
        )
    return {
        "analysis_version": VERSION,
        "status": "UNAVAILABLE"
        if not eligible
        else (
            "PARTIAL"
            if eligible < len(calls) or unidentified or not trajectory_complete
            else "AVAILABLE"
        ),
        "identified_calls": len(calls),
        "analyzed_calls": eligible,
        "skipped_calls": len(calls) - eligible,
        "unidentified_tool_events": unidentified,
        "trajectory_complete": trajectory_complete,
        "observations": observations,
        "interpretation": (
            "Identical public inputs only; tests, retries and reads may legitimately repeat. "
            "No conclusion about identical workspace state, inefficiency, stagnation or ownership. "
            "Counts cover observed calls in one physical execution, not hidden agent activity."
        ),
    }
