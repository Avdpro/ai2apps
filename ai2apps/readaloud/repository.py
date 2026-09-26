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
        if "asr_verification" in value:
            value["asr_verification"] = bool(value["asr_verification"])
        for field in ("rights_scope_json", "metadata_json", "training_json"):
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
                       (SELECT COUNT(*) FROM readaloud_segments s WHERE s.project_id=p.id AND s.deleted_at IS NULL) AS segment_count
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
        mini_app_id: str = "ai2apps.audio.audiobook",
    ) -> dict[str, Any]:
        if mini_app_id not in {"ai2apps.audio.quick-read", "ai2apps.audio.audiobook", "ai2apps.audio.ensemble-drama"}:
            raise ValueError("Unsupported narration Mini-App")
        project_id = self._id("rap")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO readaloud_projects(
                    id,owner_user_id,title,purpose,source_rights,source_text,status,
                    revision,created_at,updated_at,mini_app_id
                ) VALUES (?,?,?,?,?,?,'draft',1,?,?,?)
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
                    mini_app_id,
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
                "SELECT * FROM readaloud_segments WHERE project_id=? AND deleted_at IS NULL ORDER BY ordinal,id",
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
        allowed = {"title", "purpose", "source_rights", "source_text", "status", "asr_verification", "asr_model_id"}
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

    def get_voice_profile(self, owner_user_id: str, profile_id: str):
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM readaloud_voice_profiles WHERE id=? AND owner_user_id=? AND status!='deleted'", (profile_id, owner_user_id)).fetchone()
            if row is None:
                raise ResourceNotFoundError("readaloud_voice_profile", profile_id)
            return self._decode(row)

    def delete_voice_profile(self, owner_user_id, profile_id):
        with self.database.transaction(write=True) as connection:
            row = connection.execute("SELECT id FROM readaloud_voice_profiles WHERE id=? AND owner_user_id=? AND status!='deleted'", (profile_id, owner_user_id)).fetchone()
            if row is None:
                raise ResourceNotFoundError('readaloud_voice_profile', profile_id)
            now = utc_now_text()
            connection.execute("UPDATE readaloud_characters SET voice_profile_id=NULL,updated_at=? WHERE voice_profile_id=?", (now, profile_id))
            connection.execute("UPDATE readaloud_voice_profiles SET status='deleted',updated_at=? WHERE id=?", (now, profile_id))
        return {'deleted': True}

    def save_design_profile(self, owner_user_id, profile_id, *, name, model_id, description, text):
        if not profile_id:
            profile_id = self.create_voice_profile(owner_user_id, name=name, source_type='synthetic_designed', model_id=model_id, provider_voice_id=None, reference_transcript=text, rights_scope={})['id']
        profile = self.get_voice_profile(owner_user_id, profile_id)
        if profile['source_type'] != 'synthetic_designed' or profile.get('training', {}).get('samples'):
            raise ValueError('Select a Designed Voice')
        design = profile.get('training', {}).get('design', {})
        if (profile['model_id'], design.get('description'), profile['reference_transcript']) != (model_id, description, text):
            design = {}
        design.update(description=description)
        with self.database.transaction(write=True) as connection:
            connection.execute("UPDATE readaloud_voice_profiles SET name=?,model_id=?,reference_transcript=?,training_json=?,status=?,updated_at=? WHERE id=?",
                (name, model_id, text, canonical_json({'design':design}), 'ready' if design.get('preview') else 'unverified', utc_now_text(), profile_id))
        return self.get_voice_profile(owner_user_id, profile_id)

    def attach_design_preview(self, owner_user_id, profile_id, expected, preview):
        with self.database.transaction(write=True) as connection:
            row = connection.execute("SELECT * FROM readaloud_voice_profiles WHERE id=? AND owner_user_id=?", (profile_id, owner_user_id)).fetchone()
            if row is None:
                return False
            current = self._decode(row)
            design = current.get('training', {}).get('design', {})
            if (current['model_id'],design.get('description'),current['reference_transcript']) != expected:
                return False
            design['preview'] = preview
            connection.execute("UPDATE readaloud_voice_profiles SET training_json=?,status='ready',updated_at=? WHERE id=?", (canonical_json({'design':design}),utc_now_text(),profile_id))
            return True

    @staticmethod
    def training_identity(profile: dict[str, Any]) -> str:
        training = profile.get('training', {})
        return canonical_json({
            'model': profile.get('model_id'), 'source': profile.get('source_type'),
            'rights': {key: value for key, value in profile.get('rights_scope', {}).items() if key != 'accepted_at'},
            'revision': training.get('model_revision'),
            'samples': [{key: sample.get(key) for key in ('asset_id', 'transcript', 'confirmed')}
                        for sample in training.get('samples', []) if sample.get('selected', True)],
        })

    def verify_training_preview(self, owner_user_id: str, profile_id: str, expected: dict[str, Any]) -> bool:
        """Only verify the exact reference configuration that successfully ran."""
        with self.database.transaction(write=True) as connection:
            row = connection.execute("SELECT * FROM readaloud_voice_profiles WHERE id=? AND owner_user_id=? AND status!='deleted'", (profile_id, owner_user_id)).fetchone()
            if row is None or self.training_identity(self._decode(row)) != self.training_identity(expected):
                return False
            profile = self._decode(row)
            training = profile['training']
            training.update(state='preview_verified', verified_at=utc_now_text())
            connection.execute("UPDATE readaloud_voice_profiles SET training_json=?,status='ready',updated_at=? WHERE id=?", (canonical_json(training), utc_now_text(), profile_id))
            return True

    def update_training_profile(self, owner_user_id: str, profile_id: str, **values) -> dict[str, Any]:
        with self.database.transaction(write=True) as connection:
            row = connection.execute("SELECT * FROM readaloud_voice_profiles WHERE id=? AND owner_user_id=? AND status!='deleted'", (profile_id, owner_user_id)).fetchone()
            if row is None:
                raise ResourceNotFoundError("readaloud_voice_profile", profile_id)
            previous = self._decode(row)
            unchanged = self.training_identity(previous) == self.training_identity(values)
            status = 'ready' if previous['status'] == 'ready' and unchanged else 'unverified'
            if status == 'ready':
                values['training'].update(state='preview_verified', verified_at=previous['training'].get('verified_at'))
            connection.execute(
                """UPDATE readaloud_voice_profiles SET name=?,source_type=?,model_id=?,
                   provider_voice_id=NULL,reference_transcript=?,reference_asset_id=?,
                   rights_scope_json=?,training_json=?,status=?,updated_at=? WHERE id=?""",
                (values['name'], values['source_type'], values['model_id'], values['reference_transcript'],
                 values['reference_asset_id'], canonical_json(values['rights_scope']),
                 canonical_json(values['training']), status, utc_now_text(), profile_id),
            )
            return self._decode(connection.execute("SELECT * FROM readaloud_voice_profiles WHERE id=?", (profile_id,)).fetchone())

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
        training: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        profile_id = self._id("rav")
        now = utc_now_text()
        status = "ready" if source_type == "synthetic_designed" and not (training or {}).get("samples") else "unverified"
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
            if training is not None:
                connection.execute("UPDATE readaloud_voice_profiles SET training_json=? WHERE id=?",
                                   (canonical_json(training), profile_id))
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
        role: str = "auto",
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
                    id,project_id,name,description,voice_profile_id,sort_order,created_at,updated_at,role
                ) VALUES (?,?,?,?,?,?,?,?,?)
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
                    role,
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

    def edit_character(self, owner, project_id, character_id, *, changes=None, delete=False):
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            self._project_row(connection, owner, project_id)
            row = connection.execute('SELECT * FROM readaloud_characters WHERE id=? AND project_id=?', (character_id, project_id)).fetchone()
            if row is None:
                raise ResourceNotFoundError('readaloud_character', character_id)
            if not delete:
                name = changes['name'].strip()
                if not name:
                    raise ValueError('Character name must contain visible characters')
                voice_id = changes.get('voice_profile_id')
                if voice_id and connection.execute("SELECT id FROM readaloud_voice_profiles WHERE id=? AND owner_user_id=? AND status!='deleted'", (voice_id, owner)).fetchone() is None:
                    raise ResourceNotFoundError('readaloud_voice_profile', voice_id)
                connection.execute('UPDATE readaloud_characters SET name=?,description=?,voice_profile_id=?,updated_at=?,role=? WHERE id=?', (name, changes['description'], voice_id, now, changes.get('role', row['role']), character_id))
            connection.execute("UPDATE readaloud_segments SET review_status='needs_review',updated_at=? WHERE project_id=? AND speaker_id=? AND deleted_at IS NULL", (now, project_id, character_id))
            if delete:
                connection.execute('UPDATE readaloud_segments SET speaker_id=NULL WHERE project_id=? AND speaker_id=?', (project_id, character_id))
                connection.execute('DELETE FROM readaloud_characters WHERE id=? AND project_id=?', (character_id, project_id))
            connection.execute('UPDATE readaloud_projects SET revision=revision+1,updated_at=? WHERE id=?', (now, project_id))
        return self.get_project(owner, project_id)

    def apply_source_proposal(self, owner, project_id, proposal):
        from .source_analysis import validate_proposal
        now = utc_now_text()
        def batch_id(kind, key):
            return kind + '_' + uuid.uuid5(uuid.NAMESPACE_URL, project_id + ':' + proposal.batch_id + ':' + kind + ':' + str(key)).hex
        with self.database.transaction(write=True) as connection:
            project = self._project_row(connection, owner, project_id)
            # A retry after a lost response must not insert the batch twice.
            if connection.execute('SELECT id FROM readaloud_segments WHERE id=? AND project_id=?', (batch_id('ras', 0), project_id)).fetchone():
                return {'applied': True}
            if project['revision'] != proposal.revision:
                raise ValueError('The project changed during review. Reanalyze the text before adding it.')
            actors = [dict(row) for row in connection.execute('SELECT * FROM readaloud_characters WHERE project_id=?', (project_id,))]
            validate_proposal(proposal, {'characters':actors})
            rows = connection.execute('SELECT id,deleted_at FROM readaloud_segments WHERE project_id=? ORDER BY ordinal,id', (project_id,)).fetchall()
            active = [row['id'] for row in rows if row['deleted_at'] is None]
            archived = [row['id'] for row in rows if row['deleted_at'] is not None]
            if proposal.after_id and proposal.after_id not in active:
                raise ValueError('The insertion line no longer exists.')
            index = active.index(proposal.after_id) + 1 if proposal.after_id else len(active)
            new_actors = {}
            sort_order = connection.execute('SELECT COALESCE(MAX(sort_order),-1)+1 FROM readaloud_characters WHERE project_id=?', (project_id,)).fetchone()[0]
            for offset, actor in enumerate(proposal.actors):
                if actor.voice_profile_id and not connection.execute("SELECT id FROM readaloud_voice_profiles WHERE id=? AND owner_user_id=? AND status!='deleted'", (actor.voice_profile_id, owner)).fetchone():
                    raise ValueError('Select a voice from your character library.')
                actor_id = batch_id('rac', actor.key)
                new_actors[actor.key] = actor_id
                connection.execute('INSERT INTO readaloud_characters(id,project_id,name,description,voice_profile_id,sort_order,created_at,updated_at,role) VALUES(?,?,?,?,?,?,?,?,?)', (actor_id,project_id,actor.name.strip(),actor.notes,actor.voice_profile_id,sort_order+offset,now,now,actor.role))
            ordinal_base = connection.execute('SELECT COALESCE(MAX(ordinal),-1)+1 FROM readaloud_segments WHERE project_id=?', (project_id,)).fetchone()[0]
            new_ids = []
            for offset, line in enumerate(proposal.lines):
                line_id = batch_id('ras', offset)
                new_ids.append(line_id)
                speaker = new_actors.get(line.speaker_id, line.speaker_id)
                connection.execute("INSERT INTO readaloud_segments(id,project_id,ordinal,speaker_id,text,emotion,emotion_strength,speed,pause_after_ms,review_status,created_at,updated_at) VALUES(?,?,?,?,?,?,1,?,?,'approved',?,?)", (line_id,project_id,ordinal_base+offset,speaker,line.text.strip(),line.emotion,line.speed,line.pause_after_ms,now,now))
            order = active[:index] + new_ids + active[index:] + archived
            shift = ordinal_base + len(new_ids) + 1
            connection.execute('UPDATE readaloud_segments SET ordinal=ordinal+? WHERE project_id=?', (shift,project_id))
            for ordinal, line_id in enumerate(order):
                connection.execute('UPDATE readaloud_segments SET ordinal=? WHERE id=?', (ordinal,line_id))
            connection.execute('UPDATE readaloud_projects SET revision=revision+1,updated_at=? WHERE id=?', (now,project_id))
        return {'applied': True}

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
                "SELECT * FROM readaloud_segments WHERE id=? AND project_id=? AND deleted_at IS NULL",
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


    def change_segment_position(self, owner_user_id, project_id, segment_id, *, action):
        """Keep render-history references while editing the live script order."""
        if action not in {"delete", "up", "down"}:
            raise ValueError("Invalid line action")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            self._project_row(connection, owner_user_id, project_id)
            rows = connection.execute(
                "SELECT id,deleted_at FROM readaloud_segments WHERE project_id=? ORDER BY ordinal,id",
                (project_id,),
            ).fetchall()
            active = [r["id"] for r in rows if r["deleted_at"] is None]
            archived = [r["id"] for r in rows if r["deleted_at"] is not None]
            if segment_id not in active:
                raise ResourceNotFoundError("readaloud_segment", segment_id)
            index = active.index(segment_id)
            if action == "delete":
                active.remove(segment_id)
                archived.append(segment_id)
                connection.execute("UPDATE readaloud_segments SET deleted_at=? WHERE id=?", (now, segment_id))
            else:
                target = index + (-1 if action == "up" else 1)
                if 0 <= target < len(active):
                    active[index], active[target] = active[target], active[index]
            offset = connection.execute("SELECT COALESCE(MAX(ordinal),0)+1 FROM readaloud_segments WHERE project_id=?", (project_id,)).fetchone()[0]
            connection.execute("UPDATE readaloud_segments SET ordinal=ordinal+? WHERE project_id=?", (offset, project_id))
            for ordinal, line_id in enumerate(active + archived):
                connection.execute("UPDATE readaloud_segments SET ordinal=?,updated_at=? WHERE id=?", (ordinal, now, line_id))
            connection.execute("UPDATE readaloud_projects SET revision=revision+1,updated_at=? WHERE id=?", (now, project_id))
        return self.get_project(owner_user_id, project_id)
