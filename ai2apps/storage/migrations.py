"""Ordered, transactional migrations for the AI2Apps platform database."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from ai2apps.core import utc_now_text


class MigrationError(RuntimeError):
    """Base class for migration and schema compatibility failures."""


class FutureSchemaError(MigrationError):
    """The database was written by a newer AI2Apps schema version."""


class DatabaseCorruptionError(MigrationError):
    """SQLite or the migration ledger reported inconsistent durable state."""


class DatabaseBusyError(MigrationError):
    """The database remained locked beyond the configured startup timeout."""


@dataclass(frozen=True, slots=True)
class Migration:
    """One immutable, ordered database migration."""

    version: int
    name: str
    statements: tuple[str, ...] = ()


MIGRATIONS: tuple[Migration, ...] = (
    Migration(version=1, name="platform_bootstrap"),
    Migration(
        version=2,
        name="apps_sessions_messages_events",
        statements=(
            """
            CREATE TABLE app_definitions (
                id TEXT PRIMARY KEY
                    CHECK (
                        length(id) = 36 AND substr(id, 1, 4) = 'app_'
                        AND id = lower(id)
                        AND substr(id, 5) NOT GLOB '*[^0-9a-f]*'
                    ),
                package_id TEXT NOT NULL CHECK (length(package_id) > 0),
                package_version TEXT NOT NULL CHECK (length(package_version) > 0),
                display_name TEXT NOT NULL CHECK (length(display_name) > 0),
                instance_mode TEXT NOT NULL
                    CHECK (instance_mode IN ('multiple', 'singleton')),
                singleton_scope TEXT
                    CHECK (singleton_scope IN ('system', 'user', 'session')),
                source TEXT NOT NULL
                    CHECK (source IN ('builtin', 'local', 'installed')),
                status TEXT NOT NULL DEFAULT 'enabled'
                    CHECK (status IN ('enabled', 'disabled')),
                manifest_schema_version INTEGER NOT NULL DEFAULT 1
                    CHECK (manifest_schema_version >= 1),
                manifest_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(manifest_json)),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                updated_at TEXT NOT NULL
                    CHECK (length(updated_at) = 27 AND substr(updated_at, -1) = 'Z'),
                UNIQUE (package_id, package_version),
                CHECK (
                    (instance_mode = 'multiple' AND singleton_scope IS NULL)
                    OR
                    (instance_mode = 'singleton' AND singleton_scope IS NOT NULL)
                )
            )
            """,
            """
            CREATE TABLE app_instances (
                id TEXT PRIMARY KEY
                    CHECK (
                        length(id) = 37 AND substr(id, 1, 5) = 'appi_'
                        AND id = lower(id)
                        AND substr(id, 6) NOT GLOB '*[^0-9a-f]*'
                    ),
                app_definition_id TEXT NOT NULL,
                singleton_key TEXT UNIQUE,
                status TEXT NOT NULL DEFAULT 'creating'
                    CHECK (status IN (
                        'creating', 'active', 'background', 'suspended',
                        'closed', 'degraded', 'failed'
                    )),
                state_schema_version INTEGER NOT NULL DEFAULT 1
                    CHECK (state_schema_version >= 1),
                state_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(state_json)),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                updated_at TEXT NOT NULL
                    CHECK (length(updated_at) = 27 AND substr(updated_at, -1) = 'Z'),
                closed_at TEXT
                    CHECK (
                        closed_at IS NULL OR
                        (length(closed_at) = 27 AND substr(closed_at, -1) = 'Z')
                    ),
                FOREIGN KEY (app_definition_id)
                    REFERENCES app_definitions(id) ON DELETE RESTRICT
            )
            """,
            """
            CREATE INDEX idx_app_instances_definition
            ON app_instances(app_definition_id, status)
            """,
            """
            CREATE TRIGGER app_instances_policy_insert
            BEFORE INSERT ON app_instances
            WHEN (
                SELECT instance_mode = 'singleton'
                       AND NEW.singleton_key IS NULL
                FROM app_definitions WHERE id = NEW.app_definition_id
            ) OR (
                SELECT instance_mode = 'multiple'
                       AND NEW.singleton_key IS NOT NULL
                FROM app_definitions WHERE id = NEW.app_definition_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'app instance key violates definition policy');
            END
            """,
            """
            CREATE TRIGGER app_instances_policy_update
            BEFORE UPDATE OF app_definition_id, singleton_key ON app_instances
            WHEN (
                SELECT instance_mode = 'singleton'
                       AND NEW.singleton_key IS NULL
                FROM app_definitions WHERE id = NEW.app_definition_id
            ) OR (
                SELECT instance_mode = 'multiple'
                       AND NEW.singleton_key IS NOT NULL
                FROM app_definitions WHERE id = NEW.app_definition_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'app instance key violates definition policy');
            END
            """,
            """
            CREATE TRIGGER app_definition_policy_update
            BEFORE UPDATE OF instance_mode, singleton_scope ON app_definitions
            WHEN EXISTS (
                SELECT 1 FROM app_instances
                WHERE app_definition_id = OLD.id
            ) AND (
                NEW.instance_mode != OLD.instance_mode
                OR NEW.singleton_scope IS NOT OLD.singleton_scope
            )
            BEGIN
                SELECT RAISE(ABORT, 'cannot change instance policy with instances');
            END
            """,
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY
                    CHECK (
                        length(id) = 36 AND substr(id, 1, 4) = 'ses_'
                        AND id = lower(id)
                        AND substr(id, 5) NOT GLOB '*[^0-9a-f]*'
                    ),
                app_instance_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'archived', 'deleted')),
                is_home INTEGER NOT NULL DEFAULT 0 CHECK (is_home IN (0, 1)),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                metadata_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(metadata_json)),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                updated_at TEXT NOT NULL
                    CHECK (length(updated_at) = 27 AND substr(updated_at, -1) = 'Z'),
                archived_at TEXT
                    CHECK (
                        archived_at IS NULL OR
                        (length(archived_at) = 27 AND substr(archived_at, -1) = 'Z')
                    ),
                deleted_at TEXT
                    CHECK (
                        deleted_at IS NULL OR
                        (length(deleted_at) = 27 AND substr(deleted_at, -1) = 'Z')
                    ),
                FOREIGN KEY (app_instance_id)
                    REFERENCES app_instances(id) ON DELETE RESTRICT
            )
            """,
            """
            CREATE UNIQUE INDEX uq_sessions_home_per_instance
            ON sessions(app_instance_id) WHERE is_home = 1
            """,
            """
            CREATE INDEX idx_sessions_instance_status_updated
            ON sessions(app_instance_id, status, updated_at DESC)
            """,
            """
            CREATE TABLE messages (
                id TEXT PRIMARY KEY
                    CHECK (
                        length(id) = 36 AND substr(id, 1, 4) = 'msg_'
                        AND id = lower(id)
                        AND substr(id, 5) NOT GLOB '*[^0-9a-f]*'
                    ),
                session_id TEXT NOT NULL,
                sequence INTEGER NOT NULL CHECK (sequence > 0),
                role TEXT NOT NULL
                    CHECK (role IN ('user', 'assistant', 'system', 'tool', 'app')),
                status TEXT NOT NULL DEFAULT 'completed'
                    CHECK (status IN ('in_progress', 'completed', 'failed', 'cancelled')),
                idempotency_key TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(metadata_json)),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                updated_at TEXT NOT NULL
                    CHECK (length(updated_at) = 27 AND substr(updated_at, -1) = 'Z'),
                FOREIGN KEY (session_id)
                    REFERENCES sessions(id) ON DELETE RESTRICT,
                UNIQUE (session_id, sequence)
            )
            """,
            """
            CREATE UNIQUE INDEX uq_messages_session_idempotency
            ON messages(session_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL
            """,
            """
            CREATE INDEX idx_messages_session_created
            ON messages(session_id, sequence)
            """,
            """
            CREATE TABLE message_parts (
                id TEXT PRIMARY KEY
                    CHECK (
                        length(id) = 37 AND substr(id, 1, 5) = 'part_'
                        AND id = lower(id)
                        AND substr(id, 6) NOT GLOB '*[^0-9a-f]*'
                    ),
                message_id TEXT NOT NULL,
                position INTEGER NOT NULL CHECK (position >= 0),
                kind TEXT NOT NULL CHECK (length(kind) > 0),
                content_json TEXT NOT NULL CHECK (json_valid(content_json)),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                FOREIGN KEY (message_id)
                    REFERENCES messages(id) ON DELETE RESTRICT,
                UNIQUE (message_id, position)
            )
            """,
            """
            CREATE INDEX idx_message_parts_message_position
            ON message_parts(message_id, position)
            """,
            """
            CREATE TABLE events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE
                    CHECK (
                        length(id) = 36 AND substr(id, 1, 4) = 'evt_'
                        AND id = lower(id)
                        AND substr(id, 5) NOT GLOB '*[^0-9a-f]*'
                    ),
                type TEXT NOT NULL CHECK (length(type) > 0),
                occurred_at TEXT NOT NULL
                    CHECK (length(occurred_at) = 27 AND substr(occurred_at, -1) = 'Z'),
                app_instance_id TEXT,
                session_id TEXT,
                subject_id TEXT NOT NULL CHECK (length(subject_id) > 0),
                trace_id TEXT,
                schema_version INTEGER NOT NULL DEFAULT 1
                    CHECK (schema_version >= 1),
                payload_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(payload_json)),
                FOREIGN KEY (app_instance_id)
                    REFERENCES app_instances(id) ON DELETE RESTRICT,
                FOREIGN KEY (session_id)
                    REFERENCES sessions(id) ON DELETE RESTRICT,
                CHECK (session_id IS NULL OR app_instance_id IS NOT NULL)
            )
            """,
            """
            CREATE INDEX idx_events_session_sequence
            ON events(session_id, sequence)
            """,
            """
            CREATE INDEX idx_events_instance_sequence
            ON events(app_instance_id, sequence)
            """,
            """
            CREATE INDEX idx_events_type_sequence
            ON events(type, sequence)
            """,
            """
            CREATE TRIGGER events_scope_matches_session_insert
            BEFORE INSERT ON events
            WHEN NEW.session_id IS NOT NULL
                 AND NEW.app_instance_id IS NOT NULL
                 AND NOT EXISTS (
                     SELECT 1 FROM sessions
                     WHERE id = NEW.session_id
                       AND app_instance_id = NEW.app_instance_id
                 )
            BEGIN
                SELECT RAISE(ABORT, 'event scope does not own session');
            END
            """,
            """
            CREATE TRIGGER events_are_append_only_update
            BEFORE UPDATE ON events
            BEGIN
                SELECT RAISE(ABORT, 'events are append-only');
            END
            """,
            """
            CREATE TRIGGER events_are_append_only_delete
            BEFORE DELETE ON events
            BEGIN
                SELECT RAISE(ABORT, 'events are append-only');
            END
            """,
        ),
    ),
    Migration(
        version=3,
        name="generic_session_classification",
        statements=(
            """
            ALTER TABLE sessions ADD COLUMN session_kind TEXT NOT NULL DEFAULT 'app'
            CHECK (session_kind IN (
                'app', 'chat_thread', 'mini_chat', 'in_app_chat', 'agent_child'
            ))
            """,
            """
            ALTER TABLE sessions ADD COLUMN visibility TEXT NOT NULL DEFAULT 'listed'
            CHECK (visibility IN ('listed', 'unlisted'))
            """,
            """
            ALTER TABLE sessions ADD COLUMN retention TEXT NOT NULL DEFAULT 'durable'
            CHECK (retention IN ('durable', 'temporary'))
            """,
            """
            ALTER TABLE sessions ADD COLUMN expires_at TEXT
            CHECK (
                expires_at IS NULL OR
                (length(expires_at) = 27 AND substr(expires_at, -1) = 'Z')
            )
            """,
            """
            CREATE INDEX idx_sessions_collection
            ON sessions(
                app_instance_id, session_kind, visibility, retention,
                status, updated_at DESC
            )
            """,
            """
            CREATE TRIGGER chat_threads_are_listed_durable_insert
            BEFORE INSERT ON sessions
            WHEN NEW.session_kind = 'chat_thread'
                 AND (NEW.visibility != 'listed' OR NEW.retention != 'durable')
            BEGIN
                SELECT RAISE(ABORT, 'chat threads must be listed and durable');
            END
            """,
            """
            CREATE TRIGGER chat_threads_are_listed_durable_update
            BEFORE UPDATE OF session_kind, visibility, retention ON sessions
            WHEN NEW.session_kind = 'chat_thread'
                 AND (NEW.visibility != 'listed' OR NEW.retention != 'durable')
            BEGIN
                SELECT RAISE(ABORT, 'chat threads must be listed and durable');
            END
            """,
        ),
    ),
    Migration(
        version=4,
        name="temporary_session_retention",
        statements=(
            """
            UPDATE sessions
            SET expires_at =
                strftime('%Y-%m-%dT%H:%M:%f', updated_at, '+1 day') || '000Z'
            WHERE retention = 'temporary' AND expires_at IS NULL
            """,
            """
            CREATE INDEX idx_sessions_temporary_expiry
            ON sessions(expires_at, id)
            WHERE retention = 'temporary' AND status != 'deleted'
            """,
            """
            CREATE TRIGGER session_retention_expiry_insert
            BEFORE INSERT ON sessions
            WHEN (NEW.retention = 'temporary' AND NEW.expires_at IS NULL)
                 OR (NEW.retention = 'durable' AND NEW.expires_at IS NOT NULL)
            BEGIN
                SELECT RAISE(ABORT, 'session expiry violates retention policy');
            END
            """,
            """
            CREATE TRIGGER session_retention_expiry_update
            BEFORE UPDATE OF retention, expires_at ON sessions
            WHEN (NEW.retention = 'temporary' AND NEW.expires_at IS NULL)
                 OR (NEW.retention = 'durable' AND NEW.expires_at IS NOT NULL)
            BEGIN
                SELECT RAISE(ABORT, 'session expiry violates retention policy');
            END
            """,
        ),
    ),
    Migration(
        version=5,
        name="singleton_chat_collection",
        statements=(
            """
            CREATE TABLE chat_collections (
                app_instance_id TEXT PRIMARY KEY,
                selected_session_id TEXT,
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                updated_at TEXT NOT NULL
                    CHECK (length(updated_at) = 27 AND substr(updated_at, -1) = 'Z'),
                FOREIGN KEY (app_instance_id)
                    REFERENCES app_instances(id) ON DELETE RESTRICT,
                FOREIGN KEY (selected_session_id)
                    REFERENCES sessions(id) ON DELETE RESTRICT
            )
            """,
            """
            CREATE TABLE chat_thread_entries (
                session_id TEXT PRIMARY KEY,
                app_instance_id TEXT NOT NULL,
                pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1)),
                sort_order INTEGER NOT NULL CHECK (sort_order >= 1),
                legacy_thread_id TEXT UNIQUE,
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                updated_at TEXT NOT NULL
                    CHECK (length(updated_at) = 27 AND substr(updated_at, -1) = 'Z'),
                FOREIGN KEY (session_id)
                    REFERENCES sessions(id) ON DELETE RESTRICT,
                FOREIGN KEY (app_instance_id)
                    REFERENCES chat_collections(app_instance_id) ON DELETE RESTRICT,
                UNIQUE (app_instance_id, sort_order)
            )
            """,
            """
            CREATE INDEX idx_chat_threads_collection
            ON chat_thread_entries(app_instance_id, pinned DESC, sort_order DESC)
            """,
            """
            CREATE TRIGGER chat_collection_selected_insert
            BEFORE INSERT ON chat_collections
            WHEN NEW.selected_session_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM sessions
                WHERE id = NEW.selected_session_id
                  AND app_instance_id = NEW.app_instance_id
                  AND session_kind = 'chat_thread'
                  AND status = 'active'
            )
            BEGIN
                SELECT RAISE(ABORT, 'selected Chat thread is not active or owned');
            END
            """,
            """
            CREATE TRIGGER chat_collection_selected_update
            BEFORE UPDATE OF selected_session_id ON chat_collections
            WHEN NEW.selected_session_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM sessions
                WHERE id = NEW.selected_session_id
                  AND app_instance_id = NEW.app_instance_id
                  AND session_kind = 'chat_thread'
                  AND status = 'active'
            )
            BEGIN
                SELECT RAISE(ABORT, 'selected Chat thread is not active or owned');
            END
            """,
            """
            CREATE TRIGGER chat_thread_entry_insert
            BEFORE INSERT ON chat_thread_entries
            WHEN NOT EXISTS (
                SELECT 1 FROM sessions
                WHERE id = NEW.session_id
                  AND app_instance_id = NEW.app_instance_id
                  AND session_kind = 'chat_thread'
                  AND visibility = 'listed'
                  AND retention = 'durable'
            )
            BEGIN
                SELECT RAISE(ABORT, 'Chat entry must reference an owned Chat thread');
            END
            """,
            """
            CREATE TRIGGER chat_thread_classification_update
            BEFORE UPDATE OF app_instance_id, session_kind, visibility, retention
            ON sessions
            WHEN EXISTS (
                SELECT 1 FROM chat_thread_entries WHERE session_id = OLD.id
            ) AND (
                NEW.app_instance_id != OLD.app_instance_id
                OR NEW.session_kind != 'chat_thread'
                OR NEW.visibility != 'listed'
                OR NEW.retention != 'durable'
            )
            BEGIN
                SELECT RAISE(ABORT, 'managed Chat thread classification is immutable');
            END
            """,
            """
            CREATE TRIGGER selected_chat_thread_status_update
            BEFORE UPDATE OF status ON sessions
            WHEN NEW.status != 'active' AND EXISTS (
                SELECT 1 FROM chat_collections
                WHERE selected_session_id = OLD.id
            )
            BEGIN
                SELECT RAISE(ABORT, 'selected Chat thread must be reassigned first');
            END
            """,
            """
            CREATE TRIGGER home_chat_thread_status_update
            BEFORE UPDATE OF status ON sessions
            WHEN NEW.status != 'active' AND OLD.is_home = 1 AND EXISTS (
                SELECT 1 FROM chat_thread_entries WHERE session_id = OLD.id
            )
            BEGIN
                SELECT RAISE(ABORT, 'Home Chat thread must be reassigned first');
            END
            """,
        ),
    ),
    Migration(
        version=6,
        name="service_and_tool_registry",
        statements=(
            """
            CREATE TABLE service_descriptors (
                id TEXT PRIMARY KEY
                    CHECK (
                        length(id) = 36 AND substr(id, 1, 4) = 'svc_'
                        AND id = lower(id)
                        AND substr(id, 5) NOT GLOB '*[^0-9a-f]*'
                    ),
                service_key TEXT NOT NULL UNIQUE CHECK (length(service_key) > 0),
                package_id TEXT NOT NULL CHECK (length(package_id) > 0),
                package_version TEXT NOT NULL CHECK (length(package_version) > 0),
                display_name TEXT NOT NULL CHECK (length(display_name) > 0),
                runtime_mode TEXT NOT NULL
                    CHECK (runtime_mode IN ('in_process', 'external')),
                source TEXT NOT NULL
                    CHECK (source IN ('builtin', 'local', 'installed')),
                status TEXT NOT NULL DEFAULT 'enabled'
                    CHECK (status IN ('enabled', 'disabled')),
                capabilities_json TEXT NOT NULL DEFAULT '[]'
                    CHECK (
                        json_valid(capabilities_json)
                        AND json_type(capabilities_json) = 'array'
                    ),
                config_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(config_json)),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                updated_at TEXT NOT NULL
                    CHECK (length(updated_at) = 27 AND substr(updated_at, -1) = 'Z'),
                UNIQUE (package_id, package_version)
            )
            """,
            """
            CREATE TABLE service_dependencies (
                service_id TEXT NOT NULL,
                dependency_key TEXT NOT NULL CHECK (length(dependency_key) > 0),
                version_spec TEXT NOT NULL DEFAULT '*' CHECK (length(version_spec) > 0),
                optional INTEGER NOT NULL DEFAULT 0 CHECK (optional IN (0, 1)),
                PRIMARY KEY (service_id, dependency_key),
                FOREIGN KEY (service_id)
                    REFERENCES service_descriptors(id) ON DELETE CASCADE,
                CHECK (dependency_key != '')
            )
            """,
            """
            CREATE TABLE service_instances (
                id TEXT PRIMARY KEY
                    CHECK (
                        length(id) = 37 AND substr(id, 1, 5) = 'svci_'
                        AND id = lower(id)
                        AND substr(id, 6) NOT GLOB '*[^0-9a-f]*'
                    ),
                service_id TEXT NOT NULL,
                provider_key TEXT NOT NULL UNIQUE CHECK (length(provider_key) > 0),
                status TEXT NOT NULL DEFAULT 'installed'
                    CHECK (status IN (
                        'installed', 'disabled', 'starting', 'running',
                        'degraded', 'stopping', 'stopped', 'restarting', 'failed'
                    )),
                endpoint TEXT,
                health_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(health_json)),
                last_error TEXT,
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                updated_at TEXT NOT NULL
                    CHECK (length(updated_at) = 27 AND substr(updated_at, -1) = 'Z'),
                FOREIGN KEY (service_id)
                    REFERENCES service_descriptors(id) ON DELETE RESTRICT
            )
            """,
            """
            CREATE INDEX idx_service_instances_service_status
            ON service_instances(service_id, status)
            """,
            """
            CREATE TABLE tool_descriptors (
                id TEXT PRIMARY KEY
                    CHECK (
                        length(id) = 37 AND substr(id, 1, 5) = 'tool_'
                        AND id = lower(id)
                        AND substr(id, 6) NOT GLOB '*[^0-9a-f]*'
                    ),
                service_id TEXT NOT NULL,
                qualified_name TEXT NOT NULL UNIQUE
                    CHECK (length(qualified_name) > 0),
                display_name TEXT NOT NULL CHECK (length(display_name) > 0),
                description TEXT NOT NULL DEFAULT '',
                input_schema_json TEXT NOT NULL
                    CHECK (json_valid(input_schema_json)),
                output_schema_json TEXT NOT NULL
                    CHECK (json_valid(output_schema_json)),
                effects_json TEXT NOT NULL DEFAULT '[]'
                    CHECK (
                        json_valid(effects_json)
                        AND json_type(effects_json) = 'array'
                    ),
                required_capabilities_json TEXT NOT NULL DEFAULT '[]'
                    CHECK (
                        json_valid(required_capabilities_json)
                        AND json_type(required_capabilities_json) = 'array'
                    ),
                timeout_ms INTEGER NOT NULL DEFAULT 30000 CHECK (timeout_ms > 0),
                enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                updated_at TEXT NOT NULL
                    CHECK (length(updated_at) = 27 AND substr(updated_at, -1) = 'Z'),
                FOREIGN KEY (service_id)
                    REFERENCES service_descriptors(id) ON DELETE RESTRICT
            )
            """,
            """
            CREATE INDEX idx_tools_service_enabled
            ON tool_descriptors(service_id, enabled, qualified_name)
            """,
        ),
    ),
    Migration(
        version=7,
        name="asynchronous_agent_runtime",
        statements=(
            """
            CREATE TABLE agent_concurrency_groups (
                group_key TEXT PRIMARY KEY CHECK (length(group_key) > 0),
                concurrency_limit INTEGER NOT NULL CHECK (concurrency_limit > 0),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                updated_at TEXT NOT NULL
                    CHECK (length(updated_at) = 27 AND substr(updated_at, -1) = 'Z')
            )
            """,
            """
            CREATE TABLE agent_definitions (
                id TEXT PRIMARY KEY
                    CHECK (
                        length(id) = 36 AND substr(id, 1, 4) = 'agt_'
                        AND id = lower(id)
                        AND substr(id, 5) NOT GLOB '*[^0-9a-f]*'
                    ),
                agent_key TEXT NOT NULL UNIQUE CHECK (length(agent_key) > 0),
                package_version TEXT NOT NULL CHECK (length(package_version) > 0),
                display_name TEXT NOT NULL CHECK (length(display_name) > 0),
                description TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL
                    CHECK (source IN ('builtin', 'local', 'installed')),
                status TEXT NOT NULL DEFAULT 'enabled'
                    CHECK (status IN ('enabled', 'disabled')),
                executor_key TEXT NOT NULL CHECK (length(executor_key) > 0),
                concurrency_group TEXT,
                resume_policy TEXT NOT NULL DEFAULT 'restart'
                    CHECK (resume_policy IN ('restart', 'fail')),
                max_steps INTEGER NOT NULL DEFAULT 20 CHECK (max_steps > 0),
                timeout_seconds INTEGER NOT NULL DEFAULT 300
                    CHECK (timeout_seconds > 0),
                manifest_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(manifest_json)),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                updated_at TEXT NOT NULL
                    CHECK (length(updated_at) = 27 AND substr(updated_at, -1) = 'Z'),
                FOREIGN KEY (concurrency_group)
                    REFERENCES agent_concurrency_groups(group_key) ON DELETE RESTRICT
            )
            """,
            """
            CREATE TABLE agent_runs (
                id TEXT PRIMARY KEY
                    CHECK (
                        length(id) = 36 AND substr(id, 1, 4) = 'run_'
                        AND id = lower(id)
                        AND substr(id, 5) NOT GLOB '*[^0-9a-f]*'
                    ),
                agent_definition_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN (
                        'queued', 'planning', 'running', 'waiting_input',
                        'waiting_capability', 'interrupted', 'completed',
                        'failed', 'cancelled'
                    )),
                idempotency_key TEXT,
                priority INTEGER NOT NULL DEFAULT 0,
                input_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(input_json)),
                output_json TEXT CHECK (output_json IS NULL OR json_valid(output_json)),
                error_json TEXT CHECK (error_json IS NULL OR json_valid(error_json)),
                granted_capabilities_json TEXT NOT NULL DEFAULT '[]'
                    CHECK (
                        json_valid(granted_capabilities_json)
                        AND json_type(granted_capabilities_json) = 'array'
                    ),
                current_step INTEGER NOT NULL DEFAULT 0 CHECK (current_step >= 0),
                cancel_requested INTEGER NOT NULL DEFAULT 0
                    CHECK (cancel_requested IN (0, 1)),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                deadline_at TEXT NOT NULL
                    CHECK (length(deadline_at) = 27 AND substr(deadline_at, -1) = 'Z'),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                updated_at TEXT NOT NULL
                    CHECK (length(updated_at) = 27 AND substr(updated_at, -1) = 'Z'),
                started_at TEXT
                    CHECK (
                        started_at IS NULL OR
                        (length(started_at) = 27 AND substr(started_at, -1) = 'Z')
                    ),
                finished_at TEXT
                    CHECK (
                        finished_at IS NULL OR
                        (length(finished_at) = 27 AND substr(finished_at, -1) = 'Z')
                    ),
                FOREIGN KEY (agent_definition_id)
                    REFERENCES agent_definitions(id) ON DELETE RESTRICT,
                FOREIGN KEY (session_id)
                    REFERENCES sessions(id) ON DELETE RESTRICT
            )
            """,
            """
            CREATE UNIQUE INDEX uq_agent_runs_session_idempotency
            ON agent_runs(session_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL
            """,
            """
            CREATE INDEX idx_agent_runs_dispatch
            ON agent_runs(status, priority DESC, created_at, id)
            """,
            """
            CREATE INDEX idx_agent_runs_session_created
            ON agent_runs(session_id, created_at DESC)
            """,
            """
            CREATE TABLE agent_status_lines (
                id TEXT PRIMARY KEY
                    CHECK (
                        length(id) = 36 AND substr(id, 1, 4) = 'stl_'
                        AND id = lower(id)
                        AND substr(id, 5) NOT GLOB '*[^0-9a-f]*'
                    ),
                run_id TEXT NOT NULL,
                status_key TEXT NOT NULL DEFAULT 'primary',
                phase TEXT NOT NULL CHECK (length(phase) > 0),
                text TEXT NOT NULL,
                presentation TEXT NOT NULL DEFAULT 'plain'
                    CHECK (presentation IN (
                        'plain', 'pulse', 'progress', 'indeterminate',
                        'warning', 'error', 'safe_html', 'sandbox_html'
                    )),
                progress REAL CHECK (progress IS NULL OR (progress >= 0 AND progress <= 1)),
                content_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(content_json)),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                updated_at TEXT NOT NULL
                    CHECK (length(updated_at) = 27 AND substr(updated_at, -1) = 'Z'),
                FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
                UNIQUE (run_id, status_key)
            )
            """,
            """
            CREATE TABLE run_steps (
                id TEXT PRIMARY KEY
                    CHECK (
                        length(id) = 37 AND substr(id, 1, 5) = 'step_'
                        AND id = lower(id)
                        AND substr(id, 6) NOT GLOB '*[^0-9a-f]*'
                    ),
                run_id TEXT NOT NULL,
                sequence INTEGER NOT NULL CHECK (sequence > 0),
                action_key TEXT NOT NULL CHECK (length(action_key) > 0),
                kind TEXT NOT NULL
                    CHECK (kind IN ('model', 'tool', 'interaction', 'internal')),
                status TEXT NOT NULL
                    CHECK (status IN (
                        'pending', 'running', 'completed', 'failed',
                        'cancelled', 'uncertain'
                    )),
                tool_name TEXT,
                input_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(input_json)),
                output_json TEXT CHECK (output_json IS NULL OR json_valid(output_json)),
                error_json TEXT CHECK (error_json IS NULL OR json_valid(error_json)),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                started_at TEXT,
                finished_at TEXT,
                FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
                UNIQUE (run_id, sequence),
                UNIQUE (run_id, action_key)
            )
            """,
            """
            CREATE TABLE agent_interactions (
                id TEXT PRIMARY KEY
                    CHECK (
                        length(id) = 36 AND substr(id, 1, 4) = 'int_'
                        AND id = lower(id)
                        AND substr(id, 5) NOT GLOB '*[^0-9a-f]*'
                    ),
                run_id TEXT NOT NULL,
                request_key TEXT NOT NULL CHECK (length(request_key) > 0),
                kind TEXT NOT NULL
                    CHECK (kind IN ('text', 'menu', 'file', 'form', 'approval')),
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN (
                        'pending', 'submitted', 'approved', 'denied',
                        'expired', 'cancelled'
                    )),
                prompt TEXT NOT NULL,
                response_schema_json TEXT NOT NULL
                    CHECK (json_valid(response_schema_json)),
                ui_hints_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(ui_hints_json)),
                request_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(request_json)),
                response_json TEXT CHECK (response_json IS NULL OR json_valid(response_json)),
                response_id TEXT,
                deadline_at TEXT NOT NULL
                    CHECK (length(deadline_at) = 27 AND substr(deadline_at, -1) = 'Z'),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z'),
                updated_at TEXT NOT NULL
                    CHECK (length(updated_at) = 27 AND substr(updated_at, -1) = 'Z'),
                resolved_at TEXT,
                FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
                UNIQUE (run_id, request_key),
                UNIQUE (run_id, response_id)
            )
            """,
            """
            CREATE UNIQUE INDEX uq_agent_interactions_one_pending
            ON agent_interactions(run_id) WHERE status = 'pending'
            """,
            """
            CREATE TRIGGER agent_run_status_transition
            BEFORE UPDATE OF status ON agent_runs
            WHEN NEW.status != OLD.status AND NOT (
                (OLD.status = 'queued' AND NEW.status IN ('planning', 'cancelled')) OR
                (OLD.status = 'planning' AND NEW.status IN (
                    'running', 'queued', 'failed', 'cancelled'
                )) OR
                (OLD.status = 'running' AND NEW.status IN (
                    'queued', 'waiting_input', 'waiting_capability',
                    'interrupted', 'completed', 'failed', 'cancelled'
                )) OR
                (OLD.status IN ('waiting_input', 'waiting_capability')
                    AND NEW.status IN ('queued', 'failed', 'cancelled')) OR
                (OLD.status = 'interrupted'
                    AND NEW.status IN ('queued', 'failed', 'cancelled'))
            )
            BEGIN
                SELECT RAISE(ABORT, 'invalid AgentRun status transition');
            END
            """,
        ),
    ),
    Migration(
        version=8,
        name="capability_policy_and_grant_leases",
        statements=(
            """
            CREATE TABLE capability_policies (
                id TEXT PRIMARY KEY,
                policy_key TEXT NOT NULL UNIQUE,
                effect TEXT NOT NULL
                    CHECK (effect IN ('allow', 'deny', 'require_approval')),
                capability_pattern TEXT NOT NULL,
                agent_pattern TEXT NOT NULL DEFAULT '*',
                tool_pattern TEXT NOT NULL DEFAULT '*',
                priority INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                source TEXT NOT NULL DEFAULT 'local'
                    CHECK (source IN ('builtin', 'local', 'installed', 'ai_auditor')),
                conditions_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(conditions_json)),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX idx_capability_policies_evaluate
            ON capability_policies(enabled, priority DESC)
            """,
            """
            CREATE TABLE grant_leases (
                id TEXT PRIMARY KEY,
                scope TEXT NOT NULL
                    CHECK (scope IN ('run', 'session', 'agent', 'app')),
                scope_id TEXT NOT NULL,
                agent_definition_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                app_instance_id TEXT NOT NULL,
                capabilities_json TEXT NOT NULL
                    CHECK (json_valid(capabilities_json)
                           AND json_type(capabilities_json) = 'array'),
                tool_pattern TEXT NOT NULL DEFAULT '*',
                resource_selector_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(resource_selector_json)),
                issued_by TEXT NOT NULL,
                evidence_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(evidence_json)),
                expires_at TEXT,
                revoked_at TEXT,
                revoke_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (agent_definition_id)
                    REFERENCES agent_definitions(id) ON DELETE RESTRICT,
                FOREIGN KEY (session_id)
                    REFERENCES sessions(id) ON DELETE RESTRICT,
                FOREIGN KEY (app_instance_id)
                    REFERENCES app_instances(id) ON DELETE RESTRICT
            )
            """,
            """
            CREATE INDEX idx_grant_leases_active_scope
            ON grant_leases(scope, scope_id, revoked_at, expires_at)
            """,
            """
            CREATE TABLE capability_decisions (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                interaction_id TEXT,
                decision TEXT NOT NULL
                    CHECK (decision IN ('allow', 'deny', 'require_approval')),
                decision_source TEXT NOT NULL,
                capabilities_json TEXT NOT NULL
                    CHECK (json_valid(capabilities_json)),
                tool_name TEXT NOT NULL,
                effects_json TEXT NOT NULL CHECK (json_valid(effects_json)),
                matched_policy_ids_json TEXT NOT NULL DEFAULT '[]'
                    CHECK (json_valid(matched_policy_ids_json)),
                evidence_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(evidence_json)),
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
                FOREIGN KEY (interaction_id)
                    REFERENCES agent_interactions(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE INDEX idx_capability_decisions_run
            ON capability_decisions(run_id, created_at)
            """,
        ),
    ),
    Migration(
        version=9,
        name="workspace_resources_and_artifacts",
        statements=(
            """
            CREATE TABLE session_sandboxes (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL UNIQUE,
                quota_bytes INTEGER NOT NULL CHECK (quota_bytes > 0),
                used_bytes INTEGER NOT NULL DEFAULT 0 CHECK (used_bytes >= 0),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE artifacts (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                run_id TEXT,
                name TEXT NOT NULL,
                media_type TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                storage_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'trashed')),
                metadata_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(metadata_json)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE RESTRICT,
                FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE SET NULL,
                UNIQUE (session_id, content_hash, name)
            )
            """,
            """
            CREATE INDEX idx_artifacts_session
            ON artifacts(session_id, status, created_at DESC)
            """,
            """
            CREATE TABLE resource_handles (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                artifact_id TEXT,
                kind TEXT NOT NULL CHECK (kind IN ('file', 'directory', 'artifact')),
                display_name TEXT NOT NULL,
                locator_kind TEXT NOT NULL
                    CHECK (locator_kind IN ('workspace', 'artifact', 'external')),
                locator TEXT NOT NULL,
                capabilities_json TEXT NOT NULL CHECK (json_valid(capabilities_json)),
                media_type TEXT,
                size_bytes INTEGER,
                content_hash TEXT,
                source TEXT NOT NULL,
                expires_at TEXT,
                revoked_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (artifact_id) REFERENCES artifacts(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE INDEX idx_resource_handles_session
            ON resource_handles(session_id, revoked_at, expires_at)
            """,
            """
            CREATE TABLE artifact_exports (
                id TEXT PRIMARY KEY,
                artifact_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                destination_handle_id TEXT NOT NULL,
                destination_name TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK (status IN ('pending', 'completed', 'failed')),
                content_hash TEXT,
                error_json TEXT CHECK (error_json IS NULL OR json_valid(error_json)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (artifact_id) REFERENCES artifacts(id) ON DELETE RESTRICT,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE RESTRICT,
                FOREIGN KEY (destination_handle_id)
                    REFERENCES resource_handles(id) ON DELETE RESTRICT
            )
            """,
            """
            CREATE INDEX idx_artifact_exports_session
            ON artifact_exports(session_id, created_at DESC)
            """,
        ),
    ),
    Migration(
        version=10,
        name="sandboxed_process_service",
        statements=(
            """
            ALTER TABLE tool_descriptors ADD COLUMN capability_rules_json TEXT
                NOT NULL DEFAULT '[]' CHECK (json_valid(capability_rules_json))
            """,
            """
            CREATE TABLE process_executions (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                run_id TEXT,
                caller_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN (
                    'starting', 'running', 'exited', 'failed', 'cancelled',
                    'timed_out', 'idle_timeout', 'output_limit', 'orphaned'
                )),
                argv_json TEXT NOT NULL CHECK (json_valid(argv_json)),
                cwd TEXT NOT NULL,
                environment_keys_json TEXT NOT NULL CHECK (json_valid(environment_keys_json)),
                sandbox_backend TEXT NOT NULL,
                network_enabled INTEGER NOT NULL DEFAULT 0
                    CHECK (network_enabled IN (0, 1)),
                pid INTEGER,
                exit_code INTEGER,
                limits_json TEXT NOT NULL CHECK (json_valid(limits_json)),
                stdin_open INTEGER NOT NULL DEFAULT 1 CHECK (stdin_open IN (0, 1)),
                output_bytes INTEGER NOT NULL DEFAULT 0 CHECK (output_bytes >= 0),
                last_activity_at TEXT NOT NULL,
                error_json TEXT CHECK (error_json IS NULL OR json_valid(error_json)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE RESTRICT,
                FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE INDEX idx_process_executions_session
            ON process_executions(session_id, status, created_at DESC)
            """,
            """
            CREATE INDEX idx_process_executions_run
            ON process_executions(run_id, status)
            """,
            """
            CREATE TABLE process_log_chunks (
                id TEXT PRIMARY KEY,
                process_id TEXT NOT NULL,
                sequence INTEGER NOT NULL CHECK (sequence >= 1),
                stream TEXT NOT NULL CHECK (stream IN ('stdout', 'stderr', 'system')),
                encoding TEXT NOT NULL CHECK (encoding IN ('utf-8', 'base64')),
                content TEXT NOT NULL,
                byte_count INTEGER NOT NULL CHECK (byte_count >= 0),
                created_at TEXT NOT NULL,
                FOREIGN KEY (process_id)
                    REFERENCES process_executions(id) ON DELETE CASCADE,
                UNIQUE (process_id, sequence)
            )
            """,
            """
            CREATE TABLE host_broker_requests (
                id TEXT PRIMARY KEY,
                process_id TEXT,
                session_id TEXT NOT NULL,
                run_id TEXT,
                operation TEXT NOT NULL,
                nonce TEXT NOT NULL UNIQUE,
                token_digest TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK (status IN ('issued', 'accepted', 'denied', 'expired')),
                expires_at TEXT NOT NULL,
                evidence_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(evidence_json)),
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                FOREIGN KEY (process_id)
                    REFERENCES process_executions(id) ON DELETE SET NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE RESTRICT,
                FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE INDEX idx_host_broker_requests_session
            ON host_broker_requests(session_id, created_at DESC)
            """,
        ),
    ),
    Migration(
        version=11,
        name="trusted_service_packages",
        statements=(
            """
            ALTER TABLE grant_leases ADD COLUMN tool_service_digest TEXT
            """,
            """
            ALTER TABLE service_descriptors ADD COLUMN execution_mode TEXT
                NOT NULL DEFAULT 'in_process'
                CHECK (execution_mode IN ('in_process', 'managed_process', 'external'))
            """,
            """
            UPDATE service_descriptors SET execution_mode = runtime_mode
            """,
            """
            ALTER TABLE service_descriptors ADD COLUMN active_package_digest TEXT
            """,
            """
            ALTER TABLE service_descriptors ADD COLUMN permissions_json TEXT
                NOT NULL DEFAULT '{}' CHECK (json_valid(permissions_json))
            """,
            """
            CREATE TABLE publisher_trust (
                id TEXT PRIMARY KEY,
                publisher_key TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                key_id TEXT NOT NULL,
                algorithm TEXT NOT NULL CHECK (algorithm = 'ed25519'),
                public_key TEXT NOT NULL,
                trust_status TEXT NOT NULL
                    CHECK (trust_status IN ('trusted', 'untrusted', 'revoked')),
                source TEXT NOT NULL CHECK (source IN ('builtin', 'user', 'organization')),
                metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                revoked_at TEXT
            )
            """,
            """
            CREATE TABLE service_packages (
                id TEXT PRIMARY KEY,
                service_key TEXT NOT NULL,
                package_version TEXT NOT NULL,
                package_digest TEXT NOT NULL UNIQUE,
                publisher_key TEXT NOT NULL,
                runtime_mode TEXT NOT NULL
                    CHECK (runtime_mode IN ('in_process', 'managed_process', 'external')),
                protocol TEXT NOT NULL,
                entrypoint TEXT,
                archive_path TEXT NOT NULL,
                store_path TEXT NOT NULL,
                manifest_json TEXT NOT NULL CHECK (json_valid(manifest_json)),
                permissions_json TEXT NOT NULL CHECK (json_valid(permissions_json)),
                compatibility_json TEXT NOT NULL CHECK (json_valid(compatibility_json)),
                sbom_json TEXT NOT NULL CHECK (json_valid(sbom_json)),
                verification_json TEXT NOT NULL CHECK (json_valid(verification_json)),
                status TEXT NOT NULL CHECK (status IN (
                    'installed', 'active', 'retained', 'rejected', 'uninstalled'
                )),
                installed_at TEXT NOT NULL,
                activated_at TEXT,
                retired_at TEXT,
                FOREIGN KEY (publisher_key)
                    REFERENCES publisher_trust(publisher_key) ON DELETE RESTRICT,
                UNIQUE (service_key, package_version)
            )
            """,
            """
            CREATE INDEX idx_service_packages_active
            ON service_packages(service_key, status, installed_at DESC)
            """,
            """
            CREATE TABLE service_package_files (
                package_id TEXT NOT NULL,
                path TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                media_type TEXT,
                PRIMARY KEY (package_id, path),
                FOREIGN KEY (package_id) REFERENCES service_packages(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE package_attestations (
                id TEXT PRIMARY KEY,
                package_digest TEXT NOT NULL,
                kind TEXT NOT NULL,
                issuer TEXT NOT NULL,
                decision TEXT NOT NULL CHECK (decision IN ('pass', 'review', 'reject')),
                risk TEXT NOT NULL CHECK (risk IN ('low', 'medium', 'high', 'critical')),
                model TEXT,
                policy_version TEXT,
                evidence_json TEXT NOT NULL CHECK (json_valid(evidence_json)),
                signature_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(signature_json)),
                created_at TEXT NOT NULL,
                FOREIGN KEY (package_digest)
                    REFERENCES service_packages(package_digest) ON DELETE CASCADE
            )
            """,
            """
            CREATE INDEX idx_package_attestations_digest
            ON package_attestations(package_digest, kind, created_at DESC)
            """,
            """
            CREATE TABLE service_dependency_locks (
                service_key TEXT NOT NULL,
                package_digest TEXT NOT NULL,
                dependency_key TEXT NOT NULL,
                dependency_version TEXT NOT NULL,
                dependency_digest TEXT NOT NULL,
                optional INTEGER NOT NULL DEFAULT 0 CHECK (optional IN (0, 1)),
                created_at TEXT NOT NULL,
                PRIMARY KEY (service_key, package_digest, dependency_key),
                FOREIGN KEY (package_digest)
                    REFERENCES service_packages(package_digest) ON DELETE CASCADE,
                FOREIGN KEY (dependency_digest)
                    REFERENCES service_packages(package_digest) ON DELETE RESTRICT
            )
            """,
            """
            CREATE TABLE service_operations (
                id TEXT PRIMARY KEY,
                service_key TEXT NOT NULL,
                operation TEXT NOT NULL CHECK (operation IN (
                    'install', 'upgrade', 'rollback', 'uninstall', 'enable',
                    'disable', 'start', 'stop', 'restart', 'audit'
                )),
                status TEXT NOT NULL CHECK (status IN (
                    'pending', 'running', 'completed', 'failed', 'rolled_back'
                )),
                from_digest TEXT,
                to_digest TEXT,
                plan_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(plan_json)),
                error_json TEXT CHECK (error_json IS NULL OR json_valid(error_json)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            )
            """,
            """
            CREATE INDEX idx_service_operations_service
            ON service_operations(service_key, created_at DESC)
            """,
            """
            CREATE TABLE service_logs (
                id TEXT PRIMARY KEY,
                service_key TEXT NOT NULL,
                process_id TEXT,
                sequence INTEGER NOT NULL CHECK (sequence >= 1),
                level TEXT NOT NULL CHECK (level IN (
                    'trace', 'debug', 'info', 'warning', 'error', 'critical'
                )),
                stream TEXT NOT NULL CHECK (stream IN ('stdout', 'stderr', 'system')),
                message TEXT NOT NULL,
                fields_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(fields_json)),
                created_at TEXT NOT NULL,
                UNIQUE (service_key, sequence)
            )
            """,
            """
            CREATE TABLE managed_service_processes (
                id TEXT PRIMARY KEY,
                service_key TEXT NOT NULL,
                package_digest TEXT NOT NULL,
                pid INTEGER,
                status TEXT NOT NULL CHECK (status IN (
                    'starting', 'running', 'stopping', 'stopped', 'failed', 'orphaned'
                )),
                endpoint TEXT,
                restart_count INTEGER NOT NULL DEFAULT 0 CHECK (restart_count >= 0),
                started_at TEXT,
                stopped_at TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (package_digest)
                    REFERENCES service_packages(package_digest) ON DELETE RESTRICT
            )
            """,
            """
            CREATE INDEX idx_managed_service_processes_service
            ON managed_service_processes(service_key, status, created_at DESC)
            """,
        ),
    ),
    Migration(
        version=12,
        name="installable_agents_apps_and_local_patches",
        statements=(
            "ALTER TABLE agent_definitions ADD COLUMN upstream_digest TEXT",
            "ALTER TABLE agent_definitions ADD COLUMN effective_digest TEXT",
            "ALTER TABLE app_definitions ADD COLUMN upstream_digest TEXT",
            "ALTER TABLE app_definitions ADD COLUMN effective_digest TEXT",
            """
            CREATE TABLE interactive_packages (
                id TEXT PRIMARY KEY,
                package_kind TEXT NOT NULL CHECK (package_kind IN ('agent', 'app')),
                unit_key TEXT NOT NULL,
                package_version TEXT NOT NULL,
                package_digest TEXT NOT NULL UNIQUE,
                publisher_key TEXT NOT NULL,
                archive_path TEXT NOT NULL,
                store_path TEXT NOT NULL,
                manifest_json TEXT NOT NULL CHECK (json_valid(manifest_json)),
                file_index_json TEXT NOT NULL CHECK (json_valid(file_index_json)),
                sbom_json TEXT NOT NULL CHECK (json_valid(sbom_json)),
                verification_json TEXT NOT NULL CHECK (json_valid(verification_json)),
                status TEXT NOT NULL CHECK (
                    status IN ('installed', 'active', 'retained', 'conflicted', 'uninstalled')
                ),
                installed_at TEXT NOT NULL,
                activated_at TEXT,
                retired_at TEXT,
                UNIQUE(package_kind, unit_key, package_version, package_digest)
            )
            """,
            """
            CREATE INDEX idx_interactive_packages_active
            ON interactive_packages(package_kind, unit_key, status)
            """,
            """
            CREATE TABLE local_patches (
                id TEXT PRIMARY KEY,
                target_kind TEXT NOT NULL CHECK (target_kind IN ('agent', 'app')),
                target_key TEXT NOT NULL,
                patch_version TEXT NOT NULL,
                patch_digest TEXT NOT NULL UNIQUE,
                base_digest TEXT NOT NULL,
                intent TEXT NOT NULL,
                rebase_policy TEXT NOT NULL CHECK (
                    rebase_policy IN ('strict', 'preserve-local', 'ai-assisted', 'drop-if-satisfied')
                ),
                operations_json TEXT NOT NULL CHECK (json_valid(operations_json)),
                resources_json TEXT NOT NULL CHECK (json_valid(resources_json)),
                tests_json TEXT NOT NULL CHECK (json_valid(tests_json)),
                audit_json TEXT NOT NULL CHECK (json_valid(audit_json)),
                signature_json TEXT NOT NULL CHECK (json_valid(signature_json)),
                stack_order INTEGER NOT NULL CHECK (stack_order >= 0),
                status TEXT NOT NULL CHECK (
                    status IN ('clean', 'rebased', 'needs-review', 'conflicted',
                               'disabled', 'superseded', 'failed-tests')
                ),
                conflict_json TEXT CHECK (conflict_json IS NULL OR json_valid(conflict_json)),
                archive_path TEXT NOT NULL,
                store_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(target_kind, target_key, stack_order)
            )
            """,
            """
            CREATE TABLE effective_definitions (
                id TEXT PRIMARY KEY,
                unit_kind TEXT NOT NULL CHECK (unit_kind IN ('agent', 'app')),
                unit_key TEXT NOT NULL,
                upstream_digest TEXT NOT NULL,
                patch_set_digest TEXT NOT NULL,
                effective_digest TEXT NOT NULL UNIQUE,
                effective_version TEXT NOT NULL,
                manifest_json TEXT NOT NULL CHECK (json_valid(manifest_json)),
                resources_json TEXT NOT NULL CHECK (json_valid(resources_json)),
                audit_json TEXT NOT NULL CHECK (json_valid(audit_json)),
                status TEXT NOT NULL CHECK (status IN ('candidate', 'active', 'retained', 'conflicted')),
                revision INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                activated_at TEXT,
                retired_at TEXT
            )
            """,
            """
            CREATE UNIQUE INDEX uq_effective_definition_active
            ON effective_definitions(unit_kind, unit_key) WHERE status = 'active'
            """,
            """
            CREATE TABLE app_mounts (
                id TEXT PRIMARY KEY,
                app_instance_id TEXT NOT NULL,
                interaction_session_id TEXT,
                placement TEXT NOT NULL CHECK (placement IN ('entry', 'inline', 'sidebar')),
                renderer TEXT NOT NULL CHECK (renderer IN ('host', 'schema', 'safe-html', 'sandbox')),
                resource TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('mounted', 'unmounted')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(app_instance_id) REFERENCES app_instances(id) ON DELETE RESTRICT,
                FOREIGN KEY(interaction_session_id) REFERENCES sessions(id) ON DELETE RESTRICT
            )
            """,
            """
            CREATE TABLE app_state_snapshots (
                id TEXT PRIMARY KEY,
                app_instance_id TEXT NOT NULL,
                effective_digest TEXT NOT NULL,
                state_schema_version INTEGER NOT NULL,
                state_json TEXT NOT NULL CHECK (json_valid(state_json)),
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(app_instance_id) REFERENCES app_instances(id) ON DELETE RESTRICT
            )
            """,
            """
            CREATE TABLE interactive_operations (
                id TEXT PRIMARY KEY,
                unit_kind TEXT NOT NULL CHECK (unit_kind IN ('agent', 'app')),
                unit_key TEXT NOT NULL,
                operation TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'rolled_back')),
                detail_json TEXT NOT NULL CHECK (json_valid(detail_json)),
                created_at TEXT NOT NULL,
                finished_at TEXT
            )
            """,
            "CREATE INDEX idx_app_mounts_instance ON app_mounts(app_instance_id, status)",
            "CREATE INDEX idx_app_snapshots_instance ON app_state_snapshots(app_instance_id, created_at DESC)",
            """
            CREATE TABLE safe_mode_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                active INTEGER NOT NULL CHECK (active IN (0,1)),
                reason TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE safe_mode_patch_states (
                patch_id TEXT PRIMARY KEY,
                prior_status TEXT NOT NULL,
                FOREIGN KEY(patch_id) REFERENCES local_patches(id) ON DELETE CASCADE
            )
            """,
        ),
    ),
    Migration(
        version=13,
        name="app_mount_context",
        statements=(
            """
            ALTER TABLE app_mounts
            ADD COLUMN context_json TEXT NOT NULL DEFAULT '{}'
                CHECK (json_valid(context_json))
            """,
            """
            CREATE INDEX idx_app_mounts_interaction
            ON app_mounts(interaction_session_id, status, created_at)
            """,
        ),
    ),
    Migration(
        version=14,
        name="unified_capability_requests",
        statements=(
            """
            CREATE TABLE capability_requests (
                id TEXT PRIMARY KEY,
                subject_kind TEXT NOT NULL CHECK (subject_kind IN ('app', 'agent_run')),
                app_instance_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                run_id TEXT,
                capabilities_json TEXT NOT NULL CHECK (
                    json_valid(capabilities_json)
                    AND json_type(capabilities_json) = 'array'
                ),
                tool_name TEXT NOT NULL DEFAULT '*',
                effects_json TEXT NOT NULL DEFAULT '[]' CHECK (
                    json_valid(effects_json)
                    AND json_type(effects_json) = 'array'
                ),
                resource_selector_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(resource_selector_json)),
                reason TEXT NOT NULL,
                risk_level TEXT NOT NULL CHECK (
                    risk_level IN ('low', 'medium', 'high', 'critical')
                ),
                status TEXT NOT NULL DEFAULT 'pending' CHECK (
                    status IN ('pending', 'approved', 'denied', 'cancelled', 'expired')
                ),
                requested_by TEXT NOT NULL,
                decision_scope TEXT CHECK (
                    decision_scope IS NULL
                    OR decision_scope IN ('once', 'run', 'session', 'agent', 'app')
                ),
                decision_evidence_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(decision_evidence_json)),
                grant_lease_id TEXT,
                deadline_at TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                resolved_at TEXT,
                FOREIGN KEY (app_instance_id)
                    REFERENCES app_instances(id) ON DELETE RESTRICT,
                FOREIGN KEY (session_id)
                    REFERENCES sessions(id) ON DELETE RESTRICT,
                FOREIGN KEY (run_id)
                    REFERENCES agent_runs(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE INDEX idx_capability_requests_pending
            ON capability_requests(status, created_at)
            """,
            """
            CREATE INDEX idx_capability_requests_app
            ON capability_requests(app_instance_id, status, created_at)
            """,
            """
            ALTER TABLE grant_leases RENAME TO grant_leases_v13
            """,
            """
            CREATE TABLE grant_leases (
                id TEXT PRIMARY KEY,
                scope TEXT NOT NULL
                    CHECK (scope IN ('run', 'session', 'agent', 'app')),
                scope_id TEXT NOT NULL,
                agent_definition_id TEXT,
                session_id TEXT NOT NULL,
                app_instance_id TEXT NOT NULL,
                capabilities_json TEXT NOT NULL
                    CHECK (json_valid(capabilities_json)
                           AND json_type(capabilities_json) = 'array'),
                tool_pattern TEXT NOT NULL DEFAULT '*',
                tool_service_digest TEXT,
                resource_selector_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(resource_selector_json)),
                issued_by TEXT NOT NULL,
                evidence_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(evidence_json)),
                request_id TEXT,
                expires_at TEXT,
                revoked_at TEXT,
                revoke_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (agent_definition_id)
                    REFERENCES agent_definitions(id) ON DELETE RESTRICT,
                FOREIGN KEY (session_id)
                    REFERENCES sessions(id) ON DELETE RESTRICT,
                FOREIGN KEY (app_instance_id)
                    REFERENCES app_instances(id) ON DELETE RESTRICT,
                FOREIGN KEY (request_id)
                    REFERENCES capability_requests(id) ON DELETE SET NULL
            )
            """,
            """
            INSERT INTO grant_leases(
                id, scope, scope_id, agent_definition_id, session_id,
                app_instance_id, capabilities_json, tool_pattern,
                tool_service_digest, resource_selector_json, issued_by,
                evidence_json, expires_at, revoked_at, revoke_reason,
                created_at, updated_at
            )
            SELECT id, scope, scope_id, agent_definition_id, session_id,
                app_instance_id, capabilities_json, tool_pattern,
                tool_service_digest, resource_selector_json, issued_by,
                evidence_json, expires_at, revoked_at, revoke_reason,
                created_at, updated_at
            FROM grant_leases_v13
            """,
            "DROP TABLE grant_leases_v13",
            """
            CREATE INDEX idx_grant_leases_active_scope
            ON grant_leases(scope, scope_id, revoked_at, expires_at)
            """,
        ),
    ),
    Migration(
        version=15,
        name="durable_tool_invocations",
        statements=(
            """
            ALTER TABLE tool_descriptors
            ADD COLUMN retry_policy_json TEXT NOT NULL
                DEFAULT '{"max_attempts":1,"backoff_ms":0,"retry_codes":[]}'
                CHECK (json_valid(retry_policy_json))
            """,
            """
            CREATE TABLE tool_invocations (
                id TEXT PRIMARY KEY CHECK (
                    length(id) = 37 AND substr(id, 1, 5) = 'tinv_'
                    AND id = lower(id)
                    AND substr(id, 6) NOT GLOB '*[^0-9a-f]*'
                ),
                tool_id TEXT NOT NULL,
                qualified_name TEXT NOT NULL,
                provider_key TEXT NOT NULL,
                caller_id TEXT NOT NULL,
                session_id TEXT,
                trace_id TEXT,
                status TEXT NOT NULL CHECK (
                    status IN (
                        'running', 'completed', 'failed', 'cancelled',
                        'interrupted'
                    )
                ),
                arguments_json TEXT NOT NULL CHECK (json_valid(arguments_json)),
                output_json TEXT CHECK (
                    output_json IS NULL OR json_valid(output_json)
                ),
                error_json TEXT CHECK (
                    error_json IS NULL OR json_valid(error_json)
                ),
                progress_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(progress_json)),
                timeout_ms INTEGER NOT NULL CHECK (timeout_ms > 0),
                attempt INTEGER NOT NULL DEFAULT 1 CHECK (attempt > 0),
                duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                finished_at TEXT,
                FOREIGN KEY (session_id)
                    REFERENCES sessions(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE INDEX idx_tool_invocations_session_status
            ON tool_invocations(session_id, status, created_at)
            """,
            """
            CREATE INDEX idx_tool_invocations_trace
            ON tool_invocations(trace_id, created_at)
            """,
            """
            CREATE INDEX idx_tool_invocations_tool
            ON tool_invocations(tool_id, created_at)
            """,
        ),
    ),
    Migration(
        version=16,
        name="pausable_agent_runs",
        statements=(
            "DROP TRIGGER agent_run_status_transition",
            """
            CREATE TRIGGER agent_run_status_transition
            BEFORE UPDATE OF status ON agent_runs
            WHEN NEW.status != OLD.status AND NOT (
                (OLD.status = 'queued' AND NEW.status IN (
                    'planning', 'interrupted', 'cancelled'
                )) OR
                (OLD.status = 'planning' AND NEW.status IN (
                    'running', 'queued', 'interrupted', 'failed', 'cancelled'
                )) OR
                (OLD.status = 'running' AND NEW.status IN (
                    'queued', 'waiting_input', 'waiting_capability',
                    'interrupted', 'completed', 'failed', 'cancelled'
                )) OR
                (OLD.status IN ('waiting_input', 'waiting_capability')
                    AND NEW.status IN ('queued', 'failed', 'cancelled')) OR
                (OLD.status = 'interrupted'
                    AND NEW.status IN ('queued', 'failed', 'cancelled'))
            )
            BEGIN
                SELECT RAISE(ABORT, 'invalid AgentRun status transition');
            END
            """,
        ),
    ),
    Migration(
        version=17,
        name="agent_run_delegation",
        statements=(
            """
            ALTER TABLE agent_runs
            ADD COLUMN parent_run_id TEXT REFERENCES agent_runs(id) ON DELETE CASCADE
            """,
            """
            ALTER TABLE agent_runs
            ADD COLUMN root_run_id TEXT REFERENCES agent_runs(id) ON DELETE CASCADE
            """,
            """
            ALTER TABLE agent_runs
            ADD COLUMN depth INTEGER NOT NULL DEFAULT 0
                CHECK (depth >= 0 AND depth <= 4)
            """,
            """
            ALTER TABLE agent_runs
            ADD COLUMN delegation_json TEXT NOT NULL DEFAULT '{}'
                CHECK (json_valid(delegation_json))
            """,
            "UPDATE agent_runs SET root_run_id = id WHERE root_run_id IS NULL",
            """
            CREATE INDEX idx_agent_runs_parent
            ON agent_runs(parent_run_id, created_at)
            """,
            """
            CREATE INDEX idx_agent_runs_root
            ON agent_runs(root_run_id, depth, created_at)
            """,
            """
            CREATE TABLE agent_delegations (
                id TEXT PRIMARY KEY CHECK (
                    length(id) = 36 AND substr(id, 1, 4) = 'dlg_'
                    AND id = lower(id)
                    AND substr(id, 5) NOT GLOB '*[^0-9a-f]*'
                ),
                parent_run_id TEXT NOT NULL,
                child_run_id TEXT NOT NULL UNIQUE,
                request_key TEXT NOT NULL,
                target_agent_key TEXT NOT NULL,
                task TEXT NOT NULL,
                parameters_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(parameters_json)),
                context_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(context_json)),
                budget_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(budget_json)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (parent_run_id)
                    REFERENCES agent_runs(id) ON DELETE CASCADE,
                FOREIGN KEY (child_run_id)
                    REFERENCES agent_runs(id) ON DELETE CASCADE,
                UNIQUE (parent_run_id, request_key)
            )
            """,
            """
            CREATE INDEX idx_agent_delegations_parent
            ON agent_delegations(parent_run_id, created_at)
            """,
        ),
    ),
    Migration(
        version=18,
        name="coder_projects_and_threads",
        statements=(
            """
            CREATE TABLE coder_projects (
                id TEXT PRIMARY KEY CHECK (
                    length(id) = 37 AND substr(id, 1, 5) = 'cprj_'
                    AND id = lower(id)
                    AND substr(id, 6) NOT GLOB '*[^0-9a-f]*'
                ),
                name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
                root_path TEXT NOT NULL UNIQUE,
                project_kind TEXT NOT NULL DEFAULT 'general'
                    CHECK (project_kind IN ('general', 'ai2apps')),
                metadata_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(metadata_json)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE coder_threads (
                id TEXT PRIMARY KEY CHECK (
                    length(id) = 37 AND substr(id, 1, 5) = 'cthr_'
                    AND id = lower(id)
                    AND substr(id, 6) NOT GLOB '*[^0-9a-f]*'
                ),
                project_id TEXT NOT NULL,
                parent_thread_id TEXT,
                title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 160),
                agent TEXT NOT NULL CHECK (agent IN ('codex', 'opencode', 'claude')),
                model_source TEXT NOT NULL
                    CHECK (model_source IN ('default', 'ai2apps')),
                model TEXT NOT NULL DEFAULT '',
                terminal_session_id TEXT,
                native_session_id TEXT,
                status TEXT NOT NULL DEFAULT 'created'
                    CHECK (status IN ('created', 'running', 'stopped', 'failed', 'archived')),
                metadata_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(metadata_json)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES coder_projects(id) ON DELETE CASCADE,
                FOREIGN KEY (parent_thread_id) REFERENCES coder_threads(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE INDEX idx_coder_threads_project_updated
            ON coder_threads(project_id, updated_at DESC)
            """,
            """
            CREATE INDEX idx_coder_threads_parent
            ON coder_threads(parent_thread_id, created_at)
            """,
        ),
    ),
    Migration(
        version=19,
        name="durable_attachments_and_documents",
        statements=(
            """
            CREATE TABLE document_blobs (
                id TEXT PRIMARY KEY CHECK (
                    length(id) = 36 AND substr(id, 1, 4) = 'dbl_'
                    AND id = lower(id)
                    AND substr(id, 5) NOT GLOB '*[^0-9a-f]*'
                ),
                sha256 TEXT NOT NULL UNIQUE CHECK (
                    length(sha256) = 64 AND sha256 = lower(sha256)
                    AND sha256 NOT GLOB '*[^0-9a-f]*'
                ),
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                storage_key TEXT NOT NULL UNIQUE,
                parse_status TEXT NOT NULL DEFAULT 'queued'
                    CHECK (parse_status IN ('queued','parsing','ready','failed')),
                parser TEXT,
                parser_version TEXT,
                error_json TEXT CHECK (error_json IS NULL OR json_valid(error_json)),
                metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE attachments (
                id TEXT PRIMARY KEY CHECK (
                    length(id) = 37 AND substr(id, 1, 5) = 'attc_'
                    AND id = lower(id)
                    AND substr(id, 6) NOT GLOB '*[^0-9a-f]*'
                ),
                session_id TEXT NOT NULL,
                blob_id TEXT NOT NULL,
                filename TEXT NOT NULL CHECK (length(filename) BETWEEN 1 AND 512),
                media_type TEXT NOT NULL CHECK (length(media_type) BETWEEN 1 AND 255),
                metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (blob_id) REFERENCES document_blobs(id) ON DELETE RESTRICT
            )
            """,
            "CREATE INDEX idx_attachments_session_created ON attachments(session_id, created_at DESC)",
            """
            CREATE TABLE document_blocks (
                id TEXT PRIMARY KEY CHECK (
                    length(id) = 37 AND substr(id, 1, 5) = 'dblk_'
                    AND id = lower(id)
                    AND substr(id, 6) NOT GLOB '*[^0-9a-f]*'
                ),
                blob_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
                kind TEXT NOT NULL DEFAULT 'text',
                text TEXT NOT NULL,
                page INTEGER,
                section TEXT,
                sheet TEXT,
                slide INTEGER,
                cell_range TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
                FOREIGN KEY (blob_id) REFERENCES document_blobs(id) ON DELETE CASCADE,
                UNIQUE(blob_id, ordinal)
            )
            """,
            "CREATE INDEX idx_document_blocks_blob_ordinal ON document_blocks(blob_id, ordinal)",
        ),
    ),
    Migration(
        version=20,
        name="keychain_secret_metadata",
        statements=(
            """
            CREATE TABLE secret_records (
                id TEXT PRIMARY KEY CHECK (
                    length(id) = 36 AND substr(id, 1, 4) = 'sec_'
                    AND id = lower(id)
                    AND substr(id, 5) NOT GLOB '*[^0-9a-f]*'
                ),
                name TEXT NOT NULL UNIQUE CHECK (length(name) BETWEEN 1 AND 128),
                backend_key TEXT NOT NULL UNIQUE,
                purpose TEXT NOT NULL DEFAULT '',
                allowed_tools_json TEXT NOT NULL DEFAULT '[]'
                    CHECK (json_valid(allowed_tools_json)),
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','deleted')),
                metadata_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(metadata_json)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT
            )
            """,
            "CREATE INDEX idx_secret_records_status_name ON secret_records(status, name)",
        ),
    ),
    Migration(
        version=21,
        name="mobile_app_mounts",
        statements=(
            """
            CREATE TABLE app_mounts_v21 (
                id TEXT PRIMARY KEY,
                app_instance_id TEXT NOT NULL,
                interaction_session_id TEXT,
                placement TEXT NOT NULL
                    CHECK (placement IN ('entry', 'inline', 'sidebar', 'mobile')),
                renderer TEXT NOT NULL
                    CHECK (renderer IN ('host', 'schema', 'safe-html', 'sandbox')),
                resource TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('mounted', 'unmounted')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                context_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(context_json)),
                entry_source TEXT NOT NULL DEFAULT 'entry'
                    CHECK (entry_source IN ('entry', 'mini_entry', 'mobile_entry')),
                FOREIGN KEY(app_instance_id)
                    REFERENCES app_instances(id) ON DELETE RESTRICT,
                FOREIGN KEY(interaction_session_id)
                    REFERENCES sessions(id) ON DELETE RESTRICT
            )
            """,
            """
            INSERT INTO app_mounts_v21(
                id,app_instance_id,interaction_session_id,placement,renderer,
                resource,status,created_at,updated_at,context_json,entry_source
            )
            SELECT id,app_instance_id,interaction_session_id,placement,renderer,
                   resource,status,created_at,updated_at,context_json,
                   CASE WHEN placement IN ('inline','sidebar')
                        THEN 'mini_entry' ELSE 'entry' END
            FROM app_mounts
            """,
            "DROP TABLE app_mounts",
            "ALTER TABLE app_mounts_v21 RENAME TO app_mounts",
            "CREATE INDEX idx_app_mounts_instance ON app_mounts(app_instance_id, status)",
            """
            CREATE INDEX idx_app_mounts_interaction
            ON app_mounts(interaction_session_id, status, created_at)
            """,
            """
            CREATE INDEX idx_app_mounts_mobile
            ON app_mounts(placement, status, updated_at DESC)
            """,
        ),
    ),
    Migration(
        version=22,
        name="remote_client_devices",
        statements=(
            """
            CREATE TABLE remote_client_devices (
                device_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                platform TEXT NOT NULL,
                client_version TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('active','suspended','revoked')),
                suspension_reason TEXT,
                access_epoch INTEGER NOT NULL CHECK (access_epoch >= 1),
                public_origin TEXT NOT NULL,
                credential_version INTEGER NOT NULL CHECK (credential_version >= 1),
                credential_expires_at TEXT NOT NULL,
                server_addr TEXT NOT NULL,
                server_port INTEGER NOT NULL CHECK (server_port BETWEEN 1 AND 65535),
                proxy_name TEXT NOT NULL,
                subdomain TEXT NOT NULL,
                secret_backend_key TEXT NOT NULL UNIQUE,
                enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0,1)),
                online INTEGER NOT NULL DEFAULT 0 CHECK (online IN (0,1)),
                proxy_connected INTEGER NOT NULL DEFAULT 0 CHECK (proxy_connected IN (0,1)),
                last_seen_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX idx_remote_client_devices_status ON remote_client_devices(status, updated_at DESC)",
        ),
    ),
)


def _validate_migrations(migrations: Sequence[Migration]) -> None:
    versions = [migration.version for migration in migrations]
    expected = list(range(1, len(migrations) + 1))
    if versions != expected:
        raise MigrationError(
            f"Migration versions must be contiguous from 1; got {versions!r}"
        )
    names = [migration.name for migration in migrations]
    if len(names) != len(set(names)):
        raise MigrationError("Migration names must be unique")


def _pragma_user_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("PRAGMA user_version").fetchone()
    if row is None:
        raise DatabaseCorruptionError("SQLite did not return PRAGMA user_version")
    return int(row[0])


def apply_migrations(
    connection: sqlite3.Connection,
    migrations: Sequence[Migration] = MIGRATIONS,
) -> int:
    """Apply pending migrations atomically under a SQLite write lock."""

    _validate_migrations(migrations)
    target_version = len(migrations)
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                applied_at TEXT NOT NULL
            )
            """
        )
        ledger = {
            int(row[0]): str(row[1])
            for row in connection.execute(
                "SELECT version, name FROM schema_migrations ORDER BY version"
            )
        }
        user_version = _pragma_user_version(connection)

        if user_version > target_version:
            raise FutureSchemaError(
                "Platform database schema "
                f"v{user_version} is newer than supported v{target_version}"
            )
        if any(version > target_version for version in ledger):
            raise FutureSchemaError(
                "Migration ledger contains a version newer than this AI2Apps build"
            )

        expected_applied = {
            migration.version: migration.name
            for migration in migrations
            if migration.version <= user_version
        }
        if ledger != expected_applied:
            raise DatabaseCorruptionError(
                "PRAGMA user_version and schema_migrations ledger disagree"
            )

        for migration in migrations[user_version:]:
            for statement in migration.statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) "
                "VALUES (?, ?, ?)",
                (migration.version, migration.name, utc_now_text()),
            )
            connection.execute(f"PRAGMA user_version = {migration.version}")

        connection.commit()
        return target_version
    except Exception:
        connection.rollback()
        raise
