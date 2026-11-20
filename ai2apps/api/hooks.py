"""Local user management of observations and explicit background delegations."""
from ai2apps.apps.access import has_app_capability
import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from ai2apps.api.identity import require_app_capability
from ai2apps.events.hooks import HookError


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')


class Preview(Strict):
    consumer: dict
    event_type: str = Field(min_length=1,max_length=200)
    scope: Literal['subjects','owned_collection'] = 'subjects'
    subjects: list[str] = Field(default_factory=list,max_length=20)
    filters: list[dict] = Field(default_factory=list,max_length=12)
    execution: dict | None = None


class Save(Strict):
    preview_ref: str = Field(min_length=1,max_length=100)
    request_id: str = Field(min_length=8,max_length=128)
    expected_revision: int | None = Field(default=None,ge=1)


class Change(Strict):
    expected_revision: int = Field(ge=1)
    request_id: str = Field(min_length=8,max_length=128)


def create_hook_router(runtime_provider,principal_provider):
    import logging
    logging.getLogger(__name__).info('Hook management and monitoring loaded; source=%s',__file__)
    router=APIRouter(prefix='/hooks',dependencies=[Depends(require_app_capability(principal_provider,'app.use'))])
    principal=Depends(principal_provider)
    def service():
        hooks=getattr(runtime_provider(),'event_hooks',None)
        if hooks is None:raise HTTPException(503,'Hook service unavailable')
        return hooks
    def call(fn,*args,**kwargs):
        try:return fn(*args,**kwargs)
        except HookError as e:
            status=404 if e.code=='rule_not_found' else 403 if e.code=='subscription_denied' else 422 if e.code.startswith('invalid_') else 409
            raise HTTPException(status,{'code':e.code,'phase':'subscription','message':str(e),'retryable':False}) from e
        except (PermissionError,KeyError) as e:
            raise HTTPException(403,{'code':'subscription_denied','phase':'subscription','message':'Consumer or resource unavailable','retryable':False}) from e
        except ValueError as e:
            raise HTTPException(422,{'code':'invalid_rule','phase':'subscription','message':str(e),'retryable':False}) from e
    def background_authority(p,*,preview_ref=None,rule_id=None):
        with service().db.transaction() as db:
            if preview_ref:
                row=db.execute('SELECT spec_json FROM hook_previews WHERE id=? AND owner=?',(preview_ref,p.actor_user_id)).fetchone()
            else:
                row=db.execute('SELECT v.spec_json FROM hook_rules r JOIN hook_rule_revisions v ON v.rule_id=r.id AND v.revision=r.revision WHERE r.id=? AND r.owner=?',(rule_id,p.actor_user_id)).fetchone()
        if row and json.loads(row[0]).get('mode')=='background' and (p.client_scope!='desktop' or not has_app_capability(p,'app.coder.use')):
            raise HTTPException(403,'Background delegation requires the owning desktop user')
    @router.get('/consumers')
    def consumers(p=principal):return {'items':service().catalog()}
    @router.post('/preview')
    def preview(body:Preview,p=principal):
        if body.execution is not None and (p.client_scope!='desktop' or not has_app_capability(p,'app.coder.use')):
            raise HTTPException(403,'Background delegation requires the owning desktop user')
        return call(service().preview,p.actor_user_id,body.model_dump())
    @router.post('',status_code=201)
    def enable(body:Save,p=principal):
        background_authority(p,preview_ref=body.preview_ref)
        if body.expected_revision is not None:raise HTTPException(422,'New rules have no expected_revision')
        return call(service().save,p.actor_user_id,body.preview_ref,body.request_id)
    @router.get('')
    def rules(p=principal):return {'items':service().rules(p.actor_user_id)}
    @router.get('/monitor')
    def monitoring(limit:int=Query(50,ge=1,le=100),p=principal):
        from ai2apps.events.monitoring import monitor
        return call(monitor,service(),p.actor_user_id,limit=limit)
    @router.get('/actions')
    def action_catalog(p=principal):return {'items':runtime_provider().hook_actions.catalog()}
    @router.get('/notices')
    def list_notices(p=principal):
        from ai2apps.events.monitoring import notices
        return call(notices,service(),p.actor_user_id)
    @router.post('/notices/{notice_id}/read')
    def mark_notice_read(notice_id:str,p=principal):
        from ai2apps.events.monitoring import read_notice
        return call(read_notice,service(),p.actor_user_id,notice_id)
    @router.get('/deliveries/{delivery_id}/steps')
    def execution_steps(delivery_id:str,p=principal):
        from ai2apps.events.monitoring import steps
        return call(steps,service(),p.actor_user_id,delivery_id)
    @router.get('/{rule_id}')
    def get(rule_id:str,p=principal):return call(service().get,p.actor_user_id,rule_id)
    @router.put('/{rule_id}')
    def update(rule_id:str,body:Save,p=principal):
        background_authority(p,preview_ref=body.preview_ref)
        if body.expected_revision is None:raise HTTPException(422,'expected_revision required')
        return call(service().save,p.actor_user_id,body.preview_ref,body.request_id,rule_id=rule_id,expected_revision=body.expected_revision)
    @router.post('/{rule_id}/{action}')
    def change(rule_id:str,action:str,body:Change,p=principal):
        if action=='resume':background_authority(p,rule_id=rule_id)
        return call(service().change,p.actor_user_id,rule_id,action,body.expected_revision,body.request_id)
    @router.get('/{rule_id}/deliveries')
    def deliveries(rule_id:str,after:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),p=principal):
        return call(service().deliveries,p.actor_user_id,rule_id,after=after,limit=limit)
    return router
