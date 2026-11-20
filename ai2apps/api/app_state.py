"""Principal/instance-bound portable UI state APIs; never run business actions."""
import logging
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel,ConfigDict,Field
from ai2apps.api.identity import require_app_capability
from ai2apps.apps.state_setup import get_app_state
from ai2apps.apps.app_state import StateError
from ai2apps.core import RepositoryError
from ai2apps.extensions import ExtensionError


class StateBody(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    packet:dict

class Validate(StateBody):
    migrate:bool=False

class Capture(StateBody):
    name:str=Field(min_length=1,max_length=80)
    request_id:str=Field(min_length=8,max_length=128)

class Prepare(StateBody):
    request_id:str=Field(min_length=8,max_length=128)
    base_revision:str=Field(pattern=r'^[a-f0-9]{64}$')
    contract_digest:str=Field(pattern=r'^[a-f0-9]{64}$')

class Complete(StateBody):
    status:Literal['ui_applied','failed']


def create_app_state_router(runtime_provider,principal_provider):
    logging.getLogger(__name__).info('App-State API v1 loaded; source=%s',__file__)
    def private(response:Response):
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
    router=APIRouter(prefix='/app-state',dependencies=[Depends(require_app_capability(principal_provider,'app.use')),Depends(private)])
    actor=Depends(principal_provider)
    service=lambda:get_app_state(runtime_provider())
    def call(fn):
        try:return fn()
        except StateError as e:raise HTTPException(409,{'code':e.code,'message':str(e),'path':e.path}) from e
        except (PermissionError,RepositoryError,ExtensionError,KeyError) as e:raise HTTPException(404,'App-State target unavailable') from e

    @router.get('/instances/{instance}/contract')
    def contract(instance:str,app_id:str,mini_app_id:str|None=None,p=actor):
        def action():
            service().authorize(p,instance,app_id)
            return service().describe(app_id,mini_app_id)
        return call(action)

    @router.post('/instances/{instance}/validate')
    def validate(instance:str,body:Validate,p=actor):return call(lambda:service().validate(p,instance,body.packet,migrate=body.migrate))

    @router.get('/instances/{instance}/presets')
    def presets(instance:str,app_id:str,mini_app_id:str|None=None,p=actor):return call(lambda:service().list(p,instance,app_id,mini_app_id))

    @router.post('/instances/{instance}/presets',status_code=201)
    def capture(instance:str,body:Capture,p=actor):return call(lambda:service().save(p,instance,body.name,body.packet,body.request_id))

    @router.post('/instances/{instance}/applications',status_code=201)
    def prepare(instance:str,body:Prepare,p=actor):return call(lambda:service().prepare(p,instance,body.packet,body.request_id,body.base_revision,body.contract_digest))

    @router.post('/instances/{instance}/applications/{ref}/complete')
    def complete(instance:str,ref:str,body:Complete,p=actor):return call(lambda:service().complete(p,instance,ref,body.packet,body.status))
    return router
