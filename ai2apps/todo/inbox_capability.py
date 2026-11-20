"""Todo-owned, idempotent creation of ordinary Inbox items; no execution."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
import logging
from ai2apps.services.capability_routing import CapabilityProvider
from ai2apps.system_tasks.sessions import execution_principal
from .aaat import store

CAPABILITY='todo.inbox.create'
APP='ai2apps.todo'


class InboxItem(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str=Field(min_length=1,max_length=200)
    description:str=Field(default='',max_length=10000)
    priority:Literal['A','B','C']='B'


def install(runtime):
    logging.getLogger(__name__).info('Todo Inbox creation capability loaded; source=%s',__file__)
    async def create(args,ctx):
        value=InboxItem.model_validate(args).model_dump()
        if not value['title'].strip():raise ValueError('Todo title required')
        if not ctx.actor_user_id or not ctx.invocation_id:raise PermissionError('An owned Tool invocation is required')
        principal=execution_principal(runtime,ctx.actor_user_id)
        definition=runtime.extension_manager._active_app_definition(APP)
        if definition is None or definition['status']!='enabled':raise PermissionError('Todo is unavailable')
        runtime.extension_manager._require_app_access(definition,principal)
        with runtime.app_chat.lock:
            if runtime.app_chat.binding(ctx.session_id):runtime.app_chat.require_authorized(ctx,CAPABILITY,args)
            task=store(runtime).save(ctx.actor_user_id,value,creation_key='todo-inbox:'+ctx.invocation_id,create_inbox=True)
        return {'status':'created','task_id':task['id'],'title':task['title'],'directory_id':task['directory_id'],
                'execution_started':False,'scheduled':False,'receipt_id':task['id']}
    source=runtime.services.get_tool('todo.get')
    instance=runtime.services.get_instance_for_service(source.service_id)
    runtime.services.ensure_tool(service_id=source.service_id,qualified_name=CAPABILITY,
        display_name='创建收件箱待办 / Create Inbox Todo',
        description='Create one ordinary Todo item in the current user Inbox. Cannot edit/delete projects, select another directory, schedule execution, or start an Agent task.',
        input_schema=InboxItem.model_json_schema(),output_schema={'type':'object'},effects=('workspace.write',),required_capabilities=())
    runtime.app_capability_router.register(CapabilityProvider(APP+'.'+CAPABILITY,CAPABILITY,APP,create,version='1',
        agent_context={'schema':'ai2apps.aaat-declaration/v1','instructions':[
            'Creates an ordinary Todo in the current user Inbox. Use for a requested follow-up or reminder item, not an Agent execution task.',
            'Only title, description and priority are accepted. No schedule, executor, parent, destination or recipient may be supplied.',
            'An actual saved task_id/receipt_id proves creation. It never proves execution, scheduling or task completion. Do not claim an execution was started.'
        ],'result_semantics':{'created':'one saved Inbox item; no execution or schedule'}}))
    async def route(args,ctx):return await runtime.app_capability_router.invoke(CAPABILITY,args,ctx)
    runtime.service_registry.bind_tool(CAPABILITY,provider_key=instance.provider_key,handler=route)
