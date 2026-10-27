from ai2apps.browser.progress_watchdog import ProgressDeadline


def test_deadline_uses_progress_not_polling():
    watch=ProgressDeadline('step',now=0)
    assert not watch.observe('step',now=299)
    assert watch.observe('step',now=300)


def test_new_result_resets_deadline():
    watch=ProgressDeadline('step',now=0)
    assert not watch.observe('next',now=299)
    assert not watch.observe('next',now=598)
    assert watch.observe('next',now=599)


def test_human_wait_is_excluded_and_resume_gets_full_deadline():
    watch=ProgressDeadline('step',now=0)
    assert not watch.observe('step',now=900,waiting=True)
    assert not watch.observe('step',now=1900,waiting=True)
    assert not watch.observe('step',now=2000)
    assert not watch.observe('step',now=2299)
    assert watch.observe('step',now=2300)


def test_completed_signature_ignores_heartbeats_pending_internal_and_other_owners():
    import sqlite3
    from contextlib import nullcontext
    from types import SimpleNamespace
    from ai2apps.browser.progress_watchdog import completed_steps
    db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
    db.executescript('CREATE TABLE browser_tasks(id,owner,root_task_id,run_id,lease_until); CREATE TABLE run_steps(run_id,action_key,kind,status,output_json);')
    db.executemany('INSERT INTO browser_tasks VALUES(?,?,?,?,?)', [('a','alice','root','run-a',0),('b','bob','root','run-b',0),('c','alice','root','run-c',0)])
    database=SimpleNamespace(transaction=lambda:nullcontext(db))
    def signature():return completed_steps(database,owner='alice',root_id='root')
    initial=signature()
    db.execute('UPDATE browser_tasks SET lease_until=900')
    db.executemany('INSERT INTO run_steps VALUES(?,?,?,?,?)',[
        ('run-a','waiting','tool','running',None),('run-a','internal','internal','completed','{}'),('run-b','read','tool','completed','{}')])
    assert signature()==initial
    db.execute("INSERT INTO run_steps VALUES('run-a','read','tool','completed','{}')")
    progressed=signature();assert progressed!=initial
    db.execute("INSERT INTO run_steps VALUES('run-c','read','tool','completed','{}')")
    assert signature()==progressed
    assert completed_steps(database,owner='bob',task_id='a')==initial
    db.close()


def test_browser_activity_only_excludes_real_queue_and_user_waits():
    import sqlite3
    from contextlib import nullcontext
    from types import SimpleNamespace as NS
    from ai2apps.browser.progress_watchdog import browser_activity
    db = sqlite3.connect(':memory:'); db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE browser_tasks(owner,root_task_id,status,run_id,browser_context_json)')
    db.executemany('INSERT INTO browser_tasks VALUES(?,?,?,?,?)', [
        ('a', 'root', 'queued', '', '{}'),
        ('a', 'root', 'running', 'agent-queue', '{}'),
        ('a', 'root', 'waiting_input', 'human', '{}'),
        ('a', 'root', 'waiting_input', 'command', '{}'),
        ('a', 'root', 'running', 'running', '{}'),
        ('a', 'root', 'waiting_input', '', '{"admission_paused":true}'),
        ('b', 'root', 'running', 'other', '{}'),
        ('a', 'other', 'running', 'other', '{}'),
    ])
    runtime = NS(database=NS(transaction=lambda: nullcontext(db)), agents=NS(
        get_run=lambda id: NS(status=NS(value='queued' if id == 'agent-queue' else 'waiting_input' if id in ('human', 'command') else 'running')),
        list_interactions=lambda id: [NS(status='pending', prompt='Wait', request={'control':'browser_user_assistance' if id == 'human' else 'browser_bidi_action'})]))
    assert browser_activity(runtime, owner='a', root_id='root') == {'blocked':4, 'running':2}
    db.close()


async def test_model_queue_activity_scopes_owner_app_session_and_admission():
    import asyncio
    from ai2apps.worker_scheduler import WorkerJobScheduler, WorkloadClass
    scheduler = WorkerJobScheduler(max_heavy_compute_slots=1)
    lease = await scheduler.acquire('worker', WorkloadClass.LOCAL_FOREGROUND,
        actor_id='a', app_id='app', session_id='other')
    queued = asyncio.create_task(scheduler.acquire('worker', WorkloadClass.LOCAL_BACKGROUND,
        actor_id='a', app_id='app', session_id='channel'))
    try:
        await asyncio.sleep(0)
        scope = dict(actor_id='a', app_id='app', session_id='channel')
        assert await scheduler.scoped_activity(**scope) == {'blocked':1, 'running':0}
        for key in scope:
            assert await scheduler.scoped_activity(**{**scope,key:'unrelated'}) == {'blocked':0, 'running':0}
        await lease.release()
        admitted = await queued
        assert await scheduler.scoped_activity(**scope) == {'blocked':0, 'running':1}
        await admitted.release()
        assert await scheduler.scoped_activity(**scope) == {'blocked':0, 'running':0}
    finally:
        queued.cancel()
        await asyncio.gather(queued, return_exceptions=True)
        await lease.release()
