"""Intelligence-owned export jobs, observed/cancelled through existing System Tasks."""
import asyncio
import hashlib
import re
import time
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
from .transfer import selected_rows, export_backup, parse_time


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    channel_id: str | None = Field(default=None, max_length=256)
    format: Literal['zip','html'] = 'zip'
    since: str | None = Field(default=None, max_length=64)
    until: str | None = Field(default=None, max_length=64)
    changes: Literal['created','updated'] = 'updated'
    quality: Literal['reading','original'] = 'reading'
    include_toc: bool = True
    share_cover: str | None = Field(default=None,max_length=2048)
    request_id: str = Field(min_length=16,max_length=80,pattern=r'^[a-zA-Z0-9_-]+$')

    @model_validator(mode='after')
    def valid(self):
        if self.share_cover and not re.fullmatch(r'/v1/platform/intelligence/imports/[0-9a-f]{64}/share-cover.jpg',self.share_cover):raise ValueError('Invalid share cover')
        if self.share_cover and self.format!='html':raise ValueError('Share cover requires HTML')
        start,end=parse_time(self.since),parse_time(self.until)
        if start and end and start>=end: raise ValueError('Invalid time range')
        if self.format=='html' and not self.channel_id: raise ValueError('HTML requires one channel')
        return self


class ExportConflict(ValueError):pass


def existing_export(runtime,owner,request_id):
    with runtime.database.transaction() as db:
        row=db.execute("SELECT id FROM system_tasks WHERE owner=? AND app_id='ai2apps.intelligence' AND kind='intelligence.export' AND dedup_key=? ORDER BY created_at DESC LIMIT 1",(owner,'export:'+request_id)).fetchone()
    return runtime.system_tasks.get(owner,row['id']) if row else None


def submit_export(runtime,principal,request,*,author_name=None):
    """One owner submission service for the App and AaAT, with frozen scope."""
    from ai2apps.apps.access import has_app_capability
    if not has_app_capability(principal,'app.use'):raise PermissionError('Intelligence access required')
    if request.channel_id:runtime.intelligence_collector.store.get('channels',principal.actor_user_id,request.channel_id)
    existing=existing_export(runtime,principal.actor_user_id,request.request_id)
    if existing:
        if task_request(existing['payload']).model_dump()!=request.model_dump():raise ExportConflict('Export request ID already used with different options')
        return existing
    payload=request.model_dump()
    if author_name:payload['_author_name']=author_name
    return runtime.system_tasks.submit(principal.actor_user_id,'ai2apps.intelligence','intelligence.export',
        '导出情报 / Export intelligence',payload,dedup_key='export:'+request.request_id)


def completed_export(runtime,principal,task_id):
    from ai2apps.apps.access import has_app_capability
    if not has_app_capability(principal,'app.use'):raise PermissionError('Intelligence access required')
    owner=principal.actor_user_id;task=runtime.system_tasks.get(owner,task_id)
    if task['app_id']!='ai2apps.intelligence' or task['kind']!='intelligence.export':raise KeyError('Export not found')
    if task['status']!='completed':raise ValueError('Export is not ready')
    request=task_request(task['payload'])
    if request.channel_id:runtime.intelligence_collector.store.get('channels',owner,request.channel_id)
    kind=task['result'].get('format');path=file_path(runtime.intelligence_collector.store,owner,task_id,kind)
    if not path.is_file():raise ValueError('Export expired; create a new export')
    with path.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=task['result'].get('sha256'):raise ValueError('Export file changed')
    name=str(task['result'].get('channel_name') or 'intelligence').replace('/','_').replace('\\','_')[:120]+'-'+task_id[-8:]+'.'+kind
    return task,path,name


def save_export_to_gallery(runtime,principal,task_id):
    from ai2apps.gallery import GalleryRepository
    from .transfer import MAX_BYTES
    task,path,name=completed_export(runtime,principal,task_id)
    gallery=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery',runtime.events)
    with path.open('rb') as stream:
        asset,created=gallery.import_stream(principal.actor_user_id,stream,name=name,
            media_type='text/html' if task['result']['format']=='html' else 'application/zip',
            source_app_id='ai2apps.intelligence',source_ref=task_id,
            metadata={'export_task_id':task_id,'channel_id':task['payload'].get('channel_id')},max_bytes=MAX_BYTES)
    return {'asset':asset,'created':created,'export_id':task_id}


def file_path(store, owner, task_id, format):
    if not re.fullmatch(r'stask_[0-9a-f]{32}',task_id) or format not in ('zip','html'):
        raise ValueError('Invalid export reference')
    return store.root/'exports'/hashlib.sha256(owner.encode()).hexdigest()/(task_id+'.'+format)


async def export_author_name(runtime,owner,cloud=None):
    """Use only the authenticated export owner's display name, never email/ID."""
    if getattr(runtime,'offline_mode',False):return None
    cloud=cloud or getattr(runtime,'cloud',None)
    if cloud is None:return None
    response=None
    import httpx
    from ai2apps.secrets.backends import SecretBackendError
    try:
        async with asyncio.timeout(8):
            response=await cloud.request('GET','/v1/auth/me')
            if response.status_code!=200:return None
            user=response.json().get('user',{})
            if user.get('id')!=owner:return None
            name=user.get('displayName')
            return name.strip()[:120] if isinstance(name,str) and name.strip() else None
    except (TimeoutError,ValueError,TypeError,AttributeError,OSError,httpx.HTTPError,SecretBackendError):return None
    finally:
        if response is not None:await response.aclose()


def task_request(payload):
    return ExportRequest.model_validate({k:v for k,v in payload.items() if k!='_author_name'})


def register(runtime, principal_for):
    import logging
    logging.getLogger(__name__).info('ZIP/HTML export v20 gallery-aaat loaded from %s', __file__)
    from ai2apps.apps.access import has_app_capability
    from ai2apps.system_tasks import TaskHandler
    tasks=runtime.system_tasks;store=runtime.intelligence_collector.store
    def authorize(owner,payload):
        request=task_request(payload)
        if not has_app_capability(principal_for(owner),'app.use'): raise ValueError('Intelligence access required')
        if request.channel_id: store.get('channels',owner,request.channel_id)
    async def execute(ctx):
        from .html_export import build_html
        request=task_request(ctx.payload)
        ctx.report(message='正在准备导出 / Preparing export',progress={'stage':'snapshot'})
        scope={'since':request.since,'until':request.until,'changes':request.changes}
        if request.format=='zip':
            payload=await asyncio.to_thread(export_backup,store,ctx.owner,request.channel_id,**scope)
            info={}
        else:
            selected=await asyncio.to_thread(selected_rows,store,ctx.owner,request.channel_id,**scope)
            def report(progress):
                ctx.report(message=f"正在内嵌图片 / Embedding images {progress['images_done']}/{progress['images_total']}",progress={'stage':'images',**progress})
            label=('全部 / All' if not request.since and not request.until else f'{request.since or "…"} → {request.until or "…"}')
            author_name=ctx.payload.get('_author_name') or await export_author_name(runtime,ctx.owner)
            payload,info=await build_html(store,ctx.owner,selected,quality=request.quality,scope={'label':label},report=report,include_toc=request.include_toc,author_name=author_name,share_cover=request.share_cover)
        # Recheck owner access before publication; async cancellation cannot interleave
        # this short atomic replace, and download still requires a terminal task.
        authorize(ctx.owner,ctx.payload)
        path=file_path(store,ctx.owner,ctx.id,request.format);path.parent.mkdir(parents=True,exist_ok=True)
        temp=path.with_suffix('.partial')
        try:
            temp.write_bytes(payload);temp.replace(path)
        finally: temp.unlink(missing_ok=True)
        # Bounded private retention, cleaned lazily by the next export.
        files=sorted((p for p in path.parent.iterdir() if p.suffix in ('.zip','.html','.txt','.partial')),key=lambda p:p.stat().st_mtime,reverse=True)
        for index,old in enumerate(files):
            if old!=path and (index>=20 or time.time()-old.stat().st_mtime>7*86400): old.unlink(missing_ok=True)
        channel_name=store.get('channels',ctx.owner,request.channel_id)['name'] if request.channel_id else '全部频道 / All channels'
        if request.format=='html':info['author_name_missing']=not bool(author_name)
        result={'channel_name':channel_name,'format':request.format,'size':len(payload),'sha256':hashlib.sha256(payload).hexdigest(),**info}
        ctx.report(message='导出完成 / Export ready',progress={'stage':'complete',**{k:v for k,v in info.items() if k!='missing_images'}})
        return result
    async def cancel(ctx,force):
        for format in ('zip','html'):
            path=file_path(store,ctx.owner,ctx.id,format)
            path.unlink(missing_ok=True);path.with_suffix('.partial').unlink(missing_ok=True)
        return True
    tasks.register('intelligence.export',TaskHandler('ai2apps.intelligence',execute,cancel,authorize,resumable=False))
