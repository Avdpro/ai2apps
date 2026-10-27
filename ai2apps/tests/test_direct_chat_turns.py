"""Real API/SQLite/scheduler; model output is a controllable fixture."""
import asyncio
from dataclasses import replace

import httpx
import pytest

from ai2apps.chat import ChatRepository, LegacyChatMessageInput
from ai2apps.core import MessageRole, ResourceConflictError, RevisionConflictError
from ai2apps.identity import RequestPrincipal
from ai2apps.chat import turns
from test_app_interactions import runtime, client_app, wait


def prepared(runtime, principal=None):
    repo = ChatRepository(runtime.database, runtime.events, principal=principal)
    thread, _ = repo.create_thread(title='Offline direct Chat')
    content = repo.replace_content(thread.session.id, expected_revision=thread.session.revision,
        metadata={}, messages=(LegacyChatMessageInput(MessageRole.USER, 'hi', {'id': 'user-1'}),))
    return repo, content.thread.session.id, content.thread.session.revision


def payload(revision, key='first', text='hi'):
    return {'request_id': key, 'expected_revision': revision,
            'request': {'model': 'fixture-model', 'temperature': None,
                        'messages': [{'role': 'user', 'content': text}]}}


def result(text='hello'):
    return {'choices': [{'message': {'role': 'assistant', 'content': text,
              'reasoning_content': 'fixture reasoning'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 1, 'completion_tokens': 2}}


@pytest.mark.asyncio
async def test_closed_client_still_finishes_and_new_client_continues(runtime):
    repo, sid, revision = prepared(runtime)
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []
    async def model(request):
        calls.append(request); entered.set(); await release.wait(); return result()
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.agent_runtime.start()
    try:
        app = client_app(runtime)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.post(f'/v1/platform/chat/threads/{sid}/turns', json=payload(revision))
            assert response.status_code == 202, response.text
            rid = response.json()['id']
        # There are now no observing HTTP requests or open clients.
        await asyncio.wait_for(entered.wait(), 5)
        with pytest.raises(ResourceConflictError):
            repo.replace_content(sid, expected_revision=revision, metadata={}, messages=())
        release.set(); done = await wait(runtime, rid, 'completed')
        assert len(calls) == 1 and 'tools' not in calls[0]
        assert calls[0]['messages'] == [{'role':'user','content':'hi'}]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            restored = (await client.get(f'/v1/platform/chat/threads/{sid}/content')).json()
            assert [m['content'] for m in restored['messages']] == ['hi', 'hello']
            assert restored['messages'][-1]['metadata']['id'] == done.output['message_id']
            replay = await client.post(f'/v1/platform/chat/threads/{sid}/turns', json=payload(revision))
            assert replay.status_code == 202 and replay.json()['id'] == rid
            assert len(calls) == 1
            # Continue using the saved answer; no replay of the previous round.
            revision2 = restored['thread']['revision']
            messages = tuple(LegacyChatMessageInput(MessageRole(m['role']),m['content'],m['metadata']) for m in restored['messages'])
            updated = repo.replace_content(sid, expected_revision=revision2, metadata={},
                messages=(*messages, LegacyChatMessageInput(MessageRole.USER,'next',{})))
            assert repo.get_content(sid).messages[1].metadata['id'] == done.output['message_id']
            new = payload(updated.thread.session.revision, 'second', 'next')
            new['request']['messages'] = [{'role': m.role.value, 'content':m.content} for m in updated.messages]
            response = await client.post(f'/v1/platform/chat/threads/{sid}/turns',json=new)
            assert response.status_code == 202, response.text
            await wait(runtime,response.json()['id'],'completed')
            assert len(calls) == 2 and calls[-1]['messages'][1]['content'] == 'hello'
        with pytest.raises(RevisionConflictError):
            repo.replace_content(sid,expected_revision=revision,metadata={},messages=())
    finally:
        release.set(); await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_restart_reuses_completed_model_step_without_invoking_again(runtime):
    repo, sid, revision = prepared(runtime)
    run = turns.submit(runtime,repo,sid,**payload(revision))
    # Simulate a process stopping after model output commit and before answer commit.
    runtime.agents.claim_next()
    from ai2apps.agents.models import RunStepStatus
    step, _ = runtime.agents.create_step(run.id,action_key='reply',kind='model',input=payload(revision)['request'])
    runtime.agents.settle_step(step.id,status=RunStepStatus.COMPLETED,output=result())
    calls=[]
    async def model(request): calls.append(request); return result('must not be used')
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.agent_runtime.start()
    try:
        await wait(runtime,run.id,'completed')
        assert not calls
        assert repo.get_content(sid).messages[-1].content == 'hello'
    finally: await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_cancel_and_error_are_not_saved_as_success(runtime):
    repo,sid,revision=prepared(runtime)
    entered=asyncio.Event()
    async def model(request): entered.set(); await asyncio.Event().wait()
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.agent_runtime.start()
    try:
        run=turns.submit(runtime,repo,sid,**payload(revision))
        await asyncio.wait_for(entered.wait(),5)
        runtime.agent_runtime.cancel(run.id)
        await runtime.agent_runtime.wait_for_idle()
        assert runtime.agents.get_run(run.id).status.value=='cancelled'
        assert len(repo.get_content(sid).messages)==1
        async def empty(request): return result('')
        runtime.agent_runtime.bind_model_provider(empty)
        run=turns.submit(runtime,repo,sid,**payload(revision,'empty'))
        for _ in range(300):
            if runtime.agents.get_run(run.id).status.value=='failed': break
            await asyncio.sleep(.01)
        assert runtime.agents.get_run(run.id).error['code']=='empty_chat_reply'
        assert len(repo.get_content(sid).messages)==1
    finally: await runtime.agent_runtime.stop()


def test_ownership_scope_idempotency_and_parameter_guards(runtime):
    repo,sid,revision=prepared(runtime)
    run=turns.submit(runtime,repo,sid,**payload(revision))
    assert turns.submit(runtime,repo,sid,**payload(revision)).id==run.id
    with pytest.raises(ResourceConflictError):turns.submit(runtime,repo,sid,**payload(revision,'second'))
    with pytest.raises(ResourceConflictError):turns.submit(runtime,repo,sid,**payload(revision,text='changed'))
    with pytest.raises(ValueError):turns.submit(runtime,repo,sid,**{**payload(revision),'request':{'model':'fixture','messages':[], 'tools':[]}})
    foreign=ChatRepository(runtime.database,runtime.events,principal=replace(RequestPrincipal.legacy_local(),actor_user_id='different-owner',client_scope='owner-home'))
    from ai2apps.core import ResourceNotFoundError
    with pytest.raises(ResourceNotFoundError):turns.get(runtime,foreign,sid,run.id)


def test_concurrent_duplicate_creates_one_durable_turn(runtime):
    from concurrent.futures import ThreadPoolExecutor
    repo,sid,revision=prepared(runtime)
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids=list(pool.map(lambda _:turns.submit(runtime,repo,sid,**payload(revision)).id,range(4)))
    assert len(set(ids))==1


def test_stream_preview_is_bounded_and_excludes_tool_arguments():
    from ai2apps.agents.model_stream import ChatCompletionStreamAccumulator
    stream=ChatCompletionStreamAccumulator()
    stream.add({'ai2apps_metrics':{'prefill_tps':123},'choices':[{'delta':{'content':'abcdefgh',
        'reasoning_content':'reason','tool_calls':[{'index':0,'function':{'name':'x','arguments':'secret'}}]}}]})
    assert stream.preview(4)=={'content':'efgh','reasoning_content':'ason'}
    assert stream.metrics=={'prefill_tps':123}
    assert stream.result()['choices'][0]['message']['content']=='abcdefgh'


@pytest.mark.asyncio
async def test_disconnect_does_not_affect_progress_or_completion(runtime):
    repo,sid,revision=prepared(runtime)
    entered,release=asyncio.Event(),asyncio.Event()
    async def model(request,report,owner):
        await report({'phase':'model_streaming','text':'Receiving answer',
                      'content':{'completion_preview':{'content':'partial','reasoning_content':'thinking'},
                                 'metrics':{'prefill_tps':123}}})
        entered.set();await release.wait();return result()
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.agent_runtime.start()
    try:
        run=turns.submit(runtime,repo,sid,**payload(revision))
        await asyncio.wait_for(entered.wait(),5)
        state=turns.snapshot(runtime,runtime.agents.get_run(run.id))
        assert state['status_line']['content']['completion_preview']['content']=='partial'
        release.set();await wait(runtime,run.id,'completed')
        with runtime.database.transaction() as db:
            assert db.execute('SELECT status,output_json FROM agent_runs WHERE id=?',(run.id,)).fetchone()['status']=='completed'
        assert len(repo.get_content(sid).messages)==2
    finally:release.set();await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_regenerate_stays_with_original_user_turn_and_preserves_later_turns(runtime):
    repo,sid,revision=prepared(runtime)
    async def model(request):return result()
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.agent_runtime.start()
    try:
        first=turns.submit(runtime,repo,sid,**payload(revision))
        await wait(runtime,first.id,'completed')
        saved=repo.get_content(sid)
        updated=repo.replace_content(sid,expected_revision=saved.thread.session.revision,metadata={},messages=(
            *saved.messages,LegacyChatMessageInput(MessageRole.USER,'later question',{'id':'user-2'}),
            LegacyChatMessageInput(MessageRole.ASSISTANT,'later answer',{})))
        async def regenerated(request):return result('new first answer')
        runtime.agent_runtime.bind_model_provider(regenerated)
        run=turns.submit(runtime,repo,sid,**payload(updated.thread.session.revision,'regenerate'),
            anchor_message_id='user-1',presentation={'profileName':'test profile'})
        await wait(runtime,run.id,'completed')
        messages=repo.get_content(sid).messages
        assert [m.content for m in messages]==['hi','hello','new first answer','later question','later answer']
        assert messages[0].metadata['_activeVariantId']==messages[2].metadata['id']
        assert messages[2].metadata['meta']['profileName']=='test profile'
    finally:await runtime.agent_runtime.stop()
