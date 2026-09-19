"""Durable, scheduler-aware batch rendering for Voice Studio."""

from __future__ import annotations

import asyncio
import json
import uuid
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
                SELECT s.*,vp.provider_voice_id
                FROM readaloud_segments s
                LEFT JOIN readaloud_characters c ON c.id=s.speaker_id
                LEFT JOIN readaloud_voice_profiles vp ON vp.id=c.voice_profile_id
                WHERE s.project_id=? AND s.review_status='approved'
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
                request = {
                    "model": model_id,
                    "input": row["text"],
                    "speed": row["speed"],
                    "emotion": row["emotion"],
                    "emotionStrength": row["emotion_strength"],
                    "voice": row["provider_voice_id"],
                    "pauseAfterMs": row["pause_after_ms"],
                }
                connection.execute(
                    """
                    INSERT INTO readaloud_render_segments(
                        job_id,segment_id,ordinal,status,request_json,updated_at
                    ) VALUES (?,?,?,'queued',?,?)
                    """,
                    (job_id, row["id"], ordinal, _json(request), now),
                )
        self._queue.put_nowait(job_id)
        return self.get(job_id, owner_user_id=owner_user_id)

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
            now = utc_now_text()
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    "UPDATE readaloud_render_jobs SET status='succeeded',"
                    "completed_segments=total_segments,completed_at=?,updated_at=? "
                    "WHERE id=? AND status!='cancelled'",
                    (now, now, job_id),
                )
            self._sync_studio_run(job_id, "succeeded", 100, "Audio render complete")
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
        model = self._model(job["model_id"])
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE readaloud_render_segments SET status='running',"
                "started_at=COALESCE(started_at,?),updated_at=? "
                "WHERE job_id=? AND segment_id=?",
                (now, now, job["id"], segment["segment_id"]),
            )
        output = await self._invoke(
            job["id"], segment["segment_id"], model, request, job["owner_user_id"]
        )
        now = utc_now_text()
        relative = str(output.relative_to(self.root))
        artifact = self._materialize_artifact(job, segment, output)
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
            "speed": request["speed"],
        }
        if request.get("voice"):
            payload["voice"] = request["voice"]
        if request.get("emotion") not in {None, "neutral"}:
            payload["style"] = {"emotion": request["emotion"]}
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
        response = await invocations.invoke_background_json(
            model.id,
            "audio_speech",
            payload,
            request_id=f"readaloud-{job_id}-{segment_id}",
            **({"context": context} if context is not None else {}),
        )
        if response.status_code >= 400:
            raise ReadAloudRenderError(
                "speech_generation_failed",
                f"Speech Worker returned HTTP {response.status_code}",
                status_code=502,
            )
        content = bytes(response.body)
        if not content or len(content) > MAX_AUDIO_BYTES:
            raise ReadAloudRenderError("invalid_audio", "Speech output size is invalid")
        target = self.root / job_id / f"{segment_id}.wav"
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        await asyncio.to_thread(target.write_bytes, content)
        return target

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
            run_id=str(job["id"]),
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
