"""Durable image editing and sequential sticker generation, owned by Local."""
from __future__ import annotations

import asyncio
import base64
import json
import os

from ai2apps.model_invocation import ModelInvocationContext
from ai2apps.studio.repository import StudioRepository


def checkpoint(directory, content, metadata):
    directory.mkdir(exist_ok=True, parents=True, mode=0o700)
    for name, data in (('output', content), ('result.json', json.dumps(metadata).encode())):
        temporary = directory / (name + '.tmp')
        with temporary.open('wb') as stream:
            os.chmod(temporary, 0o600)
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, directory / name)
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def image_result(result, output_format="png"):
    from ai2apps.api.imagine_studio import _matches_image_media_type
    from ai2apps.images.history import MAX_IMAGE_BYTES
    image = result.get('image') or {}
    data_url = image.get('dataUrl', '')
    if data_url:
        header, encoded = data_url.split(',', 1)
        media_type = header.removeprefix('data:').removesuffix(';base64')
    else:
        encoded = result['data'][0]['b64_json']
        media_type = 'image/' + output_format.replace('jpg', 'jpeg')
    if media_type not in ('image/png','image/jpeg','image/webp') or len(encoded) > MAX_IMAGE_BYTES * 4 // 3 + 4:
        raise ValueError('Invalid image output format or size')
    data = base64.b64decode(encoded, validate=True)
    if not data or len(data) > MAX_IMAGE_BYTES or not _matches_image_media_type(data, media_type):
        raise ValueError('Invalid image output')
    return data, media_type


async def generate_image(runtime, principal, job, payload, request_id):
    source = payload.get('source', 'local')
    body = {key: value for key, value in payload.items() if key not in ('source','prompts')}
    if source != 'local':
        from ai2apps.cloud_gateway import request_cloud_image
        # Reuse the existing authorized Cloud/BYOK contract; no new Cloud API.
        body['idempotencyKey'] = request_id
        result = await request_cloud_image(body, edit=bool(body.get('imageDataUrls')), base_path=runtime.config.paths.base_path,
            model_manager=getattr(runtime, 'model_manager', None), cloud_client=runtime.cloud,
            cloud_headers=runtime.cloud_ai_authorization_headers(principal))
    else:
        invocations = runtime.model_invocations
        model = invocations.model(body['model'])
        if model is None or model.model_type != 'image_generation' or not model.checkpoint_ready:
            raise ValueError('Local image model is not ready')
        try:
            operation = 'image_edit' if body.get('imageDataUrls') else 'image_generation'
            response = await invocations.invoke_background_json(model.id, operation, body,
                request_id=request_id, context=ModelInvocationContext.from_principal(principal,
                    session_id=job['id'], app_instance_id=job['app_instance_id'], consumer_app_id=job['studio_id']))
            if response.status_code >= 400:
                raise ValueError('Local image editing failed')
            result = json.loads(bytes(response.body))
        except asyncio.CancelledError:
            await invocations.cancel_request(model.id, request_id)
            raise
    content, media_type = image_result(result, body.get('outputFormat', 'png'))
    return content, {'media_type': media_type, 'model': body['model'], 'prompt': body['prompt'], 'size': (result.get('image') or {}).get('size') or body.get('size'), 'format': media_type.split('/')[1]}


async def render_image_job(manager, job, principal, payload):
    repository = StudioRepository(manager.database)
    scope = manager.scope(job)
    repository.update_run(job['run_id'], status='running', progress=5, detail='Generating image', **scope)
    if job['kind'] == 'local-image-edit':
        return await generate_image(manager.runtime, principal, job, payload, job['id'])
    root = manager.root / job['id']
    for index, prompt in enumerate(payload['prompts']):
        if (root / 'stop').exists():
            raise asyncio.CancelledError()
        directory = root / f'item-{index}'
        key = job['id'] + f'-{index}'
        if not (directory / 'result.json').exists():
            content, metadata = await generate_image(manager.runtime, principal, job, {**payload, 'prompt': prompt}, key)
            checkpoint(directory, content, metadata)
        # Checkpoint before publishing. A retry reuses this exact output, including
        # the item whose inference succeeded but publication failed.
        manager.publish(job, directory, output_key=key, complete=False)
        repository.update_run(job['run_id'], status='running', progress=(index + 1) * 24,
            detail=f'{index + 1}/{len(payload["prompts"])}', **scope)
        manager._update(job['id'], 'running', result={'completed': index + 1, 'total': len(payload['prompts'])})
    return b'', {'batch': True, 'completed': len(payload['prompts'])}
