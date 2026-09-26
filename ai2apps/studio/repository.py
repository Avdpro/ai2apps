"""Principal-scoped persistence for Studio shells and their Mini-Apps."""

from __future__ import annotations

import json
import uuid
from typing import Any

from ai2apps.core import utc_now_text
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.records import canonical_json

RUN_STATUSES = {
    "draft", "queued", "running", "waiting_input", "succeeded", "failed",
    "cancelled", "expired",
}
STEP_STATUSES = {"pending", "running", "succeeded", "failed", "skipped", "cancelled"}
TERMINAL_RUN_STATUSES = {"succeeded", "failed", "cancelled", "expired"}


class StudioRepositoryError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int = 422) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class StudioRepository:
    """Generic durable object model shared by media Studio shells."""

    def __init__(self, database: PlatformDatabase) -> None:
        self.database = database

    @staticmethod
    def _id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    @staticmethod
    def _json(value: str | None, fallback):
        try:
            return json.loads(value or "")
        except (TypeError, json.JSONDecodeError):
            return fallback

    @classmethod
    def _step(cls, row) -> dict[str, Any]:
        return {
            "id": row["id"], "runId": row["run_id"], "position": row["position"],
            "label": row["label"], "status": row["status"], "progress": row["progress"],
            "detail": row["detail"], "startedAt": row["started_at"],
            "completedAt": row["completed_at"], "updatedAt": row["updated_at"],
        }

    @classmethod
    def _artifact(cls, row) -> dict[str, Any]:
        return {
            "id": row["id"], "runId": row["run_id"], "stepId": row["step_id"],
            "kind": row["kind"], "name": row["name"], "mediaType": row["media_type"],
            "uri": f"artifact://{row['id']}", "previewUrl": row["preview_url"],
            "downloadUrl": row["download_url"], "final": bool(row["is_final"]),
            "sourceId": row["source_id"],
            "metadata": cls._json(row["metadata_json"], {}), "createdAt": row["created_at"],
        }

    @classmethod
    def _run(cls, row, steps=(), artifacts=()) -> dict[str, Any]:
        return {
            "id": row["id"], "studioId": row["studio_id"],
            "miniAppId": row["mini_app_id"], "miniAppVersion": row["mini_app_version"],
            "placement": row["placement"], "status": row["status"],
            "progress": row["progress"], "title": row["title"],
            "input": cls._json(row["input_json"], {}),
            "error": cls._json(row["error_json"], None), "retryOf": row["retry_of"],
            "createdAt": row["created_at"], "startedAt": row["started_at"],
            "completedAt": row["completed_at"], "updatedAt": row["updated_at"],
            "steps": list(steps), "artifacts": list(artifacts),
        }

    def save_draft(
        self, *, actor_id: str, installation_id: str, app_instance_id: str,
        studio_id: str, mini_app_id: str, draft: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                """SELECT id,created_at FROM studio_drafts WHERE actor_id=? AND installation_id=?
                   AND app_instance_id=? AND studio_id=? AND mini_app_id=?""",
                (actor_id, installation_id, app_instance_id, studio_id, mini_app_id),
            ).fetchone()
            draft_id = row["id"] if row else self._id("std")
            created_at = row["created_at"] if row else now
            connection.execute(
                """INSERT INTO studio_drafts(id,actor_id,installation_id,app_instance_id,
                   studio_id,mini_app_id,draft_json,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                   draft_json=excluded.draft_json,updated_at=excluded.updated_at""",
                (draft_id, actor_id, installation_id, app_instance_id, studio_id,
                 mini_app_id, canonical_json(draft), created_at, now),
            )
        return {"id": draft_id, "miniAppId": mini_app_id, "draft": draft, "updatedAt": now}

    def get_draft(
        self, *, actor_id: str, installation_id: str, app_instance_id: str,
        studio_id: str, mini_app_id: str,
    ) -> dict[str, Any] | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                """SELECT * FROM studio_drafts WHERE actor_id=? AND installation_id=?
                   AND app_instance_id=? AND studio_id=? AND mini_app_id=?""",
                (actor_id, installation_id, app_instance_id, studio_id, mini_app_id),
            ).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "miniAppId": mini_app_id,
                "draft": self._json(row["draft_json"], {}), "updatedAt": row["updated_at"]}

    def create_run(
        self, *, actor_id: str, installation_id: str, app_instance_id: str,
        studio_id: str, mini_app_id: str, mini_app_version: str, placement: str,
        title: str, input_data: dict[str, Any], retry_of: str | None = None,
        step_label: str = "Run Mini-App",
    ) -> dict[str, Any]:
        run_id, step_id, now = self._id("strun"), self._id("ststep"), utc_now_text()
        with self.database.transaction(write=True) as connection:
            if retry_of:
                owned = connection.execute(
                    """SELECT 1 FROM studio_runs WHERE id=? AND actor_id=? AND installation_id=?
                       AND app_instance_id=? AND studio_id=?""",
                    (retry_of, actor_id, installation_id, app_instance_id, studio_id),
                ).fetchone()
                if owned is None:
                    raise StudioRepositoryError("studio_run_not_found", "Retry source Run was not found", status_code=404)
            connection.execute(
                """INSERT INTO studio_runs(id,actor_id,installation_id,app_instance_id,studio_id,
                   mini_app_id,mini_app_version,placement,status,progress,title,input_json,error_json,
                   retry_of,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?, 'queued',0,?,?,NULL,?,?,?)""",
                (run_id, actor_id, installation_id, app_instance_id, studio_id, mini_app_id,
                 mini_app_version, placement, title[:160], canonical_json(input_data), retry_of, now, now),
            )
            connection.execute(
                """INSERT INTO studio_run_steps(id,run_id,position,label,status,progress,detail,
                   started_at,completed_at,updated_at) VALUES (?,?,0,?,'pending',0,'',NULL,NULL,?)""",
                (step_id, run_id, step_label[:160], now),
            )
        return self.get_run(run_id, actor_id=actor_id, installation_id=installation_id,
                            app_instance_id=app_instance_id, studio_id=studio_id)

    def _owned_row(self, connection, run_id: str, *, actor_id: str,
                   installation_id: str, app_instance_id: str, studio_id: str):
        row = connection.execute(
            """SELECT * FROM studio_runs WHERE id=? AND actor_id=? AND installation_id=?
               AND app_instance_id=? AND studio_id=?""",
            (run_id, actor_id, installation_id, app_instance_id, studio_id),
        ).fetchone()
        if row is None:
            raise StudioRepositoryError("studio_run_not_found", "Studio Run was not found", status_code=404)
        return row

    def get_run(self, run_id: str, *, actor_id: str, installation_id: str,
                app_instance_id: str, studio_id: str) -> dict[str, Any]:
        with self.database.transaction() as connection:
            row = self._owned_row(connection, run_id, actor_id=actor_id,
                                  installation_id=installation_id,
                                  app_instance_id=app_instance_id, studio_id=studio_id)
            steps = [self._step(value) for value in connection.execute(
                "SELECT * FROM studio_run_steps WHERE run_id=? ORDER BY position,id", (run_id,)
            ).fetchall()]
            artifacts = [self._artifact(value) for value in connection.execute(
                "SELECT * FROM studio_artifacts WHERE run_id=? ORDER BY created_at,id", (run_id,)
            ).fetchall()]
        return self._run(row, steps, artifacts)

    def delete_run(self, run_id, workspace=None, **scope):
        run = self.get_run(run_id, **scope)
        if run['status'] not in TERMINAL_RUN_STATUSES and run['status'] != 'draft':
            raise StudioRepositoryError('run_active', 'Stop the task before deleting it', status_code=409)
        for artifact in run['artifacts']:
            metadata = artifact.get('metadata') or {}
            if workspace is not None and metadata.get('workspaceSessionId') and metadata.get('workspaceArtifactId'):
                workspace.retire_artifact(metadata['workspaceSessionId'], metadata['workspaceArtifactId'])
        with self.database.transaction(write=True) as connection:
            self._owned_row(connection, run_id, **scope)
            connection.execute('DELETE FROM studio_artifacts WHERE run_id=?', (run_id,))
            connection.execute('DELETE FROM studio_run_steps WHERE run_id=?', (run_id,))
            connection.execute('DELETE FROM studio_runs WHERE id=?', (run_id,))
        return run

    def prune_output_history(self, workspace, *, actor_id: str, installation_id: str,
                             app_instance_id: str, studio_id: str) -> None:
        """Keep twenty terminal runs per Mini-App, including their owned outputs."""
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT id FROM (
                    SELECT id,ROW_NUMBER() OVER (
                        PARTITION BY mini_app_id ORDER BY created_at DESC,id DESC) AS position
                    FROM studio_runs WHERE actor_id=? AND installation_id=?
                    AND app_instance_id=? AND studio_id=?
                    AND status IN ('succeeded','failed','cancelled','expired'))
                    WHERE position>20""",
                (actor_id, installation_id, app_instance_id, studio_id),
            ).fetchall()
        for row in rows:
            with self.database.transaction() as connection:
                artifacts = connection.execute(
                    "SELECT metadata_json FROM studio_artifacts WHERE run_id=?", (row["id"],)
                ).fetchall()
            for artifact in artifacts:
                metadata = self._json(artifact["metadata_json"], {})
                if metadata.get("workspaceSessionId") and metadata.get("workspaceArtifactId"):
                    workspace.retire_artifact(metadata["workspaceSessionId"], metadata["workspaceArtifactId"])
            with self.database.transaction(write=True) as connection:
                connection.execute("DELETE FROM studio_artifacts WHERE run_id=?", (row["id"],))
                connection.execute("DELETE FROM studio_runs WHERE id=?", (row["id"],))

    def list_runs(self, *, actor_id: str, installation_id: str, app_instance_id: str,
                  studio_id: str, limit: int = 50) -> tuple[dict[str, Any], ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT * FROM studio_runs WHERE actor_id=? AND installation_id=?
                   AND app_instance_id=? AND studio_id=? ORDER BY created_at DESC,id DESC LIMIT ?""",
                (actor_id, installation_id, app_instance_id, studio_id, max(1, min(100, limit))),
            ).fetchall()
            result = []
            for row in rows:
                steps = [self._step(value) for value in connection.execute(
                    "SELECT * FROM studio_run_steps WHERE run_id=? ORDER BY position,id", (row["id"],)
                ).fetchall()]
                artifacts = [self._artifact(value) for value in connection.execute(
                    "SELECT * FROM studio_artifacts WHERE run_id=? ORDER BY created_at,id", (row["id"],)
                ).fetchall()]
                result.append(self._run(row, steps, artifacts))
        return tuple(result)

    def update_run(self, run_id: str, *, actor_id: str, installation_id: str,
                   app_instance_id: str, studio_id: str, status: str,
                   progress: int, detail: str = "", error: dict[str, Any] | None = None) -> dict[str, Any]:
        if status not in RUN_STATUSES:
            raise StudioRepositoryError("studio_run_status_invalid", "Invalid Studio Run status")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            current = self._owned_row(connection, run_id, actor_id=actor_id,
                                      installation_id=installation_id,
                                      app_instance_id=app_instance_id, studio_id=studio_id)
            if current["status"] in TERMINAL_RUN_STATUSES and current["status"] != status:
                raise StudioRepositoryError("studio_run_terminal", "A terminal Studio Run cannot transition")
            started = current["started_at"] or (now if status == "running" else None)
            completed = now if status in TERMINAL_RUN_STATUSES else None
            connection.execute(
                """UPDATE studio_runs SET status=?,progress=?,error_json=?,started_at=?,
                   completed_at=?,updated_at=? WHERE id=?""",
                (status, max(0, min(100, progress)), canonical_json(error) if error else None,
                 started, completed, now, run_id),
            )
            step_status = {"queued": "pending", "running": "running", "waiting_input": "running",
                           "succeeded": "succeeded", "failed": "failed", "cancelled": "cancelled",
                           "expired": "failed", "draft": "pending"}[status]
            connection.execute(
                """UPDATE studio_run_steps SET status=?,progress=?,detail=?,
                   started_at=COALESCE(started_at,CASE WHEN ?='running' THEN ? END),
                   completed_at=CASE WHEN ? IN ('succeeded','failed','cancelled') THEN ? END,
                   updated_at=? WHERE run_id=? AND position=0""",
                (step_status, max(0, min(100, progress)), detail[:500], step_status, now,
                 step_status, now, now, run_id),
            )
        return self.get_run(run_id, actor_id=actor_id, installation_id=installation_id,
                            app_instance_id=app_instance_id, studio_id=studio_id)

    def create_artifact(self, run_id: str, *, actor_id: str, installation_id: str,
                        app_instance_id: str, studio_id: str, kind: str, name: str,
                        media_type: str, preview_url: str, download_url: str,
                        metadata: dict[str, Any], source_id: str) -> dict[str, Any]:
        now, artifact_id = utc_now_text(), self._id("sta")
        with self.database.transaction(write=True) as connection:
            self._owned_row(connection, run_id, actor_id=actor_id, installation_id=installation_id,
                            app_instance_id=app_instance_id, studio_id=studio_id)
            step = connection.execute(
                "SELECT id FROM studio_run_steps WHERE run_id=? ORDER BY position LIMIT 1", (run_id,)
            ).fetchone()
            connection.execute(
                """INSERT INTO studio_artifacts(id,run_id,step_id,kind,name,media_type,source_id,
                   preview_url,download_url,is_final,metadata_json,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,1,?,?)""",
                (artifact_id, run_id, step["id"] if step else None, kind, name[:255], media_type,
                 source_id, preview_url, download_url, canonical_json(metadata), now),
            )
            row = connection.execute("SELECT * FROM studio_artifacts WHERE id=?", (artifact_id,)).fetchone()
        return self._artifact(row)

    def get_artifact(self, artifact_id: str, *, actor_id: str, installation_id: str,
                     app_instance_id: str, studio_id: str) -> dict[str, Any]:
        with self.database.transaction() as connection:
            row = connection.execute(
                """SELECT a.* FROM studio_artifacts a JOIN studio_runs r ON r.id=a.run_id
                   WHERE a.id=? AND r.actor_id=? AND r.installation_id=?
                   AND r.app_instance_id=? AND r.studio_id=?""",
                (artifact_id, actor_id, installation_id, app_instance_id, studio_id),
            ).fetchone()
        if row is None:
            raise StudioRepositoryError("studio_artifact_not_found", "Studio Artifact was not found", status_code=404)
        return self._artifact(row)

    def import_legacy_artifact(
        self, *, actor_id: str, installation_id: str, app_instance_id: str,
        studio_id: str, mini_app_id: str, mini_app_version: str, title: str,
        input_data: dict[str, Any], source_id: str, name: str, media_type: str,
        preview_url: str, download_url: str, created_at: str, metadata: dict[str, Any],
    ) -> None:
        """Project an existing Studio result into the standard object model once."""

        with self.database.transaction() as connection:
            existing = connection.execute(
                """SELECT 1 FROM studio_artifacts a JOIN studio_runs r ON r.id=a.run_id
                   WHERE a.source_id=? AND r.actor_id=? AND r.installation_id=?
                   AND r.app_instance_id=? AND r.studio_id=?""",
                (source_id, actor_id, installation_id, app_instance_id, studio_id),
            ).fetchone()
        if existing:
            return
        run_id, step_id, artifact_id = self._id("strun"), self._id("ststep"), self._id("sta")
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO studio_runs(id,actor_id,installation_id,app_instance_id,studio_id,
                   mini_app_id,mini_app_version,placement,status,progress,title,input_json,error_json,
                   retry_of,created_at,started_at,completed_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,'succeeded',100,?,?,NULL,NULL,?,?,?,?)""",
                (run_id, actor_id, installation_id, app_instance_id, studio_id, mini_app_id,
                 mini_app_version, studio_id, title[:160], canonical_json(input_data),
                 created_at, created_at, created_at, created_at),
            )
            connection.execute(
                """INSERT INTO studio_run_steps(id,run_id,position,label,status,progress,detail,
                   started_at,completed_at,updated_at) VALUES (?,?,0,?,'succeeded',100,?,?,?,?)""",
                (step_id, run_id, "Generate image", "Imported from Imagine Studio history",
                 created_at, created_at, created_at),
            )
            connection.execute(
                """INSERT INTO studio_artifacts(id,run_id,step_id,kind,name,media_type,source_id,
                   preview_url,download_url,is_final,metadata_json,created_at)
                   VALUES (?,?,?,'image',?,?,?,?,?,1,?,?)""",
                (artifact_id, run_id, step_id, name, media_type, source_id, preview_url,
                 download_url, canonical_json(metadata), created_at),
            )
