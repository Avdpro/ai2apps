import pytest
from ai2apps.browser.background_page import BackgroundPage

@pytest.mark.asyncio
async def test_x_accumulates_virtualized_results_until_requested_limit(monkeypatch):
    page = BackgroundPage(None, 'owned')
    rounds = iter([[{'url':'a'}, {'url':'b'}], [{'url':'b'}, {'url':'c'}], [{'url':'d'}]])
    async def read(*a): return {'provider':'x', 'items':next(rounds)}
    async def access(name,*args):
        assert name=='handlePageAccess:0'
        return {'classification':'none'}
    monkeypatch.setattr(page,'helper',access)
    scrolls = []
    async def scroll(delta): scrolls.append(delta)
    async def sleep(*a): pass
    monkeypatch.setattr(page, 'call_json', read)
    monkeypatch.setattr(page, 'scroll', scroll)
    monkeypatch.setattr('ai2apps.browser.background_page.asyncio.sleep', sleep)
    result = await page.extract_list({'arguments':{'search_provider':'x','limit':4}})
    assert [item['url'] for item in result['items']] == ['a','b','c','d']
    assert len(scrolls) == 2
    assert result['scan_stop_reason'] == 'limit_reached'

@pytest.mark.asyncio
async def test_x_stops_after_three_stalled_scrolls(monkeypatch):
    page = BackgroundPage(None, 'owned')
    async def read(*a): return {'items':[{'url':'a'}]}
    async def access(name,*args):
        assert name=='handlePageAccess:0'
        return {'classification':'none'}
    monkeypatch.setattr(page,'helper',access)
    scrolls = []
    async def scroll(delta): scrolls.append(delta)
    async def sleep(*a): pass
    monkeypatch.setattr(page,'call_json',read)
    monkeypatch.setattr(page,'scroll',scroll)
    monkeypatch.setattr('ai2apps.browser.background_page.asyncio.sleep',sleep)
    result = await page.extract_list({'arguments':{'search_provider':'x','limit':10}})
    assert len(scrolls) == 3
    assert result['scan_stop_reason'] == 'no_more_results'

@pytest.mark.asyncio
async def test_scroll_targets_viewport_content_not_navigation_corner(monkeypatch):
    commands=[]
    class Connection:
        async def command(self, method, args): commands.append((method,args))
    page=BackgroundPage(Connection(),'owned')
    async def read(source,*args):
        if 'visibilityState' in source:return {'visible':True,'document_focus':False}
        if 'elementFromPoint' in source:return [[0,700 if commands else 0]]
        return {'x':600,'y':400}
    async def mode(): return 'fast'
    monkeypatch.setattr(page,'call_json',read)
    monkeypatch.setattr(page,'mode',mode)
    await page.scroll(700)
    action=commands[0][1]['actions'][0]['actions'][0]
    assert (action['x'],action['y'],action['deltaY'])==(600,400,700)
