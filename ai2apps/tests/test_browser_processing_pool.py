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
