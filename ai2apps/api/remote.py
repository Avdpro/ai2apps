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


class MobileAppAccessRequest(BaseModel):
    enabled: bool


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

    def mobile_owner(principal):
        if not principal.is_core or principal.authentication_type in {"owner_home_lease", "remote_session"}:
            raise HTTPException(403, "Manage Mobile Apps from the device Owner account")
        return principal

    def visitor_state(principal):
        from ai2apps.remote.visitor_space import VisitorSpaceStore
        mobile_owner(principal)
        return VisitorSpaceStore(runtime_provider().database)

    @router.get("/visitor-space")
    async def visitor_settings(principal=Depends(principal_provider)):
        from ai2apps.remote.visitor_space import eligible_apps, app_gateway_ready
        state = visitor_state(principal).get(principal.installation_id)
        state['apps'] = eligible_apps(runtime_provider().extension_manager, principal)
        state['appGatewayReady'] = app_gateway_ready()
        import uuid
        try:
            user_id = str(uuid.UUID(principal.actor_user_id))
        except (ValueError, TypeError, AttributeError):
            user_id = None
        state['userUrl'] = 'https://coder.ai2apps.com/u/' + user_id if user_id else None
        state['qr'] = svg_qr_data_url(state['userUrl']) if state['userUrl'] else None
        return state

    @router.put("/visitor-space/draft")
    async def visitor_draft(body: dict, principal=Depends(principal_provider)):
        try:
            return visitor_state(principal).update(principal.installation_id, body.get('version'), draft=body.get('draft', {}))
        except ValueError as error:
            raise HTTPException(409, str(error)) from None

    @router.post("/visitor-space/publish")
    async def visitor_publish(body: dict, principal=Depends(principal_provider)):
        from ai2apps.remote.visitor_space import build_snapshot, eligible_apps
        store = visitor_state(principal)
        try:
            state = store.get(principal.installation_id)
            published = build_snapshot(state['draft'], eligible_apps(runtime_provider().extension_manager, principal))
            result = store.update(principal.installation_id, body.get('version'), published=published)
        except ValueError as error:
            raise HTTPException(409, str(error)) from None

        manager().space.revoke()
        await manager().refresh_space_capability()
        return result

    @router.put("/visitor-space/enabled")
    async def visitor_enabled(body: dict, principal=Depends(principal_provider)):
        store = visitor_state(principal)
        if type(body.get('enabled')) is not bool:
            raise HTTPException(422, 'Invalid enabled value')
        try:
            result = store.update(principal.installation_id, body.get('version'), enabled=body['enabled'])
        except ValueError as error:
            raise HTTPException(409, str(error)) from None
        manager().space.revoke()
        await manager().refresh_space_capability()
        return result

    @router.get("/mobile-apps")
    async def mobile_apps(principal=Depends(principal_provider)):
        from ai2apps.remote.mobile_apps import MobileAppPolicy, LEGACY_APPS, package_gateway_ready
        mobile_owner(principal)
        runtime = runtime_provider()
        policy = MobileAppPolicy(runtime.database)
        items = runtime.extension_manager.list_mobile_apps(principal=principal)
        return {"items": [{**item,
            "enabled": policy.enabled(principal.installation_id, item["app_key"]),
            "supported": item["app_key"] in LEGACY_APPS or item.get("mobile_renderer") == "sandbox",
            "requiresCloudUpgrade": item["app_key"] not in LEGACY_APPS and not package_gateway_ready(),
        } for item in items]}

    @router.put("/mobile-apps/{app_key}")
    async def update_mobile_app(app_key: str, body: MobileAppAccessRequest,
                                principal=Depends(principal_provider)):
        from ai2apps.remote.mobile_apps import MobileAppPolicy, LEGACY_APPS, package_gateway_ready
        mobile_owner(principal)
        runtime = runtime_provider()
        item = next((item for item in runtime.extension_manager.list_mobile_apps(principal=principal)
                     if item["app_key"] == app_key), None)
        if item is None:
            raise HTTPException(404, "Mobile App not found")
        if body.enabled and app_key not in LEGACY_APPS:
            if item.get("mobile_renderer") != "sandbox":
                raise HTTPException(409, "Mobile renderer not supported")
            if not package_gateway_ready():
                raise HTTPException(409, "Custom App remote transport is pending activation")
        MobileAppPolicy(runtime.database).set_enabled(principal.installation_id, app_key, body.enabled)
        return {"app_key": app_key, "enabled": body.enabled}

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
