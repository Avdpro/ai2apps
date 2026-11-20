"""Trusted Todo owner adapters; binding data never comes from TaskInput."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class TodoExecutionAdapter:
    registration: str
    validate: Callable
    start: Callable
    finished: Callable | None = None
    recover: Callable | None = None
    restore: Callable | None = None
    observe: Callable | None = None
    queue_class: str = 'normal'
