from copy import deepcopy
from types import SimpleNamespace

import pytest
from jsonschema import ValidationError

from ai2apps.browser.mini_apps import WebAgentMiniAppBroker, capability_catalog, validate_web_agent
from ai2apps.browser.tasks import BrowserTaskRepository
from ai2apps.storage import PlatformDatabase
from ai2apps.studio.capability_broker import StudioCapabilityError


def declaration():
    return {'id':'demo.reader','web_agent':{'schema':'ai2apps.web-agent-mini-app/v1','capabilities':[
        {'id':'list','title':'Articles','source':{'agent_type':'web','site_scope':['https://example.com/**'],
         'inputs':{'type':'object','properties':{'count':{'type':'integer','minimum':1}},'required':['count'],'additionalProperties':False},
         'steps':[{'name':'read','operation':'inspect','on':{'success':'done','failed':'failed'}}]}},
        {'id':'article','source':{'agent_type':'web','site_scope':['https://example.com/**'],
         'steps':[{'name':'read','operation':'inspect','on':{'success':'done','failed':'failed'}}]}}
    ]}}


def test_multiple_capabilities_have_independent_parameters():
    catalog=capability_catalog(declaration())
    assert [c['capability'] for c in catalog]==['list','article']
    assert catalog[0]['input_schema']['required']==['count']
    assert catalog[1]['input_schema']['additionalProperties'] is False


@pytest.mark.parametrize('change',[
    lambda d:d['web_agent']['capabilities'].append(deepcopy(d['web_agent']['capabilities'][0])),
    lambda d:d['web_agent']['capabilities'][0]['source'].pop('site_scope'),
    lambda d:d['web_agent']['capabilities'][0]['source']['steps'][0].update(operation='unknown'),
    lambda d:d.update(web_agent={}),
])
def test_invalid_package_programs_are_rejected(change):
    raw=declaration();change(raw)
    with pytest.raises(ValueError):validate_web_agent(raw)


@pytest.fixture
def broker(tmp_path,monkeypatch):
    db=PlatformDatabase(tmp_path/'tasks.sqlite');db.initialize()
    runtime=SimpleNamespace(database=db,events=None,model_manager=SimpleNamespace(resolve_default_model=lambda *a, **kw: 'configured-model'))
    broker=WebAgentMiniAppBroker(runtime)
    mounted=SimpleNamespace(declaration=declaration(),mount={'app_instance_id':'app-one','effective_digest':'digest'})
    monkeypatch.setattr(broker,'mounted',lambda *a:mounted)
    # Submission now validates workload Session ownership. Persist a real
    # owned Session rather than bypassing that guard with a literal fixture ID.
    from dataclasses import replace
    from ai2apps.identity import RequestPrincipal
    from ai2apps.chat import ChatRepository
    actor=replace(RequestPrincipal.legacy_local(),actor_user_id='owner')
    thread,_=ChatRepository(db,principal=actor).create_thread()
    runtime.fixture_session_id=thread.session.id
    monkeypatch.setattr('ai2apps.api.agent_platform._session',lambda *a:thread.session.id)
    monkeypatch.setattr('ai2apps.browser.profiles.BrowserProfileRepository.require',lambda *a:SimpleNamespace(name='Default',is_default=True))
    monkeypatch.setattr('ai2apps.api.ownership.authorize_session',lambda *a:None)
    monkeypatch.setattr('ai2apps.identity.IdentityRepository.local_principal_for',lambda *a:SimpleNamespace(actor_user_id='owner'))
    return broker,mounted,SimpleNamespace(actor_user_id='owner',client_scope='desktop')


def test_mobile_submission_uses_same_owner_local_task_session(broker,monkeypatch):
    service,mount,principal=broker
    principal.client_scope='mobile'
    mount.mount['interaction_session_id']='mobile-chat-session'
    local=SimpleNamespace(actor_user_id='owner',client_scope='desktop')
    monkeypatch.setattr('ai2apps.identity.IdentityRepository.local_principal_for',lambda *a:local)
    calls=[]
    def session(runtime,actor,requested):
        calls.append((actor,requested))
        return runtime.fixture_session_id
    monkeypatch.setattr('ai2apps.api.agent_platform._session',session)
    task=service.submit('mount',principal,capability='list',parameters={'count':3},profile='default',request_id='mobile')
    assert calls==[(local,None)]
    assert task['session_id']==service.runtime.fixture_session_id
    assert task['owner']=='owner'


def test_submit_pins_compiled_program_in_shared_queue_and_is_idempotent(broker):
    service,mount,principal=broker
    kwargs=dict(capability='list',parameters={'count':3},profile='default',request_id='one')
    task=service.submit('mount',principal,**kwargs)
    assert task['status']=='queued'
    assert service.submit('mount',principal,**kwargs)['id']==task['id']
    with pytest.raises(ValueError,match='Request ID'):
        service.submit('mount',principal,**{**kwargs,'parameters':{'count':4}})
    repo=BrowserTaskRepository(service.runtime.database)
    program,caller=repo.program('owner',task['id'])
    assert program['steps'][0]['id']=='read'
    assert caller==service.caller(mount)
    assert repo.claim('owner','worker')['id']==task['id']


def test_inputs_and_task_scope_cannot_be_spoofed(broker):
    service,mount,principal=broker
    with pytest.raises(ValidationError):
        service.submit('mount',principal,capability='list',parameters={'count':0},profile='default',request_id='bad')
    with pytest.raises(StudioCapabilityError):
        service.submit('mount',principal,capability='undeclared',parameters={},profile='default',request_id='bad')
    task=service.submit('mount',principal,capability='article',parameters={},profile='default',request_id='ok')
    assert service.task('mount',principal,task['id'])['id']==task['id']
    mount.mount['app_instance_id']='another-app'
    with pytest.raises(StudioCapabilityError,match='does not belong'):
        service.task('mount',principal,task['id'])


def test_custom_sources_are_only_available_to_search_all_and_use_host_program(broker):
    service, mount, principal = broker
    kwargs = dict(capability='discover_source', parameters={'url': 'https://example.com/', 'locale': 'zh'},
                  profile='default', request_id='discover')
    with pytest.raises(StudioCapabilityError): service.submit('mount', principal, **kwargs)
    mount.declaration['id'] = 'ai2apps.search-all'
    task = service.submit('mount', principal, **kwargs)
    program, caller = BrowserTaskRepository(service.runtime.database).program('owner', task['id'])
    assert program['site_scope'] == ['https://example.com/**']
    assert [step['operation'] for step in program['steps']] == ['open', 'inspect', 'ai.transform', 'assign']
    with pytest.raises(ValueError):
        service.submit('mount', principal, **{**kwargs, 'parameters': {'url': 'https://127.0.0.1/', 'locale': 'zh'}})
    task = service.submit('mount', principal, capability='resolve_source',
        parameters={'description': '豆瓣/GitHub', 'locale': 'zh'}, profile='default', request_id='names')
    program, _ = BrowserTaskRepository(service.runtime.database).program('owner', task['id'])
    assert [step['operation'] for step in program['steps']] == ['ai.transform']


def test_builtin_reader_uses_shipped_declaration_and_assets():
    from ai2apps.browser.builtin_mini_apps import definitions
    minis,resources=definitions()
    mini=next(m for m in minis if m['id']=='ai2apps.web-reader')
    assert len(validate_web_agent(mini))==2
    assert 'builtin_mini_apps/web-reader/web/web_agent_mini_app_sdk.js' in resources



def test_changed_package_mount_is_rejected():
    from ai2apps.studio.capability_broker import StudioCapabilityBroker
    class Manager:
        def mount_entry(self,*args,**kwargs):
            return {'entry_source':'mini_entry','context':{'studioId':'ai2apps.ai-browser','miniAppId':'demo.reader'},'app_key':'demo','effective_digest':'old'}
        def list_studio_mini_apps(self,*args,**kwargs):
            return [{**declaration(),'provider':{'appId':'demo','digest':'new'}}]
    runtime=SimpleNamespace(extension_manager=Manager())
    with pytest.raises(StudioCapabilityError,match='no longer active'):
        StudioCapabilityBroker(runtime).mounted_mini_app('ai2apps.ai-browser','mount',principal=SimpleNamespace())


def test_http_submission_rejects_frontend_source_and_returns_durable_task(broker,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.api.studio_mini_apps import create_studio_mini_app_router
    service,mount,principal=broker
    service.runtime.extension_manager=object()
    monkeypatch.setattr(WebAgentMiniAppBroker,'mounted',lambda *a:mount)
    app=FastAPI();app.include_router(create_studio_mini_app_router(lambda:service.runtime,lambda:principal),prefix='/v1/platform')
    client=TestClient(app)
    url='/v1/platform/studios/ai2apps.ai-browser/mini-app-mounts/mount/web-agent/tasks'
    body={'capability':'article','parameters':{},'profile':'default','request_id':'http-test'}
    assert client.post(url,json={**body,'source':{'steps':[]}}).status_code==422
    result=client.post(url,json=body)
    assert result.status_code==201,result.text
    task=result.json();assert task['status']=='queued'
    assert client.get(url+'/'+task['id']).json()['id']==task['id']
    mount.mount['app_instance_id']='other'
    assert client.get(url+'/'+task['id']).status_code==404


def test_task_view_distinguishes_background_browser_wait_from_user_assistance(broker):
    service,mount,principal=broker
    task=service.submit('mount',principal,capability='article',parameters={},profile='default',request_id='wait')
    BrowserTaskRepository(service.runtime.database).update(principal.actor_user_id,task['id'],status='waiting_input',run_id='run-test')
    interaction=SimpleNamespace(status='pending',request={'control':'browser_bidi_action'},prompt='Read browser')
    service.runtime.agents=SimpleNamespace(get_run=lambda _:SimpleNamespace(output={}),list_interactions=lambda _:[interaction])
    assert service.task('mount',principal,task['id'])['status_label']=='等待浏览器响应'
    interaction.request={'control':'browser_user_assistance'}
    assert service.task('mount',principal,task['id'])['status_label']=='等待协助'


def test_retention_is_explicit_scoped_and_request_id_cannot_change_it(broker):
    service,mount,principal=broker
    options=dict(capability='article',parameters={},profile='default',request_id='retained',retain_pages=True)
    task=service.submit('mount',principal,**options)
    assert task['browser_context']['retain_pages_reason']=='mini-app-search-results'
    assert service.retained_tasks('mount',principal)[0]['id']==task['id']
    with pytest.raises(ValueError,match='Request ID'):
        service.submit('mount',principal,**{**options,'retain_pages':False})
    mount.mount['app_instance_id']='different'
    assert service.retained_tasks('mount',principal)==[]


@pytest.mark.asyncio
async def test_retained_pages_only_focus_and_close_owned_matching_profile(broker,monkeypatch):
    from unittest.mock import AsyncMock
    import json
    service,mount,principal=broker
    task=service.submit('mount',principal,capability='article',parameters={},profile='default',request_id='pages',retain_pages=True)
    context={**task['browser_context'],'owned_contexts':{'owned':'u1','other-profile':'u2'},'user_context':'u1','bidi_context':'owned','cleanup':{'state':'retained'}}
    repo=BrowserTaskRepository(service.runtime.database)
    repo.update('owner',task['id'],status='completed',browser_context_json=json.dumps(context))
    pages=[{'context':'owned','userContext':'u1','url':'https://example.com/search'}, {'context':'other-profile','userContext':'u2'}, {'context':'unowned','userContext':'u1'}]
    async def command(method,args):
        if method=='browsingContext.getTree':return {'contexts':list(pages)}
        if method=='browsingContext.close':pages[:]=[p for p in pages if p['context']!=args['context']]
        return {}
    connection=SimpleNamespace(command=AsyncMock(side_effect=command),close=AsyncMock())
    monkeypatch.setattr('ai2apps.api.client._request_shell_browser_action',lambda *a: {'status':'focused'})
    monkeypatch.setattr('ai2apps.browser.background_bidi.BackgroundBiDi.connect',AsyncMock(return_value=connection))
    result=await service.pages('mount',principal,task['id'],'focus')
    assert len(result['pages'])==1
    connection.command.assert_any_await('browsingContext.activate',{'context':'owned'})
    # A different Profile's recorded context must never be closed or block cleanup.
    result=await service.pages('mount',principal,task['id'],'close')
    assert result['pages']==[]
    assert {p['context'] for p in pages}=={'other-profile','unowned'}
    assert repo.get('owner',task['id'])['browser_context']['cleanup']['state']=='verified'


@pytest.mark.asyncio
async def test_retained_page_actions_reject_active_and_foreign_tasks(broker):
    service,mount,principal=broker
    task=service.submit('mount',principal,capability='article',parameters={},profile='default',request_id='active',retain_pages=True)
    with pytest.raises(StudioCapabilityError,match='finish'):
        await service.pages('mount',principal,task['id'],'close')
    mount.mount['app_instance_id']='different'
    with pytest.raises(StudioCapabilityError,match='does not belong'):
        await service.pages('mount',principal,task['id'],'focus')


def test_failure_projection_returns_diagnostic_code_without_page_text(broker):
    import json
    service,mount,principal=broker
    # Exercise the projection with a journal row stand-in, without exposing DOM.
    class Connection:
        def execute(self,*args):return SimpleNamespace(fetchall=lambda:[{'response_json':json.dumps({'outcome':'not_found','evidence':{'reason':'search_markup_unavailable','before':{'html':'private'}}})}])
    from contextlib import contextmanager
    @contextmanager
    def transaction():yield Connection()
    service.runtime.database=SimpleNamespace(transaction=transaction)
    assert service.failure('run',SimpleNamespace())=={'code':'search_markup_unavailable'}

def test_reader_failure_retains_csp_cause_and_run_error_without_dom(broker):
    import json
    service,_,_=broker
    cause='TypeError: innerHTML setter blocked by CSP'
    response={'outcome':'failed','evidence':{'operation':'read_page','reason':'article_extraction_failed','result':{'fallback_reason':cause,'url':'https://example.com/article','text':'PRIVATE BODY','html':'PRIVATE HTML'},'before':{'text':'PRIVATE BEFORE'}}}
    class Connection:
        def execute(self,*_):return SimpleNamespace(fetchall=lambda:[{'response_json':json.dumps(response)}])
    from contextlib import contextmanager
    @contextmanager
    def transaction():yield Connection()
    service.runtime.database=SimpleNamespace(transaction=transaction)
    failure=service.failure('run',SimpleNamespace(error={'code':'browser_agent_step_failed','message':'Read failed'}))
    assert failure['cause']['fallback_reason']==cause
    assert failure['operation']=='read_page'
    assert failure['run_error']['message']=='Read failed'
    assert 'PRIVATE' not in json.dumps(failure)

@pytest.mark.asyncio
async def test_open_result_only_accepts_observed_url_and_task_profile(broker, monkeypatch):
    service, mount, principal = broker
    calls = []
    monkeypatch.setattr(service, 'task', lambda *a: {'profile_key':'default', 'result':{'items':[{'url':'https://x.com/a/status/1'}]}})
    monkeypatch.setattr('ai2apps.api.client._request_shell_browser_action', lambda *a: calls.append(a) or {'user_context':'u1'})
    commands=[]
    class Connection:
        async def connect(self): return self
        async def command(self, method, args):
            commands.append((method,args));return {'context':'result'}
        async def close(self): pass
    monkeypatch.setattr('ai2apps.browser.background_bidi.BackgroundBiDi', Connection)
    assert await service.open_result('mount', principal, 'task', 'https://x.com/a/status/1') == {'opened':True}
    assert calls[0][-2:] == ('bind', None)
    assert commands[0][1]['userContext']=='u1'
    assert commands[1][1]['url']=='https://x.com/a/status/1'
    for url in ['https://evil.example/', 'javascript:alert(1)', 'https://user:pass@x.com/a/status/1']:
        with pytest.raises(StudioCapabilityError):
            await service.open_result('mount', principal, 'task', url)
    assert len(calls) == 2

def test_summary_can_only_read_results_observed_by_same_mini_app(broker,monkeypatch):
    service,mount,principal=broker
    mount.declaration['id']='ai2apps.search-all'
    raw=deepcopy(mount.declaration['web_agent']['capabilities'][1]);raw['id']='summarize';raw['source']['inputs']={'type':'object','properties':{'items':{'type':'array'}},'required':['items']}
    mount.declaration['web_agent']['capabilities'].append(raw)
    # The real Package declares a stricter item schema; this isolates broker authorization.
    monkeypatch.setattr(service,'task',lambda *args:{'status':'completed','result':{'items':[{'url':'https://example.com/observed'}]}})
    with pytest.raises(StudioCapabilityError,match='observed'):
        service.submit('mount',principal,capability='summarize',parameters={'items':[{'task_id':'search','url':'https://example.com/unobserved'}]},profile='default',request_id='no')


def test_gift_recommendations_use_shared_queue_normal_default_and_privacy_opt_in(broker):
    from pathlib import Path
    import json
    service,mount,principal=broker
    mount.declaration=json.loads((Path(__file__).resolve().parents[2]/'packages/ai2apps-shopping-pro/app.yaml').read_text())['mini_apps'][0]
    parameters={'recipient':'Coffee-loving friend','occasion':'Birthday','preferences':'No electronics',
                'budget_minor':5000,'currency':'USD','locale':'fr','message':'','conversation':[]}
    task=service.submit('mount',principal,capability='gift_recommend',parameters=parameters,profile='default',request_id='gift')
    assert task['status']=='queued'
    assert task['browser_context']['model_profile']=='normal'
    assert task['name']=='Recommander des cadeaux'
    program,caller=BrowserTaskRepository(service.runtime.database).program('owner',task['id'])
    assert program['steps'][0]['id']=='strategy'
    assert caller==service.caller(mount)
    private=service.submit('mount',principal,capability='gift_recommend',parameters={**parameters,'model_profile':'privacy'},profile='default',request_id='private-gift')
    assert private['browser_context']['model_profile']=='privacy'
    mount.declaration['web_agent']['model_profile']='normal'
    with pytest.raises(StudioCapabilityError,match='Privacy'):
        service.submit('mount',principal,capability='history',parameters={'pages':3},profile='default',request_id='unsafe-history')


def test_gift_cart_rejects_replenishment_provenance(broker,monkeypatch):
    from pathlib import Path
    import json
    service,mount,principal=broker
    mount.declaration=json.loads((Path(__file__).resolve().parents[2]/'packages/ai2apps-shopping-pro/app.yaml').read_text())['mini_apps'][0]
    monkeypatch.setattr(service,'task',lambda *args:{'status':'completed','capability':'history','profile_key':'default','result':{'items':[]}})
    with pytest.raises(StudioCapabilityError,match='completed tasks'):
        service.submit('mount',principal,capability='gift_prepare_cart',parameters={'locale':'zh','source_tasks':['old'],'selected':[{'id':'B000123456','quantity':1}]},profile='default',request_id='cart')

def test_search_sources_share_parallel_admission_and_settle(broker):
    service,mount,principal=broker
    mount.declaration['id']='ai2apps.search-all'
    tasks=[service.submit('mount',principal,capability='list',parameters={'count':3},profile='default',request_id=f'source{i}',batch_id='batch',batch_size=4) for i in range(4)]
    assert len({t['parent_task_id'] for t in tasks})==1
    repo=BrowserTaskRepository(service.runtime.database)
    for _ in range(3):assert repo.claim('owner','worker') is not None
    assert repo.claim('owner','worker') is None
    for t in tasks:repo.update('owner',t['id'],status='completed')
    from ai2apps.browser.task_tree import TaskTreeRepository
    tree=TaskTreeRepository(service.runtime.database)
    tree.reconcile()
    assert tree.get('owner',tasks[0]['parent_task_id'])['status']=='completed'
