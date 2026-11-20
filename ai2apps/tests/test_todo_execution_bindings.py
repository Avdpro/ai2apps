"""Trusted execution ownership is independent of business/provider identities."""
import asyncio,json
from datetime import UTC,datetime,timedelta
import pytest
from ai2apps.identity import RequestPrincipal
from ai2apps.todo.execution import TodoExecutionAdapter
from ai2apps.todo.models import Schedule,next_due,latest_due,TaskInput
from ai2apps.todo.store import TodoStore
from ai2apps.todo.transfer import export_backup,merge_backup
from test_todo import service
P=RequestPrincipal.legacy_local


def managed(s,registration='unrelated.owner/v1',schedule=None):
 return s.store.save('local',{'title':'Owned task','directory_id':'','model':'fixture','executor':'managed','schedule':schedule or {}},creation_key='owned-task',create_inbox=True,
     execution_binding={'registration':registration,'binding':{'opaque':'frozen fixture'}},execution_lane='unrelated:lane')


def test_atomic_binding_and_idempotent_launch_never_falls_back(tmp_path,monkeypatch):
 s=service(tmp_path);task=managed(s)
 with s.store.connect() as db:
  assert db.execute('SELECT 1 FROM task_execution_bindings WHERE task_id=?',(task['id'],)).fetchone()
  assert db.execute('SELECT lane FROM task_execution_lanes WHERE task_id=?',(task['id'],)).fetchone()[0]=='unrelated:lane'
 with pytest.raises(ValueError,match='owner is unavailable'):s.launch('local',task['id'],principal=P())
 seen=[]
 async def start(*args):raise AssertionError('Not dispatched in this test')
 adapter=TodoExecutionAdapter('unrelated.owner/v1',lambda a,t,b:seen.append(b),start)
 s.register_execution_adapter(adapter);monkeypatch.setattr(s,'dispatch_queue',lambda:None)
 first=s.launch('local',task['id'],principal=P(),request_key='intent-one')
 assert s.launch('local',task['id'],principal=P(),request_key='intent-one')==first
 s.store.run_update(first['id'],'completed')
 assert s.launch('local',task['id'],principal=P(),request_key='intent-one')==first
 assert len(s.store.snapshot('local')['runs'])==1
 with pytest.raises(ValueError,match='controls this assignment'):s.store.bind_execution_lane('local',task['id'],None,expected_lane='unrelated:lane')
 with pytest.raises(Exception):TaskInput.model_validate({'title':'Forged','directory_id':task['directory_id'],'execution_binding':{'registration':'forged'}})


@pytest.mark.asyncio
async def test_restore_recovers_original_receipt_without_new_executor(tmp_path,monkeypatch):
 s=service(tmp_path);t=managed(s)
 async def start(*args):raise AssertionError('Recovery must not restart execution')
 restored=[]
 def restore(owner,run_id,data):restored.append(run_id);return {'agent_run_id':'durable-arbitrary-run','session_id':'owned-session'}
 s.register_execution_adapter(TodoExecutionAdapter('unrelated.owner/v1',lambda *a:None,start,restore=restore))
 monkeypatch.setattr(s,'dispatch_queue',lambda:None)
 run=s.launch('local',t['id'],principal=P())
 s.store.run_update(run['id'],'running',todo_queued=False)
 recovered=service(tmp_path);recovered.register_execution_adapter(s.execution_adapters['unrelated.owner/v1'])
 watched=[]
 async def watch(id,agent_id):watched.append((id,agent_id));await asyncio.Event().wait()
 monkeypatch.setattr(recovered,'watch_internal',watch)
 try:
  await recovered.startup();await asyncio.sleep(0)
  assert restored==[run['id']]
  assert watched==[(run['id'],'durable-arbitrary-run')]
  assert len(recovered.store.snapshot('local')['runs'])==1
 finally:await recovered.shutdown()


def test_once_schedule_with_explicit_offset_is_consumed_once(tmp_path):
 now=datetime(2026,11,3,0,tzinfo=UTC);when=now+timedelta(hours=2)
 schedule=Schedule(frequency='once',once_at='2026-11-03T10:00:00+08:00').model_dump()
 assert next_due(schedule,now)==when
 assert next_due(schedule,when) is None and latest_due(schedule,when)==when
 with pytest.raises(ValueError):Schedule(frequency='once',once_at='2026-11-03T10:00')
 s=service(tmp_path);t=s.store.save('local',{'title':'Once','directory_id':'','model':'fixture','schedule':schedule},create_inbox=True)
 # Force an explicit due slot, independent of the machine's current date.
 with s.store.connect() as db:db.execute('UPDATE tasks SET next_due=? WHERE id=?',(when.isoformat(),t['id']))
 calls=[];s.launch=lambda *args:calls.append(args)
 s.tick(when);s.tick(when+timedelta(minutes=1))
 assert len(calls)==1 and s.store.get('local',t['id'])['next_due'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('projection_fails',[False,True])
async def test_arbitrary_owner_observes_original_status_without_controlling_execution(tmp_path,monkeypatch,projection_fails):
 from types import SimpleNamespace
 s=service(tmp_path);t=managed(s);seen=[]
 async def start(*args):raise AssertionError('Observer must not launch another execution')
 def observe(owner,id,status,data):
  seen.append((owner,id,status,data['execution_binding']['registration']))
  if projection_fails:raise RuntimeError('Synthetic projection failure')
 s.register_execution_adapter(TodoExecutionAdapter('unrelated.owner/v1',lambda *a:None,start,observe=observe))
 monkeypatch.setattr(s,'dispatch_queue',lambda:None)
 result=s.launch('local',t['id'],principal=P())
 s.runtime.agents=SimpleNamespace(get_run=lambda _:SimpleNamespace(status='waiting_input',output=None,error=None,finished_at=None),get_status_line=lambda _:SimpleNamespace(text='Waiting in original executor'))
 watcher=asyncio.create_task(s.watch_internal(result['id'],'original-agent-run'))
 try:
  for _ in range(50):
   if seen:break
   await asyncio.sleep(.01)
  assert seen==[('local',result['id'],'waiting_input','unrelated.owner/v1')]
  assert s.store.snapshot('local')['runs'][0]['status']=='waiting_input'
  assert len(s.store.snapshot('local')['runs'])==1
 finally:
  watcher.cancel();await asyncio.gather(watcher,return_exceptions=True)


def test_portable_backup_cannot_turn_managed_work_into_general_execution(tmp_path):
 source=service(tmp_path/'source');managed(source,schedule={'frequency':'daily','hour':6})
 target=service(tmp_path/'target');content=export_backup(source.store,'local')
 preview=merge_backup(target.store,'local',content);merge_backup(target.store,'local',content,preview['expected'])
 imported=target.store.snapshot('local')['tasks'][0]
 assert imported['next_due'] is None
 binding=target.store.execution_binding('local',imported['id'])
 assert binding['registration']=='owner-review-required'
 assert 'frozen fixture' not in json.dumps(binding)
 with pytest.raises(ValueError,match='owner is unavailable'):target.launch('local',imported['id'],principal=P())


@pytest.mark.parametrize('registration',['arbitrary.alpha/v1','unrelated.beta/v3'])
def test_trusted_admitted_snapshot_survives_plan_edit_but_not_task_deletion(tmp_path,monkeypatch,registration):
 s=service(tmp_path);task=managed(s,registration)
 accepted=[]
 def validate(owner,snapshot,binding):
  assert owner=='local' and snapshot['id']==task['id'] and binding=={'opaque':'frozen fixture'}
  accepted.append(snapshot['description'])
 async def start(*args):raise AssertionError('No fixture execution')
 s.register_execution_adapter(TodoExecutionAdapter(registration,validate,start));monkeypatch.setattr(s,'dispatch_queue',lambda:None)
 admitted={'task':task,'binding':s.store.execution_binding('local',task['id'])}
 with s.store.connect() as db:
  data=json.loads(db.execute('SELECT data FROM tasks WHERE id=?',(task['id'],)).fetchone()[0]);data['description']='Revised future work'
  db.execute('UPDATE tasks SET data=?,revision=revision+1 WHERE id=?',(json.dumps(data),task['id']))
 run=s.launch('local',task['id'],principal=P(),request_key='admitted-original',admitted=admitted)
 with s.store.connect() as db:
  saved=json.loads(db.execute('SELECT data FROM runs WHERE id=?',(run['id'],)).fetchone()[0])
 assert saved['snapshot']['description']==task['description'] and accepted==[task['description']]
 s.store.run_update(run['id'],'completed');s.store.delete('local',task['id'])
 with pytest.raises(ValueError,match='Restore'):s.launch('local',task['id'],principal=P(),request_key='new-after-delete',admitted=admitted)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["cancelled", "failed"])
async def test_original_terminal_status_recovers_after_todo_write_failure(tmp_path, monkeypatch, status):
    import sqlite3
    from types import SimpleNamespace

    s = service(tmp_path)
    task = managed(s)
    receipts = []

    async def start(*args):
        pytest.fail("Recovery must not launch a second execution")

    def finished(owner, run_id, result, data):
        receipts.append((run_id, result, data["finished_at"]))

    s.register_execution_adapter(TodoExecutionAdapter(
        "unrelated.owner/v1", lambda *args: None, start, finished=finished,
    ))
    monkeypatch.setattr(s, "dispatch_queue", lambda: None)
    run_id = s.launch("local", task["id"], principal=P())["id"]
    s.store.run_update(run_id, "running", agent_run_id="original-agent", todo_queued=False)
    ended = datetime.now(UTC)
    original = SimpleNamespace(status=status, output=None, error=None, finished_at=ended, session_id="original-session")
    s.runtime.agents = SimpleNamespace(get_run=lambda _: original, get_status_line=lambda _: SimpleNamespace(text=status))
    s.runtime.workspace = SimpleNamespace(list_artifacts=lambda _: [])
    write = s.store.run_update

    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(s.store, "run_update", unavailable)
    await s.watch_internal(run_id, "original-agent")
    assert s.store.snapshot("local")["runs"][0]["status"] == "running"

    monkeypatch.setattr(s.store, "run_update", write)
    s.recover_run_watchers()
    watcher = s.jobs[run_id]
    s.recover_run_watchers()
    assert s.jobs[run_id] is watcher
    await watcher
    assert s.store.snapshot("local")["runs"][0]["status"] == status
    assert receipts == [(run_id, status, ended.isoformat())]
