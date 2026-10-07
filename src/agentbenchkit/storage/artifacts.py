"""Atomic files and streaming redaction before evidence reaches disk."""

import json
import os
from pathlib import Path
from typing import Any


class Redactor:
    def __init__(self, secrets: tuple[str, ...] = ()) -> None:
        self.secrets = tuple(secret for secret in secrets if secret)

    def text(self, text: str) -> str:
        for secret in sorted(self.secrets, key=len, reverse=True):
            text = text.replace(secret, "[REDACTED]")
        return text

    def value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            return {
                str(k): self.value(v)
                for k, v in value.items()
                if str(k) not in {"protocol_data", "reasoning_content"}
            }
        if isinstance(value, (list, tuple)):
            return [self.value(v) for v in value]
        return value


class StreamRedactor:
    def __init__(self, redactor: Redactor) -> None:
        self.redactor = redactor
        self.pending = ""

    def feed(self, text: str, *, final: bool = False) -> str:
        self.pending += text
        cut = (
            len(self.pending)
            if final
            else max(
                0, len(self.pending) - max((len(s) - 1 for s in self.redactor.secrets), default=0)
            )
        )
        for secret in self.redactor.secrets:
            start = self.pending.find(secret)
            while start >= 0:
                if start < cut < start + len(secret):
                    cut = start
                start = self.pending.find(secret, start + 1)
        output, self.pending = self.pending[:cut], self.pending[cut:]
        return self.redactor.text(output)


def write_json(path: Path, value: Any, redactor: Redactor | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = (redactor or Redactor()).value(value)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(clean, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
