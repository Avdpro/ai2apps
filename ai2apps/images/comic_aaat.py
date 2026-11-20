"""Comic Translation's Package-owned Agent workflow."""
import asyncio
import base64
import hashlib
import json
import logging
import unicodedata
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from ai2apps.agents.artifact_outputs import artifact_reference
from ai2apps.images import comic_translation as comic
from ai2apps.model_invocation import ModelInvocationContext
from ai2apps.services import ToolProviderError
from ai2apps.services.aaat import principal_for
from ai2apps.studio.comic_output import MAX_OUTPUT, publish_comic, stage_page
from ai2apps.studio.package_generation_aaat import image_source, owner, receipt, reserve
from ai2apps.studio.repository import StudioRepository

MEDIA = {'image/png', 'image/jpeg', 'image/webp'}
RENDERERS = {
    'web/layout.js': {
        'ff3dbb08e5b4cb3e473adb66074aa3666c668a08d6682fe96fb30b457d4b30d5',
        'c4d7d87b78702426a7c5a0146f153e6c07ceee7278a73e87ccbf4024f1f67052',
    },
    'web/reader.js': {'ac0ae2b0f8b1611ecd9ff3206563f90a08a9a52787ba57cc1557b0ec3fbbd243'},
}
CHUNK_SIZE = 512 * 1024
log = logging.getLogger(__name__)


def available_model(catalog):
    return catalog['default'] or next((item['id'] for item in catalog['items'] if item['local']), None)


async def describe(runtime, principal, model, mini, spec):
    from copy import deepcopy
    from ai2apps.agents.parameter_forms import schema_fields
    catalog = await comic.models(runtime)
    ocr_missing = not comic.ocr_ready(runtime)
    default = available_model(catalog)
    schema = deepcopy(spec['inputSchema'])
    if default:
        schema['properties']['model_id']['default'] = default
    elif catalog['items']:
        schema['required'] = list(dict.fromkeys([*schema.get('required', []), 'model_id']))
    fields = schema_fields(schema)
    for field in fields:
        if field['key'] == 'model_id':
            field['type'] = 'model'
        if field['key'] == 'language':
            field['options'] = [{'value':value,'label':comic.LANGUAGES[value]}
                                for value in schema['properties']['language']['enum']]
    warnings = []
    if ocr_missing:
        warnings.append({'zh':'漫画识别所需的本地 SoMark OXR 模型尚未就绪。图片和翻译参数已保留，请先完成模型配置。',
                         'en':'The local SoMark OXR model required for comic recognition is not ready. Images and translation parameters are preserved; complete model setup first.'})
    if not catalog['items']:
        warnings.append({'zh':'没有可用的翻译模型。请在创意画坊配置翻译模型，然后重新检查。',
                         'en':'Configure a translation model in Imagine Studio, then recheck.'})
    return {
        'effective_schema': schema, 'fields': fields, 'model_field': 'model_id',
        'models': [{**item,'label':item.get('label') or item['id'],'ready':True} for item in catalog['items']],
        'configuration_required': ocr_missing or not catalog['items'],
        'inline_setup': ocr_missing,
        'auto_continue_after_setup': True,
        'install': {'appId': comic.STUDIO_ID, 'capability': comic.CAPABILITY, 'requirements': {}},
        'warnings': warnings,
    }


def glossary_for(runtime, binding, name, language):
    if not name:
        return []
    draft = StudioRepository(runtime.database).get_draft(**binding, mini_app_id=comic.MINI_ID)
    profiles = (draft or {}).get('draft', {}).get('profiles', [])
    def key(value):
        return unicodedata.normalize('NFC', value).strip().casefold()

    matches = [profile for profile in profiles if isinstance(profile, dict) and
               profile.get('language') == language and isinstance(profile.get('name'), str) and
               key(profile['name']) == key(name)] if isinstance(profiles, list) else []
    if len(matches) != 1:
        raise ToolProviderError('The named translation profile is missing or ambiguous for the target language')
    terms = matches[0].get('terms')
    if not isinstance(terms, list) or len(terms) > 500 or any(
        not isinstance(term, dict) or any(not isinstance(term.get(k), str) or not 1 <= len(term[k]) <= limit
                                         for k, limit in [('source', 100), ('translation', 150)])
        or term.get('kind') not in {'person', 'place', 'item', 'other'} for term in terms
    ):
        raise ToolProviderError('The translation profile contains invalid terms')
    return [{key: term[key] for key in ('source', 'translation', 'kind')} for term in terms]


def renderer_source(runtime, principal, instance, format):
    scripts = []
    for resource, digests in RENDERERS.items():
        if resource.endswith('/reader.js') and format != 'html':
            continue
        script = runtime.extension_manager.resolve_app_resource(instance, resource, principal=principal).read_bytes()
        if hashlib.sha256(script).hexdigest() not in digests:
            raise ToolProviderError('Comic Translation requires a matching Desktop renderer')
        scripts.append(script.decode())
    return '\n'.join(scripts)


@asynccontextmanager
async def rendering_page(principal, script):
    from ai2apps.browser.background_bidi import BackgroundBiDi
    from ai2apps.browser.background_page import BackgroundPage
    from ai2apps.helper_control import HelperControlClient

    helper = HelperControlClient.from_environment()
    if helper is None:
        raise ToolProviderError('Open AI2Apps Desktop to make the comic renderer available')
    await asyncio.to_thread(helper.ensure_browser_host, actor_user_id=principal.actor_user_id)
    connection = BackgroundBiDi()
    user_context = None
    try:
        await connection.connect()
        user_context = (await connection.command('browser.createUserContext', {}, timeout=10))['userContext']
        tab = await connection.command('browsingContext.create',
            {'type': 'window', 'userContext': user_context, 'background': True}, timeout=10)
        page = BackgroundPage(connection, tab['context'])
        await page.call_json('() => {\n' + script + '\nwindow.readerPages = []; return true; }')
        yield page
    finally:
        try:
            if user_context:
                try:
                    await connection.command('browser.removeUserContext', {'userContext': user_context}, timeout=10)
                except Exception:
                    log.warning('Could not confirm cleanup of the comic renderer')
        finally:
            await connection.close()


async def load_surface(page, content, media):
    # Bound each BiDi message independently of the input image size.
    encoded = base64.b64encode(content).decode()
    await page.call_json('() => { window.comicChunks = []; return true; }')
    for offset in range(0, len(encoded), CHUNK_SIZE):
        await page.call_json('part => window.comicChunks.push(part)', (encoded[offset:offset + CHUNK_SIZE],))
    return await page.call_json('''async media => {
        if (window.comicSurface) window.comicSurface.width = window.comicSurface.height = 0;
        const bytes = Uint8Array.from(atob(window.comicChunks.join('')), value => value.charCodeAt(0));
        window.comicChunks = null;
        window.comicFile = new Blob([bytes], {type: media});
        const surface = window.comicSurface = await window.ComicLayout.decode(window.comicFile);
        return {width: surface.width, height: surface.height};
    }''', (media,))


async def read_rendered(page, size, limit):
    if not isinstance(size, int) or not 0 < size <= 4 * ((limit + 2) // 3):
        raise ToolProviderError('Comic output exceeds its size limit')
    data = bytearray()
    for start in range(0, size, CHUNK_SIZE):
        part = await page.call_json('(start, end) => window.comicResult.slice(start, end)', (start, start + CHUNK_SIZE))
        data.extend(base64.b64decode(part, validate=True))
    if len(data) > limit:
        raise ToolProviderError('Comic output exceeds its size limit')
    return bytes(data)


async def identify(runtime, model_context, renderer, material, args):
    path, _, media = material
    data = path.read_bytes()
    analysis = await asyncio.to_thread(lambda: comic.analyze(comic.load_image(data)))
    dimensions = await load_surface(renderer, data, media)
    crop = analysis['crop'] if args.get('auto_crop', True) else None
    info = {**dimensions, 'crop': crop, 'bubbleLinks': analysis['region_links'], 'regions': []}
    direction = args.get('direction', 'auto')
    for index, box in enumerate(analysis['regions']):
        if crop and not (box[0] >= crop[0] and box[1] >= crop[1] and box[2] <= crop[2] and box[3] <= crop[3]):
            continue
        parts = analysis['region_parts'].get(str(index))
        size = await renderer.call_json('''(box, parts) => {
            const L = window.ComicLayout;
            const patch = L.crop(window.comicSurface, box, 1400, parts);
            window.comicResult = patch.toDataURL('image/png').split(',')[1];
            return window.comicResult.length;
        }''', (box, parts))
        patch = await read_rendered(renderer, size, comic.MAX_IMAGE)
        h, w = (box[3] - box[1]) * dimensions['height'], (box[2] - box[0]) * dimensions['width']
        vertical = direction == 'vertical' or (direction == 'auto' and h >= w * 1.2)
        text = (await comic.recognize(runtime, model_context, comic.load_image(patch), vertical=vertical)).strip()
        if text and text not in {'.', '。', '．'}:
            info['regions'].append({'id': index, 'box': box, 'parts': parts, 'source': text, 'enabled': True})
    return await renderer.call_json(r'''(info, direction) => {
        const L = window.ComicLayout;
        const vertical = direction === 'vertical' || direction === 'auto' &&
            info.regions.some(row => /\p{Script=Han}|\p{Script=Hiragana}/u.test(row.source));
        const regions = L.orderDialogue(info.regions, vertical);
        return {...info, regions, vertical, candidates: L.bubbleCandidates(info, regions)};
    }''', (info, direction))


async def translate_page(runtime, model_context, model, info, args, before, after, glossary):
    rows = info['regions']
    info['bubbleGroups'] = []
    if not rows:
        return
    sources = [row['source'] for row in rows]
    if sum(map(len, [*sources, *before, *after])) > 20_000:
        raise ToolProviderError('Dialogue on this page exceeds the supported context size')
    candidates = info.pop('candidates')
    translated = await comic.translate(runtime, model_context, sources, args.get('language', 'en'),
        model=model, before=before, after=after, targets=list(range(len(rows))), glossary=glossary,
        nearby_pairs=[a for a, b, _ in candidates if b == a + 1], bubble_candidates=candidates,
        bubble_boxes=[row['box'] for row in rows], vertical=info.pop('vertical'))
    for row, text in zip(rows, translated['translations']):
        row['translated'] = text
    info['bubbleGroups'] = [[rows[i]['id'] for i in group] for group in translated.get('bubble_groups', [])]
    known = {term['source'].lower() for term in glossary}
    for term in translated['new_terms']:
        if term['source'].lower() not in known and len(glossary) < 500:
            glossary.append(term)
            known.add(term['source'].lower())


async def render_batch(runtime, principal, model_context, model, context, args, materials, glossary, script, directory):
    format = args.get('format', 'png')
    warnings, staged = [], []
    remaining = MAX_OUTPUT
    async with rendering_page(principal, script) as page:
        prepared = []
        for index, material in enumerate(materials, 1):
            await context.report_progress(f'Reading comic page {index}/{len(materials)}')
            prepared.append(await identify(runtime, model_context, page, material, args))
        if not any(info['regions'] for info in prepared):
            raise ToolProviderError('No readable dialogue was detected on the supplied pages')
        sources = [[row['source'][:400] for row in info['regions']] for info in prepared]
        context_enabled = args.get('page_context', True)
        for index, (info, material) in enumerate(zip(prepared, materials)):
            await context.report_progress(f'Translating comic page {index + 1}/{len(materials)}')
            before = sources[index - 1][-8:] if context_enabled and index else []
            after = sources[index + 1][:8] if context_enabled and index + 1 < len(sources) else []
            await translate_page(runtime, model_context, model, info, args, before, after, glossary)
            path, _, media = material
            await load_surface(page, path.read_bytes(), media)
            result = await page.call_json('''async (info, language, format) => {
                const rendered = await window.ComicLayout.render({...info, file: window.comicFile}, language);
                const {output, original, boxes, issues} = rendered;
                if (format === 'html') {
                    const page = {width: output.width, height: output.height, boxes,
                        original: original.toDataURL(), output: output.toDataURL()};
                    window.readerPages.push(page);
                    window.readerBytes = (window.readerBytes || 0) + page.original.length + page.output.length;
                } else window.comicResult = output.toDataURL().split(',')[1];
                original.width = output.width = 0;
                return {issues, size: window.comicResult?.length, readerBytes: window.readerBytes || 0};
            }''', (info, args.get('language', 'en'), format), timeout=120)
            if not info['regions']:
                warnings.append({'page': index + 1, 'reason': 'no_dialogue'})
            if result['issues']:
                warnings.append({'page': index + 1, 'regions': [
                    {'region': issue['index'] + 1, 'reason': issue['reason']} for issue in result['issues']]})
            if format == 'png':
                output = await read_rendered(page, result['size'], remaining)
                remaining -= len(output)
                staged.append(await asyncio.to_thread(stage_page, directory, index + 1, output, format))
            elif result['readerBytes'] > MAX_OUTPUT - 1024 * 1024:
                raise ToolProviderError('Offline comic reader exceeds 64 MiB')
        if format == 'html':
            size = await page.call_json('''locale => {
                const body = window.ComicReader.readerHtml(window.readerPages, locale);
                const bytes = new TextEncoder().encode(body);
                let binary = '';
                for (let start = 0; start < bytes.length; start += 16384) {
                    binary += String.fromCharCode(...bytes.subarray(start, start + 16384));
                }
                window.comicResult = btoa(binary);
                return window.comicResult.length;
            }''', (args.get('language', 'en'),), timeout=120)
            output = await read_rendered(page, size, MAX_OUTPUT)
            staged.append(await asyncio.to_thread(stage_page, directory, 1, output, format))
    return staged, warnings


def publish(runtime, context, mini, binding, staged, format, warnings):
    run_id, outputs = publish_comic(runtime, mini, binding, staged, format)
    files = []
    for path, result in zip(staged, outputs):
        metadata = json.loads((path / 'result.json').read_text())
        reference = artifact_reference(result['downloadUrl'])
        if reference is None:
            raise ToolProviderError('Studio export returned an invalid artifact reference')
        source_session, source_id = reference
        if source_session == context.session_id:
            artifact_id = source_id
        else:
            artifact = runtime.workspace.import_artifact(context.session_id, path / 'output',
                name=metadata['filename'], media_type=metadata['media_type'],
                metadata={'studioRunId': run_id, 'studioArtifactId': source_id})
            artifact_id = artifact.id
        files.append({'url': f'/v1/platform/sessions/{context.session_id}/artifacts/{artifact_id}/download',
                      'artifact_id': artifact_id, 'filename': metadata['filename'], 'media_type': metadata['media_type']})
    result = {'status': 'completed', 'studio_run_id': run_id, 'shared_output': True, 'files': files, 'warnings': warnings}
    receipt(runtime, context, result)
    return result


async def execute(runtime, args, context, mini, spec):
    if mini['id'] != comic.MINI_ID or spec['host'] != comic.STUDIO_ID:
        raise ToolProviderError('Invalid Comic Translation binding')
    principal = principal_for(runtime, context)
    host, mounted, broker = owner(runtime, principal, comic.STUDIO_ID, comic.MINI_ID)
    if comic.CAPABILITY not in mounted.capabilities or runtime.studio_jobs is None:
        raise ToolProviderError('Comic Translation is unavailable')
    if previous := reserve(runtime, context, args, check_only=True):
        return previous
    catalog = await comic.models(runtime)
    model = args.get('model_id') or available_model(catalog)
    if not comic.ocr_ready(runtime) or model not in {row['id'] for row in catalog['items']}:
        raise ToolProviderError('Configure SoMark OXR and an available translation model in Imagine Studio')
    format = args.get('format', 'png')
    kind = 'image' if format == 'png' else 'file'
    if not any(output.get('kind') == kind and output.get('final', True) for output in mini.get('outputs', ())):
        raise ToolProviderError('The installed Comic Translation Package does not declare this output format')
    binding = {'actor_id': principal.actor_user_id, 'installation_id': principal.installation_id,
               'app_instance_id': host.id, 'studio_id': comic.STUDIO_ID}
    materials = [image_source(runtime, principal, context.session_id, identifier) for identifier in args['image_ids']]
    if any(media not in MEDIA for _, _, media in materials):
        raise ToolProviderError('Choose PNG, JPEG or WebP comic pages')
    glossary = glossary_for(runtime, binding, args.get('profile'), args.get('language', 'en'))
    script = renderer_source(runtime, principal, mounted.mount['app_instance_id'], format)
    model_context = ModelInvocationContext.from_principal(principal, session_id=context.session_id,
        app_instance_id=host.id, consumer_app_id=comic.STUDIO_ID)
    with TemporaryDirectory(prefix='comic-aaat-') as temporary:
        directory = Path(temporary)
        inputs = directory / 'inputs'
        inputs.mkdir()
        snapshots = []
        for index, (path, name, media) in enumerate(materials):
            with path.open('rb') as source:
                content = source.read(comic.MAX_IMAGE + 1)
            if not content or len(content) > comic.MAX_IMAGE:
                raise ToolProviderError('Each source image must be between 1 byte and 16 MiB')
            snapshot = inputs / str(index)
            snapshot.write_bytes(content)
            snapshots.append((snapshot, name, media))
        # Admit once before model work. Unknown outcomes must be inspected without replay.
        if previous := reserve(runtime, context, args):
            return previous
        staged, warnings = await render_batch(runtime, principal, model_context, model, context,
            args, snapshots, glossary, script, directory)
        broker.mounted_mini_app(comic.STUDIO_ID, 'aaat', principal=principal)
        publication = asyncio.create_task(asyncio.to_thread(
            publish, runtime, context, mini, binding, staged, format, warnings))
        try:
            return await asyncio.shield(publication)
        except asyncio.CancelledError:
            await publication
            raise
