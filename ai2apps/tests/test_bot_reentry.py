"""C4.1.1 work-level dependency safety; real scheduler, fixture models/effects."""
import json
import pytest
from test_app_interactions import runtime,wait
from test_app_chat_durable import bind_identity,response
from test_bot_capability_discovery import setup,P
from test_bot_app_access import save
from test_bot_delegation import until
from ai2apps.messager.delegation import DELEGATE
from agent_context_fixtures import owner_context

async def chain(r,*,via_middle=False,tool_calls=1):
    a,sid,calls,provider=setup(r);save(r,a)
    b=r.messager_bots.create('local','Middle researcher','Decompose the subtopic');save(r,b)
    targets=r.messager_bot_communication.targets('local',a['id'])
    assert targets[0]['id']==a['id'] and targets[0]['is_self'] and targets[0]['delegation_available'] and not targets[0]['consultation_available']
    requests=[]
    async def model(request):
        if 'Decide quickly' in request['messages'][0]['content']:return response(text=json.dumps({'kind':'task','text':'Queued','title':'Main research'}))
        text='\n'.join(str(m.get('content','')) for m in request['messages']);requests.append((owner_context(request),text))
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        if owner_context(request).get('collaboration_result'):return response(text='Integrated actual subtopic result')
        if owner_context(request).get('name') == 'Middle researcher':
            if not any(x.get('providers') for x in results):return response('app.describe',{'capability':DELEGATE})
            return response(DELEGATE,{'target_bot_id':a['id'],'title':'Narrow subtopic','instructions':'Study the supplied narrow subtopic','deliverable':'Evidence table'})
        if owner_context(request).get('delegated_task'):
            if sum(bool(x.get('created')) for x in results)>=tool_calls:return response(text='Narrow subtopic result')
            if not any(x.get('providers') for x in results):return response('app.describe',{'capability':provider.capability})
            return response(provider.capability,{'prompt':'subtopic evidence '+str(sum(bool(x.get('created')) for x in results)+1)})
        if not any(x.get('providers') for x in results):return response('app.describe',{'capability':DELEGATE})
        return response(DELEGATE,{'target_bot_id':b['id'] if via_middle else a['id'],'title':'Research child','instructions':'Decompose the broader research' if via_middle else 'Study the supplied narrow subtopic','deliverable':'Evidence table','allow_subdelegation':via_middle})
    r.agent_runtime.bind_model_provider(model);await r.start_background_tasks(retention_interval_seconds=60)
    rid=r.messager_dialogue.submit(P(),a['id'],sid,'research-goal','Research main topic with a distinct subtopic','fixture',[])
    await wait(r,rid,'completed');s=r.messager_bot_delegation
    def persisted():
        with r.database.transaction() as db:row=db.execute('SELECT id FROM messager_bot_delegations ORDER BY rowid LIMIT 1').fetchone()
        if row:
            saved=s.row(row[0]);return {**saved,'graph':s.graph.edge(row[0])}
    first=await until(persisted)
    parent=r.messager_dialogue.row(s.row(first['id'])['parent_job']);await wait(r,parent['worker_run'],'completed')
    return a,b,sid,calls,s,first,parent,requests

@pytest.mark.asyncio
@pytest.mark.parametrize('via_middle,tool_calls',[(False,1),(True,1),(False,2)])
async def test_same_bot_can_run_distinct_child_without_deadlock_or_private_history(runtime,via_middle,tool_calls):
    r=runtime
    try:
        a,b,sid,calls,s,first,parent,requests=await chain(r,via_middle=via_middle,tool_calls=tool_calls)
        if via_middle:assert not calls
        s.decide('local',a['id'],first['id'],first['review_hash'],'approve')
        leaf=first
        if via_middle:
            leaf=await until(lambda:next((x for x in s.work('local',a['id']) if x['id']!=first['id']),None))
            assert leaf['target_bot']==a['id'] and leaf['review_bot']==a['id'] and not calls
            s.decide('local',a['id'],leaf['id'],leaf['review_hash'],'approve')
        await until(lambda:s.graph.root(first['graph']['root'])['status']=='completed')
        child=r.messager_dialogue.row(s.row(leaf['id'])['child_job'])
        assert child['bot_id']==a['id'] and child['worker_session']!=parent['worker_session']
        assert r.messager_dialogue.sessions.for_job(child['id'])['id']!=r.messager_dialogue.sessions.for_job(parent['id'])['id']
        assert len(calls)==tool_calls
        if not via_middle:
            messages=r.app_chat.message_page(P(),sid)['items']
            assert sum('Narrow subtopic result' in str(m) for m in messages)==1,messages
        assert s.graph.work(leaf['id'])['source_task']!=s.graph.work(leaf['id'])['target_task']
        # Child request does not import unrelated main-conversation private history.
        child_prompts=[text for state,text in requests if state.get('delegated_task') and state.get('name') != 'Middle researcher']
        assert child_prompts and all('Research main topic with a distinct subtopic' not in x for x in child_prompts)
        s.recover();assert len(calls)==tool_calls
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_actual_task_wait_cycles_rejected_but_same_bot_work_is_not_a_cycle(runtime):
    r=runtime
    try:
        a,b,sid,calls,s,first,parent,requests=await chain(r,via_middle=True)
        work=s.graph.work(first['id'])
        with r.database.transaction() as db:
            with pytest.raises(ValueError,match='Task wait cycle'):s.graph.check_wait(db,'local',work['target_task'],work['source_task'])
            with pytest.raises(ValueError,match='Task wait cycle'):s.graph.check_wait(db,'local',work['source_task'],work['source_task'])
            s.graph.check_wait(db,'local',work['target_task'],'work:independent-fresh-child')
        assert not calls
    finally:await r.stop_background_tasks()


@pytest.mark.asyncio
async def test_work_identity_distinguishes_input_material_and_deliverable_not_title(runtime,monkeypatch):
    r=runtime
    try:
        a,b,sid,calls,s,first,parent,requests=await chain(r,via_middle=True)
        value=json.loads(s.row(first['id'])['value_json'])
        original=s.work_identity(parent,value)
        assert original==value['work_fingerprint']
        assert s.work_identity(parent,{**value,'title':'A renamed label'})==original
        assert s.work_identity(parent,{**value,'deliverable':'A table of counterexamples'})!=original
        read=r.messager_dialogue.sessions.instruction
        def material(ref):
            text,files=read(ref)
            return text,[*files,{'id':'fixture-different-authorized-source','filename':'other-study.txt'}]
        monkeypatch.setattr(r.messager_dialogue.sessions,'instruction',material)
        assert s.work_identity(parent,value)!=original and not calls
    finally:await r.stop_background_tasks()
