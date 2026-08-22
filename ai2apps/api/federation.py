"""Cloud Federation relay ingress for explicitly exported Local capabilities."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from ai2apps.identity import IdentityRepository
from ai2apps.core import utc_now
from ai2apps.remote import RemoteTokenError, verify_federation_relay_token
from ai2apps.services.models import ToolCallContext
from ai2apps.sharing import CapabilityKind, ShareGrant, SharingError
from ai2apps.sharing.agent_connector import invoke_agent_connector, resolve_agent_connector

from .health import PlatformRuntimeProvider


def create_federation_ingress_router(
    runtime_provider: PlatformRuntimeProvider, *, model_chat_handler=None,
) -> APIRouter:
    router = APIRouter(prefix="/federation", tags=["federation-ingress"])
    jwks_cache: dict[str, Any] = {"value": None, "expires": 0.0}

    def runtime_or_error():
        runtime = runtime_provider()
        if runtime is None or runtime.database is None or runtime.cloud is None or runtime.sharing is None:
            raise HTTPException(status_code=503, detail={"code": "federation_not_ready"})
        return runtime

    async def jwks(runtime):
        if jwks_cache["value"] is not None and float(jwks_cache["expires"]) > time.monotonic():
            return jwks_cache["value"]
        try:
            response = await runtime.cloud.request("GET", "/v1/federation/jwks.json")
            try:
                response.raise_for_status()
                value = response.json()
            finally:
                await response.aclose()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=503, detail={"code": "federation_jwks_unavailable"}) from exc
        if not isinstance(value, dict) or not isinstance(value.get("keys"), list):
            raise HTTPException(status_code=502, detail={"code": "federation_jwks_invalid"})
        jwks_cache.update(value=value, expires=time.monotonic() + 300)
        return value

    async def authorize(
        export_id: str, authorization: str | None, request_id: str | None,
        ancestor_header: str | None,
    ):
        runtime = runtime_or_error()
        if not authorization or not authorization.startswith("Relay ") or not request_id:
            raise HTTPException(status_code=401, detail={"code": "federation_relay_auth_required"})
        ancestors = tuple(value.strip() for value in (ancestor_header or "").split(",") if value.strip())
        installation = IdentityRepository(runtime.database).get_installation()
        if installation is None or installation.status != "active":
            raise HTTPException(status_code=503, detail={"code": "installation_not_active"})
        try:
            claims = verify_federation_relay_token(
                authorization.removeprefix("Relay ").strip(), await jwks(runtime),
                installation_id=installation.id, export_id=export_id,
                request_id=request_id, ancestor_node_ids=ancestors,
            )
        except RemoteTokenError as exc:
            raise HTTPException(status_code=401, detail={"code": "federation_relay_invalid", "message": str(exc)}) from exc
        return runtime, claims

    @router.post("/models/{export_id:path}")
    async def invoke_model(
        export_id: str, payload: dict[str, Any], request: Request,
        authorization: str | None = Header(default=None),
        request_id: str | None = Header(default=None, alias="X-AI2Apps-Request-Id"),
        ancestors: str | None = Header(default=None, alias="X-AI2Apps-Ancestor-Node-Ids"),
    ):
        runtime, _claims = await authorize(export_id, authorization, request_id, ancestors)
        if payload.get("model") != export_id:
            raise HTTPException(status_code=409, detail={"code": "federation_export_mismatch"})
        if not any(
            item.status == "active" and item.kind is CapabilityKind.MODEL and item.target_id == export_id
            for item in runtime.sharing.list_exports()
        ):
            raise HTTPException(status_code=404, detail={"code": "federation_export_not_found"})
        if model_chat_handler is None:
            raise HTTPException(status_code=503, detail={"code": "model_gateway_unavailable"})
        return await model_chat_handler(payload, request, None)

    @router.post("/mcp/{export_id:path}")
    async def invoke_mcp(
        export_id: str, message: dict[str, Any],
        authorization: str | None = Header(default=None),
        request_id: str | None = Header(default=None, alias="X-AI2Apps-Request-Id"),
        ancestors: str | None = Header(default=None, alias="X-AI2Apps-Ancestor-Node-Ids"),
    ):
        runtime, claims = await authorize(export_id, authorization, request_id, ancestors)
        if message.get("method") != "tools/call":
            raise HTTPException(status_code=405, detail={"code": "federation_mcp_method_not_allowed"})
        params = message.get("params") or {}
        name, arguments = params.get("name"), params.get("arguments") or {}
        if name != export_id or not isinstance(arguments, dict):
            raise HTTPException(status_code=409, detail={"code": "federation_export_mismatch"})
        active_exports = tuple(export for export in runtime.sharing.list_exports() if export.status == "active")
        selected = None
        for export in active_exports:
            if export.status != "active" or export.kind not in {CapabilityKind.TOOL, CapabilityKind.SERVICE}:
                continue
            if any(tool.qualified_name == export_id for tool in runtime.sharing.tools_for_export(export)):
                selected = export
                break
        agent_export, agent_operation = resolve_agent_connector(active_exports, export_id)
        if selected is None and agent_export is None:
            raise HTTPException(status_code=404, detail={"code": "federation_export_not_found"})
        try:
            if agent_export is not None:
                now = utc_now()
                grant = ShareGrant(
                    id=f"federation:{claims['node_link_id']}", label="Cloud Federation",
                    status="active", max_concurrency=1, max_requests=None, expires_at=None,
                    created_by_user_id=claims["sub"], request_count=0, last_used_at=None,
                    created_at=now, updated_at=now, exports=(agent_export,),
                )
                output = invoke_agent_connector(runtime.sharing, grant, agent_export, agent_operation, arguments)
            else:
                execution = await runtime.tools.execute(
                    export_id, arguments,
                    context=ToolCallContext(
                        caller_id=f"federation:{claims['node_link_id']}",
                        actor_user_id=claims["sub"],
                        installation_id=claims["downstream_installation_id"],
                        trace_id=request_id,
                    ),
                )
                output = execution.output
            result = {
                "content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False)}],
                "structuredContent": output, "isError": False,
            }
        except Exception:
            result = {"content": [{"type": "text", "text": "Federated capability operation failed."}], "isError": True}
        return JSONResponse({"jsonrpc": "2.0", "id": message.get("id"), "result": result})

    @router.post("/{kind}/{export_id:path}/cancel", status_code=202)
    async def cancel(
        kind: str, export_id: str,
        authorization: str | None = Header(default=None),
        request_id: str | None = Header(default=None, alias="X-AI2Apps-Request-Id"),
        ancestors: str | None = Header(default=None, alias="X-AI2Apps-Ancestor-Node-Ids"),
    ):
        if kind not in {"models", "mcp"}:
            raise HTTPException(status_code=404, detail={"code": "federation_export_not_found"})
        await authorize(export_id, authorization, request_id, ancestors)
        # Closing the Cloud relay request cancels a streaming model generator.
        # Stateful Agent Runs remain explicitly cancellable through the exported
        # agent.*.cancel MCP connector.
        return Response(status_code=202)

    return router
