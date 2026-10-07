"""Provider failures remain safe diagnostics, never correctness decisions."""

import io
import json
import threading
import urllib.error
from collections.abc import Iterator
from email.message import Message
from http.client import IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from test_runtime import ControlledHarness
from typer.testing import CliRunner

from agentbenchkit.analysis.judge import DIMENSIONS, call_judge, judge_sample
from agentbenchkit.analysis.judge_diagnostics import (
    MAX_DIAGNOSTIC_BYTES,
    MAX_MESSAGE,
    JudgeFailure,
    safe_error,
    safe_text,
    sanitize_diagnostic,
)
from agentbenchkit.benchmarks.micro_swe import load_tasks
from agentbenchkit.cli import app
from agentbenchkit.runtime.runner import evaluate

SECRET = "synthetic-private-key"
PRIVATE = "private-response-must-not-be-displayed"
Server = tuple[str, list[dict[str, Any]], list[tuple[int, bytes]]]


@pytest.fixture
def provider() -> Iterator[Server]:
    requests: list[dict[str, Any]] = []
    replies: list[tuple[int, bytes]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            status, body = replies.pop(0)
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests, replies
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def completion(content: Any, finish: str = "stop") -> bytes:
    return json.dumps(
        {
            "choices": [
                {
                    "message": {"content": content, "reasoning_content": PRIVATE},
                    "finish_reason": finish,
                }
            ],
            "usage": {
                "completion_tokens": 2000,
                "completion_tokens_details": {"reasoning_tokens": 1999},
            },
        }
    ).encode()


def test_http_error_through_worker_is_redacted(provider: Server) -> None:
    endpoint, _, replies = provider
    replies.append(
        (
            400,
            json.dumps(
                {
                    "error": {
                        "message": (
                            f"Unsupported option; key={SECRET}; "
                            "Authorization: Bearer another-secret"
                        ),
                        "type": "invalid_request_error",
                        "code": "invalid_parameter",
                        "param": "response_format",
                        "request": PRIVATE,
                        "headers": {"Authorization": SECRET},
                    }
                }
            ).encode(),
        )
    )
    with pytest.raises(JudgeFailure) as caught:
        call_judge(endpoint, SECRET, "test", {}, 5)
    diagnostic = caught.value.diagnostic
    assert diagnostic["http_status"] == 400
    assert diagnostic["exception_type"] == "HTTPError"
    assert diagnostic["provider_code"] == "invalid_parameter"
    assert diagnostic["provider_param"] == "response_format"
    assert diagnostic["worker_exit_code"] == 1
    encoded = json.dumps(diagnostic)
    assert SECRET not in encoded and PRIVATE not in encoded and "another-secret" not in encoded
    assert len(encoded.encode()) <= MAX_DIAGNOSTIC_BYTES


@pytest.mark.parametrize("body", [b"<html>" + PRIVATE.encode(), b"x" * 8193])
def test_non_json_and_oversized_error_body_omitted(provider: Server, body: bytes) -> None:
    endpoint, _, replies = provider
    replies.append((502, body))
    with pytest.raises(JudgeFailure) as caught:
        call_judge(endpoint, SECRET, "test", {}, 5)
    assert caught.value.diagnostic["http_status"] == 502
    assert "omitted" in str(caught.value)
    assert PRIVATE not in str(caught.value)


@pytest.mark.parametrize(
    ("body", "exception_type"),
    [
        (completion(None, "length"), "OutputTruncated"),
        (completion('{"dimensions":[]}', "length"), "OutputTruncated"),
        (completion(""), "EmptyContent"),
        (completion(None), "EmptyContent"),
        (completion(PRIVATE), "JSONDecodeError"),
        (json.dumps({"choices": []}).encode(), "IndexError"),
        (json.dumps({"unexpected": PRIVATE}).encode(), "KeyError"),
        (PRIVATE.encode(), "JSONDecodeError"),
    ],
)
def test_response_errors_retain_status_without_content(
    provider: Server, body: bytes, exception_type: str
) -> None:
    endpoint, _, replies = provider
    replies.append((200, body))
    with pytest.raises(JudgeFailure) as caught:
        call_judge(endpoint, SECRET, "test", {}, 5)
    diagnostic = caught.value.diagnostic
    assert diagnostic["http_status"] == 200
    assert diagnostic["exception_type"] == exception_type
    assert PRIVATE not in json.dumps(diagnostic)
    if exception_type == "OutputTruncated":
        assert diagnostic["completion_tokens"] == 2000
        assert diagnostic["reasoning_tokens"] == 1999
        assert diagnostic["finish_reason"] == "length"


def test_explicit_request_settings_and_legacy_defaults(provider: Server) -> None:
    endpoint, requests, replies = provider
    for _ in range(2):
        replies.append((200, completion('{"dimensions":[]}')))
    call_judge(endpoint, SECRET, "test", {}, 5)
    result = call_judge(
        endpoint, SECRET, "test", {}, 5, max_completion_tokens=8192, reasoning_effort="low"
    )
    assert requests[0]["max_completion_tokens"] == 2000
    assert "reasoning_effort" not in requests[0]
    assert requests[1]["max_completion_tokens"] == 8192
    assert requests[1]["reasoning_effort"] == "low"
    assert requests[1]["response_format"] == {"type": "json_object"}
    assert "reasoning_content" not in json.dumps(result)


def test_diagnostic_bounds_and_redaction_before_truncation() -> None:
    text = "x" * (MAX_MESSAGE - 5) + SECRET
    assert safe_text(text, SECRET).endswith("[REDA")
    assert SECRET[:5] not in safe_text(text, SECRET)
    diagnostic = sanitize_diagnostic(
        {
            "message": "中" * 10000,
            "exception_type": "x" * 10000,
            "request_headers": {"Authorization": SECRET},
            "http_status": 500,
            "reasoning_tokens": 10**100,
            "content_chars": True,
        },
        SECRET,
    )
    assert len(diagnostic["message"]) == MAX_MESSAGE
    assert set(diagnostic) == {"message", "exception_type", "http_status"}
    assert len(json.dumps(diagnostic).encode()) < MAX_DIAGNOSTIC_BYTES


def test_incomplete_http_error_body_is_safe() -> None:
    class BrokenBody(io.BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            raise IncompleteRead(PRIVATE.encode())

    error = urllib.error.HTTPError("https://example.invalid", 503, "error", Message(), BrokenBody())
    diagnostic = safe_error(error, SECRET)
    assert diagnostic["http_status"] == 503
    assert "omitted" in diagnostic["message"]
    assert PRIVATE not in json.dumps(diagnostic)


async def test_cli_diagnostics_schema_failure_and_correctness_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider: Server
) -> None:
    directory = await evaluate(load_tasks(("clamp",)), ControlledHarness(True), tmp_path)
    original = {path: path.read_bytes() for path in directory.rglob("*") if path.is_file()}
    sample = next(directory.glob("tasks/*/*/sample.json"))
    endpoint, requests, replies = provider
    monkeypatch.setenv("TEST_JUDGE_KEY", SECRET)
    replies.append(
        (401, json.dumps({"error": {"message": f"Invalid credential {SECRET}"}}).encode())
    )
    cli = CliRunner().invoke(
        app,
        [
            "judge",
            directory.name,
            sample.parent.name,
            "--model",
            "test",
            "--endpoint",
            endpoint,
            "--key-env",
            "TEST_JUDGE_KEY",
            "--output",
            str(tmp_path),
            "--max-completion-tokens",
            "8192",
            "--reasoning-effort",
            "low",
        ],
    )
    assert cli.exit_code == 2
    assert "HTTPError" in cli.output and "401" in cli.output
    assert SECRET not in cli.output
    failed = next((directory / "judge").glob("*.json"))
    failed_bytes = failed.read_bytes()
    data = json.loads(failed_bytes)
    assert data["judge_status"] == "ERROR" and data["rubric_scores"] is None
    assert data["max_completion_tokens"] == requests[0]["max_completion_tokens"] == 8192
    assert data["reasoning_effort"] == "low"

    # A 200 response with invalid rubric must not persist Pydantic input/contexts.
    replies.append(
        (200, completion(json.dumps({"dimensions": [{"dimension": PRIVATE, "score": SECRET}]})))
    )
    invalid = judge_sample(
        tmp_path, directory.name, sample.parent.name, "test", endpoint, "TEST_JUDGE_KEY"
    )
    invalid_data = json.loads(invalid.read_bytes())
    assert invalid_data["error_details"]["exception_type"] == "ValidationError"
    assert invalid_data["error_details"]["phase"] == "rubric_validation"
    assert invalid_data["error_details"]["http_status"] == 200
    assert SECRET not in invalid.read_text() and PRIVATE not in invalid.read_text()

    # Success remains possible with unchanged four-dimensional rubric.
    replies.append(
        (
            200,
            completion(
                json.dumps(
                    {
                        "dimensions": [
                            {
                                "dimension": name,
                                "score": None,
                                "reason": "No evidence",
                                "evidence_refs": [],
                            }
                            for name in DIMENSIONS
                        ]
                    }
                )
            ),
        )
    )
    passed = judge_sample(
        tmp_path, directory.name, sample.parent.name, "test", endpoint, "TEST_JUDGE_KEY"
    )
    assert json.loads(passed.read_bytes())["judge_status"] == "COMPLETED"
    assert all(path.read_bytes() == before for path, before in original.items())
    assert failed.read_bytes() == failed_bytes
    verdict = json.loads(original[sample])
    assert verdict["verifier_status"] == "PASS"
    assert verdict["candidate_pass"] is True and verdict["sample_success"] is True


@pytest.mark.parametrize(
    "stdout",
    [SECRET.encode(), b'{"error":[]}', b"x" * 65537],
    ids=["non-json", "bad-envelope", "oversized"],
)
def test_invalid_worker_diagnostic_never_exposes_raw_output(
    monkeypatch: pytest.MonkeyPatch, stdout: bytes
) -> None:
    class Process:
        returncode = 1

        def communicate(self, *args: Any, **kwargs: Any) -> tuple[bytes, bytes]:
            return stdout, (SECRET + PRIVATE).encode()

    monkeypatch.setattr("agentbenchkit.analysis.judge.subprocess.Popen", lambda *a, **k: Process())
    with pytest.raises(JudgeFailure) as caught:
        call_judge("https://example.invalid/v1", SECRET, "test", {}, 5)
    assert caught.value.diagnostic["exception_type"] == "WorkerProcessError"
    assert SECRET not in str(caught.value) and PRIVATE not in str(caught.value)


def canonical_output() -> dict[str, Any]:
    return {
        "dimensions": [
            {
                "dimension": name,
                "score": 2,
                "reason": "Evidence supports the score.",
                "evidence_refs": ["candidate.diff"],
            }
            for name in DIMENSIONS
        ]
    }


def test_canonical_prompt_matches_strict_parser_and_framework_versions() -> None:
    from agentbenchkit.analysis.judge import JudgeOutput, judge_prompt, parse_judge_output

    prompt = judge_prompt()
    example_text = prompt.split("Example JSON: ")[1].split("\nAuthoritative JSON Schema: ")[0]
    parsed = parse_judge_output(json.loads(example_text))
    assert len(parsed.dimensions) == 4
    assert all(item.judge_version == "quality-v1" for item in parsed.dimensions)
    assert (
        json.loads(prompt.split("Authoritative JSON Schema: ")[1])
        == JudgeOutput.model_json_schema()
    )
    scores = parse_judge_output(canonical_output())
    assert all(
        item.score == 2 and item.evidence_refs == ("candidate.diff",) for item in scores.dimensions
    )


@pytest.mark.parametrize(
    "case",
    [
        "mapping",
        "top-version",
        "nested-version",
        "analysis-version",
        "extra",
        "missing-field",
        "duplicate",
        "missing-dimension",
        "unknown-dimension",
        "score-string",
        "score-bool",
        "score-out-of-range",
        "score-nan",
        "refs-string",
        "refs-number",
        "reason-number",
    ],
)
def test_noncanonical_output_is_rejected_without_coercion(case: str) -> None:
    from pydantic import ValidationError

    from agentbenchkit.analysis.judge import parse_judge_output

    value = canonical_output()
    first = value["dimensions"][0]
    if case == "mapping":
        value["dimensions"] = {item["dimension"]: item for item in value["dimensions"]}
    elif case == "top-version":
        value["judge_version"] = "quality-v1"
    elif case == "nested-version":
        first["judge_version"] = "quality-v1"
    elif case == "analysis-version":
        value["analysis_version"] = "quality-v1"
    elif case == "extra":
        first["confidence"] = 0.9
    elif case == "missing-field":
        del first["evidence_refs"]
    elif case == "duplicate":
        value["dimensions"][1] = first.copy()
    elif case == "missing-dimension":
        value["dimensions"].pop()
    elif case == "unknown-dimension":
        first["dimension"] = "correctness"
    elif case == "score-string":
        first["score"] = "2"
    elif case == "score-bool":
        first["score"] = True
    elif case == "score-out-of-range":
        first["score"] = 5
    elif case == "score-nan":
        first["score"] = float("nan")
    elif case == "refs-string":
        first["evidence_refs"] = "candidate.diff"
    elif case == "refs-number":
        first["evidence_refs"] = [1]
    elif case == "reason-number":
        first["reason"] = 1
    with pytest.raises(ValidationError):
        parse_judge_output(value)


async def test_reported_shape_mismatch_preserves_history_and_verdicts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider: Server
) -> None:
    from pydantic import ValidationError

    from agentbenchkit.analysis.judge import RubricScores

    # Representative shape reproduces the recorded errors; raw live output was not retained.
    bad = {
        "dimensions": {item["dimension"]: item for item in canonical_output()["dimensions"]},
        "judge_version": "quality-v1",
    }
    with pytest.raises(ValidationError) as caught:
        RubricScores.model_validate(bad)
    assert {error["type"] for error in caught.value.errors()} == {"tuple_type", "extra_forbidden"}
    directory = await evaluate(load_tasks(("clamp",)), ControlledHarness(True), tmp_path)
    sample = next(directory.glob("tasks/*/*/sample.json"))
    original = {path: path.read_bytes() for path in directory.rglob("*") if path.is_file()}
    monkeypatch.setenv("TEST_JUDGE_KEY", SECRET)
    endpoint, requests, replies = provider
    replies.append((200, completion(json.dumps(bad))))
    failed = judge_sample(
        tmp_path, directory.name, sample.parent.name, "test", endpoint, "TEST_JUDGE_KEY"
    )
    failure = json.loads(failed.read_bytes())
    assert failure["judge_status"] == "ERROR"
    assert "dimensions: list_type" in failure["error"]
    assert "judge_version: extra_forbidden" in failure["error"]
    original[failed] = failed.read_bytes()

    valid = canonical_output()
    reference = next(sample.parent.rglob("*.diff")).relative_to(directory).as_posix()
    for item in valid["dimensions"]:
        item["evidence_refs"] = [reference]
    replies.append((200, completion(json.dumps(valid))))
    passed = judge_sample(
        tmp_path, directory.name, sample.parent.name, "test", endpoint, "TEST_JUDGE_KEY"
    )
    result = json.loads(passed.read_bytes())
    assert result["judge_status"] == "COMPLETED"
    assert result["analysis_version"] == "quality-v1"
    assert result["output_schema_version"] == "judge-output-v1"
    assert result["prompt_version"] == "quality-json-v2"
    assert all(d["judge_version"] == "quality-v1" for d in result["rubric_scores"]["dimensions"])
    assert "Authoritative JSON Schema:" in requests[1]["messages"][0]["content"]
    assert all(path.read_bytes() == before for path, before in original.items())
