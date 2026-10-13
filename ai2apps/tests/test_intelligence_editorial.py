from types import SimpleNamespace as NS
import pytest
from fastapi import HTTPException
from ai2apps.intelligence import service


def pages():
    return [dict(url=f'https://example.com/{i}',title=f'Event {i}',source_name='source',retrieved_at='now',text='facts',source_id='s') for i in range(2)]


@pytest.mark.asyncio
async def test_plan_then_events_retains_success_and_retries_only_failure(monkeypatch):
    calls=[];saved=[];state={};fail=True
    async def model(runtime,request,principal,id,instruction,data,validate,**kwargs):
        nonlocal fail
        calls.append(kwargs['stage'])
        if kwargs['stage']=='event_plan':return validate({'events':[{'title':f'E{i}','evidence_ids':[i+1]} for i in range(2)]})
        ids=data['planned_event']['evidence_ids']
        if ids==[2] and fail:raise HTTPException(502,'output truncated')
        return validate({'articles':[{'title':'E','summary':'s','body':f'fact [{ids[0]}]','evidence_ids':ids}]})
    monkeypatch.setattr(service,'model_json',model)
    result=await service.digest(None,None,None,{'id':'c'},pages(),[],checkpoint=state,on_article=lambda i,a:saved.append(i))
    assert len(result)==1 and result.failed_urls=={'https://example.com/1'} and saved==[0]
    fail=False
    result=await service.digest(None,None,None,{'id':'c'},pages(),[],checkpoint=state,on_article=lambda i,a:saved.append(i))
    assert len(result)==2 and not result.failures and saved==[0,1]
    assert calls==['event_plan','article','article','article']
    assert result[1]['body']=='fact [1]' and result[1]['sources'][0]['url']=='https://example.com/1'


@pytest.mark.asyncio
async def test_invalid_plan_ids_rejected(monkeypatch):
    async def model(*args,**kwargs):return args[-1]({'events':[{'title':'bad','evidence_ids':[3]}]})
    monkeypatch.setattr(service,'model_json',model)
    with pytest.raises(ValueError):await service.digest(None,None,None,{'id':'c'},pages(),[])


@pytest.mark.asyncio
async def test_twenty_k_truncation_retries_from_evidence_without_partial_json(monkeypatch):
    payloads=[]
    async def invoke(payload,**kwargs):
        payloads.append(payload)
        return {'choices':[{'finish_reason':'length' if len(payloads)==1 else 'stop','message':{'content':'broken partial' if len(payloads)==1 else '{"ok":true}'}}], 'usage':{'completion_tokens':20000}}
    manager=NS(resolve_default_model=lambda _: 'cloud/test/model')
    invocation=NS(model=lambda _:None,context_for_actor=lambda *a,**kw:None,invoke_agent_cloud_json=invoke)
    monkeypatch.setattr('ai2apps.intelligence.language.output_language',lambda *a:'English')
    result=await service.model_json(NS(model_manager=manager,model_invocations=invocation),None,NS(actor_user_id='owner'),'c','instruction',{},lambda x:x)
    assert result=={'ok':True}
    assert [p['max_tokens'] for p in payloads]==[20000,20000]
    assert all(m['role']!='assistant' for m in payloads[1]['messages'])


@pytest.mark.asyncio
async def test_editorial_activity_precedes_model_and_save(monkeypatch):
    activity=[]
    async def model(*args,**kwargs):
        assert activity[-1]['phase'] in ('planning','writing')
        if kwargs['stage']=='event_plan':return args[-1]({'events':[{'title':'Race','evidence_ids':[1]}]})
        return args[-1]({'articles':[{'title':'Race','summary':'s','body':'fact [1]','evidence_ids':[1]}]})
    monkeypatch.setattr(service,'model_json',model)
    await service.digest(None,None,None,{'id':'c'},pages(),[],on_progress=activity.append,
        on_article=lambda i,a:activity.append({'phase':'saved'}))
    assert [p['phase'] for p in activity]==['planning','writing','saving','saved']
    assert activity[1]['event_title']=='Race' and activity[1]['events_total']==1
