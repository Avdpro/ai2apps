import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from types import SimpleNamespace
from ai2apps.storage import PlatformDatabase
from ai2apps.agent_builder.repository import AgentBuilderRepository
from ai2apps.core import ResourceConflictError, ResourceNotFoundError
from ai2apps.api.agent_platform import create_agent_platform_router
from ai2apps.identity import MemberRole, RequestPrincipal


def test_recipe_archive_is_owner_scoped_revision_checked_and_removed_from_list(tmp_path):
    db=PlatformDatabase(tmp_path/'recipes.sqlite3');db.initialize()
    store=AgentBuilderRepository(db)
    recipe=store.create_recipe(owner_user_id='owner',name='List',description='List articles',
        source={'name':'List','site_scope':['https://example.com/**'],'steps':[]})
    with pytest.raises(ResourceNotFoundError):
        store.archive_recipe(recipe.id,'other',expected_revision=recipe.revision)
    with pytest.raises(ResourceConflictError):
        store.archive_recipe(recipe.id,'owner',expected_revision=recipe.revision+1)
    assert len(store.list_recipes('owner'))==1
    principal=RequestPrincipal(actor_user_id='owner',installation_id='install',organization_id='org',
        billing_account_id='billing',role=MemberRole.OWNER,membership_epoch=1)
    runtime=SimpleNamespace(agent_builder=store,agents=object(),agent_runtime=object())
    app=FastAPI();app.include_router(create_agent_platform_router(lambda:runtime,lambda:principal))
    response=TestClient(app).post('/agent-recipes/'+recipe.id+'/archive',json={'expected_revision':recipe.revision})
    assert response.status_code==200,response.text
    assert response.json()['recipe']['status']=='discarded'
    assert not store.list_recipes('owner')
    assert store.get_recipe(recipe.id,'owner').source==recipe.source
