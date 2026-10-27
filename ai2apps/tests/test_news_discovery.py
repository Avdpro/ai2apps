import pytest
from ai2apps.browser.background_page import BackgroundPage


@pytest.mark.asyncio
async def test_news_scan_deduplicates_follows_observed_entry_and_stops(monkeypatch):
    page=BackgroundPage(None,'test',interaction_mode=lambda url:'fast')
    current='https://example.com/'
    navigated=[]
    async def snapshot():return {'url':current}
    async def helper(name,*args):
        if name=='handlePageAccess:0':return {'classification':'none'}
        if name=='extractArticleList:0':
            suffix=['a','b'] if current.endswith('/') else ['b','c']
            return {'items':[{'url':'https://example.com/article/'+i,'title':'Story '+i} for i in suffix]}
        return {'regions':[]}
    async def call(source,*args):
        if 'scrollY' in source:return {'y':0,'height':800,'total':800}
        return {'next':'https://example.com/news' if current.endswith('/') else ''}
    async def navigate(url,**kwargs):
        nonlocal current
        current=url;navigated.append(url)
    page.snapshot=snapshot;page.helper=helper;page.call_json=call;page.navigate=navigate
    result=await page.extract_list({'arguments':{'news_scan':True,'limit':40}})
    assert len(result['items'])==3
    assert navigated==['https://example.com/news']
    assert result['discovery']['rounds']==2
    assert result['url']=='https://example.com/'


@pytest.mark.asyncio
async def test_news_scan_has_a_scroll_bound(monkeypatch):
    page=BackgroundPage(None,'test',interaction_mode=lambda url:'fast')
    scrolls=[]
    async def snapshot():return {'url':'https://example.com/news'}
    async def helper(*args):
        if args[0]=='handlePageAccess:0':return {'classification':'none'}
        return {'items':[{'url':f'https://example.com/story/{len(scrolls)}','title':'News'}]}
    async def call(source,*args):
        if 'scrollY' in source:return {'y':0,'height':800,'total':100000}
        return {'next':''}
    async def scroll(delta):scrolls.append(delta)
    async def sleep(_):pass
    monkeypatch.setattr('ai2apps.browser.background_page.asyncio.sleep',sleep)
    page.snapshot=snapshot;page.helper=helper;page.call_json=call;page.scroll=scroll
    result=await page.extract_list({'arguments':{'news_scan':True}})
    assert len(scrolls)==8
    assert result['discovery']['stop_reason']=='scroll_limit'


@pytest.mark.asyncio
async def test_news_scan_stops_when_empty_page_adds_no_links(monkeypatch):
    page=BackgroundPage(None,'test',interaction_mode=lambda url:'fast')
    scrolls=[]
    async def snapshot():return {'url':'https://example.com/news'}
    async def helper(*args):
        return {'classification':'none'} if args[0]=='handlePageAccess:0' else {'items':[]}
    async def call(source,*args):
        if 'scrollY' in source:return {'y':0,'height':800,'total':100000}
        return {'next':''}
    async def scroll(delta):scrolls.append(delta)
    async def sleep(_):pass
    monkeypatch.setattr('ai2apps.browser.background_page.asyncio.sleep',sleep)
    page.snapshot=snapshot;page.helper=helper;page.call_json=call;page.scroll=scroll
    result=await page.extract_list({'arguments':{'news_scan':True}})
    assert len(scrolls)==1
    assert result['discovery']['stop_reason']=='no_new_links'


@pytest.mark.asyncio
async def test_load_more_is_bounded_and_stops_without_new_items(monkeypatch):
    page=BackgroundPage(None,'test',interaction_mode=lambda url:'fast')
    clicks=[]
    async def snapshot():return {'url':'https://example.com/news'}
    async def helper(*args):
        return {'classification':'none'} if args[0]=='handlePageAccess:0' else {'items':[{'url':'https://example.com/story/a','title':'News A'}]}
    async def call(source,*args):
        if 'scrollY' in source:return {'y':0,'height':800,'total':800,'more':{'rect':{}}}
        return {'next':''}
    async def click(target):clicks.append(target)
    async def sleep(_):pass
    monkeypatch.setattr('ai2apps.browser.background_page.asyncio.sleep',sleep)
    page.snapshot=snapshot;page.helper=helper;page.call_json=call;page.pointer_to=click
    result=await page.extract_list({'arguments':{'news_scan':True}})
    assert len(clicks)==1
    assert result['discovery']['load_more_clicks']==1


@pytest.mark.asyncio
async def test_pagination_never_opens_a_fourth_page():
    page=BackgroundPage(None,'test')
    current=1
    navigations=[]
    async def snapshot():return {'url':f'https://example.com/news?page={current}'}
    async def helper(*args):
        return {'classification':'none'} if args[0]=='handlePageAccess:0' else {'items':[]}
    async def call(source,*args):
        if 'scrollY' in source:return {'y':0,'height':800,'total':800}
        return {'next':f'https://example.com/news?page={current+1}'}
    async def navigate(url,**kwargs):
        nonlocal current
        current+=1;navigations.append(url)
    page.snapshot=snapshot;page.helper=helper;page.call_json=call;page.navigate=navigate
    result=await page.extract_list({'arguments':{'news_scan':True}})
    assert len(result['discovery']['pages'])==3
    assert len(navigations)==2
    assert result['discovery']['stop_reason']=='page_limit'
