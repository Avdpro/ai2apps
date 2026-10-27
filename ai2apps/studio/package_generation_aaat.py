"""Studio-owned exports for Package generation; reuse original queues/output owners."""
from copy import deepcopy
import asyncio
import json
import logging
from ai2apps.services import ToolProviderError
from ai2apps.services.aaat import principal_for

VOICE='ai2apps.readaloud'
VIDEO='ai2apps.video-studio'
IMAGINE='ai2apps.imagine-studio'
AUDIO={
 'voice.generate_music':('ai2apps.audio-generation.music','audio.music_generation','生成音乐'),
 'voice.generate_sound_effects':('ai2apps.audio-generation.sfx','audio.sound_effects_generation','生成音效'),
 'voice.generate_song':('ai2apps.audio-generation.song','audio.song_generation','生成歌曲')}
ASSET={'type':'string','minLength':1,'maxLength':256,'x-ai2apps-asset':{'storage':'artifact','accept':'image/*,audio/*','references':True}}
AUDIO_SCHEMA={'type':'object','additionalProperties':False,'required':['model','prompt'],'properties':{
 'model':{'type':'string','minLength':1},'prompt':{'type':'string','minLength':1,'maxLength':2000},
 'lyrics':{'type':'string','maxLength':4096},'duration':{'type':'number','minimum':1,'maximum':120},
 'seed':{'type':'integer','minimum':0,'maximum':4294967295},'steps':{'type':'integer','minimum':1,'maximum':100},
 'schema':{'enum':['ai2apps.audio-generation/v1','ai2apps.audio-generation/v2']},
 'duration_mode':{'enum':['fixed','auto']},'generation':{'type':'object','additionalProperties':False,'properties':{
 'planning_mode':{'enum':['full','melody','off']},'abc':{'type':'string','maxLength':131072},
 'max_abc_tokens':{'type':'integer','minimum':1,'maximum':4096},'max_semantic_tokens':{'type':'integer','minimum':1,'maximum':3000},'guidance_scale':{'type':'number','minimum':1,'maximum':10}}}}}
AVATAR_SCHEMA={'type':'object','additionalProperties':False,'required':['image_id','audio_id','model_id','preset','resolution'],'properties':{
 'image_id':deepcopy(ASSET),'audio_id':deepcopy(ASSET),'model_id':{'type':'string','minLength':1},
 'preset':{'type':'string','minLength':1},'resolution':{'type':'string','minLength':1}}}
AVATAR_SCHEMA['properties']['image_id']['x-ai2apps-asset']['accept']='image/*'
AVATAR_SCHEMA['properties']['audio_id']['x-ai2apps-asset']['accept']='audio/*'
FROZEN_SCHEMA={'type':'object','additionalProperties':False,'required':['image_id','trajectory'],'properties':{
 'image_id':deepcopy(ASSET),'trajectory':{'type':'object'},'depth':{'enum':['da','vggt'],'default':'vggt'},
 'output':{'enum':['html','mp4','live-photo'],'default':'mp4'},'long_edge':{'enum':[512,768],'default':768},
 'reference_speedup':{'type':'boolean','default':True},'seed':{'type':'integer','minimum':-1,'maximum':4294967295,'default':-1}}}


FROZEN_SCHEMA['properties']['image_id']['x-ai2apps-asset']['accept']='image/*'
FROZEN_SCHEMA['properties']['audio_id']={**deepcopy(ASSET),'x-ai2apps-asset':{'storage':'artifact','accept':'audio/*','references':True}}


def owner(runtime,principal,app,mini):
 from ai2apps.studio.capability_broker import StudioCapabilityBroker,MountedMiniApp,_declared_capabilities
 definition,declaration=runtime.extension_manager._studio_mini_app_definition(app,mini,principal)
 host,_,_=runtime.extension_manager.launch_app(app,principal=principal)
 provider,_,_=runtime.extension_manager.launch_app(definition['package_id'],principal=principal)
 mounted=MountedMiniApp({'app_instance_id':provider.id,'context':{'studioInstanceId':host.id}},declaration,_declared_capabilities(declaration))
 class BoundBroker(StudioCapabilityBroker):
  def mounted_mini_app(self,studio_id,mount_id,*,principal):
   if studio_id!=app or mount_id!='aaat':raise ToolProviderError('Invalid owned Studio binding')
   # Recheck installed owner on each business service admission.
   current,_=runtime.extension_manager._studio_mini_app_definition(app,mini,principal)
   if current['package_id']!=definition['package_id'] or any(current.get(k)!=definition.get(k) for k in ('package_version','manifest_json','effective_digest')):raise ToolProviderError('Package changed before submission')
   return mounted
 return host,mounted,BoundBroker(runtime)


async def follow(runtime,principal,context,job):
 last=None
 try:
  while job['status'] not in ('succeeded','failed','cancelled','interrupted','publish_failed'):
   state=(job['status'],job.get('updated_at'))
   if state!=last:
    await context.report_progress('生成任务 · '+job['status'],content={'studio_job_id':job['id'],'studio_run_id':job.get('run_id')});last=state
   await asyncio.sleep(.5);job=runtime.studio_jobs.get(job['id'],principal)
 except asyncio.CancelledError:
  runtime.studio_jobs.cancel(job['id'],principal);raise
 if job['status']!='succeeded':raise ToolProviderError('Studio task '+job['id']+': '+str(job.get('error') or job['status']))
 return {'status':'completed','studio_job_id':job['id'],'studio_run_id':job.get('run_id'),'result':job.get('result'),'shared_output':True}


async def audio(runtime,args,context,mini,capability):
 from ai2apps.studio.audio_generation import validate_request
 principal=principal_for(runtime,context)
 if not context.invocation_id:raise ToolProviderError('Durable invocation required')
 host,mounted,_=owner(runtime,principal,VOICE,mini)
 if capability not in mounted.capabilities:raise ToolProviderError('Installed Package does not declare this audio operation')
 validate_request(runtime,capability,args)
 job=runtime.studio_jobs.submit(principal=principal,app_instance_id=host.id,studio_id=VOICE,mini_app_id=mini,
  kind='audio-generation',key='aaat:'+context.invocation_id,payload={'capability':capability,'input':args})
 return await follow(runtime,principal,context,job)


def reserve(runtime,context,args):
 if not context.invocation_id:raise ToolProviderError('Durable invocation required')
 signature=json.dumps([context.session_id,args],sort_keys=True)
 with runtime.database.transaction(write=True) as db:
  db.execute('CREATE TABLE IF NOT EXISTS studio_package_admissions(invocation TEXT PRIMARY KEY,signature TEXT NOT NULL,result TEXT)')
  old=db.execute('SELECT * FROM studio_package_admissions WHERE invocation=?',(context.invocation_id,)).fetchone()
  if old:
   if old['signature']!=signature:raise ToolProviderError('Invocation input changed')
   if not old['result']:raise ToolProviderError('Earlier submission is uncertain; inspect tasks without replay')
   return json.loads(old['result'])
  db.execute('INSERT INTO studio_package_admissions VALUES(?,?,NULL)',(context.invocation_id,signature))
 return None


def receipt(runtime,context,result):
 with runtime.database.transaction(write=True) as db:db.execute('UPDATE studio_package_admissions SET result=? WHERE invocation=?',(json.dumps(result),context.invocation_id))


def image_source(runtime,principal,session_id,identifier):
 from ai2apps.api.ownership import authorize_session
 authorize_session(runtime,principal,session_id)
 if identifier.startswith('gala_'):
  from ai2apps.gallery import GalleryRepository
  asset,path=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery').asset_path(principal.actor_user_id,identifier)
  if asset['status']!='active':raise ToolProviderError('Image material is deleted')
  name,media=asset['name'],asset['media_type']
 elif identifier.startswith('attc_'):
  asset=runtime.documents.get(session_id,identifier);path=runtime.documents.source_path(session_id,identifier);name,media=asset.filename,asset.media_type
 else:
  asset=runtime.workspace.get_artifact(session_id,identifier);path=runtime.workspace.artifact_path(asset);name,media=asset.name,asset.media_type
 if not media.startswith('image/'):raise ToolProviderError('Choose an owned image material')
 return path,name,media


async def avatar(runtime,args,context):
 from .voice_aaat import source
 from .avatar import generate_avatar,reconcile_outputs
 from .repository import StudioRepository
 principal=principal_for(runtime,context)
 host,mounted,broker=owner(runtime,principal,VIDEO,'ai2apps.avatar.photo-speaking')
 image,imagename,imagetype=image_source(runtime,principal,context.session_id,args['image_id'])
 audio,audioname,audiotype=source(runtime,principal,context.session_id,args['audio_id'])
 if not imagetype.startswith('image/') or not audiotype.startswith('audio/'):raise ToolProviderError('Choose a portrait image and driving audio')
 if image.stat().st_size>20*1024*1024 or audio.stat().st_size>100*1024*1024:raise ToolProviderError('Portrait limit 20 MiB; driving audio limit 100 MiB')
 old=reserve(runtime,context,args)
 if old:run=old
 else:
  run=await generate_avatar(broker,VIDEO,'aaat',principal=principal,request=None,
   content=audio.read_bytes(),filename=audioname,media_type=audiotype,image=image.read_bytes(),image_name=imagename,image_type=imagetype,
   preset=args['preset'],progress=None,model_id=args['model_id'],resolution=args['resolution'])
  receipt(runtime,context,run)
 scope={'actor_id':principal.actor_user_id,'installation_id':principal.installation_id,'app_instance_id':host.id,'studio_id':VIDEO}
 repo=StudioRepository(runtime.database)
 try:
  while True:
   reconcile_outputs(runtime,repo,scope);current=repo.get_run(run['id'],**scope)
   if current['status'] in ('succeeded','failed','cancelled','expired'):break
   await context.report_progress('照片说话 · '+current['status'],content={'studio_run_id':run['id']})
   await asyncio.sleep(1)
 except asyncio.CancelledError:
  await runtime.video_tasks.cancel(current['input']['videoTaskId'],actor_id=principal.actor_user_id);raise
 if current['status']!='succeeded':raise ToolProviderError(str(current.get('error') or current['status']))
 if not current['artifacts']:raise ToolProviderError('Original avatar task completed without a published shared output')
 return {'status':'completed','studio_run_id':run['id'],'artifacts':current['artifacts'],'shared_output':True}


async def frozen(runtime,args,context):
 from .voice_aaat import source
 from .repository import StudioRepository
 from .extended_jobs import submit
 from .frozen_time_editor import parse_frame_plan
 from .frozen_time_pipeline import DEPTH_MODELS,MERIDIAN
 from .live_photo import exporter_path
 from ai2apps.api.frozen_preview import normalize_upload
 from starlette.datastructures import UploadFile,Headers
 principal=principal_for(runtime,context);mini='ai2apps.imagine.frozen-time'
 host,mounted,_=owner(runtime,principal,IMAGINE,mini)
 if not {'image.frozen_time.da','image.frozen_time.vggt'}<=mounted.capabilities:raise ToolProviderError('Installed Package does not declare Frozen Time models')
 path,name,media=image_source(runtime,principal,context.session_id,args['image_id'])
 if not media.startswith('image/') or path.stat().st_size>20*1024*1024:raise ToolProviderError('Choose an image up to 20 MiB')
 settings={k:args.get(k,v) for k,v in dict(depth='vggt',output='mp4',long_edge=768,reference_speedup=True,seed=-1).items()}
 settings['trajectory']=parse_frame_plan(json.dumps(args['trajectory']))
 soundtrack=None
 if args.get('audio_id'):
  from ai2apps.api.imagine_frozen_time import normalize_soundtrack
  audio_path,audio_name,audio_media=source(runtime,principal,context.session_id,args['audio_id'],audio_only=True)
  with audio_path.open('rb') as f:
   soundtrack=await normalize_soundtrack(UploadFile(f,filename=audio_name,headers=Headers({'content-type':audio_media})),settings['output'])
 for id,cap in [(DEPTH_MODELS[settings['depth']],'depth_estimation'),(MERIDIAN,'video_generation')]:
  m=runtime.model_invocations.model(id)
  if not m or not m.checkpoint_ready or cap not in m.capabilities:raise ToolProviderError('Configure Frozen Time models on Desktop')
 if len(settings['trajectory']['frames']) not in m.metadata.get('frame_counts',[73]):raise ToolProviderError('Unsupported model frame count')
 if settings['output']=='live-photo' and exporter_path() is None:raise ToolProviderError('Desktop Live Photo exporter unavailable')
 with path.open('rb') as f:data=await normalize_upload(UploadFile(f,filename=name,headers=Headers({'content-type':media})))
 requested_seed=settings['seed']
 if requested_seed==-1:
  from random import SystemRandom
  settings['seed']=SystemRandom().randrange(4294967296)
 old=reserve(runtime,context,args)
 if old:job=runtime.studio_jobs.get(old['id'],principal)
 else:
  run=StudioRepository(runtime.database).create_run(actor_id=principal.actor_user_id,installation_id=principal.installation_id,app_instance_id=host.id,studio_id=IMAGINE,mini_app_id=mini,mini_app_version='1',placement=IMAGINE,title='静止时间',input_data=settings)
  files={'input.png':data}
  if soundtrack is not None:files['soundtrack.audio']=soundtrack
  job=submit(runtime,principal,host.id,IMAGINE,mini,'frozen-time',{'operation':'generate','settings':settings,'prepared':None,
   'metadata':{'depthModel':DEPTH_MODELS[settings['depth']],'modelId':MERIDIAN,'output':settings['output'],'seed':settings['seed'],'requestedSeed':requested_seed}},files=files,run_id=run['id'],key='aaat:'+context.invocation_id)
  receipt(runtime,context,{'id':job['id']})
 return await follow(runtime,principal,context,job)


async def avatar_descriptor(runtime,principal,model=None):
 from ai2apps.avatar import avatar_models
 from .capability_broker import StudioCapabilityBroker
 models=avatar_models(runtime);broker=StudioCapabilityBroker(runtime)
 return {'effective_schema':deepcopy(AVATAR_SCHEMA),'models':[{'id':m.id,'label':m.display_name,'ready':broker._model_stack_ready(runtime,m)} for m in models],
  'configuration_required':not any(broker._model_stack_ready(runtime,m) for m in models),
  'install':{'appId':VIDEO,'capability':'video.avatar_generation','requirements':{}}}

async def frozen_descriptor(runtime,principal,model=None):
 from .frozen_time_pipeline import DEPTH_MODELS,MERIDIAN
 ready=lambda id: bool((m:=runtime.model_invocations.model(id)) and m.checkpoint_ready)
 return {'effective_schema':deepcopy(FROZEN_SCHEMA),'configuration_required':not (ready(MERIDIAN) and any(ready(id) for id in DEPTH_MODELS.values())),
  'install':{'appId':IMAGINE,'capability':'image.frozen_time.vggt','requirements':{}}}

def install(runtime,register):
 logging.getLogger(__name__).info('Studio Package AaAT owners loaded from %s',__file__)
 common={'schema':'ai2apps.aaat-declaration/v1','instructions':['Use actual current Mini-App draft/model/material IDs. Never invent models or raw paths. Reuse the original durable Studio task and host shared Output; page closure is not cancellation. Missing models require Desktop configuration with inputs preserved. Unknown submission outcomes must not be replayed.'],
  'result_semantics':{'artifact':'Actual owner-published media or output references; UI snapshots are not generated artifacts.','shared_output':'Only a completed published owner task proves an output exists. Output references belong to the original Studio host.'}}
 for cap,(mini,operation,title) in AUDIO.items():
  schema=deepcopy(AUDIO_SCHEMA)
  if mini.endswith('.song'):
   schema['required']+=['schema','duration_mode','generation']
   schema['properties']['schema']={'const':'ai2apps.audio-generation/v2'}
   schema['properties']['duration_mode']={'const':'auto'}
  else:
   schema['required']+=['duration']
   # Fixed-duration workers use v1. Song planning fields are not accepted by
   # that executor and must never be offered in this provider's contract.
   schema['properties']['schema']={'const':'ai2apps.audio-generation/v1'}
   for field in ('duration_mode','generation'):schema['properties'].pop(field)
  async def describe(principal,model=None,operation=operation,schema=schema):
   from .audio_generation import generation_models
   models=generation_models(runtime,operation)
   return {'effective_schema':schema,'models':[{'id':m.id,'label':m.display_name,'ready':m.checkpoint_ready} for m in models],
    'configuration_required':not any(m.checkpoint_ready for m in models),'install':{'appId':VOICE,'capability':operation,'requirements':{}}}
  register(cap,VOICE,title+' / Generate audio','Generate through the installed Package and original durable Voice Studio audio queue. Uses supplied description verbatim; translate or polish only when requested. No reference audio or continuation.',schema,
   lambda a,c,m=mini,o=operation:audio(runtime,a,c,m,o),mini=mini,descriptor=describe,effects=('artifact.create',),timeout_ms=86400000,agent_context=common,
   field_labels={k:{'zh':z,'en':e} for k,z,e in [('model','模型','Model'),('prompt','描述','Description'),('duration','时长','Duration'),('lyrics','歌词','Lyrics'),('seed','随机种子','Seed'),('steps','步数','Steps'),('generation','歌曲规划','Song planning'),('schema','请求版本','Request version'),('duration_mode','时长模式','Duration mode')]},form_summary={'zh':'使用原语音队列生成并发布到共享输出。','en':'Generate using the original Voice queue and shared Output.'})
 register('video.avatar',VIDEO,'照片说话 / Talking portrait','Animate an owned portrait with driving audio through the installed Avatar Package and original video queue; publishes to shared Video Output. Portrait up to 20 MiB, audio up to 100 MiB; model-specific duration applies.',AVATAR_SCHEMA,lambda a,c:avatar(runtime,a,c),mini='ai2apps.avatar.photo-speaking',descriptor=lambda p,m=None:avatar_descriptor(runtime,p,m),field_labels={k:{'zh':z,'en':e} for k,z,e in [('image_id','人像图片','Portrait'),('audio_id','驱动音频','Driving audio'),('model_id','模型','Model'),('preset','生成档位','Preset'),('resolution','分辨率','Resolution')]},form_summary={'zh':'通过原视频队列生成照片说话，结果进入共享输出。','en':'Generate talking portraits through the original video queue and shared Output.'},effects=('artifact.create',),timeout_ms=86400000,agent_context=common)
 register('image.frozen_time',IMAGINE,'静止时间 / Frozen Time','Generate camera motion from an owned image and an explicit sampled camera plan using installed Frozen Time models and original durable Imagine queue. Use the actual UI trajectory; do not invent a default camera path. Shared Output contains the requested format.',FROZEN_SCHEMA,lambda a,c:frozen(runtime,a,c),mini='ai2apps.imagine.frozen-time',descriptor=lambda p,m=None:frozen_descriptor(runtime,p,m),field_labels={k:{'zh':z,'en':e} for k,z,e in [('image_id','图片','Image'),('audio_id','MP4 音轨','MP4 soundtrack'),('trajectory','镜头帧计划','Camera frame plan'),('depth','几何模型','Geometry model'),('output','输出格式','Output format'),('long_edge','分辨率长边','Long edge'),('reference_speedup','参考视频提速','Reference speedup'),('seed','随机种子','Seed')]},form_summary={'zh':'使用当前镜头轨迹生成静止时间，结果进入共享输出。','en':'Generate Frozen Time with the current camera plan and shared Output.'},effects=('artifact.create',),timeout_ms=86400000,agent_context=common)
