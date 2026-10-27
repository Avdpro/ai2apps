"""Local durable generation jobs. Browser lifetime is never a cancellation signal."""
from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
from types import SimpleNamespace
import uuid
from dataclasses import asdict
from pathlib import Path

from ai2apps.core import utc_now_text
from ai2apps.identity import RequestPrincipal, MemberRole
from ai2apps.studio.repository import StudioRepository


class StudioBackgroundJobs:
    def __init__(self, runtime):
        self.runtime = runtime
        self.database = runtime.database
        self.root = runtime.config.paths.base_path / 'platform' / 'studio-jobs'
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.runner = None
        self.active = None
        self.active_id = None
        self.closing = False
        self.wake = asyncio.Event()

    def submit(self, *, principal, app_instance_id, studio_id, mini_app_id, kind, key, payload, run_id=None):
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        now = utc_now_text()
        with self.database.transaction(write=True) as db:
            previous = db.execute('SELECT * FROM studio_background_jobs WHERE actor_id=? AND installation_id=? AND studio_id=? AND idempotency_key=?',
                                  (principal.actor_user_id, principal.installation_id, studio_id, key)).fetchone()
            if previous:
                if previous['request_json'] != encoded or previous['kind'] != kind or previous['mini_app_id'] != mini_app_id or previous['app_instance_id'] != app_instance_id or previous['run_id'] != run_id:
                    raise ValueError('Idempotency key already used for a different request')
                return self.public(previous)
            identifier = 'stjob_' + uuid.uuid4().hex
            if kind == 'quick-read':
                self._snapshot_voice(identifier, principal, payload)
            db.execute('''INSERT INTO studio_background_jobs
                (id,actor_id,installation_id,app_instance_id,studio_id,mini_app_id,kind,idempotency_key,request_json,principal_json,status,run_id,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,'queued',?,?,?)''',
                (identifier, principal.actor_user_id, principal.installation_id, app_instance_id, studio_id, mini_app_id, kind, key, encoded, json.dumps(asdict(principal)), run_id, now, now))
        self.wake.set()
        return self.get(identifier, principal)

    def _snapshot_voice(self, identifier, principal, payload):
        """Freeze character settings and private references before accepting the job."""
        from ai2apps.readaloud import ReadAloudRepository
        from ai2apps.readaloud.materials import VoiceMaterials
        directory = self.root / identifier
        directory.mkdir(mode=0o700)
        try:
            profile = None
            references = {}
            if payload.get('voice_profile_id'):
                profile = ReadAloudRepository(self.database, self.runtime.events).get_voice_profile(
                    principal.actor_user_id, payload['voice_profile_id'])
                materials = VoiceMaterials(self.database, self.runtime.config.paths.artifacts_path)
                total = 0
                for index, sample in enumerate((profile.get('training') or {}).get('samples', [])):
                    asset, source = materials.asset_path(principal.actor_user_id, sample['asset_id'])
                    content = source.read_bytes()
                    total += len(content)
                    if total > 64 * 1024 * 1024:
                        raise ValueError('Reference materials exceed 64 MiB')
                    name = f'reference-{index}'
                    target = directory / name
                    target.write_bytes(content)
                    target.chmod(0o600)
                    references[sample['asset_id']] = {'asset': asset, 'file': name}
            target = directory / 'input.json'
            target.write_text(json.dumps({'profile': profile, 'references': references}))
            target.chmod(0o600)
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            payload = json.loads(job['request_json'])
            if payload.get('input_root'):
                shutil.rmtree(payload['input_root'], ignore_errors=True)
            raise

    def for_run(self, run_id, principal):
        with self.database.transaction() as db:
            row = db.execute('SELECT * FROM studio_background_jobs WHERE run_id=? AND actor_id=? AND installation_id=?',
                (run_id, principal.actor_user_id, principal.installation_id)).fetchone()
        return self.public(row) if row else None

    @staticmethod
    def public(row):
        return {key: row[key] for key in ('id', 'studio_id', 'mini_app_id', 'status', 'run_id', 'created_at', 'updated_at')} | {
            'result': json.loads(row['result_json'] or 'null'), 'error': json.loads(row['error_json'] or 'null')}

    def get(self, identifier, principal):
        with self.database.transaction() as db:
            row = db.execute('SELECT * FROM studio_background_jobs WHERE id=? AND actor_id=? AND installation_id=?',
                             (identifier, principal.actor_user_id, principal.installation_id)).fetchone()
        if row is None:
            raise KeyError(identifier)
        return self.public(row)

    def list(self, principal, studio_id):
        with self.database.transaction() as db:
            rows = db.execute('SELECT * FROM studio_background_jobs WHERE actor_id=? AND installation_id=? AND studio_id=? ORDER BY created_at DESC LIMIT 100',
                              (principal.actor_user_id, principal.installation_id, studio_id)).fetchall()
        return [self.public(row) for row in rows]

    def _update(self, identifier, status, *, result=None, error=None):
        with self.database.transaction(write=True) as db:
            db.execute('UPDATE studio_background_jobs SET status=?,result_json=COALESCE(?,result_json),error_json=?,updated_at=? WHERE id=?',
                       (status, json.dumps(result) if result is not None else None, json.dumps(error) if error else None, utc_now_text(), identifier))

    async def startup(self):
        if self.runner is not None:
            return
        # Do not blindly repeat model inference after a host crash. Spool-ready jobs
        # can publish without inference; other interrupted jobs require an explicit retry.
        with self.database.transaction() as db:
            interrupted = db.execute("SELECT * FROM studio_background_jobs WHERE status='running'").fetchall()
        for row in interrupted:
            ready = (self.root / row['id'] / 'result.json').exists()
            self._update(row['id'], 'publishing' if ready else 'interrupted',
                         error=None if ready else {'code': 'host_interrupted', 'message': 'Desktop stopped during generation; retry explicitly.'})
            if not ready and row['run_id']:
                StudioRepository(self.database).update_run(row['run_id'], status='failed', progress=100, detail='Desktop interrupted', error={'code':'host_interrupted','message':'Retry explicitly'}, **self.scope(dict(row)))
        self.closing = False
        self.runner = asyncio.create_task(self._loop(), name='studio-background-jobs')

    async def shutdown(self):
        self.closing = True
        if self.runner:
            self.runner.cancel()
            try:
                await self.runner
            except asyncio.CancelledError:
                pass
            self.runner = None

    async def _loop(self):
        while True:
            self.wake.clear()
            with self.database.transaction() as db:
                row = db.execute("SELECT * FROM studio_background_jobs WHERE status IN ('queued','publishing') ORDER BY created_at,id LIMIT 1").fetchone()
            if row is None:
                await self.wake.wait()
                continue
            self.active_id = row["id"]
            self.active = asyncio.create_task(self._run(dict(row)))
            try:
                await self.active
            except asyncio.CancelledError:
                if self.closing: raise
                self._mark_cancelled(dict(row))
            self.active = None
            self.active_id = None

    async def _run(self, job):
        directory = self.root / job['id']
        directory.mkdir(exist_ok=True, mode=0o700)
        try:
            if job['status'] == 'queued':
                self._update(job['id'], 'running')
                content, metadata = await self.execute(job)
                # Result checkpoint precedes publication, so reconnect/restart never
                # needs the browser to forward bytes or announce completion.
                for name, data in [('output', content), ('result.json', json.dumps(metadata).encode())]:
                    temporary = directory / (name + '.tmp')
                    with temporary.open('wb') as file:
                        os.chmod(temporary, 0o600)

                        if isinstance(data, Path):
                            with data.open('rb') as source: shutil.copyfileobj(source, file)
                        else:
                            file.write(data)
                        file.flush(); os.fsync(file.fileno())
                    os.replace(temporary, directory / name)
                descriptor = os.open(directory, os.O_RDONLY)
                try: os.fsync(descriptor)
                finally: os.close(descriptor)
                self._update(job['id'], 'publishing')
            result = self.publish(job, directory)
            self._update(job['id'], 'succeeded', result=result)
            # Output is now durable in the Studio-owned workspace.
            shutil.rmtree(directory, ignore_errors=True)
            if job['kind'] == 'video-upscale':
                shutil.rmtree(self.runtime.config.paths.artifacts_path / 'video-upscaling-jobs' / job['run_id'], ignore_errors=True)
            if job['kind'] in ('video-media', 'video-package', 'voice-media'):
                shutil.rmtree(self.root / ('video-input-' + job['run_id']), ignore_errors=True)
        except asyncio.CancelledError:
            if self.closing:
                raise
            self._mark_cancelled(job)
        except Exception as error:
            # Keep checkpointed output for an explicit publish retry, never regenerate.
            state = 'publish_failed' if (directory / 'result.json').exists() else 'failed'
            self._update(job['id'], state, error={'code': state, 'message': str(error)[:500]})
            if job['run_id']:
                try:
                    StudioRepository(self.database).update_run(job['run_id'], status='failed', progress=100, detail='Failed',
                        error={'code': state, 'message': str(error)[:500]}, **self.scope(job))
                except Exception:
                    pass

    @staticmethod
    def scope(job):
        return {key: job[key] for key in ('actor_id', 'installation_id', 'app_instance_id', 'studio_id')}

    async def execute(self, job):
        payload = json.loads(job['request_json'])
        identity = json.loads(job['principal_json']); identity['role'] = MemberRole(identity['role'])
        principal = RequestPrincipal(**identity)
        if getattr(self.runtime, 'extension_manager', None) is not None:
            self.runtime.extension_manager.require_instance_access(job['app_instance_id'], principal)
        if job['kind'] in ('voice-preview','cloud-image','image-upscale','image-adjust','frozen-time'):
            from ai2apps.studio.extended_jobs import execute
            return await execute(self,job,principal,payload)
        if job['kind'] == 'video-upscale':
            import threading
            from ai2apps.studio.upscaling import _manager
            from ai2apps.model_invocation import ModelInvocationContext
            context = ModelInvocationContext.from_principal(principal, session_id=job['id'],
                app_instance_id=job['app_instance_id'], consumer_app_id=job['studio_id'])
            return await _manager(self.runtime)._run(job['run_id'], self.scope(job), context, threading.Event(), durable=True)
        if job['kind'] in ('video-package', 'voice-media'):
            from ai2apps.studio.video_jobs import render_package
            return await render_package(self, job, principal, payload)
        if job['kind'] == 'video-media':
            from ai2apps.studio.video_jobs import render_media
            return await render_media(self, job, principal, payload)
        if job['kind'] == 'quick-read':
            from ai2apps.api.readaloud import QuickReadRequest, render_quick_read
            directory = self.root / job['id']
            snapshot = json.loads((directory / 'input.json').read_text())
            def asset_path(owner, identifier):
                if owner != job['actor_id']:
                    raise ValueError('Reference owner mismatch')
                ref = snapshot['references'][identifier]
                return ref['asset'], directory / ref['file']
            return await render_quick_read(self.runtime, QuickReadRequest(**payload), principal, background=True,
                snapshot=snapshot, snapshot_materials=SimpleNamespace(asset_path=asset_path))
        if job['kind'] == 'audio-generation':
            from ai2apps.studio.audio_generation import render_background
            last_phase = None
            def progress(value):
                nonlocal last_phase
                phase = str(value.get('phase', ''))
                if phase in {'plan','abc','semantic','synthesis','synthesize','decode','vae','saving','complete'} and phase != last_phase:
                    last_phase = phase
                    self._update(job['id'], 'running', result={'progress': phase})
            return await render_background(self.runtime, principal, job, payload, progress=progress)
        if job['kind'] in ('local-image-edit', 'sticker-batch'):
            from ai2apps.studio.image_jobs import render_image_job
            return await render_image_job(self, job, principal, payload)
        if job['kind'] != 'local-image':
            raise ValueError('Unsupported generation kind')
        invocations = self.runtime.model_invocations
        model = invocations.model(payload['model'])
        if model is None or model.model_type != 'image_generation' or not model.checkpoint_ready:
            raise ValueError('Local image model is not ready')
        StudioRepository(self.database).update_run(job['run_id'], status='running', progress=10, detail='Generating image', **self.scope(job))
        response = await invocations.invoke_background_json(model.id, 'image_generation', payload,
            request_id=job['id'], context=invocations.context_for_actor(principal.actor_user_id,
                session_id=job['id'], consumer_app_id=job['studio_id']))
        if response.status_code >= 400:
            raise ValueError('Local image generation failed')
        result = json.loads(bytes(response.body))
        image = result.get('image') or {}
        data_url = image.get('dataUrl', '')
        if data_url:
            header, encoded = data_url.split(',', 1)
            media_type = header.removeprefix('data:').removesuffix(';base64')
        else:
            encoded = result['data'][0]['b64_json']
            media_type = 'image/' + payload.get('outputFormat', 'png').replace('jpg', 'jpeg')
        if media_type not in ('image/png', 'image/jpeg', 'image/webp'):
            raise ValueError('Unsupported image output')
        from ai2apps.images.history import MAX_IMAGE_BYTES
        from ai2apps.api.imagine_studio import _matches_image_media_type
        if len(encoded) > (MAX_IMAGE_BYTES * 4 // 3 + 4):
            raise ValueError('Image output is too large')
        content = base64.b64decode(encoded, validate=True)
        if not content or len(content) > MAX_IMAGE_BYTES or not _matches_image_media_type(content, media_type):
            raise ValueError('Invalid image output')
        return content, {'media_type': media_type, 'model': model.id}

    def publish(self, job, directory, *, output_key=None, complete=True):
        metadata = json.loads((directory / 'result.json').read_text())
        if job['kind'] == 'voice-preview':
            from ai2apps.studio.extended_jobs import publish_voice
            return publish_voice(self,job,directory)
        if metadata.get('frozen'):
            from ai2apps.studio.extended_jobs import publish_frozen
            return publish_frozen(self,job,directory,metadata)
        if job['kind'] == 'quick-read':
            url = self.runtime.readaloud_tasks.save_quick_audio(job['actor_id'], (directory / 'output').read_bytes(),
                output_key=job['id'], **metadata)
            return {'downloadUrl': url}
        if job['kind'] == 'audio-generation':
            url = self.runtime.readaloud_tasks.save_studio_output(job['actor_id'], (directory / 'output').read_bytes(),
                mini_app_id=job['mini_app_id'], filename=metadata['filename'], media_type='audio/wav', output_key=job['id'])
            return {**metadata, 'downloadUrl': url}
        if job['kind'] == 'voice-media':
            payload = json.loads(job['request_json'])
            content = (directory / 'output').read_bytes()
            publisher = self.runtime.readaloud_tasks
            if payload['capability'] == 'audio.source_separation':
                result = publisher.save_separation_output(job['actor_id'], content, payload['filename'], output_key=job['id'])
            else:
                response_url = publisher.save_studio_output(job['actor_id'], content,
                    mini_app_id=job['mini_app_id'] + ('.archive' if metadata.get('attachments') else ''),
                    filename=metadata['filename'], media_type=metadata['media_type'], output_key=job['id'])
                result = {'downloadUrl': response_url, 'responseUrl': response_url}
                if metadata.get('attachments'):
                    preview = directory / 'preview'
                    info = json.loads((preview / 'result.json').read_text())
                    result['downloadUrl'] = publisher.save_studio_output(job['actor_id'], (preview / 'output').read_bytes(),
                        mini_app_id=job['mini_app_id'], filename=info['filename'], media_type=info['media_type'], output_key=job['id']+'-preview')
                    publisher.quick_history(job['actor_id'], mini_app_id=job['mini_app_id']+'.archive')
            StudioRepository(self.database).update_run(job['run_id'], status='succeeded', progress=100, detail='Completed', **self.scope(job))
            return {**result, 'runId': job['run_id']}
        if metadata.get('batch'):
            StudioRepository(self.database).update_run(job['run_id'], status='succeeded', progress=100, detail='Completed', **self.scope(job))
            return {'runId': job['run_id'], 'completed': metadata['completed']}
        for attachment in metadata.get('attachments', []):
            if attachment != 'preview': raise ValueError('Invalid media attachment')
            self.publish(job, directory / attachment, output_key=job['id'] + '-preview', complete=False)
        output_key = output_key or job['id']
        from ai2apps.storage.repositories import SessionRepository
        from ai2apps.core import SessionKind, SessionRetention, SessionVisibility
        sessions = SessionRepository(self.database)
        # Home session is stable for this authorized Studio instance.
        with self.database.transaction() as db:
            existing = db.execute("SELECT id FROM sessions WHERE app_instance_id=? AND is_home=1 AND status='active' LIMIT 1", (job['app_instance_id'],)).fetchone()
        if job['studio_id'] == 'ai2apps.video-studio':
            session = SimpleNamespace(id=self.runtime.video_tasks.artifact_session())
        else:
            session = sessions.get(existing['id']) if existing else sessions.create(app_instance_id=job['app_instance_id'], title=job['studio_id'], is_home=True,
                session_kind=SessionKind.APP, visibility=SessionVisibility.UNLISTED, retention=SessionRetention.DURABLE)
        filename = metadata.get('filename')
        # Separate logical artifacts across jobs even when their bytes and display
        # names match, so deleting one Run never retires another Run's output.
        storage_name = (Path(filename).stem + '-' + output_key + Path(filename).suffix
                        if filename else output_key + '.' + metadata['media_type'].split('/')[1])
        artifact = self.runtime.workspace.import_artifact(session.id, directory / 'output',
            name=storage_name, media_type=metadata['media_type'],
            metadata={**metadata, 'studioId': job['studio_id'], 'miniAppId': job['mini_app_id'], 'taskId': output_key})
        url = f'/v1/platform/sessions/{session.id}/artifacts/{artifact.id}/download'
        repository = StudioRepository(self.database)
        run = repository.get_run(job['run_id'], **self.scope(job))
        if not any(item.get('sourceId') == artifact.id or item.get('metadata', {}).get('taskId') == output_key for item in run['artifacts']):
            repository.create_artifact(job['run_id'], kind=metadata.get('kind', 'image'), name=filename or artifact.name, media_type=metadata['media_type'],
                preview_url=url, download_url=url, source_id=artifact.id,
                metadata={'taskId': output_key, 'miniAppId': job['mini_app_id'], 'modelId': metadata.get('model'), 'size': metadata.get('size'), 'format': metadata.get('format'), 'prompt': metadata.get('prompt'), 'workspaceSessionId': session.id, 'workspaceArtifactId': artifact.id}, **self.scope(job))
        if complete:
            repository.update_run(job['run_id'], status='succeeded', progress=100, detail='Completed', **self.scope(job))
        return {'downloadUrl': url, 'runId': job['run_id']}

    def retry(self, identifier, principal):
        job = self.get(identifier, principal)
        video_cancelled = job['studio_id'] == 'ai2apps.video-studio' and job['status'] == 'cancelled'
        if job['status'] not in ('failed', 'interrupted', 'publish_failed') and not video_cancelled:
            raise ValueError('Only failed or interrupted jobs can be retried')
        if job['run_id']:
            with self.database.transaction() as db:
                row = dict(db.execute('SELECT * FROM studio_background_jobs WHERE id=?', (identifier,)).fetchone())
            # Only this owner-bound durable job can reopen its failed Run. Keep
            # the public Studio terminal-state transition guard unchanged.
            with self.database.transaction(write=True) as db:
                db.execute("UPDATE studio_runs SET status='queued',progress=0,error_json=NULL,started_at=NULL,completed_at=NULL,updated_at=? WHERE id=? AND actor_id=? AND installation_id=? AND app_instance_id=? AND studio_id=? AND status IN ('failed','cancelled')",
                    (utc_now_text(), job['run_id'], row['actor_id'], row['installation_id'], row['app_instance_id'], row['studio_id']))
                db.execute("UPDATE studio_run_steps SET status='pending',progress=0,detail='Queued',started_at=NULL,completed_at=NULL WHERE run_id=? AND status IN ('failed','cancelled')", (job['run_id'],))
        self._update(identifier, 'publishing' if job['status'] == 'publish_failed' else 'queued')
        self.wake.set()
        return self.get(identifier, principal)

    def _mark_cancelled(self, job):
        self._update(job['id'], 'cancelled')
        if job['run_id']:
            StudioRepository(self.database).update_run(job['run_id'], status='cancelled', progress=100, detail='Cancelled', **self.scope(job))
        shutil.rmtree(self.root / job['id'], ignore_errors=True)

    def stop_after_current(self, identifier, principal):
        job = self.get(identifier, principal)
        with self.database.transaction() as db:
            row = dict(db.execute('SELECT * FROM studio_background_jobs WHERE id=?', (identifier,)).fetchone())
        if row['kind'] != 'sticker-batch':
            raise ValueError('Only sticker batches support stopping after the current image')
        if job['status'] == 'queued':
            return self.cancel(identifier, principal)
        if job['status'] == 'running':
            directory = self.root / identifier
            directory.mkdir(exist_ok=True, mode=0o700)
            (directory / 'stop').touch(mode=0o600)
        return self.get(identifier, principal)

    def cancel(self, identifier, principal):
        job = self.get(identifier, principal)
        if job['status'] in ('succeeded', 'cancelled', 'failed', 'interrupted'):
            return job
        if job['status'] in ('publishing', 'publish_failed'):
            raise ValueError('Generation has finished; output publication cannot be cancelled')
        if self.active_id == identifier and self.active:
            self.active.cancel()
        else:
            with self.database.transaction() as db:
                row = dict(db.execute('SELECT * FROM studio_background_jobs WHERE id=?', (identifier,)).fetchone())
            self._mark_cancelled(row)
        return self.get(identifier, principal)
