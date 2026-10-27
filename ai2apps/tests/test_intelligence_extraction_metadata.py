from ai2apps.intelligence.collector import IntelligenceCollector as Collector
from ai2apps.intelligence.models import Page


def test_evidence_preserves_extraction_provenance_without_reparsing_text():
    source={'id':'source','name':'Arbitrary source'}
    page={'url':'https://example.org/report','title':'Report','text':'Complete body',
          'extraction_method':'compiled-site-agent','extracted_chars':13,'truncated':False,
          'extraction_limit':20000,'non_content_nodes_removed':9}
    result=Collector.evidence(source,page,page['url'])
    assert result['text']=='Complete body'
    assert result['extraction_method']=='compiled-site-agent'
    assert result['extracted_chars']==13
    assert result['returned_chars']==13
    assert not result['truncated']
    assert Page.model_validate(result).non_content_nodes_removed==9


def test_evidence_reports_its_own_storage_bound_without_losing_original_length():
    page={'url':'https://example.org/report','text':'x'*21000,
          'extraction_method':'readability','extracted_chars':24000,'truncated':True}
    result=Collector.evidence({'id':'source','name':'Source'},page,page['url'])
    assert len(result['text'])==20000
    assert result['returned_chars']==20000
    assert result['extracted_chars']==24000
    assert result['truncated']
