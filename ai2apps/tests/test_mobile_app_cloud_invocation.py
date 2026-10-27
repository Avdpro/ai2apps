"""Cloud App calls are independent of Mobile ASGI model routes."""
import json
import types
from types import SimpleNamespace as NS
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from ai2apps.identity import RequestPrincipal
from ai2apps.model_invocation import invoke_app_cloud_chat,ModelInvocationError


def setup(text):
    calls=[]
    async def invoke(payload,*,context):
        calls.append((payload,context))
        return {'choices':[{'finish_reason':'stop','message':{'content':text}}]}
    return NS(model_manager=NS(resolve_default_model=lambda *a,**kw:'cloud/openai/test'),
              model_invocations=NS(model=lambda _:None,invoke_agent_cloud_json=invoke)),calls


@pytest.mark.asyncio
async def test_cloud_identity_mount_and_failure():
    runtime,calls=setup('ok');p=RequestPrincipal.legacy_local()
    await invoke_app_cloud_chat(runtime,{'model':'cloud/openai/test','stream':True},principal=p,session_id='s',consumer_app_id='mini.test',app_instance_id='instance-test')
    payload,context=calls[0]
    assert payload['stream'] is False and context.actor_user_id==p.actor_user_id
    assert context.installation_id==p.installation_id and context.membership_epoch==p.membership_epoch
    assert context.app_instance_id=='instance-test' and context.consumer_app_id=='mini.test'
    async def fail(*a,**kw):raise ModelInvocationError('agent_cloud_model_failed','Cloud model returned HTTP 503')
    runtime.model_invocations.invoke_agent_cloud_json=fail
    with pytest.raises(HTTPException) as error:
        await invoke_app_cloud_chat(runtime,{'model':'cloud/openai/test'},principal=p,session_id='s',consumer_app_id='mini.test')
    assert error.value.status_code==502 and error.value.detail['code']=='agent_cloud_model_failed'


@pytest.mark.asyncio
async def test_todo_emoji_without_request_app():
    from ai2apps.api.todo import generate_task_emoji,EmojiRequest
    runtime,calls=setup('🎬')
    result=await generate_task_emoji(runtime,NS(recent_emojis=lambda *a:[]),RequestPrincipal.legacy_local(),None,EmojiRequest(title='Video',description='Subtitles'))
    assert result=={'emoji':'🎬'} and calls[0][1].consumer_app_id=='ai2apps.todo'


@pytest.mark.asyncio
async def test_studio_mini_app_mount_without_request_app():
    from ai2apps.studio.capability_broker import StudioCapabilityBroker
    runtime,calls=setup('Translated text');broker=object.__new__(StudioCapabilityBroker);broker.runtime=runtime
    mounted=NS(mount={'id':'mount1','app_instance_id':'instance1'},declaration={'id':'mini.translation'})
    result=await broker._task_completion('Translate',system='Translator',principal=RequestPrincipal.legacy_local(),mounted=mounted,request=None)
    assert result=='Translated text'
    context=calls[0][1]
    assert context.consumer_app_id=='mini.translation' and context.app_instance_id=='instance1'
    assert context.session_id.startswith('studio-mini-app:mount1:')


@pytest.mark.asyncio
async def test_agent_presentation_without_request_app():
    from ai2apps.api.agent_platform import _create_presentation_for_result
    spec={'version':1,'view':'table','data_path':'$.items','fields':[{'path':'title','label':'Title'}]}
    runtime,calls=setup(json.dumps(spec))
    result=await _create_presentation_for_result(runtime=runtime,principal=RequestPrincipal.legacy_local(),http_request=None,result={'items':[{'title':'Result'}]},locale='en',request_id='test',session_id='s')
    assert result['presentation']['view']=='table' and calls[0][1].consumer_app_id=='ai2apps.agents'


@pytest.mark.asyncio
async def test_agent_compiler_without_request_app():
    import ai2apps.api.agent_platform as module
    def find(code):
        for child in code.co_consts:
            if isinstance(child,types.CodeType):
                if child.co_name=='_invoke_compile_model_raw':return child
                found=find(child)
                if found:return found
    code=find(module.create_agent_platform_router.__code__)
    assert code and not code.co_freevars
    invoke=types.FunctionType(code,module.__dict__);runtime,calls=setup('{"compiled":true}')
    result=await invoke(runtime,None,RequestPrincipal.legacy_local(),model_id='cloud/openai/test',payload={'model':'cloud/openai/test'},request_id='compile-test',session_id='s')
    assert result['choices'] and calls[0][1].session_id=='s'


def test_visitor_html_ai_with_isolated_router(tmp_path):
    from ai2apps.storage import PlatformDatabase
    from ai2apps.api.remote import create_remote_router
    from ai2apps.remote.visitor_assets import VisitorAssets
    runtime,calls=setup('<!doctype html><html><body>Stars</body></html>')
    runtime.database=PlatformDatabase(tmp_path/'db.sqlite');runtime.database.initialize()
    p=RequestPrincipal.legacy_local();app=FastAPI();app.include_router(create_remote_router(lambda:runtime,lambda:p))
    with TestClient(app) as client:
        response=client.post('/remote/visitor-space/html-ai',json={'prompt':'Stars'})
        assert response.status_code==200,response.text
        meta,path=VisitorAssets(runtime.database,p.installation_id).get(response.json()['asset']['id'])
        assert b'Stars' in path.read_bytes() and calls[0][1].consumer_app_id=='ai2apps.remote'
