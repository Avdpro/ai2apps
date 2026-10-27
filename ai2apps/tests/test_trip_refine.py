from copy import deepcopy
import pytest
from ai2apps.agent_builder.compiler import compile_source
from ai2apps.browser.travel import query_source, search_url, candidate_matches, project_result
from ai2apps.browser.travel_refine import compose, project, source
from ai2apps.tests.test_trip_planner import trip


def offer(i='a',price='$1,200',quote=None):
    return dict(id=i,title='Observed flight '+i,quote=quote or f'United Nonstop {price} round trip',
                details='Observed',price_text=price,price_basis='round trip',recommended=True)


def params():
    return dict(trip=trip(),request='Cheapest direct flight',locale='en',model_profile='normal',source_tasks=['t'])


def proposal(action='filter'):
    return dict(sort_by='price_asc',action=action,trip=trip(),sources=[],explanation='Loaded results only',questions=[],selection=[])


def observation():
    return dict(task_id='t',provider='google_flights',leg='outbound',trip=trip(),criteria_verified=True,
                items=[offer(),offer('b','$900')])


def test_refinement_is_model_only_and_compiles():
    s=source();assert compile_source(s).valid
    assert all(x['operation'] in ('ai.transform','assign') for x in s['steps'])
    assert 'observations' in s['inputs']['required']


def test_return_reverses_route_and_uses_return_date_without_paired_fare():
    s=query_source(dict(provider='google_flights',trip=trip(),leg='return'))
    assert compile_source(s).valid
    stages={x['name']:x for x in s['steps']}
    assert stages['origin']['arguments']['origin']=='Tokyo (NRT)'
    assert stages['origin']['arguments']['destination']=='SFO'
    assert stages['dates']['arguments']['departure']=='2027-06-05'
    assert stages['dates']['arguments']['return_date']==''
    assert stages['dates']['arguments']['one_way'] is True
    assert 'One way' in stages['party']['desc']
    url=search_url('expedia_flights',trip(),'return')
    assert 'oneway' in url and 'leg2' not in url
    with pytest.raises(ValueError):query_source(dict(provider='booking',trip=trip(),leg='return'))


def test_query_preferences_are_owned_and_apply_after_search():
    value={**trip(), 'flight_cabin':'business','nonstop_only':True}
    s=query_source(dict(provider='google_flights',trip=value))
    assert compile_source(s).valid
    names=[x['name'] for x in s['steps']]
    assert names.index('preferences')>names.index('search')
    assert next(x for x in s['steps'] if x['name']=='party')['arguments']['flight_cabin']=='business'
    assert not candidate_matches('United 1 stop',{'controls':['Business']},dict(provider='google_flights',trip=value))
    assert not candidate_matches('United Nonstop',{},dict(provider='google_flights',trip=value))
    assert candidate_matches('United Nonstop',{'controls':['Business']},dict(provider='google_flights',trip=value))
    assert not candidate_matches('Two twin beds',{},dict(provider='booking',trip={**trip(),'hotel_bed':'large_double'}))
    assert candidate_matches('1 king bed Subway Access',{},dict(provider='booking',trip={**trip(),'hotel_bed':'large_double','hotel_near_transit':True,'hotel_breakfast':'not_required'}))


def test_hotel_location_prepares_geography_before_owner_compiled_search():
    s=query_source(dict(provider='booking',trip={**trip(),'hotel_area':'颐和园'}))
    assert compile_source(s).valid
    stages={x['name']:x for x in s['steps']}
    assert stages['location']['on']['success']=='search'
    assert 'GEOGRAPHIC' in stages['location']['desc'] and 'Summer Palace' in stages['location']['desc']
    assert stages['search']['operation']=='click' and stages['search']['target']=='Search'
    assert stages['search']['execution']['mode']=='compiled'


def test_only_owned_same_profile_trip_queries_enter_refinement():
    task=dict(status='completed',capability='query',profile_key='p',input={'trip':trip()},result=observation())
    result=compose(params(),'p',lambda _:task)
    assert result['observations'][0]['task_id']=='t'
    for change in ({'status':'waiting_input'},{'capability':'refine'},{'profile_key':'foreign'},
                   {'input':{'trip':{**trip(),'return_date':'2027-06-06','nights':5}}}):
        with pytest.raises(ValueError):compose(params(),'p',lambda _:{**task,**change})
    def denied(_):raise PermissionError('foreign task')
    with pytest.raises(PermissionError):compose(params(),'p',denied)


def test_cached_selection_binds_actual_ids_evidence_and_sorts_prices():
    p={**params(),'observations':[observation()]};out=proposal()
    out['selection']=[dict(task_id='t',item_id=i['id'],evidence=i['quote'],reason='Observed fare') for i in p['observations'][0]['items']]
    out['selection'].append(dict(task_id='t',item_id='fake',evidence='Fake low price',reason='Injected'))
    result=project({'assigned':{'refinement':out}},p)
    assert [x['item_id'] for x in result['selection']]==['b','a']
    assert result['selection'][0]['item']==p['observations'][0]['items'][1]
    out['selection'][0]['evidence']='United Nonstop $1 round trip'
    assert [x['item_id'] for x in project({'assigned':{'refinement':out}},p)['selection']]==['b']


def test_cached_filter_cannot_change_dates_or_upgrade_missing_evidence():
    p={**params(),'observations':[observation()]};out=proposal()
    out['trip'].update(return_date='2027-06-06',nights=5)
    with pytest.raises(ValueError):project({'assigned':{'refinement':out}},p)
    out=proposal();out['trip']['flight_cabin']='business';item=p['observations'][0]['items'][0]
    out['selection']=[dict(task_id='t',item_id=item['id'],evidence=item['quote'],reason='business')]
    assert project({'assigned':{'refinement':out}},p)['selection']==[]


def test_requery_requires_affected_sources_and_no_fabricated_selection():
    p={**params(),'observations':[observation()]};out=proposal('requery')
    with pytest.raises(ValueError):project({'assigned':{'refinement':out}},p)
    out['sources']=['booking'];out['trip']['hotel_checkout']='2027-06-06'
    result=project({'assigned':{'refinement':out}},p)
    assert result['selection']==[] and result['trip']['hotel_checkout']=='2027-06-06'


def test_followup_clarification_is_owner_scoped():
    task=dict(status='completed',capability='query',profile_key='p',input={'trip':trip()},result=observation())
    previous=dict(status='completed',capability='refine',profile_key='p',input={'trip':trip()},result={'action':'clarify','questions':['Mainland only?']})
    p={**params(),'previous_refinement':'previous'}
    assert compose(p,'p',lambda k:previous if k=='previous' else task)['previous']['questions']==['Mainland only?']
    previous['profile_key']='foreign'
    with pytest.raises(ValueError):compose(p,'p',lambda k:previous if k=='previous' else task)


def test_independent_source_identity_keeps_unaffected_results_valid():
    from ai2apps.browser.travel import research_identity
    value={**trip(),'hotel_checkout':'2027-06-06'}
    assert research_identity(value,'google_flights')==research_identity(trip(),'google_flights')
    assert research_identity(value,'booking')!=research_identity(trip(),'booking')
    moved={**trip(),'return_date':'2027-06-06','nights':5}
    assert research_identity(moved,'booking')==research_identity(trip(),'booking')
    assert research_identity(moved,'google_flights')!=research_identity(trip(),'google_flights')
