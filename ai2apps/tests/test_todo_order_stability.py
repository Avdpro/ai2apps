import json
from ai2apps.todo.store import TodoStore
from ai2apps.todo.models import TaskInput


def test_legacy_tied_positions_stay_in_place_on_edit(tmp_path):
    store=TodoStore(tmp_path)
    d=store.directory('alice','Work')
    tasks=[store.save('alice',{'title':title,'directory_id':d['id']}) for title in ['A','B','C']]
    with store.connect() as db:
        for t in tasks:
            data=json.loads(db.execute('SELECT data FROM tasks WHERE id=?',(t['id'],)).fetchone()['data'])
            data['position']=0
            db.execute('UPDATE tasks SET data=? WHERE id=?',(json.dumps(data),t['id']))
    first=store.get('alice',tasks[0]['id'])
    body={k:v for k,v in first.items() if k in TaskInput.model_fields}
    body.update(title='Edited',description='Details',progress=30,priority='U',highlight='lime',position=999)
    store.save('alice',body,first['id'],first['revision'])
    reopened=TodoStore(tmp_path)
    assert [t['id'] for t in reopened.snapshot('alice')['tasks']]==[t['id'] for t in tasks]
    assert reopened.get('alice',first['id'])['position']==0
    added=reopened.save('alice',{'title':'D','directory_id':d['id']})
    assert added['position']==1


def test_manual_order_survives_subsequent_save(tmp_path):
    store=TodoStore(tmp_path);d=store.directory('alice','Work')
    a,b=[store.save('alice',{'title':x,'directory_id':d['id']}) for x in ['A','B']]
    store.reorder('alice',d['id'],None,[{'id':b['id'],'revision':b['revision']},{'id':a['id'],'revision':a['revision']}])
    a=store.get('alice',a['id']);body={k:v for k,v in a.items() if k in TaskInput.model_fields}
    body.update(completed=True,position=0)
    store.save('alice',body,a['id'],a['revision'])
    rows=sorted(store.snapshot('alice')['tasks'],key=lambda t:t['position'])
    assert [t['id'] for t in rows]==[b['id'],a['id']]
