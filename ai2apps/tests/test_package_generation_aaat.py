"""Real owner queue/registry tests; inference is a deterministic WAV fixture."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest
from test_studio_app_chat import runtime,identity,P
from ai2apps.services import ToolCallContext
from ai2apps.chat import ChatRepository
from ai2apps.studio import package_generation_aaat as owner

@pytest.mark.asyncio
@pytest.mark.parametrize('name',list(owner.AUDIO))
async def test_audio_exports_original_queue_shared_output_and_once(runtime,monkeypatch,name):
 import wave
 mini,capability,_=owner.AUDIO[name]
 host,_,_=runtime.extension_manager.launch_app(owner.VOICE,principal=P())
 monkeypatch.setattr(owner,'owner',lambda *a:(host,NS(capabilities={capability}),None))
 metadata={'task':'sound_effects' if mini.endswith('.sfx') else 'music','minimum_duration':1,'maximum_duration':120,'lyrics':not mini.endswith('.sfx'),'planning_modes':['full'],'max_semantic_tokens':3000}
 if mini.endswith('.song'):metadata['workflow']='ai2apps.song-generation/v1'
 model=NS(id='fixture.audio',display_name='Fixture audio',checkpoint_ready=True,metadata={'audio_generation':metadata})
 monkeypatch.setattr('ai2apps.studio.audio_generation.generation_models',lambda *a:(model,))
 calls=[]
 async def infer(model,op,body,target,**kwargs):
  calls.append(kwargs['request_id'])
  with wave.open(str(target),'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(44100);w.writeframes(b'\0'*1764)
 monkeypatch.setattr(runtime.model_invocations,'invoke_background_to_file',infer)
 thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='fixture')
 ctx=replace(ToolCallContext.from_principal(P(),caller_id='test',session_id=thread.session.id),invocation_id='audio-once')
 args={'model':model.id,'prompt':'fixture','duration':1}
 if not mini.endswith('.song'):
  args.update(schema='ai2apps.audio-generation/v1',seed=42,steps=8)
 if mini.endswith('.song'):args={'model':model.id,'prompt':'fixture','schema':'ai2apps.audio-generation/v2','duration_mode':'auto','generation':{'planning_mode':'full','max_semantic_tokens':25}}
 await runtime.studio_jobs.startup()
 try:
  result=await runtime.app_capability_router.invoke(name,args,ctx)
  repeated=await runtime.app_capability_router.invoke(name,args,ctx)
  assert result['studio_job_id']==repeated['studio_job_id'] and len(calls)==1
  outputs=runtime.readaloud_tasks.output_history('local')
  assert len(outputs)==1 and outputs[0]['miniAppId']==mini
  with pytest.raises(Exception):await runtime.app_capability_router.invoke(name,{**args,'prompt':'changed'},ctx)
 finally:await runtime.studio_jobs.shutdown()

@pytest.mark.asyncio
async def test_fixed_duration_declaration_rejects_song_fields_before_submission(runtime,monkeypatch):
 from jsonschema import Draft202012Validator,ValidationError
 monkeypatch.setattr('ai2apps.studio.audio_generation.generation_models',lambda *a:())
 provider=next(p for p in runtime.app_capability_router.providers.values() if p.capability=='voice.generate_sound_effects')
 declaration=await provider.describe(P())
 schema=declaration['effective_schema']
 valid={'model':'fixture','prompt':'Rain','duration':2,'schema':'ai2apps.audio-generation/v1','seed':42,'steps':8}
 Draft202012Validator(schema).validate(valid)
 for extra in ({'duration_mode':'fixed'},{'generation':{}},{'schema':'ai2apps.audio-generation/v2'}):
  with pytest.raises(ValidationError):Draft202012Validator(schema).validate({**valid,**extra})

@pytest.mark.parametrize('app,mini,cap',[(owner.VOICE,m,c) for c,(m,_,_) in owner.AUDIO.items()]+[(owner.VIDEO,'ai2apps.avatar.photo-speaking','video.avatar'),(owner.IMAGINE,'ai2apps.imagine.frozen-time','image.frozen_time'),(owner.VIDEO,'ai2apps.media-voice.source-separation','voice.separate'),(owner.VIDEO,'ai2apps.media-voice.transcription','voice.detailed_transcription'),(owner.VOICE,'ai2apps.media-voice.video-speaker-replacement','video.replace_speaker')])
def test_package_scope_exports_exact_function(runtime,monkeypatch,app,mini,cap):
 monkeypatch.setattr(runtime.extension_manager,'_studio_mini_app_definition',lambda *a:({'package_id':'fixture.package'},{'id':mini,'version':'1'}))
 sid=runtime.app_chat.open(P(),app+'.chat',{'mini_app_id':mini},{})
 tools=runtime.app_chat.snapshot(P(),sid)['tools']
 assert cap in tools
 assert not {'todo.search','browser.navigate'}&set(tools)


def test_uncertain_admission_is_not_replayed(runtime):
 ctx=NS(invocation_id='uncertain',session_id='same')
 assert owner.reserve(runtime,ctx,{'a':1}) is None
 with pytest.raises(Exception,match='uncertain'):owner.reserve(runtime,ctx,{'a':1})
 with pytest.raises(Exception,match='changed'):owner.reserve(runtime,ctx,{'a':2})
 owner.receipt(runtime,ctx,{'id':'accepted'})
 assert owner.reserve(runtime,ctx,{'a':1})=={'id':'accepted'}

@pytest.mark.asyncio
async def test_avatar_admission_keeps_original_service_and_does_not_resubmit(runtime,monkeypatch,tmp_path):
 from PIL import Image
 from ai2apps.studio.repository import StudioRepository
 import wave
 host,_,_=runtime.extension_manager.launch_app(owner.VIDEO,principal=P())
 mounted=NS(capabilities={'video.avatar_generation'})
 monkeypatch.setattr(owner,'owner',lambda *a:(host,mounted,NS()))
 monkeypatch.setattr('ai2apps.studio.avatar.reconcile_outputs',lambda *a:None)
 thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='avatar')
 image=tmp_path/'portrait.png';Image.new('RGB',(64,64),'blue').save(image)
 audio=tmp_path/'speech.wav'
 with wave.open(str(audio),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0'*3200)
 refs=[runtime.documents.create_reference(thread.session.id,p,media_type=m) for p,m in [(image,'image/png'),(audio,'audio/wav')]]
 calls=[];scope=dict(actor_id='local',installation_id='local',app_instance_id=host.id,studio_id=owner.VIDEO);repo=StudioRepository(runtime.database)
 async def generate(*a,**kw):
  calls.append(kw);assert kw['content']==audio.read_bytes() and kw['image']==image.read_bytes()
  run=repo.create_run(**scope,mini_app_id='ai2apps.avatar.photo-speaking',mini_app_version='1',placement='inline',title='fixture',input_data={})
  repo.create_artifact(run['id'],**scope,kind='video',name='fixture.mp4',media_type='video/mp4',preview_url='/fixture.mp4',download_url='/fixture.mp4',metadata={},source_id='fixture-video')
  repo.update_run(run['id'],**scope,status='succeeded',progress=100,detail='Fixture renderer complete')
  return run
 monkeypatch.setattr('ai2apps.studio.avatar.generate_avatar',generate)
 ctx=replace(ToolCallContext.from_principal(P(),caller_id='test',session_id=thread.session.id),invocation_id='avatar-once')
 args=dict(image_id=refs[0].id,audio_id=refs[1].id,model_id='fixture',preset='default',resolution='source')
 first=await owner.avatar(runtime,args,ctx);again=await owner.avatar(runtime,args,ctx)
 assert first['studio_run_id']==again['studio_run_id'] and len(calls)==1
 with pytest.raises(Exception):await owner.avatar(runtime,{**args,'preset':'other'},ctx)

@pytest.mark.asyncio
async def test_frozen_validates_camera_plan_before_admission(runtime,monkeypatch,tmp_path):
 from PIL import Image
 host,_,_=runtime.extension_manager.launch_app(owner.IMAGINE,principal=P())
 monkeypatch.setattr(owner,'owner',lambda *a:(host,NS(capabilities={'image.frozen_time.da','image.frozen_time.vggt'}),None))
 thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='frozen')
 image=tmp_path/'input.png';Image.new('RGB',(64,64)).save(image)
 ref=runtime.documents.create_reference(thread.session.id,image,media_type='image/png')
 ctx=replace(ToolCallContext.from_principal(P(),caller_id='test',session_id=thread.session.id),invocation_id='bad-frozen')
 with pytest.raises(ValueError):await owner.frozen(runtime,{'image_id':ref.id,'trajectory':{'frames':[]}},ctx)
 with runtime.database.transaction() as db:assert db.execute('select count(*) from studio_background_jobs').fetchone()[0]==0

@pytest.mark.asyncio
async def test_frozen_original_queue_publishes_owned_output_once(runtime,monkeypatch,tmp_path):
 from PIL import Image
 from dataclasses import asdict
 from ai2apps.studio.frozen_time import CameraKey
 from ai2apps.studio.repository import StudioRepository
 host,_,_=runtime.extension_manager.launch_app(owner.IMAGINE,principal=P())
 monkeypatch.setattr(owner,'owner',lambda *a:(host,NS(capabilities={'image.frozen_time.da','image.frozen_time.vggt'}),None))
 monkeypatch.setattr(runtime.model_invocations,'model',lambda id:NS(checkpoint_ready=True,capabilities={'depth_estimation','video_generation'},metadata={'frame_counts':[73]}))
 calls=[]
 async def generate(runtime,source,directory,**kwargs):
  calls.append(kwargs['trajectory']);assert source.is_file()
  (directory/'output.html').write_text('<html>Fixture output</html>')
  return [('output.html','document','text/html')]
 monkeypatch.setattr('ai2apps.studio.frozen_time_pipeline.generate',generate)
 thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='frozen queue')
 image=tmp_path/'input.png';Image.new('RGB',(64,64)).save(image)
 ref=runtime.documents.create_reference(thread.session.id,image,media_type='image/png')
 trajectory={'schema':'ai2apps.camera-frames/v1','frames':[asdict(CameraKey(0)) for _ in range(73)],'playback':list(range(73)),'poster':36}
 args={'image_id':ref.id,'trajectory':trajectory,'output':'html'}
 ctx=replace(ToolCallContext.from_principal(P(),caller_id='test',session_id=thread.session.id),invocation_id='frozen-once')
 await runtime.studio_jobs.startup()
 try:
  first=await owner.frozen(runtime,args,ctx);again=await owner.frozen(runtime,args,ctx)
  assert first['studio_job_id']==again['studio_job_id'] and calls==[trajectory]
  run=StudioRepository(runtime.database).get_run(first['studio_run_id'],actor_id='local',installation_id='local',app_instance_id=host.id,studio_id=owner.IMAGINE)
  assert run['status']=='succeeded' and run['artifacts'][0]['name']=='output.html'
 finally:await runtime.studio_jobs.shutdown()
