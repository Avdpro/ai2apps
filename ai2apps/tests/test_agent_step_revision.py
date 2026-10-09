import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from ai2apps.api.router import create_ai2apps_router
from ai2apps.config import PlatformConfig
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.identity import RequestPrincipal, MemberRole


@pytest.mark.parametrize('capabilities', [False, True])
def test_step_conversation_repairs_and_does_not_save_or_change_other_steps(tmp_path, capabilities):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path)); runtime.start()
    runtime.model_manager = SimpleNamespace(resolve_default_model=lambda _: 'edit-model')
    runtime.model_invocations = SimpleNamespace(model=lambda _: None)
    principal = RequestPrincipal(actor_user_id='owner', installation_id='install',
        organization_id='org', billing_account_id='billing', role=MemberRole.MEMBER, membership_epoch=1)
    app = FastAPI(); app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime, principal_provider=lambda:principal))
    steps = [{'name':'read','operation':'inspect','desc':'Read page','on':{'success':'next','failed':'failed'}},
             {'name':'next','operation':'inspect','desc':'Second step','on':{'success':'done','failed':'failed'}}]
    source = {'name':'Test', 'site_scope':['https://example.com/**'],'steps':steps}
    if capabilities:
        source.pop('steps'); source['capabilities']=[{'id':'read-page','name':'read','steps':steps}]
    seen = []
    @app.post('/v1/chat/completions')
    async def completion(request:Request):
        seen.append(await request.json())
        if len(seen)==1:
            content="{'invalid':true}"
        elif len(seen)==2:
            content=json.dumps({'step':{**steps[0], 'name':'renamed'}, 'message':'Wrong name'})
        else:
            content=json.dumps({'step':{**steps[0], 'desc':'Read the title'},'message':'仅调整读取目标'})
        return {'choices':[{'message':{'content':content}}]}
    client=TestClient(app,base_url='http://127.0.0.1:62122')
    before=json.dumps(source)
    response=client.post('/v1/platform/agent-steps/revisions',json={'source':source,
        'capability_id':'read-page' if capabilities else None,'step_index':0,'feedback':'改为读取标题',
        'messages':[{'role':'user','content':'保留原来的跳转'}]})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['step']['name']=='read'
    assert result['step']['desc']=='Read the title'
    assert result['step']['on']==steps[0]['on']
    assert result['json_repairs']==2
    assert json.dumps(source)==before
    assert len(seen)==3
    assert '保留原来的跳转' in json.dumps(seen[0],ensure_ascii=False)
    assert client.get('/v1/platform/agent-drafts').json()['items']==[]
    invalid=client.post('/v1/platform/agent-steps/revisions',json={'source':source,'step_index':99,'feedback':'test'})
    assert invalid.status_code==422
    assert len(seen)==3
