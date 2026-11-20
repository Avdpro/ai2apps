"""Idempotent built-in system App registration."""

from __future__ import annotations

import json
import hashlib
import sqlite3
from typing import Any

from ai2apps.comapps import APP_ID as COMAPPS_ID
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
        "schema": "ai2apps.app/v1", "id": COMAPPS_ID, "name": "ComApps",
        "description": "Connect AI2Apps with WeChat",
        "version": "0.1.0", "instances": {"mode": "singleton", "scope": "user"},
        "access": {"capabilities": ["app.use"]},
        "entry": {"kind": "sandbox", "resource": "comapps/index.html"},
        "builtin_resources": ["comapps/index.html"],
        "navigation": {"category": "AI & Chat", "icon": "comapps", "order": 45, "pinned_default": False},
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1", "id": "ai2apps.visitor-space", "name": "Visitor Space",
        "description": "Edit, preview and publish your visitor space", "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "user"},
        "access": {"capabilities": ["app.system.manage"]},
        "entry": {"kind": "host", "resource": "ai2apps:system/visitor-space"},
        "navigation": {"category": "System", "icon": "contact-round", "order": 17, "pinned_default": False},
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1", "id": "ai2apps.intelligence", "name": "Intel Center",
        "mobile": {"ready": True, "gateway": {
            "template": "system_apps/intelligence.html",
            "assets": ["css/dashboard.css", "css/intelligence.css", "js/intelligence_i18n.js", "js/browser_bidi_client.js", "js/intelligence_site_agents.js", "js/intelligence_social.js", "js/intelligence_cards.js", "js/intelligence_entities.js", "js/intelligence_article_chat.js", "js/mini_app_chat.js", "js/purify.min.js", "js/marked.umd.js", "css/chat_mini.css", "css/chat_message_stream.css", "js/intelligence.js", "js/mobile_app_gateway.js"],
            "api": {"module": "intelligence", "factory": "create_intelligence_router", "prefix": "/v1/platform/intelligence"},
        }},
        "description": "Follow interests, monitor sources and read evidence-backed briefings",
        "version": "0.1.0", "instances": {"mode": "singleton", "scope": "user"},
        "access": {"capabilities": ["app.use"]},
        "entry": {"kind": "host", "resource": "ai2apps:system/intelligence"},
        "navigation": {"category": "Productivity", "icon": "satellite-dish", "order": 43, "pinned_default": True},
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1", "id": "ai2apps.doc-studio", "name": "Doc Studio",
        "description": "Turn source materials into editable articles, X Posts, and standalone HTML",
        "version": "0.1.0", "instances": {"mode": "singleton", "scope": "user"},
        "access": {"capabilities": ["app.use"]},
        "entry": {"kind": "host", "resource": "ai2apps:system/doc-studio"},
        "navigation": {"category": "AI & Media", "icon": "file-pen-line", "order": 37, "pinned_default": False},
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1", "id": "ai2apps.todo", "name": "Todo",
        "mobile": {"ready": True},
        "mobile_entry": {"kind": "host", "resource": "ai2apps:mobile/todo"},
        "description": "Project trees, attachments, Agent execution and schedules",
        "version": "0.1.0", "instances": {"mode": "singleton", "scope": "user"},
        "access": {"capabilities": ["app.use"]},
        "entry": {"kind": "host", "resource": "ai2apps:system/todo"},
        "navigation": {"category": "Productivity", "icon": "list-todo", "order": 42, "pinned_default": True},
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1", "id": "ai2apps.mail", "name": "Mail",
        "mobile": {"ready": True, "gateway": {
            "template": "system_apps/mail.html",
            "assets": ["css/mail.css", "js/mail.js", "js/mobile_app_gateway.js", "js/bot_avatars.js"],
            "api": {"module": "mail", "factory": "create_mobile_mail_router", "prefix": "/v1/platform/mail"},
        }},
        "description": "Connect mail accounts and read a unified inbox",
        "version": "0.1.0", "instances": {"mode": "singleton", "scope": "user"},
        "access": {"capabilities": ["app.use"]},
        "entry": {"kind": "host", "resource": "ai2apps:system/mail"},
        "navigation": {"category": "Productivity", "icon": "mail", "order": 44, "pinned_default": False},
        "state": {"version": 1, "defaults": {}},
    },
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
            "status": "development",
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
            "status": "development",
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
            "icon": "radar",
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
            "status": "development",
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
            "order": 32,
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
        "mobile": {"ready": True, "gateway": {
            "template": "mobile_ai_browser.html",
            "assets": ["css/ai_browser.css", "js/ai_browser.js", "js/ai_browser_mobile_i18n.js", "js/studio_mini_apps.js", "js/share_works_host.js", "js/mobile_app_gateway.js"],
            "api": {"module": "ai_browser_mobile", "factory": "create_ai_browser_mobile_router", "prefix": "/v1/platform"},
        }},
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
        "description": "Chat with Bots, run tasks, and use your Apps",
        "version": "0.1.0",
        "instances": {"mode": "singleton", "scope": "user"},
        "access": {"capabilities": ["app.use"]},
        "mobile": {"ready": True, "gateway": {
            "template": "system_apps/messager_mobile.html", "microphone": True,
            "assets": ["css/chat_message_feedback.css", "css/system_dialog.css", "js/text_input_dialog.js", "js/messager_usage.js", "js/bot_conversation_trim.js", "css/messager_mobile.css", "css/bot_creation.css", "js/bot_creation.js", "js/purify.min.js", "js/marked.umd.js", "js/conversation_model_policy.js", "js/bot_avatars.js", "js/bot_interactions.js", "js/studio_audio_recorder.js", "js/streaming_tts.js", "js/bot_realtime_audio.js", "js/bot_realtime_processor.js", "js/bot_realtime.js", "js/mobile_bot_voice.js", "js/messager_mobile.js", "js/mobile_app_gateway.js"],
            "api": {"module": "messager_mobile", "factory": "create_messager_mobile_router", "prefix": "/v1/platform/messager-mobile"},
        }},
        "entry": {"kind": "host", "resource": "ai2apps:system/messager"},
        "navigation": {
            "category": "AI & Chat",
            "icon": "messages-square",
            "order": 1,
            "pinned_default": True,
            "status": "active",
        },
        "state": {"version": 1, "defaults": {}},
    },
    {
        "schema": "ai2apps.app/v1",
        "id": "ai2apps.gallery",
        "mobile": {"ready": True},
        "mobile_entry": {"kind": "host", "resource": "ai2apps:mobile/gallery"},
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
            "icon": "gallery-stacked-horizontal",
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
        "mobile_entry": {"kind": "host", "resource": "ai2apps:mobile/knowledge"},
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
        "mobile": {"ready": True},
        "name": "Voice Studio",
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
        "mobile": {"ready": True},
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
        "mobile": {"ready": True},
        "name": "Imagine Studio",
        "description": "Create and edit images with Cloud and local AI Mini-Apps",
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
        "id": "ai2apps.harness",
        "name": "Harness",
        "description": "Run sandboxed commands, read documents and save task artifacts to user-named local folders",
        "version": "1.0.0",
        "instances": {"mode": "singleton", "scope": "system"},
        "access": {"capabilities": []},
        "entry": {"kind": "host", "resource": "ai2apps:generic-launcher"},
        "navigation": {"category": "Developer Tools", "icon": "square-terminal", "launcher": False},
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
            "experimental": True,
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
            "experimental": True,
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
            "status": "development",
        },
        "state": {"version": 1, "defaults": {}},
    },
)

_SYSTEM_APP_ZH: dict[str, tuple[str, str, str]] = {
    "ai2apps.intelligence": ("情报中心", "追踪兴趣与信息源，阅读有据可查的情报简报", "效率工具"),
    "ai2apps.doc-studio": ("Doc Studio", "使用来源素材撰写可编辑的文章、X Post 和独立 HTML", "AI 与媒体"),
    "ai2apps.todo": ("待办", "项目树、附件、智能体执行与定时计划", "效率工具"),
    "ai2apps.mail": ("邮件", "连接多个邮箱并在统一收件箱中阅读邮件", "效率工具"),
    "ai2apps.dashboard": ("仪表盘", "系统状态与运行时概览", "系统"),
    "ai2apps.account": ("账户", "连接可选的 AI2Apps 账户并管理云端积分", "系统"),
    "ai2apps.visitor-space": ("访客空间", "编辑、预览并发布对外开放的空间", "系统"),
    "ai2apps.sharing": ("共享", "在局域网中共享选定的本地模型和工具", "系统"),
    "ai2apps.models": ("模型", "安装、配置和管理模型", "AI 与模型"),
    "ai2apps.environment": ("环境检查", "验证硬件、依赖、存储与模型运行条件", "AI 与模型"),
    "ai2apps.discover": ("发现", "发现、验证、安装和管理 AI2Apps 软件包", "系统"),
    "ai2apps.agents": ("智能体", "管理智能体、运行记录、软件包和本地补丁", "AI 与聊天"),
    "ai2apps.general-chat": ("聊天", "与云端、Fusion、本地模型和智能体聊天", "AI 与聊天"),
    "ai2apps.ai-browser": ("AI 浏览器", "创建和管理相互隔离的 AceFox 浏览器 Profile", "AI 与聊天"),
    "ai2apps.messager": ("消息", "与 Bot 对话、执行任务，调用你的 App", "AI 与聊天"),
    COMAPPS_ID: ("传信", "连接 AI2Apps 与微信分身", "AI 与聊天"),
    "ai2apps.gallery": ("素材库", "统一管理本地 AI 生成的图片、视频、音频、网页与文件", "AI 与媒体"),
    "ai2apps.knowledge": ("知识库", "保存、检索并引用私有或本机共享知识", "AI 与聊天"),
    "ai2apps.readaloud": ("语音工坊", "本地优先的朗读、有声书与多角色音频制作", "AI 与媒体"),
    "ai2apps.video-studio": ("视频工坊", "使用已安装的 AI2Apps 视频模型在本地创作视频", "AI 与媒体"),
    "ai2apps.imagine-studio": ("创意画坊", "使用 Cloud 与本地 AI Mini-App 生成和编辑图片", "AI 与媒体"),
    "ai2apps.trust-center": ("信任中心", "检查审批、权限、密钥和安全模式", "系统"),
    "ai2apps.settings": ("设置", "配置 AI2Apps 系统", "系统"),
    "ai2apps.logs": ("日志", "检查系统和服务日志", "开发者工具"),
    "ai2apps.harness": ("Harness", "运行沙箱命令、读取文档，将任务产物保存到指定本地目录", "开发者工具"),
    "ai2apps.terminal": ("终端", "交互式系统终端会话", "开发者工具"),
    "ai2apps.coder": ("编程", "使用终端编程智能体构建软件", "开发者工具"),
    "ai2apps.benchmark": ("基准测试", "测量模型和设备性能", "开发者工具"),
}

# Browser owns its built-in frame declarations and exact shipped resource list.
from ai2apps.browser.builtin_mini_apps import definitions as _browser_minis
_browser_declarations, _browser_resources = _browser_minis()
for _manifest in _SYSTEM_APP_MANIFESTS_BASE:
    if _manifest['id'] == 'ai2apps.ai-browser':
        _manifest['mini_apps'] = _browser_declarations
        _manifest['builtin_resources'] = _browser_resources

def _messager_launcher_status() -> str:
    """Messager is available in every Desktop instance, including production."""
    return "active"



SYSTEM_APP_MANIFESTS: tuple[dict[str, Any], ...] = tuple(
    {
        **manifest,
        **({"navigation": {**manifest["navigation"], "status": _messager_launcher_status()}}
           if manifest["id"] == "ai2apps.messager" else {}),
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


def _adopt_comapps(connection, definition, now):
    """Keep instance IDs used by Shell and the bound WeChat channel."""
    definition_id = definition["id"]
    connection.execute(
        """UPDATE app_mounts SET status='unmounted',updated_at=?
           WHERE status='mounted' AND app_instance_id IN (
               SELECT i.id FROM app_instances i JOIN app_definitions d ON d.id=i.app_definition_id
               WHERE d.package_id=? AND d.source!='builtin'
           )""",
        (now, COMAPPS_ID),
    )
    connection.execute(
        """UPDATE app_instances SET app_definition_id=?,revision=revision+1,updated_at=?
           WHERE app_definition_id IN (
               SELECT id FROM app_definitions WHERE package_id=? AND id!=?
           )""",
        (definition_id, now, COMAPPS_ID, definition_id),
    )
    connection.execute(
        """UPDATE app_definitions SET status='disabled',revision=revision+1,updated_at=?
           WHERE package_id=? AND id!=? AND status='enabled'""",
        (now, COMAPPS_ID, definition_id),
    )
    if definition["source"] != "builtin":
        connection.execute(
            """UPDATE app_definitions SET source='builtin',upstream_digest=NULL,
               revision=revision+1,updated_at=? WHERE id=?""",
            (now, definition_id),
        )
    connection.execute(
        """UPDATE interactive_packages SET status='uninstalled',retired_at=?
           WHERE package_kind='app' AND unit_key=? AND status!='uninstalled'""",
        (now, COMAPPS_ID),
    )
    connection.execute(
        """UPDATE effective_definitions SET status='retained',retired_at=?
           WHERE unit_kind='app' AND unit_key=? AND status='active'""",
        (now, COMAPPS_ID),
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
                adopt = package_id == COMAPPS_ID
                digest = "sha256:" + hashlib.sha256(canonical_json(manifest).encode()).hexdigest()
                ordering = "(source='builtin') DESC,(status='enabled') DESC," if adopt else ""
                row = connection.execute(
                    "SELECT * FROM app_definitions WHERE package_id=? "
                    f"ORDER BY {ordering}created_at DESC LIMIT 1",
                    (package_id,),
                ).fetchone()
                instances = manifest["instances"]
                mode = str(instances["mode"])
                scope = str(instances["scope"])
                if row is not None:
                    if (
                        (row["source"] != "builtin" and not adopt)
                        or row["instance_mode"] != mode
                        or row["singleton_scope"] != scope
                    ):
                        raise ResourceConflictError(
                            "Reserved system App has incompatible definition: "
                            f"{package_id}"
                        )
                    if adopt:
                        _adopt_comapps(connection, row, now)
                    if (
                        row["source"] != "builtin"
                        or json.loads(row["manifest_json"]) != manifest
                        or row["display_name"] != manifest["name"]
                        or row["status"] != "enabled"
                        or row["effective_digest"] != digest
                    ):
                        connection.execute(
                            "UPDATE app_definitions SET display_name=?,"
                            "status='enabled',manifest_json=?,effective_digest=?,revision=revision+1,"
                            "updated_at=? WHERE id=?",
                            (
                                manifest["name"],
                                canonical_json(manifest),
                                digest,
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
                        manifest_json,effective_digest,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,'builtin','enabled',1,?,?,?,?)
                    """,
                    (
                        definition_id,
                        package_id,
                        manifest["version"],
                        manifest["name"],
                        mode,
                        scope,
                        canonical_json(manifest),
                        digest,
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
