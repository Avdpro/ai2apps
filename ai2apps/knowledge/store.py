"""SQLite/FTS5 authority for the opt-in local Knowledge Core.

This module deliberately has no imports from MLX, model providers, FastAPI or
the installable Package runtime.  Callers must pass a trusted RequestPrincipal;
ownership checks are performed in every repository query.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import sqlite3
import tempfile
import unicodedata
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

from ai2apps.core import parse_utc, utc_now_text
from ai2apps.identity import MemberRole, RequestPrincipal

if TYPE_CHECKING:
    from ai2apps.storage import PlatformDatabase

from .models import (
    KnowledgeAsset,
    KnowledgeBucket,
    KnowledgeItem,
    KnowledgeScope,
    KnowledgeSearchHit,
    KnowledgeSpace,
    KnowledgeTag,
)

SCHEMA_VERSION = 1
DEFAULT_INSTALLATION_BUDGET_BYTES = 10 * 1024**3
ALLOWED_KINDS = {
    "webpage",
    "document",
    "image",
    "audio",
    "video",
    "chat",
    "artifact",
    "note",
}
SHARED_CONTRIBUTOR_ROLES = {
    MemberRole.CORE,
    MemberRole.OWNER,
    MemberRole.ADMIN,
    MemberRole.DEVELOPER,
    MemberRole.MEMBER,
}
_TAG_SPACE = re.compile(r"\s+")
_LEXICAL_TERM = re.compile(r"\w+", re.UNICODE)
_SYSTEM_BUCKETS = (
    ("inbox", "Inbox", KnowledgeScope.PRIVATE),
    ("web", "Web", KnowledgeScope.PRIVATE),
    ("documents", "Documents", KnowledgeScope.PRIVATE),
    ("chats", "Chats", KnowledgeScope.PRIVATE),
    ("shared", "Local Shared", KnowledgeScope.INSTALLATION),
)


class KnowledgeError(RuntimeError):
    """Base class for Knowledge Core failures."""


class KnowledgeAccessError(KnowledgeError):
    """The principal cannot perform the requested operation."""


class KnowledgeNotFoundError(KnowledgeError):
    """The resource is absent or intentionally hidden from the principal."""


class KnowledgeConflictError(KnowledgeError):
    """The requested revision or durable invariant conflicts."""


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _normalize_tag(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    return _TAG_SPACE.sub(" ", normalized)


def _fts_query(value: str, *, operator: str = "AND") -> str:
    # Release A exposes literal token matching, not raw FTS query syntax.
    tokens = [token for token in _TAG_SPACE.split(value.strip()) if token]
    return f" {operator} ".join(
        f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens
    )


def _lexical_terms(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return set(_LEXICAL_TERM.findall(normalized))


class KnowledgeStore:
    """Knowledge authority backed by either Platform SQLite or a test database."""

    def __init__(
        self,
        storage: str | Path | PlatformDatabase,
        *,
        blob_root: str | Path | None = None,
        busy_timeout_ms: int = 5_000,
    ) -> None:
        # PlatformRuntime passes its managed database.  Path-backed operation is
        # retained for isolated contract tests and offline schema development.
        from ai2apps.storage import PlatformDatabase

        self.database = storage if isinstance(storage, PlatformDatabase) else None
        self.path = (
            self.database.path
            if self.database is not None
            else Path(storage).expanduser().resolve()
        )
        self.busy_timeout_ms = busy_timeout_ms
        self.blob_root = (
            Path(blob_root).expanduser().resolve()
            if blob_root is not None
            else self.path.parent / "knowledge-blobs"
        )

    def connect(self) -> sqlite3.Connection:
        if self.database is not None:
            return self.database.connect()
        connection = sqlite3.connect(
            self.path,
            timeout=self.busy_timeout_ms / 1_000,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        return connection

    @contextmanager
    def transaction(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        if self.database is not None:
            with self.database.transaction(write=write) as connection:
                yield connection
            return
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create the isolated schema; PlatformDatabase uses ordered migrations."""

        if self.database is not None:
            with self.database.transaction() as connection:
                row = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='knowledge_spaces'"
                ).fetchone()
            if row is None:
                raise KnowledgeConflictError(
                    "platform database has not applied the Knowledge migration"
                )
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version > SCHEMA_VERSION:
                raise KnowledgeConflictError("knowledge database uses a newer schema")
            if version == SCHEMA_VERSION:
                return
            try:
                connection.executescript(_SCHEMA_V1)
            except sqlite3.OperationalError as exc:
                if "fts5" in str(exc).casefold():
                    raise KnowledgeConflictError(
                        "this SQLite build does not provide required FTS5 support"
                    ) from exc
                raise
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def ensure_builtin_spaces(
        self, principal: RequestPrincipal
    ) -> tuple[KnowledgeSpace, KnowledgeSpace]:
        """Lazily create the actor's private bucket and Local shared bucket."""

        now = utc_now_text()
        with self.transaction(write=True) as connection:
            private_row = connection.execute(
                """
                SELECT * FROM knowledge_spaces
                WHERE installation_id = ? AND kind = 'private' AND owner_user_id = ?
                """,
                (principal.installation_id, principal.actor_user_id),
            ).fetchone()
            if private_row is None:
                private_id = _new_id("ksp")
                connection.execute(
                    """
                    INSERT INTO knowledge_spaces (
                        id, kind, installation_id, owner_user_id, display_name,
                        shareability, revision, created_at, updated_at
                    ) VALUES (?, 'private', ?, ?, 'My Knowledge', 'never', 1, ?, ?)
                    """,
                    (
                        private_id,
                        principal.installation_id,
                        principal.actor_user_id,
                        now,
                        now,
                    ),
                )
                private_row = connection.execute(
                    "SELECT * FROM knowledge_spaces WHERE id = ?", (private_id,)
                ).fetchone()
            shared_row = connection.execute(
                """
                SELECT * FROM knowledge_spaces
                WHERE installation_id = ? AND kind = 'installation'
                """,
                (principal.installation_id,),
            ).fetchone()
            if shared_row is None:
                shared_id = _new_id("ksp")
                connection.execute(
                    """
                    INSERT INTO knowledge_spaces (
                        id, kind, installation_id, owner_user_id, display_name,
                        shareability, revision, created_at, updated_at
                    ) VALUES (?, 'installation', ?, NULL, 'Local Shared',
                              'local_only', 1, ?, ?)
                    """,
                    (shared_id, principal.installation_id, now, now),
                )
                shared_row = connection.execute(
                    "SELECT * FROM knowledge_spaces WHERE id = ?", (shared_id,)
                ).fetchone()
        assert private_row is not None and shared_row is not None
        return self._space(private_row), self._space(shared_row)

    def ensure_system_buckets(
        self, principal: RequestPrincipal
    ) -> tuple[KnowledgeBucket, ...]:
        """Create Gallery-like default buckets and index legacy orphan items."""

        now = utc_now_text()
        with self.transaction(write=True) as connection:
            for system_key, name, visibility in _SYSTEM_BUCKETS:
                owner_user_id = (
                    principal.actor_user_id
                    if visibility is KnowledgeScope.PRIVATE
                    else None
                )
                bucket_id = (
                    "kbk_"
                    + uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        "ai2apps.knowledge:"
                        f"{principal.installation_id}:{owner_user_id or 'shared'}:{system_key}",
                    ).hex
                )
                connection.execute(
                    """
                    INSERT INTO knowledge_buckets(
                        id,installation_id,owner_user_id,created_by_user_id,
                        visibility,name,kind,system_key,metadata_json,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,'system',?,'{}',?,?)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        bucket_id,
                        principal.installation_id,
                        owner_user_id,
                        principal.actor_user_id,
                        visibility.value,
                        name,
                        system_key,
                        now,
                        now,
                    ),
                )

            # K1 data may predate buckets. Index it without changing authority.
            default_rows = connection.execute(
                """
                SELECT id,system_key FROM knowledge_buckets
                WHERE installation_id=? AND kind='system'
                  AND (visibility='installation' OR owner_user_id=?)
                """,
                (principal.installation_id, principal.actor_user_id),
            ).fetchall()
            default_ids = {row["system_key"]: row["id"] for row in default_rows}
            legacy_items = connection.execute(
                """
                SELECT i.id,i.visibility,i.kind FROM knowledge_items i
                WHERE i.installation_id=? AND i.deleted_at IS NULL
                  AND (i.owner_user_id=? OR i.visibility='installation')
                  AND NOT EXISTS (
                    SELECT 1 FROM knowledge_bucket_items bi WHERE bi.item_id=i.id
                  )
                ORDER BY i.created_at,i.id
                """,
                (principal.installation_id, principal.actor_user_id),
            ).fetchall()
            for position, item in enumerate(legacy_items):
                key = (
                    "shared"
                    if item["visibility"] == "installation"
                    else self._default_bucket_key(item["kind"])
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO knowledge_bucket_items(
                        bucket_id,item_id,position,added_at
                    ) VALUES (?,?,?,?)
                    """,
                    (default_ids[key], item["id"], position, now),
                )
        return self.list_buckets(principal, ensure=False)

    def list_buckets(
        self,
        principal: RequestPrincipal,
        *,
        ensure: bool = True,
    ) -> tuple[KnowledgeBucket, ...]:
        if ensure:
            return self.ensure_system_buckets(principal)
        with self.transaction() as connection:
            rows = connection.execute(
                """
                SELECT b.*,COUNT(i.id) AS item_count
                FROM knowledge_buckets b
                LEFT JOIN knowledge_bucket_items bi ON bi.bucket_id=b.id
                LEFT JOIN knowledge_items i
                  ON i.id=bi.item_id AND i.deleted_at IS NULL
                WHERE b.installation_id=?
                  AND (b.visibility='installation' OR b.owner_user_id=?)
                GROUP BY b.id
                ORDER BY CASE b.system_key
                    WHEN 'inbox' THEN 10 WHEN 'web' THEN 20
                    WHEN 'documents' THEN 30 WHEN 'chats' THEN 40
                    WHEN 'shared' THEN 50 ELSE 80 END,
                    b.created_at,b.id
                """,
                (principal.installation_id, principal.actor_user_id),
            ).fetchall()
        return tuple(self._bucket(row) for row in rows)

    def create_bucket(
        self,
        principal: RequestPrincipal,
        *,
        name: str,
        scope: KnowledgeScope = KnowledgeScope.PRIVATE,
        imported: bool = False,
    ) -> KnowledgeBucket:
        name = name.strip()
        if not name or len(name) > 200:
            raise ValueError("bucket name must contain between 1 and 200 characters")
        self.ensure_system_buckets(principal)
        bucket_id = _new_id("kbk")
        now = utc_now_text()
        owner_user_id = (
            principal.actor_user_id if scope is KnowledgeScope.PRIVATE else None
        )
        with self.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO knowledge_buckets(
                    id,installation_id,owner_user_id,created_by_user_id,
                    visibility,name,kind,system_key,metadata_json,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,NULL,'{}',?,?)
                """,
                (
                    bucket_id,
                    principal.installation_id,
                    owner_user_id,
                    principal.actor_user_id,
                    scope.value,
                    name,
                    "imported" if imported else "custom",
                    now,
                    now,
                ),
            )
            row = self._visible_bucket_row(connection, principal, bucket_id)
        return self._bucket(row)

    def delete_bucket(self, principal: RequestPrincipal, bucket_id: str) -> None:
        with self.transaction(write=True) as connection:
            row = self._visible_bucket_row(connection, principal, bucket_id)
            if row["kind"] == "system":
                raise KnowledgeConflictError(
                    "system knowledge buckets cannot be deleted"
                )
            if row["created_by_user_id"] != principal.actor_user_id:
                raise KnowledgeNotFoundError("knowledge bucket not found")
            connection.execute("DELETE FROM knowledge_buckets WHERE id=?", (bucket_id,))

    def add_item_to_bucket(
        self,
        principal: RequestPrincipal,
        bucket_id: str,
        item_id: str,
    ) -> None:
        now = utc_now_text()
        with self.transaction(write=True) as connection:
            bucket = self._visible_bucket_row(connection, principal, bucket_id)
            item = connection.execute(
                _VISIBLE_ITEM_SELECT + " AND i.id=?",
                self._visibility_args(principal) + (item_id,),
            ).fetchone()
            if item is None:
                raise KnowledgeNotFoundError("knowledge item not found")
            if bucket["visibility"] != item["visibility"]:
                raise KnowledgeConflictError(
                    "copying between Private and Local shared requires explicit sharing"
                )
            position = connection.execute(
                "SELECT COALESCE(MAX(position),-1)+1 FROM knowledge_bucket_items WHERE bucket_id=?",
                (bucket_id,),
            ).fetchone()[0]
            inserted = connection.execute(
                """
                INSERT INTO knowledge_bucket_items(bucket_id,item_id,position,added_at)
                VALUES (?,?,?,?) ON CONFLICT(bucket_id,item_id) DO NOTHING
                """,
                (bucket_id, item_id, position, now),
            )
            if inserted.rowcount:
                connection.execute(
                    """
                    INSERT INTO knowledge_change_log
                        (operation, item_id, space_id, authoritative_revision, created_at)
                    VALUES ('update', ?, ?, ?, ?)
                    """,
                    (item_id, item["space_id"], item["revision"], now),
                )

    def remove_item_from_bucket(
        self,
        principal: RequestPrincipal,
        bucket_id: str,
        item_id: str,
    ) -> None:
        now = utc_now_text()
        with self.transaction(write=True) as connection:
            self._visible_bucket_row(connection, principal, bucket_id)
            item = connection.execute(
                _VISIBLE_ITEM_SELECT + " AND i.id=?",
                self._visibility_args(principal) + (item_id,),
            ).fetchone()
            if item is None:
                raise KnowledgeNotFoundError("knowledge item not found")
            removed = connection.execute(
                "DELETE FROM knowledge_bucket_items WHERE bucket_id=? AND item_id=?",
                (bucket_id, item_id),
            )
            if removed.rowcount:
                connection.execute(
                    """
                    INSERT INTO knowledge_change_log
                        (operation, item_id, space_id, authoritative_revision, created_at)
                    VALUES ('update', ?, ?, ?, ?)
                    """,
                    (item_id, item["space_id"], item["revision"], now),
                )

    def set_context_buckets(
        self,
        principal: RequestPrincipal,
        consumer_app_id: str,
        bucket_ids: Sequence[str],
        *,
        session_id: str | None = None,
    ) -> tuple[str, ...]:
        consumer_app_id = consumer_app_id.strip()
        if not consumer_app_id or len(consumer_app_id) > 255:
            raise ValueError("consumer app id is invalid")
        selected = tuple(dict.fromkeys(bucket_ids))
        self.ensure_system_buckets(principal)
        now = utc_now_text()
        with self.transaction(write=True) as connection:
            for bucket_id in selected:
                self._visible_bucket_row(connection, principal, bucket_id)
            if session_id is not None:
                session_id = session_id.strip()
                if not session_id or len(session_id) > 128:
                    raise ValueError("consumer session id is invalid")
                connection.execute(
                    """
                    INSERT INTO knowledge_session_contexts(
                        installation_id,actor_user_id,consumer_app_id,
                        session_id,updated_at
                    ) VALUES (?,?,?,?,?)
                    ON CONFLICT(
                        installation_id,actor_user_id,consumer_app_id,session_id
                    ) DO UPDATE SET updated_at=excluded.updated_at
                    """,
                    (
                        principal.installation_id,
                        principal.actor_user_id,
                        consumer_app_id,
                        session_id,
                        now,
                    ),
                )
                connection.execute(
                    """
                    DELETE FROM knowledge_session_context_buckets
                    WHERE installation_id=? AND actor_user_id=?
                      AND consumer_app_id=? AND session_id=?
                    """,
                    (
                        principal.installation_id,
                        principal.actor_user_id,
                        consumer_app_id,
                        session_id,
                    ),
                )
                for bucket_id in selected:
                    connection.execute(
                        """
                        INSERT INTO knowledge_session_context_buckets(
                            installation_id,actor_user_id,consumer_app_id,
                            session_id,bucket_id,updated_at
                        ) VALUES (?,?,?,?,?,?)
                        """,
                        (
                            principal.installation_id,
                            principal.actor_user_id,
                            consumer_app_id,
                            session_id,
                            bucket_id,
                            now,
                        ),
                    )
                return selected
            connection.execute(
                """
                DELETE FROM knowledge_context_buckets
                WHERE installation_id=? AND actor_user_id=? AND consumer_app_id=?
                """,
                (
                    principal.installation_id,
                    principal.actor_user_id,
                    consumer_app_id,
                ),
            )
            for bucket_id in selected:
                connection.execute(
                    """
                    INSERT INTO knowledge_context_buckets(
                        installation_id,actor_user_id,consumer_app_id,
                        bucket_id,enabled,updated_at
                    ) VALUES (?,?,?,?,1,?)
                    """,
                    (
                        principal.installation_id,
                        principal.actor_user_id,
                        consumer_app_id,
                        bucket_id,
                        now,
                    ),
                )
        return selected

    def context_buckets(
        self,
        principal: RequestPrincipal,
        consumer_app_id: str,
        *,
        session_id: str | None = None,
    ) -> tuple[str, ...]:
        self.ensure_system_buckets(principal)
        with self.transaction() as connection:
            if session_id is not None:
                configured = connection.execute(
                    """
                    SELECT 1 FROM knowledge_session_contexts
                    WHERE installation_id=? AND actor_user_id=?
                      AND consumer_app_id=? AND session_id=?
                    """,
                    (
                        principal.installation_id,
                        principal.actor_user_id,
                        consumer_app_id,
                        session_id,
                    ),
                ).fetchone()
                if configured is not None:
                    rows = connection.execute(
                        """
                        SELECT cb.bucket_id
                        FROM knowledge_session_context_buckets cb
                        JOIN knowledge_buckets b ON b.id=cb.bucket_id
                        WHERE cb.installation_id=? AND cb.actor_user_id=?
                          AND cb.consumer_app_id=? AND cb.session_id=?
                          AND (
                            b.visibility='installation' OR b.owner_user_id=?
                          )
                        ORDER BY cb.rowid
                        """,
                        (
                            principal.installation_id,
                            principal.actor_user_id,
                            consumer_app_id,
                            session_id,
                            principal.actor_user_id,
                        ),
                    ).fetchall()
                    return tuple(row["bucket_id"] for row in rows)
            rows = connection.execute(
                """
                SELECT cb.bucket_id FROM knowledge_context_buckets cb
                JOIN knowledge_buckets b ON b.id=cb.bucket_id
                WHERE cb.installation_id=? AND cb.actor_user_id=?
                  AND cb.consumer_app_id=? AND cb.enabled=1
                  AND (b.visibility='installation' OR b.owner_user_id=?)
                ORDER BY cb.rowid
                """,
                (
                    principal.installation_id,
                    principal.actor_user_id,
                    consumer_app_id,
                    principal.actor_user_id,
                ),
            ).fetchall()
        return tuple(row["bucket_id"] for row in rows)

    def create_text_item(
        self,
        principal: RequestPrincipal,
        *,
        scope: KnowledgeScope = KnowledgeScope.PRIVATE,
        kind: str = "note",
        title: str,
        text: str,
        source_time: datetime | None = None,
        source_app_id: str | None = None,
        source_session_id: str | None = None,
        source_url: str | None = None,
        user_tags: Sequence[str] = (),
        bucket_id: str | None = None,
        trusted_source_facets: Sequence[tuple[str, str]] = (),
        parsed_chunks: Sequence[tuple[str, dict[str, object]]] = (),
    ) -> KnowledgeItem:
        """Save one text representation and synchronously index it with FTS5."""

        if kind not in ALLOWED_KINDS:
            raise ValueError(f"unsupported knowledge kind: {kind}")
        title = title.strip()
        text = text.strip()
        if not title or not text:
            raise ValueError("title and text must not be empty")
        if (
            scope is KnowledgeScope.INSTALLATION
            and principal.role not in SHARED_CONTRIBUTOR_ROLES
        ):
            raise KnowledgeAccessError(
                "this role cannot contribute Local shared knowledge"
            )
        private, shared = self.ensure_builtin_spaces(principal)
        space = private if scope is KnowledgeScope.PRIVATE else shared
        if self.database is not None:
            buckets = self.ensure_system_buckets(principal)
            if bucket_id is None:
                default_key = (
                    "shared"
                    if scope is KnowledgeScope.INSTALLATION
                    else self._default_bucket_key(kind)
                )
                bucket_id = next(
                    bucket.id for bucket in buckets if bucket.system_key == default_key
                )
        item_id = _new_id("kit")
        representation_id = _new_id("krp")
        now = utc_now_text()
        facets = tuple(
            dict.fromkeys(
                (
                    *self._source_facets(
                        kind=kind,
                        source_app_id=source_app_id,
                        source_session_id=source_session_id,
                        source_url=source_url,
                    ),
                    *(
                        (str(key)[:100], str(value)[:1000])
                        for key, value in trusted_source_facets
                        if str(key).strip() and str(value).strip()
                    ),
                )
            )
        )
        chunks = tuple(
            (chunk_text.strip(), metadata)
            for chunk_text, metadata in parsed_chunks
            if chunk_text.strip()
        ) or ((text, {}),)
        with self.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO knowledge_items (
                    id, space_id, installation_id, owner_user_id,
                    created_by_user_id, visibility, kind, title, source_time,
                    source_app_id, source_session_id, source_url, status,
                    revision, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', 1, ?, ?)
                """,
                (
                    item_id,
                    space.id,
                    principal.installation_id,
                    principal.actor_user_id,
                    principal.actor_user_id,
                    scope.value,
                    kind,
                    title,
                    source_time.isoformat() if source_time else None,
                    source_app_id,
                    source_session_id,
                    source_url,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO knowledge_representations (
                    id, item_id, kind, ordinal, text, producer, status, created_at
                ) VALUES (?, ?, 'parsed_block', 0, ?, 'knowledge.text/v1', 'ready', ?)
                """,
                (representation_id, item_id, text, now),
            )
            has_chunk_metadata = any(
                row["name"] == "metadata_json"
                for row in connection.execute(
                    "PRAGMA table_info(knowledge_chunks)"
                ).fetchall()
            )
            for ordinal, (chunk_text, metadata) in enumerate(chunks):
                if has_chunk_metadata:
                    connection.execute(
                        """
                        INSERT INTO knowledge_chunks (
                            id, representation_id, item_id, space_id, ordinal,
                            text, created_at, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            _new_id("kch"),
                            representation_id,
                            item_id,
                            space.id,
                            ordinal,
                            chunk_text,
                            now,
                            json.dumps(
                                metadata, ensure_ascii=False, separators=(",", ":")
                            ),
                        ),
                    )
                else:
                    connection.execute(
                        """
                        INSERT INTO knowledge_chunks (
                            id, representation_id, item_id, space_id, ordinal,
                            text, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            _new_id("kch"),
                            representation_id,
                            item_id,
                            space.id,
                            ordinal,
                            chunk_text,
                            now,
                        ),
                    )
            for key, value in facets:
                connection.execute(
                    """
                    INSERT INTO knowledge_source_facets
                        (item_id, facet_key, value, authority, created_at)
                    VALUES (?, ?, ?, 'runtime', ?)
                    """,
                    (item_id, key, value, now),
                )
            for display_name in user_tags:
                self._assign_user_tag(
                    connection, principal, item_id, scope, display_name, now
                )
            connection.execute(
                """
                INSERT INTO knowledge_change_log
                    (operation, item_id, space_id, authoritative_revision, created_at)
                VALUES ('create', ?, ?, 1, ?)
                """,
                (item_id, space.id, now),
            )
            if bucket_id is not None:
                bucket = self._visible_bucket_row(connection, principal, bucket_id)
                if bucket["visibility"] != scope.value:
                    raise KnowledgeConflictError(
                        "knowledge bucket visibility differs from the item scope"
                    )
                position = connection.execute(
                    "SELECT COALESCE(MAX(position),-1)+1 FROM knowledge_bucket_items WHERE bucket_id=?",
                    (bucket_id,),
                ).fetchone()[0]
                connection.execute(
                    """
                    INSERT INTO knowledge_bucket_items(
                        bucket_id,item_id,position,added_at
                    ) VALUES (?,?,?,?)
                    """,
                    (bucket_id, item_id, position, now),
                )
            row = connection.execute(
                _VISIBLE_ITEM_SELECT + " AND i.id = ?",
                self._visibility_args(principal) + (item_id,),
            ).fetchone()
        assert row is not None
        return self._item(row)

    def get_item(self, principal: RequestPrincipal, item_id: str) -> KnowledgeItem:
        with self.transaction() as connection:
            row = connection.execute(
                _VISIBLE_ITEM_SELECT + " AND i.id = ?",
                self._visibility_args(principal) + (item_id,),
            ).fetchone()
        if row is None:
            raise KnowledgeNotFoundError("knowledge item not found")
        return self._item(row)

    def items_by_source_url(
        self, principal: RequestPrincipal, source_url: str
    ) -> tuple[KnowledgeItem, ...]:
        with self.transaction() as connection:
            rows = connection.execute(
                _VISIBLE_ITEM_SELECT
                + " AND i.kind='webpage' AND i.source_url=? ORDER BY i.updated_at DESC, i.id",
                self._visibility_args(principal) + (source_url,),
            ).fetchall()
        return tuple(self._item(row) for row in rows)

    def update_text_item(
        self,
        principal: RequestPrincipal,
        item_id: str,
        *,
        expected_revision: int,
        title: str,
        text: str,
        trusted_source_facets: Sequence[tuple[str, str]] = (),
    ) -> KnowledgeItem:
        title = title.strip()
        text = text.strip()
        if not title or not text:
            raise ValueError("title and text must not be empty")
        now = utc_now_text()
        with self.transaction(write=True) as connection:
            row = connection.execute(
                _VISIBLE_ITEM_SELECT + " AND i.id=?",
                self._visibility_args(principal) + (item_id,),
            ).fetchone()
            if row is None or row["owner_user_id"] != principal.actor_user_id:
                raise KnowledgeNotFoundError("knowledge item not found")
            if int(row["revision"]) != expected_revision:
                raise KnowledgeConflictError("knowledge item revision changed")
            if row["kind"] != "webpage":
                raise KnowledgeConflictError("only webpage knowledge can be refreshed")
            new_revision = expected_revision + 1
            representation = connection.execute(
                "SELECT id FROM knowledge_representations WHERE item_id=? AND ordinal=0",
                (item_id,),
            ).fetchone()
            if representation is None:
                raise KnowledgeConflictError("knowledge representation is missing")
            # Delete and recreate chunks so both lexical and semantic indexers observe
            # an ordinary authoritative update instead of a second webpage item.
            connection.execute(
                "DELETE FROM knowledge_chunks WHERE representation_id=?",
                (representation["id"],),
            )
            connection.execute(
                "UPDATE knowledge_items SET title=?,updated_at=?,revision=? WHERE id=?",
                (title, now, new_revision, item_id),
            )
            connection.execute(
                "UPDATE knowledge_representations SET text=?,status='ready' WHERE id=?",
                (text, representation["id"]),
            )
            connection.execute(
                """
                INSERT INTO knowledge_chunks(
                    id,representation_id,item_id,space_id,ordinal,text,created_at,metadata_json
                ) VALUES (?,?,?,?,0,?,?,'{}')
                """,
                (_new_id("kch"), representation["id"], item_id, row["space_id"], text, now),
            )
            for key, value in trusted_source_facets:
                key = str(key)[:100]
                value = str(value)[:1000]
                connection.execute(
                    "DELETE FROM knowledge_source_facets WHERE item_id=? AND facet_key=?",
                    (item_id, key),
                )
                connection.execute(
                    """
                    INSERT INTO knowledge_source_facets(item_id,facet_key,value,authority,created_at)
                    VALUES (?,?,?,'runtime',?)
                    """,
                    (item_id, key, value, now),
                )
            connection.execute(
                """
                INSERT INTO knowledge_change_log(
                    operation,item_id,space_id,authoritative_revision,created_at
                ) VALUES ('update',?,?,?,?)
                """,
                (item_id, row["space_id"], new_revision, now),
            )
            updated = connection.execute(
                _VISIBLE_ITEM_SELECT + " AND i.id=?",
                self._visibility_args(principal) + (item_id,),
            ).fetchone()
        assert updated is not None
        return self._item(updated)

    def source_facets(
        self, principal: RequestPrincipal, item_id: str
    ) -> tuple[tuple[str, str], ...]:
        self.get_item(principal, item_id)
        with self.transaction() as connection:
            return self._facets_for_item(connection, item_id)

    def suggest_tags(
        self, principal: RequestPrincipal, item_id: str
    ) -> tuple[dict[str, object], ...]:
        """Create conservative metadata-derived suggestions for user review."""

        item = self.get_item(principal, item_id)
        candidates: list[tuple[str, float, dict[str, object]]] = []
        if item.source_url:
            from urllib.parse import urlsplit

            host = (urlsplit(item.source_url).hostname or "").casefold()
            if host:
                candidates.append((host, 0.95, {"source": "domain"}))
        suffix = Path(item.title).suffix.lstrip(".").upper()
        if suffix and len(suffix) <= 12:
            candidates.append((suffix, 0.98, {"source": "extension"}))
        if item.kind not in {"note", "document"}:
            candidates.append((item.kind.title(), 0.8, {"source": "content_kind"}))
        now = utc_now_text()
        with self.transaction(write=True) as connection:
            for display_name, confidence, evidence in candidates:
                normalized = _normalize_tag(display_name)
                if not normalized:
                    continue
                connection.execute(
                    """
                    INSERT INTO knowledge_tag_suggestions(
                        id,item_id,installation_id,actor_user_id,display_name,
                        normalized_key,producer,confidence,evidence_json,status,
                        created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,'knowledge.metadata/v1',?,?,'suggested',?,?)
                    ON CONFLICT(item_id,actor_user_id,normalized_key,producer)
                    DO NOTHING
                    """,
                    (
                        _new_id("kts"),
                        item.id,
                        principal.installation_id,
                        principal.actor_user_id,
                        display_name,
                        normalized,
                        confidence,
                        json.dumps(evidence, separators=(",", ":")),
                        now,
                        now,
                    ),
                )
        return self.list_tag_suggestions(principal, item_id=item.id)

    def list_tag_suggestions(
        self,
        principal: RequestPrincipal,
        *,
        item_id: str | None = None,
        bucket_id: str | None = None,
        status: str = "suggested",
    ) -> tuple[dict[str, object], ...]:
        if status not in {"suggested", "confirmed", "rejected"}:
            raise ValueError("invalid tag suggestion status")
        if item_id is not None:
            self.get_item(principal, item_id)
        if bucket_id is not None:
            with self.transaction() as connection:
                self._visible_bucket_row(connection, principal, bucket_id)
        clauses = [
            "s.installation_id=?",
            "s.actor_user_id=?",
            "s.status=?",
            "i.deleted_at IS NULL",
            "(i.owner_user_id=? OR i.visibility='installation')",
        ]
        arguments: list[object] = [
            principal.installation_id,
            principal.actor_user_id,
            status,
            principal.actor_user_id,
        ]
        if item_id is not None:
            clauses.append("s.item_id=?")
            arguments.append(item_id)
        if bucket_id is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM knowledge_bucket_items bi "
                "WHERE bi.item_id=s.item_id AND bi.bucket_id=?)"
            )
            arguments.append(bucket_id)
        with self.transaction() as connection:
            rows = connection.execute(
                f"""
                SELECT s.* FROM knowledge_tag_suggestions s
                JOIN knowledge_items i ON i.id=s.item_id
                WHERE {" AND ".join(clauses)}
                ORDER BY s.confidence DESC,s.created_at,s.id
                """,
                tuple(arguments),
            ).fetchall()
        return tuple(
            {**dict(row), "evidence": json.loads(row["evidence_json"])}
            for row in rows
        )

    def list_item_tags(
        self, principal: RequestPrincipal, *, bucket_id: str
    ) -> tuple[dict[str, object], ...]:
        """Return visible confirmed tags for all items in one visible bucket."""

        with self.transaction() as connection:
            self._visible_bucket_row(connection, principal, bucket_id)
            rows = connection.execute(
                """
                SELECT it.item_id,t.* FROM knowledge_item_tags it
                JOIN knowledge_tags t ON t.id=it.tag_id
                JOIN knowledge_items i ON i.id=it.item_id
                JOIN knowledge_bucket_items bi ON bi.item_id=i.id
                WHERE bi.bucket_id=? AND i.installation_id=?
                  AND i.deleted_at IS NULL
                  AND (i.owner_user_id=? OR i.visibility='installation')
                  AND it.status='active' AND t.status='active'
                  AND (t.visibility='installation' OR t.owner_user_id=?)
                ORDER BY it.item_id,t.display_name,t.id
                """,
                (
                    bucket_id,
                    principal.installation_id,
                    principal.actor_user_id,
                    principal.actor_user_id,
                ),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def decide_tag_suggestion(
        self,
        principal: RequestPrincipal,
        suggestion_id: str,
        *,
        decision: str,
    ) -> dict[str, object]:
        if decision not in {"confirm", "reject"}:
            raise ValueError("invalid tag suggestion decision")
        now = utc_now_text()
        with self.transaction(write=True) as connection:
            row = connection.execute(
                """
                SELECT s.*,i.visibility,i.owner_user_id,i.deleted_at
                FROM knowledge_tag_suggestions s
                JOIN knowledge_items i ON i.id=s.item_id
                WHERE s.id=? AND s.installation_id=? AND s.actor_user_id=?
                  AND s.status='suggested'
                  AND i.deleted_at IS NULL
                  AND (i.owner_user_id=? OR i.visibility='installation')
                """,
                (
                    suggestion_id,
                    principal.installation_id,
                    principal.actor_user_id,
                    principal.actor_user_id,
                ),
            ).fetchone()
            if row is None:
                raise KnowledgeNotFoundError("knowledge tag suggestion not found")
            tag_id = None
            if decision == "confirm":
                scope = KnowledgeScope(str(row["visibility"]))
                self._assign_user_tag(
                    connection,
                    principal,
                    str(row["item_id"]),
                    scope,
                    str(row["display_name"]),
                    now,
                )
                tag_id = connection.execute(
                    """
                    SELECT t.id FROM knowledge_tags t
                    JOIN knowledge_item_tags it ON it.tag_id=t.id
                    WHERE it.item_id=? AND t.installation_id=?
                      AND t.owner_user_id=? AND t.visibility=?
                      AND t.normalized_key=?
                    """,
                    (
                        row["item_id"],
                        principal.installation_id,
                        principal.actor_user_id,
                        row["visibility"],
                        row["normalized_key"],
                    ),
                ).fetchone()[0]
            connection.execute(
                """
                UPDATE knowledge_tag_suggestions
                SET status=?,confirmed_tag_id=?,updated_at=? WHERE id=?
                """,
                (
                    "confirmed" if decision == "confirm" else "rejected",
                    tag_id,
                    now,
                    suggestion_id,
                ),
            )
            result = connection.execute(
                "SELECT * FROM knowledge_tag_suggestions WHERE id=?",
                (suggestion_id,),
            ).fetchone()
        return {**dict(result), "evidence": json.loads(result["evidence_json"])}

    def bucket_ids_for_item(
        self, principal: RequestPrincipal, item_id: str
    ) -> tuple[str, ...]:
        self.get_item(principal, item_id)
        with self.transaction() as connection:
            rows = connection.execute(
                """
                SELECT bi.bucket_id
                FROM knowledge_bucket_items bi
                JOIN knowledge_buckets b ON b.id=bi.bucket_id
                WHERE bi.item_id=? AND b.installation_id=?
                  AND (b.visibility='installation' OR b.owner_user_id=?)
                ORDER BY bi.position,bi.bucket_id
                """,
                (item_id, principal.installation_id, principal.actor_user_id),
            ).fetchall()
        return tuple(str(row["bucket_id"]) for row in rows)

    def chunk_locations_for_item(
        self, principal: RequestPrincipal, item_id: str
    ) -> tuple[dict[str, object], ...]:
        self.get_item(principal, item_id)
        with self.transaction() as connection:
            columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(knowledge_chunks)"
                ).fetchall()
            }
            if "metadata_json" not in columns:
                return ()
            rows = connection.execute(
                """
                SELECT metadata_json FROM knowledge_chunks
                WHERE item_id=? ORDER BY ordinal
                """,
                (item_id,),
            ).fetchall()
        return tuple(
            value
            for row in rows
            if isinstance((value := json.loads(row["metadata_json"])), dict) and value
        )

    def list_items(
        self,
        principal: RequestPrincipal,
        *,
        scope: KnowledgeScope | None = None,
        kind: str | None = None,
        bucket_id: str | None = None,
        limit: int = 100,
    ) -> tuple[KnowledgeItem, ...]:
        """List recent visible items without requiring a search query."""

        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        clauses = [
            "i.installation_id = ?",
            "i.deleted_at IS NULL",
            "(i.owner_user_id = ? OR i.visibility = 'installation')",
        ]
        arguments: list[object] = [
            principal.installation_id,
            principal.actor_user_id,
        ]
        if scope is not None:
            clauses.append("i.visibility = ?")
            arguments.append(scope.value)
        if kind is not None:
            if kind not in ALLOWED_KINDS:
                raise ValueError(f"unsupported knowledge kind: {kind}")
            clauses.append("i.kind = ?")
            arguments.append(kind)
        if bucket_id is not None:
            with self.transaction() as connection:
                self._visible_bucket_row(connection, principal, bucket_id)
            clauses.append(
                "EXISTS (SELECT 1 FROM knowledge_bucket_items bi "
                "WHERE bi.item_id=i.id AND bi.bucket_id=?)"
            )
            arguments.append(bucket_id)
        arguments.append(limit)
        with self.transaction() as connection:
            rows = connection.execute(
                f"""
                SELECT i.*, r.text
                FROM knowledge_items i
                JOIN knowledge_representations r
                  ON r.item_id = i.id AND r.ordinal = 0
                WHERE {" AND ".join(clauses)}
                ORDER BY i.updated_at DESC, i.id DESC
                LIMIT ?
                """,
                tuple(arguments),
            ).fetchall()
        return tuple(self._item(row) for row in rows)

    def search(
        self,
        principal: RequestPrincipal,
        query: str,
        *,
        scope: KnowledgeScope | None = None,
        kind: str | None = None,
        tags: Sequence[str] = (),
        bucket_ids: Sequence[str] = (),
        source_app_id: str | None = None,
        source_session_id: str | None = None,
        source_after: datetime | None = None,
        source_before: datetime | None = None,
        limit: int = 20,
    ) -> tuple[KnowledgeSearchHit, ...]:
        """Search only rows visible to the principal, before ranking/limit."""

        match = _fts_query(query)
        recall_match = _fts_query(query, operator="OR")
        if not match:
            return ()
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        clauses = [
            "i.installation_id = ?",
            "i.status = 'ready'",
            "i.deleted_at IS NULL",
            "(i.owner_user_id = ? OR i.visibility = 'installation')",
        ]
        arguments: list[object] = [
            match,
            principal.installation_id,
            principal.actor_user_id,
        ]
        if scope is not None:
            clauses.append("i.visibility = ?")
            arguments.append(scope.value)
        if kind is not None:
            clauses.append("i.kind = ?")
            arguments.append(kind)
        if source_app_id is not None:
            clauses.append("i.source_app_id = ?")
            arguments.append(source_app_id)
        if source_session_id is not None:
            clauses.append("i.source_session_id = ?")
            arguments.append(source_session_id)
        if source_after is not None:
            clauses.append("COALESCE(i.source_time,i.updated_at) >= ?")
            arguments.append(source_after.isoformat())
        if source_before is not None:
            clauses.append("COALESCE(i.source_time,i.updated_at) <= ?")
            arguments.append(source_before.isoformat())
        normalized_tags = tuple(_normalize_tag(tag) for tag in tags if tag.strip())
        for tag in normalized_tags:
            clauses.append(
                """EXISTS (
                    SELECT 1 FROM knowledge_item_tags it
                    JOIN knowledge_tags t ON t.id = it.tag_id
                    WHERE it.item_id = i.id AND it.status = 'active'
                      AND t.normalized_key = ?
                      AND (t.visibility = 'installation' OR t.owner_user_id = ?)
                )"""
            )
            arguments.extend((tag, principal.actor_user_id))
        selected_buckets = tuple(dict.fromkeys(bucket_ids))
        if selected_buckets:
            with self.transaction() as connection:
                for bucket_id in selected_buckets:
                    self._visible_bucket_row(connection, principal, bucket_id)
            placeholders = ",".join("?" for _ in selected_buckets)
            clauses.append(
                "EXISTS (SELECT 1 FROM knowledge_bucket_items bi "
                f"WHERE bi.item_id=i.id AND bi.bucket_id IN ({placeholders}))"
            )
            arguments.extend(selected_buckets)
        arguments.append(min(400, limit * 4))
        with self.transaction() as connection:
            has_chunk_metadata = any(
                row["name"] == "metadata_json"
                for row in connection.execute(
                    "PRAGMA table_info(knowledge_chunks)"
                ).fetchall()
            )
        metadata_select = (
            "c.metadata_json AS chunk_metadata"
            if has_chunk_metadata
            else "'{}' AS chunk_metadata"
        )
        sql = f"""
            SELECT i.*, r.text,
                   snippet(knowledge_fts, 1, '<mark>', '</mark>', ' … ', 24) AS excerpt,
                   bm25(knowledge_fts, 3.0, 1.0) AS fts_rank,
                   {metadata_select}
            FROM knowledge_fts
            JOIN knowledge_chunks c ON c.rowid = knowledge_fts.rowid
            JOIN knowledge_items i ON i.id = c.item_id
            JOIN knowledge_representations r ON r.item_id = i.id AND r.ordinal = 0
            WHERE knowledge_fts MATCH ? AND {" AND ".join(clauses)}
            ORDER BY fts_rank, i.updated_at DESC, i.id
            LIMIT ?
        """
        with self.transaction() as connection:
            rows = connection.execute(sql, tuple(arguments)).fetchall()
            # Keep exact multi-token searches precise. Natural-language
            # questions often add function words that are absent from the
            # evidence, so retry with BM25-ranked OR only when AND found no
            # candidates at all.
            if not rows and recall_match != match:
                recall_arguments = [recall_match, *arguments[1:]]
                rows = connection.execute(sql, tuple(recall_arguments)).fetchall()
                query_terms = _lexical_terms(query)
                rows = [
                    row
                    for row in rows
                    if len(
                        query_terms
                        & _lexical_terms(f"{row['title']} {row['text']}")
                    )
                    >= min(2, len(query_terms))
                ]
            hits = []
            seen: set[str] = set()
            for row in rows:
                item = self._item(row)
                if item.id in seen:
                    continue
                seen.add(item.id)
                hits.append(
                    KnowledgeSearchHit(
                        item=item,
                        excerpt=str(row["excerpt"]),
                        rank=float(row["fts_rank"]),
                        tags=self._tags_for_item(connection, principal, item.id),
                        source_facets=self._facets_for_item(connection, item.id),
                        location=json.loads(row["chunk_metadata"]),
                    )
                )
                if len(hits) >= limit:
                    break
        return tuple(hits)

    def hydrate_semantic_hit(
        self,
        principal: RequestPrincipal,
        item_id: str,
        *,
        excerpt: str,
        distance: float,
        scope: KnowledgeScope | None = None,
        kind: str | None = None,
        tags: Sequence[str] = (),
        bucket_ids: Sequence[str] = (),
        source_app_id: str | None = None,
        source_session_id: str | None = None,
        source_after: datetime | None = None,
        source_before: datetime | None = None,
    ) -> KnowledgeSearchHit | None:
        """Recheck one derived-index candidate against SQLite authority.

        A vector backend may be stale or compromised. It can propose an Item ID,
        but only this authoritative query can turn that ID into a visible hit.
        """

        clauses = [
            "i.id = ?",
            "i.installation_id = ?",
            "i.status = 'ready'",
            "i.deleted_at IS NULL",
            "(i.owner_user_id = ? OR i.visibility = 'installation')",
        ]
        arguments: list[object] = [
            item_id,
            principal.installation_id,
            principal.actor_user_id,
        ]
        if scope is not None:
            clauses.append("i.visibility = ?")
            arguments.append(scope.value)
        if kind is not None:
            if kind not in ALLOWED_KINDS:
                raise ValueError(f"unsupported knowledge kind: {kind}")
            clauses.append("i.kind = ?")
            arguments.append(kind)
        if source_app_id is not None:
            clauses.append("i.source_app_id = ?")
            arguments.append(source_app_id)
        if source_session_id is not None:
            clauses.append("i.source_session_id = ?")
            arguments.append(source_session_id)
        if source_after is not None:
            clauses.append("COALESCE(i.source_time,i.updated_at) >= ?")
            arguments.append(source_after.isoformat())
        if source_before is not None:
            clauses.append("COALESCE(i.source_time,i.updated_at) <= ?")
            arguments.append(source_before.isoformat())
        for tag in (_normalize_tag(value) for value in tags if value.strip()):
            clauses.append(
                """EXISTS (
                    SELECT 1 FROM knowledge_item_tags it
                    JOIN knowledge_tags t ON t.id = it.tag_id
                    WHERE it.item_id = i.id AND it.status = 'active'
                      AND t.normalized_key = ?
                      AND (t.visibility = 'installation' OR t.owner_user_id = ?)
                )"""
            )
            arguments.extend((tag, principal.actor_user_id))
        selected_buckets = tuple(dict.fromkeys(bucket_ids))
        with self.transaction() as connection:
            for bucket_id in selected_buckets:
                self._visible_bucket_row(connection, principal, bucket_id)
            if selected_buckets:
                placeholders = ",".join("?" for _ in selected_buckets)
                clauses.append(
                    "EXISTS (SELECT 1 FROM knowledge_bucket_items bi "
                    f"WHERE bi.item_id=i.id AND bi.bucket_id IN ({placeholders}))"
                )
                arguments.extend(selected_buckets)
            row = connection.execute(
                f"""
                SELECT i.*,r.text
                FROM knowledge_items i
                JOIN knowledge_representations r
                  ON r.item_id=i.id AND r.ordinal=0
                WHERE {" AND ".join(clauses)}
                """,
                tuple(arguments),
            ).fetchone()
            if row is None:
                return None
            item = self._item(row)
            return KnowledgeSearchHit(
                item=item,
                # Vector index chunks are currently bounded to 1,800 characters.
                # Preserve the complete candidate so a relevant sentence near the
                # end of the chunk is not discarded before grounded generation.
                excerpt=excerpt[:2400],
                rank=distance,
                tags=self._tags_for_item(connection, principal, item.id),
                source_facets=self._facets_for_item(connection, item.id),
                location=self._location_from_excerpt(excerpt),
            )

    @staticmethod
    def _location_from_excerpt(excerpt: str) -> dict[str, object] | None:
        patterns = {
            "page": r"\[Page (\d+)",
            "slide": r"\[Slide (\d+)",
            "sheet": r"(?:\[|· )Sheet ([^·\]\n]+)",
            "cell_range": r"(?:\[|· )Cells ([^·\]\n]+)",
        }
        location: dict[str, object] = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, excerpt)
            if match is None:
                continue
            value: object = match.group(1).strip()
            if key in {"page", "slide"}:
                value = int(str(value))
            location[key] = value
        return location or None

    def delete_item(
        self, principal: RequestPrincipal, item_id: str, *, expected_revision: int
    ) -> None:
        """Soft-delete an owned item; shared governance is intentionally deferred."""

        now = utc_now_text()
        with self.transaction(write=True) as connection:
            row = connection.execute(
                """
                SELECT * FROM knowledge_items
                WHERE id = ? AND installation_id = ? AND deleted_at IS NULL
                """,
                (item_id, principal.installation_id),
            ).fetchone()
            if row is None or row["owner_user_id"] != principal.actor_user_id:
                raise KnowledgeNotFoundError("knowledge item not found")
            if int(row["revision"]) != expected_revision:
                raise KnowledgeConflictError("knowledge item revision changed")
            new_revision = expected_revision + 1
            connection.execute(
                """
                UPDATE knowledge_items
                SET status = 'deleted', deleted_at = ?, updated_at = ?, revision = ?
                WHERE id = ?
                """,
                (now, now, new_revision, item_id),
            )
            connection.execute(
                """
                INSERT INTO knowledge_change_log
                    (operation, item_id, space_id, authoritative_revision, created_at)
                VALUES ('delete', ?, ?, ?, ?)
                """,
                (item_id, row["space_id"], new_revision, now),
            )

    def create_import_job(
        self,
        principal: RequestPrincipal,
        *,
        bucket_id: str,
        filenames: Sequence[str],
        source_app_id: str | None = None,
    ) -> dict[str, object]:
        names = tuple(
            (Path(name.replace("\x00", "")).name.strip() or "Untitled")[:512]
            for name in filenames
        )
        if not names or len(names) > 500:
            raise ValueError("an import job requires between 1 and 500 files")
        job_id = _new_id("kij")
        now = utc_now_text()
        with self.transaction(write=True) as connection:
            self._visible_bucket_row(connection, principal, bucket_id)
            connection.execute(
                """
                INSERT INTO knowledge_import_jobs(
                    id,installation_id,actor_user_id,bucket_id,source_app_id,status,
                    total_files,completed_files,failed_files,created_at,updated_at
                ) VALUES (?,?,?,?,?,'queued',?,0,0,?,?)
                """,
                (
                    job_id,
                    principal.installation_id,
                    principal.actor_user_id,
                    bucket_id,
                    source_app_id,
                    len(names),
                    now,
                    now,
                ),
            )
            connection.executemany(
                """
                INSERT INTO knowledge_import_job_entries(
                    job_id,ordinal,filename,status,updated_at
                ) VALUES (?,?,?,'queued',?)
                """,
                ((job_id, ordinal, name, now) for ordinal, name in enumerate(names)),
            )
        return self.get_import_job(principal, job_id)

    def update_import_entry(
        self,
        principal: RequestPrincipal,
        job_id: str,
        ordinal: int,
        *,
        status: str,
        item_id: str | None = None,
        error: str | None = None,
    ) -> dict[str, object]:
        if status not in {"running", "completed", "failed"}:
            raise ValueError("invalid import entry status")
        now = utc_now_text()
        with self.transaction(write=True) as connection:
            job = connection.execute(
                """
                SELECT * FROM knowledge_import_jobs
                WHERE id=? AND installation_id=? AND actor_user_id=?
                """,
                (job_id, principal.installation_id, principal.actor_user_id),
            ).fetchone()
            if job is None:
                raise KnowledgeNotFoundError("knowledge import job not found")
            changed = connection.execute(
                """
                UPDATE knowledge_import_job_entries
                SET status=?,item_id=?,error=?,updated_at=?,
                    attempts=attempts+CASE WHEN ?='running' THEN 1 ELSE 0 END
                WHERE job_id=? AND ordinal=?
                """,
                (
                    status,
                    item_id,
                    (error or "")[:2_000] or None,
                    now,
                    status,
                    job_id,
                    ordinal,
                ),
            )
            if not changed.rowcount:
                raise KnowledgeNotFoundError("knowledge import entry not found")
            counts = connection.execute(
                """
                SELECT
                    SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status IN ('queued','running') THEN 1 ELSE 0 END)
                FROM knowledge_import_job_entries WHERE job_id=?
                """,
                (job_id,),
            ).fetchone()
            completed, failed, pending = (int(value or 0) for value in counts)
            if pending:
                job_status = "running"
                completed_at = None
            else:
                job_status = (
                    "completed"
                    if not failed
                    else "failed"
                    if not completed
                    else "partial"
                )
                completed_at = now
            connection.execute(
                """
                UPDATE knowledge_import_jobs
                SET status=?,completed_files=?,failed_files=?,
                    started_at=COALESCE(started_at,?),completed_at=?,updated_at=?
                WHERE id=?
                """,
                (job_status, completed, failed, now, completed_at, now, job_id),
            )
        return self.get_import_job(principal, job_id)

    def get_import_job(
        self, principal: RequestPrincipal, job_id: str
    ) -> dict[str, object]:
        with self.transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM knowledge_import_jobs
                WHERE id=? AND installation_id=? AND actor_user_id=?
                """,
                (job_id, principal.installation_id, principal.actor_user_id),
            ).fetchone()
            if row is None:
                raise KnowledgeNotFoundError("knowledge import job not found")
            entries = connection.execute(
                "SELECT * FROM knowledge_import_job_entries WHERE job_id=? ORDER BY ordinal",
                (job_id,),
            ).fetchall()
        result = dict(row)
        result["execution_status"] = result["status"]
        if result.get("control_state") in {"paused", "cancelled"}:
            result["status"] = result["control_state"]
        return {**result, "entries": [dict(entry) for entry in entries]}

    def list_import_jobs(
        self, principal: RequestPrincipal, *, limit: int = 20
    ) -> tuple[dict[str, object], ...]:
        with self.transaction() as connection:
            rows = connection.execute(
                """
                SELECT id FROM knowledge_import_jobs
                WHERE installation_id=? AND actor_user_id=?
                ORDER BY created_at DESC,id DESC LIMIT ?
                """,
                (
                    principal.installation_id,
                    principal.actor_user_id,
                    max(1, min(limit, 100)),
                ),
            ).fetchall()
        return tuple(self.get_import_job(principal, str(row["id"])) for row in rows)

    def stage_import_entry(
        self,
        principal: RequestPrincipal,
        job_id: str,
        ordinal: int,
        stream: BinaryIO,
        *,
        media_type: str | None = None,
        max_bytes: int = 64 * 1024 * 1024,
    ) -> dict[str, object]:
        """Durably stage an upload before any parser or background worker runs."""

        with self.transaction() as connection:
            stageable = connection.execute(
                """
                SELECT 1
                FROM knowledge_import_jobs j
                JOIN knowledge_import_job_entries e ON e.job_id=j.id
                WHERE j.id=? AND j.installation_id=? AND j.actor_user_id=?
                  AND e.ordinal=? AND e.status='queued'
                """,
                (
                    job_id,
                    principal.installation_id,
                    principal.actor_user_id,
                    ordinal,
                ),
            ).fetchone()
        if stageable is None:
            raise KnowledgeNotFoundError("knowledge import entry not found")
        stage_dir = self.blob_root / "staging" / job_id
        stage_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        descriptor, temporary_name = tempfile.mkstemp(prefix=".upload-", dir=stage_dir)
        temporary = Path(temporary_name)
        destination: Path | None = None
        committed = False
        try:
            with os.fdopen(descriptor, "wb") as output:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("file exceeds the Knowledge import limit")
                    digest.update(chunk)
                    output.write(chunk)
            content_hash = f"sha256:{digest.hexdigest()}"
            staging_key = f"staging/{job_id}/{ordinal}-{digest.hexdigest()}"
            destination = self.blob_root / staging_key
            os.replace(temporary, destination)
            now = utc_now_text()
            with self.transaction(write=True) as connection:
                job = connection.execute(
                    """
                    SELECT 1 FROM knowledge_import_jobs
                    WHERE id=? AND installation_id=? AND actor_user_id=?
                    """,
                    (job_id, principal.installation_id, principal.actor_user_id),
                ).fetchone()
                if job is None:
                    raise KnowledgeNotFoundError("knowledge import job not found")
                changed = connection.execute(
                    """
                    UPDATE knowledge_import_job_entries
                    SET media_type=?,size_bytes=?,content_hash=?,staging_key=?,updated_at=?
                    WHERE job_id=? AND ordinal=? AND status='queued'
                    """,
                    (
                        (media_type or "application/octet-stream")[:255],
                        size,
                        content_hash,
                        staging_key,
                        now,
                        job_id,
                        ordinal,
                    ),
                )
                if not changed.rowcount:
                    raise KnowledgeConflictError(
                        "knowledge import entry is not stageable"
                    )
                committed = True
        finally:
            if temporary.exists():
                temporary.unlink()
            if not committed and destination is not None:
                destination.unlink(missing_ok=True)
        return self.get_import_job(principal, job_id)

    def recover_import_jobs(self) -> tuple[str, ...]:
        """Requeue entries whose worker disappeared during parsing or ingestion."""

        now = utc_now_text()
        with self.transaction(write=True) as connection:
            connection.execute(
                """
                UPDATE knowledge_import_job_entries
                SET status='queued',error='Runtime restarted during import',updated_at=?
                WHERE status='running' AND job_id IN (
                    SELECT id FROM knowledge_import_jobs
                    WHERE control_state='active'
                )
                """,
                (now,),
            )
            connection.execute(
                """
                UPDATE knowledge_import_jobs
                SET status='queued',completed_at=NULL,updated_at=?
                WHERE status='running' AND control_state='active'
                """,
                (now,),
            )
            rows = connection.execute(
                """
                SELECT DISTINCT j.id
                FROM knowledge_import_jobs j
                JOIN knowledge_import_job_entries e ON e.job_id=j.id
                WHERE j.status='queued' AND j.control_state='active'
                  AND e.status='queued' AND e.staging_key IS NOT NULL
                ORDER BY j.created_at,j.id
                """
            ).fetchall()
        return tuple(str(row["id"]) for row in rows)

    def retry_import_job(
        self, principal: RequestPrincipal, job_id: str
    ) -> dict[str, object]:
        now = utc_now_text()
        with self.transaction(write=True) as connection:
            job = connection.execute(
                """
                SELECT * FROM knowledge_import_jobs
                WHERE id=? AND installation_id=? AND actor_user_id=?
                """,
                (job_id, principal.installation_id, principal.actor_user_id),
            ).fetchone()
            if job is None:
                raise KnowledgeNotFoundError("knowledge import job not found")
            if job["control_state"] != "active":
                raise KnowledgeConflictError(
                    "paused or cancelled import jobs cannot be retried"
                )
            changed = connection.execute(
                """
                UPDATE knowledge_import_job_entries
                SET status='queued',error=NULL,item_id=NULL,updated_at=?
                WHERE job_id=? AND status='failed' AND staging_key IS NOT NULL
                """,
                (now, job_id),
            )
            if not changed.rowcount:
                raise KnowledgeConflictError(
                    "knowledge import job has no retryable files"
                )
            completed = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM knowledge_import_job_entries
                    WHERE job_id=? AND status='completed'
                    """,
                    (job_id,),
                ).fetchone()[0]
            )
            connection.execute(
                """
                UPDATE knowledge_import_jobs
                SET status='queued',completed_files=?,failed_files=0,
                    completed_at=NULL,updated_at=? WHERE id=?
                """,
                (completed, now, job_id),
            )
        return self.get_import_job(principal, job_id)

    def control_import_job(
        self, principal: RequestPrincipal, job_id: str, *, action: str
    ) -> dict[str, object]:
        """Persist a cooperative pause, resume, or cancellation request."""

        if action not in {"pause", "resume", "cancel"}:
            raise ValueError("invalid import control action")
        now = utc_now_text()
        staging_keys: list[str] = []
        with self.transaction(write=True) as connection:
            job = connection.execute(
                """
                SELECT * FROM knowledge_import_jobs
                WHERE id=? AND installation_id=? AND actor_user_id=?
                """,
                (job_id, principal.installation_id, principal.actor_user_id),
            ).fetchone()
            if job is None:
                raise KnowledgeNotFoundError("knowledge import job not found")
            terminal = job["status"] in {"completed", "partial", "failed"}
            control_state = str(job["control_state"])
            if action == "pause":
                if terminal:
                    raise KnowledgeConflictError("completed import jobs cannot be paused")
                if control_state == "cancelled":
                    raise KnowledgeConflictError("cancelled import jobs cannot be paused")
                next_state = "paused"
            elif action == "resume":
                if control_state != "paused":
                    raise KnowledgeConflictError("only paused import jobs can be resumed")
                next_state = "active"
                pending = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM knowledge_import_job_entries
                        WHERE job_id=? AND status='queued'
                        """,
                        (job_id,),
                    ).fetchone()[0]
                )
                if not pending:
                    raise KnowledgeConflictError("import job has no files left to resume")
                connection.execute(
                    """
                    UPDATE knowledge_import_jobs
                    SET status='queued',completed_at=NULL WHERE id=?
                    """,
                    (job_id,),
                )
            else:
                if terminal and control_state != "paused":
                    raise KnowledgeConflictError("completed import jobs cannot be cancelled")
                next_state = "cancelled"
                staging_keys = [
                    str(row[0])
                    for row in connection.execute(
                        """
                        SELECT staging_key FROM knowledge_import_job_entries
                        WHERE job_id=? AND status='queued' AND staging_key IS NOT NULL
                        """,
                        (job_id,),
                    ).fetchall()
                ]
                connection.execute(
                    """
                    UPDATE knowledge_import_job_entries
                    SET status='failed',error='Cancelled by user',staging_key=NULL,
                        updated_at=?
                    WHERE job_id=? AND status='queued'
                    """,
                    (now, job_id),
                )
            connection.execute(
                """
                UPDATE knowledge_import_jobs
                SET control_state=?,control_updated_at=?,updated_at=?
                WHERE id=?
                """,
                (next_state, now, now, job_id),
            )
            if action == "cancel":
                counts = connection.execute(
                    """
                    SELECT
                        SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END),
                        SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END),
                        SUM(CASE WHEN status='running' THEN 1 ELSE 0 END)
                    FROM knowledge_import_job_entries WHERE job_id=?
                    """,
                    (job_id,),
                ).fetchone()
                completed, failed, running = (int(value or 0) for value in counts)
                raw_status = "running" if running else (
                    "partial" if completed and failed else "completed" if completed else "failed"
                )
                connection.execute(
                    """
                    UPDATE knowledge_import_jobs
                    SET status=?,completed_files=?,failed_files=?,
                        completed_at=CASE WHEN ?=0 THEN ? ELSE NULL END,updated_at=?
                    WHERE id=?
                    """,
                    (raw_status, completed, failed, running, now, now, job_id),
                )
        for staging_key in staging_keys:
            (self.blob_root / staging_key).unlink(missing_ok=True)
        return self.get_import_job(principal, job_id)

    def process_import_job(self, job_id: str) -> None:
        """Run one durable job; safe to call again after a process crash."""

        with self.transaction() as connection:
            job = connection.execute(
                "SELECT * FROM knowledge_import_jobs WHERE id=?", (job_id,)
            ).fetchone()
        if job is None:
            return
        principal = RequestPrincipal(
            actor_user_id=str(job["actor_user_id"]),
            installation_id=str(job["installation_id"]),
            organization_id="local",
            billing_account_id="local",
            role=MemberRole.MEMBER,
            membership_epoch=1,
            authentication_type="internal_job",
            client_scope="desktop",
        )
        while True:
            now = utc_now_text()
            with self.transaction(write=True) as connection:
                control = connection.execute(
                    "SELECT control_state FROM knowledge_import_jobs WHERE id=?",
                    (job_id,),
                ).fetchone()
                if control is None or control["control_state"] != "active":
                    return
                entry = connection.execute(
                    """
                    SELECT * FROM knowledge_import_job_entries
                    WHERE job_id=? AND status='queued'
                    ORDER BY ordinal LIMIT 1
                    """,
                    (job_id,),
                ).fetchone()
                if entry is None:
                    return
                claimed = connection.execute(
                    """
                    UPDATE knowledge_import_job_entries
                    SET status='running',attempts=attempts+1,error=NULL,updated_at=?
                    WHERE job_id=? AND ordinal=? AND status='queued'
                    """,
                    (now, job_id, int(entry["ordinal"])),
                )
                if not claimed.rowcount:
                    continue
                connection.execute(
                    """
                    UPDATE knowledge_import_jobs
                    SET status='running',started_at=COALESCE(started_at,?),updated_at=?
                    WHERE id=?
                    """,
                    (now, now, job_id),
                )
            staging_key = entry["staging_key"]
            path = self.blob_root / str(staging_key or "missing")
            try:
                if not staging_key or not path.is_file():
                    raise FileNotFoundError("staged Knowledge upload is unavailable")
                with path.open("rb") as stream:
                    item, _asset = self.import_stream(
                        principal,
                        stream,
                        name=str(entry["filename"]),
                        media_type=entry["media_type"],
                        bucket_id=str(job["bucket_id"]),
                        source_app_id=job["source_app_id"],
                    )
                self.update_import_entry(
                    principal,
                    job_id,
                    int(entry["ordinal"]),
                    status="completed",
                    item_id=item.id,
                )
                path.unlink(missing_ok=True)
            except Exception as error:
                self.update_import_entry(
                    principal,
                    job_id,
                    int(entry["ordinal"]),
                    status="failed",
                    error=str(error),
                )
            finally:
                with self.transaction() as connection:
                    control = connection.execute(
                        "SELECT control_state FROM knowledge_import_jobs WHERE id=?",
                        (job_id,),
                    ).fetchone()
                if control is not None and control["control_state"] == "cancelled":
                    path.unlink(missing_ok=True)
                    with self.transaction(write=True) as connection:
                        connection.execute(
                            """
                            UPDATE knowledge_import_job_entries
                            SET staging_key=NULL,updated_at=?
                            WHERE job_id=? AND ordinal=?
                            """,
                            (utc_now_text(), job_id, int(entry["ordinal"])),
                        )

    def import_stream(
        self,
        principal: RequestPrincipal,
        stream: BinaryIO,
        *,
        name: str,
        media_type: str | None = None,
        bucket_id: str,
        source_app_id: str | None = None,
        source_session_id: str | None = None,
        trusted_source_facets: Sequence[tuple[str, str]] = (),
        max_bytes: int = 64 * 1024 * 1024,
    ) -> tuple[KnowledgeItem, KnowledgeAsset]:
        """Persist a file, extract bounded text, and index it in one bucket."""

        safe_name = Path(name.replace("\x00", "")).name.strip()[:512]
        if not safe_name:
            raise ValueError("a file name is required")
        media_type = (
            media_type
            or mimetypes.guess_type(safe_name)[0]
            or "application/octet-stream"
        )[:255]
        bucket = next(
            (
                item
                for item in self.ensure_system_buckets(principal)
                if item.id == bucket_id
            ),
            None,
        )
        if bucket is None:
            raise KnowledgeNotFoundError("knowledge bucket not found")
        self.blob_root.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".knowledge-upload-", dir=self.blob_root
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as output:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("file exceeds the Knowledge import limit")
                    digest.update(chunk)
                    output.write(chunk)
            hexdigest = digest.hexdigest()
            storage_key = f"sha256/{hexdigest[:2]}/{hexdigest}"
            destination = self.blob_root / storage_key
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                temporary.unlink()
            else:
                os.replace(temporary, destination)
            content_hash = f"sha256:{hexdigest}"
            with self.transaction() as connection:
                duplicate = connection.execute(
                    """
                    SELECT a.*
                    FROM knowledge_assets a
                    JOIN knowledge_items i ON i.id=a.item_id
                    WHERE a.content_hash=?
                      AND i.installation_id=?
                      AND i.visibility=?
                      AND i.deleted_at IS NULL
                      AND (
                        i.visibility='installation'
                        OR i.owner_user_id=?
                      )
                    ORDER BY i.updated_at DESC, i.id
                    LIMIT 1
                    """,
                    (
                        content_hash,
                        principal.installation_id,
                        bucket.visibility.value,
                        principal.actor_user_id,
                    ),
                ).fetchone()
            if duplicate is not None:
                item = self.get_item(principal, str(duplicate["item_id"]))
                self.add_item_to_bucket(principal, bucket_id, item.id)
                return item, self._asset(duplicate)
            text, parser, parsed_chunks = self._extract_file_text(
                destination, safe_name, media_type
            )
            item = self.create_text_item(
                principal,
                scope=bucket.visibility,
                kind=self._file_kind(media_type, safe_name),
                title=safe_name,
                text=text,
                source_app_id=source_app_id,
                source_session_id=source_session_id,
                bucket_id=bucket_id,
                parsed_chunks=parsed_chunks,
                trusted_source_facets=trusted_source_facets,
            )
            asset_id = _new_id("kas")
            now = utc_now_text()
            with self.transaction(write=True) as connection:
                connection.execute(
                    """
                    INSERT INTO knowledge_assets(
                        id,item_id,filename,media_type,content_hash,size_bytes,
                        storage_key,parser,metadata_json,created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        asset_id,
                        item.id,
                        safe_name,
                        media_type,
                        content_hash,
                        size,
                        storage_key,
                        parser,
                        json.dumps({}, separators=(",", ":")),
                        now,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM knowledge_assets WHERE id=?", (asset_id,)
                ).fetchone()
            return item, self._asset(row)
        finally:
            if temporary.exists():
                temporary.unlink()

    def asset_path(
        self, principal: RequestPrincipal, item_id: str
    ) -> tuple[KnowledgeAsset, Path]:
        self.get_item(principal, item_id)
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_assets WHERE item_id=?", (item_id,)
            ).fetchone()
        if row is None:
            raise KnowledgeNotFoundError("knowledge asset not found")
        asset = self._asset(row)
        path = (self.blob_root / asset.storage_key).resolve(strict=True)
        try:
            path.relative_to(self.blob_root.resolve(strict=True))
        except ValueError as error:
            raise KnowledgeConflictError(
                "knowledge asset path escaped storage"
            ) from error
        return asset, path

    @staticmethod
    def _file_kind(media_type: str, name: str) -> str:
        if media_type.startswith("image/"):
            return "image"
        if media_type.startswith("audio/"):
            return "audio"
        if media_type.startswith("video/"):
            return "video"
        if media_type in {"text/html", "application/xhtml+xml"}:
            return "webpage"
        return "document"

    @staticmethod
    def _extract_file_text(
        path: Path, name: str, media_type: str
    ) -> tuple[str, str, tuple[tuple[str, dict[str, object]], ...]]:
        suffix = Path(name).suffix.casefold()
        text_suffixes = {
            ".txt",
            ".md",
            ".markdown",
            ".csv",
            ".tsv",
            ".json",
            ".jsonl",
            ".xml",
            ".html",
            ".htm",
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".swift",
            ".rs",
            ".go",
            ".java",
            ".c",
            ".h",
            ".cpp",
            ".hpp",
            ".css",
            ".scss",
            ".sql",
            ".sh",
            ".yaml",
            ".yml",
            ".toml",
        }
        if (
            media_type.startswith("text/")
            or suffix in text_suffixes
            or suffix
            in {
                ".pdf",
                ".docx",
                ".pptx",
                ".xlsx",
            }
        ):
            try:
                from ai2apps.documents.parsers import DocumentParser

                blocks = DocumentParser().parse(path, name, media_type)
                parsed = []
                for block in blocks:
                    metadata = {
                        key: value
                        for key, value in {
                            "kind": block.kind,
                            "page": block.page,
                            "section": block.section,
                            "sheet": block.sheet,
                            "slide": block.slide,
                            "cell_range": block.cell_range,
                        }.items()
                        if value is not None
                    }
                    labels = []
                    if block.page is not None:
                        labels.append(f"Page {block.page}")
                    if block.slide is not None:
                        labels.append(f"Slide {block.slide}")
                    if block.sheet is not None:
                        labels.append(f"Sheet {block.sheet}")
                    if block.cell_range is not None:
                        labels.append(f"Cells {block.cell_range}")
                    prefix = f"[{' · '.join(labels)}]\n" if labels else ""
                    parsed.append((prefix + block.text, metadata))
                combined = "\n\n".join(value[0] for value in parsed).strip()
                if combined:
                    return combined[:2_000_000], "ai2apps-document/v1", tuple(parsed)
            except Exception:
                pass
        if media_type.startswith("text/") or suffix in text_suffixes:
            data = path.read_bytes()
            text = data.decode("utf-8", errors="replace")[:2_000_000]
            return text, "text/v1", ((text, {}),)
        placeholder = (
            f"PDF file awaiting text extraction: {name}"
            if media_type == "application/pdf" or suffix == ".pdf"
            else f"Binary knowledge asset: {name}\nMedia type: {media_type}"
        )
        return placeholder, "metadata/v1", ((placeholder, {}),)

    @staticmethod
    def _source_facets(
        *,
        kind: str,
        source_app_id: str | None,
        source_session_id: str | None,
        source_url: str | None,
    ) -> tuple[tuple[str, str], ...]:
        source_kind = (
            "webpage"
            if source_url
            else "chat"
            if source_session_id
            else "app"
            if source_app_id
            else "upload"
        )
        facets = [("source.kind", source_kind), ("content.kind", kind)]
        if source_app_id:
            facets.append(("source.app", source_app_id))
        if source_session_id:
            facets.append(("source.session", source_session_id))
        if source_url:
            from urllib.parse import urlsplit

            host = (urlsplit(source_url).hostname or "").casefold()
            if host:
                facets.append(("source.domain", host))
        return tuple(facets)

    @staticmethod
    def _assign_user_tag(
        connection: sqlite3.Connection,
        principal: RequestPrincipal,
        item_id: str,
        scope: KnowledgeScope,
        display_name: str,
        now: str,
    ) -> None:
        display_name = display_name.strip()
        normalized = _normalize_tag(display_name)
        if not display_name or not normalized or len(display_name) > 100:
            raise ValueError("user tag is invalid")
        row = connection.execute(
            """
            SELECT id FROM knowledge_tags
            WHERE installation_id = ? AND namespace = 'user'
              AND owner_user_id = ? AND visibility = ? AND normalized_key = ?
            """,
            (
                principal.installation_id,
                principal.actor_user_id,
                scope.value,
                normalized,
            ),
        ).fetchone()
        tag_id = row["id"] if row else _new_id("ktg")
        if row is None:
            connection.execute(
                """
                INSERT INTO knowledge_tags (
                    id, installation_id, namespace, normalized_key, display_name,
                    owner_user_id, visibility, status, created_at, updated_at
                ) VALUES (?, ?, 'user', ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    tag_id,
                    principal.installation_id,
                    normalized,
                    display_name,
                    principal.actor_user_id,
                    scope.value,
                    now,
                    now,
                ),
            )
        connection.execute(
            """
            INSERT INTO knowledge_item_tags
                (item_id, tag_id, assignment_source, status, created_at, updated_at)
            VALUES (?, ?, 'user', 'active', ?, ?)
            ON CONFLICT(item_id,tag_id) DO UPDATE SET
                status='active',updated_at=excluded.updated_at
            """,
            (item_id, tag_id, now, now),
        )

    @staticmethod
    def _visibility_args(principal: RequestPrincipal) -> tuple[str, str]:
        return principal.installation_id, principal.actor_user_id

    @staticmethod
    def _space(row: sqlite3.Row) -> KnowledgeSpace:
        return KnowledgeSpace(
            id=row["id"],
            kind=KnowledgeScope(row["kind"]),
            installation_id=row["installation_id"],
            owner_user_id=row["owner_user_id"],
            display_name=row["display_name"],
            shareability=row["shareability"],
            revision=int(row["revision"]),
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _item(row: sqlite3.Row) -> KnowledgeItem:
        return KnowledgeItem(
            id=row["id"],
            space_id=row["space_id"],
            installation_id=row["installation_id"],
            owner_user_id=row["owner_user_id"],
            created_by_user_id=row["created_by_user_id"],
            visibility=KnowledgeScope(row["visibility"]),
            kind=row["kind"],
            title=row["title"],
            text=row["text"],
            source_time=parse_utc(row["source_time"]) if row["source_time"] else None,
            source_app_id=row["source_app_id"],
            source_session_id=row["source_session_id"],
            source_url=row["source_url"],
            status=row["status"],
            revision=int(row["revision"]),
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
            deleted_at=parse_utc(row["deleted_at"]) if row["deleted_at"] else None,
        )

    @staticmethod
    def _tags_for_item(
        connection: sqlite3.Connection, principal: RequestPrincipal, item_id: str
    ) -> tuple[KnowledgeTag, ...]:
        rows = connection.execute(
            """
            SELECT t.* FROM knowledge_tags t
            JOIN knowledge_item_tags it ON it.tag_id = t.id
            WHERE it.item_id = ? AND it.status = 'active' AND t.status = 'active'
              AND (t.visibility = 'installation' OR t.owner_user_id = ?)
            ORDER BY t.display_name, t.id
            """,
            (item_id, principal.actor_user_id),
        ).fetchall()
        return tuple(
            KnowledgeTag(
                id=row["id"],
                namespace=row["namespace"],
                normalized_key=row["normalized_key"],
                display_name=row["display_name"],
                owner_user_id=row["owner_user_id"],
                visibility=KnowledgeScope(row["visibility"]),
            )
            for row in rows
        )

    @staticmethod
    def _facets_for_item(
        connection: sqlite3.Connection, item_id: str
    ) -> tuple[tuple[str, str], ...]:
        rows = connection.execute(
            """
            SELECT facet_key, value FROM knowledge_source_facets
            WHERE item_id = ? ORDER BY facet_key, value
            """,
            (item_id,),
        ).fetchall()
        return tuple((row["facet_key"], row["value"]) for row in rows)

    @staticmethod
    def _default_bucket_key(kind: str) -> str:
        if kind == "webpage":
            return "web"
        if kind == "chat":
            return "chats"
        if kind in {"document", "image", "audio", "video", "artifact"}:
            return "documents"
        return "inbox"

    @staticmethod
    def _visible_bucket_row(
        connection: sqlite3.Connection,
        principal: RequestPrincipal,
        bucket_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT b.*,
                (SELECT COUNT(*) FROM knowledge_bucket_items bi
                 JOIN knowledge_items i ON i.id=bi.item_id
                 WHERE bi.bucket_id=b.id AND i.deleted_at IS NULL) AS item_count
            FROM knowledge_buckets b
            WHERE b.id=? AND b.installation_id=?
              AND (b.visibility='installation' OR b.owner_user_id=?)
            """,
            (bucket_id, principal.installation_id, principal.actor_user_id),
        ).fetchone()
        if row is None:
            raise KnowledgeNotFoundError("knowledge bucket not found")
        return row

    @staticmethod
    def _bucket(row: sqlite3.Row) -> KnowledgeBucket:
        return KnowledgeBucket(
            id=row["id"],
            installation_id=row["installation_id"],
            owner_user_id=row["owner_user_id"],
            created_by_user_id=row["created_by_user_id"],
            visibility=KnowledgeScope(row["visibility"]),
            name=row["name"],
            kind=row["kind"],
            system_key=row["system_key"],
            item_count=int(row["item_count"]),
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _asset(row: sqlite3.Row) -> KnowledgeAsset:
        return KnowledgeAsset(
            id=row["id"],
            item_id=row["item_id"],
            filename=row["filename"],
            media_type=row["media_type"],
            content_hash=row["content_hash"],
            size_bytes=int(row["size_bytes"]),
            storage_key=row["storage_key"],
            parser=row["parser"],
            created_at=parse_utc(row["created_at"]),
        )


_VISIBLE_ITEM_SELECT = """
    SELECT i.*, r.text
    FROM knowledge_items i
    JOIN knowledge_representations r ON r.item_id = i.id AND r.ordinal = 0
    WHERE i.installation_id = ? AND i.deleted_at IS NULL
      AND (i.owner_user_id = ? OR i.visibility = 'installation')
"""


_SCHEMA_V1 = """
CREATE TABLE knowledge_spaces (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('private', 'installation')),
    installation_id TEXT NOT NULL,
    owner_user_id TEXT,
    display_name TEXT NOT NULL,
    shareability TEXT NOT NULL CHECK (shareability IN ('never', 'local_only')),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (
        (kind = 'private' AND owner_user_id IS NOT NULL AND shareability = 'never')
        OR
        (kind = 'installation' AND owner_user_id IS NULL AND shareability = 'local_only')
    )
);
CREATE UNIQUE INDEX uq_knowledge_private_space
ON knowledge_spaces(installation_id, owner_user_id) WHERE kind = 'private';
CREATE UNIQUE INDEX uq_knowledge_installation_space
ON knowledge_spaces(installation_id) WHERE kind = 'installation';

CREATE TABLE knowledge_items (
    id TEXT PRIMARY KEY,
    space_id TEXT NOT NULL REFERENCES knowledge_spaces(id) ON DELETE RESTRICT,
    installation_id TEXT NOT NULL,
    owner_user_id TEXT NOT NULL,
    created_by_user_id TEXT NOT NULL,
    visibility TEXT NOT NULL CHECK (visibility IN ('private', 'installation')),
    kind TEXT NOT NULL CHECK (kind IN ('webpage','document','image','audio','video','chat','artifact','note')),
    title TEXT NOT NULL,
    source_time TEXT,
    source_app_id TEXT,
    source_session_id TEXT,
    source_url TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending','ready','partial','failed','deleted')),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE INDEX idx_knowledge_items_visible
ON knowledge_items(installation_id, visibility, owner_user_id, updated_at DESC);

CREATE TABLE knowledge_representations (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE RESTRICT,
    kind TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    text TEXT NOT NULL,
    producer TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(item_id, ordinal)
);

CREATE TABLE knowledge_chunks (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    representation_id TEXT NOT NULL REFERENCES knowledge_representations(id) ON DELETE RESTRICT,
    item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE RESTRICT,
    space_id TEXT NOT NULL REFERENCES knowledge_spaces(id) ON DELETE RESTRICT,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    text TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    UNIQUE(representation_id, ordinal)
);

CREATE VIRTUAL TABLE knowledge_fts USING fts5(
    title,
    text,
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER knowledge_chunks_ai AFTER INSERT ON knowledge_chunks BEGIN
    INSERT INTO knowledge_fts(rowid, title, text)
    SELECT new.rowid, i.title, new.text FROM knowledge_items i WHERE i.id = new.item_id;
END;
CREATE TRIGGER knowledge_chunks_ad AFTER DELETE ON knowledge_chunks BEGIN
    DELETE FROM knowledge_fts WHERE rowid = old.rowid;
END;
CREATE TRIGGER knowledge_chunks_au AFTER UPDATE ON knowledge_chunks BEGIN
    DELETE FROM knowledge_fts WHERE rowid = old.rowid;
    INSERT INTO knowledge_fts(rowid, title, text)
    SELECT new.rowid, i.title, new.text FROM knowledge_items i WHERE i.id = new.item_id;
END;

CREATE TABLE knowledge_source_facets (
    item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE RESTRICT,
    facet_key TEXT NOT NULL,
    value TEXT NOT NULL,
    authority TEXT NOT NULL CHECK (authority = 'runtime'),
    created_at TEXT NOT NULL,
    PRIMARY KEY(item_id, facet_key, value)
);

CREATE TABLE knowledge_tags (
    id TEXT PRIMARY KEY,
    installation_id TEXT NOT NULL,
    namespace TEXT NOT NULL CHECK (namespace = 'user'),
    normalized_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    owner_user_id TEXT NOT NULL,
    visibility TEXT NOT NULL CHECK (visibility IN ('private', 'installation')),
    status TEXT NOT NULL CHECK (status IN ('active', 'deleted')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(installation_id, namespace, owner_user_id, visibility, normalized_key)
);

CREATE TABLE knowledge_item_tags (
    item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE RESTRICT,
    tag_id TEXT NOT NULL REFERENCES knowledge_tags(id) ON DELETE RESTRICT,
    assignment_source TEXT NOT NULL CHECK (assignment_source = 'user'),
    status TEXT NOT NULL CHECK (status IN ('active', 'rejected')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(item_id, tag_id)
);

CREATE TABLE knowledge_tag_suggestions (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
    installation_id TEXT NOT NULL,
    actor_user_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    normalized_key TEXT NOT NULL,
    producer TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    evidence_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(evidence_json)),
    status TEXT NOT NULL DEFAULT 'suggested'
        CHECK (status IN ('suggested','confirmed','rejected')),
    confirmed_tag_id TEXT REFERENCES knowledge_tags(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(item_id, actor_user_id, normalized_key, producer)
);

CREATE TABLE knowledge_change_log (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT NOT NULL CHECK (operation IN ('create', 'update', 'delete')),
    item_id TEXT NOT NULL,
    space_id TEXT NOT NULL,
    authoritative_revision INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE knowledge_import_jobs (
    id TEXT PRIMARY KEY,
    installation_id TEXT NOT NULL,
    actor_user_id TEXT NOT NULL,
    bucket_id TEXT NOT NULL REFERENCES knowledge_buckets(id) ON DELETE CASCADE,
    source_app_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('queued','running','completed','partial','failed')),
    control_state TEXT NOT NULL DEFAULT 'active'
        CHECK (control_state IN ('active','paused','cancelled')),
    control_updated_at TEXT,
    total_files INTEGER NOT NULL CHECK (total_files > 0),
    completed_files INTEGER NOT NULL DEFAULT 0 CHECK (completed_files >= 0),
    failed_files INTEGER NOT NULL DEFAULT 0 CHECK (failed_files >= 0),
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE knowledge_import_job_entries (
    job_id TEXT NOT NULL REFERENCES knowledge_import_jobs(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    filename TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed')),
    item_id TEXT REFERENCES knowledge_items(id) ON DELETE SET NULL,
    error TEXT,
    media_type TEXT,
    size_bytes INTEGER CHECK (size_bytes IS NULL OR size_bytes >= 0),
    content_hash TEXT,
    staging_key TEXT,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    updated_at TEXT NOT NULL,
    PRIMARY KEY(job_id, ordinal)
);
CREATE INDEX ix_knowledge_import_jobs_owner
ON knowledge_import_jobs(installation_id, actor_user_id, created_at DESC);
CREATE INDEX ix_knowledge_import_entries_status
ON knowledge_import_job_entries(status, updated_at, job_id, ordinal);

CREATE TABLE knowledge_settings (
    installation_id TEXT PRIMARY KEY,
    budget_bytes INTEGER NOT NULL DEFAULT 10737418240 CHECK (budget_bytes > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""
