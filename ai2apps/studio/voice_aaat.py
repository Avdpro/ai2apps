"""Voice Studio-owned separation and observed-speaker replacement workflows."""
import asyncio
from copy import deepcopy
import json
import logging
from urllib.parse import urlsplit

from ai2apps.services import ToolProviderError
from ai2apps.services.aaat import principal_for
from .source_reference import describe as describe_source

logging.getLogger(__name__).info('Voice AaAT loaded from %s', __file__)

APP = 'ai2apps.readaloud'
SEPARATE_MINI = 'ai2apps.media-voice.source-separation'
REPLACE_MINI = 'ai2apps.media-voice.audio-speaker-replacement'
SEPARATE = 'audio.source_separation'
REPLACE = 'audio.speaker_voice_replacement'
TRANSCRIBE = 'audio.detailed_transcription'
DIARIZE = 'audio.speaker_diarization'
ASSET = {'type':'string','minLength':1,'maxLength':256,
         'x-ai2apps-asset':{'storage':'artifact','accept':'audio/*,video/*','references':True}}
SEPARATE_SCHEMA = {'type':'object','additionalProperties':False,'required':['media_id'], 'properties':{
    'media_id':ASSET,'profile':{'enum':['vocals_instrumental','dialogue_background','music_4stem'],'default':'vocals_instrumental'}}}
REPLACE_SCHEMA = {'type':'object','additionalProperties':False,'required':['media_id','action'], 'properties':{
    'media_id':{**ASSET,'x-ai2apps-asset':{**ASSET['x-ai2apps-asset'],'accept':'audio/*'}},
    'action':{'enum':['analyze','replace'],'default':'analyze'},
    'analysis_id':{'type':'string','minLength':1,'maxLength':256},
    'target_speaker':{'type':'string','minLength':1,'maxLength':128},
    'reference_id':{**ASSET,'x-ai2apps-asset':{**ASSET['x-ai2apps-asset'],'accept':'audio/*'}},
    'conversion_profile':{'enum':['timbre_fast','timbre_quality','voice_quality'],'default':'timbre_fast'},
    'consent':{'type':'boolean','default':False}},
    'allOf':[{'if':{'properties':{'action':{'const':'replace'}}},'then':{
        'required':['analysis_id','target_speaker','reference_id','consent'],
        'properties':{'consent':{'const':True}}}}]}


def source(runtime, principal, session_id, identifier, *, audio_only=False):
    """Owned IDs only. Open original paths later; no full input read or copy."""
    from ai2apps.api.ownership import authorize_session
    authorize_session(runtime,principal,session_id)
    if identifier.startswith('gala_'):
        from ai2apps.gallery import GalleryRepository
        asset,path=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery').asset_path(principal.actor_user_id,identifier)
        if asset['status']!='active':raise ToolProviderError('Gallery material is deleted')
        name,media=asset['name'],asset['media_type']
    elif identifier.startswith('attc_'):
        asset=runtime.documents.get(session_id,identifier)
        path=runtime.documents.source_path(session_id,identifier)
        name,media=asset.filename,asset.media_type
    else:
        asset=runtime.workspace.get_artifact(session_id,identifier)
        path=runtime.workspace.artifact_path(asset)
        name,media=asset.name,asset.media_type
    if not media.startswith('audio/' if audio_only else ('audio/','video/')):
        raise ToolProviderError('Select an audio material' if audio_only else 'Select an audio or video material')
    return path,name,media


def readiness(runtime):
    from .capability_broker import StudioCapabilityBroker
    broker=StudioCapabilityBroker(runtime)
    separation=set()
    for model in broker._separation_models(runtime):
        if broker._model_stack_ready(runtime,model):separation.update(broker._separation_profiles(model))
    conversion=set()
    for model in broker._voice_models(runtime):
        if broker._model_stack_ready(runtime,model):
            conversion.update(p for p in REPLACE_SCHEMA['properties']['conversion_profile']['enum'] if broker._voice_profile(model,p))
    transcription=any(broker._detailed_model_for_profile(p) for p in ('compact','quality'))
    return separation,conversion,transcription


async def descriptor(runtime, principal, *, replacement=False):
    separation,conversion,transcription=readiness(runtime)
    schema=deepcopy(REPLACE_SCHEMA if replacement else SEPARATE_SCHEMA)
    if not replacement and separation:
        schema['properties']['profile']['enum']=[p for p in schema['properties']['profile']['enum'] if p in separation]
        schema['properties']['profile']['default']=schema['properties']['profile']['enum'][0]
    # Analysis only needs transcription. Conversion prerequisites are rechecked
    # before replace, with the same owner's existing ACPF available on the form.
    return {'effective_schema':schema,'selection_required':True,
        'configuration_required':not transcription if replacement else not separation,
        'install':{'appId':APP,'capability':REPLACE if replacement else SEPARATE,'requirements':{}},
        'warnings':([{'zh':'先分析录音，再按真实说话人编号选择角色；换声需参考音频及明确使用权确认。','en':'Analyze first, then select an observed speaker. Replacement requires reference audio and explicit rights confirmation.'}] if replacement else []),
        'available_profiles':sorted(conversion if replacement else separation)}


def observation_table(runtime):
    with runtime.database.transaction() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS voice_speaker_observations (
            id TEXT PRIMARY KEY, actor TEXT NOT NULL, installation TEXT NOT NULL,
            session TEXT NOT NULL, source TEXT NOT NULL, speakers TEXT NOT NULL)''')


def observation(runtime, context, identifier, source_identity):
    observation_table(runtime)
    with runtime.database.transaction() as db:
        row=db.execute('SELECT * FROM voice_speaker_observations WHERE id=?',(identifier,)).fetchone()
    if not row or (row['actor'],row['installation'],row['session'])!=(context.actor_user_id,context.installation_id,context.session_id):
        raise ToolProviderError('Analyze this recording in the current Session before replacement')
    if json.loads(row['source'])!=source_identity:raise ToolProviderError('Analysis source changed; analyze the selected recording again')
    return json.loads(row['speakers'])


def output(runtime, principal, session_id, job):
    url=(job.get('result') or {}).get('downloadUrl','')
    parts=urlsplit(url)
    path=parts.path.split('/')
    if parts.scheme or parts.netloc or len(path)!=8 or path[1:4]!=['v1','platform','sessions'] or path[5]!='artifacts' or path[7]!='download':
        raise ToolProviderError('Invalid Voice Studio output reference')
    if path[4]!=runtime.readaloud_tasks._artifact_session(principal.actor_user_id):raise ToolProviderError('Output left its Voice Studio owner')
    artifact=runtime.workspace.get_artifact(path[4],path[6])
    location=runtime.workspace.artifact_path(artifact)
    imported=runtime.workspace.import_artifact(session_id,location,name=artifact.name,media_type=artifact.media_type)
    return location,{'artifact_id':imported.id,'filename':imported.name,'media_type':imported.media_type,
        'url':f'/v1/platform/sessions/{session_id}/artifacts/{imported.id}/download'}


async def execute(runtime,args,context,*,replacement=False,video=False,host_app=None):
    from jsonschema import Draft202012Validator
    from ai2apps.api.ownership import authorize_session
    from .capability_broker import MountedMiniApp,_declared_capabilities
    from .video_jobs import submit_package
    if not context.invocation_id or not context.session_id:raise ToolProviderError('Voice processing requires a durable Session invocation')
    principal=principal_for(runtime,context)
    authorize_session(runtime,principal,context.session_id)
    Draft202012Validator(REPLACE_SCHEMA if replacement else SEPARATE_SCHEMA).validate(args)
    app=host_app or ('ai2apps.video-studio' if video else APP)
    capability,mini=('media.video_speaker_voice_replacement','ai2apps.media-voice.video-speaker-replacement') if video else ((REPLACE,REPLACE_MINI) if replacement else (SEPARATE,SEPARATE_MINI))
    definition,declaration=runtime.extension_manager._studio_mini_app_definition(app,mini,principal)
    caps=_declared_capabilities(declaration)
    action=args.get('action','analyze')
    required={REPLACE,TRANSCRIBE,DIARIZE} if replacement else {SEPARATE}
    if video:required.update({capability,'media.audio.extract'})
    if replacement and action=='replace':
        required.update({SEPARATE,'audio.voice_conversion'})
        if video:required.add('media.video.audio_mux')
    if required-caps:raise ToolProviderError('Installed Mini-App does not declare the requested voice workflow')
    path,name,media=source(runtime,principal,context.session_id,args['media_id'],audio_only=replacement and not video)
    if video and not media.startswith('video/'):raise ToolProviderError('Select a video material')
    identity={'media_id':args['media_id'],'reference':describe_source(path)}
    if video:identity['workflow']='video-speaker-replacement'
    separation,conversion,transcription=readiness(runtime)
    reference=None
    if replacement:
        if not transcription:raise ToolProviderError('Configure transcription in Desktop Voice Studio; parameters and materials are preserved')
        options={'action':action,'target_speaker':None,'reference_filename':None,'reference_media_type':None,
            'conversion_profile':args.get('conversion_profile','timbre_fast'),'consent':False}
        if action=='replace':
            speakers=observation(runtime,context,args['analysis_id'],identity)
            if args['target_speaker'] not in {s['id'] for s in speakers}:raise ToolProviderError('Select an observed speaker from the analysis')
            if 'dialogue_background' not in separation or options['conversion_profile'] not in conversion:
                raise ToolProviderError('Configure separation and voice conversion in Desktop Voice Studio; parameters and materials are preserved')
            reference,reference_name,reference_media=source(runtime,principal,context.session_id,args['reference_id'],audio_only=True)
            options.update(target_speaker=args['target_speaker'],reference_filename=reference_name,reference_media_type=reference_media,consent=args['consent'])
    else:
        profile=args.get('profile','vocals_instrumental')
        if profile not in separation:raise ToolProviderError('Configure the selected separation profile in Desktop Voice Studio')
        options={'profile':profile}
    host,_,_=runtime.extension_manager.launch_app(app,principal=principal)
    provider,_,_=runtime.extension_manager.launch_app(definition['package_id'],principal=principal)
    mounted=MountedMiniApp({'app_instance_id':provider.id,'context':{'studioInstanceId':host.id}},declaration,caps)
    job=submit_package(runtime,principal,mounted,capability,options,path,name,media,reference,
        key='aaat:'+context.invocation_id,studio_id=app)
    try:
        while job['status'] not in ('succeeded','failed','cancelled','interrupted','publish_failed'):
            await context.report_progress('音频处理 · '+job['status'],content={'studio_job_id':job['id'],'studio_run_id':job['run_id']})
            await asyncio.sleep(1)
            job=runtime.studio_jobs.get(job['id'],principal)
    except asyncio.CancelledError:
        # Client disconnect does not cancel the handler. Explicit Run cancellation
        # cancels its one existing job; never submits through an alternate path.
        runtime.studio_jobs.cancel(job['id'],principal)
        raise
    if job['status']!='succeeded':raise ToolProviderError('Voice task '+job['id']+': '+str(job.get('error') or job['status']))
    if app=='ai2apps.video-studio':
        from .video_aaat import import_output
        file=import_output(runtime,context,job)
        location=runtime.workspace.artifact_path(runtime.workspace.get_artifact(context.session_id,file['artifact_id']))
    else:
        location,file=output(runtime,principal,context.session_id,job)
    result={'status':'completed','studio_job_id':job['id'],'studio_run_id':job['run_id'],'files':[file],
        'aaat_context':{'schema':'ai2apps.aaat-result-context/v1','status':'complete','data_trust':'untrusted',
            'scope':{'media_id':args['media_id'],'action':action if replacement else 'separate'},
            'coverage':{'shared_output':True}}}
    if not replacement:
        for track in ((job.get('result') or {}).get('tracks') or [])[:4]:
            if not isinstance(track,dict):raise ToolProviderError('Invalid separation track output')
            _,track_file=output(runtime,principal,context.session_id,{'result':{'downloadUrl':track.get('downloadUrl')}})
            if not track_file['media_type'].startswith('audio/'):raise ToolProviderError('Separation track is not audio')
            result['files'].append(track_file)
    if replacement and action=='analyze':
        if location.stat().st_size>1024*1024:raise ToolProviderError('Speaker analysis exceeds the bounded result size')
        transcript=json.loads(location.read_text())
        segments=transcript.get('segments')
        if not isinstance(segments,list):raise ToolProviderError('Speaker analysis did not return segments')
        speakers={}
        for segment in segments:
            if not isinstance(segment,dict):continue
            speaker=segment.get('speaker')
            if not isinstance(speaker,str) or not speaker or len(speaker)>128:continue
            if speaker not in speakers:
                if len(speakers)>=64:raise ToolProviderError('Too many speakers; choose a shorter recording')
                speakers[speaker]={'id':speaker,'sample':str(segment.get('text') or '')[:240],'segments':0}
            speakers[speaker]['segments']+=1
        observation_table(runtime)
        values=list(speakers.values())
        with runtime.database.transaction() as db:
            db.execute('INSERT OR REPLACE INTO voice_speaker_observations VALUES (?,?,?,?,?,?)',
                (job['id'],context.actor_user_id,context.installation_id,context.session_id,json.dumps(identity,sort_keys=True),json.dumps(values,ensure_ascii=False)))
        result.update(analysis_id=job['id'],speakers=values)
        result['aaat_context']['status']='resolved' if values else 'not_found'
        result['aaat_context']['coverage']['observed_speakers']=len(values)
    return result


def install(runtime,register):
    labels={k:{'zh':z,'en':e} for k,z,e in [
        ('media_id','源音频或视频','Source audio or video'),('profile','分离音轨','Separation tracks'),
        ('action','处理阶段','Stage'),('analysis_id','角色分析记录','Speaker analysis'),('target_speaker','目标说话人编号','Observed speaker ID'),
        ('reference_id','目标声音参考音频','Reference voice audio'),('conversion_profile','换声质量','Conversion quality'),
        ('consent','我确认拥有处理源录音和使用参考声音的权利','I confirm rights to process the recording and use the reference voice')]}
    common=['Inputs are current Session attachment/artifact IDs or owned Gallery IDs, never raw paths. Original media is referenced without copying.',
        'Use the existing durable Voice Studio job and host-owned Preview & Output. Do not claim completion until its published result exists. Missing models use Desktop ACPF; preserve materials and parameters. Client disconnect alone does not cancel submitted work.']
    register('voice.separate',APP,'分离人声和背景 / Separate voice and background',
        'Separate vocals/instrumental, dialogue/background or four music stems from audio or video through Voice Studio. Input is an owned material reference; existing model profiles only; maximum one hour.',
        SEPARATE_SCHEMA,lambda a,c:execute(runtime,a,c),mini=SEPARATE_MINI,descriptor=lambda p,m=None:descriptor(runtime,p),
        effects=('artifact.create',),selection_required=True,timeout_ms=86400000,field_labels=labels,
        option_labels={'profile':{k:{'zh':z,'en':e} for k,z,e in [('vocals_instrumental','人声 / 伴奏','Vocals / instrumental'),('dialogue_background','对白 / 背景','Dialogue / background'),('music_4stem','鼓 / 贝斯 / 其他 / 人声','Drums / bass / other / vocals')]}},
        agent_context={'schema':'ai2apps.aaat-declaration/v1','instructions':common,
            'result_semantics':{'files':'Published separation ZIP and Session-owned WAV references. The shared host Output remains the sole Studio media history; pass these file artifact IDs to subsequent compatible Apps.'}},
        form_summary={'zh':'从音频或视频分离音轨，结果进入语音工坊共享输出。','en':'Separate audio tracks into the shared Voice Studio output.'})
    register('voice.replace_speaker',APP,'分析角色并换声 / Analyze and replace a speaker',
        'Analyze audio speakers first, then replace one observed speaker using reference audio and explicit rights confirmation. Keep other voices and background on the original timeline. Never invent a speaker ID. Original recording up to one hour; reference audio up to 60 seconds.',
        REPLACE_SCHEMA,lambda a,c:execute(runtime,a,c,replacement=True),mini=REPLACE_MINI,
        descriptor=lambda p,m=None:descriptor(runtime,p,replacement=True),effects=('artifact.create',),selection_required=True,timeout_ms=86400000,field_labels={**labels,'media_id':{'zh':'源录音','en':'Source recording'},'analysis_id':{'zh':'角色分析记录（仅换声）','en':'Analysis reference (replace only)'},'target_speaker':{'zh':'目标说话人编号（仅换声）','en':'Observed speaker ID (replace only)'}},
        option_labels={'action':{'analyze':{'zh':'识别说话人','en':'Analyze speakers'},'replace':{'zh':'替换指定角色声音','en':'Replace observed speaker'}},
            'conversion_profile':{k:{'zh':z,'en':e} for k,z,e in [('timbre_fast','音色 · 快速','Timbre · fast'),('timbre_quality','音色 · 高质量','Timbre · quality'),('voice_quality','声音 · 高质量','Voice · quality')]}},
        agent_context={'schema':'ai2apps.aaat-declaration/v1','instructions':common+[
            'First call action=analyze without a target or reference. Return observed speaker IDs and sample text; ask the user to identify the target. Analysis does not replace any voice.',
            'For action=replace pass the returned analysis_id for this exact source in the same Session, one observed target_speaker and reference_id. Obtain explicit rights consent through the parameter form; consent defaults false and must never be inferred from reference availability.',
            'Keep source and reference media unchanged. Missing or changed analysis is a preflight failure; analyze again only within user authorization.'],
            'result_semantics':{'speakers':'Observed diarization IDs with short text samples, not verified real identities. Empty speaker evidence cannot authorize replacement.',
                'files':'Analysis JSON or the final mixed WAV, also published to host Output.'}},
        form_summary={'zh':'先识别录音角色，再选择目标角色与参考声音并确认使用权。','en':'Analyze first; select the target and reference voice, then confirm usage rights.'})
