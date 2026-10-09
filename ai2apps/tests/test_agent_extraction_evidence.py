import json
from ai2apps.agents.browser_builder import extraction_model_evidence


def test_newest_dom_links_and_context_survive_repeated_large_snapshots():
    page={'url':'https://example.com/search','title':'Search','html':'x'*60000,
          'text':'Observed result '*600,'items':[{'ref':'e30','text':'Author','href':'https://example.com/author'},
          {'ref':'e31','text':'Date','href':'https://example.com/post/1'}]}
    latest={'step_id':'observe','outcome':'success','evidence':{'before':page,'after':page,
            'result':{'context':'real-context','page':page}}}
    result=extraction_model_evidence([{'step_id':'old','evidence':{'html':'y'*60000}},latest])
    assert result[0]['step_id']=='observe'
    assert result[0]['evidence']['result']['context']=='real-context'
    assert result[0]['evidence']['result']['page']['items'][1]['href'].endswith('/post/1')
    assert 'after' not in result[0]['evidence']
    assert len(json.dumps(result,ensure_ascii=False))<=40000
