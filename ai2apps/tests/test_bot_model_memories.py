"""Structured preferences: current catalogs, frozen chains, no authority grants."""
import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from ai2apps.api.messager import create_messager_router
from ai2apps.model_manager import DEFAULT_MODEL_PURPOSES, ModelManagerStore
from ai2apps.model_preferences import choose, scope, validate
from ai2apps.messager.model_memories import model_value, catalog
from test_app_chat_durable import bind_identity
from test_app_interactions import runtime
from test_bot_capability_discovery import setup, P


def snapshot(model='preferred', purpose='image_generation', profile='normal'):
    return {'schema':'ai2apps.model-preferences/v1','routes':[
        {'purpose':purpose,'profile':profile,'model':model,'memory_id':'memory-1','revision':1,'bot_id':'root'}]}


def remember(r, bot, model='preferred', purpose='image_generation', profile='normal', **kw):
    return r.messager_bots.memory.records.apply('local',bot['id'],
        request_id=kw.pop('request_id','remember-'+model),subject='ignored',predicate='ignored',
        kind='model',value={'purpose':purpose,'profile':profile,'model':model},text='Model preference',**kw)


@pytest.mark.asyncio
async def test_context_isolation_explicit_priority_fallback_and_privacy():
    r=SimpleNamespace(privacy_mode=False)
    async def task(model):
        with scope(snapshot(model)):
            await asyncio.sleep(0)
            return choose(r,'image_generation','system')[0]
    assert await asyncio.gather(task('one'),task('two')) == ['one','two']
    assert choose(r,'image_generation','system')[0]=='system'
    with scope(snapshot()):
        assert choose(r,'image_generation','system',explicit='explicit')[0]=='explicit'
        model, provenance=choose(r,'image_generation','system',choices=[{'id':'other'}])
        assert model=='system' and provenance['fallback_reason']
        r.privacy_mode=True
        assert choose(r,'image_generation',None)[0] is None
    with scope(snapshot('private',profile='privacy'),profile='privacy'):
        assert choose(SimpleNamespace(),'image_generation',None)[0]=='private'


@pytest.mark.parametrize('bad',[
    {'purpose':'unknown','profile':'normal','model':'x'},
    {'purpose':'work_chat','profile':'public','model':'x'},
    {'purpose':'work_chat','profile':'normal','model':'x','access':True}])
def test_model_values_do_not_accept_new_categories_or_authority(bad):
    with pytest.raises(ValueError): model_value(bad)


def test_snapshot_rejects_duplicate_or_unbounded_routes():
    v=snapshot();v['routes']*=2
    with pytest.raises(ValueError):validate(v)
    v=snapshot();v['routes'][0]['revision']=True
    with pytest.raises(ValueError):validate(v)


def test_model_manager_reuses_all_purposes_without_cross_profile_fallback(tmp_path):
    manager=ModelManagerStore(tmp_path)
    for purpose in DEFAULT_MODEL_PURPOSES:
        with scope(snapshot(purpose=purpose)):
            assert manager.resolve_default_model(purpose)=='preferred'
    with scope(snapshot() ,profile='privacy'):
        assert manager.resolve_default_model('image_generation','normal-only') is None


def test_memory_slots_versions_chain_union_and_no_private_text_leak(runtime):
    bot,_,_,_=setup(runtime)
    child=runtime.messager_bots.create('local','Child','Help')
    grandchild=runtime.messager_bots.create('local','Grandchild','Help')
    directory=runtime.messager_bots;owner=directory.model_memories
    directory.memory.save('local',bot['id'],'A private unrelated fact')
    first=remember(runtime,bot)
    parent=owner.snapshot('local',bot['id'])
    assert owner.snapshot('local',child['id'],parent)['routes']==parent['routes']
    remember(runtime,child,'child-image')
    remember(runtime,child,'private-image',profile='privacy')
    combined=owner.snapshot('local',child['id'],parent)
    assert {r['model'] for r in combined['routes']}=={'child-image','private-image'}
    assert owner.snapshot('local',grandchild['id'],combined)['routes']==combined['routes']
    assert parent['routes'][0]['model']=='preferred'
    assert len(directory.memory.list('local',grandchild['id'])['items'])==0
    assert directory.memory.context('local',bot['id'])[0]['text']=='A private unrelated fact'
    assert 'private unrelated' not in str(combined)
    with pytest.raises(ValueError):remember(runtime,bot,'conflicting')
    changed=remember(runtime,bot,'updated',mode='replace',expected_revision=first['revision'])
    assert owner.snapshot('local',bot['id'])['routes'][0]['model']=='updated'
    assert parent['routes'][0]['model']=='preferred'  # running task snapshot unchanged
    directory.memory.records.undo('local',bot['id'],changed['change_id'],request_id='undo-model-memory')
    assert owner.snapshot('local',bot['id'])['routes'][0]['model']=='preferred'
    with pytest.raises(PermissionError):owner.snapshot('foreign',bot['id'])


@pytest.mark.asyncio
async def test_catalog_api_reuses_model_app_and_existing_origin_owner_guards(runtime,monkeypatch):
    models={'paint':{'id':'paint','model_type':'image_generation'},
        'unready':{'id':'unready','model_type':'image_generation','checkpoint_ready':False},
        'chat':{'id':'chat','model_type':'llm'},'helper':{'id':'helper','model_type':'image_generation','is_helper':True}}
    async def current(request):return models
    monkeypatch.setattr('ai2apps.api.model_profiles.model_catalog',current)
    assert {m['id'] for m in await catalog(None,'image_generation','normal')}=={'paint','unready'}
    bot,sid,_,_=setup(runtime);app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P))
    base='/messager/bots/'+bot['id']
    body={'request_id':'api-model-memory','subject':'bot','predicate':'model','kind':'model',
        'value':{'purpose':'image_generation','profile':'normal','model':'paint'},'text':'Image model'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        listed=await c.get(base+'/model-memory-catalog')
        assert listed.status_code==200 and listed.json()['purposes']==list(DEFAULT_MODEL_PURPOSES)
        assert (await c.post(base+'/memory-records',json=body)).status_code==403
        assert (await c.post(base+'/memory-records',json=body,headers={'Origin':'http://test'})).status_code==200
        for model in ('chat','unready','nonexistent'):
            body['value']['model']=model
            assert (await c.post(base+'/memory-records',json=body,headers={'Origin':'http://test'})).status_code==422
        assert (await c.get('/messager/bots/foreign/model-memory-catalog')).status_code==404
    frozen=runtime.messager_bots.model_memories.snapshot('local',bot['id'])
    models.clear()
    resolved=await runtime.messager_bots.model_memories.resolve(frozen)
    assert resolved['routes'][0]['available'] is False
    assert 'available' not in frozen['routes'][0]


@pytest.mark.asyncio
async def test_image_owner_uses_memory_but_preserves_operation_and_explicit_checks(runtime,monkeypatch):
    from ai2apps.images.parameters import from_options,describe,prepare
    from ai2apps.services.capability_routing import ProviderIncompatible
    rows=[from_options(id,id,{}) for id in ('system','preferred','explicit')]
    async def models(*args):return rows,[]
    monkeypatch.setattr('ai2apps.images.parameters.models',models)
    monkeypatch.setattr('ai2apps.images.service._default_image_model',lambda store:'system')
    with scope(snapshot()):
        assert (await prepare(runtime,P(),{'prompt':'paint'}))['model']=='preferred'
        implicit=await describe(runtime,P())
        explicit=await describe(runtime,P(),model_id='preferred')
        assert implicit['constraints']==explicit['constraints']  # provenance is not contract identity
        assert (await prepare(runtime,P(),{'prompt':'paint','model':'explicit'}))['model']=='explicit'
        with pytest.raises(ProviderIncompatible):await prepare(runtime,P(),{'prompt':'paint','model':'missing'})
        rows[:]=rows[:1]
        assert (await prepare(runtime,P(),{'prompt':'paint'}))['model']=='system'


@pytest.mark.asyncio
async def test_fresh_operation_catalog_overrides_cached_preference_readiness(runtime,monkeypatch):
    from ai2apps.images.parameters import from_options,prepare
    runtime.model_manager.put_default_models({'image_generation':'system'},available_model_ids={'system'})
    async def models(*args):return [from_options('system','System',{})],[]
    monkeypatch.setattr('ai2apps.images.parameters.models',models)
    monkeypatch.setattr('ai2apps.images.service._default_image_model',lambda manager:manager.resolve_default_model('image_generation'))
    v=snapshot();v['routes'][0]['available']=True
    with scope(v):
        assert runtime.model_manager.resolve_default_model('image_generation')=='preferred'
        assert (await prepare(runtime,P(),{'prompt':'paint'}))['model']=='system'


@pytest.mark.asyncio
async def test_model_catalog_lookup_is_coalesced_and_local_configuration_invalidates(runtime,monkeypatch):
    owner=runtime.messager_bots.model_memories;calls=[]
    async def models(request):
        calls.append(request);await asyncio.sleep(0)
        return {'preferred':{'id':'preferred','model_type':'image_generation'}}
    monkeypatch.setattr('ai2apps.api.model_profiles.model_catalog',models)
    def unrelated_workers(*args,**kwargs):raise AssertionError('Do not resolve worker credentials for invalidation')
    monkeypatch.setattr('ai2apps.model_providers.list_package_models',unrelated_workers)
    results=await asyncio.gather(owner.resolve(snapshot()),owner.resolve(snapshot()))
    assert len(calls)==1 and all(v['routes'][0]['available'] for v in results)
    runtime.model_manager.put_default_models({'image_generation':'preferred'},available_model_ids={'preferred'})
    await owner.resolve(snapshot())
    assert len(calls)==2


@pytest.mark.asyncio
async def test_image_catalog_does_not_resolve_unrelated_worker_families(runtime,monkeypatch):
    from ai2apps.images.parameters import models
    calls=[]
    def declared(r,*,model_type):calls.append(model_type);return ()
    monkeypatch.setattr('ai2apps.model_providers.list_package_models',declared)
    runtime.cloud=None
    await models(runtime,P(),False)
    assert calls==['image_generation']


@pytest.mark.asyncio
async def test_conversation_model_preference_reuses_catalog_and_never_crosses_privacy(runtime,monkeypatch):
    owner=runtime.messager_bots.model_memories;calls=[]
    async def models(request):
        calls.append(request)
        return {'preferred-chat':{'id':'preferred-chat','model_type':'llm'}}
    monkeypatch.setattr('ai2apps.api.model_profiles.model_catalog',models)
    v=snapshot('preferred-chat',purpose='work_chat')
    await owner.resolve(v)
    assert await owner.select_model('local',{},v,'work_chat','system-chat')=='preferred-chat'
    assert len(calls)==1
    runtime.privacy_mode=True
    with pytest.raises(ValueError,match='privacy profile'):
        await owner.select_model('local',{},v,'work_chat','normal-fallback')


@pytest.mark.asyncio
async def test_snapshot_is_captured_by_durable_owner_and_does_not_grant_access(runtime):
    bot,sid,_,provider=setup(runtime)
    remember(runtime,bot)
    rid=runtime.app_chat.submit(P(),sid,'frozen-model-run','Paint a fixture','fixture')
    run=runtime.agents.get_run(rid)
    assert run.input['model_preferences']['routes'][0]['model']=='preferred'
    context=runtime.tools.context_for_session(caller_id='test',session_id=sid,trace_id=rid)
    assert runtime.app_chat.authorize(context,provider.capability,{'prompt':'fixture'}) is False
    with pytest.raises(Exception):await runtime.tools.execute(provider.capability,{'prompt':'fixture'},context=context)


def test_continuation_uses_original_logical_task_snapshot(runtime):
    from test_bot_memory_history import seed
    bot,sid,_,_=setup(runtime)
    seed(runtime,bot,sid,'root-memory-task','Root')
    seed(runtime,bot,sid,'follow-memory-task','Root')
    root=runtime.messager_dialogue.row('root-memory-task')
    later=runtime.messager_dialogue.row('follow-memory-task')
    # These history fixtures have no Agent Runs: expose only the bounded source
    # snapshots to test logical linkage, without bypassing actual owner checks.
    get=runtime.agents.get_run
    runtime.agents.get_run=lambda ref:SimpleNamespace(input={'model_preferences':snapshot('old' if ref==root['source_run'] else 'new')})
    try:
        with runtime.database.transaction(write=True) as db:
            db.execute('UPDATE messager_job_sessions SET session_id=? WHERE job_id=?',(root['id'],later['id']))
        value=runtime.messager_bots.model_memories.capture('local',{'bot_id':bot['id'],'dialogue_job':later['id']})
        assert value['routes'][0]['model']=='old'
    finally:runtime.agents.get_run=get


@pytest.mark.asyncio
@pytest.mark.parametrize('child_preference',[None,'child-image'])
async def test_real_delegation_worker_inherits_frozen_preferences(runtime,monkeypatch,child_preference):
    """Real durable delegation and access review; deterministic model/tool fixtures."""
    from dataclasses import replace
    from test_bot_delegation import start,until
    create=runtime.messager_bots.create
    def create_with_memory(actor,name,duty):
        bot=create(actor,name,duty)
        if name=='Fixture Bot':remember(runtime,bot,'parent-image')
        elif child_preference:remember(runtime,bot,child_preference)
        return bot
    monkeypatch.setattr(runtime.messager_bots,'create',create_with_memory)
    async def models(request):return {m:{'id':m,'model_type':'image_generation'} for m in ['parent-image','child-image']}
    monkeypatch.setattr('ai2apps.api.model_profiles.model_catalog',models)
    observed=[]
    try:
        bot,target,sid,calls,provider,card,parent=await start(runtime)
        original=runtime.app_capability_router.providers[provider.id]
        async def execute(args,context):
            observed.append(choose(runtime,'image_generation','system')[0])
            return await original.handler(args,context)
        runtime.app_capability_router.providers[provider.id]=replace(original,handler=execute)
        service=runtime.messager_bot_delegation
        app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            approved=await client.post('/messager/bots/'+bot['id']+'/delegations/'+card['id']+'/decisions/approve',
                json={'review_hash':card['review_hash']},headers={'Origin':'http://test'})
            assert approved.status_code==200,approved.text
        row=await until(lambda:service.row(card['id']) if service.row(card['id'])['status']=='resumed' else None)
        child=runtime.messager_dialogue.row(row['child_job'])
        source=runtime.agents.get_run(child['source_run'])
        expected=child_preference or 'parent-image'
        assert source.input['model_preferences']['routes'][0]['model']==expected
        assert observed==[expected]
        assert runtime.agents.get_run(parent['source_run']).input['model_preferences']['routes'][0]['model']=='parent-image'
    finally:await runtime.stop_background_tasks()
