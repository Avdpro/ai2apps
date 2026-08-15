"""Sandboxed Process Service contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class ProcessStatus(StrEnum):
    STARTING = "starting"
    RUNNING = "running"
    EXITED = "exited"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    IDLE_TIMEOUT = "idle_timeout"
    OUTPUT_LIMIT = "output_limit"
    ORPHANED = "orphaned"

    @property
    def terminal(self) -> bool:
        return self not in {ProcessStatus.STARTING, ProcessStatus.RUNNING}


@dataclass(frozen=True, slots=True)
class ProcessLimits:
    wall_time_seconds: int
    idle_time_seconds: int
    cpu_time_seconds: int
    memory_bytes: int
    output_bytes: int

    def to_json(self) -> dict[str, int]:
        return {
            "wall_time_seconds": self.wall_time_seconds,
            "idle_time_seconds": self.idle_time_seconds,
            "cpu_time_seconds": self.cpu_time_seconds,
            "memory_bytes": self.memory_bytes,
            "output_bytes": self.output_bytes,
        }


@dataclass(frozen=True, slots=True)
class ProcessRecord:
    id: str
    session_id: str
    run_id: str | None
    caller_id: str
    status: ProcessStatus
    argv: tuple[str, ...]
    cwd: str
    environment_keys: tuple[str, ...]
    sandbox_backend: str
    network_enabled: bool
    pid: int | None
    exit_code: int | None
    limits: dict[str, int]
    stdin_open: bool
    output_bytes: int
    last_activity_at: datetime
    error: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class ProcessLogRecord:
    id: str
    process_id: str
    sequence: int
    stream: str
    encoding: str
    content: str
    byte_count: int
    created_at: datetime


class ProcessServiceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)
