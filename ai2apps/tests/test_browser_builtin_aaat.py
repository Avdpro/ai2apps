"""Real registry/mount/queue contracts; inference and browser execution are fixtures."""
import pytest
from jsonschema import Draft202012Validator, ValidationError
from ai2apps.identity import RequestPrincipal
from ai2apps.browser.builtin_mini_apps import HOST
from ai2apps.browser.goal_aaat import program, SCHEMA, GoalTasks
from ai2apps.core import ResourceNotFoundError
from ai2apps.browser.tasks import BrowserTaskRepository
from ai2apps.services import ToolProviderError
from test_app_interactions import runtime


def test_fresh_install_has_both_builtin_frames_and_exact_asset_access(runtime):
    principal=RequestPrincipal.legacy_local();manager=runtime.extension_manager
    minis=manager.list_studio_mini_apps(HOST,principal=principal)
    assert {m['id'] for m in minis}=={'ai2apps.search-all','ai2apps.web-reader'}
    assert all(m['source']=='builtin' and m['provider']['appId']==HOST for m in minis)
    for mini in minis:
        mount=manager.mount_studio_mini_app(HOST,mini['id'],principal=principal)
        path=manager.resolve_app_resource(mount['app_instance_id'],mount['resource'],principal=principal)
        assert path.is_file() and '<html' in path.read_text().lower()
        with pytest.raises(ResourceNotFoundError):manager.resolve_app_resource(mount['app_instance_id'],'builtin_mini_apps/search-all/app.yaml',principal=principal)
        with pytest.raises(Exception):manager.resolve_app_resource(mount['app_instance_id'],'../secrets',principal=principal)
        from ai2apps.api.studio_mini_apps import _content_url
        assert mount['resource'] in _content_url(mount)
    providers=runtime.app_capability_router.providers
    assert providers['ai2apps.search-all.search'].priority>providers['ai2apps.web-research.search'].priority
    assert providers['ai2apps.web-reader.fetch'].priority>providers['ai2apps.web-research.fetch'].priority
    assert providers['ai2apps.ai-browser.browser.complete_goal'].mini_app_id is None
    assert not runtime.registry_packages._load_state().get('installed')


@pytest.mark.asyncio
async def test_builtin_contract_defaults_fast(runtime):
    provider=runtime.app_capability_router.providers['ai2apps.search-all.search']
    descriptor=await provider.describe(RequestPrincipal.legacy_local())
    assert descriptor['effective_schema']['properties']['mode']['default']=='fast'
    owner=runtime.app_chat.owners[HOST+'.chat']
    assert provider in owner.exports({'mini_app_id':provider.mini_app_id})
    assert not any(p.capability in ('browser.complete_goal','web.fetch') for p in owner.exports({'mini_app_id':provider.mini_app_id}))


@pytest.mark.parametrize('host',['arbitrary-one.test','unrelated-two.test'])
def test_goal_compiles_owned_readonly_program_and_explicit_visual(monkeypatch,host):
    monkeypatch.setattr('ai2apps.research.provider.SafeHttpClient._validate_url',lambda self,url:url)
    from ai2apps.agent_builder.compiler import compile_source
    args={'url':'https://'+host+'/','goal':'Inspect the page logo','visual':True}
    Draft202012Validator(SCHEMA).validate(args)
    source=program(args);compiled=compile_source(source)
    assert compiled.valid,compiled.report
    assert source['steps'][1]['arguments']['read_only'] is True
    assert source['steps'][-2]['arguments']=={'visual_goal':args['goal']}
    assert not program({**args,'visual':False})['steps'][-2]['arguments']
    with pytest.raises(ValidationError):Draft202012Validator(SCHEMA).validate({**args,'script':'forbidden'})


def test_goal_task_observer_rejects_foreign_caller_and_session(runtime):
    repo=BrowserTaskRepository(runtime.database)
    task=repo.enqueue('local','default','goal','','','fixture',{},session_id='s1',caller_app_id='foreign.owner')
    with pytest.raises(ToolProviderError):GoalTasks(runtime,'s1').task_declared(None,RequestPrincipal.legacy_local(),task['id'])
    task=repo.enqueue('local','default','goal','','','fixture',{},session_id='s2',caller_app_id=HOST)
    with pytest.raises(ToolProviderError):GoalTasks(runtime,'s1').task_declared(None,RequestPrincipal.legacy_local(),task['id'])


def test_agent_fast_form_skips_planning_and_preserves_user_query(runtime):
    from types import SimpleNamespace as NS
    from ai2apps.chat import ChatRepository
    from ai2apps.research.search_form import begin_form
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='fast preparation')
    principal=RequestPrincipal.legacy_local()
    result=begin_form(runtime,principal,NS(id='fixture-interaction'),NS(id='fixture-run',session_id=thread.session.id),
        {'query':'exact user query','mode':'fast'},1)
    assert result['status']=='completed' and result['query']=='exact user query' and result['task_id']==''
    assert not BrowserTaskRepository(runtime.database).list(principal.actor_user_id)


def test_general_goal_preserves_real_user_assistance_without_auto_approval(runtime,monkeypatch):
    from types import SimpleNamespace as NS
    from ai2apps.chat import ChatRepository
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='browser assistance')
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.general-agent',input={'prompt':'fixture','model':'fixture'})
    repo=BrowserTaskRepository(runtime.database)
    task=repo.enqueue('local','default','goal','','','fixture',{},session_id=thread.session.id,caller_app_id=HOST)
    repo.update('local',task['id'],run_id=run.id,status='waiting_input')
    monkeypatch.setattr(runtime.agents,'list_interactions',lambda _: [NS(id='pending-assistance',status=NS(value='pending'),request={'control':'browser_user_assistance','assistance_kind':'login'},prompt='Complete login in the original Profile')])
    result=GoalTasks(runtime,thread.session.id).task_declared(None,RequestPrincipal.legacy_local(),task['id'])
    assert result['requires_user'] and result['interaction_id']=='pending-assistance'
    assert result['assistance_kind']=='login'


def test_builtin_manifest_identity_is_stable_across_filesystem_enumeration(monkeypatch):
    from pathlib import Path
    from ai2apps.browser.builtin_mini_apps import definitions
    expected=definitions();original=Path.rglob
    monkeypatch.setattr(Path,'rglob',lambda self,*a,**kw:iter(reversed(list(original(self,*a,**kw)))))
    assert definitions()==expected
    assert expected[1]==sorted(expected[1])
