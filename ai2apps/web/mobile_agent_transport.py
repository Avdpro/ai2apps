"""Prepared Mobile Agent transport. Not mounted by the production Shell.

The default-deny capability callback must be replaced by the future verified
App-session integration; a client header, body flag or URL never enables it.
"""
import re
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response

_ID = r'[A-Za-z0-9_-]{1,256}'
_PARAMS = rf'interactions/{_ID}/parameters'
_RULES = {
    'GET': ['owners', rf'browser-tasks/{_ID}',rf'interactions/{_ID}/handoff', _PARAMS, _PARAMS + r'/materials', _PARAMS + r'/setup/session', _PARAMS + rf'/search/{_ID}'],
    'PUT': [_PARAMS],
    'POST': [rf'browser-tasks/{_ID}', 'cancel', rf'interactions/{_ID}/respond', _PARAMS + r'/(?:submit|switch|search/prepare|audio|gallery|materials/upload|materials/gallery)'],
}

def allowed_control(method, path):
    return any(re.fullmatch(pattern, path) for pattern in _RULES.get(method, ()))


def create_mobile_agent_router(*, principal_provider, forward, enabled=lambda request, principal: False):
    """Build but do not mount. forward must preserve Platform's actor and guards.

    The shared forward callback receives a fixed Platform path, raw body and
    content type. It must never substitute an owner, Device or legacy API key.
    The App capability callback is server-owned and defaults to denial.
    """
    router = APIRouter(prefix='/v1/mobile')
    async def capability(request: Request, principal=Depends(principal_provider)):
        if not enabled(request, principal):
            raise HTTPException(403, 'Mobile App Agent authorization is not enabled')
        return principal

    async def relay(request, principal, method, path):
        body = await request.body()
        if len(body) > 32 * 1024 * 1024:
            raise HTTPException(413, 'Mobile Agent payload is too large')
        # No arbitrary headers, origins or target URL are forwarded.
        headers = {key: request.headers[key] for key in ('content-type', 'idempotency-key') if key in request.headers}
        result = await forward(principal=principal, method=method, path=path,
            query=request.url.query, body=body, headers=headers)
        return Response(result.content, status_code=result.status_code,
            media_type=result.headers.get('content-type', 'application/json'), headers={'Cache-Control':'no-store'})

    @router.get('/chat/threads/{thread_id}/agent-runs')
    async def history(request: Request, thread_id: str, principal=Depends(capability)):
        if not re.fullmatch(_ID, thread_id):
            raise HTTPException(404)
        return await relay(request, principal, 'GET', f'/sessions/{thread_id}/agent-runs')

    @router.api_route('/agent-runs/{run_id}/{control_path:path}', methods=['GET','POST','PUT'])
    async def control(request: Request, run_id: str, control_path: str, principal=Depends(capability)):
        if not re.fullmatch(_ID, run_id) or not allowed_control(request.method, control_path):
            raise HTTPException(404, 'Unsupported Mobile Agent control')
        return await relay(request, principal, request.method, f'/agent-runs/{run_id}/{control_path}')
    return router
