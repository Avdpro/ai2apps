"""Principal-isolated persistence for narration projects and performance scripts."""

from __future__ import annotations

import json
import uuid
from typing import Any

from ai2apps.core import ResourceNotFoundError, utc_now_text
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.records import canonical_json


class ReadAloudRepository:
    def __init__(
        self,
        database: PlatformDatabase,
        events: EventStore | None = None,
    ) -> None:
        self.database = database
        self.events = events

    @staticmethod
    def _id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    @staticmethod
    def _decode(row) -> dict[str, Any]:
        value = dict(row)
        for field in ("rights_scope_json", "metadata_json"):
            if field in value:
                target = field.removesuffix("_json")
                value[target] = json.loads(value.pop(field) or "{}")
        return value

    def _project_row(self, connection, owner_user_id: str, project_id: str):
        row = connection.execute(
            "SELECT * FROM readaloud_projects WHERE id=? AND owner_user_id=?",
            (project_id, owner_user_id),
        ).fetchone()
        if row is None:
            raise ResourceNotFoundError("readaloud_project", project_id)
        return row

    def _append_event(
        self,
        connection,
        *,
        event_type: str,
        subject_id: str,
        owner_user_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self.events is None:
            return
        self.events.append_in_transaction(
            connection,
            event_type=event_type,
            subject_id=subject_id,
            payload={"owner_user_id": owner_user_id, **(payload or {})},
        )

    def list_projects(self, owner_user_id: str) -> tuple[dict[str, Any], ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT p.*,
                       (SELECT COUNT(*) FROM readaloud_characters c WHERE c.project_id=p.id) AS character_count,
                       (SELECT COUNT(*) FROM readaloud_segments s WHERE s.project_id=p.id) AS segment_count
                FROM readaloud_projects p
                WHERE p.owner_user_id=? AND p.status!='archived'
                ORDER BY p.updated_at DESC, p.id
                """,
                (owner_user_id,),
            ).fetchall()
            return tuple(self._decode(row) for row in rows)

    def create_project(
        self,
        owner_user_id: str,
        *,
        title: str,
        purpose: str,
        source_rights: str,
        source_text: str,
    ) -> dict[str, Any]:
        project_id = self._id("rap")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO readaloud_projects(
                    id,owner_user_id,title,purpose,source_rights,source_text,status,
                    revision,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,'draft',1,?,?)
                """,
                (
                    project_id,
                    owner_user_id,
                    title,
                    purpose,
                    source_rights,
                    source_text,
                    now,
                    now,
                ),
            )
            self._append_event(
                connection,
                event_type="readaloud.project.created",
                subject_id=project_id,
                owner_user_id=owner_user_id,
                payload={"purpose": purpose, "source_rights": source_rights},
            )
            row = self._project_row(connection, owner_user_id, project_id)
            return self._decode(row)

    def get_project(self, owner_user_id: str, project_id: str) -> dict[str, Any]:
        with self.database.transaction() as connection:
            project = self._decode(
                self._project_row(connection, owner_user_id, project_id)
            )
            characters = connection.execute(
                "SELECT * FROM readaloud_characters WHERE project_id=? ORDER BY sort_order,id",
                (project_id,),
            ).fetchall()
            segments = connection.execute(
                "SELECT * FROM readaloud_segments WHERE project_id=? ORDER BY ordinal,id",
                (project_id,),
            ).fetchall()
            project["characters"] = [self._decode(row) for row in characters]
            project["segments"] = [self._decode(row) for row in segments]
            return project

    def update_project(
        self,
        owner_user_id: str,
        project_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        allowed = {"title", "purpose", "source_rights", "source_text", "status"}
        selected = {key: value for key, value in changes.items() if key in allowed}
        if not selected:
            return self.get_project(owner_user_id, project_id)
        now = utc_now_text()
        assignments = ",".join(f"{field}=?" for field in selected)
        with self.database.transaction(write=True) as connection:
            self._project_row(connection, owner_user_id, project_id)
            connection.execute(
                f"UPDATE readaloud_projects SET {assignments},revision=revision+1,updated_at=? WHERE id=?",
                (*selected.values(), now, project_id),
            )
            self._append_event(
                connection,
                event_type="readaloud.project.updated",
                subject_id=project_id,
                owner_user_id=owner_user_id,
                payload={"fields": sorted(selected)},
            )
        return self.get_project(owner_user_id, project_id)

    def list_voice_profiles(self, owner_user_id: str) -> tuple[dict[str, Any], ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM readaloud_voice_profiles
                WHERE owner_user_id=? AND status!='deleted'
                ORDER BY updated_at DESC,id
                """,
                (owner_user_id,),
            ).fetchall()
            return tuple(self._decode(row) for row in rows)

    def create_voice_profile(
        self,
        owner_user_id: str,
        *,
        name: str,
        source_type: str,
        model_id: str | None,
        provider_voice_id: str | None,
        reference_transcript: str,
        rights_scope: dict[str, Any],
        reference_asset_id: str | None = None,
    ) -> dict[str, Any]:
        profile_id = self._id("rav")
        now = utc_now_text()
        status = "ready" if source_type == "synthetic_designed" else "unverified"
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO readaloud_voice_profiles(
                    id,owner_user_id,name,source_type,model_id,provider_voice_id,
                    reference_transcript,rights_scope_json,status,created_at,updated_at,
                    reference_asset_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    profile_id,
                    owner_user_id,
                    name,
                    source_type,
                    model_id,
                    provider_voice_id,
                    reference_transcript,
                    canonical_json(rights_scope),
                    status,
                    now,
                    now,
                    reference_asset_id,
                ),
            )
            self._append_event(
                connection,
                event_type="readaloud.voice_profile.created",
                subject_id=profile_id,
                owner_user_id=owner_user_id,
                payload={
                    "source_type": source_type,
                    "status": status,
                    "has_reference_asset": reference_asset_id is not None,
                },
            )
            row = connection.execute(
                "SELECT * FROM readaloud_voice_profiles WHERE id=?",
                (profile_id,),
            ).fetchone()
            assert row is not None
            return self._decode(row)

    def create_character(
        self,
        owner_user_id: str,
        project_id: str,
        *,
        name: str,
        description: str,
        voice_profile_id: str | None,
    ) -> dict[str, Any]:
        character_id = self._id("rac")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            self._project_row(connection, owner_user_id, project_id)
            if voice_profile_id:
                profile = connection.execute(
                    "SELECT id FROM readaloud_voice_profiles WHERE id=? AND owner_user_id=? AND status!='deleted'",
                    (voice_profile_id, owner_user_id),
                ).fetchone()
                if profile is None:
                    raise ResourceNotFoundError("readaloud_voice_profile", voice_profile_id)
            sort_order = connection.execute(
                "SELECT COALESCE(MAX(sort_order),-1)+1 FROM readaloud_characters WHERE project_id=?",
                (project_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO readaloud_characters(
                    id,project_id,name,description,voice_profile_id,sort_order,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    character_id,
                    project_id,
                    name,
                    description,
                    voice_profile_id,
                    sort_order,
                    now,
                    now,
                ),
            )
            connection.execute(
                "UPDATE readaloud_projects SET revision=revision+1,updated_at=? WHERE id=?",
                (now, project_id),
            )
            row = connection.execute(
                "SELECT * FROM readaloud_characters WHERE id=?",
                (character_id,),
            ).fetchone()
            assert row is not None
            return self._decode(row)

    def create_segment(
        self,
        owner_user_id: str,
        project_id: str,
        *,
        speaker_id: str | None,
        text: str,
        emotion: str,
        emotion_strength: float,
        speed: float,
        pause_after_ms: int,
    ) -> dict[str, Any]:
        segment_id = self._id("ras")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            self._project_row(connection, owner_user_id, project_id)
            if speaker_id:
                speaker = connection.execute(
                    "SELECT id FROM readaloud_characters WHERE id=? AND project_id=?",
                    (speaker_id, project_id),
                ).fetchone()
                if speaker is None:
                    raise ResourceNotFoundError("readaloud_character", speaker_id)
            ordinal = connection.execute(
                "SELECT COALESCE(MAX(ordinal),-1)+1 FROM readaloud_segments WHERE project_id=?",
                (project_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO readaloud_segments(
                    id,project_id,ordinal,speaker_id,text,emotion,emotion_strength,
                    speed,pause_after_ms,review_status,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,'approved',?,?)
                """,
                (
                    segment_id,
                    project_id,
                    ordinal,
                    speaker_id,
                    text,
                    emotion,
                    emotion_strength,
                    speed,
                    pause_after_ms,
                    now,
                    now,
                ),
            )
            connection.execute(
                "UPDATE readaloud_projects SET revision=revision+1,updated_at=? WHERE id=?",
                (now, project_id),
            )
            row = connection.execute(
                "SELECT * FROM readaloud_segments WHERE id=?",
                (segment_id,),
            ).fetchone()
            assert row is not None
            return self._decode(row)

    def update_segment(
        self,
        owner_user_id: str,
        project_id: str,
        segment_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        allowed = {
            "speaker_id",
            "text",
            "emotion",
            "emotion_strength",
            "speed",
            "pause_after_ms",
            "review_status",
        }
        selected = {key: value for key, value in changes.items() if key in allowed}
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            self._project_row(connection, owner_user_id, project_id)
            row = connection.execute(
                "SELECT * FROM readaloud_segments WHERE id=? AND project_id=?",
                (segment_id, project_id),
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("readaloud_segment", segment_id)
            if "speaker_id" in selected and selected["speaker_id"] is not None:
                speaker = connection.execute(
                    "SELECT id FROM readaloud_characters WHERE id=? AND project_id=?",
                    (selected["speaker_id"], project_id),
                ).fetchone()
                if speaker is None:
                    raise ResourceNotFoundError(
                        "readaloud_character", selected["speaker_id"]
                    )
            if selected:
                assignments = ",".join(f"{field}=?" for field in selected)
                connection.execute(
                    f"UPDATE readaloud_segments SET {assignments},updated_at=? WHERE id=?",
                    (*selected.values(), now, segment_id),
                )
                connection.execute(
                    "UPDATE readaloud_projects SET revision=revision+1,updated_at=? WHERE id=?",
                    (now, project_id),
                )
            updated = connection.execute(
                "SELECT * FROM readaloud_segments WHERE id=?",
                (segment_id,),
            ).fetchone()
            assert updated is not None
            return self._decode(updated)
