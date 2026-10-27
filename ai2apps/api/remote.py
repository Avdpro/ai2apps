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
from ai2apps.localization import normalize_locale


class TestNotificationRequest(BaseModel):
    event_id: str = Field(pattern=r"^[-a-zA-Z0-9_.:]{1,160}$")


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

    from ai2apps.api.mobile_agent_desktop import create_desktop_agent_router
    router.include_router(create_desktop_agent_router(runtime_provider, principal_provider))

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

    def visitor_assets(principal):
        from ai2apps.remote.visitor_assets import VisitorAssets
        mobile_owner(principal)
        return VisitorAssets(runtime_provider().database, principal.installation_id)

    @router.post('/visitor-space/html-ai')
    async def visitor_html_ai(body: dict, request: Request, principal=Depends(principal_provider)):
        import json
        import asyncio
        from ai2apps.remote.visitor_html_ai import messages, extract_document
        from starlette.concurrency import run_in_threadpool
        store=visitor_assets(principal)
        current=''
        try:
            if body.get('assetId'):
                meta,path=store.get(body['assetId'])
                if meta['kind']!='html': raise ValueError('请选择 HTML 素材')
                if meta['size']>128*1024: raise ValueError('现有 HTML 超过 AI 编辑上限 128 KB；手动导入仍支持 10 MB')
                current=path.read_text(encoding='utf-8')
            context=messages(body,current)
        except ValueError as error: raise HTTPException(422,str(error)) from None
        runtime=runtime_provider()
        model=runtime.model_manager.resolve_default_model('work_standard')
        if not model: raise HTTPException(409,'请先在模型设置中配置标准任务默认模型或 API Default 模型')
        headers={k:v for k,v in request.headers.items() if k.lower() in {'authorization','cookie','x-api-key','x-ai2apps-app-id','x-ai2apps-installation-id'}}
        try:
            async with asyncio.timeout(180):
                payload={'model':model,'messages':context,'stream':False,'max_tokens':12000}
                if str(model).startswith('cloud/'):
                    import uuid
                    from ai2apps.model_invocation import invoke_app_cloud_chat
                    response=await invoke_app_cloud_chat(runtime,payload,principal=principal,
                        session_id='visitor-html-'+uuid.uuid4().hex,consumer_app_id='ai2apps.remote')
                else:
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=request.app),base_url=str(request.base_url),timeout=180) as client:
                        response=await client.post('/v1/chat/completions',headers=headers,json=payload)
            if response.status_code>=400: raise HTTPException(502,f'AI 生成失败（HTTP {response.status_code}），原作品已保留')
            html=extract_document(json.loads(response.body) if hasattr(response,'body') else response.json())
            asset=await run_in_threadpool(store.put,'html',html.encode('utf-8'))
            return {'asset':asset,'model':model}
        except (ValueError, json.JSONDecodeError) as error: raise HTTPException(422,str(error)) from None
        except (httpx.HTTPError, TimeoutError): raise HTTPException(502,'模型连接失败或超时，原作品已保留') from None

    @router.post('/visitor-space/assets/{kind}')
    async def visitor_upload(kind: str, request: Request, principal=Depends(principal_provider)):
        from ai2apps.remote.visitor_assets import LIMITS
        from starlette.concurrency import run_in_threadpool
        store=visitor_assets(principal)
        if kind not in LIMITS: raise HTTPException(422,'未知素材类型')
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>LIMITS[kind]: raise HTTPException(413,'素材超过大小限制')
        try: return await run_in_threadpool(store.put,kind,bytes(data))
        except ValueError as error: raise HTTPException(422,str(error)) from None

    @router.post('/visitor-space/gallery')
    async def visitor_gallery(body: dict, principal=Depends(principal_provider)):
        from ai2apps.gallery import GalleryRepository
        from ai2apps.remote.visitor_assets import LIMITS
        from starlette.concurrency import run_in_threadpool
        store=visitor_assets(principal);runtime=runtime_provider()
        def copy_asset():
            _,path=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery',runtime.events).asset_path(principal.actor_user_id,body.get('assetId',''))
            kind=body.get('kind')
            if kind not in {'image','video'} or path.stat().st_size>LIMITS[kind]: raise ValueError('素材类型或大小不符合限制')
            return store.put(kind,path.read_bytes())
        try: return await run_in_threadpool(copy_asset)
        except ValueError as error: raise HTTPException(422,str(error)) from None

    @router.get('/visitor-space/assets/{asset_id}')
    async def visitor_asset(asset_id: str, principal=Depends(principal_provider)):
        from fastapi.responses import FileResponse
        from ai2apps.remote.visitor_assets import HTML_CSP
        try: meta,path=visitor_assets(principal).get(asset_id)
        except ValueError: raise HTTPException(404,'素材不存在') from None
        return FileResponse(path,media_type=meta['mime'],headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':HTML_CSP,'Referrer-Policy':'no-referrer'})

    @router.get("/visitor-space")
    async def visitor_settings(principal=Depends(principal_provider)):
        from ai2apps.remote.visitor_space import eligible_apps, app_gateway_ready
        state = visitor_state(principal).get(principal.installation_id)
        state['apps'] = eligible_apps(runtime_provider().extension_manager, principal)
        state['appGatewayReady'] = app_gateway_ready()
        from ai2apps.remote.visitor_assets import content_gateway_ready
        state['contentGatewayReady'] = content_gateway_ready()
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
            published = build_snapshot(state['draft'], eligible_apps(runtime_provider().extension_manager, principal), visitor_assets(principal))
            from ai2apps.remote.visitor_assets import published_asset_ids, content_gateway_ready
            if published_asset_ids(published) and not content_gateway_ready():
                raise ValueError('素材草稿可预览；公开素材通道需 Cloud 部署后启用，暂不能发布含素材的内容')
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
    async def mobile_apps(locale: str = "en", principal=Depends(principal_provider)):
        from ai2apps.remote.mobile_apps import MobileAppPolicy, LEGACY_APPS, package_gateway_ready
        from ai2apps.web.mobile_app_gateway import supported
        mobile_owner(principal)
        runtime = runtime_provider()
        policy = MobileAppPolicy(runtime.database)
        items = runtime.extension_manager.list_mobile_apps(
            principal=principal, locale=normalize_locale(locale)
        )
        return {"items": [{**item,
            "enabled": policy.enabled(principal.installation_id, item["app_key"]),
            "supported": item["app_key"] in LEGACY_APPS or supported(item),
            "requiresCloudUpgrade": item["app_key"] not in LEGACY_APPS and not package_gateway_ready(),
        } for item in items]}

    @router.put("/mobile-apps/{app_key}")
    async def update_mobile_app(app_key: str, body: MobileAppAccessRequest,
                                principal=Depends(principal_provider)):
        from ai2apps.remote.mobile_apps import MobileAppPolicy, LEGACY_APPS, package_gateway_ready
        from ai2apps.web.mobile_app_gateway import supported
        mobile_owner(principal)
        runtime = runtime_provider()
        item = next((item for item in runtime.extension_manager.list_mobile_apps(principal=principal)
                     if item["app_key"] == app_key), None)
        if item is None:
            raise HTTPException(404, "Mobile App not found")
        if body.enabled and app_key not in LEGACY_APPS:
            if not supported(item):
                raise HTTPException(409, "Mobile renderer not supported")
            if not package_gateway_ready():
                raise HTTPException(409, "Custom App remote transport is pending activation")
        MobileAppPolicy(runtime.database).set_enabled(principal.installation_id, app_key, body.enabled)
        return {"app_key": app_key, "enabled": body.enabled}

    def notification_owner(principal):
        mobile_owner(principal)
        installation = manager().identity_repository.get_installation()
        if (not installation or principal.actor_user_id != installation.core_user_id
                or principal.installation_id != installation.id):
            raise HTTPException(403, "Only this Desktop Owner can manage notifications")
        return manager().notifications

    @router.get("/notifications")
    async def notification_status(principal=Depends(principal_provider)):
        producer = notification_owner(principal)
        await producer.refresh_policy(force=True)
        return producer.status()

    @router.post("/notifications/test", status_code=202)
    async def notification_test(body: TestNotificationRequest, principal=Depends(principal_provider)):
        producer = notification_owner(principal)
        try:
            producer.enqueue(event_id=body.event_id, kind="system.notice",
                             target_id=body.event_id, app_id="ai2apps/desktop")
        except ValueError as error:
            raise HTTPException(409, str(error)) from None
        return producer.status()

    @router.post("/notifications/resume")
    async def notification_resume(principal=Depends(principal_provider)):
        producer = notification_owner(principal)
        try:
            producer.resume()
        except ValueError as error:
            raise HTTPException(409, str(error)) from None
        return producer.status()

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
