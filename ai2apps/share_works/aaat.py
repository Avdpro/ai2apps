"""Share Works owner AaAT adapter; UI and Agent use the same publication service."""
import asyncio
import hashlib
from contextlib import ExitStack
from pathlib import Path
from ai2apps.services import ToolProviderError
from ai2apps.services.aaat import principal_for
from .service import HOST, MINI
from .artifacts import MAX_INPUT


def consent(runtime,args,context,provider_id,*,description='snapshot, destination, space, title and digest'):
    if not context.invocation_id or not context.trace_id:raise ToolProviderError('Publishing requires a durable confirmed invocation')
    run=runtime.agents.get_run(context.trace_id)
    if run.session_id!=context.session_id:raise ToolProviderError('Confirmation Session mismatch')
    provider=runtime.app_capability_router.providers[provider_id]
    for item in reversed(runtime.agents.list_interactions(run.id)):
        if item.request.get('control')!='parameter_form' or item.ui_hints.get('provider')!=provider_id:continue
        from ai2apps.agents.form_continuation import selected_form
        try:
            form=selected_form(runtime.database,item)
            if form.key!=provider_id or form.provider_version!=provider.version:break
        except (ValueError,RuntimeError):break
        result=(item.response or {}).get('result',{})
        values=dict(result.get('arguments',{}));values.pop('provider',None)
        if (item.status.value=='submitted' and (item.response or {}).get('status')=='completed'
            and item.ui_hints.get('provider_version')==provider.version and result.get('capability')==provider.capability
            and result.get('user_confirmed') is True and result.get('configure_only') is True
            and values==args):return item
        break
    raise ToolProviderError(f'Review and confirm this exact {description} in the Share Works publish form first')


async def prepare(runtime,args,context,owner):
    service=runtime.share_works
    if 'export_id' in args:
        data,filename=await service.export_input(owner,args['export_id'])
    else:
        if args['artifact_id'].startswith('attc_'):
            asset=runtime.documents.get(context.session_id,args['artifact_id'])
            path=runtime.documents.source_path(context.session_id,asset.id)
            filename=asset.filename
        else:
            asset=runtime.workspace.get_artifact(context.session_id,args['artifact_id'])
            path=runtime.workspace.artifact_path(asset)
            filename=asset.name
        if Path(filename).suffix.lower() not in ('.html','.htm','.zip'):raise ToolProviderError('Select an HTML or static ZIP artifact from this Session')
        if path.stat().st_size>MAX_INPUT:raise ToolProviderError('Artifact exceeds publication input limit')
        data=await asyncio.to_thread(path.read_bytes)
    destination=args['destination'];previous=service.preferences(owner)['targets'].get(destination,{})
    repo=args.get('repo') or previous.get('repo')
    if not repo:raise ToolProviderError('Choose an existing public static space; no space is created automatically')
    checked=await service.check(owner,destination,repo)
    url=args.get('application_url') or checked.get('application_url') or (previous.get('application_url') if previous.get('repo')==repo else None)
    if not url:raise ToolProviderError('Platform did not return an application URL; provide the existing direct application URL')
    snapshot=await service.prepare(owner,data,filename,args.get('title') or Path(filename).stem,destination,repo,url)
    return {'status':'prepared','snapshot':snapshot,'publish_parameters':{'snapshot_id':snapshot['id'],'destination':destination,'repo':repo,'title':snapshot['title'],'digest':snapshot['digest']},'published':False}


async def confirmation_policy(args,context):
    # Execution-scope exemptions never replace this owner's public-share review.
    # The normal shared exact form receipt remains usable.
    return False


async def prepare_social(runtime, args, context, owner):
    with ExitStack() as stack:
        sources = []
        for ref in args.get('artifact_ids', []):
            if ref.startswith('attc_'):
                asset = runtime.documents.get(context.session_id, ref)
                path = runtime.documents.source_path(context.session_id, asset.id)
                filename = asset.filename
            else:
                asset = runtime.workspace.get_artifact(context.session_id, ref)
                path = runtime.workspace.artifact_path(asset)
                filename = asset.name
            sources.append((filename, stack.enter_context(path.open('rb'))))
        return await runtime.share_works.social.prepare(
            owner, args['destination'], args.get('title', ''), args.get('body', ''), sources)


def install(runtime,register,mini):
    import logging
    logging.getLogger(__name__).info('Share Works AaAT v2 loaded from %s',__file__)
    for spec in mini['aaat']['exports']:
        name=spec['name'];provider_id=MINI+'.'+name.rsplit('.',1)[-1]
        async def execute(args,context,name=name,provider_id=provider_id):
            owner=principal_for(runtime,context).actor_user_id
            service=runtime.share_works;service.authorize(owner)
            if name=='share.social_prepare':
                return await prepare_social(runtime,args,context,owner)
            if name=='share.social_status':
                return service.social.view(owner,service.social.draft(owner,args['draft_id']))
            if name=='share.x_publish':
                draft=service.social.draft(owner,args['draft_id'])
                if draft['destination']!='x' or service.social.approval_parameters(draft)!=args:
                    raise ToolProviderError('X draft or account changed; prepare and review again')
                consent(runtime,args,context,provider_id,description='X account, post and media')
                row=service.social.publish_x(owner,draft['id'],draft['digest'],approved=True)
                if row.get('task_id'):
                    try:await runtime.system_tasks.follow(owner,row['task_id'],context,app_id=HOST,timeout=840)
                    except TimeoutError:pass
                    except asyncio.CancelledError:
                        runtime.system_tasks.cancel(owner,row['task_id']);raise
                return service.social.view(owner,draft)
            if name=='share.destinations':return service.preferences(owner)
            if name=='share.prepare':return await prepare(runtime,args,context,owner)
            if name=='share.history':
                if args.get('request_id'):return service.status(owner,args['request_id'])
                return {'items':[service.status(owner,row['request_id']) for row in service.store.recent(owner)[:args.get('limit',20)]]}
            if name=='share.publish':
                snapshot=service.snapshot(owner,args['snapshot_id'])
                expected={'destination':snapshot['provider'],'repo':snapshot['repo'],'title':snapshot['title'],'digest':snapshot['digest']}
                if any(args[k]!=v for k,v in expected.items()):raise ToolProviderError('Snapshot or destination changed; prepare and confirm again')
                receipt=consent(runtime,args,context,provider_id)
                request_id='aaat_'+hashlib.sha256(receipt.id.encode()).hexdigest()
                row=service.publish(owner,snapshot['id'],request_id,True)
                try:await runtime.system_tasks.follow(owner,row['task_id'],context,app_id=HOST,timeout=840)
                except TimeoutError:pass
                except asyncio.CancelledError:
                    runtime.system_tasks.cancel(owner,row['task_id']);raise
                return service.status(owner,request_id)
            row=service.store.get('publications',owner,args['request_id'])
            if name=='share.verify':
                try:await service.verify(owner,row)
                except Exception as error:
                    from .service import verification_failure
                    row['last_verification_error']=verification_failure(error)[0]
                    service.store.save('publications',owner,args['request_id'],row)
                return service.status(owner,args['request_id'])
            if name=='share.cancel':
                if row.get('task_id'):runtime.system_tasks.cancel(owner,row['task_id'])
                return {**service.status(owner,args['request_id']),'uploaded_files_may_remain':row.get('dispatched',False)}
            raise ToolProviderError('Unsupported Share Works operation')
        publishing=name in {'share.publish','share.x_publish'}
        register(name,HOST,spec['displayName']['zh']+' / '+spec['displayName']['en'],spec['summary']['en'],spec['inputSchema'],execute,
            mini=MINI,provider_id_override=provider_id,provider_version=mini['version'],
            field_labels={field['key']:field['label'] for field in spec['fields']},
            selection_required=publishing,invocation_policy=confirmation_policy if publishing else None,effects=tuple(spec['options']['effects']),
            timeout_ms=900000 if publishing else 120000,
            form_name=spec['displayName'],form_summary=spec['summary'],agent_context=spec['agentContext'])
