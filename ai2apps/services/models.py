"""Stable Service and Tool contracts for the AI2Apps Harness."""

from __future__ import annotations

import inspect
import json
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from ai2apps.identity import RequestPrincipal


def validate_progress_update(update):
    """Validate the optional portable snapshot; legacy progress stays compatible."""
    value = update.get('progress')
    if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1):
        raise ValueError('Progress must be a finite fraction from zero to one')
    snapshot = (update.get('content') or {}).get('task_progress')
    if snapshot is None:
        return update
    if not isinstance(snapshot, dict) or snapshot.get('schema') != 'ai2apps.task-progress/v1':
        raise ValueError('Invalid AaAT progress schema')
    if set(snapshot) - {'schema','state','stage','task_id','requires_user','wait_reason','metrics'}:
        raise ValueError('Unknown AaAT progress field')
    if snapshot.get('state') not in {'queued','running','waiting','completed','partial','failed','cancelled'}:
        raise ValueError('Invalid owner progress state')
    for key, limit in (('stage',100),('task_id',200),('wait_reason',500)):
        if key in snapshot and (not isinstance(snapshot[key],str) or len(snapshot[key]) > limit):
            raise ValueError('Invalid progress text field')
    if 'requires_user' in snapshot and type(snapshot['requires_user']) is not bool:
        raise ValueError('requires_user must be boolean')
    if snapshot['state'] == 'waiting' and 'requires_user' not in snapshot:
        raise ValueError('Waiting progress must distinguish user assistance')
    metrics = snapshot.get('metrics', [])
    if not isinstance(metrics,list) or len(metrics)>8:
        raise ValueError('Progress has too many metrics')
    for metric in metrics:
        if (not isinstance(metric,dict) or set(metric)-{'label','value','total'}
                or not isinstance(metric.get('label'),str) or not 1<=len(metric['label'])<=100
                or 'value' not in metric):
            raise ValueError('Invalid progress metric')
        for key in ('value','total'):
            if key in metric and (type(metric[key]) not in (int,float) or not math.isfinite(metric[key]) or metric[key]<0):
                raise ValueError('Progress metric must be finite and non-negative')
    if len(json.dumps(snapshot,ensure_ascii=False,allow_nan=False).encode())>8192:
        raise ValueError('AaAT progress snapshot exceeds 8 KiB')
    return update


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
        value = self.progress_reporter(validate_progress_update(update))
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
