import asyncio
import pytest
from ai2apps.browser.processing_pool import ordered_pool,InputLock

@pytest.mark.asyncio
async def test_pool_is_bounded_and_preserves_order():
    active=0;peak=0
    async def work(i):
        nonlocal active,peak
        active+=1;peak=max(peak,active)
        await asyncio.sleep((5-i)*.001);active-=1;return i
    assert await ordered_pool(range(6),work,3)==list(range(6))
    assert peak==3

@pytest.mark.asyncio
async def test_profile_input_is_serial_and_nested_calls_do_not_deadlock():
    lock=InputLock();active=0;peak=0
    async def work(i):
        nonlocal active,peak
        async with lock:
            active+=1;peak=max(peak,active)
            async with lock:await asyncio.sleep(.001)
            active-=1
    await ordered_pool(range(6),work,3)
    assert peak==1

@pytest.mark.asyncio
async def test_news_scan_stops_when_links_do_not_grow(monkeypatch):
    from ai2apps.browser.background_page import BackgroundPage
    import ai2apps.browser.background_page as module
    page = object.__new__(BackgroundPage)
    calls = []
    async def snapshot():return {'url':'https://example.com/news'}
    async def extract(step):
        calls.append(dict(step['arguments']))
        return {'items':[{'url':'https://example.com/article/one'}], 'observed_regions':[{'id':'news'}]}
    async def call_json(*args):return {'y':0,'height':800,'total':10000,'more':None,'next':''}
    async def noop(*args,**kwargs):pass
    page.snapshot=snapshot;page.extract_list=extract;page.call_json=call_json;page.scroll=noop
    monkeypatch.setattr(module.asyncio,'sleep',noop)
    result=await page.extract_news_list({'arguments':{'news_scan':True,'observe_regions':True,'limit':40}})
    assert result['discovery']['rounds']==3
    assert result['discovery']['stop_reason']=='no_new_links'
    assert len(result['items'])==1
    assert calls[0]['observe_regions'] is True
    assert all(not c['observe_regions'] for c in calls[1:])

@pytest.mark.asyncio
async def test_preload_releases_input_lock_before_readiness(monkeypatch):
    from ai2apps.browser.background_page import BackgroundPage
    from types import SimpleNamespace
    import ai2apps.browser.background_page as module
    events=[]
    async def sleep(_):pass
    monkeypatch.setattr(module.asyncio,'sleep',sleep)
    async def command(method,args,**kw):events.append(args['url']);return {}
    page=BackgroundPage(SimpleNamespace(command=command),'tab',interaction_mode=lambda _:'natural')
    page.input_lock=InputLock()
    async def stable(**kw):raise AssertionError('Preload must not wait for readiness')
    page.wait_stable=stable
    result=await page.preload('https://example.com/article')
    assert result['preloaded'] and events==['https://example.com/article']
    assert page.prefetched_url=='https://example.com/article'
    assert not page.input_lock.lock.locked()

@pytest.mark.asyncio
async def test_preloaded_article_waits_for_readiness_without_reopening():
    from ai2apps.browser.background_page import BackgroundPage
    from types import SimpleNamespace
    page=BackgroundPage(SimpleNamespace(),'tab')
    page.prefetched_url='https://example.com/article'
    checks=[]
    async def stable(**kw):checks.append(kw);return {'stable':True}
    async def snapshot(*args):return {'url':'https://example.com/article'}
    async def access(**kwargs):return {'classification':'needs_user','reason':'cookie_consent'}
    async def navigate(*args,**kw):raise AssertionError('Must not reload preloaded article')
    async def observed(*args,**kwargs):return {'paragraphs':[], 'notice':''}
    page.call_json=observed
    page.wait_stable=stable;page.snapshot=snapshot;page.handle_access=access;page.navigate=navigate
    result=await page.read_page({'url':page.prefetched_url,'new_tab':False})
    assert checks==[{'require_content':True}]
    assert result['reason']=='cookie_consent'
    assert page.prefetched_url is None
