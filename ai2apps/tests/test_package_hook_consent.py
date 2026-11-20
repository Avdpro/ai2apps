"""Actual signed archive install, SQLite consent, source checks and host delivery.

The event/detail provider is a fixture. No Cloud publication or private data is used.
"""
import asyncio
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import uuid
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from ai2apps.events.business import EventType
from ai2apps.events.hooks import HookError
from ai2apps.extensions import UnitKind
from ai2apps.identity import RequestPrincipal
from ai2apps.packages.hook_contract import declaration,SCHEMA,HANDLER
from test_app_interactions import runtime
from test_event_hook_execution import env,settled

spec=importlib.util.spec_from_file_location('signed_hook_test_helpers',Path(__file__).parents[2]/'tests/test_ai2apps_extensions.py')
helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)

@pytest.fixture
async def package(env,tmp_path):
 r,h,stats,emit,*_=env;private=Ed25519PrivateKey.generate();helpers._publisher(r,private)
 manifest=helpers._app();manifest['id']='example.hook-observer';manifest['name']='Hook acceptance fixture'
 permissions={'schema':SCHEMA,'handler':HANDLER,'event_types':['sample.record.changed'],'scopes':['subjects'],'background':True,'details':True,'actions':['notification.local']}
 manifest['event_hooks']=deepcopy(permissions)
 manifest['mini_apps']=[{'schema':'ai2apps.mini-app/v1','id':'example.hook-mini','name':'Hook Mini fixture','version':'1.0.0','kind':'project',
  'entry':{'kind':'sandbox','resource':'ui/hook.html','placements':['sidebar']},'placements':[{'studio':'ai2apps.video-studio','category':'audio'}],
  'requirements':{'capabilities':['events.subscribe','events.background']},'event_hooks':deepcopy(permissions)}]
 resources={'ui/package_events.js':(Path(__file__).parents[1]/'web/static/js/package_events.js').read_bytes(),'ui/entry.html':b'<main>Signed fixture</main><script src="package_events.js"></script>','ui/mini.json':b'{}','ui/hook.html':b'<main>Mini fixture</main>'}
 async def install(version=None,change=None):
  if version:manifest['version']=version
  if change:change(manifest)
  archive,_=helpers._write_bundle(tmp_path,private,manifest,'.ai2app',resources)
  await r.extension_manager.install(archive,approve_review=True)
 await install()
 instance,_,_=r.extension_manager.launch_app(manifest['id'])
 studio,home,_=r.extension_manager.launch_app('ai2apps.video-studio')
 def mount():return r.extension_manager.mount_studio_mini_app('ai2apps.video-studio','example.hook-mini',placement='sidebar',interaction_session_id=home.id,context={'studioInstanceId':studio.id})
 mounted=mount();p=RequestPrincipal.legacy_local();service=r.package_hooks
 def proposal(**kw):return {'event_type':'sample.record.changed','subjects':['r1'],'request_id':uuid.uuid4().hex,**kw}
 def approve(request):return service.decide(p,request['request_id'],'approve',service.review('local',request['request_id'])['review_hash'],uuid.uuid4().hex)
 return SimpleNamespace(r=r,h=h,s=service,stats=stats,emit=emit,p=p,instance=instance.id,mounted=mounted,manifest=manifest,install=install,mount=mount,proposal=proposal,approve=approve)

@pytest.mark.asyncio
async def test_install_proposal_and_generic_save_never_grant_permission(package):
 f=package;assert f.h.rules('local')==[]
 request=f.s.request_app(f.p,f.instance,f.proposal(read_details=True));assert set(request)=={'status','request_id','requires_user_consent'}
 assert not f.h.rules('local');assert f.s.grants('local')['items']==[]
 f.emit();f.h.scan();assert (await f.s.inbox(f.p,f.s.current('local',f.instance)))['items']==[]
 with f.r.database.transaction() as db:preview=db.execute('SELECT preview_ref FROM package_hook_requests').fetchone()[0]
 with pytest.raises(HookError,match='consent'):f.h.save('local',preview,'forged-direct-save')
 grant=f.approve(request);assert grant['status']=='approved'
 assert f.approve(request)==grant
 assert len(f.h.rules('local'))==1
 assert f.stats['reads']==0

@pytest.mark.asyncio
async def test_foreground_aaat_detail_is_opt_in_cached_revalidated_and_revocable(package):
 f=package;req=f.s.request_app(f.p,f.instance,f.proposal(read_details=True));grant=f.approve(req)
 f.emit();f.h.scan();b=f.s.current('local',f.instance);items=(await f.s.inbox(f.p,b))['items'];assert len(items)==1
 assert 'result' not in items[0] and f.stats['reads']==0
 delivery=items[0]['delivery_id'];detail=await f.s.inbox(f.p,b,detail=delivery);assert detail['n']==1
 assert await f.s.inbox(f.p,b,detail=delivery)==detail and f.stats['reads']==1
 await f.s.inbox(f.p,b,ack=delivery);assert not (await f.s.inbox(f.p,b))['items']
 f.s.revoke('local',grant['grant_id'])
 with pytest.raises(PermissionError):await f.s.inbox(f.p,b,detail=delivery)
 with pytest.raises(HookError):f.h.change('local',grant['rule_id'],'resume',1,'resume-revoked-grant')

@pytest.mark.asyncio
async def test_metadata_cannot_borrow_detail_permission_or_mini_app_grant(package):
 f=package;grant=f.approve(f.s.request_app(f.p,f.instance,f.proposal()))
 f.emit();f.h.scan();b=f.s.current('local',f.instance);delivery=(await f.s.inbox(f.p,b))['items'][0]['delivery_id']
 with pytest.raises(PermissionError):await f.s.inbox(f.p,b,detail=delivery)
 mini=f.s.mini_binding(f.p,'ai2apps.video-studio',f.mounted['id'])
 assert (await f.s.inbox(f.p,mini))['items']==[]
 with pytest.raises(PermissionError):await f.s.inbox(f.p,mini,ack=delivery)
 req=f.s.request_mini(f.p,'ai2apps.video-studio',f.mounted['id'],f.proposal());second=f.approve(req)
 assert second['grant_id']!=grant['grant_id'];f.emit();f.h.scan();assert len((await f.s.inbox(f.p,mini))['items'])==1
 with pytest.raises(Exception):f.s.current('foreign-actor',f.instance)

@pytest.mark.asyncio
async def test_background_metadata_handler_does_not_read_details(package):
 f=package;grant=f.approve(f.s.request_app(f.p,f.instance,f.proposal(background=True)))
 f.emit();await f.r.start_background_tasks(retention_interval_seconds=60)
 try:
  row=await settled(f.r,{'id':grant['rule_id']});assert json.loads(row['result_json'])['handler']==HANDLER
  assert f.stats['reads']==0
  assert len((await f.s.inbox(f.p,f.s.current('local',f.instance)))['items'])==1
 finally:await f.r.stop_background_tasks()

@pytest.mark.asyncio
async def test_background_details_and_frozen_self_notification(package):
 f=package;grant=f.approve(f.s.request_app(f.p,f.instance,f.proposal(background=True,read_details=True,actions=[{'registration':'notification.local','arguments':{'title':'Fixture notice','include_review':True}}])))
 f.emit();await f.r.start_background_tasks(retention_interval_seconds=60)
 try:
  row=await settled(f.r,{'id':grant['rule_id']});result=json.loads(row['result_json']);assert result['details']['n']==1 and len(result['actions'])==1
  assert f.stats['reads']==1
 finally:await f.r.stop_background_tasks()

@pytest.mark.asyncio
async def test_compatible_upgrade_retains_scope_major_upgrade_and_rollback_do_not(package):
 f=package;grant=f.approve(f.s.request_app(f.p,f.instance,f.proposal()));ref=grant['grant_id']
 await f.install('1.1.0');assert f.s.grants('local')['items'][0]['state']=='active'
 with f.r.database.transaction() as db:
  row=db.execute('SELECT accepted_release_json,scope_hash FROM package_hook_grants WHERE id=?',(ref,)).fetchone();assert json.loads(row[0])['version']=='1.1.0';hash=row[1]
 await f.install('2.0.0');assert f.s.grants('local')['items'][0]['state']=='needs_consent'
 await f.install('1.1.0');assert f.s.grants('local')['items'][0]['state']=='needs_consent'
 with f.r.database.transaction() as db:assert db.execute('SELECT scope_hash FROM package_hook_grants WHERE id=?',(ref,)).fetchone()[0]==hash

@pytest.mark.asyncio
async def test_permission_change_pending_upgrade_disable_and_expiry(package):
 f=package;pending=f.s.request_app(f.p,f.instance,f.proposal())
 await f.install('1.0.1')
 with pytest.raises(HookError,match='changed'):f.approve(pending)
 grant=f.approve(f.s.request_app(f.p,f.instance,f.proposal()));f.r.extension_manager.set_enabled(UnitKind.APP,f.manifest['id'],False)
 assert f.s.grants('local')['items'][0]['state']=='revoked'
 f.r.extension_manager.set_enabled(UnitKind.APP,f.manifest['id'],True);assert f.s.grants('local')['items'][0]['state']=='revoked'
 new=f.approve(f.s.request_app(f.p,f.instance,f.proposal(expires_in=60)));f.h.clock=lambda:10**12
 assert f.s.grants('local')['items'][0]['state']=='expired'

@pytest.mark.asyncio
async def test_declaration_bounds_ids_denial_and_http_host_origin(package):
 from fastapi import FastAPI
 from httpx import AsyncClient,ASGITransport
 from ai2apps.api.package_hooks import create_package_hook_router
 f=package
 with pytest.raises(PermissionError):f.s.request_app(f.p,f.instance,f.proposal(event_type='messager.message.received'))
 with pytest.raises(PermissionError):f.s.request_app(f.p,f.instance,f.proposal(actions=[{'registration':'todo.create','arguments':{'title':'No'}}],background=True))
 proposal=f.proposal();request=f.s.request_app(f.p,f.instance,proposal);assert f.s.request_app(f.p,f.instance,proposal)==request
 with pytest.raises(HookError):f.s.request_app(f.p,f.instance,{**proposal,'read_details':True})
 app=FastAPI();app.include_router(create_package_hook_router(lambda:f.r,lambda:f.p))
 async with AsyncClient(transport=ASGITransport(app=app),base_url='http://host') as client:
  review=(await client.get('/package-hooks/requests/'+request['request_id'])).json()
  body={'review_hash':review['review_hash'],'request_id':'host-decision-001'};url='/package-hooks/requests/'+request['request_id']+'/approve'
  assert (await client.post(url,json=body,headers={'Origin':'null'})).status_code==403
  assert (await client.post(url,json=body)).status_code==403
  assert (await client.post(url,json=body,headers={'Origin':'http://other'})).status_code==403
  assert not f.h.rules('local')
  assert (await client.post(url,json=body,headers={'Origin':'http://host'})).json()['status']=='approved'

@pytest.mark.parametrize('change',[
 lambda d:d.update(event_types=['*']),lambda d:d.update(handler='arbitrary.callback'),lambda d:d.update(background='yes'),lambda d:d.update(approved=True),lambda d:d.update(scopes=[{}])])
def test_signed_manifest_cannot_declare_wildcards_handlers_or_authority(change):
 d={'schema':SCHEMA,'handler':HANDLER,'event_types':['example.changed']};change(d)
 with pytest.raises(ValueError):declaration(d)

@pytest.mark.asyncio
async def test_signed_permission_enlargement_cannot_extend_existing_grant(package):
 f=package;f.approve(f.s.request_app(f.p,f.instance,f.proposal()))
 await f.install('1.0.1',lambda m:m['event_hooks'].update(actions=['notification.local','todo.create']))
 assert f.s.grants('local')['items'][0]['state']=='needs_consent'
 with pytest.raises(HookError):f.s.control('local',f.s.grants('local')['items'][0]['id'],'resume',1,'resume-after-enlarge')

@pytest.mark.asyncio
async def test_pause_resume_is_scope_bound_and_skips_backlog(package):
 f=package;grant=f.approve(f.s.request_app(f.p,f.instance,f.proposal()))
 pause=f.s.control('local',grant['grant_id'],'pause',1,'pause-consent-01');f.emit();f.h.scan()
 assert f.s.grants('local')['items'][0]['state']=='paused'
 f.s.control('local',grant['grant_id'],'resume',pause['revision'],'resume-consent-01');f.emit(2);f.h.scan()
 assert [i['event']['data']['n'] for i in (await f.s.inbox(f.p,f.s.current('local',f.instance)))['items']]==[2]

@pytest.mark.asyncio
async def test_deny_is_idempotent_and_cannot_be_changed_to_approve(package):
 f=package;req=f.s.request_app(f.p,f.instance,f.proposal());review=f.s.review('local',req['request_id']);key='deny-stable-key'
 result=f.s.decide(f.p,req['request_id'],'deny',review['review_hash'],key)
 assert f.s.decide(f.p,req['request_id'],'deny',review['review_hash'],key)==result
 with pytest.raises(HookError):f.approve(req)
 assert not f.h.rules('local')

@pytest.mark.asyncio
async def test_deleted_rule_stays_deleted_when_grant_is_revoked(package):
 f=package;grant=f.approve(f.s.request_app(f.p,f.instance,f.proposal()))
 f.h.change('local',grant['rule_id'],'delete',1,'delete-rule-stable')
 f.s.revoke('local',grant['grant_id']);assert not f.h.rules('local')

@pytest.mark.asyncio
async def test_source_or_detail_provider_revoke_blocks_cached_details(package):
 f=package;f.approve(f.s.request_app(f.p,f.instance,f.proposal(read_details=True)))
 f.emit();f.h.scan();b=f.s.current('local',f.instance);delivery=(await f.s.inbox(f.p,b))['items'][0]['delivery_id']
 await f.s.inbox(f.p,b,detail=delivery);assert f.stats['reads']==1
 provider=f.r.app_capability_router.providers['different.reader.detail']
 f.r.app_capability_router.providers[provider.id]=replace(provider,version='2')
 with pytest.raises(PermissionError):await f.s.inbox(f.p,b,detail=delivery)
 assert f.stats['reads']==1

@pytest.mark.asyncio
async def test_invalid_hook_declaration_is_rejected_by_signed_installer(package):
 from ai2apps.extensions import ExtensionError
 f=package
 with pytest.raises(ExtensionError):await f.install('1.0.1',lambda m:m['event_hooks'].update(handler='execute.anything'))
 assert f.s.current('local',f.instance)['release']['version']=='1.0.0'

@pytest.mark.asyncio
async def test_actual_studio_mount_http_requests_details_and_ack(package):
 from fastapi import FastAPI
 from httpx import AsyncClient,ASGITransport
 from ai2apps.api.router import create_ai2apps_router
 f=package;app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:f.r,principal_provider=lambda:f.p))
 base='/v1/platform/studios/ai2apps.video-studio/mini-app-mounts/'+f.mounted['id']
 async with AsyncClient(transport=ASGITransport(app=app),base_url='http://host',headers={'Origin':'http://host'}) as client:
  requested=await client.post(base+'/events/preview',json=f.proposal(read_details=True));assert requested.status_code==200,requested.text
  pending=requested.json();assert pending['requires_user_consent'] and 'preview_ref' not in pending
  assert (await client.get(base+'/events')).json()=={'items':[]}
  f.approve(pending);f.emit();f.h.scan()
  response=await client.get(base+'/events');assert response.status_code==200,response.text
  delivery=response.json()['items'][0]['delivery_id']
  detail_path='/v1/platform/package-hooks/mini-apps/ai2apps.video-studio/'+f.mounted['id']+'/deliveries/'+delivery+'/details'
  detail=await client.post(detail_path);assert detail.status_code==200,detail.text
  assert detail.json()['n']==1
  assert (await client.post(base+'/events/'+delivery+'/ack')).json()['acknowledged']==delivery
  assert not (await client.get(base+'/events')).json()['items']

@pytest.mark.asyncio
async def test_app_sdk_is_a_verified_relative_package_asset(package):
 from ai2apps.extensions.sandbox_document import inline_sandbox_assets
 f=package;m=f.r.extension_manager
 path=m.resolve_app_resource(f.instance,'ui/entry.html',principal=f.p)
 document=inline_sandbox_assets(path.read_text(),'ui/entry.html',lambda asset:m.resolve_app_resource(f.instance,asset,principal=f.p).read_text())
 assert 'AI2AppsPackageEvents' in document and 'src="package_events.js"' not in document

@pytest.mark.asyncio
async def test_request_quota_is_per_package_and_rejection_leaves_no_orphan_preview(package):
 f=package;requests=[f.s.request_app(f.p,f.instance,f.proposal()) for _ in range(10)]
 with pytest.raises(ValueError,match='ten pending'):f.s.request_app(f.p,f.instance,f.proposal())
 with f.r.database.transaction() as db:assert db.execute('SELECT count(*) FROM hook_previews WHERE consumed=0').fetchone()[0]==10
 item=f.s.review('local',requests[0]['request_id']);f.s.decide(f.p,item['id'],'deny',item['review_hash'],'denied-quota-request')
 f.s.request_app(f.p,f.instance,f.proposal())
 with f.r.database.transaction() as db:assert db.execute('SELECT count(*) FROM hook_previews WHERE consumed=0').fetchone()[0]==10
