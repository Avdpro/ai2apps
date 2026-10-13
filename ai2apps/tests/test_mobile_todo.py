from types import SimpleNamespace
from dataclasses import replace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ai2apps.identity import RequestPrincipal
from ai2apps.todo.store import TodoStore
from ai2apps.web.mobile_todo import create_mobile_todo_router
from ai2apps.web.owner_home_gateway import public_allowed

@pytest.fixture
def env(tmp_path):
    store=TodoStore(tmp_path)
    principal=replace(RequestPrincipal.legacy_local(), actor_user_id='alice', authentication_type='owner_home_lease')
    app=FastAPI()
    app.include_router(create_mobile_todo_router(lambda:SimpleNamespace(todo=SimpleNamespace(store=store)),lambda:principal,lambda *_: 'Todo'))
    with TestClient(app) as client: yield client,store

def test_create_edit_complete_and_revision(env):
    c,s=env
    d=c.post('/v1/mobile/todo/directories',json={'title':'Mobile'}).json()
    r=c.post('/v1/mobile/todo/tasks',json={'directory_id':d['id'],'title':'First'})
    assert r.status_code==200
    t=r.json()
    updated=c.put('/v1/mobile/todo/tasks/'+t['id'],json={'revision':t['revision'],'title':'Edited','status':'completed'})
    assert updated.status_code==200
    assert s.get('alice',t['id'])['completed'] is True
    assert c.put('/v1/mobile/todo/tasks/'+t['id'],json={'revision':t['revision'],'title':'Stale'}).status_code==409
    assert c.get('/v1/mobile/todo').json()['tasks'][0]['title']=='Edited'

def test_owner_isolation_and_execution_fields(env):
    c,s=env
    d=s.directory('bob','Private')
    t=s.save('bob',{'directory_id':d['id'],'title':'Secret'})
    assert c.get('/v1/mobile/todo').json()['tasks']==[]
    assert c.put('/v1/mobile/todo/tasks/'+t['id'],json={'revision':1,'title':'Attack'}).status_code==404
    assert c.post('/v1/mobile/todo/tasks',json={'directory_id':d['id'],'title':'Attack'}).status_code==404
    own=s.directory('alice','Own')
    assert c.post('/v1/mobile/todo/tasks',json={'directory_id':own['id'],'parent_id':t['id'],'title':'Attack'}).status_code==404
    for field,value in [('executor','codex'),('working_directory','/tmp'),('schedule',{'frequency':'daily'})]:
        assert c.post('/v1/mobile/todo/tasks',json={'directory_id':own['id'],'title':'Task',field:value}).status_code==422

def test_existing_execution_settings_preserved(env):
    c,s=env;d=s.directory('alice','Own')
    t=s.save('alice',{'title':'Existing','directory_id':d['id'],'executor':'codex','working_directory':'/tmp'})
    assert c.put('/v1/mobile/todo/tasks/'+t['id'],json={'revision':t['revision'],'title':'Rename'}).status_code==200
    saved=s.get('alice',t['id'])
    assert saved['executor']=='codex' and saved['working_directory']=='/tmp'
    assert 'working_directory' not in c.get('/v1/mobile/todo').json()['tasks'][0]

@pytest.mark.parametrize('method,path',[('POST','/v1/mobile/todo/tasks/x/run'),('GET','/v1/mobile/todo/backup'),('POST','/v1/mobile/todo/codex/connect'),('DELETE','/v1/mobile/todo/tasks/x'),('GET','/v1/platform/todo')])
def test_public_boundary_denies_other_todo_operations(method,path):
    assert not public_allowed(method,path)

def test_owner_boundary_todo_cookie_and_origin(tmp_path,monkeypatch):
    import time
    from unittest.mock import AsyncMock
    from ai2apps.web.public_boundary import PublicDeviceBoundary
    from ai2apps.web import owner_home_gateway as gateway
    from ai2apps.remote.owner_home import COOKIE
    from fastapi import Request, HTTPException
    s=TodoStore(tmp_path)
    principal=replace(RequestPrincipal.legacy_local(),actor_user_id='alice',authentication_type='owner_home_lease')
    record=SimpleNamespace(claims={'device_id':'device'},deadline=time.time()+60)
    device=SimpleNamespace(public_origin='https://device.example')
    async def authorize(token):
        if token!='test-owner': raise ValueError('Invalid')
        return record
    service=SimpleNamespace(authorize=authorize,valid=lambda _:None,principal=lambda _:principal)
    manager=SimpleNamespace(owner_home=service,repository=SimpleNamespace(list=lambda:[device]),require_device=lambda _:device,authorize_session=AsyncMock(return_value=None))
    runtime=SimpleNamespace(todo=SimpleNamespace(store=s),remote=manager)
    monkeypatch.setattr(gateway,'_runtime',lambda:runtime)
    def access(request:Request):
        grant=gateway.authority(request)
        if not grant: raise HTTPException(401)
        return grant[0].principal(grant[1])
    app=FastAPI();app.include_router(create_mobile_todo_router(lambda:runtime,access,lambda *_:'Todo'))
    app.add_middleware(PublicDeviceBoundary,manager_provider=lambda:manager)
    with TestClient(app,base_url=device.public_origin) as c:
        assert c.get('/v1/mobile/todo').status_code==403
        headers={'Cookie':f'{COOKIE}=test-owner','Origin':device.public_origin}
        assert c.get('/v1/mobile/todo',headers=headers).status_code==200
        assert c.post('/v1/mobile/todo/directories',headers=headers,json={'title':'Own'}).status_code==200
        assert c.post('/v1/mobile/todo/directories',headers={**headers,'Origin':'https://evil.example'},json={'title':'No'}).status_code==401
        assert c.post('/v1/mobile/todo/tasks/id/run',headers=headers,json={}).status_code==401


def test_mobile_progress_edit_and_completion(env):
    c,s=env;d=s.directory('alice','Progress')
    t=c.post('/v1/mobile/todo/tasks',json={'directory_id':d['id'],'title':'Work','progress':35}).json()
    assert (t['status'],t['progress'])==('in_progress',35)
    def save(status,progress):
        nonlocal t
        r=c.put('/v1/mobile/todo/tasks/'+t['id'],json={'revision':t['revision'],'title':t['title'],'status':status,'progress':progress})
        assert r.status_code==200
        t=r.json()
    save('in_progress',100)
    assert t['status']=='completed' and t['progress']==100
    save('completed',45)
    # An explicit completed status wins; UI changes status when lowering progress.
    assert t['progress']==100
    save('in_progress',45)
    assert t['status']=='in_progress' and t['progress']==45
    save('paused',45)
    assert t['progress']==45
    r=c.put('/v1/mobile/todo/tasks/'+t['id'],json={'revision':t['revision'],'title':'Renamed','status':'paused'})
    assert r.json()['progress']==45
    assert c.get('/v1/mobile/todo').json()['tasks'][0]['progress']==45


@pytest.mark.parametrize('progress',[-1,101,1.5])
def test_mobile_progress_range(env,progress):
    c,s=env;d=s.directory('alice','Range')
    assert c.post('/v1/mobile/todo/tasks',json={'directory_id':d['id'],'title':'Work','progress':progress}).status_code==422


def test_mobile_highlight_roundtrip_and_old_client(env):
    c,s=env;d=s.directory('alice','Colors')
    t=s.save('alice',{'directory_id':d['id'],'title':'Desktop','highlight':'lime','description':'Keep me','executor':'codex'})
    assert c.get('/v1/mobile/todo').json()['tasks'][0]['highlight']=='lime'
    url='/v1/mobile/todo/tasks/'+t['id']
    body={'title':t['title'],'description':t['description'],'revision':t['revision']}
    saved=c.put(url,json=body).json()
    assert saved['highlight']=='lime'  # Old mobile clients preserve the desktop color.
    for color in ['yellow','peach','pink','blue','lavender','']:
        response=c.put(url,json={**body,'revision':saved['revision'],'highlight':color})
        assert response.status_code==200
        saved=response.json()
        assert saved['highlight']==color
        assert s.get('alice',t['id'])['executor']=='codex'
        assert saved['description']=='Keep me' and saved['position']==t['position']
    assert c.put(url,json={**body,'revision':saved['revision'],'highlight':'red'}).status_code==422
    assert c.put(url,json={**body,'highlight':'blue'}).status_code==409
    foreign=s.save('bob',{'directory_id':s.directory('bob','Private')['id'],'title':'Secret'})
    assert c.put('/v1/mobile/todo/tasks/'+foreign['id'],json={**body,'revision':foreign['revision'],'highlight':'blue'}).status_code==404
    created=c.post('/v1/mobile/todo/tasks',json={'directory_id':d['id'],'title':'New','highlight':'pink'})
    assert created.status_code==200 and created.json()['highlight']=='pink'


def test_navigation_trace_bounded_and_logged(env, caplog):
    import logging
    c, _ = env
    body = {'session': '00000000-0000-0000-0000-000000000001', 'surface': 'todo',
            'events': [{'event': 'popstate', 'seq': 1, 'at': 1000, 'mono': 30,
                        'route': 'list', 'visible': True, 'detail': True,
                        'document_id': '00000000-0000-0000-0000-000000000002',
                        'persisted': True, 'navigation': 'back_forward'}]}
    with caplog.at_level(logging.INFO, logger='ai2apps.web.mobile_todo'):
        assert c.post('/v1/mobile/todo/navigation-trace', json=body).json() == {'accepted': 1}
    assert 'MOBILE_NAV_TRACE' in caplog.text
    assert 'popstate' in caplog.text
    body['events'][0]['title'] = 'Must not accept task content'
    assert c.post('/v1/mobile/todo/navigation-trace', json=body).status_code == 422
    del body['events'][0]['title']
    body['events'] *= 41
    assert c.post('/v1/mobile/todo/navigation-trace', json=body).status_code == 422
    assert public_allowed('POST', '/v1/mobile/todo/navigation-trace')
    assert not public_allowed('GET', '/v1/mobile/todo/navigation-trace')


def test_mobile_emoji_roundtrip_and_quick_edit_preservation(env):
    c, s = env
    directory = s.directory('alice', 'Emoji')
    created = c.post('/v1/mobile/todo/tasks', json={
        'directory_id': directory['id'], 'title': 'Task', 'emoji': '👩🏽‍💻',
    })
    assert created.status_code == 200
    task = created.json()
    assert task['emoji'] == '👩🏽‍💻'
    assert c.get('/v1/mobile/todo').json()['tasks'][0]['emoji'] == '👩🏽‍💻'
    url = '/v1/mobile/todo/tasks/' + task['id']
    saved = c.put(url, json={'title': 'Task', 'revision': task['revision'],
                            'status': 'in_progress', 'progress': 25}).json()
    assert saved['emoji'] == '👩🏽‍💻'
    for emoji in ['🚀', '']:
        response = c.put(url, json={'title': 'Task', 'revision': saved['revision'], 'emoji': emoji})
        assert response.status_code == 200
        saved = response.json()
        assert saved['emoji'] == emoji
        assert s.get('alice', task['id'])['emoji'] == emoji
    for invalid in ['hello', '🚀🎯']:
        assert c.put(url, json={'title': 'Task', 'revision': saved['revision'],
                               'emoji': invalid}).status_code == 422


def test_mobile_emoji_generation_scope_and_drafts(env, monkeypatch):
    c, s = env
    calls = []
    async def generate(runtime, store, principal, request, body, task_id=None):
        calls.append((principal.actor_user_id, task_id, body.title))
        return {'emoji': '🚀'}
    monkeypatch.setattr('ai2apps.web.mobile_todo.generate_task_emoji', generate)
    path = '/v1/mobile/todo/emoji/suggest'
    assert public_allowed('POST', path)
    assert not public_allowed('GET', path)
    assert c.post(path, json={'title': 'Draft'}).json() == {'emoji': '🚀'}
    assert s.snapshot('alice')['tasks'] == []
    own = s.save('alice', {'title': 'Own', 'directory_id': s.directory('alice', 'Own')['id']})
    assert c.post(path, json={'title': 'Edited', 'task_id': own['id']}).status_code == 200
    foreign = s.save('bob', {'title': 'Private', 'directory_id': s.directory('bob', 'Private')['id']})
    assert c.post(path, json={'title': 'Private', 'task_id': foreign['id']}).status_code == 404
    assert len(calls) == 2
    assert s.get('alice', own['id'])['emoji'] == ''


def test_mobile_emoji_missing_model(env):
    c, _ = env
    response = c.post('/v1/mobile/todo/emoji/suggest', json={'title': 'Draft'})
    assert response.status_code == 409
    assert 'Standard tasks model' in response.json()['detail']


def test_mobile_attachment_list_preview_and_owner_boundary(env):
    import io
    from PIL import Image
    c,s=env
    d=s.directory('alice','Photos')
    task=s.save('alice',{'directory_id':d['id'],'title':'Photo task'})
    content=io.BytesIO()
    Image.new('RGB',(20,10),'blue').save(content,format='PNG')
    file=s.add_attachment('alice',task['id'],'photo.png',content.getvalue())
    url='/v1/mobile/todo/attachments/'+file['id']
    assert c.get('/v1/mobile/todo').json()['attachments'][0]['id']==file['id']
    assert c.get(url).content==content.getvalue()
    response=c.get(url+'?preview=true')
    assert response.status_code==200 and response.headers['content-type']=='image/png'
    other=s.directory('bob','Private')
    foreign=s.save('bob',{'directory_id':other['id'],'title':'Private'})
    secret=s.add_attachment('bob',foreign['id'],'secret.png',content.getvalue())
    assert c.get('/v1/mobile/todo/attachments/'+secret['id']+'?preview=true').status_code==404
    s.lifecycle('alice',task['id'],'archive')
    assert c.get('/v1/mobile/todo').json()['attachments']==[]
    assert c.get(url+'?preview=true').status_code==404
    assert public_allowed('GET',url)
    assert not public_allowed('DELETE',url)
    assert not public_allowed('POST',url)
