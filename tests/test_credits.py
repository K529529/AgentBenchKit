import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_runtime import ControlledHarness

from agentbenchkit.analysis.replay import metrics, replay
from agentbenchkit.benchmarks.micro_swe import load_tasks
from agentbenchkit.core.events import Event
from agentbenchkit.runtime.runner import evaluate
from agentbenchkit.viewer.app import create_app


def credit_events() -> list[Event]:
    native: list[dict[str, Any]] = [
        {
            "kind": "usage_snapshot",
            "data": {"phase": "before", "usage": {"addOnQuota": {"remaining": 390}}},
        },
        *[
            {
                "kind": "model_finished",
                "data": {"request_id": r, "usage": {"credits": 1.5, "billable": False}},
            }
            for r in ("a", "a", "b")
        ],
        {
            "kind": "usage_snapshot",
            "data": {"phase": "after", "usage": {"addOnQuota": {"remaining": 390}}},
        },
        {
            "kind": "run_finished",
            "data": {
                "total_credits": 0,
                "reported_request_credits": 3,
                "observed_request_count": 2,
            },
        },
    ]
    return [
        Event.model_validate(
            {
                "event_id": f"e:{i}",
                "run_id": "r",
                "task_id": "t",
                "sample_id": "s",
                "physical_execution_id": "e",
                "seq": i,
                "timestamp": "2026-10-08T00:00:00Z",
                "source": "qoder",
                "type": "agent_finished" if n["kind"] == "run_finished" else n["kind"],
                "attributes": {"native": n},
            }
        )
        for i, n in enumerate(native, 1)
    ]


def test_credit_quantities_and_deduplicated_billable_flags() -> None:
    result = metrics(credit_events(), {}, True)
    assert result["reported_request_credits"] == 3
    assert result["sdk_session_credits"] == result["credits"] == 0
    assert result["observed_account_delta"] == 0
    assert result["request_billable_flags"] == {"true": 0, "false": 2, "unavailable": 0}
    assert result["cost"] is None


@pytest.mark.parametrize(
    "change", ["missing_after", "empty_after", "changed_buckets", "invalid_number"]
)
def test_account_observability_never_invents_zero(change: str) -> None:
    events = credit_events()
    if change == "missing_after":
        events.pop(-2)
    else:
        usage: dict[str, Any] = (
            {}
            if change == "empty_after"
            else {
                "userQuota" if change == "changed_buckets" else "addOnQuota": {
                    "remaining": 390 if change == "changed_buckets" else "unknown"
                }
            }
        )
        events[-2] = Event.model_validate(
            {
                **events[-2].model_dump(),
                "attributes": {
                    "native": {"kind": "usage_snapshot", "data": {"phase": "after", "usage": usage}}
                },
            }
        )
    assert metrics(events, {}, True)["observed_account_delta"] is None


def test_historical_missing_request_fields_and_observed_zero() -> None:
    terminal = credit_events()[-1]
    terminal = Event.model_validate(
        {
            **terminal.model_dump(),
            "attributes": {
                "native": {
                    "kind": "run_finished",
                    "data": {
                        "total_credits": 0,
                        "reported_request_credits": 0,
                        "observed_request_count": 0,
                    },
                }
            },
        }
    )
    result = metrics([terminal], {}, True)
    assert result["reported_request_credits"] is None
    assert result["sdk_session_credits"] == 0
    assert result["request_billable_flags"] is None
    assert result["observed_account_delta"] is None
    result = metrics([], {}, False)
    for field in (
        "reported_request_credits",
        "sdk_session_credits",
        "observed_account_delta",
        "credits",
        "request_billable_flags",
    ):
        assert result[field] is None
    events = credit_events()
    for i in (1, 2, 3):
        events[i] = Event.model_validate(
            {
                **events[i].model_dump(),
                "attributes": {
                    "native": {
                        "kind": "model_finished",
                        "data": {"request_id": "zero", "usage": {"credits": 0}},
                    }
                },
            }
        )
    result = metrics(events, {}, True)
    assert result["reported_request_credits"] == 0
    assert result["request_billable_flags"] == {"true": 0, "false": 0, "unavailable": 1}


async def test_credit_replay_and_viewer_preserve_raw_trajectory(tmp_path: Path) -> None:
    run = await evaluate(load_tasks(("clamp",)), ControlledHarness(True), tmp_path)
    sample = next(run.glob("tasks/*/*/sample.json"))
    trajectory = next(run.glob("tasks/*/*/executions/*/trajectory.jsonl"))
    trajectory.write_text(
        "".join(e.model_dump_json() + "\n" for e in credit_events()), encoding="utf-8"
    )
    before = trajectory.read_bytes()
    result = json.loads(replay(tmp_path, run.name).read_text())
    assert result["samples"][0]["metrics"]["reported_request_credits"] == 3
    with TestClient(create_app(tmp_path)) as client:
        response = client.get(f"/runs/{run.name}/samples/{sample.parent.name}")
        assert response.status_code == 200
        for key in (
            "reported_request_credits",
            "sdk_session_credits",
            "observed_account_delta",
            "request_billable_flags",
        ):
            assert key in response.text
        assert "不能互当实际扣费" in response.text
    assert trajectory.read_bytes() == before
