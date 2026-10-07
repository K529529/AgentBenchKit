"""Allowlisted, bounded diagnostics. Never retain response bodies or request headers."""

import json
import re
import urllib.error
from http.client import HTTPException
from typing import Any
from urllib.parse import quote

from pydantic import ValidationError

from agentbenchkit.storage.artifacts import Redactor

MAX_ERROR_BODY = 8192
MAX_MESSAGE = 800
MAX_DIAGNOSTIC_BYTES = 65_536
TEXT_FIELDS = {
    "exception_type",
    "phase",
    "message",
    "provider_code",
    "provider_type",
    "provider_param",
    "cause_type",
    "finish_reason",
}
NUMBER_FIELDS = {
    "http_status",
    "worker_exit_code",
    "content_chars",
    "completion_tokens",
    "reasoning_tokens",
}


def safe_text(value: str, key: str) -> str:
    variants = (key, quote(key, safe=""), json.dumps(key)[1:-1]) if key else ()
    text = Redactor(variants).text(value)
    text = re.sub(r"(?i)\bbearer\s+[^\s,;\"']+", "Bearer [REDACTED]", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", text)
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    return text[:MAX_MESSAGE]


def sanitize_diagnostic(data: dict[str, Any], key: str) -> dict[str, Any]:
    result = {
        name: safe_text(value, key)
        for name, value in data.items()
        if name in TEXT_FIELDS and isinstance(value, str)
    }
    numbers = {
        name: value
        for name, value in data.items()
        if name in NUMBER_FIELDS
        and (value is None or (type(value) is int and 0 <= value <= 2**63 - 1))
    }
    return {**result, **numbers}


class JudgeFailure(RuntimeError):
    def __init__(self, diagnostic: dict[str, Any]) -> None:
        self.diagnostic = diagnostic
        super().__init__(str(diagnostic.get("message", "Judge request failed")))


def safe_error(exc: Exception, key: str) -> dict[str, Any]:
    if isinstance(exc, JudgeFailure):
        return sanitize_diagnostic(exc.diagnostic, key)
    diagnostic: dict[str, Any] = {
        "exception_type": type(exc).__name__,
        "phase": "worker",
        "http_status": None,
    }
    if isinstance(exc, urllib.error.HTTPError):
        diagnostic.update(phase="http", http_status=exc.code, message="Provider HTTP error")
        try:
            raw = exc.read(MAX_ERROR_BODY + 1)
            if len(raw) > MAX_ERROR_BODY:
                diagnostic["message"] = "Provider error body exceeded limit; body omitted"
            else:
                data = json.loads(raw)
                error = data.get("error", data) if isinstance(data, dict) else None
                if isinstance(error, dict):
                    for source, target in (
                        ("message", "message"),
                        ("code", "provider_code"),
                        ("type", "provider_type"),
                        ("param", "provider_param"),
                    ):
                        if isinstance(error.get(source), str):
                            diagnostic[target] = error[source]
        except (OSError, ValueError, HTTPException):
            diagnostic["message"] = "Provider error body unreadable or non-JSON; body omitted"
        finally:
            exc.close()
    elif isinstance(exc, ValidationError):
        diagnostic.update(
            phase="rubric_validation",
            message="; ".join(
                f"{'.'.join(map(str, error['loc']))}: {error['type']}"
                for error in exc.errors(include_input=False, include_context=False)[:5]
            ),
        )
    else:
        diagnostic["message"] = str(exc)
        if isinstance(exc, urllib.error.URLError):
            diagnostic.update(phase="transport", cause_type=type(exc.reason).__name__)
    return sanitize_diagnostic(diagnostic, key)
