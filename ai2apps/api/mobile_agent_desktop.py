"""Loopback administrator pairing controls; never exported through Mobile."""
import httpx
import ipaddress
import hashlib
import secrets
import time
from urllib.parse import urlsplit
from fastapi import APIRouter,Depends,HTTPException,Request
from ai2apps.http_security import has_local_session_cookie
from ai2apps.qr import svg_qr_data_url
from ai2apps.remote.security import RemoteTokenError


def create_desktop_agent_router(runtime_provider,principal_provider):
    router=APIRouter(prefix='/mobile-agent');tickets={}
    def admin(request:Request,principal=Depends(principal_provider)):
        try:
            peer=ipaddress.ip_address(request.client.host)
            host=ipaddress.ip_address(request.url.hostname)
            local=peer.is_loopback and host.is_loopback
        except ValueError:local=request.url.hostname=='localhost' and request.client.host in ('127.0.0.1','::1')
        runtime=runtime_provider()
        reader=getattr(runtime,'local_session_token_from_cookies',None)
        token=reader(request.cookies) if reader else None
        verified=runtime.authorize_local_session(token) if token else None
        if not token or verified!=principal:raise HTTPException(403,'An actual Local administrator session is required')
        request.state.mobile_agent_admin_digest=hashlib.sha256(token.encode()).hexdigest()
        if not local or not has_local_session_cookie(request) or not principal.is_core or principal.authentication_type in ('legacy_api_key','owner_home_lease','remote_session','desktop_approved_agent'):
            raise HTTPException(403,'Confirm Mobile Agent access in the local administrator session')
        if request.method not in ('GET','HEAD'):
            if request.headers.get('origin')!=str(request.base_url).rstrip('/'):
                raise HTTPException(403,'Local confirmation Origin mismatch')
            ticket=tickets.get(request.headers.get('x-ai2apps-desktop-confirm',''))
            if not ticket or ticket[1]<=time.monotonic() or ticket[0]!=principal or ticket[2]!=request.state.mobile_agent_admin_digest:
                raise HTTPException(403,'Local confirmation token required')
        return principal
    def service():return runtime_provider().remote.mobile_agent
    @router.get('/confirmation')
    def confirmation(request:Request,principal=Depends(admin)):
        now=time.monotonic()
        for token,item in list(tickets.items()):
            if item[1]<=now:tickets.pop(token,None)
        token=secrets.token_urlsafe(32);tickets[token]=(principal,now+60,request.state.mobile_agent_admin_digest)
        return {'token':token,'expiresIn':60}
    async def invoke(action):
        try:return await action
        except RemoteTokenError as error:raise HTTPException(409,str(error)) from error
        except httpx.HTTPError as error:raise HTTPException(503,'Cloud is unavailable; Agent authorization was not activated') from error
        except Exception as error:
            from ai2apps.remote import RemoteAccessError
            if isinstance(error,RemoteAccessError):raise HTTPException(error.status_code,{'code':error.code,'message':str(error)}) from error
            raise
    @router.get('/{device}/status')
    def status(device:str,principal=Depends(admin)):
        return service().status(device)
    @router.post('/{device}/configure')
    async def configure(device:str,body:dict,principal=Depends(admin)):
        if type(body.get('enabled')) is not bool:raise HTTPException(422,'enabled must be boolean')
        return await invoke(service().configure(device,body['enabled']))
    @router.post('/{device}/pairings')
    async def create(device:str,principal=Depends(admin)):
        result=await invoke(service().create(device))
        return {**result,'pairingQrDataUrl':svg_qr_data_url(result['pairingUrl'])}
    @router.get('/{device}/pairings/{connection}')
    async def pairing(device:str,connection:str,principal=Depends(admin)):
        return await invoke(service().pairing(device,connection))
    @router.post('/{device}/pairings/{connection}/decision')
    async def decision(device:str,connection:str,body:dict,principal=Depends(admin)):
        if body.get('humanConfirmed') is not True:raise HTTPException(422,'Explicit confirmation required')
        return await invoke(service().decision(device,connection,body.get('decision'),body.get('expectedGeneration'),body.get('disconnectOtherClients',False)))
    @router.post('/{device}/pairings/{connection}/ack')
    async def ack(device:str,connection:str,principal=Depends(admin)):
        async with service().lock:return await invoke(service().ack(device,connection))
    @router.post('/{device}/revoke')
    async def revoke(device:str,principal=Depends(admin)):
        return await invoke(service().revoke(device))
    return router
