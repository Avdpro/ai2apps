from types import SimpleNamespace
import re
import pytest
from ai2apps.agents.models import RunStepStatus
from ai2apps.agents.citations import read_sources,bind_final,citation_instruction

URL='https://www.xiaohongshu.com/explore/note?xsec_token=exact%2Fvalue&xsec_source=pc_search'
OTHER='https://m.xiachufang.com/recipe/104170750/'

def steps():
    return [SimpleNamespace(id='step-1',kind='tool',status=RunStepStatus.COMPLETED,tool_name='web.search',output={
        'articles':[{'url':URL,'title':'小红书原文','text':'actual body','read':True},{'url':OTHER,'title':'下厨房原文','text':'other body','read':True},{'url':'https://unread.example/a','title':'failed','read':False}],
        'results':[{'url':'https://snippet.example/a','snippet':'snippet only'}],
        'citations':[{'id':'fake','url':'https://invented.example/a'}],
        'summary':{'overview':'已读正文总结','points':[{'text':'正文观点','source_ids':['1','2']}],'limitations':'来源之间有差异'}})]

def hrefs(text):return re.findall(r'\]\(<([^>]+)>\)',text)

def test_ids_are_bound_to_exact_read_urls_with_no_normalization():
    records=steps();sources=read_sources(records)
    assert [s['url'] for s in sources]==[URL,OTHER]
    output,audit=bind_final('观点 [[cite:S1]]，对照 [[cite:S2]]。',records)
    assert hrefs(output)==[URL,OTHER]
    assert audit['mode']=='source_ids'
    assert audit['sources'][0]['step_id']=='step-1'
    assert '[[cite:' not in output
    assert read_sources(records)==sources
    assert '[[cite:S1]]' in citation_instruction(records)['content']

def test_subtitle_file_never_replaces_the_original_video_citation():
    records=steps();video='https://www.bilibili.com/video/BV123456/?p=2'
    records[0].output['articles']=[{'url':video,'title':'视频字幕','text':'[00:00:01.000 --> 00:00:03.000] 实际字幕',
        'read':True,'content_kind':'subtitles','subtitle_video_url':video,
        'subtitle_track':{'url':'https://aisubtitle.hdslb.com/bfs/ai_subtitle/file.json'}}]
    output,audit=bind_final('字幕内容 [[cite:S1]]',records)
    assert hrefs(output)==[video]
    assert [s['url'] for s in audit['sources']]==[video]

@pytest.mark.parametrize('answer',[
    '正文 [小红书](https://www.xiachufang.com/explore/note) [[cite:S1]]',
    '正文 [引用]('+URL.replace('exact%2Fvalue','changed')+') [[cite:S1]]',
    '正文 [引用]('+URL+') [[cite:S1]]',
    '正文 https://invented.example/a [[cite:S1]]',
    '正文 www.invented.example [[cite:S1]]',
    '正文 [引用][ref] [[cite:S1]]\n[ref]: /other',
    '正文 ![image](//other.example/a) [[cite:S1]]',
    '正文 <a href="https&#58;//other.example">链接</a> [[cite:S1]]',
    '正文 [[cite:S99]]',
    '正文 [[cite: S1]]',
    '正文没有引用',
    '正文 `[[cite:S1]]`',
])
def test_invalid_parent_links_and_ids_fall_back_to_verified_report(answer):
    output,audit=bind_final(answer,steps())
    assert audit['mode']=='verified_report_fallback'
    assert audit['rejected_reason']
    assert set(hrefs(output))=={URL,OTHER}
    assert '正文观点' in output
    assert 'invented.example' not in output
    assert 'www.xiachufang.com/explore' not in output

def test_failed_snippet_foreign_tool_and_empty_body_cannot_grant_sources():
    records=steps();records[0].output['articles']=[{'url':URL,'read':False,'text':'failed body'},{'url':OTHER,'text':''}]
    assert read_sources(records)==[]
    output,audit=bind_final('伪造 [引用](https://unread.example/a)',records)
    assert audit['mode']=='no_read_sources' and 'https://' not in output
    records[0].tool_name='untrusted.echo'
    assert bind_final('ordinary answer',records)==('ordinary answer',None)

def test_fallback_report_cannot_inject_its_own_links():
    records=steps();records[0].output['summary']['points'][0]['text']='[wrong](https://invented.example/a)'
    records[0].output['summary']['overview']='<a href="//other.example">wrong</a>'
    output,_=bind_final('bad final',records)
    assert 'invented' not in output and 'other.example' not in output
    assert set(hrefs(output))=={URL,OTHER}
