"""Exercise the Gallery API and registered sticker adapters with fixture inference."""

import base64
from io import BytesIO

import httpx
import pytest
from fastapi import FastAPI
from PIL import Image

from ai2apps.api.gallery import create_gallery_router
from ai2apps.chat import ChatRepository
from ai2apps.gallery.repository import STICKER_PACK_MIME
from ai2apps.identity import RequestPrincipal
from ai2apps.images.parameters import from_options
from ai2apps.services import ToolCallContext
from ai2apps.services.builtin_apps import gallery
from test_app_interactions import runtime


def image(color):
    data = BytesIO()
    Image.new('RGB', (16, 16), color).save(data, 'PNG')
    return data.getvalue()


@pytest.mark.asyncio
@pytest.mark.parametrize('background',['white','transparent'])
async def test_sticker_pack_http_and_aaat(runtime, monkeypatch, background):
    app = FastAPI()
    app.include_router(create_gallery_router(lambda: runtime, RequestPrincipal.legacy_local))
    repo = gallery(runtime)
    references = [
        repo.import_stream('local', BytesIO(image(color)), name=f'{color}.png', media_type='image/png')[0]['id']
        for color in ('red', 'green')
    ]
    private = repo.import_stream('other', BytesIO(image('blue')), name='private.png', media_type='image/png')[0]['id']
    calls = []

    output = BytesIO()
    Image.new('RGBA',(16,16),(255,255,255,0 if background=='transparent' else 255)).save(output,'PNG')
    result_bytes=output.getvalue()

    async def cloud(body, **kwargs):
        calls.append(body)
        return {'image': {'dataUrl': 'data:image/png;base64,' + base64.b64encode(result_bytes).decode()}}

    model = 'cloud/ai2apps/openai/gpt-image-2'

    async def catalog(*args):
        return [from_options(model, 'Fixture', {'background':['transparent']})], []

    monkeypatch.setattr('ai2apps.images.cloud_gateway.request_cloud_image', cloud)
    monkeypatch.setattr('ai2apps.images.parameters.models', catalog)
    monkeypatch.setattr(runtime, 'cloud_ai_authorization_headers', lambda principal: {})
    session = ChatRepository(runtime.database, runtime.events).create_thread(title='Sticker fixture')[0].session.id
    context = ToolCallContext(caller_id='fixture', session_id=session, actor_user_id='local',
                              installation_id='local', invocation_id='draw-sticker')
    lookup = {'character': '马斯克', 'state': 'dizzy', 'framing': 'full', 'facing': 'left', 'background':background}
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
            url = '/gallery/sticker-packs'
            denied = await client.post(url, json={'name': 'Other owner', 'reference_ids': [private]})
            assert denied.status_code == 404
            created = await client.post(url, json={
                'name': '马斯克', 'description': 'Black jacket', 'reference_ids': references,
            })
            assert created.status_code == 201, created.text
            pack = created.json()
            listing = await client.get('/gallery/assets', params={'kind': 'sticker-pack'})
            assert listing.json()['items'][0]['kind'] == 'sticker-pack'
            append_url = url + '/' + pack['id'] + '/stickers'
            assert (await client.post(append_url, json={'state': 'dizzy', 'asset_id': private})).status_code == 404
            appended = await client.post(append_url, json={'state': 'happy', 'asset_id': references[0]})
            assert appended.status_code == 201
            opaque = await client.post(append_url, json={'state':'happy','asset_id':references[0],'background':'transparent'})
            assert opaque.status_code >= 400
            assert 'opaque' in opaque.text

            invoke = runtime.app_capability_router.invoke
            assert (await invoke('sticker.lookup', lookup, context))['status'] == 'variant_not_found'
            payload = {key: value for key, value in lookup.items() if key != 'character'}
            drawn = await invoke('sticker.generate', {**payload, 'pack_id': pack['id'], 'model': model}, context)
            assert drawn['status'] == 'generated'
            assert len(calls) == 1
            assert calls[0].get('background') == ('transparent' if background=='transparent' else None)
            assert len(calls[0]['imageDataUrls']) == 2
            assert 'full body' in calls[0]['prompt'] and 'left edge' in calls[0]['prompt']
            found = await invoke('sticker.lookup', lookup, context)
            assert found['status'] == 'found' and found['sticker'] == drawn['sticker']
            flexible = await invoke('sticker.lookup', {'character': '马斯克', 'state': 'dizzy', 'background':background}, context)
            assert flexible['sticker'] == found['sticker']
            assert len(calls) == 1
            artifact = runtime.workspace.get_artifact(session, found['materials'][0]['artifact_id'])
            assert runtime.workspace.artifact_path(artifact).read_bytes() == result_bytes
            reused = await invoke('sticker.generate', {**payload, 'pack_id': pack['id']}, context)
            assert reused['status'] == 'found' and len(calls) == 1

            downloaded = await client.get(f'/gallery/assets/{pack["id"]}/content?download=true')
            assert downloaded.headers['content-type'] == STICKER_PACK_MIME
            assert len(downloaded.json()['stickers']) == 2
            assert len(downloaded.json()['character']['references']) == 2
            assert (await invoke('sticker.lookup', {**lookup, 'facing': 'right'}, context))['status'] == 'variant_not_found'
            repo.trash_asset('local', drawn['sticker']['asset_id'])
            assert (await invoke('sticker.lookup', lookup, context))['status'] == 'variant_not_found'
    finally:
        await runtime.stop_background_tasks()
