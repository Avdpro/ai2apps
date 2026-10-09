import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.todo import create_todo_router
from ai2apps.identity import RequestPrincipal
from ai2apps.todo.models import TaskInput
from ai2apps.todo.service import TodoService
from ai2apps.codex import CodexManager


class FakeClient:
    cwd = ''
    approval = False
    disconnect = False
    instances = []

    @staticmethod
    def executable(): return '/codex'

    def __init__(self):
        self.events = asyncio.Queue()
        self.calls = []
        self.responses = []
        self.__class__.instances.append(self)

    async def __aenter__(self): return self
    async def __aexit__(self, *_): pass

    async def threads(self, cwd=None, cursor=None):
        return {'data':[{'id':'existing', 'name':'Existing', 'cwd':self.cwd}], 'nextCursor':None}

    async def call(self, method, params, **_):
        self.calls.append((method,params))
        if method == 'thread/read': return {'thread':{'id':'existing','cwd':self.cwd,'name':'Existing'}}
        if method == 'thread/start': return {'thread':{'id':'new-thread'}}
        if method == 'turn/start':
            if self.disconnect: await self.events.put({'method':'connection/closed'})
            elif self.approval:
                await self.events.put({'id':99,'method':'item/commandExecution/requestApproval','params':{'threadId':params['threadId'],'command':'echo ok'}})
            else: await self.completed()
            return {'turn':{'id':'turn-1'}}
        return {}

    async def completed(self):
        await self.events.put({'method':'item/agentMessage/delta','params':{'delta':'Finished'}})
        await self.events.put({'method':'turn/completed','params':{'turn':{'id':'turn-1','status':'completed'}}})

    async def send(self, message):
        self.responses.append(message)
        await self.completed()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    runtime = SimpleNamespace(config=SimpleNamespace(paths=SimpleNamespace(artifacts_path=tmp_path)), agent_runtime=None)
    runtime.codex = CodexManager()
    s = TodoService(runtime)
    monkeypatch.setattr(s,'desktop_access',lambda owner:None)
    monkeypatch.setattr('ai2apps.codex.transport.CodexDesktop',FakeClient)
    monkeypatch.setattr('ai2apps.codex.manager.CodexDesktop',FakeClient)
    FakeClient.cwd=str(tmp_path);FakeClient.approval=False;FakeClient.disconnect=False;FakeClient.instances=[]
    directory=s.store.directory('local','Test')
    task=s.store.save('local',{'title':'Test','directory_id':directory['id'],'executor':'codex_desktop','codex':{'project_path':str(tmp_path)}})
    return s,task,tmp_path


async def finished(s):
    for _ in range(100):
        if not s.jobs:return
        await asyncio.sleep(.01)
    raise AssertionError('Run did not release its slot')


@pytest.mark.asyncio
async def test_new_conversation_persisted_and_released(setup, monkeypatch):
    s,t,_=setup
    s.launch('local',t['id'],principal=RequestPrincipal.legacy_local())
    await finished(s)
    item=s.store.get('local',t['id'])
    assert item['codex']['thread_id']=='new-thread'
    assert item['status']=='not_started'
    run=s.store.snapshot('local')['runs'][0]
    assert run['status']=='ended' and run['output']=='Finished'
    calls=[m for m,_ in FakeClient.instances[-1].calls]
    assert 'thread/unsubscribe' in calls and 'turn/interrupt' not in calls
    async def native(*args):
        args[-1]('ended', output='Native result')
    monkeypatch.setattr(s.runtime.codex, 'native_run', native)
    s.launch('local',t['id'],principal=RequestPrincipal.legacy_local())
    await finished(s)
    calls=[m for m,_ in FakeClient.instances[-1].calls]
    assert 'thread/resume' not in calls and 'thread/start' not in calls


@pytest.mark.asyncio
async def test_waiting_approval_holds_slot_and_is_owner_scoped(setup):
    s,t,_=setup;FakeClient.approval=True
    s.launch('local',t['id'],principal=RequestPrincipal.legacy_local())
    for _ in range(100):
        if s.runtime.codex.desktop_requests:break
        await asyncio.sleep(.01)
    token=next(iter(s.runtime.codex.desktop_requests))
    assert len(s.jobs)==1
    assert s.store.snapshot('local')['runs'][0]['status']=='waiting_capability'
    with pytest.raises(ValueError):s.desktop_reply('other',token,'approve')
    s.desktop_reply('local',token,'approve')
    with pytest.raises(ValueError):s.desktop_reply('local',token,'approve')
    await finished(s)
    assert not s.runtime.codex.desktop_requests
    assert FakeClient.instances[-1].responses[0]['result']=={'decision':'accept'}


@pytest.mark.asyncio
async def test_cancel_interrupts_and_releases_waiting_conversation(setup):
    s,t,_=setup;FakeClient.approval=True
    run=s.launch('local',t['id'],principal=RequestPrincipal.legacy_local())
    while not s.runtime.codex.desktop_requests:await asyncio.sleep(.01)
    await s.cancel('local',run['id'])
    assert not s.runtime.codex.desktop_requests and not s.runtime.codex.desktop_threads
    calls=[m for m,_ in FakeClient.instances[-1].calls]
    assert 'turn/interrupt' in calls and 'thread/unsubscribe' in calls
    assert s.store.snapshot('local')['runs'][0]['status']=='cancelled'


@pytest.mark.asyncio
async def test_connection_loss_is_failed_not_success(setup):
    s,t,_=setup;FakeClient.disconnect=True
    s.launch('local',t['id'],principal=RequestPrincipal.legacy_local())
    await finished(s)
    assert s.store.snapshot('local')['runs'][0]['status']=='failed'


def test_binding_verifies_directory_and_revision_without_execution(setup):
    s,t,path=setup
    app=FastAPI();app.include_router(create_todo_router(lambda:SimpleNamespace(todo=s),RequestPrincipal.legacy_local))
    with TestClient(app) as client:
        body={'revision':t['revision'],'binding':{'project_path':str(path),'thread_id':'existing'}}
        result=client.put('/todo/tasks/'+t['id']+'/codex/desktop',json=body)
        assert result.status_code==200,result.text
        assert result.json()['codex']['thread_title']=='Existing'
        assert not s.jobs and not s.store.snapshot('local')['runs']
        assert all(method not in ('turn/start','thread/resume') for c in FakeClient.instances for method,_ in c.calls)
        assert client.put('/todo/tasks/'+t['id']+'/codex/desktop',json=body).status_code==422
        body['revision']=result.json()['revision'];FakeClient.cwd=str(path.parent)
        assert client.put('/todo/tasks/'+t['id']+'/codex/desktop',json=body).status_code==422


def test_system_api_works_without_todo_or_plugin_pairing(tmp_path, monkeypatch):
    from ai2apps.api.codex import create_codex_router
    monkeypatch.setattr('ai2apps.codex.manager.CodexDesktop', FakeClient)
    FakeClient.cwd = str(tmp_path)
    monkeypatch.setattr('ai2apps.codex.projects.saved_projects', lambda:[])
    runtime = SimpleNamespace(codex=CodexManager())
    app = FastAPI()
    app.include_router(create_codex_router(lambda:runtime, RequestPrincipal.legacy_local))
    with TestClient(app) as client:
        assert client.get('/codex/projects').json()['data'][0]['path'] == str(tmp_path)
        assert client.get('/codex/threads').json()['data'][0]['id'] == 'existing'
        assert client.post('/codex/requests/missing', json={'decision':'approve'}).status_code == 422


@pytest.mark.asyncio
async def test_shared_manager_excludes_same_session_across_callers_and_shutdown(setup, monkeypatch):
    s, task, path = setup
    manager = s.runtime.codex
    FakeClient.approval = True
    entered = asyncio.Event()
    async def native(*args):
        entered.set()
        await asyncio.Future()
    monkeypatch.setattr(manager, 'native_run', native)
    async def bound(thread_id): pass
    options = dict(cwd=str(path), title='System caller', prompt='Test', thread_id='existing',
                   on_update=lambda *args, **kwargs:None, on_thread=bound)
    first = asyncio.create_task(manager.execute('chat-run', 'local', **options))
    await asyncio.wait_for(entered.wait(), 1)
    with pytest.raises(ValueError, match='already running in AI2Apps'):
        await manager.execute('coder-run', 'local', **options)
    assert manager.desktop_threads == {'existing'}
    await manager.shutdown()
    assert first.cancelled()
    assert not manager.jobs and not manager.desktop_threads and not manager.desktop_requests
    with pytest.raises(ValueError, match='stopping'):
        await manager.execute('late-run', 'local', **options)


@pytest.mark.asyncio
async def test_external_writer_does_not_start_or_unsubscribe_other_client(setup, monkeypatch):
    s, task, path = setup
    original = FakeClient.call
    async def reject_resume(self, method, params, **kwargs):
        if method == 'thread/resume':
            self.calls.append((method, params))
            raise ValueError('thread existing already has an active writer')
        return await original(self, method, params, **kwargs)
    monkeypatch.setattr(FakeClient, 'call', reject_resume)
    async def bound(thread_id): raise AssertionError('Must not create a replacement')
    delivered=[]
    async def native(*args): delivered.append(args[1])
    monkeypatch.setattr(s.runtime.codex, 'native_run', native)
    await s.runtime.codex.execute('busy-run', 'local', cwd=str(path), title='Test',
        prompt='Do work', thread_id='existing', on_thread=bound,
        on_update=lambda *args, **kwargs:None)
    assert delivered == ['existing']
    calls=[method for method, _ in FakeClient.instances[-1].calls]
    assert 'turn/start' not in calls and 'thread/start' not in calls
    assert 'thread/unsubscribe' not in calls and 'turn/interrupt' not in calls
    assert not s.runtime.codex.desktop_threads and not s.runtime.codex.jobs


@pytest.mark.asyncio
async def test_native_delivery_survives_restart_and_cannot_fake_cancel(setup, monkeypatch):
    s,t,path=setup
    monkeypatch.setattr(s, 'dispatch_queue', lambda:None)
    run=s.launch('local',t['id'],principal=RequestPrincipal.legacy_local())
    s.store.run_update(run['id'],'queued',todo_queued=False,desktop_native=True,
        codex_thread_id='existing',native_marker='[AI2Apps run:recovered]',native_delivery='queued')
    entered=asyncio.Event()
    async def monitor(thread,marker,callback):
        assert thread=='existing' and marker=='[AI2Apps run:recovered]'
        entered.set()
        await asyncio.Future()
    monkeypatch.setattr(s.runtime.codex,'resume_native',monitor)
    await s.startup()
    await asyncio.wait_for(entered.wait(),1)
    with pytest.raises(ValueError, match='owned by Codex Desktop'):
        await s.cancel('local',run['id'])
    assert s.store.snapshot('local')['runs'][0]['status']=='queued'
    await s.shutdown()
    assert s.store.snapshot('local')['runs'][0]['status']=='queued'
