"""Managed format negotiation, buffered terminal validation and accounting preservation."""
import json
from types import SimpleNamespace as NS
import httpx
import pytest
from fastapi import HTTPException
from ai2apps.cloud_gateway import _proxy_ai2apps_chat_completion
from ai2apps.cloud_client import AI2AppsCloudClient,CloudSessionStore
from ai2apps.secrets import MemorySecretBackend

CAP={'contract':'ai2apps.structured-output.v1','modes':['json_object'],'buffered':True,'maxOutputBytes':1048576,'tools':False,'jsonSchema':False}

def request(stream=False,format=None):
    return NS(model='cloud/ai2apps/arbitrary/provider-model',stream=stream,max_tokens=100,temperature=None,tools=None,
              response_format=format if format is not None else {'type':'json_object'},
              messages=[NS(role='system',content='Return a JSON object.',tool_calls=None,tool_call_id=None),NS(role='user',content='hello',tool_calls=None,tool_call_id=None)],ai2apps_idempotency_key='original-key')

def result(text='{"kind":"reply","text":"42"}',**changes):
    return {'requestId':'fixture-request','status':'completed','stopReason':'stop','responseFormat':{'type':'json_object'},'structuredOutput':{'valid':True,'type':'json_object'},'output':[{'type':'output_text','text':text}],'usage':{'inputTokens':10,'outputTokens':5},'points':{'charged':'2'},**changes}

def client(handler):
    return AI2AppsCloudClient(base_url='https://cloud.fixture',session_store=CloudSessionStore(MemorySecretBackend(),'https://cloud.fixture'),transport=httpx.MockTransport(handler))

def handler_for(payload,*,cap=CAP,stream=None,calls=None):
    def handle(req):
        if calls is not None:calls.append((req.method,req.url.path))
        if req.method=='GET':return httpx.Response(200,json={'items':[{'id':'arbitrary/provider-model','capabilities':{'structuredOutput':cap}}]})
        body=json.loads(req.content);assert body['responseFormat']=={'type':'json_object'};assert 'response_format' not in body
        assert body['system']=='Return a JSON object.' and req.headers['idempotency-key']=='original-key'
        return httpx.Response(200,content=stream,headers={'content-type':'text/event-stream'}) if stream is not None else httpx.Response(200,json=payload)
    return handle

@pytest.mark.asyncio
async def test_json_mapping_and_success_marker(tmp_path):
    c=client(handler_for(result()));r=await _proxy_ai2apps_chat_completion(request(),c)
    value=json.loads(r.body);assert value['choices'][0]['message']['content']=='{"kind":"reply","text":"42"}'
    assert value['ai2apps_cloud']['structuredOutput']['valid'] is True and value['ai2apps_cloud']['points']['charged']=='2';await c.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('cap',[None,False,{},dict(CAP,modes=[]),dict(CAP,contract='old'),dict(CAP,buffered=False)])
async def test_unknown_capability_does_not_submit(cap):
    calls=[];c=client(handler_for(result(),cap=cap,calls=calls))
    with pytest.raises(HTTPException) as e:await _proxy_ai2apps_chat_completion(request(),c)
    assert e.value.detail['code']=='AI_RESPONSE_FORMAT_UNSUPPORTED' and all(m=='GET' for m,_ in calls);await c.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('format',[{'type':'json_schema'},{'type':'json_object','strict':True},'json_object',{}])
async def test_unsupported_format_never_calls_cloud(format):
    def forbidden(_):raise AssertionError('No Cloud call allowed')
    c=client(forbidden)
    with pytest.raises(HTTPException):await _proxy_ai2apps_chat_completion(request(format=format),c)
    await c.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('role,tools',[('system',[NS(function={})]),('developer',None)])
async def test_unsupported_combinations_not_dropped(role,tools):
    r=request();r.messages[0].role=role;r.tools=tools;c=client(lambda _:(_ for _ in ()).throw(AssertionError()))
    with pytest.raises(HTTPException):await _proxy_ai2apps_chat_completion(r,c)
    await c.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('payload',[result('42'),result('[]'),result('null'),result('```json\n{}\n```'),result('{}',structuredOutput={}),result('{}',responseFormat=None),result('{}',stopReason='length'),result('{}',stopReason='refused'),result('{}',status='failed')])
async def test_invalid_completed_result_preserves_charge_evidence(payload):
    c=client(handler_for(payload))
    with pytest.raises(HTTPException) as e:await _proxy_ai2apps_chat_completion(request(),c)
    assert e.value.detail['retryable'] is False
    assert e.value.detail['details']['points']['charged']=='2';await c.close()

def event(kind,value):return 'event: '+kind+'\ndata: '+json.dumps(value)+'\n\n'

@pytest.mark.asyncio
@pytest.mark.parametrize('ending',['success','missing','rollback','failed'])
async def test_stream_waits_for_verified_terminal(ending):
    text='{"kind":"reply","text":"42"}'
    raw=event('response.created',{'requestId':'fixture-request'})+event('output_text.delta',{'delta':text})
    if ending=='success':raw+=event('response.completed',result())
    if ending=='rollback':raw+=event('response.completed',{'stopReason':'stop'})
    if ending=='failed':raw+=event('response.failed',{'error':{'code':'AI_STRUCTURED_OUTPUT_INVALID','retryable':False,'details':{'billingStatus':'settled','points':{'charged':'2'}}}})
    c=client(handler_for(None,stream=raw.encode()));r=await _proxy_ai2apps_chat_completion(request(True),c)
    chunks=[x async for x in r.body_iterator];body=b''.join(chunks).decode()
    assert '"content":"{\\"kind' not in chunks[0].decode()
    if ending=='success':assert '"content":"{\\"kind' in body and '"phase":"completed"' in body
    else:assert '"content":"{\\"kind' not in body and '"phase":"failed"' in body and '"phase":"completed"' not in body
    if ending=='failed':assert 'settled' in body and '"charged":"2"' in body
    await c.close()

@pytest.mark.asyncio
async def test_http_failed_structured_call_keeps_billing_and_no_retry():
    calls=[]
    def handler(req):
        calls.append(req.method)
        if req.method=='GET':return httpx.Response(200,json={'items':[{'id':'arbitrary/provider-model','capabilities':{'structuredOutput':CAP}}]})
        return httpx.Response(502,json={'error':{'code':'AI_STRUCTURED_OUTPUT_INVALID','message':'Output format failed','retryable':False,'details':{'schemaVersion':'ai2apps.structured-output.v1','billingStatus':'settled','points':{'charged':'2'},'usage':{'inputTokens':10}}}})
    c=client(handler)
    with pytest.raises(HTTPException) as e:await _proxy_ai2apps_chat_completion(request(),c)
    assert e.value.detail['details']['billingStatus']=='settled' and e.value.detail['details']['points']['charged']=='2'
    assert calls==['GET','POST'];await c.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('model_id',['arbitrary/provider-model','different/vendor-language'])
async def test_capability_projection_is_provider_independent(model_id):
    r=request();r.model='cloud/ai2apps/'+model_id;calls=[]
    def handler(req):
        calls.append(req.method)
        if req.method=='GET':return httpx.Response(200,json={'items':[{'id':model_id,'capabilities':{'structuredOutput':CAP}}]})
        assert json.loads(req.content)['model']==model_id
        return httpx.Response(200,json=result())
    c=client(handler);out=await _proxy_ai2apps_chat_completion(r,c)
    assert json.loads(out.body)['choices'][0]['message']['content'].startswith('{') and calls==['GET','POST'];await c.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('kind',['oversize','unexpected_tool','malformed_output'])
async def test_structured_boundaries_never_release_invalid_content(kind):
    payload=result();cap=CAP
    if kind=='oversize':payload=result('{"text":"'+('x'*100)+'"}');cap=dict(CAP,maxOutputBytes=32)
    elif kind=='unexpected_tool':payload=result(output=[{'type':'tool_call','name':'arbitrary.write'}])
    else:payload=result(output=None)
    c=client(handler_for(payload,cap=cap))
    with pytest.raises(HTTPException) as e:await _proxy_ai2apps_chat_completion(request(),c)
    assert e.value.detail['retryable'] is False;await c.close()

@pytest.mark.asyncio
async def test_explicit_text_remains_text_without_capability_lookup():
    calls=[]
    def handler(req):
        calls.append(req.method);assert json.loads(req.content)['responseFormat']=={'type':'text'}
        return httpx.Response(200,json={'output':[{'type':'output_text','text':'ordinary text'}],'stopReason':'stop'})
    c=client(handler);r=await _proxy_ai2apps_chat_completion(request(format={'type':'text'}),c)
    assert json.loads(r.body)['choices'][0]['message']['content']=='ordinary text' and calls==['POST'];await c.close()

@pytest.mark.parametrize('raw',[{'type':'json_object','strict':True},{'type':'json_object','name':'ignored'},{'type':'json_object','schema':{}}])
def test_request_model_cannot_erase_unsupported_format_fields(raw):
    from omlx.api.openai_models import ChatCompletionRequest
    from ai2apps.cloud_structured_output import requested_format
    r=ChatCompletionRequest.model_validate({'model':'cloud/ai2apps/arbitrary/model','messages':[{'role':'system','content':'Return JSON'}],'response_format':raw})
    with pytest.raises(HTTPException) as e:requested_format(r)
    assert e.value.detail['code']=='INVALID_AI_RESPONSE_FORMAT'
