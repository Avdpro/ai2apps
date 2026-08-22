"""Core management and bearer-token data planes for Local LAN sharing."""

from __future__ import annotations

import inspect
import json
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from ai2apps.identity import RequestPrincipal
from ai2apps.qr import svg_qr_data_url
from ai2apps.sharing import CapabilityExport, CapabilityKind, ShareGrant, SharingError
from ai2apps.sharing.agent_connector import agent_connector_tools, invoke_agent_connector, resolve_agent_connector
from ai2apps.sharing.network import discover_lan_host

from .health import PlatformRuntimeProvider
from .identity import PrincipalProvider, resolve_request_principal


def _error(error: SharingError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": str(error)},
    )


def _manager(runtime_provider):
    runtime = runtime_provider()
    manager = None if runtime is None else getattr(runtime, "sharing", None)
    if manager is None:
        raise HTTPException(status_code=503, detail={"code": "sharing_not_ready"})
    return manager


def _require_core(principal_provider: PrincipalProvider):
    dependency = Depends(principal_provider)

    def authorize(principal: RequestPrincipal = dependency) -> RequestPrincipal:
        if not principal.is_core:
            raise HTTPException(
                status_code=403,
                detail={"code": "core_account_required", "message": "Only the device Core account can manage sharing."},
            )
        return principal

    return authorize


class ExportCreateRequest(BaseModel):
    kind: CapabilityKind
    target_id: str = Field(min_length=1, max_length=500)
    display_name: str = Field(min_length=1, max_length=200)


class ExportStatusRequest(BaseModel):
    status: str


class ExportResponse(BaseModel):
    id: str
    kind: CapabilityKind
    target_id: str
    display_name: str
    protocols: list[str]
    status: str
    revision: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, item: CapabilityExport):
        return cls(
            id=item.id,
            kind=item.kind,
            target_id=item.target_id,
            display_name=item.display_name,
            protocols=list(item.protocols),
            status=item.status,
            revision=item.revision,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


class GrantCreateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    export_ids: list[str] = Field(min_length=1, max_length=100)
    max_concurrency: int = Field(default=1, ge=1, le=100)
    max_requests: int | None = Field(default=None, ge=1, le=1_000_000)
    expires_in_seconds: int | None = Field(default=None, ge=60, le=31_536_000)


class GrantResponse(BaseModel):
    id: str
    label: str
    status: str
    max_concurrency: int
    max_requests: int | None
    expires_at: datetime | None
    request_count: int
    last_used_at: datetime | None
    exports: list[ExportResponse]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, item: ShareGrant):
        return cls(
            id=item.id,
            label=item.label,
            status=item.status,
            max_concurrency=item.max_concurrency,
            max_requests=item.max_requests,
            expires_at=item.expires_at,
            request_count=item.request_count,
            last_used_at=item.last_used_at,
            exports=[ExportResponse.from_record(value) for value in item.exports],
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


class IssuedGrantResponse(BaseModel):
    grant: GrantResponse
    token: str
    openai_base_url: str
    mcp_url: str
    connection_qr: str
    node_id: str | None = None
    ancestor_node_ids: list[str] = Field(default_factory=list)


class NetworkAccessRequest(BaseModel):
    mode: str
    bind_host: str = "0.0.0.0"
    port: int = Field(ge=1024, le=65535)
    expected_revision: int = Field(ge=1)


def create_sharing_management_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(prefix="/sharing", tags=["sharing"])
    core_dependency = Depends(_require_core(principal_provider))

    @router.get("/discovery")
    def discovered_gateways(_: RequestPrincipal = core_dependency):
        runtime = runtime_provider()
        discovery = None if runtime is None else getattr(runtime, "gateway_discovery", None)
        if discovery is None:
            return {"available": False, "error": "Discovery is not running.", "items": []}
        return discovery.snapshot()

    @router.post("/discovery/refresh")
    async def refresh_discovered_gateways(_: RequestPrincipal = core_dependency):
        runtime = runtime_provider()
        discovery = None if runtime is None else getattr(runtime, "gateway_discovery", None)
        if discovery is None:
            return {"available": False, "error": "Discovery is not running.", "items": []}
        return await discovery.refresh()

    @router.get("/exports")
    def list_exports(_: RequestPrincipal = core_dependency):
        return {"items": [ExportResponse.from_record(item) for item in _manager(runtime_provider).list_exports()]}

    @router.post("/cloud/exports/sync")
    async def sync_cloud_exports(principal: RequestPrincipal = core_dependency):
        runtime = runtime_provider()
        manager = _manager(runtime_provider)
        if runtime is None or runtime.cloud is None:
            raise HTTPException(status_code=503, detail={"code": "cloud_client_not_ready"})
        items: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        for export in manager.list_exports():
            if export.status != "active":
                continue
            if export.kind is CapabilityKind.MODEL:
                items.append({
                    "exportId": export.target_id, "kind": "model.chat",
                    "relativePath": "/federation/models/" + quote(export.target_id, safe=""),
                    "displayName": export.display_name,
                    "descriptor": {"capability": "model.chat@1"},
                })
            elif export.kind in {CapabilityKind.TOOL, CapabilityKind.SERVICE}:
                cloud_kind = "mcp.tool" if export.kind is CapabilityKind.TOOL else "mcp.service"
                for tool in manager.tools_for_export(export):
                    items.append({
                        "exportId": tool.qualified_name, "kind": cloud_kind,
                        "relativePath": "/federation/mcp/" + quote(tool.qualified_name, safe=""),
                        "displayName": tool.display_name,
                        "descriptor": {
                            "description": tool.description,
                            "inputSchema": tool.input_schema,
                            "outputSchema": tool.output_schema,
                        },
                    })
            elif export.kind is CapabilityKind.AGENT:
                for tool in agent_connector_tools(export):
                    items.append({
                        "exportId": tool["name"], "kind": "mcp.agent",
                        "relativePath": "/federation/mcp/" + quote(tool["name"], safe=""),
                        "displayName": tool["title"],
                        "descriptor": {
                            "description": tool["description"],
                            "inputSchema": tool["inputSchema"],
                        },
                    })
        if len(items) > 200:
            raise HTTPException(status_code=409, detail={"code": "cloud_export_limit", "count": len(items)})
        try:
            headers = runtime.cloud_ai_authorization_headers(principal)
            response = await runtime.cloud.request(
                "PUT", "/v1/internal/federation/connectors/exports",
                headers=headers, json={"exports": items},
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise HTTPException(status_code=503, detail={"code": "cloud_unavailable"}) from exc
        try:
            value = response.json()
            if response.status_code >= 400:
                raise HTTPException(status_code=response.status_code, detail=value)
        finally:
            await response.aclose()
        return {"installationId": value.get("installationId"), "items": value.get("items", []), "skipped": skipped}

    @router.get("/candidates")
    def list_candidates(_: RequestPrincipal = core_dependency):
        manager = _manager(runtime_provider)
        return {
            "tools": [
                {
                    "id": item.qualified_name,
                    "name": item.display_name,
                    "description": item.description,
                    "inputSchema": item.input_schema,
                }
                for item in manager.list_shareable_tools()
            ],
            "services": [
                {
                    "id": service.service_key,
                    "name": service.display_name,
                    "methods": [tool.qualified_name for tool in tools],
                }
                for service, tools in manager.list_shareable_services()
            ],
            "agents": [
                {
                    "id": item.agent_key,
                    "name": item.display_name,
                    "description": item.description,
                    "inputSchema": (item.manifest or {}).get("invocation_schema", {"type": "object", "properties": {}}),
                }
                for item in manager.list_shareable_agents()
            ],
        }

    @router.get("/network")
    def get_network_access(_: RequestPrincipal = core_dependency):
        return _manager(runtime_provider).network_access()

    @router.patch("/network")
    async def update_network_access(
        payload: NetworkAccessRequest,
        principal: RequestPrincipal = core_dependency,
    ):
        try:
            return await _manager(runtime_provider).update_network_access(
                mode=payload.mode,
                bind_host=payload.bind_host,
                port=payload.port,
                expected_revision=payload.expected_revision,
                updated_by_user_id=principal.actor_user_id,
            )
        except SharingError as error:
            raise _error(error) from error

    @router.post("/exports", response_model=ExportResponse)
    def create_export(payload: ExportCreateRequest, principal: RequestPrincipal = core_dependency):
        try:
            item = _manager(runtime_provider).create_export(
                kind=payload.kind,
                target_id=payload.target_id,
                display_name=payload.display_name,
                created_by_user_id=principal.actor_user_id,
            )
            return ExportResponse.from_record(item)
        except SharingError as error:
            raise _error(error) from error

    @router.patch("/exports/{export_id}", response_model=ExportResponse)
    def set_export_status(export_id: str, payload: ExportStatusRequest, _: RequestPrincipal = core_dependency):
        try:
            return ExportResponse.from_record(_manager(runtime_provider).set_export_status(export_id, payload.status))
        except SharingError as error:
            raise _error(error) from error

    @router.get("/grants")
    def list_grants(_: RequestPrincipal = core_dependency):
        return {"items": [GrantResponse.from_record(item) for item in _manager(runtime_provider).list_grants()]}

    @router.get("/audit")
    def list_audit(limit: int = 100, _: RequestPrincipal = core_dependency):
        try:
            return {"items": list(_manager(runtime_provider).list_audit(limit=limit))}
        except SharingError as error:
            raise _error(error) from error

    def issued_response(request: Request, issued) -> IssuedGrantResponse:
        runtime = runtime_provider()
        network = _manager(runtime_provider).network_access()
        upstreams = None if runtime is None else getattr(runtime, "upstreams", None)
        node_id = None if upstreams is None else upstreams.local_node_id
        ancestor_node_ids = [] if upstreams is None else list(upstreams.ancestor_node_ids())
        base = str(request.base_url).rstrip("/")
        if network.mode != "disabled":
            host = discover_lan_host(
                request.url.hostname or "127.0.0.1", network.bind_host
            )
            rendered_host = f"[{host}]" if ":" in host else host
            base = f"http://{rendered_host}:{network.port}"
        openai_base_url = f"{base}/v1/share/{issued.grant.id}"
        mcp_url = f"{base}/v1/share/{issued.grant.id}/mcp"
        connection = json.dumps(
            {
                "schema": "ai2apps.share/v1",
                "grantId": issued.grant.id,
                "token": issued.token,
                "openaiBaseUrl": openai_base_url,
                "mcpUrl": mcp_url,
                "nodeId": node_id,
                "ancestorNodeIds": ancestor_node_ids,
            },
            separators=(",", ":"),
        )
        return IssuedGrantResponse(
            grant=GrantResponse.from_record(issued.grant),
            token=issued.token,
            openai_base_url=openai_base_url,
            mcp_url=mcp_url,
            connection_qr=svg_qr_data_url(connection),
            node_id=node_id,
            ancestor_node_ids=ancestor_node_ids,
        )

    @router.post("/grants", response_model=IssuedGrantResponse)
    def create_grant(payload: GrantCreateRequest, request: Request, principal: RequestPrincipal = core_dependency):
        try:
            issued = _manager(runtime_provider).create_grant(
                label=payload.label,
                export_ids=tuple(dict.fromkeys(payload.export_ids)),
                max_concurrency=payload.max_concurrency,
                max_requests=payload.max_requests,
                expires_in_seconds=payload.expires_in_seconds,
                created_by_user_id=principal.actor_user_id,
            )
            return issued_response(request, issued)
        except SharingError as error:
            raise _error(error) from error

    @router.post("/grants/{grant_id}/rotate", response_model=IssuedGrantResponse)
    def rotate_grant(grant_id: str, request: Request, _: RequestPrincipal = core_dependency):
        try:
            return issued_response(request, _manager(runtime_provider).rotate_grant(grant_id))
        except SharingError as error:
            raise _error(error) from error

    @router.post("/grants/{grant_id}/revoke", response_model=GrantResponse)
    def revoke_grant(grant_id: str, _: RequestPrincipal = core_dependency):
        try:
            return GrantResponse.from_record(_manager(runtime_provider).revoke_grant(grant_id))
        except SharingError as error:
            raise _error(error) from error

    return router


ModelListHandler = Callable[[ShareGrant], Any | Awaitable[Any]]
ModelChatHandler = Callable[[dict[str, Any], Request, ShareGrant], Any | Awaitable[Any]]


def _bearer(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise SharingError("share_token_required", "Use Authorization: Bearer <share token>.", status_code=401)
    return token


async def _await(value):
    return await value if inspect.isawaitable(value) else value


def create_sharing_data_router(
    runtime_provider: PlatformRuntimeProvider,
    *,
    model_list_handler: ModelListHandler | None = None,
    model_chat_handler: ModelChatHandler | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/v1/share", tags=["sharing-data"])

    async def run_shared(
        manager,
        grant,
        *,
        export_id: str | None,
        operation: str,
        invoke,
    ):
        started = time.monotonic()
        audit_id = manager.start_audit(grant.id, export_id, operation=operation)
        slot = manager.acquire(grant)
        try:
            await slot.__aenter__()
            response = await _await(invoke())
        except Exception as error:
            await slot.__aexit__(type(error), error, error.__traceback__)
            manager.finish_audit(
                audit_id,
                status="failed",
                duration_ms=int((time.monotonic() - started) * 1000),
                error_code=getattr(error, "code", type(error).__name__),
            )
            raise
        if isinstance(response, StreamingResponse):
            original = response.body_iterator

            async def guarded_stream():
                status = "completed"
                error_code = None
                try:
                    async for chunk in original:
                        yield chunk
                except BaseException as error:
                    status = "failed"
                    error_code = type(error).__name__
                    raise
                finally:
                    await slot.__aexit__(None, None, None)
                    manager.finish_audit(
                        audit_id,
                        status=status,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        error_code=error_code,
                    )

            response.body_iterator = guarded_stream()
            return response
        await slot.__aexit__(None, None, None)
        manager.finish_audit(
            audit_id,
            status="completed",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return response

    def authorize(grant_id: str, authorization: str | None) -> tuple[Any, ShareGrant]:
        manager = _manager(runtime_provider)
        try:
            return manager, manager.authenticate(grant_id, _bearer(authorization))
        except SharingError as error:
            raise _error(error) from error

    @router.get("/{grant_id}/models")
    async def models(grant_id: str, authorization: str | None = Header(default=None)):
        manager, grant = authorize(grant_id, authorization)
        allowed = {item.target_id for item in grant.exports if item.kind is CapabilityKind.MODEL and item.status == "active"}
        if not allowed or model_list_handler is None:
            raise HTTPException(status_code=404, detail={"code": "models_not_shared"})
        response = await run_shared(
            manager,
            grant,
            export_id=None,
            operation="models.list",
            invoke=lambda: model_list_handler(grant),
        )
        if hasattr(response, "model_dump"):
            response = response.model_dump(mode="json")
        if isinstance(response, dict) and isinstance(response.get("data"), list):
            response["data"] = [item for item in response["data"] if item.get("id") in allowed]
        return response

    @router.post("/{grant_id}/chat/completions")
    async def chat_completions(grant_id: str, payload: dict[str, Any], request: Request, authorization: str | None = Header(default=None)):
        manager, grant = authorize(grant_id, authorization)
        model = payload.get("model")
        if not isinstance(model, str):
            raise HTTPException(status_code=422, detail={"code": "model_required"})
        try:
            export = manager.find_export(grant, kind=CapabilityKind.MODEL, target_id=model)
        except SharingError as error:
            raise _error(error) from error
        if model_list_handler is None or model_chat_handler is None:
            raise HTTPException(status_code=503, detail={"code": "model_gateway_unavailable"})
        return await run_shared(
            manager,
            grant,
            export_id=export.id,
            operation="model.chat",
            invoke=lambda: model_chat_handler(payload, request, grant),
        )

    async def mcp_call(manager, grant, message: dict[str, Any]):
        method = message.get("method")
        request_id = message.get("id")
        if method == "initialize":
            runtime = runtime_provider()
            upstreams = None if runtime is None else getattr(runtime, "upstreams", None)
            result = {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": "AI2Apps Local Sharing", "version": "0.1.0",
                    "nodeId": None if upstreams is None else upstreams.local_node_id,
                    "ancestorNodeIds": [] if upstreams is None else list(upstreams.ancestor_node_ids()),
                },
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            tools = []
            names = set()
            for export in grant.exports:
                if export.status != "active":
                    continue
                if export.kind in {CapabilityKind.TOOL, CapabilityKind.SERVICE}:
                    for tool in manager.tools_for_export(export):
                        if tool.qualified_name in names:
                            continue
                        names.add(tool.qualified_name)
                        tools.append({"name": tool.qualified_name, "title": tool.display_name, "description": tool.description, "inputSchema": tool.input_schema, "outputSchema": tool.output_schema})
                elif export.kind is CapabilityKind.AGENT:
                    for tool in agent_connector_tools(export):
                        if tool["name"] not in names:
                            names.add(tool["name"])
                            tools.append(tool)
            result = {"tools": tools}
        elif method == "tools/call":
            params = message.get("params") or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not isinstance(name, str) or not isinstance(arguments, dict):
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "Invalid tool call parameters"}}
            try:
                agent_export, operation = resolve_agent_connector(grant.exports, name)
                if agent_export is not None:
                    output = invoke_agent_connector(manager, grant, agent_export, operation, arguments)
                else:
                    execution = await manager.invoke_tool(grant, name, arguments)
                    output = execution.output
                result = {"content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False)}], "structuredContent": output, "isError": False}
            except SharingError as error:
                result = {"content": [{"type": "text", "text": str(error)}], "isError": True}
            except Exception:
                result = {"content": [{"type": "text", "text": "Shared capability operation failed."}], "isError": True}
        elif method == "notifications/initialized":
            return None
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @router.post("/{grant_id}/mcp")
    async def mcp(grant_id: str, message: dict[str, Any], authorization: str | None = Header(default=None)):
        manager, grant = authorize(grant_id, authorization)
        async with manager.acquire(grant):
            response = await mcp_call(manager, grant, message)
        return Response(status_code=202) if response is None else JSONResponse(response)

    @router.get("/{grant_id}/mcp")
    def mcp_get(grant_id: str, authorization: str | None = Header(default=None)):
        authorize(grant_id, authorization)
        return Response(status_code=405, headers={"Allow": "POST"})

    return router
