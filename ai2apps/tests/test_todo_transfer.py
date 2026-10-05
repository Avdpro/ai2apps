import io
import json
import zipfile
from datetime import UTC, datetime, timedelta

import pytest

from ai2apps.todo.models import TaskInput
from ai2apps.todo.store import TodoStore
from ai2apps.todo.transfer import export_backup, merge_backup


def create(store, title='Root', directory=None, parent=None):
    directory = directory or store.directory('u', 'Work')['id']
    return store.save('u', {'title': title, 'directory_id': directory, 'parent_id': parent})


def apply(source, target):
    content = export_backup(source, 'u')
    preview = merge_backup(target, 'u', content)
    return merge_backup(target, 'u', content, preview['expected'])


def rewrite(content, update):
    out=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content)) as src, zipfile.ZipFile(out,'w') as dst:
        data=json.loads(src.read('todo.json'));update(data)
        for name in src.namelist():
            dst.writestr(name,json.dumps(data) if name=='todo.json' else src.read(name))
    return out.getvalue()


def test_roundtrip_tree_files_lifecycle_and_idempotency(tmp_path):
    a,b=TodoStore(tmp_path/'a'),TodoStore(tmp_path/'b')
    root=create(a); child=create(a,'Child',root['directory_id'],root['id'])
    a.add_attachment('u',child['id'],'a.txt',b'file contents')
    a.lifecycle('u',root['id'],'archive')
    preview=merge_backup(b,'u',export_backup(a,'u'))
    assert preview['create']==2 and b.snapshot('u')['tasks']==[]
    apply(a,b)
    snapshot=b.snapshot('u');assert len(snapshot['tasks'])==2
    imported={t['title']:t for t in snapshot['tasks']}
    assert imported['Child']['parent_id']==imported['Root']['id']
    assert imported['Root']['archived_at'] and imported['Child']['archived_at']
    att=snapshot['attachments'][0];assert b.attachment('u',att['id'])[1].read_bytes()==b'file contents'
    assert apply(a,b)['keep']==2 and len(b.snapshot('u')['attachments'])==1
    b.lifecycle('u',imported['Root']['id'],'restore')
    assert not any(t['archived_at'] for t in b.snapshot('u')['tasks'])


def test_newer_wins_preserves_local_only_and_replaces_attachment_set(tmp_path):
    a,b=TodoStore(tmp_path/'a'),TodoStore(tmp_path/'b');t=create(a)
    a.add_attachment('u',t['id'],'old.txt',b'old');apply(a,b)
    local=create(b,'Local only',b.snapshot('u')['directories'][0]['id'])
    old=a.snapshot('u')['attachments'][0];a.remove_attachment('u',old['id'])
    current=a.get('u',t['id']);a.save('u',{**{k:current[k] for k in TaskInput.model_fields},'description':'new'},t['id'],current['revision'])
    assert apply(a,b)['update']==1
    assert len(b.snapshot('u')['tasks'])==2 and b.snapshot('u')['attachments']==[]
    root=next(t for t in b.snapshot('u')['tasks'] if t['title']=='Root')
    b.save('u',{**{k:root[k] for k in TaskInput.model_fields},'description':'local newer'},root['id'],root['revision'])
    assert apply(a,b)['keep']==1
    assert b.get('u',root['id'])['description']=='local newer'


def test_preview_detects_changes_and_ambiguous_paths(tmp_path):
    a,b=TodoStore(tmp_path/'a'),TodoStore(tmp_path/'b');create(a)
    content=export_backup(a,'u');preview=merge_backup(b,'u',content);create(b,'Later')
    with pytest.raises(ValueError,match='变化'):merge_backup(b,'u',content,preview['expected'])
    d=a.snapshot('u')['directories'][0]['id'];create(a,'Root',d)
    with pytest.raises(ValueError,match='同名'):merge_backup(b,'u',export_backup(a,'u'))


def test_corrupt_attachment_rejected_before_writes(tmp_path):
    a,b=TodoStore(tmp_path/'a'),TodoStore(tmp_path/'b');t=create(a);a.add_attachment('u',t['id'],'a',b'hi')
    content=rewrite(export_backup(a,'u'),lambda d:d['attachments'][0].update(sha256='bad'))
    with pytest.raises(ValueError,match='integrity'):merge_backup(b,'u',content)
    assert b.snapshot('u')['directories']==[]


def test_history_is_inert_idempotent_and_owner_scoped(tmp_path):
    a,b=TodoStore(tmp_path/'a'),TodoStore(tmp_path/'b');t=create(a)
    with a.connect() as db:
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?)',('run1','u',t['id'],'running',json.dumps({'agent_run_id':'secret-session','terminal_id':'live-terminal','output':'hello'})))
    apply(a,b);apply(a,b)
    runs=b.snapshot('u')['runs'];assert len(runs)==1 and runs[0]['status']=='interrupted'
    assert 'agent_run_id' not in runs[0] and 'terminal_id' not in runs[0]
    assert b.snapshot('other')['tasks']==[]
    with b.connect() as db:db.execute("UPDATE runs SET status='queued'")
    with pytest.raises(ValueError,match='停止'):merge_backup(b,'u',export_backup(a,'u'))


def test_import_restarts_schedule_in_future_and_tracks_timestamps(tmp_path):
    a,b=TodoStore(tmp_path/'a'),TodoStore(tmp_path/'b');t=create(a)
    t=a.save('u',{**{k:t[k] for k in TaskInput.model_fields},'schedule':{'frequency':'daily','auto_execute':False}},t['id'],t['revision'])
    apply(a,b);saved=b.snapshot('u')['tasks'][0]
    assert datetime.fromisoformat(saved['next_due'])>datetime.now(UTC)
    assert not saved['schedule']['auto_execute'] and saved['updated_at']==t['updated_at']
    aid=a.add_attachment('u',t['id'],'x',b'x')['id'];with_file=a.get('u',t['id'])
    assert with_file['updated_at']>t['updated_at']
    a.remove_attachment('u',aid);assert a.get('u',t['id'])['updated_at']>with_file['updated_at']


def test_merge_file_write_failure_rolls_back_metadata(tmp_path, monkeypatch):
    from pathlib import Path
    a,b=TodoStore(tmp_path/'a'),TodoStore(tmp_path/'b');t=create(a);a.add_attachment('u',t['id'],'a',b'hi')
    content=export_backup(a,'u');preview=merge_backup(b,'u',content)
    def fail(*args,**kwargs):raise OSError('disk full')
    monkeypatch.setattr(Path,'write_bytes',fail)
    with pytest.raises(OSError,match='disk full'):merge_backup(b,'u',content,preview['expected'])
    assert b.snapshot('u')['tasks']==[] and b.snapshot('u')['directories']==[]


def test_backup_api_preview_and_import(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from types import SimpleNamespace
    from ai2apps.api.todo import create_todo_router
    from ai2apps.identity import RequestPrincipal
    store=TodoStore(tmp_path/'target');source=TodoStore(tmp_path/'source');create(source)
    app=FastAPI();app.include_router(create_todo_router(lambda:SimpleNamespace(todo=SimpleNamespace(store=store)),lambda:RequestPrincipal.legacy_local()))
    client=TestClient(app);content=export_backup(source,'u')
    preview=client.post('/todo/backup/preview',files={'file':('backup.zip',content,'application/zip')})
    assert preview.status_code==200 and preview.json()['create']==1
    result=client.post('/todo/backup/import',files={'file':('backup.zip',content,'application/zip')},data={'expected':preview.json()['expected']})
    assert result.status_code==200
    assert len(store.snapshot('local')['tasks'])==1 and store.snapshot('u')['tasks']==[]
    exported=client.get('/todo/backup');assert exported.status_code==200 and exported.headers['content-type']=='application/zip'
    invalid=client.post('/todo/backup/preview',files={'file':('bad.zip',b'bad')});assert invalid.status_code==422


def test_directory_export_scopes_tree_files_history_and_owner(tmp_path):
    store=TodoStore(tmp_path/'source');target=TodoStore(tmp_path/'target')
    root=create(store);child=create(store,'Child',root['directory_id'],root['id'])
    other=create(store,'Other',store.directory('u','Other folder')['id'])
    for t in (root,child,other):
        store.add_attachment('u',t['id'],t['title']+'.txt',t['title'].encode())
        with store.connect() as db:
            db.execute('INSERT INTO runs VALUES(?,?,?,?,?)',(t['id'],'u',t['id'],'completed',json.dumps({'output':t['title']})))
    content=export_backup(store,'u',root['directory_id'])
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        data=json.loads(archive.read('todo.json'))
        assert len(data['directories'])==1
        assert {t['title'] for t in data['tasks']}=={'Root','Child'}
        assert len(data['attachments'])==len(data['runs'])==2
        assert len(archive.namelist())==3
    preview=merge_backup(target,'u',content)
    merge_backup(target,'u',content,preview['expected'])
    assert len(target.snapshot('u')['tasks'])==2
    with pytest.raises(KeyError):export_backup(store,'other-user',root['directory_id'])
    with pytest.raises(KeyError):export_backup(store,'u','missing')
    empty=store.directory('u','Empty')['id']
    with zipfile.ZipFile(io.BytesIO(export_backup(store,'u',empty))) as archive:
        data=json.loads(archive.read('todo.json'))
        assert data['directories'][0]['title']=='Empty' and data['tasks']==data['attachments']==data['runs']==[]


def test_highlight_roundtrip_and_legacy_backup(tmp_path):
    a, b = TodoStore(tmp_path/'source'), TodoStore(tmp_path/'target')
    t = create(a)
    a.save('u', {**{k:t[k] for k in TaskInput.model_fields}, 'highlight':'lime'}, t['id'], t['revision'])
    apply(a, b)
    assert b.snapshot('u')['tasks'][0]['highlight'] == 'lime'
    legacy = rewrite(export_backup(a, 'u'), lambda data: [t.pop('highlight', None) for t in data['tasks']])
    c = TodoStore(tmp_path/'legacy')
    preview = merge_backup(c, 'u', legacy)
    merge_backup(c, 'u', legacy, preview['expected'])
    assert c.snapshot('u')['tasks'][0]['highlight'] == ''
