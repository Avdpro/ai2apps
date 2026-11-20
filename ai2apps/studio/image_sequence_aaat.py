"""Typed SDK for Package-authored bounded illustration sequences, without story semantics."""
import hashlib
import re
from ai2apps.services import ToolProviderError
from ai2apps.services.aaat import principal_for
from .package_generation_aaat import owner,follow,reserve,receipt,image_source
from .image_workflow import Plan,asset_root,save_asset,submit_plan,model_catalog,CAPABILITY

async def describe(runtime,principal,action,mini,spec):
    catalog=await model_catalog(runtime,principal)
    return {'models':[{'id':m['id'],'label':m.get('label',m['id']),'ready':m['ready']} for m in catalog['items']],
            'configuration_required':not any(m['ready'] for m in catalog['items']),'model_field':'model_id'}

def deliver(runtime,context,host,result):
    """Expose only a verified artifact from this workflow's owning Host."""
    url=result.get('result',{}).get('downloadUrl','')
    match=re.fullmatch(r'/v1/platform/sessions/([A-Za-z0-9_-]+)/artifacts/([A-Za-z0-9_-]+)/download',url)
    if not match:raise ToolProviderError('Workflow completed without a valid output artifact')
    sid,aid=match.groups()
    if runtime.extension_manager.sessions.get(sid).app_instance_id!=host.id:
        raise ToolProviderError('Workflow output does not belong to its Host')
    artifact=runtime.workspace.get_artifact(sid,aid)
    if artifact.media_type!='image/png':raise ToolProviderError('Workflow output is not a PNG image')
    if sid!=context.session_id:
        artifact=runtime.workspace.import_artifact(context.session_id,runtime.workspace.artifact_path(artifact),
            name=artifact.name,media_type=artifact.media_type,
            metadata={'studioRunId':result.get('studio_run_id'),'source_artifact_id':aid})
    return result|{'files':[{'url':f'/v1/platform/sessions/{context.session_id}/artifacts/{artifact.id}/download',
        'artifact_id':artifact.id,'filename':artifact.name,'media_type':artifact.media_type}]}

async def execute(runtime,args,context,mini,spec):
    old=reserve(runtime,context,args,check_only=True)
    if old:return old
    principal=principal_for(runtime,context)
    host,mounted,broker=owner(runtime,principal,spec['host'],mini['id'])
    if CAPABILITY not in mounted.capabilities:raise ToolProviderError('Package does not declare image.workflow')
    choices=await model_catalog(runtime,principal)
    model=args.get('model_id') or choices['preferred']
    chosen=next((m for m in choices['items'] if m['id']==model and m['ready']),None)
    if not chosen:raise ToolProviderError('Select an available drawing model; no substitute was selected')
    # The private namespace matches the provider App key used by the UI.
    provider=runtime.extension_manager.instance_entry(mounted.mount['app_instance_id'],principal=principal)['app_key']
    root=asset_root(runtime,principal,provider)
    steps=[]
    for step in args['steps']:
        refs=[]
        for identifier in step.get('references',[]):
            path,_,_=image_source(runtime,principal,context.session_id,identifier)
            if path.stat().st_size>20*1024*1024:raise ToolProviderError('Reference exceeds 20 MiB')
            refs.append(save_asset(root,path.read_bytes()))
        steps.append({'prompt':step['prompt'],'caption':step.get('caption',''),'references':list(dict.fromkeys(refs)),
                      'previous':args.get('previous',2)})
    plan=Plan(key='aaat-'+hashlib.sha256(context.invocation_id.encode()).hexdigest()[:32],title=args['title'],
        model=model,size=args.get('size','1024x1024'),quality=args.get('quality','auto'),
        reference_limit=min(4,chosen['referenceLimit']),columns=args.get('columns',2),steps=steps)
    from ai2apps.images.parameters import validate_size
    validate_size(plan.size,chosen['size'])
    if plan.quality not in chosen['qualities'] or 'png' not in chosen['formats']:raise ToolProviderError('Unsupported quality or PNG format')
    broker.mounted_mini_app(spec['host'],'aaat',principal=principal)
    # Reserve only after all local input validation; uncertain submissions are never replayed.
    old=reserve(runtime,context,args)
    if old:return old
    job=await submit_plan(runtime,principal,{'provider':provider,'mini_id':mini['id'],'version':mini['version']},
        {'actor_id':principal.actor_user_id,'installation_id':principal.installation_id,'app_instance_id':host.id,'studio_id':spec['host']},plan)
    result=await follow(runtime,principal,context,job)
    broker.mounted_mini_app(spec['host'],'aaat',principal=principal)
    result=deliver(runtime,context,host,result)
    receipt(runtime,context,result)
    return result
