import asyncio
import hashlib
import io
import json
import time
import zipfile
from dataclasses import replace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from ai2apps.api.doc_studio import create_doc_studio_router
from ai2apps.api.intelligence import create_intelligence_router
from ai2apps.config import PlatformConfig
from ai2apps.doc_studio import render, translation
from ai2apps.gallery import GalleryRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.intelligence import service as editorial
from ai2apps.intelligence.manual_import import asset_path
from ai2apps.platform_runtime import PlatformRuntime


@pytest.fixture
def studio(tmp_path, monkeypatch):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    store = runtime.intelligence_collector.store
    buffer = io.BytesIO()
    Image.new('RGB', (16, 16), 'red').save(buffer, format='PNG')
    data = buffer.getvalue()
    asset = hashlib.sha256(data).hexdigest()
    path = asset_path(store, 'local', asset)
    path.parent.mkdir(parents=True)
    path.write_bytes(data)
    with store.connect() as db:
        for article in ('alpha', 'beta', 'foreign'):
            owner = 'someone-else' if article == 'foreign' else 'local'
            url = f'https://example.org/{article}'
            cover = {'url': f'/v1/platform/intelligence/imports/{asset}/image.png',
                     'alt': '<caption>', 'source_url': url, 'id': 'photo'}
            missing = {'url': '/v1/platform/intelligence/imports/' + '1' * 64 + '/missing.png',
                       'alt': 'Missing photo', 'source_url': url}
            row = {'title': f'Story {article}', 'summary': 'Brief', 'body': 'Evidence about ' + article,
                   'updated_at': '2026-11-11', 'sources': [{'url': url, 'title': 'Source ' + article}],
                   'cover_image': cover, 'images': [cover, missing],
                   'content_blocks': [{'type': 'paragraph', 'text': 'Evidence about ' + article, 'id': 'p1'},
                                      {'type': 'image', 'image_id': 'photo', 'paragraph_id': 'p1'}]}
            db.execute('INSERT INTO articles VALUES (?,?,?,?)', (article, owner, 'news', json.dumps(row)))

    async def model(runtime, request, principal, id, instruction, data, validator, **options):
        assert options['consumer_app_id'] == 'ai2apps.doc-studio'
        assert data['channel']['output_language'] == 'en'
        if 'selected_block' in data:
            assert data['selected_block'] == {'type': 'paragraph', 'text': 'Edited passage [1].'}
            assert data['revision_request'] == 'Make this clearer'
            with pytest.raises(ValueError, match='citation'):
                validator({'text': 'A rewrite with the wrong reference [99].'})
            return validator({'text': 'Clearer passage [1].'})
        assert 'In the first sentence of the body' in instruction
        assert 'reader who has not seen the sources' in instruction
        if data['user_guidance'].startswith('Write a neutral news report'):
            assert 'Attribute announcements and unverified claims' in data['user_guidance']
            if data['format'] == '短 Post':
                assert 'Keep the main event' in instruction
        if 'model failure' in data['user_guidance']:
            raise ValueError('fixture model failure')
        if 'slow generation' in data['user_guidance']:
            await asyncio.sleep(60)
        assert data['evidence'][0]['body'].startswith('Evidence')
        with pytest.raises(ValueError, match='citations'):
            validator({'title': 'Invented', 'content': 'Claim [99]', 'note': 'x', 'evidence_ids': [99]})
        if 'length fixture' in data['user_guidance']:
            if data['format'] == '长 Post':
                assert '25,000' in instruction
                assert options['stage'] == 'long_manuscript'
                content = '字' * 24_970 + ' [1]'
            else:
                content = '字' * 141 + ' [1]'
            try:
                return validator({'title': 'Length fixture', 'content': content, 'note': 'Grounded',
                                  'evidence_ids': [1]})
            except render.XPostError as error:
                from fastapi import HTTPException
                raise HTTPException(502, 'Model returned invalid output') from error
        return validator({'title': 'Draft <b>', 'content': 'News [1].', 'note': 'Grounded', 'evidence_ids': [1]})
    monkeypatch.setattr(editorial, 'model_json', model)

    def principal(request: Request):
        return replace(RequestPrincipal.legacy_local(),
                       actor_user_id=request.headers.get('x-fixture-owner', 'local'),
                       client_scope=request.headers.get('x-fixture-client', 'desktop'))

    app = FastAPI()
    app.include_router(create_intelligence_router(lambda: runtime, principal))
    app.include_router(create_doc_studio_router(lambda: runtime, principal))
    with TestClient(app) as client:
        yield client, runtime
    runtime.stop()


def post(client, path, **payload):
    response = client.post(path, json=payload)
    assert response.status_code < 300, response.text
    return response.json()


def get(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def settle(client, runtime, task, status='completed'):
    path = '/doc-studio/tasks/' + task['id']
    for _ in range(100):
        client.portal.call(runtime.system_tasks.tick)
        result = get(client, path)
        if result['status'] in ('completed', 'failed', 'interrupted', 'cancelled'):
            assert result['status'] == status, result
            return result['result']
        time.sleep(.015)
    pytest.fail('Task did not settle')


def test_passage_rewrite_and_image_rows_round_trip(studio):
    client, runtime = studio
    pack = post(client, '/intelligence/doc-studio-packs', article_ids=['alpha'])
    imported = post(client, '/doc-studio/imports', pack_id=pack['id'], request_id='layout-import')
    path = '/doc-studio/projects/' + settle(client, runtime, imported)['project_id']
    material = get(client, path)['materials'][0]['images'][0]
    generated = post(client, path + '/generate', request_id='layout-generate', style='news',
                     language='en', target='html')
    version_id = settle(client, runtime, generated)['version_id']
    version_path = path + '/versions/' + version_id
    original = get(client, version_path)
    assert [block['type'] for block in original['blocks']] == ['paragraph', 'image']

    gallery = GalleryRepository(runtime.database, runtime.config.paths.artifacts_path / 'gallery')
    buffer = io.BytesIO()
    Image.new('RGB', (16, 16), 'blue').save(buffer, format='PNG')
    buffer.seek(0)
    asset, _ = gallery.import_stream('local', buffer, name='Gallery <photo>.png', media_type='image/png')
    buffer.seek(0)
    foreign, _ = gallery.import_stream('someone-else', buffer, name='Foreign photo.png', media_type='image/png')
    copy_path = path + '/images/gallery'
    assert client.post(copy_path, json={'asset_id': foreign['id']}).status_code == 404
    gallery_image = post(client, copy_path, asset_id=asset['id'])
    assert post(client, copy_path, asset_id=asset['id']) == gallery_image
    gallery.trash_asset('local', asset['id'])
    assert client.get(path + '/images/' + gallery_image['asset_id']).content == buffer.getvalue()

    edited_text = {'type': 'paragraph', 'text': 'Edited passage [1].'}
    request = dict(version_id=version_id, block=edited_text, instruction='Make this clearer', request_id='rewrite')
    assert client.post(path + '/rewrite-block', json=request | {'version_id': 'missing'}).status_code == 404
    rewrite = post(client, path + '/rewrite-block', **request)
    suggestion = settle(client, runtime, rewrite)
    assert get(client, path)['versions'][0]['id'] == version_id
    material_image = {'asset_id': material['asset_id'], 'alt': material['alt']}
    layout = [edited_text | suggestion, {'type': 'image_row', 'images': [material_image, gallery_image]},
              {'type': 'paragraph', 'text': 'A separate paragraph.'},
              {'type': 'image_row', 'images': [gallery_image]}]
    new_version = post(client, version_path, title='Ordered draft', blocks=layout, request_id='save-layout')['id']
    saved = get(client, path + '/versions/' + new_version)
    assert saved['content'] == 'Clearer passage [1].\n\nA separate paragraph.'
    assert [len(render.block_images(block)) for block in saved['blocks']] == [0, 2, 0, 1]
    assert get(client, version_path) == original
    exported = post(client, path + '/export', version_id=new_version, request_id='render-layout')
    output_id = settle(client, runtime, exported)['output_id']
    html = client.get(path + '/outputs/' + output_id).text
    assert html.count('src="data:image/') == 3
    assert html.count('src="data:image/png;base64,') == 2
    assert html.count('<div class="image-row">') == 1
    assert html.index('Clearer passage') < html.index('<div class="image-row">') < html.index('A separate paragraph.')
    assert 'Gallery &lt;photo&gt;.png' in html

    other = post(client, '/doc-studio/projects', title='Other project', request_id='other-layout-project')
    other_path = '/doc-studio/projects/' + other['id']
    assert client.get(other_path + '/images/' + gallery_image['asset_id']).status_code == 404
    assert client.get(path + '/images/' + gallery_image['asset_id'],
                      headers={'x-fixture-owner': 'someone-else'}).status_code == 404
    forged = [{'type': 'paragraph', 'text': 'Body'}, {'type': 'image_row', 'images': [{'asset_id': 'foreign'}]}]
    assert client.post(version_path, json={'title': 'Forged', 'blocks': forged, 'request_id': 'forged'}).status_code == 409


def test_translate_document_profile_context_and_shared_output(studio, monkeypatch):
    client, runtime = studio
    calls = []

    async def catalog(runtime, actor):
        return {'default': 'cloud/default', 'models': [{'id': 'local-small', 'name': 'Local small'}]}

    async def model(payload, *, context):
        assert payload['model'] == 'local-small'
        assert context.consumer_app_id == 'ai2apps.doc-studio'
        data = json.loads(payload['messages'][1]['content'])
        calls.append(data)
        if data['current_passage'] == 'Heading':
            assert data['following'] == ['First passage.', 'Second passage with `code`.']
            translated = '标题'
        elif data['current_passage'] == 'First passage.':
            assert data['preceding'] == [{'source': 'Heading', 'translation': '标题'}]
            translated = '第一段。'
        else:
            assert data['preceding'][-1]['translation'] == '第一段。'
            assert data['following'] == []
            translated = '包含 `code` 的第二段。'
        assert data['user_guidance'] == 'Use the updated glossary'
        return {'choices': [{'message': {'content': json.dumps({'text': translated})}, 'finish_reason': 'stop'}]}

    monkeypatch.setattr('ai2apps.api.doc_studio.conversation_models', catalog)
    monkeypatch.setattr(runtime.model_invocations, 'invoke_chat_json', model)
    path = '/doc-studio/translation'
    profile = post(client, path + '/profiles', name='Glossary', guidance='Use the glossary')
    profile_path = path + '/profiles/' + profile['id']
    assert client.put(profile_path, json={'name': 'Glossary', 'guidance': 'Use the updated glossary'}).status_code == 200
    assert get(client, path + '/profiles')[0]['guidance'] == 'Use the updated glossary'
    foreign = {'x-fixture-owner': 'someone-else'}
    assert client.get(path + '/profiles', headers=foreign).json() == []
    assert client.delete(profile_path, headers=foreign).status_code == 404
    settings = {'language': 'zh', 'model_id': 'local-small', 'profile_id': profile['id'], 'request_id': 'translation'}
    file = b'# Heading\n\nFirst passage.\n\n![Keep this image](photo.png)\n\n- Second passage with `code`.\n'
    response = client.post(path, data={'options': json.dumps(settings)}, files={'file': ('input.md', file)})
    assert response.status_code == 202, response.text
    task = response.json()
    duplicate = client.post(path, data={'options': json.dumps(settings)}, files={'file': ('input.md', file)})
    assert duplicate.json()['id'] == task['id']
    assert client.delete(profile_path).status_code == 204
    result = settle(client, runtime, task)
    assert len(calls) == result['passages'] == 3
    overview = get(client, path)
    assert overview['tasks'][0]['progress']['completed'] == 3
    assert overview['outputs'][0]['target'] == 'translation-md'
    url = path + '/outputs/' + result['output_id']
    output = client.get(url + '?download=true')
    assert output.text == '# 标题\n\n第一段。\n\n![Keep this image](photo.png)\n\n- 包含 `code` 的第二段。\n'
    assert 'input.md' in output.headers['content-disposition']
    assert client.get(url, headers=foreign).status_code == 404
    assert client.get(path, headers=foreign).json() == {'outputs': [], 'tasks': []}


def test_translation_segmentation_keeps_whitespace_and_markdown_structure():
    text = 'First line\nsecond line.\n\n' + 'word ' * 720 + 'end.\n'
    parts = list(translation.split_units(text, False))
    assert ''.join(literal or passage for literal, passage in parts) == text
    assert [passage for _, passage in parts if passage][0] == 'First line\nsecond line.'
    assert all(len(passage) <= translation.UNIT_LIMIT for _, passage in parts)
    markdown = '## Heading\n\n| Header | Column |\n| --- | --- |\n```python\npass\n```\n'
    assert [part for _, part in translation.split_units(markdown, True) if part] == ['Heading', '| Header | Column |']
    assert translation.protected_literals('Code at https://github.com/OpenAI/CLIP.') == (
        translation.protected_literals('代码见 https://github.com/OpenAI/CLIP。'))


def test_pdf_chart_labels_and_same_baseline_columns_stay_separate():
    from reportlab.pdfgen import canvas

    from ai2apps.doc_studio.translation_pdf import PaperLayout

    source = io.BytesIO()
    pdf = canvas.Canvas(source, pagesize=(612, 792))
    pdf.rect(55, 590, 228, 140)
    pdf.setFont('Helvetica', 8)
    pdf.drawString(75, 620, '5 Bag of Words Prediction')
    pdf.setFont('Helvetica', 10)
    pdf.drawString(55, 573, 'Figure 2. Accuracy by sample count.')
    for index in range(10):
        y = 543 - index * 12
        pdf.drawString(55, y, f'Left passage {index} ends here.')
        pdf.drawString(307, y, f'Right passage {index} continues with an independent argument.')
    pdf.save()

    layout = PaperLayout(source.getvalue())
    assert layout.double_column
    assert [block.kind for block in layout.blocks[:2]] == ['figure', 'caption']
    assert all(not block.wide for block in layout.blocks)
    passages = ' '.join(layout.passages())
    assert 'Bag of Words' not in passages
    assert passages.index('Left passage 9') < passages.index('Right passage 0')


def test_pdf_column_balance_prefers_left_and_keeps_heading_with_body():
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph

    from ai2apps.doc_studio.translation_pdf import balanced_columns

    style = ParagraphStyle('body', leading=14)
    rows = [Paragraph(str(number), style) for number in range(5)]
    assert balanced_columns(rows, 200, 100) == (rows[:3], rows[3:])
    heading = Paragraph('Section', ParagraphStyle('heading', leading=14, keepWithNext=True))
    rows[2] = heading
    left, right = balanced_columns(rows, 200, 100)
    assert left == rows[:2]
    assert right == rows[2:]
    assert balanced_columns(rows, 200, 30) is None


@pytest.mark.asyncio
async def test_pdf_translation_restores_original_url_from_placeholder():
    from types import SimpleNamespace

    async def model(request, *, context):
        data = json.loads(request['messages'][1]['content'])
        assert data['current_passage'] == 'Code at ⟦LINK1⟧.'
        return {'choices': [{'message': {'content': '{"text":"代码见⟦LINK1⟧。更多信息见论文。"}'}}]}

    result = await translation.translate_passage(
        SimpleNamespace(invoke_chat_json=model), None,
        {'model_id': 'fixture', 'language': 'zh', 'guidance': '', 'suffix': 'pdf'},
        'Code at https://github.com/OpenAI/CLIP.', [], [],
    )
    assert result == '代码见https://github.com/OpenAI/CLIP。更多信息见论文。'


def test_long_word_translation_reuses_passages_and_preserves_runs(studio, monkeypatch):
    client, runtime = studio
    data = io.BytesIO()
    repeated = '<w:p><w:r><w:t>报告</w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>正文</w:t></w:r></w:p>'
    numeric = '<w:p><w:r><w:t>2026</w:t></w:r></w:p>'
    namespace = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    with zipfile.ZipFile(data, 'w') as archive:
        archive.writestr('word/document.xml', f'<w:document xmlns:w="{namespace}"><w:body>'
                         f'{repeated * 41}{numeric}</w:body></w:document>')
    requests = []

    async def model(payload, *, context):
        requests.append(json.loads(payload['messages'][1]['content'])['labels'])
        return {'choices': [{'message': {'content': json.dumps({'labels': ['Report ⟦1⟧text']})}}]}

    async def catalog(runtime, actor):
        return {'models': [], 'default': 'cloud/default'}

    monkeypatch.setattr('ai2apps.api.doc_studio.conversation_models', catalog)
    monkeypatch.setattr(runtime.model_invocations, 'invoke_chat_json', model)
    path = '/doc-studio/translation'
    response = client.post(path, data={'options': json.dumps({'language': 'en', 'request_id': 'long-word'})},
                           files={'file': ('long.docx', data.getvalue())})
    assert response.status_code == 202, response.text
    result = settle(client, runtime, response.json())
    output = client.get(path + '/outputs/' + result['output_id'])
    with zipfile.ZipFile(io.BytesIO(output.content)) as archive:
        xml = archive.read('word/document.xml').decode()
    assert requests == [['报告⟦1⟧正文']]
    assert xml.count('>Report<') == xml.count('>text<') == xml.count('<w:b/>') == 41
    assert '>2026<' in xml


@pytest.mark.asyncio
async def test_word_batch_reinserts_numeric_spans_after_format_retry():
    class Gateway:
        async def invoke_chat_json(self, request, *, context):
            labels = json.loads(request['messages'][1]['content'])['labels']
            translated = {'价格': 'Price', '元': 'yuan'}
            values = [translated.get(label, 'Price in yuan') for label in labels]
            return {'choices': [{'message': {'content': json.dumps({'labels': values})}}]}

    result = await translation.translate_word_batch(
        Gateway(), None, {'suffix': 'docx', 'word_batch': True, 'model_id': 'fixture',
                          'language': 'en', 'guidance': ''},
        ['价格⟦1⟧100⟦2⟧元'], [], [],
    )
    assert result == ['Price⟦1⟧100⟦2⟧yuan']


def test_word_timeout_splits_batch_and_resumes_saved_prefix(studio, monkeypatch):
    client, runtime = studio
    path = '/doc-studio/translation'
    data = io.BytesIO()
    namespace = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    labels = ['第一段', '第二段', '第三段']
    paragraphs = ''.join(f'<w:p><w:r><w:t>{label}</w:t></w:r></w:p>' for label in labels * 14)
    with zipfile.ZipFile(data, 'w') as archive:
        archive.writestr('word/document.xml', f'<w:document xmlns:w="{namespace}"><w:body>'
                         f'{paragraphs}</w:body></w:document>')
    calls, fail = [], True

    async def catalog(runtime, actor):
        return {'models': [], 'default': 'cloud/default'}

    async def model(request, *, context):
        input_data = json.loads(request['messages'][1]['content'])
        entries = input_data.get('labels') or [input_data['source']]
        calls.append(entries)
        if len(entries) > 1 or fail and entries == labels[1:2]:
            raise TimeoutError()
        if 'source' in input_data:
            return {'choices': [{'message': {'content': 'Translated'}}]}
        return {'choices': [{'message': {'content': json.dumps({'labels': ['Translated']})}}]}

    monkeypatch.setattr('ai2apps.api.doc_studio.conversation_models', catalog)
    monkeypatch.setattr(runtime.model_invocations, 'invoke_chat_json', model)
    response = client.post(path, data={'options': json.dumps({'language': 'en', 'request_id': 'resume-word'})},
                           files={'file': ('long.docx', data.getvalue())})
    assert response.status_code == 202
    task = response.json()
    settle(client, runtime, task, 'failed')
    assert calls[0] == labels
    assert runtime.system_tasks.get('local', task['id'])['checkpoint']['word_partial'] == ['Translated']
    fail = False
    calls.clear()
    url = path + '/tasks/' + task['id'] + '/resume'
    first, duplicate = client.post(url), client.post(url)
    assert first.status_code == duplicate.status_code == 202
    assert first.json()['id'] == duplicate.json()['id'] != task['id']
    result = settle(client, runtime, first.json())
    assert calls[0] == labels[1:] and all(labels[0] not in call for call in calls)
    output = client.get(path + '/outputs/' + result['output_id'])
    with zipfile.ZipFile(io.BytesIO(output.content)) as archive:
        assert archive.read('word/document.xml').count(b'>Translated<') == 42


@pytest.mark.asyncio
async def test_word_stream_closes_as_soon_as_json_is_complete():
    from starlette.responses import StreamingResponse

    class Gateway:
        def model(self, name):
            return True

        async def invoke_background_json(self, model, operation, payload, *, context):
            assert payload['stream']
            return StreamingResponse(stream())

    closed = asyncio.Event()

    async def stream():
        try:
            for part in ('{"labels":', '["English"]}'):
                event = {'choices': [{'delta': {'content': part}}]}
                wire = ('data: ' + json.dumps(event) + '\n\n').encode()
                yield wire[:5]
                yield wire[5:]
            pytest.fail('A complete response should not wait for later tokens.')
        finally:
            closed.set()

    response = await translation.request_word_translation(Gateway(), None, {'model': 'local-model'})
    assert translation.parse_model_json(response) == {'labels': ['English']}
    assert closed.is_set()


def test_word_pagination_preserves_explicit_breaks_and_content():
    from lxml import etree
    from ai2apps.doc_studio.translation_docx import W, polish_pagination

    body = etree.fromstring(f'<w:body xmlns:w="{W[1:-1]}">'
        '<w:p><w:pPr><w:sectPr/></w:pPr><w:r><w:t>Heading</w:t></w:r></w:p>'
        '<w:p><w:pPr><w:sectPr/></w:pPr></w:p>'
        '<w:p><w:pPr><w:sectPr><w:type w:val="oddPage"/></w:sectPr></w:pPr></w:p>'
        '<w:p><w:pPr><w:sectPr/></w:pPr><w:r><w:br w:type="page"/></w:r></w:p>'
        '<w:p><w:pPr><w:sectPr/></w:pPr><w:r><w:drawing/></w:r></w:p>'
        '<w:sectPr/></w:body>')
    polish_pagination(body)
    assert [item.get(W + 'val') for item in body.iter(W + 'type')] == ['continuous', 'oddPage', 'continuous']
    assert len(body) == 6


@pytest.mark.parametrize('suffix', ['docx', 'pdf'])
def test_translation_downloads_original_format(studio, monkeypatch, suffix):
    client, runtime = studio
    data = io.BytesIO()
    if suffix == 'docx':
        namespace = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('word/document.xml', f'''<w:document xmlns:w="{namespace}"><w:body>
                <w:p><w:r><w:t>Hello </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>world</w:t></w:r></w:p>
                <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Table cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
                </w:body></w:document>''')
            archive.writestr('word/media/chart.png', b'unchanged image')
        expected = {'Hello ⟦1⟧world': '你好 ⟦1⟧世界', 'Table cell': '表格'}
    else:
        from reportlab.pdfgen import canvas
        pdf = canvas.Canvas(data, pagesize=(612, 792))
        pdf.setFont('Helvetica-Bold', 18)
        pdf.drawCentredString(306, 720, 'Scientific Report')
        pdf.setFont('Helvetica', 10)
        for index in range(8):
            pdf.drawString(55, 670 - index * 12, f'Left column sample row {index}.')
            pdf.drawString(325, 670 - index * 12, f'Right column sample row {index}.')
        pdf.save()
        from ai2apps.doc_studio.translation_pdf import PaperLayout
        source_layout = PaperLayout(data.getvalue())
        assert source_layout.double_column
        assert 'Left column' in source_layout.passages()[1]
        assert 'Right column' in source_layout.passages()[2]
        expected = {text: '译文 ' + text for text in source_layout.passages()}

    async def catalog(runtime, actor):
        return {'models': [], 'default': 'cloud/default'}

    async def model(payload, *, context):
        passage = json.loads(payload['messages'][1]['content'])['current_passage']
        return {'choices': [{'message': {'content': json.dumps({'text': expected[passage]})}}]}

    monkeypatch.setattr('ai2apps.api.doc_studio.conversation_models', catalog)
    monkeypatch.setattr(runtime.model_invocations, 'invoke_chat_json', model)
    path = '/doc-studio/translation'
    response = client.post(path, data={'options': json.dumps({'language': 'zh', 'request_id': 'layout'})},
                           files={'file': ('source.' + suffix, data.getvalue())})
    assert response.status_code == 202, response.text
    task = response.json()
    result = settle(client, runtime, task)
    url = path + '/outputs/' + result['output_id']
    output = client.get(url + '?download=true')
    assert output.headers['content-type'] == translation.MEDIA_TYPES[suffix]
    assert f'source.{suffix}' in output.headers['content-disposition']
    if suffix == 'docx':
        with zipfile.ZipFile(io.BytesIO(output.content)) as archive:
            xml = archive.read('word/document.xml').decode()
            assert all(word in xml for word in ('你好', '世界', '表格', '<w:b/>', '<w:tbl>'))
            assert archive.read('word/media/chart.png') == b'unchanged image'
    else:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(output.content)) as paper:
            first = paper.pages[0]
            assert 'Scientific Report' in first.extract_text()
            assert 'Left column' in first.crop((0, 0, 306, first.height)).extract_text()
            assert 'Right column' in first.crop((306, 0, 612, first.height)).extract_text()


def test_owner_handoff_versioned_outputs_and_recovery(studio):
    client, runtime = studio
    endpoint = '/intelligence/doc-studio-packs'
    assert client.post(endpoint, json={'article_ids': ['alpha', 'foreign']}).status_code == 404
    assert client.post(endpoint, json={'article_ids': ['alpha']},
                       headers={'x-fixture-client': 'mobile'}).status_code == 403
    pack = post(client, endpoint, article_ids=['beta', 'alpha'])
    assert len(pack['entries']) == 2
    assert post(client, endpoint, article_ids=['alpha', 'beta'])['id'] == pack['id']
    first = post(client, '/doc-studio/imports', request_id='import-1', pack_id=pack['id'], title='News project')
    project = settle(client, runtime, first)['project_id']
    assert post(client, '/doc-studio/imports', request_id='import-1', pack_id=pack['id'], title='News project')['id'] == first['id']
    assert client.post('/doc-studio/imports', json={
        'request_id': 'import-1', 'pack_id': pack['id'], 'title': 'Different',
    }).status_code == 409

    path = '/doc-studio/projects/' + project
    materials = get(client, path)['materials']
    assert len(materials) == 2
    assert all(item['images'][0]['anchor'] == 'p1' for item in materials)
    assert all(item['images'][1]['error'] for item in materials)
    image_url = materials[0]['images'][0]['preview_url'].removeprefix('/v1/platform')
    assert client.get(image_url).headers['content-type'] == 'image/jpeg'
    repeated = post(client, '/doc-studio/imports', request_id='repeat', pack_id=pack['id'], project_id=project)
    settle(client, runtime, repeated)
    assert len(get(client, path)['materials']) == 2

    for target in ('x-post', 'html'):
        task = post(client, path + '/generate', request_id=target, target=target, style='news', language='en')
        version = settle(client, runtime, task)['version_id']
        assert get(client, path + '/versions/' + version)['style'] == 'news'
        task = post(client, path + '/export', request_id='export-' + target, version_id=version)
        settle(client, runtime, task)
        assert post(client, path + '/export', request_id='export-' + target, version_id=version)['id'] == task['id']
    html_version = version
    html_output = task['id']
    raw = client.get(path + '/outputs/' + html_output)
    assert 'sandbox' in raw.headers['content-security-policy']
    assert b'Draft &lt;b&gt;' in raw.content
    assert b'<a href="#source-1">[1]</a>' in raw.content
    assert b'data:image/jpeg;base64,' in raw.content
    assert b'https://example.org/' in raw.content
    edited = post(client, path + '/versions/' + html_version, request_id='edit',
                  title='New title', content='## Changed\n- <script>alert(1)</script> [1]\n> Quoted')
    task = post(client, path + '/export', request_id='export-edit', version_id=edited['id'])
    settle(client, runtime, task)
    changed = client.get(path + '/outputs/' + task['id'] + '?download=true')
    assert changed.headers['content-disposition'].startswith('attachment;')
    assert b'<h2>Changed</h2>' in changed.content and b'<ul>' in changed.content
    assert b'<script>' not in changed.content
    assert client.get(path + '/outputs/' + html_output).content == raw.content

    x_post = next(item for item in get(client, path)['outputs'] if item['target'] == 'x-post')
    x_url = x_post['preview_url'].removeprefix('/v1/platform')
    assert client.get(x_url).text.startswith('News.\nhttps://example.org/')
    for url in (path, image_url, x_url + '?download=true', path + '/versions/' + html_version,
                '/doc-studio/packs/' + pack['id'], '/doc-studio/tasks/' + task['id']):
        assert client.get(url, headers={'x-fixture-owner': 'someone-else'}).status_code == 404

    failed = post(client, path + '/generate', request_id='fail', target='html',
                  style='summary', language='en', guidance='model failure')
    settle(client, runtime, failed, 'failed')
    cancelled = post(client, path + '/generate', request_id='cancel', target='html',
                     style='summary', language='en', guidance='slow generation')
    client.portal.call(runtime.system_tasks.tick)
    post(client, '/doc-studio/tasks/' + cancelled['id'] + '/cancel')
    settle(client, runtime, cancelled, 'cancelled')
    assert len(get(client, path)['versions']) == 3
    assert len(get(client, path)['outputs']) == 3


def test_x_post_weight_and_external_urls():
    evidence = [{'evidence_id': 1, 'sources': [{'url': 'https://example.org/' + 'x' * 280}]}]
    assert render.x_post('中' * 128 + ' [1]', evidence).endswith(evidence[0]['sources'][0]['url'])
    with pytest.raises(ValueError, match='280'):
        render.x_post('中' * 129 + ' [1]', evidence)
    with pytest.raises(ValueError, match='instead of URLs'):
        render.x_post('Unknown https://example.org/ [1]', evidence)


def test_project_management_preserves_owner_and_blocks_active_deletion(studio):
    client, runtime = studio
    base = '/doc-studio/projects'
    body = {'title': 'New project', 'request_id': 'create-once'}
    project = post(client, base, **body)
    assert post(client, base, **body) == project
    assert client.post(base, json={**body, 'title': 'Other'}).status_code == 409
    path = base + '/' + project['id']
    foreign = {'x-fixture-owner': 'someone-else'}
    assert client.patch(path, json={'title': 'Foreign'}, headers=foreign).status_code == 404
    assert client.delete(path, headers=foreign).status_code == 404
    assert client.patch(path, json={'title': 'Renamed'}).json()['title'] == 'Renamed'

    pack = post(client, '/intelligence/doc-studio-packs', article_ids=['alpha'])
    job = post(client, '/doc-studio/imports', request_id='import-one',
               project_id=project['id'], pack_id=pack['id'])
    assert client.delete(path).status_code == 409
    settle(client, runtime, job)
    image = get(client, path)['materials'][0]['images'][0]['preview_url'].removeprefix('/v1/platform')
    generated = post(client, path + '/generate', request_id='write-once',
                     target='html', style='summary', language='en')
    version = settle(client, runtime, generated)['version_id']
    exported = post(client, path + '/export', request_id='export-once', version_id=version)
    output = settle(client, runtime, exported)['output_id']
    assert client.delete(path).status_code == 204
    assert client.delete(path).status_code == 204
    assert get(client, base) == []
    for url in (path, image, path + '/versions/' + version, path + '/outputs/' + output):
        assert client.get(url).status_code == 404
    assert client.post(base, json=body).status_code == 404
    assert client.post(path + '/generate', json={
        'request_id': 'after-delete', 'target': 'html', 'style': 'summary', 'language': 'en',
    }).status_code == 404


def test_writing_chat_scope_and_generation_receipt(studio):
    from ai2apps.doc_studio.chat import EXPORT, GENERATE, REGISTRATION
    from ai2apps.doc_studio.models import MINI_ID
    from ai2apps.identity import IdentityRepository, OrganizationType

    client, runtime = studio
    principal = RequestPrincipal.legacy_local()
    IdentityRepository(runtime.database).bind_installation(
        installation_id='local', cloud_device_id='test-device', organization_id='local',
        organization_type=OrganizationType.HOUSEHOLD, core_user_id='local',
        billing_account_id='local', access_epoch=1,
    )
    base = '/doc-studio/projects'
    pack = post(client, '/intelligence/doc-studio-packs', article_ids=['alpha'])
    imported = post(client, '/doc-studio/imports', request_id='chat-import', pack_id=pack['id'])
    first = settle(client, runtime, imported)['project_id']
    second = post(client, base, request_id='other-project', title='Other project')['id']
    app_chat = runtime.app_chat

    def open_chat(project):
        return app_chat.open(principal, REGISTRATION, {'mini_app_id': MINI_ID, 'project_id': project}, {})

    sid = open_chat(first)
    assert sid == open_chat(first) and sid != open_chat(second)
    with pytest.raises(ValueError, match='unavailable'):
        open_chat('unknown-project')
    context = replace(runtime.tools.context_for_session(caller_id='fixture', session_id=sid),
                      invocation_id='write-chat-fixture')
    tools = {item.qualified_name for item in runtime.tools.list_tools(context, include_requiring_approval=True)}
    assert {'studio.ui', GENERATE, EXPORT} <= tools
    assert 'image.generate' not in tools
    with pytest.raises(Exception):
        client.portal.call(runtime.app_capability_router.invoke, 'studio.ui',
                           {'action': 'update_draft', 'values': {'project_id': second}}, context)
    with pytest.raises(Exception):
        client.portal.call(runtime.app_capability_router.invoke, EXPORT, {'version_id': 'foreign-version'}, context)

    ui = {'project': {'id': first}, 'draft': {'style': 'summary'}}
    app_chat.heartbeat(principal, sid, 'writer-mount', ui)
    assert client.portal.call(runtime.app_capability_router.invoke, 'studio.ui', {'action': 'read'}, context)['ui'] == ui
    pending = client.portal.start_task_soon(runtime.app_capability_router.invoke, 'studio.ui',
                                           {'action': 'update_draft', 'values': {'style': 'analysis'}}, context)
    for _ in range(100):
        commands = app_chat.snapshot(principal, sid)['commands']
        if commands:
            break
        time.sleep(.01)
    assert commands
    command = commands[0]
    assert command['arguments']['values'] == {'style': 'analysis'}
    app_chat.acknowledge(principal, sid, command['id'], 'writer-mount', command['revision'],
                         {'applied': True, 'project_id': first}, True)
    assert pending.result(timeout=3)['status'] == 'applied'

    args = {'style': 'news', 'target': 'x-long-post', 'language': 'en'}
    queued = client.portal.call(runtime.app_capability_router.invoke, GENERATE, args, context)
    duplicate = client.portal.call(runtime.app_capability_router.invoke, GENERATE, args, context)
    assert queued['status'] == 'queued' and queued['task_id'] == duplicate['task_id']
    version = settle(client, runtime, {'id': queued['task_id']})['version_id']
    assert get(client, base + '/' + first)['versions'][0]['id'] == version
    assert get(client, base + '/' + second)['versions'] == []
    export = client.portal.call(runtime.app_capability_router.invoke, EXPORT, {'version_id': version}, context)
    output_id = settle(client, runtime, {'id': export['task_id']})['output_id']
    assert get(client, base + '/' + first)['outputs'][0]['id'] == output_id
    assert get(client, base + '/' + second)['outputs'] == []


def test_shortcut_capture_accepts_only_portable_writing_settings(studio):
    from ai2apps.apps.app_state import StateError
    from ai2apps.apps.state_setup import get_app_state
    from ai2apps.doc_studio.models import APP_ID

    _, runtime = studio
    principal = RequestPrincipal.legacy_local()
    state = get_app_state(runtime)
    instance, _, _ = runtime.extension_manager.launch_app(APP_ID, principal=principal)
    packet = {'schema': 'ai2apps.app-state/v1',
              'target': {'app_id': APP_ID, 'mini_app_id': None, 'contract_version': 1},
              'values': {'style': 'summary', 'target': 'html', 'language': 'en'}}
    assert state.validate(principal, instance.id, packet)['packet'] == packet
    news_packet = {**packet, 'values': {**packet['values'], 'style': 'news', 'target': 'x-long-post'}}
    assert state.validate(principal, instance.id, news_packet)['packet'] == news_packet
    for private in ('project_id', 'guidance', 'content'):
        with pytest.raises(StateError):
            state.validate(principal, instance.id, {**packet, 'values': {**packet['values'], private: 'private'}})


def test_external_writing_and_translation_chat_scopes(studio):
    from ai2apps.doc_studio.chat import EXPORT, GENERATE, PROJECTS, TRANSLATE, TRANSLATION_CHAT
    from ai2apps.doc_studio.models import APP_ID
    from ai2apps.messager.bots import REGISTRATION as BOT_CHAT
    from ai2apps.identity import IdentityRepository, OrganizationType
    from ai2apps.system_tasks.sessions import execution_session
    from test_app_chat_durable import response
    from test_app_interactions import wait

    client, runtime = studio
    principal = RequestPrincipal.legacy_local()
    IdentityRepository(runtime.database).bind_installation(
        installation_id='local', cloud_device_id='test-device', organization_id='local',
        organization_type=OrganizationType.HOUSEHOLD, core_user_id='local',
        billing_account_id='local', access_epoch=1,
    )
    pack = post(client, '/intelligence/doc-studio-packs', article_ids=['alpha'])
    imported = post(client, '/doc-studio/imports', request_id='external-import', pack_id=pack['id'])
    project = settle(client, runtime, imported)['project_id']
    sid = execution_session(runtime, 'local', APP_ID)
    context = replace(runtime.tools.context_for_session(caller_id='fixture', session_id=sid),
                      invocation_id='external-write-fixture')
    available = {item.qualified_name for item in runtime.tools.list_tools(context, include_requiring_approval=True)}
    assert {PROJECTS, GENERATE, EXPORT, TRANSLATE} <= available
    args = {'project_id': project, 'style': 'news', 'target': 'html', 'language': 'en'}
    queued = client.portal.call(runtime.app_capability_router.invoke, GENERATE, args, context)
    version = settle(client, runtime, {'id': queued['task_id']})['version_id']

    bot = runtime.messager_bots.create('local', 'Writer fixture', 'Find and export article drafts')
    access = runtime.messager_bot_app_access
    providers = runtime.app_capability_router.providers
    target = access.target(providers[APP_ID + '.' + PROJECTS])
    catalog = access.catalog('local', bot['id'])
    assert any(item['app_id'] == target and item['available'] for item in catalog['items'])
    access.save('local', bot['id'], catalog['revision'], catalog['review_hash'], [{'app_id':target, 'enabled':True}])
    assert access.granted('local', bot['id'], providers[APP_ID + '.' + EXPORT])
    assert not access.granted('local', bot['id'], providers[APP_ID + '.' + TRANSLATE])
    bot_session = runtime.app_chat.open(principal, BOT_CHAT, {'bot_id':bot['id']}, {})
    calls = []

    async def model(request):
        if len(calls) == 2:
            return response(text='Export queued')
        calls.append(request)
        if len(calls) == 1:
            return response('app.describe', {'capability':EXPORT})
        return response(EXPORT, {'project_id':project, 'version_id':version})

    async def bot_run():
        runtime.agent_runtime.bind_model_provider(model)
        await runtime.start_background_tasks(retention_interval_seconds=60)
        run = runtime.app_chat.submit(principal, bot_session, 'external-export', 'Export the saved draft', 'fixture')
        await wait(runtime, run, 'completed')
        with runtime.database.transaction() as db:
            row = db.execute('SELECT status,output_json FROM tool_invocations WHERE session_id=? AND qualified_name=?',
                             (bot_session, EXPORT)).fetchone()
        assert row and row['status'] == 'completed', runtime.app_chat.snapshot(principal, bot_session)['messages']
        return json.loads(row['output_json'])

    result = client.portal.call(bot_run)
    assert result['task_id']
    settle(client, runtime, {'id':result['task_id']})
    translated = runtime.app_chat.open(principal, TRANSLATION_CHAT, {'mini_app_id':translation.MINI_ID}, {})
    bound = runtime.app_chat.binding(translated)
    assert APP_ID + '.' + TRANSLATE in bound['providers']
    assert APP_ID + '.' + GENERATE not in bound['providers']


def test_x_post_length_boundaries():
    source = 'https://example.org/alpha'
    evidence = [{'evidence_id': 1, 'sources': [{'url': source}]}]
    assert render.x_post('字' * 128 + ' [1]', evidence) == '字' * 128 + '\n' + source
    with pytest.raises(render.XPostError) as short:
        render.x_post('字' * 129 + ' [1]', evidence)
    assert short.value.details == {'code': 'post_too_long', 'count': 282, 'limit': 280, 'weighted': True}
    exact = '字' * (25_000 - len(source) - 1)
    assert render.x_post(exact + ' [1]', evidence, long=True) == exact + '\n' + source
    with pytest.raises(render.XPostError) as long:
        render.x_post(exact + '字 [1]', evidence, long=True)
    assert long.value.details == {'code': 'post_too_long', 'count': 25_001, 'limit': 25_000, 'weighted': False}


def test_long_post_edit_export_and_standard_failure_details(studio):
    client, runtime = studio
    pack = post(client, '/intelligence/doc-studio-packs', article_ids=['alpha'])
    imported = post(client, '/doc-studio/imports', request_id='length-import', pack_id=pack['id'])
    project = settle(client, runtime, imported)['project_id']
    path = '/doc-studio/projects/' + project
    args = {'style': 'news', 'language': 'en', 'guidance': 'length fixture'}

    short = post(client, path + '/generate', request_id='short-length', target='x-post', **args)
    settle(client, runtime, short, 'failed')
    failed = get(client, '/doc-studio/tasks/' + short['id'])
    assert failed['progress']['draft_error'] == {
        'code': 'post_too_long', 'count': 306, 'limit': 280, 'weighted': True,
    }
    assert '306' in failed['message']
    assert get(client, path)['versions'] == []

    long = post(client, path + '/generate', request_id='long-length', target='x-long-post', **args)
    version = settle(client, runtime, long)['version_id']
    draft = get(client, path + '/versions/' + version)
    assert draft['target'] == 'x-long-post' and len(draft['content']) > 24_000
    revised = post(client, path + '/versions/' + version, request_id='long-edit',
                   title='Edited', content=draft['content'])['id']
    export = post(client, path + '/export', request_id='long-export', version_id=revised)
    output = settle(client, runtime, export)['output_id']
    result = client.get(path + '/outputs/' + output + '?download=true')
    assert result.headers['content-type'].startswith('text/plain')
    assert result.text == '字' * 24_970 + '\nhttps://example.org/alpha'

    too_long = post(client, path + '/versions/' + version, request_id='long-overflow',
                    title='Too long', content='字' * 25_000 + ' [1]')['id']
    export = post(client, path + '/export', request_id='long-overflow-export', version_id=too_long)
    settle(client, runtime, export, 'failed')
    failed = get(client, '/doc-studio/tasks/' + export['id'])
    assert failed['progress']['draft_error']['limit'] == 25_000
    assert len(get(client, path)['outputs']) == 1


def test_keep_form_preserves_interactive_values_and_only_translates_static_label(studio, monkeypatch):
    from pypdf import PdfReader
    from reportlab.pdfgen import canvas

    client, runtime = studio
    source = io.BytesIO()
    pdf = canvas.Canvas(source)
    pdf.drawString(72, 720, 'Applicant name')
    pdf.acroForm.textfield(name='name', value='Private fixture value', x=210, y=713, width=190, height=17)
    pdf.showPage()
    pdf.save()

    async def catalog(runtime, actor):
        return {'models': [{'id': 'local-test'}], 'default': 'cloud/default'}

    async def model(payload, *, context):
        body = json.loads(payload['messages'][1]['content'])
        assert body['labels'] == ['Applicant name']
        assert 'Private fixture value' not in str(payload)
        return {'choices': [{'message': {'content': '{"labels":["Nom du demandeur"]}'}}]}

    monkeypatch.setattr('ai2apps.api.doc_studio.conversation_models', catalog)
    monkeypatch.setattr(runtime.model_invocations, 'invoke_chat_json', model)
    path = '/doc-studio/translation'
    files = {'file': ('source.pdf', source.getvalue())}
    form = {'output_format': 'form'}
    options = {'language': 'fr', 'request_id': 'keep-form'}
    denied = client.post(path, data={**form, 'options': json.dumps(options)}, files=files)
    assert denied.status_code == 409
    response = client.post(path, data={**form, 'options': json.dumps({**options, 'model_id': 'local-test'})}, files=files)
    assert response.status_code == 202, response.text
    result = settle(client, runtime, response.json())
    output = client.get(path + '/outputs/' + result['output_id'])
    original = PdfReader(source)
    translated = PdfReader(io.BytesIO(output.content))
    assert translated.pages[0].extract_text().strip() == 'Nom du demandeur'
    assert translated.get_fields()['name']['/V'] == 'Private fixture value'
    old_widget = original.pages[0]['/Annots'][0].get_object()
    new_widget = translated.pages[0]['/Annots'][0].get_object()
    assert old_widget['/Rect'] == new_widget['/Rect']
    assert old_widget['/AP']['/N'].get_data() == new_widget['/AP']['/N'].get_data()
