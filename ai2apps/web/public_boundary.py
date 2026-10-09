"""Deny internal routes on public Hosts, before endpoint authentication shortcuts."""
import ipaddress
from urllib.parse import urlsplit


def local_host(host):
    try:
        name = urlsplit('//' + host).hostname
        if name == 'localhost':
            return True
        address = ipaddress.ip_address(name or '')
        return address.is_loopback or address.is_private
    except ValueError:
        return False


class PublicDeviceBoundary:
    def __init__(self, app, manager_provider):
        self.app = app
        self.manager_provider = manager_provider

    async def __call__(self, scope, receive, send):
        if scope['type'] not in {'http', 'websocket'}:
            return await self.app(scope, receive, send)
        from ai2apps.web.owner_home_gateway import MARKER, public_allowed, leased_response
        from ai2apps.remote.owner_home import COOKIE
        from starlette.requests import HTTPConnection
        manager = self.manager_provider()
        hosts = [value.decode('latin1') for key, value in scope.get('headers', []) if key.lower() == b'host']
        host = hosts[0] if len(hosts) == 1 else ''
        if host and local_host(host):
            return await self.app(scope, receive, send)
        path = scope.get('path', '')
        method = scope.get('method', 'GET')
        public = {
            ('GET', '/mobile/space/session/complete'), ('GET', '/mobile/space/anonymous/complete'), ('GET', '/mobile/space/complete'), ('GET', '/mobile/space/home'),
            ('GET', '/mobile/space/assets/space.js'), ('GET', '/mobile/space/assets/space.css'),
            ('POST', '/v1/mobile/space/exchange'), ('GET', '/v1/mobile/space/bootstrap'), ('POST', '/v1/mobile/space/bootstrap'),
            ('GET', '/mobile/member/complete'), ('POST', '/v1/mobile/member-session/exchange'),
            ('GET', '/mobile/complete'), ('POST', '/v1/mobile/session/exchange'),
        }
        manager = self.manager_provider()
        known = manager is not None and any(
            urlsplit(item.public_origin).netloc.lower() == host.lower()
            for item in manager.repository.list())
        async def recover_navigation():
            # Only the Shell document can recover without authorization. Never
            # redirect API/resource requests or grant access to private content.
            if not (known and scope['type'] == 'http' and method == 'GET'
                    and path == '/mobile'
                    and 'text/html' in HTTPConnection(scope).headers.get('accept', '')):
                return False
            from starlette.responses import RedirectResponse
            device = next(item for item in manager.repository.list()
                          if urlsplit(item.public_origin).netloc.lower() == host.lower())
            target = manager.owner_home.urls.get(device.device_id, '')
            parsed = urlsplit(target)
            import re
            if not (parsed.scheme == 'https' and parsed.netloc == 'coder.ai2apps.com'
                    and re.fullmatch(r'/u/[0-9a-f-]{36}', parsed.path)
                    and parsed.query == 'entry=owner-home' and not parsed.fragment):
                target = '/mobile/member/complete'
            await RedirectResponse(target, status_code=303,
                                   headers={'Cache-Control':'no-store', 'Referrer-Policy':'no-referrer'})(scope,receive,send)
            return True

        allowed = known and scope['type'] == 'http' and (method, path) in public
        if known and scope['type'] == 'http' and method == 'GET' and path.startswith('/mobile/space/app/'):
            from ai2apps.remote.visitor_space import app_gateway_ready
            allowed = app_gateway_ready()  # Endpoint separately validates the visitor and published resource.
        # Existing Mobile URLs retain their own session/Origin checks. Never allow
        # internal APIs, even when a caller supplies an API key or admin cookie.
        if known and scope['type'] == 'http' and path.startswith('/mobile/static/') and method == 'GET':
            allowed = True  # Existing static handler has an exact asset allowlist.
        if known and not allowed and (path == '/mobile' or path.startswith('/mobile/') or path.startswith('/v1/mobile/')):
            from starlette.requests import HTTPConnection
            connection = HTTPConnection(scope)
            try:
                session = await manager.authorize_session(connection.cookies.get('ai2apps_mobile_session'))
                if session is not None:
                    device = manager.require_device(session.device_id)
                    allowed = urlsplit(device.public_origin).netloc.lower() == host.lower()
                    origin = connection.headers.get('origin')
                    if scope['type'] == 'websocket' or method not in {'GET', 'HEAD'}:
                        allowed = allowed and origin == device.public_origin
            except Exception:
                allowed = False
        if known and not allowed:
            connection = HTTPConnection(scope)
            token = connection.cookies.get(COOKIE)
            if token:
                try:
                    if scope['type'] != 'http' or not public_allowed(method, path):
                        raise ValueError('Owner App route denied')
                    record = await manager.owner_home.authorize(token)
                    device = manager.require_device(record.claims['device_id'])
                    if urlsplit(device.public_origin).netloc.lower() != host.lower():
                        raise ValueError('Owner Host mismatch')
                    if method not in {'GET','HEAD'} and connection.headers.get('origin') != device.public_origin:
                        raise ValueError('Owner Origin mismatch')
                    scope[MARKER] = (manager.owner_home, record)
                except Exception:
                    if await recover_navigation():
                        return
                    if scope['type'] == 'websocket':
                        return await send({'type':'websocket.close', 'code':1008})
                    from starlette.responses import JSONResponse
                    return await JSONResponse({'detail':'Owner Home authorization required'},status_code=401)(scope,receive,send)
                if method == 'POST' and path == '/v1/mobile/owner-home/logout':
                    # Authentication already passed. Logout must clear its cookie
                    # after revoking the very lease guarding all other responses.
                    return await self.app(scope,receive,send)
                from ai2apps.web.owner_studio_gateway import allowed as studio_allowed, application
                target = self.app
                if studio_allowed(method, path):
                    target = application()
                    scope = {**scope, 'headers': [(k, v) for k, v in scope.get('headers', [])
                             if k.lower() not in {b'authorization', b'x-api-key', b'cookie'}],
                             'state': {}}
                return await leased_response(target,scope,receive,send,manager.owner_home,record)
        if allowed:
            return await self.app(scope, receive, send)
        if await recover_navigation():
            return
        if scope['type'] == 'websocket':
            return await send({'type':'websocket.close', 'code':1008})
        from starlette.responses import JSONResponse
        return await JSONResponse({'detail':'Public route is not allowed'}, status_code=403,
                                  headers={'Cache-Control':'no-store'})(scope, receive, send)
