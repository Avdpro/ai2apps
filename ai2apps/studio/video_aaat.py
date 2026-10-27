"""Video Studio owner: bounded basic edits using its existing Composer/queue."""
import asyncio
from copy import deepcopy
import hashlib
import json
import logging
from urllib.parse import urlsplit
from ai2apps.services import ToolProviderError
from ai2apps.services.aaat import principal_for
from .voice_aaat import source
from .source_reference import describe as describe_source

logging.getLogger(__name__).info('Video AaAT loaded from %s', __file__)

APP='ai2apps.video-studio'
COMPOSER='ai2apps.video.composer'
EXTRACT='ai2apps.video.extract-audio'
ASSET={'type':'string','minLength':1,'maxLength':256,'x-ai2apps-asset':{
    'storage':'artifact','accept':'video/*','references':True}}
SCHEMA={'type':'object','additionalProperties':False,'required':['operation','media_ids'],'properties':{
    'operation':{'enum':['extract_audio','trim','join']},
    'media_ids':{'type':'array','minItems':1,'maxItems':10,'items':ASSET},
    'start_seconds':{'type':'number','minimum':0,'maximum':86400,'default':0},
    'end_seconds':{'type':'number','exclusiveMinimum':0,'maximum':86400}},
    'allOf':[{'if':{'properties':{'operation':{'enum':['extract_audio','trim']}}},'then':{'properties':{'media_ids':{'maxItems':1}}}},
             {'if':{'properties':{'operation':{'const':'join'}}},'then':{'properties':{'media_ids':{'minItems':2}}}},
             {'if':{'properties':{'operation':{'const':'trim'}}},'then':{'required':['end_seconds']}}]}


def import_output(runtime,context,job):
    raw=(job.get('result') or {}).get('downloadUrl') or ''
    url=urlsplit(raw);parts=url.path.split('/')
    if url.scheme or url.netloc or len(parts)!=8 or parts[1:4]!=['v1','platform','sessions'] or parts[5]!='artifacts' or parts[7]!='download':
        raise ToolProviderError('Invalid Video Studio output reference')
    if parts[4]!=runtime.video_tasks.artifact_session():raise ToolProviderError('Output left Video Studio scope')
    artifact=runtime.workspace.get_artifact(parts[4],parts[6])
    output=runtime.workspace.import_artifact(context.session_id,runtime.workspace.artifact_path(artifact),name=artifact.name,media_type=artifact.media_type)
    return {'artifact_id':output.id,'filename':output.name,'media_type':output.media_type,
        'url':f'/v1/platform/sessions/{context.session_id}/artifacts/{output.id}/download'}


async def follow(runtime,principal,context,job):
    try:
        while job['status'] not in ('succeeded','failed','cancelled','interrupted','publish_failed'):
            await context.report_progress('视频处理 · '+job['status'],content={'studio_job_id':job['id'],'studio_run_id':job['run_id']})
            await asyncio.sleep(1);job=runtime.studio_jobs.get(job['id'],principal)
    except asyncio.CancelledError:
        runtime.studio_jobs.cancel(job['id'],principal);raise
    if job['status']!='succeeded':raise ToolProviderError('Video task '+job['id']+': '+str(job.get('error') or job['status']))
    return job


async def execute(runtime,args,context):
    from jsonschema import Draft202012Validator
    from .repository import StudioRepository
    from .video_jobs import submit_media
    from ai2apps.video.composer import ComposerSourceStore,ComposerProject
    from ai2apps.api.ownership import authorize_session
    if not context.session_id or not context.invocation_id:raise ToolProviderError('Video processing requires a durable Session invocation')
    principal=principal_for(runtime,context);authorize_session(runtime,principal,context.session_id)
    Draft202012Validator(SCHEMA).validate(args)
    operation=args['operation'];identifiers=args['media_ids']
    if operation!='trim' and (args.get('start_seconds',0)!=0 or 'end_seconds' in args):
        raise ToolProviderError('Time bounds apply only to trim')
    inputs=[]
    for identifier in identifiers:
        path,name,media=source(runtime,principal,context.session_id,identifier)
        if not media.startswith('video/'):raise ToolProviderError('Select video materials')
        inputs.append((path,name,media))
    # This exact request key is reused before creating another Studio Run. Scope
    # and source fingerprints make retries unable to silently change the work.
    fingerprint=hashlib.sha256(json.dumps([context.session_id,args,[describe_source(p) for p,_,_ in inputs]],sort_keys=True).encode()).hexdigest()
    key='aaat:'+context.invocation_id
    with runtime.database.transaction() as db:
        previous=db.execute('SELECT * FROM studio_background_jobs WHERE actor_id=? AND installation_id=? AND studio_id=? AND idempotency_key=?',
            (principal.actor_user_id,principal.installation_id,APP,key)).fetchone()
    if previous:
        if json.loads(previous['request_json']).get('aaat_fingerprint')!=fingerprint:raise ToolProviderError('Invocation already used for a different video request')
        job=runtime.studio_jobs.public(previous)
    else:
        host,_,_=runtime.extension_manager.launch_app(APP,principal=principal)
        scope={'actor_id':principal.actor_user_id,'installation_id':principal.installation_id,'app_instance_id':host.id,'studio_id':APP}
        store=ComposerSourceStore(runtime.config.paths.artifacts_path/'video-composer-sources')
        sources={};records=[]
        for path,name,media in inputs:
            public=store.register(path,actor_id=principal.actor_user_id,installation_id=principal.installation_id,app_instance_id=host.id,display_name=name,media_type=media)
            record,selected=store.get(public['id'],actor_id=principal.actor_user_id,installation_id=principal.installation_id,app_instance_id=host.id)
            if not record['hasVideo']:raise ToolProviderError('Material has no video stream')
            if record['duration']<=0:raise ToolProviderError('Video duration is unavailable')
            records.append(record);sources[record['id']]=(record,selected)
        mini=EXTRACT if operation=='extract_audio' else COMPOSER
        payload={'aaat_fingerprint':fingerprint,'filename':'extracted.wav' if operation=='extract_audio' else 'edited.mp4',
            'kind':'audio' if operation=='extract_audio' else 'video','media_type':'audio/wav' if operation=='extract_audio' else 'video/mp4'}
        if operation=='extract_audio':
            if not records[0]['hasAudio']:raise ToolProviderError('Video has no audio track')
            sources={'source':sources[records[0]['id']]};executor='extract'
        else:
            first=records[0];width,height=first['width'],first['height']
            if not width or not height or width<64 or height<64 or width>3840 or height>2160:
                raise ToolProviderError('Composer output supports 64–3840 × 64–2160 pixels; choose a compatible source')
            clips=[];position=0
            for index,record in enumerate(records):
                start=args.get('start_seconds',0) if operation=='trim' else 0
                end=args['end_seconds'] if operation=='trim' else record['duration']
                if end<=start or end>record['duration']+.001:raise ToolProviderError('Trim bounds exceed the observed source duration')
                duration=end-start
                clips.append({'id':'clip-'+str(index),'sourceId':record['id'],'trackId':'video','name':record['name'],
                    'start':position,'sourceStart':start,'duration':duration,'width':width,'height':height})
                position+=duration
            project=ComposerProject.model_validate({'title':'AaAT video edit','settings':{'width':width,'height':height,'fps':30},
                'tracks':[{'id':'video','kind':'video','name':'Video','order':0}],'clips':clips})
            payload['project']=project.model_dump();executor='compose'
        repo=StudioRepository(runtime.database)
        run=repo.create_run(**scope,mini_app_id=mini,mini_app_version='1.0.0',placement='inline',title='视频基础处理',input_data={'operation':operation})
        job=submit_media(runtime,principal,scope,run,operation=executor,payload=payload,sources=sources,key=key)
    job=await follow(runtime,principal,context,job)
    return {'status':'completed','studio_job_id':job['id'],'studio_run_id':job['run_id'],'files':[import_output(runtime,context,job)],
        'aaat_context':{'schema':'ai2apps.aaat-result-context/v1','status':'complete','data_trust':'untrusted',
            'scope':{'operation':operation,'media_ids':identifiers,'studio_mini_app_id':job['mini_app_id']},
            'coverage':{'processed_inputs':len(identifiers)}}}


def install(runtime,register):
    register('video.process',APP,'视频基础处理 / Basic video processing',
        'Extract audio, trim a time range, or join ordered video materials through the existing Video Studio Composer/background queue. Uses owned source references, no input copies. Trim/join outputs use the first video canvas, 30 fps, original audio, and a maximum total of ten minutes. Join accepts 2–10 inputs in the supplied order. Not subtitle translation or AI video generation.',
        SCHEMA,lambda a,c:execute(runtime,a,c),effects=('artifact.create',),selection_required=True,timeout_ms=86400000,
        agent_context={'schema':'ai2apps.aaat-declaration/v1','instructions':[
            'Use owned current Session attachment/artifact or Gallery IDs only. media_ids order is output order for join. Do not invent filesystem paths.',
            'For trim collect start_seconds and end_seconds from the source timeline. Only one video is accepted for trim/extract_audio; join needs 2–10 ordered videos. Reject unused time bounds rather than silently ignoring them.',
            'Trim and join reuse Composer rendering, first source dimensions and 30 fps; explain normalization if the source differs. Total rendered duration is at most ten minutes, same as the UI. No generative model is needed.',
            'Wait for the one durable Studio job and published artifact. Client disconnect is not cancellation. Changed/deleted input references fail explicitly; do not retry effectful work through another capability.'],
            'result_semantics':{'files':'Actual published Video Studio output, imported as a Session-owned reference for subsequent compatible Apps.','coverage':'Number of processed source references, never a count of unique people or scenes.'}},
        field_labels={k:{'zh':z,'en':e} for k,z,e in [('operation','处理方式','Operation'),('media_ids','视频素材（按输出顺序）','Videos (output order)'),('start_seconds','起始时间（秒，仅截取）','Start seconds (trim only)'),('end_seconds','结束时间（秒，仅截取）','End seconds (trim only)')]},
        option_labels={'operation':{k:{'zh':z,'en':e} for k,z,e in [('extract_audio','提取音频','Extract audio'),('trim','截取片段','Trim clip'),('join','按顺序拼接','Join in order')]}},
        form_summary={'zh':'从视频提取音频、截取片段或顺序拼接，使用原文件引用并在后台处理。','en':'Extract audio, trim or join videos using original references in the background.'})

UPSCALE_SCHEMA={'type':'object','additionalProperties':False,'required':['video_id','model_id'],'properties':{
    'video_id':ASSET,'model_id':{'type':'string','minLength':1,'maxLength':512},
    'seed':{'type':'integer','minimum':0,'maximum':4294967295,'default':0},
    'prompt':{'type':'string','maxLength':2048,'default':''}}}


async def upscale_descriptor(runtime,principal,model=None):
    from ai2apps.agents.parameter_forms import schema_fields
    from .upscaling import models_for_builtin
    models=models_for_builtin(runtime)['items']
    fields=schema_fields(UPSCALE_SCHEMA)
    return {'effective_schema':deepcopy(UPSCALE_SCHEMA),'selection_required':True,
        'fields':[{**f,'type':'model'} if f['key']=='model_id' else f for f in fields],
        'models':models,'configuration_required':not any(m['ready'] for m in models),
        'install':{'appId':APP,'capability':'video.upscaling','requirements':{}},
        'warnings':[{'zh':'视频最多 1 GiB；分段和时长遵循所选模型声明，不支持自定义提示词的模型不能填写提示词。','en':'Video up to 1 GiB. Segmentation/duration follow the selected model declaration; prompts require declared custom-prompt support.'}]}


async def upscale(runtime,args,context):
    from jsonschema import Draft202012Validator
    from ai2apps.api.ownership import authorize_session
    from .upscaling import start_builtin_job
    if not context.session_id or not context.invocation_id:raise ToolProviderError('Upscaling requires a durable Session invocation')
    principal=principal_for(runtime,context);authorize_session(runtime,principal,context.session_id)
    Draft202012Validator(UPSCALE_SCHEMA).validate(args)
    path,name,media=source(runtime,principal,context.session_id,args['video_id'])
    if not media.startswith('video/'):raise ToolProviderError('Select a video material')
    host,_,_=runtime.extension_manager.launch_app(APP,principal=principal)
    scope={'actor_id':principal.actor_user_id,'installation_id':principal.installation_id,'app_instance_id':host.id,'studio_id':APP}
    result=await start_builtin_job(runtime,scope,principal,content=path,filename=name,media_type=media,
        model_id=args['model_id'],seed=args.get('seed',0),prompt=args.get('prompt',''),key='aaat:'+context.invocation_id)
    job=runtime.studio_jobs.for_run(result['id'],principal)
    if not job:raise ToolProviderError('Upscaling did not create a durable task')
    job=await follow(runtime,principal,context,job)
    return {'status':'completed','studio_job_id':job['id'],'studio_run_id':job['run_id'],'files':[import_output(runtime,context,job)],
        'aaat_context':{'schema':'ai2apps.aaat-result-context/v1','status':'complete','data_trust':'untrusted',
            'scope':{'video_id':args['video_id'],'model_id':args['model_id']},'coverage':{'scale':2}}}


def install_upscale(runtime,register):
    register('video.upscale',APP,'视频超分辨率 / Upscale video',
        'Upscale an owned video reference 2x with an explicitly selected installed video-upscaling model. Uses existing Video Studio durable execution, bounded temporal/segmentation declarations and shared output. Source video up to 1 GiB; no source copy. Missing model preserves parameters for Desktop setup.',
        UPSCALE_SCHEMA,lambda a,c:upscale(runtime,a,c),mini='ai2apps.video.upscaling',descriptor=lambda p,m=None:upscale_descriptor(runtime,p,m),
        effects=('artifact.create',),selection_required=True,timeout_ms=86400000,
        field_labels={k:{'zh':z,'en':e} for k,z,e in [('video_id','视频素材','Video material'),('model_id','超分辨率模型','Upscaling model'),('seed','随机种子','Seed'),('prompt','提示词（需模型支持）','Prompt (model support required)')]},
        agent_context={'schema':'ai2apps.aaat-declaration/v1','instructions':[
            'Select a model from the current owner descriptor, never infer readiness or support from its name. Use a current Session/Gallery video ID, never a raw path.',
            'Existing model capability constraints determine source dimensions, temporal limits and segmentation. Do not bypass a whole-clip or frame limit by selecting another workflow after execution.',
            'Retain the source reference and parameters when setup is needed. Wait for the durable job and published result; do not claim success from acceptance or a progress message.'],
            'result_semantics':{'files':'Actual upscaled MP4 from the existing Video Studio shared output, also a Session-owned reference.'}},
        form_summary={'zh':'选择已配置模型进行 2× 视频放大，使用原文件引用并在后台运行。','en':'Upscale video 2× using a configured model and an original file reference in the background.'})
