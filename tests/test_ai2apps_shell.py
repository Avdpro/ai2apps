"""Contract tests for the AI2Apps WebUI Shell migration slice."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai2apps.config import PlatformConfig
from ai2apps.platform_runtime import PlatformRuntime
from omlx.admin import routes as admin_routes

WEB_ROOT = Path(__file__).parents[1] / "ai2apps" / "web"


def test_system_app_catalog_covers_legacy_omlx_surfaces():
    assert {app["id"] for app in admin_routes.SYSTEM_APPS} == {
        "ai2apps.dashboard",
        "ai2apps.account",
        "ai2apps.models",
        "ai2apps.discover",
        "ai2apps.agents",
        "ai2apps.general-chat",
        "ai2apps.trust-center",
        "ai2apps.settings",
        "ai2apps.logs",
        "ai2apps.terminal",
        "ai2apps.coder",
        "ai2apps.benchmark",
    }
    assert all(app["singleton"] for app in admin_routes.SYSTEM_APPS)


def test_shell_router_exposes_singleton_and_instance_urls():
    paths = {route.path for route in admin_routes.shell_router.routes}
    assert "/apps/{app_id}" in paths
    assert "/apps/{app_id}/instances/{instance_id}" in paths
    assert "/mobile" in paths
    assert "/mobile/complete" in paths
    assert "/mobile/static/{path:path}" in paths
    assert "/v1/mobile/session/exchange" in paths
    assert "/v1/mobile/apps" in paths
    assert "/v1/mobile/models" in paths
    assert "/v1/mobile/chat/completions" in paths
    assert "/v1/mobile/chat/state" in paths
    assert "/v1/mobile/chat/threads" in paths
    assert "/v1/mobile/chat/threads/{thread_id}/content" in paths
    assert "/v1/mobile/chat/threads/{thread_id}/attachments" in paths
    assert "/v1/mobile/agents" in paths
    assert "/v1/mobile/chat/threads/{thread_id}/agent-runs" in paths
    assert "/v1/mobile/agent-runs/{run_id}" in paths
    assert "/mobile/chat" in paths


def test_mobile_shell_contract_exposes_dock_launcher_and_switcher():
    template = (WEB_ROOT / "templates" / "mobile.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "mobile.js").read_text()
    styles = (WEB_ROOT / "static" / "css" / "mobile.css").read_text()
    base = (WEB_ROOT / "templates" / "mobile_base.html").read_text()

    assert "mobile-dock" in template
    assert 'data-mobile-overlay="launcher"' in template
    assert 'data-mobile-overlay="switcher"' in template
    assert "/v1/mobile/apps" in script
    assert "/v1/mobile/mounts" in script
    assert "/v1/mobile/session/exchange" in script
    assert "warmFrameLimit = 2" in script
    assert "env(safe-area-inset-bottom)" in styles
    assert "/admin/static/" not in template
    assert "/admin/static/" not in base
    assert "mobile_static('css/mobile.css')" in template
    assert "mobile_static('js/lucide.min.js')" in base
    mobile_chat = (WEB_ROOT / "templates" / "mobile_chat.html").read_text()
    mobile_chat_script = (WEB_ROOT / "static" / "js" / "mobile_chat.js").read_text()
    assert "Your local API key is never sent to the phone" in mobile_chat
    assert '{% extends "mobile_base.html" %}' in mobile_chat
    assert "/admin/static/" not in mobile_chat
    assert "mobile_static('css/mobile_chat.css')" in mobile_chat
    assert "mobile_static('js/mobile_chat.js')" in mobile_chat
    assert "<style>" not in base
    assert "/v1/mobile/chat/completions" in mobile_chat_script
    assert "/v1/mobile/chat/threads" in mobile_chat_script
    assert "/attachments" in mobile_chat_script
    assert "/agent-runs" in mobile_chat_script
    assert "data-mobile-chat-status" in mobile_chat
    assert "data-mobile-chat-file" in mobile_chat
    assert 'data-mobile-chat-mode="agent"' in mobile_chat
    assert "data-mobile-chat-session-list" in mobile_chat
    assert "compositionstart" in mobile_chat_script
    assert "compositionend" in mobile_chat_script
    assert "event.isComposing" in mobile_chat_script
    assert "event.keyCode===229" in mobile_chat_script


def test_mobile_system_apps_use_csp_safe_mobile_assets():
    mobile_base = (WEB_ROOT / "templates" / "mobile_app_base.html").read_text()
    assert "/admin/static/" not in mobile_base
    assert "<style>" not in mobile_base
    assert "mobile_static('css/tailwind.css')" in mobile_base
    assert "mobile_static('js/alpine.min.js')" in mobile_base

    expected = {
        "account": "css/account.css",
        "agents": "css/agents.css",
        "trust_center": "css/trust_center.css",
    }
    for name, stylesheet in expected.items():
        template = (WEB_ROOT / "templates" / "system_apps" / f"{name}.html").read_text()
        assert "app_base_template" in template
        assert "<style>" not in template
        assert stylesheet in template
        assert stylesheet in admin_routes.MOBILE_STATIC_FILES
        assert (WEB_ROOT / "static" / stylesheet).is_file()

    for asset in admin_routes.MOBILE_STATIC_FILES:
        assert (WEB_ROOT / "static" / asset).is_file(), asset


def test_mobile_api_routes_are_separate_from_desktop_shell_api():
    paths = {route.path for route in admin_routes.router.routes}

    assert "/admin/api/mobile/apps" in paths
    assert "/admin/api/mobile/mounts" in paths
    assert "/admin/api/mobile/apps/{app_key}/open" in paths
    assert "/admin/api/mobile/app-instances/{instance_id}/focus" in paths


def test_dock_account_status_exposes_only_summary_fields():
    class Response:
        status_code = 200

        def json(self):
            return {
                "user": {
                    "id": "user-secret-id",
                    "displayName": "Ada",
                    "email": "ada@example.com",
                    "points": {"promotional": "30", "paid": "12", "total": "42"},
                    "entitlements": ["ai.invoke"],
                }
            }

        async def aclose(self):
            return None

    class Cloud:
        async def request(self, method, path):
            assert (method, path) == ("GET", "/v1/auth/me")
            return Response()

    with patch.object(
        admin_routes,
        "_get_platform_runtime",
        return_value=SimpleNamespace(cloud=Cloud()),
    ):
        result = asyncio.run(admin_routes.shell_account_status(is_admin=True))

    assert result == {
        "state": "signed_in",
        "display_name": "Ada",
        "email": "ada@example.com",
        "points": "42",
    }


def test_model_app_exposes_managed_ai2apps_provider_for_signed_in_account():
    class Response:
        status_code = 200

        def json(self):
            return {
                "items": [
                    {
                        "id": "openai/gpt-test",
                        "provider": "openai",
                        "displayName": "GPT Test",
                        "capabilities": {"imageInput": True, "tools": True},
                        "contextWindow": 100000,
                        "maxOutputTokens": 4096,
                        "pricingVersion": "test-v1",
                        "rates": {"input": "1", "output": "2"},
                    }
                ]
            }

        async def aclose(self):
            return None

    class Cloud:
        base_url = "https://coder.ai2apps.test"

        async def request(self, method, path):
            assert (method, path) == ("GET", "/v1/ai/models")
            return Response()

    with patch.object(
        admin_routes,
        "_get_platform_runtime",
        return_value=SimpleNamespace(cloud=Cloud()),
    ):
        provider = asyncio.run(admin_routes._ai2apps_cloud_provider())

    assert provider["managed"] is True
    assert provider["configured"] is True
    assert provider["connection_state"] == "signed_in"
    assert provider["models"][0]["id"] == "openai/gpt-test"
    assert provider["models"][0]["enabled"] is True


def test_model_app_template_explains_disabled_managed_models():
    template = (WEB_ROOT / "templates" / "dashboard" / "_models.html").read_text()

    assert "cloudModel.disabled_reason" in template
    assert "local provider takes priority" in template


def test_model_manager_explains_when_local_provider_takes_priority():
    provider = {
        "models": [{"id": "openai/gpt-test", "enabled": True}],
        "enabled_model_count": 1,
    }
    store = SimpleNamespace(
        list_cloud=lambda: [
            {"id": "openai", "name": "OpenAI", "configured": True}
        ],
        list_fusion=lambda: [],
        default_models=lambda: {},
    )
    installer = SimpleNamespace(get_tasks=lambda: [])

    with (
        patch("ai2apps.model_installer.AI2AppsInstaller.catalog", return_value=[]),
        patch.object(admin_routes, "list_models", new=AsyncMock(return_value={"models": []})),
        patch.object(admin_routes, "_get_ai2apps_installer", return_value=installer),
        patch.object(admin_routes, "_model_manager_store", return_value=store),
        patch.object(
            admin_routes,
            "_ai2apps_cloud_provider",
            new=AsyncMock(return_value=provider),
        ),
    ):
        result = asyncio.run(admin_routes.get_model_manager(is_admin=True))

    managed_model = result["cloud"][0]["models"][0]
    assert managed_model["enabled"] is False
    assert managed_model["disabled_reason"] == (
        "Using local OpenAI API key (local provider takes priority)."
    )


def test_instance_route_preserves_requested_instance_id():
    request = MagicMock()
    with patch.object(admin_routes, "templates") as templates:
        templates.TemplateResponse.return_value = MagicMock()
        asyncio.run(
            admin_routes.app_instance_shell(
                request=request,
                app_id="example.notes",
                instance_id="appi_0123456789abcdef0123456789abcdef",
                is_admin=True,
            )
        )
        templates.TemplateResponse.assert_called_once_with(
            request,
            "shell.html",
            {
                "system_apps": admin_routes.SYSTEM_APPS,
                "initial_app_id": "example.notes",
                "initial_instance_id": "appi_0123456789abcdef0123456789abcdef",
            },
        )


def test_system_app_shell_passes_catalog_and_selected_app():
    request = MagicMock()
    with patch.object(admin_routes, "templates") as templates:
        templates.TemplateResponse.return_value = MagicMock()
        asyncio.run(
            admin_routes.system_app_shell(
                request=request,
                app_id="ai2apps.models",
                is_admin=True,
            )
        )
        templates.TemplateResponse.assert_called_once_with(
            request,
            "shell.html",
            {
                "system_apps": admin_routes.SYSTEM_APPS,
                "initial_app_id": "ai2apps.models",
                "initial_instance_id": None,
            },
        )


def test_unsafe_app_identifier_is_not_rendered():
    with pytest.raises(admin_routes.HTTPException) as error:
        asyncio.run(
            admin_routes.system_app_shell(
                request=MagicMock(),
                app_id="unsafe$app",
                is_admin=True,
            )
        )
    assert error.value.status_code == 404


@pytest.mark.parametrize(
    ("app_id", "template_name", "tab"),
    [
        ("ai2apps.dashboard", "system_apps/dashboard.html", "status"),
        ("ai2apps.account", "system_apps/account.html", "account"),
        ("ai2apps.models", "system_apps/models.html", "models"),
        ("ai2apps.discover", "system_apps/discover.html", "discover"),
        ("ai2apps.agents", "system_apps/agents.html", "agents"),
        ("ai2apps.trust-center", "system_apps/trust_center.html", "trust"),
        ("ai2apps.settings", "system_apps/settings.html", "settings"),
        ("ai2apps.logs", "system_apps/logs.html", "logs"),
        ("ai2apps.terminal", "system_apps/terminal.html", "terminal"),
        ("ai2apps.coder", "system_apps/coder.html", "coder"),
        ("ai2apps.benchmark", "system_apps/benchmark.html", "bench"),
    ],
)
def test_dashboard_capabilities_have_independent_host_entries(
    app_id, template_name, tab
):
    request = MagicMock()
    with (
        patch.object(admin_routes, "templates") as templates,
        patch.object(
            admin_routes,
            "_get_global_settings",
            return_value=SimpleNamespace(auth=SimpleNamespace(api_key="test-key")),
        ),
    ):
        templates.TemplateResponse.return_value = MagicMock()
        asyncio.run(
            admin_routes.system_app_content(
                request=request,
                app_id=app_id,
                is_admin=True,
            )
        )
        context = {
            "system_app": {
                "id": app_id,
                "name": admin_routes._SYSTEM_APPS_BY_ID[app_id]["name"],
                "tab": tab,
            }
        }
        if app_id in {"ai2apps.account", "ai2apps.discover", "ai2apps.agents", "ai2apps.trust-center"}:
            context["api_key"] = "test-key"
        if app_id == "ai2apps.coder":
            context["show_dock_reveal"] = False
        templates.TemplateResponse.assert_called_once_with(
            request, template_name, context
        )


def test_system_app_templates_mount_only_their_owned_surface():
    expected = {
        "dashboard.html": "dashboard/_status.html",
        "models.html": "dashboard/_models.html",
        "settings.html": "dashboard/_settings.html",
        "logs.html": "dashboard/_logs.html",
        "benchmark.html": "dashboard/_bench.html",
    }
    system_root = WEB_ROOT / "templates" / "system_apps"
    for filename, owned_partial in expected.items():
        source = (system_root / filename).read_text()
        assert owned_partial in source
        for other_partial in set(expected.values()) - {owned_partial}:
            assert other_partial not in source

    base = (system_root / "base.html").read_text()
    assert "dashboard/_navbar.html" not in base
    assert "window.AI2APPS_SYSTEM_APP" in base


def test_independent_system_app_entries_render_with_shared_runtime():
    entries = {
        "ai2apps.dashboard": ("system_apps/dashboard.html", "status"),
        "ai2apps.models": ("system_apps/models.html", "models"),
        "ai2apps.settings": ("system_apps/settings.html", "settings"),
        "ai2apps.logs": ("system_apps/logs.html", "logs"),
        "ai2apps.benchmark": ("system_apps/benchmark.html", "bench"),
    }
    for app_id, (template_name, tab) in entries.items():
        rendered = admin_routes.templates.env.get_template(template_name).render(
            system_app={
                "id": app_id,
                "name": admin_routes._SYSTEM_APPS_BY_ID[app_id]["name"],
                "tab": tab,
            }
        )
        assert f'data-app-id="{app_id}"' in rendered
        assert "window.AI2APPS_SYSTEM_APP" in rendered


def test_agent_manager_is_an_independent_management_surface():
    source = (WEB_ROOT / "templates" / "system_apps" / "agents.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "agent_manager.js").read_text()
    assert 'data-app-id="ai2apps.agents"' in source
    assert "Agent Manager" in source
    assert "Agent Studio" not in source
    assert "/agents/' + encodeURIComponent(key) + '/management" in script
    assert "/interactive-packages/install" in script
    assert "/agent-runs?" in script


def test_account_is_an_independent_optional_cloud_surface():
    source = (WEB_ROOT / "templates" / "system_apps" / "account.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "account.js").read_text()
    shell = (WEB_ROOT / "templates" / "shell.html").read_text()
    shell_script = (WEB_ROOT / "static" / "js" / "shell.js").read_text()

    assert 'data-app-id="ai2apps.account"' in source
    assert "your local workspace remains independent" in source
    assert "'/v1/platform/cloud'" in script
    assert "'/v1/platform/remote'" in script
    assert "Remote access" in source
    assert "Pair phone" in source
    assert "!device.proxyConnected" in source
    assert "Reconnecting automatically" in script
    assert "Register again" in source
    assert "reregisterRemote" in script
    assert "Scan with your phone" in source
    assert "pairingQrDataUrl" in script
    assert "/devices/reconcile" in script
    assert "device.proxyConnected?'Online'" in source
    assert "Connecting…" in source
    assert "refreshRemoteConnectionState" in script
    assert "localStorage" not in script
    assert "/auth/login" in script
    assert "/auth/password/reset" in script
    assert "/points/ledger?limit=50" in script
    assert 'data-shell-action="account"' in shell
    assert "/admin/api/shell/account-status" in shell_script
    assert "launch('ai2apps.account')" in shell_script
    assert "broadcastAccountChanged()" in shell_script
    assert "ai2apps.host.account-changed" in shell_script
    assert "ai2apps:account-changed" in (
        WEB_ROOT / "static" / "js" / "dashboard.js"
    ).read_text()


def test_discover_is_a_package_surface_not_an_app_store():
    source = (WEB_ROOT / "templates" / "system_apps" / "discover.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "discover.js").read_text()
    assert 'data-app-id="ai2apps.discover"' in source
    assert "Apps, Agents, and Services" in source
    assert "Verified locally" in source
    assert "App Store" not in source
    assert "Marketplace" not in source
    assert "/catalog/recommendations" in script
    assert "'/installed'" in script
    assert "publisher_signature_invalid" in script
    assert "Build and publish trusted packages" in source
    assert "Signing key" in source
    assert "Submission workflow" in source
    assert "/publishing/submissions" in script
    assert "registerSelectedKey" in script


def test_shell_chat_content_receives_the_local_api_key():
    source = Path(admin_routes.__file__).read_text()
    assert '"ai2apps.general-chat",' in source
    assert 'context["api_key"] = settings.auth.api_key if settings else ""' in source


def test_trust_center_is_an_independent_authority_surface():
    source = (WEB_ROOT / "templates" / "system_apps" / "trust_center.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "trust_center.js").read_text()
    assert 'data-app-id="ai2apps.trust-center"' in source
    assert "Approval Inbox" in source
    assert "Granted Permissions" in source
    assert "Secret Store" in source
    assert "Enter Safe Mode" in source
    assert "/approvals/" in script
    assert "/grant-leases/" in script
    assert "/secrets/backend" in script
    assert "scopeLabel(scope)" in script


def test_coder_is_a_singleton_project_thread_terminal_surface():
    source = (WEB_ROOT / "templates" / "system_apps" / "coder.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "coder.js").read_text()
    assert 'data-app-id="ai2apps.coder"' in source
    assert "data-coder-tree" in source
    assert "data-model-source" in source
    assert "/admin/api/coder/projects/" in script
    assert "/fork" in script
    assert "new WebSocket" in script
    assert "terminal_session_id" in script
    assert "/testflight" in script


def test_launcher_always_exposes_testflight_category():
    script = (WEB_ROOT / "static" / "js" / "shell.js").read_text()

    assert "new Set(['TestFlight', ...apps.map((app) => app.category)])" in script
    assert "loadCatalog({ quiet: true }).then" in script


def test_legacy_dashboard_tab_opens_corresponding_system_app():
    request = MagicMock()
    request.query_params = {"tab": "models"}
    with patch.object(admin_routes, "templates") as templates:
        templates.TemplateResponse.return_value = MagicMock()
        asyncio.run(admin_routes.dashboard_page(request=request, is_admin=True))
        assert templates.TemplateResponse.call_args.args[2]["initial_app_id"] == (
            "ai2apps.models"
        )


def test_chat_brand_returns_to_canonical_dashboard_app():
    chat = (WEB_ROOT / "templates" / "chat.html").read_text()
    assert chat.count('href="/apps/ai2apps.dashboard" target="_top"') == 2
    assert 'href="/admin/dashboard"' not in chat


def test_shell_assets_cover_dock_launcher_pinning_and_bridge():
    shell = (WEB_ROOT / "templates" / "shell.html").read_text()
    css = (WEB_ROOT / "static" / "css" / "shell.css").read_text()
    js = (WEB_ROOT / "static" / "js" / "shell.js").read_text()
    base = (WEB_ROOT / "templates" / "base.html").read_text()

    assert "dock-hot-zone" in shell
    assert "app-launcher" in shell
    assert 'data-mode="docked"' in shell
    assert 'data-mode="immersive"' in css
    assert "ai2apps.shell.pinnedApps" in js
    assert "ai2apps.shell.dockOrder" in js
    assert "ai2apps.shell.warmApps" in js
    assert "ai2apps.shell.runningApps" not in js
    assert "/admin/api/shell/apps" in js
    assert "ai2apps.shell.request-dock" in js
    assert "mountToken" in js
    assert "window.ai2appsShell" in base
    assert "targetInstanceId" in base
    assert "options.targetInstanceId" in js
    assert "dock-context-menu" in shell
    assert "dock-tooltip-host" in shell
    assert "data-dock-menu-action=\"force-close\"" in shell
    assert "data-dock-menu-action=\"warm\"" in shell
    assert "data-dock-menu-action=\"reload\"" in shell
    assert "data-dock-drag-id" in js
    assert "currentMountToken && frame.getAttribute('src')" in js
    assert "appId === currentId" in js
    assert "ai2apps.host.before-close" in js
    assert ".dock-app-wrap.is-running:not(.is-current)::after" in css
    assert ".dock-app-wrap.is-current::after" not in css
    assert "ai2apps.host.background" in js
    assert "ai2apps.host.activate" in js
    assert "ai2apps.host.before-evict" in js
    assert "framePool" in js
    assert "frameCacheLimit = 4" in js
    assert "'ai2apps.general-chat', 'ai2apps.coder'" in js
    assert "isFrameCacheExempt" in js
    assert "updateMode({ persist: false })" in js


def test_w4_bridge_mini_entry_trust_and_recovery_surfaces():
    shell = (WEB_ROOT / "templates" / "shell.html").read_text()
    shell_js = (WEB_ROOT / "static" / "js" / "shell.js").read_text()
    base = (WEB_ROOT / "templates" / "base.html").read_text()
    chat = (WEB_ROOT / "templates" / "chat.html").read_text()

    assert "system-control" in shell
    assert "Package Trust" in shell
    assert "Patch Conflicts" in shell
    for bridge_call in (
        "setBadge", "navigate", "openEntry", "mountMiniEntry",
        "requestCapability", "createAgentRun", "exportArtifact", "close",
    ):
        assert bridge_call in base
    assert "ai2apps.host.mini-entry-mounted" in shell_js
    assert "data-patch-resolution" in shell_js
    assert "data-safe-mode" in shell_js
    assert "data-approval-id" in shell_js
    assert "data-revoke-grant" in shell_js
    assert "capabilityBridgeWaiters" in shell_js
    assert "Approvals" in shell
    assert "Grants" in shell
    assert "miniEntriesForMessage" in chat
    assert "moveMiniEntryToSidebar" in chat
    assert "sidebarMiniEntry" in chat
    assert '<details class="mini-app-launcher' in chat


def test_shell_template_renders_boot_catalog():
    rendered = admin_routes.templates.env.get_template("shell.html").render(
        system_apps=admin_routes.SYSTEM_APPS,
        initial_app_id="ai2apps.dashboard",
        initial_instance_id=None,
    )
    assert 'id="ai2apps-shell"' in rendered
    assert 'initialAppId: "ai2apps.dashboard"' in rendered
    assert '"id": "ai2apps.general-chat"' in rendered


def test_constrained_entry_renderers_have_separate_hosts():
    safe_html = (WEB_ROOT / "templates" / "app_views" / "safe_html.html").read_text()
    schema = (WEB_ROOT / "templates" / "app_views" / "schema.html").read_text()
    safe_js = (WEB_ROOT / "static" / "js" / "app-safe-html.js").read_text()

    assert "purify.min.js" in safe_html
    assert "DOMPurify.sanitize" in safe_js
    assert "app-schema.js" in schema
    assert "FORBID_TAGS" in safe_js


def test_loading_overlay_follows_frame_and_honors_hidden_state():
    shell = (WEB_ROOT / "templates" / "shell.html").read_text()
    css = (WEB_ROOT / "static" / "css" / "shell.css").read_text()

    assert shell.index('class="app-frame"') < shell.index('class="app-loading"')
    assert ".app-loading[hidden] { display: none; }" in css
    assert ".app-frame[hidden] { display: none; }" in css
    assert ".app-frame.is-ready + .app-loading" in css


def test_admin_shell_adapter_uses_runtime_without_api_key(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / "data"))
    runtime.start()
    with patch.object(admin_routes, "_get_platform_runtime", return_value=runtime):
        catalog = asyncio.run(admin_routes.shell_apps(is_admin=True))
        launched = asyncio.run(
            admin_routes.shell_launch_app(
                app_key="ai2apps.dashboard",
                is_admin=True,
            )
        )
        entry = asyncio.run(
            admin_routes.shell_instance_entry(
                instance_id=launched["instance_id"],
                is_admin=True,
            )
        )

    assert len(catalog["items"]) >= 6
    assert launched["renderer"] == "host"
    assert launched["content_url"] == "/admin/app-content/ai2apps.dashboard"
    assert entry["instance_id"] == launched["instance_id"]


def test_admin_shell_adapter_mounts_and_restores_generic_mini_entry(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / "data"))
    runtime.start()
    dashboard, interaction_session, _ = runtime.extension_manager.launch_app(
        "ai2apps.dashboard"
    )
    settings, _, _ = runtime.extension_manager.launch_app("ai2apps.settings")
    chat_session_id = interaction_session.id
    with patch.object(admin_routes, "_get_platform_runtime", return_value=runtime):
        mounted = asyncio.run(
            admin_routes.shell_mount_app(
                instance_id=settings.id,
                request=admin_routes.ShellMountRequest(
                    interaction_session_id=chat_session_id,
                    context={"message_id": "msg_" + "b" * 32},
                ),
                is_admin=True,
            )
        )
        restored = asyncio.run(
            admin_routes.shell_session_mounts(
                session_id=chat_session_id,
                is_admin=True,
            )
        )
        control = asyncio.run(admin_routes.shell_control_snapshot(is_admin=True))
        closed = asyncio.run(
            admin_routes.shell_unmount_app(
                mount_id=mounted["id"],
                is_admin=True,
            )
        )

    assert mounted["renderer"] == "host"
    assert mounted["content_url"].endswith("/generic")
    assert restored["items"][0]["context"]["message_id"] == "msg_" + "b" * 32
    assert control["safe_mode"]["active"] is False
    assert closed["status"] == "unmounted"


def test_admin_shell_unifies_app_approval_and_grant_revocation(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / "data"))
    runtime.start()
    dashboard, home, _ = runtime.extension_manager.launch_app("ai2apps.dashboard")
    with patch.object(admin_routes, "_get_platform_runtime", return_value=runtime):
        created = asyncio.run(
            admin_routes.shell_create_capability_request(
                instance_id=dashboard.id,
                request=admin_routes.ShellCapabilityRequest(
                    session_id=home.id,
                    capabilities=["workspace.write"],
                    tool_name="workspace.write",
                    effects=["write"],
                    reason="Save Dashboard preferences",
                ),
                is_admin=True,
            )
        )
        inbox = asyncio.run(
            admin_routes.shell_approval_inbox(
                include_resolved=False,
                is_admin=True,
            )
        )
        decision = asyncio.run(
            admin_routes.shell_decide_approval(
                approval_id=created["id"],
                request=admin_routes.ShellApprovalDecisionRequest(
                    decision="approve",
                    scope="session",
                ),
                is_admin=True,
            )
        )
        grants = asyncio.run(
            admin_routes.shell_grant_leases(
                include_inactive=False,
                is_admin=True,
            )
        )
        revoked = asyncio.run(
            admin_routes.shell_revoke_grant(
                lease_id=decision["grant"]["id"],
                request=admin_routes.ShellGrantRevokeRequest(reason="test cleanup"),
                is_admin=True,
            )
        )

    assert inbox["items"][0]["id"] == created["id"]
    assert decision["request"]["status"] == "approved"
    assert decision["grant"]["scope"] == "session"
    assert grants["items"][0]["id"] == decision["grant"]["id"]
    assert revoked["revoke_reason"] == "test cleanup"
