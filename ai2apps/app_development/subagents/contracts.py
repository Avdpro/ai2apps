"""Versioned, standard-library contracts for coding task cooperation."""

from dataclasses import dataclass
from typing import Protocol

SCHEMA_VERSION = 1
ROLES = frozenset({"analyst", "tester", "reviewer", "worker"})
TERMINAL = frozenset({"completed", "failed", "cancelled"})


class SubagentError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class Request:
    role: str
    task: str
    request_key: str
    max_steps: int = 24
    max_model_tokens: int = 20000
    timeout_seconds: int = 300


class RunStore(Protocol):
    def get_run(self, run_id: str): ...


class SnapshotStore(Protocol):
    def capture(self, source, destination): ...


class BudgetStore(Protocol):
    def reserve(self, root_id, call_id, amount): ...


class ProcessExecutor(Protocol):
    async def start(self, **kwargs): ...


class EventSink(Protocol):
    def append(self, **kwargs): ...
