"""AppDefinition and AppInstance persistence."""

from __future__ import annotations

import sqlite3
from typing import Any

from ai2apps.core import (
    AppDefinitionStatus,
    AppInstanceMode,
    AppInstanceStatus,
    EntityIdKind,
    ResourceConflictError,
    ResourceNotFoundError,
    RevisionConflictError,
    SingletonScope,
    new_entity_id,
    utc_now_text,
)
from ai2apps.events import EventStore
from ai2apps.storage.database import PlatformDatabase
from ai2apps.storage.models import AppDefinitionRecord, AppInstanceRecord
from ai2apps.storage.records import (
    app_definition_from_row,
    app_instance_from_row,
    canonical_json,
)


class AppRepository:
    def __init__(
        self,
        database: PlatformDatabase,
        event_store: EventStore | None = None,
    ) -> None:
        self.database = database
        self.events = event_store or EventStore(database)

    def create_definition(
        self,
        *,
        package_id: str,
        package_version: str,
        display_name: str,
        instance_mode: AppInstanceMode,
        singleton_scope: SingletonScope | None = None,
        source: str = "local",
        status: AppDefinitionStatus = AppDefinitionStatus.ENABLED,
        manifest_schema_version: int = 1,
        manifest: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> AppDefinitionRecord:
        definition_id = new_entity_id(EntityIdKind.APP_DEFINITION)
        now = utc_now_text()
        try:
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    """
                    INSERT INTO app_definitions(
                        id, package_id, package_version, display_name,
                        instance_mode, singleton_scope, source, status,
                        manifest_schema_version, manifest_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        definition_id,
                        package_id,
                        package_version,
                        display_name,
                        instance_mode.value,
                        None if singleton_scope is None else singleton_scope.value,
                        source,
                        status.value,
                        manifest_schema_version,
                        canonical_json(manifest or {}),
                        now,
                        now,
                    ),
                )
                self.events.append_in_transaction(
                    connection,
                    event_type="app.definition.created",
                    subject_id=definition_id,
                    trace_id=trace_id,
                    payload={
                        "package_id": package_id,
                        "package_version": package_version,
                    },
                )
                row = connection.execute(
                    "SELECT * FROM app_definitions WHERE id = ?", (definition_id,)
                ).fetchone()
                assert row is not None
                return app_definition_from_row(row)
        except sqlite3.IntegrityError as exc:
            raise ResourceConflictError(str(exc)) from exc

    def get_definition(self, definition_id: str) -> AppDefinitionRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM app_definitions WHERE id = ?", (definition_id,)
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("app_definition", definition_id)
        return app_definition_from_row(row)

    def create_instance(
        self,
        *,
        app_definition_id: str,
        singleton_key: str | None = None,
        owner_user_id: str | None = None,
        status: AppInstanceStatus = AppInstanceStatus.ACTIVE,
        state_schema_version: int = 1,
        state: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> AppInstanceRecord:
        instance_id = new_entity_id(EntityIdKind.APP_INSTANCE)
        now = utc_now_text()
        try:
            with self.database.transaction(write=True) as connection:
                definition = connection.execute(
                    "SELECT id FROM app_definitions WHERE id = ?",
                    (app_definition_id,),
                ).fetchone()
                if definition is None:
                    raise ResourceNotFoundError(
                        "app_definition", app_definition_id
                    )
                connection.execute(
                    """
                    INSERT INTO app_instances(
                        id, app_definition_id, singleton_key, status,
                        state_schema_version, state_json, owner_user_id,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        instance_id,
                        app_definition_id,
                        singleton_key,
                        status.value,
                        state_schema_version,
                        canonical_json(state or {}),
                        owner_user_id,
                        now,
                        now,
                    ),
                )
                self.events.append_in_transaction(
                    connection,
                    event_type="app.instance.created",
                    subject_id=instance_id,
                    app_instance_id=instance_id,
                    trace_id=trace_id,
                    payload={
                        "app_definition_id": app_definition_id,
                        "owner_user_id": owner_user_id,
                    },
                )
                row = connection.execute(
                    "SELECT * FROM app_instances WHERE id = ?", (instance_id,)
                ).fetchone()
                assert row is not None
                return app_instance_from_row(row)
        except sqlite3.IntegrityError as exc:
            raise ResourceConflictError(str(exc)) from exc

    def get_instance(self, instance_id: str) -> AppInstanceRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM app_instances WHERE id = ?", (instance_id,)
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("app_instance", instance_id)
        return app_instance_from_row(row)

    def update_instance(
        self,
        instance_id: str,
        *,
        expected_revision: int,
        status: AppInstanceStatus | None = None,
        state_schema_version: int | None = None,
        state: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> AppInstanceRecord:
        changes: dict[str, Any] = {}
        if status is not None:
            changes["status"] = status.value
        if state_schema_version is not None:
            changes["state_schema_version"] = state_schema_version
        if state is not None:
            changes["state_json"] = canonical_json(state)
        if not changes:
            raise ValueError("At least one AppInstance field must change")

        now = utc_now_text()
        changes["updated_at"] = now
        if status is AppInstanceStatus.CLOSED:
            changes["closed_at"] = now
        elif status is not None:
            changes["closed_at"] = None
        assignments = [f"{column} = ?" for column in changes]
        assignments.append("revision = revision + 1")
        params = [*changes.values(), instance_id, expected_revision]

        try:
            with self.database.transaction(write=True) as connection:
                cursor = connection.execute(
                    f"""
                    UPDATE app_instances SET {', '.join(assignments)}
                    WHERE id = ? AND revision = ?
                    """,
                    params,
                )
                if cursor.rowcount == 0:
                    current = connection.execute(
                        "SELECT revision FROM app_instances WHERE id = ?",
                        (instance_id,),
                    ).fetchone()
                    if current is None:
                        raise ResourceNotFoundError("app_instance", instance_id)
                    raise RevisionConflictError(
                        instance_id,
                        expected_revision,
                        int(current["revision"]),
                    )
                row = connection.execute(
                    "SELECT * FROM app_instances WHERE id = ?", (instance_id,)
                ).fetchone()
                assert row is not None
                updated = app_instance_from_row(row)
                self.events.append_in_transaction(
                    connection,
                    event_type=(
                        "app.instance.closed"
                        if status is AppInstanceStatus.CLOSED
                        else "app.instance.updated"
                    ),
                    subject_id=instance_id,
                    app_instance_id=instance_id,
                    trace_id=trace_id,
                    payload={
                        "changed_fields": sorted(changes),
                        "revision": updated.revision,
                    },
                )
                return updated
        except sqlite3.IntegrityError as exc:
            raise ResourceConflictError(str(exc)) from exc
