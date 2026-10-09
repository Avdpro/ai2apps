from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from ai2apps.intelligence import service


def runtime(hits=()):
    knowledge=NS(list_buckets=Mock(return_value=[NS(id='one'),NS(id='two')]),search=Mock(return_value=hits))
    return NS(knowledge=knowledge)


def hit(id='doc',facets=()):
    return NS(item=NS(id=id,title='Guide',revision=2),excerpt='Reserve 80 hours.',source_facets=facets)


@pytest.mark.asyncio
async def test_knowledge_only_answer_and_citation(monkeypatch):
    r=runtime([hit()])
    async def model(runtime,request,principal,id,instruction,data,validate):
        assert not data['articles']
        assert data['knowledge_excerpts'][0]['evidence_id']==1
        assert 'untrusted' in instruction
        with pytest.raises(ValueError):validate({'answer':'invented [2]','evidence_ids':[2]})
        return validate({'answer':'80 hours [1]','evidence_ids':[1]})
    monkeypatch.setattr(service,'model_json',model)
    result=await service.converse(r,None,'owner',{'id':'c','name':'Watches','interests':'','knowledge_bucket_ids':['one','two']},'reserve?',[],[])
    r.knowledge.search.assert_called_once_with('owner','reserve?',bucket_ids=['one','two'],limit=12)
    assert result['references'][0]['kind']=='knowledge'
    assert result['references'][0]['item_id']=='doc'


def test_no_link_never_searches_and_missing_bucket_never_broadens():
    r=runtime([hit()])
    assert service.knowledge_conversation_evidence(r,'owner',{},'query',set())==[]
    r.knowledge.search.assert_not_called()
    with pytest.raises(HTTPException):service.knowledge_conversation_evidence(r,'owner',{'knowledge_bucket_ids':['gone']},'query',set())
    r.knowledge.search.assert_not_called()


def test_synced_article_dedup_and_unavailable_semantic_fallback():
    r=runtime([hit('dup',(('intelligence.article','a'),)),hit(),hit()])
    r.knowledge_package_runtime=NS(ready_retriever=Mock(side_effect=RuntimeError('offline')))
    result=service.knowledge_conversation_evidence(r,'owner',{'knowledge_bucket_ids':['one']},'query',{'a'})
    assert [e['id'] for e in result]==['doc']
