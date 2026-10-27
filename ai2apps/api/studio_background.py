"""Authorized Local generation submission, observation and explicit cancellation."""
import sqlite3
import json
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from ai2apps.api.ownership import authorize_app_instance
from ai2apps.api.readaloud import QuickReadRequest
from ai2apps.studio.repository import StudioRepository

class Submission(BaseModel):
    kind: Literal['quick-read', 'local-image', 'local-image-edit', 'sticker-batch']
    payload: dict
    run_id: str | None = Field(default=None, max_length=100)


class LocalImageInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model: str = Field(min_length=1, max_length=255)
    prompt: str = Field(min_length=1, max_length=32000)
    size: str = Field(default='1024x1024', max_length=40)
    quality: str = Field(default='standard', max_length=40)
    outputFormat: Literal['png', 'jpeg', 'jpg', 'webp'] = 'png'
    n: Literal[1] = 1
    num_inference_steps: int | None = Field(default=None, ge=1, le=50)
    guidance: float | None = Field(default=None, ge=0, le=20)
    negative_prompt: str | None = Field(default=None, max_length=8192)


class LocalImageEditInput(LocalImageInput):
    imageDataUrls: list[str] = Field(min_length=1, max_length=4)
    strength: float | None = Field(default=None, ge=0, le=1)
    use_kv_cache: Literal[False] | None = None


class StickerBatchInput(LocalImageEditInput):
    source: Literal['local', 'cloud', 'byok']
    prompts: list[str] = Field(min_length=4, max_length=4)


def validate_image_references(payload):
    from ai2apps.cloud_gateway import _decode_image_data_url
    from ai2apps.api.imagine_studio import _matches_image_media_type
    total = 0
    for value in payload.get('imageDataUrls', []):
        if len(value) > 12 * 1024 * 1024:
            raise HTTPException(413, 'Reference image is too large')
        data, media_type, _ = _decode_image_data_url(value, 'Reference image')
        total += len(data)
        if not data or not _matches_image_media_type(data, media_type):
            raise HTTPException(422, 'Invalid reference image content')
    if total > 24 * 1024 * 1024:
        raise HTTPException(413, 'Reference images exceed 24 MiB')


def create_studio_background_router(runtime_provider, principal_provider):
    router = APIRouter(prefix='/studio-jobs', tags=['studio-jobs'])
    dependency = Depends(principal_provider)

    def manager():
        value = getattr(runtime_provider(), 'studio_jobs', None)
        if value is None:
            raise HTTPException(503, 'Studio task service is not ready')
        return value

    def require_surface(principal, studio_id):
        if studio_id not in {'ai2apps.readaloud', 'ai2apps.imagine-studio', 'ai2apps.video-studio'}:
            raise HTTPException(404, 'Studio not found')
        if principal.authentication_type == 'owner_home_lease':
            from ai2apps.remote.mobile_apps import app_enabled
            if not app_enabled(runtime_provider(), principal, studio_id):
                raise HTTPException(403, 'This Studio is disabled for Mobile')

    def owned_job(identifier, principal):
        job = manager().get(identifier, principal)
        require_surface(principal, job['studio_id'])
        return job

    @router.post('', status_code=202)
    async def submit(body: Submission, principal=dependency,
                     app_instance_id: str = Header(alias='X-AI2Apps-App-Instance'),
                     key: str = Header(alias='Idempotency-Key', min_length=8, max_length=160)):
        runtime = runtime_provider()
        authorize_app_instance(runtime, principal, app_instance_id)
        studio_id = 'ai2apps.readaloud' if body.kind == 'quick-read' else 'ai2apps.imagine-studio'
        require_surface(principal, studio_id)
        entry = runtime.extension_manager.instance_entry(app_instance_id, principal=principal)
        if entry.get('app_key') != studio_id:
            raise HTTPException(404, 'Studio not found')
        if body.kind == 'quick-read':
            try:
                payload = QuickReadRequest(**body.payload).model_dump()
            except ValidationError as error:
                raise HTTPException(422, 'Invalid Quick Read input') from error
            if body.run_id:
                raise HTTPException(422, 'Quick Read does not accept an external Run')
            mini_app_id = 'ai2apps.audio.quick-read'
        else:
            try:
                schema = {'local-image': LocalImageInput, 'local-image-edit': LocalImageEditInput, 'sticker-batch': StickerBatchInput}[body.kind]
                payload = schema(**body.payload).model_dump(exclude_none=True)
            except ValidationError as error:
                raise HTTPException(422, 'Invalid local image input') from error
            if not body.run_id or not isinstance(payload.get('prompt'), str) or not 0 < len(payload['prompt']) <= 32000:
                raise HTTPException(422, 'A Run and prompt are required')
            validate_image_references(payload)
            if body.kind == 'sticker-batch' and (len(payload['imageDataUrls']) != 1 or any(not 0 < len(x.strip()) <= 32000 for x in payload['prompts'])):
                raise HTTPException(422, 'A sticker batch requires one reference and four bounded prompts')
            try:
                run = StudioRepository(runtime.database).get_run(body.run_id, actor_id=principal.actor_user_id,
                    installation_id=principal.installation_id, app_instance_id=app_instance_id, studio_id=studio_id)
            except Exception as error:
                raise HTTPException(404, 'Run not found') from error
            mini_app_id = run['miniAppId']
            if run['status'] != 'queued' and manager().for_run(body.run_id, principal) is None:
                raise HTTPException(409, 'Run is not queued')
            if body.kind == 'sticker-batch' and mini_app_id != 'ai2apps.imagine.sticker-workshop':
                raise HTTPException(422, 'Sticker batch requires Sticker Workshop')

        model_id = payload.get('model_id') if body.kind == 'quick-read' else payload.get('model')
        if body.kind == 'quick-read' and payload.get('voice_profile_id'):
            from ai2apps.readaloud import ReadAloudRepository
            try:
                profile = ReadAloudRepository(runtime.database, runtime.events).get_voice_profile(principal.actor_user_id, payload['voice_profile_id'])
                model_id = profile['model_id']
            except Exception as error:
                raise HTTPException(404, 'Voice profile not found') from error
        model = runtime.model_invocations.model(model_id)
        expected = 'audio_tts' if body.kind == 'quick-read' else 'image_generation'
        cloud_batch = body.kind == 'sticker-batch' and payload['source'] != 'local'
        if not cloud_batch and (not model or model.model_type != expected or not model.checkpoint_ready):
            raise HTTPException(409, 'Selected model is not ready')
        if not cloud_batch and body.kind in ('local-image-edit', 'sticker-batch'):
            capabilities = getattr(model, 'image_capabilities', None) or {}
            if 'image_edit' not in capabilities.get('operations', getattr(model, 'capabilities', ())):
                raise HTTPException(422, 'Model does not support image editing')
            limits = capabilities.get('inputs', {}).get('reference_images', {})
            if not limits.get('minimum', 1) <= len(payload['imageDataUrls']) <= limits.get('maximum', 1):
                raise HTTPException(422, 'Reference count exceeds model capability')
        if len(json.dumps(payload)) > (36 * 1024 * 1024 if body.kind in ('local-image-edit','sticker-batch') else 256000):
            raise HTTPException(413, 'Generation request is too large')
        try:
            return manager().submit(principal=principal, app_instance_id=app_instance_id, studio_id=studio_id,
                mini_app_id=mini_app_id, kind=body.kind, key=key, payload=payload, run_id=body.run_id)
        except (ValueError, sqlite3.IntegrityError) as error:
            raise HTTPException(409, str(error)) from error

    @router.get('')
    def jobs(studio_id: str, principal=dependency):
        require_surface(principal, studio_id)
        return {'items': manager().list(principal, studio_id)}

    @router.get('/by-run/{run_id}')
    def by_run(run_id: str, principal=dependency):
        job = manager().for_run(run_id, principal)
        if job is None:
            raise HTTPException(404, 'Task not found')
        require_surface(principal, job['studio_id'])
        return job

    @router.get('/{identifier}')
    def get(identifier: str, principal=dependency):
        try:
            return owned_job(identifier, principal)
        except KeyError as error:
            raise HTTPException(404, 'Task not found') from error

    @router.post('/{identifier}/retry', status_code=202)
    async def retry(identifier: str, principal=dependency):
        try:
            owned_job(identifier, principal)
            return manager().retry(identifier, principal)
        except KeyError as error:
            raise HTTPException(404, 'Task not found') from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @router.post('/{identifier}/cancel')
    async def cancel(identifier: str, after_current: bool = False, principal=dependency):
        try:
            owned_job(identifier, principal)
            return manager().stop_after_current(identifier, principal) if after_current else manager().cancel(identifier, principal)
        except KeyError as error:
            raise HTTPException(404, 'Task not found') from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
    return router
