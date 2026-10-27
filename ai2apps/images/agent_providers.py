"""Agent adapters for Imagine Studio's existing durable Mini-App jobs."""
import asyncio
import base64
from ai2apps.identity import IdentityRepository, RequestPrincipal
from ai2apps.services import ToolProviderError
from ai2apps.services.capability_routing import ProviderUnavailable
from ai2apps.studio.repository import StudioRepository
from ai2apps.studio.extended_jobs import submit

STUDIO = 'ai2apps.imagine-studio'


def principal_for(runtime, context):
    principal = (RequestPrincipal.legacy_local() if context.actor_user_id == 'local'
                 else IdentityRepository(runtime.database).local_principal_for(context.actor_user_id))
    if principal.installation_id != context.installation_id:
        raise ToolProviderError('Installation mismatch')
    return principal


def mini_app_handler(runtime_provider, workspace, model_selector, *, edit=False, mini_id=None):
    async def execute(arguments, context):
        runtime=runtime_provider()
        if runtime is None or getattr(runtime,'studio_jobs',None) is None:
            raise ProviderUnavailable('Imagine Studio job service is unavailable')
        if not context.session_id or not context.invocation_id:
            raise ToolProviderError('Image capability requires a durable Tool invocation')
        principal=principal_for(runtime,context)
        from ai2apps.model_manager import ModelManagerStore
        model=arguments.get('model') or model_selector(getattr(runtime,"model_manager",None) or ModelManagerStore(runtime.config.paths.base_path))
        mini=mini_id or ('ai2apps.imagine.image-edit' if edit else 'ai2apps.imagine.text-to-image')
        from .mini_parameters import WORKFLOWS, compose, reference_ids
        workflow=mini in WORKFLOWS
        prompt=compose(mini,arguments) if workflow else arguments['prompt']
        body={'model':model,'prompt':prompt,'size':arguments.get('size','1024x1024'),
              'quality':arguments.get('quality','auto'),'outputFormat':arguments.get('format','png')}
        refs=reference_ids(mini,arguments) if workflow else [arguments['artifact_id']] if edit else []
        if refs:
            body['imageDataUrls']=[]
            for reference_id in refs:
                reference=workspace.get_artifact(context.session_id,reference_id)
                if reference.media_type not in ('image/png','image/jpeg','image/webp'):
                    raise ToolProviderError('Reference must be a PNG, JPEG or WebP image')
                if reference.size_bytes>20*1024*1024:raise ToolProviderError('Reference exceeds 20 MiB')
                body['imageDataUrls'].append('data:'+reference.media_type+';base64,'+base64.b64encode(workspace.artifact_path(reference).read_bytes()).decode())
        local=runtime.model_invocations.model(model)
        body['source']='local' if local is not None else 'cloud'
        if local is not None:
            operation='image_edit' if refs else 'image_generation'
            if not local.checkpoint_ready or operation not in local.capabilities:
                raise ProviderUnavailable('Selected local model does not provide a ready '+operation)
        from ai2apps.api.studio_background import validate_image_references
        validate_image_references(body)
        # Use the same user-scoped App instance and Studio repository as the UI.
        instance,_,_=runtime.extension_manager.launch_app(STUDIO,principal=principal)
        scope={'actor_id':principal.actor_user_id,'installation_id':principal.installation_id,
               'app_instance_id':instance.id,'studio_id':STUDIO}
        key='agent-image-'+context.invocation_id
        repo=StudioRepository(runtime.database)
        with runtime.database.transaction() as db:
            old=db.execute('SELECT id,run_id FROM studio_background_jobs WHERE actor_id=? AND installation_id=? AND studio_id=? AND idempotency_key=?',
                           (principal.actor_user_id,principal.installation_id,STUDIO,key)).fetchone()
        if old:
            job=runtime.studio_jobs.get(old['id'],principal)
            run=repo.get_run(old['run_id'],**scope)
        else:
            run=repo.create_run(**scope,mini_app_id=mini,mini_app_version='1.0.0',placement='main',
                                title=prompt[:160],input_data={'agentRunId':context.trace_id,'capability':WORKFLOWS.get(mini,'image.edit' if edit else 'image.generate')})
            job=submit(runtime,principal,instance.id,STUDIO,mini,'cloud-image',{'body':body},run_id=run['id'],key=key)
        # Unknown/cancelled/failed jobs never trigger another provider: the job may
        # already have generated or billed. Its ID remains available for recovery.
        while job['status'] not in ('succeeded','failed','cancelled','interrupted','publish_failed'):
            await context.report_progress('Imagine Studio '+job['status'],progress=0.3)
            await asyncio.sleep(1)
            job=runtime.studio_jobs.get(job['id'],principal)
        if job['status']!='succeeded':
            raise ToolProviderError('Imagine Studio job '+job['id']+' '+job['status']+': '+str(job.get('error'))[:700])
        run=repo.get_run(run['id'],**scope)
        output=run['artifacts'][0]['metadata']
        source=workspace.get_artifact(output['workspaceSessionId'],output['workspaceArtifactId'])
        existing=next((a for a in workspace.list_artifacts(context.session_id) if a.metadata.get('studioJobId')==job['id']),None)
        artifact=existing or workspace.import_artifact(context.session_id,workspace.artifact_path(source),name=source.name,media_type=source.media_type,
            metadata={'studioJobId':job['id'],'studioRunId':run['id'],'miniAppId':mini,'model':model})
        return {'model':model,'studio_run_id':run['id'],'studio_job_id':job['id'],'mini_app_id':mini,
                'artifact':{'id':artifact.id,'uri':artifact.uri,'name':artifact.name,'media_type':artifact.media_type,
                            'size_bytes':artifact.size_bytes,'download_url':f'/v1/platform/sessions/{context.session_id}/artifacts/{artifact.id}/download'}}
    return execute
