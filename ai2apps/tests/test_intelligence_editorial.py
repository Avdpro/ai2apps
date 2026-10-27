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
    await service.digest(None,None,None,{'id':'c'},pages()[:1],[],on_progress=activity.append,
        on_article=lambda i,a:activity.append({'phase':'saved'}))
    assert activity[0]['phase']=='planning'
    assert any(p['phase']=='saved' for p in activity)
    assert activity[-1]['phase']=='saving' and activity[-1]['events_completed']==1
    assert activity[-1]['active_articles']==[]
    assert activity[1]['event_title']=='Race' and activity[1]['events_total']==1

@pytest.mark.asyncio
@pytest.mark.parametrize('succeed',[True,False])
async def test_validation_repairs_are_explicit_bounded_and_keep_original_evidence(monkeypatch,succeed):
    payloads=[];progress=[]
    async def invoke(payload,**kwargs):
        payloads.append(payload)
        return {'choices':[{'finish_reason':'stop','message':{'content':'{"ok":'+('true' if succeed and len(payloads)==3 else 'false')+'}'}}]}
    runtime=NS(model_manager=NS(resolve_default_model=lambda _:'cloud/test/model'),model_invocations=NS(
        model=lambda _:None,context_for_actor=lambda *a,**kw:None,invoke_agent_cloud_json=invoke))
    monkeypatch.setattr('ai2apps.intelligence.language.output_language',lambda *a:'English')
    def validate(value):
        if not value['ok']:raise ValueError('events[0].supporting_evidence_ids=[7] not in evidence_ids=[1]')
        return value
    call=service.model_json(runtime,None,NS(actor_user_id='owner'),'c','schema',{'evidence':[{'evidence_id':1,'text':'original'}]},validate,on_progress=progress.append)
    if succeed:assert await call=={'ok':True}
    else:
        with pytest.raises(HTTPException,match='已尝试 3 次'):await call
    assert len(payloads)==3
    for payload in payloads[1:]:
        assert payload['messages'][:2]==payloads[0]['messages'][:2]
        assert len(payload['messages'])==4
        assert 'events[0].supporting_evidence_ids=[7]' in payload['messages'][-1]['content']
        assert 'all evidence and citation checks remain mandatory' in payload['messages'][-1]['content']
    assert any(p.get('model_validation_error') for p in progress)


@pytest.mark.asyncio
async def test_plan_never_discards_outside_supporting_evidence(monkeypatch):
    async def model(*args,**kwargs):
        return args[-1]({'events':[{'title':'bad','evidence_ids':[1],'supporting_evidence_ids':[2]}]})
    monkeypatch.setattr(service,'model_json',model)
    state={}
    with pytest.raises(ValueError,match=r'events\[0\].supporting_evidence_ids'):
        await service.digest(None,None,None,{'id':'c'},pages(),[],checkpoint=state)
    assert state=={}

@pytest.mark.asyncio
@pytest.mark.parametrize('section,accepted',[(' s ',True),('unknown',False)])
async def test_category_tolerance_only_normalizes_known_id(monkeypatch,section,accepted):
    async def model(*args,**kwargs):
        if kwargs['stage']=='event_plan':return args[-1]({'events':[{'title':'E','evidence_ids':[1],'section_id':section}]})
        return args[-1]({'articles':[{'title':'E','summary':'s','body':'fact [1]','evidence_ids':[1],'section_id':'s'}]})
    monkeypatch.setattr(service,'model_json',model)
    call=service.digest(None,None,None,{'id':'c','sections':[{'id':'s'}]},pages()[:1],[])
    if accepted:assert len(await call)==1
    else:
        with pytest.raises(ValueError,match='Invalid event section_id'):await call


@pytest.mark.asyncio
@pytest.mark.parametrize('target',[None,'old'])
async def test_editorial_payload_omits_derived_channel_and_unselected_previous(monkeypatch,target):
    observed=[]
    channel={'id':'c','name':'News','interests':'facts','entity_taxonomy':{'signatures':{'huge':'x'*100000}},'hot_topics':{'items':['x'*100000]}}
    previous=[{'id':id,'title':id,'summary':'old fact','sources':[]} for id in ('old','other')]
    async def model(runtime,request,principal,id,instruction,data,validate,**kwargs):
        observed.append(data)
        assert 'entity_taxonomy' not in data['channel'] and 'hot_topics' not in data['channel']
        if kwargs['stage']=='event_plan':
            assert len(data['previous_articles'])==2
            return validate({'events':[{'title':'Event','evidence_ids':[1],'update_article_id':target}]})
        assert [a['id'] for a in data['previous_articles']]==([target] if target else [])
        assert data['evidence'][0]['evidence_id']==1
        return validate({'articles':[{'title':'Event','summary':'s','body':'fact [1]','evidence_ids':[1],'update_article_id':target}]})
    monkeypatch.setattr(service,'model_json',model)
    result=await service.digest(None,None,None,channel,pages()[:1],previous)
    assert len(result)==1 and result[0]['update_article_id']==target
    assert len(observed)==2


def test_planning_retains_all_candidates_and_source_urls_without_metadata():
    previous=[{'id':str(i),'title':'Event','summary':'Facts','sources':[
        {'url':'https://example.com/'+str(i),'title':'Long source title','retrieved_at':'now','image_url':'x'*10000},
        {'url':'https://example.com/'+str(i),'coverage':'preview'}]} for i in range(40)]
    compact=service.planning_previous(previous)
    assert len(compact)==40
    for i,a in enumerate(compact):
        assert a=={'id':str(i),'title':'Event','summary':'Facts','sources':[{'url':'https://example.com/'+str(i)}]}


@pytest.mark.asyncio
@pytest.mark.parametrize('declared',[True,False])
@pytest.mark.parametrize('stage',['x_rule','translation'])
async def test_simple_stage_budget_uses_only_declared_effort_and_expands_on_truncation(monkeypatch,declared,stage):
    payloads=[]
    async def invoke(payload,**kwargs):
        payloads.append(payload)
        return {'choices':[{'finish_reason':'length' if len(payloads)==1 else 'stop','message':{'content':'{"photo":0}'}}]}
    manager=NS(resolve_default_model=lambda _:'cloud/arbitrary/model',list_cloud=lambda:[{'id':'arbitrary','models':[{'id':'model','capabilities':{'reasoningEfforts':['low']} if declared else {}}]}])
    runtime=NS(model_manager=manager,model_invocations=NS(model=lambda _:None,context_for_actor=lambda *a,**kw:None,invoke_agent_cloud_json=invoke))
    monkeypatch.setattr('ai2apps.intelligence.language.output_language',lambda *a:'English')
    result=await service.model_json(runtime,None,NS(actor_user_id='owner'),'c','schema',{'observed':'original'},lambda x:x,stage=stage)
    assert result=={'photo':0}
    assert [p['max_tokens'] for p in payloads]==([1024,2048] if stage=='x_rule' else [20000,20000])
    assert payloads[0]['messages']==payloads[1]['messages']
    assert ('reasoning_effort' in payloads[0]) is declared
    if declared:assert payloads[0]['reasoning_effort']=='low'


@pytest.mark.asyncio
async def test_roundup_cannot_split_new_articles_but_can_update_multiple_existing(monkeypatch):
    saved=[];calls=[];previous=[{'id':id,'title':id,'summary':'s','sources':[]} for id in ('old1','old2')]
    async def model(*args,**kwargs):
        validate=args[-1];data=args[-2];calls.append(kwargs['stage'])
        if kwargs['stage']=='event_plan':
            with pytest.raises(ValueError,match='CREATE more than one'):
                validate({'events':[{'title':'Product A','evidence_ids':[1]},{'title':'Product B','evidence_ids':[1]}]})
            # Unknown update IDs cannot be used to evade the new-article cap.
            with pytest.raises(ValueError,match='Invalid event update target'):
                validate({'events':[{'title':'A','evidence_ids':[1],'update_article_id':'invented'}]})
            return validate({'events':[{'title':'Roundup','evidence_ids':[1]},
                {'title':'Update A','evidence_ids':[1],'update_article_id':'old1'},
                {'title':'Update B','evidence_ids':[1],'update_article_id':'old2'}]})
        event=data['planned_event']
        return validate({'articles':[{'title':event['title'],'summary':'s','body':'fact [1]','evidence_ids':[1],'update_article_id':event['update_article_id']}]})
    monkeypatch.setattr(service,'model_json',model)
    result=await service.digest(None,None,None,{'id':'c'},pages()[:1],previous,on_article=lambda i,a:saved.append(a))
    assert len(result)==3 and len(saved)==3
    assert sum(not a['update_article_id'] for a in result)==1
    assert {a['update_article_id'] for a in result if a['update_article_id']}=={'old1','old2'}


@pytest.mark.asyncio
async def test_legacy_digest_rejects_multiple_new_articles_from_one_source(monkeypatch):
    async def model(*args,**kwargs):
        return args[-1]({'articles':[{'title':str(i),'summary':'s','body':'fact [1]','evidence_ids':[1]} for i in range(2)]})
    monkeypatch.setattr(service,'model_json',model)
    with pytest.raises(ValueError,match='CREATE more than one'):
        await service.digest_event(None,None,None,{'id':'c'},pages()[:1],[])


@pytest.mark.asyncio
async def test_invalid_cached_fanout_plan_stops_before_generating_or_saving(monkeypatch):
    async def forbidden(*args,**kwargs):raise AssertionError('Invalid old plan must not generate more articles')
    monkeypatch.setattr(service,'model_json',forbidden)
    state={'plan':{'events':[{'title':'A','evidence_ids':[1]},{'title':'B','evidence_ids':[1]}]},'articles':{}}
    with pytest.raises(ValueError,match='CREATE more than one'):
        await service.digest(None,None,None,{'id':'c'},pages()[:1],[],checkpoint=state,on_article=lambda *a:pytest.fail('must not save'))


@pytest.mark.asyncio
async def test_model_receives_fanout_error_and_repairs_without_losing_source(monkeypatch):
    import json
    payloads=[]
    async def invoke(payload,**kwargs):
        payloads.append(payload)
        if len(payloads)==1:
            value={'events':[{'title':'A','evidence_ids':[1]},{'title':'B','evidence_ids':[1]}]}
        elif len(payloads)==2:
            assert 'CREATE more than one' in payload['messages'][-1]['content']
            assert payload['messages'][:2]==payloads[0]['messages'][:2]
            value={'events':[{'title':'Combined roundup','evidence_ids':[1]}]}
        else:
            value={'articles':[{'title':'Combined roundup','summary':'s','body':'facts [1]','evidence_ids':[1]}]}
        return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]}
    runtime=NS(model_manager=NS(resolve_default_model=lambda _:'cloud/test/model'),model_invocations=NS(
        model=lambda _:None,context_for_actor=lambda *a,**kw:None,invoke_agent_cloud_json=invoke))
    monkeypatch.setattr('ai2apps.intelligence.language.output_language',lambda *a:'English')
    saved=[]
    result=await service.digest(runtime,None,NS(actor_user_id='owner'),{'id':'c'},pages()[:1],[],on_article=lambda i,a:saved.append(a))
    assert len(payloads)==3 and len(saved)==1 and len(result)==1
    assert result[0]['sources'][0]['url']==pages()[0]['url']


@pytest.mark.asyncio
async def test_editorial_parallel_limit_checkpoint_and_stable_order(monkeypatch):
    import asyncio
    import copy
    evidence=[dict(url=f'https://example.com/{i}',title=f'E{i}',text='facts',source_id='s') for i in range(7)]
    state={'plan':{'events':[{'title':f'E{i}','evidence_ids':[i+1]} for i in range(7)]},'articles':{}}
    entered=asyncio.Event();release=asyncio.Event();running=0;peak=0;calls=[];saved=[];checkpoints=[];activity=[]
    async def generate(*args,**kwargs):
        nonlocal running,peak
        i=args[6]['evidence_ids'][0]-1;calls.append(i);running+=1;peak=max(peak,running)
        if running==3:entered.set()
        try:
            kwargs['on_progress']({'model_attempt':i+1,'model_stage':'article'})
            await release.wait()
            await asyncio.sleep((7-i)*.001)
            return [{'title':f'E{i}','body':'facts'}]
        finally:running-=1
    monkeypatch.setattr(service,'digest_event',generate)
    task=asyncio.create_task(service.digest(None,None,None,{'id':'c'},evidence,[],checkpoint=state,
        on_article=lambda i,a:saved.append(i),save_checkpoint=lambda s:checkpoints.append(copy.deepcopy(s)),on_progress=activity.append))
    await asyncio.wait_for(entered.wait(),1)
    assert calls==[0,1,2] and not saved
    assert len(activity[-1]['active_articles'])==3
    release.set();result=await task
    assert peak==3 and running==0 and sorted(saved)==list(range(7))
    assert [a['title'] for a in result]==[f'E{i}' for i in range(7)]
    assert len(checkpoints)==7 and set(checkpoints[-1]['articles'])==set(map(str,range(7)))
    assert activity[-1]['events_completed']==7 and activity[-1]['active_articles']==[]


@pytest.mark.asyncio
async def test_parallel_resume_only_unfinished_events(monkeypatch):
    evidence=[dict(url=f'https://example.com/{i}',text='facts') for i in range(4)]
    state={'plan':{'events':[{'title':f'E{i}','evidence_ids':[i+1]} for i in range(4)]},'articles':{'0':{'title':'saved'}}}
    calls=[];saved=[];fail=True
    async def generate(*args,**kwargs):
        i=args[6]['evidence_ids'][0]-1;calls.append(i)
        if i==2 and fail:raise HTTPException(502,'invalid evidence')
        return [{'title':f'E{i}'}]
    monkeypatch.setattr(service,'digest_event',generate)
    result=await service.digest(None,None,None,{'id':'c'},evidence,[],checkpoint=state,on_article=lambda i,a:saved.append(i))
    assert set(calls)=={1,2,3} and result.failed_urls=={'https://example.com/2'}
    assert set(saved)=={1,3}
    fail=False;calls.clear();saved.clear()
    result=await service.digest(None,None,None,{'id':'c'},evidence,[],checkpoint=state,on_article=lambda i,a:saved.append(i))
    assert calls==[2] and saved==[2] and not result.failures and len(result)==4


@pytest.mark.asyncio
@pytest.mark.parametrize('fatal',[False,True])
async def test_parallel_cancel_and_fatal_error_join_siblings(monkeypatch,fatal):
    import asyncio
    state={'plan':{'events':[{'title':f'E{i}','evidence_ids':[i+1]} for i in range(3)]},'articles':{}}
    evidence=[dict(url=f'https://example.com/{i}',text='facts') for i in range(3)]
    ready=asyncio.Event();running=0;ended=[];saved=[]
    async def generate(*args,**kwargs):
        nonlocal running
        i=args[6]['evidence_ids'][0]-1;running+=1
        if running==3:ready.set()
        try:
            await ready.wait()
            if fatal and i==0:raise HTTPException(409,'model unavailable')
            await asyncio.Event().wait()
        finally:ended.append(i)
    monkeypatch.setattr(service,'digest_event',generate)
    task=asyncio.create_task(service.digest(None,None,None,{'id':'c'},evidence,[],checkpoint=state,on_article=lambda i,a:saved.append(i)))
    await asyncio.wait_for(ready.wait(),1)
    if fatal:
        with pytest.raises(HTTPException) as error:await task
        assert error.value.status_code==409
    else:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    assert sorted(ended)==[0,1,2] and saved==[] and state['articles']=={}
