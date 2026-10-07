"""Normalized, capability-aware public evidence."""

from typing import Literal

from pydantic import Field, JsonValue

from agentbenchkit.core.models import Contract


class Event(Contract):
    schema_version: Literal[1] = 1
    event_id: str
    run_id: str
    task_id: str
    sample_id: str
    physical_execution_id: str
    seq: int = Field(ge=1)
    timestamp: str
    source: str
    type: str
    status: str | None = None
    native_call_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
    input_ref: str | None = None
    output_ref: str | None = None
