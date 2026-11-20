import json
import pytest
from ai2apps.todo.store import TodoStore

@pytest.mark.parametrize('registration',['arbitrary.owner.alpha','different.owner.beta'])
def test_owner_plan_cas_receipt_and_immutable_existing_run_snapshot(tmp_path,registration):
    store=TodoStore(tmp_path);binding={'registration':registration,'binding':{'version':1}}
    old=store.save('owner',{'title':'Original','description':'old instructions','model':'fixture','executor':'managed','directory_id':'','schedule':{'frequency':'daily','hour':1}},creation_key='initial',create_inbox=True,execution_binding=binding,execution_lane='arbitrary-lane')
    snapshot={'snapshot':old,'execution_binding':binding}
    with store.connect() as db:db.execute("INSERT INTO runs VALUES('existing','owner',?,'running',?)",(old['id'],json.dumps(snapshot)))
    changes={'description':'new instructions','schedule':{**old['schedule'],'hour':2}};new_binding={'version':2}
    result=store.update_execution_plan('owner',old['id'],old['revision'],registration,changes,new_binding,'change')
    assert store.update_execution_plan('owner',old['id'],old['revision'],registration,changes,new_binding,'change')==result
    with store.connect() as db:assert json.loads(db.execute("SELECT data FROM runs WHERE id='existing'").fetchone()[0])==snapshot
    assert store.execution_binding('owner',old['id'])['binding']==new_binding
    with pytest.raises(ValueError):store.update_execution_plan('owner',old['id'],old['revision'],registration,changes,new_binding,'conflict')
    with pytest.raises(PermissionError):store.update_execution_plan('other',old['id'],2,registration,changes,new_binding,'wrong-owner')
    with pytest.raises(PermissionError):store.update_execution_plan('owner',old['id'],2,'wrong-registration',changes,new_binding,'wrong-owner')
