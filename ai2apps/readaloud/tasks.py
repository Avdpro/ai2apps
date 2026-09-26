"""Durable, scheduler-aware batch rendering for Voice Studio."""

from __future__ import annotations

import asyncio
import json
import shutil
import hashlib
import os
from urllib.parse import urlencode
import uuid
import wave
import zipfile
import tempfile
from io import BytesIO
from ai2apps.audio_codecs import decode_audio_to_wav
from contextlib import suppress
from pathlib import Path
from typing import Any

from ai2apps.core import (
    AppInstanceStatus,
    ResourceNotFoundError,
    SessionKind,
    SessionRetention,
    SessionVisibility,
    utc_now_text,
)
from ai2apps.identity import user_singleton_key
from ai2apps.readaloud.speech import invoke_speech, split_speech_text, speech_chunk_units, speech_verifier
from ai2apps.readaloud.materials import VoiceMaterials
from ai2apps.readaloud.training import prepare, combined_reference
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.repositories import AppRepository, SessionRepository
from ai2apps.studio import StudioRepository, StudioRepositoryError
from ai2apps.workspace import WorkspaceRepository

MAX_AUDIO_BYTES = 64 * 1024 * 1024


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ReadAloudRenderError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class ReadAloudTaskManager:
    """Persist render snapshots and yield the Heavy Compute slot per segment."""

    def __init__(
        self,
        *,
        runtime: Any,
        database: PlatformDatabase,
        root: Path,
        workspace: WorkspaceRepository | None = None,
    ) -> None:
        self.runtime = runtime
        self.database = database
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.workspace = workspace
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._dispatcher: asyncio.Task[None] | None = None
        self._running: dict[str, asyncio.Task[None]] = {}
        self._closing = False
        self._artifact_sessions: dict[str, str] = {}

    async def startup(self) -> None:
        if self._dispatcher is not None:
            return
        self._closing = False
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            rows = connection.execute(
                "SELECT id FROM readaloud_render_jobs "
                "WHERE status IN ('queued','running') ORDER BY created_at,id"
            ).fetchall()
            connection.execute(
                "UPDATE readaloud_render_jobs SET status='queued',updated_at=? "
                "WHERE status='running'",
                (now,),
            )
            connection.execute(
                "UPDATE readaloud_render_segments SET status='queued',updated_at=? "
                "WHERE status='running'",
                (now,),
            )
        self._dispatcher = asyncio.create_task(
            self._dispatch(), name="ai2apps-readaloud-render"
        )
        for row in rows:
            self._queue.put_nowait(str(row["id"]))

    async def shutdown(self) -> None:
        self._closing = True
        if self._dispatcher is not None:
            self._dispatcher.cancel()
            with suppress(asyncio.CancelledError):
                await self._dispatcher
        self._dispatcher = None
        for task in tuple(self._running.values()):
            task.cancel()
        if self._running:
            await asyncio.gather(*tuple(self._running.values()), return_exceptions=True)
        self._running.clear()

    def _model(self, model_id: str):
        invocations = getattr(self.runtime, "model_invocations", None)
        model = None if invocations is None else invocations.model(model_id)
        if model is None:
            raise ReadAloudRenderError(
                "model_not_found", f"Speech model not found: {model_id}", status_code=404
            )
        if model.model_type != "audio_tts":
            raise ReadAloudRenderError(
                "invalid_model_type", "Selected model is not a speech generator"
            )
        if not model.checkpoint_ready:
            raise ReadAloudRenderError(
                "model_unavailable", "Speech checkpoint is not ready", status_code=503
            )
        return model

    async def create(
        self,
        *,
        owner_user_id: str,
        project_id: str,
        model_id: str,
        segment_ids: list[str] | None = None,
        mini_app_id: str = "ai2apps.audio.audiobook",
        placement: str = "ai2apps.readaloud",
        run_id: str | None = None,
        merge_output: bool = False,
    ) -> dict[str, Any]:
        model = self._model(model_id)
        model_revision = str(
            getattr(model, "revision", None)
            or getattr(model, "upstream_revision", None)
            or (getattr(model, "metadata", {}) or {}).get("revision")
            or ""
        ) or None
        job_id = run_id or f"rar_{uuid.uuid4().hex}"
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            project = connection.execute(
                "SELECT * FROM readaloud_projects WHERE id=? AND owner_user_id=?",
                (project_id, owner_user_id),
            ).fetchone()
            if project is None:
                raise ResourceNotFoundError("readaloud_project", project_id)
            rows = connection.execute(
                """
                SELECT s.*,c.updated_at AS speaker_revision,vp.provider_voice_id,vp.model_id AS voice_model_id,vp.training_json AS voice_training_json
                FROM readaloud_segments s
                LEFT JOIN readaloud_characters c ON c.id=s.speaker_id
                LEFT JOIN readaloud_voice_profiles vp ON vp.id=c.voice_profile_id
                WHERE s.project_id=? AND s.deleted_at IS NULL AND s.review_status='approved'
                ORDER BY s.ordinal,s.id
                """,
                (project_id,),
            ).fetchall()
            selected = set(segment_ids or ())
            if selected:
                rows = [row for row in rows if row["id"] in selected]
                if {row["id"] for row in rows} != selected:
                    raise ReadAloudRenderError(
                        "invalid_segments", "Segments must exist and be approved"
                    )
            if not rows:
                raise ReadAloudRenderError(
                    "no_approved_segments", "Project has no approved segments"
                )
            connection.execute(
                """
                INSERT INTO readaloud_render_jobs(
                    id,owner_user_id,project_id,project_revision,model_id,status,
                    total_segments,created_at,updated_at,mini_app_id,placement,
                    model_revision
                ) VALUES (?,?,?,?,?,'queued',?,?,?,?,?,?)
                """,
                (
                    job_id,
                    owner_user_id,
                    project_id,
                    project["revision"],
                    model_id,
                    len(rows),
                    now,
                    now,
                    mini_app_id,
                    placement,
                    model_revision,
                ),
            )
            for ordinal, row in enumerate(rows):
                request = self._segment_request(row, model_id)
                connection.execute(
                    """
                    INSERT INTO readaloud_render_segments(
                        job_id,segment_id,ordinal,status,request_json,updated_at
                    ) VALUES (?,?,?,'queued',?,?)
                    """,
                    (job_id, row["id"], ordinal, _json(request), now),
                )
        if merge_output:
            with self.database.transaction(write=True) as connection:
                connection.execute("UPDATE readaloud_render_jobs SET merge_output=1 WHERE id=?", (job_id,))
        self._queue.put_nowait(job_id)
        return self.get(job_id, owner_user_id=owner_user_id)

    def _segment_request(self, row, model_id):
        effective_id = row["voice_model_id"] or model_id
        model = self._model(effective_id)
        with self.database.transaction() as connection:
            settings = connection.execute('SELECT asr_verification,asr_model_id FROM readaloud_projects WHERE id=?', (row['project_id'],)).fetchone()
        return {
            "asrVerification": bool(settings['asr_verification']),
            "asrModelId": settings['asr_model_id'] if settings['asr_verification'] else '',

            "model": effective_id,
            "modelRevision": str((getattr(model, "weights", None) or {}).get("revision") or getattr(model, "revision", None) or (getattr(model, "metadata", None) or {}).get("revision") or ""),
            "speakerId": row["speaker_id"],
            "speakerRevision": row["speaker_revision"],
            "voiceTraining": json.loads(row["voice_training_json"] or "{}"),
            "input": row["text"], "speed": row["speed"], "emotion": row["emotion"],
            "emotionStrength": row["emotion_strength"], "voice": row["provider_voice_id"],
            "pauseAfterMs": row["pause_after_ms"],
            **({"speechChunkPolicy": ("indextts-asr-clauses-v3" if speech_chunk_units(effective_id) == 120 else "sentences-v1")}
               if speech_chunk_units(effective_id) == 120 or len(split_speech_text(row["text"], max_units=speech_chunk_units(effective_id))) > 1 else {}),
        }

    def cached_segment(self, owner_user_id, project_id, segment_id, model_id):
        with self.database.transaction() as connection:
            row = connection.execute("""SELECT s.*,c.updated_at AS speaker_revision,vp.provider_voice_id,vp.model_id AS voice_model_id,vp.training_json AS voice_training_json
                FROM readaloud_segments s JOIN readaloud_projects p ON p.id=s.project_id
                LEFT JOIN readaloud_characters c ON c.id=s.speaker_id
                LEFT JOIN readaloud_voice_profiles vp ON vp.id=c.voice_profile_id
                WHERE s.id=? AND s.project_id=? AND p.owner_user_id=? AND s.deleted_at IS NULL""",
                (segment_id, project_id, owner_user_id)).fetchone()
            if row is None:
                raise ResourceNotFoundError("readaloud_segment", segment_id)
        expected = self._segment_request(row, model_id)
        path = self._matching_output(owner_user_id, project_id, segment_id, expected)
        if path is None:
            return None
        self._save_line_audio(owner_user_id, project_id, segment_id, expected, path)
        return {"segmentId": segment_id, "url": f"/v1/platform/readaloud/projects/{project_id}/segments/{segment_id}/audio/content?" + urlencode({"model_id": model_id})}

    def line_audio_path(self, owner, project_id, segment_id, model_id):
        if self.cached_segment(owner, project_id, segment_id, model_id) is None:
            raise ResourceNotFoundError("line_audio", segment_id)
        directory = self._line_cache_dir(owner, project_id, segment_id)
        return directory / json.loads((directory / 'current.json').read_text())['file']

    def _line_cache_dir(self, owner, project_id, segment_id):
        key = hashlib.sha256(f"{owner}/{project_id}/{segment_id}".encode()).hexdigest()
        return self.root / "line-audio" / key

    @staticmethod
    def _audio_warnings(path):
        try:
            return json.loads(path.with_suffix('.warnings.json').read_text())
        except (OSError, ValueError):
            return []

    def _save_line_audio(self, owner, project_id, segment_id, request, source):
        directory = self._line_cache_dir(owner, project_id, segment_id)
        directory.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(_json(request).encode()).hexdigest()
        target = directory / (key + '.wav')
        temporary = directory / (uuid.uuid4().hex + '.tmp')
        shutil.copyfile(source, temporary)
        os.replace(temporary, target)
        target.with_suffix('.warnings.json').write_text(_json(self._audio_warnings(source)))
        manifest = directory / (uuid.uuid4().hex + '.tmp')
        manifest.write_text(_json({'request': request, 'file': target.name}))
        os.replace(manifest, directory / 'current.json')
        for previous in directory.glob('*.wav'):
            if previous != target:
                previous.unlink(missing_ok=True)
                previous.with_suffix('.warnings.json').unlink(missing_ok=True)
        return target

    def _private_line_audio(self, owner, project_id, segment_id, request):
        directory = self._line_cache_dir(owner, project_id, segment_id)
        try:
            record = json.loads((directory / 'current.json').read_text())
            path = directory / record['file']
            if record['request'] == request and path.is_file():
                return path
        except (OSError, ValueError, KeyError):
            pass
        return None

    def _matching_output(self, owner, project_id, segment_id, request):
        private = self._private_line_audio(owner, project_id, segment_id, request)
        if private:
            return private
        with self.database.transaction() as connection:
            rows = connection.execute("""SELECT s.output_path,s.request_json,s.artifact_id,a.status AS artifact_status
                FROM readaloud_render_segments s JOIN readaloud_render_jobs j ON j.id=s.job_id
                LEFT JOIN artifacts a ON a.id=s.artifact_id
                WHERE j.owner_user_id=? AND j.project_id=? AND s.segment_id=? AND s.status='succeeded'
                ORDER BY s.completed_at DESC""", (owner, project_id, segment_id)).fetchall()
        for row in rows:
            if row["artifact_id"] and row["artifact_status"] != "active":
                continue
            path = self.root / row["output_path"]
            if json.loads(row["request_json"]) == request and path.is_file():
                return path
        return None

    def _merge_dialogue(self, job):
        with self.database.transaction() as connection:
            lines = connection.execute("SELECT * FROM readaloud_render_segments WHERE job_id=? ORDER BY ordinal", (job["id"],)).fetchall()
        output = self.root / job["id"] / "dialogue.wav"
        with wave.open(str(output), 'wb') as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(24000)
            for index, line in enumerate(lines):
                content = decode_audio_to_wav((self.root / line["output_path"]).read_bytes(), input_format='wav', sample_rate=24000, max_duration_seconds=600)
                with wave.open(BytesIO(content), 'rb') as source:
                    target.writeframes(source.readframes(source.getnframes()))
                if index < len(lines) - 1:
                    pause = json.loads(line["request_json"]).get('pauseAfterMs', 0)
                    target.writeframes(b'\0' * (24000 * int(pause) // 1000 * 2))
        session_id = self._artifact_session(job["owner_user_id"])
        artifact = self.workspace.import_artifact(session_id, output, f"{job['id']}-dialogue.wav", media_type='audio/wav', metadata={'dialogueJobId':job['id'], 'projectId':job['project_id'], 'warnings': [f"Line {i + 1}: {warning}" for i, line in enumerate(lines) for warning in self._audio_warnings(self.root / line['output_path'])]})
        self._record_studio_artifact(job, {"ordinal": 0}, artifact)
        with self.database.transaction(write=True) as connection:
            connection.execute("UPDATE readaloud_render_jobs SET merged_artifact_id=?,merged_session_id=? WHERE id=?", (artifact.id,session_id,job['id']))

    async def _dispatch(self) -> None:
        while True:
            job_id = await self._queue.get()
            if self._closing:
                return
            task = asyncio.create_task(self._run(job_id), name=f"readaloud-{job_id}")
            self._running[job_id] = task
            try:
                await task
            except asyncio.CancelledError:
                if self._closing:
                    raise
            finally:
                self._running.pop(job_id, None)
                self._queue.task_done()

    async def _run(self, job_id: str) -> None:
        try:
            with self.database.transaction() as connection:
                job = connection.execute(
                    "SELECT * FROM readaloud_render_jobs WHERE id=?", (job_id,)
                ).fetchone()
                if job is None or job["status"] == "cancelled":
                    return
                segments = connection.execute(
                    "SELECT * FROM readaloud_render_segments "
                    "WHERE job_id=? AND status!='succeeded' ORDER BY ordinal",
                    (job_id,),
                ).fetchall()
            now = utc_now_text()
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    "UPDATE readaloud_render_jobs SET status='running',"
                    "started_at=COALESCE(started_at,?),updated_at=? WHERE id=?",
                    (now, now, job_id),
                )
            self._sync_studio_run(job_id, "running", 0, "Preparing audio segments")
            for segment in segments:
                await self._render_segment(job, segment)
            if job["merge_output"]:
                await asyncio.to_thread(self._merge_dialogue, job)
            now = utc_now_text()
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    "UPDATE readaloud_render_jobs SET status='succeeded',"
                    "completed_segments=total_segments,completed_at=?,updated_at=? "
                    "WHERE id=? AND status!='cancelled'",
                    (now, now, job_id),
                )
            self._sync_studio_run(job_id, "succeeded", 100, "Audio render complete")
            scope = self._studio_scope(job_id)
            if scope is not None:
                self.prune_studio_history(dict(scope))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            now = utc_now_text()
            error = {"code": getattr(exc, "code", "render_failed"), "message": str(exc)}
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    "UPDATE readaloud_render_segments SET status='failed',error_json=?,"
                    "completed_at=?,updated_at=? WHERE job_id=? AND status!='succeeded'",
                    (_json(error), now, now, job_id),
                )
                connection.execute(
                    "UPDATE readaloud_render_jobs SET status='failed',error_json=?,"
                    "completed_at=?,updated_at=? WHERE id=? AND status!='cancelled'",
                    (_json(error), now, now, job_id),
                )
            self._sync_studio_run(job_id, "failed", 0, str(exc), error=error)

    async def _render_segment(self, job, segment) -> None:
        request = json.loads(segment["request_json"])
        model = self._model(request.get("model") or job["model_id"])
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE readaloud_render_segments SET status='running',"
                "started_at=COALESCE(started_at,?),updated_at=? "
                "WHERE job_id=? AND segment_id=?",
                (now, now, job["id"], segment["segment_id"]),
            )
        output = self._matching_output(job["owner_user_id"], job["project_id"], segment["segment_id"], request) if job["merge_output"] else None
        if output is not None:
            target = self.root / job["id"] / f"{segment['segment_id']}.wav"
            target.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(shutil.copyfile, output, target)
            target.with_suffix('.warnings.json').write_text(_json(self._audio_warnings(output)))
            output = target
        else:
            output = await self._invoke(job["id"], segment["segment_id"], model, request, job["owner_user_id"])
        now = utc_now_text()
        relative = str(output.relative_to(self.root))
        await asyncio.to_thread(self._save_line_audio, job["owner_user_id"], job["project_id"], segment["segment_id"], request, output)
        artifact = None if job["merge_output"] else self._materialize_artifact(job, segment, output)
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE readaloud_render_segments SET status='succeeded',"
                "output_path=?,artifact_session_id=?,artifact_id=?,completed_at=?,updated_at=? "
                "WHERE job_id=? AND segment_id=?",
                (
                    relative,
                    None if artifact is None else artifact.session_id,
                    None if artifact is None else artifact.id,
                    now,
                    now,
                    job["id"],
                    segment["segment_id"],
                ),
            )
            connection.execute(
                "UPDATE readaloud_render_jobs SET completed_segments="
                "completed_segments+1,updated_at=? WHERE id=?",
                (now, job["id"]),
            )
            completed_row = connection.execute(
                "SELECT completed_segments,total_segments FROM readaloud_render_jobs WHERE id=?",
                (job["id"],),
            ).fetchone()
        completed = int(completed_row["completed_segments"] or 0)
        total = int(completed_row["total_segments"] or 1)
        self._sync_studio_run(
            str(job["id"]),
            "running",
            round(completed * 100 / total),
            f"Rendered {completed} of {total} audio segments",
        )

    async def _invoke(
        self, job_id: str, segment_id: str, model, request, owner_user_id: str
    ) -> Path:
        payload = {
            "model": model.id,
            "input": request["input"],
            "response_format": "wav",
        }
        tts = (getattr(model, 'audio_capabilities', None) or {}).get('tts', {})
        if tts.get('speed', {}).get('mode', 'unsupported') != 'unsupported':
            payload['speed'] = request['speed']
        if request.get("voice"):
            payload["voice"] = request["voice"]
        emotion_caps = tts.get('emotion', {})
        # Unsupported expression falls back to the model's natural delivery.
        if (request.get('emotion') not in {None, 'neutral'}
                and emotion_caps.get('mode', 'unsupported') != 'unsupported'
                and request['emotion'] in emotion_caps.get('values', [])):
            payload["style"] = {
                "emotion": request["emotion"],
                "emotion_strength": request.get("emotionStrength", 1.0),
            }
        invocations = getattr(self.runtime, "model_invocations", None)
        if invocations is None:
            raise ReadAloudRenderError(
                "model_gateway_unavailable", "Model invocation service is unavailable"
            )
        context_factory = getattr(invocations, "context_for_actor", None)
        context = (
            None
            if context_factory is None
            else context_factory(
                owner_user_id,
                session_id=f"readaloud:{job_id}",
                consumer_app_id="ai2apps.readaloud",
            )
        )
        training = request.get('voiceTraining') or {}
        options = {"request_id": f"readaloud-{job_id}-{segment_id}", **({"context": context} if context is not None else {})}
        warnings = []
        if request.get('asrVerification', False):
            from ai2apps.model_providers import list_package_models
            asr_model = next((item for item in list_package_models(self.runtime)
                              if item.model_type == 'audio_stt' and item.checkpoint_ready
                              and (not request.get('asrModelId') or item.id == request['asrModelId'])), None)
            if asr_model is not None:
                options['verifier'] = speech_verifier(invocations.invoke_background_multipart,
                    asr_model.id, request_id=options['request_id'], context=context)
            else:
                warnings.append('未找到可用 ASR 模型或所选模型不可用；本行未校验朗读文字，IndexTTS 仍检测长静音并细分恢复。')
        options['warnings'] = warnings
        if training.get('samples'):
            try:
                store = VoiceMaterials(self.database, self.runtime.config.paths.artifacts_path)
                spec, samples, files = await asyncio.to_thread(prepare, model, training['samples'], store, owner_user_id, for_execution=True)
                if not spec['executable']:
                    raise ValueError('The selected character model does not support reference preview execution.')
                if training.get('model_revision') is not None and training['model_revision'] != spec['revision']:
                    raise ValueError('The character model version changed. Rebind and preview the character again.')
                reference_audio, reference_text = combined_reference(samples, files)
            except (ValueError, ResourceNotFoundError) as error:
                raise ReadAloudRenderError('invalid_character_reference', str(error)) from error
            payload.pop('voice', None)
            if reference_text:
                payload['ref_text'] = reference_text
            # Keep the multipart parameters aligned with character preview.
            if payload.get('style'):
                style = payload.pop('style')
                payload['emotion'] = style['emotion']
                payload['emotion_strength'] = style['emotion_strength']
            response = await invoke_speech(invocations.invoke_background_multipart,
                model.id, 'audio_speech', data=payload,
                files={'reference_audio': ('reference.wav', reference_audio, 'audio/wav')}, **options)
        else:
            design = training.get('design') or {}
            if design.get('description'):
                payload['instructions'] = design['description']
            response = await invoke_speech(invocations.invoke_background_json, model.id, 'audio_speech', payload, **options)
        if response.status_code >= 400:
            detail = ''
            try:
                body = json.loads(response.body)
                detail = (body.get('error') or {}).get('message', '') if isinstance(body.get('error'), dict) else body.get('detail', '')
            except (ValueError, TypeError, AttributeError):
                pass
            raise ReadAloudRenderError(
                "speech_generation_failed",
                f"Speech Worker returned HTTP {response.status_code}" + (f": {str(detail)[:500]}" if detail else ''),
                status_code=502,
            )
        content = bytes(response.body)
        if not content or len(content) > MAX_AUDIO_BYTES:
            raise ReadAloudRenderError("invalid_audio", "Speech output size is invalid")
        target = self.root / job_id / f"{segment_id}.wav"
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        await asyncio.to_thread(target.write_bytes, content)
        target.with_suffix('.warnings.json').write_text(_json(warnings))
        return target

    def save_quick_audio(self, owner_user_id: str, content: bytes, *, title: str = "", model_label: str = "", voice: str = "", mini_app_id: str = "ai2apps.audio.quick-read", warnings: list[str] | None = None) -> str:
        """Use the shared, owner-authorized Artifact download route for Save As."""
        if self.workspace is None:
            raise ReadAloudRenderError("workspace_unavailable", "Audio storage is not ready", status_code=503)
        session_id = self._artifact_session(owner_user_id)
        name = f"quick-read-{uuid.uuid4().hex}.wav"
        source = self.root / name
        try:
            source.write_bytes(content)
            artifact = self.workspace.import_artifact(
                session_id, source, name, media_type="audio/wav",
                metadata={"studioId": "ai2apps.readaloud", "miniAppId": mini_app_id, "title": title, "model": model_label, "actor": voice, "warnings": warnings or []},
            )
        finally:
            source.unlink(missing_ok=True)
        self.quick_history(owner_user_id, mini_app_id=mini_app_id)
        return f"/v1/platform/sessions/{session_id}/artifacts/{artifact.id}/download"

    def save_separation_output(self, owner_user_id: str, content: bytes, filename: str) -> dict:
        if self.workspace is None:
            raise ReadAloudRenderError("workspace_unavailable", "Audio storage is not ready", status_code=503)
        session_id = self._artifact_session(owner_user_id)
        mini_app_id = "ai2apps.media-voice.source-separation"
        title = Path(filename).stem[:100] or "Separated audio"
        batch = uuid.uuid4().hex[:8]
        created = []
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive, tempfile.TemporaryDirectory(dir=self.root) as temp:
                members = [item for item in archive.infolist() if item.filename.lower().endswith('.wav')]
                if not 1 <= len(members) <= 8 or sum(item.file_size for item in members) > 4 * 1024**3:
                    raise ValueError("Invalid separation archive")
                for index, item in enumerate(members):
                    if item.file_size > 1024**3:
                        raise ValueError("Separated track is too large")
                    name = Path(item.filename).name
                    target = Path(temp) / f"track-{index}.wav"
                    with archive.open(item) as source, target.open('wb') as output:
                        shutil.copyfileobj(source, output)
                    with wave.open(str(target), 'rb') as wav:
                        if wav.getnframes() == 0:
                            raise ValueError("Separated track is empty")
                    created.append(self.workspace.import_artifact(session_id, target, f"{title}-{batch}-{name}", media_type="audio/wav",
                        metadata={"studioId": "ai2apps.readaloud", "miniAppId": mini_app_id, "title": f"{title} · {Path(name).stem}", "model": "MLX Demucs"}))
                target = Path(temp) / "separated.zip"
                target.write_bytes(content)
                bundle = self.workspace.import_artifact(session_id, target, f"{title}-{batch}-separated.zip", media_type="application/zip",
                    metadata={"studioId": "ai2apps.readaloud", "miniAppId": mini_app_id + ".archive"})
                created.append(bundle)
            history = self.quick_history(owner_user_id, mini_app_id=mini_app_id)
            ids = {item.id for item in created[:-1]}
            # ZIP history is bounded independently of the individual audio tracks.
            self.quick_history(owner_user_id, mini_app_id=mini_app_id + ".archive")
            return {"filename": bundle.name, "size": len(content),
                    "downloadUrl": f"/v1/platform/sessions/{session_id}/artifacts/{bundle.id}/download",
                    "tracks": [item for item in history if item['id'] in ids]}
        except Exception:
            for item in created:
                self.workspace.retire_artifact(session_id, item.id)
            raise

    def output_history(self, owner_user_id: str) -> list[dict[str, Any]]:
        """The single owner-scoped Voice Studio output feed; never contains line caches."""
        session_id = self._artifact_session(owner_user_id)
        records = [item for item in self.workspace.list_artifacts(session_id)
                   if (item.metadata.get("studioId") == "ai2apps.readaloud" or item.metadata.get("dialogueJobId"))
                   and not str(item.metadata.get("miniAppId", "")).endswith(".archive")]
        records.sort(key=lambda item: item.created_at, reverse=True)
        for item in records[20:]:
            self.workspace.retire_artifact(session_id, item.id)
        return [{"id": item.id, "title": item.metadata.get("title") or item.name,
                 "model": item.metadata.get("model", ""), "actor": item.metadata.get("actor", ""),
                 "miniAppId": item.metadata.get("miniAppId", "ai2apps.audio.audiobook"),
                 "warnings": item.metadata.get("warnings", []),
                 "mediaType": item.media_type, "createdAt": item.created_at.isoformat(), "status": "succeeded",
                 "url": f"/v1/platform/sessions/{session_id}/artifacts/{item.id}/download",
                 "downloadUrl": f"/v1/platform/sessions/{session_id}/artifacts/{item.id}/download"}
                for item in records[:20]]

    def save_studio_output(self, owner_user_id: str, content: bytes, *, mini_app_id: str, filename: str, media_type: str) -> str:
        session_id = self._artifact_session(owner_user_id)
        with tempfile.TemporaryDirectory(dir=self.root) as temp:
            source = Path(temp) / "output"
            source.write_bytes(content)
            artifact = self.workspace.import_artifact(session_id, source, f"{uuid.uuid4().hex[:8]}-{Path(filename).name}",
                media_type=media_type, metadata={"studioId": "ai2apps.readaloud", "miniAppId": mini_app_id, "title": filename})
        self.output_history(owner_user_id)
        return f"/v1/platform/sessions/{session_id}/artifacts/{artifact.id}/download"

    def quick_history(self, owner_user_id: str, *, mini_app_id: str = "ai2apps.audio.quick-read") -> list[dict[str, Any]]:
        if self.workspace is None:
            raise ReadAloudRenderError("workspace_unavailable", "Audio storage is not ready", status_code=503)
        session_id = self._artifact_session(owner_user_id)
        records = [item for item in self.workspace.list_artifacts(session_id)
                   if item.metadata.get("miniAppId") == mini_app_id]
        for item in records[20:]:
            self.workspace.retire_artifact(session_id, item.id)
        records = records[:20]
        return [{
            "id": item.id, "title": item.metadata.get("title") or item.name,
            "model": item.metadata.get("model", ""), "actor": item.metadata.get("actor", ""),
            "createdAt": item.created_at.isoformat(), "status": "succeeded",
            "url": f"/v1/platform/sessions/{session_id}/artifacts/{item.id}/download",
            "downloadUrl": f"/v1/platform/sessions/{session_id}/artifacts/{item.id}/download",
        } for item in records]

    def _artifact_session(self, owner_user_id: str) -> str:
        cached = self._artifact_sessions.get(owner_user_id)
        if cached:
            return cached
        package_id = "ai2apps.readaloud"
        singleton_key = user_singleton_key(package_id, owner_user_id)
        with self.database.transaction() as connection:
            row = connection.execute(
                """SELECT s.id FROM sessions s
                   JOIN app_instances i ON i.id=s.app_instance_id
                   JOIN app_definitions d ON d.id=i.app_definition_id
                   WHERE d.package_id=? AND i.owner_user_id=? AND s.is_home=1
                     AND s.status='active'
                   ORDER BY s.created_at LIMIT 1""",
                (package_id, owner_user_id),
            ).fetchone()
            definition = connection.execute(
                "SELECT id FROM app_definitions WHERE package_id=? ORDER BY created_at LIMIT 1",
                (package_id,),
            ).fetchone()
        if row is not None:
            session_id = str(row["id"])
            self._artifact_sessions[owner_user_id] = session_id
            return session_id
        if definition is None:
            raise ReadAloudRenderError(
                "studio_instance_unavailable",
                "Voice Studio App definition is unavailable",
                status_code=503,
            )
        apps = AppRepository(self.database)
        sessions = SessionRepository(self.database)
        with self.database.transaction() as connection:
            existing = connection.execute(
                "SELECT id FROM app_instances WHERE singleton_key=?",
                (singleton_key,),
            ).fetchone()
        if existing is None:
            instance = apps.create_instance(
                app_definition_id=str(definition["id"]),
                singleton_key=singleton_key,
                owner_user_id=owner_user_id,
                status=AppInstanceStatus.ACTIVE,
            )
            instance_id = instance.id
        else:
            instance_id = str(existing["id"])
        session = sessions.create(
            app_instance_id=instance_id,
            title="Voice Studio",
            is_home=True,
            session_kind=SessionKind.APP,
            visibility=SessionVisibility.UNLISTED,
            retention=SessionRetention.DURABLE,
        )
        self._artifact_sessions[owner_user_id] = session.id
        return session.id

    def _materialize_artifact(self, job, segment, output: Path):
        if self.workspace is None:
            return None
        session_id = self._artifact_session(str(job["owner_user_id"]))
        model = self._model(str(job["model_id"]))
        artifact = self.workspace.import_artifact(
            session_id,
            output,
            f"{job['id']}-{int(segment['ordinal']) + 1:03d}.wav",
            # Workspace run_id references agent_runs, not Studio/render jobs.
            # Preserve the Studio association in metadata and studio_artifacts.
            media_type="audio/wav",
            metadata={
                "schema": "ai2apps.studio-artifact/v1",
                "studioId": "ai2apps.readaloud",
                "miniAppId": job["mini_app_id"],
                "placement": job["placement"],
                "pipeline": "ai2apps.pipeline.speech-generation",
                "model": job["model_id"],
                "modelRevision": job["model_revision"],
                "runId": job["id"],
                "stepId": segment["segment_id"],
                "warnings": self._audio_warnings(output),
                "generator": getattr(model, "service_key", "audio.speech_generation"),
            },
        )
        self._record_studio_artifact(job, segment, artifact)
        return artifact

    def _studio_scope(self, run_id: str):
        with self.database.transaction() as connection:
            return connection.execute(
                "SELECT actor_id,installation_id,app_instance_id,studio_id "
                "FROM studio_runs WHERE id=?",
                (run_id,),
            ).fetchone()

    def _sync_studio_run(
        self,
        run_id: str,
        status: str,
        progress: int,
        detail: str,
        *,
        error: dict[str, Any] | None = None,
    ) -> None:
        scope = self._studio_scope(run_id)
        if scope is None:
            return
        try:
            StudioRepository(self.database).update_run(
                run_id,
                actor_id=scope["actor_id"],
                installation_id=scope["installation_id"],
                app_instance_id=scope["app_instance_id"],
                studio_id=scope["studio_id"],
                status=status,
                progress=progress,
                detail=detail,
                error=error,
            )
        except StudioRepositoryError:
            return

    def _record_studio_artifact(self, job, segment, artifact) -> None:
        scope = self._studio_scope(str(job["id"]))
        if scope is None:
            return
        url = (
            f"/v1/platform/sessions/{artifact.session_id}/artifacts/"
            f"{artifact.id}/download"
        )
        try:
            StudioRepository(self.database).create_artifact(
                str(job["id"]),
                actor_id=scope["actor_id"],
                installation_id=scope["installation_id"],
                app_instance_id=scope["app_instance_id"],
                studio_id=scope["studio_id"],
                kind="audio",
                name=artifact.name,
                media_type=artifact.media_type,
                preview_url=url,
                download_url=url,
                source_id=artifact.id,
                metadata={
                    **artifact.metadata,
                    "artifactSessionId": artifact.session_id,
                    "segmentOrdinal": int(segment["ordinal"]),
                },
            )
        except StudioRepositoryError:
            return

    def prune_studio_history(self, scope):
        with self.database.transaction() as connection:
            rows = connection.execute("""SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY mini_app_id ORDER BY created_at DESC,id DESC) AS position
                FROM studio_runs WHERE actor_id=? AND installation_id=? AND app_instance_id=? AND studio_id=?
                AND status IN ('succeeded','failed','cancelled','expired')) WHERE position>20""",
                (scope['actor_id'], scope['installation_id'], scope['app_instance_id'], scope['studio_id'])).fetchall()
        for row in rows:
            try:
                self.delete(row['id'], owner_user_id=scope['actor_id'])
            except ResourceNotFoundError:
                pass
            StudioRepository(self.database).delete_run(row['id'], **scope)

    def delete(self, job_id: str, *, owner_user_id: str):
        job = self.get(job_id, owner_user_id=owner_user_id)
        if job['status'] not in {'succeeded','failed','cancelled','expired'}:
            raise ReadAloudRenderError('job_active','Stop the task before deleting it',status_code=409)
        for segment in job['segments']:
            source = self.root / (segment.get('output_path') or 'missing')
            directory = self._line_cache_dir(owner_user_id, job['project_id'], segment['segment_id'])
            if not (directory / 'current.json').exists():
                # Seed legacy lines from their newest output before pruning old runs.
                with self.database.transaction() as connection:
                    saved = connection.execute('''SELECT s.output_path,s.request_json FROM readaloud_render_segments s
                        JOIN readaloud_render_jobs j ON j.id=s.job_id
                        WHERE j.owner_user_id=? AND j.project_id=? AND s.segment_id=? AND s.status='succeeded'
                        ORDER BY s.completed_at DESC''', (owner_user_id,job['project_id'],segment['segment_id'])).fetchall()
                for item in saved:
                    source = self.root / item['output_path']
                    if source.is_file():
                        self._save_line_audio(owner_user_id, job['project_id'], segment['segment_id'], json.loads(item['request_json']), source)
                        break
            if segment.get('artifact_session_id') and segment.get('artifact_id'):
                self.workspace.retire_artifact(segment['artifact_session_id'],segment['artifact_id'])
        if job.get('merged_artifact_id') and job.get('merged_session_id'):
            self.workspace.retire_artifact(job['merged_session_id'], job['merged_artifact_id'])
        job_root = (self.root / job_id).resolve()
        job_root.relative_to(self.root)
        shutil.rmtree(job_root,ignore_errors=True)
        with self.database.transaction(write=True) as connection:
            connection.execute('DELETE FROM readaloud_render_jobs WHERE id=? AND owner_user_id=?',(job_id,owner_user_id))

    def get(self, job_id: str, *, owner_user_id: str) -> dict[str, Any]:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM readaloud_render_jobs WHERE id=? AND owner_user_id=?",
                (job_id, owner_user_id),
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("readaloud_render_job", job_id)
            segments = connection.execute(
                "SELECT * FROM readaloud_render_segments WHERE job_id=? ORDER BY ordinal",
                (job_id,),
            ).fetchall()
        value = dict(row)
        if value.get("merged_artifact_id"):
            value["mergedAudio"] = f"/v1/platform/sessions/{value['merged_session_id']}/artifacts/{value['merged_artifact_id']}/download"
        value["error"] = json.loads(value.pop("error_json") or "null")
        value["segments"] = []
        for segment in segments:
            item = dict(segment)
            item["request"] = json.loads(item.pop("request_json"))
            item["error"] = json.loads(item.pop("error_json") or "null")
            if item.get("artifact_id") and item.get("artifact_session_id"):
                session_id = item["artifact_session_id"]
                artifact_id = item["artifact_id"]
                item["artifact"] = {
                    "id": artifact_id,
                    "session_id": session_id,
                    "uri": f"artifact://{artifact_id}",
                    "name": f"{value['id']}-{int(item['ordinal']) + 1:03d}.wav",
                    "media_type": "audio/wav",
                    "download_url": (
                        f"/v1/platform/sessions/{session_id}/artifacts/"
                        f"{artifact_id}/download"
                    ),
                    "metadata": {
                        "miniAppId": value.get("mini_app_id"),
                        "placement": value.get("placement"),
                        "model": value.get("model_id"),
                        "modelRevision": value.get("model_revision"),
                        "runId": value["id"],
                        "stepId": item["segment_id"],
                    },
                }
            value["segments"].append(item)
        return value

    def list(
        self,
        *,
        owner_user_id: str,
        project_id: str | None = None,
        limit: int = 50,
    ) -> tuple[dict[str, Any], ...]:
        query = "SELECT id FROM readaloud_render_jobs WHERE owner_user_id=?"
        parameters: list[Any] = [owner_user_id]
        if project_id:
            query += " AND project_id=?"
            parameters.append(project_id)
        query += " ORDER BY created_at DESC,id DESC LIMIT ?"
        parameters.append(max(1, min(100, int(limit))))
        with self.database.transaction() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()
        return tuple(self.get(str(row["id"]), owner_user_id=owner_user_id) for row in rows)

    async def retry(self, job_id: str, *, owner_user_id: str) -> dict[str, Any]:
        source = self.get(job_id, owner_user_id=owner_user_id)
        if source["status"] not in {"failed", "cancelled"}:
            raise ReadAloudRenderError(
                "run_not_retryable", "Only failed or cancelled runs can be retried"
            )
        return await self.create(
            owner_user_id=owner_user_id,
            project_id=source["project_id"],
            model_id=source["model_id"],
            segment_ids=[item["segment_id"] for item in source["segments"]],
            mini_app_id=source.get("mini_app_id") or "ai2apps.audio.audiobook",
            placement=source.get("placement") or "ai2apps.readaloud",
        )


    async def cancel(self, job_id: str, *, owner_user_id: str) -> dict[str, Any]:
        self.get(job_id, owner_user_id=owner_user_id)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE readaloud_render_jobs SET status='cancelled',"
                "cancel_requested_at=?,completed_at=?,updated_at=? "
                "WHERE id=? AND status IN ('queued','running')",
                (now, now, now, job_id),
            )
            connection.execute(
                "UPDATE readaloud_render_segments SET status='cancelled',"
                "completed_at=?,updated_at=? WHERE job_id=? AND status IN ('queued','running')",
                (now, now, job_id),
            )
        task = self._running.get(job_id)
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._sync_studio_run(job_id, "cancelled", 0, "Run cancelled")
        return self.get(job_id, owner_user_id=owner_user_id)
