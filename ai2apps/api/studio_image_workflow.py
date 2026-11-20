"""Mount-authorized primitives for Package-compiled image sequence plans."""
import asyncio
import hashlib
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from ai2apps.studio import portable_archive

from ai2apps.api.ownership import authorize_app_instance
from ai2apps.studio.capability_broker import StudioCapabilityBroker, StudioCapabilityError
from ai2apps.studio.image_workflow import CAPABILITY, Plan, asset_root, read_asset, save_asset, model_catalog as catalog
from ai2apps.studio.repository import StudioRepository
from ai2apps.studio.image_schedules import ScheduleSettings


class ArchiveExport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    document: dict
    assets: list[str] = Field(default_factory=list, max_length=2000)


def create_image_workflow_router(runtime_provider, principal_provider):
    router = APIRouter(prefix='/{studio_id}/mini-app-mounts/{mount_id}/image-workflow')
    dependency = Depends(principal_provider)

    def scope(studio_id, mount_id, principal):
        runtime = runtime_provider()
        try:
            mounted = StudioCapabilityBroker(runtime).mounted_mini_app(studio_id, mount_id, principal=principal)
            if CAPABILITY not in mounted.capabilities: raise HTTPException(403, 'image.workflow is not declared')
            instance = (mounted.mount.get('context') or {}).get('studioInstanceId')
            if not instance: raise HTTPException(409, 'Studio instance unavailable')
            authorize_app_instance(runtime, principal, instance)
            if runtime.extension_manager.instance_entry(instance, principal=principal).get('app_key') != studio_id:
                raise HTTPException(404, 'Studio instance unavailable')
            return runtime, mounted, dict(actor_id=principal.actor_user_id, installation_id=principal.installation_id,
                app_instance_id=instance, studio_id=studio_id)
        except StudioCapabilityError as error: raise HTTPException(error.status_code, str(error)) from error

    @router.get('/characters')
    def shared_characters(studio_id: str, mount_id: str, principal=dependency):
        runtime, _, _ = scope(studio_id, mount_id, principal)
        from ai2apps.gallery.characters import Characters
        from ai2apps.gallery.repository import GalleryRepository
        gallery = GalleryRepository(runtime.database, runtime.config.paths.artifacts_path / 'gallery', runtime.events)
        return {'items': Characters(gallery, principal.actor_user_id).definitions()}

    @router.post('/assets')
    async def import_image(studio_id: str, mount_id: str, file: UploadFile = File(), principal=dependency):
        runtime, mounted, _ = scope(studio_id, mount_id, principal)
        data = await file.read(20 * 1024 * 1024 + 1)
        try:
            identifier = save_asset(asset_root(runtime, principal, mounted.mount['app_key']), data)
        except (ValueError, OSError) as error: raise HTTPException(422, str(error)) from error
        return {'id': identifier}

    @router.get('/models')
    async def model_catalog(studio_id: str, mount_id: str, principal=dependency):
        runtime, _, _ = scope(studio_id, mount_id, principal)
        return await catalog(runtime, principal)

    @router.get('/assets/{identifier}')
    def get_image(studio_id: str, mount_id: str, identifier: str, principal=dependency):
        runtime, mounted, _ = scope(studio_id, mount_id, principal)
        try: data = read_asset(asset_root(runtime, principal, mounted.mount['app_key']), identifier)
        except (ValueError, FileNotFoundError) as error: raise HTTPException(404, 'Image unavailable') from error
        return Response(data, media_type='image/png', headers={'Cache-Control': 'private, no-store'})

    @router.post('/archives/export')
    def export_archive(studio_id: str, mount_id: str, body: ArchiveExport, principal=dependency):
        runtime, mounted, _ = scope(studio_id, mount_id, principal)
        try:
            root = asset_root(runtime, principal, mounted.mount['app_key'])
            data = portable_archive.encode(body.document, {key: read_asset(root, key) for key in body.assets})
            return Response(data, media_type='application/zip', headers={'Cache-Control':'private, no-store'})
        except (ValueError, FileNotFoundError, OSError) as error:
            raise HTTPException(422, str(error)) from error

    @router.post('/archives/{action}')
    async def import_archive(studio_id: str, mount_id: str, action: str, file: UploadFile = File(), principal=dependency):
        runtime, mounted, _ = scope(studio_id, mount_id, principal)
        if action not in ('inspect', 'import'): raise HTTPException(404, 'Archive action unavailable')
        try:
            document, images = portable_archive.decode(await file.read(portable_archive.MAX_BYTES + 1))
            result = {'document':document, 'asset_count':len(images), 'bytes':sum(map(len,images.values()))}
            if action == 'inspect':
                from ai2apps.studio.image_workflow import data_url
                result['previews'] = [data_url(data,thumbnail=True) for data in list(images.values())[:6]]
            if action == 'import':
                # Validate all normalized images before writing any private asset.
                from ai2apps.studio.image_workflow import image_bytes
                normalized = {key:image_bytes(data) for key,data in images.items()}
                root = asset_root(runtime, principal, mounted.mount['app_key'])
                result['mapping'] = {key:save_asset(root,data) for key,data in normalized.items()}
            return result
        except (ValueError, OSError) as error: raise HTTPException(422, str(error)) from error

    @router.post('/jobs')
    async def start(studio_id: str, mount_id: str, body: Plan, principal=dependency):
        runtime, mounted, scoped = scope(studio_id, mount_id, principal)
        from ai2apps.studio.image_workflow import submit_plan, SubmissionConflict
        binding = {'provider': mounted.mount['app_key'], 'mini_id': mounted.declaration['id'], 'version': mounted.declaration['version']}
        try:
            return await submit_plan(runtime, principal, binding, scoped, body)
        except SubmissionConflict as error: raise HTTPException(409, str(error)) from error
        except (ValueError, FileNotFoundError) as error: raise HTTPException(422, str(error)) from error

    def owned_job(studio_id, mount_id, identifier, principal):
        runtime, mounted, scoped = scope(studio_id, mount_id, principal)
        try: job = runtime.studio_jobs.get(identifier, principal)
        except KeyError as error: raise HTTPException(404, 'Job unavailable') from error
        if job['studio_id'] != studio_id or job['mini_app_id'] != mounted.declaration['id']:
            raise HTTPException(404, 'Job unavailable')
        with runtime.database.transaction() as db:
            row = db.execute('SELECT app_instance_id,kind FROM studio_background_jobs WHERE id=?', (identifier,)).fetchone()
        if row['app_instance_id'] != scoped['app_instance_id'] or row['kind'] != 'image-workflow': raise HTTPException(404, 'Job unavailable')
        return runtime, job

    @router.get('/jobs/{identifier}')
    def status(studio_id: str, mount_id: str, identifier: str, principal=dependency):
        return owned_job(studio_id, mount_id, identifier, principal)[1]

    @router.get('/submissions/{key}')
    def lookup(studio_id: str, mount_id: str, key: str, principal=dependency):
        import re
        if not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}', key): raise HTTPException(422, 'Invalid submission key')
        runtime, mounted, scoped = scope(studio_id, mount_id, principal)
        identity = 'image-workflow-' + mounted.declaration['id'] + '-' + key
        with runtime.database.transaction() as db:
            row = db.execute('SELECT * FROM studio_background_jobs WHERE actor_id=? AND installation_id=? AND studio_id=? AND app_instance_id=? AND mini_app_id=? AND idempotency_key=?',
                (principal.actor_user_id, principal.installation_id, studio_id, scoped['app_instance_id'], mounted.declaration['id'], identity)).fetchone()
        return runtime.studio_jobs.public(row) if row else None

    @router.delete('/jobs/{identifier}')
    def cancel(studio_id: str, mount_id: str, identifier: str, principal=dependency):
        runtime, _ = owned_job(studio_id, mount_id, identifier, principal)
        return runtime.studio_jobs.cancel(identifier, principal)

    @router.post('/jobs/{identifier}/retry-publication')
    def retry_publication(studio_id: str, mount_id: str, identifier: str, principal=dependency):
        runtime, job = owned_job(studio_id, mount_id, identifier, principal)
        if job['status'] != 'publish_failed' or not (runtime.studio_jobs.root / identifier / 'result.json').is_file():
            raise HTTPException(409, 'Only a checkpointed publication may be retried')
        return runtime.studio_jobs.retry(identifier, principal)

    def schedule_scope(studio_id,mount_id,principal):
        runtime,mounted,scoped=scope(studio_id,mount_id,principal)
        if 'image.workflow.schedule' not in mounted.capabilities or 'llm.text' not in mounted.capabilities:
            raise HTTPException(403,'image.workflow.schedule and llm.text are required')
        if principal.client_scope!='desktop':raise HTTPException(403,'Configure scheduled workflows from Desktop')
        service=getattr(runtime,'image_workflow_schedules',None)
        if service is None:raise HTTPException(503,'Scheduled workflows are unavailable')
        return service,service.binding(mounted,scoped,principal)

    @router.get('/schedules/{resource}')
    def scheduled_state(studio_id:str,mount_id:str,resource:str,principal=dependency):
        service,binding=schedule_scope(studio_id,mount_id,principal)
        try:return service.snapshot(binding,resource)
        except ValueError as error:raise HTTPException(422,str(error)) from error

    @router.put('/schedules/{resource}')
    async def save_schedule(studio_id:str,mount_id:str,resource:str,body:ScheduleSettings,principal=dependency):
        service,binding=schedule_scope(studio_id,mount_id,principal)
        try:return await service.configure(binding,resource,body)
        except (ValueError,FileNotFoundError) as error:raise HTTPException(422,str(error)) from error

    return router
