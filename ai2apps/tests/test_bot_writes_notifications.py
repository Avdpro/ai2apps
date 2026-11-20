"""Real owner grants, stores, Task/Run and outbox; no live accounts or models."""
import json
from dataclasses import replace
from types import SimpleNamespace
import httpx
import pytest
from fastapi import FastAPI
from ai2apps.api.messager import create_messager_router
from ai2apps.identity import RequestPrincipal
from ai2apps.messager.bots import install,REGISTRATION
from ai2apps.remote.notification_host import routes
from ai2apps.todo.aaat import store
from test_app_interactions import runtime,wait
from test_app_chat_durable import bind_identity,response
from test_bot_todo_execution import setup as task_setup,fixture_model,until
from test_event_hook_execution import env

from bot_access_fixtures import restricted_bot
from agent_context_fixtures import owner_context
P=RequestPrincipal.legacy_local


def foreground(runtime,grants=()):
    install(runtime);bot=restricted_bot(runtime,runtime.messager_bots.create('local','Write fixture','Requested local work only'))
    restricted_bot(runtime,bot)
    permissions=runtime.messager_bot_permissions
    if grants:permissions.save('local',bot['id'],1,list(grants),review_hash=permissions.review_hash())
    sid=runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
    run=runtime.app_chat.submit(P(),sid,'source','Create the requested item','fixture')
    context=runtime.tools.context_for_session(caller_id='fixture',session_id=sid,trace_id=run)
    return bot,sid,run,context


async def invoke(runtime,name,args,ctx,key):
    provider=runtime.app_capability_router.providers[('ai2apps.todo.' if name.startswith('todo.') else 'ai2apps.messager.')+name]
    return await provider.handler(args,replace(ctx,invocation_id=key))


@pytest.mark.asyncio
async def test_write_profiles_are_off_then_scope_and_idempotency_are_enforced(runtime):
    bot,sid,run,ctx=foreground(runtime)
    service=runtime.messager_bot_permissions
    catalog=service.catalog('local',bot['id'])
    writes=[x for x in catalog['items'] if x['access']=='create']
    assert len(writes)==2 and all(not x['foreground'] and not x['background'] for x in writes)
    for name,args in [('todo.inbox.create',{'title':'Denied'}),('messager.notice.create',{'title':'Denied'})]:
        with pytest.raises(Exception):await invoke(runtime,name,args,ctx,'denied-'+name)
    assert store(runtime).snapshot('local')['tasks']==[]
    runtime.agents.request_cancel(run)
    service.save('local',bot['id'],1,[{'id':p['id'],'foreground':True,'background':False} for p in writes],review_hash=service.review_hash())
    assert runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})==sid
    run=runtime.app_chat.submit(P(),sid,'allowed-source','Create one Inbox item and reminder','fixture')
    ctx=runtime.tools.context_for_session(caller_id='fixture',session_id=sid,trace_id=run)
    value={'title':'Owned ordinary Todo','description':'Synthetic fixture detail','priority':'A'}
    first=await invoke(runtime,'todo.inbox.create',value,ctx,'create-once')
    assert await invoke(runtime,'todo.inbox.create',value,ctx,'create-once')==first
    assert first['execution_started'] is False and first['scheduled'] is False
    tasks=store(runtime).snapshot('local')['tasks'];assert len(tasks)==1
    task=store(runtime).get('local',first['task_id']);assert task['schedule']['frequency']=='off' and not task['model']
    assert store(runtime).snapshot('local')['runs']==[]
    for extra in ({'schedule':{'frequency':'daily'}},{'executor':'internal'},{'directory_id':'foreign'},{'recipient':'foreign'}):
        with pytest.raises(Exception):await invoke(runtime,'todo.inbox.create',{**value,**extra},ctx,'forged')
    reminder=await invoke(runtime,'messager.notice.create',{'title':'Self reminder','body':'LOCAL_PRIVATE_MARKER'},ctx,'notice-once')
    assert await invoke(runtime,'messager.notice.create',{'title':'Self reminder','body':'LOCAL_PRIVATE_MARKER'},ctx,'notice-once')==reminder
    with pytest.raises(Exception):await invoke(runtime,'messager.notice.create',{'title':'Forged','recipient':'friend'},ctx,'forged-notice')
    notices=runtime.messager_bot_notifications
    assert notices.inbox('foreign')['items']==[]
    assert len(notices.inbox('local')['items'])==1
    assert notices.resolve('local',reminder['notification_id'])['bot_id']==bot['id']
    with pytest.raises(PermissionError):notices.resolve('foreign',reminder['notification_id'])
    assert service.capture('local',{'bot_id':bot['id']},'hook')['providers']=={}
    old=service.capture('local',{'bot_id':bot['id']},'user')
    service.save('local',bot['id'],2,[],review_hash=service.review_hash())
    with pytest.raises(PermissionError):service.validate('local',{'bot_id':bot['id']},old,'todo.inbox.create',value)
    with pytest.raises(Exception):await invoke(runtime,'todo.inbox.create',{'title':'After revocation'},ctx,'late')
    with runtime.database.transaction() as db:row=db.execute('SELECT * FROM messager_local_notices WHERE id=?',(reminder['notification_id'],)).fetchone()
    assert not notices.alert_allowed('local',row)
    assert len(store(runtime).snapshot('local')['tasks'])==1


@pytest.mark.asyncio
async def test_foreground_only_does_not_leak_into_background_and_owner_model_calls_real_write(runtime):
    install(runtime);bot=restricted_bot(runtime,runtime.messager_bots.create('local','Model fixture','Create requested ordinary Todo'))
    permissions=runtime.messager_bot_permissions
    permissions.save('local',bot['id'],1,[{'id':'todo.inbox.create','foreground':True,'background':False}],review_hash=permissions.review_hash())
    sid=runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
    async def model(request):
        results=[json.loads(m['content']) for m in request['messages'] if m['role']=='tool']
        if not results or results[-1].get('error',{}).get('code') in ('tool_declaration_required','tool_not_available'):return response('todo.inbox.create',{'title':'From actual owner Tool loop'})
        assert results[-1]['execution_started'] is False
        return response(text='An ordinary Inbox Todo was saved; no execution was started.')
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        run=runtime.app_chat.submit(P(),sid,'ordinary-request','Add a follow-up Todo','fixture');await wait(runtime,run,'completed')
        assert len(store(runtime).snapshot('local')['tasks'])==1 and store(runtime).snapshot('local')['runs']==[]
        assert permissions.capture('local',{'bot_id':bot['id']},'hook')['providers']=={}
    finally:await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_reviewed_background_inbox_write_has_no_foreground_reminder_authority(runtime):
    from ai2apps.agents.general import _tool_alias
    install(runtime);bot=restricted_bot(runtime,runtime.messager_bots.create('local','Background writer','Create requested follow-up items'))
    permissions=runtime.messager_bot_permissions
    permissions.save('local',bot['id'],1,[{'id':'todo.inbox.create','foreground':False,'background':True},{'id':'messager.notice.create','foreground':True,'background':False}],review_hash=permissions.review_hash())
    sid=runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
    async def model(request):
        background='task_access_mode' in owner_context(request)
        results=[json.loads(m['content']) for m in request['messages'] if m['role']=='tool']
        if background:
            assert _tool_alias('messager.notice.create') not in {t['function']['name'] for t in request['tools']}
            if not results or results[-1].get('error',{}).get('code') in ('tool_declaration_required','tool_not_available'):return response('todo.inbox.create',{'title':'Background ordinary follow-up'})
            return response(text='Saved the approved ordinary Todo.')
        if not results or results[-1].get('error',{}).get('code') in ('tool_declaration_required','tool_not_available'):return response('messager.task.propose',{'title':'Background write','prompt':'BG_SCOPE_WRITE_FIXTURE: create an ordinary Inbox follow-up','notify':False})
        return response(text='Review the proposed background task.')
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        source=runtime.app_chat.submit(P(),sid,'background-write-source','Prepare the requested work','fixture');await wait(runtime,source,'completed')
        proposal=runtime.messager_task_execution.work('local',bot['id'])['proposals'][0]
        result=runtime.messager_task_execution.decide('local',bot['id'],proposal['id'],proposal['review_hash'],'approve')
        # Proposal review admits the task, not every effectful operation. Keep
        # the task owner's one-time write approval and verify its exact scope.
        pending=(await until(lambda:runtime.messager_task_execution.work('local',bot['id'])['interactions']))[0]
        assert pending['kind']=='approval' and pending['operation']['tool_name']=='todo.inbox.create'
        runtime.messager_task_execution.respond('local',bot['id'],result['run_id'],pending['id'],
            pending['review_hash'],'approve-background-write',{'decision':'approve','scope':'once'})
        await until(lambda:next((r for r in runtime.todo.store.snapshot('local')['runs'] if r['id']==result['run_id'] and r['status']=='completed'),None))
        snapshot=runtime.todo.store.snapshot('local');assert len(snapshot['tasks'])==2 and len(snapshot['runs'])==1
        plain=next(t for t in snapshot['tasks'] if t['title']=='Background ordinary follow-up')
        assert runtime.todo.store.get('local',plain['id'])['schedule']['frequency']=='off'
        assert runtime.messager_bot_notifications.inbox('local')['items']==[]
    finally:await runtime.stop_background_tasks()


def test_effect_contract_changes_remove_write_provider_without_silent_upgrade(runtime,monkeypatch):
    bot,sid,run,ctx=foreground(runtime,[{'id':'todo.inbox.create','foreground':True,'background':False}])
    permissions=runtime.messager_bot_permissions;before=permissions.capture('local',{'bot_id':bot['id']},'user')
    original=runtime.services.get_tool
    def changed(name):
        tool=original(name)
        return replace(tool,effects=('network.send',)) if name=='todo.inbox.create' else tool
    monkeypatch.setattr(runtime.services,'get_tool',changed)
    profile=next(p for p in permissions.catalog('local',bot['id'])['items'] if p['id']=='todo.inbox.create')
    assert not profile['available'] and profile['needs_review']
    with pytest.raises(PermissionError):permissions.validate('local',{'bot_id':bot['id']},before,'todo.inbox.create',{'title':'Denied'})


@pytest.mark.asyncio
@pytest.mark.parametrize('finish,notify,enabled,expected',[('completed',True,True,True),('completed',False,True,False),('cancelled',True,True,True),('cancelled',True,False,False)])
async def test_task_wait_and_terminal_notices_reuse_original_run_and_policy(runtime,finish,notify,enabled,expected):
    bot,sid,tasks=task_setup(runtime);notices=runtime.messager_bot_notifications
    policy=notices.policy('local',bot['id'])
    notices.save_policy('local',bot['id'],policy['revision'],{**policy['policy'],'success':enabled,'failure':enabled})
    runtime.agent_runtime.bind_model_provider(fixture_model());await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        source=runtime.app_chat.submit(P(),sid,'task-source','Prepare work','fixture');await wait(runtime,source,'completed')
        proposal=tasks.work('local',bot['id'])['proposals'][0]
        # Use the real owner approval path but select quiet completion through the
        # owner proposal before creation when this fixture requests that policy.
        if not notify:
            ctx=runtime.tools.context_for_session(caller_id='fixture',session_id=sid,trace_id=runtime.app_chat.submit(P(),sid,'quiet-source','Prepare a quiet task','fixture'))
            ref=tasks.propose({'title':'Background fixture','prompt':'TASK_EXECUTION_FIXTURE','notify':False},replace(ctx,invocation_id='quiet-task'))
            row=tasks.proposal('local',bot['id'],ref['proposal_id']);proposal={'id':row['id'],'review_hash':row['review_hash']}
        receipt=tasks.decide('local',bot['id'],proposal['id'],proposal['review_hash'],'approve')
        interaction=(await until(lambda:tasks.work('local',bot['id'])['interactions']))[0]
        waiting=(await until(lambda:[n for n in notices.inbox('local')['items'] if n['kind']=='waiting']))[0]
        resolved=notices.resolve('local',waiting['id'])
        assert resolved['todo_run_id']==receipt['run_id'] and resolved['interaction_id']==interaction['id']
        assert runtime.agents.list_interactions(interaction['run_id'])[0].status.value=='pending'
        assert notices.read('local',waiting['id'])['task']['id']==receipt['task_id']
        assert runtime.agents.list_interactions(interaction['run_id'])[0].status.value=='pending'
        if finish=='completed':
            tasks.respond('local',bot['id'],receipt['run_id'],interaction['id'],interaction['review_hash'],'reply',{'answer':'Tomorrow'})
            await wait(runtime,interaction['run_id'],'completed')
        else:await runtime.todo.cancel('local',receipt['run_id'])
        await until(lambda:next((r for r in runtime.todo.store.snapshot('local')['runs'] if r['id']==receipt['run_id'] and r['status']==finish),None))
        tasks.recover();tasks.recover()
        with pytest.raises(PermissionError):notices.resolve('local',waiting['id'])
        current=[n for n in notices.inbox('local')['items'] if n['kind'] in ('success','failure')]
        assert bool(current)==expected
        with runtime.database.transaction() as db:
            rows=db.execute('SELECT * FROM messager_local_notices WHERE operation_key=?',('task-result:'+receipt['run_id'],)).fetchall()
        assert len(rows)==1 and bool(rows[0]['muted'])!=expected
        assert len(runtime.todo.store.snapshot('local')['runs'])==1
    finally:await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_existing_outbox_uses_generic_preview_and_rechecks_route_and_revocation(runtime,monkeypatch):
    bot,sid,run,ctx=foreground(runtime,[{'id':'messager.notice.create','foreground':True,'background':False}])
    notices=runtime.messager_bot_notifications;producer=runtime.remote.notifications
    result=await invoke(runtime,'messager.notice.create',{'title':'PRIVATE_TITLE_MARKER','body':'PRIVATE_BODY_MARKER'},ctx,'safe-preview')
    monkeypatch.setattr(producer,'identity',lambda:{'owner_id':'local','device_id':'fixture','installation_id':'local','access_epoch':1,'device_epoch':1,'credential_version':1,'cloud_origin':'https://fixture.invalid'})
    monkeypatch.setattr(producer,'supports_custom',lambda target:target=='app_route')
    with runtime.database.transaction(write=True) as db:db.execute("UPDATE app_definitions SET manifest_json=json_set(manifest_json,'$.navigation.status','active') WHERE package_id='ai2apps.messager'")
    notices.reconcile_and_enqueue();notices.reconcile_and_enqueue()
    with runtime.database.transaction() as db:rows=db.execute("SELECT body_json FROM notification_producer_outbox WHERE event_id=?",('messager.notice:'+result['notification_id'],)).fetchall()
    assert len(rows)==1
    body=json.loads(rows[0][0]);assert 'PRIVATE_' not in rows[0][0]
    assert notices.delivery_guard(body)
    destination=routes(runtime).resolve(P(),body['target'])
    assert destination['parameters']=={'notification-route':'bot-notice','notification-resource':result['notification_id']}
    with pytest.raises(PermissionError):notices.authorize_route(replace(P(),actor_user_id='foreign'),result['notification_id'])
    notices.read('local',result['notification_id']);assert not notices.delivery_guard(body)
    body['target']['id']='forged';assert not notices.delivery_guard(body)


@pytest.mark.asyncio
async def test_notification_policy_same_origin_revision_and_strict_fields(runtime):
    bot,sid,run,ctx=foreground(runtime);app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P))
    base='/messager/bots/'+bot['id']+'/notification-policy'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        policy=(await c.get(base)).json()
        assert (await c.put(base,json=policy)).status_code==403
        changed=await c.put(base,json={'revision':0,'policy':{**policy['policy'],'waiting':False}},headers={'Origin':'http://test'})
        assert changed.status_code==200 and changed.json()['revision']==1
        assert (await c.put(base,json=policy,headers={'Origin':'http://test'})).status_code==409
        assert (await c.put(base,json={'revision':1,'policy':{'waiting':'true'}},headers={'Origin':'http://test'})).status_code==422
        assert (await c.get('/messager/notices')).json()['unread_count']==0


@pytest.mark.asyncio
async def test_muted_self_reminder_is_not_resurrected_when_policy_changes(runtime):
    bot,sid,run,ctx=foreground(runtime,[{'id':'messager.notice.create','foreground':True,'background':False}])
    notices=runtime.messager_bot_notifications;p=notices.policy('local',bot['id'])
    notices.save_policy('local',bot['id'],p['revision'],{**p['policy'],'reminder':False})
    args={'title':'Quiet self reminder'}
    original=await invoke(runtime,'messager.notice.create',args,ctx,'muted')
    assert original['muted'] and notices.inbox('local')['items']==[]
    p=notices.policy('local',bot['id']);notices.save_policy('local',bot['id'],p['revision'],{**p['policy'],'reminder':True})
    assert await invoke(runtime,'messager.notice.create',args,ctx,'muted')==original
    assert notices.inbox('local')['items']==[]
    fresh=await invoke(runtime,'messager.notice.create',args,ctx,'fresh')
    assert not fresh['muted'] and len(notices.inbox('local')['items'])==1


@pytest.mark.asyncio
async def test_read_backlog_does_not_block_new_alert_and_policy_withdraws_pending_offline(runtime,monkeypatch):
    bot,sid,run,ctx=foreground(runtime,[{'id':'messager.notice.create','foreground':True,'background':False}])
    notices=runtime.messager_bot_notifications;producer=runtime.remote.notifications
    monkeypatch.setattr(producer,'identity',lambda:{'owner_id':'local','device_id':'fixture'})
    monkeypatch.setattr(producer,'supports_custom',lambda _:True)
    for index in range(51):
        result=await invoke(runtime,'messager.notice.create',{'title':'Reminder '+str(index)},ctx,'backlog-'+str(index))
        if index<50:notices.read('local',result['notification_id'])
    notices.reconcile_and_enqueue()
    with runtime.database.transaction() as db:row=db.execute("SELECT event_id,state FROM notification_producer_outbox").fetchone()
    assert row['event_id']=='messager.notice:'+result['notification_id'] and row['state']=='queued'
    assert producer.cancel_pending([row['event_id']],expected_owner_id='foreign')==0
    policy=notices.policy('local',bot['id'])
    notices.save_policy('local',bot['id'],policy['revision'],{**policy['policy'],'reminder':False})
    with runtime.database.transaction() as db:assert db.execute('SELECT state FROM notification_producer_outbox').fetchone()[0]=='cancelled'
    policy=notices.policy('local',bot['id']);notices.save_policy('local',bot['id'],policy['revision'],{**policy['policy'],'reminder':True})
    notices.reconcile_and_enqueue()
    with runtime.database.transaction() as db:assert db.execute('SELECT state FROM notification_producer_outbox').fetchone()[0]=='cancelled'


@pytest.mark.asyncio
async def test_notification_restart_preserves_original_wait_and_completion_once(runtime):
    from ai2apps.platform_runtime import PlatformRuntime
    bot,sid,tasks=task_setup(runtime);runtime.agent_runtime.bind_model_provider(fixture_model())
    await runtime.start_background_tasks(retention_interval_seconds=60)
    fresh=None
    try:
        source=runtime.app_chat.submit(P(),sid,'restart-source','Prepare work','fixture');await wait(runtime,source,'completed')
        proposal=tasks.work('local',bot['id'])['proposals'][0]
        receipt=tasks.decide('local',bot['id'],proposal['id'],proposal['review_hash'],'approve')
        item=(await until(lambda:tasks.work('local',bot['id'])['interactions']))[0]
        notice=(await until(lambda:runtime.messager_bot_notifications.inbox('local')['items']))[0]
        await runtime.stop_background_tasks();runtime.stop()
        fresh=PlatformRuntime(runtime.config);fresh.start();install(fresh)
        fresh.agent_runtime.bind_model_provider(fixture_model());await fresh.start_background_tasks(retention_interval_seconds=60)
        restored=fresh.messager_bot_notifications.inbox('local')['items']
        assert len(restored)==1 and restored[0]['id']==notice['id']
        resolved=fresh.messager_bot_notifications.read('local',notice['id'])
        assert resolved['interaction_id']==item['id'] and resolved['todo_run_id']==receipt['run_id']
        fresh.messager_task_execution.respond('local',bot['id'],receipt['run_id'],item['id'],item['review_hash'],'original-reply',{'answer':'Tomorrow'})
        await wait(fresh,item['run_id'],'completed')
        await until(lambda:any(n['kind']=='success' for n in fresh.messager_bot_notifications.inbox('local')['items']))
        fresh.messager_task_execution.recover()
        assert len(fresh.messager_bot_notifications.inbox('local')['items'])==1
        assert len(fresh.todo.store.snapshot('local')['runs'])==1
    finally:
        if fresh:await fresh.stop_background_tasks();fresh.stop()
        else:await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_background_write_grant_does_not_expand_a_hook_detail_delegation(env):
    from ai2apps.agents.general import _tool_alias
    runtime,h,_,emit,proposal,enable=env
    install(runtime);bot=restricted_bot(runtime,runtime.messager_bots.create('local','Hook fixture','Review the exact event'))
    permissions=runtime.messager_bot_permissions
    permissions.save('local',bot['id'],1,[{'id':'todo.inbox.create','foreground':False,'background':True}],review_hash=permissions.review_hash())
    value=proposal('messager.bot.observe');value['consumer']['binding']={'bot_id':bot['id']};value['execution']['settings']={'model':'fixture'}
    rule=enable(value);emit();observed=[]
    async def model(request):
        observed.append(request)
        assert _tool_alias('todo.inbox.create') not in {t['function']['name'] for t in request['tools']}
        return response(text='Read-only event review completed.')
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        from test_event_hook_execution import settled
        await settled(runtime,rule)
        assert observed and store(runtime).snapshot('local')['tasks']==[]
    finally:await runtime.stop_background_tasks()
