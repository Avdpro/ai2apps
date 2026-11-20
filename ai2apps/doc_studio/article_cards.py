"""Article Cards export using the installed Package's reviewed canvas renderer."""
import asyncio
import hashlib
import json
import tempfile
from pathlib import Path

from ai2apps.services import ToolProviderError
from ai2apps.services.aaat import principal_for
from ai2apps.studio.package_generation_aaat import owner, receipt, reserve
from ai2apps.studio.repository import StudioRepository
from ai2apps.studio.visual_sequence import CAPABILITY, MAX_BYTES, render_visual_sequence

RENDERER_SHA256 = '395f5dbdcf9b8512455437c888d513a0abd6b1adf345562c54501c13537666a8'


async def frames(runtime, principal, script, args):
    from ai2apps.browser.background_bidi import BackgroundBiDi
    from ai2apps.browser.background_page import BackgroundPage
    from ai2apps.helper_control import HelperControlClient

    helper = HelperControlClient.from_environment()
    if helper is None:
        raise ToolProviderError('Open AI2Apps Desktop to make the renderer available')
    await asyncio.to_thread(helper.ensure_browser_host, actor_user_id=principal.actor_user_id)
    connection = BackgroundBiDi()
    user_context = None
    try:
        await connection.connect()
        user_context = (await connection.command('browser.createUserContext', {}, timeout=10))['userContext']
        tab = await connection.command('browsingContext.create',
            {'type':'window', 'userContext':user_context, 'background':True}, timeout=10)
        page = BackgroundPage(connection, tab['context'])
        return await page.call_json('''(args) => {
            ''' + script + '''
            const canvas = document.createElement('canvas');
            [canvas.width, canvas.height] = args.ratio === '9:16' ? [720, 1280] : [960, 1280];
            const cards = window.ArticleCards;
            const template = cards.defaults(args.theme || 'paper');
            const pages = cards.paginate(canvas.getContext('2d'), args.article, template, canvas.width, canvas.height);
            if (!pages.length) throw Error('Article is empty');
            const output = [];
            let bytes = 0;
            for (let index = 0; index < (args.format === 'png' ? 1 : pages.length); index++) {
                if (cards.render(canvas, template, null, pages[index], index, pages.length))
                    throw Error('Text exceeds its page');
                const image = canvas.toDataURL('image/png').split(',')[1];
                bytes += image.length;
                if (bytes > 8000000) throw Error('Export exceeds the image bundle limit');
                output.push(image);
            }
            return output;
        }''', (args,), timeout=45)
    finally:
        try:
            if user_context:
                await connection.command('browser.removeUserContext', {'userContext':user_context}, timeout=10)
        finally:
            await connection.close()


async def export(runtime, args, context, mini, spec):
    article = args.get('article')
    if not isinstance(article, str) or not article.strip() or len(article) > 30000:
        raise ToolProviderError('Supply article text')
    if (args.keys() - {'article', 'ratio', 'theme', 'format'}
            or args.get('ratio', '3:4') not in ('3:4', '9:16')
            or args.get('theme', 'paper') not in ('paper', 'sage', 'ink')
            or args.get('format', 'zip') not in ('png', 'zip')):
        raise ToolProviderError('Unsupported Article Cards export settings')
    principal = principal_for(runtime, context)
    studio, mini_id = spec['host'], mini['id']
    host, mounted, broker = owner(runtime, principal, studio, mini_id)
    if CAPABILITY not in mounted.capabilities or not runtime.studio_jobs:
        raise ToolProviderError('Studio output is unavailable')
    if (previous := reserve(runtime, context, args, check_only=True)):
        return previous
    instance = mounted.mount['app_instance_id']
    resource = runtime.extension_manager.resolve_app_resource(instance, 'web/layout.js', principal=principal)
    script = resource.read_bytes()
    if hashlib.sha256(script).hexdigest() != RENDERER_SHA256:
        raise ToolProviderError('Article Cards renderer requires a matching Desktop SDK version')
    await context.report_progress('Rendering article cards')
    images = await frames(runtime, principal, script.decode(), args)
    mode = args.get('format', 'zip')
    data = json.dumps({'format':mode, 'seconds':1, 'frames':images}).encode()
    if len(data) > MAX_BYTES:
        raise ToolProviderError('Image bundle exceeds the export size limit')
    scope = {'actor_id':principal.actor_user_id, 'installation_id':principal.installation_id,
             'app_instance_id':host.id, 'studio_id':studio}
    repo = StudioRepository(runtime.database)
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        metadata = await asyncio.to_thread(render_visual_sequence, data, directory / 'output')
        broker.mounted_mini_app(studio, 'aaat', principal=principal)
        if (previous := reserve(runtime, context, args)):
            return previous
        run = repo.create_run(**scope, mini_app_id=mini_id, mini_app_version=mini['version'],
                              placement='inline', title='Article Cards', input_data={'format':mode},
                              step_label='Export article cards')
        repo.update_run(run['id'], status='running', progress=90, **scope)
        metadata['filename'] = f'article-cards-{run["id"][-8:]}.{mode}'
        (directory / 'result.json').write_text(json.dumps(metadata))
        job = {**scope, 'id':run['id'], 'run_id':run['id'], 'kind':'visual-sequence', 'mini_app_id':mini_id}
        publication = asyncio.create_task(asyncio.to_thread(runtime.studio_jobs.publish, job, directory))
        cancelled = False
        try:
            try:
                result = await asyncio.shield(publication)
            except asyncio.CancelledError:
                cancelled = True
                result = await publication
        except Exception:
            repo.update_run(run['id'], status='failed', progress=90, detail='Could not save output', **scope)
            raise
        response = {'status':'completed', 'shared_output':True, 'studio_run_id':run['id'],
                    'artifact':{'download_url':result['downloadUrl'], 'filename':metadata['filename'],
                                'media_type':metadata['media_type']}}
        receipt(runtime, context, response)
        if cancelled:
            raise asyncio.CancelledError
        return response
