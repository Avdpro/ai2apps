"""Local control API for AI2Apps Remote Access v1."""

from __future__ import annotations

import base64
import io
from dataclasses import asdict

import httpx
import qrcode
import qrcode.image.svg
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from ai2apps.api.errors import platform_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.remote import RemoteAccessError


class RegisterRemoteDeviceRequest(BaseModel):
    display_name: str = Field(alias="displayName", min_length=1, max_length=120)


def _pairing_qr_data_url(value: str) -> str:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
        box_size=8,
        border=4,
    )
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
    output = io.BytesIO()
    image.save(output)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


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


def create_remote_router(runtime_provider: PlatformRuntimeProvider) -> APIRouter:
    router = APIRouter(prefix="/remote", tags=["platform-remote"])

    def manager():
        runtime = runtime_provider()
        value = None if runtime is None else getattr(runtime, "remote", None)
        if value is None:
            raise RemoteAccessError(503, "remote_not_ready", "Remote Access is not ready")
        return value

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
    async def register(request: RegisterRemoteDeviceRequest):
        result = await run(manager().register(display_name=request.display_name))
        return result if isinstance(result, Response) else _device(result)

    @router.post("/devices/reconcile")
    async def reconcile():
        result = await run(manager().reconcile())
        return result if isinstance(result, Response) else {"devices": [_device(item) for item in result]}

    @router.post("/devices/{device_id}/credentials/rotate")
    async def rotate(device_id: str):
        result = await run(manager().rotate(device_id))
        return result if isinstance(result, Response) else _device(result)

    @router.post("/devices/{device_id}/pairing-challenges")
    async def pairing(device_id: str):
        result = await run(manager().pairing_challenge(device_id))
        if isinstance(result, Response):
            return result
        return {**result, "pairingQrDataUrl": _pairing_qr_data_url(result["pairingUrl"])}

    @router.post("/devices/{device_id}/revoke")
    async def revoke(device_id: str):
        return await run(manager().revoke(device_id))

    @router.post("/devices/{device_id}/start")
    async def start(device_id: str):
        result = await run(manager().start(device_id))
        return result if isinstance(result, Response) else _device(result)

    @router.post("/devices/{device_id}/stop")
    async def stop(device_id: str):
        result = await run(manager().stop(device_id))
        return result if isinstance(result, Response) else _device(result)

    @router.delete("/devices/{device_id}", status_code=204)
    async def redact(device_id: str):
        result = await run(manager().redact(device_id))
        return result if isinstance(result, Response) else Response(status_code=204)

    @router.get("/usage")
    async def usage():
        return await run(manager().usage())

    return router
