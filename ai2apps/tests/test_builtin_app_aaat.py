"""Behavioral first-party AaAT contracts; model calls are fixtures, not live claims."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import io
import json
from types import SimpleNamespace
import pytest
from jsonschema import Draft202012Validator
from ai2apps.agents.builtin_apps import todo_store, gallery
from ai2apps.intelligence.aaat import store as intel_store
from ai2apps.agents.parameter_forms import resolve_form
from ai2apps.chat import ChatRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.services import ToolCallContext
from test_app_interactions import runtime


def context(runtime):
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='App adapters')
    return ToolCallContext.from_principal(RequestPrincipal.legacy_local(),caller_id='ai2apps.general-chat',session_id=thread.session.id,trace_id='test-run')


def test_catalog_all_requested_hosts_and_forms(runtime):
    catalog=runtime.app_capability_router.catalog()
    for app in ('ai2apps.todo','ai2apps.intelligence','ai2apps.readaloud','ai2apps.gallery','ai2apps.knowledge'):
        entries=[x for x in catalog if x['app_id']==app]
        assert entries and all(x['display_name'] and x['summary'] for x in entries)
    assert resolve_form({'capability':'voice.transcribe'}).key=='voice.transcribe'
    assert resolve_form({'capability':'voice.quick_read'}).mini_app_id=='ai2apps.audio.quick-read'
    assert resolve_form({'capability':'shopping.history'}).mini_app_id=='ai2apps.shopping-pro'


@pytest.mark.asyncio
async def test_todo_create_search_replay_conflict_and_owned_directory(runtime):
    ctx=replace(context(runtime),invocation_id='create-1')
    store=todo_store(runtime);directory=store.directory('local','Work')
    args={'title':'AaAT task','directory_id':directory['id']};invoke=runtime.app_capability_router.invoke
    a=await invoke('todo.create',args,ctx);b=await invoke('todo.create',args,ctx)
    assert a['task']['id']==b['task']['id'] and len(store.snapshot('local')['tasks'])==1
    with pytest.raises(Exception,match='different parameters'):await invoke('todo.create',{**args,'title':'changed'},ctx)
    foreign=store.directory('other','Private')
    with pytest.raises(Exception,match='Directory not found'):
        await invoke('todo.create',{**args,'directory_id':foreign['id']},replace(ctx,invocation_id='create-2'))
    result=await invoke('todo.search',{'query':'AaAT'},ctx)
    assert result['total']==1 and result['tasks'][0]['id']==a['task']['id']
    with pytest.raises(Exception):await invoke('todo.search',{},replace(ctx,session_id='foreign-session'))
    with pytest.raises(Exception,match='Installation mismatch'):await invoke('todo.search',{},replace(ctx,installation_id='foreign-installation'))


def test_todo_creation_receipt_atomic_concurrency_and_restart(runtime):
    store=todo_store(runtime);directory=store.directory('local','Work');args={'title':'Concurrent','directory_id':directory['id']}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:todo_store(runtime).save('local',args,creation_key='shared'),range(8)))
    assert len({r['id'] for r in results})==1
    assert todo_store(runtime).save('local',args,creation_key='shared')['id']==results[0]['id']
    assert len(store.snapshot('local')['tasks'])==1


@pytest.mark.asyncio
async def test_intelligence_and_gallery_owner_scoping(runtime):
    ctx=context(runtime);invoke=runtime.app_capability_router.invoke;store=intel_store(runtime)
    from ai2apps.intelligence.models import ChannelInput
    owned=store.save_channel('local',ChannelInput(name='Local',interests='AI').model_dump());store.save_channel('other',ChannelInput(name='Private',interests='Secret').model_dump())
    result=await invoke('intelligence.channels',{},ctx)
    assert [x['id'] for x in result['channels']]==[owned['id']]
    repo=gallery(runtime)
    own,_=repo.import_stream('local',io.BytesIO(b'hello'),name='recipe.txt',media_type='text/plain')
    foreign,_=repo.import_stream('other',io.BytesIO(b'secret'),name='recipe.txt',media_type='text/plain')
    result=await invoke('gallery.search',{'query':'recipe'},ctx)
    assert [a['id'] for a in result['assets']]==[own['id']] and 'locator' not in json.dumps(result)
    with pytest.raises(Exception):await invoke('gallery.get',{'asset_id':foreign['id']},ctx)


@pytest.mark.asyncio
async def test_knowledge_facade_preserves_acl_and_citation(runtime):
    ctx=context(runtime);invoke=runtime.app_capability_router.invoke
    item=await invoke('knowledge.add_text',{'title':'Recipe','text':'Twice cooked pork with garlic sprouts'},ctx)
    assert item['app_id']=='ai2apps.knowledge'
    tool=runtime.services.get_tool('knowledge.add_text')
    assert 'knowledge.write' in tool.required_capabilities and 'write' in tool.effects
    Draft202012Validator(tool.input_schema).validate({'title':'x','text':'y','provider':item['provider']})
    result=await invoke('knowledge.search',{'query':'pork'},ctx)
    assert result['app_id']=='ai2apps.knowledge' and result['items'][0]['item']['citation']['uri'].startswith('knowledge://')


@pytest.mark.asyncio
async def test_shopping_form_uses_installed_schema_and_broker(runtime,monkeypatch):
    ctx=replace(context(runtime),invocation_id='shopping-1');seen=[]
    declaration={'web_agent':{'capabilities':[{'id':'history','source':{'inputs':{'type':'object','properties':{'pages':{'type':'integer','minimum':1,'maximum':6}},'required':['pages'],'additionalProperties':False}}}]}}
    monkeypatch.setattr(runtime.extension_manager,'_studio_mini_app_definition',lambda *a:(None,declaration))
    from ai2apps.browser.mini_apps import WebAgentMiniAppBroker
    monkeypatch.setattr(WebAgentMiniAppBroker,'registered',lambda *a:SimpleNamespace(declaration={'id':'ai2apps.shopping-pro'}))
    def submit(self,mounted,principal,**kwargs):seen.append(kwargs);return {'id':'task-broker-contract'}
    monkeypatch.setattr(WebAgentMiniAppBroker,'submit_declared',submit)
    monkeypatch.setattr(WebAgentMiniAppBroker,'task_declared',lambda *a:{'id':'task-broker-contract','status':'completed','result':{'items':[]}})
    result=await runtime.app_capability_router.invoke('shopping.history',{'pages':2,'profile':'default'},ctx)
    assert result['browser_task_id']=='task-broker-contract'
    assert seen[0]['parameters']=={'pages':2} and seen[0]['profile']=='default'
    with pytest.raises(Exception):await runtime.app_capability_router.invoke('shopping.history',{'pages':7},ctx)
    assert len(seen)==1


@pytest.mark.asyncio
async def test_quick_read_uses_host_job_and_exact_invocation_key(runtime,monkeypatch):
    monkeypatch.setattr('ai2apps.model_providers.list_package_models',lambda *a:[SimpleNamespace(id='tts-model',model_type='audio_tts',display_name='Fixture TTS',checkpoint_ready=True)])
    ctx=replace(context(runtime),invocation_id='quick-read-test');seen=[]
    monkeypatch.setattr(runtime.extension_manager,'launch_app',lambda *a,**k:(SimpleNamespace(id='voice-instance'),None,False))
    def submit(**kw):
        seen.append(kw);return {'id':'job-q','status':'succeeded','result':{'downloadUrl':'/shared/voice/output'}}
    monkeypatch.setattr(runtime.studio_jobs,'submit',submit)
    result=await runtime.app_capability_router.invoke('voice.quick_read',{'text':'朗读测试','model_id':'tts-model'},ctx)
    assert result['downloadUrl']=='/shared/voice/output' and result['mini_app_id']=='ai2apps.audio.quick-read'
    assert seen[0]['kind']=='quick-read' and seen[0]['key']=='aaat:quick-read-test'
    assert seen[0]['payload']['model_id']=='tts-model' and seen[0]['studio_id']=='ai2apps.readaloud'


@pytest.mark.asyncio
async def test_detailed_transcription_installed_identity_scoped_input_and_shared_output(runtime,monkeypatch,tmp_path):
    ctx=replace(context(runtime),invocation_id='transcript-test');seen=[]
    monkeypatch.setattr('ai2apps.studio.capability_broker.StudioCapabilityBroker._detailed_model_for_profile',lambda *a:SimpleNamespace(id='declared-fixture-model'))
    path=tmp_path/'input.wav';path.write_bytes(b'fixture-audio')
    audio=runtime.workspace.import_artifact(ctx.session_id,path,name='input.wav',media_type='audio/wav')
    session=runtime.readaloud_tasks._artifact_session('local')
    output=runtime.readaloud_tasks.save_studio_output('local',json.dumps({'segments':[{'start':0,'end':2,'text':'test caption'}]}).encode(),
        mini_app_id='ai2apps.media-voice.transcription',filename='transcript.json',media_type='application/json')
    decl={'id':'ai2apps.media-voice.transcription','version':'1','requirements':{'capabilities':['audio.detailed_transcription']}}
    monkeypatch.setattr(runtime.extension_manager,'_studio_mini_app_definition',lambda *a:({'package_id':'installed-suite'},decl))
    monkeypatch.setattr(runtime.extension_manager,'launch_app',lambda app,**k:(SimpleNamespace(id=app+'-instance'),None,False))
    def submit(runtime,principal,mounted,capability,options,content,filename,media_type,**kw):
        seen.append((mounted,capability,options,content,kw));return {'id':'job-t','run_id':'studio-r','status':'succeeded','result':{'downloadUrl':output}}
    monkeypatch.setattr('ai2apps.studio.video_jobs.submit_package',submit)
    result=await runtime.app_capability_router.invoke('voice.detailed_transcription',{'audio_artifact_id':audio.id},ctx)
    assert 'test caption' in result['text'] and result['mini_app_id']=='ai2apps.media-voice.transcription'
    assert seen[0][0].declaration==decl and seen[0][1]=='audio.detailed_transcription'
    assert seen[0][2]['word_timestamps'] and seen[0][2]['diarization']
    assert seen[0][3]==b'fixture-audio' and seen[0][4]['key']=='aaat:transcript-test'
    assert any(x['miniAppId']=='ai2apps.media-voice.transcription' for x in runtime.readaloud_tasks.output_history('local'))
    other=replace(ctx,session_id=context(runtime).session_id)
    with pytest.raises(Exception):await runtime.app_capability_router.invoke('voice.detailed_transcription',{'audio_artifact_id':audio.id},other)
    assert len(seen)==1

@pytest.mark.asyncio
@pytest.mark.parametrize('capability',['todo.create','knowledge.add_text'])
async def test_common_app_schema_is_preflight_before_any_business_handler(runtime,capability):
    from unittest.mock import AsyncMock
    from ai2apps.services.capability_routing import CapabilityInvocationError
    router=runtime.app_capability_router
    provider=next(p for p in router.providers.values() if p.capability==capability)
    handler=AsyncMock(return_value={'ok':True})
    router.providers[provider.id]=replace(provider,handler=handler)
    assert provider.prepare is not None
    with pytest.raises(CapabilityInvocationError) as caught:
        await router.invoke(capability,{},context(runtime))
    assert caught.value.code=='invalid_tool_arguments'
    assert caught.value.details['phase']=='prepare'
    handler.assert_not_awaited()
