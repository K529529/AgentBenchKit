"""Judge results are ancillary, refreshable and never mutate official evidence."""

import json
from pathlib import Path

from fastapi.testclient import TestClient
from test_viewer_workbench import fixture, hashes

from agentbenchkit.viewer.app import create_app


def test_external_judge_refresh_identity_references_and_missing_scores(tmp_path: Path) -> None:
    root, external = tmp_path / "runs", tmp_path / "judge"
    run, folder = fixture(root)
    for name in ("metadata", "results"):
        (external / name).mkdir(parents=True)
    identity = {
        "run_id": "fixture",
        "task_id": "preview-repo--task-01",
        "execution_id": "execution-1",
    }
    (external / "metadata/execution-1.json").write_text(
        json.dumps({**identity, "status": "PENDING"})
    )
    original = hashes(root)
    url = "/runs/fixture/samples/sample-01"
    with TestClient(create_app(root, judge_root=external)) as client:
        pending = client.get(url)
        assert pending.status_code == 200 and "等待中" in pending.text
        ref = "runs/fixture/" + (folder / "patch.diff").relative_to(run).as_posix()
        result = {
            **identity,
            "status": "JUDGED",
            "model_returned": "judge-model",
            "rubric_version": "quality-v1",
            "scores": {
                "dimensions": [
                    {
                        "dimension": "test_quality",
                        "score": 0,
                        "reason": "Observed zero",
                        "evidence_refs": [ref, "../../outside.json"],
                    },
                    {"dimension": "efficiency", "score": None, "reason": "Not observable"},
                ]
            },
        }
        (external / "results/execution-1.json").write_text(json.dumps(result))
        judged = client.get(url)
        assert "judge-model" in judged.text and "Observed zero" in judged.text
        assert "Not observable" in judged.text and "缺失、越界" in judged.text
        assert "path=tasks%2Fpreview-repo--task-01%2Fsample-01%2Fpatch.diff" in judged.text
        assert "等待中" not in judged.text
        assert "JUDGED" in client.get("/runs/fixture").text
        result["execution_id"] = "wrong-execution"
        (external / "results/execution-1.json").write_text(json.dumps(result))
        assert "judge-model" not in client.get(url).text
        (external / "results/execution-1.json").write_text('{"status":')
        assert client.get(url).status_code == 200
    assert hashes(root) == original


def test_native_judge_error_and_no_results(tmp_path: Path) -> None:
    run, _ = fixture(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        assert "尚无可读取的 Judge 结果" in client.get("/runs/fixture/samples/sample-01").text
        (run / "judge").mkdir()
        (run / "judge/native.json").write_text(
            json.dumps(
                {
                    "run_id": "fixture",
                    "sample_id": "sample-01",
                    "judge_status": "ERROR",
                    "model": "native-model",
                    "error": "Schema mismatch <script>alert(1)</script>",
                    "rubric_scores": None,
                }
            )
        )
        page = client.get("/runs/fixture/samples/sample-01")
        assert page.status_code == 200 and "Judge 未成功完成" in page.text
        assert "native-model" in page.text and "&lt;script&gt;" in page.text


def test_large_failure_list_is_server_paginated(tmp_path: Path) -> None:
    _, folder = fixture(tmp_path)
    path = folder / "verifier.json"
    record = json.loads(path.read_text())
    record["checks"]["official_report"]["tests_status"]["FAIL_TO_PASS"]["failure"] = [
        f"tests/test_long.py::test_case_{i:03d}" for i in range(291)
    ]
    path.write_text(json.dumps(record))
    with TestClient(create_app(tmp_path)) as client:
        url = "/runs/fixture/samples/sample-01"
        page = client.get(url)
        assert page.status_code == 200
        assert "第 1 / 30 页" in page.text and "test_case_009" in page.text
        assert (
            '<summary><span class="badge FAIL">FAIL</span> tests/test_long.py::test_case_010'
            not in page.text
        )
        last = client.get(url, params={"f2p_page": 30})
        assert "test_case_290" in last.text and "第 30 / 30 页" in last.text
        search = client.get(url, params={"f2p_page": 30, "f2p_q": "case_290"})
        assert "1 条匹配" in search.text and "第 1 / 1 页" in search.text
        assert "没有匹配的失败测试" in client.get(url, params={"f2p_q": "no-match"}).text


def test_collection_never_counts_duplicate_samples_as_final_results(tmp_path: Path) -> None:
    from test_viewer_dashboard import write_dashboard_fixture

    from agentbenchkit.viewer.presentation import collection_view

    write_dashboard_fixture(tmp_path, "first", "Pi", task_count=2)
    write_dashboard_fixture(tmp_path, "resumed", "Pi", task_count=1)
    result = collection_view([tmp_path])
    assert result["planned"] == 2 and result["ambiguous"] == 1 and result["recorded"] == 1
    with TestClient(create_app(tmp_path, collection_title="Explicit batch")) as client:
        page = client.get("/")
        assert "Explicit batch" in page.text and "已排除" in page.text


def test_collection_judge_scope_and_snapshot_notice(tmp_path: Path) -> None:
    from agentbenchkit.viewer.judges import sync_info

    run, _ = fixture(tmp_path / "runs")
    external = tmp_path / "external"
    external.mkdir()
    (external / "viewer-sync.json").write_text(
        json.dumps({"synced_at": "2026-11-09T01:00:00+00:00"})
    )
    assert sync_info(external) == "2026-11-09 09:00:00 UTC+8"
    (run / "judge").mkdir()
    (run / "judge/one.json").write_text(
        json.dumps(
            {
                "run_id": "fixture",
                "sample_id": "sample-01",
                "judge_status": "COMPLETED",
            }
        )
    )
    with TestClient(
        create_app(tmp_path / "runs", judge_root=external, collection_title="Fixed batch")
    ) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "整批 Judge 覆盖 · 50 题" in home.text
        assert "已评分 <b>1</b>" in home.text and "尚无记录 <b>49</b>" in home.text
        assert "2026-11-09 09:00:00 UTC+8" in home.text
        run_page = client.get("/runs/fixture")
        assert "本 Run 的 Judge 覆盖 · 50 题" in run_page.text
        assert "查看整批任务与 Judge 汇总" in run_page.text
        assert "不会同步云端" in run_page.text


def test_continued_run_fills_missing_rows_without_rewriting_statistics(tmp_path: Path) -> None:
    from test_viewer_dashboard import write_dashboard_fixture
    from test_viewer_workbench import hashes

    first = write_dashboard_fixture(tmp_path, "first", "Pi", task_count=2)
    write_dashboard_fixture(tmp_path, "resumed", "Pi", task_count=1)
    missing = next(first.glob("tasks/*/sample-01/sample.json"))
    missing.unlink()
    before = hashes(tmp_path)
    with TestClient(create_app(tmp_path, collection_title="Batch")) as client:
        page = client.get("/runs/first")
        assert page.status_code == 200
        assert "整批评测：2 / 2 题已有结果" in page.text
        assert "<small>仍无结果任务</small><strong>0</strong>" in page.text
        assert "<small>已在续跑完成</small><strong>1</strong>" in page.text
        assert "/runs/resumed/samples/sample-01" in page.text
        assert 'data-execution="NO_RESULT"' not in page.text
        assert page.text.count("data-result-row") == 2
        assert "本 Run 的 Judge 覆盖 · 1 题" in page.text
    with TestClient(create_app(tmp_path)) as client:
        page = client.get("/runs/first")
        assert 'data-execution="NO_RESULT"' in page.text
        assert "续跑结果 ·" not in page.text
    assert hashes(tmp_path) == before
