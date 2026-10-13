import asyncio
import pytest
from ai2apps.browser.background_page import BackgroundPage

@pytest.mark.asyncio
async def test_xhs_reads_body_metrics_and_restores_search(monkeypatch):
    commands=[]
    class Connection:
        async def command(self, method, params): commands.append((method,params))
    page=BackgroundPage(Connection(),'owned')
    async def snapshot(): return {'url':'https://www.xiaohongshu.com/search_result?keyword=watch'}
    async def call(source,args):
        if '.close-circle' in source:return None
        if 'scrollIntoView' in source:return {'rect':{}}
        return {'ready':True,'content':'Observed full note body','like_count':'40','collect_count':'15','comment_count':'3'}
    clicks=[]
    async def click(target):clicks.append(target)
    async def mode():return 'natural'
    async def pause(_):pass
    async def sleep(_):pass
    page.snapshot=snapshot;page.call_json=call;page.pointer_to=click;page.mode=mode;page.pause=pause
    monkeypatch.setattr(asyncio,'sleep',sleep)
    result={'items':[{'title':'Title','content':'Title','url':'https://www.xiaohongshu.com/search_result/abc?xsec_token=observed'}]}
    await page.enrich_xhs_notes(result)
    assert result['items'][0]['content']=='Observed full note body'
    assert result['items'][0]['collect_count']=='15'
    assert result['items'][0]['content_status']=='detail_read'
    assert len(clicks)==1
    assert commands[0][0]=='browsingContext.traverseHistory'
    assert commands[0][1]['delta']==-1

@pytest.mark.asyncio
async def test_xhs_verification_stops_without_dismissing(monkeypatch):
    page=BackgroundPage(None,'owned')
    async def snapshot():return {'url':'https://www.xiaohongshu.com/search_result?keyword=watch'}
    async def call(source,args):return {'rect':{}} if 'scrollIntoView' in source else {'ready':False}
    async def click(_):pass
    async def access(*_):return {'classification':'needs_user','reason':'captcha','assistance_kind':'captcha'}
    async def sleep(_):pass
    page.snapshot=snapshot;page.call_json=call;page.pointer_to=click;page.helper=access
    monkeypatch.setattr(asyncio,'sleep',sleep)
    result={'items':[{'url':'https://www.xiaohongshu.com/search_result/abc'}]}
    await page.enrich_xhs_notes(result)
    assert result['classification']=='needs_user'
    assert result['reason']=='captcha'

@pytest.mark.asyncio
async def test_xhs_native_back_reads_next_note(monkeypatch):
    class Connection:
        async def command(self, method, params):
            nonlocal current
            assert method=='browsingContext.traverseHistory'
            current=original
    page=BackgroundPage(Connection(),'owned')
    original='https://www.xiaohongshu.com/search_result?keyword=watch'
    current=original
    async def snapshot():return {'url':current}
    async def call(source,args):
        if '.close-circle' in source:return {'close':True,'rect':{}}
        if 'scrollIntoView' in source:return {'close':False,'rect':{}}
        return {'ready':True,'content':'Full body'}
    async def click(target):
        nonlocal current
        current=original if target['close'] else 'https://www.xiaohongshu.com/explore/abc'
    async def sleep(_):pass
    async def mode():return 'natural'
    page.snapshot=snapshot;page.call_json=call;page.pointer_to=click;page.mode=mode;page.pause=sleep
    monkeypatch.setattr(asyncio,'sleep',sleep)
    updates=[]
    async def progress(value):
        import copy
        updates.append(copy.deepcopy(value))
    page.search_progress=progress
    result={'items':[{'url':'https://www.xiaohongshu.com/search_result/abc'},{'url':'https://www.xiaohongshu.com/search_result/def'}]}
    await page.enrich_xhs_notes(result)
    assert [i['content_status'] for i in result['items']]==['detail_read','detail_read']
    assert current==original

    assert [sum(item['content_status']=='detail_read' for item in update['items']) for update in updates]==[0,1,2]

@pytest.mark.asyncio
async def test_cover_copies_only_bounded_observed_pixels():
    calls=[]
    class Connection:
        async def command(self, method, params, **kwargs):
            calls.append((method,params))
            return {'data':'/9j/AAAA'}
    page=BackgroundPage(Connection(),'owned')
    rect={'x':10,'y':20,'width':160,'height':200}
    assert (await page.xhs_cover(rect,400000)).startswith('data:image/jpeg;base64,')
    assert calls[0][0]=='browsingContext.captureScreenshot'
    assert calls[0][1]['context']=='owned'
    assert calls[0][1]['clip']=={'type':'box',**rect}
    assert await page.xhs_cover(rect,10) is None
    count=len(calls)
    assert await page.xhs_cover({**rect,'x':float('inf')},400000) is None
    assert await page.xhs_cover({**rect,'width':2000},400000) is None
    assert len(calls)==count

@pytest.mark.asyncio
async def test_rednote_missing_back_entry_restores_search_without_losing_note(monkeypatch):
    from unittest.mock import AsyncMock
    original='https://www.rednote.com/search_result?keyword=recipe'
    current=original
    class Connection:
        async def command(self,*args):raise RuntimeError('no such history entry: History entry with delta -1 not found')
    page=BackgroundPage(Connection(),'owned')
    async def snapshot():return {'url':current}
    async def call(source,args=()):
        if '.close-circle' in source:return None
        if 'scrollIntoView' in source:return {'rect':{},'url':'https://www.rednote.com/explore/abc'}
        return {'ready':True,'content':'Recipe body'}
    async def click(target):
        nonlocal current
        current='https://www.rednote.com/explore/abc'
    async def navigate(url,delay):
        nonlocal current
        current=url
    page.snapshot=snapshot;page.call_json=call;page.pointer_to=click;page.navigate=navigate
    page.mode=AsyncMock(return_value='natural');page.pause=AsyncMock()
    monkeypatch.setattr(asyncio,'sleep',AsyncMock())
    result={'items':[{'url':'https://www.rednote.com/explore/abc'}]}
    await page.enrich_xhs_notes(result)
    assert result['items'][0]['content']=='Recipe body'
    assert result['items'][0]['content_status']=='detail_read'
    assert current==original
