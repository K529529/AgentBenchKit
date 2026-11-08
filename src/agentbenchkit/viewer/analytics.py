"""Display-only statistics over known evidence; no evaluation or RCA semantics."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any, TypeGuard


def numeric(value: Any) -> TypeGuard[int | float]:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def percentile(values: list[float], fraction: float) -> float:
    position = (len(values) - 1) * fraction
    low = math.floor(position)
    high = math.ceil(position)
    return values[low] + (values[high] - values[low]) * (position - low)


def distribution(
    samples: list[dict[str, Any]], key: str, label: str, unit: str, scale: float = 1
) -> dict[str, Any]:
    points = [
        {"task": s["task_id"], "sample": s["sample_id"], "value": s[key] / scale}
        for s in samples
        if numeric(s.get(key))
    ]
    values = sorted(p["value"] for p in points)
    result: dict[str, Any] = {
        "label": label,
        "unit": unit,
        "known": len(values),
        "total": len(samples),
        "complete": bool(values) and len(values) == len(samples),
        "bins": [],
        "ranking": sorted(points, key=lambda p: p["value"], reverse=True)[:10],
        "median": None,
        "p90": None,
        "maximum": None,
        "outliers": [],
    }
    if not values:
        return result
    result.update(median=percentile(values, 0.5), p90=percentile(values, 0.9), maximum=values[-1])
    if len(values) >= 4:
        q1, q3 = percentile(values, 0.25), percentile(values, 0.75)
        threshold = q3 + 1.5 * (q3 - q1)
        result["outliers"] = [p for p in points if p["value"] > threshold]
        result["threshold"] = threshold
    if result["complete"]:
        count = min(6, len(values)) if values[-1] > values[0] else 1
        width = (values[-1] - values[0]) / count if count > 1 else 1
        bins = [
            {"low": values[0] + i * width, "high": values[0] + (i + 1) * width, "count": 0}
            for i in range(count)
        ]
        if count == 1:
            bins[0]["high"] = values[-1]
        for v in values:
            index = min(count - 1, int((v - values[0]) / width))
            bins[index]["count"] += 1
        result["bins"] = bins
    return result


def paired_metrics(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, Any]:
    groups: list[dict[str, list[dict[str, Any]]]] = [defaultdict(list), defaultdict(list)]
    for group, samples in zip(groups, (before, after), strict=True):
        for sample in samples:
            group[sample["task_id"]].append(sample)
    rows = {}
    for task in groups[0].keys() | groups[1].keys():
        left, right = groups[0].get(task, []), groups[1].get(task, [])
        row: dict[str, Any] = {
            "reason": "仅两侧各有一个逻辑样本时计算配对差值",
            "duration": None,
            "tokens": None,
        }
        if len(left) == len(right) == 1:
            for field, key, scale in [
                ("duration", "viewer_duration", 1000),
                ("tokens", "viewer_tokens", 1),
            ]:
                a, b = left[0].get(key), right[0].get(key)
                if numeric(a) and numeric(b):
                    row[field] = {
                        "before": a / scale,
                        "after": b / scale,
                        "delta": (b - a) / scale,
                        "percent": (b - a) / a * 100 if a else None,
                    }
            row["reason"] = "B − A；只描述这两个已观察样本，不证明能力或效率变化"
        rows[task] = row
    return {
        "rows": rows,
        "coverage": dict(
            Counter(k for r in rows.values() for k in ["duration", "tokens"] if r[k] is not None)
        ),
        "shared": len(groups[0].keys() & groups[1].keys()),
    }
