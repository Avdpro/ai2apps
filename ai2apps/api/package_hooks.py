"""Authenticated host review and caller-bound Package requests/inbox."""
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from ai2apps.api.identity import require_app_capability
from ai2apps.events.hooks import HookError
from ai2apps.extensions import ExtensionError
from ai2apps.core import RepositoryError
from ai2apps.services import ToolGatewayError

class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    review_hash:str=Field(min_length=64,max_length=64)
    request_id:str=Field(min_length=8,max_length=128)


class GrantControl(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision:int=Field(ge=1)
    request_id:str=Field(min_length=8,max_length=128)


def create_package_hook_router(runtime_provider,principal_provider):
    router=APIRouter(prefix='/package-hooks',dependencies=[Depends(require_app_capability(principal_provider,'app.use'))])
    principal=Depends(principal_provider)
    def service():return runtime_provider().package_hooks
    def call(fn,*args,**kwargs):
        try:return fn(*args,**kwargs)
        except HookError as exc:raise HTTPException(404 if exc.code=='rule_not_found' else 409,{'code':exc.code,'message':str(exc)}) from exc
        except (PermissionError,ExtensionError,RepositoryError) as exc:raise HTTPException(403,'Package Hook access unavailable') from exc
        except (ValueError,TypeError,KeyError) as exc:raise HTTPException(422,'Invalid Package Hook request') from exc
    async def async_call(fn,*args,**kwargs):
        try:return await fn(*args,**kwargs)
        except (HookError,PermissionError,ExtensionError,RepositoryError) as exc:raise HTTPException(403,'Package Hook access unavailable') from exc
        except ToolGatewayError as exc:raise HTTPException(409,'Approved detail read is unavailable') from exc
        except (ValueError,TypeError,KeyError) as exc:raise HTTPException(422,'Invalid Package Hook request') from exc
    def host(p):
        if p.client_scope!='desktop':raise HTTPException(403,'Open permissions in the Local desktop host')
    def host_decision(request,p):
        host(p)
        # Opaque Package frames cannot forge this browser Origin or borrow the
        # host Session. No confirmation flags supplied by a Package are accepted.
        if request.headers.get('origin')!=str(request.base_url).rstrip('/'):
            raise HTTPException(403,'Consent decisions require the same-origin desktop host')
    @router.get('/requests')
    def requests(p=principal):host(p);return call(service().requests,p.actor_user_id)
    @router.get('/requests/{rid}')
    def review(rid:str,p=principal):host(p);return call(service().review,p.actor_user_id,rid)
    @router.post('/requests/{rid}/{choice}')
    def decide(rid:str,choice:str,body:Decision,request:Request,p=principal):
        host_decision(request,p);return call(service().decide,p,rid,choice,body.review_hash,body.request_id)
    @router.get('/grants')
    def grants(p=principal):host(p);return call(service().grants,p.actor_user_id)
    @router.post('/grants/{ref}/revoke')
    def revoke(ref:str,request:Request,p=principal):host_decision(request,p);return call(service().revoke,p.actor_user_id,ref)
    @router.post('/grants/{ref}/control/{operation}')
    def control(ref:str,operation:str,body:GrantControl,request:Request,p=principal):
        host_decision(request,p)
        return call(service().control,p.actor_user_id,ref,operation,body.expected_revision,body.request_id)
    async def data(request):
        raw=bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>16000:raise HTTPException(413,'Hook request is too large')
        import json
        try:return json.loads(raw)
        except (ValueError,UnicodeDecodeError):raise HTTPException(422,'Invalid Hook request') from None
    @router.post('/apps/{instance}/requests')
    async def request_app(instance:str,request:Request,p=principal):return call(service().request_app,p,instance,await data(request))
    @router.get('/apps/{instance}/inbox')
    async def inbox_app(instance:str,p=principal):
        b=call(service().current,p.actor_user_id,instance)
        return await async_call(service().inbox,p,b)
    @router.post('/apps/{instance}/deliveries/{delivery}/{operation}')
    async def delivery_app(instance:str,delivery:str,operation:str,p=principal):
        if operation not in ('ack','details'):raise HTTPException(404)
        b=call(service().current,p.actor_user_id,instance)
        return await async_call(service().inbox,p,b,**{'ack' if operation=='ack' else 'detail':delivery})
    @router.post('/mini-apps/{studio}/{mount}/requests')
    async def request_mini(studio:str,mount:str,request:Request,p=principal):return call(service().request_mini,p,studio,mount,await data(request))
    @router.get('/mini-apps/{studio}/{mount}/inbox')
    async def inbox_mini(studio:str,mount:str,p=principal):
        b=call(service().mini_binding,p,studio,mount)
        return await async_call(service().inbox,p,b)
    @router.post('/mini-apps/{studio}/{mount}/deliveries/{delivery}/{operation}')
    async def delivery_mini(studio:str,mount:str,delivery:str,operation:str,p=principal):
        if operation not in ('ack','details'):raise HTTPException(404)
        b=call(service().mini_binding,p,studio,mount)
        return await async_call(service().inbox,p,b,**{'ack' if operation=='ack' else 'detail':delivery})
    return router
