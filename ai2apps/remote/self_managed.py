"""User-owned VPN/tunnel ingress. Never issues a Desktop login credential."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, replace
import hashlib
import ipaddress
import json
import logging
import secrets
import socket
import time
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from ai2apps.remote.security import RemoteTokenError

COOKIE = 'ai2apps_private_mobile'


def configuration(value):
    mode = value.get('mode')
    address = ipaddress.ip_address(value.get('bind', ''))
    port = value.get('port')
    origin = value.get('origin', '').rstrip('/')
    parsed = urlsplit(origin)
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Port must be between 1024 and 65535')
    if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or not parsed.hostname:
        raise ValueError('Enter an origin only, without path or credentials')
    if mode == 'tunnel':
        if not address.is_loopback or parsed.scheme != 'https':
            raise ValueError('Tunnel mode requires a loopback bind address and an HTTPS origin')
    elif mode == 'vpn':
        if address.is_unspecified or address.is_multicast or address.is_loopback:
            raise ValueError('Select the specific VPN interface IP address')
        if parsed.scheme != 'http' or parsed.hostname != str(address) or parsed.port != port:
            raise ValueError('VPN origin must match the bound IP and port (http://IP:port)')
    else:
        raise ValueError('Select vpn or tunnel')
    return dict(mode=mode, bind=str(address), port=port, origin=origin)


@dataclass
class MobileSession:
    id: str
    name: str
    actor: object
    deadline: float
    absolute: float
    idle: float
    claims: dict
    activity: float | None = None
    revoked: bool = False


class SelfManagedAccess:
    def __init__(self, runtime, path):
        logging.getLogger(__name__).info("Self-managed access loaded from %s", __file__)
        self.runtime, self.path = runtime, Path(path)
        self.config = None
        self.sessions, self.pending, self.invitations = {}, {}, {}
        self.urls = {}
        self.server = self.task = None
        self.error = None
        if self.path.exists():
            try:
                self.config = configuration(json.loads(self.path.read_text()))
            except (OSError, ValueError, TypeError, AttributeError):
                self.error = 'Network access configuration is invalid; save it again on Desktop'

    def owner(self):
        actor = self.runtime.legacy_api_key_principal()
        if not actor.is_core or actor.authentication_type == 'legacy_api_key':
            raise ValueError('Activate offline mode or sign in on Desktop first')
        return actor

    def valid(self, record):
        owner = self.owner()
        if (not self.server or record.revoked or time.time() >= record.deadline
                or (owner.actor_user_id, owner.installation_id, owner.membership_epoch) != (record.actor.actor_user_id, record.actor.installation_id, record.actor.membership_epoch)):
            raise RemoteTokenError('Phone session ended; pair again on Desktop')
        return record

    def principal(self, record):
        self.valid(record)
        # Reuse the restricted Mobile App gateway, not Local administrator auth.
        return replace(record.actor, authentication_type='owner_home_lease', client_scope='owner-home')

    async def revoke(self, record):
        record.revoked = True

    def status(self):
        now = time.time()
        self.pending = {k:v for k,v in self.pending.items() if v['expires'] > now}
        self.sessions = {k:v for k,v in self.sessions.items() if not v.revoked and v.deadline > now}
        return {'config': self.config, 'running': bool(self.task and not self.task.done()), 'error': self.error,
                'pending': [{k:v for k,v in row.items() if k in {'id','name','code','expires','approved'}} for row in self.pending.values()],
                'devices': [{'id':r.id,'name':r.name,'expires':r.deadline} for r in self.sessions.values() if not r.revoked and r.deadline > now]}

    def invite(self):
        self.owner()
        if not self.server:
            raise ValueError('Enable network access first')
        token = secrets.token_urlsafe(32)
        self.invitations = {hashlib.sha256(token.encode()).hexdigest(): time.time()+300}
        return self.config['origin'] + '/pair#' + token

    async def stop(self):
        for record in self.sessions.values():
            record.revoked = True
        self.sessions.clear(); self.pending.clear(); self.invitations.clear()
        if self.server:
            self.server.should_exit = True
        if self.task:
            try:
                await asyncio.wait_for(asyncio.shield(self.task), 5)
            except asyncio.TimeoutError:
                self.task.cancel()
                await asyncio.gather(self.task, return_exceptions=True)
        self.server = self.task = None

    async def start(self):
        if not self.config:
            return
        self.owner()
        import uvicorn
        family = socket.AF_INET6 if ':' in self.config['bind'] else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            sock.bind((self.config['bind'], self.config['port']))
            sock.listen(128); sock.setblocking(False)
            self.server = uvicorn.Server(uvicorn.Config(self.application(), lifespan='off', access_log=False, proxy_headers=False, log_level='warning'))
            from contextlib import nullcontext
            self.server.capture_signals = nullcontext
            self.task = asyncio.create_task(self.server.serve(sockets=[sock]))
            for _ in range(100):
                if self.server.started:
                    self.error = None
                    return
                if self.task.done():
                    await self.task
                    raise ValueError('Listener failed to start')
                await asyncio.sleep(.02)
            raise ValueError('Listener startup timed out')
        except BaseException:
            sock.close()
            await self.stop()
            raise

    def application(self, target_app=None):
        service = self
        pairing = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

        @pairing.get('/pair')
        async def page():
            return HTMLResponse((Path(__file__).parents[1]/'web/templates/private_pair.html').read_text(), headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer', 'Content-Security-Policy':"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"})

        async def body_json(request):
            data = bytearray()
            async for chunk in request.stream():
                data.extend(chunk)
                if len(data) > 4096:
                    raise HTTPException(413, 'Pairing request too large')
            try:
                value = json.loads(data)
                if not isinstance(value, dict): raise ValueError()
                return value
            except (ValueError, TypeError):
                raise HTTPException(400, 'Invalid pairing request') from None

        @pairing.post('/pair/request')
        async def claim(request: Request):
            body = await body_json(request)
            token = str(body.get('token',''))
            expiry = service.invitations.pop(hashlib.sha256(token.encode()).hexdigest(), 0)
            if expiry <= time.time():
                raise HTTPException(401, 'QR code expired or already scanned. Generate a new code on Desktop.')
            service.owner()
            service.status()
            if len(service.pending) >= 32 or len(service.sessions) >= 128:
                raise HTTPException(429, 'Too many paired devices or pending requests')
            proof = secrets.token_urlsafe(32)
            key = hashlib.sha256(proof.encode()).hexdigest()
            service.pending[key] = {'id':secrets.token_hex(16), 'name':str(body.get('name') or 'Phone')[:80], 'code':str(secrets.randbelow(1000000)).zfill(6),'expires':time.time()+300,'approved':False}
            return {'proof':proof, 'code':service.pending[key]['code']}

        @pairing.post('/pair/finish')
        async def finish(request: Request):
            body = await body_json(request)
            key = hashlib.sha256(str(body.get('proof','')).encode()).hexdigest()
            row = service.pending.get(key)
            if not row or row['expires'] <= time.time():
                raise HTTPException(401, 'Pairing expired; scan a new QR code')
            if not row['approved']:
                return JSONResponse({'waiting':True}, status_code=202)
            del service.pending[key]
            token = secrets.token_urlsafe(48)
            now = time.time(); expires = now+8*3600
            actor = service.owner()
            service.sessions[hashlib.sha256(token.encode()).hexdigest()] = MobileSession(row['id'],row['name'],actor,expires,expires,expires,{'device_id':'self-managed'})
            response = JSONResponse({'connected':True})
            response.set_cookie(COOKIE, token, httponly=True, secure=service.config['mode']=='tunnel', samesite='strict', max_age=8*3600)
            response.headers['Cache-Control'] = 'no-store'
            return response

        async def ingress(scope, receive, send):
            from starlette.requests import HTTPConnection
            from ai2apps.web.owner_home_gateway import MARKER, public_allowed, leased_response
            from ai2apps.web.owner_studio_gateway import allowed, application
            async def deny(status):
                if scope['type'] == 'websocket':
                    await send({'type':'websocket.close','code':1008})
                else:
                    await JSONResponse({'detail':'Pair this phone from Desktop to access this address'},status_code=status)(scope,receive,send)
            if scope['type'] not in {'http','websocket'}:
                return
            connection = HTTPConnection(scope)
            expected = urlsplit(service.config['origin'])
            hosts = [v.decode() for k,v in scope['headers'] if k.lower()==b'host']
            if hosts != [expected.netloc]:
                return await deny(403)
            method, path = scope.get('method','GET'), scope['path']
            if (method not in {'GET','HEAD'} or scope['type']=='websocket') and connection.headers.get('origin') != service.config['origin']:
                return await deny(403)
            if path in {'/pair','/pair/request','/pair/finish'} and scope['type']=='http':
                return await pairing(scope,receive,send)
            record = service.sessions.get(hashlib.sha256(connection.cookies.get(COOKIE,'').encode()).hexdigest())
            try:
                if record is None: raise RemoteTokenError('Pair required')
                service.valid(record)
            except (RemoteTokenError,ValueError):
                return await deny(401)
            if scope['type']=='websocket' or not (public_allowed(method,path) or (method=='GET' and path.startswith('/mobile/static/'))):
                return await deny(403)
            # Strip ambient credentials; the unforgeable in-process authority is
            # the only identity accepted by the Mobile gateway.
            forwarded = {**scope, MARKER:(service,record), 'state':{},
                'headers':[(k,v) for k,v in scope['headers'] if k.lower() not in {b'authorization',b'cookie',b'x-api-key',b'host',b'origin',b'forwarded',b'x-forwarded-host',b'x-forwarded-proto',b'x-forwarded-for'}]+[(b'host',b'127.0.0.1')]}
            if target_app is None:
                from omlx.server import app
            else:
                app = target_app
            target = application() if allowed(method,path) else app
            return await leased_response(target,forwarded,receive,send,service,record)
        return ingress
