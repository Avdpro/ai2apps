"""Real Bot services through a scoped Mobile owner adapter."""
from dataclasses import replace
import httpx
import pytest
from fastapi import FastAPI,HTTPException
from ai2apps.api.messager_mobile import create_messager_mobile_router
from ai2apps.web.mobile_app_gateway import api_response
from ai2apps.core import MessageRole
from ai2apps.storage.repositories import MessageRepository
from ai2apps.storage.models import MessagePartInput
from test_bot_capability_discovery import setup,P
from test_app_interactions import runtime
SPEC={'api':{'module':'messager_mobile','factory':'create_messager_mobile_router','prefix':'/v1/platform/messager-mobile'}}
def owner():return replace(P(),authentication_type='owner_home_lease',client_scope='owner-home')

@pytest.mark.asyncio
async def test_mobile_owner_messages_cursor_upload_and_scope(runtime):
 bot,sid,_,_=setup(runtime);principal=[owner()]
 MessageRepository(runtime.database,runtime.events).append(session_id=sid,role=MessageRole.ASSISTANT,parts=[MessagePartInput(kind='text',content={'text':'Mobile fixture'})])
 app=FastAPI();app.include_router(create_messager_mobile_router(lambda:runtime,lambda:principal[0]))
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
  root='/messager-mobile';base=root+'/bots/'+bot['id']
  assert (await c.get(root+'/bots')).status_code==200
  assert (await c.post(root+'/open',json={'bot_id':bot['id']})).json()['session_id']==sid
  assert (await c.post(root+'/open',json={'bot_id':bot['id'],'registration':'other'})).status_code==422
  assert (await c.get(base+'/messages',params={'session_id':sid})).json()['items'][0]['content']=='Mobile fixture'
  assert (await c.get(base+'/state',params={'session_id':sid})).json()['unread']['unread_count']==1
  assert (await c.post(base+'/read',json={'session_id':sid,'through_sequence':1})).json()['unread_count']==0
  uploaded=await c.post(base+'/attachments',params={'session_id':sid},files={'file':('note.txt',b'Uploaded mobile fixture','text/plain')})
  assert uploaded.status_code==201,uploaded.text
  aid=uploaded.json()['id'];content=await c.get(base+'/files/'+sid+'/attachments/'+aid)
  assert content.content==b'Uploaded mobile fixture'
  sibling=runtime.messager_bots.create('local','Other Bot','Separate')
  assert (await c.get(root+'/bots/'+sibling['id']+'/files/'+sid+'/attachments/'+aid)).status_code==404
  principal[0]=replace(owner(),actor_user_id='foreign')
  assert (await c.get(base+'/messages',params={'session_id':sid})).status_code==404
  principal[0]=P();assert (await c.get(root+'/bots')).status_code==403
  principal[0]=replace(owner(),authentication_type='forged');assert (await c.get(root+'/bots')).status_code==403

@pytest.mark.asyncio
async def test_gateway_is_confined_to_mobile_owner_adapter(runtime):
 setup(runtime)
 assert (await api_response(runtime,owner(),SPEC,{'path':'/v1/platform/messager-mobile/bots'})).status_code==200
 for path in ('/v1/platform/messager/bots','/v1/platform/agent-runs','/admin/api/models','https://evil.invalid/v1/platform/messager-mobile/bots'):
  with pytest.raises(HTTPException):await api_response(runtime,owner(),SPEC,{'path':path})
 assert (await api_response(runtime,owner(),SPEC,{'path':'/v1/platform/messager-mobile/agent-runs','verb':'POST'})).status_code==404

@pytest.mark.asyncio
async def test_mobile_turn_is_durable_and_preserves_owner_scope(runtime):
 bot,sid,_,_=setup(runtime)
 from ai2apps.messager.conversation_profile import settings
 settings(runtime,'local',bot['id'],model_id='fixture',expected_revision=0)
 app=FastAPI();app.include_router(create_messager_mobile_router(lambda:runtime,owner))
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
  path='/messager-mobile/bots/'+bot['id']+'/turns';body={'session_id':sid,'request_id':'mobile-fixture-request','text':'Hello from Mobile','attachments':[]}
  first=await c.post(path,json=body);assert first.status_code==202,first.text
  assert (await c.post(path,json=body)).json()==first.json()
  assert runtime.agents.get_run(first.json()['run_id']).session_id==sid
  assert runtime.agents.get_run(first.json()['run_id']).input['model']=='fixture'
  history=await c.get('/messager-mobile/bots/'+bot['id']+'/messages',params={'session_id':sid})
  assert [m['client_request_id'] for m in history.json()['items'] if m['role']=='user']==[body['request_id']]
  body['text']='Different input';assert (await c.post(path,json=body)).status_code==409

def test_declared_mobile_assets_exist():
 from pathlib import Path
 from ai2apps.apps.system import SYSTEM_APP_MANIFESTS
 spec=next(m for m in SYSTEM_APP_MANIFESTS if m['id']=='ai2apps.messager')['mobile']['gateway'];assert spec['api']['prefix']=='/v1/platform/messager-mobile'
 root=Path(__file__).parents[1]/'web';assert (root/'templates'/spec['template']).is_file()
 for asset in spec['assets']:assert (root/'static'/asset).is_file()
 # Render with the real mount resource handler, not an unrestricted static stub.
 from jinja2 import Environment,FileSystemLoader
 from ai2apps.web.mobile_app_gateway import asset_response
 used=[]
 def scoped_asset(name):
  response=asset_response(spec,'assets/'+name)
  assert response.headers['cache-control']=='no-store'
  used.append(name)
  return '/app-assets/'+name
 env=Environment(loader=FileSystemLoader(root/'templates'),autoescape=True)
 env.get_template(spec['template']).render(current_lang='en',t=lambda key:key,static=scoped_asset,
  mobile_static=lambda name:'/mobile/static/'+name,mobile_gateway_config={'apiPrefix':spec['api']['prefix'],'bridge':'/bridge','resourceBase':'/resource/'})
 assert {'js/messager_usage.js','js/text_input_dialog.js','css/system_dialog.css'}<=set(used)
 with pytest.raises(HTTPException) as denied:asset_response(spec,'assets/js/mobile.js')
 assert denied.value.status_code==404


@pytest.mark.asyncio
async def test_model_projection_exports_no_settings_and_avatar_keeps_owner(runtime,monkeypatch):
 import io
 from PIL import Image
 from ai2apps.web import owner_home_gateway,mobile_model_catalog
 from ai2apps.gallery import GalleryRepository
 bot,sid,_,_=setup(runtime)
 async def models(p):return {'data':[{'id':'fixture','model_type':'llm','capabilities':['work_standard','tool_calling_reliable'],'settings':{'api_key':'secret'},'source_type':'cloud'}]}
 async def projection(public):return mobile_model_catalog.merge_catalog(public,[])
 monkeypatch.setattr(owner_home_gateway,'_models',models);monkeypatch.setattr(mobile_model_catalog,'desktop_catalog_projection',projection)
 gallery=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery')
 image=io.BytesIO();Image.new('RGB',(2,2),'blue').save(image,format='PNG');image.seek(0)
 asset,_=gallery.import_stream('local',image,name='avatar.png',media_type='image/png')
 runtime.messager_bots.set_avatar('local',bot['id'],{'kind':'image','asset_id':asset['id']})
 app=FastAPI();app.include_router(create_messager_mobile_router(lambda:runtime,owner))
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
  r=await c.get('/messager-mobile/models');assert r.status_code==200,r.text
  assert r.json()['data'][0]['id']=='fixture' and 'secret' not in r.text and 'settings' not in r.text
  r=await c.get('/messager-mobile/bots/'+bot['id']+'/avatar');assert r.status_code==200,r.text;assert r.content==image.getvalue()

@pytest.mark.asyncio
async def test_mobile_profile_shared_model_revision_and_owner(runtime):
 from ai2apps.messager.conversation_profile import settings
 bot,sid,_,_=setup(runtime)
 first=settings(runtime,'local',bot['id'],model_id='fixture',expected_revision=0)
 assert first=={'model_id':'fixture','effective_model':'fixture','revision':1,'reasoning_effort':None,'supported_reasoning_efforts':[]}
 with pytest.raises(ValueError):settings(runtime,'local',bot['id'],model_id='wrong',expected_revision=0)
 with pytest.raises(PermissionError):settings(runtime,'foreign',bot['id'])
 app=FastAPI();app.include_router(create_messager_mobile_router(lambda:runtime,owner))
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
  base='/messager-mobile/bots/'+bot['id']
  value=(await c.post('/messager-mobile/open',json={'bot_id':bot['id']})).json()
  assert value['profile']['model_id']=='fixture'
  detail=await c.get(base+'/details');assert detail.status_code==200,detail.text
  assert detail.json()['model']['model_id']=='fixture'
  update=await c.put(base+'/conversation-model',json={'model_id':'chosen-on-mobile','revision':1})
  assert update.status_code==200,update.text
  assert settings(runtime,'local',bot['id'])['model_id']=='chosen-on-mobile'
  assert (await c.put(base+'/conversation-model',json={'model_id':'stale','revision':1})).status_code==409
  assert (await c.patch(base+'/profile',json={'name':'Updated','duty':'Shared role'})).status_code==200
  assert runtime.messager_bots.identity('local',{'bot_id':bot['id']})['name']=='Updated'
  other=runtime.messager_bots.create('foreign','Other','Private')
  assert (await c.get('/messager-mobile/bots/'+other['id']+'/details')).status_code==404


@pytest.mark.asyncio
async def test_mobile_thinking_level_is_bound_to_the_selected_provider(runtime, monkeypatch):
 from ai2apps.messager.conversation_profile import settings
 bot,_,_,_=setup(runtime)
 byok='cloud/test-provider/same-model'
 managed='cloud/ai2apps/test-provider/same-model'
 monkeypatch.setattr(runtime.model_manager,'resolve_cloud_model',lambda model: {
  'capabilities': {'reasoningControl': {'format':'responses','efforts':['medium','high']}},
 } if model==byok else None)
 app=FastAPI();app.include_router(create_messager_mobile_router(lambda:runtime,owner))
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
  path='/messager-mobile/bots/'+bot['id']
  for model,levels in [(byok,['medium','high']),(managed,[])]:
   options=await c.get(path+'/reasoning-efforts',params={'model_id':model})
   assert options.json()=={'supported_reasoning_efforts':levels}
  saved=await c.put(path+'/conversation-model',json={'model_id':byok,'revision':0,'reasoning_effort':'high'})
  assert saved.json()['reasoning_effort']=='high'
  invalid=await c.put(path+'/conversation-model',json={'model_id':managed,'revision':1,'reasoning_effort':'high'})
  assert invalid.status_code==409
  assert settings(runtime,'local',bot['id'])['reasoning_effort']=='high'
  legacy=await c.put(path+'/conversation-model',json={'model_id':byok,'revision':1})
  assert legacy.json()['reasoning_effort']=='high'
  switch=await c.put(path+'/conversation-model',json={'model_id':managed,'revision':2})
  assert switch.json()['reasoning_effort'] is None and switch.json()['supported_reasoning_efforts']==[]

@pytest.mark.asyncio
async def test_mobile_answers_original_bot_question_and_rejects_foreign_targets(runtime):
 import json
 from test_app_chat_durable import response,bind_identity
 from ai2apps.identity import IdentityRepository,OrganizationType
 from test_app_interactions import wait
 from test_bot_dialogue import job_wait
 IdentityRepository(runtime.database).bind_installation(installation_id='local',cloud_device_id='local-device',organization_id='local',organization_type=OrganizationType.HOUSEHOLD,core_user_id='local',billing_account_id='local',access_epoch=1)
 bot,sid,_,_=setup(runtime)
 async def model(request):
  if 'Decide quickly' in request['messages'][0]['content']:
   return response(text=json.dumps({'kind':'task','title':'Inspect usage','text':'Queued'}))
  results=[m for m in request['messages'] if m['role']=='tool']
  if results:return response(text='Received '+json.loads(results[-1]['content'])['answer'])
  return response('agent.ask_user',{'question_id':'direction','question':'Which area?','options':['Workspace','Library']})
 runtime.agent_runtime.bind_model_provider(model)
 await runtime.start_background_tasks(retention_interval_seconds=60)
 try:
  source=runtime.messager_dialogue.submit(P(),bot['id'],sid,'question-mobile','Inspect usage','fixture',[])
  await wait(runtime,source,'completed');job=await job_wait(runtime,source,'running');rid=job['worker_run']
  await wait(runtime,rid,'waiting_input')
  item=runtime.agents.list_interactions(rid)[0]
  app=FastAPI();app.include_router(create_messager_mobile_router(lambda:runtime,owner))
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
   path=f'/messager-mobile/bots/{bot["id"]}/runs/{rid}/questions/{item.id}/respond'
   payload={'session_id':sid,'response_id':'mobile-answer','response':{'answer':'Workspace only; do not delete'}}
   assert (await c.post(path.replace(rid,'foreign-run'),json=payload)).status_code==404
   sibling=runtime.messager_bots.create('local','Other','Different Bot')
   assert (await c.post(path.replace(bot['id'],sibling['id']),json=payload)).status_code==404
   result=await c.post(path,json=payload);assert result.status_code==200,result.text
  await job_wait(runtime,source,'completed')
  assert 'Workspace only; do not delete' in runtime.agents.get_run(rid).output['content']
 finally:await runtime.stop_background_tasks()
