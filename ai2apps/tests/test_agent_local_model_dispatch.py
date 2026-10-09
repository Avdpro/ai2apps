import pytest
from types import SimpleNamespace
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from ai2apps.api.router import create_ai2apps_router
from ai2apps.config import PlatformConfig
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.identity import RequestPrincipal, MemberRole
from ai2apps.web.public_boundary import PublicDeviceBoundary


@pytest.mark.parametrize('malformed_first', [False, True])
@pytest.mark.parametrize('goal', ['读取当前页面作者、摘要和链接', '打开 https://example.com，读取作者、摘要和链接', '读取所有页面的文章列表，随后总结'])
def test_exploration_fallback_retains_local_host_boundary(tmp_path, malformed_first, goal):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    runtime.model_manager = SimpleNamespace(resolve_default_model=lambda _: 'fallback-model')
    runtime.model_invocations = SimpleNamespace(model=lambda _: None)
    principal = RequestPrincipal(actor_user_id='test-owner', installation_id='test-installation',
        organization_id='test-org', billing_account_id='test-billing', role=MemberRole.MEMBER, membership_epoch=1)
    app = FastAPI()
    app.add_middleware(PublicDeviceBoundary, manager_provider=lambda: None)
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=lambda: principal))
    seen = []
    @app.post('/v1/chat/completions')
    async def completion(request: Request):
        seen.append(request.url.hostname)
        if malformed_first and len(seen) == 1:
            return {'choices':[{'message':{'content':"{'decision': 'act'}"}}]}
        return {'choices':[{'message':{'content':'{"decision":"act","reason":"Read the page","step":{"name":"read","operation":"inspect","on":{"success":"done","failed":"failed"}}}'}}]}
    client = TestClient(app, base_url='http://127.0.0.1:62122')
    response = client.post('/v1/platform/agent-explorations/next', json={
        'goal':goal,'name':'test','verify_goal_with_ai':False,'page':{'url':'https://example.com','title':'Example'},
        'observation':{'text':'Requested content'},'attempts':[{'outcome':'success','compiled_step':{'operation':'extract_list'},'evidence':{'result':{'items':[{'author':'','summary':'','url':'https://example.com/unrelated'}]}}}]})
    assert response.status_code == 200, response.text
    assert seen == ['127.0.0.1'] * (2 if malformed_first else 1)
    assert client.post('http://untrusted.example/v1/chat/completions',json={}).status_code == 403


@pytest.mark.parametrize('endpoint', ['agent-recipes', 'agent-explorations/next', 'review'])
@pytest.mark.parametrize('exhausted', [False, True])
def test_format_and_schema_share_two_repairs(tmp_path, endpoint, exhausted):
    import json
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    runtime.model_manager = SimpleNamespace(resolve_default_model=lambda _: 'deepseek-test')
    runtime.model_invocations = SimpleNamespace(model=lambda _: None)
    principal = RequestPrincipal(actor_user_id='test-owner', installation_id='test-installation',
        organization_id='test-org', billing_account_id='test-billing', role=MemberRole.MEMBER, membership_epoch=1)
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=lambda: principal))
    seen = []
    valid_step = {'name':'read', 'operation':'inspect', 'on':{'success':'done','failed':'failed'}}
    valid = {'steps':[valid_step]} if endpoint in {'agent-recipes', 'review'} else {'decision':'act','step':valid_step}
    @app.post('/v1/chat/completions')
    async def completion(request: Request):
        payload = await request.json()
        seen.append(payload)
        if payload['messages'][0]['content'].startswith('Name a browser Agent capability'):
            return {'choices':[{'message':{'content':json.dumps({'title':'Read page','description':'Read the current page.'})}}]}
        if len(seen) == 1:
            return {'choices':[{'message':{'content':"{'broken': true}"}}]}
        if exhausted or len(seen) == 2:
            return {'choices':[{'message':{'content':'[]'}}]}
        return {'choices':[{'message':{'content':json.dumps(valid)}}]}
    client = TestClient(app, base_url='http://127.0.0.1:62122')
    if endpoint == 'review':
        runtime.model_manager = SimpleNamespace(resolve_default_model=lambda _: None)
        created = client.post('/v1/platform/agent-recipes', json={'name':'test','prompt':'Read the page','page':{'url':'https://example.com'}})
        assert created.status_code == 201, created.text
        recipe = created.json()
        runtime.model_manager = SimpleNamespace(resolve_default_model=lambda _: 'deepseek-test')
    body = {'name':'test','page':{'url':'https://example.com'}}
    if endpoint == 'agent-recipes':
        body['prompt'] = 'Read the page'
    else:
        body.update(goal='Read the page', verify_goal_with_ai=True, allow_model_escalation=False)
    if endpoint == 'review':
        body = {'expected_revision': recipe['revision'], 'feedback':'Read the page'}
        target = 'agent-recipes/'+recipe['id']+'/review/revisions'
    else:
        target = endpoint
    response = client.post('/v1/platform/'+target, json=body)
    assert len(seen) == (4 if endpoint == 'agent-recipes' and not exhausted else 3)
    if endpoint == 'agent-recipes' and not exhausted:
        assert seen[-1]['max_tokens'] == 300  # Separate capability naming, not a third repair.
    assert all(item['model'] == 'deepseek-test' for item in seen)
    assert 'broken' in seen[1]['messages'][-2]['content']
    assert response.status_code == (422 if exhausted else (201 if endpoint == 'agent-recipes' else 200)), response.text


def test_repeated_foundation_read_is_goal_verified_before_execution(tmp_path):
    import json
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    runtime.model_manager = SimpleNamespace(resolve_default_model=lambda _: 'test-model')
    runtime.model_invocations = SimpleNamespace(model=lambda _: None)
    principal = RequestPrincipal(actor_user_id='test-owner', installation_id='test-installation',
        organization_id='test-org', billing_account_id='test-billing', role=MemberRole.MEMBER, membership_epoch=1)
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=lambda: principal))
    step = {'name': 'extract_current', 'operation': 'agent.call', 'arguments': {
        'agent_id': 'builtin:web:extract-list', 'capability': 'web.extract-list', 'parameters': {'limit': 50}}}
    seen = []
    @app.post('/v1/chat/completions')
    async def completion(request: Request):
        payload = await request.json()
        seen.append(payload)
        result = ({'decision': 'act', 'step': step, 'reason': 'Confirm current list despite prior success'}
                  if len(seen) == 1 else {'decision': 'complete', 'reason': 'Required title and url already returned'})
        return {'choices': [{'message': {'content': json.dumps(result)}}]}
    response = TestClient(app, base_url='http://127.0.0.1:62122').post(
        '/v1/platform/agent-explorations/next', json={
            'name': 'Articles', 'goal': '打开网站，读取文章列表，每项至少包含 title 和 url',
            'page': {'url': 'https://example.com/'}, 'observation': {},
            'attempts': [{'outcome': 'success', 'source_step': {**step, 'name': 'extract_first'},
                'evidence': {'result': {'page_url': 'https://example.com/', 'items': [
                    {'title': 'Article', 'url': 'https://example.com/a'}]}}}]})
    assert response.status_code == 200, response.text
    assert response.json()['decision'] == 'complete'
    assert len(seen) == 2
    assert 'changed DOM length/fingerprint' in seen[1]['messages'][0]['content']
