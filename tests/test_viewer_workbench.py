"""Synthetic UI contract fixtures; these are not real-agent acceptance."""

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_viewer_dashboard import write_dashboard_fixture

from agentbenchkit.viewer.app import create_app
from agentbenchkit.viewer.presentation import diff_rows, exception_summary, sample_view


def fixture(root: Path) -> tuple[Path, Path]:
    run = write_dashboard_fixture(root, "fixture", "Pi", task_count=50)
    folder = run / "tasks/preview-repo--task-01/sample-01"
    execution = folder / "executions/execution-1"
    execution.mkdir(parents=True)
    (execution / "execution.json").write_text(
        json.dumps(
            {
                "physical_execution_id": "execution-1",
                "started_at": "2026-01-01",
                "process": {"duration_ms": 1500, "output_truncated": False},
            }
        )
    )
    trajectory = execution / "trajectory.jsonl"
    values = [
        {
            "type": "tool_call_started",
            "native_call_id": "call-1",
            "seq": 1,
            "attributes": {
                "native": {
                    "data": {"name": "apply_patch", "step": 50, "arguments": "src/a.py"},
                    "pi": {},
                }
            },
        },
        {
            "type": "tool_call_finished",
            "native_call_id": "call-1",
            "seq": 2,
            "attributes": {
                "native": {
                    "data": {"is_error": True},
                    "pi": {"result": {"content": [{"text": "failure <script>"}]}},
                }
            },
        },
        {
            "type": "agent_finished",
            "seq": 3,
            "attributes": {
                "native": {
                    "data": {
                        "steps": 50,
                        "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
                    }
                }
            },
        },
    ]
    trajectory.write_text("".join(json.dumps(v) + "\n" for v in values))
    (folder / "verifier.json").write_text(
        json.dumps(
            {
                "status": "FAIL",
                "stdout_ref": "verify/missing.log",
                "checks": {
                    "official_report": {
                        "patch_exists": True,
                        "patch_successfully_applied": True,
                        "resolved": False,
                        "tests_status": {
                            "FAIL_TO_PASS": {"success": [], "failure": ["tests/test_a.py"]}
                        },
                    }
                },
            }
        )
    )
    logs = folder / "verify"
    logs.mkdir()
    (logs / "test_output.txt").write_text(
        "tests/test_a.py:10: in <module>\nsrc/a.py:367: in <module>\nE   NameError: name missing\n"
        "<script>alert(1)</script>\n"
    )
    (folder / "patch.diff").write_text(
        "diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n"
        "@@ -366,2 +366,2 @@\n same\n-old\n+new\n"
        "diff --git a/b.py b/b.py\n--- a/b.py\n+++ b/b.py\n@@ -1 +1 @@\n-a\n+b\n"
    )
    return run, folder


def hashes(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def test_diagnostic_chain_and_immutable_evidence(tmp_path: Path) -> None:
    run, folder = fixture(tmp_path)
    before = hashes(run)
    with TestClient(create_app(tmp_path)) as client:
        page = client.get("/runs/fixture/samples/sample-01")
        assert page.status_code == 200
        assert "NameError" in page.text and "367" in page.text
        assert "UNAVAILABLE" in page.text  # no invented RCA
        assert "<script>alert(1)</script>" not in page.text
        rel = (folder / "patch.diff").relative_to(run).as_posix()
        patch = client.get(
            "/runs/fixture/evidence", params={"path": rel, "file": "src/a.py", "line": 367}
        )
        assert patch.status_code == 200 and "target-line" in patch.text
        trajectory = (
            (folder / "executions/execution-1/trajectory.jsonl").relative_to(run).as_posix()
        )
        timeline = client.get(
            "/runs/fixture/evidence", params={"path": trajectory, "call": "call-1"}
        )
        assert "Step 50" in timeline.text and "tool_call_finished" in timeline.text
        assert "agent_finished</span>" not in timeline.text
        result = client.get(
            "/runs/fixture/samples/sample-01/file-events", params={"file": "src/a.py"}
        )
        assert result.status_code == 200 and "Step 50" in result.text
        matrix = client.get("/runs/fixture")
        assert matrix.status_code == 200 and matrix.text.count("data-result-row") == 50
        assert "data-matrix-sort" in matrix.text
    assert hashes(run) == before


@pytest.mark.parametrize(
    "bad",
    [
        "../secret.json",
        "tasks/../../secret.json",
        "/etc/passwd",
        "C:/secret.json",
        "tasks/x:stream.json",
        "tasks/x/work/a.json",
        "tasks\\..\\secret.json",
    ],
)
def test_all_artifact_routes_share_path_boundary(tmp_path: Path, bad: str) -> None:
    fixture(tmp_path)
    with TestClient(create_app(tmp_path)) as c:
        for route in ["artifact", "evidence", "download"]:
            assert c.get(f"/runs/fixture/{route}", params={"path": bad}).status_code == 404


def test_streaming_page_search_and_truncated_events(tmp_path: Path) -> None:
    run, folder = fixture(tmp_path)
    path = folder / "executions/execution-1/trajectory.jsonl"
    with path.open("a") as stream:
        for i in range(4, 150):
            stream.write(
                json.dumps(
                    {"type": "message", "seq": i, "content": "needle" if i == 148 else "x" * 10000}
                )
                + "\n"
            )
        stream.write("{unfinished")
    with TestClient(create_app(tmp_path)) as c:
        rel = path.relative_to(run).as_posix()
        page = c.get("/runs/fixture/evidence", params={"path": rel})
        assert page.status_code == 200 and 0 < page.text.count('class="timeline-event') <= 60
        assert len(page.content) < 1_000_000
        found = c.get("/runs/fixture/evidence", params={"path": rel, "q": "needle"})
        assert "148" in found.text and "needle" in found.text
        broken = c.get("/runs/fixture/evidence", params={"path": rel, "kind": "failure"})
        assert "unparsed" in broken.text
    assert sample_view(run, folder / "sample.json")["metrics"]["trajectory_complete"] is False


def test_missing_usage_not_zero_and_partial_writes(tmp_path: Path) -> None:
    run, folder = fixture(tmp_path)
    trajectory = folder / "executions/execution-1/trajectory.jsonl"
    trajectory.write_text("{partial")
    result = sample_view(run, folder / "sample.json")
    assert result["metrics"]["total_tokens"] is None
    assert result["groups"][1]["failed"] is None
    (folder / "verifier.json").write_text("{partial")
    with TestClient(create_app(tmp_path)) as c:
        assert c.get("/runs/fixture/samples/sample-01").status_code == 200
        (run / "summary.json").write_text("{partial")
        assert c.get("/runs/fixture").status_code == 200
        (folder / "sample.json").write_text("{partial")
        assert c.get("/runs/fixture").status_code == 200
        assert c.get("/runs/fixture/samples/sample-01").status_code == 503


def test_exception_requires_structural_evidence_and_diff_line_numbers(tmp_path: Path) -> None:
    run, folder = fixture(tmp_path)
    log = folder / "verify/test_output.txt"
    exceptions = exception_summary(log)
    assert exceptions[0]["location"]["file"] == "src/a.py"
    assert exceptions[0]["location"]["line"] == 367
    log.write_text("We might have a NameError in this task.\n")
    assert exception_summary(log) == []
    rows = list(diff_rows(folder / "patch.diff"))
    assert next(r for r in rows if r["text"] == "+new")["new"] == 367
    assert next(r for r in rows if r["text"] == "+b")["new"] == 1


def test_library_pagination_and_record_navigation(tmp_path: Path) -> None:
    for i in range(19):
        write_dashboard_fixture(tmp_path, f"run-{i:02}", "Pi", task_count=1)
    with TestClient(create_app(tmp_path)) as c:
        first = c.get("/")
        second = c.get("/?page=2")
        assert first.status_code == second.status_code == 200
        assert "run-00" not in first.text and "run-00" in second.text
        result = c.get("/?q=run-00")
        assert "run-00" in result.text and "run-18" not in result.text
        record = c.get("/runs/run-00/evidence", params={"path": "manifest.json"})
        assert record.status_code == 200 and "STRUCTURED EVIDENCE" in record.text
        nested = c.get(
            "/runs/run-00/evidence", params={"path": "manifest.json", "node": "/tasks/0"}
        )
        assert nested.status_code == 200 and "Synthetic UI fixture" in nested.text
        invalid = c.get("/runs/run-00/evidence", params={"path": "manifest.json", "node": "/nope"})
        assert invalid.status_code == 404


def test_explicit_multiple_roots_do_not_need_symlinks(tmp_path: Path) -> None:
    a, b = tmp_path / "formal", tmp_path / "pilot"
    write_dashboard_fixture(a, "formal-50", "Pi", task_count=50)
    write_dashboard_fixture(b, "pilot", "Pi", task_count=2)
    with TestClient(create_app(a, (b,))) as c:
        assert c.get("/runs/pilot").status_code == 200
        assert c.get("/runs/formal-50").status_code == 200
        assert "pilot" in c.get("/").text


def test_custom_log_refs_and_evidence_directory(tmp_path: Path) -> None:
    run, folder = fixture(tmp_path)
    custom = folder / "verify/custom-output.txt"
    custom.write_text("src/a.py:7: in <module>\nE   ValueError: custom verifier output\n")
    report = json.loads((folder / "verifier.json").read_text())
    report["stdout_ref"] = "verify/custom-output.txt"
    (folder / "verifier.json").write_text(json.dumps(report))
    from agentbenchkit.viewer.presentation import event_view

    assert event_view(1, {"type": "message", "attributes": None})["type"] == "message"
    assert event_view(1, {"type": "message", "duration_ms": 0})["duration"] == 0
    data = sample_view(run, folder / "sample.json")
    assert any(e["type"] == "ValueError" for e in data["exceptions"])
    with TestClient(create_app(tmp_path)) as client:
        page = client.get("/runs/fixture/samples/sample-01/files?q=custom-output")
        assert page.status_code == 200 and "custom-output.txt" in page.text
        sample = client.get("/runs/fixture/samples/sample-01")
        assert "custom-output.txt" in sample.text


def test_native_step_seq_and_repeated_call_results(tmp_path: Path) -> None:
    run, folder = fixture(tmp_path)
    trajectory = folder / "executions/execution-1/trajectory.jsonl"
    entries = [json.loads(line) for line in trajectory.read_text().splitlines()]
    duplicate = {**entries[0], "seq": 40, "native_call_id": "call-without-result"}
    entries.insert(2, duplicate)
    trajectory.write_text("".join(json.dumps(e) + "\n" for e in entries))
    repeated = sample_view(run, folder / "sample.json")["repeats"][0]
    assert repeated["calls"][0]["results"][0]["failure"] is True
    assert repeated["calls"][1]["results"] == []
    rel = trajectory.relative_to(run).as_posix()
    with TestClient(create_app(tmp_path)) as client:
        step = client.get("/runs/fixture/evidence", params={"path": rel, "step": "50"})
        assert step.status_code == 200 and step.text.count('class="timeline-event') == 2
        seq = client.get("/runs/fixture/evidence", params={"path": rel, "seq": "40"})
        assert seq.status_code == 200 and seq.text.count('class="timeline-event') == 1
        assert "call-without-result" in seq.text
        missing = client.get("/runs/fixture/evidence", params={"path": rel, "step": "999"})
        assert "没有匹配的事件" in missing.text
        sample = client.get("/runs/fixture/samples/sample-01")
        assert "关联结果" in sample.text and "缺少明确 Call ID" in sample.text


def test_navigation_errors_are_readable_and_transitional_states_filterable(tmp_path: Path) -> None:
    fixture(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        for url, status in [("/?page=wrong", 422), ("/no-such-page", 404)]:
            response = client.get(url)
            assert response.status_code == status
            assert response.headers["content-type"].startswith("text/html")
            assert "返回评测工作台" in response.text
        run = client.get("/runs/fixture")
        assert 'value="PREPARING"' in run.text and 'value="COLLECTING"' in run.text
        assert "data-filter-reset" in run.text


def test_filtered_reader_backtracking_and_long_text_progress(tmp_path: Path) -> None:
    run, folder = fixture(tmp_path)
    log = folder / "verify/test_output.txt"
    log.write_text("".join(f"{'match' if i % 2 else 'skip'} {i}\n" for i in range(1, 301)))
    with TestClient(create_app(tmp_path)) as client:
        first = client.get(
            "/runs/fixture/evidence", params={"path": log.relative_to(run).as_posix(), "q": "match"}
        )
        next_link = re.search(r'href="([^"]+)"[^>]*>下一页', first.text)
        assert next_link is not None
        second = client.get(html.unescape(next_link[1]))
        back = re.search(r'href="([^"]+)"[^>]*>← 上一页', second.text)
        assert back is not None and "q=match" in back[1]
        previous = client.get(html.unescape(back[1]))
        assert 'id="L1"' in previous.text and 'id="L119"' in previous.text
        assert 'id="L121"' not in previous.text
        record = folder / "large.json"
        record.write_text(json.dumps({"body": "x" * 45000}))
        text = client.get(
            "/runs/fixture/evidence",
            params={
                "path": record.relative_to(run).as_posix(),
                "node": "/body",
                "text_offset": 20000,
            },
        )
        assert text.status_code == 200 and "20001–40000" in text.text
        assert "上一段文本" in text.text and "45000" in text.text
        beyond = client.get(
            "/runs/fixture/evidence",
            params={
                "path": record.relative_to(run).as_posix(),
                "node": "/body",
                "text_offset": 999999,
                "start": 999999,
            },
        )
        assert beyond.status_code == 200 and "40001–45000" in beyond.text
        assert "当前从第 1 项开始" in beyond.text


def test_compare_uses_recorded_process_duration_and_safe_default_pair(tmp_path: Path) -> None:
    primary, secondary = tmp_path / "primary", tmp_path / "secondary"
    fixture(primary)
    write_dashboard_fixture(primary, "fixture-b", "Pi", task_count=50)
    write_dashboard_fixture(secondary, "zz-other-source", "Pi", task_count=1)
    before = hashes(tmp_path)
    with TestClient(create_app(primary, (secondary,))) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert 'required value="fixture-b"' in home.text
        assert 'required value="fixture"' in home.text
        comparison = client.get("/compare?baseline=fixture&candidate=fixture-b")
        assert comparison.status_code == 200
        assert "1.5s · 工具 N/A" in comparison.text
        assert "耗时 N/A · 工具 N/A" in comparison.text
        assert "0.0s" not in comparison.text
        missing = client.get("/runs/fixture/samples/sample-02")
        assert "合成数据，不代表实际评测结果" in missing.text
        assert "未收集可读取的验证日志" in missing.text
        assert "使用下方日志阅读器" not in missing.text
    assert hashes(tmp_path) == before


def test_pi_native_duration_and_missing_event_are_readable(tmp_path: Path) -> None:
    from agentbenchkit.viewer.presentation import event_view

    native = {"pi": {"durationMs": 4824, "toolName": "bash"}}
    event: dict[str, Any] = {
        "type": "tool_call_finished", "duration_ms": None, "attributes": {"native": native}
    }
    assert event_view(12, event)["duration"] == 4824
    event["duration_ms"] = 0
    assert event_view(12, event)["duration"] == 0
    event["duration_ms"] = -1
    native["pi"]["durationMs"] = True
    assert event_view(12, event)["duration"] is None
    archive = {"attributes": {"native": {"pi": {"type": "abk_native_archive"}}}}
    assert "压缩归档" in event_view(7, archive)["summary"]
    run, folder = fixture(tmp_path)
    path = (folder / "executions/execution-1/trajectory.jsonl").relative_to(run).as_posix()
    with TestClient(create_app(tmp_path)) as client:
        missing = client.get("/runs/fixture/evidence", params={"path": path, "event": 999999})
        assert missing.status_code == 404
        assert "事件不存在或尚未落盘" in missing.text
        sample = client.get("/runs/fixture/samples/sample-01")
        assert "02 验证结果" in sample.text
        assert "官方验证与测试结果" in sample.text
