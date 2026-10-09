"""Transactional, owner-scoped recent project activity."""
import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

FIELDS = ('title', 'description', 'status', 'progress', 'priority', 'emoji', 'highlight',
          'parent_id', 'directory_id', 'position', 'schedule', 'executor', 'model',
          'working_directory', 'archived_at', 'deleted_at')


def install(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL,
      task_id TEXT NOT NULL, directory_id TEXT, happened_at TEXT NOT NULL, kind TEXT NOT NULL,
      path TEXT NOT NULL, before_data TEXT NOT NULL, after_data TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS activity_owner_time ON activity(owner,happened_at,id);
    CREATE INDEX IF NOT EXISTS activity_retention ON activity(happened_at);
    CREATE TABLE IF NOT EXISTS activity_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    INSERT OR IGNORE INTO activity_meta VALUES('started_at',strftime('%Y-%m-%dT%H:%M:%fZ','now'));
    CREATE INDEX IF NOT EXISTS activity_task ON activity(owner,task_id,id);
    ''')
    def projection(ref):
        return 'json_object(' + ','.join("'%s',json_extract(%s.data,'$.%s')" % (f, ref, f) for f in FIELDS) + ')'
    for operation, ref, before, after in [('INSERT','NEW',"'{}'",projection('NEW')),
                                         ('UPDATE','NEW',projection('OLD'),projection('NEW')),
                                         ('DELETE','OLD',projection('OLD'),"'{}'")]:
        # Snapshot the path at event time, even if the task is later renamed or removed.
        path = f'''(WITH RECURSIVE ancestors(id,parent_id,path,depth) AS (
          SELECT {ref}.id,json_extract({ref}.data,'$.parent_id'),json_extract({ref}.data,'$.title'),0
          UNION ALL SELECT t.id,json_extract(t.data,'$.parent_id'),json_extract(t.data,'$.title')||' / '||a.path,a.depth+1
          FROM tasks t JOIN ancestors a ON t.id=a.parent_id WHERE t.owner={ref}.owner AND a.depth<100
        ) SELECT COALESCE((SELECT title FROM directories WHERE id=json_extract({ref}.data,'$.directory_id') AND owner={ref}.owner),'')||' / '||path FROM ancestors ORDER BY depth DESC LIMIT 1)'''
        condition = f'WHEN {before} != {after}' if operation == 'UPDATE' else ''
        db.executescript(f'''
        CREATE TRIGGER IF NOT EXISTS todo_activity_{operation.lower()} AFTER {operation} ON tasks {condition}
        BEGIN
          INSERT INTO activity(owner,task_id,directory_id,happened_at,kind,path,before_data,after_data)
          VALUES({ref}.owner,{ref}.id,json_extract({ref}.data,'$.directory_id'),strftime('%Y-%m-%dT%H:%M:%fZ','now'),'{operation.lower()}',{path},{before},{after});
          DELETE FROM activity WHERE happened_at < strftime('%Y-%m-%dT%H:%M:%fZ','now','-30 days');
        END;
        ''')


def query(db, owner, *, directory_id=None, task_id=None, days=1, timezone='Asia/Shanghai', before_id=None, limit=100):
    zone = ZoneInfo(timezone)
    now = datetime.now(UTC)
    start = (now.astimezone(zone).replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=days-1)).astimezone(UTC)
    floor = now-timedelta(days=30)
    stamp = lambda d: d.isoformat(timespec='milliseconds').replace('+00:00','Z')
    db.execute('DELETE FROM activity WHERE happened_at < ?', (stamp(floor),))
    clauses=['owner=?','happened_at>=?'];args=[owner,stamp(max(start,floor))]
    if directory_id:
        clauses.append("(directory_id=? OR json_extract(before_data,'$.directory_id')=?)");args.extend([directory_id,directory_id])
    if task_id:
        clauses.append("task_id IN (WITH RECURSIVE subtree(id) AS (SELECT ? UNION SELECT t.id FROM tasks t JOIN subtree s ON json_extract(t.data,'$.parent_id')=s.id WHERE t.owner=?) SELECT id FROM subtree)")
        args.extend([task_id,owner])
    if before_id:
        clauses.append('id<?');args.append(before_id)
    rows=db.execute('SELECT * FROM activity WHERE '+' AND '.join(clauses)+' ORDER BY id DESC LIMIT ?',[*args,limit+1]).fetchall()
    events=[]
    for row in rows[:limit]:
        old,new=json.loads(row['before_data']),json.loads(row['after_data'])
        changes={f:{'before':old.get(f),'after':new.get(f)} for f in FIELDS if old.get(f)!=new.get(f)}
        # Long text remains in storage; bound each result delivered to Chat.
        for value in changes.values():
            for side in ('before','after'):
                if isinstance(value[side],str) and len(value[side])>1000:
                    value[side]=value[side][:1000]+'… [truncated]'
        events.append({k:row[k] for k in ('id','task_id','directory_id','happened_at','kind','path')}|{'changes':changes})
    return {'events':events,'next_cursor':events[-1]['id'] if len(rows)>limit else None,
            'timezone':timezone,'since':stamp(max(start,floor)),'retention_days':30,
            'recording_started_at':db.execute("SELECT value FROM activity_meta WHERE key='started_at'").fetchone()[0],
            'coverage':'Recorded since feature activation only; no earlier history can be inferred.'}
