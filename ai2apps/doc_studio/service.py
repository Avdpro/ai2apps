"""Project operations and durable System Task handlers owned by Doc Studio."""
import asyncio
import hashlib
import io
import json
import logging
import re
from collections import Counter
from threading import RLock

from fastapi import HTTPException
from PIL import Image
from pydantic import Field, ValidationError

from ai2apps.apps.access import has_app_capability
from ai2apps.core import ResourceNotFoundError
from ai2apps.gallery import GalleryRepository
from ai2apps.intelligence import doc_studio_pack as source, html_export, service as editorial, writing
from ai2apps.research.provider import WebProviderError
from ai2apps.system_tasks import TaskHandler
from ai2apps.system_tasks.sessions import execution_principal

from . import render
from .models import (
    APP_ID, MAX_DRAFT_CHARS, MAX_LONG_DRAFT_CHARS, MINI_ID, X_LONG_POST_LIMIT,
    Export, Generate, ImageRow, Import, RewriteBlock, TextBlock,
)
from .repository import Repository

_project_admission = RLock()

IMAGE_LIMIT = 20
IMAGE_BUDGET = 12 * 1024 * 1024
STYLES = {
    'summary': 'Summarize the important developments concisely.',
    'analysis': 'Analyze implications and distinguish interpretations from evidence.',
    'commentary': 'Write a repost commentary with a clear opinion grounded in the evidence.',
    'news': (
        'Write a neutral news report. Lead with the main event, then add the most relevant '
        'background and concrete facts. Include when, where and how only if relevant and '
        'supported. Attribute announcements and unverified claims to whoever made them. '
        'If the evidence covers unrelated events, focus on the event relevant to the request '
        'and project title unless the user asks for a roundup.'
    ),
}
SELF_CONTAINED_LEAD = (
    'Write for a reader who has not seen the sources. In the first sentence of the body, name '
    'who or what the story is about and say what happened. Briefly explain unfamiliar names or '
    'terms where needed to understand the event. Put essential context in the body even if it '
    'appears in the title or linked source. Introduce the event before interpreting it. '
)
NAMES = {'import': '导入素材 / Import materials', 'generate': '生成稿件 / Generate draft',
         'export': '渲染产物 / Render output', 'rewrite_block': '改写段落 / Rewrite passage'}


class LongPostManuscript(writing.Manuscript):
    content: str = Field(min_length=1, max_length=MAX_LONG_DRAFT_CHARS)


def _report_draft_error(ctx, error, stage):
    if isinstance(error, render.XPostError):
        details = error.details
    elif isinstance(error, writing.ManuscriptCitationError):
        details = {'code': 'invalid_citations'}
    elif isinstance(error, (ValidationError, json.JSONDecodeError)):
        details = {'code': 'invalid_draft'}
    else:
        return
    ctx.report(message=str(error) if isinstance(error, render.XPostError) else 'Model draft failed validation',
               progress={'stage': stage, 'draft_error': details})


def require_access(principal):
    if not has_app_capability(principal, 'app.use') or principal.client_scope != 'desktop':
        raise PermissionError('Doc Studio Local access required')


def pack_summary(pack):
    return {k: pack[k] for k in ('id', 'schema', 'pack_key', 'version')} | {
        'entries': [{'title': item['title'], 'source_id': item['source_id'],
                     'images': len(item['images'])} for item in pack['entries']],
    }


def create_pack(repo, store, principal, selection):
    require_access(principal)
    return pack_summary(repo.save_pack(principal.actor_user_id,
                                      source.snapshot(store, principal.actor_user_id, selection.article_ids)))


def submit(runtime, principal, operation, project_id, body):
    require_access(principal)
    owner = principal.actor_user_id
    if isinstance(body, Import):
        # Retransmitting the same new-project intent always targets the same ID.
        project_id = body.project_id or source.digest([owner, body.request_id])[:32]
    with _project_admission:
        return runtime.system_tasks.submit(
            owner, APP_ID, 'doc_studio.' + operation, NAMES[operation],
            {'project_id': project_id, 'input': body.model_dump()},
            receipt_key=operation + ':' + body.request_id,
        )


def create_project(repo, owner, body):
    return repo.create_project(owner, source.digest(['manual-project', owner, body.request_id])[:32], body.title)


def delete_project(repo, owner, project_id):
    with _project_admission:
        repo.delete_project(owner, project_id)


def task(runtime, owner, task_id):
    result = runtime.system_tasks.get(owner, task_id)
    if result['app_id'] != APP_ID:
        raise KeyError('Doc Studio task unavailable')
    return {key: result[key] for key in ('id', 'kind', 'status', 'message', 'progress', 'result')} | {
        'project_id': result['payload']['project_id'],
    }


def version_data(title, content, options, evidence, *, origin, parent=None, note='', layout=None):
    refs = render.references(content, {item['evidence_id'] for item in evidence})
    blocks = render.blocks(content) if layout is None else layout
    if layout is None and options['target'] == 'html':
        attached, size = set(), 0
        for item in evidence:
            if item['evidence_id'] not in refs:
                continue
            citation = f'[{item["evidence_id"]}]'
            image = next((i for i in item['images'] if i.get('asset_id')), None)
            if not image or image['asset_id'] in attached or size + image['size'] > IMAGE_BUDGET:
                continue
            attached.add(image['asset_id'])
            size += image['size']
            position = next((i + 1 for i, block in enumerate(blocks)
                             if citation in block.get('text', ' '.join(block.get('items', [])))), len(blocks))
            blocks.insert(position, {'type': 'image', **image})
    return {**{key: options[key] for key in ('style', 'target', 'language', 'guidance')},
            'title': title, 'content': content, 'blocks': blocks, 'evidence': evidence, 'evidence_ids': refs,
            'origin': origin, 'parent_version_id': parent, 'note': note}


def ordered_blocks(repo, owner, project_id, base, blocks):
    images = [image for block in blocks if isinstance(block, ImageRow) for image in block.images]
    if len(images) > IMAGE_LIMIT:
        raise ValueError(f'每版稿件最多插入 {IMAGE_LIMIT} 张图片 / A draft version supports up to {IMAGE_LIMIT} images.')
    counts = Counter(image.asset_id for image in images)
    sizes = repo.image_sizes(owner, project_id, list(counts))
    if counts.keys() != sizes.keys():
        raise ValueError('部分图片不属于当前工程 / Some images are unavailable in this project.')
    if sum(sizes[asset] * count for asset, count in counts.items()) > IMAGE_BUDGET:
        raise ValueError('稿件图片合计超过 12 MiB，请移除部分图片 / Draft images exceed 12 MiB. Remove some images.')
    sources = {image['asset_id']: image.get('source_url', '')
               for material in repo.materials(owner, project_id) for image in material['images']
               if image.get('asset_id')}
    for block in base['blocks']:
        for image in render.block_images(block):
            if image.get('source_url'):
                sources[image['asset_id']] = image['source_url']
    layout = []
    for block in blocks:
        if isinstance(block, ImageRow):
            layout.append({'type': 'image_row', 'images': [
                {**image.model_dump(), 'source_url': sources.get(image.asset_id, '')} for image in block.images
            ]})
        elif block.type == 'list':
            layout.append({'type': 'list', 'items': [line.strip() for line in block.text.splitlines() if line.strip()]})
        else:
            layout.append(block.model_dump())
    return layout


def edit(repo, owner, project_id, version_id, body):
    base = repo.version(owner, project_id, version_id)
    content, layout = body.content, None
    if body.blocks is not None:
        layout = ordered_blocks(repo, owner, project_id, base, body.blocks)
        passages = [render.block_text(block) for block in layout if not render.block_images(block)]
        previous = [render.block_text(block) for block in base['blocks'] if not render.block_images(block)]
        content = base['content'] if passages == previous else '\n\n'.join(passages)
    elif content == base['content']:
        layout = base['blocks']
    if not content:
        raise ValueError('请保留至少一段正文 / Keep at least one text block in the draft.')
    limit = MAX_LONG_DRAFT_CHARS if base['target'] == 'x-long-post' else MAX_DRAFT_CHARS
    if len(content) > limit:
        raise ValueError(f'稿件正文最多 {limit:,} 字符 / Draft body is limited to {limit:,} characters.')
    version = version_data(body.title, content, base, base['evidence'],
                           origin='manual', parent=version_id, layout=layout)
    request = {'base': version_id, **body.model_dump()}
    return repo.save_version(owner, project_id, source.digest(['edit', body.request_id])[:32],
                             version | {'request': request}, request=request)


def import_gallery_image(runtime, owner, project_id, asset_id):
    repo = Repository(runtime.database)
    repo.project(owner, project_id)
    gallery = GalleryRepository(runtime.database, runtime.config.paths.artifacts_path / 'gallery')
    try:
        asset, path = gallery.asset_path(owner, asset_id)
        if asset['status'] != 'active' or asset['kind'] != 'image':
            raise ValueError('请选择 Gallery 中可用的图片 / Select an available image in Gallery.')
        limit = 8 * 1024 * 1024
        with path.open('rb') as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Gallery 图片超过 8 MiB / Gallery image exceeds 8 MiB.')
        with Image.open(io.BytesIO(data)) as image:
            mime = Image.MIME.get(image.format)
            if mime not in {'image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/avif'}:
                raise ValueError('请使用 PNG、JPEG、WebP、GIF 或 AVIF 图片 / Use a PNG, JPEG, WebP, GIF or AVIF image.')
            if image.width * image.height > 40_000_000:
                raise ValueError('图片超过 4,000 万像素 / Image exceeds 40 million pixels.')
            image.verify()
    except ResourceNotFoundError as error:
        raise KeyError('Gallery image unavailable') from error
    except (OSError, SyntaxError, Image.DecompressionBombError) as error:
        raise ValueError('无法读取这张 Gallery 图片 / This Gallery image could not be read.') from error
    stored_id = hashlib.sha256(data).hexdigest()
    repo.store_image(owner, project_id, stored_id, data, mime)
    return {'asset_id': stored_id, 'alt': asset['name'][:1000]}


def _evidence(repo, owner, project_id, guidance):
    materials = {item['id']: item for item in repo.materials(owner, project_id) if item['active']}
    articles = [{**item, 'body': item['body'] or item['summary']} for item in materials.values()]
    return [dict(evidence_id=item['evidence_id'], **{k: materials[item['id']][k] for k in
                 ('id', 'title', 'sources', 'images')}, body=item['body'], summary=item['summary'])
            for item in editorial.conversation_evidence(articles, guidance, [])]


def _attach_pack(store, owner, pack):
    materials, assets, loaded = [], {}, {}
    used = attempts = 0
    for entry in pack['entries']:
        images = []
        for image in entry['images']:
            url = image['url']
            if url not in loaded:
                if attempts >= IMAGE_LIMIT or used >= IMAGE_BUDGET:
                    loaded[url] = {'error': 'Image import limit reached'}
                else:
                    attempts += 1
                    try:
                        data, mime = source.load_image(store, owner, image)
                        if len(data) + used > IMAGE_BUDGET:
                            raise ValueError('Image import limit reached')
                        asset = hashlib.sha256(data).hexdigest()
                        if asset not in assets:
                            assets[asset] = (data, mime)
                            used += len(data)
                        loaded[url] = {'asset_id': asset, 'size': len(data)}
                    except (OSError, ValueError, WebProviderError, Image.DecompressionBombError) as error:
                        loaded[url] = {'error': html_export.image_failure(error)}
            images.append({**image, **loaded[url]})
        item = {**entry, 'images': images}
        materials.append({**item, 'id': source.digest(item)})
    return materials, assets


def _metadata(version):
    target = version['target']
    suffix, mime = ('html', 'text/html') if target == 'html' else ('txt', 'text/plain')
    return {'kind': 'document' if target == 'html' else 'text', 'target': target,
            'name': version['title'], 'version_id': version['id'],
            'mini_app_id': MINI_ID, 'media_type': mime, 'suffix': suffix}


def register(runtime):
    logging.getLogger(__name__).info('Doc Studio Phase A loaded from %s', __file__)
    repo = Repository(runtime.database)
    store = runtime.intelligence_collector.store
    from .translation import register as register_translation
    register_translation(runtime)

    def authorize(owner, payload, operation):
        require_access(execution_principal(runtime, owner))
        data = payload['input']
        project = payload['project_id']
        if operation == 'import':
            repo.pack(owner, data['pack_id'])
            if data['project_id'] is not None:
                repo.project(owner, project)
        else:
            repo.project(owner, project)
            version = data.get('base_version_id') if operation == 'generate' else data['version_id']
            if version:
                repo.version(owner, project, version)

    async def import_pack(ctx):
        body = Import.model_validate(ctx.payload['input'])
        owner, project = ctx.owner, ctx.payload['project_id']
        if not repo.imported(owner, project, body.pack_id):
            pack = repo.pack(owner, body.pack_id)
            ctx.report(message='正在保存素材和图片 / Saving materials and images', progress={'stage': 'import'})
            materials, assets = await asyncio.to_thread(_attach_pack, store, owner, pack)
            title = (body.title or pack['entries'][0]['title'][:160]) if body.project_id is None else None
            if ctx.service.get(owner, ctx.id)['status'] != 'cancelling':
                authorize(owner, ctx.payload, 'import')
                repo.import_pack(owner, project, title, body.pack_id, materials, assets, task_id=ctx.id)
        return {'project_id': project}

    async def generate(ctx):
        owner, project = ctx.owner, ctx.payload['project_id']
        body = Generate.model_validate(ctx.payload['input'])
        base = repo.version(owner, project, body.base_version_id) if body.base_version_id else None
        evidence = base['evidence'] if base else _evidence(repo, owner, project, body.guidance)
        if not evidence:
            raise ValueError('Import article materials before generating a draft')
        kind = {'x-post': 'short_post', 'x-long-post': 'long_post', 'html': 'long_article'}[body.target]
        long_post = kind == 'long_post'
        model_evidence = [{**{k: item[k] for k in ('id', 'evidence_id', 'title', 'body', 'summary')},
                           'coverage': 'preview' if any(s['coverage'] == 'preview' for s in item['sources']) else 'article'}
                          for item in evidence]
        guidance = STYLES[body.style] + ('\n' + body.guidance.strip() if body.guidance.strip() else '')
        format_constraints = {
            'short_post': (
                'Write one standard X post. Aim for at most 230 weighted characters before the source link. '
                'For Chinese, Japanese or Korean, aim for about 100 characters including punctuation. '
                'Use one or two short sentences. Keep the main event and trim secondary commentary first. '
                'No URLs, use only numbered citations.'
            ),
            'long_post': (
                f'Write one long X post in plain-text paragraphs. The exported post, including any '
                f'source link, may use up to {X_LONG_POST_LIMIT:,} characters. '
                'Choose the length needed to explain the story. Do not pad to reach the limit. '
                'Use numbered citations and leave raw URLs out of the draft.'
            ),
            'long_article': (
                'For headings use ##, for lists use - and for quotations use > at the start of a line. '
                'Put each block on a separate line. No images or raw URLs.'
            ),
        }
        ctx.report(message='正在生成稿件 / Generating draft', progress={'stage': 'generate'})
        try:
            manuscript = await writing.compose(
                runtime, None, execution_principal(runtime, owner), project,
                {'kind': kind, 'scope_label': repo.project(owner, project)['title'],
                 'guidance': guidance, 'evidence': model_evidence,
                 'current': {k: base[k] for k in ('title', 'content')} if base else None},
                guidance, constraints=SELF_CONTAINED_LEAD + format_constraints[kind],
                output_language=body.language, consumer_app_id=APP_ID,
                manuscript_model=LongPostManuscript if long_post else writing.Manuscript,
                stage='long_manuscript' if long_post else 'editorial',
                on_progress=lambda progress: ctx.report(message='正在生成稿件 / Generating draft',
                                                        progress={'stage': 'generate', **progress}),
                validate_content=(lambda value: render.x_post(value.content, evidence, long=long_post))
                if body.target != 'html' else None,
            )
        except HTTPException as error:
            cause = error.__cause__
            _report_draft_error(ctx, cause, 'generate')
            if isinstance(cause, render.XPostError):
                raise cause from None
            raise
        except render.XPostError as error:
            _report_draft_error(ctx, error, 'generate')
            raise
        # Keep the bounded, numbered evidence scope for edits and later revisions.
        version = version_data(manuscript['title'].strip(), manuscript['content'].strip(), body.model_dump(),
                               evidence, origin='generated', parent=body.base_version_id, note=manuscript['note'])
        if ctx.service.get(owner, ctx.id)['status'] != 'cancelling':
            authorize(owner, ctx.payload, 'generate')
            repo.save_version(owner, project, ctx.id, version, task_id=ctx.id)
        return {'project_id': project, 'version_id': ctx.id}

    async def rewrite_block(ctx):
        owner, project = ctx.owner, ctx.payload['project_id']
        body = RewriteBlock.model_validate(ctx.payload['input'])
        version = repo.version(owner, project, body.version_id)
        citations = set(render.CITATION.findall(body.block.text))
        valid_citations = {str(item['evidence_id']) for item in version['evidence']}
        if citations - valid_citations:
            raise ValueError('请先修正此段的引用编号 / Correct the citation numbers in this block first.')

        def validate(value):
            revised = TextBlock.model_validate({'type': body.block.type, **value})
            if revised.type != body.block.type:
                raise ValueError('Keep the same block type.')
            if set(render.CITATION.findall(revised.text)) != citations:
                raise ValueError('Preserve the original citation numbers.')
            if render.URL.search(revised.text) and not render.URL.search(body.block.text):
                raise ValueError('Do not add URLs.')
            if revised.type != 'list' and re.search(r'\n\s*\n', revised.text):
                raise ValueError('Return a single passage.')
            return {'text': revised.text}

        message = '正在改写选中的段落 / Rewriting selected passage'
        ctx.report(message=message, progress={'stage': 'rewrite_block'})
        try:
            return await editorial.model_json(
                runtime, None, execution_principal(runtime, owner), project,
                'Revise only the selected block as directed by revision_request. Return {"text": "..."} with '
                'the replacement, without a title or commentary. For a list, use one item per line without '
                'bullets. Keep the block type, citation numbers and factual attributions. Use the evidence '
                'only for facts supporting this passage.',
                {'channel': {'output_language': version['language']}, 'article_title': version['title'],
                 'selected_block': body.block.model_dump(), 'revision_request': body.instruction,
                 'evidence': [{k: item[k] for k in ('evidence_id', 'title', 'body', 'summary')}
                              for item in version['evidence'] if str(item['evidence_id']) in citations]},
                validate, consumer_app_id=APP_ID, stage='long_manuscript' if len(body.block.text) > 8000 else 'editorial',
                on_progress=lambda progress: ctx.report(message=message, progress={'stage': 'rewrite_block', **progress}),
            )
        except HTTPException as error:
            if error.status_code == 502 and isinstance(error.__cause__, (ValueError, KeyError, TypeError)):
                raise ValueError('模型未能返回保留原引用的单段改写，请调整指令后重试。 / '
                                 'The model could not revise this passage with its original citations. Try a different instruction.') from error
            raise

    def build_output(owner, project, version):
        if version['target'] != 'html':
            return render.x_post(version['content'], version['evidence'],
                                 long=version['target'] == 'x-long-post').encode()
        ids = {image['asset_id'] for block in version['blocks'] for image in render.block_images(block)}
        images = {asset: repo.image(owner, project, asset) for asset in ids}
        return render.html_document(version, images)

    async def export(ctx):
        owner, project = ctx.owner, ctx.payload['project_id']
        body = Export.model_validate(ctx.payload['input'])
        version = repo.version(owner, project, body.version_id)
        ctx.report(message='正在渲染产物 / Rendering output', progress={'stage': 'render'})
        try:
            data = await asyncio.to_thread(build_output, owner, project, version)
        except render.XPostError as error:
            _report_draft_error(ctx, error, 'render')
            raise
        if ctx.service.get(owner, ctx.id)['status'] != 'cancelling':
            authorize(owner, ctx.payload, 'export')
            repo.save_output(owner, project, ctx.id, _metadata(version), data)
        return {'project_id': project, 'output_id': ctx.id}

    for operation, execute in (('import', import_pack), ('generate', generate), ('export', export),
                               ('rewrite_block', rewrite_block)):
        runtime.system_tasks.register('doc_studio.' + operation, TaskHandler(
            APP_ID, execute, authorize=lambda owner, payload, op=operation: authorize(owner, payload, op),
        ))
