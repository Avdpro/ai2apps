"""Transactional persistence and state machine for asynchronous AgentRuns."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from ai2apps.capabilities import CapabilityRepository, GrantScope
from ai2apps.core import (
    EntityIdKind,
    ResourceConflictError,
    ResourceNotFoundError,
    format_utc,
    new_entity_id,
    parse_utc,
    utc_now_text,
)
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase

from .models import (
    AgentDefinitionRecord,
    AgentDefinitionStatus,
    AgentRunRecord,
    AgentRunStatus,
    InteractionKind,
    InteractionRecord,
    InteractionStatus,
    RunStepRecord,
    RunStepStatus,
    StatusLineRecord,
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _optional_json(value: str | None):
    return None if value is None else json.loads(value)


def _optional_time(value: str | None):
    return None if value is None else parse_utc(value)


def _resume_deadline(deadline: str, suspended_at: str, now: datetime) -> str:
    """Freeze an execution deadline while a durable Run awaits external action."""

    paused_for = max(timedelta(0), now - parse_utc(suspended_at))
    return format_utc(parse_utc(deadline) + paused_for)


class AgentRepository:
    MAX_DELEGATION_DEPTH = 2
    MAX_CHILD_RUNS = 4
    MAX_RUN_RETRIES = 3

    def __init__(
        self,
        database: PlatformDatabase,
        events: EventStore,
        capabilities: CapabilityRepository | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities

    @staticmethod
    def _definition(row) -> AgentDefinitionRecord:
        return AgentDefinitionRecord(
            id=row["id"],
            agent_key=row["agent_key"],
            package_version=row["package_version"],
            display_name=row["display_name"],
            description=row["description"],
            source=row["source"],
            status=AgentDefinitionStatus(row["status"]),
            executor_key=row["executor_key"],
            concurrency_group=row["concurrency_group"],
            concurrency_limit=row["concurrency_limit"],
            resume_policy=row["resume_policy"],
            max_steps=row["max_steps"],
            timeout_seconds=row["timeout_seconds"],
            manifest=json.loads(row["manifest_json"]),
            revision=row["revision"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _run(row) -> AgentRunRecord:
        return AgentRunRecord(
            id=row["id"],
            agent_definition_id=row["agent_definition_id"],
            session_id=row["session_id"],
            parent_run_id=row["parent_run_id"],
            root_run_id=row["root_run_id"] or row["id"],
            depth=row["depth"],
            delegation=json.loads(row["delegation_json"]),
            status=AgentRunStatus(row["status"]),
            idempotency_key=row["idempotency_key"],
            priority=row["priority"],
            input=json.loads(row["input_json"]),
            output=_optional_json(row["output_json"]),
            error=_optional_json(row["error_json"]),
            granted_capabilities=tuple(json.loads(row["granted_capabilities_json"])),
            current_step=row["current_step"],
            cancel_requested=bool(row["cancel_requested"]),
            revision=row["revision"],
            deadline_at=parse_utc(row["deadline_at"]),
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
            started_at=_optional_time(row["started_at"]),
            finished_at=_optional_time(row["finished_at"]),
        )

    @staticmethod
    def _status(row) -> StatusLineRecord:
        return StatusLineRecord(
            id=row["id"],
            run_id=row["run_id"],
            status_key=row["status_key"],
            phase=row["phase"],
            text=row["text"],
            presentation=row["presentation"],
            progress=row["progress"],
            content=json.loads(row["content_json"]),
            revision=row["revision"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _step(row) -> RunStepRecord:
        return RunStepRecord(
            id=row["id"],
            run_id=row["run_id"],
            sequence=row["sequence"],
            action_key=row["action_key"],
            kind=row["kind"],
            status=RunStepStatus(row["status"]),
            tool_name=row["tool_name"],
            input=json.loads(row["input_json"]),
            output=_optional_json(row["output_json"]),
            error=_optional_json(row["error_json"]),
            created_at=parse_utc(row["created_at"]),
            started_at=_optional_time(row["started_at"]),
            finished_at=_optional_time(row["finished_at"]),
        )

    @staticmethod
    def _interaction(row) -> InteractionRecord:
        return InteractionRecord(
            id=row["id"],
            run_id=row["run_id"],
            request_key=row["request_key"],
            kind=InteractionKind(row["kind"]),
            status=InteractionStatus(row["status"]),
            prompt=row["prompt"],
            response_schema=json.loads(row["response_schema_json"]),
            ui_hints=json.loads(row["ui_hints_json"]),
            request=json.loads(row["request_json"]),
            response=_optional_json(row["response_json"]),
            response_id=row["response_id"],
            deadline_at=parse_utc(row["deadline_at"]),
            revision=row["revision"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
            resolved_at=_optional_time(row["resolved_at"]),
        )

    @staticmethod
    def _definition_query() -> str:
        return """
            SELECT d.*, g.concurrency_limit
            FROM agent_definitions d
            LEFT JOIN agent_concurrency_groups g
              ON g.group_key = d.concurrency_group
        """

    def ensure_definition(
        self,
        *,
        agent_key: str,
        package_version: str,
        display_name: str,
        executor_key: str,
        description: str = "",
        source: str = "builtin",
        concurrency_group: str | None = None,
        concurrency_limit: int | None = None,
        resume_policy: str = "restart",
        max_steps: int = 20,
        timeout_seconds: int = 300,
        manifest: dict[str, Any] | None = None,
    ) -> AgentDefinitionRecord:
        if (concurrency_group is None) != (concurrency_limit is None):
            raise ValueError(
                "concurrency_group and concurrency_limit must be set together"
            )
        if concurrency_limit is not None and concurrency_limit <= 0:
            raise ValueError("concurrency_limit must be positive")
        manifest_data = manifest or {}
        invocation_schema = manifest_data.get(
            "invocation_schema", {"type": "object", "properties": {}}
        )
        if not isinstance(invocation_schema, dict):
            raise ValueError("Agent invocation_schema must be a JSON object")
        Draft202012Validator.check_schema(invocation_schema)
        if invocation_schema.get("type", "object") != "object":
            raise ValueError("Agent invocation_schema must describe an object")
        definition_id = new_entity_id(EntityIdKind.AGENT_DEFINITION)
        now = utc_now_text()
        try:
            with self.database.transaction(write=True) as connection:
                if concurrency_group is not None:
                    group = connection.execute(
                        "SELECT concurrency_limit FROM agent_concurrency_groups WHERE group_key = ?",
                        (concurrency_group,),
                    ).fetchone()
                    if group is None:
                        connection.execute(
                            """
                            INSERT INTO agent_concurrency_groups(
                                group_key, concurrency_limit, created_at, updated_at
                            ) VALUES (?, ?, ?, ?)
                            """,
                            (concurrency_group, concurrency_limit, now, now),
                        )
                    elif group["concurrency_limit"] != concurrency_limit:
                        raise ResourceConflictError(
                            f"Concurrency group {concurrency_group} already has limit "
                            f"{group['concurrency_limit']}"
                        )
                row = connection.execute(
                    "SELECT * FROM agent_definitions WHERE agent_key = ?",
                    (agent_key,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO agent_definitions(
                            id, agent_key, package_version, display_name, description,
                            source, executor_key, concurrency_group, resume_policy,
                            max_steps, timeout_seconds, manifest_json, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            definition_id,
                            agent_key,
                            package_version,
                            display_name,
                            description,
                            source,
                            executor_key,
                            concurrency_group,
                            resume_policy,
                            max_steps,
                            timeout_seconds,
                            _json(manifest_data),
                            now,
                            now,
                        ),
                    )
                    self.events.append_in_transaction(
                        connection,
                        event_type="agent.definition.registered",
                        subject_id=definition_id,
                        payload={"agent_key": agent_key},
                    )
                else:
                    definition_id = row["id"]
                    if row["executor_key"] != executor_key:
                        raise ResourceConflictError(
                            f"Agent {agent_key} is owned by another executor"
                        )
                    if source == "builtin" and row["source"] == "builtin":
                        connection.execute(
                            """
                            UPDATE agent_definitions SET
                                package_version = ?, display_name = ?, description = ?,
                                concurrency_group = ?, resume_policy = ?, max_steps = ?,
                                timeout_seconds = ?, manifest_json = ?,
                                revision = revision + 1, updated_at = ?
                            WHERE id = ? AND (
                                package_version != ? OR display_name != ? OR
                                description != ? OR concurrency_group IS NOT ? OR
                                resume_policy != ? OR max_steps != ? OR
                                timeout_seconds != ? OR manifest_json != ?
                            )
                            """,
                            (
                                package_version,
                                display_name,
                                description,
                                concurrency_group,
                                resume_policy,
                                max_steps,
                                timeout_seconds,
                                _json(manifest_data),
                                now,
                                definition_id,
                                package_version,
                                display_name,
                                description,
                                concurrency_group,
                                resume_policy,
                                max_steps,
                                timeout_seconds,
                                _json(manifest_data),
                            ),
                        )
                row = connection.execute(
                    self._definition_query() + " WHERE d.id = ?",
                    (definition_id,),
                ).fetchone()
                assert row is not None
                return self._definition(row)
        except sqlite3.IntegrityError as exc:
            raise ResourceConflictError(str(exc)) from exc

    def get_definition(self, agent_id_or_key: str) -> AgentDefinitionRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                self._definition_query() + " WHERE d.id = ? OR d.agent_key = ?",
                (agent_id_or_key, agent_id_or_key),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("agent_definition", agent_id_or_key)
        return self._definition(row)

    def list_definitions(self) -> tuple[AgentDefinitionRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                self._definition_query() + " ORDER BY d.agent_key"
            ).fetchall()
        return tuple(self._definition(row) for row in rows)

    def set_definition_status(
        self, agent_id_or_key: str, status: AgentDefinitionStatus
    ) -> AgentDefinitionRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM agent_definitions WHERE id = ? OR agent_key = ?",
                (agent_id_or_key, agent_id_or_key),
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("agent_definition", agent_id_or_key)
            if row["status"] != status.value:
                connection.execute(
                    """
                    UPDATE agent_definitions SET status = ?, revision = revision + 1,
                        updated_at = ? WHERE id = ?
                    """,
                    (status.value, now, row["id"]),
                )
                self.events.append_in_transaction(
                    connection,
                    event_type=f"agent.definition.{status.value}",
                    subject_id=row["id"],
                    payload={"agent_key": row["agent_key"], "status": status.value},
                )
            updated = connection.execute(
                self._definition_query() + " WHERE d.id = ?", (row["id"],)
            ).fetchone()
            assert updated is not None
            return self._definition(updated)

    def list_runs(
        self,
        *,
        agent_definition_id: str | None = None,
        status: AgentRunStatus | None = None,
        root_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[AgentRunRecord, ...]:
        if limit <= 0 or limit > 500:
            raise ValueError("AgentRun limit must be between 1 and 500")
        if offset < 0:
            raise ValueError("AgentRun offset must be non-negative")
        clauses: list[str] = []
        parameters: list[Any] = []
        if agent_definition_id is not None:
            clauses.append("agent_definition_id = ?")
            parameters.append(agent_definition_id)
        if status is not None:
            clauses.append("status = ?")
            parameters.append(status.value)
        if root_only:
            clauses.append("parent_run_id IS NULL")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        parameters.extend((limit, offset))
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_runs"
                + where
                + " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                parameters,
            ).fetchall()
        return tuple(self._run(row) for row in rows)

    def run_counts(self, agent_definition_id: str) -> dict[str, int]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS count FROM agent_runs
                WHERE agent_definition_id = ? GROUP BY status
                """,
                (agent_definition_id,),
            ).fetchall()
        counts = {status.value: 0 for status in AgentRunStatus}
        counts.update({row["status"]: row["count"] for row in rows})
        counts["total"] = sum(row["count"] for row in rows)
        counts["active"] = sum(
            counts[key]
            for key in (
                "queued",
                "planning",
                "running",
                "waiting_input",
                "waiting_capability",
            )
        )
        return counts

    def create_run(
        self,
        *,
        session_id: str,
        agent_key: str,
        input: dict[str, Any],
        idempotency_key: str | None = None,
        priority: int = 0,
        trace_id: str | None = None,
        parent_run_id: str | None = None,
        delegation: dict[str, Any] | None = None,
        budget: dict[str, int] | None = None,
    ) -> tuple[AgentRunRecord, bool]:
        definition = self.get_definition(agent_key)
        if definition.status is not AgentDefinitionStatus.ENABLED:
            raise ResourceConflictError(f"Agent is disabled: {agent_key}")
        invocation_schema = definition.manifest.get(
            "invocation_schema", {"type": "object", "properties": {}}
        )
        Draft202012Validator.check_schema(invocation_schema)
        parameters = input.get("parameters", {})
        if not isinstance(parameters, dict):
            raise ValueError("Agent parameters must be a JSON object")
        try:
            Draft202012Validator(invocation_schema).validate(parameters)
        except ValidationError as error:
            path = ".".join(str(item) for item in error.absolute_path)
            prefix = f"Agent parameter {path}: " if path else "Agent parameters: "
            raise ValueError(prefix + error.message) from error
        caller_invocation = input.get("invocation", {})
        invocation_source = (
            caller_invocation.get("source", "api")
            if isinstance(caller_invocation, dict)
            else "api"
        )
        delegation_data = dict(delegation or {})
        budget_data = dict(budget or {})
        for key in ("max_steps", "timeout_seconds", "max_model_tokens"):
            value = budget_data.get(key)
            if value is not None and (not isinstance(value, int) or value <= 0):
                raise ValueError(f"Agent Run budget {key} must be a positive integer")
        normalized_input = {
            **input,
            "parameters": parameters,
            "invocation": {
                "agent_definition_id": definition.id,
                "agent_key": definition.agent_key,
                "package_version": definition.package_version,
                "source": str(invocation_source)[:64],
            },
            **({"run_budget": budget_data} if budget_data else {}),
        }
        run_id = new_entity_id(EntityIdKind.AGENT_RUN)
        status_id = new_entity_id(EntityIdKind.STATUS_LINE)
        now_dt = datetime.now(UTC)
        now = format_utc(now_dt)
        timeout_seconds = min(
            definition.timeout_seconds,
            budget_data.get("timeout_seconds", definition.timeout_seconds),
        )
        deadline = format_utc(now_dt + timedelta(seconds=timeout_seconds))
        try:
            with self.database.transaction(write=True) as connection:
                session = connection.execute(
                    "SELECT app_instance_id FROM sessions WHERE id = ? AND status = 'active'",
                    (session_id,),
                ).fetchone()
                if session is None:
                    raise ResourceNotFoundError("active_session", session_id)
                root_run_id = run_id
                depth = 0
                if parent_run_id is not None:
                    parent_row = connection.execute(
                        "SELECT * FROM agent_runs WHERE id = ?", (parent_run_id,)
                    ).fetchone()
                    if parent_row is None:
                        raise ResourceNotFoundError("parent_agent_run", parent_run_id)
                    parent = self._run(parent_row)
                    if parent.session_id != session_id:
                        raise ResourceConflictError(
                            "Delegated AgentRun must use its parent's Session"
                        )
                    if parent.status not in {
                        AgentRunStatus.PLANNING,
                        AgentRunStatus.RUNNING,
                    }:
                        raise ResourceConflictError(
                            "Delegation requires an active parent AgentRun"
                        )
                    depth = parent.depth + 1
                    if depth > self.MAX_DELEGATION_DEPTH:
                        raise ResourceConflictError(
                            f"Delegation depth exceeds {self.MAX_DELEGATION_DEPTH}"
                        )
                    child_count = connection.execute(
                        "SELECT COUNT(*) FROM agent_runs WHERE parent_run_id = ?",
                        (parent_run_id,),
                    ).fetchone()[0]
                    if child_count >= self.MAX_CHILD_RUNS:
                        raise ResourceConflictError(
                            f"Parent AgentRun already has {self.MAX_CHILD_RUNS} children"
                        )
                    root_run_id = parent.root_run_id
                    delegated_timeout = delegation_data.get("budget", {}).get(
                        "timeout_seconds", definition.timeout_seconds
                    )
                    if not isinstance(delegated_timeout, int) or delegated_timeout <= 0:
                        raise ValueError("Delegation timeout_seconds must be positive")
                    child_deadline = now_dt + timedelta(
                        seconds=min(delegated_timeout, timeout_seconds)
                    )
                    deadline = format_utc(min(child_deadline, parent.deadline_at))
                    delegation_data = {
                        **delegation_data,
                        "parent_run_id": parent.id,
                        "root_run_id": root_run_id,
                        "depth": depth,
                    }
                    normalized_input["delegation"] = delegation_data
                if idempotency_key is not None:
                    existing = connection.execute(
                        """
                        SELECT * FROM agent_runs
                        WHERE session_id = ? AND idempotency_key = ?
                        """,
                        (session_id, idempotency_key),
                    ).fetchone()
                    if existing is not None:
                        if existing["agent_definition_id"] != definition.id or existing[
                            "input_json"
                        ] not in {_json(input), _json(normalized_input)}:
                            raise ResourceConflictError(
                                "AgentRun idempotency key was reused with different input"
                            )
                        return self._run(existing), False
                connection.execute(
                    """
                    INSERT INTO agent_runs(
                        id, agent_definition_id, session_id, idempotency_key,
                        priority, input_json, deadline_at, created_at, updated_at,
                        parent_run_id, root_run_id, depth, delegation_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        definition.id,
                        session_id,
                        idempotency_key,
                        priority,
                        _json(normalized_input),
                        deadline,
                        now,
                        now,
                        parent_run_id,
                        root_run_id,
                        depth,
                        _json(delegation_data),
                    ),
                )
                if parent_run_id is not None:
                    request_key = delegation_data.get("request_key")
                    task = delegation_data.get("task")
                    if not isinstance(request_key, str) or not request_key:
                        raise ValueError("Delegation request_key is required")
                    if not isinstance(task, str) or not task.strip():
                        raise ValueError("Delegation task is required")
                    connection.execute(
                        """
                        INSERT INTO agent_delegations(
                            id, parent_run_id, child_run_id, request_key,
                            target_agent_key, task, parameters_json,
                            context_json, budget_json, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            new_entity_id(EntityIdKind.AGENT_DELEGATION),
                            parent_run_id,
                            run_id,
                            request_key,
                            definition.agent_key,
                            task.strip(),
                            _json(delegation_data.get("parameters", {})),
                            _json(delegation_data.get("context", {})),
                            _json(delegation_data.get("budget", {})),
                            now,
                            now,
                        ),
                    )
                connection.execute(
                    """
                    INSERT INTO agent_status_lines(
                        id, run_id, phase, text, presentation,
                        created_at, updated_at
                    ) VALUES (?, ?, 'queued', 'Queued', 'pulse', ?, ?)
                    """,
                    (status_id, run_id, now, now),
                )
                self.events.append_in_transaction(
                    connection,
                    event_type="agent.run.queued",
                    subject_id=run_id,
                    app_instance_id=session["app_instance_id"],
                    session_id=session_id,
                    trace_id=trace_id,
                    payload={
                        "agent_key": definition.agent_key,
                        "status": "queued",
                        "status_line": {"text": "Queued", "presentation": "pulse"},
                        "parent_run_id": parent_run_id,
                        "root_run_id": root_run_id,
                        "depth": depth,
                    },
                )
                row = connection.execute(
                    "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
                ).fetchone()
                assert row is not None
                return self._run(row), True
        except sqlite3.IntegrityError as exc:
            raise ResourceConflictError(str(exc)) from exc

    def get_run(self, run_id: str) -> AgentRunRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("agent_run", run_id)
        return self._run(row)

    def retry_run(
        self,
        run_id: str,
        *,
        idempotency_key: str | None = None,
        trace_id: str | None = None,
    ) -> tuple[AgentRunRecord, bool]:
        """Create a fresh, auditable attempt from a failed or cancelled Run."""

        original = self.get_run(run_id)
        if original.status not in {AgentRunStatus.FAILED, AgentRunStatus.CANCELLED}:
            raise ResourceConflictError(
                "Only a failed or cancelled AgentRun can be retried"
            )
        retry_metadata = original.input.get("retry")
        root_attempt_run_id = (
            retry_metadata.get("root_attempt_run_id", original.id)
            if isinstance(retry_metadata, dict)
            else original.id
        )
        with self.database.transaction() as connection:
            if idempotency_key is not None:
                existing = connection.execute(
                    """
                    SELECT * FROM agent_runs
                    WHERE session_id = ? AND idempotency_key = ?
                    """,
                    (original.session_id, idempotency_key),
                ).fetchone()
                if existing is not None:
                    retry = json.loads(existing["input_json"]).get("retry", {})
                    if retry.get("retry_of_run_id") != original.id:
                        raise ResourceConflictError(
                            "AgentRun retry idempotency key was reused"
                        )
                    return self._run(existing), False
            previous_attempts = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM agent_runs
                    WHERE session_id = ?
                      AND json_extract(input_json, '$.retry.root_attempt_run_id') = ?
                    """,
                    (original.session_id, root_attempt_run_id),
                ).fetchone()[0]
            )
        attempt = previous_attempts + 1
        if attempt > self.MAX_RUN_RETRIES:
            raise ResourceConflictError(
                f"AgentRun retry limit reached ({self.MAX_RUN_RETRIES})"
            )
        definition = self.get_definition(original.agent_definition_id)
        copied_input = dict(original.input)
        copied_input.pop("invocation", None)
        copied_input.pop("delegation", None)
        copied_input["retry"] = {
            "attempt": attempt,
            "retry_of_run_id": original.id,
            "root_attempt_run_id": root_attempt_run_id,
        }
        return self.create_run(
            session_id=original.session_id,
            agent_key=definition.agent_key,
            input=copied_input,
            idempotency_key=idempotency_key,
            priority=original.priority,
            trace_id=trace_id,
        )

    def list_children(self, run_id: str) -> tuple[AgentRunRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_runs WHERE parent_run_id = ? ORDER BY created_at, id",
                (run_id,),
            ).fetchall()
        return tuple(self._run(row) for row in rows)

    def list_descendants(self, run_id: str) -> tuple[AgentRunRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                WITH RECURSIVE descendants(id) AS (
                    SELECT id FROM agent_runs WHERE parent_run_id = ?
                    UNION ALL
                    SELECT child.id FROM agent_runs child
                    JOIN descendants parent ON child.parent_run_id = parent.id
                )
                SELECT run.* FROM agent_runs run
                JOIN descendants ON descendants.id = run.id
                ORDER BY run.depth, run.created_at, run.id
                """,
                (run_id,),
            ).fetchall()
        return tuple(self._run(row) for row in rows)

    def get_delegated_child(
        self, parent_run_id: str, request_key: str
    ) -> AgentRunRecord | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT child.* FROM agent_delegations delegation
                JOIN agent_runs child ON child.id = delegation.child_run_id
                WHERE delegation.parent_run_id = ? AND delegation.request_key = ?
                """,
                (parent_run_id, request_key),
            ).fetchone()
        return None if row is None else self._run(row)

    def get_status_line(self, run_id: str) -> StatusLineRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM agent_status_lines WHERE run_id = ? AND status_key = 'primary'",
                (run_id,),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("agent_status_line", run_id)
        return self._status(row)

    def list_steps(self, run_id: str) -> tuple[RunStepRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM run_steps WHERE run_id = ? ORDER BY sequence",
                (run_id,),
            ).fetchall()
        return tuple(self._step(row) for row in rows)

    def list_interactions(self, run_id: str) -> tuple[InteractionRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_interactions WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        return tuple(self._interaction(row) for row in rows)

    def snapshot(self, run_id: str):
        run = self.get_run(run_id)
        definition = self.get_definition(run.agent_definition_id)
        return (
            definition,
            run,
            self.get_status_line(run_id),
            self.list_steps(run_id),
            self.list_interactions(run_id),
        )

    def _status_line_in_transaction(
        self,
        connection,
        run_row,
        *,
        phase: str,
        text: str,
        presentation: str,
        progress: float | None = None,
        content: dict[str, Any] | None = None,
    ) -> StatusLineRecord:
        now = utc_now_text()
        connection.execute(
            """
            UPDATE agent_status_lines
            SET phase = ?, text = ?, presentation = ?, progress = ?,
                content_json = ?, revision = revision + 1, updated_at = ?
            WHERE run_id = ? AND status_key = 'primary'
            """,
            (
                phase,
                text,
                presentation,
                progress,
                _json(content or {}),
                now,
                run_row["id"],
            ),
        )
        row = connection.execute(
            "SELECT * FROM agent_status_lines WHERE run_id = ? AND status_key = 'primary'",
            (run_row["id"],),
        ).fetchone()
        assert row is not None
        status = self._status(row)
        session = connection.execute(
            "SELECT app_instance_id FROM sessions WHERE id = ?",
            (run_row["session_id"],),
        ).fetchone()
        assert session is not None
        self.events.append_in_transaction(
            connection,
            event_type="agent.status",
            subject_id=run_row["id"],
            app_instance_id=session["app_instance_id"],
            session_id=run_row["session_id"],
            payload={
                "run_id": run_row["id"],
                "status_id": "primary",
                "phase": phase,
                "text": text,
                "presentation": presentation,
                "progress": progress,
                "content": content or {},
                "revision": status.revision,
            },
        )
        return status

    def update_status_line(
        self,
        run_id: str,
        *,
        phase: str,
        text: str,
        presentation: str = "plain",
        progress: float | None = None,
        content: dict[str, Any] | None = None,
    ) -> StatusLineRecord:
        with self.database.transaction(write=True) as connection:
            run = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if run is None:
                raise ResourceNotFoundError("agent_run", run_id)
            return self._status_line_in_transaction(
                connection,
                run,
                phase=phase,
                text=text,
                presentation=presentation,
                progress=progress,
                content=content,
            )

    def transition(
        self,
        run_id: str,
        *,
        expected: set[AgentRunStatus],
        status: AgentRunStatus,
        output: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        status_text: str | None = None,
        presentation: str | None = None,
    ) -> AgentRunRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("agent_run", run_id)
            current = AgentRunStatus(row["status"])
            if current not in expected:
                raise ResourceConflictError(
                    f"AgentRun {run_id} is {current.value}, expected "
                    + ", ".join(sorted(item.value for item in expected))
                )
            finished = status in {
                AgentRunStatus.COMPLETED,
                AgentRunStatus.FAILED,
                AgentRunStatus.CANCELLED,
            }
            connection.execute(
                """
                UPDATE agent_runs
                SET status = ?, output_json = COALESCE(?, output_json),
                    error_json = COALESCE(?, error_json),
                    started_at = CASE
                        WHEN ? = 'running' THEN COALESCE(started_at, ?)
                        ELSE started_at END,
                    finished_at = CASE WHEN ? THEN ? ELSE finished_at END,
                    revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    None if output is None else _json(output),
                    None if error is None else _json(error),
                    status.value,
                    now,
                    int(finished),
                    now,
                    now,
                    run_id,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            assert updated is not None
            defaults = {
                AgentRunStatus.QUEUED: ("Queued", "pulse"),
                AgentRunStatus.PLANNING: ("Planning…", "pulse"),
                AgentRunStatus.RUNNING: ("Running…", "pulse"),
                AgentRunStatus.WAITING_INPUT: ("Waiting for your input", "warning"),
                AgentRunStatus.WAITING_CAPABILITY: ("Waiting for approval", "warning"),
                AgentRunStatus.INTERRUPTED: ("Interrupted; recovery needed", "warning"),
                AgentRunStatus.COMPLETED: ("Completed", "plain"),
                AgentRunStatus.FAILED: ("Failed", "error"),
                AgentRunStatus.CANCELLED: ("Cancelled", "plain"),
            }
            default_text, default_presentation = defaults[status]
            self._status_line_in_transaction(
                connection,
                updated,
                phase=status.value,
                text=status_text or default_text,
                presentation=presentation or default_presentation,
            )
            session = connection.execute(
                "SELECT app_instance_id FROM sessions WHERE id = ?",
                (updated["session_id"],),
            ).fetchone()
            assert session is not None
            self.events.append_in_transaction(
                connection,
                event_type=f"agent.run.{status.value}",
                subject_id=run_id,
                app_instance_id=session["app_instance_id"],
                session_id=updated["session_id"],
                payload={"run_id": run_id, "status": status.value},
            )
            return self._run(updated)

    def claim_next(self) -> AgentRunRecord | None:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            expired = connection.execute(
                """
                SELECT id FROM agent_runs
                WHERE status = 'queued' AND deadline_at <= ?
                """,
                (now,),
            ).fetchall()
            for item in expired:
                connection.execute(
                    """
                    UPDATE agent_runs SET status = 'cancelled',
                        error_json = ?, finished_at = ?, updated_at = ?,
                        revision = revision + 1 WHERE id = ?
                    """,
                    (_json({"code": "run_deadline_exceeded"}), now, now, item["id"]),
                )
                expired_run = connection.execute(
                    "SELECT * FROM agent_runs WHERE id = ?", (item["id"],)
                ).fetchone()
                assert expired_run is not None
                self._status_line_in_transaction(
                    connection,
                    expired_run,
                    phase="cancelled",
                    text="Run deadline exceeded",
                    presentation="error",
                )
            candidates = connection.execute(
                """
                SELECT r.*, d.concurrency_group, g.concurrency_limit
                FROM agent_runs r
                JOIN agent_definitions d ON d.id = r.agent_definition_id
                LEFT JOIN agent_concurrency_groups g
                  ON g.group_key = d.concurrency_group
                WHERE r.status = 'queued' AND r.cancel_requested = 0
                  AND r.deadline_at > ? AND d.status = 'enabled'
                ORDER BY r.priority DESC, r.created_at, r.id
                """,
                (now,),
            ).fetchall()
            selected = None
            for candidate in candidates:
                group = candidate["concurrency_group"]
                if group is None:
                    selected = candidate
                    break
                active = connection.execute(
                    """
                    SELECT COUNT(*) FROM agent_runs r
                    JOIN agent_definitions d ON d.id = r.agent_definition_id
                    WHERE d.concurrency_group = ?
                      AND r.status IN ('planning', 'running')
                    """,
                    (group,),
                ).fetchone()[0]
                if active < candidate["concurrency_limit"]:
                    selected = candidate
                    break
            if selected is None:
                return None
            connection.execute(
                """
                UPDATE agent_runs SET status = 'planning',
                    revision = revision + 1, updated_at = ?
                WHERE id = ? AND status = 'queued'
                """,
                (now, selected["id"]),
            )
            row = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (selected["id"],)
            ).fetchone()
            assert row is not None
            self._status_line_in_transaction(
                connection,
                row,
                phase="planning",
                text="Planning…",
                presentation="pulse",
            )
            session = connection.execute(
                "SELECT app_instance_id FROM sessions WHERE id = ?",
                (row["session_id"],),
            ).fetchone()
            assert session is not None
            self.events.append_in_transaction(
                connection,
                event_type="agent.run.planning",
                subject_id=row["id"],
                app_instance_id=session["app_instance_id"],
                session_id=row["session_id"],
                payload={"run_id": row["id"], "status": "planning"},
            )
            return self._run(row)

    def dispatching_count(self) -> int:
        with self.database.transaction() as connection:
            return int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM agent_runs
                    WHERE status IN ('queued', 'planning', 'running')
                    """
                ).fetchone()[0]
            )

    def suspend_queued_for_shutdown(self) -> int:
        """Mark queued Runs so their deadline excludes time spent offline."""

        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute(
                """
                UPDATE agent_runs SET error_json = ?, updated_at = ?,
                    revision = revision + 1
                WHERE status = 'queued' AND cancel_requested = 0
                  AND (error_json IS NULL OR json_extract(error_json, '$.code')
                       != 'runtime_stopped')
                """,
                (_json({"code": "runtime_stopped"}), now),
            )
            return int(cursor.rowcount)

    def create_step(
        self,
        run_id: str,
        *,
        action_key: str,
        kind: str,
        input: dict[str, Any],
        tool_name: str | None = None,
    ) -> tuple[RunStepRecord, bool]:
        now = utc_now_text()
        step_id = new_entity_id(EntityIdKind.RUN_STEP)
        with self.database.transaction(write=True) as connection:
            existing = connection.execute(
                "SELECT * FROM run_steps WHERE run_id = ? AND action_key = ?",
                (run_id, action_key),
            ).fetchone()
            if existing is not None:
                return self._step(existing), False
            run = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if run is None:
                raise ResourceNotFoundError("agent_run", run_id)
            sequence = run["current_step"] + 1
            connection.execute(
                """
                INSERT INTO run_steps(
                    id, run_id, sequence, action_key, kind, status,
                    tool_name, input_json, created_at, started_at
                ) VALUES (?, ?, ?, ?, ?, 'running', ?, ?, ?, ?)
                """,
                (
                    step_id,
                    run_id,
                    sequence,
                    action_key,
                    kind,
                    tool_name,
                    _json(input),
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE agent_runs SET current_step = ?, revision = revision + 1,
                    updated_at = ? WHERE id = ?
                """,
                (sequence, now, run_id),
            )
            row = connection.execute(
                "SELECT * FROM run_steps WHERE id = ?", (step_id,)
            ).fetchone()
            assert row is not None
            return self._step(row), True

    def settle_step(
        self,
        step_id: str,
        *,
        status: RunStepStatus,
        output: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> RunStepRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute(
                """
                UPDATE run_steps SET status = ?, output_json = ?, error_json = ?,
                    finished_at = ? WHERE id = ? AND status = 'running'
                """,
                (
                    status.value,
                    None if output is None else _json(output),
                    None if error is None else _json(error),
                    now,
                    step_id,
                ),
            )
            if cursor.rowcount == 0:
                row = connection.execute(
                    "SELECT * FROM run_steps WHERE id = ?", (step_id,)
                ).fetchone()
                if row is None:
                    raise ResourceNotFoundError("run_step", step_id)
                return self._step(row)
            row = connection.execute(
                "SELECT * FROM run_steps WHERE id = ?", (step_id,)
            ).fetchone()
            assert row is not None
            return self._step(row)

    def abandon_step_for_retry(
        self,
        step_id: str,
        *,
        error: dict[str, Any],
    ) -> RunStepRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute(
                """
                UPDATE run_steps SET status = 'cancelled',
                    action_key = action_key || ':retry:' || id,
                    error_json = ?, finished_at = ?
                WHERE id = ? AND status = 'running'
                """,
                (_json(error), now, step_id),
            )
            if cursor.rowcount == 0:
                raise ResourceConflictError("RunStep is not running")
            row = connection.execute(
                "SELECT * FROM run_steps WHERE id = ?", (step_id,)
            ).fetchone()
            assert row is not None
            return self._step(row)

    def create_interaction(
        self,
        run_id: str,
        *,
        request_key: str,
        kind: InteractionKind,
        prompt: str,
        response_schema: dict[str, Any],
        ui_hints: dict[str, Any] | None = None,
        request: dict[str, Any] | None = None,
        timeout_seconds: int = 86_400,
    ) -> InteractionRecord:
        Draft202012Validator.check_schema(response_schema)
        now_dt = datetime.now(UTC)
        now = format_utc(now_dt)
        deadline = format_utc(now_dt + timedelta(seconds=timeout_seconds))
        interaction_id = new_entity_id(EntityIdKind.INTERACTION)
        with self.database.transaction(write=True) as connection:
            existing = connection.execute(
                """
                SELECT * FROM agent_interactions
                WHERE run_id = ? AND request_key = ?
                """,
                (run_id, request_key),
            ).fetchone()
            if existing is not None:
                return self._interaction(existing)
            run = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if run is None:
                raise ResourceNotFoundError("agent_run", run_id)
            waiting = (
                AgentRunStatus.WAITING_CAPABILITY
                if kind is InteractionKind.APPROVAL
                else AgentRunStatus.WAITING_INPUT
            )
            connection.execute(
                """
                INSERT INTO agent_interactions(
                    id, run_id, request_key, kind, prompt, response_schema_json,
                    ui_hints_json, request_json, deadline_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    interaction_id,
                    run_id,
                    request_key,
                    kind.value,
                    prompt,
                    _json(response_schema),
                    _json(ui_hints or {}),
                    _json(request or {}),
                    deadline,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE agent_runs SET status = ?, revision = revision + 1,
                    updated_at = ? WHERE id = ? AND status = 'running'
                """,
                (waiting.value, now, run_id),
            )
            updated = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            assert updated is not None
            self._status_line_in_transaction(
                connection,
                updated,
                phase=waiting.value,
                text=prompt,
                presentation="warning",
            )
            session = connection.execute(
                "SELECT app_instance_id FROM sessions WHERE id = ?",
                (updated["session_id"],),
            ).fetchone()
            assert session is not None
            self.events.append_in_transaction(
                connection,
                event_type=(
                    "agent.approval.request"
                    if kind is InteractionKind.APPROVAL
                    else "agent.input.request"
                ),
                subject_id=run_id,
                app_instance_id=session["app_instance_id"],
                session_id=updated["session_id"],
                payload={
                    "run_id": run_id,
                    "interaction_id": interaction_id,
                    "kind": kind.value,
                    "prompt": prompt,
                    "response_schema": response_schema,
                    "ui_hints": ui_hints or {},
                    "request": request or {},
                    "deadline_at": deadline,
                },
            )
            row = connection.execute(
                "SELECT * FROM agent_interactions WHERE id = ?",
                (interaction_id,),
            ).fetchone()
            assert row is not None
            return self._interaction(row)

    def respond_interaction(
        self,
        run_id: str,
        interaction_id: str,
        *,
        response: dict[str, Any],
        response_id: str,
    ) -> InteractionRecord:
        now_dt = datetime.now(UTC)
        now = format_utc(now_dt)
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                """
                SELECT * FROM agent_interactions
                WHERE id = ? AND run_id = ?
                """,
                (interaction_id, run_id),
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("agent_interaction", interaction_id)
            if row["status"] != "pending":
                if row["response_id"] == response_id and row["response_json"] == _json(
                    response
                ):
                    return self._interaction(row)
                raise ResourceConflictError("Interaction has already been resolved")
            if row["deadline_at"] <= now:
                raise ResourceConflictError("Interaction deadline has expired")
            try:
                Draft202012Validator(json.loads(row["response_schema_json"])).validate(
                    response
                )
            except ValidationError as exc:
                raise ResourceConflictError(
                    f"Interaction response is invalid: {exc.message}"
                ) from exc
            kind = InteractionKind(row["kind"])
            if kind is InteractionKind.FILE:
                handle_values = [
                    value
                    for value in response.values()
                    if isinstance(value, str) and value.startswith("resource://")
                ]
                if len(handle_values) != 1:
                    raise ResourceConflictError(
                        "File interaction must return one ResourceHandle URI"
                    )
                handle_id = handle_values[0].removeprefix("resource://")
                run_session = connection.execute(
                    "SELECT session_id FROM agent_runs WHERE id = ?", (run_id,)
                ).fetchone()
                assert run_session is not None
                handle = connection.execute(
                    """SELECT id FROM resource_handles
                       WHERE id = ? AND session_id = ? AND revoked_at IS NULL
                         AND kind IN ('file', 'artifact')
                         AND EXISTS (
                             SELECT 1 FROM json_each(capabilities_json)
                             WHERE value = 'read'
                         )
                         AND (expires_at IS NULL OR expires_at > ?)""",
                    (handle_id, run_session["session_id"], now),
                ).fetchone()
                if handle is None:
                    raise ResourceConflictError(
                        "ResourceHandle is unavailable in this Session"
                    )
            decision = (
                response.get("decision") if kind is InteractionKind.APPROVAL else None
            )
            new_status = (
                InteractionStatus.APPROVED
                if decision == "approve"
                else InteractionStatus.DENIED
                if decision == "deny"
                else InteractionStatus.SUBMITTED
            )
            connection.execute(
                """
                UPDATE agent_interactions
                SET status = ?, response_json = ?, response_id = ?, resolved_at = ?,
                    revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (
                    new_status.value,
                    _json(response),
                    response_id,
                    now,
                    now,
                    interaction_id,
                ),
            )
            run = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            assert run is not None
            resumed_deadline = _resume_deadline(
                run["deadline_at"], run["updated_at"], now_dt
            )
            session = connection.execute(
                "SELECT app_instance_id FROM sessions WHERE id = ?",
                (run["session_id"],),
            ).fetchone()
            assert session is not None
            if new_status is InteractionStatus.DENIED:
                connection.execute(
                    """
                    UPDATE agent_runs SET status = 'failed', error_json = ?,
                        finished_at = ?, revision = revision + 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        _json(
                            {
                                "code": "approval_denied",
                                "interaction_id": interaction_id,
                            }
                        ),
                        now,
                        now,
                        run_id,
                    ),
                )
                next_phase = "failed"
                status_text = "Approval denied"
                presentation = "error"
            else:
                grants = set(json.loads(run["granted_capabilities_json"]))
                if new_status is InteractionStatus.APPROVED:
                    approval_request = json.loads(row["request_json"])
                    approved = tuple(approval_request.get("capabilities", []))
                    grants.update(approved)
                    requested_scope = response.get("scope", "once")
                    single_use = requested_scope == "once"
                    scope = GrantScope.RUN if single_use else GrantScope(requested_scope)
                    scope_id = {
                        GrantScope.RUN: run_id,
                        GrantScope.SESSION: run["session_id"],
                        GrantScope.AGENT: run["agent_definition_id"],
                        GrantScope.APP: session["app_instance_id"],
                    }[scope]
                    lease_id = new_entity_id(EntityIdKind.GRANT_LEASE)
                    expires_at = resumed_deadline if scope is GrantScope.RUN else None
                    evidence = {
                        "interaction_id": interaction_id,
                        "response_id": response_id,
                        "decision": "approve",
                        "scope": scope.value,
                        "requested_scope": requested_scope,
                        "single_use": single_use,
                    }
                    tool_name = approval_request.get("tool_name", "*")
                    tool_row = connection.execute(
                        """SELECT s.active_package_digest FROM tool_descriptors t
                           JOIN service_descriptors s ON s.id = t.service_id
                           WHERE t.qualified_name = ?""",
                        (tool_name,),
                    ).fetchone()
                    tool_service_digest = None if tool_row is None else tool_row[0]
                    connection.execute(
                        """INSERT INTO grant_leases(
                            id, scope, scope_id, agent_definition_id, session_id,
                            app_instance_id, capabilities_json, tool_pattern,
                            tool_service_digest,
                            resource_selector_json, issued_by, evidence_json,
                            expires_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'user', ?, ?, ?, ?)""",
                        (
                            lease_id,
                            scope.value,
                            scope_id,
                            run["agent_definition_id"],
                            run["session_id"],
                            session["app_instance_id"],
                            _json(sorted(set(approved))),
                            tool_name,
                            tool_service_digest,
                            _json(approval_request.get("resource_selector", {})),
                            _json(evidence),
                            expires_at,
                            now,
                            now,
                        ),
                    )
                    self.events.append_in_transaction(
                        connection,
                        event_type="capability.grant.created",
                        subject_id=lease_id,
                        app_instance_id=session["app_instance_id"],
                        session_id=run["session_id"],
                        trace_id=run_id,
                        payload={
                            "run_id": run_id,
                            "scope": scope.value,
                            "capabilities": sorted(set(approved)),
                            "tool_pattern": approval_request.get("tool_name", "*"),
                            "issued_by": "user",
                            "evidence": evidence,
                        },
                    )
                connection.execute(
                    """
                    UPDATE agent_runs SET status = 'queued',
                        granted_capabilities_json = ?, revision = revision + 1,
                        deadline_at = ?, updated_at = ? WHERE id = ?
                    """,
                    (_json(sorted(grants)), resumed_deadline, now, run_id),
                )
                next_phase = "queued"
                status_text = "Input received; queued to resume"
                presentation = "pulse"
            updated_run = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            assert updated_run is not None
            self._status_line_in_transaction(
                connection,
                updated_run,
                phase=next_phase,
                text=status_text,
                presentation=presentation,
            )
            self.events.append_in_transaction(
                connection,
                event_type=f"agent.interaction.{new_status.value}",
                subject_id=run_id,
                app_instance_id=session["app_instance_id"],
                session_id=run["session_id"],
                payload={
                    "run_id": run_id,
                    "interaction_id": interaction_id,
                    "status": new_status.value,
                    "response": response,
                },
            )
            if kind is InteractionKind.APPROVAL:
                approval_request = json.loads(row["request_json"])
                decision_id = new_entity_id(EntityIdKind.CAPABILITY_DECISION)
                decision_value = (
                    "allow" if new_status is InteractionStatus.APPROVED else "deny"
                )
                evidence = {
                    "interaction_id": interaction_id,
                    "response_id": response_id,
                    "response": response,
                }
                connection.execute(
                    """INSERT INTO capability_decisions(
                        id, run_id, interaction_id, decision, decision_source,
                        capabilities_json, tool_name, effects_json,
                        matched_policy_ids_json, evidence_json, created_at
                    ) VALUES (?, ?, ?, ?, 'user', ?, ?, ?, '[]', ?, ?)""",
                    (
                        decision_id,
                        run_id,
                        interaction_id,
                        decision_value,
                        _json(approval_request.get("capabilities", [])),
                        approval_request.get("tool_name", "*"),
                        _json(approval_request.get("effects", [])),
                        _json(evidence),
                        now,
                    ),
                )
                self.events.append_in_transaction(
                    connection,
                    event_type=f"capability.decision.{decision_value}",
                    subject_id=run_id,
                    app_instance_id=session["app_instance_id"],
                    session_id=run["session_id"],
                    trace_id=run_id,
                    payload={
                        "decision_id": decision_id,
                        "source": "user",
                        "capabilities": approval_request.get("capabilities", []),
                        "tool_name": approval_request.get("tool_name", "*"),
                        "evidence": evidence,
                    },
                )
            resolved = connection.execute(
                "SELECT * FROM agent_interactions WHERE id = ?",
                (interaction_id,),
            ).fetchone()
            assert resolved is not None
            return self._interaction(resolved)

    def request_pause(self, run_id: str) -> AgentRunRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("agent_run", run_id)
            if row["status"] == "interrupted":
                return self._run(row)
            if row["status"] not in ("queued", "planning", "running"):
                raise ResourceConflictError(
                    "Only a queued, planning, or running AgentRun can pause"
                )
            connection.execute(
                """
                UPDATE agent_runs SET status = 'interrupted', error_json = ?,
                    revision = revision + 1, updated_at = ? WHERE id = ?
                """,
                (_json({"code": "user_paused"}), now, run_id),
            )
            updated = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            assert updated is not None
            self._status_line_in_transaction(
                connection,
                updated,
                phase="interrupted",
                text="Paused",
                presentation="warning",
            )
            session = connection.execute(
                "SELECT app_instance_id FROM sessions WHERE id = ?",
                (updated["session_id"],),
            ).fetchone()
            assert session is not None
            self.events.append_in_transaction(
                connection,
                event_type="agent.run.paused",
                subject_id=run_id,
                app_instance_id=session["app_instance_id"],
                session_id=updated["session_id"],
                payload={"run_id": run_id, "status": "interrupted"},
            )
            return self._run(updated)

    def request_cancel(self, run_id: str) -> AgentRunRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("agent_run", run_id)
            if row["status"] in ("completed", "failed", "cancelled"):
                return self._run(row)
            connection.execute(
                """
                UPDATE agent_runs SET status = 'cancelled', cancel_requested = 1,
                    finished_at = ?, revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (now, now, run_id),
            )
            connection.execute(
                """
                UPDATE agent_interactions SET status = 'cancelled', resolved_at = ?,
                    revision = revision + 1, updated_at = ?
                WHERE run_id = ? AND status = 'pending'
                """,
                (now, now, run_id),
            )
            updated = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            assert updated is not None
            self._status_line_in_transaction(
                connection,
                updated,
                phase="cancelled",
                text="Cancelled",
                presentation="plain",
            )
            session = connection.execute(
                "SELECT app_instance_id FROM sessions WHERE id = ?",
                (updated["session_id"],),
            ).fetchone()
            assert session is not None
            self.events.append_in_transaction(
                connection,
                event_type="agent.run.cancelled",
                subject_id=run_id,
                app_instance_id=session["app_instance_id"],
                session_id=updated["session_id"],
                payload={"run_id": run_id, "status": "cancelled"},
            )
            return self._run(updated)

    def resume_interrupted(
        self,
        run_id: str,
        *,
        uncertain_resolution: str | None = None,
    ) -> AgentRunRecord:
        if uncertain_resolution not in {None, "retry", "assume_completed"}:
            raise ValueError("uncertain_resolution must be retry or assume_completed")
        now_dt = datetime.now(UTC)
        now = format_utc(now_dt)
        with self.database.transaction(write=True) as connection:
            run = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if run is None:
                raise ResourceNotFoundError("agent_run", run_id)
            if run["status"] != "interrupted":
                raise ResourceConflictError("Only an interrupted AgentRun can resume")
            resumed_deadline = _resume_deadline(
                run["deadline_at"], run["updated_at"], now_dt
            )
            uncertain = connection.execute(
                "SELECT * FROM run_steps WHERE run_id = ? AND status = 'uncertain'",
                (run_id,),
            ).fetchall()
            if uncertain and uncertain_resolution is None:
                raise ResourceConflictError(
                    "Uncertain Tool effects require retry or assume_completed"
                )
            for step in uncertain:
                if uncertain_resolution == "retry":
                    connection.execute(
                        """
                        UPDATE run_steps SET status = 'failed',
                            action_key = action_key || ':uncertain:' || id,
                            error_json = ?, finished_at = ? WHERE id = ?
                        """,
                        (
                            _json({"code": "uncertain_effect_retry_authorized"}),
                            now,
                            step["id"],
                        ),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE run_steps SET status = 'completed', output_json = ?,
                            finished_at = ? WHERE id = ?
                        """,
                        (
                            _json({"assumed_completed": True, "user_resolved": True}),
                            now,
                            step["id"],
                        ),
                    )
            connection.execute(
                """
                UPDATE agent_runs SET status = 'queued', error_json = NULL,
                    cancel_requested = 0, deadline_at = ?,
                    revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (resumed_deadline, now, run_id),
            )
            updated = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            assert updated is not None
            self._status_line_in_transaction(
                connection,
                updated,
                phase="queued",
                text="Queued to resume",
                presentation="pulse",
            )
            return self._run(updated)

    def recover_interrupted(self) -> dict[str, int]:
        recovered = interrupted = failed = 0
        now_dt = datetime.now(UTC)
        now = format_utc(now_dt)
        with self.database.transaction(write=True) as connection:
            suspended = connection.execute(
                """
                SELECT * FROM agent_runs
                WHERE status = 'queued'
                  AND json_extract(error_json, '$.code') = 'runtime_stopped'
                """
            ).fetchall()
            for run in suspended:
                connection.execute(
                    """
                    UPDATE agent_runs SET deadline_at = ?, error_json = NULL,
                        revision = revision + 1, updated_at = ? WHERE id = ?
                    """,
                    (
                        _resume_deadline(
                            run["deadline_at"], run["updated_at"], now_dt
                        ),
                        now,
                        run["id"],
                    ),
                )
                recovered += 1
            rows = connection.execute(
                """
                SELECT r.*, d.resume_policy FROM agent_runs r
                JOIN agent_definitions d ON d.id = r.agent_definition_id
                WHERE r.status IN ('planning', 'running')
                """
            ).fetchall()
            for run in rows:
                uncertain = connection.execute(
                    """
                    SELECT id FROM run_steps
                    WHERE run_id = ? AND kind = 'tool' AND status = 'running'
                    """,
                    (run["id"],),
                ).fetchall()
                if uncertain:
                    connection.execute(
                        "UPDATE run_steps SET status = 'uncertain' WHERE run_id = ? AND status = 'running'",
                        (run["id"],),
                    )
                    target = "interrupted"
                    error = {"code": "uncertain_tool_side_effect"}
                    interrupted += 1
                elif run["resume_policy"] == "restart":
                    target = "queued"
                    error = None
                    recovered += 1
                else:
                    target = "failed"
                    error = {"code": "run_interrupted"}
                    failed += 1
                recovered_deadline = (
                    run["deadline_at"]
                    if target == "failed"
                    else _resume_deadline(run["deadline_at"], run["updated_at"], now_dt)
                )
                connection.execute(
                    """
                    UPDATE agent_runs SET status = ?, error_json = ?, deadline_at = ?,
                        finished_at = CASE WHEN ? = 'failed' THEN ? ELSE NULL END,
                        revision = revision + 1, updated_at = ? WHERE id = ?
                    """,
                    (
                        target,
                        None if error is None else _json(error),
                        recovered_deadline,
                        target,
                        now,
                        now,
                        run["id"],
                    ),
                )
                updated = connection.execute(
                    "SELECT * FROM agent_runs WHERE id = ?", (run["id"],)
                ).fetchone()
                assert updated is not None
                status_text = {
                    "queued": "Recovered and queued",
                    "interrupted": "Interrupted during a Tool; choose recovery",
                    "failed": "Failed after server interruption",
                }[target]
                self._status_line_in_transaction(
                    connection,
                    updated,
                    phase=target,
                    text=status_text,
                    presentation="warning" if target != "failed" else "error",
                )
        return {"recovered": recovered, "interrupted": interrupted, "failed": failed}

    def expire_interactions(self) -> int:
        now = utc_now_text()
        count = 0
        with self.database.transaction(write=True) as connection:
            rows = connection.execute(
                """
                SELECT * FROM agent_interactions
                WHERE status = 'pending' AND deadline_at <= ?
                """,
                (now,),
            ).fetchall()
            for interaction in rows:
                connection.execute(
                    """
                    UPDATE agent_interactions SET status = 'expired', resolved_at = ?,
                        revision = revision + 1, updated_at = ? WHERE id = ?
                    """,
                    (now, now, interaction["id"]),
                )
                connection.execute(
                    """
                    UPDATE agent_runs SET status = 'failed', error_json = ?,
                        finished_at = ?, revision = revision + 1, updated_at = ?
                    WHERE id = ? AND status IN ('waiting_input', 'waiting_capability')
                    """,
                    (
                        _json(
                            {
                                "code": "interaction_expired",
                                "interaction_id": interaction["id"],
                            }
                        ),
                        now,
                        now,
                        interaction["run_id"],
                    ),
                )
                run = connection.execute(
                    "SELECT * FROM agent_runs WHERE id = ?",
                    (interaction["run_id"],),
                ).fetchone()
                assert run is not None
                if run["status"] == "failed":
                    self._status_line_in_transaction(
                        connection,
                        run,
                        phase="failed",
                        text="Interaction expired",
                        presentation="error",
                    )
                    session = connection.execute(
                        "SELECT app_instance_id FROM sessions WHERE id = ?",
                        (run["session_id"],),
                    ).fetchone()
                    assert session is not None
                    self.events.append_in_transaction(
                        connection,
                        event_type="agent.interaction.expired",
                        subject_id=run["id"],
                        app_instance_id=session["app_instance_id"],
                        session_id=run["session_id"],
                        payload={
                            "run_id": run["id"],
                            "interaction_id": interaction["id"],
                        },
                    )
                count += 1
        return count
