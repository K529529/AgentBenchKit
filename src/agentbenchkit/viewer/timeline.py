"""Bounded timeline navigation; observed turns are distinct from Harness steps."""

import json
from pathlib import Path
from typing import Any

from agentbenchkit.viewer import presentation as view


def rows(path: Path) -> Any:
    turn = 0
    for number, event in view.events(path):
        if event.get("type") == "turn_start":
            turn += 1
        row = view.event_view(number, event)
        row["turn"] = turn or None
        yield row, event


def matches(row: dict[str, Any], event: dict[str, Any], filters: dict[str, str]) -> bool:
    kind = filters.get("kind")
    return bool(
        (not kind or row["type"] == kind or row.get(kind))
        and all(
            not filters.get(k) or str(row[field]) == filters[k]
            for k, field in (
                ("tool", "tool"),
                ("call", "call_id"),
                ("step", "step"),
                ("seq", "seq"),
                ("turn", "turn"),
            )
        )
        and (
            not filters.get("q")
            or filters["q"].casefold() in json.dumps(event, ensure_ascii=False).casefold()
        )
    )


def navigation(path: Path, filters: dict[str, str]) -> dict[str, Any]:
    pages: list[int] = []
    count = budget = total = matched = turns = last_turn = last_activity = 0
    steps: set[str] = set()
    for row, event in rows(path):
        total = row["line"]
        turns = row["turn"] or 0
        if row["type"] == "turn_start":
            last_turn = total
        if row["type"] in {
            "tool_call_started",
            "tool_call_finished",
            "model_call_started",
            "model_call_finished",
            "agent_finished",
            "message",
        }:
            last_activity = total
        if row["step"] is not None:
            steps.add(str(row["step"]))
        if not matches(row, event, filters):
            continue
        if not count or count >= 60 or budget > 350_000:
            pages.append(total)
            count = budget = 0
        row["raw"] = json.dumps(event, ensure_ascii=False, indent=2)[:3000]
        budget += len(json.dumps(row, ensure_ascii=False).encode("utf-8")) * 2
        count += 1
        matched += 1
    return dict(
        total=total,
        matched=matched,
        pages=pages,
        turns=turns,
        last_turn=last_turn,
        last_activity=last_activity,
        has_steps=bool(steps),
    )
