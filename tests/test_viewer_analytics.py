"""Presentation statistics only; synthetic data is not agent acceptance."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_viewer_dashboard import snapshot, write_dashboard_fixture

from agentbenchkit.viewer.analytics import distribution, paired_metrics
from agentbenchkit.viewer.app import create_app
from agentbenchkit.viewer.presentation import diff_rows, run_view


def test_distribution_coverage_and_outliers() -> None:
    samples = [
        dict(task_id=str(i), sample_id=str(i), value=v) for i, v in enumerate([0, 1, 1, 1, 100])
    ]
    result = distribution(samples, "value", "Duration", "s")
    assert result["median"] == 1
    assert result["p90"] == pytest.approx(60.4)
    assert sum(b["count"] for b in result["bins"]) == 5
    assert [p["value"] for p in result["outliers"]] == [100]
    assert result["ranking"][0]["sample"] == "4"
    for invalid in (None, True, -1, float("nan"), float("inf"), "1"):
        partial = distribution(
            samples + [dict(task_id="missing", sample_id="missing", value=invalid)],
            "value",
            "Duration",
            "s",
        )
        assert partial["known"] == 5 and partial["total"] == 6
        assert not partial["bins"] and not partial["complete"]
    assert distribution([], "value", "Duration", "s")["median"] is None
    constant = distribution(
        [dict(task_id="x", sample_id="x", value=0)] * 4, "value", "Duration", "s"
    )
    assert constant["bins"] == [dict(low=0, high=0, count=4)]


def test_paired_metrics_require_unique_known_samples() -> None:
    a = [dict(task_id="x", viewer_duration=0, viewer_tokens=100)]
    b = [dict(task_id="x", viewer_duration=2000, viewer_tokens=50)]
    result = paired_metrics(a, b)
    assert result["rows"]["x"]["duration"]["delta"] == 2
    assert result["rows"]["x"]["duration"]["percent"] is None
    assert result["rows"]["x"]["tokens"]["percent"] == -50
    assert paired_metrics(a * 2, b)["coverage"] == {}
    assert paired_metrics(a, [dict(task_id="x", viewer_tokens=None)])["coverage"] == {}
    assert paired_metrics(a, [dict(task_id="other")])["shared"] == 0


def test_overview_null_native_partial_trace_and_readonly_compare(tmp_path: Path) -> None:
    run = write_dashboard_fixture(tmp_path, "a", "Pi", task_count=1)
    write_dashboard_fixture(tmp_path, "b", "Pi", task_count=1)
    folder = run / "tasks/preview-repo--task-01/sample-01"
    execution = folder / "executions/e"
    execution.mkdir(parents=True)
    (execution / "execution.json").write_text(
        json.dumps(dict(physical_execution_id="e", process=dict(duration_ms=0)))
    )
    trajectory = execution / "trajectory.jsonl"
    trajectory.write_text('{"type":"agent_finished","attributes":{"native":null}}\n')
    records = [json.loads((folder / "sample.json").read_text())]
    run_view(run, records, {})
    assert records[0]["viewer_duration"] == 0
    assert records[0]["viewer_tokens"] is None
    trajectory.write_text("{partial")
    run_view(run, records, {})
    assert any("结束事件" in note for note in records[0]["viewer_investigate"])
    before = snapshot(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        overview = client.get("/runs/a")
        assert overview.status_code == 200 and "指标分布" in overview.text
        comparison = client.get("/compare?baseline=a&candidate=b")
        assert comparison.status_code == 200 and "配对差值" in comparison.text
        assert 'data-filter="REGRESSED"' in comparison.text
        assert "N/A · 缺失或非一对一样本" in comparison.text
    assert snapshot(tmp_path) == before


def test_deleted_and_quoted_diff_file_keeps_real_filename(tmp_path: Path) -> None:
    patch = tmp_path / "patch.diff"
    patch.write_text(
        'diff --git a/gone.py b/gone.py\n--- a/gone.py\n+++ /dev/null\n'
        '@@ -1 +0,0 @@\n-gone\ndiff --git "a/has space.py" "b/has space.py"\n'
        '--- "a/has space.py"\n+++ "b/has space.py"\n@@ -1 +1 @@\n-old\n+new\n'
    )
    rows = list(diff_rows(patch))
    assert next(row for row in rows if row["text"] == "-gone")["file"] == "gone.py"
    changed = next(row for row in rows if row["text"] == "+new")
    assert changed["file"] == "has space.py" and changed["new"] == 1
