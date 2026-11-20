"""Lossless appended state; arbitrary owners, no business-specific selection."""
from copy import deepcopy
from types import SimpleNamespace as NS
import json
import pytest
from test_app_interactions import runtime
from ai2apps.agents.context_history import snapshot_changes, PROFILE, PROFILE_KEY
from ai2apps.agents.session_memory import SessionMemory
from ai2apps.storage.repositories import SessionRepository
from test_aaat_execution_flow import new_run


def apply(previous, changes):
    value = deepcopy(previous)
    for change in changes:
        path = change['path']
        if not path:
            if change['op']=='set':value=deepcopy(change['value']);continue
            target=value
        else:
            target=value
            for part in path[:-1]:target=target[part]
        if change['op']=='set':target[path[-1]]=deepcopy(change['value'])
        elif change['op']=='remove':del target[path[-1]]
        else:
            if path:target=target[path[-1]]
            start=change['start'];target[start:start+change['delete']]=deepcopy(change['items'])
    return value


@pytest.mark.parametrize('owner',['unrelated.alpha','arbitrary.beta'])
def test_snapshot_lossless_append_restart_and_compaction_fallback(runtime,owner):
    parent=SessionRepository(runtime.database).get(new_run(runtime,[]).session_id)
    sid=SessionRepository(runtime.database,runtime.events).create(app_instance_id=parent.app_instance_id,metadata={PROFILE_KEY:PROFILE}).id
    memory=SessionMemory(runtime.database,runtime.events,lambda item:None)
    context=lambda rid:NS(run=NS(id=rid,session_id=sid))
    old={'owner':owner,'facts':{'text':'stable material '*2000,'flag':True},'items':[{'id':1,'note':'N'*4000}]}
    full=memory.freeze_state_snapshot(context('r1'),'ui',old,[])
    current=deepcopy(old);current['facts']['flag']=False;current['items'].insert(0,{'id':2,'status':'failed','error':'actual failure'})
    changed=memory.freeze_state_snapshot(context('r2'),'ui',current,[full])
    assert 'snapshot delta' in changed['content'] and len(changed['content'])<len(full['content'])/10
    delta=json.loads(changed['content'][changed['content'].index('{'):])
    assert delta['base_snapshot']=='r1' and apply(old,delta['changes'])==current
    recovered=SessionMemory(runtime.database,runtime.events,lambda item:None)
    assert recovered.freeze_state_snapshot(context('r2'),'ui',{},[])==changed
    third=deepcopy(current);del third['facts']['flag'];third['items'][1]['id']=3
    next_view=recovered.freeze_state_snapshot(context('r3'),'ui',third,[full,changed])
    delta=json.loads(next_view['content'][next_view['content'].index('{'):]);assert apply(current,delta['changes'])==third
    # Even if the most recent delta survived compaction, its full chain must remain.
    reset=recovered.freeze_state_snapshot(context('r4'),'ui',third,[changed,next_view])
    assert 'snapshot delta' not in reset['content'] and json.loads(reset['content'].split(': ',1)[1])==third
    assert json.loads(full['content'].split(': ',1)[1])==old


def test_snapshot_operations_and_old_sessions(runtime):
    pairs=[({'a':1},{'b':2}),([1,2,3],[1,4,5,3]),([1,2],[1]),({},[]),([{'x':1}],[{'x':2}]),({'x':None},{}),([],[])]
    for old,new in pairs:assert apply(old,snapshot_changes(old,new))==new
    sid=new_run(runtime,[]).session_id
    m=SessionMemory(runtime.database,runtime.events,lambda item:None)
    ctx=NS(run=NS(id='old',session_id=sid))
    state={'owner':'any','unchanged':'X'*4000}
    first=m.freeze_state_snapshot(ctx,'ui',state,[])
    assert m.freeze_state_snapshot(NS(run=NS(id='old2',session_id=sid)),'ui',state,[first])==first
    with runtime.database.transaction() as connection:
        assert not m._events(connection,sid,('agent.context.history.prelude',))
