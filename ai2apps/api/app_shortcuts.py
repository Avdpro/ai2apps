"""Authenticated ASC-Bot capture and instance-bound UI launch intents."""
from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel,ConfigDict,Field
from ai2apps.api.identity import require_app_capability
from ai2apps.core import RepositoryError
from ai2apps.extensions import ExtensionError
from ai2apps.apps.app_state import StateError
from ai2apps.messager.creation import CreationAvatar
from ai2apps.messager.shortcuts import service

class Capture(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    source_instance_id:str=Field(min_length=1,max_length=128)
    packet:dict
    name:str=Field(min_length=1,max_length=64)
    avatar:CreationAvatar=Field(default_factory=CreationAvatar)
    request_id:str=Field(min_length=8,max_length=128)
class Launch(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    request_id:str=Field(min_length=8,max_length=128)
class Claim(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    instance_id:str=Field(min_length=1,max_length=128)

def create_app_shortcuts_router(runtime_provider,principal_provider):
    def private(response:Response):response.headers['Cache-Control']='no-store'
    router=APIRouter(prefix='/app-shortcuts',dependencies=[Depends(require_app_capability(principal_provider,'app.use')),Depends(private)])
    actor=Depends(principal_provider)
    def call(fn):
        try:return fn()
        except StateError as e:raise HTTPException(409,{'code':e.code,'message':str(e)}) from e
        except (PermissionError,RepositoryError,ExtensionError) as e:raise HTTPException(404,'Shortcut unavailable') from e
        except ValueError as e:raise HTTPException(409,{'code':'shortcut_invalid','message':str(e)}) from e
    @router.post('/bots',status_code=201)
    def capture(body:Capture,p=actor):return call(lambda:service(runtime_provider()).create(p,body))
    @router.post('/bots/{bot}/launch',status_code=201)
    def launch(bot:str,body:Launch,p=actor):return call(lambda:service(runtime_provider()).launch(p,bot,body.request_id))
    @router.get('/launches/{ref}')
    def get(ref:str,p=actor):return call(lambda:service(runtime_provider()).get(p,ref))
    @router.post('/launches/{ref}/claim')
    def claim(ref:str,body:Claim,p=actor):return call(lambda:service(runtime_provider()).claim(p,ref,body.instance_id))
    return router
