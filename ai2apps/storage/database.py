"""SQLite connection and bootstrap boundary for AI2Apps platform state."""

from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from ai2apps.config import PLATFORM_DATABASE_SCHEMA_VERSION
from ai2apps.storage.migrations import (
    DatabaseBusyError,
    DatabaseCorruptionError,
    apply_migrations,
)

DEFAULT_BUSY_TIMEOUT_MS = 5_000
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DatabaseState:
    """Observed state after a successful database bootstrap."""

    path: Path
    schema_version: int
    journal_mode: str


@dataclass(frozen=True, slots=True)
class DatabaseDiagnostics:
    """Read-only operator diagnostics for the live SQLite database."""

    path: Path
    schema_version: int
    journal_mode: str
    quick_check: str
    foreign_key_violations: int
    page_count: int
    page_size: int


@dataclass(frozen=True, slots=True)
class DatabaseBackupState:
    """Validated snapshot produced by SQLite's online backup API."""

    source_path: Path
    destination_path: Path
    schema_version: int
    quick_check: str


class PlatformDatabase:
    """Own SQLite setup while keeping transactions explicit and short-lived."""

    def __init__(
        self,
        path: str | Path,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> None:
        self.path = Path(path).expanduser().resolve()
        self.busy_timeout_ms = busy_timeout_ms
        self._commit_hooks: dict[int, list[Callable[[], None]]] = {}
        self._commit_hooks_lock = Lock()

    def after_commit(
        self,
        connection: sqlite3.Connection,
        callback: Callable[[], None],
    ) -> None:
        """Register a non-throwing notification callback for this transaction."""

        with self._commit_hooks_lock:
            self._commit_hooks.setdefault(id(connection), []).append(callback)

    def _take_commit_hooks(self, connection: sqlite3.Connection):
        with self._commit_hooks_lock:
            return self._commit_hooks.pop(id(connection), [])

    def connect(self) -> sqlite3.Connection:
        """Open a configured connection; callers own its transaction and close."""

        connection = sqlite3.connect(
            self.path,
            timeout=self.busy_timeout_ms / 1_000,
            isolation_level=None,
        )
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        return connection

    @contextmanager
    def transaction(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        """Open one explicit short transaction and always close its connection."""

        connection = self.connect()
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
            for callback in self._take_commit_hooks(connection):
                try:
                    callback()
                except Exception:
                    logger.exception("AI2Apps post-commit notification failed")
        except Exception:
            connection.rollback()
            self._take_commit_hooks(connection)
            raise
        finally:
            connection.close()

    def _enable_wal(self, connection: sqlite3.Connection) -> str:
        """Enable WAL with bounded retry for SQLite's journal-mode lock gap."""

        deadline = time.monotonic() + self.busy_timeout_ms / 1_000
        while True:
            try:
                row = connection.execute("PRAGMA journal_mode = WAL").fetchone()
                return str(row[0]).lower() if row else ""
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
                if time.monotonic() >= deadline:
                    raise DatabaseBusyError(
                        "Platform database remained locked during WAL setup"
                    ) from exc
                time.sleep(0.025)

    def initialize(self) -> DatabaseState:
        """Create the managed directory, verify SQLite, and migrate to latest."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = self.connect()
        try:
            journal_mode = self._enable_wal(connection)
            connection.execute("PRAGMA synchronous = NORMAL")
            quick_check = connection.execute("PRAGMA quick_check").fetchone()
            if quick_check is None or str(quick_check[0]).lower() != "ok":
                detail = "unknown" if quick_check is None else str(quick_check[0])
                raise DatabaseCorruptionError(
                    f"Platform database integrity check failed: {detail}"
                )
            schema_version = apply_migrations(connection)
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                raise DatabaseBusyError(
                    "Platform database remained locked during startup"
                ) from exc
            raise DatabaseCorruptionError(
                f"Platform database could not be read safely: {exc}"
            ) from exc
        except sqlite3.DatabaseError as exc:
            raise DatabaseCorruptionError(
                f"Platform database could not be read safely: {exc}"
            ) from exc
        finally:
            connection.close()

        if schema_version != PLATFORM_DATABASE_SCHEMA_VERSION:
            raise RuntimeError(
                "Migration target does not match PLATFORM_DATABASE_SCHEMA_VERSION"
            )
        return DatabaseState(
            path=self.path,
            schema_version=schema_version,
            journal_mode=journal_mode,
        )

    def diagnose(self) -> DatabaseDiagnostics:
        """Inspect integrity and schema state without mutating the database."""

        with self.connect() as connection:
            quick_check_row = connection.execute("PRAGMA quick_check").fetchone()
            quick_check = (
                "unknown" if quick_check_row is None else str(quick_check_row[0])
            )
            foreign_key_violations = len(
                connection.execute("PRAGMA foreign_key_check").fetchall()
            )
            schema_version = int(
                connection.execute("PRAGMA user_version").fetchone()[0]
            )
            journal_mode = str(
                connection.execute("PRAGMA journal_mode").fetchone()[0]
            ).lower()
            page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
            page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        return DatabaseDiagnostics(
            path=self.path,
            schema_version=schema_version,
            journal_mode=journal_mode,
            quick_check=quick_check,
            foreign_key_violations=foreign_key_violations,
            page_count=page_count,
            page_size=page_size,
        )

    def backup(self, destination: str | Path) -> DatabaseBackupState:
        """Create, validate, then atomically publish an online SQLite backup."""

        destination_path = Path(destination).expanduser().resolve()
        if destination_path == self.path:
            raise ValueError("Backup destination must differ from the live database")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination_path.name}.",
            suffix=".tmp",
            dir=destination_path.parent,
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            with self.connect() as source, sqlite3.connect(temporary_path) as target:
                source.backup(target)
                quick_check_row = target.execute("PRAGMA quick_check").fetchone()
                quick_check = (
                    "unknown" if quick_check_row is None else str(quick_check_row[0])
                )
                schema_version = int(
                    target.execute("PRAGMA user_version").fetchone()[0]
                )
            if quick_check.lower() != "ok":
                raise DatabaseCorruptionError(
                    f"Platform backup integrity check failed: {quick_check}"
                )
            os.replace(temporary_path, destination_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return DatabaseBackupState(
            source_path=self.path,
            destination_path=destination_path,
            schema_version=schema_version,
            quick_check=quick_check,
        )
