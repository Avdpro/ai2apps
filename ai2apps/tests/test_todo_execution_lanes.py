"""Persistent serial execution lanes, independent of any consuming App identity."""
import asyncio

import pytest

from ai2apps.identity import RequestPrincipal
from test_todo import service, task


@pytest.mark.asyncio
async def test_serial_lane_skips_busy_group_without_blocking_other_groups(tmp_path, monkeypatch):
    s = service(tmp_path)
    started, gates = [], {}
    async def execute(id, owner, data):
        started.append(id)
        gates[id] = asyncio.Event()
        await gates[id].wait()
        s.store.run_update(id, 'completed')
    monkeypatch.setattr(s, 'execute', execute)
    def launch(owner, lane):
        t = task(s.store, owner, model='test')
        if lane:
            s.store.bind_execution_lane(owner, t['id'], lane)
        return s.launch(owner, t['id'], principal=RequestPrincipal.legacy_local())['id']
    try:
        first = launch('alice', 'arbitrary-provider:alpha')
        second = launch('alice', 'arbitrary-provider:alpha')
        other = launch('alice', 'unrelated-provider:beta')
        foreign = launch('bob', 'arbitrary-provider:alpha')
        await asyncio.sleep(0)
        assert started == [first, other, foreign]
        s.store.run_update(first, 'waiting_input')
        s.dispatch_queue()
        assert second not in s.jobs
        gates[first].set()
        for _ in range(4):
            await asyncio.sleep(0)
        assert second in started
    finally:
        await s.shutdown()


@pytest.mark.asyncio
async def test_recovery_preserves_lane_while_original_agent_waits(tmp_path, monkeypatch):
    s = service(tmp_path)
    async def execute(id, owner, data):
        s.store.run_update(id, 'waiting_capability', agent_run_id='fixture-durable-run')
        await asyncio.Event().wait()
    monkeypatch.setattr(s, 'execute', execute)
    ids = []
    for _ in range(2):
        t = task(s.store, 'local', model='test')
        s.store.bind_execution_lane('local', t['id'], 'provider:any-lane')
        ids.append(s.launch('local', t['id'], principal=RequestPrincipal.legacy_local())['id'])
    await asyncio.sleep(0)
    await s.shutdown()
    recovered = service(tmp_path)
    resume_gate = asyncio.Event()
    started = []
    async def watch(id, agent_id):
        assert agent_id == 'fixture-durable-run'
        await resume_gate.wait()
        recovered.store.run_update(id, 'completed')
    async def next_task(id, owner, data):
        started.append(id)
        recovered.store.run_update(id, 'completed')
    monkeypatch.setattr(recovered, 'watch_internal', watch)
    monkeypatch.setattr(recovered, 'execute', next_task)
    try:
        await recovered.startup()
        await asyncio.sleep(0)
        assert started == []
        resume_gate.set()
        for _ in range(4):
            await asyncio.sleep(0)
        assert started == [ids[1]]
    finally:
        await recovered.shutdown()


@pytest.mark.asyncio
async def test_another_dispatcher_observes_persisted_lane_claim(tmp_path, monkeypatch):
    first, second = service(tmp_path), service(tmp_path)
    async def execute(*args):
        await asyncio.Event().wait()
    monkeypatch.setattr(first, 'execute', execute)
    monkeypatch.setattr(second, 'execute', execute)
    tasks = [task(first.store, 'local', model='test') for _ in range(2)]
    for t in tasks:
        first.store.bind_execution_lane('local', t['id'], 'third-party-provider:lane')
    try:
        one = first.launch('local', tasks[0]['id'], principal=RequestPrincipal.legacy_local())['id']
        two = second.launch('local', tasks[1]['id'], principal=RequestPrincipal.legacy_local())['id']
        assert one in first.jobs and two not in second.jobs
        with pytest.raises(ValueError, match='active run'):
            first.store.bind_execution_lane('local', tasks[0]['id'], None, expected_lane='third-party-provider:lane')
        # Original run frozen lane cannot be cleared through task editing.
        assert next(r for r in first.store.snapshot('local')['runs'] if r['id']==one)['execution_lane'] == 'third-party-provider:lane'
    finally:
        await first.shutdown()
        await second.shutdown()


def test_lane_assignment_checks_owner_existing_assignment_and_stale_release(tmp_path):
    s = service(tmp_path)
    t = task(s.store, 'alice')
    with pytest.raises(KeyError):
        s.store.bind_execution_lane('bob', t['id'], 'foreign')
    s.store.bind_execution_lane('alice', t['id'], 'provider:a')
    s.store.bind_execution_lane('alice', t['id'], 'provider:a')
    with pytest.raises(ValueError, match='existing assignment'):
        s.store.bind_execution_lane('alice', t['id'], 'provider:b')
    with pytest.raises(ValueError, match='changed'):
        s.store.bind_execution_lane('alice', t['id'], None, expected_lane='provider:b')
    s.store.bind_execution_lane('alice', t['id'], None, expected_lane='provider:a')
    assert s.store.execution_lane_tasks('alice', 'provider:a')['items'] == []

@pytest.mark.asyncio
async def test_cancel_queued_lane_task_does_not_release_running_task(tmp_path, monkeypatch):
    s = service(tmp_path)
    gates, started = {}, []
    async def execute(id, owner, data):
        started.append(id)
        gates[id] = asyncio.Event()
        await gates[id].wait()
        s.store.run_update(id, 'completed')
    monkeypatch.setattr(s, 'execute', execute)
    ids = []
    try:
        for _ in range(3):
            t = task(s.store, 'local', model='test')
            s.store.bind_execution_lane('local', t['id'], 'arbitrary:cancel-lane')
            ids.append(s.launch('local', t['id'], principal=RequestPrincipal.legacy_local())['id'])
        await asyncio.sleep(0)
        await s.cancel('local', ids[1])
        assert started == [ids[0]]
        gates[ids[0]].set()
        for _ in range(4):
            await asyncio.sleep(0)
        assert started == [ids[0], ids[2]]
    finally:
        await s.shutdown()


def test_bounded_task_projection_keeps_active_old_task_visible(tmp_path):
    import json
    s = service(tmp_path)
    schedule = task(s.store, 'alice', title='Daily report', schedule={'frequency':'daily','hour':7})
    s.store.bind_execution_lane('alice', schedule['id'], 'provider:bounded')
    tasks = [task(s.store, 'alice', title=f'Project {i}') for i in range(52)]
    for t in tasks:
        s.store.bind_execution_lane('alice', t['id'], 'provider:bounded')
    with s.store.connect() as db:
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?)', ('receipt','alice',tasks[0]['id'],'waiting_input',json.dumps({'log':'progress','output':'private execution output'})))
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?)', ('scheduled-receipt','alice',schedule['id'],'completed',json.dumps({'finished_at':'2026-11-16T23:00:00Z'})))
    value = s.store.execution_lane_tasks('alice', 'provider:bounded')
    assert len(value['items']) == 50 and value['has_more']
    assert value['items'][0]['id'] == tasks[0]['id']
    assert value['items'][0]['run']['status'] == 'waiting_input'
    assert value['items'][1]['id'] == schedule['id'] and value['items'][1]['scheduled']
    assert value['items'][1]['run']['status'] == 'completed'
    assert value['items'][1]['updated_at'] == schedule['updated_at']
    assert 'private execution output' not in json.dumps(value)
    assert s.store.execution_lane_tasks('bob', 'provider:bounded')['items'] == []
    with s.store.connect() as db:
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?)', ('current-receipt','alice',schedule['id'],'running','{}'))
    items = s.store.execution_lane_tasks('alice', 'provider:bounded')['items']
    scheduled = next(item for item in items if item['id'] == schedule['id'])
    assert scheduled['run']['id'] == 'current-receipt'
    assert scheduled['previous_finished_run']['id'] == 'scheduled-receipt'
    assert scheduled['previous_finished_run']['finished_at'] == '2026-11-16T23:00:00Z'

@pytest.mark.parametrize('registration',['arbitrary.owner.upkeep','different.provider.maintenance'])
@pytest.mark.asyncio
async def test_trusted_maintenance_priority_is_nonpreemptive_and_fair(tmp_path,monkeypatch,registration):
    from ai2apps.todo.execution import TodoExecutionAdapter
    from ai2apps.todo.models import Schedule
    s=service(tmp_path);started=[];gates={}
    adapter=TodoExecutionAdapter(registration,lambda *a:None,lambda *a:None,queue_class='maintenance')
    s.register_execution_adapter(adapter)
    async def execute(ref,owner,data):
        started.append(ref);gates[ref]=asyncio.Event();await gates[ref].wait();s.store.run_update(ref,'completed')
    monkeypatch.setattr(s,'execute',execute)
    def launch(maintenance=False):
        if maintenance:
            value={'title':'Upkeep','description':'Fixture','executor':'managed','model':'fixture','schedule':Schedule().model_dump()}
            from uuid import uuid4
            t=s.store.save('local',value,creation_key=uuid4().hex,create_inbox=True,execution_binding={'registration':registration,'binding':{}},execution_lane='unrelated:lane')
        else:
            t=task(s.store,'local',model='fixture');s.store.bind_execution_lane('local',t['id'],'unrelated:lane')
        return s.launch('local',t['id'],principal=RequestPrincipal.legacy_local())['id']
    from ai2apps.identity import RequestPrincipal
    try:
        first=launch();await asyncio.sleep(0)
        normal=launch();upkeep=[launch(True) for _ in range(3)]
        s.store.run_update(first,'waiting_input');s.dispatch_queue();assert started==[first]
        async def release(ref):
            gates[ref].set()
            for _ in range(5):await asyncio.sleep(0)
        await release(first);assert started[-1]==upkeep[0]
        await release(upkeep[0]);assert started[-1]==upkeep[1]
        await release(upkeep[1]);assert started[-1]==normal
        await release(normal);assert started[-1]==upkeep[2]
        await release(upkeep[2])
    finally:await s.shutdown()
