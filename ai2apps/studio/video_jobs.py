"""Durable Video Studio media work; all paths are frozen by authorized submitters."""
from __future__ import annotations
import asyncio
import json
import shutil
from pathlib import Path
from ai2apps.studio.repository import StudioRepository

STUDIO_ID = 'ai2apps.video-studio'


def submit_media(runtime, principal, scope, run, *, operation, payload, sources, key=None):
    jobs = runtime.studio_jobs
    from .source_reference import describe
    # Preserve authorized source paths and identities; do not duplicate large
    # inputs into the job directory merely to outlive a browser page.
    root = jobs.root / ('video-input-' + run['id'])
    root.mkdir(exist_ok=True, mode=0o700)
    frozen = {}
    try:
        for source_key, (record, source) in sources.items():
            frozen[source_key] = {'record': record, 'reference':describe(source)}
        return jobs.submit(principal=principal, app_instance_id=scope['app_instance_id'],
            studio_id=STUDIO_ID, mini_app_id=run['miniAppId'], kind='video-media',
            key=key or 'video-' + run['id'], run_id=run['id'],
            payload={'operation': operation, **payload, 'sources': frozen})
    except BaseException:
        if jobs.for_run(run['id'], principal) is None:
            shutil.rmtree(root, ignore_errors=True)
        raise


async def render_media(manager, job, principal, payload):
    from ai2apps.video.composer import ComposerProject, render_composition, render_clip_output
    from ai2apps.video.audio_extraction import extract_audio_to_wav
    repository = StudioRepository(manager.database)
    scope = manager.scope(job)
    directory = manager.root / job['id']
    destination = directory / payload['filename']
    from .source_reference import resolve
    sources = {key: (item['record'], resolve(item['reference']) if 'reference' in item else Path(item['path'])) for key, item in payload['sources'].items()}
    operation = payload['operation']
    repository.update_run(job['run_id'], **scope, status='running', progress=5, detail='Preparing media')
    import threading
    stopped = threading.Event()
    async def finish_worker(work):
        task = asyncio.create_task(work)
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            stopped.set()
            try: await task
            except Exception: pass
            raise
    def progress(done, total):
        if stopped.is_set(): raise InterruptedError('Media task cancelled')
        repository.update_run(job['run_id'], **scope, status='running',
            progress=min(95, 10 + round(85 * done / total)) if total else 10,
            detail=f'composer.{"clip_output" if operation == "clip" else "rendering"}:{done:.3f}:{total:.3f}')
    metadata = {'filename': payload['filename'], 'media_type': payload['media_type'], 'kind': payload['kind'], **{k:v for k,v in payload.get('metadata', {}).items() if v is not None}}
    if operation == 'extract':
        # Shield the thread so cancelling a job cannot remove its files under ffmpeg.
        work = asyncio.create_task(asyncio.to_thread(extract_audio_to_wav, sources['source'][1], destination))
        try:
            metadata.update(await asyncio.shield(work))
        except asyncio.CancelledError:
            await work
            raise
    elif operation == 'join':
        listing = directory / 'clips.txt'
        listing.write_text(''.join("file '" + str(sources[key][1]).replace("'", "'\\''") + "'\n" for key in sorted(sources, key=int)))
        process = await asyncio.create_subprocess_exec('ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', str(listing), '-c', 'copy', str(destination),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        try:
            _, error = await asyncio.wait_for(process.communicate(), timeout=600)
            if process.returncode: raise ValueError('Video join failed: ' + error.decode(errors='replace')[-500:])
        finally:
            if process.returncode is None:
                process.kill(); await process.wait()
    else:
        project = ComposerProject.model_validate(payload['project'])
        metadata.update(trackCount=len(project.tracks), clipCount=len(project.clips))
        if operation == 'compose':
            await finish_worker(render_composition(project, sources, destination, progress))
        elif operation == 'clip':
            metadata.update(outputType='clip', clipId=payload['clip_id'])
            descriptor = await finish_worker(render_clip_output(project, payload['clip_id'], sources, destination, progress))
            metadata.update(kind=descriptor.get('kind', metadata['kind']), media_type=descriptor.get('mediaType', metadata['media_type']))
        else:
            raise ValueError('Unknown video media operation')
    for item in payload['sources'].values():
        if 'reference' in item:resolve(item['reference'])
    if not destination.is_file() or not destination.stat().st_size:
        raise ValueError('Media renderer produced no output')
    return destination, metadata


PACKAGE_CAPABILITIES = frozenset({'audio.source_separation', 'audio.detailed_transcription', 'media.video_subtitles', 'media.video_audio_translation', 'media.video_speaker_voice_replacement'})


VOICE_CAPABILITIES = frozenset({'audio.source_separation', 'audio.detailed_transcription', 'audio.speaker_voice_replacement'})

def submit_package(runtime, principal, mounted, capability, options, content, filename, media_type, reference=None, *, key=None, studio_id=STUDIO_ID):
    if capability not in (VOICE_CAPABILITIES if studio_id == 'ai2apps.readaloud' else PACKAGE_CAPABILITIES) or studio_id not in (STUDIO_ID, 'ai2apps.readaloud'):
        raise ValueError('Unsupported Studio media capability')
    import uuid
    jobs = runtime.studio_jobs
    instance = (mounted.mount.get('context') or {}).get('studioInstanceId')
    if not isinstance(instance, str) or not instance:
        raise ValueError('Video Studio output scope is missing')
    runtime.extension_manager.require_instance_access(instance, principal)
    scope = dict(actor_id=principal.actor_user_id, installation_id=principal.installation_id,
                 app_instance_id=instance, studio_id=studio_id)
    import hashlib
    from .source_reference import describe
    source_reference=describe(content) if isinstance(content,Path) else None
    if source_reference and capability not in {'audio.detailed_transcription','media.video_subtitles','audio.source_separation','audio.speaker_voice_replacement','media.video_audio_translation','media.video_speaker_voice_replacement'}:
        raise ValueError('This workflow has not declared support for source references')
    reference_reference=describe(reference) if isinstance(reference,Path) else None
    reference_identity=json.dumps(reference_reference,sort_keys=True).encode() if reference_reference else (reference or b'')
    identity=json.dumps(source_reference,sort_keys=True).encode() if source_reference else content
    fingerprint = hashlib.sha256(identity + reference_identity + json.dumps(
        [capability, options, filename, media_type, mounted.declaration, scope], sort_keys=True).encode()).hexdigest()
    key = key or 'video-' + uuid.uuid4().hex
    with runtime.database.transaction() as db:
        previous = db.execute('SELECT * FROM studio_background_jobs WHERE actor_id=? AND installation_id=? AND studio_id=? AND idempotency_key=?',
            (principal.actor_user_id, principal.installation_id, studio_id, key)).fetchone()
    if previous:
        if json.loads(previous['request_json']).get('fingerprint') != fingerprint:
            raise ValueError('Idempotency key already used for different video input')
        return jobs.public(previous)
    repository = StudioRepository(runtime.database)
    run = repository.create_run(**scope, mini_app_id=mounted.declaration['id'],
        mini_app_version=mounted.declaration.get('version', '1'), placement='inline',
        title=Path(filename).name[:160] or 'Video', input_data={'capability': capability})
    root = jobs.root / ('video-input-' + run['id']);root.mkdir(mode=0o700)
    try:
        if not source_reference:
            (root / 'source').write_bytes(content);(root / 'source').chmod(0o600)
        if reference is not None and not reference_reference:
            (root / 'reference').write_bytes(reference);(root / 'reference').chmod(0o600)
        # Persist only the verified capability declaration and identity, never auth headers.
        payload = {'fingerprint': fingerprint, 'capability': capability, 'options': options, 'filename': Path(filename).name,
            'media_type': media_type, 'root': str(root), 'source_reference':source_reference, 'reference_reference':reference_reference, 'has_reference': reference is not None,
            'declaration': mounted.declaration, 'capabilities': sorted(mounted.capabilities),
            'mount': {'id': 'background-' + uuid.uuid4().hex, 'app_instance_id': mounted.mount['app_instance_id'],
                      'context': {'studioId': studio_id, 'miniAppId': mounted.declaration['id']}}}
        return jobs.submit(principal=principal, app_instance_id=scope['app_instance_id'], studio_id=studio_id,
            mini_app_id=mounted.declaration['id'], kind='voice-media' if studio_id == 'ai2apps.readaloud' else 'video-package', key=key,
            run_id=run['id'], payload=payload)
    except BaseException as error:
        shutil.rmtree(root, ignore_errors=True)
        repository.update_run(run['id'], **scope, status='failed', progress=0,
            detail='Submission failed', error={'code': 'submission_failed', 'message': str(error)[:500]})
        raise


async def render_package(manager, job, principal, payload):
    from ai2apps.studio.capability_broker import StudioCapabilityBroker, MountedMiniApp
    from ai2apps.model_invocation import ModelInvocationContext
    from ai2apps.task_llm import resolve_task_model, task_payload
    class Invocations:
        def __getattr__(self, name):
            return getattr(manager.runtime.model_invocations, name.replace('invoke_foreground_', 'invoke_background_'))
    class Runtime:
        model_invocations = Invocations()
        def __getattr__(self, name): return getattr(manager.runtime, name)
    class WorkerRequest:
        async def is_disconnected(self): return False
    class Broker(StudioCapabilityBroker):
        def mounted_mini_app(self, studio_id, mount_id, *, principal):
            if studio_id != job['studio_id'] or principal.actor_user_id != job['actor_id']:
                raise ValueError('Background scope mismatch')
            return MountedMiniApp(payload['mount'], payload['declaration'], frozenset(payload['capabilities']))
        async def _task_completion(self, prompt, *, system, principal, mounted, request,
                                   purpose='work_standard', profile='normal'):
            model_id = resolve_task_model(self.runtime, purpose.removeprefix('work_'), profile)
            if not model_id: raise ValueError('No task model configured')
            body = task_payload(model_id, [{'role':'system','content':system},{'role':'user','content':prompt}],
                purpose.removeprefix('work_'), max_tokens=min(16000, max(512,len(prompt)*2)))
            invocations = self.runtime.model_invocations
            context = ModelInvocationContext.from_principal(principal, session_id=job['id'],
                app_instance_id=job['app_instance_id'], consumer_app_id=job['mini_app_id'])
            if model_id.startswith('cloud/'):
                value = await invocations.invoke_agent_cloud_json(body, context=context)
            else:
                response = await invocations.invoke_background_json(model_id, 'chat_completions', body, context=context)
                if response.status_code >= 400: raise ValueError('Task model failed')
                value = json.loads(bytes(response.body))
            return self._completion_text(value)
    manager.runtime.extension_manager.require_instance_access(payload['mount']['app_instance_id'], principal)
    broker = Broker(Runtime())
    root = Path(payload['root'])
    options = dict(payload['options'])
    repository = StudioRepository(manager.database)
    async def progress(phase_index, status, percent, detail):
        repository.update_run(job['run_id'], **manager.scope(job), status='running',
            progress=min(95, max(0, percent)), detail=detail)
        manager._update(job['id'], 'running', result={'progress': {'phaseIndex':phase_index,'status':status,'percent':percent,'detail':detail}})
    await progress(0, 'running', 1, 'Preparing video workflow')
    from .source_reference import resolve
    source=resolve(payload['source_reference']) if payload.get('source_reference') else (root/'source').read_bytes()
    common = dict(principal=principal, content=source,
        filename=payload['filename'], media_type=payload['media_type'])
    capability = payload['capability']
    output_format = options.pop('output_format', 'json')
    if capability == 'media.video_subtitles':
        response = await broker.video_subtitles(job['studio_id'], payload['mount']['id'], **common,
            request=WorkerRequest(), progress=progress, **options)
        name, media = 'video-subtitles.zip', 'application/zip'
    elif capability == 'media.video_audio_translation':
        response = await broker.video_audio_translation(job['studio_id'], payload['mount']['id'], **common,
            request=WorkerRequest(), progress=progress, **options)
        name, media = 'translated-video.mp4', 'video/mp4'
    elif capability == 'media.video_speaker_voice_replacement':
        response = await broker.video_speaker_replacement(job['studio_id'], payload['mount']['id'], **common,
            reference=(resolve(payload['reference_reference']) if payload.get('reference_reference') else (root/'reference').read_bytes()) if payload['has_reference'] else None, **options)
        name, media = ('speaker-analysis.json', 'application/json') if options.get('action')=='analyze' else ('speaker-replaced.mp4', 'video/mp4')
    elif capability == 'audio.speaker_voice_replacement':
        response = await broker.audio_speaker_replacement(job['studio_id'], payload['mount']['id'], **common,
            reference=(resolve(payload['reference_reference']) if payload.get('reference_reference') else (root/'reference').read_bytes()) if payload['has_reference'] else None, **options)
        name, media = ('speaker-analysis.json', 'application/json') if options.get('action')=='analyze' else ('speaker-replaced.wav', 'audio/wav')
    elif capability == 'audio.source_separation':
        response = await broker.source_separation(job['studio_id'], payload['mount']['id'], **common, **options)
        name, media = 'separated-audio.zip', 'application/zip'
    elif capability == 'audio.detailed_transcription':
        response = await broker.detailed_transcription(job['studio_id'], payload['mount']['id'], **common, **options)
        name, media = 'transcript.json', 'application/json'
    else:
        raise ValueError('Unsupported video workflow')
    if payload.get('source_reference'):resolve(payload['source_reference'])
    if payload.get('reference_reference'):resolve(payload['reference_reference'])
    if response.status_code >= 400: raise ValueError('Video workflow failed')
    content = bytes(response.body)
    if not content: raise ValueError('Video workflow returned no output')
    metadata = {'filename': name, 'media_type': media, 'kind': 'video' if media.startswith('video/') else 'audio' if media.startswith('audio/') else 'file'}
    if capability == 'audio.detailed_transcription' and output_format != 'json':
        from ai2apps.readaloud.transcript import transcript_output
        from ai2apps.studio.image_jobs import checkpoint
        formatted, filename, mime = transcript_output(content, output_format)
        checkpoint(manager.root / job['id'] / 'preview', formatted,
            {'filename':filename,'media_type':mime,'kind':'file'})
        metadata['attachments'] = ['preview']
    if capability == 'media.video_subtitles' and options.get('burn_in'):
        import io, zipfile
        from ai2apps.studio.image_jobs import checkpoint
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            video = archive.read('subtitled-video.mp4')
        checkpoint(manager.root / job['id'] / 'preview', video,
            {'filename':'subtitled-video.mp4','media_type':'video/mp4','kind':'video'})
        metadata['attachments'] = ['preview']
    return content, metadata
