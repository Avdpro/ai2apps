"""Durable Service and Tool registries."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from typing import Any

from jsonschema import Draft202012Validator

from ai2apps.core import (
    EntityIdKind,
    ResourceConflictError,
    ResourceNotFoundError,
    RevisionConflictError,
    new_entity_id,
    parse_utc,
    utc_now_text,
)
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase

from .models import (
    ServiceDependency,
    ServiceDescriptorRecord,
    ServiceInstanceRecord,
    ServiceInstanceStatus,
    ServiceRuntimeMode,
    ServiceStatus,
    ToolDescriptorRecord,
    ToolInvocationRecord,
    ToolInvocationStatus,
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class ServiceRepository:
    def __init__(self, database: PlatformDatabase, events: EventStore) -> None:
        self.database = database
        self.events = events

    @staticmethod
    def _dependencies(connection, service_id: str) -> tuple[ServiceDependency, ...]:
        rows = connection.execute(
            """
            SELECT dependency_key, version_spec, optional
            FROM service_dependencies WHERE service_id = ?
            ORDER BY dependency_key
            """,
            (service_id,),
        ).fetchall()
        return tuple(
            ServiceDependency(
                row["dependency_key"], row["version_spec"], bool(row["optional"])
            )
            for row in rows
        )

    @classmethod
    def _service(cls, connection, row) -> ServiceDescriptorRecord:
        return ServiceDescriptorRecord(
            id=row["id"],
            service_key=row["service_key"],
            package_id=row["package_id"],
            package_version=row["package_version"],
            display_name=row["display_name"],
            runtime_mode=ServiceRuntimeMode(row["execution_mode"]),
            source=row["source"],
            status=ServiceStatus(row["status"]),
            capabilities=tuple(json.loads(row["capabilities_json"])),
            config=json.loads(row["config_json"]),
            package_digest=row["active_package_digest"],
            permissions=json.loads(row["permissions_json"]),
            dependencies=cls._dependencies(connection, row["id"]),
            revision=row["revision"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _instance(row) -> ServiceInstanceRecord:
        return ServiceInstanceRecord(
            id=row["id"],
            service_id=row["service_id"],
            provider_key=row["provider_key"],
            status=ServiceInstanceStatus(row["status"]),
            endpoint=row["endpoint"],
            health=json.loads(row["health_json"]),
            last_error=row["last_error"],
            revision=row["revision"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _tool(row) -> ToolDescriptorRecord:
        return ToolDescriptorRecord(
            id=row["id"],
            service_id=row["service_id"],
            qualified_name=row["qualified_name"],
            display_name=row["display_name"],
            description=row["description"],
            input_schema=json.loads(row["input_schema_json"]),
            output_schema=json.loads(row["output_schema_json"]),
            effects=tuple(json.loads(row["effects_json"])),
            required_capabilities=tuple(json.loads(row["required_capabilities_json"])),
            capability_rules=tuple(json.loads(row["capability_rules_json"])),
            retry_policy=json.loads(row["retry_policy_json"]),
            timeout_ms=row["timeout_ms"],
            enabled=bool(row["enabled"]),
            revision=row["revision"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    def ensure_service(
        self,
        *,
        service_key: str,
        package_id: str,
        package_version: str,
        display_name: str,
        runtime_mode: ServiceRuntimeMode,
        source: str = "builtin",
        capabilities: Iterable[str] = (),
        config: dict[str, Any] | None = None,
        package_digest: str | None = None,
        permissions: dict[str, Any] | None = None,
        dependencies: Iterable[ServiceDependency] = (),
    ) -> ServiceDescriptorRecord:
        now = utc_now_text()
        service_id = new_entity_id(EntityIdKind.SERVICE)
        capabilities_value = tuple(sorted(set(capabilities)))
        dependencies_value = tuple(dependencies)
        try:
            with self.database.transaction(write=True) as connection:
                row = connection.execute(
                    "SELECT * FROM service_descriptors WHERE service_key = ?",
                    (service_key,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO service_descriptors(
                            id, service_key, package_id, package_version, display_name,
                            runtime_mode, execution_mode, source, capabilities_json,
                            config_json, active_package_digest, permissions_json,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            service_id,
                            service_key,
                            package_id,
                            package_version,
                            display_name,
                            (
                                ServiceRuntimeMode.EXTERNAL.value
                                if runtime_mode is ServiceRuntimeMode.MANAGED_PROCESS
                                else runtime_mode.value
                            ),
                            runtime_mode.value,
                            source,
                            _json(capabilities_value),
                            _json(config or {}),
                            package_digest,
                            _json(permissions or {}),
                            now,
                            now,
                        ),
                    )
                    self.events.append_in_transaction(
                        connection,
                        event_type="service.registered",
                        subject_id=service_id,
                        payload={
                            "service_key": service_key,
                            "runtime_mode": runtime_mode.value,
                        },
                    )
                else:
                    service_id = row["id"]
                    if row["package_id"] != package_id:
                        raise ResourceConflictError(
                            f"Service key {service_key} is owned by {row['package_id']}"
                        )
                    old_dependencies = self._dependencies(connection, service_id)
                    descriptor_changed = (
                        row["package_version"] != package_version
                        or row["display_name"] != display_name
                        or row["execution_mode"] != runtime_mode.value
                        or row["source"] != source
                        or row["capabilities_json"] != _json(capabilities_value)
                        or row["config_json"] != _json(config or {})
                        or row["active_package_digest"] != package_digest
                        or row["permissions_json"] != _json(permissions or {})
                        or old_dependencies
                        != tuple(
                            sorted(
                                dependencies_value,
                                key=lambda dependency: dependency.service_key,
                            )
                        )
                    )
                    if descriptor_changed:
                        connection.execute(
                            """
                            UPDATE service_descriptors
                            SET package_version = ?, display_name = ?, runtime_mode = ?,
                                execution_mode = ?, source = ?, capabilities_json = ?,
                                config_json = ?, active_package_digest = ?, permissions_json = ?,
                                revision = revision + 1, updated_at = ?
                            WHERE id = ?
                            """,
                            (
                                package_version,
                                display_name,
                                (
                                    ServiceRuntimeMode.EXTERNAL.value
                                    if runtime_mode
                                    is ServiceRuntimeMode.MANAGED_PROCESS
                                    else runtime_mode.value
                                ),
                                runtime_mode.value,
                                source,
                                _json(capabilities_value),
                                _json(config or {}),
                                package_digest,
                                _json(permissions or {}),
                                now,
                                service_id,
                            ),
                        )
                connection.execute(
                    "DELETE FROM service_dependencies WHERE service_id = ?",
                    (service_id,),
                )
                for dependency in dependencies_value:
                    connection.execute(
                        """
                        INSERT INTO service_dependencies(
                            service_id, dependency_key, version_spec, optional
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (
                            service_id,
                            dependency.service_key,
                            dependency.version_spec,
                            int(dependency.optional),
                        ),
                    )
                row = connection.execute(
                    "SELECT * FROM service_descriptors WHERE id = ?", (service_id,)
                ).fetchone()
                assert row is not None
                return self._service(connection, row)
        except sqlite3.IntegrityError as exc:
            raise ResourceConflictError(str(exc)) from exc

    def get_service(self, service_id_or_key: str) -> ServiceDescriptorRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM service_descriptors
                WHERE id = ? OR service_key = ?
                """,
                (service_id_or_key, service_id_or_key),
            ).fetchone()
            if row is not None:
                return self._service(connection, row)
        raise ResourceNotFoundError("service", service_id_or_key)

    def list_services(self) -> tuple[ServiceDescriptorRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM service_descriptors ORDER BY service_key"
            ).fetchall()
            return tuple(self._service(connection, row) for row in rows)

    def set_service_status(
        self,
        service_id_or_key: str,
        *,
        expected_revision: int,
        status: ServiceStatus,
    ) -> ServiceDescriptorRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            current = connection.execute(
                "SELECT * FROM service_descriptors WHERE id = ? OR service_key = ?",
                (service_id_or_key, service_id_or_key),
            ).fetchone()
            if current is None:
                raise ResourceNotFoundError("service", service_id_or_key)
            if current["revision"] != expected_revision:
                raise RevisionConflictError(
                    current["id"], expected_revision, current["revision"]
                )
            connection.execute(
                """
                UPDATE service_descriptors
                SET status = ?, revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (status.value, now, current["id"]),
            )
            row = connection.execute(
                "SELECT * FROM service_descriptors WHERE id = ?", (current["id"],)
            ).fetchone()
            assert row is not None
            self.events.append_in_transaction(
                connection,
                event_type=f"service.{status.value}",
                subject_id=current["id"],
                payload={"service_key": current["service_key"]},
            )
            return self._service(connection, row)

    def ensure_instance(
        self,
        *,
        service_id: str,
        provider_key: str,
        status: ServiceInstanceStatus,
        endpoint: str | None = None,
        health: dict[str, Any] | None = None,
    ) -> ServiceInstanceRecord:
        now = utc_now_text()
        instance_id = new_entity_id(EntityIdKind.SERVICE_INSTANCE)
        try:
            with self.database.transaction(write=True) as connection:
                row = connection.execute(
                    "SELECT * FROM service_instances WHERE provider_key = ?",
                    (provider_key,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO service_instances(
                            id, service_id, provider_key, status, endpoint,
                            health_json, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            instance_id,
                            service_id,
                            provider_key,
                            status.value,
                            endpoint,
                            _json(health or {}),
                            now,
                            now,
                        ),
                    )
                    self.events.append_in_transaction(
                        connection,
                        event_type="service.instance.registered",
                        subject_id=instance_id,
                        payload={
                            "service_id": service_id,
                            "provider_key": provider_key,
                        },
                    )
                else:
                    instance_id = row["id"]
                    if row["service_id"] != service_id:
                        raise ResourceConflictError(
                            f"Provider key {provider_key} is bound to another Service"
                        )
                    connection.execute(
                        """
                        UPDATE service_instances
                        SET status = ?, endpoint = ?, health_json = ?, last_error = NULL,
                            revision = revision + 1, updated_at = ?
                        WHERE id = ?
                        """,
                        (status.value, endpoint, _json(health or {}), now, instance_id),
                    )
                row = connection.execute(
                    "SELECT * FROM service_instances WHERE id = ?", (instance_id,)
                ).fetchone()
                assert row is not None
                if status in {
                    ServiceInstanceStatus.STARTING,
                    ServiceInstanceStatus.RUNNING,
                    ServiceInstanceStatus.DEGRADED,
                }:
                    connection.execute(
                        """
                        UPDATE service_instances
                        SET status = 'stopped', revision = revision + 1, updated_at = ?
                        WHERE service_id = ? AND id != ?
                          AND status IN ('starting', 'running', 'degraded')
                        """,
                        (now, service_id, instance_id),
                    )
                return self._instance(row)
        except sqlite3.IntegrityError as exc:
            raise ResourceConflictError(str(exc)) from exc

    def get_instance_for_service(self, service_id: str) -> ServiceInstanceRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM service_instances WHERE service_id = ?
                ORDER BY
                    CASE status
                        WHEN 'running' THEN 0
                        WHEN 'degraded' THEN 1
                        WHEN 'starting' THEN 2
                        ELSE 3
                    END,
                    updated_at DESC,
                    created_at DESC
                LIMIT 1
                """,
                (service_id,),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("service_instance", service_id)
        return self._instance(row)

    def set_instance_status(
        self,
        instance_id: str,
        status: ServiceInstanceStatus,
        *,
        health: dict[str, Any] | None = None,
        last_error: str | None = None,
    ) -> ServiceInstanceRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute(
                """
                UPDATE service_instances
                SET status = ?, health_json = COALESCE(?, health_json), last_error = ?,
                    revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    None if health is None else _json(health),
                    last_error,
                    now,
                    instance_id,
                ),
            )
            if cursor.rowcount == 0:
                raise ResourceNotFoundError("service_instance", instance_id)
            row = connection.execute(
                "SELECT * FROM service_instances WHERE id = ?", (instance_id,)
            ).fetchone()
            assert row is not None
            self.events.append_in_transaction(
                connection,
                event_type=f"service.instance.{status.value}",
                subject_id=instance_id,
                payload={"service_id": row["service_id"]},
            )
            return self._instance(row)

    def ensure_tool(
        self,
        *,
        service_id: str,
        qualified_name: str,
        display_name: str,
        description: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        effects: Iterable[str] = (),
        required_capabilities: Iterable[str] = (),
        capability_rules: Iterable[dict[str, Any]] = (),
        retry_policy: dict[str, Any] | None = None,
        timeout_ms: int = 30_000,
    ) -> ToolDescriptorRecord:
        Draft202012Validator.check_schema(input_schema)
        Draft202012Validator.check_schema(output_schema)
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        effects_value = tuple(sorted(set(effects)))
        supplied_retry_policy = retry_policy or {}
        unknown_retry_fields = set(supplied_retry_policy) - {
            "max_attempts",
            "backoff_ms",
            "retry_codes",
            "allow_effect_replay",
        }
        if unknown_retry_fields:
            raise ValueError(
                f"Unknown retry_policy fields: {sorted(unknown_retry_fields)}"
            )
        retry_policy_value = {
            "max_attempts": 1,
            "backoff_ms": 0,
            "retry_codes": [],
            "allow_effect_replay": False,
            **supplied_retry_policy,
        }
        if (
            not isinstance(retry_policy_value["max_attempts"], int)
            or not 1 <= retry_policy_value["max_attempts"] <= 3
        ):
            raise ValueError("retry_policy.max_attempts must be between 1 and 3")
        if (
            not isinstance(retry_policy_value["backoff_ms"], int)
            or not 0 <= retry_policy_value["backoff_ms"] <= 5_000
        ):
            raise ValueError("retry_policy.backoff_ms must be between 0 and 5000")
        retry_codes = retry_policy_value["retry_codes"]
        if not isinstance(retry_codes, list) or not all(
            isinstance(code, str) for code in retry_codes
        ):
            raise ValueError("retry_policy.retry_codes must be an array of strings")
        if set(retry_codes) - {"provider_error", "tool_timeout"}:
            raise ValueError("retry_policy contains an unsupported retry code")
        if (
            effects_value
            and retry_policy_value["max_attempts"] > 1
            and retry_policy_value["allow_effect_replay"] is not True
        ):
            raise ValueError(
                "Effectful Tool retries require retry_policy.allow_effect_replay"
            )
        now = utc_now_text()
        tool_id = new_entity_id(EntityIdKind.TOOL)
        values = (
            display_name,
            description,
            _json(input_schema),
            _json(output_schema),
            _json(effects_value),
            _json(tuple(sorted(set(required_capabilities)))),
            _json(tuple(capability_rules)),
            _json(retry_policy_value),
            timeout_ms,
        )
        try:
            with self.database.transaction(write=True) as connection:
                row = connection.execute(
                    "SELECT * FROM tool_descriptors WHERE qualified_name = ?",
                    (qualified_name,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO tool_descriptors(
                            id, service_id, qualified_name, display_name, description,
                            input_schema_json, output_schema_json, effects_json,
                            required_capabilities_json, capability_rules_json,
                            retry_policy_json,
                            timeout_ms, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (tool_id, service_id, qualified_name, *values, now, now),
                    )
                    self.events.append_in_transaction(
                        connection,
                        event_type="tool.registered",
                        subject_id=tool_id,
                        payload={
                            "service_id": service_id,
                            "qualified_name": qualified_name,
                        },
                    )
                else:
                    tool_id = row["id"]
                    if row["service_id"] != service_id:
                        raise ResourceConflictError(
                            f"Tool name {qualified_name} is owned by another Service"
                        )
                    current_values = (
                        row["display_name"],
                        row["description"],
                        row["input_schema_json"],
                        row["output_schema_json"],
                        row["effects_json"],
                        row["required_capabilities_json"],
                        row["capability_rules_json"],
                        row["retry_policy_json"],
                        row["timeout_ms"],
                    )
                    if current_values != values or not row["enabled"]:
                        connection.execute(
                            """
                            UPDATE tool_descriptors
                            SET display_name = ?, description = ?, input_schema_json = ?,
                                output_schema_json = ?, effects_json = ?,
                                required_capabilities_json = ?, capability_rules_json = ?,
                                retry_policy_json = ?,
                                timeout_ms = ?, enabled = 1,
                                revision = revision + 1, updated_at = ?
                            WHERE id = ?
                            """,
                            (*values, now, tool_id),
                        )
                row = connection.execute(
                    "SELECT * FROM tool_descriptors WHERE id = ?", (tool_id,)
                ).fetchone()
                assert row is not None
                return self._tool(row)
        except sqlite3.IntegrityError as exc:
            raise ResourceConflictError(str(exc)) from exc

    @staticmethod
    def _invocation(row) -> ToolInvocationRecord:
        return ToolInvocationRecord(
            id=row["id"],
            tool_id=row["tool_id"],
            qualified_name=row["qualified_name"],
            provider_key=row["provider_key"],
            caller_id=row["caller_id"],
            session_id=row["session_id"],
            trace_id=row["trace_id"],
            status=ToolInvocationStatus(row["status"]),
            arguments=json.loads(row["arguments_json"]),
            output=(
                None if row["output_json"] is None else json.loads(row["output_json"])
            ),
            error=(
                None if row["error_json"] is None else json.loads(row["error_json"])
            ),
            progress=json.loads(row["progress_json"]),
            timeout_ms=row["timeout_ms"],
            attempt=row["attempt"],
            duration_ms=row["duration_ms"],
            revision=row["revision"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
            finished_at=(
                None if row["finished_at"] is None else parse_utc(row["finished_at"])
            ),
        )

    def create_invocation(
        self,
        *,
        tool: ToolDescriptorRecord,
        provider_key: str,
        caller_id: str,
        session_id: str | None,
        trace_id: str | None,
        arguments: dict[str, Any],
        timeout_ms: int,
    ) -> ToolInvocationRecord:
        invocation_id = new_entity_id(EntityIdKind.TOOL_INVOCATION)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO tool_invocations(
                    id, tool_id, qualified_name, provider_key, caller_id,
                    session_id, trace_id, status, arguments_json, timeout_ms,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?, ?)
                """,
                (
                    invocation_id,
                    tool.id,
                    tool.qualified_name,
                    provider_key,
                    caller_id,
                    session_id,
                    trace_id,
                    _json(arguments),
                    timeout_ms,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM tool_invocations WHERE id = ?", (invocation_id,)
            ).fetchone()
        assert row is not None
        return self._invocation(row)

    def update_invocation_progress(
        self, invocation_id: str, progress: dict[str, Any]
    ) -> ToolInvocationRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute(
                """
                UPDATE tool_invocations
                SET progress_json = ?, revision = revision + 1, updated_at = ?
                WHERE id = ? AND status = 'running'
                """,
                (_json(progress), now, invocation_id),
            )
            if cursor.rowcount != 1:
                raise ResourceConflictError(
                    f"Tool invocation is not running: {invocation_id}"
                )
            row = connection.execute(
                "SELECT * FROM tool_invocations WHERE id = ?", (invocation_id,)
            ).fetchone()
        assert row is not None
        return self._invocation(row)

    def set_invocation_attempt(
        self, invocation_id: str, attempt: int
    ) -> ToolInvocationRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                UPDATE tool_invocations
                SET attempt = ?, revision = revision + 1, updated_at = ?
                WHERE id = ? AND status = 'running'
                """,
                (attempt, now, invocation_id),
            )
            row = connection.execute(
                "SELECT * FROM tool_invocations WHERE id = ?", (invocation_id,)
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("tool_invocation", invocation_id)
        return self._invocation(row)

    def settle_invocation(
        self,
        invocation_id: str,
        *,
        status: ToolInvocationStatus,
        duration_ms: int,
        output: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> ToolInvocationRecord:
        if status is ToolInvocationStatus.RUNNING:
            raise ValueError("A Tool invocation cannot settle as running")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute(
                """
                UPDATE tool_invocations
                SET status = ?, output_json = ?, error_json = ?, duration_ms = ?,
                    finished_at = ?, revision = revision + 1, updated_at = ?
                WHERE id = ? AND status = 'running'
                """,
                (
                    status.value,
                    None if output is None else _json(output),
                    None if error is None else _json(error),
                    duration_ms,
                    now,
                    now,
                    invocation_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ResourceConflictError(
                    f"Tool invocation is not running: {invocation_id}"
                )
            row = connection.execute(
                "SELECT * FROM tool_invocations WHERE id = ?", (invocation_id,)
            ).fetchone()
        assert row is not None
        return self._invocation(row)

    def get_invocation(self, invocation_id: str) -> ToolInvocationRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM tool_invocations WHERE id = ?", (invocation_id,)
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("tool_invocation", invocation_id)
        return self._invocation(row)

    def list_invocations(
        self,
        *,
        session_id: str | None = None,
        trace_id: str | None = None,
        status: ToolInvocationStatus | None = None,
        limit: int = 100,
    ) -> tuple[ToolInvocationRecord, ...]:
        conditions = []
        params: list[Any] = []
        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)
        if trace_id is not None:
            conditions.append("trace_id = ?")
            params.append(trace_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)
        where = "" if not conditions else "WHERE " + " AND ".join(conditions)
        params.append(max(1, min(limit, 1000)))
        with self.database.transaction() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM tool_invocations {where}
                ORDER BY created_at DESC LIMIT ?
                """,
                params,
            ).fetchall()
        return tuple(self._invocation(row) for row in rows)

    def recover_interrupted_invocations(self) -> tuple[ToolInvocationRecord, ...]:
        now = utc_now_text()
        error = _json({"code": "runtime_restarted"})
        with self.database.transaction(write=True) as connection:
            rows = connection.execute(
                "SELECT id FROM tool_invocations WHERE status = 'running'"
            ).fetchall()
            connection.execute(
                """
                UPDATE tool_invocations
                SET status = 'interrupted', error_json = ?, finished_at = ?,
                    revision = revision + 1, updated_at = ?
                WHERE status = 'running'
                """,
                (error, now, now),
            )
            recovered = [
                connection.execute(
                    "SELECT * FROM tool_invocations WHERE id = ?", (row["id"],)
                ).fetchone()
                for row in rows
            ]
        return tuple(self._invocation(row) for row in recovered if row is not None)

    def get_tool(self, tool_id_or_name: str) -> ToolDescriptorRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM tool_descriptors
                WHERE id = ? OR qualified_name = ?
                """,
                (tool_id_or_name, tool_id_or_name),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("tool", tool_id_or_name)
        return self._tool(row)

    def list_tools(
        self, *, include_disabled: bool = False
    ) -> tuple[ToolDescriptorRecord, ...]:
        condition = "" if include_disabled else "WHERE enabled = 1"
        with self.database.transaction() as connection:
            rows = connection.execute(
                f"SELECT * FROM tool_descriptors {condition} ORDER BY qualified_name"
            ).fetchall()
        return tuple(self._tool(row) for row in rows)

    def disable_unseen_tools(self, service_id: str, active_names: set[str]) -> None:
        with self.database.transaction(write=True) as connection:
            rows = connection.execute(
                "SELECT id, qualified_name FROM tool_descriptors WHERE service_id = ?",
                (service_id,),
            ).fetchall()
            for row in rows:
                if row["qualified_name"] not in active_names:
                    connection.execute(
                        "UPDATE tool_descriptors SET enabled = 0 WHERE id = ?",
                        (row["id"],),
                    )

    def remove_service(self, service_id_or_key: str) -> None:
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT id, service_key FROM service_descriptors WHERE id = ? OR service_key = ?",
                (service_id_or_key, service_id_or_key),
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("service", service_id_or_key)
            connection.execute(
                "DELETE FROM tool_descriptors WHERE service_id = ?", (row["id"],)
            )
            connection.execute(
                "DELETE FROM service_instances WHERE service_id = ?", (row["id"],)
            )
            connection.execute(
                "DELETE FROM service_dependencies WHERE service_id = ?", (row["id"],)
            )
            connection.execute(
                "DELETE FROM service_descriptors WHERE id = ?", (row["id"],)
            )
            self.events.append_in_transaction(
                connection,
                event_type="service.uninstalled",
                subject_id=row["id"],
                payload={"service_key": row["service_key"]},
            )
