"""Owner Cloud Search protocol with real SQLite and synthetic Device transport."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from ai2apps.browser import cloud_search as cloud
from ai2apps.browser import search_api
from ai2apps.research import search_preparation as prep
from test_search_workflow import prepared,values
from test_app_interactions import runtime

PRICE='deepseek-search-v1-20261024'
OFFER={'provider':'deepseek','transport':'cloud','available':True,'reason':None,'price_version':PRICE,
       'points_per_search':'1','max_query_chars':128,'max_results':50,'result_retention_seconds':86400,'privacy_mode_allowed':False}

class Transport:
    async def close(self):pass
    def __init__(self):self.calls=[];self.records={};self.lost=False;self.empty=False;self.pending=False
    async def request(self,method,path,*,json=None,headers=None):
        assert headers['Authorization']=='Device fixture-device.fixture-secret'
        self.calls.append((method,path,json))
        if path.endswith('/capabilities'):return httpx.Response(200,json=OFFER)
        if path==cloud.ROOT+'/requests':
            assert set(json)=={'query','count','request_id','price_version','privacy_mode'} and json['privacy_mode'] is False
            assert json['request_id'] not in self.records,'Duplicate paid POST'
            value={'provider':'deepseek','transport':'cloud','status':'completed','items':[] if self.empty else [{'title':'Article','url':'https://example.com/article','summary':'Snippet'}],
                'error_code':None,'usage':{'request_id':json['request_id'],'price_version':PRICE,'points_charged':'0' if self.empty else '1','billing_status':'released' if self.empty else 'charged'}}
            self.records[json['request_id']]=value
            if self.lost:raise httpx.ReadTimeout('opaque transport failure')
            if self.pending:return httpx.Response(202,json={**value,'status':'in_progress','items':[], 'usage':{**value['usage'],'points_charged':'0','billing_status':'reserved'}})
            return httpx.Response(200,json=value)
        key=path.split('/requests/')[1].split('/')[0]
        if method=='DELETE':return httpx.Response(200,json={'deleted':True,'request_id':key})
        if key not in self.records:return httpx.Response(404,json={'error':{'code':'SEARCH_REQUEST_NOT_FOUND'}})
        return httpx.Response(200,json=self.records[key])

@pytest.fixture
def transport(runtime,monkeypatch):
    t=Transport();monkeypatch.setattr(runtime,'cloud',t,raising=False)
    monkeypatch.setattr(runtime,'cloud_ai_authorization_headers',lambda principal:{'Authorization':'Device fixture-device.fixture-secret'},raising=False)
    monkeypatch.setattr(search_api,'byok_available',lambda *args:False)
    monkeypatch.setattr(cloud,'_poll_delay',AsyncMock())
    return t

async def approve(runtime,prepared):
    actor,_,mini,state,_=prepared
    await cloud.refresh_offer(runtime,actor.actor_user_id)
    payload=values(prepared,mode='custom',sources=['deepseek'],cloud_consent=True,cloud_price_version=PRICE,cloud_max_points='1')
    return prep.confirm(runtime,actor,mini,state['id'],payload,scope='app:app')

@pytest.mark.asyncio
async def test_cloud_cost_requires_human_receipt_and_pins_price(runtime,prepared,transport):
    actor,_,mini,state,_=prepared
    await cloud.refresh_offer(runtime,'local')
    payload=values(prepared,sources=['deepseek'])
    with pytest.raises(ValueError,match='CONFIRMATION'):prep.confirm(runtime,actor,mini,state['id'],payload,scope='app:app')
    for change in ({'cloud_price_version':'old'},{'cloud_max_points':'0'},{'cloud_consent':False}):
        with pytest.raises(ValueError):prep.confirm(runtime,actor,mini,state['id'],{**payload,'cloud_consent':True,'cloud_price_version':PRICE,'cloud_max_points':'1',**change},scope='app:app')
    receipt=await approve(runtime,prepared)
    assert cloud.route(runtime,'local',receipt['confirmation_id'])['route']=='cloud'
    assert not any(c[0]=='POST' for c in transport.calls)

@pytest.mark.asyncio
@pytest.mark.parametrize('lost,pending,empty',[(False,False,False),(True,False,False),(False,True,False),(False,False,True)])
async def test_paid_post_once_then_read_only_recovery(runtime,prepared,transport,lost,pending,empty):
    receipt=await approve(runtime,prepared);transport.lost=lost;transport.pending=pending;transport.empty=empty
    result=await cloud.execute(runtime,'local',receipt['query'],5,receipt['confirmation_id'],'task-one')
    assert result['status']=='completed' and len(result['items'])==(0 if empty else 1)
    assert result['usage']['points_charged']==('0' if empty else '1')
    replay=await cloud.execute(runtime,'local',receipt['query'],5,receipt['confirmation_id'],'another-task',recover=True)
    assert replay==result
    assert len([c for c in transport.calls if c[0]=='POST'])==1
    assert 'fixture-secret' not in str(result)
    with pytest.raises(ValueError,match='CONFIRMATION_CHANGED'):
        await cloud.execute(runtime,'local','changed',5,receipt['confirmation_id'],'task-one')

@pytest.mark.asyncio
async def test_byok_priority_and_failed_byok_does_not_charge_cloud(runtime,prepared,transport,monkeypatch):
    await cloud.refresh_offer(runtime,'local');monkeypatch.setattr(search_api,'byok_available',lambda *args:True)
    receipt=await approve(runtime,prepared)
    assert cloud.route(runtime,'local',receipt['confirmation_id'])['route']=='byok'
    monkeypatch.setattr(search_api,'deepseek_search',AsyncMock(side_effect=ValueError('BYOK HTTP 402')))
    with pytest.raises(ValueError,match='402'):
        await search_api.search(runtime,'local',receipt['query'],5,provider='deepseek',receipt_id=receipt['confirmation_id'],task_id='task-one')
    assert not any(c[0]=='POST' for c in transport.calls)

@pytest.mark.asyncio
@pytest.mark.parametrize('system,profile',[(True,'normal'),(False,'privacy')])
async def test_privacy_blocks_before_external_request(runtime,prepared,transport,system,profile):
    receipt=await approve(runtime,prepared);transport.calls.clear();runtime.privacy_mode=system
    with pytest.raises(ValueError,match='PRIVACY'):
        await cloud.execute(runtime,'local',receipt['query'],5,receipt['confirmation_id'],'task-one',profile)
    assert transport.calls==[]

@pytest.mark.asyncio
async def test_recover_never_posts_even_if_no_request_exists(runtime,prepared,transport):
    receipt=await approve(runtime,prepared)
    assert await cloud.execute(runtime,'local',receipt['query'],5,receipt['confirmation_id'],'task-one',recover=True) is None
    assert not any(c[0]=='POST' for c in transport.calls)

@pytest.mark.asyncio
async def test_cancel_delete_and_foreign_scope(runtime,prepared,transport,monkeypatch):
    receipt=await approve(runtime,prepared)
    await cloud.execute(runtime,'local',receipt['query'],5,receipt['confirmation_id'],'task-one')
    read=await cloud.observe(runtime,'local','task-one');assert read['usage']['points_charged']=='1'
    cancelled=await cloud.observe(runtime,'local','task-one',action='cancel');assert cancelled['status']=='completed'
    removed=await cloud.observe(runtime,'local','task-one',action='delete');assert removed['status']=='deleted'
    assert len([c for c in transport.calls if c[1]==cloud.ROOT+'/requests'])==1
    monkeypatch.setattr(cloud,'principal_for',lambda *args:SimpleNamespace(installation_id='foreign'))
    with pytest.raises(ValueError,match='NOT_FOUND'):cloud.owned_request(runtime,'local','task-one')

@pytest.mark.asyncio
async def test_price_change_denied_before_post(runtime,prepared,transport,monkeypatch):
    receipt=await approve(runtime,prepared)
    monkeypatch.setattr(cloud,'refresh_offer',AsyncMock(return_value={**OFFER,'price_version':'future-price'}))
    with pytest.raises(ValueError,match='PRICE_CHANGED'):
        await cloud.execute(runtime,'local',receipt['query'],5,receipt['confirmation_id'],'task-one')
    assert not any(c[0]=='POST' for c in transport.calls)

@pytest.mark.asyncio
async def test_fast_preparation_has_no_model_or_plan_task(runtime,prepared,transport):
    actor,thread,mini,_,calls=prepared
    await cloud.refresh_offer(runtime,'local')
    before=len(calls)
    state=prep.begin(runtime,actor,mini,scope='app:app',session_id=thread.session.id,query='DeepSeek',request_id='fast-no-llm',fast=True)
    assert state['status']=='completed' and state['fast_source']=='deepseek' and state['query']=='DeepSeek'
    assert state['task_id']=='' and len(calls)==before
    assert prep.begin(runtime,actor,mini,scope='app:app',session_id=thread.session.id,query='DeepSeek',request_id='fast-no-llm',fast=True)['id']==state['id']
    with pytest.raises(ValueError,match='mode changed'):
        prep.begin(runtime,actor,mini,scope='app:app',session_id=thread.session.id,query='DeepSeek',request_id='fast-no-llm',fast=False)

@pytest.mark.asyncio
async def test_aaat_form_explicit_paid_consent_before_exact_invocation(runtime,prepared,transport,monkeypatch):
    from fastapi import FastAPI
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.identity import RequestPrincipal
    from test_app_interactions import wait
    import test_parameter_forms
    initial={'query':'DeepSeek','mode':'fast','profile':'default','limit':5}
    monkeypatch.setattr(test_parameter_forms,'ARGS',{'request_id':'paid-form','capability':'web.search','provider':'ai2apps.search-all.search','values':initial})
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    runtime.cloud=None
    await runtime.start_background_tasks(retention_interval_seconds=60)
    runtime.cloud=transport
    try:
        run=test_parameter_forms.setup(runtime);await wait(runtime,run.id,'waiting_input')
        item=runtime.agents.list_interactions(run.id)[0];url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            state=(await client.get(url)).json()
            field=next(f for f in state['descriptor']['fields'] if f['key']=='cloud_consent')
            assert '1 Point' in field['label']['en'] and not field.get('default',False)
            plan=await client.post(url+'/search/prepare',json={'revision':0,'values':initial});assert plan.status_code==200,plan.text
            chosen={**initial,'sources':['deepseek'],'query':'DeepSeek','preparation_id':plan.json()['id'],'preparation_ready':True,
                'cloud_price_version':PRICE,'cloud_max_points':'1','cloud_consent':False}
            saved=await client.put(url,json={'revision':0,'values':chosen});assert saved.status_code==200,saved.text
            denied=await client.post(url+'/submit',json={'revision':1,'values':chosen});assert denied.status_code==422,denied.text
            assert not any(c[0]=='POST' for c in transport.calls)
            current=(await client.get(url)).json()
            accepted={**chosen,'cloud_consent':True}
            saved=await client.put(url,json={'revision':current['revision'],'values':accepted});assert saved.status_code==200,saved.text
            approved=await client.post(url+'/submit',json={'revision':current['revision']+1,'values':accepted})
            assert approved.status_code==200,approved.text
            args=approved.json()['result']['arguments']
            assert args['cloud_consent'] is True and args['cloud_price_version']==PRICE
            assert cloud.route(runtime,'local',args['confirmation_id'])['route']=='cloud'
            assert not any(c[0]=='POST' for c in transport.calls) # Consent is not an API submission.
    finally:await runtime.stop_background_tasks()
