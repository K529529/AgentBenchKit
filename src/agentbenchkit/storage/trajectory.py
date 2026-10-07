"""Bounded evidence reader tolerant only of an interrupted final JSONL record."""

import json
from pathlib import Path

from agentbenchkit.core.events import Event


def read_events(path: Path, max_bytes: int = 8_000_000) -> tuple[list[Event], bool]:
    if path.stat().st_size > max_bytes:
        raise ValueError("trajectory exceeds reader size limit")
    data = path.read_text(encoding="utf-8")
    lines = data.splitlines()
    incomplete = bool(data and not data.endswith("\n"))
    events: list[Event] = []
    for index, line in enumerate(lines):
        try:
            event = Event.model_validate_json(line)
        except (ValueError, json.JSONDecodeError):
            if index == len(lines) - 1 and incomplete:
                break
            raise ValueError(f"invalid trajectory record at line {index + 1}") from None
        if events and event.seq <= events[-1].seq:
            raise ValueError("trajectory sequence is not increasing")
        events.append(event)
    return events, incomplete
