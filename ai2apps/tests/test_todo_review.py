import json
import pytest
from ai2apps.todo.store import TodoStore


def fixture(tmp_path, status='ended'):
    store = TodoStore(tmp_path)
    directory = store.directory('alice', 'Work')
    task = store.save('alice', dict(title='Task', directory_id=directory['id'], highlight='lime', progress=45, status='in_progress'))
    with store.connect() as db:
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?)', ('run','alice',task['id'],status,json.dumps({'output':'Evidence'})))
    return store, task


def test_review_atomic_persistent_and_idempotent(tmp_path):
    store, task = fixture(tmp_path)
    result = store.review_run('alice','run','completed',task['revision'])
    saved = store.get('alice',task['id'])
    assert (saved['status'],saved['progress'],saved['completed']) == ('completed',100,True)
    assert saved['highlight']=='lime' and saved['revision']==task['revision']+1
    assert store.review_run('alice','run','completed',task['revision'])==result
    run=TodoStore(tmp_path).snapshot('alice')['runs'][0]
    assert run['status']=='ended' and run['output']=='Evidence' and run['review']==result
    with pytest.raises(ValueError): store.review_run('alice','run','continue',saved['revision'])


@pytest.mark.parametrize('initial,expected',[(45,45),(100,0)])
def test_continue_reopens_without_inventing_progress(tmp_path,initial,expected):
    store, task=fixture(tmp_path)
    with store.connect() as db:
        raw=json.loads(db.execute('SELECT data FROM tasks').fetchone()['data'])
        raw.update(progress=initial,status='completed' if initial==100 else 'in_progress',completed=initial==100)
        db.execute('UPDATE tasks SET data=?',(json.dumps(raw),))
    store.review_run('alice','run','continue',task['revision'])
    saved=store.get('alice',task['id'])
    assert saved['status']=='in_progress' and saved['progress']==expected and not saved['completed']


def test_review_rejects_foreign_stale_and_superseded(tmp_path):
    store,task=fixture(tmp_path)
    with pytest.raises(KeyError): store.review_run('bob','run','completed',task['revision'])
    with pytest.raises(ValueError): store.review_run('alice','run','completed',999)
    with store.connect() as db:
        assert 'review' not in json.loads(db.execute('SELECT data FROM runs').fetchone()['data'])
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?)',('new','alice',task['id'],'running','{}'))
    with pytest.raises(ValueError): store.review_run('alice','run','completed',task['revision'])
    with pytest.raises(ValueError): store.review_run('alice','new','completed',task['revision'])
    assert store.get('alice',task['id'])['progress']==45
