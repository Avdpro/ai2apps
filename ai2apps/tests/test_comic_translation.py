import io
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from PIL import Image, ImageDraw

from ai2apps.api.imagine_studio import create_imagine_studio_router
from ai2apps.identity import RequestPrincipal
from ai2apps.images.comic_translation import (
    MINI_ID, OCR_ID, STUDIO_ID, _can_tighten_region, _enclosed_text_bounds, _overlapping_column_parts,
    _shares_bubble_interior, detect, page_bounds,
)
from test_app_interactions import runtime


def comic_test_loader(tmp_path):
    # This Package is deliberately outside automatic Development discovery.
    # Mount the actual owner only in this isolated test checkout.
    import shutil
    from ai2apps.extensions.development import DevelopmentPackageLoader
    checkout=tmp_path/'fixture-checkout'
    (checkout/'ai2apps').mkdir(parents=True)
    (checkout/'ai2apps/__init__.py').write_text('')
    source=Path(__file__).resolve().parents[2]/'packages/paused-development/ai2apps-comic-translation'
    shutil.copytree(source,checkout/'packages/ai2apps-comic-translation')
    return DevelopmentPackageLoader(checkout)


@pytest.mark.asyncio
@pytest.mark.parametrize('finish_reason, retries', [('length', True), ('content_filter', False)])
@pytest.mark.parametrize('model, can_disable, expected_effort', [
    ('fixture/translator', True, None),
    ('cloud/fixture/translator', True, 'none'),
    ('cloud/fixture/translator', False, None),
    ('cloud/ai2apps/fixture/translator', True, None),
])
async def test_translation_retries_only_output_limit(finish_reason, retries, model, can_disable, expected_effort):
    from ai2apps.images import comic_translation as comic

    calls = []
    context = object()

    async def chat(payload, **kwargs):
        assert kwargs['context'] is context
        assert payload.get('reasoning_effort') == expected_effort
        calls.append(payload)
        if len(calls) == 1:
            return {'choices': [{'finish_reason': finish_reason, 'message': {'content': 'partial'}}]}
        return {'choices': [{'finish_reason': 'stop', 'message': {
            'content': '{"translations":["Hello"],"new_terms":[]}',
        }}]}

    manager = SimpleNamespace(enabled_cloud_models=lambda: [{
        'gateway_id': model, 'capabilities': {'reasoningControl': {'can_disable': can_disable}},
    }])
    service = SimpleNamespace(model_invocations=SimpleNamespace(invoke_chat_json=chat), model_manager=manager)
    translate = comic.translate(service, context, ['你好'], 'en', model=model, glossary=[])
    if not retries:
        with pytest.raises(ValueError, match='without a complete translation'):
            await translate
        assert len(calls) == 1
        return
    assert await translate == {'translations': ['Hello'], 'new_terms': []}
    assert calls[0]['max_tokens'] < calls[1]['max_tokens']
    assert calls[0]['messages'] == calls[1]['messages']
    assert [call['model'] for call in calls] == [model] * 2


def test_comic_ocr_setup_plans_the_required_model(runtime, monkeypatch):
    from ai2apps.provisioning import orchestrator
    from ai2apps.images.comic_translation import CAPABILITY

    monkeypatch.setattr(orchestrator, 'device_profile', lambda: {
        'os': 'macos', 'architecture': 'arm64', 'system_memory_gib': 16,
        'accelerator': {'vendor': 'apple', 'api': 'metal', 'unified_memory_gib': 16},
    })
    result = runtime.provisioning.ensure(
        actor_id='local', installation_id='local', app_instance_id='imagine-fixture',
        app_id=STUDIO_ID, capability=CAPABILITY, action_id='setup-mini-app',
        requirements={}, intent={'completionPolicy': 'configure_only'},
    )
    assert result['status'] == 'setup_required'
    session = result['session']
    assert session['status'] == 'awaiting_confirmation'
    stack = session['plan']['stack']
    assert stack['runtime']['version'] == '>=1.8.15,<2.0.0'
    assert stack['provider']['package_id'] == 'ai2apps/model-oxr'
    assert stack['checkpoint']['model_id'] == OCR_ID


def test_desktop_crop_respects_the_full_page():
    image = Image.new('RGB', (1400, 1100), '#424258')
    draw = ImageDraw.Draw(image)
    draw.rectangle((390, 105, 1020, 1035), fill='#eee')
    for top, bottom in ((120, 380), (400, 670), (690, 1020)):
        draw.rectangle((403, top, 1007, bottom), outline='black', width=5)
    box = page_bounds(image)
    assert box
    assert tuple(round(value * extent) for value, extent in zip(box, (1400, 1100, 1400, 1100))) == pytest.approx(
        (390, 105, 1020, 1035), abs=8)
    assert page_bounds(Image.new('RGB', (900, 1100), 'white')) is None


def test_desktop_crop_keeps_both_pages_when_panel_rules_stop_at_the_gutter():
    image = Image.new('RGB', (1200, 800), '#212121')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 25, 1199, 94), fill='#f6f3f6')
    draw.rectangle((118, 95, 1081, 799), fill='white')
    for left, right in ((118, 565), (638, 1040)):
        for top, bottom in ((142, 355), (371, 521), (543, 765)):
            draw.rectangle((left, top, right, bottom), outline='black', width=5)
    draw.rectangle((15, 730, 105, 774), fill='black')
    draw.rectangle((1070, 713, 1185, 772), fill='black')
    box = page_bounds(image)
    assert box
    assert tuple(round(value * extent) for value, extent in zip(box, image.size * 2)) == pytest.approx(
        (118, 95, 1082, 800), abs=4)


def test_recovers_faint_outline_without_treating_textured_art_as_dialogue():
    page = Image.new('RGB', (640, 420), 'white')
    draw = ImageDraw.Draw(page)
    draw.ellipse((44, 34, 174, 248), outline='#dedede', width=3)
    for y in (80, 105, 130):
        draw.rectangle((102, y, 113, y + 13), fill='black')
    draw.rectangle((260, 90, 470, 300), outline='black', width=5)
    for y in range(95, 296):
        draw.line((265, y, 465, y), fill='#d1d1d1' if y % 2 else '#fcfcfc')
    for x in range(268, 460, 6):
        for y in range(98, 290, 7):
            draw.rectangle((x, y, x + 2, y + 2), fill='#777777')
    boxes = detect(page)
    assert len(boxes) == 1
    assert tuple(round(value * size) for value, size in zip(boxes[0], page.size * 2)) == pytest.approx(
        (100, 78, 116, 146), abs=3)


def test_recovers_dialogue_columns_in_an_open_contiguous_bubble():
    page = Image.new('RGB', (640, 420), 'white')
    draw = ImageDraw.Draw(page)
    draw.line([(120, 150), (120, 75), (145, 52), (185, 52),
               (204, 66), (220, 60), (251, 75), (251, 180)], fill='black', width=3)
    for x, top in ((165, 100), (181, 80), (197, 80)):
        for y in range(top, top + 48, 10):
            draw.rectangle((x, y, x + 6, y + 6), fill='black')
    draw.line([(300, 84), (360, 84), (360, 198), (460, 198)], fill='black', width=5)
    pixels = [tuple(round(value * size) for value, size in zip(box, page.size * 2))
              for box in detect(page)]
    assert pixels == [pytest.approx((163, 78, 205, 149), abs=4)]


def test_staggered_text_boxes_join_across_white_space_but_not_a_border():
    image = Image.new('L', (100, 100), 'white')
    draw = ImageDraw.Draw(image)
    left, right = (20, 15, 43, 85), (44, 15, 70, 61)
    draw.rectangle((44, 62, 70, 85), fill='black')
    draw.rectangle((26, 22, 32, 76), fill='black')
    draw.rectangle((50, 22, 56, 53), fill='black')
    assert _shares_bubble_interior(image, left, right)
    draw.line((43, 15, 43, 61), fill='black')
    assert not _shares_bubble_interior(image, left, right)


def test_refines_a_small_balloon_next_to_line_art_without_including_the_outline():
    image = Image.new('L', (160, 120), 'white')
    draw = ImageDraw.Draw(image)
    outer, text = (15, 15, 121, 106), (97, 17, 120, 87)
    draw.line([(19, 22), (32, 93), (64, 62), (43, 25)], fill='black', width=2)
    draw.rectangle((99, 20, 117, 83), outline='black')
    for y in (31, 44, 57):
        draw.rectangle((105, y, 111, y + 6), fill='black')
    assert _can_tighten_region(image, outer, text)
    refined = _enclosed_text_bounds(image, image.size, outer, text)
    assert tuple(round(value * size) for value, size in zip(refined, image.size * 2)) == (104, 28, 113, 67)

    # The same narrow candidate is not enough evidence when there is other substantial ink.
    for x in (34, 47, 60, 73, 86):
        for y in (30, 47, 64):
            draw.rectangle((x, y, x + 7, y + 8), fill='black')
    assert not _can_tighten_region(image, outer, text)


def test_overlapping_vertical_ocr_windows_assign_the_shared_glyphs_once():
    image = Image.new('L', (100, 120), 'white')
    upper, lower = (58, 20, 72, 52), (30, 42, 73, 99)
    assert _overlapping_column_parts(image, upper, lower) == [
        [upper], [(30, 42, 58, 99), (58, 52, 73, 99)],
    ]
    ImageDraw.Draw(image).line((53, 46, 74, 46), fill='black', width=2)
    assert _overlapping_column_parts(image, upper, lower) is None


@pytest.mark.asyncio
async def test_comic_aaat_uses_owned_pages_and_returns_the_same_shared_outputs_on_replay(runtime, monkeypatch, tmp_path):
    from dataclasses import replace

    from ai2apps.chat.repository import ChatRepository
    from ai2apps.extensions.development import DevelopmentPackageLoader
    from ai2apps.images import comic_aaat, comic_translation
    from ai2apps.services import ToolCallContext
    from ai2apps.studio.comic_output import stage_page
    from ai2apps.studio.repository import StudioRepository

    manager = runtime.extension_manager
    monkeypatch.setattr(manager, '_development_loader', comic_test_loader(tmp_path))
    manager.refresh_development_packages()
    runtime.package_mini_exports.sync()
    principal = RequestPrincipal.legacy_local()
    provider = next(item for item in runtime.app_capability_router.providers.values()
                    if item.capability == 'imagine.translate_comic')
    thread, _ = ChatRepository(runtime.database, runtime.events).create_thread(title='Comic pages')
    context = replace(ToolCallContext.from_principal(principal, caller_id='test', session_id=thread.session.id),
                      invocation_id='comic-invocation-1')
    picture = tmp_path / 'page.png'
    Image.new('RGB', (32, 48), 'white').save(picture)
    asset = runtime.workspace.import_artifact(thread.session.id, picture, name='page.png', media_type='image/png')
    calls = []

    async def catalog(_):
        return {'default': None, 'items': [{'id': 'local/fixture', 'local': True}]}

    async def render(_runtime, _principal, model_context, model, _context, args, materials, glossary, script, directory):
        assert model_context.session_id == context.session_id
        assert model == 'local/fixture' and args['language'] == 'en'
        assert materials[0][0].read_bytes() == picture.read_bytes()
        assert not glossary and 'window.ComicLayout' in script
        calls.append(model)
        return [stage_page(directory, 1, picture.read_bytes(), 'png')], []

    monkeypatch.setattr(comic_translation, 'models', catalog)
    monkeypatch.setattr(comic_translation, 'ocr_ready', lambda _: False)
    missing = await provider.describe(principal)
    assert missing['inline_setup'] and missing['configuration_required']
    assert missing['install']['capability'] == comic_translation.CAPABILITY
    monkeypatch.setattr(comic_translation, 'ocr_ready', lambda _: True)
    monkeypatch.setattr(comic_aaat, 'render_batch', render)
    ready = await provider.describe(principal)
    assert not ready['selection_required'] and not ready['inline_setup']
    assert (await provider.prepare({'image_ids': [asset.id]}, context))['format'] == 'png'
    result = await provider.handler({'image_ids': [asset.id]}, context)
    assert result['shared_output'] and len(result['files']) == 1
    output = runtime.workspace.get_artifact(thread.session.id, result['files'][0]['artifact_id'])
    assert runtime.workspace.artifact_path(output).read_bytes() == picture.read_bytes()
    host, _, _ = manager.launch_app(STUDIO_ID, principal=principal)
    run = StudioRepository(runtime.database).get_run(result['studio_run_id'], actor_id=principal.actor_user_id,
        installation_id=principal.installation_id, studio_id=STUDIO_ID, app_instance_id=host.id)
    assert run['status'] == 'succeeded' and len(run['artifacts']) == 1
    assert await provider.handler({'image_ids': [asset.id]}, context) == result
    assert calls == ['local/fixture']


@pytest.mark.asyncio
async def test_package_mount_model_selection_context_and_offline_output(runtime, monkeypatch, tmp_path):
    from ai2apps.api.studio_mini_apps import create_studio_mini_app_router
    from ai2apps.extensions.development import DevelopmentPackageLoader
    from ai2apps.studio.repository import StudioRepository

    root = Path(__file__).resolve().parents[2]
    manager = runtime.extension_manager
    monkeypatch.setattr(manager, '_development_loader', comic_test_loader(tmp_path))
    manager.refresh_development_packages()
    principal = RequestPrincipal.legacy_local()
    instance, _, _ = manager.launch_app(STUDIO_ID, principal=principal)
    mount = manager.mount_studio_mini_app(STUDIO_ID, MINI_ID,
        context={'studioInstanceId': instance.id}, principal=principal)
    calls = []

    async def catalog():
        return [{'id': 'test-local', 'name': 'Local model', 'model_type': 'llm', 'source_type': 'local'},
                {'id': 'cloud/test/remote', 'name': 'Remote model', 'model_type': 'llm', 'source_type': 'cloud'}]

    async def model(payload, *, context):
        calls.append(payload)
        request = json.loads(payload['messages'][1]['content'])
        content = ['Hello!']
        if isinstance(request, dict) and 'glossary' in request:
            corrected = 'exact preferred spellings' in payload['messages'][0]['content']
            content = {
                'translations': ['Lin arrives in Pecking.' if corrected else 'Lin arrives in Beijing.'],
                'new_terms': [
                    {'source': '北京', 'translation': 'Beijing', 'kind': 'place'},
                    {'source': '小林', 'translation': 'Lin', 'kind': 'person'},
                    {'source': '月球', 'translation': 'Moon', 'kind': 'place'},
                ],
            }
            if 'bubble_candidates' in request:
                content = {'translations': ['stay home.', 'If it rains,', 'Goodbye.'], 'new_terms': [],
                           'bubble_groups': [[2, 1], [1, 2], [2, 3]]}
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(content)}}]}

    monkeypatch.setattr(runtime.model_invocations, 'chat_catalog', catalog)
    monkeypatch.setattr(runtime.model_invocations, 'invoke_chat_json', model)
    monkeypatch.setattr(runtime.model_invocations, 'model', lambda identifier: None)
    monkeypatch.setattr(runtime, 'privacy_mode', True, raising=False)
    app = FastAPI()
    app.include_router(create_studio_mini_app_router(lambda: runtime, lambda: principal))
    base = f'/studios/{STUDIO_ID}/mini-app-mounts/{mount["id"]}/comic-translation'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
        result = await client.get(base + '/models')
        assert result.status_code == 200, result.text
        assert [item['id'] for item in result.json()['items']] == ['test-local']
        assert result.json()['ocrReady'] is False
        probe = await client.get(base.removesuffix('/comic-translation') + '/capabilities')
        assert probe.status_code == 200, probe.text
        assert not next(item for item in probe.json()['items'] if item['capability'] == 'comic.translation')['ready']
        monkeypatch.setattr(runtime.model_invocations, 'model',
                            lambda identifier: SimpleNamespace(checkpoint_ready=identifier == OCR_ID))
        assert (await client.get(base + '/models')).json()['ocrReady'] is True
        body = {'model': 'test-local', 'language': 'en', 'texts': ['你好'], 'before': ['前一页'], 'after': ['下一页']}
        denied = await client.post(base + '/translate', json={**body, 'model': 'cloud/test/remote'})
        assert denied.status_code == 409
        assert not calls
        accepted = await client.post(base + '/translate', json=body)
        assert accepted.json() == {'translations': ['Hello!']}
        assert json.loads(calls[0]['messages'][1]['content']) == {
            'previous_page': ['前一页'], 'current_page': ['你好'], 'next_page': ['下一页']}
        partial = {**body, 'texts': ['如果今天下雨，', '就留在家里。'], 'targets': [1], 'nearby_pairs': [0]}
        accepted = await client.post(base + '/translate', json=partial)
        assert accepted.json() == {'translations': ['Hello!']}
        assert json.loads(calls[-1]['messages'][1]['content']) == {
            'previous_page': ['前一页'], 'current_page': partial['texts'], 'next_page': ['下一页'],
            'translate_boxes': [2], 'nearby_boxes': [[1, 2]],
        }
        invalid = await client.post(base + '/translate', json={**partial, 'nearby_pairs': [1]})
        assert invalid.status_code == 422
        assert len(calls) == 2
        glossary = [
            {'source': '北京', 'translation': 'Pecking', 'kind': 'place'},
            {'source': '上海', 'translation': 'Shanghai', 'kind': 'place'},
        ]
        result = await client.post(base + '/translate', json={
            **body, 'texts': ['小林来到北京。'], 'targets': [0], 'glossary': glossary,
        })
        assert result.json() == {'translations': ['Lin arrives in Pecking.'],
                                 'new_terms': [{'source': '小林', 'translation': 'Lin', 'kind': 'person'}]}
        assert len(calls) == 4
        assert json.loads(calls[-1]['messages'][1]['content'])['glossary'] == glossary[:1]
        grouped = await client.post(base + '/translate', json={
            **body, 'texts': ['就留在家里。', '如果今天下雨，', '再見。'], 'targets': [0, 1, 2],
            'glossary': [], 'bubble_candidates': [[0, 1, True]],
            'bubble_boxes': [[.2, .3, .3, .5], [.3, .2, .4, .4], [.6, .2, .7, .4]],
            'vertical': True,
        })
        assert grouped.json() == {'translations': ['stay home.', 'If it rains,', 'Goodbye.'], 'new_terms': [],
                                  'bubble_groups': [[1, 0]]}
        assert json.loads(calls[-1]['messages'][1]['content'])['source_direction'] == 'vertical right-to-left'
        exported = await client.post(base + '/export/html', files=[
            ('files', ('reader.html', b'<!doctype html><meta name="generator" content="ai2apps-comic-reader/v1">', 'text/html'))])
        assert exported.status_code == 200, exported.text
        run = StudioRepository(runtime.database).get_run(exported.json()['runId'],
            actor_id=principal.actor_user_id, installation_id=principal.installation_id,
            app_instance_id=instance.id, studio_id=STUDIO_ID)
        reader = run['artifacts'][0]
        assert run['status'] == 'succeeded' and reader['name'] == 'comic-reader.html'
        assert reader['kind'] == 'file' and reader['mediaType'] == 'application/octet-stream'

        png = io.BytesIO()
        Image.new('RGB', (32, 32), 'white').save(png, 'PNG')
        files = [('files', ('page.png', png.getvalue(), 'image/png'))] * 50
        exported = await client.post(base + '/export/png', files=files)
        assert exported.status_code == 200, exported.text
        run = StudioRepository(runtime.database).get_run(exported.json()['runId'],
            actor_id=principal.actor_user_id, installation_id=principal.installation_id,
            app_instance_id=instance.id, studio_id=STUDIO_ID)
        assert run['status'] == 'succeeded'
        assert sorted(artifact['name'] for artifact in run['artifacts']) == [
            f'comic-{index:02d}.png' for index in range(1, 51)]
        denied = await client.post(base + '/export/png', files=[*files, files[0]])
        assert denied.status_code == 422


@pytest.mark.asyncio
async def test_comic_translation_regions_and_model_boundaries(runtime, monkeypatch):
    page = Image.new('RGB', (640, 380), '#536487')
    draw = ImageDraw.Draw(page)
    for x, y in [(30, 30), (350, 190)]:
        draw.ellipse((x, y, x + 250, y + 130), fill='white', outline='black', width=3)
        for column in range(8):
            draw.rectangle((x + 70 + column * 12, y + 62, x + 74 + column * 12, y + 72), fill='black')
    data = io.BytesIO()
    page.save(data, 'PNG')
    calls = []

    async def response(payload, *, context):
        calls.append(payload)
        text = 'Good morning!' if payload['model'] == OCR_ID else '["早上好！"]'
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': text}}]}

    runtime.model_invocations.invoke_chat_json = response
    monkeypatch.setattr(runtime.model_invocations, 'model', lambda identifier: SimpleNamespace(checkpoint_ready=True))
    monkeypatch.setattr('ai2apps.images.comic_translation.resolve_task_model',
                        lambda runtime, tier, profile: 'local/translator' if profile == 'privacy' else None)
    principal = RequestPrincipal.legacy_local()
    instance, _, _ = runtime.extension_manager.launch_app('ai2apps.imagine-studio', principal=principal)
    app = FastAPI()
    app.include_router(create_imagine_studio_router(lambda: runtime, lambda: principal))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture',
                                 headers={'X-AI2Apps-App-Instance': instance.id}) as client:
        root = '/imagine-studio/comic-translation'
        detected = await client.post(root + '/ocr/detect', files={'file': ('page.png', data.getvalue())})
        assert detected.status_code == 200, detected.text
        regions = detected.json()['regions']
        assert len(regions) == 2 and not calls
        assert regions[0][0] * 640 == pytest.approx(100, abs=4)
        assert regions[1][1] * 380 == pytest.approx(252, abs=4)
        cropped = await client.post(root + '/ocr/recognize', files={'file': ('crop.png', data.getvalue())})
        assert cropped.json() == {'text': 'Good morning!'}
        translated = await client.post(root + '/translate', json={'language': 'zh', 'texts': ['Good morning!']})
        assert translated.json() == {'translations': ['早上好！']}
        assert [call['model'] for call in calls] == [OCR_ID, 'local/translator']
        assert json.loads(calls[1]['messages'][1]['content']) == ['Good morning!']
        invalid = await client.post(root + '/ocr/detect', files={'file': ('page.png', b'invalid')})
        assert invalid.status_code == 422
        wrong_instance = await client.post(root + '/ocr/detect', files={'file': ('page.png', data.getvalue())},
                                           headers={'X-AI2Apps-App-Instance': 'missing'})
        assert wrong_instance.status_code == 404


@pytest.mark.parametrize('ocr_ready',[False,True])
@pytest.mark.asyncio
async def test_comic_descriptor_exposes_defaults_choices_and_actual_setup_reason(monkeypatch,ocr_ready):
    from ai2apps.images import comic_aaat,comic_translation
    async def catalog(_):return {'default':'fixture.default','items':[{'id':'fixture.default','label':'Default translator','local':False}]}
    monkeypatch.setattr(comic_translation,'models',catalog)
    monkeypatch.setattr(comic_translation,'ocr_ready',lambda _:ocr_ready)
    spec={'inputSchema':{'type':'object','properties':{
        'image_ids':{'type':'array','items':{'type':'string'}},
        'language':{'type':'string','enum':['en','fr'],'default':'en'},
        'model_id':{'type':'string'}},'required':['image_ids']}}
    descriptor=await comic_aaat.describe(None,None,None,None,spec)
    assert descriptor['configuration_required'] is not ocr_ready
    assert descriptor['inline_setup'] is not ocr_ready
    assert descriptor['model_field']=='model_id'
    assert descriptor['effective_schema']['properties']['model_id']['default']=='fixture.default'
    assert descriptor['models']==[{'id':'fixture.default','label':'Default translator','local':False,'ready':True}]
    language=next(f for f in descriptor['fields'] if f['key']=='language')
    assert language['options']==[{'value':'en','label':'English'},{'value':'fr','label':'French'}]
    assert bool(descriptor['warnings']) is not ocr_ready
    if not ocr_ready:assert 'OXR' in descriptor['warnings'][0]['en']
    assert 'default' not in spec['inputSchema']['properties']['model_id']
