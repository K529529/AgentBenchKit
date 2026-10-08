import json
from pathlib import Path
from typing import Any

import pytest
from test_runtime import ControlledHarness

from agentbenchkit.analysis.repetition import repeated_tool_calls
from agentbenchkit.analysis.replay import evidence_hash, replay
from agentbenchkit.benchmarks.micro_swe import load_tasks
from agentbenchkit.core.events import Event
from agentbenchkit.harnesses.codex import CodexHarness
from agentbenchkit.runtime.runner import evaluate


def nexus(
    seq: int,
    call: str | None,
    args: str = '{"command":"pytest"}',
    tool: str = "exec_command",
    **updates: Any,
) -> Event:
    return Event.model_validate(
        {
            "event_id": f"e{seq}",
            "run_id": "r",
            "task_id": "t",
            "sample_id": "s",
            "physical_execution_id": "x",
            "seq": seq,
            "timestamp": "now",
            "source": "nexus",
            "type": "tool_call_started",
            "native_call_id": call,
            "attributes": {
                "native": {
                    "kind": "tool_started",
                    "data": {"name": tool, "arguments_json": args, "step": seq},
                }
            },
            **updates,
        }
    )


def codex(seq: int, call: str, command: str | None, phase: str = "started", **extra: Any) -> Event:
    item = {"id": call, "type": "command_execution", **extra}
    if command is not None:
        item["command"] = command
    native = CodexHarness("codex").decode(json.dumps({"type": f"item.{phase}", "item": item}))
    return nexus(
        seq,
        call,
        source="codex",
        type="tool_call_finished" if phase == "completed" else "tool_call_started",
        attributes={"native": native},
    )


def analyze(events: list[Event], complete: bool = True) -> dict[str, Any]:
    return repeated_tool_calls(events, "tasks/t/s/executions/x/trajectory.jsonl", complete)


def test_contiguous_and_across_step_repetition_canonicalizes_json_only() -> None:
    events = [
        nexus(1, "a", '{"command":"pytest", "workdir":"."}'),
        nexus(2, "b", '{ "workdir": ".", "command": "pytest" }'),
        nexus(3, "c", '{"patch":"change"}', "apply_patch"),
        nexus(4, "d", '{"command":"pytest", "workdir":"."}'),
    ]
    result = analyze(events)
    finding = result["observations"][0]
    assert result["status"] == "AVAILABLE"
    assert finding["occurrences"] == 3 and finding["repeat_count"] == 2
    assert finding["max_consecutive_observed"] == 2
    assert finding["patterns"] == ["consecutive_observed_calls", "nonconsecutive_calls"]
    assert finding["steps"] == [1, 2, 4]
    assert finding["call_ids"] == ["a", "b", "d"]
    assert finding["evidence_refs"] == [
        f"tasks/t/s/executions/x/trajectory.jsonl#e{i}" for i in [1, 2, 4]
    ]


def test_lifecycle_pairs_and_duplicate_delivery_are_one_call() -> None:
    events = [
        codex(1, "a", "pytest"),
        codex(2, "a", "pytest", "completed"),
        codex(3, "a", "pytest", "completed"),
    ]
    assert analyze(events)["observations"] == []
    events += [codex(4, "b", "pytest", "completed")]
    result = analyze(events)
    assert result["identified_calls"] == result["analyzed_calls"] == 2
    finding = result["observations"][0]
    assert finding["occurrences"] == 2
    assert finding["match_scope"] == "published_command"
    assert finding["steps"] == [None, None]
    assert finding["evidence_refs"][-1].endswith("#e4")


@pytest.mark.parametrize(
    "different",
    [
        '{"command":"pytest -q"}',
        '{"command":"pytest", "workdir":"elsewhere"}',
        '{"command":"printf \'a  b\'"}',
        '{"command":"pytest \\n"}',
    ],
)
def test_commands_and_execution_context_are_not_simplified(different: str) -> None:
    assert analyze([nexus(1, "a"), nexus(2, "b", different)])["observations"] == []


def test_tools_arrays_and_string_whitespace_remain_distinct() -> None:
    events = [
        nexus(1, "a", '{"args":["a","b"]}'),
        nexus(2, "b", '{"args":["b","a"]}'),
        nexus(3, "c", '{"args":["a","b"]}', "other_tool"),
        nexus(4, "d", '{"args":["a ","b"]}'),
    ]
    assert analyze(events)["observations"] == []


@pytest.mark.parametrize(
    "bad", ["{", '{"command":"[REDACTED]"}', '{"a":1,"a":2}', '["pytest"]', '{"a":NaN}']
)
def test_unusable_arguments_abstain(bad: str) -> None:
    result = analyze([nexus(1, "a", bad), nexus(2, "b", bad)])
    assert result["status"] == "UNAVAILABLE"
    assert result["skipped_calls"] == 2 and not result["observations"]


def test_missing_inputs_and_ids_break_consecutiveness() -> None:
    events = [nexus(1, "a"), nexus(2, None), nexus(3, "b", "{"), nexus(4, "c")]
    result = analyze(events)
    assert result["status"] == "PARTIAL"
    assert result["unidentified_tool_events"] == 1
    assert result["observations"][0]["patterns"] == ["nonconsecutive_calls"]
    assert analyze([codex(1, "a", None), codex(2, "b", None)])["status"] == "UNAVAILABLE"


def test_conflicting_lifecycle_inputs_abstain() -> None:
    result = analyze(
        [codex(1, "a", "pytest"), codex(2, "a", "cat x", "completed"), codex(3, "b", "pytest")]
    )
    assert result["status"] == "PARTIAL"
    assert result["skipped_calls"] == 1 and result["observations"] == []


def test_executions_samples_and_agents_are_never_merged() -> None:
    assert (
        analyze(
            [
                nexus(1, "a"),
                nexus(2, "b", physical_execution_id="retry"),
                nexus(3, "c", sample_id="another"),
                nexus(4, "d", source="unrecognized"),
            ]
        )["observations"]
        == []
    )


def test_incomplete_trajectory_marks_positive_evidence_partial() -> None:
    result = analyze([nexus(1, "a"), nexus(2, "b")], complete=False)
    assert result["status"] == "PARTIAL"
    assert result["observations"][0]["occurrences"] == 2
    assert analyze([], complete=False)["status"] == "UNAVAILABLE"


def test_codex_public_cwd_when_present_is_part_of_signature() -> None:
    assert (
        analyze(
            [
                codex(1, "a", "pytest", cwd="/a"),
                codex(2, "b", "pytest", cwd="/b"),
                codex(3, "c", "pytest"),
            ]
        )["observations"]
        == []
    )


async def test_repeat_after_edit_is_neutral_and_replay_preserves_verdict(tmp_path: Path) -> None:
    directory = await evaluate(load_tasks(("clamp",)), ControlledHarness(True), tmp_path)
    sample = next(directory.glob("tasks/*/*/sample.json"))
    trajectory = next(sample.parent.glob("executions/*/trajectory.jsonl"))
    terminal = Event.model_validate_json(trajectory.read_text(encoding="utf-8").splitlines()[-1])
    identity = {
        name: getattr(terminal, name)
        for name in ("run_id", "task_id", "sample_id", "physical_execution_id")
    }
    events = [
        nexus(1, "a", **identity),
        nexus(2, "edit", '{"patch":"fix"}', "apply_patch", **identity),
        nexus(3, "b", **identity),
        terminal.model_copy(update={"seq": 4}),
    ]
    trajectory.write_text("".join(e.model_dump_json() + "\n" for e in events), encoding="utf-8")
    original = sample.read_bytes()
    before = evidence_hash(directory)
    first = replay(tmp_path, directory.name)
    baseline = first.read_bytes()
    second = replay(tmp_path, directory.name)
    result = json.loads(second.read_text(encoding="utf-8"))["samples"][0]
    assert result["trajectory_analysis"]["repeated_tool_calls"]["observations"]
    assert result["failure"]["suspected_owner"] == "UNKNOWN"
    assert result["failure"]["observations"] == []
    assert result["sample_success"] is True
    assert "STAGNATION" not in json.dumps(result)
    assert sample.read_bytes() == original and evidence_hash(directory) == before
    assert first.read_bytes() == baseline and first != second


def test_quoted_shell_whitespace_is_significant() -> None:
    a = nexus(1, "a", json.dumps({"command": "printf 'a  b'"}))
    b = nexus(2, "b", json.dumps({"command": "printf 'a b'"}))
    assert analyze([a, b])["observations"] == []


def test_qoder_public_inputs_are_distinct_from_results() -> None:
    def event(seq: int, call: str, kind: str, data: dict[str, Any]) -> Event:
        return nexus(seq, call, source="qoder", type=kind, attributes={"native": {"data": data}})

    result = analyze(
        [
            event(
                1, "a", "tool_call_started", {"name": "Bash", "arguments": {"command": "pytest"}}
            ),
            event(2, "a", "tool_call_finished", {"content": "pytest", "is_error": False}),
            event(
                3, "b", "tool_call_started", {"name": "Bash", "arguments": {"command": "pytest"}}
            ),
        ]
    )
    assert result["analyzed_calls"] == 2
    assert result["observations"][0]["call_ids"] == ["a", "b"]
    assert result["observations"][0]["occurrences"] == 2
