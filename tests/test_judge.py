import json
from pathlib import Path
from typing import Any

import pytest
from test_runtime import ControlledHarness

from agentbenchkit.analysis.judge import DIMENSIONS, judge_sample, unavailable_scores
from agentbenchkit.analysis.replay import evidence_hash, replay
from agentbenchkit.benchmarks.micro_swe import load_tasks
from agentbenchkit.runtime.runner import evaluate


async def test_judge_failure_and_replay_preserve_correctness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = await evaluate(load_tasks(("clamp",)), ControlledHarness(True), tmp_path)
    sample = next(directory.glob("tasks/*/*/sample.json"))
    original = sample.read_bytes()
    before = evidence_hash(directory)
    monkeypatch.setenv("TEST_JUDGE_KEY", "synthetic-judge-secret")

    def broken(*args: Any) -> dict[str, Any]:
        raise RuntimeError("synthetic-judge-secret unavailable")

    failed = judge_sample(
        tmp_path,
        directory.name,
        sample.parent.name,
        "test",
        "https://example.invalid/v1",
        "TEST_JUDGE_KEY",
        broken,
    )
    data = json.loads(failed.read_text())
    assert data["judge_status"] == "ERROR"
    assert "synthetic-judge-secret" not in failed.read_text()

    def good(*args: Any) -> dict[str, Any]:
        return {
            "scores": {
                "dimensions": [
                    {
                        "dimension": name,
                        "score": 2,
                        "reason": "test fixture",
                        "evidence_refs": [next(iter(args[3]["artifacts"]))],
                    }
                    for name in DIMENSIONS
                ]
            },
            "usage": {"input_tokens": 3},
        }

    passed = judge_sample(
        tmp_path,
        directory.name,
        sample.parent.name,
        "test",
        "https://example.invalid/v1",
        "TEST_JUDGE_KEY",
        good,
    )
    assert passed != failed and failed.exists()
    assert json.loads(passed.read_text())["judge_status"] == "COMPLETED"
    replay(tmp_path, directory.name)
    assert failed.exists() and passed.exists()
    assert sample.read_bytes() == original and evidence_hash(directory) == before
    assert json.loads(original)["sample_success"] is True
    assert all(item["score"] is None for item in unavailable_scores()["dimensions"])


def test_judge_http_worker_and_deadline() -> None:
    import subprocess
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from agentbenchkit.analysis.judge import call_judge

    requests = []
    slow = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, self.headers["Authorization"], body["model"]))
            if slow.is_set():
                time.sleep(3)
                return
            result = json.dumps(
                {
                    "choices": [{"message": {"content": '{"dimensions":[]}'}}],
                    "usage": {"input_tokens": 5},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(result)))
            self.end_headers()
            self.wfile.write(result)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True)
    thread.start()
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/v1"
        result = call_judge(endpoint, "test-key", "test-model", {}, 5)
        assert result["usage"]["input_tokens"] == 5
        assert requests == [("/v1/chat/completions", "Bearer test-key", "test-model")]
        slow.set()
        start = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired):
            call_judge(endpoint, "test-key", "test-model", {}, 0.5)
        assert time.monotonic() - start < 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
