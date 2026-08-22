"""Stable Service and Tool contracts for the AI2Apps Harness."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from ai2apps.identity import RequestPrincipal


class ServiceRuntimeMode(StrEnum):
    IN_PROCESS = "in_process"
    MANAGED_PROCESS = "managed_process"
    EXTERNAL = "external"


class ServiceStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class ServiceInstanceStatus(StrEnum):
    INSTALLED = "installed"
    DISABLED = "disabled"
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    RESTARTING = "restarting"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ServiceDependency:
    service_key: str
    version_spec: str = "*"
    optional: bool = False


@dataclass(frozen=True, slots=True)
class ServiceDescriptorRecord:
    id: str
    service_key: str
    package_id: str
    package_version: str
    display_name: str
    runtime_mode: ServiceRuntimeMode
    source: str
    status: ServiceStatus
    capabilities: tuple[str, ...]
    config: dict[str, Any]
    package_digest: str | None
    permissions: dict[str, Any]
    dependencies: tuple[ServiceDependency, ...]
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ServiceInstanceRecord:
    id: str
    service_id: str
    provider_key: str
    status: ServiceInstanceStatus
    endpoint: str | None
    health: dict[str, Any]
    last_error: str | None
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ToolDescriptorRecord:
    id: str
    service_id: str
    qualified_name: str
    display_name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    effects: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    capability_rules: tuple[dict[str, Any], ...]
    retry_policy: dict[str, Any]
    timeout_ms: int
    enabled: bool
    revision: int
    created_at: datetime
    updated_at: datetime


ToolProgressReporter = Callable[
    [dict[str, Any]], None | Awaitable[None]
]


@dataclass(frozen=True, slots=True)
class ToolCallContext:
    caller_id: str
    session_id: str | None = None
    actor_user_id: str | None = None
    installation_id: str | None = None
    organization_id: str | None = None
    billing_account_id: str | None = None
    membership_epoch: int | None = None
    granted_capabilities: frozenset[str] = frozenset()
    trace_id: str | None = None
    invocation_id: str | None = None
    progress_reporter: ToolProgressReporter | None = None

    @classmethod
    def from_principal(
        cls,
        principal: RequestPrincipal,
        *,
        caller_id: str,
        session_id: str | None = None,
        granted_capabilities: frozenset[str] = frozenset(),
        trace_id: str | None = None,
        progress_reporter: ToolProgressReporter | None = None,
    ) -> ToolCallContext:
        return cls(
            caller_id=caller_id,
            session_id=session_id,
            actor_user_id=principal.actor_user_id,
            installation_id=principal.installation_id,
            organization_id=principal.organization_id,
            billing_account_id=principal.billing_account_id,
            membership_epoch=principal.membership_epoch,
            granted_capabilities=granted_capabilities,
            trace_id=trace_id,
            progress_reporter=progress_reporter,
        )

    async def report_progress(
        self,
        text: str,
        *,
        phase: str = "tool",
        progress: float | None = None,
        content: dict[str, Any] | None = None,
    ) -> None:
        if self.progress_reporter is None:
            return
        update = {
            "phase": phase,
            "text": text,
            "progress": progress,
            "content": content or {},
        }
        value = self.progress_reporter(update)
        if inspect.isawaitable(value):
            await value


class ToolInvocationStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True, slots=True)
class ToolInvocationRecord:
    id: str
    tool_id: str
    qualified_name: str
    provider_key: str
    caller_id: str
    session_id: str | None
    trace_id: str | None
    status: ToolInvocationStatus
    arguments: dict[str, Any]
    output: dict[str, Any] | None
    error: dict[str, Any] | None
    progress: dict[str, Any]
    timeout_ms: int
    attempt: int
    duration_ms: int | None
    revision: int
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    invocation_id: str
    tool_id: str
    qualified_name: str
    provider_key: str
    output: dict[str, Any]
    duration_ms: int


class ToolGatewayError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.retryable = retryable
        self.details = details or {}
        super().__init__(message)


class ToolProviderError(RuntimeError):
    """A bound provider returned a stable execution failure."""
