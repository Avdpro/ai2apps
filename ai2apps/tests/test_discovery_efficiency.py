from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace as NS
import json
import pytest
from ai2apps.packages.bilingual_search import search,detail
from ai2apps.packages.discovery_projection import latest
from ai2apps.agents.run_metrics import observed_metrics
from ai2apps.services import ToolProviderError
from test_app_interactions import runtime
from test_discover_bilingual import context,item,result

@pytest.mark.asyncio
async def test_summary_default_latest_detail_is_owned_and_preserves_exact_install_binding(runtime,monkeypatch):
    async def plan(*a):return ['arbitrary'],{'status':'expanded'}
    monkeypatch.setattr('ai2apps.packages.bilingual_search.keywords',plan)
    cards=[item('match',version='1.0.0'),item('match',version='2.0.0')]+[item('excluded',identity='excluded-'+str(i)) for i in range(60)]
    calls=[]
    async def single(rt,args,ctx):calls.append(args);return result(deepcopy(cards))
    page=await search(runtime,{'query':'arbitrary','studio':'arbitrary.host','mini_app_category':'audio','input_type':'audio/wav'},context(),single)
    assert len(page['candidates'])==1 and page['candidates'][0]['version']=='2.0.0'
    assert page['candidates'][0]['history_count']==1 and page['excluded']==[]
    assert 'installation_target' not in page['candidates'][0] and 'source_matches' not in page['candidates'][0]
    assert len(json.dumps(page))<4000
    assert calls[0]['studio']=='arbitrary.host' and calls[0]['mini_app_category']=='audio'
    args={'snapshot_id':page['snapshot_id'],'candidate_id':page['candidates'][0]['candidate_id']}
    card=detail(runtime,args,context())['candidates'][0]
    assert card['installation_target']==cards[1]['installation_target'] and len(calls)==1
    with pytest.raises(ToolProviderError):detail(runtime,args,replace(context(),session_id='foreign'))
    with pytest.raises(ToolProviderError):detail(runtime,{**args,'candidate_id':'invented'},context())
    with runtime.database.transaction() as db:db.execute('UPDATE discover_keyword_snapshots SET expires=0')
    with pytest.raises(ToolProviderError):detail(runtime,args,context())

def test_latest_compatible_prefers_known_match_and_does_not_select_excluded_release():
    assert latest([item('match',version='1.0.0'),item('unverified',version='2.0.0')])[0]['version']=='1.0.0'

def model_step(i,usage,cloud=None):
    now=datetime.now(timezone.utc)
    return NS(id=str(i),kind='model',output={'usage':usage,'ai2apps_cloud':cloud},started_at=now,finished_at=now+timedelta(seconds=2))

def test_cache_unknown_stays_unknown_and_settled_points_deduplicate_request():
    steps=[model_step(1,{'prompt_tokens':100,'completion_tokens':5,'prompt_tokens_details':{'cached_tokens':80},'cacheUsageReported':True,'cacheUsageSource':'upstream-reported'}, {'requestId':'same','points':{'charged':'2'}}),
           model_step(2,{'prompt_tokens':100,'completion_tokens':5}, {'requestId':'same','points':{'charged':'2'}})]
    m=observed_metrics(steps)
    assert m['input_tokens']==200 and m['cached_input_tokens'] is None and m['cache_reported_calls']==1
    assert m['charged_points']=='2' and m['settled_requests']==1
    assert m['rows'][0]['uncached_input_tokens']==20 and m['rows'][0]['elapsed_seconds']==2
    assert observed_metrics([model_step(3,{'prompt_tokens':100,'completion_tokens':5})])['charged_points'] is None

def test_gateway_preserves_observed_cache_but_does_not_invent_missing_cache():
    from ai2apps.cloud_gateway import _openai_usage
    assert _openai_usage({'inputTokens':100,'cachedInputTokens':75,'outputTokens':5})['prompt_tokens_details']=={'cached_tokens':75}
    assert 'prompt_tokens_details' not in _openai_usage({'inputTokens':100,'outputTokens':5})

@pytest.mark.asyncio
async def test_inventory_is_bounded_and_selected_schema_still_available(runtime):
    from ai2apps.services import ToolCallContext
    provider=runtime.service_registry.bound_tool('app.describe')
    inventory=await provider.handler({'query':'discover','limit':2},context())
    assert inventory['projection']=='summary' and len(inventory['providers'])<=2
    assert all('schema' not in v and 'agent_context' not in v for v in inventory['providers'])
    full=await provider.handler({'capability':'discover.packages'},context())
    assert full['forms'] and 'schema' in full['forms'][0]

def test_duplicate_reads_reference_unchanged_source_and_explicit_reread_works():
    from ai2apps.agents.result_reference import install_result_reader,RESULT_READER
    from ai2apps.agents.models import RunStepStatus
    source=NS(id='source',kind='tool',tool_name='arbitrary.read',status=RunStepStatus.COMPLETED,output={'body':'x'*20000})
    steps=[source];handlers={}
    agents=NS(get_run=lambda _:NS(id='run-a',session_id='session-a'),list_steps=lambda _:steps)
    registry=NS(bind_tool=lambda name,**kw:handlers.update({name:kw['handler']}))
    install_result_reader(agents,NS(ensure_tool=lambda **kw:None),registry,service_id='s',provider_key='p')
    args={'step_id':'source','offset':10,'limit':100}
    first=handlers[RESULT_READER](args,context())
    steps.append(NS(id='first',kind='tool',tool_name=RESULT_READER,status=RunStepStatus.COMPLETED,output=first))
    repeat=handlers[RESULT_READER](args,context())
    assert repeat['already_read'] and repeat['previous_read_step_id']=='first' and 'content' not in repeat
    assert handlers[RESULT_READER]({**args,'reread':True},context())['content']==first['content']
    assert source.output=={'body':'x'*20000} and steps[1].output==first
    with pytest.raises(ToolProviderError):handlers[RESULT_READER](args,replace(context(),session_id='foreign'))

@pytest.mark.asyncio
async def test_exact_filters_do_not_require_keyword_translation(runtime,monkeypatch):
    async def forbidden(*a):raise AssertionError('No keyword model needed')
    monkeypatch.setattr('ai2apps.packages.bilingual_search.keywords',forbidden)
    calls=[]
    async def single(rt,args,ctx):calls.append(args);return result([item('match')])
    page=await search(runtime,{'capability':'arbitrary.animate','studio':'arbitrary.host'},context(),single)
    assert page['search_complete'] and page['keyword_expansion']['model_called'] is False
    assert calls[0]['capability']=='arbitrary.animate' and calls[0]['query']==''


@pytest.mark.asyncio
async def test_empty_and_phrase_search_retries_observed_words_without_domain_rules(runtime,monkeypatch):
    async def plan(*a):return ['orbital renderer','轨道渲染','orbital renderer'],{'status':'expanded'}
    monkeypatch.setattr('ai2apps.packages.bilingual_search.keywords',plan)
    calls=[]
    async def single(rt,args,ctx):
        calls.append(args['query'])
        return result([item('match')]) if args['query']=='renderer' else result([])
    page=await search(runtime,{'query':'orbital renderer'},context(),single)
    assert page['candidates'] and page['keyword_expansion']['deterministic_word_fallback']
    assert 'renderer' in calls and len(calls)<=11
