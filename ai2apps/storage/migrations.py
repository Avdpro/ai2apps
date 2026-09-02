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
    Migration(
        version=23,
        name="installation_member_identity",
        statements=(
            """
            CREATE TABLE installations (
                id TEXT PRIMARY KEY CHECK (length(id) BETWEEN 1 AND 200),
                cloud_device_id TEXT NOT NULL UNIQUE
                    CHECK (length(cloud_device_id) BETWEEN 1 AND 200),
                organization_id TEXT NOT NULL
                    CHECK (length(organization_id) BETWEEN 1 AND 200),
                organization_type TEXT NOT NULL
                    CHECK (organization_type IN ('household','business')),
                core_user_id TEXT NOT NULL
                    CHECK (length(core_user_id) BETWEEN 1 AND 200),
                billing_account_id TEXT NOT NULL
                    CHECK (length(billing_account_id) BETWEEN 1 AND 200),
                access_epoch INTEGER NOT NULL CHECK (access_epoch >= 1),
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','suspended','revoked')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE installation_memberships (
                installation_id TEXT NOT NULL,
                cloud_user_id TEXT NOT NULL
                    CHECK (length(cloud_user_id) BETWEEN 1 AND 200),
                role TEXT NOT NULL CHECK (role IN (
                    'core','owner','admin','developer','member','child','guest'
                )),
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','suspended','revoked')),
                membership_epoch INTEGER NOT NULL CHECK (membership_epoch >= 1),
                last_verified_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (installation_id, cloud_user_id),
                FOREIGN KEY (installation_id)
                    REFERENCES installations(id) ON DELETE RESTRICT
            )
            """,
            """
            CREATE INDEX idx_installation_memberships_user_status
            ON installation_memberships(cloud_user_id, status)
            """,
            """
            CREATE TABLE local_login_sessions (
                token_digest TEXT PRIMARY KEY CHECK (length(token_digest) = 64),
                installation_id TEXT NOT NULL,
                actor_user_id TEXT NOT NULL,
                role_snapshot TEXT NOT NULL CHECK (role_snapshot IN (
                    'core','owner','admin','developer','member','child','guest'
                )),
                membership_epoch INTEGER NOT NULL CHECK (membership_epoch >= 1),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_access_check_at TEXT NOT NULL,
                FOREIGN KEY (installation_id, actor_user_id)
                    REFERENCES installation_memberships(
                        installation_id, cloud_user_id
                    ) ON DELETE RESTRICT
            )
            """,
            """
            CREATE INDEX idx_local_login_sessions_installation_actor
            ON local_login_sessions(installation_id, actor_user_id, expires_at)
            """,
            """
            ALTER TABLE app_instances ADD COLUMN owner_user_id TEXT
                CHECK (owner_user_id IS NULL OR length(owner_user_id) BETWEEN 1 AND 200)
            """,
            """
            CREATE INDEX idx_app_instances_owner_status
            ON app_instances(owner_user_id, status, updated_at DESC)
            """,
        ),
    ),
    Migration(
        version=24,
        name="user_owned_coder_projects",
        statements=(
            """
            ALTER TABLE coder_projects
            ADD COLUMN owner_user_id TEXT
                CHECK (
                    owner_user_id IS NULL
                    OR length(owner_user_id) BETWEEN 1 AND 200
                )
            """,
            """
            CREATE INDEX idx_coder_projects_owner_updated
            ON coder_projects(owner_user_id, updated_at DESC)
            """,
        ),
    ),
    Migration(
        version=25,
        name="cloud_ai_request_ownership",
        statements=(
            """
            CREATE TABLE cloud_ai_requests (
                idempotency_key TEXT PRIMARY KEY
                    CHECK (length(idempotency_key) BETWEEN 8 AND 160),
                cloud_request_id TEXT UNIQUE
                    CHECK (
                        cloud_request_id IS NULL
                        OR length(cloud_request_id) BETWEEN 1 AND 200
                    ),
                actor_user_id TEXT NOT NULL
                    CHECK (length(actor_user_id) BETWEEN 1 AND 200),
                installation_id TEXT NOT NULL
                    CHECK (length(installation_id) BETWEEN 1 AND 200),
                organization_id TEXT NOT NULL
                    CHECK (length(organization_id) BETWEEN 1 AND 200),
                billing_account_id TEXT NOT NULL
                    CHECK (length(billing_account_id) BETWEEN 1 AND 200),
                membership_epoch INTEGER NOT NULL CHECK (membership_epoch >= 1),
                operation TEXT NOT NULL CHECK (operation IN (
                    'responses','images.generations','images.edits'
                )),
                model TEXT NOT NULL CHECK (length(model) <= 500),
                status TEXT NOT NULL CHECK (status IN (
                    'requested','in_progress','completed','failed',
                    'cancel_requested','cancelled'
                )),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX idx_cloud_ai_requests_actor_updated
            ON cloud_ai_requests(
                installation_id, actor_user_id, updated_at DESC
            )
            """,
            """
            CREATE INDEX idx_cloud_ai_requests_status_updated
            ON cloud_ai_requests(status, updated_at DESC)
            """,
        ),
    ),
    Migration(
        version=26,
        name="local_client_session_scope",
        statements=(
            """
            ALTER TABLE local_login_sessions
            ADD COLUMN client_scope TEXT NOT NULL DEFAULT 'desktop'
                CHECK (length(client_scope) BETWEEN 1 AND 200)
            """,
        ),
    ),
    Migration(
        version=27,
        name="local_capability_sharing",
        statements=(
            """
            CREATE TABLE capability_exports (
                id TEXT PRIMARY KEY
                    CHECK (length(id) = 36 AND substr(id, 1, 4) = 'exp_'),
                kind TEXT NOT NULL CHECK (kind IN ('model','tool')),
                target_id TEXT NOT NULL CHECK (length(target_id) BETWEEN 1 AND 500),
                display_name TEXT NOT NULL CHECK (length(display_name) BETWEEN 1 AND 200),
                protocols_json TEXT NOT NULL CHECK (json_valid(protocols_json)),
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','paused','revoked')),
                created_by_user_id TEXT NOT NULL
                    CHECK (length(created_by_user_id) BETWEEN 1 AND 200),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE UNIQUE INDEX uq_active_capability_export_target
            ON capability_exports(kind, target_id) WHERE status != 'revoked'
            """,
            """
            CREATE TABLE capability_share_grants (
                id TEXT PRIMARY KEY
                    CHECK (length(id) = 36 AND substr(id, 1, 4) = 'shr_'),
                label TEXT NOT NULL CHECK (length(label) BETWEEN 1 AND 200),
                token_digest TEXT NOT NULL UNIQUE CHECK (length(token_digest) = 64),
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','revoked')),
                max_concurrency INTEGER NOT NULL DEFAULT 1
                    CHECK (max_concurrency BETWEEN 1 AND 100),
                expires_at TEXT,
                created_by_user_id TEXT NOT NULL
                    CHECK (length(created_by_user_id) BETWEEN 1 AND 200),
                request_count INTEGER NOT NULL DEFAULT 0 CHECK (request_count >= 0),
                last_used_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE capability_share_grant_exports (
                grant_id TEXT NOT NULL,
                export_id TEXT NOT NULL,
                PRIMARY KEY (grant_id, export_id),
                FOREIGN KEY (grant_id)
                    REFERENCES capability_share_grants(id) ON DELETE RESTRICT,
                FOREIGN KEY (export_id)
                    REFERENCES capability_exports(id) ON DELETE RESTRICT
            )
            """,
            """
            CREATE TABLE capability_share_audit (
                id TEXT PRIMARY KEY
                    CHECK (length(id) = 36 AND substr(id, 1, 4) = 'sha_'),
                grant_id TEXT NOT NULL,
                export_id TEXT,
                operation TEXT NOT NULL CHECK (length(operation) BETWEEN 1 AND 200),
                status TEXT NOT NULL CHECK (status IN ('started','completed','failed','denied')),
                duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
                error_code TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (grant_id)
                    REFERENCES capability_share_grants(id) ON DELETE RESTRICT,
                FOREIGN KEY (export_id)
                    REFERENCES capability_exports(id) ON DELETE RESTRICT
            )
            """,
            """
            CREATE INDEX idx_capability_share_audit_grant_created
            ON capability_share_audit(grant_id, created_at DESC)
            """,
        ),
    ),
    Migration(
        version=28,
        name="core_controlled_lan_access",
        statements=(
            """
            CREATE TABLE local_network_access (
                singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                mode TEXT NOT NULL DEFAULT 'disabled'
                    CHECK (mode IN ('disabled','share_only','full')),
                bind_host TEXT NOT NULL DEFAULT '0.0.0.0'
                    CHECK (length(bind_host) BETWEEN 1 AND 200),
                port INTEGER NOT NULL DEFAULT 8011
                    CHECK (port BETWEEN 1024 AND 65535),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                updated_by_user_id TEXT NOT NULL DEFAULT 'local'
                    CHECK (length(updated_by_user_id) BETWEEN 1 AND 200),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            INSERT INTO local_network_access(
                singleton_id,mode,bind_host,port,revision,
                updated_by_user_id,created_at,updated_at
            ) VALUES (1,'disabled','0.0.0.0',8011,1,'local',
                strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            """,
        ),
    ),
    Migration(
        version=29,
        name="upstream_ai_gateways",
        statements=(
            """
            CREATE TABLE upstream_gateways (
                id TEXT PRIMARY KEY
                    CHECK (length(id) = 36 AND substr(id, 1, 4) = 'upg_'),
                label TEXT NOT NULL CHECK (length(label) BETWEEN 1 AND 200),
                openai_base_url TEXT NOT NULL
                    CHECK (length(openai_base_url) BETWEEN 1 AND 2000),
                mcp_url TEXT NOT NULL CHECK (length(mcp_url) BETWEEN 1 AND 2000),
                secret_backend_key TEXT NOT NULL UNIQUE
                    CHECK (length(secret_backend_key) BETWEEN 1 AND 500),
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','disabled')),
                health_status TEXT NOT NULL DEFAULT 'unknown'
                    CHECK (health_status IN ('unknown','online','offline')),
                capabilities_json TEXT NOT NULL DEFAULT '{}'
                    CHECK (json_valid(capabilities_json)),
                last_error TEXT CHECK (
                    last_error IS NULL OR length(last_error) <= 1000
                ),
                last_checked_at TEXT,
                created_by_user_id TEXT NOT NULL
                    CHECK (length(created_by_user_id) BETWEEN 1 AND 200),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE UNIQUE INDEX uq_active_upstream_gateway_endpoint
            ON upstream_gateways(openai_base_url) WHERE status = 'active'
            """,
            """
            CREATE INDEX idx_upstream_gateways_status_updated
            ON upstream_gateways(status, updated_at DESC)
            """,
        ),
    ),
    Migration(
        version=30,
        name="upstream_gateway_activity",
        statements=(
            """
            CREATE TABLE upstream_gateway_activity (
                id TEXT PRIMARY KEY
                    CHECK (length(id) = 36 AND substr(id, 1, 4) = 'upa_'),
                gateway_id TEXT NOT NULL,
                operation TEXT NOT NULL
                    CHECK (operation IN ('probe','model','tool')),
                capability_id TEXT CHECK (
                    capability_id IS NULL OR length(capability_id) <= 500
                ),
                status TEXT NOT NULL CHECK (status IN ('completed','failed')),
                duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
                error_code TEXT CHECK (
                    error_code IS NULL OR length(error_code) <= 100
                ),
                created_at TEXT NOT NULL,
                FOREIGN KEY (gateway_id)
                    REFERENCES upstream_gateways(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE INDEX idx_upstream_gateway_activity_gateway_created
            ON upstream_gateway_activity(gateway_id, created_at DESC)
            """,
        ),
    ),
    Migration(
        version=31,
        name="share_grant_request_budget",
        statements=(
            """
            ALTER TABLE capability_share_grants
            ADD COLUMN max_requests INTEGER CHECK (
                max_requests IS NULL OR max_requests BETWEEN 1 AND 1000000
            )
            """,
        ),
    ),
    Migration(
        version=32,
        name="share_services_and_agents",
        statements=(
            """
            CREATE TABLE capability_exports_v32 (
                id TEXT PRIMARY KEY
                    CHECK (length(id) = 36 AND substr(id, 1, 4) = 'exp_'),
                kind TEXT NOT NULL
                    CHECK (kind IN ('model','tool','service','agent')),
                target_id TEXT NOT NULL
                    CHECK (length(target_id) BETWEEN 1 AND 500),
                display_name TEXT NOT NULL
                    CHECK (length(display_name) BETWEEN 1 AND 200),
                protocols_json TEXT NOT NULL CHECK (json_valid(protocols_json)),
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','paused','revoked')),
                created_by_user_id TEXT NOT NULL
                    CHECK (length(created_by_user_id) BETWEEN 1 AND 200),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            INSERT INTO capability_exports_v32
            SELECT * FROM capability_exports
            """,
            """
            CREATE TABLE capability_share_grant_exports_v32 (
                grant_id TEXT NOT NULL,
                export_id TEXT NOT NULL,
                PRIMARY KEY (grant_id, export_id),
                FOREIGN KEY (grant_id)
                    REFERENCES capability_share_grants(id) ON DELETE RESTRICT,
                FOREIGN KEY (export_id)
                    REFERENCES capability_exports_v32(id) ON DELETE RESTRICT
            )
            """,
            """
            INSERT INTO capability_share_grant_exports_v32
            SELECT * FROM capability_share_grant_exports
            """,
            """
            CREATE TABLE capability_share_audit_v32 (
                id TEXT PRIMARY KEY
                    CHECK (length(id) = 36 AND substr(id, 1, 4) = 'sha_'),
                grant_id TEXT NOT NULL,
                export_id TEXT,
                operation TEXT NOT NULL CHECK (length(operation) BETWEEN 1 AND 200),
                status TEXT NOT NULL
                    CHECK (status IN ('started','completed','failed','denied')),
                duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
                error_code TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (grant_id)
                    REFERENCES capability_share_grants(id) ON DELETE RESTRICT,
                FOREIGN KEY (export_id)
                    REFERENCES capability_exports_v32(id) ON DELETE RESTRICT
            )
            """,
            """
            INSERT INTO capability_share_audit_v32
            SELECT * FROM capability_share_audit
            """,
            "DROP TABLE capability_share_audit",
            "DROP TABLE capability_share_grant_exports",
            "DROP TABLE capability_exports",
            "ALTER TABLE capability_exports_v32 RENAME TO capability_exports",
            "ALTER TABLE capability_share_grant_exports_v32 RENAME TO capability_share_grant_exports",
            "ALTER TABLE capability_share_audit_v32 RENAME TO capability_share_audit",
            """
            CREATE UNIQUE INDEX uq_active_capability_export_target
            ON capability_exports(kind, target_id) WHERE status != 'revoked'
            """,
            """
            CREATE INDEX idx_capability_share_audit_grant_created
            ON capability_share_audit(grant_id, created_at DESC)
            """,
        ),
    ),
    Migration(
        version=33,
        name="parent_local_routing",
        statements=(
            """
            ALTER TABLE upstream_gateways ADD COLUMN remote_node_id TEXT
                CHECK (remote_node_id IS NULL OR length(remote_node_id) BETWEEN 8 AND 128)
            """,
            """
            ALTER TABLE upstream_gateways ADD COLUMN ancestor_node_ids_json TEXT
                NOT NULL DEFAULT '[]' CHECK (json_valid(ancestor_node_ids_json))
            """,
            """
            ALTER TABLE upstream_gateways ADD COLUMN is_parent INTEGER
                NOT NULL DEFAULT 1 CHECK (is_parent IN (0,1))
            """,
            """
            ALTER TABLE upstream_gateways ADD COLUMN is_default INTEGER
                NOT NULL DEFAULT 0 CHECK (is_default IN (0,1))
            """,
            """
            ALTER TABLE upstream_gateways ADD COLUMN priority INTEGER
                NOT NULL DEFAULT 100 CHECK (priority BETWEEN 1 AND 1000)
            """,
            """
            ALTER TABLE upstream_gateways ADD COLUMN route_models INTEGER
                NOT NULL DEFAULT 1 CHECK (route_models IN (0,1))
            """,
            """
            ALTER TABLE upstream_gateways ADD COLUMN route_mcp INTEGER
                NOT NULL DEFAULT 1 CHECK (route_mcp IN (0,1))
            """,
            """
            CREATE UNIQUE INDEX uq_upstream_remote_node
            ON upstream_gateways(remote_node_id) WHERE remote_node_id IS NOT NULL
            """,
            """
            CREATE UNIQUE INDEX uq_default_parent_local
            ON upstream_gateways(is_default) WHERE is_default = 1
            """,
            """
            UPDATE upstream_gateways SET is_default=1
            WHERE id=(
                SELECT id FROM upstream_gateways
                WHERE is_parent=1 AND status='active'
                ORDER BY created_at,id LIMIT 1
            )
            """,
            """
            CREATE TABLE upstream_route_settings (
                singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                model_policy TEXT NOT NULL DEFAULT 'explicit_only'
                    CHECK (model_policy IN ('explicit_only','parent_first')),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                updated_by_user_id TEXT NOT NULL
                    CHECK (length(updated_by_user_id) BETWEEN 1 AND 200),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            INSERT INTO upstream_route_settings(
                singleton_id,model_policy,revision,updated_by_user_id,created_at,updated_at
            ) VALUES (
                1,'explicit_only',1,'system',
                strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                strftime('%Y-%m-%dT%H:%M:%fZ','now')
            )
            """,
        ),
    ),
    Migration(
        version=34,
        name="cloud_relay_parent_transport",
        statements=(
            """
            ALTER TABLE upstream_gateways ADD COLUMN transport_kind TEXT
                NOT NULL DEFAULT 'direct' CHECK (transport_kind IN ('direct','cloud_relay'))
            """,
            """
            ALTER TABLE upstream_gateways ADD COLUMN downstream_installation_id TEXT
                CHECK (downstream_installation_id IS NULL OR length(downstream_installation_id) BETWEEN 8 AND 200)
            """,
            """
            ALTER TABLE upstream_gateways ADD COLUMN node_link_id TEXT
                CHECK (node_link_id IS NULL OR length(node_link_id) BETWEEN 8 AND 200)
            """,
            """
            CREATE UNIQUE INDEX uq_upstream_node_link
            ON upstream_gateways(node_link_id) WHERE node_link_id IS NOT NULL
            """,
            """
            CREATE TABLE federation_pairing_attempts (
                pairing_id TEXT PRIMARY KEY CHECK (length(pairing_id) BETWEEN 8 AND 200),
                secret_backend_key TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','exchanged','expired')),
                created_by_user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        ),
    ),
    Migration(
        version=35,
        name="local_security_instance_identity",
        statements=(
            """
            CREATE TABLE local_security_identity (
                singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                security_instance_id TEXT NOT NULL UNIQUE
                    CHECK (
                        length(security_instance_id) = 38
                        AND substr(security_instance_id, 1, 6) = 'local_'
                        AND substr(security_instance_id, 7)
                            NOT GLOB '*[^0-9a-f]*'
                    ),
                created_at TEXT NOT NULL
                    CHECK (length(created_at) = 27 AND substr(created_at, -1) = 'Z')
            )
            """,
        ),
    ),
    Migration(
        version=36,
        name="messager_local_conversations",
        statements=(
            """
            CREATE TABLE messager_conversations (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                peer_user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(owner_user_id, peer_user_id),
                CHECK (owner_user_id <> peer_user_id)
            )
            """,
            """
            CREATE TABLE messager_messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES messager_conversations(id) ON DELETE CASCADE,
                owner_user_id TEXT NOT NULL,
                peer_user_id TEXT NOT NULL,
                direction TEXT NOT NULL CHECK (direction IN ('incoming','outgoing')),
                transport TEXT NOT NULL CHECK (transport IN ('local_e2ee','cloud_offline')),
                status TEXT NOT NULL CHECK (status IN ('queued','sending','sent','received','result_unknown','failed')),
                body TEXT NOT NULL CHECK (length(body) BETWEEN 0 AND 4000),
                client_message_id TEXT,
                remote_message_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE UNIQUE INDEX uq_messager_outgoing_client_message
            ON messager_messages(owner_user_id, client_message_id)
            WHERE client_message_id IS NOT NULL
            """,
            """
            CREATE UNIQUE INDEX uq_messager_incoming_remote_message
            ON messager_messages(owner_user_id, remote_message_id)
            WHERE remote_message_id IS NOT NULL
            """,
            """
            CREATE INDEX ix_messager_messages_conversation_created
            ON messager_messages(conversation_id, created_at, id)
            """,
        ),
    ),
    Migration(
        version=37,
        name="messager_image_attachments",
        statements=(
            "ALTER TABLE messager_messages ADD COLUMN attachment_id TEXT",
            "ALTER TABLE messager_messages ADD COLUMN attachment_media_type TEXT",
            "ALTER TABLE messager_messages ADD COLUMN attachment_byte_size INTEGER",
            "ALTER TABLE messager_messages ADD COLUMN attachment_width INTEGER",
            "ALTER TABLE messager_messages ADD COLUMN attachment_height INTEGER",
            "ALTER TABLE messager_messages ADD COLUMN attachment_content_path TEXT",
        ),
    ),
    Migration(
        version=38,
        name="messager_peer_replay_protection",
        statements=(
            "DROP INDEX uq_messager_incoming_remote_message",
            """
            CREATE UNIQUE INDEX uq_messager_incoming_remote_message
            ON messager_messages(owner_user_id, peer_user_id, remote_message_id)
            WHERE remote_message_id IS NOT NULL
            """,
            """
            CREATE TABLE messager_peer_handshake_replays (
                assertion_jti TEXT PRIMARY KEY,
                handshake_id TEXT NOT NULL UNIQUE,
                initiator_user_id TEXT NOT NULL,
                initiator_device_id TEXT NOT NULL,
                expires_at INTEGER NOT NULL CHECK (expires_at > 0),
                accepted_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX ix_messager_peer_replay_expiry
            ON messager_peer_handshake_replays(expires_at)
            """,
        ),
    ),
    Migration(
        version=39,
        name="readaloud_studio_projects",
        statements=(
            """
            CREATE TABLE readaloud_projects (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 160),
                purpose TEXT NOT NULL CHECK (purpose IN ('private','noncommercial','commercial')),
                source_rights TEXT NOT NULL CHECK (
                    source_rights IN ('user_owned','licensed','public_domain','personal_use')
                ),
                source_text TEXT NOT NULL DEFAULT '' CHECK (length(source_text) <= 200000),
                status TEXT NOT NULL CHECK (status IN ('draft','ready','archived')),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX ix_readaloud_projects_owner_updated
            ON readaloud_projects(owner_user_id, updated_at DESC)
            """,
            """
            CREATE TABLE readaloud_voice_profiles (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
                source_type TEXT NOT NULL CHECK (
                    source_type IN ('synthetic_designed','self_voice','authorized_person')
                ),
                model_id TEXT,
                provider_voice_id TEXT,
                reference_transcript TEXT NOT NULL DEFAULT '' CHECK (
                    length(reference_transcript) <= 20000
                ),
                rights_scope_json TEXT NOT NULL DEFAULT '{}' CHECK (
                    json_valid(rights_scope_json)
                ),
                status TEXT NOT NULL CHECK (
                    status IN ('unverified','ready','blocked','deleted')
                ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX ix_readaloud_voice_profiles_owner_updated
            ON readaloud_voice_profiles(owner_user_id, updated_at DESC)
            """,
            """
            CREATE TABLE readaloud_characters (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES readaloud_projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
                description TEXT NOT NULL DEFAULT '' CHECK (length(description) <= 2000),
                voice_profile_id TEXT REFERENCES readaloud_voice_profiles(id),
                sort_order INTEGER NOT NULL CHECK (sort_order >= 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, name)
            )
            """,
            """
            CREATE INDEX ix_readaloud_characters_project_order
            ON readaloud_characters(project_id, sort_order, id)
            """,
            """
            CREATE TABLE readaloud_segments (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES readaloud_projects(id) ON DELETE CASCADE,
                ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
                speaker_id TEXT REFERENCES readaloud_characters(id),
                text TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND 10000),
                emotion TEXT NOT NULL DEFAULT 'neutral' CHECK (length(emotion) BETWEEN 1 AND 80),
                emotion_strength REAL NOT NULL DEFAULT 1.0 CHECK (
                    emotion_strength BETWEEN 0.0 AND 2.0
                ),
                speed REAL NOT NULL DEFAULT 1.0 CHECK (speed BETWEEN 0.5 AND 2.0),
                pause_after_ms INTEGER NOT NULL DEFAULT 300 CHECK (
                    pause_after_ms BETWEEN 0 AND 10000
                ),
                review_status TEXT NOT NULL CHECK (
                    review_status IN ('suggested','needs_review','approved')
                ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, ordinal)
            )
            """,
            """
            CREATE INDEX ix_readaloud_segments_project_order
            ON readaloud_segments(project_id, ordinal, id)
            """,
        ),
    ),
    Migration(
        version=40,
        name="durable_video_generation_tasks",
        statements=(
            """
            CREATE TABLE video_generation_tasks (
                id TEXT PRIMARY KEY,
                actor_id TEXT NOT NULL,
                model_id TEXT NOT NULL,
                model_revision TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('queued','running','succeeded','failed','cancelled','expired')
                ),
                request_json TEXT NOT NULL CHECK (json_valid(request_json)),
                request_hash TEXT NOT NULL,
                idempotency_key TEXT,
                progress_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(progress_json)),
                input_manifest_json TEXT NOT NULL DEFAULT '{}' CHECK (
                    json_valid(input_manifest_json)
                ),
                artifact_id TEXT,
                artifact_session_id TEXT,
                error_json TEXT CHECK (error_json IS NULL OR json_valid(error_json)),
                cancel_requested_at TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (artifact_id) REFERENCES artifacts(id) ON DELETE SET NULL,
                FOREIGN KEY (artifact_session_id) REFERENCES sessions(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE UNIQUE INDEX uq_video_generation_task_idempotency
            ON video_generation_tasks(actor_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL
            """,
            """
            CREATE INDEX ix_video_generation_tasks_actor_created
            ON video_generation_tasks(actor_id, created_at DESC, id DESC)
            """,
            """
            CREATE INDEX ix_video_generation_tasks_status_created
            ON video_generation_tasks(status, created_at, id)
            """,
        ),
    ),
    Migration(
        version=41,
        name="acpf_provisioning_sessions",
        statements=(
            """
            CREATE TABLE provisioning_sessions (
                id TEXT PRIMARY KEY CHECK (
                    length(id) = 36 AND substr(id, 1, 4) = 'prv_'
                    AND id = lower(id)
                    AND substr(id, 5) NOT GLOB '*[^0-9a-f]*'
                ),
                actor_id TEXT NOT NULL,
                installation_id TEXT NOT NULL,
                app_id TEXT NOT NULL CHECK (length(app_id) BETWEEN 1 AND 200),
                capability TEXT NOT NULL CHECK (length(capability) BETWEEN 1 AND 200),
                action_id TEXT NOT NULL CHECK (length(action_id) BETWEEN 1 AND 120),
                status TEXT NOT NULL CHECK (status IN (
                    'planning','awaiting_confirmation','installing_runtime',
                    'awaiting_restart','installing_provider','downloading_checkpoint',
                    'activating','verifying','ready','failed','cancelled','unsupported'
                )),
                profile_id TEXT,
                plan_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(plan_json)),
                intent_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(intent_json)),
                operations_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(operations_json)),
                progress_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(progress_json)),
                error_json TEXT CHECK (error_json IS NULL OR json_valid(error_json)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            )
            """,
            """
            CREATE INDEX ix_provisioning_sessions_actor_updated
            ON provisioning_sessions(actor_id, updated_at DESC)
            """,
            """
            CREATE UNIQUE INDEX uq_provisioning_sessions_active_intent
            ON provisioning_sessions(actor_id, installation_id, app_id, capability, action_id)
            WHERE status IN (
                'planning','awaiting_confirmation','installing_runtime',
                'awaiting_restart','installing_provider','downloading_checkpoint',
                'activating','verifying'
            )
            """,
        ),
    ),
    Migration(
        version=42,
        name="desktop_session_authority_epochs",
        statements=(
            """
            ALTER TABLE installations
            ADD COLUMN local_session_epoch INTEGER NOT NULL DEFAULT 1
                CHECK (local_session_epoch >= 1)
            """,
            """
            ALTER TABLE installation_memberships
            ADD COLUMN account_session_epoch INTEGER NOT NULL DEFAULT 1
                CHECK (account_session_epoch >= 1)
            """,
            """
            ALTER TABLE local_login_sessions
            ADD COLUMN access_epoch INTEGER NOT NULL DEFAULT 1
                CHECK (access_epoch >= 1)
            """,
            """
            ALTER TABLE local_login_sessions
            ADD COLUMN local_session_epoch INTEGER NOT NULL DEFAULT 1
                CHECK (local_session_epoch >= 1)
            """,
            """
            ALTER TABLE local_login_sessions
            ADD COLUMN account_session_epoch INTEGER NOT NULL DEFAULT 1
                CHECK (account_session_epoch >= 1)
            """,
            """
            UPDATE local_login_sessions
            SET access_epoch = COALESCE(
                    (
                        SELECT installations.access_epoch
                        FROM installations
                        WHERE installations.id = local_login_sessions.installation_id
                    ),
                    1
                ),
                local_session_epoch = COALESCE(
                    (
                        SELECT installations.local_session_epoch
                        FROM installations
                        WHERE installations.id = local_login_sessions.installation_id
                    ),
                    1
                ),
                account_session_epoch = COALESCE(
                    (
                        SELECT installation_memberships.account_session_epoch
                        FROM installation_memberships
                        WHERE installation_memberships.installation_id =
                                local_login_sessions.installation_id
                          AND installation_memberships.cloud_user_id =
                                local_login_sessions.actor_user_id
                    ),
                    1
                )
            """,
        ),
    ),
    Migration(
        version=43,
        name="acpf_trusted_app_instance_and_request_identity",
        statements=(
            """
            ALTER TABLE provisioning_sessions
            ADD COLUMN app_instance_id TEXT NOT NULL DEFAULT 'legacy'
                CHECK (length(app_instance_id) BETWEEN 1 AND 200)
            """,
            """
            ALTER TABLE provisioning_sessions
            ADD COLUMN request_fingerprint TEXT NOT NULL DEFAULT ''
                CHECK (
                    request_fingerprint = '' OR (
                        length(request_fingerprint) = 64
                        AND request_fingerprint = lower(request_fingerprint)
                        AND request_fingerprint NOT GLOB '*[^0-9a-f]*'
                    )
                )
            """,
            "DROP INDEX uq_provisioning_sessions_active_intent",
            """
            CREATE UNIQUE INDEX uq_provisioning_sessions_active_request
            ON provisioning_sessions(
                actor_id, installation_id, app_instance_id, app_id,
                capability, action_id, request_fingerprint
            )
            WHERE status IN (
                'planning','awaiting_confirmation','installing_runtime',
                'awaiting_restart','installing_provider','downloading_checkpoint',
                'activating','verifying'
            )
            """,
        ),
    ),
    Migration(
        version=44,
        name="gallery_assets_and_collections",
        statements=(
            """
            CREATE TABLE gallery_assets (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 512),
                kind TEXT NOT NULL CHECK (
                    kind IN ('image','video','audio','web','document','file')
                ),
                media_type TEXT NOT NULL CHECK (length(media_type) BETWEEN 1 AND 255),
                content_hash TEXT NOT NULL CHECK (
                    length(content_hash) = 71 AND substr(content_hash, 1, 7) = 'sha256:'
                ),
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                storage_key TEXT NOT NULL CHECK (length(storage_key) > 0),
                source_app_id TEXT,
                source_ref TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','trashed')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                trashed_at TEXT,
                UNIQUE (owner_user_id, content_hash, name)
            )
            """,
            """
            CREATE INDEX ix_gallery_assets_owner_status_created
            ON gallery_assets(owner_user_id, status, created_at DESC, id DESC)
            """,
            """
            CREATE INDEX ix_gallery_assets_blob_reference
            ON gallery_assets(storage_key)
            """,
            """
            CREATE TABLE gallery_collections (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
                kind TEXT NOT NULL CHECK (kind IN ('system','custom','project')),
                system_key TEXT CHECK (
                    system_key IS NULL OR system_key IN ('downloads','public','personal','trash')
                ),
                sort_mode TEXT NOT NULL DEFAULT 'manual' CHECK (
                    sort_mode IN ('manual','created_desc','name')
                ),
                metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (owner_user_id, system_key)
            )
            """,
            """
            CREATE INDEX ix_gallery_collections_owner_kind
            ON gallery_collections(owner_user_id, kind, created_at, id)
            """,
            """
            CREATE TABLE gallery_collection_items (
                collection_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                position INTEGER NOT NULL CHECK (position >= 0),
                added_at TEXT NOT NULL,
                PRIMARY KEY (collection_id, asset_id),
                FOREIGN KEY (collection_id) REFERENCES gallery_collections(id) ON DELETE CASCADE,
                FOREIGN KEY (asset_id) REFERENCES gallery_assets(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE INDEX ix_gallery_collection_items_order
            ON gallery_collection_items(collection_id, position, added_at, asset_id)
            """,
            """
            CREATE TRIGGER gallery_collection_item_owner_insert
            BEFORE INSERT ON gallery_collection_items
            WHEN NOT EXISTS (
                SELECT 1
                FROM gallery_collections c
                JOIN gallery_assets a ON a.id = NEW.asset_id
                WHERE c.id = NEW.collection_id
                  AND c.owner_user_id = a.owner_user_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'gallery collection and asset owners differ');
            END
            """,
        ),
    ),
    Migration(
        version=45,
        name="video_studio_acpf_drafts",
        statements=(
            """
            CREATE TABLE video_studio_drafts (
                id TEXT PRIMARY KEY CHECK (
                    length(id) = 36 AND substr(id, 1, 4) = 'vsd_'
                    AND id = lower(id)
                    AND substr(id, 5) NOT GLOB '*[^0-9a-f]*'
                ),
                actor_id TEXT NOT NULL,
                installation_id TEXT NOT NULL,
                app_instance_id TEXT NOT NULL CHECK (
                    length(app_instance_id) BETWEEN 1 AND 200
                ),
                action_id TEXT NOT NULL CHECK (length(action_id) BETWEEN 1 AND 120),
                draft_json TEXT NOT NULL CHECK (json_valid(draft_json)),
                first_frame_json TEXT CHECK (
                    first_frame_json IS NULL OR json_valid(first_frame_json)
                ),
                last_frame_json TEXT CHECK (
                    last_frame_json IS NULL OR json_valid(last_frame_json)
                ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX ix_video_studio_drafts_owner_updated
            ON video_studio_drafts(
                actor_id,installation_id,app_instance_id,updated_at DESC
            )
            """,
        ),
    ),
    Migration(
        version=46,
        name="imagine_studio_durable_history",
        statements=(
            """
            CREATE TABLE imagine_studio_results (
                id TEXT PRIMARY KEY CHECK (
                    length(id) = 36 AND substr(id, 1, 4) = 'isr_'
                    AND id = lower(id)
                    AND substr(id, 5) NOT GLOB '*[^0-9a-f]*'
                ),
                actor_id TEXT NOT NULL,
                installation_id TEXT NOT NULL,
                app_instance_id TEXT NOT NULL CHECK (length(app_instance_id) BETWEEN 1 AND 200),
                pipeline_id TEXT NOT NULL CHECK (length(pipeline_id) BETWEEN 1 AND 120),
                title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
                prompt TEXT NOT NULL CHECK (length(prompt) <= 32000),
                model_id TEXT NOT NULL CHECK (length(model_id) BETWEEN 1 AND 255),
                model_label TEXT NOT NULL CHECK (length(model_label) BETWEEN 1 AND 120),
                image_size TEXT NOT NULL CHECK (length(image_size) BETWEEN 1 AND 40),
                quality TEXT NOT NULL CHECK (length(quality) BETWEEN 1 AND 40),
                output_format TEXT NOT NULL CHECK (length(output_format) BETWEEN 1 AND 20),
                filename TEXT NOT NULL CHECK (length(filename) BETWEEN 1 AND 255),
                media_type TEXT NOT NULL CHECK (media_type IN ('image/png','image/jpeg','image/webp')),
                size_bytes INTEGER NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 67108864),
                relative_path TEXT NOT NULL CHECK (length(relative_path) BETWEEN 1 AND 255),
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX ix_imagine_studio_results_owner_created
            ON imagine_studio_results(actor_id,installation_id,app_instance_id,created_at DESC,id DESC)
            """,
        ),
    ),
    Migration(
        version=47,
        name="readaloud_voice_reference_assets",
        statements=(
            """
            ALTER TABLE readaloud_voice_profiles
            ADD COLUMN reference_asset_id TEXT
            """,
            """
            CREATE INDEX ix_readaloud_voice_profiles_reference_asset
            ON readaloud_voice_profiles(owner_user_id, reference_asset_id)
            """,
        ),
    ),
    Migration(
        version=48,
        name="system_knowledge_core",
        statements=(
            """
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
            )
            """,
            """
            CREATE UNIQUE INDEX uq_knowledge_private_space
            ON knowledge_spaces(installation_id, owner_user_id)
            WHERE kind = 'private'
            """,
            """
            CREATE UNIQUE INDEX uq_knowledge_installation_space
            ON knowledge_spaces(installation_id) WHERE kind = 'installation'
            """,
            """
            CREATE TABLE knowledge_items (
                id TEXT PRIMARY KEY,
                space_id TEXT NOT NULL REFERENCES knowledge_spaces(id) ON DELETE RESTRICT,
                installation_id TEXT NOT NULL,
                owner_user_id TEXT NOT NULL,
                created_by_user_id TEXT NOT NULL,
                visibility TEXT NOT NULL CHECK (visibility IN ('private', 'installation')),
                kind TEXT NOT NULL CHECK (kind IN (
                    'webpage','document','image','audio','video','chat','artifact','note'
                )),
                title TEXT NOT NULL,
                source_time TEXT,
                source_app_id TEXT,
                source_session_id TEXT,
                source_url TEXT,
                status TEXT NOT NULL CHECK (status IN (
                    'pending','ready','partial','failed','deleted'
                )),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT
            )
            """,
            """
            CREATE INDEX idx_knowledge_items_visible
            ON knowledge_items(
                installation_id, visibility, owner_user_id, updated_at DESC
            )
            """,
            """
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
            )
            """,
            """
            CREATE TABLE knowledge_chunks (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                representation_id TEXT NOT NULL
                    REFERENCES knowledge_representations(id) ON DELETE RESTRICT,
                item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE RESTRICT,
                space_id TEXT NOT NULL REFERENCES knowledge_spaces(id) ON DELETE RESTRICT,
                ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(representation_id, ordinal)
            )
            """,
            """
            CREATE VIRTUAL TABLE knowledge_fts USING fts5(
                title, text, tokenize='unicode61 remove_diacritics 2'
            )
            """,
            """
            CREATE TRIGGER knowledge_chunks_ai AFTER INSERT ON knowledge_chunks BEGIN
                INSERT INTO knowledge_fts(rowid, title, text)
                SELECT new.rowid, i.title, new.text
                FROM knowledge_items i WHERE i.id = new.item_id;
            END
            """,
            """
            CREATE TRIGGER knowledge_chunks_ad AFTER DELETE ON knowledge_chunks BEGIN
                INSERT INTO knowledge_fts(knowledge_fts, rowid, title, text)
                SELECT 'delete', old.rowid, i.title, old.text
                FROM knowledge_items i WHERE i.id = old.item_id;
            END
            """,
            """
            CREATE TRIGGER knowledge_chunks_au AFTER UPDATE ON knowledge_chunks BEGIN
                INSERT INTO knowledge_fts(knowledge_fts, rowid, title, text)
                SELECT 'delete', old.rowid, i.title, old.text
                FROM knowledge_items i WHERE i.id = old.item_id;
                INSERT INTO knowledge_fts(rowid, title, text)
                SELECT new.rowid, i.title, new.text
                FROM knowledge_items i WHERE i.id = new.item_id;
            END
            """,
            """
            CREATE TABLE knowledge_source_facets (
                item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE RESTRICT,
                facet_key TEXT NOT NULL,
                value TEXT NOT NULL,
                authority TEXT NOT NULL CHECK (authority = 'runtime'),
                created_at TEXT NOT NULL,
                PRIMARY KEY(item_id, facet_key, value)
            )
            """,
            """
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
                UNIQUE(
                    installation_id, namespace, owner_user_id,
                    visibility, normalized_key
                )
            )
            """,
            """
            CREATE TABLE knowledge_item_tags (
                item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE RESTRICT,
                tag_id TEXT NOT NULL REFERENCES knowledge_tags(id) ON DELETE RESTRICT,
                assignment_source TEXT NOT NULL CHECK (assignment_source = 'user'),
                status TEXT NOT NULL CHECK (status IN ('active', 'rejected')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(item_id, tag_id)
            )
            """,
            """
            CREATE TABLE knowledge_change_log (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL CHECK (operation IN ('create', 'update', 'delete')),
                item_id TEXT NOT NULL,
                space_id TEXT NOT NULL,
                authoritative_revision INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE knowledge_settings (
                installation_id TEXT PRIMARY KEY,
                budget_bytes INTEGER NOT NULL DEFAULT 10737418240
                    CHECK (budget_bytes > 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        ),
    ),
    Migration(
        version=49,
        name="knowledge_buckets_assets_and_context",
        statements=(
            """
            CREATE TABLE knowledge_buckets (
                id TEXT PRIMARY KEY,
                installation_id TEXT NOT NULL,
                owner_user_id TEXT,
                created_by_user_id TEXT NOT NULL,
                visibility TEXT NOT NULL CHECK (
                    visibility IN ('private', 'installation')
                ),
                name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
                kind TEXT NOT NULL CHECK (kind IN ('system', 'custom', 'imported')),
                system_key TEXT CHECK (system_key IN (
                    'inbox', 'web', 'documents', 'chats', 'shared'
                )),
                metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK (
                    (visibility = 'private' AND owner_user_id IS NOT NULL)
                    OR
                    (visibility = 'installation' AND owner_user_id IS NULL)
                ),
                CHECK (
                    (kind = 'system' AND system_key IS NOT NULL)
                    OR
                    (kind != 'system' AND system_key IS NULL)
                )
            )
            """,
            """
            CREATE UNIQUE INDEX uq_knowledge_private_system_bucket
            ON knowledge_buckets(installation_id, owner_user_id, system_key)
            WHERE visibility = 'private' AND system_key IS NOT NULL
            """,
            """
            CREATE UNIQUE INDEX uq_knowledge_shared_system_bucket
            ON knowledge_buckets(installation_id, system_key)
            WHERE visibility = 'installation' AND system_key IS NOT NULL
            """,
            """
            CREATE INDEX ix_knowledge_buckets_owner
            ON knowledge_buckets(
                installation_id, visibility, owner_user_id, kind, created_at
            )
            """,
            """
            CREATE TABLE knowledge_bucket_items (
                bucket_id TEXT NOT NULL REFERENCES knowledge_buckets(id) ON DELETE CASCADE,
                item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
                position INTEGER NOT NULL CHECK (position >= 0),
                added_at TEXT NOT NULL,
                PRIMARY KEY(bucket_id, item_id)
            )
            """,
            """
            CREATE INDEX ix_knowledge_bucket_items_order
            ON knowledge_bucket_items(bucket_id, position, added_at, item_id)
            """,
            """
            CREATE TRIGGER knowledge_bucket_item_scope_insert
            BEFORE INSERT ON knowledge_bucket_items
            WHEN NOT EXISTS (
                SELECT 1 FROM knowledge_buckets b
                JOIN knowledge_items i ON i.id = NEW.item_id
                WHERE b.id = NEW.bucket_id
                  AND b.installation_id = i.installation_id
                  AND b.visibility = i.visibility
                  AND (
                    b.visibility = 'installation'
                    OR b.owner_user_id = i.owner_user_id
                  )
            )
            BEGIN
                SELECT RAISE(ABORT, 'knowledge bucket and item scopes differ');
            END
            """,
            """
            CREATE TABLE knowledge_assets (
                id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL UNIQUE
                    REFERENCES knowledge_items(id) ON DELETE CASCADE,
                filename TEXT NOT NULL CHECK (length(filename) BETWEEN 1 AND 512),
                media_type TEXT NOT NULL CHECK (length(media_type) BETWEEN 1 AND 255),
                content_hash TEXT NOT NULL CHECK (
                    length(content_hash) = 71 AND substr(content_hash, 1, 7) = 'sha256:'
                ),
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                storage_key TEXT NOT NULL CHECK (length(storage_key) > 0),
                parser TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX ix_knowledge_assets_content
            ON knowledge_assets(content_hash, storage_key)
            """,
            """
            CREATE TABLE knowledge_context_buckets (
                installation_id TEXT NOT NULL,
                actor_user_id TEXT NOT NULL,
                consumer_app_id TEXT NOT NULL,
                bucket_id TEXT NOT NULL REFERENCES knowledge_buckets(id) ON DELETE CASCADE,
                enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                updated_at TEXT NOT NULL,
                PRIMARY KEY(installation_id, actor_user_id, consumer_app_id, bucket_id)
            )
            """,
            """
            CREATE INDEX ix_knowledge_context_consumer
            ON knowledge_context_buckets(
                installation_id, actor_user_id, consumer_app_id, enabled
            )
            """,
            """
            CREATE TRIGGER knowledge_context_bucket_visibility_insert
            BEFORE INSERT ON knowledge_context_buckets
            WHEN NOT EXISTS (
                SELECT 1 FROM knowledge_buckets b
                WHERE b.id = NEW.bucket_id
                  AND b.installation_id = NEW.installation_id
                  AND (
                    b.visibility = 'installation'
                    OR b.owner_user_id = NEW.actor_user_id
                  )
            )
            BEGIN
                SELECT RAISE(ABORT, 'knowledge context bucket is not visible');
            END
            """,
        ),
    ),
    Migration(
        version=50,
        name="knowledge_p0_context_and_index_state",
        statements=(
            """
            CREATE TABLE knowledge_session_contexts (
                installation_id TEXT NOT NULL,
                actor_user_id TEXT NOT NULL,
                consumer_app_id TEXT NOT NULL,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(
                    installation_id, actor_user_id, consumer_app_id, session_id
                )
            )
            """,
            """
            CREATE TRIGGER knowledge_session_context_owner_insert
            BEFORE INSERT ON knowledge_session_contexts
            WHEN NOT EXISTS (
                SELECT 1 FROM sessions s
                JOIN app_instances i ON i.id=s.app_instance_id
                JOIN app_definitions d ON d.id=i.app_definition_id
                WHERE s.id=NEW.session_id
                  AND s.status='active'
                  AND i.owner_user_id=NEW.actor_user_id
                  AND d.package_id=NEW.consumer_app_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'knowledge session context is not owned by actor');
            END
            """,
            """
            CREATE TABLE knowledge_session_context_buckets (
                installation_id TEXT NOT NULL,
                actor_user_id TEXT NOT NULL,
                consumer_app_id TEXT NOT NULL,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                bucket_id TEXT NOT NULL
                    REFERENCES knowledge_buckets(id) ON DELETE CASCADE,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(
                    installation_id, actor_user_id, consumer_app_id,
                    session_id, bucket_id
                ),
                FOREIGN KEY(
                    installation_id, actor_user_id, consumer_app_id, session_id
                ) REFERENCES knowledge_session_contexts(
                    installation_id, actor_user_id, consumer_app_id, session_id
                ) ON DELETE CASCADE
            )
            """,
            """
            CREATE INDEX ix_knowledge_session_context
            ON knowledge_session_context_buckets(
                installation_id, actor_user_id, consumer_app_id, session_id
            )
            """,
            """
            CREATE TRIGGER knowledge_session_context_bucket_visibility_insert
            BEFORE INSERT ON knowledge_session_context_buckets
            WHEN NOT EXISTS (
                SELECT 1 FROM knowledge_buckets b
                WHERE b.id=NEW.bucket_id
                  AND b.installation_id=NEW.installation_id
                  AND (
                    b.visibility='installation'
                    OR b.owner_user_id=NEW.actor_user_id
                  )
            )
            BEGIN
                SELECT RAISE(ABORT, 'knowledge session bucket is not visible');
            END
            """,
            """
            CREATE TABLE knowledge_index_states (
                profile_id TEXT PRIMARY KEY,
                generation TEXT NOT NULL,
                sequence INTEGER NOT NULL DEFAULT 0 CHECK (sequence >= 0),
                target_sequence INTEGER NOT NULL DEFAULT 0
                    CHECK (target_sequence >= 0),
                status TEXT NOT NULL DEFAULT 'idle'
                    CHECK (status IN ('idle', 'indexing', 'ready', 'error')),
                processed_changes INTEGER NOT NULL DEFAULT 0
                    CHECK (processed_changes >= 0),
                indexed_chunks INTEGER NOT NULL DEFAULT 0
                    CHECK (indexed_chunks >= 0),
                last_error TEXT,
                started_at TEXT,
                completed_at TEXT,
                updated_at TEXT NOT NULL
            )
            """,
        ),
    ),
    Migration(
        version=51,
        name="knowledge_p1_ask_ingestion_and_citations",
        statements=(
            """
            ALTER TABLE knowledge_chunks
            ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'
                CHECK (json_valid(metadata_json))
            """,
            """
            CREATE TABLE knowledge_import_jobs (
                id TEXT PRIMARY KEY,
                installation_id TEXT NOT NULL,
                actor_user_id TEXT NOT NULL,
                bucket_id TEXT NOT NULL
                    REFERENCES knowledge_buckets(id) ON DELETE CASCADE,
                source_app_id TEXT,
                status TEXT NOT NULL
                    CHECK (status IN ('queued','running','completed','partial','failed')),
                total_files INTEGER NOT NULL CHECK (total_files > 0),
                completed_files INTEGER NOT NULL DEFAULT 0
                    CHECK (completed_files >= 0),
                failed_files INTEGER NOT NULL DEFAULT 0
                    CHECK (failed_files >= 0),
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE knowledge_import_job_entries (
                job_id TEXT NOT NULL
                    REFERENCES knowledge_import_jobs(id) ON DELETE CASCADE,
                ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
                filename TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK (status IN ('queued','running','completed','failed')),
                item_id TEXT REFERENCES knowledge_items(id) ON DELETE SET NULL,
                error TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(job_id, ordinal)
            )
            """,
            """
            CREATE INDEX ix_knowledge_import_jobs_owner
            ON knowledge_import_jobs(
                installation_id, actor_user_id, created_at DESC
            )
            """,
        ),
    ),
    Migration(
        version=52,
        name="knowledge_recoverable_import_staging",
        statements=(
            "ALTER TABLE knowledge_import_job_entries ADD COLUMN media_type TEXT",
            "ALTER TABLE knowledge_import_job_entries ADD COLUMN size_bytes INTEGER CHECK (size_bytes IS NULL OR size_bytes >= 0)",
            "ALTER TABLE knowledge_import_job_entries ADD COLUMN content_hash TEXT",
            "ALTER TABLE knowledge_import_job_entries ADD COLUMN staging_key TEXT",
            "ALTER TABLE knowledge_import_job_entries ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0)",
            """
            CREATE INDEX ix_knowledge_import_entries_status
            ON knowledge_import_job_entries(status, updated_at, job_id, ordinal)
            """,
        ),
    ),
    Migration(
        version=53,
        name="knowledge_import_job_controls",
        statements=(
            """
            ALTER TABLE knowledge_import_jobs
            ADD COLUMN control_state TEXT NOT NULL DEFAULT 'active'
                CHECK (control_state IN ('active','paused','cancelled'))
            """,
            """
            ALTER TABLE knowledge_import_jobs
            ADD COLUMN control_updated_at TEXT
            """,
            """
            CREATE INDEX ix_knowledge_import_jobs_control
            ON knowledge_import_jobs(control_state, status, updated_at)
            """,
        ),
    ),
    Migration(
        version=54,
        name="knowledge_tag_suggestion_lifecycle",
        statements=(
            """
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
            )
            """,
            """
            CREATE INDEX ix_knowledge_tag_suggestions_actor
            ON knowledge_tag_suggestions(
                installation_id, actor_user_id, status, updated_at DESC
            )
            """,
        ),
    ),
    Migration(
        version=55,
        name="worker_management_operations_and_preferences",
        statements=(
            """
            CREATE TABLE worker_preferences (
                service_key TEXT PRIMARY KEY,
                pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1)),
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE worker_operations (
                id TEXT PRIMARY KEY,
                service_key TEXT NOT NULL,
                action TEXT NOT NULL CHECK (action IN (
                    'load','exit','drain_and_exit','pin','unpin','evict'
                )),
                status TEXT NOT NULL CHECK (status IN (
                    'pending','running','completed','failed','interrupted'
                )),
                expected_generation INTEGER CHECK (
                    expected_generation IS NULL OR expected_generation >= 0
                ),
                idempotency_key TEXT,
                result_json TEXT CHECK (
                    result_json IS NULL OR json_valid(result_json)
                ),
                error_json TEXT CHECK (
                    error_json IS NULL OR json_valid(error_json)
                ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            )
            """,
            """
            CREATE INDEX ix_worker_operations_service
            ON worker_operations(service_key, created_at DESC)
            """,
            """
            CREATE UNIQUE INDEX ux_worker_operations_idempotency
            ON worker_operations(service_key, action, idempotency_key)
            WHERE idempotency_key IS NOT NULL
            """,
        ),
    ),
    Migration(
        version=56,
        name="readaloud_durable_render_jobs",
        statements=(
            """
            CREATE TABLE readaloud_render_jobs (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                project_id TEXT NOT NULL REFERENCES readaloud_projects(id) ON DELETE CASCADE,
                project_revision INTEGER NOT NULL CHECK (project_revision > 0),
                model_id TEXT NOT NULL CHECK (length(model_id) BETWEEN 1 AND 255),
                status TEXT NOT NULL CHECK (
                    status IN ('queued','running','succeeded','failed','cancelled')
                ),
                total_segments INTEGER NOT NULL CHECK (total_segments > 0),
                completed_segments INTEGER NOT NULL DEFAULT 0 CHECK (
                    completed_segments >= 0 AND completed_segments <= total_segments
                ),
                error_json TEXT CHECK (error_json IS NULL OR json_valid(error_json)),
                cancel_requested_at TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            )
            """,
            """
            CREATE INDEX ix_readaloud_render_jobs_owner_created
            ON readaloud_render_jobs(owner_user_id, created_at DESC, id DESC)
            """,
            """
            CREATE TABLE readaloud_render_segments (
                job_id TEXT NOT NULL REFERENCES readaloud_render_jobs(id) ON DELETE CASCADE,
                segment_id TEXT NOT NULL REFERENCES readaloud_segments(id) ON DELETE RESTRICT,
                ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
                status TEXT NOT NULL CHECK (
                    status IN ('queued','running','succeeded','failed','cancelled')
                ),
                request_json TEXT NOT NULL CHECK (json_valid(request_json)),
                output_path TEXT,
                error_json TEXT CHECK (error_json IS NULL OR json_valid(error_json)),
                started_at TEXT,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                PRIMARY KEY (job_id, segment_id),
                UNIQUE (job_id, ordinal)
            )
            """,
            """
            CREATE INDEX ix_readaloud_render_segments_job_order
            ON readaloud_render_segments(job_id, ordinal)
            """,
        ),
    ),
    Migration(
        version=57,
        name="worker_operation_cancellation",
        statements=(
            "ALTER TABLE worker_operations RENAME TO worker_operations_v56",
            """
            CREATE TABLE worker_operations (
                id TEXT PRIMARY KEY,
                service_key TEXT NOT NULL,
                action TEXT NOT NULL CHECK (action IN (
                    'load','exit','drain_and_exit','pin','unpin','evict'
                )),
                status TEXT NOT NULL CHECK (status IN (
                    'pending','running','completed','failed','interrupted','cancelled'
                )),
                expected_generation INTEGER CHECK (
                    expected_generation IS NULL OR expected_generation >= 0
                ),
                idempotency_key TEXT,
                result_json TEXT CHECK (
                    result_json IS NULL OR json_valid(result_json)
                ),
                error_json TEXT CHECK (
                    error_json IS NULL OR json_valid(error_json)
                ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            )
            """,
            """
            INSERT INTO worker_operations(
                id,service_key,action,status,expected_generation,idempotency_key,
                result_json,error_json,created_at,updated_at,completed_at
            ) SELECT
                id,service_key,action,status,expected_generation,idempotency_key,
                result_json,error_json,created_at,updated_at,completed_at
            FROM worker_operations_v56
            """,
            "DROP TABLE worker_operations_v56",
            """
            CREATE INDEX ix_worker_operations_service
            ON worker_operations(service_key, created_at DESC)
            """,
            """
            CREATE UNIQUE INDEX ux_worker_operations_idempotency
            ON worker_operations(service_key, action, idempotency_key)
            WHERE idempotency_key IS NOT NULL
            """,
        ),
    ),
    Migration(
        version=58,
        name="browser_agent_builder_drafts",
        statements=(
            """
            CREATE TABLE agent_drafts (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 160),
                description TEXT NOT NULL DEFAULT '',
                site_scope_json TEXT NOT NULL DEFAULT '[]'
                    CHECK (
                        json_valid(site_scope_json)
                        AND json_type(site_scope_json) = 'array'
                    ),
                source_json TEXT NOT NULL CHECK (
                    json_valid(source_json)
                    AND json_type(source_json) = 'object'
                ),
                status TEXT NOT NULL DEFAULT 'editing'
                    CHECK (status IN ('editing','compiled','active','archived')),
                active_generation_id TEXT,
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX ix_agent_drafts_owner_updated
            ON agent_drafts(owner_user_id, updated_at DESC, id)
            """,
            """
            CREATE TABLE agent_compile_generations (
                id TEXT PRIMARY KEY,
                draft_id TEXT NOT NULL REFERENCES agent_drafts(id) ON DELETE CASCADE,
                source_revision INTEGER NOT NULL CHECK (source_revision >= 1),
                source_digest TEXT NOT NULL,
                compiler_version TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                ir_json TEXT NOT NULL CHECK (
                    json_valid(ir_json) AND json_type(ir_json) = 'object'
                ),
                report_json TEXT NOT NULL CHECK (
                    json_valid(report_json) AND json_type(report_json) = 'object'
                ),
                status TEXT NOT NULL CHECK (
                    status IN ('candidate','validated','active','failed')
                ),
                created_at TEXT NOT NULL,
                activated_at TEXT
            )
            """,
            """
            CREATE INDEX ix_agent_compile_generations_draft
            ON agent_compile_generations(draft_id, created_at DESC, id)
            """,
            """
            CREATE TABLE agent_step_evidence (
                id TEXT PRIMARY KEY,
                draft_id TEXT NOT NULL REFERENCES agent_drafts(id) ON DELETE CASCADE,
                generation_id TEXT REFERENCES agent_compile_generations(id) ON DELETE SET NULL,
                run_id TEXT REFERENCES agent_runs(id) ON DELETE SET NULL,
                step_name TEXT NOT NULL,
                page_fingerprint TEXT NOT NULL DEFAULT '',
                outcome TEXT NOT NULL CHECK (
                    outcome IN ('success','not_found','retryable_error',
                                'needs_user','restricted','failed')
                ),
                evidence_json TEXT NOT NULL CHECK (
                    json_valid(evidence_json) AND json_type(evidence_json) = 'object'
                ),
                user_feedback TEXT,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX ix_agent_step_evidence_draft_step
            ON agent_step_evidence(draft_id, step_name, created_at DESC)
            """,
        ),
    ),
    Migration(
        version=59,
        name="universal_agent_workflows_schedules",
        statements=(
            """
            ALTER TABLE agent_drafts ADD COLUMN agent_type TEXT NOT NULL
                DEFAULT 'web' CHECK (agent_type IN (
                    'web','workflow','knowledge','research','coding','app','composite'
                ))
            """,
            """
            CREATE INDEX ix_agent_drafts_owner_type_updated
            ON agent_drafts(owner_user_id, agent_type, updated_at DESC, id)
            """,
            """
            CREATE TABLE agent_workflows (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 160),
                description TEXT NOT NULL DEFAULT '',
                definition_json TEXT NOT NULL CHECK (
                    json_valid(definition_json)
                    AND json_type(definition_json) = 'object'
                ),
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','archived')),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX ix_agent_workflows_owner_updated
            ON agent_workflows(owner_user_id, updated_at DESC, id)
            """,
            """
            CREATE TABLE agent_schedules (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                draft_id TEXT REFERENCES agent_drafts(id) ON DELETE CASCADE,
                workflow_id TEXT REFERENCES agent_workflows(id) ON DELETE CASCADE,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 160),
                kind TEXT NOT NULL CHECK (kind IN ('once','interval')),
                status TEXT NOT NULL DEFAULT 'enabled'
                    CHECK (status IN ('enabled','paused','completed')),
                input_json TEXT NOT NULL DEFAULT '{}' CHECK (
                    json_valid(input_json) AND json_type(input_json) = 'object'
                ),
                knowledge_bucket_id TEXT,
                interval_seconds INTEGER CHECK (
                    interval_seconds IS NULL OR interval_seconds >= 60
                ),
                run_at TEXT,
                next_run_at TEXT,
                last_run_at TEXT,
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK ((draft_id IS NOT NULL) != (workflow_id IS NOT NULL)),
                CHECK (
                    (kind='once' AND run_at IS NOT NULL AND interval_seconds IS NULL)
                    OR
                    (kind='interval' AND interval_seconds IS NOT NULL)
                )
            )
            """,
            """
            CREATE INDEX ix_agent_schedules_due
            ON agent_schedules(status, next_run_at, id)
            """,
            """
            CREATE INDEX ix_agent_schedules_owner_updated
            ON agent_schedules(owner_user_id, updated_at DESC, id)
            """,
            """
            CREATE TABLE agent_schedule_dispatches (
                id TEXT PRIMARY KEY,
                schedule_id TEXT NOT NULL REFERENCES agent_schedules(id)
                    ON DELETE CASCADE,
                run_id TEXT REFERENCES agent_runs(id) ON DELETE SET NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('claimed','dispatched','failed','completed')
                ),
                error_json TEXT CHECK (
                    error_json IS NULL OR json_valid(error_json)
                ),
                dispatched_at TEXT NOT NULL,
                completed_at TEXT
            )
            """,
            """
            CREATE INDEX ix_agent_schedule_dispatches_schedule
            ON agent_schedule_dispatches(schedule_id, dispatched_at DESC, id)
            """,
        ),
    ),
    Migration(
        version=60,
        name="repair_legacy_agent_active_generation",
        statements=(
            """
            UPDATE agent_drafts
            SET active_generation_id=(
                    SELECT g.id FROM agent_compile_generations g
                    WHERE g.draft_id=agent_drafts.id AND g.status='active'
                    ORDER BY g.activated_at DESC,g.created_at DESC,g.id DESC LIMIT 1
                ),
                status='active'
            WHERE active_generation_id IS NULL
              AND EXISTS(
                SELECT 1 FROM agent_compile_generations g
                WHERE g.draft_id=agent_drafts.id AND g.status='active'
              )
            """,
        ),
    ),
    Migration(
        version=61,
        name="site_agents_and_temporary_recipes",
        statements=(
            "ALTER TABLE agent_drafts ADD COLUMN site_key TEXT",
            """
            CREATE INDEX ix_agent_drafts_owner_site
            ON agent_drafts(owner_user_id, site_key, updated_at DESC, id)
            """,
            """
            CREATE TABLE agent_recipes (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                site_key TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 160),
                description TEXT NOT NULL DEFAULT '',
                source_json TEXT NOT NULL CHECK (
                    json_valid(source_json) AND json_type(source_json)='object'
                ),
                page_json TEXT NOT NULL DEFAULT '{}' CHECK (
                    json_valid(page_json) AND json_type(page_json)='object'
                ),
                status TEXT NOT NULL DEFAULT 'draft' CHECK (
                    status IN ('draft','tested','committed','discarded')
                ),
                committed_draft_id TEXT REFERENCES agent_drafts(id) ON DELETE SET NULL,
                committed_capability_id TEXT,
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX ix_agent_recipes_owner_updated
            ON agent_recipes(owner_user_id, updated_at DESC, id)
            """,
        ),
    ),
    Migration(
        version=62,
        name="agent_packages_health_repair_and_site_state",
        statements=(
            """
            CREATE TABLE agent_site_package_bindings (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                package_key TEXT NOT NULL,
                package_version TEXT NOT NULL,
                package_digest TEXT NOT NULL,
                publisher_id TEXT NOT NULL,
                site_key TEXT NOT NULL,
                draft_id TEXT NOT NULL REFERENCES agent_drafts(id) ON DELETE CASCADE,
                granted_permissions_json TEXT NOT NULL DEFAULT '[]' CHECK (
                    json_valid(granted_permissions_json)
                    AND json_type(granted_permissions_json)='array'
                ),
                source_digest TEXT NOT NULL,
                hint_digest TEXT,
                status TEXT NOT NULL DEFAULT 'installed' CHECK (
                    status IN ('installed','active','retained','uninstalled','conflicted')
                ),
                installed_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(owner_user_id, package_key, package_digest)
            )
            """,
            """
            CREATE INDEX ix_agent_package_bindings_owner_site
            ON agent_site_package_bindings(owner_user_id, site_key, updated_at DESC)
            """,
            """
            CREATE TABLE agent_capability_health (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                draft_id TEXT NOT NULL REFERENCES agent_drafts(id) ON DELETE CASCADE,
                capability_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'unknown' CHECK (status IN (
                    'unknown','healthy','suspect','drifted','repairing','local_patched',
                    'needs_user','degraded','failed'
                )),
                consecutive_failures INTEGER NOT NULL DEFAULT 0 CHECK (consecutive_failures>=0),
                success_count INTEGER NOT NULL DEFAULT 0 CHECK (success_count>=0),
                failure_count INTEGER NOT NULL DEFAULT 0 CHECK (failure_count>=0),
                last_error_class TEXT,
                last_error_json TEXT CHECK (last_error_json IS NULL OR json_valid(last_error_json)),
                structure_fingerprint TEXT NOT NULL DEFAULT '',
                circuit_open_until TEXT,
                metrics_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metrics_json)),
                last_run_id TEXT REFERENCES agent_runs(id) ON DELETE SET NULL,
                last_success_at TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(owner_user_id,draft_id,capability_name)
            )
            """,
            """
            CREATE INDEX ix_agent_capability_health_status
            ON agent_capability_health(owner_user_id,status,updated_at DESC)
            """,
            """
            CREATE TABLE agent_site_states (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                draft_id TEXT NOT NULL REFERENCES agent_drafts(id) ON DELETE CASCADE,
                capability_name TEXT NOT NULL,
                source_identity TEXT NOT NULL,
                generation_id TEXT NOT NULL REFERENCES agent_compile_generations(id) ON DELETE CASCADE,
                checkpoint_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(checkpoint_json)),
                item_index_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(item_index_json)),
                structure_fingerprint TEXT NOT NULL DEFAULT '',
                calibration_status TEXT NOT NULL DEFAULT 'pending' CHECK (
                    calibration_status IN ('pending','passed','failed')
                ),
                updated_at TEXT NOT NULL,
                UNIQUE(owner_user_id,draft_id,capability_name,source_identity)
            )
            """,
            """
            CREATE TABLE agent_repair_candidates (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                draft_id TEXT NOT NULL REFERENCES agent_drafts(id) ON DELETE CASCADE,
                capability_name TEXT NOT NULL,
                base_generation_id TEXT NOT NULL REFERENCES agent_compile_generations(id) ON DELETE CASCADE,
                candidate_generation_id TEXT REFERENCES agent_compile_generations(id) ON DELETE SET NULL,
                strategy TEXT NOT NULL CHECK (strategy IN ('deterministic','lightweight','advanced','manual')),
                source_json TEXT NOT NULL CHECK (json_valid(source_json)),
                report_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(report_json)),
                status TEXT NOT NULL DEFAULT 'candidate' CHECK (
                    status IN ('candidate','validated','activated','rejected','failed')
                ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX ix_agent_repairs_draft
            ON agent_repair_candidates(draft_id,created_at DESC,id DESC)
            """,
            """
            CREATE TABLE agent_app_dependencies (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                consumer_app_id TEXT NOT NULL,
                capability_name TEXT NOT NULL,
                site_scope TEXT NOT NULL DEFAULT '',
                provider_draft_id TEXT REFERENCES agent_drafts(id) ON DELETE SET NULL,
                provider_package_key TEXT,
                version_constraint TEXT NOT NULL DEFAULT '',
                required INTEGER NOT NULL DEFAULT 1 CHECK (required IN (0,1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(owner_user_id,consumer_app_id,capability_name,site_scope)
            )
            """,
            """
            CREATE TABLE agent_run_knowledge_exports (
                run_id TEXT PRIMARY KEY REFERENCES agent_runs(id) ON DELETE CASCADE,
                knowledge_item_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            "ALTER TABLE agent_schedules ADD COLUMN installation_id TEXT NOT NULL DEFAULT 'local'",
            "ALTER TABLE agent_schedules ADD COLUMN max_concurrent_runs INTEGER NOT NULL DEFAULT 1 CHECK (max_concurrent_runs BETWEEN 1 AND 16)",
            "ALTER TABLE agent_schedules ADD COLUMN max_failures INTEGER NOT NULL DEFAULT 5 CHECK (max_failures BETWEEN 1 AND 100)",
        ),
    ),
    Migration(
        version=63,
        name="site_agent_discovery_and_version_governance",
        statements=(
            """
            ALTER TABLE agent_site_package_bindings
            ADD COLUMN source_json TEXT NOT NULL DEFAULT '{}' CHECK (
                json_valid(source_json) AND json_type(source_json)='object'
            )
            """,
            """
            ALTER TABLE agent_site_package_bindings
            ADD COLUMN update_policy TEXT NOT NULL DEFAULT 'manual' CHECK (
                update_policy IN ('manual','pinned')
            )
            """,
            """
            ALTER TABLE agent_site_package_bindings
            ADD COLUMN pinned_version TEXT
            """,
            """
            ALTER TABLE agent_site_package_bindings
            ADD COLUMN activated_at TEXT
            """,
            """
            CREATE TABLE agent_site_package_events (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                package_key TEXT NOT NULL,
                action TEXT NOT NULL CHECK (action IN (
                    'installed','candidate_created','activated','rolled_back','policy_changed'
                )),
                from_digest TEXT,
                to_digest TEXT,
                details_json TEXT NOT NULL DEFAULT '{}' CHECK (
                    json_valid(details_json) AND json_type(details_json)='object'
                ),
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX ix_agent_site_package_events_owner_package
            ON agent_site_package_events(owner_user_id,package_key,created_at DESC,id DESC)
            """,
        ),
    ),
    Migration(
        version=64,
        name="repair_knowledge_fts_delete_triggers",
        statements=(
            "DROP TRIGGER knowledge_chunks_ad",
            "DROP TRIGGER knowledge_chunks_au",
            """
            CREATE TRIGGER knowledge_chunks_ad AFTER DELETE ON knowledge_chunks BEGIN
                DELETE FROM knowledge_fts WHERE rowid = old.rowid;
            END
            """,
            """
            CREATE TRIGGER knowledge_chunks_au AFTER UPDATE ON knowledge_chunks BEGIN
                DELETE FROM knowledge_fts WHERE rowid = old.rowid;
                INSERT INTO knowledge_fts(rowid, title, text)
                SELECT new.rowid, i.title, new.text
                FROM knowledge_items i WHERE i.id = new.item_id;
            END
            """,
        ),
    ),
    Migration(
        version=65,
        name="user_browser_profiles",
        statements=(
            """
            CREATE TABLE browser_profiles (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                profile_key TEXT NOT NULL CHECK (
                    length(profile_key)=32 AND profile_key NOT GLOB '*[^0-9a-f]*'
                ),
                name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(owner_user_id, profile_key)
            )
            """,
            """
            CREATE INDEX ix_browser_profiles_owner_created
            ON browser_profiles(owner_user_id, created_at, id)
            """,
        ),
    ),
    Migration(
        version=66,
        name="peer_core_and_model_share_ledgers",
        statements=(
            """
            CREATE TABLE peer_sessions (
                session_id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                protocol TEXT NOT NULL CHECK (protocol IN ('messager-v2','model-share-v1','checkpoint-v1')),
                purpose_type TEXT NOT NULL CHECK (purpose_type IN ('conversation','compute_contract','checkpoint_distribution')),
                purpose_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending','active','closed','expired','revoked')),
                expires_at TEXT NOT NULL,
                self_user_id TEXT NOT NULL,
                self_device_id TEXT NOT NULL,
                self_installation_id TEXT NOT NULL,
                self_access_epoch INTEGER NOT NULL CHECK (self_access_epoch >= 1),
                self_key_id TEXT NOT NULL,
                self_key_epoch INTEGER NOT NULL CHECK (self_key_epoch >= 1),
                peer_user_id TEXT NOT NULL,
                peer_device_id TEXT NOT NULL,
                peer_installation_id TEXT NOT NULL,
                peer_access_epoch INTEGER NOT NULL CHECK (peer_access_epoch >= 1),
                peer_key_id TEXT NOT NULL,
                peer_key_epoch INTEGER NOT NULL CHECK (peer_key_epoch >= 1),
                allowed_transports TEXT NOT NULL CHECK (allowed_transports IN ('direct_quic','relay_https','direct_quic,relay_https')),
                max_bytes TEXT NOT NULL CHECK (max_bytes GLOB '[1-9]*' AND max_bytes NOT GLOB '*[^0-9]*'),
                max_streams INTEGER NOT NULL CHECK (max_streams >= 1),
                policy_version INTEGER NOT NULL CHECK (policy_version >= 1),
                fallback_policy TEXT NOT NULL CHECK (fallback_policy IN ('offline_system_message','rematch_or_fail')),
                updated_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX ix_peer_sessions_owner_status ON peer_sessions(owner_user_id,status,expires_at)",
            """
            CREATE TABLE peer_replay_tokens (
                jti_digest TEXT PRIMARY KEY CHECK (length(jti_digest)=64 AND jti_digest NOT GLOB '*[^0-9a-f]*'),
                session_id TEXT NOT NULL REFERENCES peer_sessions(session_id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL,
                consumed_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX ix_peer_replay_expiry ON peer_replay_tokens(expires_at)",
            """
            CREATE TABLE model_share_jobs (
                contract_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES peer_sessions(session_id) ON DELETE RESTRICT,
                owner_user_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('buyer','provider')),
                status TEXT NOT NULL CHECK (status IN ('accepted','running','result_committed','completed','result_unknown','failed')),
                request_digest TEXT NOT NULL CHECK (length(request_digest)=64 AND request_digest NOT GLOB '*[^0-9a-f]*'),
                result_digest TEXT CHECK (result_digest IS NULL OR (length(result_digest)=64 AND result_digest NOT GLOB '*[^0-9a-f]*')),
                input_tokens INTEGER CHECK (input_tokens IS NULL OR input_tokens >= 0),
                output_tokens INTEGER CHECK (output_tokens IS NULL OR output_tokens >= 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX ix_model_share_jobs_owner_status ON model_share_jobs(owner_user_id,status,updated_at DESC)",
        ),
    ),
    Migration(
        version=67,
        name="model_share_provider_preferences",
        statements=(
            """
            CREATE TABLE model_share_device_preferences (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1)),
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE model_share_model_preferences (
                model_id TEXT PRIMARY KEY,
                service_key TEXT NOT NULL,
                model_revision TEXT NOT NULL CHECK (
                    length(model_revision) BETWEEN 40 AND 64
                    AND model_revision NOT GLOB '*[^0-9a-f]*'
                ),
                runtime TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1)),
                rate_card_id TEXT NOT NULL,
                rate_card_version TEXT NOT NULL,
                max_concurrency INTEGER NOT NULL DEFAULT 1 CHECK (
                    max_concurrency BETWEEN 1 AND 32
                ),
                estimated_tokens_per_second INTEGER NOT NULL DEFAULT 1 CHECK (
                    estimated_tokens_per_second >= 1
                ),
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX ix_model_share_model_preferences_enabled
            ON model_share_model_preferences(enabled, service_key, model_id)
            """,
        ),
    ),
    Migration(
        version=68,
        name="durable_registry_install_continuations",
        statements=(
            """
            CREATE TABLE registry_install_continuations (
                actor_id TEXT NOT NULL,
                installation_id TEXT NOT NULL,
                package_id TEXT NOT NULL CHECK (
                    length(package_id) BETWEEN 3 AND 200
                    AND instr(package_id, '/') > 1
                ),
                package_version TEXT,
                approve_review INTEGER NOT NULL DEFAULT 0 CHECK (
                    approve_review IN (0, 1)
                ),
                dependency_json TEXT NOT NULL DEFAULT '{}' CHECK (
                    json_valid(dependency_json)
                ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(actor_id, installation_id)
            )
            """,
        ),
    ),
    Migration(
        version=69,
        name="model_share_multimodal_pricing_projection",
        statements=(
            "ALTER TABLE model_share_jobs ADD COLUMN calculator_type TEXT",
            "ALTER TABLE model_share_jobs ADD COLUMN maximum_charge_minor TEXT",
            "ALTER TABLE model_share_jobs ADD COLUMN actual_usage_json TEXT",
            "ALTER TABLE model_share_jobs ADD COLUMN charged_minor TEXT",
            "ALTER TABLE model_share_jobs ADD COLUMN released_minor TEXT",
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
