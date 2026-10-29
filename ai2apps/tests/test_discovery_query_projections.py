"""Cloud1.80 contract integration; arbitrary identities, no install authorization."""
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from ai2apps.packages.capability_catalog import FEATURE,content,validate_page
from ai2apps.packages.registry import RegistryError
from ai2apps.packages.aaat import _search_single,taxonomy
from ai2apps.packages.bilingual_search import search,detail_current
from ai2apps.agents.run_metrics import observed_metrics
from test_capability_catalog_client import card,TARGET
from test_discovery_efficiency import model_step
from test_discover_bilingual import context
from test_app_interactions import runtime


def page(projection='summary'):
    c=card('match');c.update(tags=['agent.aaat'],lifecycle={'state':'active','revision':1},
        advisory={'excludeFromAutoRecommendation':False,'revision':1,'maturity':'stable','warning':'none'})
    c['release']['detailsUrl']='/v1/registry/content?query_contract=projections-v1'
    c['match']['unknown']=[]
    if projection=='summary':
        from ai2apps.packages.capability_catalog import validator
        keys=validator('capability-query-v1.schema.json').schema['$defs']['summary']['properties']
        c={k:v for k,v in c.items() if k in keys};c['match']={'status':'match'}
    return {'schemaVersion':'ai2apps.capability-query.v1','catalogSnapshot':'c'*64,
        'matching':'normalized-keyword-and-exact-filters','outcome':'matches',
        'projection':projection,'releasePolicy':'latest_compatible' if projection=='summary' else 'all',
        'taxonomyVersion':'2026-10-29.1','counts':{'match':1,'unverified':4,'excluded':3},
        'candidateCounts':{'match':2,'unverified':4,'excluded':3},'exclusionCounts':{'INCOMPATIBLE':3},
        'items':[c],'nextCursor':None}


def manager(calls,query=None):
    async def discovery():return {'capabilityCatalog':{**FEATURE,'queryProjections':{'value':'projections-v1'}}}
    async def catalog(**args):
        calls.append(args)
        return await query(args) if query else page(args.get('projection','detail'))
    return NS(discovery_capabilities=discovery,content_catalog=catalog)


@pytest.mark.asyncio
async def test_summary_negotiates_only_when_advertised_and_legacy_fallback():
    calls=[];m=manager(calls)
    p=await content(m,projection='summary',q='fixture',tags='agent.aaat',tag_operator='or',match_status='match')
    assert p['schemaVersion']=='ai2apps.capability-query.v1'
    assert calls[-1]['query_contract']=='projections-v1' and 'sort' not in calls[-1]
    assert calls[-1]['release_policy']=='latest_compatible' and calls[-1]['tag_operator']=='or'
    async def old():return {'capabilityCatalog':FEATURE}
    m.discovery_capabilities=old
    from test_capability_catalog_client import page as legacy_page
    async def catalog(**args):calls.append(args);return legacy_page()
    m.content_catalog=catalog
    await content(m,projection='summary',release_policy='latest_compatible',q='fixture')
    assert 'query_contract' not in calls[-1] and 'projection' not in calls[-1]
    with pytest.raises(ValueError,match='silently ignored'):
        await content(m,projection='summary',tags='agent.aaat')


@pytest.mark.asyncio
async def test_summary_then_fresh_exact_detail_never_inherits_search_filters(runtime,monkeypatch):
    calls=[];m=manager(calls);monkeypatch.setattr(runtime,'registry_packages',m)
    args={'capability':'fixture.render','tags':['agent.aaat'],'tag_operator':'and'}
    result=await search(runtime,args,context(),_search_single)
    assert result['catalog_support']=='projections-v1' and result['sources'][0]['counts']['unverified']==4
    assert result['sources'][0]['exclusion_counts']=={'INCOMPATIBLE':3}
    candidate=result['candidates'][0]
    assert 'installation_target' not in candidate and 'provides' not in candidate
    assert candidate['tags']==['agent.aaat']
    selected={'snapshot_id':result['snapshot_id'],'candidate_id':candidate['candidate_id']}
    fresh=await detail_current(runtime,selected,context())
    assert fresh['detail_refreshed'] and fresh['candidates'][0]['installation_target']==TARGET
    assert calls[-1]=={'projection':'detail','package_id':TARGET['packageId'],'version':TARGET['version'],
        'card_key':card()['cardKey'],'artifact_sha256':TARGET['artifactSha256'],
        'manifest_sha256':TARGET['manifestSha256'],'query_contract':'projections-v1','discovery':'capabilities-v1'}
    # Detail withdrawal/conflict is never converted into a different release.
    for code in ('package_withdrawn','capability_release_unavailable','content_release_changed'):
        async def denied(**kw):raise RegistryError(code,'release refused')
        m.content_catalog=denied
        with pytest.raises(RegistryError):await detail_current(runtime,selected,context())


@pytest.mark.asyncio
async def test_history_status_filters_and_cloud_cursor_failure_do_not_mix_snapshots(runtime,monkeypatch):
    calls=[];m=manager(calls);monkeypatch.setattr(runtime,'registry_packages',m)
    with pytest.raises(Exception,match='requires at least one'):
        await _search_single(runtime,{'query':'fixture','tag_operator':'or'},None)
    await _search_single(runtime,{'query':'fixture','include_history':True,'match_status':'excluded'},None)
    assert calls[-1]['release_policy']=='all' and calls[-1]['match_status']=='excluded'
    n=0
    async def changed(rt,args,ctx):
        nonlocal n
        n+=1
        p={'query':'','candidates':[],'excluded':[],'counts':{},'outcome':'matches',
            'catalog_support':'projections-v1','next_cursor':'next' if n==1 else None,
            'catalog_snapshot':('a' if n==1 else 'b')*64}
        return p
    with pytest.raises(Exception,match='snapshot changed'):
        await search(runtime,{'capability':'fixture.render'},context(),changed)
    async def expired(rt,args,ctx):raise RegistryError('catalog_cursor_expired','expired')
    with pytest.raises(Exception,match='discard pagination'):
        await search(runtime,{'capability':'fixture.render'},context(),expired)


def test_projection_validation_rejects_binding_and_wrong_shape():
    from ai2apps.packages.bilingual_search import project_page
    p={'candidates':[],'excluded':[],'queries':['x'],'keyword_expansion':{'status':'expanded'},
       'sources':[{'candidate_counts':{'match':0,'unverified':2,'excluded':1}}],
       'catalog_support':'projections-v1'}
    assert project_page(p,'x',5,0,'snapshot')['absence_established'] is False
    assert validate_page(page())['projection']=='summary'
    invalid=page();invalid['items'][0]['release']['artifactSha256']='d'*64
    with pytest.raises(ValueError,match='binding'):validate_page(invalid)
    invalid=page();invalid['items'][0]['permissions']=[]
    with pytest.raises(Exception):validate_page(invalid)


def test_usage_reported_zero_unreported_and_historic_unknown_are_distinct():
    cloud={'requestId':'id','points':{'charged':'1'}}
    def row(flag,source):
        usage={'prompt_tokens':100,'completion_tokens':2,'prompt_tokens_details':{'cached_tokens':0}}
        if source is not None:usage.update(cacheUsageReported=flag,cacheUsageSource=source)
        return observed_metrics([model_step(1,usage,cloud)])
    reported=row(True,'upstream-reported');missing=row(False,'upstream-not-reported');historic=row(None,None)
    assert reported['cached_input_tokens']==0 and reported['cache_reported_calls']==1
    assert missing['cached_input_tokens'] is None and missing['cache_not_reported_calls']==1
    assert historic['cached_input_tokens'] is None and historic['cache_unknown_calls']==1
    from ai2apps.cloud_gateway import _openai_usage
    normalized=_openai_usage({'inputTokens':100,'outputTokens':2,'cachedInputTokens':0,
        'cacheUsageReported':False,'cacheUsageSource':'upstream-not-reported','providerCurrencyCost':None})
    assert normalized['cacheUsageReported'] is False and normalized['providerCurrencyCost'] is None
