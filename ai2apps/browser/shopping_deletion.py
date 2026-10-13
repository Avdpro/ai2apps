"""Permanent app-scoped removal of Shopping Pro content, retaining empty audit metadata."""
import json

from ai2apps.studio.capability_broker import StudioCapabilityError

TERMINAL = {'completed', 'failed', 'cancelled'}


def delete_shopping_data(database, *, owner, caller, scope, confirmation):
    if confirmation != 'DELETE':
        raise StudioCapabilityError('shopping_delete_confirmation_required', 'Type DELETE to permanently delete shopping data', status_code=422)
    with database.transaction(write=True) as c:
        c.execute('PRAGMA secure_delete=ON')
        tasks=c.execute('SELECT t.* FROM browser_tasks t JOIN browser_task_programs p ON p.task_id=t.id WHERE t.owner=? AND p.owner=? AND p.caller_app_id=?',(owner,owner,caller)).fetchall()
        if any(t['status'] not in TERMINAL for t in tasks):
            raise StudioCapabilityError('shopping_delete_busy','Finish or cancel Shopping Pro tasks before deleting',status_code=409)
        runs=[t['run_id'] for t in tasks if t['run_id']]
        for run in runs:
            row=c.execute('SELECT status FROM agent_runs WHERE id=?',(run,)).fetchone()
            if row and row['status'] not in TERMINAL:
                raise StudioCapabilityError('shopping_delete_busy','Shopping execution is still active',status_code=409)
        ids={t['id'] for t in tasks}|set(runs)
        columns={row['name']:{col['name'] for col in c.execute('PRAGMA table_info("'+row['name']+'")')} for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        def redact(table,where,parameters,extra=()):
            if table not in columns:return
            fields=[name for name in columns[table] if name.endswith('_json')]
            rows=c.execute('SELECT rowid AS purge_rowid,* FROM "'+table+'" WHERE '+where,parameters).fetchall()
            for row in rows:
                updates={name:('[]' if isinstance(json.loads(row[name] or '{}'),list) else '{}') for name in fields if row[name] is not None}
                for name in fields:
                    def collect(value):
                        if isinstance(value,str) and value.startswith(('tinv_','int_','step_')):ids.add(value)
                        elif isinstance(value,dict):
                            for v in value.values():collect(v)
                        elif isinstance(value,list):
                            for v in value:collect(v)
                    collect(json.loads(row[name] or '{}'))
                updates.update({name:'' for name in extra if name in columns[table]})
                if updates:c.execute('UPDATE "'+table+'" SET '+','.join('"'+name+'"=?' for name in updates)+' WHERE rowid=?',(*updates.values(),row['purge_rowid']))
            return rows
        for run in runs:
            for table in ('agent_runs','run_steps','agent_interactions','agent_status_lines','browser_action_executions','agent_step_evidence'):
                where='id=?' if table=='agent_runs' else 'run_id=?'
                if table in columns and (table=='agent_runs' or 'run_id' in columns[table]):
                    rows=redact(table,where,(run,),('prompt','text')) or []
                    ids.update(r['id'] for r in rows if 'id' in r.keys())
        # Tool payloads and message parts may retain copies of model/browser evidence.
        for table in ('tool_invocations','messages','events'):
            if table not in columns:continue
            fields=[name for name in columns[table] if name.endswith('_json')]
            for row in c.execute('SELECT rowid AS purge_rowid,* FROM "'+table+'"').fetchall():
                def references(value):
                    if isinstance(value,str):return any(ident in value for ident in ids)
                    if isinstance(value,dict):return any(references(v) for v in value.values())
                    if isinstance(value,list):return any(references(v) for v in value)
                    return False
                direct=any(any(ident in str(row[name] or '') for ident in ids) for name in ('subject_id','caller_id','trace_id') if name in row.keys())
                if direct or any(references(json.loads(row[name] or '{}')) for name in fields):
                    if 'id' in row.keys():ids.add(row['id'])
                    if table=='messages':
                        c.execute('DELETE FROM message_parts WHERE message_id=?',(row['id'],))
                    redact(table,'rowid=?',(row['purge_rowid'],))
        for task in tasks:
            c.execute("UPDATE browser_tasks SET input_json='{}',browser_context_json='{}',name='Shopping data permanently deleted',message='Shopping data permanently deleted' WHERE id=? AND owner=?",(task['id'],owner))
            c.execute("UPDATE browser_task_programs SET ir_json='{}' WHERE task_id=? AND owner=?",(task['id'],owner))
            node=task['execution_task_id'] if 'execution_task_id' in task.keys() else ''
            if node and 'task_nodes' in columns:
                c.execute("WITH RECURSIVE selected(id) AS (SELECT id FROM task_nodes WHERE owner=? AND id=? UNION ALL SELECT n.id FROM task_nodes n JOIN selected s ON n.parent_id=s.id WHERE n.owner=?) UPDATE task_nodes SET result_json='{}',name='Shopping data permanently deleted' WHERE owner=? AND id IN (SELECT id FROM selected)",(owner,node,owner,owner))
        c.execute('DELETE FROM studio_drafts WHERE actor_id=? AND installation_id=? AND app_instance_id=? AND studio_id=? AND mini_app_id=?',tuple(scope[k] for k in ('actor_id','installation_id','app_instance_id','studio_id','mini_app_id')))
    # Truncate obsolete WAL frames when no concurrent reader pins them.
    if hasattr(database,'connect'):
        import sqlite3
        connection=None
        try:
            connection=database.connect()
            connection.execute('PRAGMA busy_timeout=1000')
            connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        except sqlite3.OperationalError:
            pass  # Logical removal committed; normal database checkpoints retry later.
        finally:
            if connection is not None:connection.close()
    return {'deleted':True,'task_count':len(tasks)}
