"""Desktop-only management of user-owned network access."""
import json
import os
import tempfile
from fastapi import APIRouter, Depends, HTTPException, Request
from ai2apps.qr import svg_qr_data_url
from ai2apps.remote.self_managed import configuration


def create_self_managed_router(runtime_provider, principal_provider):
    router = APIRouter(prefix='/self-managed-access')

    def service(request: Request, actor=Depends(principal_provider)):
        from ai2apps.http_security import enforce_same_origin_cookie_request
        enforce_same_origin_cookie_request(request)
        if not actor.is_core or actor.authentication_type not in {'offline_session','local_session','cloud_session'}:
            raise HTTPException(403, 'Manage network access from Desktop')
        if request.client is None or request.client.host not in {'127.0.0.1','::1'}:
            raise HTTPException(403, 'Desktop loopback required')
        return runtime_provider().self_managed_access

    @router.get('')
    def status(access=Depends(service)):
        return access.status()

    @router.put('')
    async def configure(body: dict, access=Depends(service)):
        try:
            candidate = configuration(body)
            access.owner()
            await access.stop()
            access.path.unlink(missing_ok=True)
            access.config = candidate
            await access.start()
            fd, name = tempfile.mkstemp(dir=access.path.parent, prefix='.private-access-')
            try:
                with os.fdopen(fd,'w') as output:
                    json.dump(candidate,output)
                os.replace(name,access.path)
            finally:
                if os.path.exists(name): os.unlink(name)
            return access.status()
        except (ValueError,OSError) as error:
            access.error = str(error)
            raise HTTPException(400, str(error)) from error

    @router.delete('')
    async def disable(access=Depends(service)):
        await access.stop()
        access.path.unlink(missing_ok=True)
        access.config = None
        return access.status()

    @router.post('/pairing')
    def pairing(access=Depends(service)):
        try:
            url = access.invite()
            return {'url':url,'qr':svg_qr_data_url(url),'expiresIn':300}
        except ValueError as error:
            raise HTTPException(409,str(error)) from error

    @router.post('/pairing/{request_id}/approve')
    def approve(request_id: str, access=Depends(service)):
        access.status()
        row = next((v for v in access.pending.values() if v['id']==request_id),None)
        if row is None: raise HTTPException(404, 'Pairing request expired')
        row['approved'] = True
        return {'approved':True}

    @router.delete('/devices/{device_id}')
    async def revoke(device_id: str, access=Depends(service)):
        for record in access.sessions.values():
            if record.id == device_id: await access.revoke(record)
        return access.status()
    return router
