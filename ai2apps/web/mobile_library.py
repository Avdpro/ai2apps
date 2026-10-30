"""Small Owner Mobile library surface; no generic file or admin proxy."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict, HttpUrl
from ai2apps.http_security import enforce_same_origin_cookie_request

class MobileKnowledgeCapture(BaseModel):
    model_config=ConfigDict(extra="forbid")
    title:str=Field(default='',max_length=500)
    text:str=Field(default='',max_length=2_000_000)
    bucket_id:str='auto'
    url:HttpUrl|None=None

class MobileKnowledgeQuestion(BaseModel):
    model_config=ConfigDict(extra="forbid")
    question:str=Field(min_length=1,max_length=4000)
    bucket_id:str|None=None

from ai2apps.apps.access import has_app_capability
from ai2apps.core import RepositoryError
from ai2apps.gallery import GalleryRepository, GalleryError
from ai2apps.knowledge import KnowledgeScope, KnowledgeStore, KnowledgeAccessError, KnowledgeNotFoundError

MEDIA = frozenset({'image/png','image/jpeg','image/webp','image/gif','image/avif','video/mp4','video/webm','video/quicktime'})

def item_view(item, full=False):
    data={k:getattr(item,k) for k in ('id','title','kind','updated_at','visibility')}
    data['text']=item.text if full else item.text[:240]
    return data


def create_mobile_library_router(runtime_provider, principal_provider, renderer):
    router=APIRouter()
    import logging
    logging.getLogger(__name__).info("Mobile Knowledge capture/ask routes loaded from %s", __file__)
    dep=Depends(principal_provider)
    def runtime(p):
        if not has_app_capability(p,'app.use'): raise HTTPException(403,'App access required')
        r=runtime_provider()
        if r is None: raise HTTPException(503,'Library unavailable')
        return r
    def knowledge(p):
        r=runtime(p)
        return getattr(r,'knowledge',None) or KnowledgeStore(r.database,blob_root=r.config.paths.artifacts_path/'knowledge')
    def gallery(p):
        r=runtime(p)
        return GalleryRepository(r.database,r.config.paths.artifacts_path/'gallery',getattr(r,'events',None))
    def checked(fn,*args,**kwargs):
        try:return fn(*args,**kwargs)
        except KnowledgeAccessError:raise HTTPException(403,'Knowledge access denied') from None
        except (KnowledgeNotFoundError,RepositoryError,FileNotFoundError):raise HTTPException(404,'Item not found') from None
        except (ValueError,GalleryError):raise HTTPException(422,'Invalid library request') from None

    # Explicit Knowledge-owned composition, sharing desktop validation/services.
    # This is not a proxy to arbitrary Platform or administrator endpoints.
    def mobile_principal(request:Request,p=dep):
        # Remote ingress already validates the registered public Origin and lease.
        # Its TLS origin differs from the internal HTTP transport; never infer
        # trust from forwarded headers or the principal's authentication label.
        from .owner_home_gateway import authority
        grant=authority(request)
        if grant is None and not getattr(request.state,'ai2apps_mobile_local_session',None):
            enforce_same_origin_cookie_request(request)
        runtime(p)
        return p
    from ai2apps.api.knowledge import create_knowledge_router
    owned=create_knowledge_router(runtime_provider,mobile_principal)
    exposed={
        ('POST','/knowledge/items/import-batch'):'/v1/mobile/knowledge/files',
        ('GET','/knowledge/imports'):'/v1/mobile/knowledge/imports',
        ('GET','/knowledge/image-ocr'):'/v1/mobile/knowledge/image-ocr',
        ('POST','/knowledge/image-ocr/{item_id}/decision'):'/v1/mobile/knowledge/image-ocr/{item_id}/decision',
        ('GET','/knowledge/bucket-routing'):'/v1/mobile/knowledge/bucket-routing',
        ('POST','/knowledge/bucket-routing/{item_id}/decision'):'/v1/mobile/knowledge/bucket-routing/{item_id}/decision',
    }
    for route in owned.routes:
        for method in route.methods:
            target=exposed.get((method,route.path))
            if target:router.add_api_route(target,route.endpoint,methods=[method],status_code=route.status_code)

    handlers={route.path:route.endpoint for route in owned.routes if 'POST' in route.methods}
    @router.post('/v1/mobile/knowledge/notes',status_code=201)
    def mobile_note(body:MobileKnowledgeCapture,p=Depends(mobile_principal)):
        from ai2apps.api.knowledge import KnowledgeItemCreateRequest
        if not body.title.strip() or not body.text.strip():raise HTTPException(422,'请填写标题和正文')
        bucket=next((b for b in knowledge(p).list_buckets(p) if b.id==body.bucket_id),None)
        scope=bucket.visibility.value if bucket else 'private'
        request=KnowledgeItemCreateRequest(title=body.title,text=body.text,bucket_id=body.bucket_id,scope=scope,kind='note',source_app_id='ai2apps.knowledge')
        return handlers['/knowledge/items'](request,p)

    @router.post('/v1/mobile/knowledge/web',status_code=201)
    async def mobile_web(body:MobileKnowledgeCapture,p=Depends(mobile_principal)):
        from ai2apps.api.knowledge import KnowledgeWebImportRequest
        if body.url is None:raise HTTPException(422,'请填写网页链接')
        request=KnowledgeWebImportRequest(url=body.url,title=body.title or None,bucket_id=body.bucket_id,fetch_mode='static',auto_accept_cookies=False)
        return await handlers['/knowledge/items/web'](request,p)

    @router.post('/v1/mobile/knowledge/ask')
    async def ask(body:MobileKnowledgeQuestion,p=Depends(mobile_principal)):
        selected=runtime(p)
        if not body.question.strip():raise HTTPException(422,'请填写问题')
        from ai2apps.knowledge.mobile_ask import answer_mobile
        try:return await answer_mobile(selected,p,body.question.strip(),body.bucket_id)
        except ValueError as error:raise HTTPException(422,str(error)) from None
        except Exception:raise HTTPException(503,'知识问答暂不可用，请稍后重试') from None

    @router.get('/mobile/knowledge')
    def knowledge_page(request:Request,p=dep):
        runtime(p);return renderer(request,p,'knowledge')
    @router.get('/mobile/gallery')
    def gallery_page(request:Request,p=dep):
        runtime(p);return renderer(request,p,'gallery')

    @router.get('/v1/mobile/knowledge/buckets')
    def buckets(p=dep):
        return {'items':[{'id':b.id,'name':{'inbox':'收件箱','web':'网页','documents':'文档与文件','chats':'对话记录','shared':'本机共享'}.get(b.system_key,b.name),'visibility':b.visibility} for b in checked(knowledge(p).list_buckets,p)]}
    @router.get('/v1/mobile/knowledge/items')
    def items(q:str=Query(default='',max_length=4000),bucket_id:str|None=None,limit:int=Query(default=100,ge=1,le=100),p=dep):
        s=knowledge(p)
        if q.strip():
            hits=checked(s.search,p,q,bucket_ids=[bucket_id] if bucket_id else (),limit=limit)
            if hits:
                return {'items':[{**item_view(h.item),'text':h.excerpt} for h in hits]}
            # FTS tokenization can miss short CJK substrings. Keep the fallback
            # inside the same principal/bucket visibility checks.
            recent=checked(s.list_items,p,bucket_id=bucket_id,limit=500)
            needle=q.strip().casefold()
            return {'items':[item_view(i) for i in recent if needle in (i.title+' '+i.text).casefold()][:limit], 'fallback_recent_limit':500}
        return {'items':[item_view(i) for i in checked(s.list_items,p,bucket_id=bucket_id,limit=limit)]}
    @router.get('/v1/mobile/knowledge/items/{item_id}')
    def item(item_id:str,p=dep):return item_view(checked(knowledge(p).get_item,p,item_id),True)
    @router.get('/v1/mobile/knowledge/items/{item_id}/attachments')
    def record_attachments(item_id:str,p=dep):
        from ai2apps.knowledge.groups import attachments
        return {'items':checked(attachments,knowledge(p),p,item_id)}

    @router.get('/v1/mobile/knowledge/items/{item_id}/attachments/{child_id}')
    def record_attachment_content(item_id:str,child_id:str,p=dep):
        from ai2apps.knowledge.groups import attachments
        s=knowledge(p)
        members=checked(attachments,s,p,item_id)
        if child_id not in {m['item_id'] for m in members}:raise HTTPException(404,'Attachment unavailable')
        asset,path=checked(s.asset_path,p,child_id)
        return FileResponse(path,media_type=asset.media_type,filename=asset.filename,content_disposition_type='attachment',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; sandbox"})

    @router.post('/v1/mobile/knowledge/items/{item_id}/collect')
    def collect(item_id:str,p=dep):
        s=knowledge(p);checked(s.get_item,p,item_id)
        bucket=next((b for b in checked(s.list_buckets,p) if b.owner_user_id==p.actor_user_id and b.name=='手机收藏' and b.kind=='custom'),None)
        if bucket is None:bucket=checked(s.create_bucket,p,name='手机收藏',scope=KnowledgeScope.PRIVATE)
        checked(s.add_item_to_bucket,p,bucket.id,item_id)
        return {'bucket_id':bucket.id,'saved':True}

    @router.get('/v1/mobile/gallery/collections')
    def collections(p=dep):
        return {'items':[{'id':c['id'],'name':c['name']} for c in checked(gallery(p).list_collections,p.actor_user_id) if c.get('system_key')!='trash']}
    @router.get('/v1/mobile/gallery/assets')
    def assets(q:str=Query(default='',max_length=500),collection_id:str|None=None,kind:str|None=None,limit:int=Query(default=100,ge=1,le=500),p=dep):
        if kind not in (None,'image','video'):raise HTTPException(422,'Unsupported media kind')
        rows=checked(gallery(p).list_assets,p.actor_user_id,collection_id=collection_id,kind=kind,search=q,limit=limit)
        return {'items':[{k:a.get(k) for k in ('id','name','kind','media_type','size_bytes','created_at')} for a in rows if a['media_type'] in MEDIA and a.get('status')=='active']}
    @router.get('/v1/mobile/gallery/assets/{asset_id}/content')
    def content(asset_id:str,download:bool=False,p=dep):
        asset,path=checked(gallery(p).asset_path,p.actor_user_id,asset_id)
        if asset['media_type'] not in MEDIA or asset.get('status')!='active':raise HTTPException(404,'Media unavailable')
        return FileResponse(path,media_type=asset['media_type'],filename=asset['name'] if download else None,
            content_disposition_type='attachment' if download else 'inline',
            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; sandbox"})
    return router
