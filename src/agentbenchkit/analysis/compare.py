"""Manifest-first comparison; observed changes are not causal capability claims."""

from collections import defaultdict
from pathlib import Path
from typing import Any

from agentbenchkit.analysis.replay import analyze_run, replay
from agentbenchkit.storage.index import read_json, resolve_run


def conditions(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "tasks": {
            task["task_id"]: {
                key: task.get(key)
                for key in (
                    "fixture_hash",
                    "verifier_hash",
                    "baseline_revision",
                    "timeouts",
                    "prompt",
                )
            }
            for task in manifest["tasks"]
        },
        "environment": manifest["environment"],
        "agent_config": manifest.get("agent_config"),
        "model": manifest.get("model"),
        "requested_model": manifest.get("requested_model"),
        "harness": {
            key: manifest["harness"].get(key)
            for key in ("name", "reported_version", "harness_version", "capabilities")
        },
        "samples_per_task": manifest["samples_per_task"],
        "concurrency": manifest["concurrency"],
        "analyzers": manifest.get("analyzers"),
        "k": manifest.get("k", 1),
    }


def compare(
    root: Path,
    baseline_id: str,
    candidate_id: str,
    expected_changes: tuple[str, ...] = (),
    persist_analysis: bool = True,
) -> dict[str, Any]:
    allowed = {
        "harness",
        "model",
        "requested_model",
        "agent_config",
        "environment",
        "concurrency",
        "tasks",
        "samples_per_task",
        "analyzers",
        "k",
    }
    if set(expected_changes) - allowed:
        raise ValueError("unknown expected-change field")
    base_dir, next_dir = resolve_run(root, baseline_id), resolve_run(root, candidate_id)
    before, after = (
        conditions(read_json(base_dir / "manifest.json")),
        conditions(read_json(next_dir / "manifest.json")),
    )
    changes = [key for key in before if before[key] != after[key]]
    unexpected = [key for key in changes if key not in expected_changes]
    eligibility_warnings = []
    for label, condition in (("baseline", before), ("candidate", after)):
        config = condition.get("agent_config") or {}
        if condition.get("model") is None:
            eligibility_warnings.append(f"{label}: missing typed model conditions")
        if config.get("evaluation_class") != "explicit_api":
            eligibility_warnings.append(f"{label}: not an explicit API evaluation")
        if condition.get("model") is not None:
            uncontrolled = [
                field
                for field in ("max_output_tokens", "temperature", "top_p", "seed")
                if condition["model"].get(field) is None
            ]
            if uncontrolled:
                eligibility_warnings.append(
                    f"{label}: unspecified controls: {', '.join(uncontrolled)}"
                )
    base, candidate = (
        (read_json(replay(root, baseline_id)), read_json(replay(root, candidate_id)))
        if persist_analysis
        else (analyze_run(base_dir), analyze_run(next_dir))
    )

    def grouped(analysis: dict[str, Any]) -> dict[str, list[Any]]:
        groups: dict[str, list[Any]] = defaultdict(list)
        for sample in analysis["samples"]:
            groups[sample["task_id"]].append(sample["sample_success"])
        return groups

    a, b = grouped(base), grouped(candidate)
    tasks = {}
    for task in sorted(a.keys() | b.keys()):
        if task not in a:
            status = "ADDED"
        elif task not in b:
            status = "REMOVED"
        elif unexpected or None in a[task] or None in b[task]:
            status = "INCONCLUSIVE"
        else:
            delta = sum(b[task]) / len(b[task]) - sum(a[task]) / len(a[task])
            status = "IMPROVED" if delta > 0 else "REGRESSED" if delta < 0 else "UNCHANGED"
        tasks[task] = {"status": status, "baseline": a.get(task), "candidate": b.get(task)}
    return {
        "baseline_run": baseline_id,
        "candidate_run": candidate_id,
        "changed_conditions": changes,
        "expected_changes": list(expected_changes),
        "comparability_warnings": unexpected + eligibility_warnings,
        "formal_comparable": not unexpected and not eligibility_warnings,
        "tasks": tasks,
        "baseline_summary": base["summary"],
        "candidate_summary": candidate["summary"],
        "baseline_failure_distribution": base["failure_distribution"],
        "candidate_failure_distribution": candidate["failure_distribution"],
        "baseline_samples": base["samples"],
        "candidate_samples": candidate["samples"],
        "interpretation": (
            "Observed sample changes; one stochastic run is not proof of stable capability change."
        ),
    }
