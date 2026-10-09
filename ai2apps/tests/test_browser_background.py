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


class JournalDatabase:
    def __init__(self, path):
        self.path = path
        with self.transaction(write=True) as c:
            c.executescript('''CREATE TABLE agent_runs(id TEXT PRIMARY KEY,input_json TEXT,status TEXT);
CREATE TABLE agent_interactions(id TEXT PRIMARY KEY,run_id TEXT,status TEXT,request_json TEXT);
CREATE TABLE browser_action_executions(interaction_id TEXT PRIMARY KEY,run_id TEXT,owner TEXT,context_id TEXT,request_hash TEXT,state TEXT,response_json TEXT,started_at REAL,finished_at REAL);''')
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
async def test_200k_input_is_bounded_chunks_and_native_keys(monkeypatch):
    class Connection:
        def __init__(self): self.commands=[]
        async def command(self, method, params, **kwargs):
            self.commands.append((method, params))
            return {}
    connection=Connection();page=BackgroundPage(connection, 'tab')
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
    monkeypatch.setattr(transport.ShellBiDiEndpoint,'load',lambda _:None)
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
