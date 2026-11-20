"""Durable observe-only rules, with arbitrary independent provider/consumer identities."""
from dataclasses import replace
import json

import pytest

from ai2apps.events.business import EventType
from ai2apps.events.hooks import HookSubscriptions, HookError, ConsumerType
from test_app_interactions import runtime


@pytest.fixture
def env(runtime):
    allowed={'local':{'resource-a','resource-b'},'other':{'resource-c'}}
    consumer_allowed={'local':{'bot-a','mini-b'},'other':{'foreign'}}
    hooks=runtime.event_hooks
    now=[100.0]
    hooks.clock=lambda:now[0]
    def validate(actor,binding):
        if set(binding)!={'id'} or binding['id'] not in consumer_allowed.get(actor,set()):
            raise PermissionError('Consumer unavailable')
        return dict(binding)
    for id,kind,app in [('owner.alpha.observe','app','example.alpha'),('owner.beta.observe','mini-app','different.beta')]:
        hooks.register_consumer(ConsumerType(id,kind,app,'1',validate))
    definition=EventType('arbitrary.changed','example.publisher','Change','item',
        {'type':'object','properties':{'score':{'type':'integer'},'status':{'enum':['ready','failed']}},
         'required':['score','status'],'additionalProperties':False},('score','status'),'fixture',
        lambda actor,subject:subject in allowed.get(actor,set()))
    publisher=runtime.business_events.register(definition)
    sequence=[0]
    def emit(score=1,subject='resource-a',owner='local',status='ready'):
        sequence[0]+=1
        with runtime.database.transaction(write=True) as db:
            return publisher.publish(db,owner=owner,subject_id=subject,occurrence_key=str(sequence[0]),data={'score':score,'status':status})
    def proposal(consumer='owner.alpha.observe',target='bot-a',subjects=None,filters=None):
        return dict(consumer={'registration':consumer,'binding':{'id':target}},event_type=definition.name,
            subjects=subjects or ['resource-a'],filters=filters or [])
    return runtime,hooks,emit,proposal,allowed,consumer_allowed,now


def enable(hooks,value,key='create-rule-1'):
    preview=hooks.preview('local',value)
    return hooks.save('local',preview['preview_ref'],key)


def test_from_now_filter_fanout_duplicate_scan_and_owner_isolation(env):
    runtime,hooks,emit,proposal,*_=env
    emit(10)  # Never backfilled into a newly enabled rule.
    a=enable(hooks,proposal(filters=[{'field':'score','op':'gte','value':5}]))
    b=enable(hooks,proposal('owner.beta.observe','mini-b'),'create-rule-2')
    emit(3);wanted=emit(7);emit(99,'resource-c','other')
    hooks.scan();hooks.scan()
    da=hooks.deliveries('local',a['id'])['items']
    assert len(da)==1 and da[0]['event_id']==wanted and da[0]['state']=='matched' and not da[0]['executed']
    assert len(hooks.deliveries('local',b['id'])['items'])==2
    assert hooks.rules('other')==[]
    with pytest.raises(HookError,match='unavailable'):hooks.get('other',a['id'])
    with pytest.raises(HookError):hooks.deliveries('other',a['id'])


def test_preview_has_no_rule_and_enable_request_is_idempotent(env):
    runtime,hooks,emit,proposal,*_=env
    p=hooks.preview('local',proposal());assert not hooks.rules('local')
    rule=hooks.save('local',p['preview_ref'],'enable-request-1')
    assert hooks.save('local',p['preview_ref'],'enable-request-1')==rule
    with pytest.raises(HookError) as err:hooks.save('local',p['preview_ref'],'enable-request-2')
    assert err.value.code=='preview_consumed'
    p2=hooks.preview('local',proposal())
    with pytest.raises(HookError) as err:hooks.save('local',p2['preview_ref'],'enable-request-1')
    assert err.value.code=='request_conflict'


def test_restart_resumes_cursor_without_duplicate(env):
    runtime,hooks,emit,proposal,*_=env
    rule=enable(hooks,proposal());emit()
    replacement=HookSubscriptions(runtime.business_events)
    for c in hooks.consumers.values():replacement.register_consumer(c)
    replacement.scan();emit();replacement.scan()
    assert len(replacement.deliveries('local',rule['id'])['items'])==2
    hooks.scan()
    assert len(hooks.deliveries('local',rule['id'])['items'])==2


def test_revision_boundary_handles_backlog_with_original_filters(env):
    runtime,hooks,emit,proposal,*_=env
    rule=enable(hooks,proposal(filters=[{'field':'score','op':'eq','value':1}]))
    old=emit(1)
    p=hooks.preview('local',proposal(filters=[{'field':'score','op':'eq','value':2}]))
    updated=hooks.save('local',p['preview_ref'],'update-request-1',rule_id=rule['id'],expected_revision=1)
    emit(1);new=emit(2)
    hooks.scan()
    rows=hooks.deliveries('local',rule['id'])['items']
    assert [(r['event_id'],r['rule_revision']) for r in rows]==[(old,1),(new,2)]
    assert updated['revision']==2


def test_pause_resume_skips_unscanned_and_paused_ranges(env):
    runtime,hooks,emit,proposal,*_=env
    rule=enable(hooks,proposal());emit()
    pause=hooks.change('local',rule['id'],'pause',1,'pause-request-1')
    emit();hooks.scan();assert not hooks.deliveries('local',rule['id'])['items']
    resumed=hooks.change('local',rule['id'],'resume',pause['revision'],'resume-request-1')
    expected=emit();hooks.scan()
    assert [r['event_id'] for r in hooks.deliveries('local',rule['id'])['items']]==[expected]
    revisions=hooks.get('local',rule['id'])['revisions']
    assert [r['scan_state'] for r in revisions]==['skipped','skipped','active']
    result=hooks.change('local',rule['id'],'delete',resumed['revision'],'delete-request-1')
    assert result['status']=='deleted' and hooks.rules('local')==[]
    assert hooks.get('local',rule['id'])['status']=='deleted'
    assert len(hooks.deliveries('local',rule['id'])['items'])==1
    assert hooks.change('local',rule['id'],'delete',resumed['revision'],'delete-request-1')==result


@pytest.mark.parametrize('condition',[
    {'field':'secret','op':'eq','value':1}, {'field':'score','op':'eq','value':True},
    {'field':'score','op':'eq','value':'5'}, {'field':'status','op':'gt','value':'ready'},
    {'field':'score','op':'in','value':[]}, {'field':'score','op':'gt','value':float('inf')},
    {'field':'score','op':'exec','value':'print(1)'},
])
def test_filters_are_declared_typed_and_bounded(env,condition):
    _,hooks,_,proposal,*_=env
    with pytest.raises(HookError):hooks.preview('local',proposal(filters=[condition]))


def test_expiry_revocation_stale_revision_and_consumer_change(env):
    runtime,hooks,emit,proposal,allowed,consumers,now=env
    p=hooks.preview('local',proposal());now[0]+=601
    with pytest.raises(HookError) as err:hooks.save('local',p['preview_ref'],'expired-request')
    assert err.value.code=='preview_expired'
    rule=enable(hooks,proposal());emit();hooks.scan()
    consumers['local'].clear()
    assert hooks.deliveries('local',rule['id'])['items'][0]['state']=='unavailable'
    hooks.scan();assert hooks.get('local',rule['id'])['status']=='paused'
    with pytest.raises(HookError):hooks.change('local',rule['id'],'delete',7,'stale-revision')
    consumers['local'].add('bot-a');allowed['local'].clear()
    with pytest.raises(HookError):hooks.preview('local',proposal())


def test_declaration_change_pauses_without_using_new_schema(env):
    runtime,hooks,emit,proposal,*_=env
    rule=enable(hooks,proposal());emit()
    original=runtime.business_events.types['arbitrary.changed']
    runtime.business_events.types[original.name]=replace(original,coverage='changed')
    hooks.scan()
    assert hooks.get('local',rule['id'])['error']=='declaration_changed'
    assert not hooks.deliveries('local',rule['id'])['items']


def test_gap_and_capacity_do_not_silently_drop_pending_events(env):
    runtime,hooks,emit,proposal,*_=env
    rule=enable(hooks,proposal());emit()
    with runtime.database.transaction(write=True) as db:
        high=hooks._high(db)
        db.execute('UPDATE business_event_retention SET floor_sequence=?',(high,))
    hooks.scan();assert hooks.get('local',rule['id'])['error']=='cursor_gap'
    # A different rule starts after the floor, then retains cursor at overflow.
    hooks.MAX_MATCHES=1
    second=enable(hooks,proposal(),'second-rule-create');one=emit();two=emit()
    hooks.scan();state=hooks.get('local',second['id'])
    assert state['error']=='quota_exceeded'
    assert state['revisions'][0]['cursor']==runtime.events.get(one).sequence
    assert len(hooks.deliveries('local',second['id'])['items'])==1

@pytest.mark.asyncio
async def test_http_management_rejects_forgery_conflicts_and_cross_actor(env):
    from fastapi import FastAPI
    from httpx import AsyncClient, ASGITransport
    from ai2apps.api.hooks import create_hook_router
    from ai2apps.identity import RequestPrincipal
    runtime,hooks,emit,proposal,*_=env
    current=[RequestPrincipal.legacy_local()]
    app=FastAPI();app.include_router(create_hook_router(lambda:runtime,lambda:current[0]))
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://fixture') as client:
        forged=proposal();forged['consumer']['binding']={'id':'foreign'}
        assert (await client.post('/hooks/preview',json=forged)).status_code==403
        wildcard=proposal(subjects=['*'])
        assert (await client.post('/hooks/preview',json=wildcard)).status_code==403
        preview=(await client.post('/hooks/preview',json=proposal())).json()
        body={'preview_ref':preview['preview_ref'],'request_id':'http-enable-request'}
        result=await client.post('/hooks',json=body);assert result.status_code==201,result.text
        rule=result.json()
        assert (await client.post('/hooks',json=body)).json()==rule
        emit();hooks.scan()
        matches=(await client.get('/hooks/'+rule['id']+'/deliveries')).json()['items']
        assert len(matches)==1 and matches[0]['executed'] is False
        current[0]=replace(current[0],actor_user_id='other')
        assert (await client.get('/hooks')).json()['items']==[]
        assert (await client.get('/hooks/'+rule['id'])).status_code==404
        assert (await client.get('/hooks/'+rule['id']+'/deliveries')).status_code==404
        assert (await client.post('/hooks',json={**body,'request_id':'foreign-enable-1'})).status_code==409


@pytest.mark.asyncio
async def test_background_scanner_recovers_without_ui_or_model(env):
    import asyncio
    runtime,hooks,emit,proposal,*_=env
    rule=enable(hooks,proposal())
    emit()  # Written while no worker/UI is running.
    await runtime.business_event_relay.startup()
    try:
        for _ in range(60):
            if hooks.deliveries('local',rule['id'])['items']:break
            await asyncio.sleep(.05)
        else:pytest.fail('Background Hook scanner did not resume')
        assert not runtime.agents.list_runs()  # No model execution was created.
    finally:
        await runtime.business_event_relay.shutdown()


def test_real_bot_binding_does_not_grant_foreign_bot_or_execution(runtime):
    from ai2apps.messager.bots import install
    from ai2apps.events.builtin import VOICE
    from ai2apps.readaloud.repository import ReadAloudRepository
    install(runtime)
    bot=runtime.messager_bots.create('local','Observer','Observe only')
    profile=ReadAloudRepository(runtime.database,runtime.events).create_voice_profile('local',name='Voice',source_type='synthetic_designed',
        model_id=None,provider_voice_id=None,reference_transcript='',rights_scope={})
    value={'consumer':{'registration':'messager.bot.observe','binding':{'bot_id':bot['id']}},
           'event_type':VOICE,'subjects':[profile['id']],'filters':[]}
    preview=runtime.event_hooks.preview('local',value)
    assert preview['rule']['consumer']['binding']=={'bot_id':bot['id']}
    with pytest.raises(PermissionError):runtime.event_hooks.preview('other',value)
    assert runtime.event_hooks.save('local',preview['preview_ref'],'bot-observer-request')['mode']=='observe_only'


def test_concurrent_scanners_record_once_and_cursor_update_rolls_back(env):
    from concurrent.futures import ThreadPoolExecutor
    runtime,hooks,emit,proposal,*_=env
    rule=enable(hooks,proposal())
    for _ in range(8):emit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _:hooks.scan(),range(2)))
    assert len(hooks.deliveries('local',rule['id'])['items'])==8
    # SQLite failure after match insert must roll back insert and cursor together.
    emit()
    before=hooks.get('local',rule['id'])['revisions'][0]['cursor']
    with runtime.database.transaction(write=True) as db:
        db.execute("CREATE TRIGGER fail_hook_cursor BEFORE UPDATE OF cursor ON hook_rule_revisions BEGIN SELECT RAISE(ABORT,'fixture crash'); END")
    with pytest.raises(Exception):hooks.scan()
    assert hooks.get('local',rule['id'])['revisions'][0]['cursor']==before
    assert len(hooks.deliveries('local',rule['id'])['items'])==8
    with runtime.database.transaction(write=True) as db:db.execute('DROP TRIGGER fail_hook_cursor')
    hooks.scan();assert len(hooks.deliveries('local',rule['id'])['items'])==9


def test_real_app_binding_requires_owned_active_instance(runtime):
    from ai2apps.messager.bots import install
    from ai2apps.storage.repositories.apps import AppRepository
    from ai2apps.events.builtin import VOICE
    from ai2apps.readaloud.repository import ReadAloudRepository
    install(runtime)
    with runtime.database.transaction() as db:
        definition=db.execute("SELECT id FROM app_definitions WHERE package_id='ai2apps.messager'").fetchone()[0]
    instance=AppRepository(runtime.database,runtime.events).create_instance(app_definition_id=definition,owner_user_id='local',singleton_key='ai2apps.messager:user:local')
    profile=ReadAloudRepository(runtime.database,runtime.events).create_voice_profile('local',name='Voice',source_type='synthetic_designed',
        model_id=None,provider_voice_id=None,reference_transcript='',rights_scope={})
    proposal={'consumer':{'registration':'messager.app.observe','binding':{'app_instance_id':instance.id}},
        'event_type':VOICE,'subjects':[profile['id']],'filters':[]}
    assert runtime.event_hooks.preview('local',proposal)['mode']=='observe_only'
    with pytest.raises(PermissionError):runtime.event_hooks.preview('other',proposal)
    with runtime.database.transaction(write=True) as db:db.execute("UPDATE app_instances SET status='closed' WHERE id=?",(instance.id,))
    with pytest.raises(PermissionError):runtime.event_hooks.preview('local',proposal)


def test_owned_collection_can_subscribe_before_voice_exists_but_never_other_actor(runtime):
    from ai2apps.messager.bots import install
    from ai2apps.events.builtin import VOICE, CHANNEL
    from ai2apps.readaloud.repository import ReadAloudRepository
    install(runtime)
    bot=runtime.messager_bots.create('local','Observer','Observe only')
    proposal={'consumer':{'registration':'messager.bot.observe','binding':{'bot_id':bot['id']}},
        'event_type':VOICE,'scope':'owned_collection','subjects':[],'filters':[]}
    rule=enable(runtime.event_hooks,proposal)
    repo=ReadAloudRepository(runtime.database,runtime.events)
    for actor in ('local','other'):
        repo.create_voice_profile(actor,name='New',source_type='synthetic_designed',model_id=None,
            provider_voice_id=None,reference_transcript='',rights_scope={})
    runtime.event_hooks.scan()
    rows=runtime.event_hooks.deliveries('local',rule['id'])['items']
    assert len(rows)==1 and rows[0]['event']['type']==VOICE
    with pytest.raises(HookError):runtime.event_hooks.preview('local',{**proposal,'event_type':CHANNEL})


def test_bulk_matching_spans_batches_without_silent_skips(env):
    runtime,hooks,emit,proposal,*_=env
    rule=enable(hooks,proposal())
    for i in range(7):emit(i)
    for _ in range(4):hooks.scan(limit=2)
    assert len(hooks.deliveries('local',rule['id'])['items'])==7


def test_consumer_version_change_requires_new_preview(env):
    _,hooks,emit,proposal,*_=env
    rule=enable(hooks,proposal());emit()
    old=hooks.consumers['owner.alpha.observe']
    hooks.consumers[old.id]=replace(old,version='2')
    hooks.scan()
    assert hooks.get('local',rule['id'])['error']=='declaration_changed'
    with pytest.raises(HookError):hooks.change('local',rule['id'],'resume',1,'consumer-resume-1')


def test_reapproval_replaces_paused_consumer_version_without_replaying_backlog(env):
    runtime,hooks,emit,proposal,*_=env
    rule=enable(hooks,proposal());emit()
    old=hooks.consumers['owner.alpha.observe']
    hooks.consumers[old.id]=replace(old,version='2')
    hooks.scan();assert hooks.get('local',rule['id'])['status']=='paused'
    preview=hooks.preview('local',proposal())
    replacement=hooks.save('local',preview['preview_ref'],'replace-paused-rule',rule_id=rule['id'],expected_revision=1)
    assert replacement['revision']==2
    expected=emit();hooks.scan()
    assert [r['event_id'] for r in hooks.deliveries('local',rule['id'])['items']]==[expected]


@pytest.mark.asyncio
async def test_shutdown_waits_for_inflight_scanner_even_if_it_fails(env):
    import asyncio
    from threading import Event
    from ai2apps.events.relay import EventRelay
    runtime,*_=env
    entered,release=Event(),Event()
    relay=EventRelay(runtime)
    def flush():
        entered.set();release.wait(3);raise ValueError('fixture worker failure')
    relay.register(flush)
    await relay.startup()
    for _ in range(100):
        if entered.is_set():break
        await asyncio.sleep(.01)
    assert entered.is_set()
    stopping=asyncio.create_task(relay.shutdown())
    await asyncio.sleep(.02);assert not stopping.done()
    release.set()
    await asyncio.wait_for(stopping,timeout=3)
    assert relay.task is None
