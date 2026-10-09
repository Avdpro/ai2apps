"""Narrow in-process App forwarding and lease-bound response lifetime."""
import asyncio
import re

from ai2apps.remote.security import RemoteTokenError

MARKER = 'ai2apps_owner_home_authority'
CHAT_APP = 'ai2apps.general-chat'
from ai2apps.remote.mobile_apps import LEGACY_APPS as OWNER_APPS
PUBLIC_METHODS = {
    'GET': re.compile(r'^(?:/mobile|/mobile/chat|/v1/mobile/(?:apps|mounts|models|chat/(?:state|threads|threads/[^/]+/content)|owner-home/status))$'),
    'POST': re.compile(r'^(?:/v1/mobile/(?:apps/ai2apps\.general-chat/open|app-instances/[^/]+/focus|chat/(?:threads|completions)|owner-home/(?:activity|logout)))$'),
    'PUT': re.compile(r'^/v1/mobile/chat/threads/[^/]+/content$'),
    'DELETE': re.compile(r'^/v1/mobile/mounts/[^/]+$'),
}
_runtime = _models = _completion = None


def configure(runtime_provider, models_handler, completion_handler):
    global _runtime, _models, _completion
    _runtime, _models, _completion = runtime_provider, models_handler, completion_handler


def public_allowed(method, path):
    from ai2apps.web.owner_studio_gateway import STUDIO_APPS, allowed
    if method == 'POST' and re.fullmatch(r'/v1/mobile/apps/[A-Za-z0-9._-]+/open', path):
        return True
    if method == 'GET' and re.fullmatch(r'/mobile/app-resource/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/.+', path):
        return True
    if method == 'POST' and re.fullmatch(r'/v1/mobile/app-mounts/[A-Za-z0-9_-]+/bridge', path):
        return True
    if allowed(method, path):
        return True
    if method == "GET" and path in {"/mobile/app-content/" + key for key in STUDIO_APPS | {"ai2apps.gallery"}}:
        return True
    if method == "GET" and re.fullmatch(r"/mobile/app-content/studio-resource/[A-Za-z0-9_-]+/.+", path):
        return True
    if method == "POST" and path in {"/v1/mobile/apps/" + key + "/open" for key in STUDIO_APPS}:
        return True
    if method == 'GET' and re.fullmatch(r'(?:/mobile/(?:knowledge|gallery)|/v1/mobile/knowledge/(?:buckets|items(?:/[A-Za-z0-9_-]+)?)|/v1/mobile/gallery/(?:collections|assets(?:/[A-Za-z0-9_-]+/content)?))',path):
        return True
    if method == 'POST' and (path in ('/v1/mobile/apps/ai2apps.knowledge/open','/v1/mobile/apps/ai2apps.gallery/open') or re.fullmatch(r'/v1/mobile/knowledge/items/[A-Za-z0-9_-]+/collect',path)):
        return True
    if method == 'GET' and path in ('/mobile/todo', '/v1/mobile/todo'):
        return True
    if method == 'POST' and path in ('/v1/mobile/apps/ai2apps.todo/open', '/v1/mobile/todo/tasks', '/v1/mobile/todo/directories'):
        return True
    if method == 'PUT' and re.fullmatch(r'/v1/mobile/todo/tasks/[A-Za-z0-9_-]+', path):
        return True
    pattern = PUBLIC_METHODS.get(method)
    return bool(pattern and pattern.fullmatch(path))


def authority(request):
    value = request.scope.get(MARKER)
    if value is None:
        return None
    runtime = _runtime() if _runtime else None
    manager = getattr(runtime, 'remote', None)
    if manager is None or value[0] is not manager.owner_home:
        raise RemoteTokenError('Owner gateway authority mismatch')
    value[0].valid(value[1])
    return value


def scoped(principal):
    return principal.authentication_type == 'owner_home_lease'


async def chat_proxy(request, method, path, payload=None):
    """Dispatch only Chat routes in an isolated app, never the main server."""
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import Response
    from ai2apps.api.chat import create_chat_router
    import httpx
    grant = authority(request)
    allowed = ((method == 'GET' and path in ('/chat', '/chat/threads'))
        or (method == 'POST' and path == '/chat/threads')
        or (method in ('GET','PUT') and re.fullmatch(r'/chat/threads/[A-Za-z0-9_-]+/content',path)))
    if grant is None or not allowed:
        raise HTTPException(403, 'Owner Chat route denied')
    def principal():
        return grant[0].principal(grant[1])
    isolated = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    isolated.include_router(create_chat_router(_runtime, principal_provider=principal))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=isolated), base_url='http://chat.internal') as client:
        response = await client.request(method,path,json=payload)
    grant[0].valid(grant[1])
    return Response(response.content,status_code=response.status_code,
        media_type=response.headers.get('content-type','application/json'),headers={'Cache-Control':'no-store'})


async def models(request):
    grant = authority(request)
    if grant is None or _models is None:
        raise RemoteTokenError('Owner model gateway unavailable')
    principal = grant[0].principal(grant[1])
    result = await _models(principal)
    if request.url.path == '/v1/mobile/models' and principal.is_core:
        from ai2apps.web.mobile_model_catalog import desktop_catalog_projection
        if hasattr(result, 'model_dump'):
            result = result.model_dump(mode='json')
        result = {**result, 'data': await desktop_catalog_projection(result.get('data', []))}
        grant[0].valid(grant[1])
    return result


async def completion(request, payload):
    grant = authority(request)
    if grant is None or _completion is None:
        raise RemoteTokenError('Owner Chat gateway unavailable')
    # Callback receives the verified actor directly, never an API key or cookie.
    principal = grant[0].principal(grant[1])
    request.state.ai2apps_principal = principal
    return await _completion(payload,request,principal)


async def leased_response(app, scope, receive, send, service, record):
    started = False
    finished = False
    async def guarded_send(message):
        nonlocal started, finished
        service.valid(record)
        if message['type'] == 'http.response.start':
            started = True
        if message['type'] == 'http.response.body' and not message.get('more_body',False):
            finished = True
        await send(message)
    async def deadline():
        while True:
            service.valid(record)
            import time
            await asyncio.sleep(max(0,min(.25,record.deadline-time.time())))
    task = asyncio.create_task(app(scope,receive,guarded_send))
    timer = asyncio.create_task(deadline())
    async def expired_response():
        if not started:
            from starlette.responses import JSONResponse
            await JSONResponse({'detail':'Owner Home lease expired'},status_code=401)(scope,receive,send)
        elif not finished:
            await send({'type':'http.response.body','body':b'','more_body':False})
    try:
        done,_ = await asyncio.wait((task,timer),return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            try:
                await task
            except RemoteTokenError:
                await expired_response()
        else:
            timer.exception()
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
            await expired_response()
    finally:
        task.cancel()
        timer.cancel()
        await asyncio.gather(task,timer,return_exceptions=True)
