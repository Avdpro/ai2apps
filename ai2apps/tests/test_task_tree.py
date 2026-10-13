import json
import concurrent.futures
import pytest
from ai2apps.storage import PlatformDatabase
from ai2apps.browser.task_tree import TaskTreeRepository
from ai2apps.browser.tasks import BrowserTaskRepository


@pytest.fixture
def repositories(tmp_path):
    db = PlatformDatabase(tmp_path/'tasks.sqlite'); db.initialize()
    return TaskTreeRepository(db), BrowserTaskRepository(db)


def child(tree, tasks, parent, profile='default'):
    return tasks.enqueue('owner', profile, '', '', '', 'Read', {}, parent_task_id=parent)


def test_nested_identity_owner_isolation_and_terminal_parent(repositories):
    tree, tasks = repositories
    tree.create('owner', 'root', 'Update')
    tree.create('owner', 'source', 'F1', parent_id='root')
    leaf = child(tree, tasks, 'source')
    assert (leaf['root_task_id'], leaf['parent_task_id']) == ('root', 'source')
    with pytest.raises(ValueError):
        tasks.enqueue('other', 'default', '', '', '', 'Read', {}, parent_task_id='source')
    with pytest.raises(ValueError):tree.create('owner', 'source', 'Moved', parent_id=None)
    assert tree.list('other') == []


def test_group_serial_execution_and_different_profiles(repositories):
    tree, tasks = repositories
    tree.create('owner', 'root', 'Update')
    tasks.configure('owner', 2, 2)
    for profile in ('a', 'a', 'b'):child(tree, tasks, 'root', profile)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        claimed = [t for t in pool.map(lambda _:tasks.claim('owner', 'worker'), range(4)) if t]
    assert len(claimed) == 2
    assert {t['profile_key'] for t in claimed} == {'a', 'b'}
    assert len({t['root_task_id'] for t in claimed}) == 1
    tasks.update('owner', next(t for t in claimed if t['profile_key']=='a')['id'], status='completed')
    assert tasks.claim('owner', 'worker')['profile_key'] == 'a'


def test_composite_parent_does_not_hold_browser_slot(repositories):
    tree, tasks = repositories
    tree.create('owner', 'root', 'Update')
    tasks.configure('owner', 1, 1)
    one = child(tree, tasks, 'root')
    two = child(tree, tasks, 'root')
    assert tasks.claim('owner', 'worker')['id'] == one['id']
    tasks.update('owner', one['id'], status='completed')
    assert tasks.claim('owner', 'worker')['id'] == two['id']


def test_completion_waits_for_cleanup_and_recovers(repositories):
    tree, tasks = repositories
    tree.create('owner', 'root', 'Update')
    tree.create('owner', 'source', 'F1', parent_id='root')
    one = child(tree, tasks, 'source')
    tasks.update('owner', one['id'], status='completed', run_id='run', browser_context_json=json.dumps({'created_by_run':'run'}))
    assert not tree.finish('owner', 'source')
    assert not tree.finish('owner', 'root')
    assert tasks.claim('owner', 'worker') is None
    tasks.update('owner', one['id'], browser_context_json=json.dumps({'cleanup':{'state':'verified'}}))
    restored = TaskTreeRepository(tree.database)
    restored.reconcile()
    assert restored.get('owner', 'root')['status'] == 'completed'


def test_cancel_descendants_and_block_new_work(repositories):
    tree, tasks = repositories
    tree.create('owner', 'root', 'Update')
    tree.create('owner', 'source', 'F1', parent_id='root')
    one = child(tree, tasks, 'source')
    tasks.update('owner', one['id'], status='running', run_id='run')
    two = child(tree, tasks, 'source')
    assert tree.cancel('owner', 'root') == ['run']
    assert tasks.get('owner', two['id'])['status'] == 'cancelled'
    with pytest.raises(ValueError):child(tree, tasks, 'source')
    assert tasks.get('owner', one['id'])['status'] == 'cancelling'
    assert tree.get('owner', 'root')['status'] == 'finishing'
    tasks.update('owner', one['id'], status='cancelled', browser_context_json=json.dumps({'cleanup':{'state':'verified'}}))
    tree.reconcile()
    assert tree.get('owner', 'root')['status'] == 'cancelled'


def test_pending_cleanup_holds_group_but_unbound_failure_does_not(repositories):
    tree, tasks = repositories
    tree.create('owner', 'root', 'Update')
    one = child(tree, tasks, 'root')
    two = child(tree, tasks, 'root')
    tasks.claim('owner', 'worker')
    tasks.update('owner', one['id'], status='completed', run_id='run',
                 browser_context_json=json.dumps({'created_by_run':'run', 'cleanup':{'state':'pending'}}))
    assert tasks.claim('owner', 'worker') is None
    tasks.update('owner', one['id'], browser_context_json=json.dumps({'created_by_run':'run', 'cleanup':{'state':'verified'}}))
    assert tasks.claim('owner', 'worker')['id'] == two['id']
    tasks.update('owner', two['id'], status='failed', run_id='unbound')
    tree.reconcile()
    assert tree.finish('owner', 'root', 'failed')


def test_idempotency_cannot_reparent_browser_task(repositories):
    tree, tasks = repositories
    tree.create('owner', 'one', 'One')
    tree.create('owner', 'two', 'Two')
    kwargs = dict(session_id='session', idempotency_key='stable', parent_task_id='one')
    original = tasks.enqueue('owner', 'default', '', '', '', 'Read', {}, **kwargs)
    assert tasks.enqueue('owner', 'default', '', '', '', 'Read', {}, **kwargs)['id'] == original['id']
    with pytest.raises(ValueError):
        tasks.enqueue('owner', 'default', '', '', '', 'Read', {}, **{**kwargs, 'parent_task_id':'two'})


def test_source_finish_waits_for_reusable_page_cleanup(repositories):
    tree,tasks=repositories
    tree.create('owner','root','Update')
    tree.create('owner','source','Source',parent_id='root')
    task=tasks.enqueue('owner','default','','','','Read',{},parent_task_id='source',reuse_page=True)
    assert task['browser_context']['reuse_scope']=='source'
    context={'created_by_run':'run','reuse_scope':'source','cleanup':{'state':'retained'}}
    tasks.update('owner',task['id'],status='completed',browser_context_json=json.dumps(context))
    tree.finish('owner',task['execution_task_id'])
    assert not tree.finish('owner','source')
    assert not tree.finish('owner','root')
    context['cleanup']['state']='verified'
    tasks.update('owner',task['id'],browser_context_json=json.dumps(context))
    tree.reconcile()
    assert tree.get('owner','root')['status']=='completed'
