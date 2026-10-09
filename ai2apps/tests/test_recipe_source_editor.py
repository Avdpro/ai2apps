from dataclasses import dataclass, replace
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ai2apps.api.agent_platform import create_agent_platform_router, ResourceConflictError
from ai2apps.identity import MemberRole, RequestPrincipal

@dataclass
class Recipe:
    id: str
    source: dict
    status: str = 'tested'
    revision: int = 1

class Store:
    recipe = Recipe('recipe', {})
    def revise_recipe(self, recipe_id, owner, *, expected_revision, source, status):
        assert recipe_id == 'recipe' and owner == 'editor-user'
        if expected_revision != self.recipe.revision:
            raise ResourceConflictError('Recipe revision changed')
        self.recipe = replace(self.recipe, source=source, status=status, revision=expected_revision+1)
        return self.recipe

def test_recipe_editor_preserves_inputs_variables_graph_and_invalidates_approval():
    store = Store()
    principal = RequestPrincipal(actor_user_id='editor-user', installation_id='editor-install',
        organization_id='org', billing_account_id='billing', role=MemberRole.OWNER, membership_epoch=1)
    runtime = SimpleNamespace(agent_builder=store, agents=object(), agent_runtime=object())
    app = FastAPI()
    app.include_router(create_agent_platform_router(lambda: runtime, lambda: principal))
    client = TestClient(app)
    source = {'name':'Loop', 'site_scope':['https://example.com/**'],
        'inputs':{'type':'object','properties':{'query':{'type':'string','default':'watch'}}},
        'variables':{'type':'object','properties':{'index':{'type':'integer','default':0}}},
        'steps':[{'name':'check','operation':'condition','arguments':{'expression':'vars.index < 2'},
            'on':{'true':'increment','false':'done','failed':'failed'}},
            {'name':'increment','operation':'assign','arguments':{'assignments':[{'variable':'index','expression':'vars.index + 1'}]},
                'on':{'success':'check','failed':'failed'}}]}
    response = client.patch('/agent-recipes/recipe/source', json={'expected_revision':1,'source':source})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['review']['compiler']['valid'], result
    assert result['review']['status'] == 'awaiting_review'
    assert result['recipe']['source'] == source
    assert result['recipe']['revision'] == 2
    assert client.patch('/agent-recipes/recipe/source', json={'expected_revision':1,'source':source}).status_code == 409
    source['steps'][0]['on']['true'] = 'missing'
    response = client.patch('/agent-recipes/recipe/source', json={'expected_revision':2,'source':source})
    assert response.status_code == 200
    assert not response.json()['review']['compiler']['valid']

def test_recipe_run_admission_conflict_returns_explanatory_error(monkeypatch):
    from ai2apps.api import agent_platform
    source = {'name':'Read','site_scope':['https://example.com/**'],
        'steps':[{'name':'open','operation':'open','arguments':{'url':'https://example.com'},'on':{'success':'done','failed':'failed'}}]}
    recipe = SimpleNamespace(id='recipe',source=source,page={})
    store = SimpleNamespace(get_recipe=lambda *args: recipe)
    runtime = SimpleNamespace(agent_builder=store,agents=object(),agent_runtime=object())
    principal = RequestPrincipal(actor_user_id='editor-user',installation_id='editor-install',
        organization_id='org',billing_account_id='billing',role=MemberRole.OWNER,membership_epoch=1)
    monkeypatch.setattr(agent_platform,'_session',lambda *args:'session')
    def conflict(*args,**kwargs):
        raise ValueError('WebAgent 并发名额已满，请取消现有任务。')
    monkeypatch.setattr(agent_platform,'create_ir_run',conflict)
    app=FastAPI();app.include_router(create_agent_platform_router(lambda:runtime,lambda:principal))
    response=TestClient(app).post('/agent-recipes/recipe/runs',json={'input':{}})
    assert response.status_code==409,response.text
    assert '并发名额已满' in response.text
    assert response.json()['error']['code']=='agent_recipe_run_conflict'
