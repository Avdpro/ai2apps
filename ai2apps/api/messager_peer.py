"""Narrow public ingress for Cloud-authorized Messager Noise exchanges."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.messager.peer_service import MessagerPeerError


def create_messager_peer_ingress_router(
    runtime_provider: PlatformRuntimeProvider,
) -> APIRouter:
    router = APIRouter(tags=["messager-peer"])

    async def bounded_json(request: Request) -> dict[str, Any]:
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > 32_768:
                raise MessagerPeerError(
                    "MESSAGER_REQUEST_TOO_LARGE",
                    "Peer request exceeds the 32 KiB limit.",
                    status_code=413,
                )
        try:
            payload = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MessagerPeerError(
                "MESSAGER_REQUEST_INVALID", "Peer request JSON is invalid."
            ) from error
        if not isinstance(payload, dict):
            raise MessagerPeerError(
                "MESSAGER_REQUEST_INVALID", "Peer request must be an object."
            )
        return payload

    def service():
        runtime = runtime_provider()
        selected = None if runtime is None else getattr(runtime, "messager_peer", None)
        if selected is None:
            raise MessagerPeerError(
                "MESSAGER_NOT_READY", "Messager peer transport is not ready.", status_code=503, retryable=True
            )
        return selected

    def service_v2():
        runtime = runtime_provider()
        selected = None if runtime is None else getattr(runtime, "messager_peer_v2", None)
        if selected is None:
            raise MessagerPeerError(
                "MESSAGER_NOT_READY", "Messager Peer v2 is not ready.", status_code=503, retryable=True
            )
        return selected

    def bearer(request: Request) -> str:
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer ") or not 1 <= len(authorization[7:]) <= 8192:
            raise MessagerPeerError("PEER_GRANT_REQUIRED", "A Peer Grant is required.", status_code=401)
        return authorization[7:]

    def error_response(error: MessagerPeerError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": error.code,
                    "message": str(error),
                    "retryable": error.retryable,
                }
            },
            headers={"Cache-Control": "no-store"},
        )

    @router.post("/v1/messager/peer/v1/handshakes", status_code=201)
    async def accept_handshake(request: Request):
        try:
            return await service().accept_handshake(await bounded_json(request))
        except MessagerPeerError as error:
            return error_response(error)

    @router.post("/v1/messager/peer/v1/messages")
    async def accept_message(request: Request):
        try:
            return await service().accept_message(await bounded_json(request))
        except MessagerPeerError as error:
            return error_response(error)

    @router.post("/v1/messager/peer/v2/handshakes", status_code=201)
    async def accept_handshake_v2(request: Request):
        try:
            return await service_v2().accept_handshake(bearer(request), await bounded_json(request))
        except MessagerPeerError as error:
            return error_response(error)

    @router.post("/v1/messager/peer/v2/messages")
    async def accept_message_v2(request: Request):
        try:
            return await service_v2().accept_message(bearer(request), await bounded_json(request))
        except MessagerPeerError as error:
            return error_response(error)

    return router
