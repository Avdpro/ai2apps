"""Task continuation, durable feedback and retained context; deterministic model fixtures."""
import asyncio,json
from dataclasses import replace
from types import SimpleNamespace
import pytest
from test_app_chat_durable import bind_identity,response
from test_app_interactions import runtime,wait
from test_bot_capability_discovery import setup,P
from test_bot_dialogue import job_wait

async def ready(r,rid):await wait(r,rid,'completed');return r.agents.get_run(rid).output


@pytest.mark.parametrize('first_uses_tool,fixture_name,app,artifact,risk,unclear,allowed', [
    (True, 'fixture.make', 'ai2apps.gallery', True, 'low', True, True),
    (False, 'different.compose', 'ai2apps.knowledge', True, 'low', True, True),
    (False, 'fixture.make', 'ai2apps.gallery', True, 'unknown', True, False),
    (False, 'fixture.make', 'ai2apps.gallery', True, 'low', False, False),
    (False, 'fixture.make', 'ai2apps.gallery', False, 'low', True, False),
])
@pytest.mark.asyncio
async def test_task_continuation_access_and_ai_review(runtime, first_uses_tool, fixture_name, app,
                                                      artifact, risk, unclear, allowed):
    effects = ('network', 'ai.usage', 'workspace.write', 'artifact.create') if artifact else ('workspace.write',)
    bot, sid, calls, provider = setup(runtime, fixture_name, app, effects=effects)
    access = runtime.messager_bot_app_access
    access.set_approval_rule('local', bot['id'], 'ai', 0)
    service = runtime.messager_dialogue
    reviews = []
    target = None
    original = 'Create a panda illustration'
    prior_reply = 'Result and next step: 1. Retry the panda illustration'

    async def model(request):
        system = request['messages'][0]['content']
        if 'Decide quickly' in system:
            follow = request['messages'][-1]['content'] == '1'
            return response(text=json.dumps({'kind': 'continue' if follow else 'task',
                'target_session_id': target, 'text': 'ack', 'title': 'Panda',
                'step_label': 'Retry the panda illustration' if follow else 'Create illustration'}))
        if system.startswith('Review a proposed Tool invocation'):
            data = json.loads(request['messages'][1]['content'])
            reviews.append(data)
            follow = data['goal'] == '1'
            return response(text=json.dumps({'risk': risk if follow else 'low',
                'necessary': not follow, 'intent_unclear': unclear if follow else False, 'reason': 'fixture'}))
        messages = request['messages']
        latest = max(i for i, m in enumerate(messages) if m['role'] == 'user')
        prompt = messages[latest]['content']
        results = [json.loads(m['content']) for m in messages[latest + 1:] if m['role'] == 'tool']
        if prompt == original and not first_uses_tool:
            return response(text=prior_reply)
        if any(v.get('created') for v in results):
            return response(text=prior_reply if prompt == original else 'Retry result')
        if not any(v.get('providers') for v in results):
            return response('app.describe', {'capability': provider.capability})
        return response(provider.capability, {'prompt': 'panda illustration'})

    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        first = service.submit(P(), bot['id'], sid, 'approval-first', original, 'fixture', [])
        target = (await ready(runtime, first))['task_session_id']
        await job_wait(runtime, first, 'completed')
        retry = service.submit(P(), bot['id'], sid, 'approval-retry', '1', 'fixture', [], target)
        assert (await ready(runtime, retry))['task_session_id'] == target
        if allowed:
            await job_wait(runtime, retry, 'completed')
            assert len(calls) == (2 if first_uses_tool else 1)
        else:
            job = await job_wait(runtime, retry, 'running')
            await wait(runtime, job['worker_run'], 'waiting_capability')
            assert not calls
        assert len(reviews) == 1
        assert not access.granted('local', bot['id'], provider)
        if first_uses_tool:
            assert reviews[0]['goal'] == original
            assert access.tree.granted('local', retry, provider)
            assert not access.tree.granted('local', retry, replace(provider, version='changed'))
            unrelated = service.submit(P(), bot['id'], sid, 'approval-unrelated', 'Create another illustration', 'fixture', [])
            assert (await ready(runtime, unrelated))['task_session_id'] != target
            assert not access.tree.granted('local', unrelated, provider)
            await job_wait(runtime, unrelated, 'completed')
            assert len(reviews) == 2
            runtime.messager_bot_permissions.invalidate('local', bot['id'], app_id=app)
            assert not access.tree.granted('local', retry, provider)
        else:
            assert reviews[0]['goal'] == '1'
            context = reviews[0]['owner_rule']['task_context']
            assert context['task_title'] == 'Panda'
            assert context['original_request'] == original
            assert ''.join(context['previous_result_excerpt']) == prior_reply
    finally:
        await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_running_and_completed_followups_reuse_session_and_report_decisions(runtime):
    bot,sid,_,_=setup(runtime);service=runtime.messager_dialogue;entered=asyncio.Event();release=asyncio.Event();worker_calls=[];target=None
    async def model(request):
        if 'Decide quickly' in request['messages'][0]['content']:
            follow='hat' in request['messages'][-1]['content']
            return response(text=json.dumps({'kind':'continue' if follow else 'task','target_session_id':target,'text':'ack','title':'Panda'}))
        worker_calls.append(request)
        assert sum(m.get('content') == 'draw panda' for m in request['messages']) == 1
        assert not any(m.get('content','').startswith('Starting “') for m in request['messages'] if isinstance(m.get('content'),str))
        if len(worker_calls)==1:entered.set();await release.wait();return response(text='Panda result')
        assert not any(m.get('content')=='ack' for m in request['messages'])
        assert any(m.get('content')=='Panda result' for m in request['messages'])
        assert sum(m.get('content') == 'Panda result' for m in request['messages']) == 1
        return response(text='Panda wearing hat')
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        a=service.submit(P(),bot['id'],sid,'session-first','draw panda','fixture',[]);first=await ready(runtime,a);target=first['task_session_id'];await asyncio.wait_for(entered.wait(),10)
        b=service.submit(P(),bot['id'],sid,'session-next','add a hat','fixture',[]);second=await ready(runtime,b)
        assert second['decision']=='waiting' and second['task_session_id']==target
        await job_wait(runtime,b,'queued');assert len(worker_calls)==1
        release.set();ja=await job_wait(runtime,a,'completed');jb=await job_wait(runtime,b,'completed');assert ja['worker_session']==jb['worker_session'] and ja['worker_run']!=jb['worker_run']
        c=service.submit(P(),bot['id'],sid,'session-again','change the hat','fixture',[],target);third=await ready(runtime,c);assert third['decision']=='continued';jc=await job_wait(runtime,c,'completed');assert jc['worker_session']==ja['worker_session']
        messages=runtime.app_chat.message_page(P(),sid)['items'];assert any('再接着处理' in m['content'] for m in messages);assert any('接着之前的成果' in m['content'] for m in messages)
        service.recover();assert sum('这一步已完成' in m['content'] for m in runtime.app_chat.message_page(P(),sid)['items'])==1
    finally:release.set();await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_queued_amendment_merges_once_without_an_extra_execution(runtime):
    bot,sid,_,_=setup(runtime);s=runtime.messager_dialogue;entered=asyncio.Event();release=asyncio.Event();target=None;calls=[]
    async def model(request):
        if 'Decide quickly' in request['messages'][0]['content']:
            text=request['messages'][-1]['content'];return response(text=json.dumps({'kind':'continue' if text=='B addition' else 'task','target_session_id':target,'text':'ack','title':text}))
        calls.append(request)
        if len(calls)==1:entered.set();await release.wait()
        else:assert any('B addition' in str(m.get('content')) and 'B work' in str(m.get('content')) for m in request['messages'])
        return response(text='finished')
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        a=s.submit(P(),bot['id'],sid,'blocking-task','A work','fixture',[]);await ready(runtime,a);await asyncio.wait_for(entered.wait(),10)
        b=s.submit(P(),bot['id'],sid,'pending-task','B work','fixture',[]);result=await ready(runtime,b);target=result['task_session_id'];await job_wait(runtime,b,'queued')
        c=s.submit(P(),bot['id'],sid,'pending-addition','B addition','fixture',[]);out=await ready(runtime,c);assert out['decision']=='amended' and out['job_id']==result['job_id']
        with runtime.database.transaction() as db:assert db.execute('SELECT count(*) FROM messager_job_amendments WHERE source_run=?',(c,)).fetchone()[0]==1;assert not db.execute('SELECT 1 FROM messager_dialogue_jobs WHERE source_run=?',(c,)).fetchone()
        release.set();await job_wait(runtime,a,'completed');await job_wait(runtime,b,'completed');assert len(calls)==2
    finally:release.set();await runtime.stop_background_tasks()

@pytest.mark.parametrize('via_todo',[False,True])
@pytest.mark.asyncio
async def test_stop_prevents_queued_continuation_and_does_not_resume_on_new_prompt(runtime,via_todo):
    bot,sid,_,_=setup(runtime);s=runtime.messager_dialogue;entered=asyncio.Event();release=asyncio.Event();target=None;count=0
    async def model(request):
        nonlocal count
        if 'Decide quickly' in request['messages'][0]['content']:return response(text=json.dumps({'kind':'continue' if target else 'task','target_session_id':target,'text':'ack','title':'Stopped'}))
        count+=1;entered.set();await release.wait();return response(text='result')
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        a=s.submit(P(),bot['id'],sid,'stop-first','work','fixture',[]);out=await ready(runtime,a);target=out['task_session_id'];await asyncio.wait_for(entered.wait(),10)
        b=s.submit(P(),bot['id'],sid,'stop-follow','follow','fixture',[]);await ready(runtime,b)
        if via_todo:
            job=s.row(out['job_id'])
            run=next(r for r in runtime.todo.store.snapshot('local')['runs'] if r['task_id']==job['task_id'])
            await runtime.todo.cancel('local',run['id'])
            release.set();await job_wait(runtime,a,'cancelled')
            await asyncio.sleep(.2)
        else:await s.request_cancel('local',bot['id'],out['job_id']);release.set()
        c=s.submit(P(),bot['id'],sid,'stopped-prompt','continue it','fixture',[]);again=await ready(runtime,c);assert again['kind']=='clarify';assert count==1
        assert 'Stopped' in again['content'] and '如果要重新尝试' in again['content']
        with runtime.database.transaction() as db:assert not db.execute('SELECT 1 FROM messager_dialogue_jobs WHERE source_run=?',(c,)).fetchone()
    finally:release.set();await runtime.stop_background_tasks()


def test_recent_twenty_pin_archive_preserve_full_history_and_ownership(runtime):
    bot,sid,_,_=setup(runtime);s=runtime.messager_dialogue
    for i in range(24):
        ref='retained-'+str(i)
        with runtime.database.transaction(write=True) as db:db.execute("INSERT INTO messager_dialogue_jobs VALUES(?,?,?,?,?,?,'completed',NULL,NULL,NULL)",(ref,'local',bot['id'],sid,'fake-source-'+str(i),'Task '+str(i)))
        s.sessions.link(s.row(ref));s.sessions.summarize(ref,'actual result '+str(i))
    assert len(s.sessions.recent('local',bot['id'],sid))==20
    assert s.sessions.get('local',bot['id'],'retained-0')['summary']=='actual result 0'
    s.sessions.manage('local',bot['id'],'retained-0','pin');assert s.sessions.recent('local',bot['id'],sid)[0]['id']=='retained-0'
    s.sessions.manage('local',bot['id'],'retained-0','archive');assert all(v['id']!='retained-0' for v in s.sessions.recent('local',bot['id'],sid));assert s.sessions.get('local',bot['id'],'retained-0')['summary']
    s.sessions.manage('local',bot['id'],'retained-0','restore');assert s.sessions.recent('local',bot['id'],sid)[0]['id']=='retained-0'
    other=runtime.messager_bots.create('local','Other','Help')
    with pytest.raises(PermissionError):s.sessions.get('local',other['id'],'retained-0')

@pytest.mark.asyncio
async def test_task_session_browse_archive_and_actor_bound_http_api(runtime):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.messager import create_messager_router
    bot,sid,_,_=setup(runtime);s=runtime.messager_dialogue
    for i in range(22):
        ref='browse-'+str(i)
        with runtime.database.transaction(write=True) as db:db.execute("INSERT INTO messager_dialogue_jobs VALUES(?,?,?,?,?,?,'completed',NULL,NULL,NULL)",(ref,'local',bot['id'],sid,'fake-'+str(i),'Task '+str(i)))
        s.sessions.link(s.row(ref))
    app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P));base='/messager/bots/'+bot['id']
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Origin':'http://test'}) as client:
        first=await client.get(base+'/task-sessions',params={'session_id':sid});assert first.status_code==200
        assert len(first.json()['items'])==20 and first.json()['has_more']
        rest=(await client.get(base+'/task-sessions',params={'session_id':sid,'offset':20})).json();assert len(rest['items'])==2 and not rest['has_more']
        ref=first.json()['items'][0]['id']
        assert (await client.post(base+'/task-sessions/'+ref+'/archive',json={},headers={'Origin':'null'})).status_code==403
        assert (await client.post(base+'/task-sessions/'+ref+'/archive',json={})).status_code==200
        archived=(await client.get(base+'/task-sessions',params={'session_id':sid,'archived':True})).json();assert [x['id'] for x in archived['items']]==[ref]
        assert (await client.get(base+'/task-sessions/'+ref)).json()['runs'][0]['id']==ref
        assert (await client.post(base+'/task-sessions/'+ref+'/restore',json={})).status_code==200


@pytest.mark.asyncio
async def test_visible_continuation_overrides_model_target_for_this_message_only(runtime):
    bot, sid, _, _ = setup(runtime)
    service = runtime.messager_dialogue
    wrong = None

    async def model(request):
        if 'Decide quickly' not in request['messages'][0]['content']:
            return response(text='fixture result')
        text = request['messages'][-1]['content']
        return response(text=json.dumps({
            'kind': 'continue' if text.startswith('继续 /#') else 'task',
            'target_session_id': wrong, 'text': 'ack', 'title': text,
        }))

    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        first = service.submit(P(), bot['id'], sid, 'ref-first', '腕表 日报', 'fixture', [])
        selected = (await ready(runtime, first))['task_session_id']
        await job_wait(runtime, first, 'completed')
        other = service.submit(P(), bot['id'], sid, 'ref-other', 'Other task', 'fixture', [])
        wrong = (await ready(runtime, other))['task_session_id']
        await job_wait(runtime, other, 'completed')

        explicit = '继续 /#"腕表 日报" 补充新品'
        turn = service.submit(P(), bot['id'], sid, 'ref-continue', explicit, 'fixture', [])
        assert (await ready(runtime, turn))['task_session_id'] == selected
        assert service.submit(P(), bot['id'], sid, 'ref-continue', explicit, 'fixture', []) == turn
        await job_wait(runtime, turn, 'completed')

        new_topic = service.submit(P(), bot['id'], sid, 'ref-new', '参考 /#'+selected+' 新建周报', 'fixture', [])
        assert (await ready(runtime, new_topic))['task_session_id'] not in (selected, wrong)
        context = runtime.agents.get_run(new_topic).input['owner_context']
        assert context['message_task_references'] == [selected]
        assert context['selected_task_session'] is None
        await job_wait(runtime, new_topic, 'completed')

        plain = service.submit(P(), bot['id'], sid, 'ref-plain', '独立的新话题', 'fixture', [])
        assert (await ready(runtime, plain))['task_session_id'] not in (selected, wrong)
        assert runtime.agents.get_run(plain).input['owner_context']['message_task_references'] == []
    finally:
        await runtime.stop_background_tasks()


def test_reference_lookup_rejects_ambiguity_and_foreign_conversation(runtime):
    bot, sid, _, _ = setup(runtime)
    service = runtime.messager_dialogue
    other = runtime.messager_bots.create('local', 'Other Bot', 'Help')
    for ref, owner_bot in [('owned-1',bot['id']), ('owned-2',bot['id']), ('foreign-1',other['id'])]:
        with runtime.database.transaction(write=True) as db:
            db.execute("INSERT INTO messager_dialogue_jobs VALUES(?,?,?,?,?,?,'completed',NULL,NULL,NULL)",
                       (ref,'local',owner_bot,sid,'source-'+ref,'同名'))
        service.sessions.link(service.row(ref))
    assert {r['id'] for r in service.sessions.search_references('local',bot['id'],sid,'同名')} == {'owned-1','owned-2'}
    for text in ['继续 /#同名', '继续 /#foreign-1', '继续 /#"未闭合', '继续 /#']:
        with pytest.raises(ValueError):
            service.submit(P(),bot['id'],sid,'bad-reference',text,'fixture',[])
    assert service.sessions.references('local',bot['id'],sid,'示例 `/#unknown`','zh') == ([],None)
    records, target = service.sessions.references('local',bot['id'],sid,'继续 /#owned-2，补充内容','zh')
    assert [record['id'] for record in records] == [target] == ['owned-2']
