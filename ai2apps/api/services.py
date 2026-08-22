"""Service Registry, Tool discovery, lifecycle, and invocation APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai2apps.api.errors import platform_error_response, repository_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import (
    PrincipalProvider,
    require_app_capability,
    resolve_request_principal,
)
from ai2apps.api.ownership import authorize_session
from ai2apps.apps.access import APP_SYSTEM_MANAGE
from ai2apps.core import RepositoryError
from ai2apps.identity import RequestPrincipal
from ai2apps.packages import PackageError
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.services import (
    ServiceDescriptorRecord,
    ServiceInstanceRecord,
    ServiceInstanceStatus,
    ServiceRuntimeMode,
    ServiceStatus,
    ToolCallContext,
    ToolDescriptorRecord,
    ToolGatewayError,
    ToolInvocationRecord,
    ToolInvocationStatus,
)


class ServiceInstanceResponse(BaseModel):
    id: str
    provider_key: str
    status: ServiceInstanceStatus
    endpoint: str | None
    health: dict[str, Any]
    last_error: str | None
    revision: int

    @classmethod
    def from_record(cls, record: ServiceInstanceRecord) -> ServiceInstanceResponse:
        return cls(**{name: getattr(record, name) for name in cls.model_fields})


class ServiceResponse(BaseModel):
    id: str
    service_key: str
    package_id: str
    package_version: str
    display_name: str
    runtime_mode: ServiceRuntimeMode
    source: str
    status: ServiceStatus
    capabilities: list[str]
    dependencies: list[dict[str, Any]]
    config: dict[str, Any]
    package_digest: str | None
    permissions: dict[str, Any]
    revision: int
    created_at: datetime
    updated_at: datetime
    instance: ServiceInstanceResponse | None = None

    @classmethod
    def from_record(
        cls,
        record: ServiceDescriptorRecord,
        instance: ServiceInstanceRecord | None = None,
    ) -> ServiceResponse:
        return cls(
            id=record.id,
            service_key=record.service_key,
            package_id=record.package_id,
            package_version=record.package_version,
            display_name=record.display_name,
            runtime_mode=record.runtime_mode,
            source=record.source,
            status=record.status,
            capabilities=list(record.capabilities),
            dependencies=[
                {
                    "service_key": dependency.service_key,
                    "version_spec": dependency.version_spec,
                    "optional": dependency.optional,
                }
                for dependency in record.dependencies
            ],
            config=record.config,
            package_digest=record.package_digest,
            permissions=record.permissions,
            revision=record.revision,
            created_at=record.created_at,
            updated_at=record.updated_at,
            instance=(
                None
                if instance is None
                else ServiceInstanceResponse.from_record(instance)
            ),
        )


class ServiceListResponse(BaseModel):
    items: list[ServiceResponse]


class ServiceLifecycleRequest(BaseModel):
    expected_revision: int = Field(ge=1)


class ToolResponse(BaseModel):
    id: str
    service_id: str
    qualified_name: str
    display_name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    effects: list[str]
    required_capabilities: list[str]
    capability_rules: list[dict[str, Any]]
    retry_policy: dict[str, Any]
    timeout_ms: int

    @classmethod
    def from_record(cls, record: ToolDescriptorRecord) -> ToolResponse:
        return cls(
            id=record.id,
            service_id=record.service_id,
            qualified_name=record.qualified_name,
            display_name=record.display_name,
            description=record.description,
            input_schema=record.input_schema,
            output_schema=record.output_schema,
            effects=list(record.effects),
            required_capabilities=list(record.required_capabilities),
            capability_rules=list(record.capability_rules),
            retry_policy=record.retry_policy,
            timeout_ms=record.timeout_ms,
        )


class ToolListResponse(BaseModel):
    items: list[ToolResponse]


class ToolInvokeRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None
    timeout_ms: int | None = Field(default=None, ge=1)


class ToolInvokeResponse(BaseModel):
    invocation_id: str
    tool_id: str
    qualified_name: str
    provider_key: str
    output: dict[str, Any]
    duration_ms: int


class ToolInvocationResponse(BaseModel):
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

    @classmethod
    def from_record(cls, record: ToolInvocationRecord) -> ToolInvocationResponse:
        return cls(**{name: getattr(record, name) for name in cls.model_fields})


class ToolInvocationListResponse(BaseModel):
    items: list[ToolInvocationResponse]


def _runtime_or_error(
    runtime_provider: PlatformRuntimeProvider,
) -> PlatformRuntime | JSONResponse:
    runtime = runtime_provider()
    if (
        runtime is None
        or runtime.services is None
        or runtime.service_registry is None
        or runtime.tools is None
    ):
        return platform_error_response(
            status_code=503,
            code="platform_not_ready",
            message="AI2Apps Service runtime is not ready.",
            retryable=True,
        )
    return runtime


def _gateway_error(error: ToolGatewayError) -> JSONResponse:
    status = {
        "tool_not_found": 404,
        "session_not_found": 404,
        "invalid_tool_input": 422,
        "invalid_timeout": 422,
        "capability_denied": 403,
        "tool_disabled": 409,
        "service_disabled": 409,
        "provider_identity_mismatch": 409,
        "invalid_tool_output": 502,
        "provider_error": 502,
        "provider_unavailable": 503,
        "service_unavailable": 503,
        "tool_timeout": 504,
    }.get(error.code, 500)
    return platform_error_response(
        status_code=status,
        code=error.code,
        message=str(error),
        retryable=error.retryable,
        details=error.details,
    )


def create_service_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(
        dependencies=[
            Depends(require_app_capability(principal_provider, APP_SYSTEM_MANAGE))
        ]
    )
    principal_dependency = Depends(principal_provider)

    @router.get("/services", response_model=ServiceListResponse)
    def list_services():
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        items = []
        for service in runtime.services.list_services():
            try:
                instance = runtime.services.get_instance_for_service(service.id)
            except RepositoryError:
                instance = None
            items.append(ServiceResponse.from_record(service, instance))
        return ServiceListResponse(items=items)

    @router.get("/services/{service_key}", response_model=ServiceResponse)
    def get_service(service_key: str):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            service = runtime.services.get_service(service_key)
            instance = runtime.services.get_instance_for_service(service.id)
            return ServiceResponse.from_record(service, instance)
        except RepositoryError as error:
            return repository_error_response(error)

    async def change_enabled(
        service_key: str, request: ServiceLifecycleRequest, enabled: bool
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            managed = (
                runtime.package_manager is not None
                and runtime.package_repository is not None
                and runtime.package_repository.active(service_key) is not None
            )
            if managed:
                operation = (
                    runtime.package_manager.enable
                    if enabled
                    else runtime.package_manager.disable
                )
                service = await operation(service_key, request.expected_revision)
            else:
                service = await runtime.service_registry.set_enabled(
                    service_key,
                    expected_revision=request.expected_revision,
                    enabled=enabled,
                )
            instance = runtime.services.get_instance_for_service(service.id)
            return ServiceResponse.from_record(service, instance)
        except RepositoryError as error:
            return repository_error_response(error)
        except ToolGatewayError as error:
            return _gateway_error(error)
        except PackageError as error:
            return platform_error_response(
                status_code=409,
                code=error.code,
                message=str(error),
                details=error.details,
            )

    @router.post("/services/{service_key}/enable", response_model=ServiceResponse)
    async def enable_service(service_key: str, request: ServiceLifecycleRequest):
        return await change_enabled(service_key, request, True)

    @router.post("/services/{service_key}/disable", response_model=ServiceResponse)
    async def disable_service(service_key: str, request: ServiceLifecycleRequest):
        return await change_enabled(service_key, request, False)

    @router.post("/services/{service_key}/restart", response_model=ServiceResponse)
    async def restart_service(service_key: str):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            if (
                runtime.package_manager is not None
                and runtime.package_repository is not None
                and runtime.package_repository.active(service_key) is not None
            ):
                await runtime.package_manager.restart(service_key)
            else:
                await runtime.service_registry.restart(service_key)
            service = runtime.services.get_service(service_key)
            instance = runtime.services.get_instance_for_service(service.id)
            return ServiceResponse.from_record(service, instance)
        except RepositoryError as error:
            return repository_error_response(error)
        except ToolGatewayError as error:
            return _gateway_error(error)

    @router.get("/tools", response_model=ToolListResponse)
    def list_tools(principal: RequestPrincipal = principal_dependency):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        context = ToolCallContext.from_principal(
            principal, caller_id="api:authenticated"
        )
        return ToolListResponse(
            items=[
                ToolResponse.from_record(tool)
                for tool in runtime.tools.list_tools(context)
            ]
        )

    @router.get(
        "/tool-invocations", response_model=ToolInvocationListResponse
    )
    def list_tool_invocations(
        session_id: str | None = None,
        trace_id: str | None = None,
        status: ToolInvocationStatus | None = None,
        limit: int = 100,
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        if principal.authentication_type != "legacy_api_key":
            if session_id is None:
                raise HTTPException(
                    status_code=403,
                    detail={"code": "session_scope_required"},
                )
            authorize_session(runtime, principal, session_id)
        return ToolInvocationListResponse(
            items=[
                ToolInvocationResponse.from_record(item)
                for item in runtime.services.list_invocations(
                    session_id=session_id,
                    trace_id=trace_id,
                    status=status,
                    limit=limit,
                )
            ]
        )

    @router.get(
        "/tool-invocations/{invocation_id}",
        response_model=ToolInvocationResponse,
    )
    def get_tool_invocation(
        invocation_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            invocation = runtime.services.get_invocation(invocation_id)
            if principal.authentication_type != "legacy_api_key":
                if invocation.session_id is None:
                    raise HTTPException(
                        status_code=404,
                        detail={"code": "tool_invocation_not_found"},
                    )
                authorize_session(runtime, principal, invocation.session_id)
            return ToolInvocationResponse.from_record(invocation)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post(
        "/tools/{qualified_name}/invoke",
        response_model=ToolInvokeResponse,
    )
    async def invoke_tool(
        qualified_name: str,
        request: ToolInvokeRequest,
        x_trace_id: str | None = Header(default=None),
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        if principal.authentication_type != "legacy_api_key":
            if request.session_id is None:
                raise HTTPException(
                    status_code=403,
                    detail={"code": "session_scope_required"},
                )
            authorize_session(runtime, principal, request.session_id)
        try:
            result = await runtime.tools.execute(
                qualified_name,
                request.arguments,
                context=ToolCallContext.from_principal(
                    principal,
                    caller_id="api:authenticated",
                    session_id=request.session_id,
                    trace_id=x_trace_id,
                ),
                timeout_ms=request.timeout_ms,
            )
            return ToolInvokeResponse(
                invocation_id=result.invocation_id,
                tool_id=result.tool_id,
                qualified_name=result.qualified_name,
                provider_key=result.provider_key,
                output=result.output,
                duration_ms=result.duration_ms,
            )
        except ToolGatewayError as error:
            return _gateway_error(error)

    return router
