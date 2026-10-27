"""Text-only audio generation behind the authenticated Studio mount broker."""
from __future__ import annotations

import asyncio
import contextlib
import json
import tempfile
import uuid
import wave
from pathlib import Path

from ai2apps.model_invocation import ModelInvocationContext, ModelInvocationError
from ai2apps.model_providers import list_package_models
from ai2apps.model_worker.audio_generation import validate_audio_generation
from ai2apps.model_worker.protocol import ModelWorkerError

CAPABILITIES = {'audio.music_generation': 'music', 'audio.sound_effects_generation': 'sound_effects', 'audio.song_generation': 'music'}


def generation_models(runtime, capability):
    task = CAPABILITIES.get(capability)
    return tuple(sorted((m for m in list_package_models(runtime)
        if task and m.model_type == 'audio_generation'
        and 'audio_generate' in m.endpoints
        and not m.metadata.get('internal')
        and m.metadata.get('audio_generation', {}).get('task') == task
        and ((m.metadata['audio_generation'].get('workflow') == 'ai2apps.song-generation/v1')
             == (capability == 'audio.song_generation'))), key=lambda m: m.id))


def authorize(broker, studio_id, mount_id, principal, capability):
    from .capability_broker import StudioCapabilityError
    mounted = broker.mounted_mini_app(studio_id, mount_id, principal=principal)
    if studio_id != 'ai2apps.readaloud' or capability not in CAPABILITIES or capability not in mounted.capabilities:
        raise StudioCapabilityError('capability_not_declared', 'Audio generation is not allowed for this mount', status_code=403)
    return mounted


def model_options(broker, studio_id, mount_id, principal, capability):
    authorize(broker, studio_id, mount_id, principal, capability)
    return {'items': [dict(id=m.id, label=m.display_name, ready=m.checkpoint_ready,
        preferredPromptLanguage=m.metadata['audio_generation'].get('preferred_prompt_language'),
        minimumSeconds=m.metadata['audio_generation']['minimum_duration'],
        maximumSeconds=m.metadata['audio_generation']['maximum_duration'],
        lyrics=m.metadata['audio_generation']['lyrics'],
        planningModes=m.metadata['audio_generation'].get('planning_modes', []),
        maximumTokens=min(3000, m.metadata['audio_generation'].get('max_semantic_tokens', 3000))) for m in generation_models(broker.runtime, capability)]}


async def generate(broker, studio_id, mount_id, *, principal, request, capability, payload, progress=None):
    from .capability_broker import StudioCapabilityError
    mounted = authorize(broker, studio_id, mount_id, principal, capability)
    model, body = validate_request(broker.runtime, capability, payload)
    song = capability == 'audio.song_generation'
    request_id = 'studio-audio-' + uuid.uuid4().hex
    context = ModelInvocationContext.from_principal(principal, session_id=f'studio-mini-app:{mount_id}:{request_id}',
        app_instance_id=mounted.mount['app_instance_id'], consumer_app_id=mounted.declaration['id'])
    cancelled = asyncio.Event()
    async def watch_disconnect():
        while not cancelled.is_set():
            if await request.is_disconnected():
                cancelled.set()
                return
            await asyncio.sleep(.25)
    watcher = asyncio.create_task(watch_disconnect())
    try:
        prepared_prompt = body['prompt']
        body = {**body, 'prompt': prepared_prompt}
        authorize(broker, studio_id, mount_id, principal, capability)
        with tempfile.TemporaryDirectory(prefix='ai2apps-studio-audio-') as directory:
            target = Path(directory) / 'generated.wav'
            await broker.runtime.model_invocations.invoke_background_to_file(model.id, 'audio_generate', body, target,
                request_id=request_id, context=context, cancel_requested=cancelled.is_set, progress=progress)
            if cancelled.is_set():
                raise StudioCapabilityError('generation_cancelled', 'Generation cancelled', status_code=499)
            authorize(broker, studio_id, mount_id, principal, capability)
            if target.stat().st_size > 128 * 1024 * 1024:
                raise StudioCapabilityError('invalid_audio_output', 'Generated audio exceeds output limit')
            with wave.open(str(target), 'rb') as audio:
                if audio.getnchannels() != 2 or audio.getsampwidth() != 2 or audio.getframerate() not in (44100, 48000) or not 0 < audio.getnframes() / audio.getframerate() <= 121:
                    raise StudioCapabilityError('invalid_audio_output', 'Invalid generated WAV')
            filename = ('song' if song else 'music' if capability == 'audio.music_generation' else 'sound-effect') + '.wav'
            if progress:
                progress({'phase': 'saving'})
            url = await asyncio.to_thread(broker.runtime.readaloud_tasks.save_studio_output, principal.actor_user_id,
                target.read_bytes(), mini_app_id=mounted.declaration['id'], filename=filename, media_type='audio/wav')
            duration = audio.getnframes() / audio.getframerate()
            return {'downloadUrl': url, 'filename': filename, 'durationSeconds': duration,
                    'preparedPrompt': prepared_prompt,
                    'reachedLimit': bool(song and duration >= body['generation']['max_semantic_tokens'] / 25 - .05)}
    except ModelInvocationError as error:
        raise StudioCapabilityError(error.code, str(error), status_code=499 if error.code == 'generation_cancelled' else 502) from error
    except asyncio.CancelledError:
        cancelled.set()
        await broker.runtime.model_invocations.cancel_request(model.id, request_id)
        raise
    finally:
        cancelled.set()
        watcher.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watcher


def validate_request(runtime, capability, payload):
    from .capability_broker import StudioCapabilityError
    model = next((m for m in generation_models(runtime, capability) if m.id == payload.get('model')), None)
    if model is None or not model.checkpoint_ready:
        raise StudioCapabilityError('model_not_ready', 'Select and prepare an audio generation model', status_code=409)
    try:
        body = validate_audio_generation({**payload, 'task': CAPABILITIES[capability]})
    except ModelWorkerError as error:
        raise StudioCapabilityError(error.code, str(error), status_code=422) from error
    contract = model.metadata['audio_generation']
    song = capability == 'audio.song_generation'
    if song:
        g = body.get('generation', {})
        maximum = min(3000, int(contract['maximum_duration'] * 25), contract.get('max_semantic_tokens', 3000))
        if (body.get('schema') != 'ai2apps.audio-generation/v2'
            or body.get('duration_mode') != 'auto'
            or g.get('planning_mode', 'full') not in contract.get('planning_modes', [])
            or type(g.get('max_semantic_tokens')) is not int
            or not 1 <= g['max_semantic_tokens'] <= maximum):
            raise StudioCapabilityError('invalid_audio_generation', 'Unsupported song workflow or token limit', status_code=422)
    elif body.get('schema', 'ai2apps.audio-generation/v1') != 'ai2apps.audio-generation/v1':
        raise StudioCapabilityError('invalid_audio_generation', 'This model requires fixed-duration generation', status_code=422)
    if (not song and not contract['minimum_duration'] <= body['duration'] <= contract['maximum_duration']) or (body['lyrics'] and not contract['lyrics']):
        raise StudioCapabilityError('invalid_audio_generation', 'Duration or lyrics are unsupported by the selected model', status_code=422)
    return model, body


async def render_background(runtime, principal, job, payload, progress=None):
    """Execute an accepted owner-bound job without retaining its mount or HTTP request."""
    model, body = validate_request(runtime, payload['capability'], payload['input'])
    context = ModelInvocationContext.from_principal(principal, session_id=job['id'],
        app_instance_id=job['app_instance_id'], consumer_app_id=job['mini_app_id'])
    try:
        with tempfile.TemporaryDirectory(prefix='ai2apps-studio-audio-') as directory:
            target = Path(directory) / 'generated.wav'
            await runtime.model_invocations.invoke_background_to_file(model.id, 'audio_generate', body, target,
                request_id=job['id'], context=context, progress=progress)
            if target.stat().st_size > 128 * 1024 * 1024:
                raise ValueError('Generated audio exceeds output limit')
            with wave.open(str(target), 'rb') as audio:
                duration = audio.getnframes() / audio.getframerate()
                if audio.getnchannels() != 2 or audio.getsampwidth() != 2 or audio.getframerate() not in (44100, 48000) or not 0 < duration <= 121:
                    raise ValueError('Invalid generated WAV')
            song = payload['capability'] == 'audio.song_generation'
            filename = ('song' if song else 'music' if payload['capability'] == 'audio.music_generation' else 'sound-effect') + '.wav'
            return target.read_bytes(), {'filename': filename, 'durationSeconds': duration,
                'preparedPrompt': body['prompt'],
                'reachedLimit': bool(song and duration >= body['generation']['max_semantic_tokens'] / 25 - .05)}
    except asyncio.CancelledError:
        await runtime.model_invocations.cancel_request(model.id, job['id'])
        raise
