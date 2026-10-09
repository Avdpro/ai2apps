from fastapi import FastAPI
from fastapi.testclient import TestClient
from ai2apps.api.agent_builder import create_agent_builder_router
from ai2apps.identity import MemberRole, RequestPrincipal


def client():
    principal = RequestPrincipal(actor_user_id='check-user', installation_id='check-install',
        organization_id='check-org', billing_account_id='check-billing', role=MemberRole.OWNER, membership_epoch=1)
    app = FastAPI()
    # No runtime exists: checking must never save a draft or create a browser run.
    app.include_router(create_agent_builder_router(lambda: None, lambda: principal), prefix='/v1/platform')
    return TestClient(app)


def test_source_check_needs_no_runtime_or_page():
    source = {'name':'Check', 'site_scope':['https://example.com/**'],
        'inputs':{'type':'object','properties':{'url':{'type':'string'}}},
        'steps':[{'name':'open','operation':'open','desc':'打开网址','arguments':{'url':'${input.url}'},'on':{'success':'read','failed':'failed'}},
            {'name':'read','operation':'read','desc':'读取页面','on':{'success':'done','failed':'failed'}}]}
    response = client().post('/v1/platform/agent-source/check',json={'source':source})
    assert response.status_code == 200
    assert response.json()['valid'] is True, response.text
    source['steps'][0]['on']['success'] = 'missing-step'
    response = client().post('/v1/platform/agent-source/check',json={'source':source})
    assert response.json()['valid'] is False
    assert response.json()['report']['errors']
