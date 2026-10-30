import asyncio
import io
import json
from types import SimpleNamespace
import pytest
from PIL import Image, ImageDraw
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ai2apps.api.knowledge import create_knowledge_router
from ai2apps.identity import RequestPrincipal,MemberRole
from ai2apps.knowledge import KnowledgeStore,KnowledgeScope,KnowledgeConflictError,KnowledgeAccessError
from ai2apps.knowledge.ocr import KnowledgeOCRManager,select_model,recognize_result
from ai2apps.knowledge.ocr_store import KnowledgeOCRStore
from ai2apps.storage import PlatformDatabase


def vision(id,**kw):return {'id':id,'model_type':'vlm','capabilities':['image_recognition'],'source_type':'local_runtime',**kw}
def text(id):return {'id':id,'model_type':'llm','capabilities':['work']}
def principal(actor='alice'):
 return RequestPrincipal(actor_user_id=actor,installation_id='installation',organization_id='organization',
     billing_account_id='billing',role=MemberRole.MEMBER,membership_epoch=1)


@pytest.mark.parametrize('private,normal,api,expected',[
 ({'work_simple':'p-low','work_standard':'p-mid'},{'image_recognition':'normal'},'api','p-low'),
 ({'work_simple':'text-only','work_standard':'p-mid'},{'image_recognition':'normal'},'api','p-mid'),
 ({'work_simple':'text-only'},{'image_recognition':'normal','work_simple':'n-low'},'api','normal'),
 ({},{'image_recognition':'text-only','work_simple':'n-low','work_standard':'n-mid'},'api','n-low'),
 ({},{'work_simple':'text-only','work_standard':'n-mid'},'api','n-mid'),
 ({},{'work_standard':'text-only'},'api','api'),
 ({},{},'text-only',None),
])
def test_explicit_order_and_multimodal_gate(private,normal,api,expected):
 catalog=[vision(x) for x in ['p-low','p-mid','normal','n-low','n-mid','api']]+[text('text-only')]
 s=select_model(catalog,private,normal,api)
 assert (s.model_id if s else None)==expected
 if s:assert s.private==(expected in {'p-low','p-mid'})


def test_dedicated_ocr_has_priority_without_name_inference():
 catalog=[vision('arbitrary',capabilities=['image_recognition','ocr']),vision('p-low'),vision('OXR-name-only')]
 s=select_model(catalog,{'work_simple':'p-low'},{},None)
 assert s.model_id=='arbitrary' and s.dedicated
 # A package's local loopback endpoint alone cannot prove it keeps images private.
 catalog[0]['source_type']='package'
 assert select_model(catalog,{'work_simple':'p-low'},{},None).model_id=='p-low'
 assert select_model(catalog,{'work_simple':'p-low'},{},None,dedicated_ids={'arbitrary'}).model_id=='arbitrary'


class Gateway:
 chat_provider_ready=True
 def __init__(self,catalog):self.catalog=catalog;self.calls=[];self.error=None;self.wait=None
 async def chat_catalog(self):return self.catalog
 async def invoke_chat_json(self,payload,*,context):
  self.calls.append((payload['model'],context))
  if self.wait:await self.wait.wait()
  if self.error:raise self.error
  return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'text':'ZX314 recognized text','description':'A test document.'})}}]}


@pytest.fixture
def env(tmp_path):
 db=PlatformDatabase(tmp_path/'platform.sqlite3');db.initialize();kb=KnowledgeStore(db)
 p=principal();bucket=kb.create_bucket(p,name='images')
 image=Image.new('RGB',(600,250),'white');ImageDraw.Draw(image).text((35,55),'ZX314',fill='black')
 data=io.BytesIO();image.save(data,format='PNG');raw=data.getvalue()
 def add(name='image.png',scope=None):
  b=bucket if scope is None else kb.create_bucket(p,name='shared',scope=scope)
  return kb.import_stream(p,io.BytesIO(raw),name=name,media_type='image/png',bucket_id=b.id)[0]
 routes={'privacy':{},'normal':{'image_recognition':'ordinary'}}
 manager=SimpleNamespace(default_models=lambda profile:routes[profile],cloud_default_policy=lambda:{})
 gateway=Gateway([vision('ordinary')]);runtime=SimpleNamespace(config=SimpleNamespace(paths=None),knowledge=kb,database=db,model_manager=manager,
  model_invocations=gateway,registry_packages=None,package_repository=None,knowledge_package_runtime=None)
 worker=KnowledgeOCRManager(runtime);worker.principal=lambda row:p
 return SimpleNamespace(db=db,kb=kb,p=p,bucket=bucket,add=add,routes=routes,gateway=gateway,runtime=runtime,worker=worker,
                        store=worker.store,raw=raw)


@pytest.mark.asyncio
async def test_import_waits_for_specific_consent_then_indexes_once(env):
 item=env.add();row=env.store.next();assert row['status']=='queued'
 await env.worker.process(row)
 assert not env.gateway.calls
 waiting=env.store.get(env.p,item.id);assert waiting['status']=='awaiting_consent'
 env.store.decide(env.p,item.id,revision=waiting['revision'],token=waiting['consent_token'],allow=True)
 with pytest.raises(KnowledgeConflictError):env.store.decide(env.p,item.id,revision=waiting['revision'],token=waiting['consent_token'],allow=True)
 await env.worker.process(env.store.next())
 assert len(env.gateway.calls)==1
 current=env.kb.get_item(env.p,item.id);assert 'ZX314' in current.text and current.revision==2
 assert env.kb.search(env.p,'ZX314')
 assert env.store.get(env.p,item.id)['text']=='ZX314 recognized text'
 # Duplicate files reuse the completed task, with no second call.
 assert env.add('duplicate.png').id==item.id
 assert env.store.next() is None


@pytest.mark.asyncio
async def test_private_low_is_automatic_and_failure_never_discloses(env):
 item=env.add();env.routes['privacy']['work_simple']='private-low';env.gateway.catalog.append(vision('private-low'))
 env.gateway.error=RuntimeError('Provider failed; image bytes and tokens must not be logged')
 await env.worker.process(env.store.next())
 assert [x[0] for x in env.gateway.calls]==['private-low']
 row=env.store.get(env.p,item.id);assert row['status']=='failed' and row['error']=='recognition_failed'
 assert env.store.next() is None
 assert env.kb.get_item(env.p,item.id).revision==1


@pytest.mark.asyncio
async def test_decline_is_durable_and_does_not_run_after_recovery(env):
 item=env.add();await env.worker.process(env.store.next());row=env.store.get(env.p,item.id)
 env.store.decide(env.p,item.id,revision=row['revision'],token=row['consent_token'],allow=False)
 env.store.recover();assert env.store.next() is None and not env.gateway.calls
 assert env.store.get(env.p,item.id)['status']=='skipped'
 assert env.kb.asset_path(env.p,item.id)[1].exists()


@pytest.mark.asyncio
async def test_route_change_invalidates_approval_before_any_send(env):
 item=env.add();await env.worker.process(env.store.next());row=env.store.get(env.p,item.id)
 env.store.decide(env.p,item.id,revision=row['revision'],token=row['consent_token'],allow=True)
 env.gateway.catalog.append(vision('replacement'));env.routes['normal']['image_recognition']='replacement'
 await env.worker.process(env.store.next());new=env.store.get(env.p,item.id)
 assert new['status']=='awaiting_consent' and new['model_id']=='replacement'
 assert new['consent_token']!=row['consent_token'] and not env.gateway.calls


@pytest.mark.asyncio
async def test_delete_before_execution_never_sends(env):
 item=env.add();await env.worker.process(env.store.next());row=env.store.get(env.p,item.id)
 env.store.decide(env.p,item.id,revision=row['revision'],token=row['consent_token'],allow=True)
 env.kb.delete_item(env.p,item.id,expected_revision=1)
 await env.worker.process(env.store.next());assert not env.gateway.calls


@pytest.mark.asyncio
async def test_cancel_inflight_prevents_index_commit_and_does_not_replay(env):
 item=env.add();env.routes['privacy']['work_simple']='ordinary';env.gateway.wait=asyncio.Event()
 task=asyncio.create_task(env.worker.process(env.store.next()))
 for _ in range(200):
  if env.gateway.calls:break
  await asyncio.sleep(.01)
 assert env.gateway.calls
 row=env.store.get(env.p,item.id);env.store.control(env.p,item.id,revision=row['revision'],action='cancel')
 env.gateway.wait.set();await task
 assert env.store.get(env.p,item.id)['status']=='cancelled'
 assert env.kb.get_item(env.p,item.id).revision==1
 assert not env.kb.search(env.p,'ZX314')


def test_recovery_does_not_replay_running_paid_call(env):
 item=env.add();row=env.store.next();env.store.transition(row,'running',run_token='previous-process')
 env.store.recover();assert env.store.next() is None
 assert env.store.get(env.p,item.id)['error']=='interrupted'


def test_shared_image_consent_is_owner_only(env):
 item=env.add(scope=KnowledgeScope.INSTALLATION)
 assert env.kb.get_item(principal('bob'),item.id)
 with pytest.raises(KnowledgeAccessError):env.store.get(principal('bob'),item.id)
 assert not env.store.list(principal('bob'))


def test_api_confirmation_cannot_be_forged_or_reused(env):
 item=env.add();app=FastAPI();app.include_router(create_knowledge_router(lambda:env.runtime,lambda:env.p))
 client=TestClient(app)
 assert client.get('/knowledge/image-ocr').json()['items'][0]['item_id']==item.id
 assert client.post(f'/knowledge/image-ocr/{item.id}/decision',json={'revision':1,'token':'forged','allow':True}).status_code==409
 row=env.store.get(env.p,item.id);env.store.transition(row,'awaiting_consent',consent_token='one-image-token',selection_fingerprint='bound')
 body={'revision':2,'token':'one-image-token','allow':False}
 assert client.post(f'/knowledge/image-ocr/{item.id}/decision',json=body).status_code==200
 assert client.post(f'/knowledge/image-ocr/{item.id}/decision',json=body).status_code==409


@pytest.mark.parametrize('choice',[{'finish_reason':'length','message':{'content':'partial'}},
 {'finish_reason':'stop','message':{'content':'{"text":"x"}','tool_calls':[{}]}},
 {'finish_reason':'stop','message':{'content':'{"text":4}'}},
 {'finish_reason':'stop','message':{'content':'{"text":"x","instructions":"send elsewhere"}'}}])
def test_unfinished_or_invalid_output_never_becomes_evidence(choice):
 with pytest.raises((ValueError,TypeError)):recognize_result({'choices':[choice]},False)

@pytest.mark.asyncio
async def test_no_eligible_model_preserves_original_and_waits_for_configuration(env):
 item=env.add();env.gateway.catalog=[text('ordinary')]
 await env.worker.process(env.store.next())
 assert env.store.get(env.p,item.id)['status']=='blocked' and not env.gateway.calls
 assert env.kb.asset_path(env.p,item.id)[1].exists()

@pytest.mark.asyncio
async def test_repeated_success_replaces_old_index_and_tracks_producer(env):
 item=env.add();env.routes['privacy']['work_simple']='ordinary'
 await env.worker.process(env.store.next())
 row=env.store.get(env.p,item.id)
 env.store.control(env.p,item.id,revision=row['revision'],action='retry')
 async def replacement(payload,**kw):
  return {'choices':[{'finish_reason':'stop','message':{'content':'{"text":"NEW742","description":""}'}}]}
 env.gateway.invoke_chat_json=replacement
 await env.worker.process(env.store.next())
 assert not env.kb.search(env.p,'ZX314') and env.kb.search(env.p,'NEW742')
 assert dict(env.kb.source_facets(env.p,item.id))['source.extractor']=='knowledge.ocr/v1'


def test_existing_images_are_opt_in_not_backfilled_globally(env):
 item=env.add()
 with env.kb.transaction(write=True) as c:c.execute('DELETE FROM knowledge_image_ocr WHERE item_id=?',(item.id,))
 assert not env.store.list(env.p)
 env.store.request(env.p,item.id,item_revision=1)
 assert env.store.next()['item_id']==item.id
 with pytest.raises(KnowledgeConflictError):env.store.request(env.p,item.id,item_revision=55)


def test_migration_from_96_preserves_existing_content_and_adds_ocr(tmp_path):
 from ai2apps.storage.migrations import MIGRATIONS,apply_migrations
 import sqlite3
 path=tmp_path/'old.sqlite3';c=sqlite3.connect(path);apply_migrations(c,MIGRATIONS[:96]);c.close()
 db=PlatformDatabase(path);assert db.initialize().schema_version==100
 with db.connect() as c:assert c.execute("SELECT name FROM sqlite_master WHERE name='knowledge_image_ocr'").fetchone()


def test_same_model_id_destination_change_invalidates_fingerprint():
 catalog=[vision('cloud/custom/vision')]
 a=select_model(catalog,{}, {'image_recognition':'cloud/custom/vision'},None,bindings={'cloud/custom/vision':{'base_url':'https://first.example'}})
 b=select_model(catalog,{}, {'image_recognition':'cloud/custom/vision'},None,bindings={'cloud/custom/vision':{'base_url':'https://second.example'}})
 assert a.fingerprint!=b.fingerprint


@pytest.mark.asyncio
async def test_model_change_during_decode_requeues_without_disclosure(env,monkeypatch):
 import ai2apps.knowledge.ocr as module
 item=env.add();await env.worker.process(env.store.next());row=env.store.get(env.p,item.id)
 env.store.decide(env.p,item.id,revision=row['revision'],token=row['consent_token'],allow=True)
 env.gateway.catalog.append(vision('other'))
 def decode(*args):
  env.routes['normal']['image_recognition']='other'
  return 'data:image/png;base64,fixture'
 monkeypatch.setattr(module,'prepare_image',decode)
 await env.worker.process(env.store.next())
 assert not env.gateway.calls and env.store.next()
 await env.worker.process(env.store.next())
 row=env.store.get(env.p,item.id);assert row['status']=='awaiting_consent' and row['model_id']=='other'

@pytest.mark.asyncio
async def test_restart_requires_fresh_consent_for_approved_but_unstarted_image(env):
 item=env.add();await env.worker.process(env.store.next())
 row=env.store.get(env.p,item.id)
 env.store.decide(env.p,item.id,revision=row['revision'],token=row['consent_token'],allow=True)
 env.store.recover()
 await env.worker.process(env.store.next())
 assert not env.gateway.calls
 fresh=env.store.get(env.p,item.id)
 assert fresh['status']=='awaiting_consent' and fresh['consent_token']!=row['consent_token']

@pytest.mark.asyncio
async def test_auto_bucket_uses_content_and_restricts_model_output_to_private_buckets(env):
 from ai2apps.knowledge.routing import KnowledgeBucketRouter
 item=env.kb.create_text_item(env.p,title='Watch report',text='Watch movement research',bucket_id='auto')
 router=env.worker.bucket_router
 assert router.list(env.p)[0]['status']=='pending'
 env.routes['privacy']['work_simple']='ordinary'
 calls=[]
 async def classify(payload,**kw):
  calls.append(payload)
  return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'bucket_id':env.bucket.id})}}]}
 env.gateway.invoke_chat_json=classify
 await router.tick()
 assert router.list(env.p)[0]['status']=='completed'
 assert env.kb.bucket_ids_for_item(env.p,item.id)==(env.bucket.id,)
 assert 'Watch movement research' in calls[0]['messages'][1]['content']

@pytest.mark.asyncio
async def test_auto_bucket_nonprivate_requires_fresh_one_shot_consent(env):
 item=env.kb.create_text_item(env.p,title='Note',text='private words',bucket_id='auto')
 env.routes['normal']['work_simple']='ordinary'
 router=env.worker.bucket_router
 await router.tick();row=router.list(env.p)[0]
 assert row['status']=='awaiting_consent' and not env.gateway.calls
 with pytest.raises(ValueError):router.decide(env.p,item.id,'forged',True)
 router.decide(env.p,item.id,row['token'],False)
 await router.tick();assert not env.gateway.calls
 assert router.list(env.p)[0]['status']=='skipped'

@pytest.mark.asyncio
async def test_auto_image_waits_for_ocr_not_filename(env):
 item,_=env.kb.import_stream(env.p,io.BytesIO(env.raw),name='watch-report.png',bucket_id='auto',media_type='image/png')
 env.routes['privacy']['work_simple']='ordinary'
 await env.worker.bucket_router.tick()
 assert not env.gateway.calls
 assert env.worker.bucket_router.list(env.p)[0]['status']=='pending'

def test_auto_import_job_preserves_target_policy(env):
 job=env.kb.create_import_job(env.p,bucket_id='auto',filenames=['notes.md'])
 with env.kb.transaction() as c:row=c.execute('SELECT auto_bucket,bucket_id FROM knowledge_import_jobs WHERE id=?',(job['id'],)).fetchone()
 assert row['auto_bucket']==1 and row['bucket_id']!='auto'

@pytest.mark.asyncio
async def test_auto_audio_uses_private_asr_before_bucket_selection(env,monkeypatch):
 import ai2apps.audio_codecs as codecs
 monkeypatch.setattr(codecs,'decode_audio_to_wav',lambda *a,**kw:b'wav-fixture')
 item,_=env.kb.import_stream(env.p,io.BytesIO(b'audio-fixture'),name='recording.wav',media_type='audio/wav',bucket_id='auto')
 env.gateway.catalog=[{'id':'asr','model_type':'audio','package_service':'asr-package','capabilities':['speech_recognition']}]
 env.runtime.package_repository=SimpleNamespace(active=lambda service:SimpleNamespace(permissions={'network':{'outbound':False}}))
 calls=[]
 async def transcribe(model,operation,**kw):
  calls.append((model,operation));return SimpleNamespace(status_code=200,body=b'{"text":"Watch research transcript"}')
 env.gateway.invoke_background_multipart=transcribe
 await env.worker.bucket_router.tick()
 assert calls==[('asr','audio_transcription')]
 assert env.kb.get_item(env.p,item.id).text=='Watch research transcript'
 assert env.worker.bucket_router.list(env.p)[0]['status']=='pending'

@pytest.mark.asyncio
async def test_auto_bucket_rejects_unknown_model_bucket(env):
 item=env.kb.create_text_item(env.p,title='Note',text='content',bucket_id='auto')
 before=env.kb.bucket_ids_for_item(env.p,item.id)
 env.routes['privacy']['work_simple']='ordinary'
 async def classify(*a,**kw):return {'choices':[{'finish_reason':'stop','message':{'content':'{"bucket_id":"shared-or-forged"}'}}]}
 env.gateway.invoke_chat_json=classify
 await env.worker.bucket_router.tick()
 assert env.worker.bucket_router.list(env.p)[0]['status']=='failed'
 assert env.kb.bucket_ids_for_item(env.p,item.id)==before

@pytest.mark.asyncio
async def test_auto_bucket_approval_runs_once_and_restart_expires_unstarted_approval(env):
 item=env.kb.create_text_item(env.p,title='Note',text='private content',bucket_id='auto')
 env.routes['normal']['work_simple']='ordinary';router=env.worker.bucket_router
 await router.tick();first=router.list(env.p)[0]
 router.decide(env.p,item.id,first['token'],True)
 router.recover();await router.tick();second=router.list(env.p)[0]
 assert second['status']=='awaiting_consent' and second['token']!=first['token'] and not env.gateway.calls
 router.decide(env.p,item.id,second['token'],True)
 calls=[]
 async def classify(*a,**kw):
  calls.append(1);return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'bucket_id':env.bucket.id})}}]}
 env.gateway.invoke_chat_json=classify
 await router.tick();await router.tick();assert calls==[1]
 assert router.list(env.p)[0]['status']=='completed'

@pytest.mark.parametrize('filename',['notes.md','notes.log','notes.yaml','script.py'])
def test_auto_text_file_extracts_content_before_routing(env,filename):
 item,_=env.kb.import_stream(env.p,io.BytesIO(b'Watch movement document ZX864'),name=filename,bucket_id='auto')
 assert 'ZX864' in item.text and env.kb.search(env.p,'ZX864')
 assert env.worker.bucket_router.list(env.p)[0]['status']=='pending'

def grouped_job(env,files,media='text/plain',title='购物单'):
 job=env.kb.create_import_job(env.p,bucket_id='auto',filenames=[n for n,_ in files],merge_record=True,record_title=title)
 for n,(_,data) in enumerate(files):env.kb.stage_import_entry(env.p,job['id'],n,io.BytesIO(data),media_type=media)
 env.kb.process_import_job(job['id'])
 return env.kb.get_import_job(env.p,job['id'])

def test_grouped_texts_are_one_searchable_record_with_ordered_originals(env):
 from ai2apps.knowledge.groups import attachments,group_content
 job=grouped_job(env,[('a.txt',b'Apples ZX111'),('b.txt',b'Bread ZX222')])
 assert job['status']=='completed'
 parent=env.kb.get_item(env.p,job['group_parent_id'])
 assert parent.title=='购物单' and 'Apples ZX111' in parent.text and 'Bread ZX222' in parent.text
 assert [i.id for i in env.kb.list_items(env.p)]==[parent.id]
 assert {h.item.id for h in env.kb.search(env.p,'ZX111')}=={parent.id}
 assert {h.item.id for h in env.kb.search(env.p,'ZX222')}=={parent.id}
 files=attachments(env.kb,env.p,parent.id)
 assert [f['name'] for f in files]==['a.txt','b.txt']
 assert env.kb.asset_path(env.p,files[1]['item_id'])[1].read_bytes()==b'Bread ZX222'
 # Internal attachments never become independent vector-search candidates.
 assert env.kb.hydrate_semantic_hit(env.p,files[0]['item_id'],excerpt='stale vector',distance=0.1) is None

def test_group_does_not_adopt_or_hide_existing_duplicate_records(env):
 existing,_=env.kb.import_stream(env.p,io.BytesIO(b'Apples ZX111'),name='a.txt',bucket_id=env.bucket.id)
 job=grouped_job(env,[('a.txt',b'Apples ZX111')])
 assert {i.id for i in env.kb.list_items(env.p)}=={existing.id,job['group_parent_id']}
 # A later ordinary import must not reuse a hidden grouped attachment.
 ordinary,_=env.kb.import_stream(env.p,io.BytesIO(b'Apples ZX111'),name='again.txt',bucket_id=env.bucket.id)
 assert ordinary.id==existing.id

def test_group_job_recovery_is_idempotent_and_preserves_title(env):
 job=grouped_job(env,[('a.txt',b'One'),('b.txt',b'Two')],title='My purchase')
 env.kb.process_import_job(job['id'])
 assert len(env.kb.list_items(env.p))==1
 with env.kb.transaction() as c:assert c.execute('SELECT COUNT(*) FROM knowledge_record_attachments').fetchone()[0]==2
 assert env.kb.get_item(env.p,job['group_parent_id']).title=='My purchase'

def test_group_parent_delete_blocks_attachment_access(env):
 from ai2apps.knowledge.groups import attachments
 job=grouped_job(env,[('a.txt',b'One')]);parent=env.kb.get_item(env.p,job['group_parent_id']);child=attachments(env.kb,env.p,parent.id)[0]['item_id']
 env.kb.delete_item(env.p,parent.id,expected_revision=parent.revision)
 with pytest.raises(Exception):env.kb.asset_path(env.p,child)
 assert not env.kb.list_items(env.p)

def test_group_ocr_updates_parent_without_duplicate_search_hits(env):
 from ai2apps.knowledge.groups import refresh_groups
 job=grouped_job(env,[('receipt.png',env.raw)],media='image/png')
 parent_id=job['group_parent_id'];row=env.store.next();assert row
 assert env.store.transition(row,'running',run_token='ocr')
 claimed={**row,'run_token':'ocr','revision':row['revision']+1,'model_id':'local-ocr'}
 assert env.store.complete(env.p,claimed,text='Shopping total ZX993 128.00',description='')
 refresh_groups(env.kb)
 assert 'ZX993' in env.kb.get_item(env.p,parent_id).text
 assert {h.item.id for h in env.kb.search(env.p,'ZX993')}=={parent_id}
 with env.kb.transaction() as c:assert c.execute('SELECT ready FROM knowledge_record_groups WHERE parent_id=?',(parent_id,)).fetchone()[0]==1

def test_two_receipt_images_aggregate_after_independent_ocr(env):
 from ai2apps.knowledge.groups import refresh_groups,attachments
 job=grouped_job(env,[('page-1.png',env.raw),('page-2.png',env.raw)],media='image/png',title='一次购物')
 parent=job['group_parent_id'];assert len(env.kb.list_items(env.p))==1
 assert len(attachments(env.kb,env.p,parent))==2
 for text in ['Apples ZX551 12.00','Bread ZX552 8.00']:
  row=env.store.next();assert row
  env.store.transition(row,'running',run_token='receipt-run')
  env.store.complete(env.p,{**row,'revision':row['revision']+1,'run_token':'receipt-run','model_id':'local-ocr'},text=text,description='')
  refresh_groups(env.kb)
 merged=env.kb.get_item(env.p,parent).text
 assert 'ZX551' in merged and 'ZX552' in merged and merged.index('page-1.png')<merged.index('page-2.png')
 assert {h.item.id for h in env.kb.search(env.p,'ZX552')}=={parent}

def test_legacy_standalone_v2_gets_group_columns(tmp_path):
 import sqlite3
 from ai2apps.knowledge.store import KnowledgeStore,_SCHEMA_V1
 from ai2apps.knowledge.ocr_store import OCR_SCHEMA
 path=tmp_path/'legacy.sqlite'
 with sqlite3.connect(path) as c:
  c.executescript(_SCHEMA_V1);c.execute(OCR_SCHEMA);c.execute('PRAGMA user_version=2')
 store=KnowledgeStore(path);store.initialize()
 with store.transaction() as c:
  assert c.execute('PRAGMA user_version').fetchone()[0]==4
  assert {'merge_record','record_title','group_parent_id','auto_bucket'}<={r[1] for r in c.execute('PRAGMA table_info(knowledge_import_jobs)')}

def test_group_recovery_does_not_reset_running_media_extraction(env):
 from ai2apps.knowledge.groups import attach,attachments
 job=grouped_job(env,[('audio.wav',b'audio-fixture')],media='audio/wav')
 parent=job['group_parent_id'];child=env.kb.get_item(env.p,attachments(env.kb,env.p,parent)[0]['item_id'])
 with env.kb.transaction(write=True) as c:c.execute("UPDATE knowledge_bucket_routing SET status='running',run_token='original-operation' WHERE item_id=?",(child.id,))
 attach(env.kb,env.p,parent,child,0)
 with env.kb.transaction() as c:
  row=c.execute('SELECT status,run_token FROM knowledge_bucket_routing WHERE item_id=?',(child.id,)).fetchone()
  assert row['status']=='running' and row['run_token']=='original-operation'


def test_group_screenshot_overlap_preserves_raw_ocr_and_evidence(env):
 from ai2apps.knowledge.groups import refresh_groups,group_content,attachments
 overlap='第一行详细记录项目甲以及相关信息 alpha\n第二行详细记录项目乙以及相关信息 beta\n第三行详细记录项目丙以及相关信息 gamma'
 job=grouped_job(env,[('one.png',env.raw),('two.png',env.raw)],media='image/png')
 for text in ['独有开头\n'+overlap,overlap+'\n独有结尾']:
  row=env.store.next();env.store.transition(row,'running',run_token='overlap')
  env.store.complete(env.p,{**row,'revision':row['revision']+1,'run_token':'overlap','model_id':'local-ocr'},text=text,description='')
 refresh_groups(env.kb)
 parent=job['group_parent_id']
 assert env.kb.get_item(env.p,parent).text.count('第一行详细')==1
 children=attachments(env.kb,env.p,parent)
 assert all('第一行详细' in env.kb.get_item(env.p,f['item_id']).text for f in children)
 assert '重叠 3 行' in group_content(env.kb,env.p,parent).body.decode()
 with env.kb.transaction(write=True) as c:c.execute('UPDATE knowledge_import_jobs SET detect_overlap=0 WHERE id=?',(job['id'],))
 refresh_groups(env.kb)
 assert env.kb.get_item(env.p,parent).text.count('第一行详细')==2
