"""Idempotent built-in system App registration."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ai2apps.core import (
    EntityIdKind,
    ResourceConflictError,
    new_entity_id,
    utc_now_text,
)
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.records import canonical_json

SYSTEM_APP_MANIFESTS: tuple[dict[str, Any], ...] = (
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.dashboard",
        "name": "Dashboard",
        "description": "System status and runtime overview",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "system"},
        "mobile": {"ready": True},
        "entry": {"kind": "host", "resource": "ai2apps:system/dashboard"},
        "navigation": {
            "category": "System",
            "icon": "layout-dashboard",
            "order": 10,
            "pinned_default": True,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.account",
        "name": "Account",
        "description": "Connect an optional AI2Apps account and manage Cloud points",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "user"},
        "mobile": {"ready": True},
        "entry": {"kind": "host", "resource": "ai2apps:system/account"},
        "navigation": {
            "category": "System",
            "icon": "circle-user-round",
            "order": 15,
            "pinned_default": False,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.models",
        "name": "Models",
        "description": "Install, configure, and manage models",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "system"},
        "entry": {"kind": "host", "resource": "ai2apps:system/models"},
        "navigation": {
            "category": "AI & Models",
            "icon": "box",
            "order": 20,
            "pinned_default": True,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.discover",
        "name": "Discover",
        "description": "Discover, verify, install, and manage AI2Apps packages",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "system"},
        "entry": {"kind": "host", "resource": "ai2apps:system/discover"},
        "navigation": {
            "category": "System",
            "icon": "compass",
            "order": 22,
            "pinned_default": True,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.agents",
        "name": "Agents",
        "description": "Manage Agents, Runs, packages, and local Patches",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "system"},
        "mobile": {"ready": True},
        "entry": {"kind": "host", "resource": "ai2apps:system/agents"},
        "navigation": {
            "category": "AI & Chat",
            "icon": "bot",
            "order": 25,
            "pinned_default": False,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.general-chat",
        "name": "Chat",
        "description": "Chat with local models and Agents",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "user"},
        "mobile": {"ready": True},
        "mobile_entry": {"kind": "host", "resource": "ai2apps:mobile/chat"},
        "entry": {"kind": "host", "resource": "ai2apps:system/chat"},
        "navigation": {
            "category": "AI & Chat",
            "icon": "message-square",
            "order": 30,
            "pinned_default": True,
        },
        "session_kind": "chat_thread",
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.trust-center",
        "name": "Trust Center",
        "description": "Review approvals, permissions, secrets, and Safe Mode",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "system"},
        "mobile": {"ready": True},
        "entry": {"kind": "host", "resource": "ai2apps:system/trust-center"},
        "navigation": {
            "category": "System",
            "icon": "shield-check",
            "order": 35,
            "pinned_default": True,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.settings",
        "name": "Settings",
        "description": "Configure the AI2Apps system",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "system"},
        "entry": {"kind": "host", "resource": "ai2apps:system/settings"},
        "navigation": {
            "category": "System",
            "icon": "settings",
            "order": 40,
            "pinned_default": False,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.logs",
        "name": "Logs",
        "description": "Inspect system and service logs",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "system"},
        "entry": {"kind": "host", "resource": "ai2apps:system/logs"},
        "navigation": {
            "category": "Developer Tools",
            "icon": "scroll-text",
            "order": 50,
            "pinned_default": False,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.terminal",
        "name": "Terminal",
        "description": "Interactive system terminal sessions",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "system"},
        "entry": {"kind": "host", "resource": "ai2apps:system/terminal"},
        "navigation": {
            "category": "Developer Tools",
            "icon": "square-terminal",
            "order": 55,
            "pinned_default": False,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.coder",
        "name": "Coder",
        "description": "Build software with terminal-based coding Agents",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "user"},
        "entry": {"kind": "host", "resource": "ai2apps:system/coder"},
        "navigation": {
            "category": "Developer Tools",
            "icon": "code-2",
            "order": 58,
            "pinned_default": True,
        },
        "presentation": {"dock_reveal": False},
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.benchmark",
        "name": "Bench",
        "description": "Measure model and device performance",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "system"},
        "entry": {"kind": "host", "resource": "ai2apps:system/benchmark"},
        "navigation": {
            "category": "Developer Tools",
            "icon": "gauge",
            "order": 60,
            "pinned_default": False,
        },
        "state": {"version": 1, "defaults": {}},
    },
)


def ensure_system_apps(
    database: PlatformDatabase,
    events: EventStore,
    *,
    trace_id: str | None = None,
) -> None:
    """Register or refresh immutable product-owned App manifests."""

    now = utc_now_text()
    try:
        with database.transaction(write=True) as connection:
            for manifest in SYSTEM_APP_MANIFESTS:
                package_id = str(manifest["id"])
                row = connection.execute(
                    "SELECT * FROM app_definitions WHERE package_id=? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (package_id,),
                ).fetchone()
                instances = manifest["instances"]
                mode = str(instances["mode"])
                scope = str(instances["scope"])
                if row is not None:
                    if (
                        row["source"] != "builtin"
                        or row["instance_mode"] != mode
                        or row["singleton_scope"] != scope
                    ):
                        raise ResourceConflictError(
                            "Reserved system App has incompatible definition: "
                            f"{package_id}"
                        )
                    if (
                        json.loads(row["manifest_json"]) != manifest
                        or row["display_name"] != manifest["name"]
                        or row["status"] != "enabled"
                    ):
                        connection.execute(
                            "UPDATE app_definitions SET display_name=?,"
                            "status='enabled',manifest_json=?,revision=revision+1,"
                            "updated_at=? WHERE id=?",
                            (
                                manifest["name"],
                                canonical_json(manifest),
                                now,
                                row["id"],
                            ),
                        )
                    continue
                definition_id = new_entity_id(EntityIdKind.APP_DEFINITION)
                connection.execute(
                    """
                    INSERT INTO app_definitions(
                        id,package_id,package_version,display_name,instance_mode,
                        singleton_scope,source,status,manifest_schema_version,
                        manifest_json,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,'builtin','enabled',1,?,?,?)
                    """,
                    (
                        definition_id,
                        package_id,
                        manifest["version"],
                        manifest["name"],
                        mode,
                        scope,
                        canonical_json(manifest),
                        now,
                        now,
                    ),
                )
                events.append_in_transaction(
                    connection,
                    event_type="app.definition.created",
                    subject_id=definition_id,
                    trace_id=trace_id,
                    payload={
                        "package_id": package_id,
                        "package_version": manifest["version"],
                        "source": "builtin",
                    },
                )
    except sqlite3.IntegrityError as exc:
        raise ResourceConflictError(str(exc)) from exc
