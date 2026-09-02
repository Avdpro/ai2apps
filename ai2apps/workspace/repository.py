"""Session-isolated filesystem, ResourceHandle, and Artifact persistence."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import shutil
import tempfile
from contextlib import suppress
from pathlib import Path, PurePosixPath
from typing import Any

from ai2apps.config import (
    DEFAULT_RESOURCE_IMPORT_LIMIT_BYTES,
    DEFAULT_SESSION_WORKSPACE_QUOTA_BYTES,
    DEFAULT_WORKSPACE_READ_LIMIT_BYTES,
    PlatformPaths,
)
from ai2apps.core import (
    EntityIdKind,
    ResourceNotFoundError,
    new_entity_id,
    parse_utc,
    utc_now_text,
)
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase

from .broker import HostExportBroker, LocalHostExportBroker
from .models import (
    ArtifactRecord,
    LocatorKind,
    ResourceHandleRecord,
    ResourceKind,
    SandboxRecord,
    WorkspaceError,
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _time(value: str | None):
    return None if value is None else parse_utc(value)


def _safe_name(value: str) -> str:
    name = Path(value).name.strip().replace("\x00", "")
    if not name or name in {".", ".."}:
        raise WorkspaceError("invalid_name", "A safe filename is required")
    return name[:255]


class WorkspaceRepository:
    def __init__(
        self,
        database: PlatformDatabase,
        events: EventStore,
        paths: PlatformPaths,
        broker: HostExportBroker | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.paths = paths
        self.broker = broker or LocalHostExportBroker()

    @staticmethod
    def _sandbox(row) -> SandboxRecord:
        return SandboxRecord(
            id=row["id"],
            session_id=row["session_id"],
            quota_bytes=row["quota_bytes"],
            used_bytes=row["used_bytes"],
            revision=row["revision"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _handle(row) -> ResourceHandleRecord:
        return ResourceHandleRecord(
            id=row["id"],
            session_id=row["session_id"],
            artifact_id=row["artifact_id"],
            kind=ResourceKind(row["kind"]),
            display_name=row["display_name"],
            locator_kind=LocatorKind(row["locator_kind"]),
            locator=row["locator"],
            capabilities=tuple(json.loads(row["capabilities_json"])),
            media_type=row["media_type"],
            size_bytes=row["size_bytes"],
            content_hash=row["content_hash"],
            source=row["source"],
            expires_at=_time(row["expires_at"]),
            revoked_at=_time(row["revoked_at"]),
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _artifact(row) -> ArtifactRecord:
        return ArtifactRecord(
            id=row["id"],
            session_id=row["session_id"],
            run_id=row["run_id"],
            name=row["name"],
            media_type=row["media_type"],
            content_hash=row["content_hash"],
            size_bytes=row["size_bytes"],
            storage_key=row["storage_key"],
            status=row["status"],
            metadata=json.loads(row["metadata_json"]),
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    def _root(self, session_id: str) -> Path:
        return self.paths.sandboxes_path / session_id / "workspace"

    def _temporary_root(self, session_id: str) -> Path:
        return self.paths.sandboxes_path / session_id / "temporary"

    def resolve_browser_upload(self, session_id: str, relative_path: str) -> Path:
        """Resolve an Agent-selected upload strictly inside its Session workspace."""

        path = self._resolve(session_id, relative_path)
        if not path.is_file() or path.is_symlink():
            raise WorkspaceError("not_file", f"Not an uploadable file: {relative_path}")
        return path

    def browser_download_directory(self, session_id: str) -> Path:
        """Return the isolated temporary Chrome download directory for a Session."""

        self.ensure_sandbox(session_id)
        directory = self._temporary_root(session_id) / "browser-downloads"
        directory.mkdir(parents=True, exist_ok=True)
        return directory.resolve(strict=True)

    def adopt_browser_download(self, session_id: str, filename: str) -> dict[str, Any]:
        """Move a completed Chrome download into the durable Session workspace."""

        safe_name = _safe_name(filename)
        source_root = self.browser_download_directory(session_id)
        source = (source_root / safe_name).resolve(strict=True)
        try:
            source.relative_to(source_root)
        except ValueError as exc:
            raise WorkspaceError("path_escape", "Download escaped its staging root") from exc
        if not source.is_file() or source.is_symlink() or source.name.endswith(".crdownload"):
            raise WorkspaceError("download_incomplete", f"Incomplete download: {safe_name}")
        destination_dir = self._resolve(session_id, "downloads", missing=True)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / safe_name
        stem, suffix = destination.stem, destination.suffix
        serial = 2
        while destination.exists():
            destination = destination_dir / f"{stem}-{serial}{suffix}"
            serial += 1
        size = source.stat().st_size
        self._check_quota(session_id, 0, size)
        os.replace(source, destination)
        self._sync_usage(session_id)
        return {
            "name": destination.name,
            "path": destination.relative_to(self._root(session_id)).as_posix(),
            "size_bytes": size,
            "media_type": mimetypes.guess_type(destination.name)[0]
            or "application/octet-stream",
        }

    def ensure_sandbox(self, session_id: str) -> SandboxRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            session = connection.execute(
                "SELECT id FROM sessions WHERE id = ? AND status != 'deleted'",
                (session_id,),
            ).fetchone()
            if session is None:
                raise ResourceNotFoundError("session", session_id)
            row = connection.execute(
                "SELECT * FROM session_sandboxes WHERE session_id = ?", (session_id,)
            ).fetchone()
            if row is None:
                sandbox_id = new_entity_id(EntityIdKind.SESSION_SANDBOX)
                connection.execute(
                    """INSERT INTO session_sandboxes(
                        id, session_id, quota_bytes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)""",
                    (
                        sandbox_id,
                        session_id,
                        DEFAULT_SESSION_WORKSPACE_QUOTA_BYTES,
                        now,
                        now,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM session_sandboxes WHERE id = ?", (sandbox_id,)
                ).fetchone()
            assert row is not None
        self._root(session_id).mkdir(parents=True, exist_ok=True)
        self._temporary_root(session_id).mkdir(parents=True, exist_ok=True)
        return self._sandbox(row)

    def _resolve(
        self, session_id: str, relative_path: str, *, missing: bool = False
    ) -> Path:
        self.ensure_sandbox(session_id)
        raw = PurePosixPath(relative_path)
        if raw.is_absolute() or ".." in raw.parts or "\x00" in relative_path:
            raise WorkspaceError(
                "path_escape", "Workspace paths must be safe and relative"
            )
        root = self._root(session_id).resolve(strict=True)
        candidate = root.joinpath(*raw.parts)
        resolved = candidate.resolve(strict=not missing)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise WorkspaceError(
                "path_escape", "Path escapes the Session workspace"
            ) from exc
        return resolved

    def _used_bytes(self, session_id: str) -> int:
        total = 0
        for path in self._root(session_id).rglob("*"):
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        return total

    def _check_quota(self, session_id: str, replaced: int, incoming: int) -> None:
        sandbox = self.ensure_sandbox(session_id)
        used = self._used_bytes(session_id)
        if used - replaced + incoming > sandbox.quota_bytes:
            raise WorkspaceError(
                "workspace_quota_exceeded", "Session workspace quota exceeded"
            )

    def _sync_usage(self, session_id: str) -> None:
        now = utc_now_text()
        used = self._used_bytes(session_id)
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE session_sandboxes SET used_bytes = ?, revision = revision + 1,
                   updated_at = ? WHERE session_id = ?""",
                (used, now, session_id),
            )

    def list(
        self, session_id: str, path: str = ".", *, offset: int = 0, limit: int = 200
    ):
        directory = self._resolve(session_id, path)
        if not directory.is_dir():
            raise WorkspaceError("not_directory", f"Not a directory: {path}")
        entries = sorted(
            directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())
        )
        root = self._root(session_id).resolve()
        result = []
        for item in entries[offset : offset + limit]:
            stat = item.lstat()
            result.append(
                {
                    "name": item.name,
                    "path": item.relative_to(root).as_posix(),
                    "kind": "symlink"
                    if item.is_symlink()
                    else "directory"
                    if item.is_dir()
                    else "file",
                    "size_bytes": stat.st_size if item.is_file() else None,
                    "modified_at": stat.st_mtime,
                }
            )
        return {
            "items": result,
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < len(entries),
        }

    def stat(self, session_id: str, path: str):
        item = self._resolve(session_id, path)
        stat = item.stat()
        return {
            "path": path,
            "kind": "directory" if item.is_dir() else "file",
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
        }

    def read(
        self,
        session_id: str,
        path: str,
        *,
        offset: int = 0,
        limit: int = DEFAULT_WORKSPACE_READ_LIMIT_BYTES,
    ):
        item = self._resolve(session_id, path)
        if not item.is_file():
            raise WorkspaceError("not_file", f"Not a file: {path}")
        with item.open("rb") as file:
            file.seek(offset)
            content = file.read(limit + 1)
        truncated = len(content) > limit
        content = content[:limit]
        try:
            text = content.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            text = base64.b64encode(content).decode("ascii")
            encoding = "base64"
        return {
            "path": path,
            "content": text,
            "encoding": encoding,
            "offset": offset,
            "bytes_returned": len(content),
            "truncated": truncated,
        }

    def write(
        self, session_id: str, path: str, content: str, *, encoding: str = "utf-8"
    ):
        destination = self._resolve(session_id, path, missing=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Re-resolve after mkdir to catch a concurrently introduced symlink.
        destination = self._resolve(session_id, path, missing=True)
        data = (
            content.encode("utf-8")
            if encoding == "utf-8"
            else base64.b64decode(content, validate=True)
        )
        replaced = (
            destination.stat().st_size
            if destination.exists() and destination.is_file()
            else 0
        )
        self._check_quota(session_id, replaced, len(data))
        descriptor, temporary = tempfile.mkstemp(
            prefix=".ai2apps-write-", dir=destination.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, destination)
        except BaseException:
            with suppress(FileNotFoundError):
                os.unlink(temporary)
            raise
        self._sync_usage(session_id)
        digest = hashlib.sha256(data).hexdigest()
        self._event(
            session_id,
            "workspace.file.written",
            path,
            {"path": path, "size_bytes": len(data), "content_hash": f"sha256:{digest}"},
        )
        return {
            "path": path,
            "size_bytes": len(data),
            "content_hash": f"sha256:{digest}",
        }

    def apply_patch(
        self, session_id: str, path: str, replacements: list[dict[str, Any]]
    ):
        current = self.read(session_id, path, limit=DEFAULT_WORKSPACE_READ_LIMIT_BYTES)
        if current["encoding"] != "utf-8" or current["truncated"]:
            raise WorkspaceError(
                "patch_target_unsupported", "Patch target must be bounded UTF-8 text"
            )
        text = current["content"]
        applied = 0
        for replacement in replacements:
            old = replacement.get("old")
            new = replacement.get("new")
            count = int(replacement.get("count", 1))
            if not isinstance(old, str) or not isinstance(new, str) or not old:
                raise WorkspaceError(
                    "invalid_patch",
                    "Each replacement needs non-empty old and string new",
                )
            occurrences = text.count(old)
            if occurrences < count:
                raise WorkspaceError(
                    "patch_conflict",
                    f"Expected {count} occurrence(s), found {occurrences}",
                )
            text = text.replace(old, new, count)
            applied += count
        result = self.write(session_id, path, text)
        return {**result, "replacements_applied": applied}

    def search(self, session_id: str, query: str, *, path: str = ".", limit: int = 100):
        if not query:
            raise WorkspaceError("invalid_query", "Search query cannot be empty")
        root = self._resolve(session_id, path)
        files = [root] if root.is_file() else sorted(root.rglob("*"))
        matches = []
        workspace_root = self._root(session_id).resolve()
        for file in files:
            if len(matches) >= limit or not file.is_file() or file.is_symlink():
                continue
            try:
                text = file.read_text("utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if query.lower() in line.lower():
                    matches.append(
                        {
                            "path": file.relative_to(workspace_root).as_posix(),
                            "line": number,
                            "text": line[:500],
                        }
                    )
                    if len(matches) >= limit:
                        break
        return {"matches": matches, "truncated": len(matches) >= limit}

    def import_bytes(
        self,
        session_id: str,
        filename: str,
        data: bytes,
        *,
        media_type: str | None = None,
        source: str = "user_picker",
    ):
        if len(data) > DEFAULT_RESOURCE_IMPORT_LIMIT_BYTES:
            raise WorkspaceError(
                "resource_too_large", "Selected resource exceeds import limit"
            )
        handle_id = new_entity_id(EntityIdKind.RESOURCE_HANDLE)
        name = _safe_name(filename)
        relative = f"imports/{handle_id}/{name}"
        encoded = base64.b64encode(data).decode("ascii")
        written = self.write(session_id, relative, encoded, encoding="base64")
        return self._insert_handle(
            handle_id=handle_id,
            session_id=session_id,
            kind=ResourceKind.FILE,
            display_name=name,
            locator_kind=LocatorKind.WORKSPACE,
            locator=relative,
            capabilities=("read",),
            media_type=media_type or mimetypes.guess_type(name)[0],
            size_bytes=len(data),
            content_hash=written["content_hash"],
            source=source,
        )

    def _insert_handle(
        self,
        *,
        handle_id: str,
        session_id: str,
        kind: ResourceKind,
        display_name: str,
        locator_kind: LocatorKind,
        locator: str,
        capabilities: tuple[str, ...],
        source: str,
        artifact_id: str | None = None,
        media_type: str | None = None,
        size_bytes: int | None = None,
        content_hash: str | None = None,
    ):
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO resource_handles(
                    id, session_id, artifact_id, kind, display_name, locator_kind,
                    locator, capabilities_json, media_type, size_bytes, content_hash,
                    source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    handle_id,
                    session_id,
                    artifact_id,
                    kind.value,
                    display_name,
                    locator_kind.value,
                    locator,
                    _json(capabilities),
                    media_type,
                    size_bytes,
                    content_hash,
                    source,
                    now,
                    now,
                ),
            )
            session = connection.execute(
                "SELECT app_instance_id FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            assert session is not None
            self.events.append_in_transaction(
                connection,
                event_type="resource.handle.created",
                subject_id=handle_id,
                app_instance_id=session["app_instance_id"],
                session_id=session_id,
                payload={
                    "kind": kind.value,
                    "display_name": display_name,
                    "capabilities": capabilities,
                    "source": source,
                },
            )
            row = connection.execute(
                "SELECT * FROM resource_handles WHERE id = ?", (handle_id,)
            ).fetchone()
            assert row is not None
            return self._handle(row)

    def get_handle(
        self, session_id: str, handle_or_uri: str, *, capability: str | None = None
    ):
        handle_id = handle_or_uri.removeprefix("resource://")
        now = utc_now_text()
        with self.database.transaction() as connection:
            row = connection.execute(
                """SELECT * FROM resource_handles WHERE id = ? AND session_id = ?
                   AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > ?)""",
                (handle_id, session_id, now),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("resource_handle", handle_id)
        record = self._handle(row)
        if capability is not None and capability not in record.capabilities:
            raise WorkspaceError(
                "resource_capability_denied", f"Handle lacks {capability}"
            )
        return record

    def list_handles(self, session_id: str):
        self.ensure_sandbox(session_id)
        now = utc_now_text()
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT * FROM resource_handles WHERE session_id = ?
                   AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > ?)
                   ORDER BY created_at DESC""",
                (session_id, now),
            ).fetchall()
        return tuple(self._handle(row) for row in rows)

    def revoke_handle(self, session_id: str, handle_id: str):
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            changed = connection.execute(
                """UPDATE resource_handles SET revoked_at = ?, updated_at = ?
                   WHERE id = ? AND session_id = ? AND revoked_at IS NULL""",
                (now, now, handle_id, session_id),
            ).rowcount
            if not changed:
                raise ResourceNotFoundError("resource_handle", handle_id)

    def create_artifact(
        self,
        session_id: str,
        source_path: str,
        name: str | None = None,
        *,
        run_id: str | None = None,
        media_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        source = self._resolve(session_id, source_path)
        return self.import_artifact(
            session_id,
            source,
            name,
            run_id=run_id,
            media_type=media_type,
            metadata=metadata,
        )

    def import_artifact(
        self,
        session_id: str,
        source: Path,
        name: str | None = None,
        *,
        run_id: str | None = None,
        media_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Atomically import a trusted Host file without buffering it in memory."""

        self.ensure_sandbox(session_id)
        if not source.is_file():
            raise WorkspaceError("not_file", "Artifact source must be a file")
        hasher = hashlib.sha256()
        size = 0
        with source.open("rb") as input_file:
            while chunk := input_file.read(8 * 1024 * 1024):
                hasher.update(chunk)
                size += len(chunk)
        digest = hasher.hexdigest()
        artifact_name = _safe_name(name or source.name)
        storage_key = f"sha256/{digest[:2]}/{digest}"
        destination = self.paths.artifacts_path / storage_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            descriptor, temporary = tempfile.mkstemp(
                prefix=".artifact-", dir=destination.parent
            )
            try:
                with source.open("rb") as input_file, os.fdopen(descriptor, "wb") as output:
                    shutil.copyfileobj(input_file, output, length=8 * 1024 * 1024)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, destination)
            except BaseException:
                with suppress(FileNotFoundError):
                    os.unlink(temporary)
                raise
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            existing = connection.execute(
                """SELECT * FROM artifacts WHERE session_id = ? AND content_hash = ?
                   AND name = ?""",
                (session_id, f"sha256:{digest}", artifact_name),
            ).fetchone()
            if existing is not None:
                return self._artifact(existing)
            artifact_id = new_entity_id(EntityIdKind.ARTIFACT)
            connection.execute(
                """INSERT INTO artifacts(
                    id, session_id, run_id, name, media_type, content_hash,
                    size_bytes, storage_key, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    artifact_id,
                    session_id,
                    run_id,
                    artifact_name,
                    media_type
                    or mimetypes.guess_type(artifact_name)[0]
                    or "application/octet-stream",
                    f"sha256:{digest}",
                    size,
                    storage_key,
                    _json(metadata or {}),
                    now,
                    now,
                ),
            )
            session = connection.execute(
                "SELECT app_instance_id FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            assert session is not None
            self.events.append_in_transaction(
                connection,
                event_type="artifact.created",
                subject_id=artifact_id,
                app_instance_id=session["app_instance_id"],
                session_id=session_id,
                trace_id=run_id,
                payload={
                    "name": artifact_name,
                    "media_type": media_type,
                    "size_bytes": size,
                    "content_hash": f"sha256:{digest}",
                },
            )
            row = connection.execute(
                "SELECT * FROM artifacts WHERE id = ?", (artifact_id,)
            ).fetchone()
            assert row is not None
            return self._artifact(row)

    def get_artifact(self, session_id: str, artifact_id: str):
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM artifacts WHERE id = ? AND session_id = ? AND status = 'active'",
                (artifact_id, session_id),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("artifact", artifact_id)
        return self._artifact(row)

    def list_artifacts(self, session_id: str):
        self.ensure_sandbox(session_id)
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT * FROM artifacts WHERE session_id = ? AND status = 'active'
                   ORDER BY created_at DESC""",
                (session_id,),
            ).fetchall()
        return tuple(self._artifact(row) for row in rows)

    def artifact_path(self, artifact: ArtifactRecord) -> Path:
        path = (self.paths.artifacts_path / artifact.storage_key).resolve(strict=True)
        path.relative_to(self.paths.artifacts_path.resolve(strict=True))
        return path

    def preview_artifact(
        self, session_id: str, artifact_id: str, limit: int = 256 * 1024
    ):
        artifact = self.get_artifact(session_id, artifact_id)
        data = self.artifact_path(artifact).read_bytes()[: limit + 1]
        truncated = len(data) > limit
        data = data[:limit]
        if artifact.media_type.startswith("text/") or artifact.media_type in {
            "application/json",
            "image/svg+xml",
        }:
            content, encoding = data.decode("utf-8", errors="replace"), "utf-8"
        else:
            content, encoding = base64.b64encode(data).decode("ascii"), "base64"
        return {
            "artifact_id": artifact.id,
            "media_type": artifact.media_type,
            "content": content,
            "encoding": encoding,
            "truncated": truncated,
        }

    def register_external_directory(
        self, session_id: str, directory: Path, *, display_name: str | None = None
    ):
        resolved = directory.expanduser().resolve(strict=True)
        if not resolved.is_dir():
            raise NotADirectoryError(str(resolved))
        return self._insert_handle(
            handle_id=new_entity_id(EntityIdKind.RESOURCE_HANDLE),
            session_id=session_id,
            kind=ResourceKind.DIRECTORY,
            display_name=display_name or resolved.name,
            locator_kind=LocatorKind.EXTERNAL,
            locator=str(resolved),
            capabilities=("export",),
            source="trusted_host_picker",
        )

    def export_artifact(
        self,
        session_id: str,
        artifact_id: str,
        destination_handle: str,
        name: str | None = None,
    ):
        artifact = self.get_artifact(session_id, artifact_id)
        handle = self.get_handle(session_id, destination_handle, capability="export")
        if (
            handle.kind is not ResourceKind.DIRECTORY
            or handle.locator_kind is not LocatorKind.EXTERNAL
        ):
            raise WorkspaceError(
                "invalid_export_target", "Export needs an external directory handle"
            )
        export_id = new_entity_id(EntityIdKind.ARTIFACT_EXPORT)
        export_name = _safe_name(name or artifact.name)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO artifact_exports(
                    id, artifact_id, session_id, destination_handle_id,
                    destination_name, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (export_id, artifact.id, session_id, handle.id, export_name, now, now),
            )
        try:
            destination = self.broker.export(
                self.artifact_path(artifact), Path(handle.locator), export_name
            )
        except BaseException as exc:
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    """UPDATE artifact_exports SET status = 'failed', error_json = ?,
                       updated_at = ? WHERE id = ?""",
                    (
                        _json({"type": type(exc).__name__, "message": str(exc)}),
                        utc_now_text(),
                        export_id,
                    ),
                )
            raise
        completed = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE artifact_exports SET status = 'completed', content_hash = ?,
                   completed_at = ?, updated_at = ? WHERE id = ?""",
                (artifact.content_hash, completed, completed, export_id),
            )
        return {
            "export_id": export_id,
            "name": export_name,
            "content_hash": artifact.content_hash,
            "destination": destination.name,
        }

    def _event(
        self, session_id: str, event_type: str, subject_id: str, payload: dict[str, Any]
    ):
        with self.database.transaction(write=True) as connection:
            session = connection.execute(
                "SELECT app_instance_id FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            assert session is not None
            self.events.append_in_transaction(
                connection,
                event_type=event_type,
                subject_id=subject_id,
                app_instance_id=session["app_instance_id"],
                session_id=session_id,
                payload=payload,
            )
