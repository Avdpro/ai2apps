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

_SYSTEM_APP_MANIFESTS_BASE: tuple[dict[str, Any], ...] = (
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.dashboard",
        "name": "Dashboard",
        "description": "System status and runtime overview",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "system"},
        "access": {"capabilities": ["app.system.manage"]},
        "mobile": {"ready": True},
        "entry": {"kind": "host", "resource": "ai2apps:system/dashboard"},
        "navigation": {
            "category": "System",
            "icon": "layout-dashboard",
            "order": 10,
            "pinned_default": False,
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
        "access": {"capabilities": ["app.use"]},
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
        "id": "ai2apps.sharing",
        "name": "Sharing",
        "description": "Share selected Local models and Tools on your LAN",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "system"},
        "access": {"capabilities": ["app.sharing.manage"]},
        "entry": {"kind": "host", "resource": "ai2apps:system/sharing"},
        "navigation": {
            "category": "System",
            "icon": "share-2",
            "order": 18,
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
        "access": {"capabilities": ["app.system.manage"]},
        "entry": {"kind": "host", "resource": "ai2apps:system/models"},
        "navigation": {
            "category": "AI & Models",
            "icon": "box",
            "order": 20,
            "pinned_default": False,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.environment",
        "name": "Environment",
        "description": "Validate hardware, dependencies, storage, and model readiness",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "system"},
        "access": {"capabilities": ["app.system.manage"]},
        "entry": {"kind": "host", "resource": "ai2apps:system/environment"},
        "navigation": {
            "category": "AI & Models",
            "icon": "stethoscope",
            "order": 21,
            "pinned_default": False,
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
        "access": {"capabilities": ["app.system.manage"]},
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
        "access": {"capabilities": ["app.system.manage"]},
        "mobile": {"ready": True},
        "entry": {"kind": "host", "resource": "ai2apps:system/agents"},
        "mini_entry": {
            "kind": "host",
            "resource": "ai2apps:system/agent-mini",
            "placements": ["sidebar"],
        },
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
        "description": "Chat with cloud, Fusion, local models, and Agents",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "user"},
        "access": {"capabilities": ["app.chat.use"]},
        "mobile": {"ready": True},
        "mobile_entry": {"kind": "host", "resource": "ai2apps:mobile/chat"},
        "entry": {"kind": "host", "resource": "ai2apps:system/chat"},
        "mini_entry": {
            "kind": "host",
            "resource": "ai2apps:system/chat-mini",
            "placements": ["sidebar"],
        },
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
        "access": {"capabilities": ["app.system.manage"]},
        "mobile": {"ready": True},
        "entry": {"kind": "host", "resource": "ai2apps:system/trust-center"},
        "navigation": {
            "category": "System",
            "icon": "shield-check",
            "order": 35,
            "pinned_default": False,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.ai-browser",
        "name": "AI Browser",
        "description": "Create and manage isolated AceFox browser Profiles",
        "version": "0.1.0",
        "instances": {"mode": "singleton", "scope": "user"},
        "access": {"capabilities": ["app.use"]},
        "entry": {"kind": "host", "resource": "ai2apps:system/ai-browser"},
        "navigation": {
            "category": "AI & Chat",
            "icon": "globe-2",
            "order": 31,
            "pinned_default": True,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.messager",
        "name": "Messager",
        "description": "Private Local-first conversations with Cloud offline fallback",
        "version": "0.1.0",
        "instances": {"mode": "singleton", "scope": "user"},
        "access": {"capabilities": ["app.use"]},
        "mobile": {"ready": True},
        "entry": {"kind": "host", "resource": "ai2apps:system/messager"},
        "navigation": {
            "category": "AI & Chat",
            "icon": "messages-square",
            "order": 32,
            "pinned_default": False,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.gallery",
        "name": "Gallery",
        "description": "Manage local AI-generated images, video, audio, web, and files",
        "version": "0.1.0",
        "instances": {"mode": "singleton", "scope": "user"},
        "access": {"capabilities": ["app.use"]},
        "entry": {"kind": "host", "resource": "ai2apps:system/gallery"},
        "mini_entry": {
            "kind": "host",
            "resource": "ai2apps:system/gallery-mini",
            "placements": ["sidebar"],
        },
        "navigation": {
            "category": "AI & Media",
            "icon": "gallery-horizontal-end",
            "order": 31,
            "pinned_default": True,
        },
        "presentation": {
            "shell_sidebar": {
                "entry": "mini_entry",
                "persistent": True,
                "singleton": True,
                "status": "active",
            }
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.knowledge",
        "name": "Knowledge",
        "description": "Save, search, and cite private or Local shared knowledge",
        "version": "0.1.0",
        "instances": {"mode": "singleton", "scope": "user"},
        "access": {"capabilities": ["app.use"]},
        "mobile": {"ready": True},
        "entry": {"kind": "host", "resource": "ai2apps:system/knowledge"},
        "mini_entry": {
            "kind": "host",
            "resource": "ai2apps:system/knowledge-mini",
            "placements": ["inline", "sidebar"],
        },
        "navigation": {
            "category": "AI & Chat",
            "icon": "library-big",
            "order": 33,
            "pinned_default": True,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.readaloud",
        "name": "Read Aloud",
        "description": "Create local-first narration, audiobooks, and multi-character audio",
        "version": "0.1.0",
        "instances": {"mode": "singleton", "scope": "user"},
        "access": {"capabilities": ["app.use"]},
        "entry": {"kind": "host", "resource": "ai2apps:system/readaloud"},
        "navigation": {
            "category": "AI & Media",
            "icon": "audio-lines",
            "order": 34,
            "pinned_default": True,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.video-studio",
        "name": "Video Studio",
        "description": "Create local videos with installed AI2Apps video models",
        "version": "0.1.0",
        "instances": {"mode": "singleton", "scope": "user"},
        "access": {"capabilities": ["app.use"]},
        "entry": {"kind": "host", "resource": "ai2apps:system/video-studio"},
        "navigation": {
            "category": "AI & Media",
            "icon": "clapperboard",
            "order": 35,
            "pinned_default": True,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.imagine-studio",
        "name": "Imagine Studio",
        "description": "Create and edit images with Cloud and local AI Pipelines",
        "version": "0.1.0",
        "instances": {"mode": "singleton", "scope": "user"},
        "access": {"capabilities": ["app.use"]},
        "entry": {"kind": "host", "resource": "ai2apps:system/imagine-studio"},
        "navigation": {
            "category": "AI & Media",
            "icon": "palette",
            "order": 36,
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
        "access": {"capabilities": ["app.system.manage"]},
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
        "access": {"capabilities": ["app.system.manage"]},
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
        "access": {"capabilities": ["app.system.manage"]},
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
        "access": {"capabilities": ["app.coder.use"]},
        "entry": {"kind": "host", "resource": "ai2apps:system/coder"},
        "navigation": {
            "category": "Developer Tools",
            "icon": "code-2",
            "order": 58,
            "pinned_default": True,
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.benchmark",
        "name": "Bench",
        "description": "Measure model and device performance",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "system"},
        "access": {"capabilities": ["app.system.manage"]},
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

_SYSTEM_APP_ZH: dict[str, tuple[str, str, str]] = {
    "ai2apps.dashboard": ("仪表盘", "系统状态与运行时概览", "系统"),
    "ai2apps.account": ("账户", "连接可选的 AI2Apps 账户并管理云端积分", "系统"),
    "ai2apps.sharing": ("共享", "在局域网中共享选定的本地模型和工具", "系统"),
    "ai2apps.models": ("模型", "安装、配置和管理模型", "AI 与模型"),
    "ai2apps.environment": ("环境检查", "验证硬件、依赖、存储与模型运行条件", "AI 与模型"),
    "ai2apps.discover": ("发现", "发现、验证、安装和管理 AI2Apps 软件包", "系统"),
    "ai2apps.agents": ("智能体", "管理智能体、运行记录、软件包和本地补丁", "AI 与聊天"),
    "ai2apps.general-chat": ("聊天", "与云端、Fusion、本地模型和智能体聊天", "AI 与聊天"),
    "ai2apps.ai-browser": ("AI 浏览器", "创建和管理相互隔离的 AceFox 浏览器 Profile", "AI 与聊天"),
    "ai2apps.messager": ("消息", "以本地加密通信为主、Cloud 离线消息为兜底的好友对话", "AI 与聊天"),
    "ai2apps.gallery": ("图库", "统一管理本地 AI 生成的图片、视频、音频、网页与文件", "AI 与媒体"),
    "ai2apps.knowledge": ("知识库", "保存、检索并引用私有或本机共享知识", "AI 与聊天"),
    "ai2apps.readaloud": ("朗读工坊", "本地优先的朗读、有声书与多角色音频制作", "AI 与媒体"),
    "ai2apps.video-studio": ("视频工坊", "使用已安装的 AI2Apps 视频模型在本地创作视频", "AI 与媒体"),
    "ai2apps.imagine-studio": ("创意画坊", "使用 Cloud 与本地 AI Pipeline 生成和编辑图片", "AI 与媒体"),
    "ai2apps.trust-center": ("信任中心", "检查审批、权限、密钥和安全模式", "系统"),
    "ai2apps.settings": ("设置", "配置 AI2Apps 系统", "系统"),
    "ai2apps.logs": ("日志", "检查系统和服务日志", "开发者工具"),
    "ai2apps.terminal": ("终端", "交互式系统终端会话", "开发者工具"),
    "ai2apps.coder": ("编程", "使用终端编程智能体构建软件", "开发者工具"),
    "ai2apps.benchmark": ("基准测试", "测量模型和设备性能", "开发者工具"),
}

SYSTEM_APP_MANIFESTS: tuple[dict[str, Any], ...] = tuple(
    {
        **manifest,
        "localizations": {
            "zh": {
                "name": _SYSTEM_APP_ZH[manifest["id"]][0],
                "description": _SYSTEM_APP_ZH[manifest["id"]][1],
                "navigation": {"category": _SYSTEM_APP_ZH[manifest["id"]][2]},
            }
        },
    }
    for manifest in _SYSTEM_APP_MANIFESTS_BASE
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
