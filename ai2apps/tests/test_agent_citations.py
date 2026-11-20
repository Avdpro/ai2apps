from types import SimpleNamespace
import re
import pytest
from ai2apps.agents.models import RunStepStatus
from ai2apps.research.citations import read_sources,bind_final,citation_instruction
from ai2apps.browser.goal_aaat import citation_sources

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


def test_task_failure_keeps_read_evidence_and_search_attempt_counts():
    from ai2apps.research.citations import failure_receipt
    records=steps()
    records[0].output['articles'].pop()
    records[0].output['read_failures']=[{'url':'https://unread.example/a'}]
    records[0].output['summary']['points'].append({'text':'Unverified rumor','source_ids':['99']})
    second=steps()[0]
    second.output['articles']=[second.output['articles'][1]]
    second.output['summary']['points']=[{'text':'另一次读到的观点','source_ids':['1']}]
    records.append(second)
    receipt=failure_receipt(records,zh=False)
    assert 'Attempted 4 page reads' in receipt['progress']
    assert '2 distinct sources' in receipt['progress']
    assert '正文观点' in receipt['evidence'] and '来源之间有差异' in receipt['evidence']
    assert hrefs(receipt['evidence'])==[URL,OTHER]
    assert '正文观点 [1, 2]' in receipt['evidence']
    assert '另一次读到的观点 [2]' in receipt['evidence']
    assert 'Unverified rumor' not in receipt['evidence']


def test_browser_goal_binds_observed_detail_and_retains_owner_answer_on_invalid_parent_link():
    detail = 'https://manufacturer.example/product/blue-41'
    invented = 'https://manufacturer.example/product/invented'
    evidence = [
        {'step_id': 'open', 'outcome': 'success', 'evidence': {'operation': 'open',
         'after': {'url': OTHER, 'text': 'Collection'}}},
        {'step_id': 'explore', 'outcome': 'success', 'evidence': {'operation': 'inspect', 'attempts': [
            {'outcome': 'success', 'evidence': {'after': {'url': detail, 'text': 'Product overview'}}},
            {'outcome': 'failed', 'evidence': {'after': {'url': invented, 'text': 'Failed observation'}}},
        ]}},
        {'step_id': 'observe', 'outcome': 'success', 'evidence': {'operation': 'inspect',
         'result': {'page': {'url': detail, 'title': 'Product detail', 'text': '41 mm, 13.26 mm, 60 hours'}}}},
        {'step_id': 'answer', 'outcome': 'success', 'evidence': {'operation': 'ai.extract',
         'result': {'url': invented, 'text': 'Invented page'}}},
    ]
    answer = 'Reference 220.10.41.21.03.007, 41 mm, 13.26 mm, 60 hours, USD 7,400.'
    goal = SimpleNamespace(id='browser-step', kind='tool', status=RunStepStatus.COMPLETED,
                           tool_name='browser.complete_goal', output={
                               'status': 'completed', 'citation_sources': citation_sources(evidence),
                               'result': {'url': detail, 'answer': answer, 'limitations': 'One new model verified.'}})
    assert [source['url'] for source in read_sources([goal])] == [OTHER, detail]
    assert 'Product detail' in citation_instruction([goal])['content']
    text, audit = bind_final('The case is `41 mm` [[cite:S2]].', [goal])
    assert audit['mode'] == 'source_ids' and hrefs(text) == [detail]
    for invalid in (f'{answer} [[cite:S2]] {invented}', '```\n[[cite:S2]]\n```'):
        text, audit = bind_final(invalid, [goal])
        assert audit['mode'] == 'verified_report_fallback'
        assert answer in text and hrefs(text) == [detail]
        assert invented not in text
    goal.output['result']['url'] = invented
    text, _ = bind_final('No markers', [goal])
    assert answer not in text and invented not in text
