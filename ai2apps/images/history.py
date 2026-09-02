"""Private durable output history for the built-in Imagine Studio App."""

from __future__ import annotations

import os
import shutil
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from ai2apps.core import utc_now_text
from ai2apps.storage import PlatformDatabase

MAX_HISTORY_ITEMS = 20
MAX_IMAGE_BYTES = 64 * 1024 * 1024
_IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


class ImagineStudioHistoryError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int = 422) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class ImagineStudioHistoryRepository:
    """Store the latest generated images on disk with principal-scoped metadata."""

    def __init__(self, database: PlatformDatabase, root: str | Path) -> None:
        self.database = database
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _image(data: bytes) -> tuple[str, str]:
        if not data or len(data) > MAX_IMAGE_BYTES:
            raise ImagineStudioHistoryError(
                "imagine_history_image_too_large",
                "Generated image must contain between 1 byte and 64 MiB.",
            )
        try:
            with Image.open(BytesIO(data)) as image:
                image.verify()
                return _IMAGE_FORMATS[str(image.format).upper()]
        except (KeyError, UnidentifiedImageError, OSError) as error:
            raise ImagineStudioHistoryError(
                "imagine_history_image_invalid",
                "Generated image must be a valid PNG, JPEG, or WebP image.",
            ) from error

    @staticmethod
    def _record(row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "pipelineId": row["pipeline_id"],
            "title": row["title"],
            "prompt": row["prompt"],
            "modelId": row["model_id"],
            "modelLabel": row["model_label"],
            "size": row["image_size"],
            "quality": row["quality"],
            "format": row["output_format"],
            "filename": row["filename"],
            "mediaType": row["media_type"],
            "sizeBytes": row["size_bytes"],
            "createdAt": row["created_at"],
        }

    def create(
        self,
        *,
        actor_id: str,
        installation_id: str,
        app_instance_id: str,
        metadata: dict[str, Any],
        data: bytes,
    ) -> dict[str, Any]:
        media_type, suffix = self._image(data)
        result_id = "isr_" + uuid.uuid4().hex
        result_root = self.root / result_id
        result_root.mkdir(mode=0o700)
        path = result_root / f"image{suffix}"
        temporary = result_root / f".image{suffix}.tmp"
        filename = Path(str(metadata.get("filename") or f"imagine-studio{suffix}").replace("\x00", "")).name[:255]
        now = utc_now_text()
        stale_ids: list[str] = []
        try:
            temporary.write_bytes(data)
            temporary.chmod(0o600)
            os.replace(temporary, path)
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    """INSERT INTO imagine_studio_results(
                        id,actor_id,installation_id,app_instance_id,pipeline_id,title,
                        prompt,model_id,model_label,image_size,quality,output_format,
                        filename,media_type,size_bytes,relative_path,created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        result_id, actor_id, installation_id, app_instance_id,
                        str(metadata.get("pipelineId") or "text-image")[:120],
                        str(metadata.get("title") or "Imagine Studio")[:120],
                        str(metadata.get("prompt") or "")[:32000],
                        str(metadata.get("modelId") or "openai/gpt-image-2")[:255],
                        str(metadata.get("modelLabel") or "GPT Image 2")[:120],
                        str(metadata.get("size") or "1024x1024")[:40],
                        str(metadata.get("quality") or "auto")[:40],
                        str(metadata.get("format") or suffix.lstrip("."))[:20],
                        filename or f"imagine-studio{suffix}", media_type, len(data), path.name, now,
                    ),
                )
                rows = connection.execute(
                    """SELECT id FROM imagine_studio_results
                       WHERE actor_id=? AND installation_id=? AND app_instance_id=?
                       ORDER BY created_at DESC,id DESC LIMIT -1 OFFSET ?""",
                    (actor_id, installation_id, app_instance_id, MAX_HISTORY_ITEMS),
                ).fetchall()
                stale_ids = [row["id"] for row in rows]
                if stale_ids:
                    connection.executemany(
                        "DELETE FROM imagine_studio_results WHERE id=?",
                        ((value,) for value in stale_ids),
                    )
        except Exception:
            shutil.rmtree(result_root, ignore_errors=True)
            raise
        for stale_id in stale_ids:
            shutil.rmtree(self.root / stale_id, ignore_errors=True)
        record = self.get(result_id, actor_id=actor_id, installation_id=installation_id, app_instance_id=app_instance_id)
        assert record is not None
        return record

    def list(self, *, actor_id: str, installation_id: str, app_instance_id: str, limit: int = MAX_HISTORY_ITEMS) -> tuple[dict[str, Any], ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT * FROM imagine_studio_results
                   WHERE actor_id=? AND installation_id=? AND app_instance_id=?
                   ORDER BY created_at DESC,id DESC LIMIT ?""",
                (actor_id, installation_id, app_instance_id, min(MAX_HISTORY_ITEMS, max(1, limit))),
            ).fetchall()
        return tuple(self._record(row) for row in rows)

    def get(self, result_id: str, *, actor_id: str, installation_id: str, app_instance_id: str) -> dict[str, Any] | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                """SELECT * FROM imagine_studio_results
                   WHERE id=? AND actor_id=? AND installation_id=? AND app_instance_id=?""",
                (result_id, actor_id, installation_id, app_instance_id),
            ).fetchone()
        return None if row is None else self._record(row)

    def content_path(self, result_id: str, *, actor_id: str, installation_id: str, app_instance_id: str) -> tuple[dict[str, Any], Path] | None:
        record = self.get(result_id, actor_id=actor_id, installation_id=installation_id, app_instance_id=app_instance_id)
        if record is None:
            return None
        with self.database.transaction() as connection:
            row = connection.execute("SELECT relative_path FROM imagine_studio_results WHERE id=?", (result_id,)).fetchone()
        path = (self.root / result_id / row["relative_path"]).resolve()
        if self.root not in path.parents or not path.is_file():
            return None
        return record, path

    def delete(self, result_id: str, *, actor_id: str, installation_id: str, app_instance_id: str) -> bool:
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute(
                """DELETE FROM imagine_studio_results
                   WHERE id=? AND actor_id=? AND installation_id=? AND app_instance_id=?""",
                (result_id, actor_id, installation_id, app_instance_id),
            )
        if cursor.rowcount:
            shutil.rmtree(self.root / result_id, ignore_errors=True)
            return True
        return False

    def clear(self, *, actor_id: str, installation_id: str, app_instance_id: str) -> int:
        with self.database.transaction(write=True) as connection:
            rows = connection.execute(
                "SELECT id FROM imagine_studio_results WHERE actor_id=? AND installation_id=? AND app_instance_id=?",
                (actor_id, installation_id, app_instance_id),
            ).fetchall()
            connection.execute(
                "DELETE FROM imagine_studio_results WHERE actor_id=? AND installation_id=? AND app_instance_id=?",
                (actor_id, installation_id, app_instance_id),
            )
        for row in rows:
            shutil.rmtree(self.root / row["id"], ignore_errors=True)
        return len(rows)
