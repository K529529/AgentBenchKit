"""Synthetic UI contract fixtures; these are not real-agent acceptance."""

import hashlib
import json
from pathlib import Path

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
