"""Principal-isolated Local Messager history APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ai2apps.api.errors import platform_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import (
    PrincipalProvider,
    require_app_capability,
    resolve_request_principal,
)
from ai2apps.apps.access import APP_SYSTEM_MANAGE
from ai2apps.identity import RequestPrincipal
from ai2apps.messager import MessagerRepository
from ai2apps.messager.peer_service import MessagerPeerError
from ai2apps.peer.broker import PeerBrokerError


def _message_payload(row: dict) -> dict:
    return {
        "id": row["id"],
        "peerUserId": row["peer_user_id"],
        "direction": row["direction"],
        "transport": row["transport"],
        "status": row["status"],
        "body": row["body"],
        "clientMessageId": row["client_message_id"],
        "remoteMessageId": row["remote_message_id"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "attachment": (
            None
            if row["attachment_id"] is None
            else {
                "id": row["attachment_id"],
                "mediaType": row["attachment_media_type"],
                "byteSize": row["attachment_byte_size"],
                "width": row["attachment_width"],
                "height": row["attachment_height"],
                "contentPath": row["attachment_content_path"],
            }
        ),
    }


def create_messager_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(prefix="/messager", tags=["platform-messager"])
    principal_dependency = Depends(principal_provider)

    def repository() -> MessagerRepository | JSONResponse:
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        events = None if runtime is None else getattr(runtime, "events", None)
        if database is None:
            return platform_error_response(
                status_code=503,
                code="platform_not_ready",
                message="Messager persistence is not ready.",
                retryable=True,
            )
        return MessagerRepository(database, events)

    @router.get("/conversations")
    def list_conversations(
        limit: int = Query(default=100, ge=1, le=100),
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        items = selected.list_conversations(principal.actor_user_id, limit=limit)
        return {
            "items": [
                {
                    "id": row["id"],
                    "peerUserId": row["peer_user_id"],
                    "lastBody": row["last_body"],
                    "lastStatus": row["last_status"],
                    "createdAt": row["created_at"],
                    "updatedAt": row["updated_at"],
                }
                for row in items
            ]
        }

    @router.get("/conversations/{peer_user_id}/messages")
    def list_messages(
        peer_user_id: str,
        limit: int = Query(default=200, ge=1, le=500),
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return {
            "items": [
                _message_payload(row)
                for row in selected.list_messages(
                    principal.actor_user_id,
                    peer_user_id,
                    limit=limit,
                )
            ]
        }

    @router.post("/send")
    async def send_local_first(
        payload: dict,
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = runtime_provider()
        peer_v1 = None if runtime is None else getattr(runtime, "messager_peer", None)
        peer_v2 = None if runtime is None else getattr(runtime, "messager_peer_v2", None)
        if peer_v1 is None:
            return platform_error_response(
                status_code=503,
                code="messager_not_ready",
                message="Messager peer transport is not ready.",
                retryable=True,
            )
        required = {"recipientUserId", "clientMessageId", "body"}
        if set(payload) != required or not all(
            isinstance(payload.get(name), str) and payload[name]
            for name in required
        ) or len(payload["body"]) > 4000:
            return platform_error_response(
                status_code=422,
                code="messager_request_invalid",
                message="Messager send fields are invalid.",
            )
        try:
            if peer_v2 is None:
                return await peer_v1.send_local(
                    principal=principal, recipient_user_id=payload["recipientUserId"],
                    client_message_id=payload["clientMessageId"], body=payload["body"],
                )
            return await peer_v2.send_local(
                principal=principal,
                recipient_user_id=payload["recipientUserId"],
                client_message_id=payload["clientMessageId"],
                body=payload["body"],
            )
        except PeerBrokerError as error:
            if error.code != "PEER_POLICY_DISABLED":
                return platform_error_response(
                    status_code=error.status_code, code=error.code.lower(),
                    message=str(error), retryable=error.retryable,
                )
            try:
                return await peer_v1.send_local(
                    principal=principal, recipient_user_id=payload["recipientUserId"],
                    client_message_id=payload["clientMessageId"], body=payload["body"],
                )
            except MessagerPeerError as error:
                return platform_error_response(
                    status_code=error.status_code, code=error.code.lower(),
                    message=str(error), retryable=error.retryable,
                )
        except MessagerPeerError as error:
            if error.code != "MESSAGER_RESULT_UNKNOWN" and error.retryable:
                try:
                    return await peer_v1.send_local(
                        principal=principal, recipient_user_id=payload["recipientUserId"],
                        client_message_id=payload["clientMessageId"], body=payload["body"],
                    )
                except MessagerPeerError as fallback_error:
                    error = fallback_error
            return platform_error_response(
                status_code=error.status_code,
                code=error.code.lower(),
                message=str(error),
                retryable=error.retryable,
            )

    @router.post(
        "/device-key/rotate",
        dependencies=[
            Depends(require_app_capability(principal_provider, APP_SYSTEM_MANAGE))
        ],
    )
    async def rotate_device_key(
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = runtime_provider()
        peer = None if runtime is None else getattr(runtime, "messager_peer", None)
        if peer is None:
            return platform_error_response(
                status_code=503,
                code="messager_not_ready",
                message="Messager peer transport is not ready.",
                retryable=True,
            )
        try:
            registered = await peer.rotate_device_key(principal)
        except MessagerPeerError as error:
            return platform_error_response(
                status_code=error.status_code,
                code=error.code.lower(),
                message=str(error),
                retryable=error.retryable,
            )
        return JSONResponse(
            {
                "deviceId": registered["deviceId"],
                "keyId": registered.get("keyId"),
                "status": registered["status"],
            },
            headers={"Cache-Control": "no-store"},
        )

    return router
