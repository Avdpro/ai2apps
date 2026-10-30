# SPDX-License-Identifier: Apache-2.0
"""Worker-owned SSD prefix cache policy; no conversation contents in lease state."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

DEFAULT_IDLE_SECONDS = 24 * 60 * 60
DEFAULT_MAX_BYTES = 20 * 1024**3


class WorkerPrefixCache:
    def __init__(
        self,
        root: Path,
        checkpoint,
        *,
        idle_seconds=DEFAULT_IDLE_SECONDS,
        max_bytes=DEFAULT_MAX_BYTES,
        clock=time.time,
    ):
        if idle_seconds <= 0 or max_bytes <= 0:
            raise ValueError("Prefix cache expiry and size must be positive")
        identity = json.dumps(
            [checkpoint.repo_id, checkpoint.revision, str(checkpoint.path)],
            separators=(",", ":"),
        )
        self.root = (
            root / "prefix-kv-v1" / hashlib.sha256(identity.encode()).hexdigest()
        )
        self.model_name = checkpoint.repo_id + "@" + checkpoint.revision
        self.model_path = str(checkpoint.path)
        self.idle_seconds, self.max_bytes, self.clock = idle_seconds, max_bytes, clock
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self.database = self.root / "leases.sqlite3"
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS leases (owner TEXT PRIMARY KEY, generation TEXT NOT NULL, touched REAL NOT NULL)"
            )
        os.chmod(self.database, 0o600)

    def _connect(self):
        return sqlite3.connect(self.database, timeout=10)

    def namespace(self, session_id: str) -> tuple[str, ...]:
        # The Host supplies its actor/installation/Session-bound cache namespace.
        # Store only a digest, and never use an untrusted ID as a filesystem path.
        owner = hashlib.sha256(session_id.encode()).hexdigest()
        now = self.clock()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM leases WHERE touched<=?", (now - self.idle_seconds,)
            )
            row = connection.execute(
                "SELECT generation FROM leases WHERE owner=?", (owner,)
            ).fetchone()
            generation = row[0] if row else uuid.uuid4().hex
            connection.execute(
                "INSERT OR REPLACE INTO leases VALUES (?,?,?)", (owner, generation, now)
            )
            connection.execute(
                "DELETE FROM leases WHERE owner IN (SELECT owner FROM leases ORDER BY touched DESC LIMIT -1 OFFSET 1024)"
            )
        return ("ai2apps-session-kv-v1", owner, generation)

    def configure(self, engine) -> bool:
        """Configure standard oMLX engines before start, including Package subclasses."""
        if not hasattr(engine, "_scheduler_config"):
            return False  # Specialized engines retain their own cache contract.
        from dataclasses import replace

        from omlx.scheduler import SchedulerConfig

        config = getattr(engine, "_scheduler_config", None) or SchedulerConfig()
        engine._scheduler_config = replace(
            config,
            paged_ssd_cache_dir=str(self.root / "blocks"),
            paged_ssd_cache_max_size=self.max_bytes,
            hot_cache_only=False,
            hot_cache_max_size=0,
            hot_cache_budget=None,
            model_name=self.model_name,
            model_path=self.model_path,
        )
        return True

    def activate(self, engine):
        inner = getattr(engine, "_engine", None)
        scheduler = getattr(getattr(inner, "engine", None), "scheduler", None)
        manager = getattr(scheduler, "paged_ssd_cache_manager", None)
        if manager is not None:
            manager.configure_idle_expiry(self.idle_seconds)
            scheduler.persistent_prefix_store = self
        return bool(getattr(engine, "prefix_cache_enabled", False))

    @staticmethod
    def _lineage_key(lineage):
        return hashlib.sha256(
            json.dumps(lineage, separators=(",", ":")).encode()
        ).hexdigest()

    @staticmethod
    def _token_digest(tokens):
        return hashlib.sha256(
            json.dumps(tokens, separators=(",", ":")).encode()
        ).hexdigest()

    def save(self, lineage, tokens):
        """Record a safe exact boundary, never prompt text or recoverable token IDs."""
        if not tokens:
            return
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS boundaries (lineage TEXT PRIMARY KEY, token_count INTEGER NOT NULL, digest TEXT NOT NULL, touched REAL NOT NULL)"
            )
            connection.execute(
                "DELETE FROM boundaries WHERE touched<=?",
                (self.clock() - self.idle_seconds,),
            )
            connection.execute(
                "INSERT OR REPLACE INTO boundaries VALUES (?,?,?,?)",
                (
                    self._lineage_key(lineage),
                    len(tokens),
                    self._token_digest(tokens),
                    self.clock(),
                ),
            )
            connection.execute(
                "DELETE FROM boundaries WHERE lineage IN (SELECT lineage FROM boundaries ORDER BY touched DESC LIMIT -1 OFFSET 1024)"
            )

    def match(self, lineage, prompt):
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS boundaries (lineage TEXT PRIMARY KEY, token_count INTEGER NOT NULL, digest TEXT NOT NULL, touched REAL NOT NULL)"
            )
            row = connection.execute(
                "SELECT token_count,digest,touched FROM boundaries WHERE lineage=?",
                (self._lineage_key(lineage),),
            ).fetchone()
            if (
                row is None
                or self.clock() - row[2] >= self.idle_seconds
                or not 0 < row[0] < len(prompt)
            ):
                return None
            tokens = prompt[: row[0]]
            if self._token_digest(tokens) != row[1]:
                return None
            connection.execute(
                "UPDATE boundaries SET touched=? WHERE lineage=?",
                (self.clock(), self._lineage_key(lineage)),
            )
            return list(tokens)
