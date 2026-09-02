"""App-owned durable drafts for Video Studio ACPF resume."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from ai2apps.core import utc_now_text
from ai2apps.storage import PlatformDatabase

MAX_DRAFT_JSON_BYTES = 512 * 1024
MAX_FRAME_BYTES = 64 * 1024 * 1024
_IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


class VideoStudioDraftError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int = 422) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class VideoStudioDraftRepository:
    """Persist private form state and keyframes outside the ACPF Session."""

    def __init__(self, database: PlatformDatabase, root: str | Path) -> None:
        self.database = database
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _frame(data: bytes, name: str) -> tuple[dict[str, Any], str]:
        if not data or len(data) > MAX_FRAME_BYTES:
            raise VideoStudioDraftError(
                "video_draft_frame_too_large",
                "Keyframe must contain between 1 byte and 64 MiB.",
            )
        try:
            with Image.open(BytesIO(data)) as image:
                image.verify()
                media_type, suffix = _IMAGE_FORMATS[str(image.format).upper()]
        except (KeyError, UnidentifiedImageError, OSError) as error:
            raise VideoStudioDraftError(
                "video_draft_frame_invalid",
                "Keyframe must be a valid PNG, JPEG, or WebP image.",
            ) from error
        return {
            "name": Path(name.replace("\x00", "")).name[:255] or f"frame{suffix}",
            "mediaType": media_type,
            "sizeBytes": len(data),
        }, suffix

    @staticmethod
    def _record(row) -> dict[str, Any]:
        value = {
            "id": row["id"],
            "actorId": row["actor_id"],
            "installationId": row["installation_id"],
            "appInstanceId": row["app_instance_id"],
            "actionId": row["action_id"],
            "draft": json.loads(row["draft_json"]),
            "frames": {},
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
        for which in ("first", "last"):
            encoded = row[f"{which}_frame_json"]
            if encoded:
                value["frames"][which] = json.loads(encoded)
        return value

    def create(
        self,
        *,
        actor_id: str,
        installation_id: str,
        app_instance_id: str,
        action_id: str,
        draft: dict[str, Any],
        first_frame: tuple[str, bytes] | None = None,
        last_frame: tuple[str, bytes] | None = None,
    ) -> dict[str, Any]:
        encoded = _json(draft)
        if len(encoded.encode("utf-8")) > MAX_DRAFT_JSON_BYTES:
            raise VideoStudioDraftError(
                "video_draft_too_large", "Video Studio draft is too large."
            )
        draft_id = "vsd_" + uuid.uuid4().hex
        draft_root = self.root / draft_id
        draft_root.mkdir(mode=0o700)
        descriptors: dict[str, dict[str, Any] | None] = {"first": None, "last": None}
        try:
            for which, frame in (("first", first_frame), ("last", last_frame)):
                if frame is None:
                    continue
                name, data = frame
                descriptor, suffix = self._frame(data, name)
                relative_path = f"{which}{suffix}"
                temporary = draft_root / f".{relative_path}.tmp"
                temporary.write_bytes(data)
                temporary.chmod(0o600)
                os.replace(temporary, draft_root / relative_path)
                descriptors[which] = {**descriptor, "path": relative_path}
            now = utc_now_text()
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    """INSERT INTO video_studio_drafts(
                        id,actor_id,installation_id,app_instance_id,action_id,
                        draft_json,first_frame_json,last_frame_json,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        draft_id,
                        actor_id,
                        installation_id,
                        app_instance_id,
                        action_id,
                        encoded,
                        None if descriptors["first"] is None else _json(descriptors["first"]),
                        None if descriptors["last"] is None else _json(descriptors["last"]),
                        now,
                        now,
                    ),
                )
        except Exception:
            shutil.rmtree(draft_root, ignore_errors=True)
            raise
        record = self.get(
            draft_id,
            actor_id=actor_id,
            installation_id=installation_id,
            app_instance_id=app_instance_id,
        )
        assert record is not None
        return record

    def get(
        self,
        draft_id: str,
        *,
        actor_id: str,
        installation_id: str,
        app_instance_id: str,
    ) -> dict[str, Any] | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                """SELECT * FROM video_studio_drafts
                   WHERE id=? AND actor_id=? AND installation_id=? AND app_instance_id=?""",
                (draft_id, actor_id, installation_id, app_instance_id),
            ).fetchone()
        return None if row is None else self._record(row)

    def frame_path(
        self,
        draft_id: str,
        which: str,
        *,
        actor_id: str,
        installation_id: str,
        app_instance_id: str,
    ) -> tuple[dict[str, Any], Path] | None:
        record = self.get(
            draft_id,
            actor_id=actor_id,
            installation_id=installation_id,
            app_instance_id=app_instance_id,
        )
        descriptor = None if record is None else record["frames"].get(which)
        if descriptor is None:
            return None
        path = (self.root / draft_id / descriptor["path"]).resolve()
        if self.root not in path.parents or not path.is_file():
            return None
        return descriptor, path

    def delete(
        self,
        draft_id: str,
        *,
        actor_id: str,
        installation_id: str,
        app_instance_id: str,
    ) -> bool:
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute(
                """DELETE FROM video_studio_drafts
                   WHERE id=? AND actor_id=? AND installation_id=? AND app_instance_id=?""",
                (draft_id, actor_id, installation_id, app_instance_id),
            )
        if cursor.rowcount:
            shutil.rmtree(self.root / draft_id, ignore_errors=True)
            return True
        return False
