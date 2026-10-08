"""Synthetic read-only presentation checks; never model evaluation evidence."""

import json
import re
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from agentbenchkit.core.metrics import summarize
from agentbenchkit.core.models import SampleResult
from agentbenchkit.viewer.app import create_app


def write_dashboard_fixture(root: Path, run_id: str, agent: str, offset: int = 0) -> Path:
    directory = root / run_id
    directory.mkdir(parents=True, exist_ok=True)
    tasks = [
        {"task_id": f"preview-repo--task-{i:02}", "prompt": "Synthetic UI fixture"}
        for i in range(1, 17)
    ]
    manifest: dict[str, Any] = {
        "preview_notice": "布局预览 · 合成数据，不是 16×2 实验结果",
        "created_at": "2026-10-08T10:00:00Z",
        "benchmark": "featurebench-v1.1-fast",
        "harness": {"name": agent, "capabilities": {}},
        "environment": {"provider": "docker"},
        "model": {"model_id": "preview-model"},
        "tasks": tasks,
        "samples_per_task": 1,
        "concurrency": 1,
        "k": 1,
    }
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    samples = []
    for i, task in enumerate(tasks):
        # Includes PASS candidate + failed E2E, test failure and unknown verification.
        sample = SampleResult.model_validate(
            {
                "sample_id": f"sample-{i + 1:02}",
                "task_id": task["task_id"],
                "execution_status": "FINISHED",
                "agent_outcome": "LIMITED" if i == 0 else "COMPLETED",
                "candidate_frozen": True,
                "verifier_status": (
                    ["PASS", "PASS", "FAIL", "NOT_RUN"]
                    if not offset
                    else ["PASS", "PASS", "PASS", "FAIL"]
                )[(i + offset) % 4],
            }
        )
        samples.append(sample)
        folder = directory / "tasks" / task["task_id"] / sample.sample_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "sample.json").write_text(
            json.dumps(
                {
                    **sample.model_dump(mode="json"),
                    "candidate_pass": sample.candidate_pass,
                    "sample_success": sample.sample_success,
                }
            ),
            encoding="utf-8",
        )
    (directory / "summary.json").write_text(summarize(samples).model_dump_json(), encoding="utf-8")
    return directory


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_dashboard_all_tasks_comparison_and_readonly(tmp_path: Path) -> None:
    write_dashboard_fixture(tmp_path, "preview-a", "Nexus <script>")
    write_dashboard_fixture(tmp_path, "preview-b", "Qoder CN", 1)
    before = snapshot(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        overview = client.get("/runs/preview-a")
        comparison = client.get("/compare?baseline=preview-a&candidate=preview-b")
        assert overview.status_code == comparison.status_code == 200
        assert overview.text.count("data-result-row") == 16
        assert comparison.text.count("data-result-row") == 16
        assert overview.text.count('class="task-tile"') == 16
        assert 'data-filter="unknown"' in overview.text
        assert 'src="/static/viewer.js"' in overview.text
        assert client.get("/static/viewer.js").status_code == 200
        assert "Nexus &lt;script&gt;" in comparison.text
        assert "Nexus <script>" not in comparison.text
        for i in range(1, 17):
            assert f"preview-repo--task-{i:02}" in overview.text
            assert f"preview-repo--task-{i:02}" in comparison.text
        # Preserve the independent dimensions instead of collapsing them into one verdict.
        first = re.search(r'<tr id="task-1".*?</tr>', overview.text, re.S)
        assert first is not None
        assert 'class="badge PASS">PASS' in first[0]
        assert 'class="badge FAIL">FAIL' in first[0]
        assert "N/A" in overview.text
        assert "可比性受限" in comparison.text
        assert "missing typed model" not in comparison.text
        assert "unspecified controls" in comparison.text
        assert "合成数据" in client.get("/runs/preview-b").text
        assert "合成预览" in client.get("/").text
    assert snapshot(tmp_path) == before


def test_dashboard_missing_results_and_planned_only_samples(tmp_path: Path) -> None:
    directory = write_dashboard_fixture(tmp_path, "preview-a", "Nexus")
    for path in directory.glob("tasks/*/*/sample.json"):
        path.unlink()
    (directory / "summary.json").unlink()
    planned = [
        {
            "sample_id": f"sample-{i:02}",
            "task_id": f"preview-repo--task-{i:02}",
            "execution_status": "PENDING",
        }
        for i in range(1, 17)
    ]
    (directory / "plan.json").write_text(json.dumps(planned), encoding="utf-8")
    before = snapshot(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        page = client.get("/runs/preview-a")
        assert page.status_code == 200
        assert page.text.count("N/A · 尚无样本结果") == 16
        assert page.text.count('class="meter-unavailable"') == 4
        compare = client.get("/compare?baseline=preview-a&candidate=preview-a")
        assert compare.status_code == 200
        assert compare.text.count("data-result-row") == 16
        assert 'href="/runs/preview-a/samples/' not in compare.text
        assert 'class="badge UNKNOWN">N/A' in compare.text
    assert snapshot(tmp_path) == before
