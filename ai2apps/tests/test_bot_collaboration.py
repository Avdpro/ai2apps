"""C3 real Run/Todo/Hook/policy; deterministic model and effect fixtures."""
import asyncio,json
from dataclasses import replace
import pytest
from test_app_interactions import runtime,wait
from test_app_chat_durable import bind_identity,response
from test_bot_capability_discovery import setup,P
from test_bot_app_access import save
from test_bot_delegation import until
from ai2apps.messager.collaboration import PROPOSE
from ai2apps.events.business import EventType
from agent_context_fixtures import owner_context

async def plan(r,*,count=2,trigger='immediate',aggregation='all_success',special=False):
    bot,sid,calls,provider=setup(r);save(r,bot)
    targets=[r.messager_bots.create('local','Reviewer '+str(i),'Deliver independent work') for i in range(count)]
    for target in targets:save(r,target)
    if special:r.app_capability_router.providers[provider.id]=replace(provider,access_policy='confirm')
    value={'title':'Independent reviews','participants':[{'bot_id':b['id'],'instructions':'Deliver independent review '+str(i)} for i,b in enumerate(targets)],'trigger':trigger,'aggregation':aggregation}
    publisher=None
    if trigger=='event':
        cap='fixture.event.details';pid='fixture.owner.details'
        async def read(args,ctx):return {'event_id':args['event_id'],'report':'approved detail'}
        from ai2apps.services.capability_routing import CapabilityProvider
        r.app_capability_router.register(CapabilityProvider(pid,cap,'ai2apps.gallery',read,version='1'))
        t=r.services.get_tool('voice.event_details');r.services.ensure_tool(service_id=t.service_id,qualified_name=cap,display_name='Fixture event detail',description='Fixture',input_schema={'type':'object','properties':{'event_id':{'type':'string'}}},output_schema={'type':'object'})
        async def route(a,c):return await r.app_capability_router.invoke(cap,a,c)
        r.service_registry.bind_tool(cap,provider_key=r.service_registry.bound_tool('voice.event_details').provider_key,handler=route)
        publisher=r.business_events.register(EventType('fixture.record.finished','fixture.owner','Fixture finished','record',{'type':'object','properties':{'n':{'type':'integer'}},'required':['n']},('n',),'fixture',lambda actor,subject:actor=='local' and subject=='record',details=(cap,pid,'1')))
        value['event']={'event_type':'fixture.record.finished','subjects':['record'],'filters':[]}
    if trigger=='schedule':value['schedule']={'frequency':'daily','hour':6}
    async def model(request):
        text='\n'.join(str(m.get('content','')) for m in request['messages'])
        if not owner_context(request).get('delegated_task'):
            results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
            if any(x.get('plan_id') for x in results):return response(text='Plan awaits your review')
            if not any(x.get('providers') for x in results):return response('app.describe',{'capability':PROPOSE})
            return response(PROPOSE,value)
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        if any(x.get('created') for x in results):return response(text='Independent canonical result')
        if not any(x.get('providers') for x in results):return response('app.describe',{'capability':provider.capability})
        return response(provider.capability,{'prompt':'independent output'})
    r.agent_runtime.bind_model_provider(model);await r.start_background_tasks(retention_interval_seconds=60)
    rid=r.app_chat.submit(P(),sid,'review-collaboration','Prepare the requested collaboration','fixture')
    await wait(r,rid,'completed')
    cards=r.messager_bot_collaboration.work('local',bot['id'])
    assert len(cards)==1,json.dumps([(step.kind,step.output,step.error) for step in r.agents.list_steps(rid) if step.kind!='model'])
    return bot,sid,calls,targets,cards[0],publisher

@pytest.mark.asyncio
async def test_multibot_review_background_intersection_and_durable_aggregate(runtime):
    r=runtime
    try:
        bot,sid,calls,targets,card,_=await plan(r);s=r.messager_bot_collaboration
        assert not calls
        with pytest.raises(PermissionError):s.decide('other',bot['id'],card['id'],card['review_hash'],'approve')
        with pytest.raises(ValueError):s.decide('local',bot['id'],card['id'],'stale','approve')
        s.decide('local',bot['id'],card['id'],card['review_hash'],'approve')
        key='immediate:'+card['id'];batch=s.activate(s.row(card['id']),key)
        await until(lambda:s.batch(batch['id'])['status']!='running')
        assert s.batch(batch['id'])['status']=='completed',s.batch(batch['id'])
        assert len(calls)==2 and s.activate(s.row(card['id']),key)['id']==batch['id']
        matches=[m for m in r.app_chat.message_page(P(),sid)['items'] if 'Independent canonical result' in str(m)]
        assert len(matches)==1 and all(t['name'] in str(matches[0]) for t in targets)
        with r.database.transaction() as db:
            children=db.execute('SELECT value_json FROM messager_bot_delegations WHERE parent_job=?',(batch['id'],)).fetchall()
            assert len(children)==2 and all(json.loads(c[0])['target_authorization']['mode']=='background' for c in children)
            assert 0<db.execute('SELECT count(*) FROM messager_collaboration_calls').fetchone()[0]<=36
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_special_confirmation_returns_to_origin_and_pause_stops_all(runtime):
    r=runtime
    try:
        bot,sid,calls,targets,card,_=await plan(r,count=1,special=True);s=r.messager_bot_collaboration
        s.decide('local',bot['id'],card['id'],card['review_hash'],'approve')
        pending=await until(lambda:next((x for x in r.messager_bot_delegation.work('local',bot['id']) if x['runs']),None))
        run=pending['runs'][0];assert run['interactions'][0]['schema']['properties']['scope']['enum']==['once']
        assert not calls and any(x['id']==run['id'] for x in r.messager_dialogue.snapshot(P(),bot['id'],sid)['runs'])
        with r.database.transaction(write=True) as db:
            batch=dict(db.execute('SELECT * FROM messager_collaboration_batches').fetchone())
            db.execute('UPDATE messager_collaboration_batches SET coordinator=NULL WHERE id=?',(batch['id'],))
        restored=s.activate(s.row(card['id']),batch['trigger_key'])
        assert restored['coordinator']==batch['coordinator']
        s.pause('local',bot['id'],card['id']);await asyncio.sleep(.5)
        assert not calls
        await until(lambda:r.agents.get_run(batch['coordinator']).status.value=='cancelled')
        with pytest.raises(PermissionError):s.activate(s.row(card['id']),'cannot-restart')
        with r.database.transaction() as db:assert db.execute('SELECT status FROM messager_collaboration_batches').fetchone()[0]=='cancelled'
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_event_hook_details_dedup_and_causal_reentry(runtime):
    r=runtime
    try:
        bot,sid,calls,targets,card,publisher=await plan(r,count=1,trigger='event');s=r.messager_bot_collaboration
        s.decide('local',bot['id'],card['id'],card['review_hash'],'approve');assert s.row(card['id'])['hook_id']
        with r.database.transaction(write=True) as db:publisher.publish(db,owner='local',subject_id='record',occurrence_key='first',data={'n':1})
        def latest():
            with r.database.transaction() as db:row=db.execute('SELECT * FROM messager_collaboration_batches ORDER BY rowid DESC LIMIT 1').fetchone()
            return dict(row) if row else None
        batch=await until(latest);await until(lambda:s.batch(batch['id'])['status']!='running')
        assert s.batch(batch['id'])['status']=='completed',s.batch(batch['id'])
        assert len(calls)==1 and 'approved detail' in batch['context_json']
        from ai2apps.events.causality import cause_scope
        with cause_scope(json.loads(batch['cause_json'])),r.database.transaction(write=True) as db:publisher.publish(db,owner='local',subject_id='record',occurrence_key='echo',data={'n':2})
        r.event_hooks.scan();r.hook_execution.admit();await asyncio.sleep(.2)
        assert len(calls)==1
        def suppressed():
            with r.database.transaction() as db:return db.execute("SELECT count(*) FROM hook_executions WHERE state='suppressed'").fetchone()[0]==1
        await until(suppressed)
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_schedule_uses_todo_and_refuses_changed_execution(runtime):
    r=runtime
    try:
        bot,sid,calls,targets,card,_=await plan(r,count=1,trigger='schedule');s=r.messager_bot_collaboration
        s.decide('local',bot['id'],card['id'],card['review_hash'],'approve');row=s.row(card['id'])
        assert row['task_id'] and not calls
        launched=r.todo.launch('local',row['task_id'],principal=P(),request_key='schedule-fixture-slot')
        await until(lambda:len(calls)==1)
        with r.database.transaction() as db:batch=dict(db.execute('SELECT * FROM messager_collaboration_batches').fetchone())
        await until(lambda:s.batch(batch['id'])['status']!='running');assert batch['trigger_key']=='todo:'+launched['id']
        s.pause('local',bot['id'],card['id'])
        with pytest.raises(PermissionError):r.todo.launch('local',row['task_id'],principal=P(),request_key='new-slot-after-pause')
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
@pytest.mark.parametrize('aggregation,expected',[('allow_partial','partial'),('all_success','failed')])
async def test_independent_failure_has_explicit_partial_policy_and_no_effectful_retry(runtime,aggregation,expected):
    r=runtime
    try:
        bot,sid,calls,targets,card,_=await plan(r,special=True,aggregation=aggregation);s=r.messager_bot_collaboration
        s.decide('local',bot['id'],card['id'],card['review_hash'],'approve')
        pending=await until(lambda:(x if len(x:=r.messager_bot_delegation.work('local',bot['id']))==2 and all(c['runs'] for c in x) else None))
        first=pending[0]['runs'][0];interaction=first['interactions'][0]
        r.agents.respond_interaction(first['id'],interaction['id'],response_id='one-reviewed-operation',response={'decision':'approve','scope':'once'});r.agent_runtime.wake()
        r.messager_bot_delegation.stop(r.messager_bot_delegation.row(pending[1]['id']),'failed')
        with r.database.transaction() as db:batch=dict(db.execute('SELECT * FROM messager_collaboration_batches').fetchone())
        await until(lambda:s.batch(batch['id'])['status']!='running')
        assert s.batch(batch['id'])['status']==expected and len(calls)==1
        s.recover();assert len(calls)==1
        with pytest.raises(PermissionError,match='already admitted'):s.activate(s.row(card['id']),'new-key-same-root',cause=json.loads(batch['cause_json']))
        with r.database.transaction() as db:
            events=[dict(x) for x in db.execute("SELECT * FROM business_event_facts WHERE type='messager.collaboration.completed'")]
            assert len(events)==1 and json.loads(events[0]['data_json'])['status']==expected
            assert events[0]['cause_root_id']==json.loads(batch['cause_json'])['root_id']
        from ai2apps.system_tasks.sessions import execution_session
        from ai2apps.messager.collaboration import DETAILS
        context=r.tools.context_for_session(caller_id='fixture',session_id=execution_session(r,'local','ai2apps.messager'))
        detail=await r.tools.execute(DETAILS,{'event_id':events[0]['event_id']},context=context)
        assert detail.output['status']==expected and detail.output['execution_authority'] is False
        assert '未完成' in str(r.app_chat.message_page(P(),sid)['items'])
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_original_conversation_is_not_occupied_and_access_revocation_blocks_batch(runtime):
    r=runtime
    try:
        bot,sid,calls,targets,card,_=await plan(r,count=1,special=True);s=r.messager_bot_collaboration
        s.decide('local',bot['id'],card['id'],card['review_hash'],'approve')
        pending=await until(lambda:next((x for x in r.messager_bot_delegation.work('local',bot['id']) if x['runs']),None))
        with r.database.transaction() as db:batch=dict(db.execute('SELECT * FROM messager_collaboration_batches').fetchone())
        assert r.agents.get_run(batch['coordinator']).session_id!=sid
        save(r,targets[0],enabled=False)
        await until(lambda:s.batch(batch['id'])['status']!='running')
        assert not calls and s.batch(batch['id'])['status']=='failed'
        with pytest.raises(PermissionError):s.activate(s.row(card['id']),'after-revocation')
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_reviewed_replacement_keeps_admitted_batch_and_closes_future_old_slots(runtime):
    r=runtime
    try:
        bot,sid,calls,targets,card,_=await plan(r,count=1,special=True,trigger='schedule');s=r.messager_bot_collaboration
        s.decide('local',bot['id'],card['id'],card['review_hash'],'approve');old=s.row(card['id'])
        r.todo.launch('local',old['task_id'],principal=P(),request_key='old-scheduled-slot')
        await until(lambda:next((x for x in r.messager_bot_delegation.work('local',bot['id']) if x['runs']),None))
        with r.database.transaction() as db:batch=dict(db.execute('SELECT * FROM messager_collaboration_batches').fetchone())
        rid=r.app_chat.submit(P(),sid,'replace-plan-turn','Update this collaboration','fixture')
        ctx=replace(r.tools.context_for_session(caller_id='fixture',session_id=sid,trace_id=rid),invocation_id='reviewed-replacement')
        value={**card['value']['request'],'title':'Revised independent review','replaces_plan_id':card['id']}
        proposal=s.propose(value,ctx);r.agents.request_cancel(rid)
        new=s.row(proposal['plan_id']);s.decide('local',bot['id'],new['id'],new['review_hash'],'approve')
        assert s.row(old['id'])['status']=='retiring'
        s.check_batch(s.batch(batch['id']))
        with pytest.raises(PermissionError):s.activate(s.row(old['id']),'new-old-slot')
        with r.todo.store.connect() as db:assert db.execute('SELECT next_due FROM tasks WHERE id=?',(old['task_id'],)).fetchone()[0] is None
        assert json.loads(s.row(new['id'])['value_json'])['replaces_hash']==old['review_hash']
        s.pause('local',bot['id'],old['id']);assert not calls
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_daily_admission_budget_survives_new_roots_and_cancellation(runtime):
    r=runtime
    try:
        bot,sid,calls,targets,card,_=await plan(r,count=1,trigger='schedule');s=r.messager_bot_collaboration
        s.decide('local',bot['id'],card['id'],card['review_hash'],'approve');row=s.row(card['id'])
        # Real host admissions and cancellation receipts, with no event-loop
        # yield that could begin model/effect work in these queued coordinators.
        for number in range(24):
            batch=s.activate(row,'independent-reviewed-slot:'+str(number))
            s.stop_batch(batch['id'],'cancelled')
        with pytest.raises(PermissionError,match='daily admission'):s.activate(row,'new-key-new-root-still-bounded')
        assert not calls
        with r.database.transaction() as db:
            assert db.execute('SELECT count(*) FROM messager_collaboration_batches').fetchone()[0]==24
            assert db.execute('SELECT count(*) FROM messager_collaboration_reservations').fetchone()[0]==24
    finally:await r.stop_background_tasks()
