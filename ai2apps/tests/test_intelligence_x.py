import pytest
from ai2apps.intelligence.models import SourceInput
from ai2apps.intelligence.social import x_targets
from ai2apps.intelligence.collector import IntelligenceCollector
from ai2apps.agent_builder.compiler import compile_source
from ai2apps.browser.background_page import BackgroundPage


def test_x_accounts_normalize_and_deduplicate():
    values,urls=x_targets('accounts',['@Formula1','https://x.com/F1','@formula1'])
    assert values==['formula1','f1']
    assert urls==['https://x.com/formula1','https://x.com/f1']
    source=SourceInput(name='F1',url='https://x.com/',x_mode='accounts',x_values=['@F1','@Formula1'])
    assert source.kind=='social' and source.url=='https://x.com/f1'
    assert compile_source(IntelligenceCollector.program(source.model_dump(),'read_page',{'url':source.url,'x':'feed'})).valid


def test_x_search_queries_stay_independent_and_latest():
    values,urls=x_targets('search',['F1 qualifying','"watch launch" lang:en'])
    assert len(urls)==2 and all('f=live' in u for u in urls)
    assert 'q=F1+qualifying' in urls[0]
    for values in [[],['a']*21,['https://evil.example/F1'],['@home'],['bad/name']]:
        with pytest.raises(ValueError):x_targets('accounts',values)


@pytest.mark.asyncio
async def test_x_feed_merges_scrolled_posts_and_detail_matches_id(monkeypatch):
    page=BackgroundPage(None,'tab');page.handle_access=lambda:access()
    async def access():return {'classification':'ready'}
    calls=[]
    first={'url':'https://x.com/a/status/1','post_id':'1','title':'One','text':'one','author':'A','published_at':'now','images':[]}
    second={**first,'url':'https://x.com/b/status/2','post_id':'2','text':'two'}
    async def snapshot(*a):calls.append(1);return {'items':[first] if len(calls)==1 else [first,second]}
    page.call_json=snapshot
    async def scroll(*a):pass
    page.scroll=scroll
    async def sleep(*a):pass
    monkeypatch.setattr('ai2apps.browser.background_page.asyncio.sleep',sleep)
    result=await page.x_page({'url':'https://x.com/a','x':'feed'})
    assert [p['post_id'] for p in result['items']]==['1','2']
    result=await page.x_page({'url':'https://x.com/b/status/2','x':'detail'})
    assert result['post_id']=='2' and result['text'].endswith('two')


@pytest.mark.asyncio
async def test_x_reader_keeps_post_photos_and_feed_succeeds():
    page=BackgroundPage(None,'tab')
    async def navigate(*a):pass
    async def snapshot(*a):return {'url':'https://x.com/f1'}
    async def access():return {'classification':'ready'}
    async def posts(*a):return {'text':'F1 news','items':[{'post_id':'1'}],
        'images':[{'url':'https://pbs.twimg.com/media/f1.jpg'}],
        'cover_image':{'url':'https://pbs.twimg.com/media/f1.jpg'}}
    async def helper(*a):raise AssertionError('Generic webpage images must not replace X photos')
    page.navigate=navigate;page.snapshot=snapshot;page.handle_access=access;page.x_page=posts;page.helper=helper
    result=await page.read_page({'url':'https://x.com/f1','x':'feed','new_tab':False,
        'include_cover':True,'include_images':True})
    assert result['outcome']=='success' and result['cover_image']['url'].endswith('/f1.jpg')


def test_x_lists_canonicalize_share_links_and_preserve_order():
    values,urls=x_targets('lists',['https://x.com/i/lists/123?s=20',
        'https://twitter.com/i/lists/456/', 'https://www.x.com/i/lists/123#share'])
    assert values==urls==['https://x.com/i/lists/123','https://x.com/i/lists/456']
    source=SourceInput(name='F1 Lists',url='https://x.com/',x_mode='lists',x_values=values)
    assert source.kind=='social' and source.x_mode=='lists' and source.url==urls[0]
    assert compile_source(IntelligenceCollector.program(source.model_dump(),'read_page',{'url':source.url,'x':'feed'})).valid


@pytest.mark.parametrize('url',['https://evil.example/i/lists/123','https://x.com/Formula1',
    'https://x.com/i/lists/no-id','https://x.com/i/lists/123/members',
    'https://user:password@x.com/i/lists/123','https://x.com:8888/i/lists/123',
    'javascript:alert(1)','https://x.com/i/lists/','https://x.com/i/lists/123456789012345678901'])
def test_x_lists_reject_invalid_targets(url):
    with pytest.raises(ValueError):x_targets('lists',[url])


@pytest.mark.asyncio
async def test_x_missing_detail_is_known_failure_without_scrolling(monkeypatch):
    page=BackgroundPage(None,'tab')
    async def snapshot(*a):return {'url':'https://x.com/F1/status/1'}
    async def navigate(*a):pass
    async def access():return {'classification':'ready'}
    calls=[]
    async def posts(*a):calls.append(1);return {'items':[]}
    async def scroll(*a):raise AssertionError('Do not scroll the requested post away while it loads')
    async def sleep(*a):pass
    page.navigate=navigate;page.snapshot=snapshot;page.handle_access=access;page.call_json=posts;page.scroll=scroll
    monkeypatch.setattr('ai2apps.browser.background_page.asyncio.sleep',sleep)
    result=await page.read_page({'url':'https://x.com/F1/status/1','x':'detail','new_tab':False})
    assert result['outcome']=='failed' and result['reason']=='x_post_body_not_visible'
    assert len(calls)==3


def test_browser_waiting_run_can_pause_without_resolving_pending_action(tmp_path):
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.config import PlatformConfig
    from ai2apps.chat import ChatRepository
    from ai2apps.agents import AgentRunStatus, InteractionKind
    runtime=PlatformRuntime(PlatformConfig.from_base_path(tmp_path));runtime.start()
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Pause waiting browser')
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.diagnostic-agent',input={'mode':'text'})
    runtime.agents.claim_next()
    runtime.agents.transition(run.id,expected={AgentRunStatus.PLANNING},status=AgentRunStatus.RUNNING)
    interaction=runtime.agents.create_interaction(run.id,request_key='browser-action',kind=InteractionKind.TEXT,
        prompt='Read post',response_schema={'type':'object'})
    paused=runtime.agents.request_pause(run.id)
    assert paused.status==AgentRunStatus.INTERRUPTED
    assert runtime.agents.list_interactions(run.id)[0].id==interaction.id
    assert runtime.agents.list_interactions(run.id)[0].status.value=='pending'

@pytest.mark.asyncio
async def test_x_feed_discovers_past_three_snapshots_and_tolerates_loading_gaps(monkeypatch):
    page=BackgroundPage(None,'tab');calls=[];scrolls=[]
    async def access():return {'classification':'ready'}
    async def snapshot(*args):
        calls.append(1)
        i=1 if len(calls) in (2,3) else len(calls)
        return {'items':[dict(post_id=str(i),url=f'https://x.com/F1/status/{i}',title='News')]}
    async def scroll(*args):scrolls.append(1)
    async def sleep(*args):pass
    page.handle_access=access;page.call_json=snapshot;page.scroll=scroll
    monkeypatch.setattr('ai2apps.browser.background_page.asyncio.sleep',sleep)
    result=await page.x_page({'url':'https://x.com/F1','x':'feed'})
    assert len(calls)==20 and len(scrolls)==19
    assert result['items'][-1]['post_id']=='20'


def test_x_search_sort_options():
    from urllib.parse import urlsplit, parse_qs
    from ai2apps.intelligence.models import SourceInput
    default=SourceInput(name='F1',url='https://x.com/',x_mode='search',x_values=['F1'])
    assert default.x_sort=='latest' and parse_qs(urlsplit(default.url).query)['f']==['live']
    top=SourceInput(**{**default.model_dump(),'x_sort':'top'})
    assert 'f' not in parse_qs(urlsplit(top.url).query)
    _,urls=x_targets('search',['F1','watches'], 'top')
    assert len(urls)==2 and all('f=' not in url for url in urls)
    with pytest.raises(ValueError):SourceInput(**{**default.model_dump(),'x_sort':'random'})
