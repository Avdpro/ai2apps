"""Durable contracts for asynchronous Agent execution and interaction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class AgentDefinitionStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class AgentRunStatus(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    WAITING_CAPABILITY = "waiting_capability"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNCERTAIN = "uncertain"


class InteractionKind(StrEnum):
    TEXT = "text"
    MENU = "menu"
    FILE = "file"
    FORM = "form"
    APPROVAL = "approval"


class InteractionStatus(StrEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class AgentDefinitionRecord:
    id: str
    agent_key: str
    package_version: str
    display_name: str
    description: str
    source: str
    status: AgentDefinitionStatus
    executor_key: str
    concurrency_group: str | None
    concurrency_limit: int | None
    resume_policy: str
    max_steps: int
    timeout_seconds: int
    manifest: dict[str, Any]
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AgentRunRecord:
    id: str
    agent_definition_id: str
    session_id: str
    parent_run_id: str | None
    root_run_id: str
    depth: int
    delegation: dict[str, Any]
    status: AgentRunStatus
    idempotency_key: str | None
    priority: int
    input: dict[str, Any]
    output: dict[str, Any] | None
    error: dict[str, Any] | None
    granted_capabilities: tuple[str, ...]
    current_step: int
    cancel_requested: bool
    revision: int
    deadline_at: datetime
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class StatusLineRecord:
    id: str
    run_id: str
    status_key: str
    phase: str
    text: str
    presentation: str
    progress: float | None
    content: dict[str, Any]
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class RunStepRecord:
    id: str
    run_id: str
    sequence: int
    action_key: str
    kind: str
    status: RunStepStatus
    tool_name: str | None
    input: dict[str, Any]
    output: dict[str, Any] | None
    error: dict[str, Any] | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class InteractionRecord:
    id: str
    run_id: str
    request_key: str
    kind: InteractionKind
    status: InteractionStatus
    prompt: str
    response_schema: dict[str, Any]
    ui_hints: dict[str, Any]
    request: dict[str, Any]
    response: dict[str, Any] | None
    response_id: str | None
    deadline_at: datetime
    revision: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


@dataclass(frozen=True, slots=True)
class CompleteAction:
    output: dict[str, Any]


@dataclass(frozen=True, slots=True)
class FailAction:
    code: str
    message: str
    retryable: bool = False


@dataclass(frozen=True, slots=True)
class ContinueAction:
    status_text: str = "Continuing…"


@dataclass(frozen=True, slots=True)
class StatusAction:
    phase: str
    text: str
    presentation: str = "pulse"
    progress: float | None = None
    content: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class InteractionAction:
    request_key: str
    kind: InteractionKind
    prompt: str
    response_schema: dict[str, Any]
    ui_hints: dict[str, Any] | None = None
    request: dict[str, Any] | None = None
    timeout_seconds: int = 86_400


@dataclass(frozen=True, slots=True)
class ToolCallAction:
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    timeout_ms: int | None = None


@dataclass(frozen=True, slots=True)
class ModelCallAction:
    call_id: str
    request: dict[str, Any]


AgentAction = (
    CompleteAction
    | FailAction
    | ContinueAction
    | StatusAction
    | InteractionAction
    | ToolCallAction
    | ModelCallAction
)


@dataclass(frozen=True, slots=True)
class AgentExecutionContext:
    definition: AgentDefinitionRecord
    run: AgentRunRecord
    steps: tuple[RunStepRecord, ...]
    interactions: tuple[InteractionRecord, ...]

    def interaction(self, request_key: str) -> InteractionRecord | None:
        return next(
            (item for item in self.interactions if item.request_key == request_key),
            None,
        )

    def step(self, action_key: str) -> RunStepRecord | None:
        return next(
            (item for item in self.steps if item.action_key == action_key), None
        )


class AgentRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str, *, details=None) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(message)
