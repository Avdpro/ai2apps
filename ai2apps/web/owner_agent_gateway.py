"""Unified Owner Mobile adapter; reuses exact Agent transport and owner checks."""
import re
from fastapi import Request, HTTPException
from starlette.responses import JSONResponse
from ai2apps.remote.mobile_unified import authorized
from ai2apps.web import mobile_agent_gateway as agent

PREFIX = '/v1/mobile/owner-agent'


def allowed(method, path):
    if not path.startswith(PREFIX + '/'):
        return False
    relative = path[len(PREFIX):]
    return bool(agent.business_target(method, relative) or method == 'GET' and (
        relative == '/models' or re.fullmatch(r'/(?:assets/' + agent._ID + r'/\d+/\d+|(?:artifacts|files)/' + agent._ID + r'/' + agent._ID + r')', relative)))


async def application(scope, receive, send):
    from ai2apps.web.owner_home_gateway import authority, _runtime, _models
    request = Request(scope, receive=receive)
    try:
        grant = authority(request)
        if grant is None or not authorized(grant[1].claims):
            raise HTTPException(403, 'Unified Mobile authorization required')
        method, path = scope['method'], scope['path']
        if not allowed(method, path) or scope.get('raw_path', path.encode()) != path.encode('ascii'):
            raise HTTPException(403, 'Noncanonical Mobile Agent path')
        chunks = []; size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 21 * 1024 * 1024:
                raise HTTPException(413)
            chunks.append(chunk)
        body = b''.join(chunks)
        principal = grant[0].principal(grant[1])
        relative = path[len(PREFIX):]
        runtime = _runtime()
        if relative == '/models':
            value = await _models(principal)
            response = JSONResponse(value.model_dump(mode='json') if hasattr(value, 'model_dump') else value)
        elif relative.startswith('/assets/'):
            response = await agent.result_image(runtime, principal, relative)
        elif relative.startswith('/files/'):
            response = await agent.generated_file(runtime, principal, relative)
        elif relative.startswith('/artifacts/'):
            response = await agent.generated_image(runtime, principal, relative)
        else:
            response = await agent.dispatch(runtime, principal, method, agent.business_target(method, relative), body,
                {k:request.headers[k] for k in ('content-type','idempotency-key') if k in request.headers},
                scope.get('query_string', b'').decode('ascii'))
        grant[0].valid(grant[1])
    except HTTPException as error:
        response = JSONResponse({'detail': error.detail}, status_code=error.status_code)
    await response(scope, receive, send)
