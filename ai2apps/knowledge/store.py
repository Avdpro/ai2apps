"""SQLite/FTS5 authority for the opt-in local Knowledge Core.

This module deliberately has no imports from MLX, model providers, FastAPI or
the installable Package runtime.  Callers must pass a trusted RequestPrincipal;
ownership checks are performed in every repository query.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from ai2apps.core import parse_utc, utc_now_text
from ai2apps.identity import MemberRole, RequestPrincipal

from .models import (
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


def _fts_query(value: str) -> str:
    # Release A exposes literal token matching, not raw FTS query syntax.
    tokens = [token for token in _TAG_SPACE.split(value.strip()) if token]
    return " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)


class KnowledgeStore:
    """An explicitly initialized, standalone Knowledge database."""

    def __init__(self, path: str | Path, *, busy_timeout_ms: int = 5_000) -> None:
        self.path = Path(path).expanduser().resolve()
        self.busy_timeout_ms = busy_timeout_ms

    def connect(self) -> sqlite3.Connection:
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
        """Create the isolated schema. Nothing calls this during App startup."""

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
                    (private_id, principal.installation_id, principal.actor_user_id, now, now),
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
    ) -> KnowledgeItem:
        """Save one text representation and synchronously index it with FTS5."""

        if kind not in ALLOWED_KINDS:
            raise ValueError(f"unsupported knowledge kind: {kind}")
        title = title.strip()
        text = text.strip()
        if not title or not text:
            raise ValueError("title and text must not be empty")
        if scope is KnowledgeScope.INSTALLATION and principal.role not in SHARED_CONTRIBUTOR_ROLES:
            raise KnowledgeAccessError("this role cannot contribute Local shared knowledge")
        private, shared = self.ensure_builtin_spaces(principal)
        space = private if scope is KnowledgeScope.PRIVATE else shared
        item_id = _new_id("kit")
        representation_id = _new_id("krp")
        chunk_id = _new_id("kch")
        now = utc_now_text()
        facets = self._source_facets(
            kind=kind,
            source_app_id=source_app_id,
            source_session_id=source_session_id,
            source_url=source_url,
        )
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
            connection.execute(
                """
                INSERT INTO knowledge_chunks (
                    id, representation_id, item_id, space_id, ordinal, text, created_at
                ) VALUES (?, ?, ?, ?, 0, ?, ?)
                """,
                (chunk_id, representation_id, item_id, space.id, text, now),
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
                self._assign_user_tag(connection, principal, item_id, scope, display_name, now)
            connection.execute(
                """
                INSERT INTO knowledge_change_log
                    (operation, item_id, space_id, authoritative_revision, created_at)
                VALUES ('create', ?, ?, 1, ?)
                """,
                (item_id, space.id, now),
            )
            row = connection.execute(
                _VISIBLE_ITEM_SELECT + " AND i.id = ?", self._visibility_args(principal) + (item_id,)
            ).fetchone()
        assert row is not None
        return self._item(row)

    def get_item(self, principal: RequestPrincipal, item_id: str) -> KnowledgeItem:
        with self.transaction() as connection:
            row = connection.execute(
                _VISIBLE_ITEM_SELECT + " AND i.id = ?", self._visibility_args(principal) + (item_id,)
            ).fetchone()
        if row is None:
            raise KnowledgeNotFoundError("knowledge item not found")
        return self._item(row)

    def search(
        self,
        principal: RequestPrincipal,
        query: str,
        *,
        scope: KnowledgeScope | None = None,
        kind: str | None = None,
        tags: Sequence[str] = (),
        limit: int = 20,
    ) -> tuple[KnowledgeSearchHit, ...]:
        """Search only rows visible to the principal, before ranking/limit."""

        match = _fts_query(query)
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
        arguments: list[object] = [match, principal.installation_id, principal.actor_user_id]
        if scope is not None:
            clauses.append("i.visibility = ?")
            arguments.append(scope.value)
        if kind is not None:
            clauses.append("i.kind = ?")
            arguments.append(kind)
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
        arguments.append(limit)
        sql = f"""
            SELECT i.*, r.text,
                   snippet(knowledge_fts, 1, '<mark>', '</mark>', ' … ', 24) AS excerpt,
                   bm25(knowledge_fts, 3.0, 1.0) AS fts_rank
            FROM knowledge_fts
            JOIN knowledge_chunks c ON c.rowid = knowledge_fts.rowid
            JOIN knowledge_items i ON i.id = c.item_id
            JOIN knowledge_representations r ON r.item_id = i.id AND r.ordinal = 0
            WHERE knowledge_fts MATCH ? AND {' AND '.join(clauses)}
            ORDER BY fts_rank, i.updated_at DESC, i.id
            LIMIT ?
        """
        with self.transaction() as connection:
            rows = connection.execute(sql, tuple(arguments)).fetchall()
            hits = []
            for row in rows:
                item = self._item(row)
                hits.append(
                    KnowledgeSearchHit(
                        item=item,
                        excerpt=str(row["excerpt"]),
                        rank=float(row["fts_rank"]),
                        tags=self._tags_for_item(connection, principal, item.id),
                        source_facets=self._facets_for_item(connection, item.id),
                    )
                )
        return tuple(hits)

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

    @staticmethod
    def _source_facets(
        *, kind: str, source_app_id: str | None, source_session_id: str | None, source_url: str | None
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
            (principal.installation_id, principal.actor_user_id, scope.value, normalized),
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
    INSERT INTO knowledge_fts(knowledge_fts, rowid, title, text)
    SELECT 'delete', old.rowid, i.title, old.text FROM knowledge_items i WHERE i.id = old.item_id;
END;
CREATE TRIGGER knowledge_chunks_au AFTER UPDATE ON knowledge_chunks BEGIN
    INSERT INTO knowledge_fts(knowledge_fts, rowid, title, text)
    SELECT 'delete', old.rowid, i.title, old.text FROM knowledge_items i WHERE i.id = old.item_id;
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

CREATE TABLE knowledge_change_log (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT NOT NULL CHECK (operation IN ('create', 'update', 'delete')),
    item_id TEXT NOT NULL,
    space_id TEXT NOT NULL,
    authoritative_revision INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE knowledge_settings (
    installation_id TEXT PRIMARY KEY,
    budget_bytes INTEGER NOT NULL DEFAULT 10737418240 CHECK (budget_bytes > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""
