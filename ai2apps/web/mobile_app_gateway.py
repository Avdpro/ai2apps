"""Mount-bound transport for manifest-declared trusted host Apps.

Packages retain their opaque sandbox and context-only bridge. A host descriptor
is executable configuration and is accepted only from built-in definitions.
"""
import base64
from importlib import import_module
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request
from starlette.responses import Response


_APPS = {}

def supported(item):
    return item.get('mobile_renderer') == 'sandbox' or bool(item.get('mobile_gateway'))


def descriptor(manager, mount):
    if mount.get('source') != 'builtin' or mount.get('renderer') != 'host':
        return None
    # Resolve only the registered definition, never request-provided metadata.
    with manager.database.transaction() as db:
        row = db.execute('SELECT d.manifest_json FROM app_instances i JOIN app_definitions d ON d.id=i.app_definition_id WHERE i.id=?', (mount['app_instance_id'],)).fetchone()
    import json
    mobile = json.loads(row['manifest_json']).get('mobile', {}) if row else {}
    value = mobile.get('gateway')
    return value if mobile.get('ready') and isinstance(value, dict) else None


def resource_url(mount, resource):
    from urllib.parse import quote
    return f"/mobile/app-resource/{quote(mount['id'], safe='')}/{quote(mount['app_instance_id'], safe='')}/{resource}"


def asset_response(spec, resource):
    from starlette.responses import FileResponse
    relative = resource.removeprefix('assets/')
    if relative not in spec.get('assets', []):
        raise HTTPException(404, 'App resource not declared')
    root = Path(__file__).parent / 'static'
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise HTTPException(404, 'App resource not found')
    return FileResponse(path, headers={'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'})


async def api_response(runtime, principal, spec, body):
    if not isinstance(body, dict) or set(body) - {'method','verb','path','body','headers'}:
        raise HTTPException(422, 'Invalid App request')
    verb = body.get('verb', 'GET')
    path = body.get('path', '')
    parsed = urlsplit(path)
    prefix = spec['api']['prefix']
    if verb not in {'GET','POST','PUT','PATCH','DELETE'} or parsed.scheme or parsed.netloc or not (parsed.path == prefix or parsed.path.startswith(prefix + '/')) or '..' in parsed.path or '\\' in path or '#' in path:
        raise HTTPException(403, 'App API scope denied')
    if not isinstance(body.get('body', ''), str) or len(body.get('body', '')) > 29 * 1024 * 1024:
        raise HTTPException(413, 'App body too large')
    try:
        content = base64.b64decode(body.get('body', ''), validate=True)
    except (ValueError, TypeError):
        raise HTTPException(422, 'Invalid App body')
    if len(content) > 21 * 1024 * 1024:
        raise HTTPException(413, 'App body too large')
    headers = body.get('headers') or {}
    if not isinstance(headers, dict) or any(key.lower() not in {'content-type','x-intelligence-language','x-ai2apps-app-instance'} for key in headers):
        raise HTTPException(403, 'App header denied')
    key = (id(runtime), spec['api']['module'], spec['api']['factory'])
    if key not in _APPS:
        async def actor(request: Request):
            return request.state.mobile_app_principal
        app = FastAPI()
        factory = getattr(import_module('ai2apps.api.' + spec['api']['module']), spec['api']['factory'])
        app.include_router(factory(lambda: runtime, actor), prefix='/v1/platform')
        _APPS[key] = app
    app = _APPS[key]
    async def scoped(scope, receive, send):
        scope.setdefault('state', {})['mobile_app_principal'] = principal
        await app(scope, receive, send)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=scoped), base_url='http://app.local', timeout=None) as client:
        result = await client.request(verb, path, headers=headers, content=content)
    return result


async def bridge(runtime, principal, spec, body):
    result = await api_response(runtime, principal, spec, body)
    return {'status':result.status_code, 'contentType':result.headers.get('content-type','application/octet-stream'),
            'body':base64.b64encode(result.content).decode('ascii')}


async def api_resource(runtime, principal, spec, resource, query):
    result = await api_response(runtime, principal, spec, {'verb':'GET', 'path':spec['api']['prefix'] + '/' + resource.removeprefix('api/') + (('?' + query) if query else '')})
    return Response(result.content, result.status_code, media_type=result.headers.get('content-type'), headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
