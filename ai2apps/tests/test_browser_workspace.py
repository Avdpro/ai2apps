import concurrent.futures
import pytest
from ai2apps.storage import PlatformDatabase
from ai2apps.browser.tasks import BrowserTaskRepository

@pytest.fixture
def tasks(tmp_path):
    database=PlatformDatabase(tmp_path/'tasks.sqlite3');database.initialize()
    return BrowserTaskRepository(database)

def enqueue(tasks, profile='default', owner='owner'):
    return tasks.enqueue(owner,profile,'draft','post','generation','Post',{})

def test_atomic_profile_and_global_admission(tasks):
    tasks.configure('owner',2,1)
    for profile in ['a','a','b','c']:enqueue(tasks,profile)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        claims=list(pool.map(lambda n:tasks.claim('owner',str(n)*16),range(8)))
    admitted=[c for c in claims if c]
    assert len(admitted)==2
    assert len({c['profile_key'] for c in admitted})==2
    assert tasks.claim('owner','worker'*4) is None
    tasks.update('owner',admitted[0]['id'],status='completed')
    assert tasks.claim('owner','worker'*4)

def test_interrupted_keeps_slot_and_owner_isolation(tasks):
    tasks.configure('owner',1,1)
    one=enqueue(tasks);enqueue(tasks)
    assert tasks.claim('other','worker'*4) is None
    assert tasks.list('other')==[]
    with pytest.raises(KeyError):tasks.get('other',one['id'])
    claimed=tasks.claim('owner','worker'*4)
    tasks.update('owner',claimed['id'],status='interrupted')
    assert tasks.claim('owner','worker'*4) is None
    tasks.update('owner',claimed['id'],status='cancelled')
    assert tasks.claim('owner','worker'*4)

def test_lower_limits_does_not_cancel_active_tasks(tasks):
    tasks.configure('owner',3,3)
    for _ in range(3):enqueue(tasks)
    claims=[tasks.claim('owner','worker'*4) for _ in range(3)]
    tasks.configure('owner',1,1)
    assert all(tasks.get('owner',t['id'])['status']=='starting' for t in claims)
    enqueue(tasks)
    assert tasks.claim('owner','worker'*4) is None
    with pytest.raises(ValueError):tasks.configure('owner',1,2)

def test_direct_admission_and_queue_share_slots(tasks):
    direct=tasks.reserve_external('owner','default','draft','read','gen','Read',{}, {'bidi_context':'tab'},key='once')
    assert tasks.reserve_external('owner','default','draft','read','gen','Read',{}, {},key='once')['id']==direct['id']
    enqueue(tasks)
    assert tasks.claim('owner','worker'*4) is None
    with pytest.raises(ValueError):tasks.reserve_external('owner','default','draft','read','gen','Read',{}, {})

def test_workspace_api_pins_generation_and_rejects_wrong_worker(tmp_path, monkeypatch):
    monkeypatch.setattr("ai2apps.browser.site_icons.discover_site_icon", lambda domain: "data:image/png;base64,test")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.identity import RequestPrincipal,MemberRole
    runtime=PlatformRuntime(PlatformConfig.from_base_path(tmp_path));runtime.start()
    principal=RequestPrincipal(actor_user_id='owner',installation_id='install',organization_id='org',billing_account_id='billing',role=MemberRole.MEMBER,membership_epoch=1)
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=lambda:principal));client=TestClient(app)
    base='/v1/platform'
    source={'name':'Reader','site_scope':['https://example.com/**'],'capabilities':[{'id':'read','name':'site.read','title':'读取页面','inputs':{'type':'object','properties':{'count':{'type':'integer'}},'required':['count']},'steps':[{'name':'inspect','operation':'inspect','desc':'Read page','on':{'success':'done','failed':'failed'}}]}]}
    draft=client.post(base+'/agent-drafts',json={'name':'Reader','site_scope':source['site_scope'],'source':source}).json()
    compiled=client.post(base+'/agent-drafts/'+draft['id']+'/compile');assert compiled.status_code==200,compiled.text
    generation=compiled.json()
    assert client.post(base+'/agent-drafts/'+draft['id']+'/generations/'+generation['id']+'/activate').status_code==200
    assert client.post(base+'/browser-workspace/domains',json={'domain':'https://Example.com/'}).json()['domain']=='example.com'
    assert client.get(base+'/browser-workspace').json()['domain_icons']['example.com']=='data:image/png;base64,test'
    for value in ['https://u:p@example.com','https://example.com/path','https://example.com:443']:
        assert client.post(base+'/browser-workspace/domains',json={'domain':value}).status_code==422
    payload={'profile_key':'default','agent_id':draft['id'],'capability':'site.read','name':'Read','input':{'count':1}}
    assert client.post(base+'/browser-workspace/tasks',json={**payload,'input':{'count':'wrong'}}).status_code==422
    response=client.post(base+'/browser-workspace/tasks',json=payload);assert response.status_code==201,response.text
    task=response.json();assert task['generation_id']==generation['id']
    worker='worker-1234567890'
    admission=client.post(base+'/browser-workspace/claim',json={'worker':worker}).json()
    assert admission == {'task': None, 'execution_owner': 'local'}
    assert client.post(base+'/browser-workspace/tasks/'+task['id']+'/start',json={'worker':worker,'browser_context':{'bidi_context':'tab'}}).status_code==409
    runtime.background_browser_runner.dispatch_queue()
    started=client.get(base+'/browser-workspace').json()['tasks'][0]
    run_id=started['run_id'];assert run_id
    run=runtime.agents.get_run(run_id)
    assert run.input['parameters']['execution_owner']=='local'
    assert run.input['parameters']['browser_context']=={'profile_key':'default'}
    assert run.session_id==task['session_id']
    assert len(client.get(base+'/browser-workspace').json()['tasks'])==1
    assert client.post(base+'/browser-workspace/tasks/'+task['id']+'/cancel').json()['status']=='cancelled'
    assert client.get(base+'/browser-workspace').status_code==200
    assert client.post(base+'/browser-workspace/tasks/not-owned/cancel').status_code==404
    # Legacy single-capability Agents expose a canonical catalog fallback.
    legacy=client.post(base+'/agent-drafts',json={'name':'Legacy','site_scope':['https://example.com/**'],'source':{'site_scope':['https://example.com/**'],'steps':[{'name':'inspect','operation':'inspect','desc':'Read page','on':{'success':'done','failed':'failed'}}]}}).json()
    legacy_generation=client.post(base+'/agent-drafts/'+legacy['id']+'/compile').json()
    assert client.post(base+'/agent-drafts/'+legacy['id']+'/generations/'+legacy_generation['id']+'/activate').status_code==200
    capability=next(c for c in client.get(base+'/agent-capabilities').json()['items'] if c['agent_id']==legacy['id'])
    legacy_task=client.post(base+'/browser-workspace/tasks',json={'profile_key':'default','agent_id':legacy['id'],'capability':capability['name'],'name':'Legacy','input':{}}).json()
    runtime.background_browser_runner.dispatch_queue()
    legacy_started=next(t for t in client.get(base+'/browser-workspace').json()['tasks'] if t['id']==legacy_task['id'])
    assert legacy_started['run_id']
    client.post(base+'/browser-workspace/tasks/'+legacy_task['id']+'/cancel')
    runtime.stop()

def test_profile_bootstrap_binding_contains_no_browser_control_commands():
    from ai2apps.browser.shell_window import ShellBrowserWindowBroker
    broker=ShellBrowserWindowBroker()
    request=broker.enqueue(action='bind',profile_key='a'*64,profile_name='Work',is_default=False)
    assert broker.claim_next()['action']=='bind'
    broker.finish(request,status='bound',pid=100,user_context='opaque-bidi-user-context')
    result=broker.wait(request)
    assert result=={'status':'bound','pid':100,'user_context':'opaque-bidi-user-context'}


def test_active_tasks_are_not_hidden_by_recent_history(tasks):
    active = enqueue(tasks)
    for _ in range(201):
        task = enqueue(tasks)
        tasks.update('owner', task['id'], status='completed')
    result = tasks.list('owner')
    assert active['id'] in {task['id'] for task in result}
    assert len(result) == 201

def test_domain_survives_last_agent_and_requires_explicit_empty_domain_deletion(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.identity import RequestPrincipal,MemberRole
    runtime=PlatformRuntime(PlatformConfig.from_base_path(tmp_path));runtime.start()
    principal=RequestPrincipal(actor_user_id='owner',installation_id='install',organization_id='org',billing_account_id='billing',role=MemberRole.MEMBER,membership_epoch=1)
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=lambda:principal));client=TestClient(app)
    base='/v1/platform'
    try:
        recipe=runtime.agent_builder.create_recipe(owner_user_id='owner',name='Read',description='List',source={'site_scope':['https://example.com/**'],'steps':[]})
        assert 'example.com' in client.get(base+'/browser-workspace').json()['domains']
        assert client.delete(base+'/browser-workspace/domains/example.com').status_code==409
        runtime.agent_builder.archive_recipe(recipe.id,'owner',expected_revision=recipe.revision)
        assert 'example.com' in client.get(base+'/browser-workspace').json()['domains']
        assert client.delete(base+'/browser-workspace/domains/example.com').status_code==200
        assert 'example.com' not in client.get(base+'/browser-workspace').json()['domains']
        assert 'example.com' not in client.get(base+'/browser-workspace').json()['domains']
    finally:
        runtime.stop()


def test_domain_execution_mode_is_persistent_validated_and_owner_bound(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.identity import RequestPrincipal, MemberRole
    monkeypatch.setattr('ai2apps.browser.site_icons.discover_site_icon', lambda domain: '')
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path)); runtime.start()
    principal = RequestPrincipal(actor_user_id='owner', installation_id='install', organization_id='org', billing_account_id='billing', role=MemberRole.MEMBER, membership_epoch=1)
    app = FastAPI(); app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=lambda: principal))
    client = TestClient(app); base = '/v1/platform/browser-workspace'
    try:
        assert client.post(base+'/domains', json={'domain':'example.com'}).status_code == 201
        path=base+'/domains/example.com/settings'
        assert client.get(path).json()['interaction_mode']=='natural'
        assert client.put(path,json={'interaction_mode':'fast'}).status_code==200
        assert client.get(path).json()['interaction_mode']=='fast'
        assert client.get(base).json()['domain_settings']['example.com']['interaction_mode']=='fast'
        assert client.put(path,json={'interaction_mode':'invalid'}).status_code==422
        with runtime.database.transaction(write=True) as c:
            c.execute("INSERT INTO browser_domains(owner,domain,interaction_mode) VALUES('other','foreign.com','fast')")
        assert client.get(base+'/domains/foreign.com/settings').json()['interaction_mode']=='natural'
        assert client.put(base+'/domains/foreign.com/settings',json={'interaction_mode':'natural'}).status_code==404
    finally:
        runtime.stop()


def test_cancelled_task_cannot_be_resurrected_by_late_browser_failure(tasks):
    task=enqueue(tasks)
    tasks.update('owner',task['id'],status='cancelled')
    result=tasks.update('owner',task['id'],status='interrupted',message='Late error')
    assert result['status']=='cancelled'
