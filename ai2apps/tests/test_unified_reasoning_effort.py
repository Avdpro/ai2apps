"""Caller intent survives routing; declarations own native controls."""
import json
from types import SimpleNamespace
import httpx
import pytest
from fastapi import HTTPException
from ai2apps.model_worker.reasoning_capabilities import adapt_reasoning_effort, ReasoningEffortError, validate_reasoning_control
from ai2apps.model_worker.reasoning_capabilities import validate_reasoning_capabilities, ReasoningCapabilitiesError
from ai2apps.task_llm import task_payload, prepare_task_request

@pytest.mark.parametrize('fmt,expected', [
 ('openai',{'reasoning_effort':'low'}),
 ('thinking',{'thinking':{'type':'enabled'},'reasoning_effort':'low'}),
 ('responses',{'reasoning':{'effort':'low'}}),
 ('chat_template',{'chat_template_kwargs':{'enable_thinking':True,'reasoning_effort':'low'}}),
 ('output_config',{'thinking':{'type':'adaptive'},'output_config':{'effort':'low'}}),('none',{})])
def test_formats_no_mutation(fmt,expected):
    original={'messages':[{'role':'user','content':'Hello'}],'reasoning_effort':'low'}
    output=adapt_reasoning_effort(original,{'format':fmt,'efforts':['low']})
    assert output=={'messages':original['messages'],**expected}
    output['messages'][0]['content']='Changed'
    assert original['messages'][0]['content']=='Hello'

@pytest.mark.parametrize('fmt',['thinking','chat_template','responses','output_config'])
def test_disable(fmt):
    body=adapt_reasoning_effort({'reasoning_effort':'none'},{'format':fmt,'efforts':['low'],'can_disable':True})
    assert body.get('reasoning_effort') is None
    if fmt=='responses':assert body['reasoning']=={'effort':'none'}
    elif fmt=='chat_template':assert body['chat_template_kwargs']=={'enable_thinking':False}
    else:assert body['thinking']=={'type':'disabled'}

def test_compatibility_and_aliases():
    body={'thinking':{'type':'enabled'}}
    assert adapt_reasoning_effort(body,{'format':'none'})==body
    assert adapt_reasoning_effort({'reasoning_effort':'low'})=={'reasoning_effort':'low'}
    with pytest.raises(ReasoningEffortError):adapt_reasoning_effort({'reasoning_effort':'LOW'})
    with pytest.raises(ReasoningEffortError):adapt_reasoning_effort({'reasoning_effort':'low'},{'format':'openai','efforts':['high']})
    assert adapt_reasoning_effort({'reasoning_effort':'medium'},{'format':'openai','efforts':['high'],'aliases':{'medium':'high'}})=={'reasoning_effort':'high'}

@pytest.mark.parametrize('control',[{'format':[]},{'format':'openai','efforts':[{}]},
 {'format':'openai','efforts':['low','low']},{'format':'openai','aliases':{'low':'bogus'},'efforts':['high']},
 {'format':'thinking','can_disable':1},{'format':'unknown'},{'format':'none','extra':1}])
def test_bad_declarations(control):
    with pytest.raises(ReasoningEffortError):validate_reasoning_control(control)

@pytest.mark.parametrize('payload,control',[
 ({'reasoning_effort':'low','thinking':{'type':'disabled'}},{'format':'thinking'}),
 ({'reasoning_effort':'low','chat_template_kwargs':{'reasoning_effort':'high'}},{'format':'chat_template'}),
 ({'reasoning_effort':'low','reasoning':[]},{'format':'responses'})])
def test_conflicts(payload,control):
    with pytest.raises(ReasoningEffortError):adapt_reasoning_effort(payload,control)

def test_task_privacy_rerouting():
    body=task_payload('cloud/test/model',[],'simple',reasoning_effort='low')
    assert 'reasoning_effort' not in task_payload('model',[],'simple')
    runtime=SimpleNamespace(privacy_mode=True,model_manager=SimpleNamespace(resolve_default_model=lambda *a,**k:'private-model'))
    routed=prepare_task_request(runtime,{**body,'_ai2apps_task_route':{'profile':'normal','complexity':'simple'}})
    assert routed['model']=='private-model' and routed['reasoning_effort']=='low'
    with pytest.raises(ReasoningEffortError):task_payload('model',[],'simple',reasoning_effort='invalid')

@pytest.mark.asyncio
@pytest.mark.parametrize('effort,expected',[('low',{'type':'enabled'}),('none',{'type':'disabled'}),('ultra',{'type':'enabled'})])
async def test_catalog_gateway_deepseek(tmp_path,effort,expected):
    from ai2apps.cloud_gateway import proxy_cloud_chat_completion
    from ai2apps.model_manager import ModelManagerStore
    store=ModelManagerStore(tmp_path)
    store.put_cloud('deepseek',{'api_key':'fixture-key','models':['deepseek-flash']})
    store.set_cloud_model_enabled('deepseek','deepseek-flash',True)
    request=SimpleNamespace(model='cloud/deepseek/deepseek-flash',stream=False)
    request.model_dump=lambda **k:{'model':request.model,'messages':[{'role':'user','content':'Define WAL'}],'reasoning_effort':effort}
    seen=[]
    def handle(req):
        body=json.loads(req.content);seen.append(body)
        assert body['thinking']==expected
        if effort=='none':assert 'reasoning_effort' not in body
        else:assert body['reasoning_effort']==('max' if effort=='ultra' else effort)
        return httpx.Response(200,json={'choices':[]})
    response=await proxy_cloud_chat_completion(request,base_path=tmp_path,model_manager=store,transport=httpx.MockTransport(handle))
    assert response.status_code==200 and len(seen)==1

def test_managed_cloud_never_discards():
    from ai2apps.cloud_gateway import _ai2apps_request_body
    with pytest.raises(HTTPException,match='reasoning_effort'):_ai2apps_request_body(SimpleNamespace(reasoning_effort='low'))

def test_signed_package_declaration():
    old={'schema':'ai2apps.reasoning/v1','mode':'optional'}
    assert 'effort_control' not in validate_reasoning_capabilities(old)
    assert validate_reasoning_capabilities({**old,'effort_control':{'format':'chat_template','efforts':['low','high']}})['effort_control']['format']=='chat_template'
    with pytest.raises(ReasoningCapabilitiesError):validate_reasoning_capabilities({**old,'mode':'required','effort_control':{'format':'thinking','can_disable':True}})

@pytest.mark.asyncio
async def test_package_undeclared_before_worker():
    from ai2apps.model_providers import proxy_package_json
    model=SimpleNamespace(runtime=None,model_type='llm',endpoints={'chat':'/chat'},metadata={})
    with pytest.raises(HTTPException,match='does not declare'):await proxy_package_json(model,'chat',{'reasoning_effort':'low'})

@pytest.mark.asyncio
@pytest.mark.parametrize('stream',[False,True])
async def test_package_declared_control_reaches_worker(monkeypatch,stream):
    from ai2apps import model_providers as provider
    model=SimpleNamespace(runtime=None,model_type='llm',endpoints={'chat':'/chat'},
        metadata={'reasoning':{'mode':'optional','effort_control':{'format':'chat_template','efforts':['low','high']}}},
        upstream_id='arbitrary-worker-model',scheduler=None,internal_headers=None,endpoint='http://127.0.0.1:9999')
    async def ready(model):return model
    monkeypatch.setattr(provider,'_ensure_package_model_ready',ready)
    seen=[]
    def handle(req):
        body=json.loads(req.content);seen.append(body)
        assert body['chat_template_kwargs']=={'enable_thinking':True,'reasoning_effort':'low'}
        assert 'reasoning_effort' not in body
        return httpx.Response(200,json={'choices':[]})
    factory=httpx.AsyncClient
    monkeypatch.setattr(provider.httpx,'AsyncClient',lambda **kwargs:factory(transport=httpx.MockTransport(handle),**kwargs))
    response=await provider.proxy_package_json(model,'chat',{'reasoning_effort':'low','stream':stream})
    if stream:
        async for _ in response.body_iterator:pass
    assert response.status_code==200 and len(seen)==1

@pytest.mark.parametrize('fmt',['thinking','chat_template','output_config'])
def test_disabling_requires_declaration(fmt):
    with pytest.raises(ReasoningEffortError):adapt_reasoning_effort({'reasoning_effort':'none'},{'format':fmt})

@pytest.mark.asyncio
async def test_declared_responses_endpoint_preserves_mapped_effort():
    from ai2apps.cloud_gateway import proxy_cloud_chat_completion
    class Store:
        def resolve_cloud_model(self,model):return {'base_url':'https://arbitrary.example/v1','api_key':'fixture',
            'model_id':'arbitrary','protocol':'openai','capabilities':{'reasoningControl':{'format':'responses','efforts':['low']}}}
    request=SimpleNamespace(model='cloud/arbitrary/arbitrary',stream=False)
    request.model_dump=lambda **k:{'model':request.model,'messages':[{'role':'user','content':'Hello'}],'reasoning_effort':'low'}
    seen=[]
    def handle(req):
        body=json.loads(req.content);seen.append(body)
        assert req.url.path=='/v1/responses' and body['reasoning']=={'effort':'low'}
        return httpx.Response(200,json={'id':'response','model':'arbitrary','output':[]})
    response=await proxy_cloud_chat_completion(request,base_path=None,model_manager=Store(),transport=httpx.MockTransport(handle))
    assert response.status_code==200 and len(seen)==1
