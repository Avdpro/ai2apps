"""Real delegation/SQLite/Todo lanes with fixture model and business output."""
import json
import pytest
from test_app_chat_durable import bind_identity,response
from test_app_interactions import runtime
from test_bot_delegation import start,until
from ai2apps.messager.memory_returns import RETURN
from agent_context_fixtures import owner_context

async def returned(r,*,duplicate=False,resource=False,clear_during_publish=False,two_sources=False):
    bot,target,sid,calls,provider,card,parent=await start(r)
    if resource:
        from dataclasses import replace
        async def output(args,ctx):
            from pathlib import Path
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.txt') as f:
                f.write(b'fixture resource');f.flush()
                a=r.workspace.import_artifact(ctx.session_id,Path(f.name),name='finding.txt',media_type='text/plain')
            calls.append(a.id);return {'created':'fixture-output','artifact_id':a.id}
        r.app_capability_router.providers[provider.id]=replace(provider,handler=output)
    async def model(request):
        text='\n'.join(str(m.get('content','')) for m in request['messages'])
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        if owner_context(request).get('collaboration_result'):return response(text='Parent delivered result')
        offers=[x for x in results if x.get('return_ids')]
        created=[x for x in results if x.get('created')]
        if offers and (not two_sources or len(offers)>=2):return response(text='Child done')
        if two_sources and len(offers)==1 and len(created)==1:return response(provider.capability,{'prompt':'second independent task observation'})
        if created:
            evidence_id=provider.capability
            if two_sources:
                with r.database.transaction() as db:worker=db.execute("SELECT worker_run FROM messager_dialogue_jobs WHERE bot_id=? AND worker_run IS NOT NULL ORDER BY rowid DESC LIMIT 1",(target['id'],)).fetchone()[0]
                evidence_id=[step.id for step in r.agents.list_steps(worker) if step.tool_name==provider.capability and step.status.value=='completed'][-1]
            return response(RETURN,{'items':[{'subject':'task finding','predicate':'result','text':'Delegated fixture finding','value':'fixture-output','evidence_kind':'tool_step','evidence_id':evidence_id,'quote':'fixture-output',**({'kind':'resource','artifact_id':next(x['artifact_id'] for x in results if x.get('artifact_id'))} if resource else {})}]*(2 if duplicate else 1)})
        if not any(x.get('providers') for x in results):return response('app.describe',{'capability':provider.capability})
        return response(provider.capability,{'prompt':'fixture task'})
    if clear_during_publish:
        service=r.messager_bots.memory_returns;original=service.valid;triggered=[]
        def invalidate_gap(row,**kw):
            if not triggered and r.agents.get_run(row['worker_run']).status.value=='completed':
                triggered.append(True);r.messager_bots.memory.clear('local',bot['id'])
            return original(row,**kw)
        service.valid=invalidate_gap
    r.agent_runtime.bind_model_provider(model)
    s=r.messager_bot_delegation;s.decide('local',bot['id'],card['id'],card['review_hash'],'approve')
    await until(lambda:s.row(card['id'])['status']=='resumed')
    if not clear_during_publish:await until(lambda:r.messager_bots.memory_tasks.pending('local',bot['id'])['items'])
    return bot,target,sid,card

@pytest.mark.asyncio
async def test_review_merge_idempotence_provenance_and_source_withdrawal(runtime):
    try:
        bot,target,sid,card=await returned(runtime,duplicate=True)
        m=runtime.messager_bots.memory_tasks;returns=runtime.messager_bots.memory_returns
        pending=m.pending('local',bot['id'])['items'];assert len(pending)==1
        item=pending[0];assert item['state']=='review' and item['provenance']['source_valid']
        assert item['provenance']['path']==[target['id'],bot['id']]
        assert item['provenance']['title']=='Child output'
        assert not runtime.messager_bots.memory.context('local',bot['id'])
        with pytest.raises(PermissionError):m.decide('local',target['id'],item['id'],'confirm')
        m.decide('local',bot['id'],item['id'],'confirm');m.decide('local',bot['id'],item['id'],'confirm')
        await until(lambda:runtime.messager_bots.memory.context('local',bot['id']))
        rows=runtime.messager_bots.memory.context('local',bot['id']);assert len(rows)==1
        with runtime.database.transaction() as db:
            packet=dict(db.execute('SELECT * FROM messager_memory_returns').fetchone())
            source=json.loads(db.execute('SELECT source_json FROM messager_memory_evidence WHERE memory_id=?',(rows[0]['id'],)).fetchone()[0])
        assert packet['state']=='applied' and source['kind']=='delegated_memory'
        returns.publish(runtime.messager_bot_delegation.row(card['id']),None);returns.recover()
        assert len(runtime.messager_bots.memory.context('local',bot['id']))==1
        runtime.messager_bots.memory.clear('local',target['id'])
        assert not runtime.messager_bots.memory.context('local',bot['id'])
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_withdrawn_source_cannot_be_approved_or_replayed(runtime):
    try:
        bot,target,sid,card=await returned(runtime)
        m=runtime.messager_bots.memory_tasks;item=m.pending('local',bot['id'])['items'][0]
        runtime.messager_bots.memory.clear('local',target['id'])
        with pytest.raises(ValueError):m.decide('local',bot['id'],item['id'],'confirm')
        runtime.messager_bots.memory_returns.recover()
        assert not m.pending('local',bot['id'])['items']
        assert not runtime.messager_bots.memory.context('local',bot['id'])
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_parent_cancellation_does_not_restore_candidate(runtime):
    try:
        bot,target,sid,card=await returned(runtime)
        m=runtime.messager_bots.memory_tasks;item=m.pending('local',bot['id'])['items'][0]
        m.decide('local',bot['id'],item['id'],'cancel');m.decide('local',bot['id'],item['id'],'cancel')
        runtime.messager_bots.memory_returns.publish(runtime.messager_bot_delegation.row(card['id']),None)
        assert not m.pending('local',bot['id'])['items']
        with pytest.raises(ValueError):m.decide('local',bot['id'],item['id'],'confirm')
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_resource_transfers_only_after_approval_and_keeps_exact_bytes(runtime):
    try:
        bot,target,sid,card=await returned(runtime,resource=True)
        m=runtime.messager_bots.memory_tasks;item=m.pending('local',bot['id'])['items'][0]
        assert not [a for a in runtime.workspace.list_artifacts(sid) if a.metadata.get('memory_return')]
        m.decide('local',bot['id'],item['id'],'confirm')
        await until(lambda:runtime.messager_bots.memory.context('local',bot['id']))
        copies=[a for a in runtime.workspace.list_artifacts(sid) if a.metadata.get('memory_return')]
        assert len(copies)==1 and runtime.workspace.artifact_path(copies[0]).read_bytes()==b'fixture resource'
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_fabricated_evidence_private_controls_and_return_loops_are_rejected(runtime):
    from types import SimpleNamespace
    from ai2apps.messager.memory_returns import Offer
    try:
        bot,target,sid,card=await returned(runtime)
        s=runtime.messager_bot_delegation;edge=s.row(card['id']);job=runtime.messager_dialogue.row(edge['child_job']);run=runtime.agents.get_run(job['worker_run'])
        returns=runtime.messager_bots.memory_returns
        base={'subject':'finding','predicate':'result','text':'untrusted claim','value':'invented','evidence_kind':'tool_step','evidence_id':'nonexistent','quote':'invented'}
        with pytest.raises(PermissionError):returns.proof(Offer(**base),edge,job,run)
        private=runtime.messager_bots.memory.records.apply('local',target['id'],request_id='private-note',subject='finding',predicate='result',value='invented',text='private note')
        with pytest.raises(PermissionError):returns.proof(Offer(**{**base,'evidence_kind':'memory_change','evidence_id':private['change_id']}),edge,job,run)
        with pytest.raises(PermissionError):returns.proof(Offer(**{**base,'evidence_kind':'return','evidence_id':next(iter(runtime.messager_bots.memory_tasks.pending('local',bot['id'])['items']))['provenance']['return_id']}),edge,job,run)
        with pytest.raises(PermissionError):returns.edge(SimpleNamespace(invocation_id=None,session_id=sid,trace_id=run.id,actor_user_id='local'))
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_multilevel_return_preserves_origin_and_never_forwards_before_review(runtime):
    import asyncio
    from test_bot_multilevel import start as tree,nested
    try:
        a,b,c,sid,calls,s,root,parent=await tree(runtime)
        leaf=await nested(s,a);approved=asyncio.Event()
        provider=next(p for p in runtime.app_capability_router.providers.values() if p.capability=='fixture.paint')
        async def model(request):
            text='\n'.join(str(m.get('content','')) for m in request['messages'])
            results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
            if owner_context(request).get('name') == 'Leaf specialist':
                if any(x.get('return_ids') for x in results):return response(text='Leaf complete')
                if any(x.get('created') for x in results):return response(RETURN,{'items':[{'subject':'finding','predicate':'result','text':'finding','value':'fixture-output','evidence_kind':'tool_step','evidence_id':provider.capability,'quote':'fixture-output'}]})
                if not any(x.get('providers') for x in results):return response('app.describe',{'capability':provider.capability})
                return response(provider.capability,{'prompt':'fixture leaf'})
            if owner_context(request).get('name') == 'Middle specialist':
                await asyncio.wait_for(approved.wait(),15)
                if any(x.get('return_ids') for x in results):return response(text='Middle complete')
                with runtime.database.transaction() as db:prior=dict(db.execute('SELECT * FROM messager_memory_returns WHERE parent_bot=?',(b['id'],)).fetchone())
                return response(RETURN,{'items':[{'subject':'finding','predicate':'result','text':'finding','value':'fixture-output','evidence_kind':'return','evidence_id':prior['id']}]})
            return response(text='Root complete')
        runtime.agent_runtime.bind_model_provider(model)
        s.decide('local',a['id'],leaf['id'],leaf['review_hash'],'approve')
        m=runtime.messager_bots.memory_tasks
        await until(lambda:m.pending('local',b['id'])['items'])
        assert not m.pending('local',a['id'])['items']
        item=m.pending('local',b['id'])['items'][0];m.decide('local',b['id'],item['id'],'confirm');approved.set()
        await until(lambda:m.pending('local',a['id'])['items'])
        inherited=m.pending('local',a['id'])['items'][0]
        assert inherited['provenance']['path']==[c['id'],b['id'],a['id']]
        assert inherited['provenance']['proof']['kind']=='return'
        runtime.messager_bots.memory.clear('local',c['id'])
        with pytest.raises(ValueError):m.decide('local',a['id'],inherited['id'],'confirm')
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_local_confirmation_survives_source_withdrawal_and_undo_prevents_replay(runtime):
    try:
        bot,target,sid,card=await returned(runtime)
        m=runtime.messager_bots.memory_tasks;item=m.pending('local',bot['id'])['items'][0]
        m.decide('local',bot['id'],item['id'],'confirm')
        await until(lambda:runtime.messager_bots.memory.context('local',bot['id']))
        records=runtime.messager_bots.memory.records
        with runtime.database.transaction() as db:mid=db.execute("SELECT id FROM messages WHERE session_id=? AND role='user' ORDER BY rowid LIMIT 1",(sid,)).fetchone()[0]
        local=records.apply('local',bot['id'],request_id='local-evidence',subject='task finding',predicate='result',value='fixture-output',text='fixture-output',source={'session_id':sid,'message_id':mid})
        runtime.messager_bots.memory.clear('local',target['id'])
        assert len(runtime.messager_bots.memory.context('local',bot['id']))==1
        records.undo('local',bot['id'],local['change_id'],request_id='undo-local-evidence')
        assert not runtime.messager_bots.memory.context('local',bot['id'])
        runtime.messager_bots.memory_returns.recover()
        assert not m.pending('local',bot['id'])['items']
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_clear_between_projection_check_and_commit_does_not_recreate_candidate(runtime):
    try:
        bot,target,sid,card=await returned(runtime,clear_during_publish=True)
        assert not runtime.messager_bots.memory_tasks.pending('local',bot['id'])['items']
        runtime.messager_bots.memory_returns.recover()
        assert not runtime.messager_bots.memory.context('local',bot['id'])
        with runtime.database.transaction() as db:assert db.execute('SELECT state FROM messager_memory_returns').fetchone()[0]=='stale'
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_same_value_merge_keeps_other_valid_delegated_evidence(runtime):
    try:
        bot,target,sid,card=await returned(runtime,two_sources=True)
        m=runtime.messager_bots.memory_tasks
        await until(lambda:len(m.pending('local',bot['id'])['items'])==2)
        items=m.pending('local',bot['id'])['items']
        for item in items:
            m.decide('local',bot['id'],item['id'],'confirm')
            await until(lambda:not any(x['id']==item['id'] for x in m.pending('local',bot['id'])['items']))
        returns=runtime.messager_bots.memory_returns
        with runtime.database.transaction() as db:packets=[dict(x) for x in db.execute('SELECT * FROM messager_memory_returns')]
        assert len(packets)==2 and all(returns.valid(p) for p in packets)
        assert len(runtime.messager_bots.memory.context('local',bot['id']))==1
        records=runtime.messager_bots.memory.records
        with runtime.database.transaction() as db:change=db.execute('SELECT change_id FROM messager_memory_candidates WHERE id=?',(items[-1]['id'],)).fetchone()[0]
        records.undo('local',bot['id'],change,request_id='undo-second-source')
        assert len(runtime.messager_bots.memory.context('local',bot['id']))==1
        assert returns.valid(returns.row(items[0]['provenance']['return_id']))
    finally:await runtime.stop_background_tasks()
