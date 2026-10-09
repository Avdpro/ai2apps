"""Personal space Open-Entry. Deliberately independent of internal App bridges."""
import logging
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
import httpx

from ai2apps.remote.security import RemoteTokenError
from ai2apps.remote.visitor_sessions import LeaseUnavailable

COOKIE = '__Secure-ai2apps_space'
HEADERS = {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
           'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"}


def create_space_router(manager_provider, mobile_renderer=None, extension_provider=None):
    router = APIRouter()

    def device_for(request):
        manager = manager_provider()
        device = next((device for device in manager.repository.list()
                       if request.headers.get('host', '').lower() == urlsplit(device.public_origin).netloc.lower()), None)
        if device is None:
            raise HTTPException(404, 'Personal space is unavailable')
        if request.method not in {'GET', 'HEAD'} and request.headers.get('origin') != device.public_origin:
            raise HTTPException(403, 'Personal space Origin is not allowed')
        return manager, device

    @router.get('/mobile/member/complete', response_class=HTMLResponse)
    async def member_entry(request: Request):
        manager, device = device_for(request)
        request.state.owner_home_url = manager.owner_home.urls.get(device.device_id)
        if mobile_renderer is None:
            raise HTTPException(503, 'Mobile Home is unavailable')
        response = mobile_renderer(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    @router.post('/v1/mobile/member-session/exchange')
    async def member_exchange(request: Request, payload: dict):
        from ai2apps.remote import RemoteAccessError
        manager, device = device_for(request)
        handoff = payload.get('handoff')
        if not isinstance(handoff, str) or not 24 <= len(handoff) <= 200:
            raise HTTPException(422, 'Invalid member handoff')
        try:
            token, session = await manager.owner_home.exchange(device, handoff)
        except RemoteTokenError as error:
            logging.getLogger(__name__).warning('Owner handoff validation failed: %s', error)
            raise HTTPException(401, 'Owner authorization must be restarted') from None
        except httpx.HTTPError:
            logging.getLogger(__name__).warning('Owner handoff Cloud transport failed')
            raise HTTPException(401, 'Owner authorization must be restarted') from None
        except RemoteAccessError as error:
            raise HTTPException(error.status_code, 'Owner authorization must be restarted') from None
        from ai2apps.remote.owner_home import COOKIE as OWNER_COOKIE
        import time
        response = JSONResponse({'connected': True}, headers={'Cache-Control': 'no-store'})
        response.set_cookie(OWNER_COOKIE, token, max_age=max(0, int(session.absolute-time.time())),
                            httponly=True, secure=True, samesite='strict', path='/')
        return response

    @router.get('/mobile/space/session/complete', response_class=HTMLResponse)
    @router.get('/mobile/space/anonymous/complete', response_class=HTMLResponse)
    @router.get('/mobile/space/complete', response_class=HTMLResponse)
    @router.get('/mobile/space/home', response_class=HTMLResponse)
    async def entry(request: Request):
        device_for(request)
        page = (Path(__file__).parent / 'templates/space.html').read_text()
        if request.url.path == '/mobile/space/session/complete':
            page = page.replace('data-visitor-public', 'data-visitor-public data-visitor-session')
        if request.url.path == '/mobile/space/anonymous/complete':
            page = page.replace('data-visitor-public', 'data-visitor-public data-anonymous')
        return HTMLResponse(page, headers=HEADERS)

    @router.get('/mobile/space/assets/{name}')
    async def asset(name: str):
        from fastapi.responses import Response
        if name not in {'space.js', 'space.css'}:
            raise HTTPException(404)
        folder, kind = ('js', 'text/javascript') if name.endswith('.js') else ('css', 'text/css')
        return Response((Path(__file__).parent / 'static' / folder / name).read_text(), media_type=kind,
                        headers={'Cache-Control': 'no-store'})

    @router.post('/v1/mobile/space/exchange')
    async def exchange(request: Request, payload: dict):
        manager, device = device_for(request)
        handoff = payload.get('handoff')
        if not isinstance(handoff, str) or not 24 <= len(handoff) <= 200:
            raise HTTPException(422, 'Invalid personal space handoff')
        try:
            anonymous = payload.get('protocol') == 'personal-space-anonymous-v1'
            session_protocol = payload.get('protocol') == 'personal-space-anonymous-session-v1'
            if 'protocol' in payload and not (anonymous or session_protocol):
                raise HTTPException(422, 'Invalid visitor protocol')
            if session_protocol:
                token, claims = await manager.space.visitor_sessions.exchange(device, handoff)
            else:
                token, claims = await manager.space.exchange(device, handoff, **({'anonymous': True} if anonymous else {}))
        except LeaseUnavailable:
            raise HTTPException(503, 'Visitor connection is recovering', headers={'Retry-After':'10'}) from None
        except (RemoteTokenError, httpx.HTTPError):
            raise HTTPException(401, 'Personal space login must be restarted') from None
        except Exception as error:
            from ai2apps.remote import RemoteAccessError
            if isinstance(error, RemoteAccessError):
                raise HTTPException(error.status_code, 'Personal space login must be restarted') from None
            raise
        response = JSONResponse({'connected': True}, headers={'Cache-Control': 'no-store'})
        from ai2apps.core import utc_now
        response.set_cookie(COOKIE, token, max_age=max(0, claims.get('absolute_expires_at', claims['exp']) - int(utc_now().timestamp())),
                            httponly=True, secure=True, samesite='strict', path='/')
        return response

    @router.get('/v1/mobile/owner-home/status')
    async def owner_status(request: Request):
        from ai2apps.web.owner_home_gateway import MARKER
        authority = request.scope.get(MARKER)
        if authority is None:
            raise HTTPException(401, 'Owner authorization required')
        service, record = authority
        service.valid(record)
        return JSONResponse({'authorized': True, 'leaseExpiresAt': record.deadline,
            'absoluteExpiresAt': record.absolute, 'idleExpiresAt': record.idle,
            'ownerAuthorizationUrl': service.urls.get(record.claims['device_id'])}, headers={'Cache-Control':'no-store'})

    @router.post('/v1/mobile/owner-home/activity')
    async def owner_activity(request: Request):
        from ai2apps.web.owner_home_gateway import MARKER
        import time
        authority = request.scope.get(MARKER)
        if authority is None:
            raise HTTPException(401, 'Owner authorization required')
        authority[0].valid(authority[1])
        authority[1].activity = time.time()
        return {'ok':True}

    @router.post('/v1/mobile/owner-home/logout')
    async def owner_logout(request: Request):
        from ai2apps.web.owner_home_gateway import MARKER
        from ai2apps.remote.owner_home import COOKIE as OWNER_COOKIE
        authority = request.scope.get(MARKER)
        if authority is None:
            raise HTTPException(401, 'Owner authorization required')
        try:
            await authority[0].revoke(authority[1])
        except Exception:
            pass  # Local revocation takes effect even if Cloud is unavailable.
        response = JSONResponse({'signedOut':True})
        response.delete_cookie(OWNER_COOKIE, secure=True, httponly=True, samesite='strict')
        return response

    async def visitor_authorize(manager, device, request):
        from ai2apps.remote.visitor_sessions import LeaseUnavailable
        try:
            return await manager.space.visitor_sessions.authorize(device, request.cookies.get(COOKIE),
                activity=request.method == 'POST')
        except LeaseUnavailable:
            raise HTTPException(503, 'Visitor connection is recovering', headers={'Retry-After':'10'}) from None

    @router.post('/v1/mobile/space/bootstrap')
    @router.get('/v1/mobile/space/bootstrap')
    async def bootstrap(request: Request):
        manager, device = device_for(request)
        try:
            claims = await visitor_authorize(manager, device, request)
        except RemoteTokenError:
            raise HTTPException(401, 'Personal space login must be restarted') from None
        settings = manager.space.visitor_settings(device)
        # Only the published snapshot; never Local principal or private mounts.
        from ai2apps.remote.owner_home import READY
        return JSONResponse({'mode': claims['access_mode'], 'expiresAt': claims['exp'],
                             'sessionProtocol': claims.get('protocol'), 'leaseVersion': claims.get('lease_version'),
                             'absoluteExpiresAt': claims.get('absolute_expires_at', claims['exp']),
                             'idleExpiresAt': claims.get('idle_expires_at', claims['exp']),
                             'space': settings['published'], 'revision': settings['revision'],
                             'userUrl': 'https://coder.ai2apps.com/u/' + claims['owner_user_id'],
                             'entries': [], 'ownerAuthorizationUrl': manager.owner_home.urls.get(device.device_id) if READY and claims['access_mode'] == 'owner' else None}, headers={'Cache-Control': 'no-store'})

    @router.get('/mobile/space/app/{revision}/{app_key}/{resource:path}')
    async def app_resource(request: Request, revision: int, app_key: str, resource: str):
        from ai2apps.remote.visitor_space import resolve_resource, app_gateway_ready
        from fastapi.responses import FileResponse
        manager, device = device_for(request)
        try:
            await visitor_authorize(manager, device, request)
            settings = manager.space.visitor_settings(device)
            if not app_gateway_ready() or revision != settings['revision']:
                raise ValueError('Visitor App unavailable')
            card = next(c for c in settings['published']['cards'] if c['kind'] == 'app' and c['appKey'] == app_key)
            if extension_provider is None:
                raise ValueError('Visitor App unavailable')
            path = resolve_resource(extension_provider(), card, resource)
        except (RemoteTokenError, ValueError, StopIteration):
            raise HTTPException(403, 'Visitor App access denied') from None
        origin = device.public_origin
        csp = (f"sandbox allow-scripts; default-src 'none'; script-src {origin} 'unsafe-inline'; "
               f"style-src {origin} 'unsafe-inline'; img-src {origin} data: blob:; font-src {origin}; "
               "connect-src 'none'; form-action 'none'; base-uri 'none'; frame-ancestors 'self'")
        return FileResponse(path, headers={'Cache-Control':'no-store', 'Content-Security-Policy':csp,
                                          'Referrer-Policy':'no-referrer', 'X-Content-Type-Options':'nosniff'})

    return router
