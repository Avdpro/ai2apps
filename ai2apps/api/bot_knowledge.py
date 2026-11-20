"""Local host UI for Bot-owned history and explicit structured memory operations."""
from fastapi import HTTPException,Query,Request
from fastapi.responses import FileResponse
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from ai2apps.identity import RequestPrincipal


class MemoryCommand(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    request_id:str=Field(min_length=8,max_length=128)
    subject:str=Field(min_length=1,max_length=120)
    predicate:str=Field(min_length=1,max_length=120)
    value:str|dict
    text:str=Field(min_length=1,max_length=2000)
    kind:Literal['fact','preference','resource','model']='fact'
    variant:str=Field(default='',max_length=120)
    mode:Literal['merge','replace']='merge'
    expected_revision:int|None=Field(default=None,ge=1)
    source:dict|None=None


class UndoMemory(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str=Field(min_length=8,max_length=128)


def add_routes(router,runtime_provider,principal_dependency,bot_access,task_host,task_call):
    def history():return runtime_provider().messager_bots.history
    def records():return runtime_provider().messager_bots.memory.records

    @router.get('/bots/{bot_id}/history',dependencies=[bot_access])
    def search(bot_id:str,q:str=Query(default='',max_length=300),limit:int=Query(default=20,ge=1,le=50),offset:int=Query(default=0,ge=0,le=10000),archived:bool=False,index_after:str=Query(default='',max_length=256),principal:RequestPrincipal=principal_dependency):
        return task_call(lambda:history().search(principal.actor_user_id,bot_id,q,limit=limit,offset=offset,archived=archived,index_after=index_after))

    @router.get('/bots/{bot_id}/history/{task_id}',dependencies=[bot_access])
    def detail(bot_id:str,task_id:str,archived:bool=False,principal:RequestPrincipal=principal_dependency):
        return task_call(lambda:history().detail(principal.actor_user_id,bot_id,task_id,archived=archived))

    @router.get('/bots/{bot_id}/memory-changes',dependencies=[bot_access])
    def changes(bot_id:str,session_id:str|None=None,limit:int=Query(default=50,ge=1,le=100),offset:int=Query(default=0,ge=0,le=10000),message_id:list[str]=Query(default=[],max_length=100),principal:RequestPrincipal=principal_dependency):
        return task_call(lambda:records().changes(principal.actor_user_id,bot_id,sid=session_id,limit=limit,offset=offset,message_ids=message_id or None))

    @router.get('/bots/{bot_id}/memory-changes/{change_id}',dependencies=[bot_access])
    def change(bot_id:str,change_id:str,principal:RequestPrincipal=principal_dependency):
        return task_call(lambda:records().detail(principal.actor_user_id,bot_id,change_id))

    @router.post('/bots/{bot_id}/memory-records',dependencies=[bot_access])
    async def remember(bot_id:str,body:MemoryCommand,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        if body.kind == 'model':
            from ai2apps.messager.model_memories import model_value, catalog
            try:
                value=model_value(body.value)
                choices=await catalog(request,value['purpose'],value['profile'])
                if not any(m['id']==value['model'] and m['ready'] for m in choices):
                    raise ValueError('Choose an available model from Model-App for this purpose')
            except ValueError as error:raise HTTPException(422,str(error)) from error
        return task_call(lambda:records().apply(principal.actor_user_id,bot_id,**body.model_dump()))

    @router.get('/bots/{bot_id}/model-memory-catalog',dependencies=[bot_access])
    async def model_memories(bot_id:str,request:Request,purpose:str='image_generation',profile:Literal['normal','privacy']='normal',principal:RequestPrincipal=principal_dependency):
        from ai2apps.model_manager import DEFAULT_MODEL_PURPOSES
        from ai2apps.messager.model_memories import catalog
        task_call(lambda:runtime_provider().messager_bots.scope(principal.actor_user_id,{'bot_id':bot_id}))
        try:models=await catalog(request,purpose,profile)
        except ValueError as error:raise HTTPException(422,str(error)) from error
        return {'purposes':list(DEFAULT_MODEL_PURPOSES),'models':models,'purpose':purpose,'profile':profile}

    @router.post('/bots/{bot_id}/memory-changes/{change_id}/undo',dependencies=[bot_access])
    def undo(bot_id:str,change_id:str,body:UndoMemory,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:records().undo(principal.actor_user_id,bot_id,change_id,request_id=body.request_id))

    @router.get('/bots/{bot_id}/memory-candidates',dependencies=[bot_access])
    def candidates(bot_id:str,feed:bool=False,principal:RequestPrincipal=principal_dependency):
        return task_call(lambda:runtime_provider().messager_bots.memory_tasks.pending(principal.actor_user_id,bot_id,feed=feed))

    @router.post('/bots/{bot_id}/memory-candidates/{candidate_id}/{decision}',dependencies=[bot_access])
    def decide_candidate(bot_id:str,candidate_id:str,decision:Literal['confirm','cancel'],request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_bots.memory_tasks.decide(principal.actor_user_id,bot_id,candidate_id,decision))

    @router.get('/bots/{bot_id}/memory-records/{memory_id}/resource',dependencies=[bot_access])
    def resource(bot_id:str,memory_id:str,principal:RequestPrincipal=principal_dependency):
        runtime=runtime_provider();actor=principal.actor_user_id
        task_call(lambda:runtime.messager_bots.scope(actor,{'bot_id':bot_id}))
        with runtime.database.transaction() as db:
            row=db.execute('''SELECT f.metadata_json FROM messager_memory_fields f JOIN messager_bot_memories m ON m.id=f.memory_id
                WHERE f.actor=? AND f.bot_id=? AND f.memory_id=? AND m.deleted=0''',(actor,bot_id,memory_id)).fetchone()
        if not row:raise HTTPException(404,'Memory resource unavailable')
        import json
        metadata=json.loads(row[0]);ref=metadata.get('value',{})
        if metadata.get('kind')!='resource':raise HTTPException(404,'Not a resource memory')
        ref={k:ref[k] for k in ('session_id','artifact_id')}
        value=task_call(lambda:history().resource(actor,bot_id,ref,retained=True))
        if not value['available']:raise HTTPException(404,'Memory resource unavailable')
        asset=runtime.workspace.get_artifact(ref['session_id'],ref['artifact_id'])
        return FileResponse(runtime.workspace.artifact_path(asset),media_type=asset.media_type,filename=asset.name,content_disposition_type='inline' if asset.media_type in ('image/png','image/jpeg','image/webp','image/gif') else 'attachment',headers={'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})
