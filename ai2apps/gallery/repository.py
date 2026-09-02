"""Principal-isolated Gallery catalog and content-addressed Blob storage."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import tempfile
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any, BinaryIO

from ai2apps.core import ResourceNotFoundError, utc_now_text
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.records import canonical_json

_SYSTEM_COLLECTIONS = (
    ("downloads", "Downloads", "created_desc"),
    ("public", "Public", "manual"),
    ("personal", "Personal", "manual"),
    ("trash", "Trash", "created_desc"),
)


class GalleryError(ValueError):
    """Stable Gallery validation failure surfaced by the API."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class GalleryRepository:
    def __init__(
        self,
        database: PlatformDatabase,
        blob_root: str | Path,
        events: EventStore | None = None,
    ) -> None:
        self.database = database
        self.blob_root = Path(blob_root).expanduser().resolve()
        self.events = events

    @staticmethod
    def _id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    @staticmethod
    def _safe_name(value: str) -> str:
        name = Path(value.replace("\x00", "")).name.strip()
        name = re.sub(r"[\r\n\t]+", " ", name)
        if not name:
            raise GalleryError("gallery_name_invalid", "A file name is required.")
        return name[:512]

    @staticmethod
    def _kind(media_type: str, name: str) -> str:
        if media_type.startswith("image/"):
            return "image"
        if media_type.startswith("video/"):
            return "video"
        if media_type.startswith("audio/"):
            return "audio"
        if media_type in {"text/html", "application/xhtml+xml"}:
            return "web"
        if media_type.startswith("text/") or media_type in {
            "application/pdf",
            "application/json",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }:
            return "document"
        if Path(name).suffix.lower() in {".html", ".htm"}:
            return "web"
        return "file"

    @staticmethod
    def _decode(row) -> dict[str, Any]:
        value = dict(row)
        if "metadata_json" in value:
            value["metadata"] = json.loads(value.pop("metadata_json") or "{}")
        return value

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

    def ensure_system_collections(self, owner_user_id: str) -> None:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            for system_key, name, sort_mode in _SYSTEM_COLLECTIONS:
                collection_id = "galc_" + uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"ai2apps.gallery:{owner_user_id}:{system_key}",
                ).hex
                connection.execute(
                    """
                    INSERT INTO gallery_collections(
                        id,owner_user_id,name,kind,system_key,sort_mode,
                        metadata_json,created_at,updated_at
                    ) VALUES (?, ?, ?, 'system', ?, ?, '{}', ?, ?)
                    ON CONFLICT(owner_user_id,system_key) DO NOTHING
                    """,
                    (
                        collection_id,
                        owner_user_id,
                        name,
                        system_key,
                        sort_mode,
                        now,
                        now,
                    ),
                )

    def list_collections(self, owner_user_id: str) -> tuple[dict[str, Any], ...]:
        self.ensure_system_collections(owner_user_id)
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT c.*,
                    CASE
                      WHEN c.system_key='trash' THEN (
                        SELECT COUNT(*) FROM gallery_assets a
                        WHERE a.owner_user_id=c.owner_user_id AND a.status='trashed'
                      )
                      ELSE (
                        SELECT COUNT(*)
                        FROM gallery_collection_items i
                        JOIN gallery_assets a ON a.id=i.asset_id
                        WHERE i.collection_id=c.id AND a.status='active'
                      )
                    END AS asset_count
                FROM gallery_collections c
                WHERE c.owner_user_id=?
                ORDER BY CASE c.system_key
                    WHEN 'downloads' THEN 10 WHEN 'public' THEN 20
                    WHEN 'personal' THEN 30 WHEN 'trash' THEN 90 ELSE 50 END,
                    c.created_at,c.id
                """,
                (owner_user_id,),
            ).fetchall()
            active_count = connection.execute(
                "SELECT COUNT(*) FROM gallery_assets WHERE owner_user_id=? AND status='active'",
                (owner_user_id,),
            ).fetchone()[0]
        recent = {
            "id": "recent",
            "owner_user_id": owner_user_id,
            "name": "Recent",
            "kind": "system",
            "system_key": "recent",
            "sort_mode": "created_desc",
            "metadata": {},
            "asset_count": active_count,
        }
        return (recent, *(self._decode(row) for row in rows))

    def create_collection(
        self,
        owner_user_id: str,
        *,
        name: str,
        kind: str = "custom",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_name = name.strip()
        if not normalized_name or len(normalized_name) > 200:
            raise GalleryError(
                "gallery_collection_name_invalid",
                "Collection name must contain between 1 and 200 characters.",
            )
        if kind not in {"custom", "project"}:
            raise GalleryError(
                "gallery_collection_kind_invalid",
                "Collection kind must be custom or project.",
            )
        collection_id = self._id("galc")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO gallery_collections(
                    id,owner_user_id,name,kind,system_key,sort_mode,
                    metadata_json,created_at,updated_at
                ) VALUES (?,?,?,?,NULL,'manual',?,?,?)
                """,
                (
                    collection_id,
                    owner_user_id,
                    normalized_name,
                    kind,
                    canonical_json(metadata or {}),
                    now,
                    now,
                ),
            )
            self._append_event(
                connection,
                event_type="gallery.collection.created",
                subject_id=collection_id,
                owner_user_id=owner_user_id,
                payload={"kind": kind},
            )
            row = connection.execute(
                "SELECT * FROM gallery_collections WHERE id=?", (collection_id,)
            ).fetchone()
        assert row is not None
        value = self._decode(row)
        value["asset_count"] = 0
        return value

    def delete_collection(self, owner_user_id: str, collection_id: str) -> None:
        """Delete one user collection and its indexes without deleting assets."""
        with self.database.transaction(write=True) as connection:
            collection = self._collection_row(
                connection, owner_user_id, collection_id
            )
            if collection["system_key"] is not None or collection["kind"] == "system":
                raise GalleryError(
                    "gallery_system_collection_delete_forbidden",
                    "System collections cannot be deleted.",
                )
            indexed_asset_count = connection.execute(
                "SELECT COUNT(*) FROM gallery_collection_items WHERE collection_id=?",
                (collection_id,),
            ).fetchone()[0]
            connection.execute(
                "DELETE FROM gallery_collections WHERE id=? AND owner_user_id=?",
                (collection_id, owner_user_id),
            )
            self._append_event(
                connection,
                event_type="gallery.collection.deleted",
                subject_id=collection_id,
                owner_user_id=owner_user_id,
                payload={
                    "kind": collection["kind"],
                    "indexed_asset_count": indexed_asset_count,
                },
            )

    def _collection_row(self, connection, owner_user_id: str, collection_id: str):
        row = connection.execute(
            "SELECT * FROM gallery_collections WHERE id=? AND owner_user_id=?",
            (collection_id, owner_user_id),
        ).fetchone()
        if row is None:
            raise ResourceNotFoundError("gallery_collection", collection_id)
        return row

    def _asset_row(
        self,
        connection,
        owner_user_id: str,
        asset_id: str,
        *,
        include_trashed: bool = True,
    ):
        query = "SELECT * FROM gallery_assets WHERE id=? AND owner_user_id=?"
        values: tuple[Any, ...] = (asset_id, owner_user_id)
        if not include_trashed:
            query += " AND status='active'"
        row = connection.execute(query, values).fetchone()
        if row is None:
            raise ResourceNotFoundError("gallery_asset", asset_id)
        return row

    def import_stream(
        self,
        owner_user_id: str,
        stream: BinaryIO,
        *,
        name: str,
        media_type: str | None = None,
        collection_id: str | None = None,
        source_app_id: str | None = None,
        source_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
        max_bytes: int | None = None,
    ) -> tuple[dict[str, Any], bool]:
        safe_name = self._safe_name(name)
        effective_media_type = (
            (media_type or "").split(";", 1)[0].strip().lower()
            or mimetypes.guess_type(safe_name)[0]
            or "application/octet-stream"
        )
        self.blob_root.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".gallery-import-", dir=self.blob_root
        )
        digest = hashlib.sha256()
        size = 0
        try:
            with os.fdopen(descriptor, "wb") as output:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if max_bytes is not None and size > max_bytes:
                        raise GalleryError(
                            "gallery_file_too_large",
                            f"File exceeds the {max_bytes}-byte import limit.",
                        )
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            hex_digest = digest.hexdigest()
            content_hash = f"sha256:{hex_digest}"
            storage_key = f"sha256/{hex_digest[:2]}/{hex_digest}"
            destination = self.blob_root / storage_key
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                Path(temporary_name).unlink(missing_ok=True)
            else:
                os.replace(temporary_name, destination)

            now = utc_now_text()
            created = False
            with self.database.transaction(write=True) as connection:
                if collection_id and collection_id != "recent":
                    self._collection_row(connection, owner_user_id, collection_id)
                row = connection.execute(
                    """
                    SELECT * FROM gallery_assets
                    WHERE owner_user_id=? AND content_hash=? AND name=?
                    """,
                    (owner_user_id, content_hash, safe_name),
                ).fetchone()
                if row is None:
                    asset_id = self._id("gala")
                    connection.execute(
                        """
                        INSERT INTO gallery_assets(
                            id,owner_user_id,name,kind,media_type,content_hash,
                            size_bytes,storage_key,source_app_id,source_ref,
                            metadata_json,status,created_at,updated_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'active',?,?)
                        """,
                        (
                            asset_id,
                            owner_user_id,
                            safe_name,
                            self._kind(effective_media_type, safe_name),
                            effective_media_type,
                            content_hash,
                            size,
                            storage_key,
                            source_app_id,
                            source_ref,
                            canonical_json(metadata or {}),
                            now,
                            now,
                        ),
                    )
                    created = True
                    self._append_event(
                        connection,
                        event_type="gallery.asset.created",
                        subject_id=asset_id,
                        owner_user_id=owner_user_id,
                        payload={
                            "content_hash": content_hash,
                            "media_type": effective_media_type,
                            "size_bytes": size,
                            "source_app_id": source_app_id,
                        },
                    )
                else:
                    asset_id = row["id"]
                    if row["status"] == "trashed":
                        connection.execute(
                            """
                            UPDATE gallery_assets
                            SET status='active',trashed_at=NULL,updated_at=? WHERE id=?
                            """,
                            (now, asset_id),
                        )
                if collection_id and collection_id != "recent":
                    self._add_to_collection_in_transaction(
                        connection, owner_user_id, collection_id, asset_id, now
                    )
                row = self._asset_row(connection, owner_user_id, asset_id)
            return self._decode(row), created
        finally:
            Path(temporary_name).unlink(missing_ok=True)

    def list_assets(
        self,
        owner_user_id: str,
        *,
        collection_id: str | None = None,
        kind: str | None = None,
        search: str | None = None,
        limit: int = 200,
    ) -> tuple[dict[str, Any], ...]:
        if kind is not None and kind not in {
            "image", "video", "audio", "web", "document", "file"
        }:
            raise GalleryError("gallery_kind_invalid", "Unsupported asset kind.")
        limit = max(1, min(limit, 500))
        values: list[Any] = [owner_user_id]
        filters = []
        with self.database.transaction() as connection:
            if not collection_id or collection_id == "recent":
                query = "SELECT a.* FROM gallery_assets a WHERE a.owner_user_id=? AND a.status='active'"
                order = " ORDER BY a.created_at DESC,a.id DESC"
            else:
                collection = self._collection_row(
                    connection, owner_user_id, collection_id
                )
                if collection["system_key"] == "trash":
                    query = "SELECT a.* FROM gallery_assets a WHERE a.owner_user_id=? AND a.status='trashed'"
                    order = " ORDER BY a.trashed_at DESC,a.id DESC"
                else:
                    query = """
                        SELECT a.* FROM gallery_collection_items i
                        JOIN gallery_assets a ON a.id=i.asset_id
                        WHERE a.owner_user_id=? AND a.status='active'
                    """
                    filters.append("i.collection_id=?")
                    values.append(collection_id)
                    order = (
                        " ORDER BY a.created_at DESC,a.id DESC"
                        if collection["sort_mode"] == "created_desc"
                        else " ORDER BY i.position,i.added_at,i.asset_id"
                    )
            if kind:
                filters.append("a.kind=?")
                values.append(kind)
            if search and search.strip():
                filters.append("a.name LIKE ? ESCAPE '\\'")
                escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                values.append(f"%{escaped}%")
            if filters:
                query += " AND " + " AND ".join(filters)
            rows = connection.execute(query + order + " LIMIT ?", (*values, limit)).fetchall()
        return tuple(self._decode(row) for row in rows)

    def get_asset(self, owner_user_id: str, asset_id: str) -> dict[str, Any]:
        with self.database.transaction() as connection:
            return self._decode(self._asset_row(connection, owner_user_id, asset_id))

    def rename_asset(
        self, owner_user_id: str, asset_id: str, name: str
    ) -> dict[str, Any]:
        safe_name = self._safe_name(name)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            self._asset_row(connection, owner_user_id, asset_id)
            connection.execute(
                "UPDATE gallery_assets SET name=?,updated_at=? WHERE id=?",
                (safe_name, now, asset_id),
            )
            self._append_event(
                connection,
                event_type="gallery.asset.renamed",
                subject_id=asset_id,
                owner_user_id=owner_user_id,
                payload={"name": safe_name},
            )
            row = self._asset_row(connection, owner_user_id, asset_id)
        return self._decode(row)

    def asset_path(self, owner_user_id: str, asset_id: str) -> tuple[dict[str, Any], Path]:
        asset = self.get_asset(owner_user_id, asset_id)
        path = (self.blob_root / asset["storage_key"]).resolve(strict=True)
        try:
            path.relative_to(self.blob_root.resolve(strict=True))
        except ValueError as error:
            raise GalleryError(
                "gallery_storage_key_invalid", "Asset storage location is invalid."
            ) from error
        return asset, path

    def _add_to_collection_in_transaction(
        self,
        connection,
        owner_user_id: str,
        collection_id: str,
        asset_id: str,
        now: str,
    ) -> None:
        collection = self._collection_row(connection, owner_user_id, collection_id)
        if collection["system_key"] == "trash":
            raise GalleryError(
                "gallery_collection_read_only", "Use the trash action for this collection."
            )
        self._asset_row(connection, owner_user_id, asset_id, include_trashed=False)
        position = connection.execute(
            "SELECT COALESCE(MAX(position),-1)+1 FROM gallery_collection_items WHERE collection_id=?",
            (collection_id,),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO gallery_collection_items(collection_id,asset_id,position,added_at)
            VALUES (?,?,?,?) ON CONFLICT(collection_id,asset_id) DO NOTHING
            """,
            (collection_id, asset_id, position, now),
        )

    def add_to_collection(
        self, owner_user_id: str, collection_id: str, asset_id: str
    ) -> None:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            self._add_to_collection_in_transaction(
                connection, owner_user_id, collection_id, asset_id, now
            )
            self._append_event(
                connection,
                event_type="gallery.collection.asset_added",
                subject_id=asset_id,
                owner_user_id=owner_user_id,
                payload={"collection_id": collection_id},
            )

    def remove_from_collection(
        self, owner_user_id: str, collection_id: str, asset_id: str
    ) -> None:
        with self.database.transaction(write=True) as connection:
            self._collection_row(connection, owner_user_id, collection_id)
            self._asset_row(connection, owner_user_id, asset_id)
            connection.execute(
                "DELETE FROM gallery_collection_items WHERE collection_id=? AND asset_id=?",
                (collection_id, asset_id),
            )
            self._append_event(
                connection,
                event_type="gallery.collection.asset_removed",
                subject_id=asset_id,
                owner_user_id=owner_user_id,
                payload={"collection_id": collection_id},
            )

    def reorder_collection(
        self, owner_user_id: str, collection_id: str, asset_ids: list[str]
    ) -> None:
        if len(asset_ids) != len(set(asset_ids)):
            raise GalleryError(
                "gallery_order_invalid", "Asset order cannot contain duplicates."
            )
        with self.database.transaction(write=True) as connection:
            collection = self._collection_row(connection, owner_user_id, collection_id)
            if collection["sort_mode"] != "manual":
                raise GalleryError(
                    "gallery_collection_not_manual",
                    "This collection does not use manual ordering.",
                )
            existing = {
                row[0]
                for row in connection.execute(
                    "SELECT asset_id FROM gallery_collection_items WHERE collection_id=?",
                    (collection_id,),
                )
            }
            if not set(asset_ids).issubset(existing):
                raise GalleryError(
                    "gallery_order_invalid",
                    "Asset order contains an item outside the collection.",
                )
            trailing = [item for item in existing if item not in set(asset_ids)]
            for position, asset_id in enumerate([*asset_ids, *sorted(trailing)]):
                connection.execute(
                    "UPDATE gallery_collection_items SET position=? WHERE collection_id=? AND asset_id=?",
                    (position, collection_id, asset_id),
                )
            connection.execute(
                "UPDATE gallery_collections SET updated_at=? WHERE id=?",
                (utc_now_text(), collection_id),
            )

    def trash_asset(self, owner_user_id: str, asset_id: str) -> dict[str, Any]:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            self._asset_row(connection, owner_user_id, asset_id)
            connection.execute(
                "UPDATE gallery_assets SET status='trashed',trashed_at=?,updated_at=? WHERE id=?",
                (now, now, asset_id),
            )
            self._append_event(
                connection,
                event_type="gallery.asset.trashed",
                subject_id=asset_id,
                owner_user_id=owner_user_id,
            )
            row = self._asset_row(connection, owner_user_id, asset_id)
        return self._decode(row)

    def restore_asset(self, owner_user_id: str, asset_id: str) -> dict[str, Any]:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            self._asset_row(connection, owner_user_id, asset_id)
            connection.execute(
                "UPDATE gallery_assets SET status='active',trashed_at=NULL,updated_at=? WHERE id=?",
                (now, asset_id),
            )
            self._append_event(
                connection,
                event_type="gallery.asset.restored",
                subject_id=asset_id,
                owner_user_id=owner_user_id,
            )
            row = self._asset_row(connection, owner_user_id, asset_id)
        return self._decode(row)

    def delete_asset(self, owner_user_id: str, asset_id: str) -> None:
        storage_key: str
        referenced = True
        with self.database.transaction(write=True) as connection:
            row = self._asset_row(connection, owner_user_id, asset_id)
            storage_key = row["storage_key"]
            connection.execute("DELETE FROM gallery_assets WHERE id=?", (asset_id,))
            referenced = connection.execute(
                "SELECT 1 FROM gallery_assets WHERE storage_key=? LIMIT 1",
                (storage_key,),
            ).fetchone() is not None
            self._append_event(
                connection,
                event_type="gallery.asset.deleted",
                subject_id=asset_id,
                owner_user_id=owner_user_id,
            )
        if not referenced:
            candidate = (self.blob_root / storage_key).resolve()
            try:
                candidate.relative_to(self.blob_root.resolve())
            except ValueError:
                return
            with suppress(FileNotFoundError):
                candidate.unlink()
