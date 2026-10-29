"""Trusted AaAT adapters for first-party Apps; business services retain authority."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import inspect
import json
import time
from types import SimpleNamespace
from jsonschema import Draft202012Validator
from ai2apps.services import ServiceRuntimeMode, ServiceInstanceStatus, ToolProviderError
from ai2apps.services.capability_routing import CapabilityProvider
from ai2apps.services.aaat import principal_for
from ai2apps.todo.aaat import store as todo_store


def obj(properties, required=()):
    return {'type': 'object', 'properties': properties, 'required': list(required), 'additionalProperties': False}


def string(title='', maximum=500):
    return {'type': 'string', 'minLength': 1, 'maxLength': maximum, **({'title': title} if title else {})}


LIMIT = {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 20, 'title': '结果数量 / Limit'}



def gallery(runtime):
    from ai2apps.gallery import GalleryRepository
    return GalleryRepository(runtime.database, runtime.config.paths.artifacts_path / 'gallery')


def public_asset(asset):
    # Storage locators and filesystem paths stay behind the owning App's API.
    return {k: v for k, v in asset.items() if k in {
        'id', 'name', 'kind', 'media_type', 'size_bytes', 'status', 'created_at', 'updated_at'}}


async def local_operation(runtime, name, args, context):
    principal = principal_for(runtime, context)
    owner = principal.actor_user_id
    if name == 'gallery.search':
        repo = gallery(runtime)
        return {'collections': list(repo.list_collections(owner)), 'assets': [public_asset(a) for a in repo.list_assets(
            owner, search=args.get('query'), kind=args.get('kind'), collection_id=args.get('collection_id'), limit=args.get('limit', 20))]}
    if name == 'gallery.get':
        return {'asset': public_asset(gallery(runtime).get_asset(owner, args['asset_id']))}
    raise ToolProviderError('Unknown App operation')


async def quick_read(runtime, args, context):
    from ai2apps.api.readaloud import QuickReadRequest
    if not context.invocation_id or not context.session_id: raise ToolProviderError('Quick Read requires a durable Session invocation')
    principal = principal_for(runtime, context)
    from ai2apps.api.ownership import authorize_session
    authorize_session(runtime, principal, context.session_id)
    payload = QuickReadRequest(**args).model_dump()
    instance, _, _ = runtime.extension_manager.launch_app('ai2apps.readaloud', principal=principal)
    job = runtime.studio_jobs.submit(principal=principal, app_instance_id=instance.id,
        studio_id='ai2apps.readaloud', mini_app_id='ai2apps.audio.quick-read', kind='quick-read',
        key='aaat:' + context.invocation_id, payload=payload)
    deadline = time.monotonic() + 850
    while job['status'] not in ('succeeded', 'failed', 'cancelled', 'interrupted', 'publish_failed'):
        await context.report_progress('快速朗读 / Quick Read: ' + job['status'], content={'studio_job_id': job['id']})
        if time.monotonic() >= deadline: raise ToolProviderError('Quick Read is still running; studio_job_id=' + job['id'])
        await asyncio.sleep(1)
        job = runtime.studio_jobs.get(job['id'], principal)
    if job['status'] != 'succeeded': raise ToolProviderError('Quick Read ' + job['id'] + ': ' + str(job.get('error') or job['status']))
    from ai2apps.studio.voice_aaat import output
    _, file = output(runtime, principal, context.session_id, job)
    return {'studio_job_id': job['id'], 'status': 'completed', **(job.get('result') or {}), 'files': [file]}


async def transcribe(runtime, args, context):
    from ai2apps.readaloud.parameter_form import complete
    from ai2apps.agents.parameter_forms import FORMS
    if not context.invocation_id or not context.session_id: raise ToolProviderError('Transcription requires a durable Session invocation')
    principal = principal_for(runtime, context)
    await context.report_progress('正在转写音频 / Transcribing audio', progress=0.1)
    result = await complete(runtime, principal, FORMS['voice.transcribe'], args, SimpleNamespace(session_id=context.session_id,id=context.invocation_id))
    return {**result, 'status': 'completed'}


async def detailed_transcription(runtime, args, context, host_app='ai2apps.readaloud',mini_app_id=None):
    from ai2apps.studio.capability_broker import MountedMiniApp, _declared_capabilities
    from ai2apps.studio.video_jobs import submit_package
    if not context.invocation_id: raise ToolProviderError('Detailed transcription requires a durable invocation')
    principal=principal_for(runtime,context)
    definition,declaration=runtime.extension_manager._studio_mini_app_definition(host_app,mini_app_id or 'ai2apps.media-voice.transcription',principal)
    capabilities=_declared_capabilities(declaration)
    if 'audio.detailed_transcription' not in capabilities: raise ToolProviderError('Installed Mini-App does not declare detailed transcription')
    reference_input=args['audio_artifact_id'].startswith('attc_')
    if args['audio_artifact_id'].startswith('gala_'):
        from ai2apps.gallery import GalleryRepository
        record,source=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery').asset_path(principal.actor_user_id,args['audio_artifact_id'])
        if record['status']!='active':raise ToolProviderError('Gallery material is deleted')
        asset=SimpleNamespace(media_type=record['media_type']);filename=record['name']
    elif reference_input:
        asset=runtime.documents.get(context.session_id,args['audio_artifact_id'])
        source=runtime.documents.source_path(context.session_id,asset.id)
        filename=asset.filename
    else:
        asset=runtime.workspace.get_artifact(context.session_id,args['audio_artifact_id'])
        if asset.size_bytes>100*1024*1024: raise ToolProviderError('Stored audio/video input exceeds 100 MiB; select a file reference')
        source=runtime.workspace.artifact_path(asset).read_bytes();filename=asset.name
    if not asset.media_type.startswith(('audio/','video/')): raise ToolProviderError('Select an audio/video material')
    host,_,_=runtime.extension_manager.launch_app(host_app,principal=principal)
    provider,_,_=runtime.extension_manager.launch_app(definition['package_id'],principal=principal)
    mounted=MountedMiniApp({'app_instance_id':provider.id,'context':{'studioInstanceId':host.id}},declaration,capabilities)
    options={k:v for k,v in args.items() if k!='audio_artifact_id'}
    job=submit_package(runtime,principal,mounted,'audio.detailed_transcription',options,
        source,filename,asset.media_type,key='aaat:'+context.invocation_id,studio_id=host_app)
    deadline=time.monotonic()+850
    while job['status'] not in ('succeeded','failed','cancelled','interrupted','publish_failed'):
        await context.report_progress('详细转写 / Detailed transcription: '+job['status'],content={'studio_job_id':job['id'],'studio_run_id':job['run_id'],'result':job.get('result')})
        if time.monotonic()>=deadline: raise ToolProviderError('Transcription still running; studio_job_id='+job['id'])
        await asyncio.sleep(1)
        job=runtime.studio_jobs.get(job['id'],principal)
    if job['status']!='succeeded': raise ToolProviderError('Transcription '+job['id']+': '+str(job.get('error') or job['status']))
    result=job.get('result') or {}
    # Read back only an output from the owner's shared Voice Artifact session.
    url=result.get('downloadUrl','')
    text=''
    if url.startswith('/v1/platform/sessions/'):
        session=url.split('/')[4];identifier=url.split('/')[-2]
        expected=runtime.video_tasks.artifact_session() if host_app=='ai2apps.video-studio' else runtime.readaloud_tasks._artifact_session(principal.actor_user_id)
        if session!=expected:raise ToolProviderError('Transcription output left its owner scope')
        output=runtime.workspace.get_artifact(session,identifier)
        if output.media_type in ('application/json','text/plain','text/markdown','application/x-subrip'):
            text=runtime.workspace.artifact_path(output).read_bytes()[:1024*1024].decode('utf-8',errors='replace')
    return {**result,'studio_job_id':job['id'],'studio_run_id':job['run_id'],'text':text[:24000],
        'truncated':len(text)>24000,'untrusted':True,'status':'completed'}


def install(runtime):
    from ai2apps.intelligence.agent_interaction import DECLARATIONS
    from ai2apps.agents.app_interactions import CAPABILITIES, register_capability
    for key,descriptor in DECLARATIONS.items():
        if key not in CAPABILITIES:register_capability(descriptor)
    router = runtime.app_capability_router
    repo, registry = runtime.services, runtime.service_registry
    service = repo.ensure_service(service_key='ai2apps.builtin-app-adapters', package_id='ai2apps.core',
        package_version='0.1.0', display_name='Built-in App AaAT adapters', runtime_mode=ServiceRuntimeMode.IN_PROCESS,
        capabilities=('app.invoke',), config={})
    instance = repo.ensure_instance(service_id=service.id, provider_key='builtin:app-adapters', status=ServiceInstanceStatus.RUNNING,
        endpoint=None, health={'status': 'ok'})
    active_adapter_tools = set()

    def register(name, app, title, summary, schema, execute, *, mini=None, descriptor=None, effects=(), capabilities=(), existing=False, agent_context=None, selection_required=False, timeout_ms=30000, open_parameters=False, priority=100, discovery_context=None, field_labels=None, option_labels=None, form_name=None, form_summary=None, provider_version="1", invocation_policy=None, provider_id_override=None):
        provider_id = provider_id_override or app + '.' + name
        async def describe(principal, model=None):
            from ai2apps.agents.parameter_forms import schema_fields, present_fields
            result=await descriptor(principal,model) if descriptor else {'effective_schema':deepcopy(schema),'selection_required':selection_required}
            result['fields']=present_fields(result.get('fields') or schema_fields(result['effective_schema']),field_labels,option_labels)
            return result
        async def prepare(args, context):
            # Shared with parameter forms: validation is read-only and does not
            # require execution authority. The handler retains the Session guard.
            declaration=await describe(principal_for(runtime, context))
            if declaration.get('configuration_required'):raise ValueError('Provider requires model configuration; parameters and materials are preserved')
            active_schema = declaration.get('effective_schema', schema)
            payload = deepcopy(args)
            for key, spec in active_schema.get('properties', {}).items():
                if key not in payload and 'default' in spec: payload[key] = deepcopy(spec['default'])
            Draft202012Validator(active_schema).validate(payload)
            return payload
        async def handler(payload, context):
            if not context.session_id and not existing: raise ToolProviderError('App capability requires an owned Session')
            # Recheck authority immediately before business execution. Parameter
            # validation belongs to prepare, whose failure proves no submission.
            from ai2apps.api.ownership import authorize_session
            if context.session_id: authorize_session(runtime, principal_for(runtime, context), context.session_id)
            await context.report_progress(title, progress=0.05, content={'app_id': app, 'mini_app_id': mini})
            value = execute(payload, context)
            result = await value if inspect.isawaitable(value) else value
            return {**result, 'app_id': app, 'mini_app_id': mini}
        router.register(CapabilityProvider(provider_id, name, app, handler, mini_app_id=mini, priority=priority, version=provider_version,
            describe=describe, prepare=prepare, display_name=form_name or ({'zh':title.split(' / ',1)[0],'en':title.split(' / ',1)[1]} if ' / ' in title else title), summary=form_summary or summary, agent_context=agent_context, discovery_context=discovery_context, invocation_policy=invocation_policy))
        async def routed(args, context): return await router.invoke(name, args, context)
        if existing:
            tool = repo.get_tool(name)
            routed_schema=deepcopy(schema)
            routed_schema['properties'].update(provider={'type':'string'},parameters={'type':'object'})
            repo.ensure_tool(service_id=tool.service_id,qualified_name=name,display_name=tool.display_name,description=tool.description,
                input_schema=routed_schema,output_schema=tool.output_schema,effects=tool.effects,
                required_capabilities=tool.required_capabilities,capability_rules=tool.capability_rules,
                retry_policy=tool.retry_policy,timeout_ms=tool.timeout_ms)
            registry.bind_tool(name, provider_key=registry.bound_tool(name).provider_key, handler=routed)
        else:
            active_adapter_tools.add(name)
            tool_schema = deepcopy(schema)
            if open_parameters: tool_schema['additionalProperties'] = True
            tool_schema['properties'].update(provider={'type': 'string'}, parameters={'type': 'object'})
            repo.ensure_tool(service_id=service.id, qualified_name=name, display_name=title,
                description=summary + ' Use app.collect_parameters to edit missing parameters. Results identify the owning App/Mini-App. Cancellation is not success.',
                input_schema=tool_schema, output_schema={'type': 'object'}, effects=effects,
                required_capabilities=capabilities, timeout_ms=timeout_ms)
            registry.bind_tool(name, provider_key=instance.provider_key, handler=routed)

    from ai2apps.packages.aaat import install as install_discover
    install_discover(runtime,register)

    from ai2apps.todo.aaat import install as install_todo
    install_todo(runtime,register)

    definitions = [
        ('gallery.search', 'ai2apps.gallery', '查找素材 / Search Gallery', 'Find owned assets and collections. Returns stable asset IDs and metadata.', obj({'query': {'type':'string','maxLength':500}, 'collection_id': string(), 'kind': {'enum':['image','video','audio','web','document','file']}, 'limit': LIMIT})),
        ('gallery.get', 'ai2apps.gallery', '读取素材信息 / Read asset', 'Read owned asset metadata for subsequent App asset selection.', obj({'asset_id': string()}, ['asset_id'])),
    ]
    for name, app, title, summary, schema in definitions:
        register(name, app, title, summary, schema, lambda a,c,n=name:local_operation(runtime,n,a,c),form_summary={'zh':'查找素材库中的可访问素材及集合。','en':summary},field_labels={k:{'zh':z,'en':e} for k,z,e in [('query','搜索内容','Search query'),('collection_id','集合 ID','Collection ID'),('kind','素材类型','Material type'),('limit','结果数量','Result limit'),('asset_id','素材 ID','Asset ID')]},option_labels={'kind':{k:{'zh':z,'en':e} for k,z,e in [('image','图片','Image'),('video','视频','Video'),('audio','音频','Audio'),('web','网页','Web page'),('document','文档','Document'),('file','文件','File')]}})
    from ai2apps.intelligence.aaat import install as install_intelligence
    install_intelligence(runtime, register)

    # Reuse Knowledge's complete service implementation, ACLs, retriever and citations.
    for name in ('knowledge.search', 'knowledge.get', 'knowledge.add_text'):
        tool, bound = repo.get_tool(name), registry.bound_tool(name)
        register(name, 'ai2apps.knowledge', tool.display_name, tool.description, tool.input_schema,
            bound.handler, existing=True,form_summary={'zh':'搜索、读取或保存可访问的本地知识。','en':tool.description},form_name={'zh':{'knowledge.search':'搜索知识','knowledge.get':'读取知识','knowledge.add_text':'保存知识'}[name],'en':{'knowledge.search':'Search Knowledge','knowledge.get':'Read Knowledge','knowledge.add_text':'Save to Knowledge'}[name]},field_labels={k:{'zh':z,'en':e} for k,z,e in [('query','搜索内容','Search query'),('limit','结果数量','Result limit'),('item_id','知识条目 ID','Knowledge item ID'),('title','标题','Title'),('text','正文','Text'),('scope','可见范围','Visibility'),('kind','内容类型','Content type'),('source_url','来源链接','Source URL'),('tags','标签','Tags'),('bucket_ids','知识桶 ID','Knowledge bucket IDs'),('source_app_id','来源应用 ID','Source App ID'),('source_session_id','来源会话 ID','Source session ID'),('source_after','来源时间下限','Source after'),('source_before','来源时间上限','Source before')]},option_labels={'scope':{'private':{'zh':'私有','en':'Private'},'installation':{'zh':'此安装实例','en':'This installation'}},'kind':{k:{'zh':z,'en':e} for k,z,e in [('image','图片','Image'),('audio','音频','Audio'),('video','视频','Video'),('webpage','网页','Web page'),('document','文档','Document'),('chat','对话','Chat'),('artifact','产物','Artifact'),('note','笔记','Note')]}})

    voice_labels={k:{'zh':z,'en':e} for k,z,e in [('text','朗读文本','Text to read'),('model_id','语音模型','Speech model'),('voice','音色','Voice'),('voice_profile_id','角色 ID','Character ID'),('speed','语速','Speed'),('audio_artifact_id','音频或视频','Audio or video'),('profile','转写方案','Transcription profile'),('language','语言','Language'),('word_timestamps','逐词时间戳','Word timestamps'),('diarization','区分说话人','Speaker diarization'),('output_format','输出格式','Output format')]}
    quick_schema = obj({'text': string('朗读文本 / Text',10000), 'model_id': string('语音模型 / Speech model',255),
        'voice': string('音色 / Voice',255), 'voice_profile_id': string('角色 ID / Character ID',255),
        'speed': {'type':'number','minimum':0.5,'maximum':2,'default':1,'title':'语速 / Speed'}}, ['text','model_id'])
    async def quick_descriptor(principal, model=None):
        from ai2apps.model_providers import list_package_models
        from ai2apps.agents.parameter_forms import schema_fields
        fields = schema_fields(quick_schema)
        return {'effective_schema':quick_schema, 'fields':[{**f,'type':'model'} if f['key']=='model_id' else f for f in fields],
            'selection_required':True,
            'configuration_required':not any(m.checkpoint_ready for m in list_package_models(runtime) if m.model_type=='audio_tts'),
            'install':{'appId':'ai2apps.readaloud','capability':'audio.speech_generation','requirements':{'operations':['speech_generation']}},
            'models':[{'id':m.id,'label':m.display_name,'ready':m.checkpoint_ready} for m in list_package_models(runtime) if m.model_type=='audio_tts']}
    register('voice.quick_read','ai2apps.readaloud','快速朗读 / Quick Read','Render text using the shared durable Voice Studio queue and publish to host Preview & Output.', quick_schema,
        lambda a,c:quick_read(runtime,a,c), mini='ai2apps.audio.quick-read', descriptor=quick_descriptor, effects=('artifact.create',),timeout_ms=900000,field_labels=voice_labels,form_summary={'zh':'使用语音工作室队列朗读文本，结果显示在共享输出区。','en':'Read text through Voice Studio and publish to shared Output.'})
    from ai2apps.readaloud.parameter_form import install as voice_forms
    from ai2apps.agents.parameter_forms import FORMS
    voice_forms()
    voice_form = FORMS['voice.transcribe']
    async def transcribe_descriptor(principal, model=None):
        from ai2apps.model_providers import list_package_models
        return {'effective_schema':voice_form.schema, 'fields':list(voice_form.fields),
            'selection_required':True,
            'configuration_required':not any(m.checkpoint_ready for m in list_package_models(runtime) if m.model_type=='audio_stt'),
            'install':{'appId':'ai2apps.readaloud','capability':'audio.speech_recognition','requirements':{'operations':['speech_recognition']}},
            'models':[{'id':m.id,'label':m.display_name,'ready':m.checkpoint_ready} for m in list_package_models(runtime) if m.model_type=='audio_stt']}
    register('voice.transcribe','ai2apps.readaloud','音频转写 / Transcribe audio','Transcribe an owner-scoped Voice audio material and publish transcript JSON to shared Voice Studio Output.',voice_form.schema,
        lambda a,c:transcribe(runtime,a,c),descriptor=transcribe_descriptor,effects=('artifact.create',),timeout_ms=900000,priority=-10,form_summary={'zh':'转写所选音频，结果保存到语音工作室共享输出区。','en':'Transcribe selected audio into shared Voice Studio Output.'})
    from ai2apps.studio.video_aaat import install as install_video_processing
    install_video_processing(runtime, register)
    from ai2apps.studio.video_aaat import install_upscale
    install_upscale(runtime, register)

    from ai2apps.browser.builtin_mini_apps import install as install_browser_minis
    install_browser_minis(runtime, register)
    from ai2apps.browser.goal_aaat import install as install_browser_goal
    install_browser_goal(runtime, register)
    from ai2apps.browser.social import install as install_social
    install_social(runtime,register)
    from ai2apps.browser.travel_reader import install as install_travel_readers
    install_travel_readers(runtime)
    from ai2apps.studio.chat_generation import install as install_chat_generation
    install_chat_generation(runtime,register)
    from ai2apps.studio.app_chat import install_tools as install_studio_chat_tools
    install_studio_chat_tools(runtime,register)
    repo.retire_unseen_tools(service.id, active_adapter_tools)
    import logging
    logging.getLogger(__name__).info('Built-in App AaAT adapters loaded from %s',__file__)
    return register
