"""Nexus public event accounting and narrowly scoped, redacted session preservation."""

import hashlib
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from agentbenchkit.storage.artifacts import Redactor, write_json


def root_event(event: dict[str, JsonValue]) -> bool:
    data = event.get("data")
    return event.get("kind") != "subagent_event" and (
        not isinstance(data, dict) or data.get("agent_id") in (None, "root")
    )


def statistics(events: list[dict[str, JsonValue]]) -> dict[str, Any]:
    agents: dict[str, dict[str, Any]] = {"root": {"agent_id": "root"}}
    reports: list[dict[str, Any]] = []
    started = 0
    seen: set[tuple[str, str, str]] = set()
    for outer in events:
        event = outer
        agent = "root"
        if outer.get("kind") == "subagent_event":
            wrapped = outer.get("data")
            if not isinstance(wrapped, dict):
                continue
            event = wrapped
            agent = str(wrapped.get("agent_id"))
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        kind = event.get("kind")
        if kind in {"agent_created", "agent_state"}:
            identity = str(data.get("agent_id"))
            agents[identity] = {
                key: data.get(key)
                for key in ("agent_id", "parent_id", "role", "model", "reasoning_effort", "state")
            }
        if kind == "run_started":
            agent = str(data.get("agent_id", agent))
            agents.setdefault(agent, {"agent_id": agent}).update(
                {
                    key: data[key]
                    for key in ("model", "reasoning_effort", "execution_mode")
                    if key in data
                }
            )
        if kind not in {"model_started", "model_finished"}:
            continue
        # Request IDs identify actual attempts, including compaction. Snapshots and
        # compaction_usage duplicate their underlying model_finished usage.
        request = data.get("request_id")
        if request is not None:
            key = (agent, str(kind), str(request) + ":" + str(data.get("attempt", 1)))
            if key in seen:
                continue
            seen.add(key)
        agents.setdefault(agent, {"agent_id": agent})
        if data.get("model"):
            agents[agent]["model"] = data["model"]
        if kind == "model_started":
            started += 1
        else:
            usage = data.get("usage")
            reports.append(dict(usage) if isinstance(usage, dict) else {})
    result: dict[str, Any] = {
        "scope": "root_and_all_descendants_actual_model_attempts",
        "agent_count": len(agents),
        "delegated": len(agents) > 1,
        "agents": list(agents.values()),
        "model_calls": started,
        "model_calls_finished": len(reports),
    }
    for name in ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens"):
        known = [r[name] for r in reports if type(r.get(name)) is int]
        result[name] = sum(known) if started == len(reports) == len(known) and started else None
        result[name + "_known"] = sum(known)
    return result


def archive_sessions(home: Path, destination: Path, redactor: Redactor) -> None:
    root = home / ".nexus" / "sessions"
    if not root.exists():
        return
    for parent in (home, home / ".nexus", root):
        if parent.is_symlink() or parent.is_junction():
            raise ValueError("linked Nexus session directory cannot be archived")
    entries = []
    for source in sorted(root.rglob("*.jsonl")):
        if any(
            p.is_symlink() or p.is_junction()
            for p in (source, *source.parents)
            if p.is_relative_to(home)
        ) or not source.resolve().is_relative_to(root.resolve()):
            raise ValueError("Nexus session log escapes isolated HOME")
        relative = source.relative_to(root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        content = redactor.text(source.read_text(encoding="utf-8")).encode()
        target.write_bytes(content)
        entries.append({"path": relative.as_posix(), "sha256": hashlib.sha256(content).hexdigest()})
    write_json(
        destination / "manifest.json",
        {"scope": "isolated Nexus sessions only", "redacted": True, "files": entries},
    )
