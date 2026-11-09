"""Read-only adapters for native and independently stored post-hoc Judge results."""

import json
from collections import Counter
from pathlib import Path
from typing import Any

from agentbenchkit.viewer import presentation as view
from agentbenchkit.viewer.analytics import numeric

LABELS = {
    "test_quality": "测试质量",
    "tool_use_quality": "工具使用质量",
    "solution_quality": "方案质量",
    "efficiency": "效率",
}


def read_record(path: Path, root: Path) -> dict[str, Any]:
    try:
        if not path.resolve().is_relative_to(root.resolve()):
            return {}
        if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
            return {}
        if path.stat().st_size > view.JSON_LIMIT:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def records(directory: Path, external: Path | None) -> list[dict[str, Any]]:
    """Read completed records and explicit pending metadata, never inputs or requests."""
    found: list[dict[str, Any]] = []
    sources = [(directory / "judge", directory)]
    if external is not None:
        sources += [(external / "results", external), (external / "metadata", external)]
    result_ids: set[str] = set()
    for folder, root in sources:
        for path in sorted(folder.glob("*.json")):
            record = read_record(path, root)
            if record.get("run_id") != directory.name:
                continue
            execution = str(record.get("execution_id") or "")
            if folder.name == "metadata" and execution in result_ids:
                continue
            if folder.name == "results":
                result_ids.add(execution)
            try:
                modified = path.stat().st_mtime
            except OSError:
                continue
            record = {**record, "viewer_source": path.name, "viewer_mtime": modified}
            found.append(record)
    return sorted(found, key=lambda r: r["viewer_mtime"], reverse=True)


def for_sample(
    directory: Path, sample: dict[str, Any], executions: set[str], all_records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result = []
    for record in all_records:
        execution = record.get("execution_id") or record.get("physical_execution_id")
        if record.get("sample_id") != sample["sample_id"] and not (
            execution in executions and record.get("task_id") == sample["task_id"]
        ):
            continue
        status = record.get("judge_status") or record.get("status") or "UNKNOWN"
        status = "JUDGED" if status == "COMPLETED" else status
        scores = view.mapping(record.get("rubric_scores") or record.get("scores"))
        dimensions = []
        for key, label in LABELS.items():
            entries = scores.get("dimensions", [])
            entries = entries if isinstance(entries, list) else []
            item = next(
                (d for d in entries if isinstance(d, dict) and d.get("dimension") == key), {}
            )
            score = item.get("score")
            score = score if status == "JUDGED" and numeric(score) and score <= 4 else None
            refs = []
            for ref in (
                item.get("evidence_refs", []) if isinstance(item.get("evidence_refs"), list) else []
            ):
                prefix = f"runs/{directory.name}/"
                relative = str(ref).removeprefix(prefix)
                refs.append(
                    view.reference(directory, directory.name, relative, "", sample["sample_id"])
                )
            dimensions.append(
                {
                    "key": key,
                    "label": label,
                    "score": score,
                    "reason": item.get("reason") or "尚无可用评分理由",
                    "refs": refs,
                }
            )
        result.append(
            {
                "status": status,
                "source": record["viewer_source"],
                "execution": execution,
                "model": record.get("model_returned")
                or record.get("model")
                or record.get("model_requested"),
                "rubric": record.get("rubric_version") or record.get("analysis_version"),
                "prompt": record.get("prompt_version"),
                "created": record.get("created_at"),
                "dimensions": dimensions,
                "uncertainty": record.get("uncertainty"),
                "error": record.get("error"),
                "usage": record.get("judge_usage") or record.get("usage"),
                "duration_ms": record.get("duration_ms")
                if record.get("duration_ms") is not None
                else record.get("elapsed_seconds", 0) * 1000
                if numeric(record.get("elapsed_seconds"))
                else None,
                "raw": record,
            }
        )
    return result


def coverage(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(row["status"] for row in rows))
