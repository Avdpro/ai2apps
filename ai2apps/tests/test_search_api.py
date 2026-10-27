from types import SimpleNamespace
from unittest.mock import AsyncMock
import json
import pytest
from ai2apps.browser.search_api import search, record, configure, TOOL

class Secrets:
    def __init__(self):self.items=[];self.values={}
    def list(self):return self.items
    def create(self,**kwargs):
        item=SimpleNamespace(id='id',uri='secret://id',metadata=kwargs['metadata'],allowed_tools=kwargs['allowed_tools']);self.items.append(item);self.values[item.uri]=kwargs['value'];return item
    def replace(self,id,value):self.values['secret://'+id]=value
    def inject_arguments(self,args,tool):
        assert tool==TOOL
        return SimpleNamespace(arguments={'config':self.values[args['config']]})

def test_config_credentials_are_owner_scoped_and_replace_protected_value():
    runtime=SimpleNamespace(secrets=Secrets());configure(runtime,'alice','google','private-key','engine')
    assert record(runtime,'bob') is None
    assert 'private-key' not in str(runtime.secrets.items[0].metadata)
    configure(runtime,'alice','serpapi-bing','second-key')
    assert len(runtime.secrets.items)==1
    assert json.loads(runtime.secrets.values['secret://id'])['provider']=='serpapi-bing'

@pytest.mark.asyncio
async def test_missing_api_never_reads_other_owners_key():
    runtime=SimpleNamespace(secrets=Secrets());configure(runtime,'alice','google','private-key','engine')
    with pytest.raises(ValueError,match='not configured'):await search(runtime,'bob','query',10)

@pytest.mark.asyncio
async def test_api_normalizes_organic_links_and_keeps_key_out_of_result(monkeypatch):
    import ai2apps.browser.search_api as module
    runtime=SimpleNamespace(secrets=Secrets());configure(runtime,'alice','serpapi-bing','private-key')
    response=SimpleNamespace(status_code=200,content=b'{}',json=lambda:{'organic_results':[{'title':'Recipe','link':'https://example.com/recipe','snippet':'Cook'},{'title':'Unsafe','link':'javascript:alert(1)'}]})
    class Client:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def get(self,url,params):
            assert url=='https://serpapi.com/search.json';assert params['engine']=='bing';return response
    monkeypatch.setattr(module.httpx,'AsyncClient',lambda **kwargs:Client())
    result=await search(runtime,'alice','recipe',10)
    assert result['provider']=='bing' and result['transport']=='api'
    assert len(result['items'])==1 and 'private-key' not in json.dumps(result)

@pytest.mark.asyncio
async def test_transport_errors_do_not_disclose_request_url(monkeypatch):
    import ai2apps.browser.search_api as module
    runtime=SimpleNamespace(secrets=Secrets());configure(runtime,'alice','google','private-key','engine')
    class Client:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def get(self,*args,**kwargs):raise module.httpx.ConnectError('URL contains private-key')
    monkeypatch.setattr(module.httpx,'AsyncClient',lambda **kwargs:Client())
    with pytest.raises(ValueError) as error:await search(runtime,'alice','recipe',10)
    assert 'private-key' not in str(error.value)

def test_api_key_request_logs_are_redacted():
    import logging
    from ai2apps.browser.search_api import _SearchKeyLogFilter
    entry=logging.LogRecord('httpx',20,'file',1,'HTTP Request: GET %s',('https://serpapi.com/search.json?q=test&api_key=private-key&engine=google',),None)
    assert _SearchKeyLogFilter().filter(entry)
    assert 'private-key' not in entry.getMessage() and 'q=test' in entry.getMessage()

@pytest.mark.asyncio
async def test_api_interaction_uses_task_journal_without_creating_browser_tab():
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    from unittest.mock import Mock
    run=SimpleNamespace(id='run',input={'parameters':{'owner_user_id':'alice'}})
    interaction=SimpleNamespace(id='interaction',request={'step':{'operation':'search.api'}})
    agents=SimpleNamespace(get_run=lambda id:run,list_interactions=lambda id:[interaction],respond_interaction=Mock())
    runner=object.__new__(BackgroundBrowserRunner)
    runner.runtime=SimpleNamespace(agents=agents,agent_runtime=SimpleNamespace(wake=Mock()))
    runner.journal=SimpleNamespace(lookup=lambda id:None,claim=Mock(return_value=({},True)),complete=Mock())
    runner.page_for=AsyncMock(side_effect=AssertionError('API must not open a tab'))
    response={'outcome':'success','evidence':{'result':{'items':[]}}}
    runner.executor=SimpleNamespace(execute=AsyncMock(return_value=response))
    await runner.execute_interaction({'run_id':'run','id':'interaction'})
    runner.page_for.assert_not_called()
    assert runner.journal.claim.call_args.kwargs['context_id'] is None
    runner.journal.complete.assert_called_once_with('interaction',response)
    agents.respond_interaction.assert_called_once()

@pytest.mark.asyncio
async def test_api_provider_must_be_inside_reviewed_agent_scope():
    runtime=SimpleNamespace(secrets=Secrets());configure(runtime,'alice','google','private-key','engine')
    with pytest.raises(ValueError,match='outside'):await search(runtime,'alice','query',10,scopes=['https://example.com/**'])

@pytest.mark.asyncio
async def test_context_free_api_runs_through_real_sqlite_journal_and_replays_once(tmp_path,monkeypatch):
    from test_browser_background import JournalDatabase
    from ai2apps.browser.action_journal import BrowserActionJournal
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    from ai2apps.browser.background_executor import BackgroundExecutor
    import ai2apps.browser.search_api as module
    from unittest.mock import Mock
    db=JournalDatabase(tmp_path/'strict-action-journal.sqlite')
    request={'step':{'operation':'search.api','arguments':{'provider':'deepseek','query':'DeepSeek','limit':1}},
             'site_scope':['https://api.deepseek.com/v1/tools/search']}
    with db.transaction(write=True) as c:
        c.execute('UPDATE agent_interactions SET request_json=? WHERE id=?',(json.dumps(request),'interaction'))
    calls=[]
    class Client:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            calls.append(url)
            return SimpleNamespace(status_code=200,content=b'{}',json=lambda:{'results':[{'title':'DeepSeek','url':'https://www.deepseek.com','snippet':'Official'}]})
    monkeypatch.setattr(module,'byok_available',lambda *args:True)
    monkeypatch.setattr(module.httpx,'AsyncClient',lambda **kwargs:Client())
    run=SimpleNamespace(id='run',input={'parameters':{'owner_user_id':'alice'}})
    interaction=SimpleNamespace(id='interaction',request=request)
    runtime=SimpleNamespace(agents=SimpleNamespace(get_run=lambda _:run,list_interactions=lambda _:[interaction],respond_interaction=Mock()),
        agent_runtime=SimpleNamespace(wake=Mock()),model_manager=SimpleNamespace(resolve_credential=lambda _:'fixture-key'))
    runner=object.__new__(BackgroundBrowserRunner);runner.runtime=runtime
    runner.journal=BrowserActionJournal(db);runner.executor=BackgroundExecutor(runtime)
    runner.page_for=AsyncMock(side_effect=AssertionError('API must never create a page'))
    await runner.execute_interaction({'run_id':'run','id':'interaction'})
    saved=runner.journal.lookup('interaction')
    assert saved['state']=='completed' and saved['context_id']==''
    assert json.loads(saved['response_json'])['evidence']['result']['items'][0]['title']=='DeepSeek'
    await runner.execute_interaction({'run_id':'run','id':'interaction'})
    assert len(calls)==1
    runner.page_for.assert_not_called()
    with pytest.raises(ValueError,match='identity changed'):
        runner.journal.claim(run_id='run',interaction_id='interaction',owner='alice',context_id='another-tab',request=request)
