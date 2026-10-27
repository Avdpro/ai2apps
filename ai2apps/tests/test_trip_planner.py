from copy import deepcopy
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from jsonschema import ValidationError

from ai2apps.browser.travel import (MINI, PROVIDERS, compose_summary, prepare_source,
    project_result, query_source, validate_trip, lodging_area)
from ai2apps.browser.mini_apps import observed_result_urls, validate_web_agent
from ai2apps.agent_builder.compiler import compile_source
from ai2apps.extensions.development import DevelopmentPackageLoader
from ai2apps.studio.capability_broker import StudioCapabilityBroker
from ai2apps.studio.capability_broker import StudioCapabilityError
from ai2apps.tests.test_web_agent_mini_apps import broker

ROOT = Path(__file__).resolve().parents[2]


def trip():
    return dict(origin='SFO',destination='Tokyo (NRT)',departure='2027-06-01',
        return_date='2027-06-05',hotel_checkin='2027-06-02',hotel_checkout='2027-06-05',
        nights=4,adults=2,purpose='business',preferences='Near the venue, budget USD 250/night')


def test_package_uses_public_loader_and_three_task_capabilities():
    package = DevelopmentPackageLoader(ROOT)._load(ROOT/'packages/ai2apps-trip-planner')
    entries = validate_web_agent(package.manifest['mini_apps'][0])
    assert [e['id'] for e in entries] == ['prepare','query','summarize','refine']
    for entry in entries:
        assert compile_source(entry['source']).valid
    assert all(s['operation'] in ('ai.transform','assign') for s in prepare_source()['steps'])


@pytest.mark.parametrize('provider', PROVIDERS)
def test_queries_are_read_only_and_urls_use_confirmed_criteria(provider):
    source = query_source(dict(provider=provider,trip=trip()))
    assert compile_source(source).valid
    assert all(s['operation'] in ('open','page_access','inspect','read_page','ai.transform','assign') or
        (provider=='ctrip_hotels' and s['operation']=='input' and s['name']=='keyword' and s['target']=='位置/品牌/酒店 (选填)') or
        (provider in ('google_flights','booking','expedia_hotels','ctrip_flights','ctrip_hotels') and s['operation']=='click' and s.get('target')==('搜索' if provider.startswith('ctrip_') else 'Search') and s['name']=='search')
        for s in source['steps'])
    assert all(s['arguments']['preparation_only'] is True for s in source['steps'] if s.get('execution',{}).get('mode')=='interpreted')
    read = source['steps'][0]['arguments']
    query = parse_qs(urlsplit(read['url']).query)
    if provider=='booking':
        assert query['checkin']==['2027-06-02'] and query['checkout']==['2027-06-05']
        assert query['group_adults']==['2'] and query['no_rooms']==['1']
    if provider=='expedia_flights':
        assert 'from:SFO,to:NRT,departure:06/01/2027' in query['leg1'][0]
    if provider=='sights':
        assert trip()['preferences'] not in query['q'][0]
    assert all('https://*' not in scope for scope in source['site_scope'])


@pytest.mark.parametrize('change',[
    {'departure':'2020-01-01'}, {'return_date':'2027-06-01'}, {'nights':2},
    {'hotel_checkin':'2027-06-06'}, {'origin':''}, {'adults':0},
])
def test_invalid_or_ambiguous_trip_never_reads_a_website(change):
    value={**trip(),**change}
    with pytest.raises((ValueError, ValidationError)):
        validate_trip(value,flights=True,hotels=True,today=date(2026,10,22))


def test_expedia_never_guesses_airports_from_city_names():
    with pytest.raises(ValueError, match='机场代码'):
        query_source(dict(provider='expedia_flights',trip={**trip(),'origin':'San Francisco'}))


def test_model_options_and_price_must_have_verbatim_observed_evidence():
    page={'url':'https://www.booking.com/searchresults.html','text':'Hotel Sakura — USD 240 per night, taxes unknown.','title':'Hotels'}
    good={'title':'Sakura','details':'Near the station','quote':page['text'],'price_text':'USD 240','price_basis':'per night'}
    hallucinated={**good,'title':'Invented','quote':'Hotel invented costs USD 10'}
    wrong_price={**good,'title':'Wrong price','price_text':'USD 1'}
    raw={'assigned':{'travel_report':{'page':page,'extracted':{'items':[good,hallucinated,wrong_price],'criteria_note':'Dates not confirmed'}}}}
    result=project_result(raw,{'provider':'booking','trip':trip()})
    assert len(result['items'])==2 and result['items'][0]['price_text']=='USD 240'
    assert result['items'][1]['price_text']==''
    assert result['items'][0]['url']==page['url']
    assert observed_result_urls(result)=={page['url']}
    page['url']='https://evil.test/fake'
    assert not project_result(raw,{'provider':'booking','trip':trip()})['items']
    assert not project_result(raw,{'provider':'booking','trip':trip()})['links']


def test_empty_observed_page_can_be_opened_without_claiming_options():
    raw={'assigned':{'travel_report':{'page':{'url':'https://www.booking.com/searchresults.html','text':'Nothing found'},'extracted':{'items':[]}}}}
    result=project_result(raw,{'provider':'booking','trip':trip()})
    assert result['status']=='partial' and result['items']==[]
    assert observed_result_urls(result)=={'https://www.booking.com/searchresults.html'}


def test_summary_accepts_only_same_trip_profile_owner_observed_tasks():
    params={'source_tasks':['a'],'trip':trip(),'locale':'en','model_profile':'normal'}
    source={'status':'completed','capability':'query','profile_key':'p','input':{'trip':trip()},'result':{'provider':'booking','items':[{'title':'Observed'}],'status':'partial'}}
    assert compose_summary(params,'p',lambda key:source)['observations'][0]['items']==[{'title':'Observed'}]
    for change in [{'status':'waiting_input'},{'profile_key':'other'},{'capability':'prepare'},{'input':{'trip':{**trip(),'adults':1}}}]:
        with pytest.raises(ValueError):compose_summary(params,'p',lambda key:{**source,**change})
    def foreign(key):raise PermissionError('foreign owner denied')
    with pytest.raises(PermissionError):compose_summary(params,'p',foreign)


@pytest.mark.parametrize('identity',['example.maps','another.travel'])
def test_device_location_probe_is_declared_optional_and_identity_independent(identity):
    declaration={'id':identity,'requirements':{'capabilities':[{'capability':'device.location','optional':True}]},
        'web_agent':{'schema':'ai2apps.web-agent-mini-app/v1','capabilities':[{'id':'prepare','source':prepare_source()}]}}
    broker=StudioCapabilityBroker(SimpleNamespace(extension_manager=None))
    location=next(v for v in broker.probe_declaration('ai2apps.ai-browser',declaration)['items'] if v['capability']=='device.location')
    assert location['ready'] is True and location['required'] is False
    declaration.pop('requirements')
    assert not any(v['capability']=='device.location' for v in broker.probe_declaration('ai2apps.ai-browser',declaration)['items'])


@pytest.mark.parametrize('private,requested,expected', [(False,'normal','normal'),(False,'privacy','privacy'),(True,'normal','privacy')])
def test_travel_uses_shared_task_queue_and_system_privacy(broker, private, requested, expected):
    service, mounted, principal = broker
    mounted.declaration = DevelopmentPackageLoader(ROOT)._load(ROOT/'packages/ai2apps-trip-planner').manifest['mini_apps'][0]
    calls = []
    service.runtime.privacy_mode = private
    service.runtime.model_manager.resolve_default_model = lambda purpose, profile='normal': calls.append((purpose,profile)) or 'configured-model'
    params = {'provider':'booking','trip':trip(),'model_profile':requested,'locale':'zh'}
    task = service.submit('mount',principal,capability='query',parameters=params,profile='default',request_id='trip-query')
    assert task['status']=='queued'
    assert calls[0]==('work_standard',expected)
    assert task['browser_context']['model_profile']==expected
    assert service.submit('mount',principal,capability='query',parameters=params,profile='default',request_id='trip-query')['id']==task['id']


def test_missing_model_blocks_travel_before_any_website_task(broker):
    service, mounted, principal = broker
    mounted.declaration = DevelopmentPackageLoader(ROOT)._load(ROOT/'packages/ai2apps-trip-planner').manifest['mini_apps'][0]
    service.runtime.model_manager.resolve_default_model = lambda *a,**kw:None
    with pytest.raises(StudioCapabilityError, match='Configure'):
        service.submit('mount',principal,capability='query',parameters={
            'provider':'booking','trip':trip(),'model_profile':'privacy','locale':'zh'},profile='default',request_id='missing-model')
    with service.runtime.database.transaction() as connection:
        assert connection.execute('SELECT count(*) FROM browser_tasks').fetchone()[0]==0


def test_lodging_area_is_applied_to_search_and_legacy_preferences_migrate():
    value={**trip(),'preferences':'住宿在颐和园附近；行程5天'}
    assert lodging_area(value)=='颐和园'
    for provider in ['booking','expedia_hotels']:
        source=query_source({'provider':provider,'trip':value})
        query=parse_qs(urlsplit(source['steps'][0]['arguments']['url']).query)
        assert '颐和园' in (query.get('ss') or query['destination'])[0]
    assert lodging_area({**value,'hotel_area':'海淀公园附近'})=='海淀公园'


def test_google_uses_actual_form_stages_instead_of_ignored_q_parameter():
    source=query_source({'provider':'google_flights','trip':trip()})
    assert 'q=' not in source['steps'][0]['arguments']['url']
    stages=[s['name'] for s in source['steps']]
    assert stages[:9]==['open','access','origin','destination','dates','dates_commit','party','search','read']
    assert source['steps'][8]['arguments']=={'owner_action':'travel_results'}
    assert source['steps'][7]['operation']=='click'
    assert source['steps'][7]['target']=='Search'
    assert source['steps'][7]['execution']['mode']=='compiled'


def test_no_recommendation_for_unverified_criteria_or_downtown_distance():
    observed={'id':'option-0','title':'Actual hotel','quote':'Actual hotel\n2.7 miles from downtown\nUSD 607 for 5 nights','url':'https://www.booking.com/hotel/cn/actual.html'}
    item={'id':'option-0','title':'Model invented name','quote':observed['quote'],'price_text':'USD 607',
        'score':98,'area_match':'matched','area_evidence':'2.7 miles from downtown','recommendation_reason':'Close to landmark'}
    raw={'assigned':{'travel_report':{'page':{'url':'https://www.booking.com/searchresults.html','text':observed['quote'],'observed_items':[observed]},
        'extracted':{'items':[item],'criteria_verified':True}}}}
    result=project_result(raw,{'provider':'booking','trip':{**trip(),'hotel_area':'颐和园'}})
    assert result['status']=='partial'
    assert result['items'][0]['title']=='Actual hotel'
    assert not result['items'][0]['recommended'] and not result['items'][0]['area_verified']
    observed['quote']='Actual hotel\n0.8 km from Summer Palace\nUSD 607 for 5 nights'
    raw['assigned']['travel_report']['page']['text']=observed['quote']
    item.update(quote=observed['quote'],area_evidence='0.8 km from Summer Palace')
    result=project_result(raw,{'provider':'booking','trip':{**trip(),'hotel_area':'颐和园'}})
    assert result['items'][0]['recommended'] and result['items'][0]['url']==observed['url']
    raw['assigned']['travel_report']['extracted']['criteria_verified']=False
    assert not project_result(raw,{'provider':'booking','trip':trip()})['items'][0]['recommended']

@pytest.mark.asyncio
async def test_travel_reader_uses_only_current_scoped_visible_page():
    from unittest.mock import AsyncMock
    from ai2apps.browser.travel_reader import read
    page=SimpleNamespace(wait_stable=AsyncMock(return_value={'stable':True}), snapshot=AsyncMock(return_value={'url':'https://www.booking.com/searchresults.html'}),
        handle_access=AsyncMock(return_value={'classification':'none'}),
        call_json=AsyncMock(return_value={'observed_items':[{'id':'option-0','title':'Visible hotel'}]}))
    result=await read(page,{},dict(provider='booking'),None)
    assert result['evidence']['result']['observed_items'][0]['title']=='Visible hotel'
    page.snapshot=AsyncMock(return_value={'url':'https://evil.test/'})
    assert (await read(page,{},dict(provider='booking'),None))['outcome']=='restricted'
    assert page.call_json.await_count==1


def test_card_quote_whitespace_normalization_preserves_native_proof_and_rejects_rewrites():
    native='10:45 AM\xa0–\xa05:25 PM+1\nUnited\nNonstop\n$1,215 round trip'
    item={'id':'option-0','title':'Flight','quote':native.replace('\xa0',' '),'price_text':'$1,215','score':90}
    raw={'assigned':{'travel_report':{'page':{'url':'https://www.google.com/travel/flights/search','text':native,
        'observed_items':[{'id':'option-0','title':'Observed flight','quote':native}]},
        'extracted':{'criteria_verified':True,'items':[item]}}}}
    params={'provider':'google_flights','trip':trip()}
    result=project_result(raw,params)
    assert result['status']=='complete' and result['items'][0]['quote']==native
    item['quote']=item['quote'].replace('Nonstop','直飞')
    assert project_result(raw,params)['items']==[]

@pytest.mark.parametrize('private,requested,expected', [(False,'normal','normal'),(False,'privacy','privacy'),(True,'normal','privacy')])
def test_refine_uses_existing_task_and_shared_privacy_route(broker, private, requested, expected):
    from ai2apps.browser.travel_refine import INPUTS
    service,mounted,principal=broker
    mounted.declaration=DevelopmentPackageLoader(ROOT)._load(ROOT/'packages/ai2apps-trip-planner').manifest['mini_apps'][0]
    service.runtime.privacy_mode=private
    calls=[]
    service.runtime.model_manager.resolve_default_model=lambda purpose,profile='normal':calls.append((purpose,profile)) or 'configured-model'
    prior=dict(status='completed',capability='query',profile_key='default',input={'trip':trip(),'provider':'google_flights'},
               result={'provider':'google_flights','items':[],'criteria_verified':True})
    params={'trip':trip(),'request':'Nonstop only','locale':'en','model_profile':requested,'source_tasks':['prior']}
    task=service.submit_declared(mounted,principal,capability='refine',parameters=params,profile='default',request_id='refine-public',_task=lambda _:prior)
    assert task['status']=='queued' and task['capability']=='refine'
    assert task['browser_context']['model_profile']==expected and calls[0]==('work_standard',expected)
    assert task['input']['observations'][0]['task_id']=='prior'
    assert service.submit_declared(mounted,principal,capability='refine',parameters=params,profile='default',request_id='refine-public',_task=lambda _:prior)['id']==task['id']

@pytest.mark.parametrize('origin,destination,flight,hotel',[
    ('北京','上海','ctrip_flights','ctrip_hotels'),
    ('Beijing (PEK)','Shanghai (PVG)','ctrip_flights','ctrip_hotels'),
    ('SFO','北京','google_flights','ctrip_hotels'),
    ('北京','Tokyo','google_flights','booking'),
    ('巴黎','伦敦','google_flights','booking'),
    ('未知城市','未知目的地','google_flights','booking'),
])
def test_domestic_default_sources_do_not_depend_on_ui_language(origin,destination,flight,hotel):
    from ai2apps.browser.travel import default_sources
    value={'origin':origin,'destination':destination}
    assert default_sources(value,'flight')==[flight]
    assert default_sources(value,'hotel')==[hotel]


def test_ctrip_return_form_and_lodging_landmark_have_explicit_stages():
    value={**trip(),'origin':'北京','destination':'上海','hotel_area':'人民广场'}
    flight=query_source({'provider':'ctrip_flights','trip':value,'leg':'return'})
    route=next(s for s in flight['steps'] if s['name']=='origin')['arguments']
    assert (route['origin'],route['destination'],route['departure'],route['return_date'],route['one_way'])==('上海','北京',value['return_date'],'',True)
    hotel=query_source({'provider':'ctrip_hotels','trip':value})
    location=next(s for s in hotel['steps'] if s['name']=='location')
    assert location['arguments']['hotel_area']=='人民广场'
    assert 'ONLY the MAIN Ctrip CITY' in location['desc']
    assert next(s for s in hotel['steps'] if s['name']=='search')['target']=='搜索'
    assert hotel['site_scope']==['https://hotels.ctrip.com/**']


def test_ctrip_keyword_is_free_text_after_city_and_party_not_an_ai_autocomplete_loop():
    for area in ('三元桥','颐和园',''):
        source=query_source({'provider':'ctrip_hotels','trip':{**trip(),'hotel_area':area}})
        steps={s['name']:s for s in source['steps']}
        assert steps['location']['on']['success']=='dates'
        assert steps['dates']['on']['success']=='party'
        assert steps['party']['on']['success']=='keyword'
        keyword=steps['keyword']
        if area:
            assert keyword['execution']['mode']=='compiled' and keyword['operation']=='input'
            assert keyword['arguments']=={'value':area}
            assert keyword['target']=='位置/品牌/酒店 (选填)' and 'ai' not in keyword
        else:
            assert keyword['execution']['mode']=='interpreted'
            assert 'stale keyword' in keyword['arguments']['goal']
        assert keyword['on']['success']=='search'
        assert 'only' in steps['location']['desc'].lower()
        assert compile_source(source).valid

@pytest.mark.asyncio
async def test_ctrip_keyword_runs_once_in_public_compiled_executor_without_planner():
    from ai2apps.browser.background_executor import BackgroundExecutor
    source=query_source({'provider':'ctrip_hotels','trip':{**trip(),'hotel_area':'三元桥'}})
    step=next(s for s in compile_source(source).ir['steps'] if s['id']=='keyword')
    class Page:
        def __init__(self):self.value='';self.actions=[]
        async def snapshot(self):return {'url':'https://hotels.ctrip.com/','items':[{'name':'位置/品牌/酒店 (选填)','value':self.value}]}
        async def find_target(self,name,operation):
            assert name=='位置/品牌/酒店 (选填)' and operation=='input'
            return {'name':name,'tag':'input','type':'text'}
        async def pointer_to(self,target,**kwargs):self.actions.append('focus');return {}
        async def type_text(self,value,replace,submit):
            assert replace and not submit
            self.actions.append('input');self.value=value
        async def related_windows(self):return []
    page=Page();executor=BackgroundExecutor(None)
    result=await executor.compiled(page,step,source['site_scope'])
    assert result['outcome']=='success' and page.value=='三元桥'
    assert page.actions==['focus','input']


def test_travel_queries_enable_bounded_existing_visual_recovery_and_airport_constraints():
    value={**trip(),'origin':'北京','destination':'上海','destination_airport':'虹桥','excluded_airports':['浦东'],'preferences':'不要浦东机场'}
    source=query_source({'provider':'ctrip_flights','trip':value,'locale':'zh'})
    steps={s['name']:s for s in source['steps']}
    assert source['execution_policy']=={'visual_locating':True,'visual_review':'on_recovery','readback':True}
    assert 'route' not in steps and steps['trip_type']['on']['success']=='origin'
    assert steps['origin']['on']['success']=='destination'
    args=steps['destination']['arguments']
    assert args['destination_airport']=='虹桥' and args['excluded_airports']==['浦东']
    assert args['preferences']=='不要浦东机场' and args['assistance_label']=='选择到达城市或机场'
    from ai2apps.browser.travel import candidate_matches,airport_constraints
    parameters={'provider':'ctrip_flights','trip':value}
    assert not candidate_matches('东方航空 PEK–PVG 商务舱 ¥800',{},parameters)
    assert candidate_matches('东方航空 北京首都机场 → 上海虹桥机场 商务舱 ¥800',{},parameters)
    assert not candidate_matches('东方航空 商务舱 CNY 800',{},parameters)
    assert airport_constraints(value,'return')['origin_airport']=='虹桥'
    assert airport_constraints({**value,'excluded_airports':[]})['excluded_airports']==['浦东']


def test_summary_rechecks_current_airport_exclusions_without_mutating_saved_results():
    value={**trip(),'excluded_airports':['PVG']}
    saved={'provider':'ctrip_flights','leg':'outbound','items':[{'quote':'PEK–PVG 商务舱 ¥800','recommended':True},{'quote':'PEK–SHA 商务舱 ¥900','recommended':True}],'status':'complete'}
    task={'status':'completed','capability':'query','profile_key':'p','input':{'trip':trip(),'provider':'ctrip_flights'},'result':saved}
    summary=compose_summary({'trip':value,'source_tasks':['one']},'p',lambda _:task)
    assert [x['recommended'] for x in summary['observations'][0]['items']]==[False,True]
    assert all(x['recommended'] for x in saved['items'])

def test_ctrip_cabin_group_is_not_individual_business_fare_evidence():
    from ai2apps.browser.travel import candidate_matches
    parameters={'provider':'ctrip_flights','trip':{**trip(),'flight_cabin':'business'}}
    page={'controls':[{'label':'舱等','value':'公务/头等舱'}]}
    assert candidate_matches('航班 AB123 公务舱 ¥1200',page,parameters)
    assert not candidate_matches('航班 AB123 头等舱 ¥2400',page,parameters)
    assert not candidate_matches('航班 AB123 ¥800',page,parameters)


def test_ctrip_owner_explains_actual_passenger_and_counter_controls():
    flights=query_source({'provider':'ctrip_flights','trip':trip()})
    flight_party=next(s for s in flights['steps'] if s['name']=='party')['arguments']['goal']
    assert 'per-adult fare search' in flight_party and 'group label alone is NOT proof' in flight_party
    hotels=query_source({'provider':'ctrip_hotels','trip':trip()})
    hotel_party=next(s for s in hotels['steps'] if s['name']=='party')['arguments']['goal']
    assert 'middle number does NOT decrement' in hotel_party and 'visual review' in hotel_party
