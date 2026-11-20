"""C2 owner coordination using real SQLite/Todo/Run with deterministic models."""
import asyncio,json
from dataclasses import replace
import pytest
from test_app_chat_durable import bind_identity,response
from test_app_interactions import runtime,wait
from test_bot_capability_discovery import setup,P
from test_bot_app_access import save
from ai2apps.messager.delegation import DELEGATE

async def until(check):
    for _ in range(600):
        v=check()
        if v:return v
        await asyncio.sleep(.03)
    raise AssertionError('Expected collaboration state did not arrive')

async def start(r,*,special=False,source_access=True,bot_use=False,child_discovery_tokens=10,target_access=True,reuse_approval=False, approval_risk=None, reviews=None):
    bot,sid,calls,provider=setup(r)
    target=r.messager_bots.create('local','Child specialist','Execute the requested child work')
    if source_access is not None:save(r,bot,enabled=source_access)
    if target_access is not None:
        save(r,target,enabled=target_access)
    else:
        from bot_access_fixtures import restricted_bot
        restricted_bot(r,target)
    if bot_use:
        access=r.messager_bot_access
        access.set_mode('local',target['id'],'private',access.catalog('local',target['id'])['revision'])
        access.set_link('local',bot['id'],target['id'],True,access.catalog('local',bot['id'])['revision'])
    if special:r.app_capability_router.providers[provider.id]=replace(provider,access_policy='confirm')
    async def model(request):
        if request['messages'][0]['content'].startswith('Review a proposed Tool invocation'):
            reviews.append(json.loads(request['messages'][1]['content']))
            return response(text=json.dumps({'risk':approval_risk,'necessary':True,'reason':'fixture'}))
        if 'Decide quickly' in request['messages'][0]['content']:
            return response(text=json.dumps({'kind':'reply' if request['messages'][-1]['content']=='hello' else 'task','text':'hello back','title':'Parent goal'}))
        text='\n'.join(str(m.get('content','')) for m in request['messages'])
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        if any(m.get('role')=='assistant' and m.get('content')=='Child canonical deliverable' for m in request['messages']):
            if reuse_approval and not any(v.get('created') for v in results):
                if not any(v.get('providers') for v in results):
                    return response('app.describe',{'capability':provider.capability})
                return response(provider.capability,{'prompt':'root follow-up'})
            return response(text='Parent used the completed child result')
        if any(m.get('role')=='user' and m.get('content')=='independent marker' for m in request['messages']):return response(text='Independent task finished')
        if any(m.get('role')=='user' and m.get('content')=='Produce the requested fixture output' for m in request['messages']):
            if any(v.get('created') for v in results):return response(text='Child canonical deliverable')
            if not any(v.get('providers') for v in results):
                return {**response('app.describe',{'capability':provider.capability}),
                        'usage':{'total_tokens':child_discovery_tokens}}
            return response(provider.capability,{'prompt':'child work'})
        return response(DELEGATE,{'target_bot_id':target['id'],'title':'Child output','instructions':'Produce the requested fixture output'})
    r.agent_runtime.bind_model_provider(model);await r.start_background_tasks(retention_interval_seconds=60)
    rid=r.messager_dialogue.submit(P(),bot['id'],sid,'parent-user-request','Delegate and summarize','fixture',[])
    await wait(r,rid,'completed')
    card=await until(lambda:next(iter(r.messager_bot_delegation.work('local',bot['id'])),None))
    job=r.messager_dialogue.row(r.messager_bot_delegation.row(card['id'])['parent_job'])
    await wait(r,job['worker_run'],'completed')
    return bot,target,sid,calls,provider,card,job

@pytest.mark.asyncio
async def test_delegated_tool_task_releases_parent_lane_and_resumes_same_session(runtime):
    try:
        bot,target,sid,calls,provider,card,parent=await start(runtime)
        service=runtime.messager_bot_delegation
        assert not calls and card['status']=='pending'
        assert runtime.messager_dialogue.snapshot(P(),bot['id'],sid)['task_sessions'][0]['status']=='waiting_collaboration'
        hello=runtime.messager_dialogue.submit(P(),bot['id'],sid,'parallel-hello','hello','fixture',[])
        await wait(runtime,hello,'completed');assert runtime.agents.get_run(hello).output['kind']=='reply'
        independent=runtime.messager_dialogue.submit(P(),bot['id'],sid,'independent-task','independent marker','fixture',[])
        await wait(runtime,independent,'completed')
        await until(lambda: any('Independent task finished' in m['content'] for m in runtime.app_chat.message_page(P(),sid)['items']))
        service.decide('local',bot['id'],card['id'],card['review_hash'],'approve')
        service.decide('local',bot['id'],card['id'],card['review_hash'],'approve')
        row=await until(lambda:service.row(card['id']) if service.row(card['id'])['status']=='resumed' else None)
        child=runtime.messager_dialogue.row(row['child_job']);resume=runtime.messager_dialogue.row(row['resume_job'])
        try:await until(lambda:runtime.messager_dialogue.row(resume['id'])['status']=='completed')
        except AssertionError:
            observed=runtime.messager_dialogue.row(resume['id'])
            with runtime.todo.store.connect() as db:todo=[dict(r) for r in db.execute('SELECT status,data FROM runs WHERE task_id=?',(observed['task_id'],))]
            raise AssertionError((observed,runtime.agents.get_run(observed['worker_run']).error if observed['worker_run'] else None,todo))
        resume=runtime.messager_dialogue.row(resume['id'])
        resumed_source=runtime.agents.get_run(resume['source_run'])
        resumed_worker=runtime.agents.get_run(resume['worker_run'])
        assert resumed_worker.input['prompt'].startswith('Delegated work has completed.')
        assert resumed_source.input['owner_context']['original_task_request']=='Delegate and summarize'
        assert resumed_worker.input['owner_context']['collaboration_result']['data_trust']=='untrusted'
        assert len(calls)==1
        assert child['bot_id']==target['id'] and child['task_id'] and resume['worker_session']==parent['worker_session']
        assert runtime.messager_dialogue.sessions.for_job(resume['id'])['id']==runtime.messager_dialogue.sessions.for_job(parent['id'])['id']
        messages=[m['content'] for m in runtime.app_chat.message_page(P(),sid)['items']]
        assert any('Parent used' in m for m in messages)
        accepted=next(i for i,m in enumerate(messages) if '已接受子任务并排队执行' in m)
        started=[i for i,m in enumerate(messages) if '协作已开始：「Child specialist」正在处理「Child output」' in m]
        result=next(i for i,m in enumerate(messages) if 'Child canonical deliverable' in m)
        assert len(started)==1 and accepted<started[0]<result
        service.recover();assert service.row(card['id'])['resume_job']==resume['id']
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
@pytest.mark.parametrize('continue_work',[True,False])
async def test_child_model_budget_waits_in_origin_and_resumes_same_run(runtime,continue_work):
    from datetime import UTC, datetime, timedelta
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from ai2apps.agents.token_budget import CONTINUE, STOP
    from ai2apps.api.agents import create_agent_router
    try:
        bot,target,sid,calls,provider,card,parent=await start(runtime,child_discovery_tokens=64_000)
        service=runtime.messager_bot_delegation
        service.decide('local',bot['id'],card['id'],card['review_hash'],'approve')
        def pending():
            return next((run for run in runtime.messager_dialogue.snapshot(P(),bot['id'],sid)['runs']
                         if run.get('delegation_id')==card['id'] and run['interactions']),None)
        child_run=await until(pending)
        interaction=child_run['interactions'][0]
        assert child_run['status']=='waiting_input' and interaction['request']['collaboration_budget']
        assert interaction['request']['used_tokens']==interaction['request']['additional_tokens']==64_000
        assert not calls
        now=datetime.now(UTC)
        root=card['graph']['root']
        with runtime.database.transaction(write=True) as db:
            db.execute('UPDATE messager_delegation_roots SET deadline=? WHERE id=?',
                       (now.timestamp()-10,root))
            db.execute('UPDATE agent_interactions SET created_at=? WHERE id=?',
                       ((now-timedelta(seconds=60)).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),interaction['id']))
        service.recover()
        assert pending()['interactions'][0]['id']==interaction['id']
        answer={'answer':CONTINUE if continue_work else STOP}
        app=FastAPI()
        app.include_router(create_agent_router(lambda:runtime,P))
        path=f"/agent-runs/{child_run['id']}/interactions/{interaction['id']}/respond"
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
            for _ in range(2):
                reply=await client.post(path,json={'response':answer,'response_id':'same-budget-choice'})
                assert reply.status_code==200,reply.text
        status='resumed' if continue_work else 'cancelled'
        await until(lambda:service.row(card['id'])['status']==status)
        assert runtime.agents.get_run(child_run['id']).status.value=='completed'
        assert len(calls)==int(continue_work)
        with runtime.database.transaction() as db:
            tokens=db.execute('SELECT tokens FROM messager_delegation_leases WHERE lease=?',('child:'+card['id'],)).fetchone()[0]
        assert tokens==(128_000 if continue_work else 64_000)
        assert bool(service.row(card['id'])['resume_job'])==continue_work
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_sensitive_child_approval_is_same_original_interaction_in_both_dialogues(runtime):
    try:
        bot,target,sid,calls,provider,card,parent=await start(runtime,special=True)
        s=runtime.messager_bot_delegation;s.decide('local',bot['id'],card['id'],card['review_hash'],'approve')
        row=await until(lambda:s.row(card['id']) if s.row(card['id'])['child_job'] and runtime.messager_dialogue.row(s.row(card['id'])['child_job'])['worker_run'] else None)
        child=runtime.messager_dialogue.row(row['child_job']);await wait(runtime,child['worker_run'],'waiting_capability')
        a=next(r for r in runtime.messager_dialogue.snapshot(P(),bot['id'],sid)['runs'] if r.get('delegation_id'))
        b=next(r for r in runtime.messager_dialogue.snapshot(P(),target['id'],child['source_session'])['runs'] if r.get('delegation_id'))
        assert a['id']==b['id']==child['worker_run'] and a['interactions'][0]['id']==b['interactions'][0]['id']
        assert not calls
        runtime.agents.respond_interaction(a['id'],a['interactions'][0]['id'],response_id='original-user-once',response={'decision':'approve','scope':'once'})
        runtime.agent_runtime.wake();await until(lambda:s.row(card['id'])['status']=='resumed');assert len(calls)==1
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_reject_or_revoke_never_launches_or_resumes_child(runtime):
    try:
        bot,target,sid,calls,provider,card,parent=await start(runtime)
        s=runtime.messager_bot_delegation
        with pytest.raises(PermissionError):s.decide('local',target['id'],card['id'],card['review_hash'],'approve')
        with pytest.raises(PermissionError):s.get('other',bot['id'],card['id'])
        with pytest.raises(ValueError):s.decide('local',bot['id'],card['id'],'0'*64,'approve')
        s.decide('local',bot['id'],card['id'],card['review_hash'],'reject')
        row=s.row(card['id']);assert row['status']=='rejected' and not row['child_job'] and not row['resume_job'] and not calls
        s.recover();assert s.row(card['id'])==row
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
@pytest.mark.parametrize('action',['cancel','revoke'])
async def test_waiting_child_is_cancelled_without_effect_or_parent_replay(runtime,action):
    try:
        bot,target,sid,calls,provider,card,parent=await start(runtime,special=True)
        s=runtime.messager_bot_delegation;s.decide('local',bot['id'],card['id'],card['review_hash'],'approve')
        row=await until(lambda:s.row(card['id']) if s.row(card['id'])['child_job'] and runtime.messager_dialogue.row(s.row(card['id'])['child_job'])['worker_run'] else None)
        child=runtime.messager_dialogue.row(row['child_job']);await wait(runtime,child['worker_run'],'waiting_capability')
        frozen=runtime.app_chat.execution_authorization(child['worker_run'])
        assert DELEGATE not in frozen.get('discovery_tools',{}) and set(frozen['controls'])=={runtime.messager_bots.memory_returns.provider.id}
        assert runtime.agents.list_interactions(child['worker_run'])[0].response_schema['properties']['scope']['enum']==['once']
        if action=='cancel':await s.cancel('local',bot['id'],card['id'])
        else:runtime.messager_bot_permissions.invalidate('local',target['id'])
        await wait(runtime,child['worker_run'],'cancelled')
        s.recover();row=s.row(card['id'])
        assert row['status']=='cancelled' and not row['resume_job'] and not calls
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_child_can_use_receiver_access_even_if_sender_disabled_it(runtime):
    try:
        bot,target,sid,calls,provider,card,parent=await start(runtime,source_access=False)
        row=runtime.messager_bot_delegation.row(card['id']);v=json.loads(row['value_json'])
        assert provider.id in v['allowed'] and not calls
        runtime.messager_bot_delegation.decide('local',bot['id'],card['id'],card['review_hash'],'reject')
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_origin_api_review_and_admission_gap_recovery_are_idempotent(runtime,monkeypatch):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.messager import create_messager_router
    try:
        bot,target,sid,calls,provider,card,parent=await start(runtime)
        s=runtime.messager_bot_delegation
        app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P))
        path='/messager/bots/'+bot['id']+'/delegations/'+card['id']+'/decisions/approve'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            assert (await client.post(path,json={'review_hash':card['review_hash']})).status_code==403
        original_observer=s.ensure_observer;original_admit=s.admit_child
        monkeypatch.setattr(s,'ensure_observer',lambda row:None)
        def gap(row):raise RuntimeError('fixture crash before child admission')
        monkeypatch.setattr(s,'admit_child',gap)
        with pytest.raises(RuntimeError):s.decide('local',bot['id'],card['id'],card['review_hash'],'approve')
        assert s.row(card['id'])['status']=='admitting' and not calls
        monkeypatch.setattr(s,'ensure_observer',original_observer);monkeypatch.setattr(s,'admit_child',original_admit)
        s.recover();s.recover()
        await until(lambda:s.row(card['id'])['status']=='resumed')
        assert len(calls)==1
    finally:await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_task_access_approval_is_shared_with_parent_but_does_not_change_bot_grants(runtime):
    from ai2apps.core.errors import RepositoryError
    r=runtime
    try:
        bot,target,sid,calls,provider,card,parent=await start(r,source_access=None,target_access=None,reuse_approval=True)
        delegation=r.messager_bot_delegation
        access=r.messager_bot_app_access
        delegation.decide('local',bot['id'],card['id'],card['review_hash'],'approve')
        ref=card['id']
        def pending():
            row=next((entry for entry in delegation.work('local',bot['id']) if entry['id']==ref),None)
            return row['runs'][0] if row and row['runs'] else None
        active=await until(pending)
        interaction=active['interactions'][0]['id']
        with pytest.raises(PermissionError):
            access.request('local',target['id'],active['id'],interaction)
        review=access.request('local',bot['id'],active['id'],interaction)
        assert review['task_tree'] and not review['access_granted'] and not calls
        assert access.allow('local',bot['id'],active['id'],interaction,review['request_hash'])=={'continued':True}
        with pytest.raises((RepositoryError,ValueError)):
            access.allow('local',bot['id'],active['id'],interaction,review['request_hash'])
        resumed=await until(lambda:delegation.row(ref)['resume_job'])
        job=await until(lambda: j if (j:=r.messager_dialogue.row(resumed))['worker_run'] else None)
        await wait(r,job['worker_run'],'completed')
        assert not r.agents.list_interactions(job['worker_run'])
        root=delegation.graph.edge(ref)['root']
        assert access.tree.granted('local',root,provider)
        assert not access.tree.granted('local','unrelated-task',provider)
        assert not access.tree.granted('other-user',root,provider)
        assert not access.granted('local',bot['id'],provider)
        assert not access.granted('local',target['id'],provider)
        assert [args['prompt'] for args,_ in calls]==['child work','root follow-up']
    finally:
        await r.stop_background_tasks()


@pytest.mark.asyncio
async def test_recipient_can_inherit_unconfigured_access_but_explicit_off_blocks_it(runtime):
    r=runtime
    try:
        bot,target,_,_,provider,card,_=await start(r,target_access=None)
        access=r.messager_bot_app_access
        row=r.messager_bot_delegation.row(card['id'])
        allowed=json.loads(row['value_json'])['allowed']
        assert allowed[provider.id]==provider.version
        assert not access.granted('local',target['id'],provider)
        save(r,target,enabled=False)
        assert access.blocked('local',target['id'],provider)
        assert provider.id not in access.tree.path('local',target['id'],allowed,{})
    finally:
        await r.stop_background_tasks()


@pytest.mark.asyncio
@pytest.mark.parametrize(('root_mode','child_mode','risk','special','expected'), [
    ('manual','always',None,False,'automatic'),
    ('ai','manual','low',False,'automatic'),
    ('ai','always',None,False,'automatic'),
    ('manual','ai','high',False,'manual'),
    ('always','always',None,True,'manual'),
])
async def test_task_approval_uses_current_path_and_stays_in_tree(runtime,root_mode,child_mode,risk,special,expected):
    r=runtime
    reviews=[]
    try:
        bot,target,_,calls,provider,card,parent=await start(
            r,source_access=None,target_access=None,special=special,reuse_approval=True,
            approval_risk=risk,reviews=reviews)
        access=r.messager_bot_app_access
        delegation=r.messager_bot_delegation
        for current,mode in ((bot,root_mode),(target,child_mode)):
            access.set_approval_rule('local',current['id'],mode,0)
        frozen=r.app_chat.execution_authorization(parent['worker_run'])
        root_scope=r.app_chat.binding(parent['worker_session'])['scope']
        root=access.tree.context('local',root_scope,frozen)
        assert access.tree.approval_chain('local',root_scope,frozen,root)['mode']==root_mode
        delegation.decide('local',bot['id'],card['id'],card['review_hash'],'approve')
        if expected=='automatic':
            ref=await until(lambda:delegation.row(card['id'])['resume_job'])
            job=await until(lambda: j if (j:=r.messager_dialogue.row(ref))['worker_run'] else None)
            await wait(r,job['worker_run'],'completed')
            assert [args['prompt'] for args,_ in calls]==['child work','root follow-up']
            assert not r.agents.list_interactions(job['worker_run'])
            assert access.tree.granted('local',root[0],provider)
        else:
            active=await until(lambda:next((x['runs'][0] for x in delegation.work('local',bot['id']) if x['runs']),None))
            assert active['interactions'][0]['kind']=='approval' and not calls
            assert not access.tree.granted('local',root[0],provider)
        assert len(reviews)==int(risk is not None)
        if reviews:
            assert reviews[0]['owner_rule']['root_goal']=='Delegate and summarize'
            assert reviews[0]['goal']=='Produce the requested fixture output'
        assert not access.granted('local',bot['id'],provider)
        assert not access.granted('local',target['id'],provider)
    finally:
        await r.stop_background_tasks()
