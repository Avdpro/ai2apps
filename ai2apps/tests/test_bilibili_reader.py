import pytest
from ai2apps.browser.background_page import BackgroundPage


@pytest.mark.asyncio
@pytest.mark.parametrize('text', ['', '视频说明\n先煮肉再切片，回锅煸炒后加豆瓣酱和蒜苗。'])
async def test_bilibili_reader_does_not_fall_back_to_recommendations(text):
    page = BackgroundPage(None, 'owned-video-tab')
    async def snapshot(maximum):
        return {'url': 'https://www.bilibili.com/video/BV123456/',
                'title': '回锅肉', 'text': '02:31 08:09 05:24'}
    calls = []
    async def call_json(script, args):
        calls.append(script)
        return {'url': 'https://www.bilibili.com/video/BV123456/', 'text': text,
                'content_kind': 'description' if text else 'unavailable',
                'extraction_method': 'bilibili-video-content'}
    page.snapshot = snapshot
    page.call_json = call_json
    result = await page.rendered_page(12000)
    assert result['text'] == text
    assert len(calls) == 3
    assert '__INITIAL_STATE__' in calls[0]
    assert 'bpx-player-ctrl-subtitle' in calls[1]


@pytest.mark.asyncio
async def test_native_subtitle_menu_loads_captions_before_description():
    page = BackgroundPage(None, 'owned-video-tab')
    async def snapshot(maximum):
        return {'url':'https://www.bilibili.com/video/BV123456/'}
    rect={'x':10,'y':10,'width':30,'height':20}
    replies=iter([{'content_kind':'description','text':'视频说明'},
                  {'rect':rect,'name':'字幕'}, {'rect':rect,'name':'中文'},
                  {'content_kind':'subtitles','text':'字幕/转录\n煮肉、切片，再煸炒加豆瓣酱。'}])
    async def call_json(*args):return next(replies)
    clicks=[]
    async def pointer_to(target,click):clicks.append((target['name'],click))
    async def wait_stable(**kwargs):return {'stable':True}
    page.snapshot=snapshot;page.call_json=call_json;page.pointer_to=pointer_to;page.wait_stable=wait_stable
    assert (await page.rendered_page())['content_kind']=='subtitles'
    assert clicks==[('字幕',True),('中文',True)]
