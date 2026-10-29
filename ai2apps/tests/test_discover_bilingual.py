from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import json
import pytest
from ai2apps.packages.bilingual_search import keywords,search
from ai2apps.services import ToolCallContext,ToolProviderError
from ai2apps.identity import RequestPrincipal
from ai2apps.chat import ChatRepository
from test_app_interactions import runtime


def context():return ToolCallContext(caller_id='fixture',actor_user_id='local',installation_id='local',session_id='session-a',trace_id='run-a')

def item(status='unverified',version='1.0.0',identity='mini-a'):
    return {'package_id':'arbitrary/portrait','version':version,'kind':'mini-app','identity':identity,
        'installation_target':{'packageId':'arbitrary/portrait','version':version,'manifestSha256':'a'*64,'artifactSha256':'b'*64},
        'name':'Portrait','agent_support':'unverified','runtime_verified':False,
        'match':{'status':status,'reasons':[],'exclusions':[],'unknown':[]}}


def result(items,more=None):
    return {'candidates':[i for i in items if i['match']['status']!='excluded'],'excluded':[i for i in items if i['match']['status']=='excluded'],
        'outcome':'unverified_candidates','counts':{'unverified':2,'excluded':3},'next_cursor':more,'catalog_support':'capabilities-v1'}

@pytest.mark.asyncio
async def test_separate_queries_merge_exact_components_keep_sources_and_snapshot_pages(runtime,monkeypatch):
    calls=[];plans=[]
    async def plan(*args):plans.append(1);return ['数字人','虚拟人','digital avatar'],{'status':'expanded'}
    monkeypatch.setattr('ai2apps.packages.bilingual_search.keywords',plan)
    async def single(rt,args,ctx):
        calls.append(args)
        return result([item('excluded')]) if args['query']=='数字人' else result([item(),item(version='2.0.0'),item(identity='mini-b')])
    args={'query':'数字人','limit':1,'capability':'arbitrary.animate','include_history':True}
    page=await search(runtime,args,context(),single)
    assert [c['query'] for c in calls]==['数字人','虚拟人','digital avatar']
    assert all(c['capability']=='arbitrary.animate' and c['limit']==64 for c in calls)
    assert page['counts']=={'match':0,'unverified':3,'excluded':0}
    from ai2apps.packages.bilingual_search import detail
    candidate=detail(runtime,{'snapshot_id':page['snapshot_id'],'candidate_id':page['candidates'][0]['candidate_id']},context())['candidates'][0]
    assert candidate['matched_queries']==['虚拟人','digital avatar']
    assert len(candidate['source_matches'])==3 and candidate['source_matches'][0]['match']['status']=='excluded'
    assert candidate['agent_support']=='unverified' and not candidate['runtime_verified']
    assert page['counts_scope']=='observed_unique_cards'
    next_=await search(runtime,{**args,'cursor':page['next_cursor']},context(),single)
    assert next_['candidates'][0]['version']=='2.0.0' and len(calls)==3 and len(plans)==1
    # New facade, same persisted database; no model or network replay.
    final=await search(SimpleNamespace(database=runtime.database),{**args,'cursor':next_['next_cursor']},context(),single)
    assert final['candidates'][0]['identity']=='mini-b' and final['next_cursor'] is None
    for bad in ({**args,'query':'changed'},{**args,'capability':'different.capability'},{**args,'limit':2}):
        with pytest.raises(ToolProviderError):await search(runtime,{**bad,'cursor':page['next_cursor']},context(),single)
    with pytest.raises(ToolProviderError):await search(runtime,{**args,'cursor':page['next_cursor']},replace(context(),session_id='other'),single)
    with runtime.database.transaction() as db:db.execute('UPDATE discover_keyword_snapshots SET expires=0')
    with pytest.raises(ToolProviderError):await search(runtime,{**args,'cursor':page['next_cursor']},context(),single)

@pytest.mark.asyncio
async def test_partial_errors_and_incomplete_expansion_never_become_full_empty_conclusion(runtime,monkeypatch):
    async def plan(*a):return ['数字人','avatar'],{'status':'expanded'}
    monkeypatch.setattr('ai2apps.packages.bilingual_search.keywords',plan)
    async def single(rt,args,ctx):
        if args['query']=='avatar':raise RuntimeError('secret must not appear')
        return result([])
    page=await search(runtime,{'query':'数字人'},context(),single)
    assert page['outcome']=='partial' and page['aaat_context']['status']=='partial'
    assert 'secret' not in json.dumps(page) and page['sources'][1]['error']=='catalog_query_failed'
    async def failure(*a):return ['数字人'],{'status':'unavailable','reason':'keyword_expansion_failed'}
    monkeypatch.setattr('ai2apps.packages.bilingual_search.keywords',failure)
    assert (await search(runtime,{'query':'数字人'},context(),single))['outcome']=='partial'
    async def all_failed(*a):raise ValueError('offline')
    with pytest.raises(ToolProviderError,match='All catalog'):await search(runtime,{'query':'数字人'},context(),all_failed)

@pytest.mark.asyncio
async def test_digest_conflicts_are_not_silently_deduplicated(runtime,monkeypatch):
    async def plan(*a):return ['数字人','avatar'],{'status':'expanded'}
    monkeypatch.setattr('ai2apps.packages.bilingual_search.keywords',plan)
    async def single(rt,args,ctx):
        i=item()
        if args['query']=='avatar':i['installation_target']['artifactSha256']='c'*64
        return result([i])
    with pytest.raises(ToolProviderError,match='Conflicting'):await search(runtime,{'query':'数字人'},context(),single)

@pytest.mark.asyncio
async def test_keyword_model_uses_current_owned_model_bounded_bilingual_json(runtime,monkeypatch):
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Bilingual search')
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.general-agent',input={'model':'cloud/fixture/current','prompt':'private original task not needed for translation'})
    ctx=ToolCallContext.from_principal(RequestPrincipal.legacy_local(),caller_id='fixture',session_id=thread.session.id,trace_id=run.id)
    calls=[]
    async def invoke(payload,**kwargs):
        calls.append(payload);return {'choices':[{'message':{'content':json.dumps({'zh':['数字人','虚拟人'],'en':['digital avatar','talking portrait']})}}]}
    monkeypatch.setattr(runtime,'model_invocations',SimpleNamespace(context_for_actor=lambda *a,**kw:kw,invoke_agent_cloud_json=invoke))
    queries,meta=await keywords(runtime,'数字人',ctx)
    assert queries==['数字人','虚拟人','digital avatar','talking portrait'] and meta['model']=='cloud/fixture/current'
    assert len(calls)==1 and calls[0]['model']=='cloud/fixture/current'
    assert 'private original task' not in json.dumps(calls)
    async def invalid(*a,**kw):return {'choices':[{'message':{'content':'{"zh":["avatar"],"en":["avatar"]}'}}]}
    runtime.model_invocations.invoke_agent_cloud_json=invalid
    assert (await keywords(runtime,'数字人',ctx))[1]['status']=='unavailable'

@pytest.mark.asyncio
async def test_later_source_page_finds_signed_release_and_preserves_filters(runtime,monkeypatch):
    async def plan(*a):return ['原始','alternative'],{'status':'expanded'}
    monkeypatch.setattr('ai2apps.packages.bilingual_search.keywords',plan)
    calls=[]
    async def single(rt,args,ctx):
        calls.append(deepcopy(args))
        if not args.get('cursor'):return result([item('excluded',version='0.1.0')],more='source-page-2')
        v=item('match',version='0.2.0');v['agent_support']='declared'
        return result([v])
    args={'query':'原始','limit':1,'capability':'arbitrary.animate','input_type':'image','output_type':'video'}
    page=await search(runtime,args,context(),single)
    assert len(calls)==4 and [v.get('cursor') for v in calls]==[None,'source-page-2',None,'source-page-2']
    assert all(all(v[k]==args[k] for k in ('capability','input_type','output_type')) for v in calls)
    assert page['search_complete'] and not page['absence_established']
    assert page['candidates'][0]['version']=='0.2.0'
    assert page['candidates'][0]['agent_support']=='declared' and not page['candidates'][0]['runtime_verified']
    assert page['candidates'][0]['matched_queries']==['原始','alternative']
    assert all(s['pages_read']==2 and not s['truncated'] for s in page['sources'])

@pytest.mark.asyncio
@pytest.mark.parametrize('failure',['repeat','error','limit'])
async def test_incomplete_upstream_never_establishes_absence(runtime,monkeypatch,failure):
    async def plan(*a):return ['arbitrary'],{'status':'expanded'}
    monkeypatch.setattr('ai2apps.packages.bilingual_search.keywords',plan)
    monkeypatch.setattr('ai2apps.packages.bilingual_search.MAX_SOURCE_PAGES',3)
    calls=[]
    async def single(rt,args,ctx):
        calls.append(args)
        if len(calls)>1 and failure=='error':raise ValueError('private failure')
        return result([],more='same' if failure=='repeat' else 'page-'+str(len(calls)))
    page=await search(runtime,{'query':'arbitrary'},context(),single)
    assert page['outcome']=='partial' and not page['search_complete'] and not page['absence_established']
    assert page['aaat_context']['status']=='partial' and page['sources'][0]['truncated']
    assert page['sources'][0]['error']=={'repeat':'catalog_cursor_repeated','error':'catalog_query_failed','limit':'catalog_page_limit'}[failure]
    assert len(calls)<=3 and 'private failure' not in json.dumps(page)

@pytest.mark.asyncio
async def test_empty_fully_consumed_catalog_establishes_only_search_absence(runtime,monkeypatch):
    async def plan(*a):return ['arbitrary'],{'status':'expanded'}
    monkeypatch.setattr('ai2apps.packages.bilingual_search.keywords',plan)
    async def single(*a):return result([])
    page=await search(runtime,{'query':'arbitrary'},context(),single)
    assert page['search_complete'] and page['absence_established'] and page['outcome']=='no_candidates'

@pytest.mark.asyncio
async def test_later_page_failure_retains_already_observed_candidate(runtime,monkeypatch):
    async def plan(*a):return ['arbitrary'],{'status':'expanded'}
    monkeypatch.setattr('ai2apps.packages.bilingual_search.keywords',plan)
    async def single(rt,args,ctx):
        if args.get('cursor'):raise RuntimeError('offline')
        return result([item('match')],more='next')
    page=await search(runtime,{'query':'arbitrary'},context(),single)
    assert len(page['candidates'])==1 and page['outcome']=='partial' and not page['absence_established']
