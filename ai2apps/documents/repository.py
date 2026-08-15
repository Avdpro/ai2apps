"""Session-scoped attachment persistence with content-addressed blobs."""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from ai2apps.config import PlatformPaths
from ai2apps.core import (
    EntityIdKind,
    ResourceNotFoundError,
    new_entity_id,
    utc_now_text,
)
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.records import canonical_json

from .models import AttachmentRecord, DocumentBlock, DocumentStatus
from .parsers import DocumentParser

MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".csv",
    ".txt",
    ".md",
    ".json",
    ".html",
    ".htm",
}


class DocumentRepository:
    def __init__(self, database: PlatformDatabase, paths: PlatformPaths) -> None:
        self.database = database
        self.root = paths.documents_path
        self.parser = DocumentParser()

    def create(
        self,
        session_id: str,
        *,
        filename: str,
        media_type: str,
        data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> AttachmentRecord:
        filename = Path(filename).name.strip()
        if not filename or len(filename) > 512:
            raise ValueError("Attachment filename is invalid")
        if Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError("Unsupported attachment type")
        if len(data) > MAX_ATTACHMENT_BYTES:
            raise ValueError("Attachment exceeds the 25 MiB limit")
        self._validate_content(Path(filename).suffix.lower(), data)
        digest = hashlib.sha256(data).hexdigest()
        storage_key = f"{digest[:2]}/{digest[2:4]}/{digest}"
        attachment_id = new_entity_id(EntityIdKind.ATTACHMENT)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            session = connection.execute(
                "SELECT id FROM sessions WHERE id = ? AND status != 'deleted'",
                (session_id,),
            ).fetchone()
            if session is None:
                raise ResourceNotFoundError("session", session_id)
            row = connection.execute(
                "SELECT id FROM document_blobs WHERE sha256 = ?", (digest,)
            ).fetchone()
            if row is None:
                blob_id = new_entity_id(EntityIdKind.DOCUMENT_BLOB)
                connection.execute(
                    """INSERT INTO document_blobs(
                        id,sha256,size_bytes,storage_key,parse_status,metadata_json,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (blob_id, digest, len(data), storage_key, "queued", "{}", now, now),
                )
            else:
                blob_id = str(row["id"])
            connection.execute(
                """INSERT INTO attachments(
                    id,session_id,blob_id,filename,media_type,metadata_json,created_at
                ) VALUES(?,?,?,?,?,?,?)""",
                (
                    attachment_id,
                    session_id,
                    blob_id,
                    filename,
                    media_type or "application/octet-stream",
                    canonical_json(metadata or {}),
                    now,
                ),
            )
        target = self.root / storage_key
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                prefix=".upload-", dir=target.parent
            )
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return self.get(session_id, attachment_id)

    @staticmethod
    def _validate_content(suffix: str, data: bytes) -> None:
        if suffix == ".pdf" and b"%PDF-" not in data[:1024]:
            raise ValueError("Attachment content is not a PDF")
        if suffix in {".docx", ".pptx", ".xlsx"}:
            if not data.startswith(b"PK"):
                raise ValueError("Attachment content is not an Office document")
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    names = set(archive.namelist())
            except zipfile.BadZipFile as exc:
                raise ValueError("Attachment Office archive is invalid") from exc
            required = {".docx": "word/", ".pptx": "ppt/", ".xlsx": "xl/"}[suffix]
            if not any(name.startswith(required) for name in names):
                raise ValueError(f"Attachment content does not match {suffix}")
        if (
            suffix in {".txt", ".md", ".csv", ".json", ".html", ".htm"}
            and b"\x00" in data[:4096]
        ):
            raise ValueError("Text attachment contains binary data")

    def _row(self, connection, session_id: str, attachment_id: str):
        row = connection.execute(
            """SELECT a.*, b.sha256,b.size_bytes,b.parse_status,b.error_json,b.storage_key
               FROM attachments a JOIN document_blobs b ON b.id=a.blob_id
               WHERE a.id=? AND a.session_id=?""",
            (attachment_id, session_id),
        ).fetchone()
        if row is None:
            raise ResourceNotFoundError("attachment", attachment_id)
        return row

    @staticmethod
    def _record(row) -> AttachmentRecord:
        return AttachmentRecord(
            id=row["id"],
            session_id=row["session_id"],
            blob_id=row["blob_id"],
            filename=row["filename"],
            media_type=row["media_type"],
            size_bytes=row["size_bytes"],
            sha256=row["sha256"],
            status=DocumentStatus(row["parse_status"]),
            metadata=json.loads(row["metadata_json"]),
            error=None if row["error_json"] is None else json.loads(row["error_json"]),
            created_at=row["created_at"],
        )

    def get(self, session_id: str, attachment_id: str) -> AttachmentRecord:
        with self.database.transaction() as connection:
            return self._record(self._row(connection, session_id, attachment_id))

    def list(self, session_id: str) -> tuple[AttachmentRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT a.*, b.sha256,b.size_bytes,b.parse_status,b.error_json,b.storage_key
                   FROM attachments a JOIN document_blobs b ON b.id=a.blob_id
                   WHERE a.session_id=? ORDER BY a.created_at DESC""",
                (session_id,),
            ).fetchall()
            return tuple(self._record(row) for row in rows)

    def parse(self, session_id: str, attachment_id: str) -> AttachmentRecord:
        with self.database.transaction(write=True) as connection:
            row = self._row(connection, session_id, attachment_id)
            if row["parse_status"] == "ready":
                return self._record(row)
            if row["parse_status"] == "parsing":
                return self._record(row)
            connection.execute(
                "UPDATE document_blobs SET parse_status='parsing', error_json=NULL, updated_at=? WHERE id=?",
                (utc_now_text(), row["blob_id"]),
            )
            path = self.root / row["storage_key"]
            blob_id = row["blob_id"]
            filename = row["filename"]
            media_type = row["media_type"]
        try:
            blocks = self.parser.parse(path, filename, media_type)
            if not blocks:
                raise RuntimeError("No extractable content found")
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    "DELETE FROM document_blocks WHERE blob_id=?", (blob_id,)
                )
                for ordinal, block in enumerate(blocks):
                    connection.execute(
                        """INSERT INTO document_blocks(
                            id,blob_id,ordinal,kind,text,page,section,sheet,slide,cell_range,metadata_json
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            new_entity_id(EntityIdKind.DOCUMENT_BLOCK),
                            blob_id,
                            ordinal,
                            block.kind,
                            block.text,
                            block.page,
                            block.section,
                            block.sheet,
                            block.slide,
                            block.cell_range,
                            "{}",
                        ),
                    )
                connection.execute(
                    """UPDATE document_blobs SET parse_status='ready',parser=?,parser_version=?,
                       error_json=NULL,updated_at=? WHERE id=?""",
                    (self.parser.name, self.parser.version, utc_now_text(), blob_id),
                )
        except Exception as exc:
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    "UPDATE document_blobs SET parse_status='failed',error_json=?,updated_at=? WHERE id=?",
                    (
                        canonical_json({"code": "parse_failed", "message": str(exc)}),
                        utc_now_text(),
                        blob_id,
                    ),
                )
        return self.get(session_id, attachment_id)

    def blocks(
        self, session_id: str, attachment_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[DocumentBlock, ...]:
        with self.database.transaction() as connection:
            row = self._row(connection, session_id, attachment_id)
            rows = connection.execute(
                "SELECT * FROM document_blocks WHERE blob_id=? ORDER BY ordinal LIMIT ? OFFSET ?",
                (row["blob_id"], min(max(limit, 1), 200), max(offset, 0)),
            ).fetchall()
            return tuple(self._block(item) for item in rows)

    def search(
        self, session_id: str, attachment_id: str, query: str, *, limit: int = 20
    ) -> tuple[DocumentBlock, ...]:
        with self.database.transaction() as connection:
            row = self._row(connection, session_id, attachment_id)
            rows = connection.execute(
                """SELECT * FROM document_blocks WHERE blob_id=? AND instr(lower(text),lower(?))>0
                   ORDER BY ordinal LIMIT ?""",
                (row["blob_id"], query, min(max(limit, 1), 100)),
            ).fetchall()
            return tuple(self._block(item) for item in rows)

    @staticmethod
    def _block(row) -> DocumentBlock:
        return DocumentBlock(
            id=row["id"],
            ordinal=row["ordinal"],
            kind=row["kind"],
            text=row["text"],
            page=row["page"],
            section=row["section"],
            sheet=row["sheet"],
            slide=row["slide"],
            cell_range=row["cell_range"],
            metadata=json.loads(row["metadata_json"]),
        )

    def recover_pending(self) -> tuple[tuple[str, str], ...]:
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE document_blobs SET parse_status='queued' WHERE parse_status='parsing'"
            )
            rows = connection.execute(
                """SELECT MIN(a.session_id) session_id, MIN(a.id) attachment_id
                   FROM attachments a JOIN document_blobs b ON b.id=a.blob_id
                   WHERE b.parse_status='queued' GROUP BY b.id"""
            ).fetchall()
            return tuple((row["session_id"], row["attachment_id"]) for row in rows)
