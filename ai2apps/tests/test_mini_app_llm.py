import asyncio
from types import SimpleNamespace
import pytest
from fastapi import FastAPI, Request
from pydantic import ValidationError
from ai2apps.api.studio_mini_apps import MiniAppLLMRequest
from ai2apps.studio.capability_broker import StudioCapabilityBroker, StudioCapabilityError

@pytest.mark.asyncio
@pytest.mark.parametrize('complexity', ['simple','standard','complex'])
@pytest.mark.parametrize('system_private,requested,declared,expected', [
 (False,'normal','normal','normal'),(False,'privacy','normal','privacy'),
 (True,'normal','normal','privacy'),(False,'normal','privacy','privacy')])
async def test_routes_and_privacy(monkeypatch,complexity,system_private,requested,declared,expected):
    resolutions=[];payloads=[];checks=[]
    def resolve(purpose,profile='normal'):
        resolutions.append((purpose,profile));return 'cloud/test/'+profile
    runtime=SimpleNamespace(extension_manager=None,model_manager=SimpleNamespace(resolve_default_model=resolve),privacy_mode=system_private)
    broker=StudioCapabilityBroker(runtime)
    mounted=SimpleNamespace(capabilities={'llm.text'},declaration={'llm':{'profile':declared}})
    monkeypatch.setattr(broker,'mounted_mini_app',lambda *a,**kw: checks.append(kw['principal']) or mounted)
    app=FastAPI()
    @app.post('/v1/chat/completions')
    async def complete(request:Request):
        payloads.append(await request.json());return {'choices':[{'message':{'content':'Answer'}}]}
    async def connected(): return False
    request=SimpleNamespace(app=app,headers={},is_disconnected=connected)
    result=await broker.llm_complete('studio','mount',principal='owner',request=request,
        prompt='Input',system='Instructions',complexity=complexity,profile=requested)
    assert resolutions==[('work_'+complexity,expected)]
    assert result=={'text':'Answer','complexity':complexity,'profile':expected}
    assert payloads[0]['messages'][1]['content']=='Input'
    assert checks==['owner','owner']

@pytest.mark.asyncio
async def test_privacy_missing_never_falls_back(monkeypatch):
    seen=[]
    def resolve(purpose,profile='normal'): seen.append(profile);return None
    broker=StudioCapabilityBroker(SimpleNamespace(extension_manager=None,model_manager=SimpleNamespace(resolve_default_model=resolve),privacy_mode=True))
    mounted=SimpleNamespace(capabilities={'llm.text'},declaration={})
    monkeypatch.setattr(broker,'mounted_mini_app',lambda *a,**kw: mounted)
    async def connected():return False
    with pytest.raises(StudioCapabilityError) as error:
        await broker.llm_complete('s','m',principal='owner',request=SimpleNamespace(is_disconnected=connected),prompt='text')
    assert error.value.status_code==409 and seen==['privacy']

@pytest.mark.asyncio
async def test_undeclared_capability_rejected(monkeypatch):
    broker=StudioCapabilityBroker(SimpleNamespace(extension_manager=None))
    monkeypatch.setattr(broker,'mounted_mini_app',lambda *a,**kw: SimpleNamespace(capabilities=set()))
    with pytest.raises(StudioCapabilityError) as error:
        await broker.llm_complete('s','m',principal='owner',request=None,prompt='text')
    assert error.value.status_code==403

@pytest.mark.asyncio
async def test_disconnect_cancels_work(monkeypatch):
    broker=StudioCapabilityBroker(SimpleNamespace(extension_manager=None))
    monkeypatch.setattr(broker,'mounted_mini_app',lambda *a,**kw: SimpleNamespace(capabilities={'llm.text'},declaration={}))
    async def work(*a,**kw): await asyncio.Event().wait()
    monkeypatch.setattr(broker,'_task_completion',work)
    async def disconnected():return True
    with pytest.raises(StudioCapabilityError) as error:
        await broker.llm_complete('s','m',principal='owner',request=SimpleNamespace(is_disconnected=disconnected),prompt='text')
    assert error.value.status_code==499

def test_request_defaults_and_bounds():
    assert MiniAppLLMRequest(prompt='x').complexity=='simple'
    for values in ({'complexity':'other'},{'model':'bypass'},{'profile':'other'},{'prompt':'x'*128001}):
        with pytest.raises(ValidationError):MiniAppLLMRequest(**({'prompt':'x'}|values))
