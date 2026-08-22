"""Local control API for AI2Apps Remote Access v1."""

from __future__ import annotations

from dataclasses import asdict

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ai2apps.api.errors import platform_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import (
    PrincipalProvider,
    require_app_capability,
    resolve_request_principal,
)
from ai2apps.apps.access import APP_SYSTEM_MANAGE
from ai2apps.cloud_client import AI2APPS_CLOUD_BROWSER_COOKIE
from ai2apps.qr import svg_qr_data_url
from ai2apps.remote import RemoteAccessError


class RegisterRemoteDeviceRequest(BaseModel):
    display_name: str = Field(alias="displayName", min_length=1, max_length=120)


def _device(value) -> dict:
    result = asdict(value)
    return {
        "deviceId": result["device_id"], "displayName": result["display_name"],
        "platform": result["platform"], "clientVersion": result["client_version"],
        "status": result["status"], "suspensionReason": result["suspension_reason"],
        "accessEpoch": result["access_epoch"], "publicOrigin": result["public_origin"],
        "credentialVersion": result["credential_version"],
        "credentialExpiresAt": result["credential_expires_at"].isoformat(),
        "serverAddr": result["server_addr"], "serverPort": result["server_port"],
        "proxyName": result["proxy_name"], "subdomain": result["subdomain"],
        "enabled": result["enabled"], "online": result["online"],
        "proxyConnected": result["proxy_connected"],
        "lastSeenAt": None if result["last_seen_at"] is None else result["last_seen_at"].isoformat(),
        "createdAt": result["created_at"].isoformat(), "updatedAt": result["updated_at"].isoformat(),
    }


def create_remote_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(
        prefix="/remote",
        tags=["platform-remote"],
        dependencies=[
            Depends(require_app_capability(principal_provider, APP_SYSTEM_MANAGE))
        ],
    )

    def manager():
        runtime = runtime_provider()
        value = None if runtime is None else getattr(runtime, "remote", None)
        if value is None:
            raise RemoteAccessError(503, "remote_not_ready", "Remote Access is not ready")
        return value

    def browser_cloud(
        request: Request,
    ):
        runtime = runtime_provider()
        cookie_reader = (
            None
            if runtime is None
            else getattr(runtime, "cloud_browser_session_from_cookies", None)
        )
        browser_session_id = (
            cookie_reader(request.cookies)
            if cookie_reader is not None
            else request.cookies.get(AI2APPS_CLOUD_BROWSER_COOKIE)
        )
        resolver = (
            None if runtime is None else getattr(runtime, "cloud_for_browser", None)
        )
        if resolver is None:
            cloud = None if runtime is None else getattr(runtime, "cloud", None)
        else:
            try:
                cloud = resolver(browser_session_id or "")
            except (RuntimeError, ValueError):
                cloud = None
        if cloud is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "cloud_browser_session_required",
                    "message": "Sign in to AI2Apps Cloud in this browser first",
                },
            )
        return cloud

    browser_cloud_dependency = Depends(browser_cloud)

    async def run(operation):
        try:
            return await operation
        except RemoteAccessError as error:
            return platform_error_response(
                status_code=error.status_code, code=error.code.lower(), message=str(error),
                retryable=error.status_code >= 500 or error.status_code == 429,
            )
        except httpx.TimeoutException:
            return platform_error_response(status_code=504, code="cloud_timeout", message="AI2Apps Cloud did not respond in time", retryable=True)
        except httpx.HTTPError:
            return platform_error_response(status_code=502, code="cloud_unavailable", message="AI2Apps Cloud is unavailable", retryable=True)

    @router.get("/status")
    async def status():
        value = manager()
        return {"devices": [_device(item) for item in value.repository.list()],
                "connector": value.frpc.status()}

    @router.post("/devices")
    async def register(
        request: RegisterRemoteDeviceRequest, cloud=browser_cloud_dependency
    ):
        result = await run(
            manager().register(display_name=request.display_name, cloud=cloud)
        )
        return result if isinstance(result, Response) else _device(result)

    @router.post("/devices/reconcile")
    async def reconcile(cloud=browser_cloud_dependency):
        result = await run(manager().reconcile(cloud=cloud))
        return result if isinstance(result, Response) else {"devices": [_device(item) for item in result]}

    @router.post("/devices/{device_id}/credentials/rotate")
    async def rotate(device_id: str, cloud=browser_cloud_dependency):
        result = await run(manager().rotate(device_id, cloud=cloud))
        return result if isinstance(result, Response) else _device(result)

    @router.post("/devices/{device_id}/pairing-challenges")
    async def pairing(device_id: str, cloud=browser_cloud_dependency):
        result = await run(manager().pairing_challenge(device_id, cloud=cloud))
        if isinstance(result, Response):
            return result
        return {**result, "pairingQrDataUrl": svg_qr_data_url(result["pairingUrl"])}

    @router.post("/devices/{device_id}/revoke")
    async def revoke(device_id: str, cloud=browser_cloud_dependency):
        return await run(manager().revoke(device_id, cloud=cloud))

    @router.post("/devices/{device_id}/start")
    async def start(device_id: str, cloud=browser_cloud_dependency):
        result = await run(manager().start(device_id, cloud=cloud))
        return result if isinstance(result, Response) else _device(result)

    @router.post("/devices/{device_id}/stop")
    async def stop(device_id: str):
        result = await run(manager().stop(device_id))
        return result if isinstance(result, Response) else _device(result)

    @router.delete("/devices/{device_id}", status_code=204)
    async def redact(device_id: str, cloud=browser_cloud_dependency):
        result = await run(manager().redact(device_id, cloud=cloud))
        return result if isinstance(result, Response) else Response(status_code=204)

    @router.get("/usage")
    async def usage(cloud=browser_cloud_dependency):
        return await run(manager().usage(cloud=cloud))

    return router
