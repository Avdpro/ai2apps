"""Durable Process execution, bounded logs, and broker audit records."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ai2apps.core import (
    EntityIdKind,
    ResourceNotFoundError,
    format_utc,
    new_entity_id,
    parse_utc,
    utc_now_text,
)
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase

from .models import ProcessLimits, ProcessLogRecord, ProcessRecord, ProcessStatus


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _time(value: str | None):
    return None if value is None else parse_utc(value)


class ProcessRepository:
    def __init__(self, database: PlatformDatabase, events: EventStore) -> None:
        self.database = database
        self.events = events

    @staticmethod
    def _record(row) -> ProcessRecord:
        return ProcessRecord(
            id=row["id"],
            session_id=row["session_id"],
            run_id=row["run_id"],
            caller_id=row["caller_id"],
            status=ProcessStatus(row["status"]),
            argv=tuple(json.loads(row["argv_json"])),
            cwd=row["cwd"],
            environment_keys=tuple(json.loads(row["environment_keys_json"])),
            sandbox_backend=row["sandbox_backend"],
            network_enabled=bool(row["network_enabled"]),
            pid=row["pid"],
            exit_code=row["exit_code"],
            limits=json.loads(row["limits_json"]),
            stdin_open=bool(row["stdin_open"]),
            output_bytes=row["output_bytes"],
            last_activity_at=parse_utc(row["last_activity_at"]),
            error=None if row["error_json"] is None else json.loads(row["error_json"]),
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
            started_at=_time(row["started_at"]),
            finished_at=_time(row["finished_at"]),
        )

    @staticmethod
    def _log(row) -> ProcessLogRecord:
        return ProcessLogRecord(
            id=row["id"],
            process_id=row["process_id"],
            sequence=row["sequence"],
            stream=row["stream"],
            encoding=row["encoding"],
            content=row["content"],
            byte_count=row["byte_count"],
            created_at=parse_utc(row["created_at"]),
        )

    def create(
        self,
        *,
        session_id: str,
        run_id: str | None,
        caller_id: str,
        argv: tuple[str, ...],
        cwd: str,
        environment_keys: tuple[str, ...],
        sandbox_backend: str,
        network_enabled: bool,
        limits: ProcessLimits,
    ) -> ProcessRecord:
        process_id = new_entity_id(EntityIdKind.PROCESS_EXECUTION)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            session = connection.execute(
                "SELECT app_instance_id FROM sessions WHERE id = ? AND status = 'active'",
                (session_id,),
            ).fetchone()
            if session is None:
                raise ResourceNotFoundError("session", session_id)
            connection.execute(
                """INSERT INTO process_executions(
                    id, session_id, run_id, caller_id, status, argv_json, cwd,
                    environment_keys_json, sandbox_backend, network_enabled,
                    limits_json, last_activity_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'starting', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    process_id,
                    session_id,
                    run_id,
                    caller_id,
                    _json(argv),
                    cwd,
                    _json(environment_keys),
                    sandbox_backend,
                    int(network_enabled),
                    _json(limits.to_json()),
                    now,
                    now,
                    now,
                ),
            )
            self.events.append_in_transaction(
                connection,
                event_type="process.starting",
                subject_id=process_id,
                app_instance_id=session["app_instance_id"],
                session_id=session_id,
                trace_id=run_id,
                payload={
                    "argv": argv,
                    "cwd": cwd,
                    "sandbox": sandbox_backend,
                    "network_enabled": network_enabled,
                    "limits": limits.to_json(),
                },
            )
            row = connection.execute(
                "SELECT * FROM process_executions WHERE id = ?", (process_id,)
            ).fetchone()
            assert row is not None
            return self._record(row)

    def mark_running(self, process_id: str, pid: int) -> ProcessRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE process_executions SET status = 'running', pid = ?,
                   started_at = ?, last_activity_at = ?, updated_at = ? WHERE id = ?""",
                (pid, now, now, now, process_id),
            )
            return self._get_in_transaction(connection, process_id)

    def get(
        self,
        process_id: str,
        *,
        session_id: str | None = None,
        run_id: str | None = None,
    ) -> ProcessRecord:
        query = "SELECT * FROM process_executions WHERE id = ?"
        params: list[Any] = [process_id]
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        if run_id is not None:
            query += " AND run_id = ?"
            params.append(run_id)
        with self.database.transaction() as connection:
            row = connection.execute(query, params).fetchone()
        if row is None:
            raise ResourceNotFoundError("process", process_id)
        return self._record(row)

    def _get_in_transaction(self, connection, process_id: str) -> ProcessRecord:
        row = connection.execute(
            "SELECT * FROM process_executions WHERE id = ?", (process_id,)
        ).fetchone()
        if row is None:
            raise ResourceNotFoundError("process", process_id)
        return self._record(row)

    def active_count(self, session_id: str) -> int:
        with self.database.transaction() as connection:
            return int(
                connection.execute(
                    """SELECT COUNT(*) FROM process_executions
                   WHERE session_id = ? AND status IN ('starting', 'running')""",
                    (session_id,),
                ).fetchone()[0]
            )

    def append_log(
        self, process_id: str, stream: str, encoding: str, content: str, byte_count: int
    ) -> int:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT session_id, run_id, output_bytes FROM process_executions WHERE id = ?",
                (process_id,),
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("process", process_id)
            sequence = int(
                connection.execute(
                    "SELECT COALESCE(MAX(sequence), 0) + 1 FROM process_log_chunks WHERE process_id = ?",
                    (process_id,),
                ).fetchone()[0]
            )
            connection.execute(
                """INSERT INTO process_log_chunks(
                    id, process_id, sequence, stream, encoding, content,
                    byte_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_entity_id(EntityIdKind.PROCESS_LOG),
                    process_id,
                    sequence,
                    stream,
                    encoding,
                    content,
                    byte_count,
                    now,
                ),
            )
            connection.execute(
                """UPDATE process_executions SET output_bytes = output_bytes + ?,
                   last_activity_at = ?, updated_at = ? WHERE id = ?""",
                (byte_count, now, now, process_id),
            )
            return row["output_bytes"] + byte_count

    def logs(self, process_id: str, *, after: int = 0, limit: int = 200):
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT * FROM process_log_chunks WHERE process_id = ? AND sequence > ?
                   ORDER BY sequence LIMIT ?""",
                (process_id, after, limit),
            ).fetchall()
        return tuple(self._log(row) for row in rows)

    def touch(self, process_id: str, *, stdin_open: bool | None = None) -> None:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            if stdin_open is None:
                connection.execute(
                    "UPDATE process_executions SET last_activity_at = ?, updated_at = ? WHERE id = ?",
                    (now, now, process_id),
                )
            else:
                connection.execute(
                    """UPDATE process_executions SET stdin_open = ?, last_activity_at = ?,
                       updated_at = ? WHERE id = ?""",
                    (int(stdin_open), now, now, process_id),
                )

    def settle(
        self,
        process_id: str,
        status: ProcessStatus,
        *,
        exit_code: int | None,
        error: dict[str, Any] | None = None,
    ) -> ProcessRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            current = self._get_in_transaction(connection, process_id)
            if current.status.terminal:
                return current
            connection.execute(
                """UPDATE process_executions SET status = ?, exit_code = ?,
                   stdin_open = 0, error_json = ?, finished_at = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    status.value,
                    exit_code,
                    None if error is None else _json(error),
                    now,
                    now,
                    process_id,
                ),
            )
            session = connection.execute(
                "SELECT app_instance_id FROM sessions WHERE id = ?",
                (current.session_id,),
            ).fetchone()
            assert session is not None
            self.events.append_in_transaction(
                connection,
                event_type=f"process.{status.value}",
                subject_id=process_id,
                app_instance_id=session["app_instance_id"],
                session_id=current.session_id,
                trace_id=current.run_id,
                payload={
                    "exit_code": exit_code,
                    "error": error,
                    "output_bytes": current.output_bytes,
                },
            )
            return self._get_in_transaction(connection, process_id)

    def active_for_run(self, run_id: str) -> tuple[ProcessRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT * FROM process_executions WHERE run_id = ?
                   AND status IN ('starting', 'running')""",
                (run_id,),
            ).fetchall()
        return tuple(self._record(row) for row in rows)

    def active(self) -> tuple[ProcessRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT * FROM process_executions
                   WHERE status IN ('starting', 'running')"""
            ).fetchall()
        return tuple(self._record(row) for row in rows)

    def recover_orphans(self) -> int:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            rows = connection.execute(
                """SELECT id FROM process_executions
                   WHERE status IN ('starting', 'running')"""
            ).fetchall()
            for row in rows:
                connection.execute(
                    """UPDATE process_executions SET status = 'orphaned', stdin_open = 0,
                       error_json = ?, finished_at = ?, updated_at = ? WHERE id = ?""",
                    (_json({"code": "runtime_restarted"}), now, now, row["id"]),
                )
            return len(rows)

    def issue_broker_request(
        self,
        *,
        request_id: str,
        process_id: str | None,
        session_id: str,
        run_id: str | None,
        operation: str,
        nonce: str,
        token_digest: str,
        expires_at: datetime,
        evidence: dict[str, Any],
    ) -> None:
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO host_broker_requests(
                    id, process_id, session_id, run_id, operation, nonce,
                    token_digest, status, expires_at, evidence_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'issued', ?, ?, ?)""",
                (
                    request_id,
                    process_id,
                    session_id,
                    run_id,
                    operation,
                    nonce,
                    token_digest,
                    format_utc(expires_at),
                    _json(evidence),
                    utc_now_text(),
                ),
            )

    def resolve_broker_request(self, request_id: str, status: str) -> None:
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE host_broker_requests SET status = ?, resolved_at = ?
                   WHERE id = ? AND status = 'issued'""",
                (status, utc_now_text(), request_id),
            )
