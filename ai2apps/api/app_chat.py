"""Fixed scoped Chat API; no client-selected Tool grants or executable hooks."""
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field,ConfigDict
from ai2apps.api.identity import resolve_request_principal

class Strict(BaseModel):model_config=ConfigDict(extra='forbid')
class Open(Strict):
    include_messages:bool=True
    registration:str=Field(min_length=1,max_length=200)
    scope:dict=Field(default_factory=dict)
    ui:dict=Field(default_factory=dict)
class Heartbeat(Strict):
    mount:str=Field(min_length=8,max_length=128)
    ui:dict
class Turn(Strict):
    request_id:str=Field(min_length=8,max_length=128)
    text:str=Field(min_length=1,max_length=16000)
    model:str=Field(min_length=1,max_length=300)
    attachments:list[str]=Field(default_factory=list,max_length=8)
class Ack(Strict):
    mount:str=Field(min_length=8,max_length=128)
    revision:int=Field(ge=1)
    applied:bool
    result:dict=Field(default_factory=dict)


def create_app_chat_router(runtime_provider,principal_provider=resolve_request_principal):
    router=APIRouter(prefix='/app-chat');principal=Depends(principal_provider)
    def service():
        r=runtime_provider()
        if not r or not getattr(r,'app_chat',None):raise HTTPException(503,'App Chat unavailable')
        return r.app_chat
    def call(fn,*args):
        try:return fn(*args)
        except PermissionError as e:raise HTTPException(403,str(e)) from e
        except (KeyError,ValueError) as e:raise HTTPException(409,str(e)) from e
    @router.post('/sessions')
    def open_session(body:Open,p=principal):
        s=service();sid=call(s.open,p,body.registration,body.scope,body.ui)
        return call(s.snapshot,p,sid,body.include_messages)
    @router.get('/sessions/{sid}')
    def snapshot(sid:str,p=principal):return call(service().snapshot,p,sid)
    @router.get('/sessions/{sid}/state')
    def state(sid:str,p=principal):return call(service().snapshot,p,sid,False)
    @router.get('/sessions/{sid}/messages')
    def messages(sid:str,limit:int=Query(50,ge=1,le=50),before:int|None=Query(None,ge=1),after:int|None=Query(None,ge=0),p=principal):
        return call(service().message_page,p,sid,limit,before,after)
    @router.put('/sessions/{sid}/ui')
    def ui(sid:str,body:Heartbeat,p=principal):return call(service().heartbeat,p,sid,body.mount,body.ui)
    @router.post('/sessions/{sid}/turns',status_code=202)
    def turn(sid:str,body:Turn,p=principal):
        rid=call(lambda: service().submit(p,sid,body.request_id,body.text,body.model,attachments=body.attachments))
        return {'run_id':rid}
    @router.post('/sessions/{sid}/ui/{command_id}')
    def ack(sid:str,command_id:str,body:Ack,p=principal):
        return call(service().acknowledge,p,sid,command_id,body.mount,body.revision,body.result,body.applied)
    return router
