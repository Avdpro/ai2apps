# SPDX-License-Identifier: Apache-2.0
"""Migration and lifecycle tests for the AI2Apps platform database."""

from __future__ import annotations

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai2apps.config import PLATFORM_DATABASE_SCHEMA_VERSION, PlatformConfig
from ai2apps.core import AppInstanceMode, SessionRetention, SessionStatus
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.storage import (
    DatabaseCorruptionError,
    DatabaseDiagnostics,
    FutureSchemaError,
    PlatformDatabase,
)
from ai2apps.storage.migrations import MIGRATIONS, Migration, apply_migrations
from ai2apps.storage.repositories import AppRepository, SessionRepository


def test_database_bootstrap_creates_current_platform_schema(tmp_path):
    database_path = tmp_path / "platform" / "ai2apps-platform.sqlite3"
    database = PlatformDatabase(database_path)

    state = database.initialize()

    assert state.path == database_path.resolve()
    assert state.schema_version == PLATFORM_DATABASE_SCHEMA_VERSION
    assert state.journal_mode == "wal"
    with database.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        ledger = connection.execute(
            "SELECT version, name, applied_at FROM schema_migrations"
        ).fetchall()
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5_000
        assert (
            connection.execute("PRAGMA user_version").fetchone()[0]
            == PLATFORM_DATABASE_SCHEMA_VERSION
        )

    assert tables == {
        "app_definitions",
        "app_instances",
        "chat_collections",
        "chat_thread_entries",
        "events",
        "message_parts",
        "messages",
        "schema_migrations",
        "sessions",
        "service_dependencies",
        "service_descriptors",
        "service_instances",
        "tool_descriptors",
        "tool_invocations",
        "agent_concurrency_groups",
        "agent_definitions",
        "agent_interactions",
        "agent_runs",
        "agent_delegations",
        "agent_status_lines",
        "run_steps",
        "capability_policies",
        "grant_leases",
        "capability_decisions",
        "session_sandboxes",
        "resource_handles",
        "artifacts",
        "artifact_exports",
        "process_executions",
        "process_log_chunks",
        "host_broker_requests",
        "publisher_trust",
        "service_packages",
        "service_package_files",
        "package_attestations",
        "service_dependency_locks",
        "service_operations",
        "service_logs",
        "managed_service_processes",
        "interactive_packages",
        "local_patches",
        "effective_definitions",
        "app_mounts",
        "app_state_snapshots",
        "interactive_operations",
        "safe_mode_state",
        "safe_mode_patch_states",
        "capability_requests",
        "coder_projects",
        "coder_threads",
        "document_blobs",
        "attachments",
        "document_blocks",
        "secret_records",
        "remote_client_devices",
    }
    assert [(row[0], row[1]) for row in ledger] == [
        (1, "platform_bootstrap"),
        (2, "apps_sessions_messages_events"),
        (3, "generic_session_classification"),
        (4, "temporary_session_retention"),
        (5, "singleton_chat_collection"),
        (6, "service_and_tool_registry"),
        (7, "asynchronous_agent_runtime"),
        (8, "capability_policy_and_grant_leases"),
        (9, "workspace_resources_and_artifacts"),
        (10, "sandboxed_process_service"),
        (11, "trusted_service_packages"),
        (12, "installable_agents_apps_and_local_patches"),
        (13, "app_mount_context"),
        (14, "unified_capability_requests"),
        (15, "durable_tool_invocations"),
        (16, "pausable_agent_runs"),
        (17, "agent_run_delegation"),
        (18, "coder_projects_and_threads"),
        (19, "durable_attachments_and_documents"),
        (20, "keychain_secret_metadata"),
        (21, "mobile_app_mounts"),
        (22, "remote_client_devices"),
    ]
    assert all(row[2].endswith("Z") for row in ledger)


def test_database_bootstrap_is_idempotent(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    with database.connect() as connection:
        first_rows = connection.execute(
            "SELECT version, applied_at FROM schema_migrations ORDER BY version"
        ).fetchall()

    database.initialize()

    with database.connect() as connection:
        rows = connection.execute(
            "SELECT version, applied_at FROM schema_migrations"
        ).fetchall()
    assert rows == first_rows


def test_schema_v1_upgrades_to_current_without_rewriting_ledger(tmp_path):
    database_path = tmp_path / "upgrade.sqlite3"
    connection = sqlite3.connect(database_path, isolation_level=None)
    apply_migrations(
        connection,
        (Migration(version=1, name="platform_bootstrap"),),
    )
    first_applied_at = connection.execute(
        "SELECT applied_at FROM schema_migrations WHERE version = 1"
    ).fetchone()[0]
    connection.close()

    state = PlatformDatabase(database_path).initialize()

    assert state.schema_version == PLATFORM_DATABASE_SCHEMA_VERSION
    with PlatformDatabase(database_path).connect() as connection:
        ledger = connection.execute(
            "SELECT version, name, applied_at FROM schema_migrations ORDER BY version"
        ).fetchall()
    assert ledger[0] == (1, "platform_bootstrap", first_applied_at)
    assert ledger[1][0:2] == (2, "apps_sessions_messages_events")
    assert ledger[2][0:2] == (3, "generic_session_classification")
    assert ledger[3][0:2] == (4, "temporary_session_retention")
    assert ledger[4][0:2] == (5, "singleton_chat_collection")
    assert ledger[5][0:2] == (6, "service_and_tool_registry")
    assert ledger[6][0:2] == (7, "asynchronous_agent_runtime")
    assert ledger[7][0:2] == (8, "capability_policy_and_grant_leases")
    assert ledger[8][0:2] == (9, "workspace_resources_and_artifacts")
    assert ledger[9][0:2] == (10, "sandboxed_process_service")
    assert ledger[10][0:2] == (11, "trusted_service_packages")
    assert ledger[11][0:2] == (12, "installable_agents_apps_and_local_patches")
    assert ledger[12][0:2] == (13, "app_mount_context")
    assert ledger[13][0:2] == (14, "unified_capability_requests")
    assert ledger[14][0:2] == (15, "durable_tool_invocations")
    assert ledger[15][0:2] == (16, "pausable_agent_runs")
    assert ledger[16][0:2] == (17, "agent_run_delegation")
    assert ledger[17][0:2] == (18, "coder_projects_and_threads")


def test_schema_v4_backfills_temporary_expiry_and_enforces_policy(tmp_path):
    database_path = tmp_path / "upgrade-v3.sqlite3"
    with sqlite3.connect(database_path, isolation_level=None) as connection:
        apply_migrations(connection, MIGRATIONS[:3])
        connection.execute("PRAGMA foreign_keys = ON")
        now = "2025-01-01T00:00:00.000000Z"
        app_id = "app_" + "1" * 32
        instance_id = "appi_" + "2" * 32
        session_id = "ses_" + "3" * 32
        connection.execute(
            """
            INSERT INTO app_definitions(
                id, package_id, package_version, display_name, instance_mode,
                source, created_at, updated_at
            ) VALUES (?, 'upgrade.test', '1.0.0', 'Upgrade', 'multiple',
                      'local', ?, ?)
            """,
            (app_id, now, now),
        )
        connection.execute(
            """
            INSERT INTO app_instances(
                id, app_definition_id, status, created_at, updated_at
            ) VALUES (?, ?, 'active', ?, ?)
            """,
            (instance_id, app_id, now, now),
        )
        connection.execute(
            """
            INSERT INTO sessions(
                id, app_instance_id, retention, created_at, updated_at
            ) VALUES (?, ?, 'temporary', ?, ?)
            """,
            (session_id, instance_id, now, now),
        )

    PlatformDatabase(database_path).initialize()

    with sqlite3.connect(database_path) as connection:
        expires_at = connection.execute(
            "SELECT expires_at FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()[0]
        assert expires_at == "2025-01-02T00:00:00.000000Z"
        with pytest.raises(sqlite3.IntegrityError, match="retention policy"):
            connection.execute(
                "UPDATE sessions SET expires_at = NULL WHERE id = ?", (session_id,)
            )


def test_concurrent_database_bootstrap_serializes_migrations(tmp_path):
    database_path = tmp_path / "platform.sqlite3"

    with ThreadPoolExecutor(max_workers=2) as executor:
        states = list(
            executor.map(
                lambda _: PlatformDatabase(database_path).initialize(),
                range(2),
            )
        )

    assert [state.schema_version for state in states] == [
        PLATFORM_DATABASE_SCHEMA_VERSION,
        PLATFORM_DATABASE_SCHEMA_VERSION,
    ]
    with PlatformDatabase(database_path).connect() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
            == PLATFORM_DATABASE_SCHEMA_VERSION
        )


def test_migration_failure_rolls_back_schema_and_version(tmp_path):
    database_path = tmp_path / "rollback.sqlite3"
    connection = sqlite3.connect(database_path, isolation_level=None)
    migrations = (
        Migration(
            version=1,
            name="broken",
            statements=(
                "CREATE TABLE should_rollback (id INTEGER PRIMARY KEY)",
                "THIS IS NOT SQL",
            ),
        ),
    )

    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(connection, migrations)

    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    assert tables == []
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
    connection.close()


def test_future_database_schema_is_rejected_without_downgrade(tmp_path):
    database_path = tmp_path / "future.sqlite3"
    future_version = PLATFORM_DATABASE_SCHEMA_VERSION + 1
    with sqlite3.connect(database_path) as connection:
        connection.execute(f"PRAGMA user_version = {future_version}")

    with pytest.raises(FutureSchemaError, match="newer than supported"):
        PlatformDatabase(database_path).initialize()

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == future_version
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'schema_migrations'"
            ).fetchone()
            is None
        )


def test_corrupt_database_reports_typed_diagnostic(tmp_path):
    database_path = tmp_path / "corrupt.sqlite3"
    database_path.write_bytes(b"not a sqlite database")

    with pytest.raises(DatabaseCorruptionError, match="could not be read safely"):
        PlatformDatabase(database_path).initialize()


def test_platform_runtime_reports_ready_database(tmp_path):
    config = PlatformConfig.from_base_path(tmp_path)
    runtime = PlatformRuntime(config)

    before = runtime.database_status
    after = runtime.start()

    assert before.status == "not_initialized"
    assert before.schema_version == 0
    assert after.status == "ready"
    assert after.schema_version == PLATFORM_DATABASE_SCHEMA_VERSION
    assert after.target_schema_version == PLATFORM_DATABASE_SCHEMA_VERSION
    assert after.journal_mode == "wal"


@pytest.mark.asyncio
async def test_runtime_retention_task_expires_temporary_sessions(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    assert runtime.database is not None
    assert runtime.events is not None
    apps = AppRepository(runtime.database, runtime.events)
    definition = apps.create_definition(
        package_id="retention.test",
        package_version="1.0.0",
        display_name="Retention",
        instance_mode=AppInstanceMode.MULTIPLE,
    )
    instance = apps.create_instance(app_definition_id=definition.id)
    sessions = SessionRepository(runtime.database, runtime.events)
    session = sessions.create(
        app_instance_id=instance.id,
        retention=SessionRetention.TEMPORARY,
        expires_at="2025-01-01T00:00:00.000000Z",
    )

    await runtime.start_background_tasks(retention_interval_seconds=0.01)
    for _ in range(100):
        if sessions.get(session.id).status is SessionStatus.DELETED:
            break
        await asyncio.sleep(0.01)
    await runtime.stop_background_tasks()

    assert sessions.get(session.id).status is SessionStatus.DELETED
    assert runtime.events.latest_for_subject(session.id).type == "session.expired"


def test_database_diagnostics_and_atomic_online_backup(tmp_path):
    database = PlatformDatabase(tmp_path / "live.sqlite3")
    database.initialize()
    with database.transaction(write=True) as connection:
        connection.execute("CREATE TABLE operator_test(value TEXT NOT NULL)")
        connection.execute("INSERT INTO operator_test VALUES ('before')")

    diagnostics = database.diagnose()
    backup_path = tmp_path / "backups" / "platform.sqlite3"
    backup = database.backup(backup_path)
    with database.transaction(write=True) as connection:
        connection.execute("INSERT INTO operator_test VALUES ('after')")

    assert isinstance(diagnostics, DatabaseDiagnostics)
    assert diagnostics.quick_check == "ok"
    assert diagnostics.foreign_key_violations == 0
    assert diagnostics.schema_version == PLATFORM_DATABASE_SCHEMA_VERSION
    assert diagnostics.page_count > 0
    assert backup.destination_path == backup_path.resolve()
    assert backup.quick_check == "ok"
    with sqlite3.connect(backup_path) as connection:
        assert connection.execute("SELECT value FROM operator_test").fetchall() == [
            ("before",)
        ]


def test_uncommitted_write_is_absent_after_connection_crash(tmp_path):
    database = PlatformDatabase(tmp_path / "crash.sqlite3")
    database.initialize()
    connection = database.connect()
    connection.execute("BEGIN IMMEDIATE")
    connection.execute(
        "INSERT INTO schema_migrations(version, name, applied_at) VALUES (99, 'lost', ?)",
        ("2025-01-01T00:00:00.000000Z",),
    )
    connection.close()

    with database.connect() as reopened:
        assert (
            reopened.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE version = 99"
            ).fetchone()[0]
            == 0
        )


def test_server_lifecycle_boundary_publishes_ready_health(tmp_path):
    from omlx.server import (
        ServerState,
        app,
        start_ai2apps_platform,
        stop_ai2apps_platform,
    )

    state = ServerState(global_settings=SimpleNamespace(base_path=tmp_path))
    with patch("omlx.server._server_state", state):
        start_ai2apps_platform()
        try:
            response = TestClient(app).get("/v1/platform/health")
        finally:
            stop_ai2apps_platform()

    assert response.status_code == 200
    assert response.json()["database"] == {
        "configured": True,
        "status": "ready",
        "schema_version": PLATFORM_DATABASE_SCHEMA_VERSION,
        "target_schema_version": PLATFORM_DATABASE_SCHEMA_VERSION,
        "filename": "ai2apps-platform.sqlite3",
        "journal_mode": "wal",
    }


def test_fastapi_lifespan_starts_and_stops_platform_runtime(tmp_path):
    from omlx.server import ServerState, app
    from omlx.settings import GlobalSettings

    state = ServerState(global_settings=GlobalSettings(base_path=tmp_path))
    with (
        patch("omlx.server._server_state", state),
        patch("omlx.utils.network.detect_server_aliases", return_value=[]),
        TestClient(app) as client,
    ):
        response = client.get("/v1/platform/health")
        services = client.get("/v1/platform/services")
        echo = client.post(
            "/v1/platform/tools/system.echo/invoke",
            json={"arguments": {"value": "lifespan-ready"}},
        )
        assert state.ai2apps_platform_runtime is not None
        assert response.json()["database"]["status"] == "ready"
        assert {item["service_key"] for item in services.json()["items"]} == {
            "ai2apps.diagnostics",
            "ai2apps.documents",
            "ai2apps.images",
            "ai2apps.mcp",
            "ai2apps.model-runtime",
            "ai2apps.process",
            "ai2apps.agent-runtime",
            "ai2apps.browser",
            "ai2apps.terminal",
            "ai2apps.web-research",
            "ai2apps.workspace",
        }
        assert echo.json()["output"] == {"value": "lifespan-ready"}

    assert state.ai2apps_platform_runtime is None
