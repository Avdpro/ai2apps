"""Run-bound UI controls for an existing observed Browser Task, never a new job."""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ai2apps.api.ownership import authorize_agent_run
from .tasks import BrowserTaskRepository
from .task_presentation import browser_task_wait_presentation

logging.getLogger(__name__).info('Run-bound Browser task controls loaded from %s',__file__)

class AssistanceAction(BaseModel):
    action: str
    interaction_id: str | None = None
    response_id: str | None = None
    approve: bool = True


def require_task(runtime, principal, run_id, task_id):
    authorize_agent_run(runtime,principal,run_id)
    # Tool progress is persisted by the invocation runtime. A Model-provided ID
    # or a task owned by the same person alone is not a task linkage.
    with runtime.database.transaction() as db:
        rows=db.execute('SELECT progress_json FROM tool_invocations WHERE trace_id=?', (run_id,)).fetchall()
    if not any(json.loads(row['progress_json'] or '{}').get('content',{}).get('browser_task_id')==task_id for row in rows):
        raise HTTPException(404,'Task was not observed by this Run')
    repo=BrowserTaskRepository(runtime.database,runtime.events)
    try:task=repo.get(principal.actor_user_id,task_id)
    except KeyError:raise HTTPException(404,'Task not found') from None
    interactions=runtime.agents.list_interactions(task['run_id']) if task.get('run_id') else []
    task.update(browser_task_wait_presentation(interactions,task.get('browser_context')))
    pending=[i for i in interactions if i.status.value=='pending' and i.request.get('control') in ('browser_user_assistance','agent_confirmation','agent_budget')]
    return repo,task,pending


def create_router(runtime_provider,principal_provider):
    router=APIRouter()
    path='/agent-runs/{run_id}/browser-tasks/{task_id}'
    @router.get(path)
    def snapshot(run_id:str,task_id:str,principal=Depends(principal_provider)):
        _,task,pending=require_task(runtime_provider(),principal,run_id,task_id)
        return {'id':task['id'],'status':task['status'],'message':task.get('message',''),'requires_user':task.get('requires_user',False),
                'interactions':[{'id':i.id,'prompt':i.prompt,'control':i.request['control'],'request':{'control':i.request['control']}} for i in pending]}
    @router.post(path)
    async def act(run_id:str,task_id:str,body:AssistanceAction,principal=Depends(principal_provider)):
        runtime=runtime_provider();repo,task,pending=require_task(runtime,principal,run_id,task_id)
        if runtime.agents.get_run(run_id).status.value in ('completed','failed','cancelled','interrupted'):
            raise HTTPException(409,'Originating Run is no longer active')
        if body.action=='cancel':
            from .task_tree import TaskTreeRepository
            for rid in TaskTreeRepository(runtime.database,runtime.events).cancel(principal.actor_user_id,task['execution_task_id']):runtime.agent_runtime.cancel(rid)
        elif body.action=='continue':
            item=next((i for i in runtime.agents.list_interactions(task['run_id']) if i.id==body.interaction_id and i.request.get('control') in ('browser_user_assistance','agent_confirmation','agent_budget')),None)
            if not item:raise HTTPException(409,'Assistance changed; refresh before continuing')
            if not body.response_id:raise HTTPException(422,'Response ID required')
            if item.request['control']=='agent_budget':
                from ai2apps.agents.token_budget import CONTINUE, STOP
                response={'answer':CONTINUE if body.approve else STOP}
            else:
                response={'decision':'approve' if body.approve else 'deny'} if item.request['control']=='agent_confirmation' else {'continued':True}
            if item.status.value!='pending':
                if item.response_id==body.response_id and item.response==response:return snapshot(run_id,task_id,principal)
                raise HTTPException(409,'Assistance already resolved')
            if task['status']!='waiting_input':raise HTTPException(409,'Task is no longer waiting')
            runtime.agents.respond_interaction(task['run_id'],item.id,response=response,response_id=body.response_id)
            runtime.agent_runtime.wake()
        elif body.action=='open':
            if not pending or not task.get('requires_user'):raise HTTPException(409,'Task no longer needs assistance')
            from .background_bidi import BackgroundBiDi
            from .profiles import BrowserProfileRepository
            from ai2apps.api.client import _request_shell_browser_action
            import asyncio
            context=task.get('browser_context') or {};target=task.get('assistance_context') or context.get('bidi_context')
            connection=await BackgroundBiDi().connect()
            try:
                tree=await connection.command('browsingContext.getTree',{'maxDepth':0})
                if not any(c['context']==target and c.get('userContext')==context.get('user_context') for c in tree.get('contexts',[])):raise HTTPException(409,'Original task page is no longer available')
                await connection.command('browsingContext.activate',{'context':target})
                profile=BrowserProfileRepository(runtime.database).require(principal.actor_user_id,task['profile_key'])
                await asyncio.to_thread(_request_shell_browser_action,principal.actor_user_id,task['profile_key'],profile.name,profile.is_default,'open',None)
            finally:await connection.close()
        else:raise HTTPException(422,'Unknown assistance action')
        return snapshot(run_id,task_id,principal)
    return router
