from types import SimpleNamespace
import pytest
from ai2apps.browser.background_runner import BackgroundBrowserRunner


@pytest.mark.asyncio
@pytest.mark.parametrize('status,caller,owned,expected', [
    ('completed','ai2apps.intelligence',True,['root','child']),
    ('failed','ai2apps.intelligence',True,['root','child']),
    ('cancelled','ai2apps.intelligence',True,['root','child']),
    ('waiting_input','ai2apps.intelligence',True,[]),
    ('completed','ai2apps.intelligence',False,['child']),
    ('completed','ai2apps.other',True,['root','child','grandchild']),
])
async def test_only_terminal_collection_owned_tabs_close(status, caller, owned, expected):
    closed=[]
    class Connection:
        detached=False
        async def command(self, method, params):
            if method=='browsingContext.getTree':
                return {'contexts':[{'context':c,'userContext':p} for c,p in
                    [('root','profile'),('child','profile'),('grandchild','profile'),('foreign','other'),('user','profile')] if c not in closed]}
            closed.append(params['context'])
        async def close(self): self.detached=True
    connection=Connection()
    page=SimpleNamespace(connection=connection,created_contexts={'child':'root',**({'grandchild':'child'} if caller=='ai2apps.other' else {})})
    run=SimpleNamespace(id='run',status=SimpleNamespace(value=status),input={'parameters':{
        'caller_app_id':caller,'browser_context':{'bidi_context':'root','user_context':'profile',
        'created_by_run':'run' if owned else None}}})
    records=[]
    runner=SimpleNamespace(save_page_state=lambda run,page,**kw: records.append(kw))
    await BackgroundBrowserRunner.release_page(runner,run,page)
    assert closed==expected
    assert connection.detached == (status != 'waiting_input')
    if records: assert records[-1]['cleanup']['state']=='verified'


@pytest.mark.asyncio
@pytest.mark.parametrize('reason,close_works,state', [
    ('User needs to review the generated report',False,'retained'),
    ('',False,'pending'),
    ('',True,'verified'),
])
async def test_cleanup_verifies_actual_browser_state(reason,close_works,state):
    live=True
    queries=0
    closes=[]
    records=[]
    class Connection:
        async def command(self,method,params):
            nonlocal live,queries
            if method=='browsingContext.getTree':
                queries+=1
                return {'contexts':[{'context':'root','userContext':'p'}] if live else []}
            closes.append(params['context'])
            if close_works: live=False
        async def close(self): pass
    run=SimpleNamespace(id='r',status=SimpleNamespace(value='completed'),input={'parameters':{
        'browser_context':{'bidi_context':'root','user_context':'p','created_by_run':'r','retain_pages_reason':reason}}})
    page=SimpleNamespace(connection=Connection(),created_contexts={})
    runner=SimpleNamespace(save_page_state=lambda run,page,**kw:records.append(kw['cleanup']))
    if state=='pending':
        with pytest.raises(RuntimeError,match='cleanup is incomplete'):
            await BackgroundBrowserRunner.release_page(runner,run,page)
    else:
        await BackgroundBrowserRunner.release_page(runner,run,page)
    assert queries==2
    assert records[-1]['state']==state
    assert closes==([] if reason else ['root'])


@pytest.mark.asyncio
async def test_restart_cleanup_reattaches_without_creating_pages():
    from contextlib import contextmanager
    class DB:
        @contextmanager
        def transaction(self): yield self
        def execute(self,sql): return self
        def fetchall(self): return [{'id':'r'}]
    class Connection:
        async def connect(self): return self
        async def close(self): pass
    run=SimpleNamespace(id='r',input={'parameters':{'browser_context':{
        'bidi_context':'old-root','owned_contexts':{'child':'old-root'}}}})
    seen=[]
    async def release(run,page): seen.append((page.context_id,page.created_contexts))
    runner=SimpleNamespace(runtime=SimpleNamespace(database=DB(),agents=SimpleNamespace(get_run=lambda _:run)),
        pages={},_active={},connection_factory=Connection,release_page=release)
    await BackgroundBrowserRunner.recover_cleanup(runner)
    assert seen==[('old-root',{'child':'old-root'})]


@pytest.mark.asyncio
@pytest.mark.parametrize('scope_status,run_status,expected', [('running','completed','retained'),('finishing','completed','verified'),('running','failed','verified'),('finishing','cancelled','verified')])
async def test_reusable_page_lives_only_until_source_finishes(tmp_path, scope_status, run_status, expected):
    from ai2apps.storage import PlatformDatabase
    from ai2apps.browser.task_tree import TaskTreeRepository
    db=PlatformDatabase(tmp_path/'reuse.sqlite');db.initialize()
    tree=TaskTreeRepository(db);tree.create('alice','source','Source')
    with db.transaction(write=True) as c:c.execute('UPDATE task_nodes SET status=? WHERE id=?',(scope_status,'source'))
    closed=[];records=[]
    class Connection:
        async def command(self, method, params):
            if method=='browsingContext.getTree':return {'contexts':[] if closed else [{'context':'tab','userContext':'p'}]}
            closed.append(params['context'])
        async def close(self):pass
    runner=SimpleNamespace(runtime=SimpleNamespace(database=db),save_page_state=lambda run,page,**kw:records.append(kw['cleanup']))
    run=SimpleNamespace(id='r',status=SimpleNamespace(value=run_status),input={'parameters':{'owner_user_id':'alice','browser_context':{'bidi_context':'tab','user_context':'p','created_by_run':'r','reuse_scope':'source'}}})
    await BackgroundBrowserRunner.release_page(runner,run,SimpleNamespace(connection=Connection(),created_contexts={}))
    assert records[-1]['state']==expected
    assert bool(closed)==(expected=='verified')
