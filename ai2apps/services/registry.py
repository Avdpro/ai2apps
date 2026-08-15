"""In-memory provider bindings and the authoritative Tool gateway."""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from ai2apps.core import ResourceNotFoundError, RevisionConflictError
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase

from .models import (
    ServiceInstanceStatus,
    ServiceStatus,
    ToolCallContext,
    ToolExecutionResult,
    ToolGatewayError,
    ToolInvocationStatus,
    ToolProviderError,
)
from .repository import ServiceRepository

ToolHandler = Callable[
    [dict[str, Any], ToolCallContext], dict[str, Any] | Awaitable[dict[str, Any]]
]
LifecycleHandler = Callable[[], None | Awaitable[None]]
SecretResolver = Callable[[dict[str, Any], str], Any]


@dataclass(frozen=True, slots=True)
class BoundTool:
    provider_key: str
    handler: ToolHandler


@dataclass(frozen=True, slots=True)
class ServiceLifecycle:
    start: LifecycleHandler | None = None
    stop: LifecycleHandler | None = None
    restart: LifecycleHandler | None = None


async def _await_if_needed(value):
    if inspect.isawaitable(value):
        return await value
    return value


class ServiceRegistry:
    """Combines durable descriptors with process-local provider authority."""

    def __init__(self, repository: ServiceRepository) -> None:
        self.repository = repository
        self._handlers: dict[str, BoundTool] = {}
        self._lifecycles: dict[str, ServiceLifecycle] = {}

    def bind_tool(
        self,
        qualified_name: str,
        *,
        provider_key: str,
        handler: ToolHandler,
    ) -> None:
        tool = self.repository.get_tool(qualified_name)
        instance = self.repository.get_instance_for_service(tool.service_id)
        if instance.provider_key != provider_key:
            raise ToolGatewayError(
                "provider_identity_mismatch",
                f"Provider {provider_key} does not own {qualified_name}",
            )
        self._handlers[qualified_name] = BoundTool(provider_key, handler)

    def bind_lifecycle(
        self,
        service_key: str,
        *,
        lifecycle: ServiceLifecycle,
    ) -> None:
        service = self.repository.get_service(service_key)
        self._lifecycles[service.id] = lifecycle

    def bound_tool(self, qualified_name: str) -> BoundTool | None:
        return self._handlers.get(qualified_name)

    async def set_enabled(
        self,
        service_key: str,
        *,
        expected_revision: int,
        enabled: bool,
    ):
        service = self.repository.get_service(service_key)
        if service.revision != expected_revision:
            raise RevisionConflictError(
                service.id,
                expected_revision,
                service.revision,
            )
        instance = self.repository.get_instance_for_service(service.id)
        lifecycle = self._lifecycles.get(service.id, ServiceLifecycle())
        if enabled:
            self.repository.set_instance_status(
                instance.id, ServiceInstanceStatus.STARTING
            )
            try:
                if lifecycle.start is not None:
                    await _await_if_needed(lifecycle.start())
                self.repository.set_instance_status(
                    instance.id, ServiceInstanceStatus.RUNNING
                )
            except Exception as exc:
                self.repository.set_instance_status(
                    instance.id,
                    ServiceInstanceStatus.FAILED,
                    last_error=str(exc),
                )
                raise
            return self.repository.set_service_status(
                service.id,
                expected_revision=expected_revision,
                status=ServiceStatus.ENABLED,
            )
        self.repository.set_instance_status(instance.id, ServiceInstanceStatus.STOPPING)
        try:
            if lifecycle.stop is not None:
                await _await_if_needed(lifecycle.stop())
            self.repository.set_instance_status(
                instance.id, ServiceInstanceStatus.DISABLED
            )
        except Exception as exc:
            self.repository.set_instance_status(
                instance.id,
                ServiceInstanceStatus.FAILED,
                last_error=str(exc),
            )
            raise
        return self.repository.set_service_status(
            service.id,
            expected_revision=expected_revision,
            status=ServiceStatus.DISABLED,
        )

    async def restart(self, service_key: str) -> None:
        service = self.repository.get_service(service_key)
        if service.status is ServiceStatus.DISABLED:
            raise ToolGatewayError(
                "service_disabled", f"Service {service_key} is disabled"
            )
        instance = self.repository.get_instance_for_service(service.id)
        lifecycle = self._lifecycles.get(service.id, ServiceLifecycle())
        self.repository.set_instance_status(
            instance.id, ServiceInstanceStatus.RESTARTING
        )
        try:
            if lifecycle.restart is not None:
                await _await_if_needed(lifecycle.restart())
            else:
                if lifecycle.stop is not None:
                    await _await_if_needed(lifecycle.stop())
                if lifecycle.start is not None:
                    await _await_if_needed(lifecycle.start())
            self.repository.set_instance_status(
                instance.id, ServiceInstanceStatus.RUNNING
            )
        except Exception as exc:
            self.repository.set_instance_status(
                instance.id,
                ServiceInstanceStatus.FAILED,
                last_error=str(exc),
            )
            raise


class ToolGateway:
    """Validate, authorize, route, time-bound, and audit Tool calls."""

    def __init__(
        self,
        database: PlatformDatabase,
        events: EventStore,
        repository: ServiceRepository,
        registry: ServiceRegistry,
    ) -> None:
        self.database = database
        self.events = events
        self.repository = repository
        self.registry = registry
        self._secret_resolver: SecretResolver | None = None

    def bind_secret_resolver(self, resolver: SecretResolver | None) -> None:
        """Resolve secret:// references only after validation and authorization."""

        self._secret_resolver = resolver

    def list_tools(
        self,
        context: ToolCallContext,
        *,
        include_requiring_approval: bool = False,
    ) -> tuple:
        """Return active bound Tools visible for execution or Agent planning.

        Planning may include Tools whose capabilities have not been granted yet;
        execution still checks those capabilities and cannot bypass approval.
        """

        visible = []
        for tool in self.repository.list_tools():
            service = self.repository.get_service(tool.service_id)
            if service.status is not ServiceStatus.ENABLED:
                continue
            try:
                instance = self.repository.get_instance_for_service(tool.service_id)
            except ResourceNotFoundError:
                continue
            if instance.status not in {
                ServiceInstanceStatus.RUNNING,
                ServiceInstanceStatus.DEGRADED,
            }:
                continue
            if not include_requiring_approval and not set(
                tool.required_capabilities
            ).issubset(context.granted_capabilities):
                continue
            binding = self.registry.bound_tool(tool.qualified_name)
            if binding is None or binding.provider_key != instance.provider_key:
                continue
            visible.append(tool)
        return tuple(visible)

    @staticmethod
    def required_capabilities(tool, arguments: dict[str, Any]) -> frozenset[str]:
        """Resolve static plus declarative argument-dependent capabilities."""

        required = set(tool.required_capabilities)
        for rule in tool.capability_rules:
            condition = rule.get("when", {})
            property_name = condition.get("property")
            if not isinstance(property_name, str):
                continue
            if arguments.get(property_name) == condition.get("equals"):
                values = rule.get("require", [])
                if isinstance(values, list) and all(isinstance(x, str) for x in values):
                    required.update(values)
        return frozenset(required)

    def _audit(
        self,
        *,
        tool_id: str,
        invocation_id: str,
        context: ToolCallContext,
        status: str,
        duration_ms: int,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self.database.transaction(write=True) as connection:
            app_instance_id = None
            if context.session_id is not None:
                row = connection.execute(
                    "SELECT app_instance_id FROM sessions WHERE id = ?",
                    (context.session_id,),
                ).fetchone()
                if row is None:
                    raise ToolGatewayError(
                        "session_not_found",
                        f"Session not found: {context.session_id}",
                    )
                app_instance_id = row["app_instance_id"]
            event_type = {
                "started": "tool.invocation.started",
                "progress": "tool.invocation.progress",
                "retrying": "tool.invocation.retrying",
                "completed": "tool.invocation.completed",
                "cancelled": "tool.invocation.cancelled",
            }.get(status, "tool.invocation.failed")
            self.events.append_in_transaction(
                connection,
                event_type=event_type,
                subject_id=tool_id,
                app_instance_id=app_instance_id,
                session_id=context.session_id,
                trace_id=context.trace_id,
                payload={
                    "caller_id": context.caller_id,
                    "invocation_id": invocation_id,
                    "status": status,
                    "duration_ms": duration_ms,
                    **(details or {}),
                    **({} if code is None else {"code": code}),
                },
            )

    async def execute(
        self,
        qualified_name: str,
        arguments: dict[str, Any],
        *,
        context: ToolCallContext,
        timeout_ms: int | None = None,
    ) -> ToolExecutionResult:
        try:
            tool = self.repository.get_tool(qualified_name)
        except ResourceNotFoundError as exc:
            raise ToolGatewayError("tool_not_found", str(exc)) from exc
        service = self.repository.get_service(tool.service_id)
        instance = self.repository.get_instance_for_service(tool.service_id)
        binding = self.registry.bound_tool(tool.qualified_name)
        if not tool.enabled or service.status is not ServiceStatus.ENABLED:
            raise ToolGatewayError(
                "tool_disabled", f"Tool {qualified_name} is disabled"
            )
        if instance.status not in {
            ServiceInstanceStatus.RUNNING,
            ServiceInstanceStatus.DEGRADED,
        }:
            raise ToolGatewayError(
                "service_unavailable",
                f"Service provider for {qualified_name} is {instance.status.value}",
                retryable=True,
            )
        if binding is None:
            raise ToolGatewayError(
                "provider_unavailable",
                f"No runtime provider is bound for {qualified_name}",
                retryable=True,
            )
        if binding.provider_key != instance.provider_key:
            raise ToolGatewayError(
                "provider_identity_mismatch",
                f"Bound provider does not own {qualified_name}",
            )
        missing = sorted(
            self.required_capabilities(tool, arguments) - context.granted_capabilities
        )
        if missing:
            raise ToolGatewayError(
                "capability_denied",
                f"Missing capabilities for {qualified_name}",
                details={"missing": missing},
            )
        if context.session_id is not None:
            with self.database.transaction() as connection:
                session = connection.execute(
                    "SELECT id FROM sessions WHERE id = ? AND status = 'active'",
                    (context.session_id,),
                ).fetchone()
            if session is None:
                raise ToolGatewayError(
                    "session_not_found",
                    f"Active Session not found: {context.session_id}",
                )
        try:
            Draft202012Validator(tool.input_schema).validate(arguments)
        except ValidationError as exc:
            raise ToolGatewayError(
                "invalid_tool_input",
                exc.message,
                details={"path": list(exc.absolute_path)},
            ) from exc

        handler_arguments = arguments
        sensitive_values: tuple[str, ...] = ()
        if self._secret_resolver is not None:
            injection = self._secret_resolver(arguments, qualified_name)
            handler_arguments = injection.arguments
            sensitive_values = injection.sensitive_values

        def redact(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: redact(item) for key, item in value.items()}
            if isinstance(value, list):
                return [redact(item) for item in value]
            if isinstance(value, str):
                for secret in sensitive_values:
                    if secret:
                        value = value.replace(secret, "[secret]")
            return value

        effective_timeout_ms = tool.timeout_ms
        if timeout_ms is not None:
            if timeout_ms <= 0:
                raise ToolGatewayError("invalid_timeout", "timeout_ms must be positive")
            effective_timeout_ms = min(timeout_ms, tool.timeout_ms)
        invocation = self.repository.create_invocation(
            tool=tool,
            provider_key=instance.provider_key,
            caller_id=context.caller_id,
            session_id=context.session_id,
            trace_id=context.trace_id,
            arguments=arguments,
            timeout_ms=effective_timeout_ms,
        )
        started = time.monotonic()
        self._audit(
            tool_id=tool.id,
            invocation_id=invocation.id,
            context=context,
            status="started",
            duration_ms=0,
            details={"qualified_name": qualified_name, "attempt": 1},
        )

        async def report_progress(update: dict[str, Any]) -> None:
            safe_update = redact(update)
            self.repository.update_invocation_progress(invocation.id, safe_update)
            duration = int((time.monotonic() - started) * 1_000)
            self._audit(
                tool_id=tool.id,
                invocation_id=invocation.id,
                context=context,
                status="progress",
                duration_ms=duration,
                details={"update": safe_update},
            )
            if context.progress_reporter is not None:
                await _await_if_needed(context.progress_reporter(safe_update))

        execution_context = replace(
            context,
            invocation_id=invocation.id,
            progress_reporter=report_progress,
        )
        retry_policy = tool.retry_policy
        max_attempts = retry_policy.get("max_attempts", 1)
        retry_codes = set(retry_policy.get("retry_codes", ()))
        backoff_ms = retry_policy.get("backoff_ms", 0)
        output = None
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            if attempt > 1:
                self.repository.set_invocation_attempt(invocation.id, attempt)
            error_code = None
            error_message = None
            retryable = False
            caught: Exception | None = None
            try:
                async with asyncio.timeout(effective_timeout_ms / 1_000):
                    output = await _await_if_needed(
                        binding.handler(handler_arguments, execution_context)
                    )
                Draft202012Validator(tool.output_schema).validate(output)
                break
            except asyncio.CancelledError:
                duration = int((time.monotonic() - started) * 1_000)
                self.repository.settle_invocation(
                    invocation.id,
                    status=ToolInvocationStatus.CANCELLED,
                    duration_ms=duration,
                    error={"code": "tool_cancelled"},
                )
                self._audit(
                    tool_id=tool.id,
                    invocation_id=invocation.id,
                    context=context,
                    status="cancelled",
                    duration_ms=duration,
                    code="tool_cancelled",
                )
                raise
            except TimeoutError as exc:
                caught = exc
                error_code = "tool_timeout"
                error_message = (
                    f"Tool {qualified_name} exceeded {effective_timeout_ms} ms"
                )
                retryable = True
            except ValidationError as exc:
                caught = exc
                error_code = "invalid_tool_output"
                error_message = exc.message
            except ToolProviderError as exc:
                caught = exc
                error_code = "provider_error"
                error_message = redact(str(exc))
                retryable = True
            except Exception as exc:
                caught = exc
                error_code = "provider_error"
                error_message = redact(str(exc))
                retryable = True

            duration = int((time.monotonic() - started) * 1_000)
            if error_code in retry_codes and attempt < max_attempts:
                self._audit(
                    tool_id=tool.id,
                    invocation_id=invocation.id,
                    context=context,
                    status="retrying",
                    duration_ms=duration,
                    code=error_code,
                    details={"attempt": attempt, "next_attempt": attempt + 1},
                )
                if backoff_ms:
                    await asyncio.sleep(backoff_ms / 1_000)
                continue
            self.repository.settle_invocation(
                invocation.id,
                status=ToolInvocationStatus.FAILED,
                duration_ms=duration,
                error={
                    "code": error_code,
                    "message": error_message,
                    "retryable": retryable,
                },
            )
            self._audit(
                tool_id=tool.id,
                invocation_id=invocation.id,
                context=context,
                status="failed",
                duration_ms=duration,
                code=error_code,
                details={"attempt": attempt},
            )
            raise ToolGatewayError(
                error_code or "provider_error",
                error_message or "Tool provider failed",
                retryable=retryable,
            ) from caught

        assert output is not None
        output = redact(output)
        duration = int((time.monotonic() - started) * 1_000)
        self.repository.settle_invocation(
            invocation.id,
            status=ToolInvocationStatus.COMPLETED,
            duration_ms=duration,
            output=output,
        )
        self._audit(
            tool_id=tool.id,
            invocation_id=invocation.id,
            context=context,
            status="completed",
            duration_ms=duration,
            details={"attempt": attempt},
        )
        return ToolExecutionResult(
            invocation_id=invocation.id,
            tool_id=tool.id,
            qualified_name=qualified_name,
            provider_key=instance.provider_key,
            output=output,
            duration_ms=duration,
        )
