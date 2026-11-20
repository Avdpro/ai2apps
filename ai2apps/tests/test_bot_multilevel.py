"""C4.1 actual Todo/Run/SQLite/approvals, with deterministic models and effects."""
import json,asyncio
from dataclasses import replace
import pytest
from test_app_interactions import runtime,wait
from test_app_chat_durable import bind_identity,response
from test_bot_capability_discovery import setup,P
from test_bot_app_access import save
from test_bot_delegation import until
from ai2apps.messager.delegation import DELEGATE

async def start(r,*,special=False,cycle=False,extra=False):
    a,sid,calls,provider=setup(r)
    b=r.messager_bots.create('local','Middle specialist','Do bounded work')
    c=r.messager_bots.create('local','Leaf specialist','Execute leaf work')
    if extra:
        from ai2apps.services.capability_routing import CapabilityProvider
        t=r.services.get_tool('todo.get');instance=r.services.get_instance_for_service(t.service_id)
        name='independent.extra_write'
        r.services.ensure_tool(service_id=t.service_id,qualified_name=name,display_name='Extra fixture write',description='Fixture',input_schema={'type':'object','properties':{}},output_schema={'type':'object'},effects=('workspace.write',),required_capabilities=())
        async def extra_write(args,ctx):raise AssertionError('Unreviewed provider must never execute')
        p=CapabilityProvider('ai2apps.knowledge.'+name,name,'ai2apps.knowledge',extra_write,version='1',access_policy='write')
        r.app_capability_router.register(p);r.c41_extra=r.app_capability_router.providers[p.id]
        async def route(args,ctx):return await r.app_capability_router.invoke(name,args,ctx)
        r.service_registry.bind_tool(name,provider_key=instance.provider_key,handler=route)
    for bot in (a,b,c):save(r,bot)
    if extra:
        for bot in (b,c):
            service=r.messager_bot_app_access;catalog=service.catalog('local',bot['id'])
            service.save('local',bot['id'],catalog['revision'],catalog['review_hash'],[{'app_id':app,'enabled':True} for app in ('ai2apps.gallery','ai2apps.knowledge')])
    if special:r.app_capability_router.providers[provider.id]=replace(provider,access_policy='confirm')
    async def model(request):
        if 'Decide quickly' in request['messages'][0]['content']:return response(text=json.dumps({'kind':'reply' if request['messages'][-1]['content']=='hello' else 'task','text':'Hello; you can keep chatting','title':'Root goal'}))
        text='\n'.join(str(m.get('content','')) for m in request['messages'])
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        prompt=next(m['content'] for m in reversed(request['messages']) if m.get('role')=='user')
        if str(prompt).startswith('Delegated work has completed.'):
            # A host continuation consumes the returned evidence. It must not
            # route the replayed original request as another delegation.
            assert 'original_task_request' in text and 'collaboration_result' in text
            if 'Middle used leaf result' in text:return response(text='Root used the middle result')
            if 'Leaf delivered canonical output' in text:return response(text='Middle used leaf result')
            if 'Further assignment was refused' in text:return response(text='Root used the refusal result')
            raise AssertionError('Continuation did not carry the completed child result')
        if 'Execute the specific leaf work' in str(prompt) and not cycle:
            if any(x.get('created') for x in results):return response(text='Leaf delivered canonical output')
            if not any(x.get('providers') for x in results):return response('app.describe',{'capability':provider.capability})
            return response(provider.capability,{'prompt':'leaf work'})
        if 'Divide the requested work once if necessary' in str(prompt):
            if 'Leaf delivered canonical output' in text:return response(text='Middle used leaf result')
            if any('ancestor' in str(x.get('error',{})) or 'cycle' in str(x.get('error',{})) or 'Repeated unchanged' in str(x.get('error',{})) for x in results):return response(text='Further assignment was refused; no operation was submitted')
            if not any(x.get('providers') for x in results):return response('app.describe',{'capability':DELEGATE})
            return response(DELEGATE,{'target_bot_id':a['id'] if cycle else c['id'],'title':'Leaf deliverable','instructions':'Execute the specific leaf work','allow_subdelegation':cycle})
        if 'Middle used leaf result' in text:return response(text='Root used the middle result')
        if not any(x.get('providers') for x in results):return response('app.describe',{'capability':DELEGATE})
        return response(DELEGATE,{'target_bot_id':b['id'],'title':'Middle deliverable','instructions':'Divide the requested work once if necessary','allow_subdelegation':True})
    r.agent_runtime.bind_model_provider(model);await r.start_background_tasks(retention_interval_seconds=60)
    rid=r.messager_dialogue.submit(P(),a['id'],sid,'root-chain-goal','Complete the requested coordinated goal','fixture',[])
    await wait(r,rid,'completed')
    s=r.messager_bot_delegation
    root=await until(lambda:next(iter(s.work('local',a['id'])),None))
    parent=r.messager_dialogue.row(s.row(root['id'])['parent_job']);await wait(r,parent['worker_run'],'completed')
    s.decide('local',a['id'],root['id'],root['review_hash'],'approve')
    return a,b,c,sid,calls,s,root,parent

async def nested(s,a):
    try:return await until(lambda:next((x for x in s.work('local',a['id']) if x['graph'] and x['graph']['depth']==2),None))
    except AssertionError:
        with s.db.transaction() as db:rows=[dict(x) for x in db.execute('SELECT * FROM messager_bot_delegations')]
        details=[]
        for row in rows:
            if row['child_job']:
                job=s.runtime.messager_dialogue.row(row['child_job']);run=s.runtime.agents.get_run(job['worker_run']) if job['worker_run'] else None
                details.append((row['status'],job,run.error if run else None,[(x.tool_name,x.error,x.output) for x in s.runtime.agents.list_steps(run.id) if x.kind=='tool'] if run else []))
        raise AssertionError(json.dumps(details,default=str))

@pytest.mark.asyncio
async def test_three_bots_yield_resume_same_logical_tasks_and_review_only_at_origin(runtime):
    r=runtime
    try:
        a,b,c,sid,calls,s,root,parent=await start(r)
        child=await nested(s,a)
        assert child['source_bot']==b['id'] and child['target_bot']==c['id'] and child['review_bot']==a['id']
        assert s.row(root['id'])['status']=='running' and not s.row(root['id'])['resume_job'] and not calls
        with pytest.raises(PermissionError):s.decide('local',b['id'],child['id'],child['review_hash'],'approve')
        hello=r.messager_dialogue.submit(P(),a['id'],sid,'hello-while-tree-waits','hello','fixture',[]);await wait(r,hello,'completed')
        s.decide('local',a['id'],child['id'],child['review_hash'],'approve')
        ref=child['graph']['root']
        await until(lambda:s.graph.root(ref)['status']!='active')
        assert s.graph.root(ref)['status']=='completed',s.graph.root(ref)
        assert len(calls)==1 and s.row(root['id'])['status']==s.row(child['id'])['status']=='resumed'
        middle_original=r.messager_dialogue.row(s.row(root['id'])['child_job']);middle_resume=r.messager_dialogue.row(s.row(child['id'])['resume_job'])
        assert middle_original['worker_session']==middle_resume['worker_session']
        root_resume=r.messager_dialogue.row(s.row(root['id'])['resume_job'])
        assert root_resume['worker_session']==parent['worker_session']
        assert any('Root used the middle result' in str(x) for x in r.app_chat.message_page(P(),sid)['items'])
        with r.database.transaction() as db:
            assert db.execute('SELECT count(*) FROM messager_delegation_edges').fetchone()[0]==2
            assert db.execute('SELECT count(*),sum(tokens) FROM messager_delegation_leases').fetchone()[1]==256_000
        s.recover();assert len(calls)==1
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_leaf_sensitive_interaction_is_same_run_at_initial_and_receiver_dialogues(runtime):
    r=runtime
    try:
        a,b,c,sid,calls,s,root,parent=await start(r,special=True);child=await nested(s,a)
        access=r.messager_bot_app_access
        access.set_approval_rule('local',a['id'],'ai',0)
        access.set_approval_rule('local',b['id'],'always',0)
        s.decide('local',a['id'],child['id'],child['review_hash'],'approve')
        card=await until(lambda:next((x for x in s.work('local',a['id']) if x['id']==child['id'] and x['runs']),None))
        leaf=r.messager_dialogue.row(s.row(child['id'])['child_job'])
        frozen=r.app_chat.execution_authorization(leaf['worker_run'])
        scope=r.app_chat.binding(leaf['worker_session'])['scope']
        tree=access.tree.context('local',scope,frozen)
        assert access.tree.approval_chain('local',scope,frozen,tree)['mode']=='always'
        origin=next(x for x in r.messager_dialogue.snapshot(P(),a['id'],sid)['runs'] if x.get('delegation_id')==child['id'])
        receiver=next(x for x in r.messager_dialogue.snapshot(P(),c['id'],leaf['source_session'])['runs'] if x.get('delegation_id')==child['id'])
        assert origin['id']==receiver['id']==leaf['worker_run'] and origin['interactions'][0]['id']==receiver['interactions'][0]['id']
        assert origin['interactions'][0]['schema']['properties']['scope']['enum']==['once'] and not calls
        item=origin['interactions'][0]
        r.agents.respond_interaction(origin['id'],item['id'],response_id='review-leaf-once',response={'decision':'approve','scope':'once'});r.agent_runtime.wake()
        await until(lambda:s.graph.root(child['graph']['root'])['status']=='completed');assert len(calls)==1
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_ancestor_bot_assignment_uses_a_new_work_item(runtime):
    r=runtime
    try:
        a,b,c,sid,calls,s,root,parent=await start(r,cycle=True)
        child=await nested(s,a)
        assert child['target_bot']==a['id'] and child['status']=='pending' and not calls
        assert s.graph.work(child['id'])['source_task']!=s.graph.work(child['id'])['target_task']
        s.decide('local',a['id'],child['id'],child['review_hash'],'approve')
        await until(lambda:s.graph.root(root['graph']['root'])['status']!='active')
        # The returned researcher may not decompose the exact original work again.
        run=r.messager_dialogue.row(s.row(child['id'])['child_job'])
        assert any('Repeated unchanged work' in str(x.error) for x in r.agents.list_steps(run['worker_run']))
        assert not calls
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_root_cancel_stops_pending_descendants_and_never_replays(runtime):
    r=runtime
    try:
        a,b,c,sid,calls,s,root,parent=await start(r);child=await nested(s,a)
        await s.cancel('local',a['id'],root['id'])
        assert s.graph.root(root['graph']['root'])['status']=='stopped'
        assert s.row(root['id'])['status']==s.row(child['id'])['status']=='cancelled' and not calls
        s.recover();assert not s.row(child['id'])['child_job'] and not calls
        with pytest.raises(PermissionError):s.graph.reserve(s.row(root['id']),'new-lease-after-stop')
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_shared_invocations_and_base_reservations_remain_bounded(runtime):
    r=runtime
    try:
        a,b,c,sid,calls,s,root,parent=await start(r,special=True);child=await nested(s,a)
        s.decide('local',a['id'],child['id'],child['review_hash'],'approve')
        await until(lambda:next((x for x in s.work('local',a['id']) if x['id']==child['id'] and x['runs']),None))
        job=r.messager_dialogue.row(s.row(child['id'])['child_job'])
        ctx=r.tools.context_for_session(caller_id='fixture',session_id=job['worker_session'],trace_id=job['worker_run'])
        graph=s.graph;ref=child['graph']['root']
        with r.database.transaction() as db:used=db.execute('SELECT count(*) FROM messager_delegation_calls WHERE root=?',(ref,)).fetchone()[0]
        for n in range(36-used):
            bound=replace(ctx,invocation_id='fixture-call-'+str(n))
            with graph.scope(bound):pass
            with graph.scope(bound):pass
        with pytest.raises(PermissionError,match='Tool budget'):
            with graph.scope(replace(ctx,invocation_id='one-too-many')):pass
        with r.database.transaction() as db:assert db.execute('SELECT count(*) FROM messager_delegation_calls WHERE root=?',(ref,)).fetchone()[0]==36
        # The remaining immutable round leases cannot exceed the same root cap.
        count=0
        while True:
            try:graph.reserve(s.row(child['id']),'fixture-round-'+str(count));count+=1
            except PermissionError as e:assert 'model allowance' in str(e);break
        with r.database.transaction() as db:assert db.execute('SELECT sum(tokens) FROM messager_delegation_leases WHERE root=?',(ref,)).fetchone()[0]==512_000
        assert not calls
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_stopped_root_recovers_child_cleanup_without_replaying_effects(runtime,monkeypatch):
    r=runtime
    try:
        a,b,c,sid,calls,s,root,parent=await start(r);child=await nested(s,a);ref=child['graph']['root']
        original=s.stop
        def crash(*args,**kwargs):raise RuntimeError('fixture crash after durable root stop')
        monkeypatch.setattr(s,'stop',crash)
        with pytest.raises(RuntimeError):s.graph.stop(ref,'Original reviewed stop reason')
        monkeypatch.setattr(s,'stop',original)
        assert s.graph.root(ref)['status']=='stopped' and s.row(child['id'])['status']=='pending'
        s.recover();s.recover()
        assert s.row(child['id'])['status']==s.row(root['id'])['status']=='cancelled' and not calls
        with r.database.transaction() as db:assert db.execute('SELECT reason FROM messager_delegation_stops WHERE root=?',(ref,)).fetchone()[0]=='Original reviewed stop reason'
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_independent_roots_may_use_the_same_bots_in_opposite_directions(runtime):
    r=runtime
    try:
        a,b,c,sid,calls,s,root,parent=await start(r)
        bsid=r.app_chat.open(P(),'ai2apps.messager.bots',{'bot_id':b['id']},{})
        candidate={'id':'fixture-opposite-edge','actor':'local','source_bot':b['id'],'target_bot':a['id'],'source_session':bsid,'parent_job':'fixture-independent-job','value_json':json.dumps({'root_run':'fixture-independent-root','work_fingerprint':'different-work'})}
        with r.database.transaction(write=True) as db:
            s.graph.insert(db,candidate,None,'fixture-independent-logical-task')
        assert s.graph.work(candidate['id'])['source_task']!=s.graph.work(root['id'])['target_task']
        assert not calls
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_reviewed_depth_limit_prevents_transfer_of_delegate_controls(runtime,monkeypatch):
    from ai2apps.messager.delegation_graph import POLICY
    monkeypatch.setitem(POLICY,'max_depth',1)
    r=runtime
    try:
        a,b,c,sid,calls,s,root,parent=await start(r)
        assert root['graph_policy']['max_depth']==1
        row=s.row(root['id']);assert not s.graph.can_delegate(row)
        job=await until(lambda:(j if (j:=r.messager_dialogue.row(s.row(root['id'])['child_job']))['worker_run'] else None))
        frozen=r.app_chat.execution_authorization(job['worker_run'])
        assert set(frozen['controls'])=={r.messager_bots.memory_returns.provider.id} and not calls
        assert DELEGATE not in {p.capability for p in s.child_exports({'bot_id':b['id'],'dialogue_job':job['id']})}
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_descendant_inherits_middle_access_without_widening_root(runtime):
    r=runtime
    try:
        a,b,c,sid,calls,s,root,parent=await start(r,extra=True);child=await nested(s,a)
        extra=r.c41_extra
        assert r.messager_bot_app_access.granted('local',b['id'],extra) and r.messager_bot_app_access.granted('local',c['id'],extra)
        assert not r.messager_bot_app_access.granted('local',a['id'],extra)
        upstream=json.loads(s.row(root['id'])['value_json'])['allowed'];downstream=json.loads(s.row(child['id'])['value_json'])['allowed']
        assert upstream[extra.id]==downstream[extra.id]==extra.version
        assert extra.id not in r.app_chat.execution_authorization(parent['worker_run'])['task_tree_providers']
        assert not calls
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_stop_cleanup_recovers_after_edges_terminal_before_task_halt(runtime,monkeypatch):
    r=runtime
    try:
        a,b,c,sid,calls,s,root,parent=await start(r);child=await nested(s,a);ref=child['graph']['root']
        original=r.messager_dialogue.sessions.halt
        def crash(*args,**kwargs):raise RuntimeError('fixture halt crash')
        monkeypatch.setattr(r.messager_dialogue.sessions,'halt',crash)
        with pytest.raises(RuntimeError):s.graph.stop(ref,'Keep original cleanup reason')
        # Narrow gap after edge-state cleanup but before task/Run cleanup.
        with r.database.transaction(write=True) as db:
            db.execute("UPDATE messager_bot_delegations SET status='cancelled' WHERE id IN (SELECT id FROM messager_delegation_edges WHERE root=?)",(ref,))
        monkeypatch.setattr(r.messager_dialogue.sessions,'halt',original)
        s.recover()
        assert r.messager_dialogue.sessions.for_job(parent['id'])['halted'] and not calls
        assert r.messager_dialogue.sessions.for_job(s.row(root['id'])['child_job'])['halted']
    finally:await r.stop_background_tasks()
