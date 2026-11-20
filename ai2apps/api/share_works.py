"""Trusted, mount- and owner-bound publication API. No browser or shell command API."""
import asyncio
import base64
import hashlib
import re
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from ai2apps.studio import StudioCapabilityBroker, StudioCapabilityError
from ai2apps.share_works.service import HOST, MINI
from ai2apps.share_works.cli import PublishError
from ai2apps.share_works.artifacts import MAX_INPUT


class Target(BaseModel):
    model_config=ConfigDict(extra='forbid')
    provider:Literal['hf','ms']
    repo:str=Field(default='',max_length=193)

class Publication(BaseModel):
    model_config=ConfigDict(extra='forbid')
    snapshot_id:str=Field(pattern=r'^[0-9a-f]{32}$')
    request_id:str=Field(pattern=r'^[A-Za-z0-9_-]{16,80}$')
    confirmed:bool=False

class SocialApproval(BaseModel):
    model_config=ConfigDict(extra='forbid')
    digest:str=Field(pattern=r'^[0-9a-f]{64}$')
    confirmed:Literal[True]


def create_share_works_router(runtime_provider,principal_provider):
    router=APIRouter(prefix='/studios/{studio_id}/mini-app-mounts/{mount_id}/share-works',tags=['share-works'])
    from ai2apps.api.identity import require_app_capability
    async def scope(studio_id:str,mount_id:str,principal=Depends(require_app_capability(principal_provider,'app.use'))):
        runtime=runtime_provider()
        try:
            mount=StudioCapabilityBroker(runtime).mounted_mini_app(studio_id,mount_id,principal=principal)
            if studio_id!=HOST or mount.declaration.get('id')!=MINI or mount.mount.get('app_key')!=HOST:raise PermissionError()
            runtime.share_works.authorize(principal.actor_user_id)
        except (PermissionError,StudioCapabilityError):raise HTTPException(403,'share_access_denied')
        return runtime,principal.actor_user_id

    async def checked(call,*args,**kwargs):
        try:
            value=call(*args,**kwargs)
            return await value if hasattr(value,'__await__') else value
        except PublishError as error:raise HTTPException(422,error.code)
        except PermissionError:raise HTTPException(403,'share_access_denied')
        except KeyError:raise HTTPException(404,'share_not_found')
        except (TimeoutError,asyncio.TimeoutError):raise HTTPException(504,'cli_timeout')
        except (ValueError,OSError):raise HTTPException(422,'share_operation_failed')

    @router.get('/preferences')
    async def preferences(context=Depends(scope)):
        runtime,owner=context
        return await checked(runtime.share_works.preferences,owner)

    @router.post('/social/drafts')
    async def social_prepare(destination:Literal['x','rednote']=Form(...),title:str=Form(''),
                             body:str=Form(''),files:list[UploadFile]=File(default=[]),context=Depends(scope)):
        runtime,owner=context
        try:
            sources=[(item.filename or '',item.file) for item in files]
            return await checked(runtime.share_works.social.prepare,owner,destination,title,body,sources)
        finally:
            for item in files:
                await item.close()

    @router.get('/social/drafts')
    async def social_history(context=Depends(scope)):
        runtime,owner=context
        service=runtime.share_works.social
        return {'items':[service.view(owner,draft) for draft in service.store.recent_social(owner)]}

    @router.get('/social/drafts/{draft_id}/media/{index}')
    async def social_media(draft_id:str,index:int,context=Depends(scope)):
        runtime,owner=context
        service=runtime.share_works.social
        draft=await checked(service.draft,owner,draft_id)
        if not 0<=index<len(draft['media']):
            raise HTTPException(404,'share_not_found')
        item=draft['media'][index]
        path=service.store.path(owner,draft_id)/item['name']
        return FileResponse(path,media_type=item['type'],filename=item['filename'],
                            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @router.post('/social/drafts/{draft_id}/publish')
    async def social_publish(draft_id:str,body:SocialApproval,context=Depends(scope)):
        runtime,owner=context
        return await checked(runtime.share_works.social.publish_x,owner,draft_id,body.digest,approved=body.confirmed)

    @router.post('/check')
    async def check(body:Target,context=Depends(scope)):
        runtime,owner=context
        return await checked(runtime.share_works.check,owner,body.provider,body.repo)

    @router.post('/prepare')
    async def prepare(provider:Literal['hf','ms']=Form(...),repo:str=Form(...),application_url:str=Form(...),
                      title:str=Form(''),export_id:str=Form(''),file:UploadFile|None=File(None),context=Depends(scope)):
        runtime,owner=context
        if bool(file)==bool(export_id):raise HTTPException(422,'one_artifact_required')
        if file:
            try:data=await file.read(MAX_INPUT+1);filename=file.filename or ''
            finally:await file.close()
        else:
            data,filename=await checked(runtime.share_works.export_input,owner,export_id)
        if not data or len(data)>MAX_INPUT:raise HTTPException(413,'artifact_size_limit')
        return await checked(runtime.share_works.prepare,owner,data,filename,title,provider,repo,application_url)

    @router.post('/publish')
    async def publish(body:Publication,context=Depends(scope)):
        runtime,owner=context
        return await checked(runtime.share_works.publish,owner,body.snapshot_id,body.request_id,body.confirmed)

    @router.get('/history')
    async def history(context=Depends(scope)):
        runtime,owner=context
        return {'items':[runtime.share_works.status(owner,row['request_id']) for row in runtime.share_works.store.recent(owner)]}

    @router.get('/publications/{request_id}')
    async def status(request_id:str,context=Depends(scope)):
        runtime,owner=context
        return await checked(runtime.share_works.status,owner,request_id)

    @router.post('/publications/{request_id}/cancel')
    async def cancel(request_id:str,context=Depends(scope)):
        runtime,owner=context
        record=await checked(runtime.share_works.store.get,'publications',owner,request_id)
        if record.get('task_id'):await checked(runtime.system_tasks.cancel,owner,record['task_id'])
        return {'cancel_requested':True,'uploaded_files_may_remain':record.get('dispatched',False)}

    @router.post('/publications/{request_id}/verify')
    async def verify(request_id:str,context=Depends(scope)):
        runtime,owner=context
        record=await checked(runtime.share_works.store.get,'publications',owner,request_id)
        # Verification is read-only. It never retries the upload/deployment.
        try:return await runtime.share_works.verify(owner,record)
        except Exception as error:
            from ai2apps.share_works.service import verification_failure
            reason,_=verification_failure(error)
            record['last_verification_error']=reason
            record['last_verification_exception']=type(error).__name__
            record['last_verification_detail_code']=getattr(error,'code',None) if re.fullmatch(r'[a-z][a-z0-9_]{1,80}',str(getattr(error,'code',''))) else ''
            runtime.share_works.store.save('publications',owner,request_id,record)
            raise HTTPException(422,reason) from error

    @router.get('/snapshots/{snapshot_id}/preview')
    async def preview(snapshot_id:str,context=Depends(scope)):
        runtime,owner=context
        snap=await checked(runtime.share_works.snapshot,owner,snapshot_id)
        folder=runtime.share_works.store.path(owner,snapshot_id)
        # Match the accepted HTML size, including self-contained image exports.
        path=folder/'index.html'
        if path.stat().st_size>MAX_INPUT:raise HTTPException(413,'preview_size_limit')
        raw=await asyncio.to_thread(path.read_bytes)
        if len(raw)>MAX_INPUT:raise HTTPException(413,'preview_size_limit')
        remaining=MAX_INPUT-len(raw)
        text=raw.decode('utf-8')
        # Self-contained image preview; rendered only in a sandbox without script,
        # forms, navigation or network access. Never serve user HTML as App HTML.
        import mimetypes
        def resource(match):
            nonlocal remaining
            name=match[2]
            if name in snap['manifest'] and name.lower().endswith(('.png','.jpg','.jpeg','.gif','.webp')):
                resource_path=folder/name
                if resource_path.stat().st_size>=2*1024*1024:return match[0]
                data=resource_path.read_bytes()
                if len(data)<2*1024*1024:
                    value=match[1]+'data:'+mimetypes.guess_type(name)[0]+';base64,'+base64.b64encode(data).decode()+match[3]
                    growth=len(value.encode('utf-8'))-len(match[0].encode('utf-8'))
                    if growth>remaining:raise HTTPException(413,'preview_size_limit')
                    remaining-=growth
                    return value
            return match[0]
        text=re.sub(r'''(src=["'])([^"']+)(["'])''',resource,text,flags=re.I)
        return {'html':text}
    return router
