"""Bounded Package-owned project transforms and durable image-sequence execution.

The Host knows no project schema: signed pure JavaScript receives data and returns
queries, a validated plan or a draft patch. It has no Host credentials or bridge.
"""
import asyncio
import hashlib
import json
from ai2apps.services import ToolProviderError
from ai2apps.services.aaat import principal_for
from .package_generation_aaat import owner, reserve, receipt, follow
from .image_sequence_aaat import deliver
from .image_workflow import Plan, model_catalog, submit_plan, CAPABILITY, asset_root, read_asset
from .repository import StudioRepository, StudioRepositoryError

async def transform(runtime,principal,instance,spec,action,data):
    from ai2apps.browser.background_bidi import BackgroundBiDi
    from ai2apps.browser.background_page import BackgroundPage
    from ai2apps.helper_control import HelperControlClient
    scripts=spec['options']['scripts']
    if not isinstance(scripts,list) or not 1<=len(scripts)<=4:raise ToolProviderError('Invalid project transform resources')
    source='\n'.join(runtime.extension_manager.resolve_app_resource(instance,p,principal=principal).read_text() for p in scripts)
    if len(source.encode())>256000 or len(json.dumps(data).encode())>4*1024*1024:raise ToolProviderError('Project transform exceeds limit')
    helper=HelperControlClient.from_environment()
    if helper is None:raise ToolProviderError('Open Desktop to access the Package project interpreter')
    await asyncio.to_thread(helper.ensure_browser_host,actor_user_id=principal.actor_user_id)
    connection=BackgroundBiDi();user=None
    try:
        await connection.connect()
        user=(await connection.command('browser.createUserContext',{},timeout=10))['userContext']
        tab=await connection.command('browsingContext.create',{'type':'window','userContext':user,'background':True},timeout=10)
        page=BackgroundPage(connection,tab['context'])
        await page.call_json('''() => {document.head.innerHTML='<meta http-equiv="Content-Security-Policy" content="default-src \\'none\\'; connect-src \\'none\\'; form-action \\'none\\'; sandbox allow-scripts">'; return true;}''')
        # about:blank is not a secure context; supply UUID from native WebCrypto
        # without giving the transform a network origin or any Host credentials.
        await page.call_json('''() => {if(!crypto.randomUUID)crypto.randomUUID=()=>{
            const b=crypto.getRandomValues(new Uint8Array(16));b[6]=(b[6]&15)|64;b[8]=(b[8]&63)|128;
            const h=Array.from(b,x=>x.toString(16).padStart(2,'0')).join('');
            return h.slice(0,8)+'-'+h.slice(8,12)+'-'+h.slice(12,16)+'-'+h.slice(16,20)+'-'+h.slice(20);
        };return true;}''')
        await page.call_json('() => {\n'+source+'\nreturn true;}')
        value=await page.call_json('(action,data) => ImageProject[action](data)',(action,data),timeout=15)
        if len(json.dumps(value).encode())>4*1024*1024:raise ToolProviderError('Project result exceeds limit')
        return value
    finally:
        try:
            if user:await connection.command('browser.removeUserContext',{'userContext':user},timeout=10)
        finally:await connection.close()

async def describe(runtime,principal,model,mini,spec):
    # Read-only project discovery does not require a drawing model.
    if spec['options']['operation']=='query':return {'configuration_required':False}
    catalog=await model_catalog(runtime,principal)
    return {'models':[{'id':m['id'],'label':m.get('label',m['id']),'ready':m['ready']} for m in catalog['items']],
            'model_field':'model_id','configuration_required':not any(m['ready'] for m in catalog['items'])}

async def execute(runtime,args,context,mini,spec):
    principal=principal_for(runtime,context)
    host,mounted,broker=owner(runtime,principal,spec['host'],mini['id'])
    if CAPABILITY not in mounted.capabilities:raise ToolProviderError('Image workflow is not declared')
    scope={'actor_id':principal.actor_user_id,'installation_id':principal.installation_id,
           'app_instance_id':host.id,'studio_id':spec['host'],'mini_app_id':mini['id']}
    repository=StudioRepository(runtime.database)
    def current():
        saved=repository.get_draft(**scope)
        return saved or {'draft':{},'updatedAt':''}
    instance=mounted.mount['app_instance_id']
    snapshot=current()
    if spec['options']['operation']=='query':
        result=await transform(runtime,principal,instance,spec,'query',{'draft':snapshot['draft'],'args':args})
        broker.mounted_mini_app(spec['host'],'aaat',principal=principal)
        return {'status':'completed','library_revision':snapshot['updatedAt'],**result}
    if spec['options']['operation']!='create':raise ToolProviderError('Unsupported project operation')
    if old:=reserve(runtime,context,args,check_only=True):return old
    if args['library_revision']!=snapshot['updatedAt']:raise ToolProviderError('Project changed. Query it again before drawing.')
    catalog=await model_catalog(runtime,principal)
    prepared=await transform(runtime,principal,instance,spec,'prepare',{'draft':snapshot['draft'],'args':args,'catalog':catalog})
    plan=Plan.model_validate(prepared['plan'])
    plan.key='project-'+hashlib.sha256(context.invocation_id.encode()).hexdigest()[:32]
    from ai2apps.images.parameters import validate_size
    chosen=next((m for m in catalog['items'] if m['id']==plan.model and m['ready']),None)
    if not chosen:raise ToolProviderError('Selected drawing model is unavailable')
    validate_size(plan.size,chosen['size'])
    if plan.quality not in chosen['qualities'] or plan.reference_limit>chosen['referenceLimit']:
        raise ToolProviderError('Unsupported drawing settings')
    provider=runtime.extension_manager.instance_entry(instance,principal=principal)['app_key']
    root=asset_root(runtime,principal,provider)
    references={ref for step in plan.steps for ref in step.references}
    if sum(len(read_asset(root,ref)) for ref in references)>64*1024*1024:raise ToolProviderError('References exceed limit')
    broker.mounted_mini_app(spec['host'],'aaat',principal=principal)
    if current()['updatedAt']!=snapshot['updatedAt']:raise ToolProviderError('Project changed before submission')
    if old:=reserve(runtime,context,args):return old
    job=await submit_plan(runtime,principal,{'provider':provider,'mini_id':mini['id'],'version':mini['version']},
        {k:v for k,v in scope.items() if k!='mini_app_id'},plan)
    result=await follow(runtime,principal,context,job)
    broker.mounted_mini_app(spec['host'],'aaat',principal=principal)
    result=deliver(runtime,context,host,result)
    # Only the non-effectful draft transform may retry a concurrent edit. Never resubmit images.
    for attempt in range(3):
        latest=current()
        draft=await transform(runtime,principal,instance,spec,'commit',{'draft':latest['draft'],'prepared':prepared,'result':result})
        if draft.get('schema')!='ai2apps.mini-app-draft/v1' or draft.get('miniApp')!=mini['id']:raise ToolProviderError('Invalid project draft result')
        try:
            repository.save_draft(**scope,draft=draft,expected_updated_at=latest['updatedAt'])
            result.update(project=prepared['identity'],history_saved=True);break
        except StudioRepositoryError as error:
            if error.code!='studio_draft_conflict':raise
    else:result.update(history_saved=False,warnings=['Output completed; project history changed concurrently. Keep the job and output; do not redraw.'])
    receipt(runtime,context,result)
    return result
