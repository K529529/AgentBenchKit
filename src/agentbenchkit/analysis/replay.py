"""Versioned rule-first analysis derived from immutable public evidence."""

import hashlib
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentbenchkit.core.events import Event
from agentbenchkit.core.metrics import summarize
from agentbenchkit.core.models import SampleResult
from agentbenchkit.runtime.recovery import load_sample
from agentbenchkit.storage.artifacts import write_json
from agentbenchkit.storage.index import index_run, read_json, resolve_run
from agentbenchkit.storage.trajectory import read_events

VERSION = "rules-v1"


def evidence_hash(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory)
        if (
            not path.is_file()
            or path.is_symlink()
            or "work" in relative.parts
            or "analyses" in relative.parts
            or "judge" in relative.parts
            or relative.name in {"owner.lock", "summary.md", "summary.json", "run_state.json"}
        ):
            continue
        digest.update(relative.as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def metrics(events: list[Event], capabilities: dict[str, Any], complete: bool) -> dict[str, Any]:
    terminals = [event for event in events if event.type == "agent_finished"]
    terminal: dict[str, Any] = {}
    if terminals:
        native = terminals[-1].attributes.get("native")
        data = native.get("data") if isinstance(native, dict) else None
        if isinstance(data, dict):
            terminal = dict(data)
    usage = terminal.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    tool_events = [
        event for event in events if event.type in {"tool_call_started", "tool_call_finished"}
    ]
    tool_count = len({event.native_call_id or event.event_id for event in tool_events})
    return {
        "steps": terminal.get("steps"),
        "model_calls": terminal.get("model_calls"),
        "tool_calls": tool_count if capabilities.get("tool_calls") and complete else None,
        "input_tokens": usage.get("input_tokens") if capabilities.get("model_usage") else None,
        "output_tokens": usage.get("output_tokens") if capabilities.get("model_usage") else None,
        "cached_input_tokens": usage.get("cached_input_tokens")
        if capabilities.get("model_usage")
        else None,
        "cost": None,
        "cost_reason": "no pinned provider price table",
        "trajectory_complete": complete,
        "events_observed": len(events),
        "capabilities": capabilities,
    }


def analyze_sample(
    directory: Path, sample_path: Path, capabilities: dict[str, Any]
) -> dict[str, Any]:
    sample = load_sample(sample_path)
    folder = sample_path.parent
    records = [(path, read_json(path)) for path in folder.glob("executions/*/execution.json")]
    records.sort(key=lambda item: item[1].get("started_at", ""))
    events: list[Event] = []
    complete = False
    trajectory_error = None
    execution: dict[str, Any] = records[-1][1] if records else {}
    if records:
        trajectory = records[-1][0].parent / "trajectory.jsonl"
        if trajectory.exists():
            try:
                events, truncated = read_events(trajectory)
                complete = (
                    not truncated
                    and not execution.get("process", {}).get("output_truncated")
                    and any(event.type == "agent_finished" for event in events)
                )
            except ValueError as exc:
                trajectory_error = str(exc)
    refs = [sample_path.relative_to(directory).as_posix()]
    observations = []
    owner, confidence, phase = "UNKNOWN", 0.0, execution.get("phase", "UNKNOWN")
    termination = sample.execution_status.value
    if sample.execution_status in {"TIMED_OUT", "CANCELLED", "INTERRUPTED"}:
        observations.append(
            "COMMAND_TIMEOUT"
            if sample.execution_status == "TIMED_OUT"
            else sample.execution_status.value
        )
    elif sample.startup_retries_exhausted:
        observations.append("SETUP_FAILURE")
        owner, confidence, phase = "ENVIRONMENT", 0.8, "PREPARE"
    elif sample.agent_outcome in {"FAILED", "LIMITED", "ABORTED"}:
        termination = sample.agent_outcome.value
        owner, confidence, phase = "AGENT", 0.7, "AGENT"
    if sample.verifier_status == "FAIL":
        observations.append("TEST_FAILURE")
        if owner == "UNKNOWN" and sample.execution_status == "FINISHED":
            owner, confidence, phase = "AGENT", 0.7, "VERIFY"
    if sample.verifier_status == "ERROR":
        observations.append("VERIFIER_ERROR")
        if sample.execution_status == "FINISHED":
            owner, confidence, phase = "VERIFIER", 0.8, "VERIFY"
    candidate_path = folder / "candidate_manifest.json"
    if candidate_path.exists():
        candidate = read_json(candidate_path)
        if not candidate["changed"] and not candidate["deleted"]:
            observations.append("NO_MUTATION")
        refs.append(candidate_path.relative_to(directory).as_posix())
    if sample.execution_status == "ERROR":
        if any("protocol" in str(error) for error in execution.get("errors", [])):
            observations.append("INCOMPLETE_PROTOCOL")
            owner, confidence = "HARNESS", 0.7
        elif owner == "UNKNOWN":
            owner, confidence = "FRAMEWORK", 0.5
    for event in events:
        native = event.attributes.get("native")
        data = native.get("data") if isinstance(native, dict) else None
        if event.type == "tool_call_finished" and isinstance(data, dict):
            if (
                data.get("ok") is False
                or data.get("status") == "failed"
                or isinstance(data.get("exit_code"), int)
                and data["exit_code"] != 0
            ):
                observations.append("TOOL_ERROR")
                refs.append(
                    f"{records[-1][0].parent.relative_to(directory).as_posix()}/trajectory.jsonl#{event.event_id}"
                )
    if trajectory_error or not complete:
        observations.append("INCOMPLETE_OBSERVABILITY")
    verifier = folder / "verifier.json"
    if verifier.exists():
        refs.append(verifier.relative_to(directory).as_posix())
    derived = metrics(events, capabilities, complete)
    derived["latency_ms"] = (
        sum(float(data.get("duration_ms", 0)) for _, data in records) if records else None
    )
    return {
        "sample_id": sample.sample_id,
        "task_id": sample.task_id,
        "candidate_pass": sample.candidate_pass,
        "sample_success": sample.sample_success,
        "metrics": derived,
        "failure": {
            "phase": phase,
            "observations": sorted(set(observations)),
            "termination_reason": termination,
            "suspected_owner": owner,
            "confidence": confidence,
            "evidence_refs": refs,
            "analysis_version": VERSION,
            "uncertainty": "Observed facts do not establish model capability or sole root cause.",
        },
        "trajectory_error": trajectory_error,
    }


def analyze_run(directory: Path) -> dict[str, Any]:
    run_id = directory.name
    state = directory / "run_state.json"
    if state.exists() and read_json(state)["status"] == "RUNNING":
        raise ValueError("run is still RUNNING; finish or recover it before replay")
    manifest = read_json(directory / "manifest.json")
    capabilities = manifest["harness"]["capabilities"]
    sample_paths = sorted(directory.glob("tasks/*/*/sample.json"))
    samples = [load_sample(path) for path in sample_paths]
    plan = directory / "plan.json"
    if plan.exists():
        known = {sample.sample_id for sample in samples}
        samples.extend(
            SampleResult.model_validate(item)
            for item in read_json(plan)
            if item["sample_id"] not in known
        )
    results = [analyze_sample(directory, path, capabilities) for path in sample_paths]
    observed = {result["sample_id"] for result in results}
    for sample in samples:
        if sample.sample_id not in observed:
            results.append(
                {
                    "sample_id": sample.sample_id,
                    "task_id": sample.task_id,
                    "sample_success": sample.sample_success,
                    "candidate_pass": sample.candidate_pass,
                    "metrics": metrics([], capabilities, False),
                    "failure": {
                        "phase": "UNKNOWN",
                        "observations": ["MISSING_SAMPLE_EVIDENCE"],
                        "termination_reason": sample.execution_status.value,
                        "suspected_owner": "UNKNOWN",
                        "confidence": 0,
                        "evidence_refs": ["plan.json"],
                        "analysis_version": VERSION,
                    },
                    "trajectory_error": "No final sample record",
                }
            )
    analysis_id = uuid.uuid4().hex
    output = {
        "analysis_id": analysis_id,
        "analysis_version": VERSION,
        "input_evidence_hash": evidence_hash(directory),
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "status": "PARTIAL"
        if any(not r["metrics"]["trajectory_complete"] for r in results)
        else "COMPLETED",
        "summary": summarize(samples, manifest.get("k", 1)).model_dump(),
        "samples": results,
        "failure_distribution": dict(
            Counter(
                r["failure"]["suspected_owner"] for r in results if r["sample_success"] is not True
            )
        ),
    }
    return output


def replay(root: Path, run_id: str) -> Path:
    directory = resolve_run(root, run_id)
    output = analyze_run(directory)
    target = directory / "analyses" / f"{output['analysis_id']}.json"
    write_json(target, output)
    index_run(root, run_id)
    return target
