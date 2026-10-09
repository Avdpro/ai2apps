"""Owner-only Studio ASGI app. No forwarding to the general/admin server.

The checked-in route inventory is deliberate: adding a desktop endpoint does not
silently export it remotely. Existing resource/actor/mount guards are retained.
"""
from importlib import import_module
import json
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, File, Form, UploadFile
from starlette.routing import compile_path
from ai2apps.web import owner_home_gateway as owner

STUDIO_APPS = frozenset({'ai2apps.imagine-studio', 'ai2apps.video-studio', 'ai2apps.readaloud'})
ROUTES = json.loads(Path(__file__).with_name('owner_studio_routes.json').read_text())
EXTRA = [
    ('GET', '/v1/models'), ('POST', '/v1/chat/completions'),
    ('POST', '/v1/images/generations'), ('POST', '/v1/images/edits'),
    ('GET', '/v1/videos/generations'), ('POST', '/v1/videos/generations'),
    ('GET', '/v1/videos/generations/{task_id}'), ('DELETE', '/v1/videos/generations/{task_id}'),
    ('POST', '/v1/videos/joins'), ('POST', '/v1/audio/transcriptions'),
]
MATCHERS = [(r['method'], compile_path(r['path'])[0]) for r in ROUTES]
MATCHERS += [(method, compile_path(path)[0]) for method, path in EXTRA]


def allowed(method, path):
    if '/studios/' in path and path.split('/studios/', 1)[1].split('/', 1)[0] not in STUDIO_APPS:
        return False
    return any(method == verb and pattern.fullmatch(path) for verb, pattern in MATCHERS)


async def principal(request: Request):
    if not allowed(request.method, request.url.path):
        raise HTTPException(403, "Studio route denied")
    grant = owner.authority(request)
    if grant is None:
        raise HTTPException(401, 'Owner Studio authorization required')
    actor = grant[0].principal(grant[1])
    if not actor.is_core or actor.authentication_type != 'owner_home_lease':
        raise HTTPException(403, 'Owner Studio authorization required')
    if request.method in {'POST', 'PUT', 'PATCH'} and 'application/json' in request.headers.get('content-type', ''):
        payload = await request.json()
        if request.url.path == '/v1/platform/capabilities/probe' and (not isinstance(payload, dict) or payload.get('appId') not in STUDIO_APPS):
            raise HTTPException(403, 'Only Studio capability probes are available')
        def native_path(value):
            if isinstance(value, dict):
                return any((key.replace('_', '').lower() in {'sourcepath', 'targetpath', 'outputroot', 'localpath'} and bool(item))
                           or native_path(item) for key, item in value.items())
            return isinstance(value, list) and any(native_path(item) for item in value)
        if native_path(payload) or (request.url.path.endswith('/batch-output/chunks')
                and isinstance(payload, dict) and isinstance(payload.get('target'), dict)
                and payload['target'].get('kind') == 'local'):
            raise HTTPException(403, 'Mobile Studio requires uploaded files or owned Gallery handles')
    from ai2apps.remote.mobile_apps import app_enabled
    runtime = request.app.state.runtime_provider()
    path = request.url.path
    module_apps = {'imagine_studio': 'ai2apps.imagine-studio',
                   'video_studio': 'ai2apps.video-studio', 'readaloud': 'ai2apps.readaloud'}
    required = None
    for route in ROUTES:
        if route['method'] == request.method and compile_path(route['path'])[0].fullmatch(path):
            required = module_apps.get(route['module'])
            break
    if '/studios/' in path:
        required = path.split('/studios/', 1)[1].split('/', 1)[0]
    if required and not app_enabled(runtime, actor, required):
        raise HTTPException(403, 'This Studio is disabled for Mobile')
    if not required and not any(app_enabled(runtime, actor, key) for key in STUDIO_APPS | {'ai2apps.gallery'}):
        raise HTTPException(403, 'Mobile media access is disabled')
    request.state.ai2apps_principal = actor
    return actor


def create_app(runtime_provider):
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None,
                  dependencies=[Depends(principal)])
    app.state.runtime_provider = runtime_provider
    @app.middleware('http')
    async def private_responses(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        media_type = response.headers.get('content-type', '').split(';', 1)[0]
        if media_type in {'text/html', 'application/xhtml+xml', 'image/svg+xml'}:
            response.headers['Content-Security-Policy'] = "default-src 'none'; sandbox; frame-ancestors 'none'"
            response.headers['Content-Disposition'] = 'attachment'
        return response

    factories = {'studio_mini_apps': 'create_studio_mini_app_router'}
    for module in sorted({row['module'] for row in ROUTES} - {'cloud'}):
        factory = getattr(import_module('ai2apps.api.' + module),
                          factories.get(module, 'create_' + module + '_router'))
        router = factory(runtime_provider, principal_provider=principal)
        approved = {(r['method'], r['path']) for r in ROUTES if r['module'] == module}
        router.routes[:] = [r for r in router.routes if any(
            (verb, '/v1/platform' + r.path) in approved for verb in r.methods)]
        app.include_router(router, prefix='/v1/platform')

    @app.get('/v1/platform/cloud/ai/defaults')
    async def cloud_defaults(actor=Depends(principal)):
        store = getattr(runtime_provider(), 'model_manager', None)
        return {'policy': store.cloud_default_policy() if store else {}}

    @app.get('/v1/platform/cloud/ai/models')
    async def cloud_models(actor=Depends(principal)):
        from starlette.responses import Response
        runtime = runtime_provider()
        cloud = getattr(runtime, 'cloud', None)
        if cloud is None:
            raise HTTPException(503, 'Cloud model catalog unavailable')
        resolver = getattr(runtime, "cloud_ai_authorization_headers", None)
        if resolver is None:
            raise HTTPException(503, "Cloud device authorization unavailable")
        headers = resolver(actor)
        response = await cloud.request('GET', '/v1/ai/models', headers=headers)
        try:
            return Response(response.content, status_code=response.status_code,
                            media_type='application/json', headers={'Cache-Control': 'no-store'})
        finally:
            await response.aclose()

    @app.get('/v1/models')
    async def models(request: Request):
        return await owner.models(request)

    @app.post('/v1/chat/completions')
    async def completion(request: Request, payload: dict):
        return await owner.completion(request, payload)

    async def image(payload, actor, edit):
        from ai2apps.model_providers import resolve_package_model
        from ai2apps.model_invocation import ModelInvocationContext
        runtime = runtime_provider()
        model = resolve_package_model(runtime, str(payload.get('model') or ''))
        if model is None or model.model_type != 'image_generation':
            raise HTTPException(400, 'Use a local image model or the Studio run API')
        return await runtime.model_invocations.invoke_foreground_json(
            model.id, 'image_edit' if edit else 'image_generation', payload,
            context=ModelInvocationContext.from_principal(actor, session_id='mobile-image:' + secrets.token_hex(16), consumer_app_id='ai2apps.imagine-studio'))

    @app.post('/v1/images/generations')
    async def generate_image(payload: dict, actor=Depends(principal)):
        return await image(payload, actor, False)

    @app.post('/v1/images/edits')
    async def edit_image(payload: dict, actor=Depends(principal)):
        return await image(payload, actor, True)

    @app.post('/v1/audio/transcriptions')
    async def transcribe(file: UploadFile = File(...), model: str = Form(...),
                         language: str | None = Form(None), prompt: str | None = Form(None),
                         actor=Depends(principal)):
        import asyncio
        from ai2apps.audio_codecs import AudioCodecError, decode_audio_to_wav, infer_audio_format
        from ai2apps.model_providers import resolve_package_model
        from ai2apps.model_invocation import ModelInvocationContext
        runtime = runtime_provider()
        selected = resolve_package_model(runtime, model)
        if selected is None or selected.model_type != 'audio_stt':
            raise HTTPException(400, 'Select an installed speech-to-text Model Package')
        content = await file.read(100*1024*1024+1)
        await file.close()
        if len(content) > 100*1024*1024:
            raise HTTPException(413, 'Audio input is too large')
        try:
            wav = await asyncio.to_thread(decode_audio_to_wav, content,
                input_format=infer_audio_format(file.filename, file.content_type),
                sample_rate=16000, max_duration_seconds=7200)
        except AudioCodecError as error:
            raise HTTPException(415, str(error)) from error
        return await runtime.model_invocations.invoke_foreground_multipart(
            selected.id, 'audio_transcription',
            data={'language': language, 'prompt': prompt, 'response_format': 'json', 'stream': 'false'},
            files={'file': ('audio.wav', wav, 'audio/wav')},
            context=ModelInvocationContext.from_principal(actor,
                session_id='mobile-asr:' + secrets.token_hex(16), consumer_app_id='ai2apps.readaloud'))

    def videos():
        from ai2apps.video import VideoGenerationError
        value = getattr(runtime_provider(), 'video_tasks', None)
        if value is None:
            raise HTTPException(503, 'Video service unavailable')
        return value

    @app.get('/v1/videos/generations')
    async def list_videos(limit: int = 20, after: str | None = None, actor=Depends(principal)):
        return videos().list(actor_id=actor.actor_user_id, limit=limit, after=after)

    @app.get('/v1/videos/generations/{task_id}')
    async def get_video(task_id: str, actor=Depends(principal)):
        return videos().get(task_id, actor_id=actor.actor_user_id)

    @app.delete('/v1/videos/generations/{task_id}')
    async def cancel_video(task_id: str, actor=Depends(principal)):
        return await videos().cancel(task_id, actor_id=actor.actor_user_id)

    @app.post('/v1/videos/generations', status_code=202)
    async def create_video(request: Request, actor=Depends(principal)):
        from starlette.datastructures import UploadFile
        uploads = {}
        payload = None
        if request.headers.get('content-type', '').startswith('multipart/form-data'):
            async with request.form(max_files=16, max_fields=32, max_part_size=100*1024*1024) as form:
                for name, value in form.multi_items():
                    if isinstance(value, UploadFile):
                        data = await value.read(100*1024*1024+1)
                        if len(data) > 100*1024*1024:
                            raise HTTPException(413, 'Video input is too large')
                        if name == 'request':
                            payload = json.loads(data)
                        else:
                            uploads[name] = (Path(value.filename or 'input.bin').name, data, value.content_type)
                    elif name == 'request':
                        payload = json.loads(str(value))
        else:
            payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(422, 'Video request must be an object')
        return await videos().create(payload, actor_id=actor.actor_user_id,
            invocation_actor_id=actor.actor_user_id, uploads=uploads,
            idempotency_key=request.headers.get('idempotency-key'))

    @app.post('/v1/videos/joins')
    async def join_videos(payload: dict, actor=Depends(principal)):
        return await videos().join(payload.get('task_ids'), actor_id=actor.actor_user_id)

    from ai2apps.video import VideoGenerationError
    from starlette.responses import JSONResponse
    @app.exception_handler(VideoGenerationError)
    async def video_error(request, error):
        return JSONResponse({'error': {'code': error.code, 'message': str(error)}}, status_code=error.status_code)
    return app


_cached_runtime = None
_cached_app = None

def application():
    global _cached_runtime, _cached_app
    runtime = owner._runtime() if owner._runtime else None
    if runtime is not _cached_runtime or _cached_app is None:
        _cached_runtime = runtime
        _cached_app = create_app(lambda: runtime)
    return _cached_app
