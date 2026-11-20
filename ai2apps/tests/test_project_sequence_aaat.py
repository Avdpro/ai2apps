from types import SimpleNamespace
import pytest
from test_app_interactions import runtime
from ai2apps.apps.access import RequestPrincipal
from ai2apps.studio import project_sequence_aaat as sdk
from ai2apps.studio.repository import StudioRepository

@pytest.mark.parametrize('identity',['example.project','another.story'])
@pytest.mark.asyncio
async def test_query_needs_no_model(runtime,monkeypatch,identity):
 p=RequestPrincipal.legacy_local();mini={'id':identity,'version':'1'}
 mounted=SimpleNamespace(capabilities=['image.workflow'],mount={'app_instance_id':'provider'})
 monkeypatch.setattr(sdk,'principal_for',lambda *a:p)
 monkeypatch.setattr(sdk,'owner',lambda *a:(SimpleNamespace(id='host'),mounted,SimpleNamespace(mounted_mini_app=lambda *a,**k:None)))
 async def transform(r,principal,instance,spec,action,data):
  assert instance=='provider' and action=='query' and data['draft']=={}
  return {'items':[]}
 monkeypatch.setattr(sdk,'transform',transform)
 result=await sdk.execute(runtime,{},SimpleNamespace(),mini,{'host':'studio','options':{'operation':'query'}})
 assert result['library_revision']=='' and result['items']==[]
 assert await sdk.describe(runtime,p,None,mini,{'options':{'operation':'query'}})=={'configuration_required':False}

@pytest.mark.asyncio
async def test_create_preserves_concurrent_draft_and_no_replay(runtime,monkeypatch):
 p=RequestPrincipal.legacy_local();mini={'id':'example.project','version':'1'};context=SimpleNamespace(session_id='caller',invocation_id='project-create')
 scope=dict(actor_id=p.actor_user_id,installation_id=p.installation_id,app_instance_id='host',studio_id='studio',mini_app_id=mini['id'])
 repo=StudioRepository(runtime.database);saved=repo.save_draft(**scope,draft={'schema':'ai2apps.mini-app-draft/v1','miniApp':mini['id'],'edited':False})
 mounted=SimpleNamespace(capabilities=['image.workflow'],mount={'app_instance_id':'provider'})
 monkeypatch.setattr(sdk,'principal_for',lambda *a:p)
 monkeypatch.setattr(sdk,'owner',lambda *a:(SimpleNamespace(id='host'),mounted,SimpleNamespace(mounted_mini_app=lambda *a,**k:None)))
 monkeypatch.setattr(runtime.extension_manager,'instance_entry',lambda *a,**k:{'app_key':'example.project'})
 async def catalog(*a):return {'items':[{'id':'test','ready':True,'size':{'mode':'fixed','presets':['1024x1024']},'qualities':['auto'],'referenceLimit':4}]}
 monkeypatch.setattr(sdk,'model_catalog',catalog)
 async def transform(r,principal,instance,spec,action,data):
  if action=='prepare':return {'identity':{'id':'p'},'plan':{'key':'fixture-key','title':'new','model':'test','size':'1024x1024','steps':[{'prompt':'one'},{'prompt':'two'}]}}
  assert action=='commit' and data['draft']['edited']
  return data['draft']|{'completed':True}
 monkeypatch.setattr(sdk,'transform',transform)
 calls=[]
 async def submit(*a,**k):calls.append(a);return {'id':'job'}
 async def follow(*a):repo.save_draft(**scope,draft=saved['draft']|{'edited':True});return {'result':{'assetIds':['x','y']},'studio_job_id':'job'}
 monkeypatch.setattr(sdk,'submit_plan',submit);monkeypatch.setattr(sdk,'follow',follow)
 monkeypatch.setattr(sdk,'deliver',lambda r,c,h,result:result|{'files':[{'artifact_id':'art'}]})
 args={'library_revision':saved['updatedAt']};spec={'host':'studio','options':{'operation':'create'}}
 result=await sdk.execute(runtime,args,context,mini,spec)
 assert result['history_saved'] and repo.get_draft(**scope)['draft']['completed']
 assert await sdk.execute(runtime,args,context,mini,spec)==result and len(calls)==1
 with pytest.raises(Exception,match='Project changed'):await sdk.execute(runtime,args,SimpleNamespace(session_id='caller',invocation_id='other'),mini,spec)
