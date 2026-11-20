"""Real owner policies/SQLite/Todo; arbitrary fixture capabilities, no external effects."""
import asyncio,json
from dataclasses import replace
from types import SimpleNamespace
import pytest
from test_app_interactions import runtime,wait
from test_bot_capability_discovery import setup,P
from test_app_chat_durable import bind_identity,response
from ai2apps.messager.tasks import TASK_CHAT
from ai2apps.services.capability_routing import CapabilityProvider


def prepare(r,mode='fixed',special=False):
    bot,sid,calls,p=setup(r)
    if special:
        r.app_capability_router.providers[p.id]=p=replace(p,access_policy='confirm')
    from ai2apps.todo.service import TodoService
    if r.todo is None:r.todo=TodoService(r)
    tasks=r.messager_task_execution
    rid=r.app_chat.submit(P(),sid,'prepare-plan','Prepare future work','fixture')
    proposed=tasks.propose({'title':'Fixture plan','prompt':'Perform the fixture job','schedule':{'frequency':'daily','hour':6},'access_requirements':[{'capability':p.capability,'provider':p.id,'reason':'Requested output'}]},SimpleNamespace(actor_user_id='local',session_id=sid,trace_id=rid,invocation_id='preflight'))
    item=next(x for x in tasks.work('local',bot['id'])['proposals'] if x['id']==proposed['proposal_id'])
    before=r.messager_bot_app_access.current('local',bot['id'])
    saved=tasks.decide('local',bot['id'],item['id'],item['review_hash'],'approve',mode,[p.app_id])
    assert (r.messager_bot_app_access.current('local',bot['id'])==before)==(mode=='auto')
    r.agents.request_cancel(rid)  # Fixture prepared a proposal directly; do not execute that synthetic foreground Run.
    binding=r.todo.store.execution_binding('local',saved['task_id'])['binding']
    return bot,sid,calls,p,tasks,item,saved,binding


@pytest.mark.parametrize('mode',['fixed','auto'])
def test_plan_scope_no_business_execution_no_permanent_grant_and_pins(runtime,mode):
    bot,sid,calls,p,tasks,item,saved,b=prepare(runtime,mode)
    assert calls==[] and saved['run_id'] is None
    assert runtime.messager_bot_app_access.granted('local',bot['id'],p)==(mode=='fixed')
    assert tasks.authorization('local',bot['id'],b['authorization'],p.capability,{}) is True
    with pytest.raises(PermissionError):tasks.authorization('local',bot['id'],b['authorization'],'missing.other',{})
    other=runtime.messager_bots.create('local','Other','Help')
    with pytest.raises(PermissionError):tasks.authorization('local',other['id'],b['authorization'])
    runtime.app_capability_router.providers[p.id]=replace(p,version='changed')
    with pytest.raises(PermissionError):tasks.authorization('local',bot['id'],b['authorization'],p.capability,{})
    assert calls==[]


def test_required_scope_replay_and_revocation(runtime):
    bot,sid,calls,p,tasks,item,saved,b=prepare(runtime)
    with pytest.raises(ValueError):tasks.decide('local',bot['id'],item['id'],item['review_hash'],'approve','auto',[p.app_id])
    assert tasks.decide('local',bot['id'],item['id'],item['review_hash'],'approve','fixed',[p.app_id])==saved
    tasks.access.revoke('local',bot['id'],item['id'])
    assert runtime.todo.store.get('local',saved['task_id'])['next_due'] is None
    with pytest.raises(PermissionError):tasks.validate_task('local',runtime.todo.store.get('local',saved['task_id']),b)


def test_preflight_required_optional_cross_provider_and_epoch(runtime):
    bot,sid,calls,p,tasks,item,saved,b=prepare(runtime)
    access=tasks.access;base=runtime.messager_bot_permissions.capture('local',{'bot_id':bot['id']},'hook')
    q=replace(p,id='unrelated.owner',app_id='ai2apps.knowledge',capability='unrelated.make')
    tool=runtime.services.get_tool(p.capability)
    runtime.services.ensure_tool(service_id=tool.service_id,qualified_name=q.capability,display_name='Other',description='Other fixture',input_schema=tool.input_schema,output_schema=tool.output_schema,effects=tool.effects,required_capabilities=())
    runtime.app_capability_router.register(q)
    runtime.app_capability_router.providers[p.id]=replace(p,related_capabilities=(q.capability,))
    pre=access.preflight('local',bot['id'],[{'capability':p.capability,'reason':'Requested'}],base)
    targets={a['app_id']:a for a in pre['apps']}
    assert targets[p.app_id]['required'] and targets[q.app_id]['predicted'] and not targets[q.app_id]['required']
    with pytest.raises(ValueError):access.seal('local',bot['id'],'missing-required',pre,base,'fixed',[])
    access.seal('local',bot['id'],'optional-excluded',pre,base,'fixed',[p.app_id])
    runtime.messager_bot_permissions.invalidate('local',bot['id'])
    with pytest.raises(PermissionError):access.validate('local',bot['id'],b['authorization'])
    assert calls==[]


@pytest.mark.asyncio
@pytest.mark.parametrize('special',[False,True])
async def test_original_task_run_auto_admission_and_special_once(runtime,special):
    bot,sid,calls,p,tasks,item,saved,b=prepare(runtime,'auto',special)
    async def model(request):
        if any(m.get('role')=='tool' and 'fixture-output' in m.get('content','') for m in request['messages']):return response(text='Done')
        return response(p.capability,{'prompt':'fixture'})
    runtime.agent_runtime.bind_model_provider(model)
    # Original proposal dialogue is unrelated to execution and must not run fixture effects.
    runtime.agents.request_cancel(runtime.app_chat.snapshot(P(),sid)['active_run_id']) if runtime.app_chat.snapshot(P(),sid).get('active_run_id') else None
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        launched=runtime.todo.launch('local',saved['task_id'],principal=P(),request_key='fixture-launch')
        for _ in range(600):
            with runtime.database.transaction() as db:row=db.execute('SELECT * FROM messager_task_runs WHERE todo_run_id=?',(launched['id'],)).fetchone()
            if row and row['agent_run_id']:break
            await asyncio.sleep(.02)
        assert row and row['agent_run_id'];rid=row['agent_run_id']
        await wait(runtime,rid,'waiting_capability' if special else 'completed')
        assert runtime.app_chat.binding(row['session_id'])['registration']==TASK_CHAT
        if special:
            assert not calls
            interaction=next(x for x in tasks.work('local',bot['id'])['interactions'] if x['run_id']==rid)
            assert interaction['schema']['properties']['scope']['enum']==['once']
            tasks.respond('local',bot['id'],launched['id'],interaction['id'],interaction['review_hash'],'fixture-response',{'decision':'approve','scope':'once','resource_scope':'current'})
            await wait(runtime,rid,'completed')
        assert len(calls)==1
        assert runtime.messager_bot_app_access.granted('local',bot['id'],p,include_special=True)
        assert tasks.access.audit('local',bot['id'])[0]['access_admissions']>=1
    finally:await runtime.stop_background_tasks()


def test_amendment_repreflights_new_target_and_preserves_old_snapshot(runtime):
    bot,sid,calls,p,tasks,item,saved,old_binding=prepare(runtime)
    from ai2apps.services.capability_routing import CapabilityProvider
    tool=runtime.services.get_tool(p.capability)
    runtime.services.ensure_tool(service_id=tool.service_id,qualified_name='alternate.archive',display_name='Archive fixture',description='Fixture archive',input_schema=tool.input_schema,output_schema=tool.output_schema,effects=tool.effects,required_capabilities=())
    q=CapabilityProvider('alternate.provider','alternate.archive','ai2apps.knowledge',p.handler)
    runtime.app_capability_router.register(q)
    d=runtime.messager_dialogue;rid=d.submit(P(),bot['id'],sid,'amend-access','Also archive output','fixture',[])
    plan=d.plans.prepare('local',bot['id'],runtime.agents.get_run(rid),saved['task_id'],None,[{'capability':q.capability,'provider':q.id,'reason':'New archive step'}])
    pending=d.plans.pending('local',bot['id'])[0]
    assert any(a['app_id']==p.app_id and a['predicted'] for a in pending['value']['access_preflight']['apps'])
    with pytest.raises(ValueError):d.plans.decide('local',bot['id'],plan['id'],plan['review_hash'],'approve','fixed',[p.app_id])
    d.plans.decide('local',bot['id'],plan['id'],plan['review_hash'],'approve','auto',[p.app_id,q.app_id])
    new=runtime.todo.store.execution_binding('local',saved['task_id'])['binding']
    assert new['authorization']['task_access']['mode']=='auto'
    assert q.id in new['authorization']['providers'] and q.id not in old_binding['authorization']['providers']
    tasks.authorization('local',bot['id'],old_binding['authorization'],p.capability,{})
    with pytest.raises(PermissionError):tasks.authorization('local',bot['id'],old_binding['authorization'],q.capability,{})
    with pytest.raises(ValueError):d.plans.decide('local',bot['id'],plan['id'],plan['review_hash'],'approve','fixed',[p.app_id,q.app_id])


@pytest.mark.asyncio
async def test_host_api_replay_and_revoke_origin_guard(runtime):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.messager import create_messager_router
    bot,sid,calls,p,tasks,item,saved,b=prepare(runtime)
    app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P))
    url='/messager/bots/'+bot['id']+'/task-access/'+item['id']+'/revoke'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Origin':'http://test'}) as c:
        assert (await c.post(url,headers={'Origin':'null'})).status_code==403
        assert (await c.post(url.replace(bot['id'],'other-bot'))).status_code in (403,404)
        assert (await c.post(url)).status_code==200
        assert (await c.post(url)).status_code==200
    assert not calls


def test_oversized_plan_snapshot_rejected_before_policy_commit(runtime,monkeypatch):
    bot,sid,calls,p,tasks,item,saved,b=prepare(runtime)
    access=tasks.access;base=runtime.messager_bot_permissions.capture('local',{'bot_id':bot['id']},'hook')
    pre=access.preflight('local',bot['id'],[],base)
    entry=next(a for a in pre['apps'] if a['app_id']==p.app_id)
    entry['pins']={('provider-'+str(i)):dict(access.pin(p),capability='x'*256) for i in range(150)}
    # Isolate the byte-budget guard; real declaration/version checks covered above.
    monkeypatch.setattr(access,'check_pin',lambda *args:p)
    with pytest.raises(ValueError,match='snapshot is too large'):access.seal('local',bot['id'],'oversized-fixture',pre,base,'fixed',[p.app_id])
    with runtime.database.transaction() as db:assert db.execute('SELECT 1 FROM messager_task_access_policies WHERE id=?',('oversized-fixture',)).fetchone() is None


@pytest.mark.asyncio
async def test_plan_parameter_form_stays_in_original_run_and_cannot_expand_target(runtime):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.agents.parameter_forms import ParameterForm,register_form,FORMS
    bot,sid,calls,p,tasks,item,saved,b=prepare(runtime,'auto')
    with pytest.raises(PermissionError):tasks.authorization('local',bot['id'],b['authorization'],'app.collect_parameters',{'capability':'unapproved.target'})
    register_form(ParameterForm(p.id,p.app_id,runtime.services.get_tool(p.capability).input_schema,capability=p.capability,provider_version=p.version))
    async def model(request):
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        if any(x.get('created') for x in results):return response(text='Done')
        if any(x.get('status')=='completed' for x in results):return response(p.capability,{'prompt':'supplied'})
        if not any(x.get('providers') for x in results):return response('app.describe',{'capability':p.capability})
        return response('app.collect_parameters',{'request_id':'plan-form','capability':p.capability,'provider':p.id,'values':{}})
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        launched=runtime.todo.launch('local',saved['task_id'],principal=P(),request_key='plan-form-launch')
        for _ in range(600):
            with runtime.database.transaction() as db:row=db.execute('SELECT * FROM messager_task_runs WHERE todo_run_id=?',(launched['id'],)).fetchone()
            if row and row['agent_run_id']:break
            await asyncio.sleep(.02)
        rid=row['agent_run_id'];await wait(runtime,rid,'waiting_input')
        interaction=next(x for x in tasks.work('local',bot['id'])['interactions'] if x['run_id']==rid)
        assert interaction['control']=='parameter_form' and not calls
        assert tasks.access.audit('local',bot['id'])[0]['access_admissions']==0
        app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=P))
        url=f'/v1/platform/agent-runs/{rid}/interactions/{interaction["id"]}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            current=await client.get(url);assert current.status_code==200,current.text
            draft=await client.put(url,json={'revision':current.json()['revision'],'values':{'prompt':'supplied'}})
            assert draft.status_code==200,draft.text
            result=await client.post(url+'/submit',json={'revision':draft.json()['revision'],'values':{'prompt':'supplied'}})
            assert result.status_code==200,result.text
        await wait(runtime,rid,'completed');assert calls==[({'prompt':'supplied'},row['session_id'])]
    finally:
        FORMS.pop(p.id,None);await runtime.stop_background_tasks()


def test_auto_admission_rechecks_revocation_before_saving_bot_access(runtime):
    bot,sid,calls,p,tasks,item,saved,b=prepare(runtime,'auto')
    frozen=b['authorization'];scope={'bot_id':bot['id'],'task_id':saved['task_id'],'todo_run_id':'fixture-admission'}
    with runtime.database.transaction(write=True) as db:
        db.execute('INSERT INTO messager_task_runs VALUES(?,?,?,?,?,?,?,?,?)',('fixture-admission','local',bot['id'],saved['task_id'],item['id'],json.dumps(frozen),'{}',None,None))
    runtime.messager_bot_permissions.invalidate('local',bot['id'])
    with pytest.raises(PermissionError):tasks.access.admit_call('local',bot['id'],frozen,scope,p.capability,{})
    assert not runtime.messager_bot_app_access.granted('local',bot['id'],p)


def test_inherited_plan_captures_new_grants_and_rejects_revoked_access(runtime):
    from test_bot_app_access import save

    bot,_,_,p,tasks,_,_,binding=prepare(runtime,'inherit')
    plan=binding['authorization']
    base=tasks.permissions.capture('local',{'bot_id':bot['id']},'hook')
    review=tasks.access.preflight('local',bot['id'],[{'capability':'intelligence.channels','reason':'Read saved channels'}],base)
    inherited_app=next(app for app in review['apps'] if 'intelligence.channels' in app['capabilities'])
    assert inherited_app['current_access']
    tasks.access.seal('local',bot['id'],'existing-read-grant',review,base,'inherit',[])
    first=tasks.access.capture('local',bot['id'],plan)
    assert tasks.authorization('local',bot['id'],first,p.capability,{})
    target=runtime.messager_bots.create('local','Receiver','Fixture receiver')
    access=runtime.messager_bot_access
    access.set_link('local',bot['id'],target['id'],True,access.catalog('local',bot['id'])['revision'])
    assert target['id'] not in first['bot_links']
    assert target['id'] in tasks.access.capture('local',bot['id'],plan)['bot_links']

    save(runtime,bot,enabled=False)
    with pytest.raises(PermissionError):
        tasks.authorization('local',bot['id'],first,p.capability,{})
    assert tasks.authorization('local',bot['id'],plan)
    new=tasks.access.capture('local',bot['id'],plan)
    with pytest.raises(PermissionError):
        tasks.authorization('local',bot['id'],new,p.capability,{})


def test_plan_review_can_add_exact_directed_bot_access(runtime):
    bot,_,_,_,tasks,_,_,_=prepare(runtime,'inherit')
    target=runtime.messager_bots.create('local','Additional recipient','Fixture receiver')
    base=tasks.permissions.capture('local',{'bot_id':bot['id']},'hook')
    review=tasks.access.preflight('local',bot['id'],[],base)
    assert not runtime.messager_bot_access.link('local',bot['id'],target['id'])['enabled']
    sealed=tasks.access.seal('local',bot['id'],'additional-recipient',review,base,'inherit',[],[target['id']])
    assert runtime.messager_bot_access.link('local',bot['id'],target['id'])['enabled']
    assert target['id'] in tasks.access.capture('local',bot['id'],sealed)['bot_links']
    with pytest.raises(ValueError):
        tasks.access.seal('local',bot['id'],'additional-recipient',review,base,'inherit',[],[])


@pytest.mark.asyncio
@pytest.mark.parametrize('ending', ['completed', 'expired', 'observer_failed', 'tree_approval', 'auto_tree_approval'])
async def test_system_clock_delegates_with_current_bot_access(runtime,monkeypatch,ending):
    from datetime import UTC, datetime
    from test_bot_app_access import save
    from test_bot_delegation import until
    from ai2apps.messager.communication import DIRECTORY
    from ai2apps.messager.delegation import BUDGET, DELEGATE
    from ai2apps.todo.system_schedules import KIND

    bot,_,calls,p,_,_,saved,_=prepare(runtime,'inherit')
    target=runtime.messager_bots.create('local','Channel specialist','Produces a watch news brief')
    if ending in ('tree_approval','auto_tree_approval'):
        from bot_access_fixtures import restricted_bot
        restricted_bot(runtime,target)
        restricted_bot(runtime,bot)
        if ending=='auto_tree_approval':
            runtime.messager_bot_app_access.set_approval_rule('local',target['id'],'always',0)
    else:
        save(runtime,target)
    access=runtime.messager_bot_access
    access.set_link('local',bot['id'],target['id'],True,access.catalog('local',bot['id'])['revision'])
    if ending == 'expired':
        monkeypatch.setitem(BUDGET, 'timeout_seconds', 0)
    if ending == 'observer_failed':
        from ai2apps.messager.delegation import OBSERVER
        async def fail_observer(ctx):
            raise OSError('Fixture: observer storage unavailable')
        handlers = runtime.system_tasks.handlers
        monkeypatch.setitem(handlers, OBSERVER, replace(handlers[OBSERVER], execute=fail_observer))

    async def model(request):
        messages=request['messages']
        text='\n'.join(str(m.get('content','')) for m in messages)
        results=[json.loads(m['content']) for m in messages if m.get('role')=='tool']
        if 'Summarize channel news' in text:
            if any(v.get('created') for v in results):
                return {**response(text='Five watch news headlines from the channel'),
                        'usage':{'prompt_tokens':40,'completion_tokens':10}}
            if not any(v.get('providers') for v in results):
                return response('app.describe',{'capability':p.capability})
            return response(p.capability,{'prompt':'child work'})
        if any('Five watch news headlines' in v.get('content','') for v in results):
            return response(text='Scheduled Bot received the brief')
        for result in results:
            if result.get('delegation_id') and result.get('status') in ('expired','failed'):
                assert result['status']==('expired' if ending=='expired' else 'failed')
                assert result['child_status']=='not_admitted'
                assert result['child_started'] is False and result['outcome_uncertain'] is False
                return response(text='Child did not start. Verified source results preserved.')
        if not any(v.get('items') for v in results):
            if not any(v.get('providers') for v in results):return response('app.describe',{'capability':DIRECTORY})
            return response(DIRECTORY,{})
        assert next(v['items'] for v in results if v.get('items'))[0]['id']==target['id']
        if not any(v.get('providers') and DELEGATE in str(v) for v in results):
            return response('app.describe',{'capability':DELEGATE})
        return response(DELEGATE,{'target_bot_id':target['id'],'title':'Watch news','instructions':'Summarize channel news'})

    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        system=runtime.system_tasks
        system.max_per_owner=1
        system.max_per_app=1
        schedule=next(s for s in system.snapshot('local')['schedules'] if s['kind']==KIND)
        now=datetime.fromtimestamp(schedule['next_run']+1,UTC)
        system.clock=lambda:now.timestamp()
        await system.tick()

        def actual_run():
            with runtime.database.transaction() as db:
                return db.execute('SELECT * FROM messager_task_runs WHERE task_id=? AND agent_run_id IS NOT NULL',(saved['task_id'],)).fetchone()
        row=await until(actual_run)
        if ending=='tree_approval':
            app_access=runtime.messager_bot_app_access
            delegation=runtime.messager_bot_delegation
            child=await until(lambda:next((entry['runs'][0] for entry in delegation.work('local',bot['id']) if entry['runs']),None))
            item=child['interactions'][0]
            review=app_access.request('local',bot['id'],child['id'],item['id'])
            assert review['task_tree'] and not review['access_granted']
            app_access.allow('local',bot['id'],child['id'],item['id'],review['request_hash'])
            assert not app_access.granted('local',bot['id'],p)
            assert not app_access.granted('local',target['id'],p)
        run=await until(lambda: r if (r:=runtime.agents.get_run(row['agent_run_id'])).status.value=='completed' else None)
        if ending in ('expired','observer_failed'):
            assert 'Verified source results preserved.' in run.output['content']
            assert not calls and not runtime.agents.list_interactions(run.id)
            return
        assert 'Scheduled Bot received the brief' in run.output['content']
        assert len(calls)==1
        if ending=='auto_tree_approval':
            app_access=runtime.messager_bot_app_access
            assert app_access.tree.granted('local',row['todo_run_id'],p)
            assert not app_access.granted('local',bot['id'],p)
            assert not app_access.granted('local',target['id'],p)
        def reject_full_export(scope):
            pytest.fail('Provider visibility must not rebuild all task exports')
        owner=runtime.app_chat.owners[TASK_CHAT]
        monkeypatch.setitem(runtime.app_chat.owners,TASK_CHAT,replace(owner,exports=reject_full_export))
        provider=runtime.app_capability_router.providers[p.id]
        assert runtime.app_chat.provider_visible(row['session_id'],provider)
        with runtime.database.transaction() as db:
            child=db.execute('SELECT target_bot,status FROM messager_bot_delegations WHERE source_run=?',(run.id,)).fetchone()
        assert tuple(child)==(target['id'],'resumed')
        from ai2apps.messager.statistics import statistics
        usage=statistics(runtime,'local',bot['id'],todo_task_id=saved['task_id'])['task_usage']
        assert usage['delegated']['known_tokens']>=50
        assert usage['total']['known_tokens']>=usage['delegated']['known_tokens']
    finally:
        await runtime.stop_background_tasks()
