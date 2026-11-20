"""Fixture inference, real Todo, Gateway, system scheduler and SQLite persistence."""
import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from legacy_package_backend_fixture import runtime
from ai2apps.system_tasks.agent_flows import AgentFlows, Proposal
from ai2apps.services.builtin_apps import gallery
from io import BytesIO


@pytest.mark.asyncio
async def test_confirm_then_dispatch_frozen_read_and_optional_model(runtime,monkeypatch):
    flows=runtime.todo_agent_flows
    monkeypatch.setattr(flows,'model',lambda tier,profile:'fixture/'+profile+'/'+tier)
    _,ctx=flows.identity('local')
    op=next(v for v in flows.catalog(ctx).values() if v['owner']=='ai2apps.gallery' and v['role']=='read')
    own,_=gallery(runtime).import_stream('local',BytesIO(b'evidence'),name='proof.txt',media_type='text/plain')
    infer=AsyncMock(side_effect=[json.dumps({'providers':[op['provider_id']]}),json.dumps({'name':'Gallery report','steps':[
        {'type':'read','provider':op['provider_id'],'arguments':{'asset_id':own['id']}},
        {'type':'model','instruction':'Report asset name','complexity':'simple','profile':'privacy','inputs':[0]}]}),'proof.txt'])
    monkeypatch.setattr(flows,'complete',infer)
    now=runtime.system_tasks.clock()
    draft=await flows.preview('local',Proposal(prompt='Read the selected asset and report its name',first_run=now+120,interval_minutes=60))
    assert not any(s['id']==draft['id'] for s in runtime.system_tasks.snapshot('local')['schedules'])
    flows.confirm('local',draft['id']);flows.confirm('local',draft['id'])
    monkeypatch.setattr(flows.system,'clock',lambda:now+121)
    await flows.system.tick()
    await asyncio.gather(*flows.system.jobs.values())
    row=next(t for t in flows.system.snapshot('local')['tasks'] if t['kind']=='todo.agent_chat_flow')
    assert row['status']=='completed',row['message']
    assert flows.system.get('local',row['id'])['result']=={'text':'proof.txt','notify':False}
    assert infer.await_count==3
    assert own['id'] in str(infer.await_args.args[-1])
    flows.revoke('local',draft['id'])
    with pytest.raises(ValueError):flows.approved('local',draft['id'])


@pytest.mark.asyncio
async def test_unknown_tool_cannot_be_approved(runtime,monkeypatch):
    flows=runtime.todo_agent_flows
    monkeypatch.setattr(flows,'model',lambda *_:'fixture')
    monkeypatch.setattr(flows,'complete',AsyncMock(return_value=json.dumps({'providers':['not.registered']})))
    with pytest.raises(ValueError,match='Invalid capability selection'):
        await flows.preview('local',Proposal(prompt='Unknown tool',first_run=flows.system.clock()+300,interval_minutes=5))


@pytest.mark.asyncio
async def test_receipt_revocation_and_success_notification(runtime,monkeypatch):
    flows=runtime.todo_agent_flows
    monkeypatch.setattr(flows,'model',lambda *_:'fixture/private')
    inference=AsyncMock(side_effect=['{"providers":[]}',json.dumps({'name':'Summary','steps':[
        {'type':'model','instruction':'Write a note','complexity':'simple','profile':'privacy','inputs':[]}]}),'Concrete result'])
    monkeypatch.setattr(flows,'complete',inference)
    plan=await flows.preview('local',Proposal(prompt='Write a note',first_run=flows.system.clock()+120,interval_minutes=5,notify=True))
    flows.confirm('local',plan['id'])
    task=flows.system.start_schedule('local',plan['id'])
    await flows.system.tick();await asyncio.gather(*flows.system.jobs.values())
    from unittest.mock import Mock
    producer=runtime.remote.notifications
    monkeypatch.setattr(producer,'supports_custom',lambda _:True)
    monkeypatch.setattr(producer,'identity',lambda:{'owner_id':'other'})
    outbox=Mock();monkeypatch.setattr(producer,'enqueue_custom',outbox)
    assert flows.push_completed()==0
    monkeypatch.setattr(producer,'identity',lambda:{'owner_id':'local'})
    assert flows.push_completed()==1 and flows.push_completed()==0
    assert outbox.call_args.kwargs['content']['body']=='Concrete result'
    assert outbox.call_args.kwargs['target']['id']==task['id']
    flows.revoke('local',plan['id'])
    with pytest.raises(ValueError):flows.confirm('local',plan['id'])


def test_immutable_bindings_resolve_paths_without_evaluation():
    from ai2apps.system_tasks.agent_flows import references,bind
    args={'id':{'$step':0,'path':['items',0,'id']}}
    assert references(args,1) and bind(args,[{'items':[{'id':'a'}]}])=={'id':'a'}
    with pytest.raises(ValueError):references(args,0)
    with pytest.raises(ValueError):bind(args,[{}])


@pytest.mark.asyncio
async def test_model_route_drift_stops_confirmed_schedule_before_inference(runtime,monkeypatch):
    flows=runtime.todo_agent_flows
    monkeypatch.setattr(flows,'model',lambda *_:'fixture/original')
    inference=AsyncMock(side_effect=['{"providers":[]}',json.dumps({'name':'Pinned route','steps':[
        {'type':'model','instruction':'Write a note','complexity':'simple','profile':'privacy','inputs':[]}]})])
    monkeypatch.setattr(flows,'complete',inference)
    draft=await flows.preview('local',Proposal(prompt='Write a note',first_run=flows.system.clock()+120,interval_minutes=5))
    flows.confirm('local',draft['id'])
    monkeypatch.setattr(flows,'model',lambda *_:'fixture/replacement')
    task=flows.system.start_schedule('local',draft['id'])
    await flows.system.tick()
    await asyncio.gather(*flows.system.jobs.values())
    row=flows.system.get('local',task['id'])
    assert row['status']=='failed'
    assert inference.await_count==2
