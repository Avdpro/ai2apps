import json
import httpx
import pytest
from fastapi import FastAPI, HTTPException
from ai2apps.api.messager import create_messager_router
from test_bot_capability_discovery import setup,P
from test_app_chat_durable import bind_identity,response
from test_app_interactions import runtime,wait
from test_bot_dialogue import job_wait

@pytest.mark.asyncio
@pytest.mark.parametrize('decision',[42,[],None,{}, {'kind':'reply','text':4},{'kind':'task','text':'Queued','title':[]},{'kind':'unknown','text':'x'}, {'kind':'reply','text':'x','schedule':{'hour':'9'}},{'kind':'task','text':'Queued','access_requirements':[{'capability':4}]}])
async def test_invalid_business_decision_is_safe_failure(runtime,decision):
    bot,sid,_,_=setup(runtime);calls=[]
    async def model(_):calls.append(1);return response(text=json.dumps(decision))
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'invalid-decision','hello','fixture',[])
        await wait(runtime,rid,'failed');run=runtime.agents.get_run(rid)
        assert run.error['code']=='bot_dialogue_response' and '请再发一次' in run.error['message']
        snap=runtime.messager_dialogue.snapshot(P(),bot['id'],sid)
        assert snap['runs'][-1]['error'] is None
        messages=runtime.app_chat.message_page(P(),sid)['items']
        assert sum(m['content']==run.error['message'] for m in messages)==1
        with runtime.database.transaction() as db:
            assert not db.execute('SELECT count(*) FROM messager_dialogue_jobs').fetchone()[0]
            assert not db.execute('SELECT count(*) FROM messager_memory_candidates').fetchone()[0]
        assert len(calls)==2
    finally:await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_dialogue_state_reuses_failure_message_saved_before_upgrade(runtime):
    bot,sid,_,_=setup(runtime)
    dialogue=runtime.messager_dialogue

    async def model(_):
        return response(text=' '*120)

    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=dialogue.submit(P(),bot['id'],sid,'legacy-failure','Find a reference','fixture',[],language='en')
        await wait(runtime,rid,'failed')
        old_text='This turn did not finish and was not retried automatically. Select a task to continue or send again.'
        saved=dialogue.append(sid,'assistant',old_text,'bot-dialogue-failure:'+rid,
                              {'origin':'bot_dialogue','agent_run_id':rid,'decision':'failed'})
        app=FastAPI()
        app.include_router(create_messager_router(lambda:runtime,P))
        url=f"/messager/bots/{bot['id']}/dialogue/state"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            for _ in range(2):
                result=await client.get(url,params={'session_id':sid})
                assert result.status_code==200,result.text
                assert result.json()['runs'][-1]['status']=='failed'
                assert result.json()['runs'][-1]['error'] is None
        messages=runtime.app_chat.message_page(P(),sid)['items']
        assert [(item['id'],item['content']) for item in messages if item['role']=='assistant']==[(saved.value.message.id,old_text)]
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
@pytest.mark.parametrize('repair_after_recall',[False,True])
async def test_blank_dialogue_decision_recovers_without_replaying_work(runtime,tmp_path,repair_after_recall):
    bot,sid,_,_=setup(runtime)
    path=tmp_path/'reference.txt'
    path.write_text('Fixture reference')
    attachment=runtime.documents.create_reference(sid,path,filename=path.name,media_type='text/plain')
    dialogue_requests=[]
    worker_requests=[]
    blank=' '*120
    recall=json.dumps({'kind':'recall','text':'Checking past work','recall_query':'reference'})
    task=json.dumps({'kind':'task','text':'Queued','title':'Find previous reference'})
    replies=iter([recall,blank,task] if repair_after_recall else [blank,recall,task])

    async def model(request):
        if 'Decide quickly' not in request['messages'][0]['content']:
            worker_requests.append(request)
            return response(text='Search completed in fixture')
        assert not request.get('tools')
        dialogue_requests.append(request)
        return response(text=next(replies))

    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        source=runtime.messager_dialogue.submit(P(),bot['id'],sid,'recover-decision','Start a new task to find my reference','fixture',[attachment.id])
        await wait(runtime,source,'completed')
        await job_wait(runtime,source,'completed')
        assert len(worker_requests)==1
        assert len(dialogue_requests)==3
        assert all(r['messages'][-1]==dialogue_requests[0]['messages'][-1] for r in dialogue_requests)
        assert attachment.id in dialogue_requests[0]['messages'][-1]['content']
        repaired=dialogue_requests[2 if repair_after_recall else 1]['messages'][0]['content']
        assert 'previous answer did not contain a valid decision' in repaired
        assert ('Recall completed' in repaired)==repair_after_recall
    finally:
        await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_provider_failure_preserves_generic_code_and_settled_usage(runtime):
    bot,sid,_,_=setup(runtime)
    details={'schemaVersion':'arbitrary-provider-error.v1','billingStatus':'settled','points':{'charged':'2'},'usage':{'inputTokens':10}}
    async def model(_):raise HTTPException(502,{'code':'PROVIDER_FORMAT_INVALID','message':'Structured response failed','retryable':False,'details':details})
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'provider-failure','hello','fixture',[]);await wait(runtime,rid,'failed')
        error=runtime.agents.get_run(rid).error
        assert error=={'code':'PROVIDER_FORMAT_INVALID','message':'Structured response failed','retryable':False,'details':details}
    finally:await runtime.stop_background_tasks()
