import asyncio
import concurrent.futures
import json
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

import pytest

from ai2apps.browser.action_journal import BrowserActionJournal
from ai2apps.browser.background_page import BackgroundPage
from ai2apps.browser.background_executor import BackgroundExecutor, scope_allows


@pytest.mark.parametrize('description',[
    'Choose workspace category. Do not submit.', 'Set priority; never press Enter.',
    '选择分类，不要提交；不要按回车。',
])
def test_preparation_negated_submission_is_not_an_enter_instruction(description):
    from ai2apps.browser.background_executor import requests_submission
    assert not requests_submission({'description':description})


@pytest.mark.parametrize('description',[
    'Press Enter to search', 'Submit the search', '搜索后按回车',
    'Do not submit the form; press Enter to search',
])
def test_preparation_actual_submission_remains_detected(description):
    from ai2apps.browser.background_executor import requests_submission
    assert requests_submission({'description':description})


@pytest.mark.asyncio
@pytest.mark.parametrize('context', ['provider-alpha-tab', 'provider-beta-tab'])
async def test_native_input_activation_waits_for_owned_page_visibility(context, monkeypatch):
    commands=[]
    class Connection:
        async def command(self, method, parameters):
            commands.append((method, parameters))
    page=BackgroundPage(Connection(),context)
    visibility=iter([False,False,True])
    async def read(source):
        assert 'document.visibilityState' in source
        return next(visibility)
    async def no_sleep(_):pass
    page.call_json=read
    monkeypatch.setattr(asyncio,'sleep',no_sleep)
    await page.activate_for_input()
    assert commands==[('browsingContext.unhideBrowserWindow',{'context':context}),
                      ('browsingContext.activate',{'context':context})]


@pytest.mark.asyncio
async def test_hidden_page_never_receives_native_input(monkeypatch):
    commands=[]
    class Connection:
        async def command(self, method, parameters):commands.append(method)
    page=BackgroundPage(Connection(),'owned-tab')
    async def hidden(_):return False
    async def no_sleep(_):pass
    page.call_json=hidden
    monkeypatch.setattr(asyncio,'sleep',no_sleep)
    with pytest.raises(RuntimeError,match='not visible'):
        await page.pointer_to({'rect':{'x':0,'y':0,'width':20,'height':20}})
    assert commands==['browsingContext.unhideBrowserWindow','browsingContext.activate']*2


@pytest.mark.asyncio
async def test_visible_page_activation_does_not_unhide_other_windows():
    commands=[]
    class Connection:
        async def command(self, method, parameters):commands.append((method,parameters))
    page=BackgroundPage(Connection(),'owned-visible-tab')
    async def visible(_):return True
    page.call_json=visible
    await page.activate_for_input()
    assert commands==[]


@pytest.mark.asyncio
async def test_failed_window_restore_never_dispatches_input():
    commands=[]
    class Connection:
        async def command(self, method, parameters):
            commands.append(method)
            raise RuntimeError('Native window unavailable')
    page=BackgroundPage(Connection(),'owned-hidden-tab')
    async def hidden(_):return False
    page.call_json=hidden
    with pytest.raises(RuntimeError,match='Native window unavailable'):
        await page.pointer_to({'rect':{'x':0,'y':0,'width':20,'height':20}})
    assert commands==['browsingContext.unhideBrowserWindow']*2


class JournalDatabase:
    def __init__(self, path):
        self.path = path
        with self.transaction(write=True) as c:
            c.executescript('''CREATE TABLE agent_runs(id TEXT PRIMARY KEY,input_json TEXT,status TEXT);
CREATE TABLE agent_interactions(id TEXT PRIMARY KEY,run_id TEXT,status TEXT,request_json TEXT);
CREATE TABLE browser_action_executions(interaction_id TEXT PRIMARY KEY,run_id TEXT,owner TEXT,context_id TEXT NOT NULL,request_hash TEXT,state TEXT,response_json TEXT,started_at REAL,finished_at REAL);''')
            c.execute('INSERT INTO agent_runs VALUES(?,?,?)', ('run', json.dumps({'parameters': {'owner_user_id': 'alice'}}), 'waiting_input'))
            c.execute('INSERT INTO agent_interactions VALUES(?,?,?,?)', ('interaction','run','pending','{"step": "click"}'))

    @contextmanager
    def transaction(self, write=False):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback(); raise
        finally:
            c.close()


def test_journal_claim_is_atomic_and_completed_response_is_recoverable(tmp_path):
    journal = BrowserActionJournal(JournalDatabase(tmp_path/'journal.sqlite'))
    claim = dict(run_id='run', interaction_id='interaction', owner='alice', context_id='tab', request={'step':'click'})
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: journal.claim(**claim), range(8)))
    assert sum(admitted for _, admitted in results) == 1
    response = {'outcome':'success','evidence':{'result':{'items':[{'title':'A','url':'https://example.com/a'}]}}}
    journal.complete('interaction', response)
    journal.complete('interaction', response)
    recovered, admitted = journal.claim(**claim)
    assert not admitted and json.loads(recovered['response_json']) == response
    with pytest.raises(ValueError, match='identity changed'):
        journal.claim(**{**claim, 'owner':'bob'})


def test_restart_never_replays_started_mutation(tmp_path):
    database = JournalDatabase(tmp_path/'journal.sqlite')
    claim = dict(run_id='run', interaction_id='interaction', owner='alice', context_id='tab', request={'step':'click'})
    BrowserActionJournal(database).claim(**claim)
    journal = BrowserActionJournal(database)
    assert journal.recover() == [{'run_id':'run','interaction_id':'interaction'}]
    record, admitted = journal.claim(**claim)
    assert record['state'] == 'uncertain' and not admitted
    with pytest.raises(ValueError, match='explicit resolution'):
        journal.complete('interaction', {'outcome':'success','evidence':{}})


@pytest.mark.parametrize('url', ['http://localhost/', 'http://10.0.0.1/', 'http://[::1]/', 'http://[fe80::1]/', 'file:///tmp/a', 'https://user:pass@example.com/'])
def test_public_reader_rejects_private_locations(url):
    with pytest.raises(ValueError):
        BackgroundPage.public_url(url)


@pytest.mark.asyncio
async def test_navigation_uses_dom_readiness_without_waiting_for_all_resources(monkeypatch):
    class Connection:
        async def command(self, method, params, **kwargs):
            assert method == 'browsingContext.navigate'
            assert params['context'] == 'owned'
            if params['wait'] == 'complete':
                raise asyncio.TimeoutError('analytics resource still loading')
            assert params['wait'] == 'none'
            return {'url': params['url']}
    page = BackgroundPage(Connection(), 'owned')
    checks = []
    async def stable(**kwargs):
        checks.append(kwargs)
        return {'stable': True}
    async def no_sleep(_): pass
    page.wait_stable = stable
    monkeypatch.setattr(asyncio, 'sleep', no_sleep)
    result = await page.navigate('https://www.xiaohongshu.com/search_result', 3000)
    assert result['stable'] is True
    assert checks == [{'require_content': True}]


@pytest.mark.asyncio
async def test_200k_input_is_bounded_chunks_and_native_keys(monkeypatch):
    class Connection:
        def __init__(self): self.commands=[]
        async def command(self, method, params, **kwargs):
            self.commands.append((method, params))
            return {}
    connection=Connection();page=BackgroundPage(connection, 'tab')
    from unittest.mock import AsyncMock
    page.activate_for_input=AsyncMock()
    calls=[]
    async def helper(name,*args): calls.append((name,args));return True
    async def mode():return 'natural'
    async def pause(_):pass
    async def no_sleep(_):pass
    page.helper=helper;page.mode=mode;page.pause=pause
    monkeypatch.setattr(asyncio,'sleep',no_sleep)
    await page.type_text('文'*200000,replace=True,submit=True)
    chunks=[args[1] for name,args in calls if name=='insertTextChunk:0' and args[1]]
    assert max(map(len,chunks))<=8192
    assert len(chunks)<30
    keydowns=[action['value'] for _,params in connection.commands for source in params['actions'] for action in source['actions'] if action['type']=='keyDown']
    assert keydowns.count('文')<=16
    assert keydowns[-1]=='\uE007'
    assert calls[-1][0]=='typeText:2'  # release the focused editor token


@pytest.mark.asyncio
async def test_upload_restores_interception_after_failed_click():
    page=BackgroundPage(None,'tab');calls=[]
    async def mode():return 'natural'
    async def target(_):return {'ref':'upload','rect':{}}
    async def helper(name,*args):calls.append(name)
    async def click(_):raise RuntimeError('transport lost')
    page.mode=mode;page.find_target=target;page.helper=helper;page.pointer_to=click
    with pytest.raises(RuntimeError,match='transport lost'):
        await page.upload('upload',['/owned/file'])
    assert calls==['chooseAttachmentFiles:0','chooseAttachmentFiles:1']


@pytest.mark.asyncio
async def test_ambiguous_native_failure_does_not_enter_adaptive_fallback():
    executor=BackgroundExecutor(None)
    class Page:
        context_id='tab'
        async def validate_context(self):pass
    async def compiled(*args):raise RuntimeError('command response lost')
    async def forbidden(*args):raise AssertionError('must not replay')
    executor.compiled=compiled;executor.adaptive=forbidden
    with pytest.raises(RuntimeError,match='response lost'):
        await executor.execute(Page(),{'step':{'operation':'click','mode':'adaptive'}},None)


def test_scope_requires_exact_authorized_destination():
    assert scope_allows('https://example.com/a',['https://example.com/**'])
    assert not scope_allows('https://example.com.evil/a',['https://example.com/**'])
    assert not scope_allows('https://user@example.com/a',['https://example.com/**'])


def test_assistance_is_durable_and_continuation_requests_a_fresh_action():
    from types import SimpleNamespace
    from ai2apps.agent_builder.compiler import compile_source
    from ai2apps.agents.browser_builder import browser_builder_executor
    from ai2apps.agents.models import InteractionStatus, InteractionAction, CompleteAction
    ir = compile_source({'site_scope':['https://example.com/**'], 'steps':[{
        'name':'read','desc':'Extract articles','operation':'extract_list',
        'on':{'success':'done','failed':'failed'}}]}).ir
    run = SimpleNamespace(input={'parameters':{'ir':ir}})
    interactions=[]
    def context():
        return SimpleNamespace(run=run, definition=SimpleNamespace(max_steps=100), interactions=interactions,
            interaction=lambda key: next((item for item in interactions if item.request_key==key),None))
    first=browser_builder_executor(context())
    def submitted(action, id, response):
        return SimpleNamespace(id=id, request=action.request, request_key=action.request_key,
            status=InteractionStatus.SUBMITTED, response=response)
    interactions.append(submitted(first,'action-1',{'outcome':'needs_user','evidence':{'reason':'captcha'}}))
    assistance=browser_builder_executor(context())
    assert assistance.request['control']=='browser_user_assistance'
    assert browser_builder_executor(context()).request_key==assistance.request_key
    interactions.append(submitted(assistance,'human-1',{'continued':True}))
    next_action=browser_builder_executor(context())
    assert isinstance(next_action, InteractionAction)
    assert next_action.request['control']=='browser_bidi_action'
    assert next_action.request_key != first.request_key
    interactions.append(submitted(next_action,'action-2',{'outcome':'success','evidence':{'result':{'items':[{'title':'A','url':'https://example.com/a'}]}}}))
    completed=browser_builder_executor(context())
    assert isinstance(completed,CompleteAction)
    assert len(completed.output['result']['items'])==1


def test_publish_completion_requires_send_but_navigation_step_can_finish():
    from ai2apps.browser.background_planner import validate_completion
    inspected = [{'outcome':'success','source_step':{'operation':'inspect'}}]
    with pytest.raises(ValueError,match='publish/send control'):
        validate_completion({'operation':'click','target':{'intent':'发布'}}, inspected)
    validate_completion({'operation':'open','description':'Open editor before publishing'}, inspected)
    validate_completion({'operation':'click','target':{'intent':'发布'}}, [
        {'outcome':'success','source_step':{'operation':'click','target':{'intent':'发布'}}}])


@pytest.mark.asyncio
async def test_completed_journal_response_survives_missing_browser(tmp_path):
    from types import SimpleNamespace
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    database = JournalDatabase(tmp_path/'journal.sqlite')
    runner = BackgroundBrowserRunner(SimpleNamespace(database=database,events=None))
    request={'step':'click'}
    runner.journal.claim(run_id='run',interaction_id='interaction',owner='alice',context_id='tab',request=request)
    response={'outcome':'success','evidence':{'result':{'items':[{'title':'Saved','url':'https://example.com/a'}]}}}
    runner.journal.complete('interaction',response)
    delivered=[]
    runner.runtime.agents=SimpleNamespace(
        get_run=lambda _:SimpleNamespace(id='run',input={'parameters':{'owner_user_id':'alice','browser_context':{'bidi_context':'tab'}}}),
        list_interactions=lambda _:[SimpleNamespace(id='interaction',request=request)],
        respond_interaction=lambda *args,**kwargs:delivered.append(kwargs['response']))
    runner.runtime.agent_runtime=SimpleNamespace(wake=lambda:None)
    async def unavailable(_):raise AssertionError('completed response must not require a live browser')
    runner.page_for=unavailable
    await runner.execute_interaction({'run_id':'run','id':'interaction'})
    assert delivered==[response]


@pytest.mark.asyncio
async def test_temporary_reader_checks_read_url_not_restored_blank_caller():
    class Page:
        async def snapshot(self):return {'url':'about:blank'}
        async def read_page(self,args):return {'outcome':'success','url':'https://example.com/article','text':'Body'}
    executor=BackgroundExecutor(None)
    result=await executor.compiled(Page(),{'operation':'read_page','arguments':{'url':'https://example.com/article'}},['https://example.com/**'])
    assert result['outcome']=='success'
    class Redirected(Page):
        async def read_page(self,args):return {'outcome':'success','url':'https://outside.example/article','text':'Body'}
    assert (await executor.compiled(Redirected(),{'operation':'read_page','arguments':{'url':'https://example.com/article'}},['https://example.com/**']))['outcome']=='restricted'


@pytest.mark.asyncio
async def test_cold_transport_retries_only_before_actions(monkeypatch):
    from ai2apps.browser import background_bidi as transport
    calls=[]
    class Upstream:
        async def __aiter__(self):
            await asyncio.Event().wait()
            yield ''
    @asynccontextmanager
    async def attachment(*args):
        calls.append('attach')
        if len(calls)==1:
            try:raise ConnectionRefusedError('listener starting')
            except OSError as error:raise RuntimeError('session could not be created') from error
        yield {},Upstream()
    monkeypatch.setattr(transport.ShellBiDiEndpoint,'load',lambda _:type('Endpoint',(),{'pid':123})())
    monkeypatch.setattr(transport,'shell_bidi_descriptor_path',lambda:None)
    monkeypatch.setattr(transport,'attach_shell_bidi_session',attachment)
    connection=await transport.BackgroundBiDi().connect()
    assert calls==['attach','attach']
    await connection.close()


@pytest.mark.asyncio
async def test_site_list_rule_initializes_blank_tab_without_ai():
    class Page:
        url = 'about:blank'
        visits = []
        async def snapshot(self):return {'url':self.url}
        async def navigate(self,url,delay):self.visits.append((url,delay));self.url=url
        async def extract_list(self,step):return {'items':[{'title':'Article','url':self.url+'article'}]}
    page=Page(); executor=BackgroundExecutor(None)
    step={'operation':'extract_list','arguments':{'site_extraction':{
        'schema':'ai2apps.site-extraction/v1','kind':'list','origin':'https://example.com','path':'/archives/'}}}
    result=await executor.compiled(page,step,['https://example.com/**'])
    assert result['outcome']=='success'
    assert page.visits==[('https://example.com/archives/',3000)]
    await executor.compiled(page,step,['https://example.com/**'])
    assert len(page.visits)==1
    page.url='about:blank'
    assert (await executor.compiled(page,step,['https://example.com/**'],preview=True))['outcome']=='success'
    assert len(page.visits)==1
    assert (await executor.compiled(page,step,['https://other.example/**']))['outcome']=='restricted'
    assert len(page.visits)==1
    async def redirect(url,delay):page.url='https://outside.example/'
    page.navigate=redirect
    assert (await executor.compiled(page,step,['https://example.com/**']))['outcome']=='restricted'


@pytest.mark.asyncio
async def test_site_article_rule_initializes_reader_url():
    class Page:
        async def snapshot(self):return {'url':'about:blank'}
        async def read_page(self,args):
            assert args['url']=='https://example.com/article'
            return {'outcome':'success','url':args['url'],'text':'Body'}
    result=await BackgroundExecutor(None).compiled(Page(),{'operation':'read_page','arguments':{
        'site_extraction':{'schema':'ai2apps.site-extraction/v1','kind':'article','origin':'https://example.com','path':'/article'}}},['https://example.com/**'])
    assert result['outcome']=='success'

@pytest.mark.asyncio
async def test_source_page_handoff_reuses_only_owned_profile_context(tmp_path, monkeypatch):
    from types import SimpleNamespace as NS
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    from ai2apps.browser.profiles import BrowserProfileRepository
    from ai2apps.helper_control import HelperControlClient
    from ai2apps.browser.shell_window import shell_browser_window_broker
    db=JournalDatabase(tmp_path/'handoff.sqlite')
    shared={'bidi_context':'existing','user_context':'profile','created_by_run':'old', 'reuse_scope':'source','cleanup':{'state':'retained'}}
    incoming={'profile_key':'default','reuse_scope':'source'}
    with db.transaction(write=True) as c:
        c.execute('CREATE TABLE browser_tasks(id TEXT,owner TEXT,profile_key TEXT,status TEXT,run_id TEXT,browser_context_json TEXT,updated_at REAL)')
        c.execute('INSERT INTO browser_tasks VALUES(?,?,?,?,?,?,?)',('old-task','alice','default','completed','old',json.dumps(shared),0))
        c.execute('INSERT INTO agent_runs VALUES(?,?,?)',('old',json.dumps({'parameters':{'browser_context':shared}}),'completed'))
        c.execute('UPDATE agent_runs SET input_json=? WHERE id=?',(json.dumps({'parameters':{'browser_context':incoming}}),'run'))
    monkeypatch.setattr(BrowserProfileRepository,'require',lambda *a:NS(name='Default',is_default=True))
    monkeypatch.setattr(HelperControlClient,'from_environment',lambda:None)
    monkeypatch.setattr(shell_browser_window_broker,'enqueue',lambda **kw:'bind')
    monkeypatch.setattr(shell_browser_window_broker,'wait',lambda *a:{'user_context':'profile'})
    commands=[]
    class Connection:
        async def connect(self):return self
        async def command(self,method,params,**kwargs):
            commands.append(method)
            assert method!='browsingContext.create'
            return {'contexts':[{'context':'existing','userContext':'profile'}]}
        async def close(self):pass
    async def valid(_):pass
    monkeypatch.setattr(BackgroundPage,'validate_context',valid)
    runtime=NS(database=db,events=NS())
    runner=BackgroundBrowserRunner(runtime,connection_factory=Connection)
    run=NS(id='run',input={'parameters':{'owner_user_id':'alice','browser_context':incoming}})
    page=await runner.page_for(run)
    assert page.context_id=='existing'
    with db.transaction() as c:
        old=json.loads(c.execute('SELECT browser_context_json FROM browser_tasks').fetchone()[0])
        new=json.loads(c.execute("SELECT input_json FROM agent_runs WHERE id='run'").fetchone()[0])['parameters']['browser_context']
    assert old['created_by_run']=='' and old['cleanup']['transferred_to']=='run'
    assert new['created_by_run']=='run' and new['cleanup']['state']=='pending'


@pytest.mark.asyncio
@pytest.mark.parametrize('order',['latest','general','likes'])
async def test_xhs_sort_applies_native_control_and_verifies(monkeypatch,order):
    page=BackgroundPage(object(),'context')
    states=iter([{'option':{'rect':{'x':1}},'verified':False},{'verified':True}])
    clicks=[]
    async def read(*args):return next(states)
    async def click(target,**kwargs):clicks.append(target)
    async def stable(**kwargs):return {}
    async def pause(*args):pass
    monkeypatch.setattr(page,'call_json',read)
    monkeypatch.setattr(page,'pointer_to',click)
    monkeypatch.setattr(page,'wait_stable',stable)
    monkeypatch.setattr('ai2apps.browser.background_page.asyncio.sleep',pause)
    await page.ensure_xhs_sort(order)
    assert len(clicks)==1


@pytest.mark.asyncio
async def test_xhs_sort_never_accepts_unverified_results(monkeypatch):
    page=BackgroundPage(object(),'context')
    async def read(*args):return {'verified':False}
    async def pause(*args):pass
    monkeypatch.setattr(page,'call_json',read)
    monkeypatch.setattr('ai2apps.browser.background_page.asyncio.sleep',pause)
    with pytest.raises(RuntimeError,match='xiaohongshu_sort_not_verified'):
        await page.ensure_xhs_sort('general')


@pytest.mark.asyncio
async def test_x_search_sort_checks_selected_tab(monkeypatch):
    page=BackgroundPage(object(),'context')
    calls=[]
    async def read(script,args):
        calls.append(args)
        return {'verified':True}
    async def stable(**kwargs):pass
    monkeypatch.setattr(page,'call_json',read)
    monkeypatch.setattr(page,'wait_stable',stable)
    await page.ensure_x_search_sort('https://x.com/search?q=F1&f=live')
    await page.ensure_x_search_sort('https://x.com/search?q=F1')
    await page.ensure_x_search_sort('https://x.com/search?q=F1&f=live','top')
    assert calls==[['latest','F1'],['top','F1'],['top','F1']]


@pytest.mark.asyncio
async def test_x_search_sort_rejects_wrong_query(monkeypatch):
    page=BackgroundPage(object(),'context')
    async def read(*args):return {'invalid':True}
    monkeypatch.setattr(page,'call_json',read)
    with pytest.raises(RuntimeError,match='x_search_wrong_page'):
        await page.ensure_x_search_sort('https://x.com/search?q=F1&f=live')


@pytest.mark.asyncio
@pytest.mark.parametrize('existing',[True,False])
async def test_cold_profile_uses_existing_host_without_reference(tmp_path,monkeypatch,existing):
    from types import SimpleNamespace as NS
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    from ai2apps.browser.profiles import BrowserProfileRepository
    from ai2apps.helper_control import HelperControlClient
    from ai2apps.browser.shell_window import shell_browser_window_broker
    db=JournalDatabase(tmp_path/'cold.sqlite')
    incoming={'profile_key':'default'}
    with db.transaction(write=True) as c:
        c.execute('UPDATE agent_runs SET input_json=? WHERE id=?',(json.dumps({'parameters':{'browser_context':incoming}}),'run'))
    monkeypatch.setattr(BrowserProfileRepository,'require',lambda *a:NS(name='Default',is_default=True))
    monkeypatch.setattr(HelperControlClient,'from_environment',lambda:None)
    monkeypatch.setattr(shell_browser_window_broker,'enqueue',lambda **kw:'bind')
    monkeypatch.setattr(shell_browser_window_broker,'wait',lambda *a:{'user_context':'profile'})
    created=[]
    class Connection:
        async def connect(self):return self
        async def command(self,method,params,**kwargs):
            if method=='browsingContext.create':created.append(params);return {'context':'new'}
            if params.get('root'):return {'contexts':[{'context':'new','userContext':'profile'}]}
            return {'contexts':[{'context':'old','userContext':'profile'}] if existing else []}
        async def close(self):pass
    async def valid(_):pass
    monkeypatch.setattr(BackgroundPage,'validate_context',valid)
    runner=BackgroundBrowserRunner(NS(database=db,events=NS()),connection_factory=Connection)
    runner.tasks=NS(list=lambda owner:[])
    page=await runner.page_for(NS(id='run',input={'parameters':{'owner_user_id':'alice','browser_context':incoming}}))
    assert page.context_id=='new'
    assert created==[{'type':'tab' if existing else 'window','userContext':'profile','background':True,**({'referenceContext':'old'} if existing else {})}]


@pytest.mark.asyncio
@pytest.mark.parametrize('observed,calls',[('https://example.com/a',1),('about:blank',2)])
async def test_navigation_timeout_verifies_original_tab_before_retry(monkeypatch,observed,calls):
    class Connection:
        def __init__(self):self.navigation=0;self.reconnects=0
        async def reconnect(self):self.reconnects+=1
        async def command(self,method,params,**kwargs):
            if method=='browsingContext.getTree':return {'contexts':[{'context':'owned','userContext':'profile','url':observed}]}
            assert method=='browsingContext.navigate' and params['context']=='owned'
            self.navigation+=1
            if self.navigation==1:raise TimeoutError()
            return {}
    c=Connection();page=BackgroundPage(c,'owned');page.user_context='profile'
    async def stable(**kwargs):return {'stable':True}
    async def no_sleep(_):pass
    page.wait_stable=stable;monkeypatch.setattr(asyncio,'sleep',no_sleep)
    result=await page.navigate('https://example.com/a')
    assert c.navigation==calls and c.reconnects==1
    assert result['navigation_recovered']==(calls==1)


@pytest.mark.asyncio
async def test_navigation_never_adopts_other_tab_on_timeout():
    class Connection:
        async def command(self,method,params,**kwargs):
            if method=='browsingContext.getTree':return {'contexts':[{'context':'foreign','url':'https://example.com/a'}]}
            raise TimeoutError()
    with pytest.raises(RuntimeError,match='original browser context'):
        await BackgroundPage(Connection(),'owned').navigate('https://example.com/a')


@pytest.mark.asyncio
async def test_bidi_timeout_diagnostics_do_not_include_url():
    from types import SimpleNamespace as NS
    from ai2apps.browser.background_bidi import BackgroundBiDi,BrowserCommandTimeout
    c=BackgroundBiDi();sent=[]
    async def send(value):sent.append(json.loads(value))
    c._upstream=NS(send=send);c._reader=asyncio.current_task()
    with pytest.raises(BrowserCommandTimeout) as error:
        await c.command('browsingContext.navigate',{'url':'https://example.com/private'},timeout=.001)
    assert error.value.method=='browsingContext.navigate' and error.value.outcome_unknown
    assert 'private' not in str(error.value) and not c._pending and len(sent)==1


@pytest.mark.asyncio
async def test_action_exception_delivers_durable_failure_not_pause(tmp_path):
    from types import SimpleNamespace as NS
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    from ai2apps.browser.background_bidi import BrowserCommandTimeout
    database=JournalDatabase(tmp_path/'journal.sqlite');delivered=[];executed=[]
    request={'step':{'operation':'click'}}
    with database.transaction(write=True) as c:c.execute('UPDATE agent_interactions SET request_json=? WHERE id=?',(json.dumps(request),'interaction'))
    run=NS(id='run',status=NS(value='waiting_input'),input={'parameters':{'owner_user_id':'alice','browser_context':{'bidi_context':'tab'}}})
    async def execute(*a):executed.append(1);raise BrowserCommandTimeout('input.performActions',30,1)
    runtime=NS(database=database,events=None,agents=NS(get_run=lambda _:run,list_interactions=lambda _:[NS(id='interaction',request=request)],respond_interaction=lambda *a,**kw:delivered.append(kw['response'])),agent_runtime=NS(wake=lambda:None))
    runner=BackgroundBrowserRunner(runtime);runner.executor=NS(execute=execute)
    async def command(*a,**kw):return {'contexts':[]}
    page=NS(context_id='tab',connection=NS(command=command),created_contexts={})
    async def page_for(_):return page
    runner.page_for=page_for;runner.save_page_state=lambda *a:None
    await runner.execute_interaction({'run_id':'run','id':'interaction'})
    await runner.execute_interaction({'run_id':'run','id':'interaction'})
    assert executed==[1] and delivered[0]==delivered[1]
    assert delivered[0]['outcome']=='failed' and delivered[0]['evidence']['action_outcome_unknown']
    assert delivered[0]['evidence']['method']=='input.performActions'


def test_unknown_action_journal_failure_does_not_readmit(tmp_path):
    journal=BrowserActionJournal(JournalDatabase(tmp_path/'journal.sqlite'))
    claim=dict(run_id='run',interaction_id='interaction',owner='alice',context_id='tab',request={'step':'click'})
    journal.claim(**claim);journal.recover()
    response={'outcome':'failed','evidence':{'action_outcome_unknown':True,'automatic_replay_allowed':False}}
    journal.report_failure('interaction',response)
    record,admitted=journal.claim(**claim)
    assert not admitted and json.loads(record['response_json'])==response


@pytest.mark.asyncio
async def test_navigation_retry_exhausts_at_two_commands():
    class Connection:
        def __init__(self):self.calls=0
        async def command(self,method,params,**kwargs):
            if method=='browsingContext.getTree':return {'contexts':[{'context':'owned','url':'about:blank'}]}
            self.calls+=1;raise TimeoutError()
    c=Connection()
    with pytest.raises(TimeoutError) as error:await BackgroundPage(c,'owned').navigate('https://example.com/a')
    assert c.calls==2 and error.value.navigation_attempts==2


def test_browser_agent_failed_transition_exposes_transport_reason():
    from types import SimpleNamespace as NS
    from ai2apps.agent_builder.compiler import compile_source
    from ai2apps.agents.browser_builder import browser_builder_executor
    from ai2apps.agents.models import InteractionStatus,FailAction
    ir=compile_source({'site_scope':['https://example.com/**'],'steps':[{'name':'open','operation':'open','arguments':{'url':'https://example.com/a'},'on':{'success':'done','failed':'failed'}}]}).ir
    interactions=[];context=NS(run=NS(input={'parameters':{'ir':ir}}),definition=NS(max_steps=100),interactions=interactions,interaction=lambda _:None)
    first=browser_builder_executor(context)
    interactions.append(NS(id='failure',request=first.request,request_key=first.request_key,status=InteractionStatus.SUBMITTED,response={'outcome':'failed','evidence':{'reason':'browser_command_timeout','message':'Navigation did not respond','action_outcome_unknown':True}}))
    result=browser_builder_executor(context)
    assert isinstance(result,FailAction) and result.message=='Navigation did not respond'


@pytest.mark.asyncio
async def test_restart_unknown_action_delivers_failure_without_browser_replay(tmp_path):
    from types import SimpleNamespace as NS
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    database=JournalDatabase(tmp_path/'journal.sqlite');delivered=[]
    runner=BackgroundBrowserRunner(NS(database=database,events=None))
    runner.journal.claim(run_id='run',interaction_id='interaction',owner='alice',context_id='tab',request={'step':'click'})
    runner.runtime.agents=NS(get_run=lambda _:NS(status=NS(value='interrupted')),respond_interaction=lambda *a,**kw:delivered.append(kw['response']))
    runner.runtime.agent_runtime=NS(wake=lambda:None,cancel=lambda _:None)
    runner.tasks=NS(owners=lambda:[])
    async def loop():pass
    runner._loop=loop
    await runner.startup();await runner._loop_task
    assert delivered[0]['outcome']=='failed' and delivered[0]['evidence']['reason']=='browser_process_interrupted'
    assert runner.journal.lookup('interaction')['state']=='completed'

@pytest.mark.asyncio
async def test_reused_open_skips_navigation_only_for_exact_current_url():
    class Page:
        url='https://example.com/news'
        def __init__(self):self.visits=[]
        async def snapshot(self):return {'url':self.url}
        async def navigate(self,url,delay):self.visits.append(url);self.url=url;return {'url':url}
    page=Page();executor=BackgroundExecutor(None)
    step={'operation':'open','arguments':{'url':page.url,'reuse_current_page':True}}
    result=await executor.compiled(page,step,['https://example.com/**'])
    assert result['evidence']['result']['page_reused']
    assert page.visits==[]
    step['arguments']['url']='https://example.com/news?page=2'
    await executor.compiled(page,step,['https://example.com/**'])
    assert page.visits==['https://example.com/news?page=2']
    step['arguments']['reuse_current_page']=False
    await executor.compiled(page,step,['https://example.com/**'])
    assert len(page.visits)==2

@pytest.mark.asyncio
async def test_http3_navigation_rejection_retries_same_get_once(monkeypatch):
    from unittest.mock import AsyncMock
    from ai2apps.browser.background_page import BackgroundPage
    import ai2apps.browser.background_page as module
    monkeypatch.setattr(module.asyncio,'sleep',AsyncMock())
    connection=type('Connection',(),{})()
    connection.command=AsyncMock(side_effect=[RuntimeError('unknown error: NS_ERROR_NET_HTTP3_PROTOCOL_ERROR'),{}])
    page=BackgroundPage(connection,'original-tab')
    page.wait_stable=AsyncMock(return_value={'stable':True})
    result=await page.navigate('https://www.google.com/search?q=recipe',0)
    assert result['navigation_attempts']==2
    calls=connection.command.await_args_list
    assert calls[0].args==calls[1].args
    assert calls[0].args[0]=='browsingContext.navigate'
    assert calls[0].args[1]['context']=='original-tab'


def test_pending_browser_actions_require_readmission_after_human_pause(tmp_path):
    from types import SimpleNamespace
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    database=JournalDatabase(tmp_path/'admission.sqlite')
    with database.transaction(write=True) as c:
        c.execute('ALTER TABLE agent_interactions ADD COLUMN created_at REAL DEFAULT 0')
        c.execute('CREATE TABLE browser_tasks(run_id TEXT,status TEXT,browser_context_json TEXT)')
        c.execute('UPDATE agent_runs SET input_json=?', (json.dumps({'parameters':{'execution_owner':'local'}}),))
        c.execute('UPDATE agent_interactions SET request_json=?', (json.dumps({'control':'browser_bidi_action'}),))
        c.execute('INSERT INTO browser_tasks VALUES(?,?,?)', ('run','waiting_input',json.dumps({'admission_paused':True})))
    runner=BackgroundBrowserRunner(SimpleNamespace(database=database,events=None))
    assert runner.pending()==[]
    with database.transaction(write=True) as c:c.execute("UPDATE browser_tasks SET status='queued'")
    assert runner.pending()==[]
    with database.transaction(write=True) as c:c.execute("UPDATE browser_tasks SET status='running',browser_context_json='{}'")
    assert runner.pending()==[{'id':'interaction','run_id':'run'}]


def test_browser_result_repairs_utf16_before_persistence_and_delivery(tmp_path):
    journal = BrowserActionJournal(JournalDatabase(tmp_path/'unicode.sqlite'))
    claim = dict(run_id='run', interaction_id='interaction', owner='alice', context_id='tab', request={'step':'click'})
    journal.claim(**claim)
    original = {'outcome':'success', 'evidence':{'items':[{'title':'中文 🧵 𝒜', 'snippet':'cut\ud835', 'pair':'\ud835\udc9c', 'low':'\udc9c'}]}}
    expected = {'outcome':'success', 'evidence':{'items':[{'title':'中文 🧵 𝒜', 'snippet':'cut�', 'pair':'𝒜', 'low':'�'}]}}
    delivered = journal.complete('interaction', original)
    assert delivered == expected
    # The exact value delivered to the Agent must also be valid UTF-8 JSON.
    assert json.loads(json.dumps(delivered, ensure_ascii=False).encode('utf-8')) == expected
    assert original['evidence']['items'][0]['snippet'] == 'cut\ud835'
    assert journal.complete('interaction', original) == expected
    recovered, admitted = journal.claim(**claim)
    assert not admitted and json.loads(recovered['response_json']) == expected


@pytest.mark.asyncio
async def test_runner_delivers_repaired_response_without_replaying_browser(tmp_path):
    from types import SimpleNamespace as NS
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    database = JournalDatabase(tmp_path/'runner-unicode.sqlite')
    request = {'step':{'operation':'search.api'}}
    with database.transaction(write=True) as c:
        c.execute('UPDATE agent_interactions SET request_json=? WHERE id=?', (json.dumps(request),'interaction'))
    run = NS(id='run', input={'parameters':{'owner_user_id':'alice'}})
    delivered, executed = [], []
    def respond(*args, **kw):
        # Simulate the Agent repository's real SQLite UTF-8 serialization.
        json.dumps(kw['response'], ensure_ascii=False).encode('utf-8')
        delivered.append(kw['response'])
    runtime = NS(database=database, events=None, agents=NS(get_run=lambda _:run,
        list_interactions=lambda _:[NS(id='interaction', request=request)], respond_interaction=respond),
        agent_runtime=NS(wake=lambda:None))
    runner = BackgroundBrowserRunner(runtime)
    async def execute(*args):
        executed.append(1)
        return {'outcome':'success', 'evidence':{'text':'cut\ud835'}}
    runner.executor = NS(execute=execute)
    await runner.execute_interaction({'run_id':'run','id':'interaction'})
    await runner.execute_interaction({'run_id':'run','id':'interaction'})
    assert executed == [1]
    assert delivered == [{'outcome':'success','evidence':{'text':'cut�'}}] * 2


@pytest.mark.asyncio
@pytest.mark.parametrize('bad_evidence',[False,True])
async def test_x_rule_loading_snapshot_does_not_poison_later_valid_evidence(monkeypatch,bad_evidence):
    from ai2apps.browser.background_page import BackgroundPage
    class Page(BackgroundPage):
        def __init__(self):self.calls=0
        async def handle_access(self):return {'classification':'open'}
        async def call_json(self,*args):
            self.calls+=1
            if self.calls==1:
                return {'items':[{'post_id':'other','text':'fallback evidence'}] if bad_evidence else [],'x_rule_valid':False,'x_rule_compared':False}
            return {'items':[{'post_id':'1','author':'Author','published_at':'','images':[],'text':'Actual post'}],'x_rule_valid':True,'x_rule_compared':True}
    async def no_sleep(*args):pass
    monkeypatch.setattr('ai2apps.browser.background_page.asyncio.sleep',no_sleep)
    result=await Page().x_page({'x':'detail','url':'https://x.com/Author/status/1','x_extraction':{'card':'article'}})
    assert result['text'].endswith('Actual post')
    assert result['x_rule_valid'] is (not bad_evidence)
    assert result['x_rule_compared'] is (not bad_evidence)

@pytest.mark.parametrize('owner_message', ['Open the Acme inventory page; check item X before continuing.', None])
def test_assistance_uses_owner_message_not_internal_reason(owner_message):
    from types import SimpleNamespace as NS
    from ai2apps.agent_builder.compiler import compile_source
    from ai2apps.agents.browser_builder import browser_builder_executor
    from ai2apps.agents.models import InteractionStatus
    ir=compile_source({'site_scope':['https://arbitrary.test/**'],'steps':[{'name':'inspect','operation':'inspect','on':{'success':'done','failed':'failed'}}]}).ir
    run=NS(input={'parameters':{'ir':ir}})
    interactions=[]
    context=NS(run=run,definition=NS(max_steps=100),interactions=interactions,interaction=lambda key: next((i for i in interactions if i.request_key==key),None))
    first=browser_builder_executor(context)
    evidence={'reason':'opaque_owner_code'}
    if owner_message:evidence['assistance_message']=owner_message
    interactions.append(NS(id='action-1',request=first.request,request_key=first.request_key,status=InteractionStatus.SUBMITTED,response={'outcome':'needs_user','evidence':evidence}))
    action=browser_builder_executor(context)
    assert action.request['reason']=='opaque_owner_code'
    assert 'opaque_owner_code' not in action.prompt
    assert action.prompt==(owner_message or '任务未能继续。请打开任务页面检查当前状态，反馈具体情况或取消；不要重复执行尚未核实的操作。')


@pytest.mark.asyncio
async def test_annotated_refs_resolve_only_current_observed_control():
    from unittest.mock import AsyncMock
    page = BackgroundPage(None, 'context')
    page.snapshot = AsyncMock(return_value={'items':[
        {'ref':'e1','text':'Same label','rect':[0,0,10,10]},
        {'ref':'e2','text':'Same label with details','rect':[10,0,10,10]}]})
    assert (await page.find_target('Same label (ref e2)'))['ref'] == 'e2'
    assert (await page.find_target('Same label (e2)'))['ref'] == 'e2'
    assert await page.find_target('Same label (ref e999)') is None
    assert (await page.find_target('gridcell e2 (full date label)'))['ref']=='e2'
    assert await page.find_target('e1 or e2') is None

@pytest.mark.asyncio
@pytest.mark.parametrize('provider',['arbitrary-provider-a','independent-provider-b'])
async def test_uncertain_action_uses_trusted_read_only_observation_without_readmission(tmp_path,provider):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock,Mock
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    db=JournalDatabase(tmp_path/'recover.sqlite')
    request={'step':{'operation':'search.api','arguments':{'provider':provider}}}
    with db.transaction(write=True) as c:c.execute('UPDATE agent_interactions SET request_json=?',(json.dumps(request),))
    journal=BrowserActionJournal(db)
    journal.claim(run_id='run',interaction_id='interaction',owner='alice',context_id=None,request=request)
    journal.recover()
    run=SimpleNamespace(id='run',input={'parameters':{'owner_user_id':'alice'}})
    interaction=SimpleNamespace(id='interaction',request=request)
    expected={'outcome':'success','evidence':{'result':{'items':[],'provider':provider}}}
    runner=object.__new__(BackgroundBrowserRunner);runner.journal=journal
    runner.runtime=SimpleNamespace(agents=SimpleNamespace(get_run=lambda _:run,list_interactions=lambda _:[interaction],respond_interaction=Mock()),agent_runtime=SimpleNamespace(wake=Mock()))
    runner.executor=SimpleNamespace(recover_observation=AsyncMock(return_value=expected),execute=AsyncMock(side_effect=AssertionError('Never execute again')))
    runner.page_for=AsyncMock(side_effect=AssertionError('No page for API'))
    await runner.execute_interaction({'run_id':'run','id':'interaction'})
    assert json.loads(journal.lookup('interaction')['response_json'])==expected
    runner.executor.execute.assert_not_called();runner.page_for.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('label,goal',[('出发地','MAIN form: visible 单程 option above 出发地'),('Workspace','Search document only inside Workspace toolbar')])
async def test_narrative_target_does_not_match_an_incidental_short_label(label,goal):
    from unittest.mock import AsyncMock
    page=BackgroundPage(None,'context')
    page.snapshot=AsyncMock(return_value={'items':[{'ref':'e1','text':label,'rect':[0,0,10,10]},{'ref':'e2','text':'Search','rect':[20,0,10,10]}]})
    assert await page.find_target(goal,'click') is None
    assert (await page.find_target(label,'click'))['ref']=='e1'
    assert (await page.find_target('e1','click'))['ref']=='e1'

@pytest.mark.asyncio
@pytest.mark.parametrize('host',['workspace.fixture.test','catalog.fixture.test'])
async def test_inspection_can_finish_from_actual_initial_read_without_invented_click(host):
    from types import SimpleNamespace as NS
    from unittest.mock import AsyncMock
    from ai2apps.browser.background_planner import validate_completion
    observation={'context':'owned','url':f'https://{host}/form','items':[],'text':'Category already set'}
    async def plan(**kwargs):
        validate_completion(kwargs['step'],kwargs['attempts'])
        assert kwargs['attempts'][0]['evidence']['result']['url']==observation['url']
        return {'decision':'complete'}
    page=NS(context_id='owned',observation=AsyncMock(return_value=observation),related_windows=AsyncMock(return_value=[]))
    executor=BackgroundExecutor(None);executor.planner=NS(next=plan)
    executor.compiled=AsyncMock(side_effect=AssertionError('no invented input'))
    result=await executor.adaptive(page,{'step':{'operation':'inspect','arguments':{'preparation_only':True}},'site_scope':[f'https://{host}/**']},None)
    assert result['outcome']=='success'
    executor.compiled.assert_not_called();page.observation.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('operation,url',[('click','https://workspace.fixture.test/form'),('inspect','https://different.fixture.test/form')])
async def test_initial_observation_cannot_prove_effectful_or_out_of_scope_completion(operation,url):
    from types import SimpleNamespace as NS
    from unittest.mock import AsyncMock
    from ai2apps.browser.background_planner import validate_completion
    async def plan(**kwargs):
        validate_completion(kwargs['step'],kwargs['attempts'])
        return {'decision':'complete'}
    page=NS(context_id='owned',observation=AsyncMock(return_value={'url':url}),related_windows=AsyncMock(return_value=[]))
    executor=BackgroundExecutor(None);executor.planner=NS(next=plan)
    with pytest.raises(ValueError,match='successful evidence'):
        await executor.adaptive(page,{'step':{'operation':operation},'site_scope':['https://workspace.fixture.test/**']},None)


@pytest.mark.asyncio
async def test_planning_and_explicit_ref_resolution_use_the_same_bounded_probe():
    from unittest.mock import AsyncMock
    page = BackgroundPage(None, 'owned')
    row = {'ref':'e987','tag':'button','text':'Late calendar option','rect':[0,0,30,30]}
    async def snapshot(*args, **kwargs):
        assert kwargs['max_items'] == 600
        return {'url':'https://fixture.test/','items':[row],'text':'option'}
    page.snapshot = AsyncMock(side_effect=snapshot)
    assert (await page.observation())['controls'][0]['ref'] == 'e987'
    assert (await page.find_target('Late option (ref e987)'))['ref'] == 'e987'

@pytest.mark.asyncio
@pytest.mark.parametrize('allow_intervention',[True,False])
@pytest.mark.parametrize('policy_source',['request','run_ir'])
async def test_pre_dispatch_failure_is_durable_and_never_reexecuted(tmp_path,allow_intervention,policy_source):
    from types import SimpleNamespace as NS
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    from ai2apps.browser.background_page import NativeInputNotDispatched
    from ai2apps.browser.input_dispatch import InputDiagnostics
    database=JournalDatabase(tmp_path/'journal.sqlite');delivered=[];executed=[]
    request={'step':{'operation':'scroll'},**({'execution_policy':{'allow_user_intervention':allow_intervention}} if policy_source=='request' else {})}
    with database.transaction(write=True) as c:c.execute('UPDATE agent_interactions SET request_json=? WHERE id=?',(json.dumps(request),'interaction'))
    run=NS(id='run',status=NS(value='waiting_input'),input={'parameters':{'owner_user_id':'alice','browser_context':{'bidi_context':'tab'},'ir':{'execution_policy':{'allow_user_intervention':allow_intervention}}}})
    async def execute(*a):executed.append(1);raise NativeInputNotDispatched('not sent')
    runtime=NS(database=database,events=None,agents=NS(get_run=lambda _:run,list_interactions=lambda _:[NS(id='interaction',request=request)],respond_interaction=lambda *a,**kw:delivered.append(kw['response'])),agent_runtime=NS(wake=lambda:None))
    runner=BackgroundBrowserRunner(runtime);runner.executor=NS(execute=execute)
    async def command(*a,**kw):return {'contexts':[]}
    page=NS(context_id='tab',connection=NS(command=command),created_contexts={},input_diagnostics=InputDiagnostics())
    async def page_for(_):return page
    runner.page_for=page_for;runner.save_page_state=lambda *a:None
    await runner.execute_interaction({'run_id':'run','id':'interaction'})
    await runner.execute_interaction({'run_id':'run','id':'interaction'})
    assert executed==[1] and delivered[0]==delivered[1]
    assert delivered[0]['outcome']==('needs_user' if allow_intervention else 'failed')
    assert delivered[0]['evidence']['input_dispatched'] is False
    assert delivered[0]['evidence']['action_outcome_unknown'] is False
    assert runner.journal.lookup('interaction')['state']=='completed'
