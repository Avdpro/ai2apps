import asyncio
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from ai2apps.todo.codex_bridge import CodexBridge
from ai2apps.todo.models import TaskInput
from ai2apps.todo.store import TodoStore
from ai2apps.todo.transfer import export_backup, merge_backup

ADAPTER = Path(__file__).parents[1]/'integrations/codex-todo/scripts/server.py'
spec = importlib.util.spec_from_file_location('todo_adapter', ADAPTER)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


@pytest.fixture
def bridge(tmp_path):
    return CodexBridge(TodoStore(tmp_path))


def create(bridge, owner='alice', **values):
    directory = bridge.store.directory(owner,'Work')
    return bridge.call(owner,'todo_create',{'title':'Root','directory_id':directory['id'],**values})


def test_binding_inheritance_and_thread_isolation(bridge):
    root = create(bridge)
    root = bridge.call('alice','todo_bind',{'task_id':root['id'],'revision':root['revision'],'binding':{'project_id':'project-1','project_name':'AI2Apps','thread_id':'thread-1'}})
    child = bridge.call('alice','todo_create',{'parent_id':root['id'],'title':'Child'})
    result = bridge.call('alice','todo_read',{'task_id':child['id']})
    assert result['effective_codex']['project_id']=='project-1'
    assert result['project_inherited']
    assert not result['effective_codex'].get('thread_id')
    assert len(bridge.call('alice','todo_list',{'project_id':'project-1'})['tasks'])==2
    assert len(bridge.call('alice','todo_list',{'thread_id':'thread-1'})['tasks'])==1
    child = bridge.call('alice','todo_bind',{'task_id':child['id'],'revision':child['revision'],'binding':{'inherit_project':False}})
    assert not bridge.call('alice','todo_read',{'task_id':child['id']})['project_inherited']


def test_owner_revision_validation_and_no_execution(bridge):
    task = create(bridge)
    with pytest.raises(KeyError): bridge.call('bob','todo_read',{'task_id':task['id']})
    assert bridge.call('bob','todo_list',{})['tasks']==[]
    with pytest.raises(ValueError): bridge.call('alice','todo_update',{'task_id':task['id'],'revision':99,'progress':50})
    with pytest.raises(ValueError): bridge.call('alice','todo_update',{'task_id':task['id'],'revision':1,'executor':'codex'})
    with pytest.raises(ValueError): bridge.call('alice','todo_run',{'task_id':task['id']})
    with pytest.raises(ValueError): bridge.call('alice','todo_bind',{'task_id':task['id'],'revision':1,'binding':{'thread_id':'<script>'}})
    updated = bridge.call('alice','todo_update',{'task_id':task['id'],'revision':1,'status':'in_progress','summary':'Added tests; review remains.'})
    assert not updated['completed']
    assert updated['codex_updates'][-1]['summary']=='Added tests; review remains.'
    assert bridge.store.snapshot('alice')['runs']==[]
    assert not bridge.call('alice','todo_list',{'query':'not found'})['tasks']
    bridge.store.lifecycle('alice',task['id'],'archive')
    assert bridge.call('alice','todo_list',{})['tasks']==[]
    with pytest.raises(ValueError): bridge.call('alice','todo_update',{'task_id':task['id'],'revision':bridge.store.get('alice',task['id'])['revision'],'progress':20})


def test_reports_and_bindings_survive_backup_and_normal_edits(bridge,tmp_path):
    task = create(bridge)
    task = bridge.call('alice','todo_bind',{'task_id':task['id'],'revision':1,'binding':{'project_path':'/work/repo','thread_id':'abc-123'}})
    task = bridge.call('alice','todo_update',{'task_id':task['id'],'revision':task['revision'],'summary':'Ready for review'})
    other = TodoStore(tmp_path/'imported')
    payload = export_backup(bridge.store,'alice')
    preview = merge_backup(other,'alice',payload)
    merge_backup(other,'alice',payload,preview['expected'])
    imported = other.snapshot('alice')['tasks'][0]
    assert imported['codex']==task['codex']
    assert imported['codex_updates']==task['codex_updates']
    data = {k:task[k] for k in TaskInput.model_fields}
    data['priority']='U'
    assert bridge.store.save('alice',data,task['id'],task['revision'])['codex']==task['codex']


@pytest.mark.asyncio
async def test_pair_restart_revoke_and_real_mcp_transport(bridge):
    task = create(bridge)
    try:
        status = await bridge.connect('alice')
        path = Path(status['config_path'])
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700
        first = json.loads(path.read_text())
        result = await asyncio.to_thread(adapter.call,path,'todo_read',{'task_id':task['id']})
        assert result['task']['id']==task['id']
        # Actual plugin process initializes, discovers tools and queries the paired bridge.
        messages = [
            {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}},
            {'jsonrpc':'2.0','method':'notifications/initialized'},
            {'jsonrpc':'2.0','id':2,'method':'tools/list'},
            {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'todo_list','arguments':{}}},
        ]
        proc = await asyncio.create_subprocess_exec(sys.executable,str(ADAPTER),'--config',str(path),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate(('\n'.join(json.dumps(m) for m in messages)+'\n').encode())
        assert proc.returncode==0,stderr
        replies = [json.loads(line) for line in stdout.splitlines()]
        assert len(replies)==3
        assert len(replies[1]['result']['tools'])==5
        assert not replies[2]['result']['isError']
        assert task['id'] in replies[2]['result']['content'][0]['text']
        await bridge.close()
        await bridge.start()
        assert (await asyncio.to_thread(adapter.call,path,'todo_list',{}))['total']==1
        await bridge.connect('alice')
        reader, writer = await asyncio.open_connection('127.0.0.1',bridge.server.sockets[0].getsockname()[1])
        writer.write((json.dumps({'token':first['token'],'name':'todo_list','arguments':{}})+'\n').encode());await writer.drain()
        response = json.loads(await reader.readline())
        writer.close();await writer.wait_closed()
        assert 'error' in response
        assert first['token'] not in json.dumps(response)
        bridge.revoke('alice')
        assert not path.exists()
        assert not bridge.status('alice')['connected']
    finally:
        await bridge.close()


def test_pairing_api_is_local_and_owner_scoped():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from types import SimpleNamespace
    from ai2apps.api.todo import create_todo_router
    from ai2apps.identity import RequestPrincipal
    seen = []
    class FakeBridge:
        def status(self, owner): return {'connected':False,'config_path':'/private/connection.json'}
        async def connect(self, owner): seen.append(('connect',owner)); return {'connected':True,'config_path':'/private/connection.json'}
        def revoke(self, owner): seen.append(('revoke',owner))
    app = FastAPI()
    runtime = SimpleNamespace(todo=SimpleNamespace(codex_bridge=FakeBridge()))
    app.include_router(create_todo_router(lambda:runtime,RequestPrincipal.legacy_local))
    local = TestClient(app,client=('127.0.0.1',1234))
    remote = TestClient(app,client=('192.0.2.1',1234))
    assert remote.post('/todo/codex/connect').status_code==403
    assert not seen
    assert local.post('/todo/codex/connect',json={'owner':'victim'}).json()['connected']
    assert seen==[('connect','local')]
    assert 'token' not in local.get('/todo/codex').text
    assert not local.post('/todo/codex/disconnect').json()['connected']
    assert seen[-1]==('revoke','local')
