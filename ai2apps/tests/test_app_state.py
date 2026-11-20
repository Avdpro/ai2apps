"""Portable state: schemas, owner scope and idempotent UI receipts."""
from dataclasses import replace
from types import SimpleNamespace
import httpx,pytest
from fastapi import FastAPI
from ai2apps.apps.app_state import AppStateService,StateContract,StateError
from ai2apps.apps.state_setup import get_app_state
from ai2apps.api.app_state import create_app_state_router
from ai2apps.identity import RequestPrincipal
from test_app_interactions import runtime
P=RequestPrincipal.legacy_local

def schema():return {'type':'object','properties':{'mode':{'type':'string','enum':['compact','full'],'x-app-state':'portable'}},'required':['mode'],'additionalProperties':False}
def packet(app='fixture.alpha',version=1,values=None):return {'schema':'ai2apps.app-state/v1','target':{'app_id':app,'mini_app_id':None,'contract_version':version},'values':values or {'mode':'compact'}}

@pytest.mark.parametrize('app',['arbitrary.alpha','unrelated.beta'])
def test_owner_contract_freezing_version_migration_and_receipts(runtime,app):
 r=SimpleNamespace(database=runtime.database,extension_manager=SimpleNamespace(require_instance_access=lambda i,p:{'package_id':app}));s=AppStateService(r)
 original=schema();s.register(StateContract(app,None,2,'Fixture',original,migrations={1:lambda v:v}));original['properties']['secret']={'type':'string'}
 assert 'secret' not in s.describe(app)['schema']['properties']
 with pytest.raises(StateError):s.validate(P(),'instance',packet(app))
 value=s.validate(P(),'instance',packet(app),migrate=True);exact=value['packet'];assert exact['target']['contract_version']==2
 saved=s.save(P(),'instance','My settings',exact,'save-request');assert s.save(P(),'instance','My settings',exact,'save-request')['id']==saved['id']
 assert len(s.list(P(),'instance',app)['items'])==1 and not s.list(replace(P(),actor_user_id='other'),'instance',app)['items']
 prepared=s.prepare(P(),'instance',exact,'restore-request','a'*64,value['contract_digest']);assert s.prepare(P(),'instance',exact,'restore-request','a'*64,value['contract_digest'])['id']==prepared['id']
 with pytest.raises(StateError):s.prepare(P(),'instance',exact,'restore-request','b'*64,value['contract_digest'])
 with pytest.raises(PermissionError):s.complete(replace(P(),actor_user_id='other'),'instance',prepared['id'],exact,'ui_applied')
 with pytest.raises(StateError):s.complete(P(),'instance',prepared['id'],{**exact,'values':{'mode':'full'}},'ui_applied')
 receipt=s.complete(P(),'instance',prepared['id'],exact,'ui_applied');assert s.complete(P(),'instance',prepared['id'],exact,'ui_applied')==receipt
 with pytest.raises(StateError):s.complete(P(),'instance',prepared['id'],exact,'failed')

@pytest.mark.parametrize('values',[{'mode':'full','token':'SECRET'},{'mode':'unsupported'},{'mode':['full']},{'__proto__':{}},{'mode':'x'*17000}])
def test_private_unknown_oversized_or_invalid_fields_never_persist(runtime,values):
 r=SimpleNamespace(database=runtime.database,extension_manager=SimpleNamespace(require_instance_access=lambda i,p:{'package_id':'fixture.alpha'}));s=AppStateService(r);s.register(StateContract('fixture.alpha',None,1,'Fixture',schema()))
 with pytest.raises(StateError):s.save(P(),'instance','Invalid',packet(values=values),'invalid-save')
 with runtime.database.transaction() as db:assert db.execute('SELECT count(*) FROM portable_app_state_presets').fetchone()[0]==0

def test_rejects_unbounded_or_undeclared_contracts(runtime):
 s=AppStateService(runtime)
 for value in ({'type':'object','properties':{},'additionalProperties':True},{'type':'object','properties':{'token':{'type':'string'}},'required':['token'],'additionalProperties':False}):
  with pytest.raises(StateError):s.register(StateContract('fixture',None,1,'Bad',value))

@pytest.mark.asyncio
async def test_real_reference_api_owner_instance_and_desktop_mobile_portability(runtime,monkeypatch):
 instance,_,_=runtime.extension_manager.launch_app('ai2apps.imagine-studio',principal=P());instance=instance.id;principal=[P()]
 app=FastAPI();app.include_router(create_app_state_router(lambda:runtime,lambda:principal[0]));base='/app-state/instances/'+instance
 state={'schema':'ai2apps.app-state/v1','target':{'app_id':'ai2apps.imagine-studio','mini_app_id':'ai2apps.imagine.style-transfer','contract_version':1},'values':{'model_id':'cloud/fixture/image','style_id':'ghibli-256-png','width':1024,'height':1024,'quality':'high','format':'png'}}
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as c:
  value=await c.post(base+'/presets',json={'name':'Style preset','packet':state,'request_id':'desktop-save'});assert value.status_code==201,value.text
  contract=await c.get(base+'/contract',params={'app_id':'ai2apps.imagine-studio','mini_app_id':'ai2apps.imagine.style-transfer'});assert contract.status_code==200,contract.text
  assert contract.headers['cache-control']=='no-store'
  principal[0]=replace(P(),client_scope='owner-home',authentication_type='owner_home_lease');monkeypatch.setattr('ai2apps.remote.mobile_apps.app_enabled',lambda r,p,key:key=='ai2apps.imagine-studio')
  mobile=await c.get(base+'/presets',params={'app_id':'ai2apps.imagine-studio','mini_app_id':'ai2apps.imagine.style-transfer'});assert mobile.status_code==200 and mobile.json()['items'][0]['packet']==state
  wrong=await c.post(base+'/validate',json={'packet':packet('ai2apps.todo')});assert wrong.status_code==404
  monkeypatch.setattr('ai2apps.remote.mobile_apps.app_enabled',lambda *args:False);assert (await c.get(base+'/contract',params={'app_id':'ai2apps.imagine-studio'})).status_code==404
  principal[0]=P();bad={**state,'values':{**state['values'],'prompt':'private text'}};assert (await c.post(base+'/validate',json={'packet':bad})).status_code==409

def test_mobile_route_inventory_exposes_only_exact_state_operations():
 from ai2apps.web.owner_studio_gateway import allowed
 assert allowed('POST','/v1/platform/app-state/instances/i/applications') and allowed('GET','/v1/platform/app-state/instances/i/contract')
 assert not allowed('POST','/v1/platform/app-state/execute') and not allowed('DELETE','/v1/platform/app-state/instances/i/presets')


@pytest.mark.parametrize('mini',['ai2apps.imagine.style-transfer','ai2apps.imagine.text-to-image','ai2apps.imagine.image-edit','ai2apps.imagine.reference-creation','ai2apps.imagine.group-photo','ai2apps.imagine.character-design'])
def test_image_continuations_and_presets_use_registered_settings_contract(runtime,mini):
 from ai2apps.apps.state_setup import get_app_state
 instance,_,_=runtime.extension_manager.launch_app('ai2apps.imagine-studio',principal=P())
 state={'schema':'ai2apps.app-state/v1','target':{'app_id':'ai2apps.imagine-studio','mini_app_id':mini,'contract_version':1},'values':{'model_id':'cloud/fixture/image','style_id':'','width':None,'height':None,'quality':'auto','format':'png'}}
 service=get_app_state(runtime)
 assert service.validate(P(),instance.id,state)['packet']==state
 with pytest.raises(StateError):service.validate(P(),instance.id,{**state,'values':{**state['values'],'width':1024}})
 with pytest.raises(StateError):service.validate(P(),instance.id,{**state,'values':{**state['values'],'prompt':'PRIVATE'}})
