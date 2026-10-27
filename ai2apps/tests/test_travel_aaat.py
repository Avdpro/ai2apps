"""AaAT travel owner acceptance; website/model responses are fixtures."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import json
import pytest
from jsonschema import ValidationError, Draft202012Validator
from test_web_agent_mini_apps import broker
from test_app_interactions import runtime
from ai2apps.browser.travel_aaat import TravelAdapters, schema, reviewed_trip, combined_trip, DECLARATION, MINI
from ai2apps.services import ToolCallContext, ToolProviderError


def args(**extra):
    return {'origin':'San Francisco','destination':'Beijing','departure':'2027-06-01',
            'return_date':'2027-06-06','direction':'both',**extra}


def setup(broker,monkeypatch):
    service,mounted,principal=broker
    mounted.declaration=json.loads((Path(__file__).resolve().parents[2]/'packages/ai2apps-trip-planner/app.yaml').read_text())['mini_apps'][0]
    mounted.mount.update(app_key=MINI,interaction_session_id='session')
    adapter=TravelAdapters(service.runtime);adapter.broker=service
    monkeypatch.setattr(adapter,'resolve',lambda _:(principal,mounted))
    ctx=ToolCallContext('test',session_id='session',actor_user_id='owner',installation_id='install',invocation_id='invocation')
    return adapter,ctx


def test_domain_schemas_have_independent_required_fields_and_no_booking():
    assert 'origin' not in schema('hotels')['properties']
    assert schema('flights')['properties']['direction']['default']=='outbound'
    assert schema('hotels')['required']==['destination','hotel_checkin','hotel_checkout']
    assert 'source_tasks' in schema('refine')['required']
    for operation in ('flights','hotels','guide','refine'):Draft202012Validator.check_schema(schema(operation))
    assert 'never reserve' in DECLARATION['instructions'][0]
    trip=reviewed_trip({'destination':'Beijing','hotel_checkin':'2027-06-01','hotel_checkout':'2027-06-03'},'hotels')
    assert trip['nights']==2 and trip['origin']==''


@pytest.mark.asyncio
async def test_flights_submit_both_legs_with_same_public_task_and_privacy_routing(broker,monkeypatch):
    adapter,ctx=setup(broker,monkeypatch);seen=[]
    async def wait(runtime,broker,mounted,principal,task,*_):
        seen.append(task);return {**task,'result':{'status':'complete','items':[{'quote':'Actual fixture'}]}}
    monkeypatch.setattr('ai2apps.browser.travel_aaat.wait_task',wait)
    result=await adapter.execute('flights',args(model_profile='privacy'),ctx)
    assert sorted(t['input']['leg'] for t in seen)==['outbound','return']
    assert all(t['input']['model_profile']=='privacy' for t in seen)
    assert result['aaat_context']['status']=='complete' and len(result['sources'])==2
    assert len({t['id'] for t in seen})==2
    again=await adapter.execute('flights',args(model_profile='privacy'),ctx)
    assert set(again['source_tasks'])==set(result['source_tasks'])


@pytest.mark.asyncio
async def test_one_failed_flight_leg_preserves_other_leg_and_failure_identity(broker,monkeypatch):
    adapter,ctx=setup(broker,monkeypatch)
    async def wait(runtime,broker,mounted,principal,task,*_):
        if task['input']['leg']=='return':raise ToolProviderError('Fixture unavailable')
        return {**task,'result':{'status':'complete','items':[{'quote':'Native fixture'}]}}
    monkeypatch.setattr('ai2apps.browser.travel_aaat.wait_task',wait)
    result=await adapter.execute('flights',args(),ctx)
    assert len(result['sources'])==1 and result['failures'][0]['leg']=='return'
    assert result['aaat_context']['status']=='partial'


@pytest.mark.asyncio
async def test_hotel_query_needs_no_flight_origin_and_preserves_bed_area_preferences(broker,monkeypatch):
    adapter,ctx=setup(broker,monkeypatch);seen=[]
    async def wait(runtime,broker,mounted,principal,task,*_):
        seen.append(task);return {**task,'result':{'status':'partial','items':[]}}
    monkeypatch.setattr('ai2apps.browser.travel_aaat.wait_task',wait)
    result=await adapter.execute('hotels',{'destination':'Beijing','hotel_checkin':'2027-06-01',
        'hotel_checkout':'2027-06-03','hotel_area':'Summer Palace','hotel_bed':'large_double','hotel_near_transit':True},ctx)
    assert len(seen)==1 and seen[0]['input']['provider']=='ctrip_hotels'
    assert seen[0]['input']['trip']['hotel_bed']=='large_double'
    assert seen[0]['input']['trip']['hotel_near_transit']
    assert result['aaat_context']['status']=='partial'
    with pytest.raises(ValidationError):await adapter.execute('hotels',{'destination':'Beijing'},ctx)
    with pytest.raises(ValueError):await adapter.execute('flights',args(sources=['expedia_flights']),ctx)


@pytest.mark.asyncio
async def test_guide_uses_observed_source_tasks_for_owner_summary(broker,monkeypatch):
    adapter,ctx=setup(broker,monkeypatch);seen=[]
    async def wait(runtime,broker,mounted,principal,task,*_):
        seen.append(task);return {**task,'result':{'status':'partial','items':[]} if task['capability']=='query' else {'summary':'Fixture guide'}}
    monkeypatch.setattr('ai2apps.browser.travel_aaat.wait_task',wait)
    # Broker summary requires the actual query to be completed; fixture only its
    # observer/submit boundary here, while query-source ownership has owner tests.
    original=adapter.broker.submit_declared
    def submit(*a,**kw):
        if kw['capability']=='summarize':return {'id':'summary','input':kw['parameters'],'capability':'summarize'}
        return original(*a,**kw)
    monkeypatch.setattr(adapter.broker,'submit_declared',submit)
    result=await adapter.execute('guide',{k:v for k,v in args().items() if k not in ('origin','direction')},ctx)
    assert [t['capability'] for t in seen]==['query','summarize']
    assert seen[1]['input']['source_tasks']==[seen[0]['id']]
    assert result['itinerary']['summary']=='Fixture guide'


def test_refinement_references_reject_another_session_profile_or_incomplete_task(broker,monkeypatch):
    adapter,ctx=setup(broker,monkeypatch)
    task={'id':'observed','session_id':'session','profile_key':'default','status':'completed','capability':'query'}
    monkeypatch.setattr(adapter.broker,'task_declared',lambda *a:task)
    assert adapter.observed(None,None,'observed',ctx,'default')==task
    for change in ({'session_id':'foreign'},{'profile_key':'other'},{'status':'running'},{'capability':'prepare'}):
        original=deepcopy(task);task.update(change)
        with pytest.raises(ToolProviderError):adapter.observed(None,None,'observed',ctx,'default')
        task.clear();task.update(original)


@pytest.mark.asyncio
async def test_registered_capabilities_forms_and_trusted_declaration(runtime):
    catalog=runtime.app_capability_router.catalog()
    owned=[p for p in catalog if p['mini_app_id']==MINI]
    assert {p['capability'] for p in owned}=={'travel.flights','travel.hotels','travel.guide','travel.refine'}
    from ai2apps.identity import RequestPrincipal
    from ai2apps.agents.parameter_forms import resolve_form
    for provider in owned:
        assert provider['agent_context']==DECLARATION
        tool=runtime.services.get_tool(provider['capability'])
        assert set(tool.effects)=={'external_read','network'}
        form=resolve_form({'capability':provider['capability'],'provider':provider['id']})
        descriptor=await form.describe(runtime,RequestPrincipal.legacy_local(),form,{},None) if form.describe else None
        assert form.app_id=='ai2apps.ai-browser'
        assert descriptor['schema']['required']==schema(provider['capability'].split('.')[-1])['required']
        assert any(isinstance(f.get('label'),dict) and 'zh' in f['label'] for f in descriptor['fields'])


@pytest.mark.asyncio
async def test_refine_returns_reviewable_proposal_without_submitting_requery(broker,monkeypatch):
    adapter,ctx=setup(broker,monkeypatch);seen=[]
    previous={'id':'source','input':{'provider':'google_flights','trip':reviewed_trip(args(),'flights')},'capability':'query'}
    monkeypatch.setattr(adapter,'observed',lambda *a:previous)
    def submit(*a,**kw):
        seen.append(kw);return {'id':'refine-task','input':kw['parameters']}
    monkeypatch.setattr(adapter.broker,'submit_declared',submit)
    async def wait(*a):return {**a[4],'result':{'action':'requery','trip':{**previous['input']['trip'],'flight_cabin':'business'},'sources':['google_flights']}}
    monkeypatch.setattr('ai2apps.browser.travel_aaat.wait_task',wait)
    result=await adapter.execute('refine',{'request':'Cheap business class','source_tasks':['source']},ctx)
    assert [s['capability'] for s in seen]==['refine']
    assert result['requires_review'] and result['proposal']['action']=='requery'
    assert result['aaat_context']['status']=='resolved'


def test_independent_flight_and_hotel_inputs_can_be_refined_together_without_scope_loss():
    flight=reviewed_trip(args(),'flights')
    hotel=reviewed_trip({'destination':'Beijing','hotel_checkin':'2027-06-02','hotel_checkout':'2027-06-06',
                        'hotel_area':'Summer Palace','hotel_bed':'large_double'},'hotels')
    tasks=[{'input':{'provider':'google_flights','trip':flight}},{'input':{'provider':'booking','trip':hotel}}]
    combined=combined_trip(tasks)
    assert combined['origin']=='San Francisco' and combined['departure']=='2027-06-01'
    assert combined['hotel_area']=='Summer Palace' and combined['hotel_checkin']=='2027-06-02'
    assert combined['hotel_bed']=='large_double'
    from ai2apps.browser.travel import research_identity
    for task in tasks:
        p=task['input'];assert research_identity(combined,p['provider'])==research_identity(p['trip'],p['provider'])
    hotel['destination']='Tokyo'
    with pytest.raises(ToolProviderError):combined_trip(tasks)


@pytest.mark.asyncio
async def test_first_source_is_visible_before_slow_second_source_finishes(broker,monkeypatch):
    import asyncio
    adapter,ctx=setup(broker,monkeypatch);visible=asyncio.Event();release=asyncio.Event();updates=[]
    async def progress(update):
        updates.append(update)
        if update.get('content',{}).get('travel_sources'):visible.set()
    async def wait(runtime,broker,mounted,principal,task,*_):
        if task['input']['leg']=='return':await release.wait()
        return {**task,'result':{'status':'complete','items':[{'quote':'Observed fixture'}]}}
    monkeypatch.setattr('ai2apps.browser.travel_aaat.wait_task',wait)
    pending=asyncio.create_task(adapter.execute('flights',args(),replace(ctx,progress_reporter=progress)))
    try:
        await asyncio.wait_for(visible.wait(),2)
        assert not pending.done()
        assert updates[-1]['content']['travel_sources'][0]['parameters']['leg']=='outbound'
    finally:release.set()
    assert len((await pending)['source_tasks'])==2


def test_discovery_does_not_launch_a_missing_instance(runtime,monkeypatch):
    from ai2apps.chat import ChatRepository
    from ai2apps.identity import RequestPrincipal
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Travel discovery')
    ctx=ToolCallContext.from_principal(RequestPrincipal.legacy_local(),caller_id='test',session_id=thread.session.id)
    monkeypatch.setattr(runtime.extension_manager,'_studio_mini_app_definition',lambda *a:({'package_id':'fixture.not-launched','effective_digest':'v1'},{}))
    def forbidden(*a,**kw):raise AssertionError('Discovery must not launch an App')
    monkeypatch.setattr(runtime.extension_manager,'launch_app',forbidden)
    _,mounted=TravelAdapters(runtime).discovery_mount(ctx)
    assert mounted is None


@pytest.mark.asyncio
async def test_recent_context_is_scoped_to_session_and_does_not_include_private_notes(broker,monkeypatch):
    from ai2apps.browser.travel_aaat import install
    adapter,ctx=setup(broker,monkeypatch)
    # The broker fixture binds tasks to its real persisted Session.
    ctx=replace(ctx,session_id=adapter.runtime.fixture_session_id)
    async def wait(runtime,broker,mounted,principal,task,*_):return {**task,'result':{'status':'complete'}}
    monkeypatch.setattr('ai2apps.browser.travel_aaat.wait_task',wait)
    result=await adapter.execute('flights',args(preferences='private meeting notes'),ctx)
    with adapter.runtime.database.transaction(write=True) as db:
        db.execute('UPDATE browser_tasks SET session_id=? WHERE id=?',('foreign-session',result['source_tasks'][0]))
    service,mounted,principal=broker
    monkeypatch.setattr(TravelAdapters,'discovery_mount',lambda *a:(principal,mounted))
    registrations={}
    def capture(name,*a,**kw):registrations[name]=kw
    install(adapter.runtime,capture)
    context=registrations['travel.refine']['discovery_context'](ctx)
    assert [t['task_id'] for t in context['recent_tasks']]==[result['source_tasks'][1]]
    assert 'private meeting notes' not in json.dumps(context)


@pytest.mark.asyncio
async def test_routed_tool_reaches_public_broker_and_persists_owned_tasks(runtime,monkeypatch):
    """Real Tool router/auth/Task repository; browser/model completion is fixture."""
    from ai2apps.chat import ChatRepository
    from ai2apps.identity import IdentityRepository,OrganizationType
    from ai2apps.studio.capability_broker import MountedMiniApp
    from ai2apps.browser.tasks import BrowserTaskRepository
    identities=IdentityRepository(runtime.database)
    identities.bind_installation(installation_id='travel-install',cloud_device_id='travel-device',organization_id='travel-org',
        organization_type=OrganizationType.HOUSEHOLD,core_user_id='travel-owner',billing_account_id='travel-billing',access_epoch=1)
    principal=identities.local_principal_for('travel-owner')
    thread,_=ChatRepository(runtime.database,runtime.events,principal=principal).create_thread(title='Travel routed fixture')
    ctx=replace(ToolCallContext.from_principal(principal,caller_id='test',session_id=thread.session.id),invocation_id='travel-routed-fixture')
    declaration=json.loads((Path(__file__).resolve().parents[2]/'packages/ai2apps-trip-planner/app.yaml').read_text())['mini_apps'][0]
    mounted=MountedMiniApp(mount={'app_instance_id':'fixture-trip-instance','app_key':MINI,
        'effective_digest':'fixture-digest','interaction_session_id':thread.session.id},declaration=declaration,capabilities=frozenset())
    monkeypatch.setattr('ai2apps.browser.mini_apps.WebAgentMiniAppBroker.registered',lambda *a:mounted)
    monkeypatch.setattr('ai2apps.browser.profiles.BrowserProfileRepository.require',lambda *a:NS(name='Default',is_default=True))
    monkeypatch.setattr(runtime.model_manager,'resolve_default_model',lambda *a,**kw:'configured-model')
    async def wait(runtime,broker,mount,principal,task,*_):return {**task,'result':{'status':'complete','items':[{'quote':'Fixture observed flight'}]}}
    monkeypatch.setattr('ai2apps.browser.travel_aaat.wait_task',wait)
    result=await runtime.app_capability_router.invoke('travel.flights',args(),ctx)
    assert result['app_id']=='ai2apps.ai-browser' and result['mini_app_id']==MINI
    repository=BrowserTaskRepository(runtime.database,runtime.events)
    tasks=[repository.get(principal.actor_user_id,key) for key in result['source_tasks']]
    assert len(tasks)==2 and all(t['session_id']==thread.session.id for t in tasks)
    for task in tasks:
        _,caller=repository.program(principal.actor_user_id,task['id'])
        assert caller=='web-mini-app:fixture-trip-instance:'+MINI


def test_one_way_without_return_date_and_conditional_return_requirement():
    from ai2apps.browser.travel import query_source, search_url
    validator=Draft202012Validator(schema('flights'))
    values={'origin':'SFO','destination':'PEK','departure':'2027-06-01'}
    validator.validate(values)
    trip=reviewed_trip(values,'flights')
    assert trip['return_date']=='' and trip['hotel_checkout']==''
    for direction in ('both','return'):
        with pytest.raises(ValidationError):validator.validate({**values,'direction':direction})
        with pytest.raises(ValueError):reviewed_trip({**values,'direction':direction},'flights')
    source=query_source({'provider':'google_flights','trip':trip,'locale':'zh','model_profile':'normal'})
    steps={s['name']:s for s in source['steps']}
    assert steps['dates']['arguments']['one_way'] is True
    assert 'One way' in steps['party']['arguments']['goal']
    assert 'ONLY' in steps['dates']['arguments']['goal']
    assert 'trip=oneway' in search_url('expedia_flights',trip)
    assert 'leg2=' not in search_url('expedia_flights',trip)
    with pytest.raises(ValueError):query_source({'provider':'google_flights','trip':trip,'leg':'return'})
    with pytest.raises(ValueError):reviewed_trip({**values,'departure':'2020-01-01'},'flights')


@pytest.mark.asyncio
async def test_default_outbound_task_needs_no_return_date(broker,monkeypatch):
    adapter,ctx=setup(broker,monkeypatch);seen=[]
    async def wait(runtime,broker,mounted,principal,task,*_):
        seen.append(task);return {**task,'result':{'status':'complete','items':[]}}
    monkeypatch.setattr('ai2apps.browser.travel_aaat.wait_task',wait)
    await adapter.execute('flights',{'origin':'San Francisco','destination':'Beijing','departure':'2027-06-01'},ctx)
    assert len(seen)==1 and seen[0]['input']['leg']=='outbound'
    assert seen[0]['input']['trip']['return_date']==''

@pytest.mark.asyncio
@pytest.mark.parametrize('sources,expected',[([], 'ctrip_flights'),(['google_flights'],'google_flights')])
async def test_ctrip_domestic_default_preserves_explicit_source(broker,monkeypatch,sources,expected):
    adapter,ctx=setup(broker,monkeypatch);seen=[]
    async def wait(runtime,broker,mounted,principal,task,*_):
        seen.append(task);return {**task,'result':{'status':'partial','items':[]}}
    monkeypatch.setattr('ai2apps.browser.travel_aaat.wait_task',wait)
    await adapter.execute('flights',args(origin='北京',destination='上海',**({'sources':sources} if sources else {})),ctx)
    assert {t['input']['provider'] for t in seen}=={expected}
