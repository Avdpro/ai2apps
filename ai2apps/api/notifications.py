"""Read-only notification target resolution through the current Local session."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool
from ai2apps.api.identity import require_app_capability
from ai2apps.remote.notification_host import NotificationHost, routes
from ai2apps.core import ResourceNotFoundError


class NotificationTargetRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    target:dict


def create_notification_router(runtime_provider,principal_provider):
    router=APIRouter(prefix='/notifications',tags=['notifications'],dependencies=[Depends(require_app_capability(principal_provider,'app.use'))])
    @router.post('/resolve-target')
    async def resolve(body:NotificationTargetRequest,principal=Depends(principal_provider)):
        runtime=runtime_provider()
        def check():
            host=NotificationHost(runtime)
            host._owner(principal)
            return {**routes(runtime).resolve(principal,body.target),
                    "source_device_id":host.producer.identity()["device_id"]}
        try:
            return await run_in_threadpool(check)
        except (ValueError,KeyError,ResourceNotFoundError):
            raise HTTPException(403,'Notification target unavailable or not authorized') from None
    return router
