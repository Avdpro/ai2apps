import json
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from ai2apps.browser.shopping_deletion import delete_shopping_data
from ai2apps.studio.capability_broker import StudioCapabilityError

RUN='run_'+'a'*32
TASK='btask_'+'b'*32
SCOPE=dict(actor_id='owner',installation_id='local',app_instance_id='host',studio_id='ai2apps.ai-browser',mini_app_id='ai2apps.shopping-pro')

@pytest.fixture
def data():
    c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
    c.executescript('''
CREATE TABLE browser_tasks(id TEXT PRIMARY KEY,owner TEXT,status TEXT,run_id TEXT,execution_task_id TEXT,input_json TEXT,browser_context_json TEXT,message TEXT,name TEXT);
CREATE TABLE browser_task_programs(task_id TEXT PRIMARY KEY,owner TEXT,caller_app_id TEXT,ir_json TEXT);
CREATE TABLE agent_runs(id TEXT PRIMARY KEY,status TEXT,input_json TEXT,output_json TEXT,error_json TEXT);
CREATE TABLE run_steps(id TEXT PRIMARY KEY,run_id TEXT,input_json TEXT,output_json TEXT,error_json TEXT);
CREATE TABLE events(sequence INTEGER PRIMARY KEY,subject_id TEXT,payload_json TEXT);
CREATE TABLE messages(id TEXT PRIMARY KEY,metadata_json TEXT);
CREATE TABLE message_parts(message_id TEXT,content_json TEXT);
CREATE TABLE task_nodes(id TEXT PRIMARY KEY,owner TEXT,parent_id TEXT,result_json TEXT,name TEXT);
CREATE TABLE studio_drafts(actor_id TEXT,installation_id TEXT,app_instance_id TEXT,studio_id TEXT,mini_app_id TEXT,draft_json TEXT);
''')
    for owner,task,run,caller in [('owner',TASK,RUN,'shopping-caller'),('other','btask_'+'c'*32,'run_'+'d'*32,'shopping-caller'),('owner','btask_'+'e'*32,'run_'+'f'*32,'other-app')]:
        c.execute('INSERT INTO browser_tasks VALUES(?,?,?,?,?,?,?,?,?)',(task,owner,'completed',run,'webtask:'+task,'{"catalog":"SECRET"}','{}','','Shopping task'))
        c.execute('INSERT INTO browser_task_programs VALUES(?,?,?,?)',(task,owner,caller,'{"catalog":"SECRET"}'))
        c.execute('INSERT INTO agent_runs VALUES(?,?,?,?,?)',(run,'completed','{"catalog":"SECRET"}','{"history":"SECRET"}',None))
        c.execute('INSERT INTO run_steps VALUES(?,?,?,?,?)',('step_'+run,run,'{"prompt":"SECRET"}','{"content":"SECRET"}',None))
        c.execute('INSERT INTO events(subject_id,payload_json) VALUES(?,?)',(task,json.dumps({'run_id':run,'shopping':'SECRET'})))
    c.execute('INSERT INTO messages VALUES(?,?)',('msg-one',json.dumps({'agent_run_id':RUN})))
    c.execute('INSERT INTO message_parts VALUES(?,?)',('msg-one','{"text":"SECRET"}'))
    c.execute('INSERT INTO task_nodes VALUES(?,?,?,?,?)',('webtask:'+TASK,'owner',None,'{"orders":"SECRET"}','Shopping task'))
    c.execute('INSERT INTO studio_drafts VALUES(?,?,?,?,?,?)',(*SCOPE.values(),'{"deletedHistory":{"catalog":"SECRET"}}'))
    c.commit()
    @contextmanager
    def transaction(**kwargs):
        try:yield c;c.commit()
        except Exception:c.rollback();raise
    return SimpleNamespace(transaction=transaction),c


def purge(db,confirmation='DELETE'):
    return delete_shopping_data(db,owner='owner',caller='shopping-caller',scope=SCOPE,confirmation=confirmation)


def test_permanent_delete_scrubs_payloads_and_backup_but_preserves_other_owner_and_app(data):
    db,c=data
    result=purge(db)
    assert result['deleted'] and result['task_count']==1
    assert c.execute('SELECT count(*) FROM studio_drafts').fetchone()[0]==0
    assert c.execute('SELECT count(*) FROM message_parts').fetchone()[0]==0
    for table in ('agent_runs','run_steps','browser_task_programs','browser_tasks','events','task_nodes'):
        rows=[dict(row) for row in c.execute('SELECT * FROM '+table)]
        target=[row for row in rows if any(RUN in str(v) or TASK in str(v) for v in row.values())]
        assert all('SECRET' not in json.dumps(row) for row in target)
    assert 'SECRET' in c.execute('SELECT input_json FROM agent_runs WHERE id=?',('run_'+'d'*32,)).fetchone()[0]
    assert 'SECRET' in c.execute('SELECT input_json FROM agent_runs WHERE id=?',('run_'+'f'*32,)).fetchone()[0]
    assert purge(db)['deleted']


def test_delete_requires_exact_confirmation_and_does_not_mutate(data):
    db,c=data
    with pytest.raises(StudioCapabilityError):purge(db,'delete')
    assert c.execute('SELECT count(*) FROM studio_drafts').fetchone()[0]==1


@pytest.mark.parametrize('active_table',['browser_tasks','agent_runs'])
def test_delete_rejects_active_task_atomically(data,active_table):
    db,c=data;key=TASK if active_table=='browser_tasks' else RUN
    c.execute('UPDATE '+active_table+' SET status=? WHERE id=?',('running',key));c.commit()
    with pytest.raises(StudioCapabilityError):purge(db)
    assert c.execute('SELECT count(*) FROM studio_drafts').fetchone()[0]==1
    assert 'SECRET' in c.execute('SELECT input_json FROM agent_runs WHERE id=?',(RUN,)).fetchone()[0]
