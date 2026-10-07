"""Independent status dimensions from the frozen architecture."""

from enum import StrEnum


class ExecutionStatus(StrEnum):
    PENDING = "PENDING"
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    COLLECTING = "COLLECTING"
    FINISHED = "FINISHED"
    ERROR = "ERROR"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


class AgentOutcome(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    LIMITED = "LIMITED"
    ABORTED = "ABORTED"
    UNKNOWN = "UNKNOWN"


class Verdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    NOT_RUN = "NOT_RUN"


class AuxiliaryStatus(StrEnum):
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    ERROR = "ERROR"
    NOT_RUN = "NOT_RUN"
