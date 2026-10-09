from datetime import UTC, datetime, timedelta
import json
import pytest
from ai2apps.todo.store import TodoStore
from ai2apps.todo.models import TaskInput


def body(t):
    return {k:t[k] for k in TaskInput.model_fields}


def test_activity_changes_noop_owner_and_path(tmp_path):
    s=TodoStore(tmp_path);d=s.directory('alice','Work')
    parent=s.save('alice',{'directory_id':d['id'],'title':'Parent'})
    t=s.save('alice',{'directory_id':d['id'],'parent_id':parent['id'],'title':'Child'})
    t=s.save('alice',{**body(t),'progress':25},t['id'],t['revision'])
    events=s.activity('alice',task_id=parent['id'])['events']
    assert events[0]['changes']['progress']=={'before':0,'after':25}
    assert events[0]['path']=='Work / Parent / Child'
    assert len(events)==3
    s.save('alice',body(t),t['id'],t['revision'])
    assert len(s.activity('alice')['events'])==3
    assert s.activity('bob')['events']==[]
    s.lifecycle('alice',t['id'],'archive')
    assert 'archived_at' in s.activity('alice')['events'][0]['changes']
    s.lifecycle('alice',t['id'],'restore')
    assert s.activity('alice')['events'][0]['changes']['archived_at']['after'] is None


def test_activity_transaction_retention_pagination_and_schedule(tmp_path):
    s=TodoStore(tmp_path);d=s.directory('alice','Work')
    t=s.save('alice',{'directory_id':d['id'],'title':'One','progress':30})
    with pytest.raises(RuntimeError):
        with s.connect() as db:
            value={**body(t),'progress':50}
            db.execute('UPDATE tasks SET data=? WHERE id=?',(json.dumps(value),t['id']))
            raise RuntimeError('rollback')
    assert len(s.activity('alice')['events'])==1
    # Scheduler writes through SQL, not Store.save, and must also be recorded.
    with s.connect() as db:
        value={**body(t),'status':'not_started','progress':0}
        db.execute('UPDATE tasks SET data=? WHERE id=?',(json.dumps(value),t['id']))
    page=s.activity('alice',limit=1)
    assert page['events'][0]['changes']['progress']=={'before':30,'after':0}
    assert len(s.activity('alice',before_id=page['next_cursor'])['events'])==1
    with s.connect() as db:
        db.execute("UPDATE activity SET happened_at=?",((datetime.now(UTC)-timedelta(days=31)).isoformat(),))
    assert s.activity('alice',days=30)['events']==[]
    with s.connect() as db:
        assert db.execute('SELECT count(*) FROM activity').fetchone()[0]==0


def test_activity_calendar_days_and_api_scope(tmp_path):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.api.todo import create_todo_router
    from ai2apps.identity import RequestPrincipal
    s=TodoStore(tmp_path);d=s.directory('local','Own')
    t=s.save('local',{'directory_id':d['id'],'title':'Today'})
    other=s.save('bob',{'directory_id':s.directory('bob','Private')['id'],'title':'Secret'})
    app=FastAPI();app.include_router(create_todo_router(lambda:SimpleNamespace(todo=SimpleNamespace(store=s)),RequestPrincipal.legacy_local))
    with TestClient(app) as c:
        result=c.get('/todo/activity?timezone=Asia/Shanghai').json()
        assert len(result['events'])==1 and result['recording_started_at']
        from zoneinfo import ZoneInfo
        expected=datetime.now(UTC).astimezone(ZoneInfo('Asia/Shanghai')).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(UTC)
        assert datetime.fromisoformat(result['since'])==expected
        assert c.get('/todo/activity?days=31').status_code==422
        assert c.get('/todo/activity?timezone=Invalid').status_code==422
        assert c.get('/todo/activity?task_id='+other['id']).status_code==404
        assert c.get('/todo/activity?directory_id='+other['directory_id']).json()['events']==[]
