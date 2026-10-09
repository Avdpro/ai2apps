import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.todo import create_todo_router
from ai2apps.identity import RequestPrincipal
from ai2apps.todo.models import TaskInput, latest_due, next_due
from ai2apps.todo.service import TodoService
from ai2apps.terminal import TerminalManager
from ai2apps.todo.store import TodoStore


def stamp(s):
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


@pytest.fixture
def store(tmp_path):
    return TodoStore(tmp_path)


def task(store, owner="alice", **values):
    directory = store.directory(owner, "Work")
    return store.save(
        owner, {"title": "Project", "directory_id": directory["id"], **values}
    )


def body(t):
    return {
        k: v
        for k, v in t.items()
        if k in TaskInput.model_fields
    }


def test_owner_isolation_and_cycle(store):
    a = task(store)
    assert store.snapshot("bob")["tasks"] == []
    with pytest.raises(KeyError):
        store.get("bob", a["id"])
    with pytest.raises(KeyError):
        store.save("bob", body(a))
    b = store.save("alice", {**body(a), "parent_id": a["id"], "title": "Child"})
    with pytest.raises(ValueError, match="itself"):
        store.save("alice", {**body(a), "parent_id": b["id"]}, a["id"], a["revision"])
    store.delete("alice", a["id"])
    assert store.get("alice", b["id"])["deleted_at"]


def test_optimistic_write_and_persistence(store):
    a = task(store)
    b = store.save("alice", {**body(a), "title": "Updated"}, a["id"], a["revision"])
    with pytest.raises(ValueError, match="changed"):
        store.save("alice", body(a), a["id"], a["revision"])
    assert TodoStore(store.root).get("alice", a["id"])["title"] == b["title"]


def test_attachments_owner_and_immutable_blob(store):
    a = task(store)
    x = store.add_attachment("alice", a["id"], "../../one.txt", b"one")
    store.add_attachment("alice", a["id"], "two.txt", b"two")
    assert len(store.snapshot("alice")["attachments"]) == 2
    meta, path = store.attachment("alice", x["id"])
    assert meta["name"] == "one.txt"
    with pytest.raises(KeyError):
        store.attachment("bob", x["id"])
    store.remove_attachment("alice", x["id"])
    assert path.read_bytes() == b"one"


@pytest.mark.parametrize(
    "frequency,after,expected",
    [
        ("hourly", "2026-10-03T09:20:00", "2026-10-03T10:00:00"),
        ("daily", "2026-10-03T09:20:00", "2026-10-04T09:00:00"),
        ("weekly", "2026-10-03T09:20:00", "2026-10-05T09:00:00"),
        ("monthly", "2026-01-31T10:00:00", "2026-02-28T09:00:00"),
    ],
)
def test_schedule_slots(frequency, after, expected):
    s = {"frequency": frequency, "timezone": "UTC", "day": 31}
    assert next_due(s, stamp(after)) == stamp(expected)


def test_timezone_and_dst():
    s = {"frequency": "daily", "hour": 2, "minute": 30, "timezone": "America/New_York"}
    assert next_due(s, stamp("2026-03-08T00:00:00")) == stamp("2026-03-09T06:30:00")
    assert latest_due(
        {"frequency": "monthly", "timezone": "UTC", "day": 31},
        stamp("2026-04-12T12:00:00"),
    ) == stamp("2026-03-31T09:00:00")


def service(tmp_path):
    return TodoService(
        SimpleNamespace(
            config=SimpleNamespace(paths=SimpleNamespace(artifacts_path=tmp_path)),
            agent_runtime=None,
            terminal=TerminalManager(default_cwd=tmp_path),
        )
    )


@pytest.mark.parametrize(
    "frequency,count", [("hourly", 0), ("daily", 1), ("weekly", 1), ("monthly", 1)]
)
def test_catchup_only_latest_and_no_duplicate(tmp_path, frequency, count):
    s = service(tmp_path)
    t = task(s.store, schedule={"frequency": frequency, "timezone": "UTC"})
    now = stamp("2026-10-03T14:00:00")
    s.started = now
    with s.store.connect() as db:
        db.execute(
            "UPDATE tasks SET next_due=? WHERE id=?",
            ("2026-06-01T09:00:00+00:00", t["id"]),
        )
    calls = []
    s.launch = lambda *args: calls.append(args)
    s.tick(now)
    s.tick(now)
    assert len(calls) == count
    if count:
        assert calls[0][2] == latest_due(t["schedule"], now).isoformat()


def test_enable_schedule_does_not_backfill(store):
    t = task(store)
    t = store.save(
        "alice",
        {**body(t), "schedule": {"frequency": "daily", "timezone": "UTC"}},
        t["id"],
        t["revision"],
    )
    assert datetime.fromisoformat(t["next_due"]) > datetime.now(UTC)
    due = t["next_due"]
    t = store.save("alice", {**body(t), "title": "Rename"}, t["id"], t["revision"])
    assert t["next_due"] == due


def test_api_owner_guards_and_attachments(tmp_path):
    s = service(tmp_path)
    app = FastAPI()
    principal = RequestPrincipal.legacy_local()
    app.include_router(
        create_todo_router(lambda: SimpleNamespace(todo=s), lambda: principal)
    )
    client = TestClient(app)
    d = client.post("/todo/directories", json={"title": "Work"}).json()
    t = client.post("/todo/tasks", json={"title": "A", "directory_id": d["id"]}).json()
    assert (
        client.post(
            "/todo/tasks/" + t["id"] + "/attachments",
            files={"file": ("one.txt", b"demo")},
        ).status_code
        == 200
    )
    attachment = client.get("/todo").json()["attachments"][0]
    assert client.get("/todo/attachments/" + attachment["id"]).content == b"demo"
    assert (
        client.put(
            "/todo/tasks/" + t["id"], json={**body(t), "revision": 50}
        ).status_code
        == 422
    )
    assert client.get("/todo/attachments/unknown").status_code == 404


@pytest.mark.asyncio
async def test_external_execution_and_no_overlap(tmp_path, monkeypatch):
    s = service(tmp_path)
    # A harmless local fixture executable exercises pipes, cwd, persisted results.
    exe = tmp_path / "fake-codex"
    exe.write_text('#!/bin/sh\nprintf "\\nDONE\\n"\n')
    exe.chmod(0o755)
    monkeypatch.setattr(s, "executable", lambda _: str(exe))
    t = task(s.store, "local", executor="codex", working_directory=str(tmp_path))
    p = RequestPrincipal.legacy_local()
    run = s.launch("local", t["id"], principal=p)
    with pytest.raises(ValueError, match="active"):
        s.launch("local", t["id"], principal=p)
    job = s.jobs[run["id"]]
    await job
    saved = s.store.snapshot("local")["runs"][0]
    assert saved["status"] == "ended", (saved.get("error"), saved.get("output"))
    assert "DONE" in saved["output"]
    assert s.store.get("local", t["id"])["completed"] is False


@pytest.mark.asyncio
async def test_cancel_and_restart_recovery(tmp_path, monkeypatch):
    s = service(tmp_path)
    exe = tmp_path / "fake-codex"
    exe.write_text("#!/bin/sh\nsleep 30\n")
    exe.chmod(0o755)
    monkeypatch.setattr(s, "executable", lambda _: str(exe))
    t = task(s.store, "local", executor="codex", working_directory=str(tmp_path))
    run = s.launch("local", t["id"], principal=RequestPrincipal.legacy_local())
    await asyncio.sleep(0.05)
    await s.cancel("local", run["id"])
    assert s.store.snapshot("local")["runs"][0]["status"] == "cancelled"
    with s.store.connect() as db:
        db.execute("UPDATE runs SET status='running'")
    await s.startup()
    assert s.store.snapshot("local")["runs"][0]["status"] == "interrupted"
    await s.shutdown()


@pytest.mark.asyncio
async def test_internal_harness_uses_real_agent_repository(tmp_path):
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime

    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    from ai2apps.identity import IdentityRepository, OrganizationType

    identities = IdentityRepository(runtime.database)
    identities.bind_installation(
        installation_id="todo-test",
        cloud_device_id="device-test",
        organization_id="org-test",
        organization_type=OrganizationType.HOUSEHOLD,
        core_user_id="todo-user",
        billing_account_id="billing-test",
        access_epoch=1,
    )
    principal = identities.principal_for("todo-user")
    calls = []

    async def provider(request):
        calls.append(request)
        return {
            "choices": [{"message": {"role": "assistant", "content": "Todo result"}}]
        }

    runtime.agent_runtime.bind_model_provider(provider)
    await runtime.agent_runtime.start()
    s = TodoService(runtime)
    try:
        t = task(s.store, "todo-user", model="test-model")
        s.store.add_attachment(
            "todo-user", t["id"], "sample.txt", b"Todo attachment sample"
        )
        run = s.launch("todo-user", t["id"], principal=principal)
        await asyncio.wait_for(s.jobs[run["id"]], 8)
        record = s.store.snapshot("todo-user")["runs"][0]
        assert record["status"] == "completed", record.get("error")
        assert record["output"] == "Todo result"
        assert len(record["input_resources"]) == 1
        assert runtime.documents.list(record["session_id"])[0].filename == "sample.txt"
        assert calls
        with runtime.database.transaction() as db:
            row = db.execute(
                "SELECT owner_user_id FROM app_instances a JOIN sessions s ON s.app_instance_id=a.id WHERE s.id=?",
                (record["session_id"],),
            ).fetchone()
        assert row["owner_user_id"] == "todo-user"
    finally:
        await s.shutdown()
        await runtime.agent_runtime.stop()
        runtime.stop()


@pytest.mark.asyncio
async def test_shutdown_preserves_durable_internal_run_for_recovery(
    tmp_path, monkeypatch
):
    s = service(tmp_path)
    ready = asyncio.Event()

    async def internal(owner, id, task, prompt, attachments):
        s.store.run_update(id, "running", agent_run_id="durable-run")
        ready.set()
        return "durable-run"

    async def watch(id, agent_id):
        await asyncio.sleep(30)

    monkeypatch.setattr(s, "internal_run", internal)
    monkeypatch.setattr(s, "watch_internal", watch)
    t = task(s.store, "local", model="test-model")
    s.launch("local", t["id"], principal=RequestPrincipal.legacy_local())
    await ready.wait()
    await s.shutdown()
    record = s.store.snapshot("local")["runs"][0]
    assert record["status"] == "running"
    assert record["agent_run_id"] == "durable-run"
    recovered = []

    async def resumed(id, agent_id):
        recovered.append(agent_id)
        s.store.run_update(id, "completed")

    monkeypatch.setattr(s, "watch_internal", resumed)
    await s.startup()
    await asyncio.sleep(0)
    await s.shutdown()
    assert recovered == ["durable-run"]


@pytest.mark.parametrize("emoji", ["🎬", "👩🏽‍💻", "🇨🇳", "1️⃣", "❤️", ""])
def test_emoji_persistence_and_clear(store, emoji):
    t = task(store, emoji=emoji)
    assert TodoStore(store.root).get("alice", t["id"])["emoji"] == emoji
    updated = store.save("alice", {**body(t), "emoji": ""}, t["id"], t["revision"])
    assert updated["emoji"] == ""


@pytest.mark.parametrize("emoji", ["hello", "🎬🎵", "<script>", "a", "123"])
def test_emoji_rejects_non_single_symbol(store, emoji):
    with pytest.raises(ValueError, match="single Emoji"):
        task(store, emoji=emoji)


def test_legacy_task_without_emoji(store):
    import json

    t = task(store)
    old = body(t)
    old.pop("emoji")
    with store.connect() as db:
        db.execute("UPDATE tasks SET data=? WHERE id=?", (json.dumps(old), t["id"]))
    assert store.get("alice", t["id"])["emoji"] == ""


def test_emoji_ai_scoped_preview_and_validation(tmp_path):
    from fastapi.responses import JSONResponse

    s = service(tmp_path)
    t = task(s.store, "local", title="Video", description="Translate subtitles")
    calls = []
    response_text = "🎬"

    class Invocations:
        def model(self, model_id):
            return SimpleNamespace(id=model_id, endpoints={"chat_completions": {}})

        def context_for_actor(self, owner, **kwargs):
            assert owner == "local"
            assert kwargs["consumer_app_id"] == "ai2apps.todo"
            return owner

        async def invoke_foreground_json(self, model_id, endpoint, payload, **kwargs):
            calls.append(payload)
            return JSONResponse({"choices": [{"message": {"content": response_text.pop(0) if isinstance(response_text, list) else response_text}}]})

    runtime = SimpleNamespace(todo=s, model_invocations=Invocations(), model_manager=SimpleNamespace(resolve_default_model=lambda _: "standard-test"))
    app = FastAPI()
    app.include_router(create_todo_router(lambda: runtime, RequestPrincipal.legacy_local))
    client = TestClient(app)
    url = f"/todo/tasks/{t['id']}/emoji/suggest"
    draft = {"title": "Video translation", "description": "Translate subtitles to English"}
    assert client.post(url, json=draft).json() == {"emoji": "🎬"}
    assert draft["title"] in calls[0]["messages"][1]["content"]
    assert draft["description"] in calls[0]["messages"][1]["content"]
    assert s.store.get("local", t["id"])["emoji"] == ""  # Preview does not mutate.
    foreign = task(s.store, "alice")
    assert client.post(f"/todo/tasks/{foreign['id']}/emoji/suggest", json=draft).status_code == 404
    assert len(calls) == 1
    response_text = ["🎯", "🎬", "🚀"]
    assert client.post(url, json={**draft, "current_emoji": "🎯"}).json() == {"emoji": "🚀"}
    assert '🎯' in calls[1]["messages"][1]["content"]
    assert '🎬' in calls[1]["messages"][1]["content"]
    assert len(calls) == 4
    response_text = "🚀"
    assert client.post(url, json=draft).status_code == 502
    assert len(calls) == 7  # Bounded retries, never return a duplicate.
    response_text = "Here is an emoji: 🎬, alternatively 🧩"
    assert client.post(url, json=draft).json() == {"emoji": "🧩"}
    response_text = ["No symbol", "建议使用：👩🏽‍💻"]
    assert client.post(url, json=draft).json() == {"emoji": "👩🏽‍💻"}
    response_text = "No symbol"
    before = len(calls)
    assert client.post(url, json=draft).status_code == 502
    assert len(calls) == before + 3
    runtime.model_manager = None
    assert client.post(url, json=draft).status_code == 409


def test_emoji_history_bounded_persistent_and_owner_scoped(store):
    t = task(store, emoji="❤️")
    assert not store.remember_emoji("alice", t["id"], "❤")
    values = ["🎬", "🎵", "🚀", "🌱", "🔍", "📋"]
    for emoji in values:
        assert store.remember_emoji("alice", t["id"], emoji)
    reopened = TodoStore(store.root)
    assert reopened.recent_emojis("alice", t["id"]) == values[-5:]
    assert not reopened.remember_emoji("alice", t["id"], "📋")
    with pytest.raises(KeyError):
        reopened.recent_emojis("bob", t["id"])
    other = task(store)
    assert reopened.recent_emojis("alice", other["id"]) == []
    assert reopened.remember_emoji("alice", other["id"], "📋")
    assert store.get("alice", t["id"])["revision"] == t["revision"]


def test_reorder_siblings_atomic_persistent_and_scoped(store):
    parent = task(store)
    a = store.save('alice', {**body(parent), 'title': 'A', 'parent_id': parent['id']})
    b = store.save('alice', {**body(a), 'title': 'B'})
    child = store.save('alice', {**body(a), 'title': 'nested', 'parent_id': a['id']})
    request = [{'id': t['id'], 'revision': t['revision']} for t in [b, a]]
    store.reorder('alice', parent['directory_id'], parent['id'], request)
    reopened = TodoStore(store.root)
    assert reopened.get('alice', b['id'])['position'] == 0
    assert reopened.get('alice', a['id'])['position'] == 1
    assert reopened.get('alice', child['id']) == child
    assert reopened.get('alice', a['id'])['next_due'] == a['next_due']
    snapshot = reopened.snapshot('alice')
    with pytest.raises(ValueError, match='changed'):
        store.reorder('alice', parent['directory_id'], parent['id'], request)
    assert store.snapshot('alice') == snapshot
    for invalid in [request[:1], [request[0], request[0]], [{'id': child['id'], 'revision': 1}, request[0]]]:
        with pytest.raises(ValueError):
            store.reorder('alice', parent['directory_id'], parent['id'], invalid)
        assert store.snapshot('alice') == snapshot
    with pytest.raises(KeyError):
        store.reorder('bob', parent['directory_id'], parent['id'], request)


def test_reorder_root_api(tmp_path):
    s = service(tmp_path)
    a = task(s.store, 'local')
    b = s.store.save('local', {**body(a), 'title': 'B'})
    app = FastAPI()
    app.include_router(create_todo_router(lambda: SimpleNamespace(todo=s), RequestPrincipal.legacy_local))
    client = TestClient(app)
    payload = {'directory_id': a['directory_id'], 'parent_id': None, 'items': [{'id': t['id'], 'revision': t['revision']} for t in [b, a]]}
    assert client.post('/todo/tasks/reorder', json=payload).status_code == 200
    assert client.post('/todo/tasks/reorder', json=payload).status_code == 422
    assert s.store.get('local', a['id'])['position'] == 1


@pytest.mark.parametrize('priority', ['U', 'S', 'A', 'B', 'C', 'D'])
def test_priority_save_and_reorder_preserves(store, priority):
    a = task(store, priority=priority)
    b = store.save('alice', {**body(a), 'title': 'B', 'priority': 'D'})
    store.reorder('alice', a['directory_id'], None, [{'id': t['id'], 'revision': t['revision']} for t in [b, a]])
    a = TodoStore(store.root).get('alice', a['id'])
    assert a['priority'] == priority
    updated = store.save('alice', {**body(a), 'priority': 'U'}, a['id'], a['revision'])
    assert updated['priority'] == 'U'


def test_priority_default_legacy_and_validation(store):
    import json

    a = task(store)
    assert a['priority'] == 'C'
    data = body(a)
    data.pop('priority')
    with store.connect() as db:
        db.execute('UPDATE tasks SET data=? WHERE id=?', (json.dumps(data), a['id']))
    assert store.get('alice', a['id'])['priority'] == 'C'
    for invalid in ['E', 'u', '', 1]:
        with pytest.raises(ValueError):
            task(store, priority=invalid)


def test_project_status_progress_and_completion(store):
    a = task(store)
    def edit(**patch):
        nonlocal a
        a = store.save('alice', {**body(a), **patch}, a['id'], a['revision'])
    assert (a['status'], a['progress'], a['completed']) == ('not_started', 0, False)
    edit(progress=35)
    assert a['status'] == 'in_progress'
    edit(status='paused')
    assert (a['progress'], a['completed']) == (35, False)
    edit(status='completed')
    assert (a['progress'], a['completed']) == (100, True)
    edit(progress=60)
    assert (a['status'], a['completed']) == ('in_progress', False)
    edit(progress=100)
    assert (a['status'], a['completed']) == ('completed', True)
    edit(completed=False)
    assert (a['status'], a['progress']) == ('not_started', 0)
    edit(completed=True)
    assert (a['status'], a['progress']) == ('completed', 100)
    assert TodoStore(store.root).get('alice', a['id']) == a


def test_project_state_legacy_and_invalid(store):
    import json
    a = task(store, completed=True)
    data = body(a)
    data.pop('status'); data.pop('progress')
    with store.connect() as db:
        db.execute('UPDATE tasks SET data=? WHERE id=?', (json.dumps(data), a['id']))
    old = store.get('alice', a['id'])
    assert (old['status'], old['progress']) == ('completed', 100)
    for patch in [{'progress': -1}, {'progress': 101}, {'progress': 1.5}, {'status':'invalid'}]:
        with pytest.raises(ValueError):
            task(store, **patch)


def test_directory_order_persistence_conflicts_and_owner(store):
    a = store.directory('alice', 'A')
    b = store.directory('alice', 'B')
    c = store.directory('bob', 'C')
    original = [a['id'], b['id']]
    store.reorder_directories('alice', original[::-1], original)
    assert [d['id'] for d in TodoStore(store.root).snapshot('alice')['directories']] == original[::-1]
    for ids, expected in [(original, original), ([a['id'], c['id']], original[::-1]), ([a['id'], a['id']], original[::-1])]:
        with pytest.raises(ValueError):
            store.reorder_directories('alice', ids, expected)
    new = store.directory('alice', 'New')
    assert [d['id'] for d in store.snapshot('alice')['directories']] == [b['id'], a['id'], new['id']]
    assert store.snapshot('bob')['directories'] == [c]


def test_directory_order_api(tmp_path):
    s = service(tmp_path)
    app = FastAPI()
    app.include_router(create_todo_router(lambda: SimpleNamespace(todo=s), RequestPrincipal.legacy_local))
    client = TestClient(app)
    ids = [client.post('/todo/directories',json={'title': x}).json()['id'] for x in ['A','B']]
    data = {'ids':ids[::-1], 'expected':ids}
    assert client.post('/todo/directories/reorder',json=data).status_code == 200
    assert client.post('/todo/directories/reorder',json=data).status_code == 422


def test_archive_trash_restore_subtrees_and_preserve_history(store):
    a = task(store, schedule={'frequency':'daily'})
    b = store.save('alice', {**body(a), 'title':'child','parent_id':a['id']})
    c = store.save('alice', {**body(a), 'title':'independent archived child','parent_id':a['id']})
    attachment = store.add_attachment('alice', b['id'], 'notes.txt', b'keep')
    store.lifecycle('alice', c['id'], 'archive')
    store.lifecycle('alice', a['id'], 'archive')
    for item in [a,b,c]:
        assert store.get('alice',item['id'])['archived_at']
        assert store.get('alice',item['id'])['next_due'] is None
    with pytest.raises(ValueError,match='Restore'):
        store.save('alice',body(a),a['id'],a['revision'])
    store.lifecycle('alice',a['id'],'restore')
    assert not store.get('alice',b['id'])['archived_at']
    assert store.get('alice',c['id'])['archived_at']
    assert datetime.fromisoformat(store.get('alice',b['id'])['next_due']) > datetime.now(UTC)
    store.delete('alice',a['id'])
    assert all(store.get('alice',item['id'])['deleted_at'] for item in [a,b,c])
    assert store.attachment('alice',attachment['id'])[1].read_bytes() == b'keep'
    with pytest.raises(ValueError,match='parent'):
        store.lifecycle('alice',b['id'],'restore')
    with pytest.raises(KeyError):
        store.lifecycle('bob',a['id'],'restore')
    store.lifecycle('alice',a['id'],'restore')
    assert not store.get('alice',b['id'])['deleted_at']
    assert store.get('alice',c['id'])['archived_at']
    assert not store.get('alice',c['id'])['deleted_at']


def test_lifecycle_active_runs_and_execution_guard(tmp_path):
    import json
    s=service(tmp_path)
    a=task(s.store,'local')
    with s.store.connect() as db:
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?)',('run','local',a['id'],'planning',json.dumps({})))
    with pytest.raises(ValueError,match='Stop active'):
        s.store.delete('local',a['id'])
    assert not s.store.get('local',a['id'])['deleted_at']
    s.store.run_update('run','completed',output='retained')
    s.store.lifecycle('local',a['id'],'archive')
    with pytest.raises(ValueError,match='Restore'):
        s.launch('local',a['id'],principal=RequestPrincipal.legacy_local())
    with pytest.raises(ValueError,match='Restore'):
        s.store.add_attachment('local',a['id'],'no.txt',b'no')
    s.tick(datetime.now(UTC))
    assert s.store.snapshot('local')['runs'][0]['output']=='retained'


def test_completion_timestamp_tracks_transitions_not_edits(store):
    t = task(store)
    assert t['completed_at'] is None
    t = store.save('alice', {**body(t), 'completed': True}, t['id'], t['revision'])
    completed = t['completed_at']
    assert datetime.fromisoformat(completed).tzinfo is not None
    t = store.save('alice', {**body(t), 'title': 'Renamed'}, t['id'], t['revision'])
    assert t['completed_at'] == completed
    store.reorder('alice', t['directory_id'], None, [{'id': t['id'], 'revision': t['revision']}])
    t = store.get('alice', t['id'])
    assert t['completed_at'] == completed
    t = store.save('alice', {**body(t), 'completed': False}, t['id'], t['revision'])
    assert t['completed_at'] is None
    t = store.save('alice', {**body(t), 'progress': 100}, t['id'], t['revision'])
    assert t['completed_at'] >= completed


@pytest.mark.parametrize('frequency,missed,count', [('daily', True, 1), ('weekly', True, 1), ('monthly', True, 1), ('hourly', True, 0), ('hourly', False, 1)])
def test_reminder_schedule_resets_without_agent(tmp_path, frequency, missed, count):
    s = service(tmp_path)
    t = task(s.store, completed=True, schedule={'frequency': frequency, 'timezone': 'UTC', 'auto_execute': False})
    now = stamp('2026-10-03T14:00:00')
    s.started = now if missed else stamp('2026-10-03T13:00:00')
    due = '2026-06-01T09:00:00+00:00' if missed else now.isoformat()
    with s.store.connect() as db:
        db.execute('UPDATE tasks SET next_due=? WHERE id=?', (due, t['id']))
    def no_launch(*args):
        pytest.fail('Reminder must not launch an Agent')
    s.launch = no_launch
    s.tick(now)
    s.tick(now)
    updated = s.store.get('alice', t['id'])
    assert updated['completed'] == (not bool(count))
    assert updated['status'] == ('not_started' if count else 'completed')
    assert updated['progress'] == (0 if count else 100)
    assert updated['revision'] == t['revision'] + count
    assert bool(updated['completed_at']) == (not bool(count))
    assert datetime.fromisoformat(updated['next_due']) > now
    assert s.store.snapshot('alice')['runs'] == []


@pytest.mark.asyncio
async def test_todo_queue_limit_fifo_cancel_and_restart(tmp_path, monkeypatch):
    s = service(tmp_path)
    started = []
    gates = {}
    async def execute(id, owner, data):
        started.append(id)
        gates[id] = asyncio.Event()
        await gates[id].wait()
        s.store.run_update(id, 'completed', finished_at=datetime.now(UTC).isoformat())
    monkeypatch.setattr(s, 'execute', execute)
    runs = [s.launch('local', task(s.store, 'local', model='test')['id'], principal=RequestPrincipal.legacy_local())['id'] for _ in range(6)]
    await asyncio.sleep(0)
    assert started == runs[:3]
    assert len(s.jobs) == 3
    waiting = {r['id']: r for r in s.store.snapshot('local')['runs']}
    assert waiting[runs[3]]['todo_queued'] and waiting[runs[3]]['started_at'] is None
    await s.cancel('local', runs[4])
    gates[runs[0]].set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert started == runs[:4]
    assert len(s.jobs) == 3
    await s.shutdown()
    # Waiting run survives shutdown; started non-durable runs are not rerun.
    recovered = service(tmp_path)
    recovered_started = []
    async def resumed(id, owner, data):
        recovered_started.append(id)
        recovered.store.run_update(id, 'completed')
    monkeypatch.setattr(recovered, 'execute', resumed)
    await recovered.startup()
    await asyncio.sleep(0)
    assert recovered_started == [runs[5]]
    await recovered.shutdown()


@pytest.mark.asyncio
async def test_queue_waiting_cancel_requires_harness_confirmation(tmp_path, monkeypatch):
    s = service(tmp_path)
    s.max_concurrent_runs = 1
    confirmed = asyncio.Event()
    starts = []
    requests = []
    s.runtime.agent_runtime = SimpleNamespace(cancel=lambda id: requests.append(id))
    async def execute(id, owner, data):
        starts.append(id)
        if len(starts) == 1:
            s.store.run_update(id, 'waiting_input', agent_run_id='agent-wait')
            await confirmed.wait()
            s.store.run_update(id, 'cancelled')
        else:
            s.store.run_update(id, 'completed')
    monkeypatch.setattr(s, 'execute', execute)
    ids = [s.launch('local', task(s.store, 'local', model='test')['id'], principal=RequestPrincipal.legacy_local())['id'] for _ in range(2)]
    await asyncio.sleep(0)
    q = s.queue_status('local')
    assert (q['occupied'], q['waiting_user'], q['queued']) == (1, 1, 1)
    assert q['positions'] == {ids[1]: 1}
    assert s.queue_status('other')['positions'] == {}
    await s.cancel('local', ids[0])
    await asyncio.sleep(0)
    assert requests == ['agent-wait'] and starts == ids[:1]
    assert s.queue_status('local')['occupied'] == 1
    confirmed.set()
    for _ in range(4):
        await asyncio.sleep(0)
    assert starts == ids
    await s.shutdown()


@pytest.mark.asyncio
async def test_unexpected_job_failure_releases_queue_slot(tmp_path, monkeypatch):
    s = service(tmp_path)
    s.max_concurrent_runs = 1
    starts = []
    async def execute(id, owner, data):
        starts.append(id)
        if len(starts) == 1:
            raise RuntimeError('fixture failure')
        s.store.run_update(id, 'completed')
    monkeypatch.setattr(s, 'execute', execute)
    ids = [s.launch('local', task(s.store, 'local', model='test')['id'], principal=RequestPrincipal.legacy_local())['id'] for _ in range(2)]
    for _ in range(5):
        await asyncio.sleep(0)
    rows = {r['id']:r for r in s.store.snapshot('local')['runs']}
    assert starts == ids and rows[ids[0]]['status'] == 'failed'
    assert rows[ids[1]]['status'] == 'completed'
    assert s.queue_status('local')['occupied'] == 0
    await s.shutdown()


@pytest.mark.parametrize('highlight', ['lime', 'yellow', 'peach', 'pink', 'blue', 'lavender'])
def test_highlight_persists_and_clears(store, highlight):
    item = task(store)
    assert item['highlight'] == ''
    saved = store.save('alice', {**body(item), 'highlight': highlight}, item['id'], item['revision'])
    assert store.get('alice', item['id'])['highlight'] == highlight
    saved = store.save('alice', {**body(saved), 'title': 'Renamed'}, saved['id'], saved['revision'])
    assert saved['highlight'] == highlight
    cleared = store.save('alice', {**body(saved), 'highlight': ''}, saved['id'], saved['revision'])
    assert cleared['highlight'] == ''


def test_highlight_rejects_arbitrary_css():
    with pytest.raises(ValueError):
        TaskInput(title='Task', directory_id='dir', highlight='red;display:none')


def test_emoji_fallback_preserves_local_origin_and_error(tmp_path):
    from fastapi import Request
    from fastapi.responses import JSONResponse
    s=service(tmp_path)
    t=task(s.store,'local')
    runtime=SimpleNamespace(todo=s,model_manager=SimpleNamespace(resolve_default_model=lambda _: 'remote'))
    app=FastAPI()
    app.include_router(create_todo_router(lambda:runtime,RequestPrincipal.legacy_local))
    @app.post('/v1/chat/completions')
    async def completion(request:Request):
        assert str(request.base_url)=='http://127.0.0.1:56842/'
        assert request.headers['origin']=='http://127.0.0.1:56842'
        assert request.headers['sec-fetch-site']=='same-origin'
        return JSONResponse({'error':{'message':'Model unavailable'}},status_code=503)
    client=TestClient(app,base_url='http://127.0.0.1:56842')
    response=client.post(f"/todo/tasks/{t['id']}/emoji/suggest",json={'title':'Test','description':''},headers={'origin':'http://127.0.0.1:56842','sec-fetch-site':'same-origin'})
    assert response.status_code==503
    assert 'Model unavailable' in response.json()['detail']


@pytest.mark.parametrize("text,excluded,expected", [
    ("建议：**👩🏽‍💻**，代表开发", [], "👩🏽‍💻"),
    ('{"emoji": "🇨🇳"}', [], "🇨🇳"),
    ("1. 推荐 1️⃣", [], "1️⃣"),
    ("❤️ 或 🧰", ["❤"], "🧰"),
    ("🤖🌐", ["🤖"], "🌐"),
    ("no emoji 123", [], ""),
    ("🎬", ["🎬"], ""),
    (None, [], ""),
])
def test_extract_ai_emoji(text, excluded, expected):
    from ai2apps.todo.models import extract_ai_emoji
    assert extract_ai_emoji(text, excluded) == expected
