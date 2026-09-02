"""Contract tests for the AI2Apps WebUI Shell migration slice."""

import asyncio
import json
import plistlib
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from ai2apps.apps import SYSTEM_APP_MANIFESTS
from ai2apps.config import PlatformConfig
from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.platform_runtime import PlatformRuntime
from omlx.admin import routes as admin_routes

WEB_ROOT = Path(__file__).parents[1] / "ai2apps" / "web"
CORE_PRINCIPAL = RequestPrincipal.legacy_local()
MEMBER_PRINCIPAL = RequestPrincipal(
    actor_user_id="member-user",
    installation_id="device-one",
    organization_id="household-one",
    billing_account_id="core-billing",
    role=MemberRole.MEMBER,
    membership_epoch=1,
)


def test_system_app_catalog_covers_legacy_omlx_surfaces():
    assert {app["id"] for app in admin_routes.SYSTEM_APPS} == {
        "ai2apps.dashboard",
        "ai2apps.account",
        "ai2apps.sharing",
        "ai2apps.environment",
        "ai2apps.models",
        "ai2apps.discover",
        "ai2apps.agents",
        "ai2apps.general-chat",
        "ai2apps.ai-browser",
        "ai2apps.messager",
        "ai2apps.gallery",
        "ai2apps.knowledge",
        "ai2apps.readaloud",
        "ai2apps.video-studio",
        "ai2apps.imagine-studio",
        "ai2apps.trust-center",
        "ai2apps.settings",
        "ai2apps.logs",
        "ai2apps.terminal",
        "ai2apps.coder",
        "ai2apps.benchmark",
    }
    assert all(app["singleton"] for app in admin_routes.SYSTEM_APPS)


def test_default_dock_contains_core_creation_apps():
    assert {
        manifest["id"]
        for manifest in SYSTEM_APP_MANIFESTS
        if manifest["navigation"].get("pinned_default")
    } == {
        "ai2apps.general-chat",
        "ai2apps.ai-browser",
        "ai2apps.gallery",
        "ai2apps.knowledge",
        "ai2apps.discover",
        "ai2apps.coder",
        "ai2apps.readaloud",
        "ai2apps.video-studio",
        "ai2apps.imagine-studio",
    }


def test_shell_router_exposes_singleton_and_instance_urls():
    paths = {route.path for route in admin_routes.shell_router.routes}
    assert "/" in paths
    assert "/apps/{app_id}" in paths
    assert "/apps/{app_id}/instances/{instance_id}" in paths
    assert "/mobile" in paths
    assert "/mobile/complete" in paths
    assert "/auth/complete" in paths
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


def test_desktop_home_renders_shell_without_launching_dashboard():
    request = MagicMock()
    with patch.object(admin_routes, "templates") as templates:
        templates.TemplateResponse.return_value = MagicMock()
        asyncio.run(admin_routes.desktop_home(request=request, principal=CORE_PRINCIPAL))

    templates.TemplateResponse.assert_called_once_with(
        request,
        "shell.html",
        {
            "system_apps": admin_routes.SYSTEM_APPS,
            "initial_app_id": "",
            "initial_instance_id": None,
            "desktop_client_version": None,
            "desktop_client_build": None,
            "can_manage_system": True,
        },
    )


def test_desktop_shell_has_a_home_surface_and_root_navigation():
    shell = (WEB_ROOT / "templates" / "shell.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "shell.js").read_text()
    styles = (WEB_ROOT / "static" / "css" / "shell.css").read_text()

    assert 'class="desktop-home"' in shell
    assert 'data-shell-action="home"' in shell
    assert "function showHome(options)" in script
    assert "window.history.pushState({ home: true }, '', '/')" in script
    assert ".desktop-home-apps" in styles
    assert "shell.home.hero.line1" in shell
    assert "shell.home.hero.line2_prefix" in shell
    assert "shell.home.hero.line2_suffix" in shell
    assert "<span data-desktop-device-label>" in shell
    assert "default('Device', true)" in shell
    assert "function applyDesktopDeviceLabel()" in script
    assert "shell.home.open_source.title" in shell
    assert 'href="https://github.com/Avdpro/ai2apps"' in shell
    assert 'rel="noopener noreferrer"' in shell
    assert ".desktop-home-open-source" in styles
    assert "desktop-home-actions" not in shell
    assert "shell.home.action.chat" not in shell
    assert "shell.home.action.browse" not in shell
    assert "'ai2apps.general-chat',\n            'ai2apps.imagine-studio',\n            'ai2apps.readaloud',\n            'ai2apps.video-studio'," in script
    assert "const visible = preferred.map((id) => byId.get(id)).filter(Boolean);" in script
    assert 'data-desktop-home-account' in shell
    assert "function renderHomeAccount(result)" in script
    assert "homeAppsLocked" in script
    assert ".desktop-home-app.is-locked" in styles
    assert "function resumeProvisioningApp()" in script
    assert "'/v1/platform/provisioning/sessions'" in script
    assert "acknowledge-return" not in script
    assert "await resumeProvisioningApp()" in script


def test_desktop_dock_home_button_uses_logo_without_visible_wordmark():
    shell = (WEB_ROOT / "templates" / "shell.html").read_text()
    styles = (WEB_ROOT / "static" / "css" / "shell.css").read_text()

    assert 'class="dock-launcher-button"' in shell
    assert 'class="dock-logo"' in shell
    assert "shell.home.aria" in shell
    assert 'class="dock-wordmark"' not in shell
    assert ".dock-wordmark" not in styles


def test_desktop_shell_auto_allows_only_chat_microphone_requests():
    repository_root = Path(__file__).parents[1]
    shell_script = (WEB_ROOT / "static" / "js" / "shell.js").read_text()
    browser_launcher = (
        repository_root
        / "apps/ai2apps-acefox/Sources/AI2AppsBrowserLauncher/main.swift"
    ).read_text()
    app_launcher = (
        repository_root
        / "apps/ai2apps-acefox/Sources/AI2AppsLauncher/main.swift"
    ).read_text()
    dev_packager = (
        repository_root / "apps/ai2apps-acefox/scripts/build-dev-app.sh"
    ).read_text()
    launcher_entitlements = (
        repository_root / "apps/ai2apps-acefox/entitlements/launcher.plist"
    ).read_text()

    assert "record.appId === 'ai2apps.general-chat'" in shell_script
    assert "clipboard-read; clipboard-write; microphone" in shell_script
    assert 'user_pref("permissions.default.microphone", 1);' in browser_launcher
    assert 'user_pref("permissions.default.microphone", 1);' in app_launcher
    assert 'user_pref("media.navigator.permission.disabled", true);' in browser_launcher
    assert 'user_pref("media.navigator.permission.disabled", true);' in app_launcher
    assert '"${PROJECT_DIR}/scripts/sign-release-app.sh"' in dev_packager
    assert 'codesign --force --deep --sign - "${SHELL_APP}"' not in dev_packager
    assert "com.apple.security.device.audio-input" in launcher_entitlements


def test_desktop_shell_downloads_always_open_the_native_save_dialog():
    repository_root = Path(__file__).parents[1]
    launchers = [
        repository_root
        / "apps/ai2apps-acefox/Sources/AI2AppsLauncher/main.swift",
        repository_root
        / "apps/ai2apps-acefox/Sources/AI2AppsBrowserLauncher/main.swift",
    ]

    for launcher in launchers:
        source = launcher.read_text()
        assert 'user_pref("browser.download.useDownloadDir", false);' in source
        assert 'user_pref("browser.download.useDownloadDir", true);' not in source


def test_desktop_shell_profile_disables_page_pinch_zooming():
    repository_root = Path(__file__).parents[1]
    launchers = [
        repository_root
        / "apps/ai2apps-acefox/Sources/AI2AppsLauncher/main.swift",
        repository_root
        / "apps/ai2apps-acefox/Sources/AI2AppsBrowserLauncher/main.swift",
    ]

    for launcher in launchers:
        source = launcher.read_text()
        assert 'user_pref("apz.allow_zooming", false);' in source
        assert 'user_pref("apz.allow_double_tap_zooming", false);' in source
        assert 'user_pref("browser.gesture.pinch.in", "");' in source
        assert 'user_pref("browser.gesture.pinch.in.shift", "");' in source
        assert 'user_pref("browser.gesture.pinch.out", "");' in source
        assert 'user_pref("browser.gesture.pinch.out.shift", "");' in source


def test_desktop_packages_one_shared_acefox_bundle_for_shell_and_agents():
    repository_root = Path(__file__).parents[1]
    contracts = (
        repository_root
        / "apps/ai2apps-acefox/Sources/AI2AppsContracts/HelperLaunchConfiguration.swift"
    ).read_text()
    launch_plan = (
        repository_root
        / "apps/ai2apps-acefox/Sources/AI2AppsSupervisorCore/BrowserAgentLaunchPlan.swift"
    ).read_text()
    dev_packager = (
        repository_root / "apps/ai2apps-acefox/scripts/build-dev-app.sh"
    ).read_text()
    release_packager = (
        repository_root / "apps/ai2apps-acefox/scripts/build-release-app.sh"
    ).read_text()
    verifier = (
        repository_root / "apps/ai2apps-acefox/scripts/verify-release-app.sh"
    ).read_text()

    assert "Applications/AI2AppsShell.app/Contents/MacOS/acefox-bin" in contracts
    assert "Resources/AceFoxAgent.app/Contents/MacOS/acefox-bin" not in contracts
    assert '"MOZ_APP_NO_DOCK": "1"' not in launch_plan
    assert "ditto \"${SHELL_APP}\" \"${AGENT_APP}\"" not in dev_packager
    assert "ditto \"${SHELL_APP}\" \"${AGENT_APP}\"" not in release_packager
    assert "AI2AppsSharedBrowserBundle bool true" in dev_packager
    assert "AI2AppsSharedBrowserBundle bool true" in release_packager
    assert "duplicated Agent Gecko bundle is still packaged" in verifier


def test_shell_recovers_if_firefox_restores_the_iframe_before_load_listener():
    shell_script = (WEB_ROOT / "static" / "js" / "shell.js").read_text()

    assert "function markFrameReady(record)" in shell_script
    assert "frame.contentDocument?.readyState === 'complete'" in shell_script
    assert "if (activeRecord) markFrameReady(activeRecord)" in shell_script
    assert "function watchFrameReadiness(record, remainingChecks = 100)" in shell_script
    assert "frameLocation !== 'about:blank'" in shell_script
    assert "watchFrameReadiness(record);" in shell_script


@pytest.mark.parametrize(
    ("system_name", "description", "expected"),
    [
        ("Darwin", "Apple MacBookPro", "Mac"),
        ("Windows", "Desktop", "PC"),
        ("Linux", "NVIDIA DGX Spark", "Spark"),
        ("Linux", "NVIDIA GB10", "Spark"),
        ("Linux", "Generic workstation", "PC"),
        ("FreeBSD", "Unknown", "Device"),
    ],
)
def test_desktop_device_label_matches_host(system_name, description, expected):
    assert admin_routes._desktop_device_label(system_name, description) == expected


def test_login_redirect_handler_preserves_desktop_home_destination():
    source = (Path(admin_routes.__file__).parents[1] / "server.py").read_text()
    assert '"/": "/admin?redirect=/"' in source


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
    assert "mobile_static('css/app-readability.css')" in mobile_base
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
            assert method == "GET"
            if path == "/v1/currency/balances":
                return CurrencyResponse(
                    {
                        "items": [
                            {
                                "assetCode": "PROMO_POINTS",
                                "available": "42",
                                "exponent": 0,
                            },
                            {
                                "assetCode": "USD_COMPUTE_CREDIT",
                                "available": "1250",
                                "exponent": 3,
                            },
                        ]
                    }
                )
            if path == "/v1/currency/provider-balances":
                return CurrencyResponse(
                    {
                        "items": [
                            {
                                "assetCode": "USD_PROVIDER_EARNINGS",
                                "available": "875",
                                "exponent": 3,
                            }
                        ]
                    }
                )
            assert path == "/v1/auth/me"
            return Response()

    class CurrencyResponse:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

        async def aclose(self):
            return None

    with patch.object(
        admin_routes,
        "_get_platform_runtime",
        return_value=SimpleNamespace(cloud=Cloud()),
    ):
        result = asyncio.run(
            admin_routes.shell_account_status(
                request=SimpleNamespace(cookies={}),
                principal=CORE_PRINCIPAL,
            )
        )

    assert result == {
        "installation_registered": False,
        "principal_actor_user_id": CORE_PRINCIPAL.actor_user_id,
        "principal_role": "core",
        "principal_is_core": True,
        "principal_membership_epoch": CORE_PRINCIPAL.membership_epoch,
        "state": "signed_in",
        "signed_in_user_is_core": False,
        "display_name": "Ada",
        "email": "ada@example.com",
        "points": "42",
        "currencies": [
            {"code": "points", "amount_minor": "42", "exponent": 0},
            {"code": "gas", "amount_minor": "1250", "exponent": 3},
            {"code": "cash", "amount_minor": "875", "exponent": 3},
        ],
    }


def test_core_user_can_update_installation_language():
    settings = SimpleNamespace(
        ui=SimpleNamespace(language="en"),
        save=MagicMock(),
    )
    with (
        patch.object(admin_routes, "_get_global_settings", return_value=settings),
        patch.object(admin_routes, "_refresh_i18n_globals") as refresh_i18n,
    ):
        result = asyncio.run(
            admin_routes.update_account_ui_language(
                request=admin_routes.AccountLanguageRequest(language="zh"),
                principal=CORE_PRINCIPAL,
            )
        )

    assert result == {"language": "zh"}
    assert settings.ui.language == "zh"
    settings.save.assert_called_once_with()
    refresh_i18n.assert_called_once_with()


def test_member_cannot_update_installation_language():
    with pytest.raises(admin_routes.HTTPException) as error:
        asyncio.run(
            admin_routes.update_account_ui_language(
                request=admin_routes.AccountLanguageRequest(language="zh"),
                principal=MEMBER_PRINCIPAL,
            )
        )

    assert error.value.status_code == 403


def test_member_can_read_device_locale_for_trusted_shell_surface():
    settings = SimpleNamespace(ui=SimpleNamespace(language="zh"))
    with patch.object(admin_routes, "_get_global_settings", return_value=settings):
        result = asyncio.run(
            admin_routes.shell_ui_locale(_principal=MEMBER_PRINCIPAL)
        )

    assert result["language"] == "zh"
    assert result["strings"]["chat"] == "对话"
    assert result["strings"]["currentPage"] == "当前页面"


def test_account_language_is_limited_to_english_and_chinese():
    with pytest.raises(ValueError):
        admin_routes.AccountLanguageRequest(language="ja")


def test_legacy_global_settings_endpoint_cannot_change_language():
    with (
        patch.object(
            admin_routes,
            "_get_global_settings",
            return_value=SimpleNamespace(),
        ),
        pytest.raises(admin_routes.HTTPException) as error,
    ):
        asyncio.run(
            admin_routes.update_global_settings(
                request=admin_routes.GlobalSettingsRequest(ui_language="zh"),
                is_admin=True,
            )
        )

    assert error.value.status_code == 400
    assert "Account App" in error.value.detail


def test_dock_account_status_uses_the_browser_isolated_cloud_session():
    class Response:
        status_code = 200

        def json(self):
            return {
                "user": {
                    "id": CORE_PRINCIPAL.actor_user_id,
                    "displayName": "Browser Core",
                    "email": "core@example.com",
                    "points": {"total": "99"},
                }
            }

        async def aclose(self):
            return None

    class BrowserCloud:
        async def request(self, method, path):
            assert method == "GET"
            if path == "/v1/auth/me":
                return Response()
            assert path in {
                "/v1/currency/balances",
                "/v1/currency/provider-balances",
            }
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"items": []},
                aclose=AsyncMock(),
            )

    global_cloud = MagicMock()
    runtime = SimpleNamespace(
        cloud=global_cloud,
        cloud_browser_session_from_cookies=lambda cookies: cookies.get(
            "ai2apps_cloud_browser_test"
        ),
        cloud_for_browser=lambda session_id: (
            BrowserCloud() if session_id == "b" * 32 else None
        ),
        database=None,
    )
    with patch.object(
        admin_routes,
        "_get_platform_runtime",
        return_value=runtime,
    ):
        result = asyncio.run(
            admin_routes.shell_account_status(
                request=SimpleNamespace(
                    cookies={"ai2apps_cloud_browser_test": "b" * 32}
                ),
                principal=CORE_PRINCIPAL,
            )
        )

    assert result["display_name"] == "Browser Core"
    assert result["email"] == "core@example.com"
    assert result["points"] == "99"
    assert result["currencies"] == [
        {"code": "points", "amount_minor": "99", "exponent": 0},
        {"code": "gas", "amount_minor": "0", "exponent": 0},
        {"code": "cash", "amount_minor": "0", "exponent": 0},
    ]
    global_cloud.request.assert_not_called()


def test_dock_account_status_marks_registered_core_signed_out():
    class Response:
        status_code = 401

        async def aclose(self):
            return None

    class Cloud:
        async def request(self, method, path):
            return Response()

    installation = SimpleNamespace(core_user_id="core-user")
    repository = MagicMock()
    repository.get_installation.return_value = installation
    runtime = SimpleNamespace(cloud=Cloud(), database=object())
    with (
        patch.object(admin_routes, "_get_platform_runtime", return_value=runtime),
        patch.object(admin_routes, "IdentityRepository", return_value=repository),
    ):
        result = asyncio.run(
            admin_routes.shell_account_status(
                request=SimpleNamespace(cookies={}),
                principal=CORE_PRINCIPAL,
            )
        )

    assert result == {
        "installation_registered": True,
        "principal_actor_user_id": CORE_PRINCIPAL.actor_user_id,
        "principal_role": "core",
        "principal_is_core": True,
        "principal_membership_epoch": CORE_PRINCIPAL.membership_epoch,
        "state": "signed_out",
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


def test_model_app_uses_device_authorization_for_cloud_catalog():
    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {"items": []}

        async def aclose(self):
            return None

    class Cloud:
        base_url = "https://coder.ai2apps.test"

        async def request(self, method, path, *, headers=None):
            captured.update(method=method, path=path, headers=headers)
            return Response()

    runtime = SimpleNamespace(
        cloud=Cloud(),
        cloud_ai_authorization_headers=lambda principal: {
            "Authorization": "Device device-id.device-secret",
            "X-AI2Apps-Actor-User-Id": principal.actor_user_id,
            "X-AI2Apps-Membership-Epoch": str(principal.membership_epoch),
        },
    )
    with patch.object(admin_routes, "_get_platform_runtime", return_value=runtime):
        provider = asyncio.run(
            admin_routes._ai2apps_cloud_provider(principal=CORE_PRINCIPAL)
        )

    assert provider["connection_state"] == "signed_in"
    assert captured == {
        "method": "GET",
        "path": "/v1/ai/models",
        "headers": {
            "Authorization": "Device device-id.device-secret",
            "X-AI2Apps-Actor-User-Id": CORE_PRINCIPAL.actor_user_id,
            "X-AI2Apps-Membership-Epoch": str(CORE_PRINCIPAL.membership_epoch),
        },
    }


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
        result = asyncio.run(
            admin_routes.get_model_manager(request=MagicMock(), is_admin=True)
        )

    managed_model = result["cloud"][0]["models"][0]
    assert managed_model["enabled"] is False
    assert managed_model["disabled_reason"] == (
        "Using local OpenAI API key (local provider takes priority)."
    )


def test_model_manager_does_not_treat_runtime_package_as_prepared_weights(tmp_path):
    recipe = {
        "id": "demo-cached-moe",
        "name": "Demo Cached-MoE",
        "recipe": "cache_moe",
        "sources": [{"repo_id": "demo/model", "revision": "pinned-revision"}],
    }
    runtime_model = {
        "id": "demo-cached-moe",
        "source_type": "package",
        "source_repo_id": "demo/model",
    }
    store = SimpleNamespace(
        list_cloud=lambda: [],
        list_fusion=lambda: [],
        default_models=lambda: {},
    )
    installer = SimpleNamespace(get_tasks=lambda: [])
    downloader = SimpleNamespace(model_dir=tmp_path)

    with (
        patch(
            "ai2apps.model_installer.AI2AppsInstaller.catalog",
            return_value=[recipe],
        ),
        patch(
            "ai2apps.model_installer.installed_shared_model_source_reference",
            return_value=None,
        ),
        patch.object(
            admin_routes,
            "list_models",
            new=AsyncMock(return_value={"models": [runtime_model]}),
        ),
        patch.object(admin_routes, "_hf_downloader", downloader),
        patch.object(admin_routes, "_get_ai2apps_installer", return_value=installer),
        patch.object(admin_routes, "_model_manager_store", return_value=store),
        patch.object(
            admin_routes,
            "_ai2apps_cloud_provider",
            new=AsyncMock(return_value={"models": []}),
        ),
    ):
        result = asyncio.run(
            admin_routes.get_model_manager(request=MagicMock(), is_admin=True)
        )

    cached = result["cached_moe"][0]
    assert cached["runtime_model"] == runtime_model
    assert cached["installed"] is False


def test_instance_route_preserves_requested_instance_id():
    request = MagicMock()
    manager = MagicMock()
    manager.instance_entry.return_value = {"app_key": "example.notes"}
    manager.list_apps.return_value = ({"app_key": "example.notes"},)
    with (
        patch.object(admin_routes, "templates") as templates,
        patch.object(admin_routes, "_shell_manager", return_value=manager),
    ):
        templates.TemplateResponse.return_value = MagicMock()
        asyncio.run(
            admin_routes.app_instance_shell(
                request=request,
                app_id="example.notes",
                instance_id="appi_0123456789abcdef0123456789abcdef",
                principal=CORE_PRINCIPAL,
            )
        )
        templates.TemplateResponse.assert_called_once_with(
            request,
            "shell.html",
            {
                "system_apps": admin_routes.SYSTEM_APPS,
            "initial_app_id": "example.notes",
            "initial_instance_id": "appi_0123456789abcdef0123456789abcdef",
            "desktop_client_version": None,
            "desktop_client_build": None,
            "can_manage_system": True,
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
                principal=CORE_PRINCIPAL,
            )
        )
        templates.TemplateResponse.assert_called_once_with(
            request,
            "shell.html",
            {
                "system_apps": admin_routes.SYSTEM_APPS,
            "initial_app_id": "ai2apps.models",
            "initial_instance_id": None,
            "desktop_client_version": None,
            "desktop_client_build": None,
            "can_manage_system": True,
            },
        )


def test_member_shell_exposes_only_member_apps_and_no_system_control():
    request = MagicMock()
    with patch.object(admin_routes, "templates") as templates:
        templates.TemplateResponse.return_value = MagicMock()
        asyncio.run(
            admin_routes.system_app_shell(
                request=request,
                app_id="ai2apps.general-chat",
                principal=MEMBER_PRINCIPAL,
            )
        )

    context = templates.TemplateResponse.call_args.args[2]
    assert {app["id"] for app in context["system_apps"]} == {
        "ai2apps.account",
        "ai2apps.general-chat",
        "ai2apps.ai-browser",
        "ai2apps.messager",
        "ai2apps.gallery",
        "ai2apps.knowledge",
        "ai2apps.readaloud",
        "ai2apps.video-studio",
        "ai2apps.imagine-studio",
    }
    assert context["can_manage_system"] is False


@pytest.mark.parametrize(
    "app_id",
    ["ai2apps.agents", "ai2apps.coder", "ai2apps.logs", "ai2apps.terminal"],
)
def test_member_cannot_open_sensitive_system_app_by_url(app_id):
    with pytest.raises(admin_routes.HTTPException) as error:
        asyncio.run(
            admin_routes.system_app_shell(
                request=MagicMock(),
                app_id=app_id,
                principal=MEMBER_PRINCIPAL,
            )
        )
    assert error.value.status_code == 404


@pytest.mark.parametrize(
    "app_id",
    ["ai2apps.agents", "ai2apps.coder", "ai2apps.logs", "ai2apps.terminal"],
)
def test_mobile_member_cannot_open_sensitive_app_content_by_url(app_id):
    with pytest.raises(admin_routes.HTTPException) as error:
        asyncio.run(
            admin_routes.remote_mobile_app_content(
                request=MagicMock(),
                app_id=app_id,
                principal=MEMBER_PRINCIPAL,
            )
        )
    assert error.value.status_code == 404


def test_mobile_gateway_propagates_principal_to_catalog_and_content():
    source = Path(admin_routes.__file__).read_text()

    assert "list_mobile_apps(\n            principal=principal,\n            locale=_current_ui_language()," in source
    assert "list_mobile_mounts(principal=principal)" in source
    assert "manager.launch_app(app_key, principal=principal)" in source
    assert "principal=principal,\n        mobile_surface=True" in source
    assert "principal=RequestPrincipal.legacy_local(),\n        mobile_surface=True" not in source
    assert "_mobile_proxy_auth_headers(request)" in source
    assert 'Cookie": f"{cookie_name}={local_session}"' in source
    assert "headers=_mobile_proxy_auth_headers(request)" in source
    assert 'headers={**_mobile_proxy_auth_headers(request), "Accept": "text/event-stream"}' in source
    assert '_require_system_app_access("ai2apps.agents", principal)' in source


def test_shell_rebuilds_cached_frames_when_local_principal_changes():
    script = (WEB_ROOT / "static" / "js" / "shell.js").read_text()

    assert "function synchronizeAccountBoundary()" in script
    assert "async function rebuildForPrincipalChange()" in script
    assert "record.frame.src = 'about:blank'" in script
    assert "loadCatalog({ quiet: true, fallback: false })" in script


def test_member_account_content_never_receives_core_api_key():
    request = MagicMock()
    with (
        patch.object(admin_routes, "templates") as templates,
        patch.object(
            admin_routes,
            "_get_global_settings",
            return_value=SimpleNamespace(auth=SimpleNamespace(api_key="core-secret")),
        ),
    ):
        templates.TemplateResponse.return_value = MagicMock()
        asyncio.run(
            admin_routes.system_app_content(
                request=request,
                app_id="ai2apps.account",
                principal=MEMBER_PRINCIPAL,
            )
        )

    context = templates.TemplateResponse.call_args.args[2]
    assert "api_key" not in context


def test_account_app_exposes_core_member_management_without_persisting_grants():
    template = (WEB_ROOT / "templates" / "system_apps" / "account.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "account.js").read_text()

    assert 'x-data="accountApp()"' in template
    assert 'x-init="init()"' not in template
    assert "account.members.invite_email" in template
    assert "account.members.role_password" in template
    assert "account.quota.title" in template
    assert "account.capacity.title" in template
    assert "account.devices.title" in template
    assert "account.devices.revoke_password" in template
    assert "account.devices.this_device" in template
    assert "revokeCoreDevice(device)" in template
    assert "renameCoreDevice(device)" in template
    assert "account.devices.device_name" in template
    assert template.count('x-model="uiLanguage"') == 1
    assert "currentCoreDevice.pendingDisplayName" in template
    assert "renameCoreDevice(currentCoreDevice)" in template
    assert 'x-if="device.id===currentCloudDeviceId"' in template
    assert "account.capacity.note" in template
    assert "account.members.seats" in template
    assert "account.policy.title" in template
    assert "account.members.one_use_link" in template
    assert "inviteQrDataUrl" in template
    assert "account.members.invitation_qr_alt" in template
    assert "account.capacity.pending_invitations" in template
    assert "account.members.creating_invitation" in template
    assert "account.members.creating_description" in template
    assert "invitationDeliveryLabel" in template
    assert "resendInvitation(pending)" in template
    assert "registrationNotice" in template
    assert "account.local_access.core_session" in template
    assert "installationAccess==='manager'" in template
    assert "cloud('/installation/members')" in script
    assert "cloud('/installation/invitations'" in script
    assert "cloud('/installation/invitations?status=pending')" in script
    assert "upsertPendingInvitation" in script
    assert "this.invitationCreating = true" in script
    assert "'/resend'" in script
    assert "account.delivery.failed_notice" in script
    assert "account.delivery.accepted" in script
    assert "cloud('/installation/policy'" in script
    assert "cloud('/capacity-policy')" in script
    assert "cloud('/account/devices')" in script
    assert "async revokeCoreDevice(device)" in script
    assert "async renameCoreDevice(device)" in script
    assert "method: 'PATCH', body: { displayName }" in script
    assert "ownerPassword: this.deviceOwnerPassword" in script
    assert "CORE_DEVICE_LIMIT_REACHED" in script
    assert "INSTALLATION_MEMBER_LIMIT_REACHED" in script
    assert "get effectiveCapacityLimits()" in script
    assert "get memberSeatAvailable()" in script
    assert "busy||!inviteEmail||!memberSeatAvailable" in template
    assert "organization.member.quota_change" not in script
    assert "inviteUrl" in script
    assert "installationAccess: 'unknown'" in script
    assert "clearInstallationAccess('unregistered')" in script
    assert "account.notice.unregistered_account" in script
    assert "rejectUnregisteredCloudAccount()" in script
    assert "activateRegisteredCloudMember()" in script
    assert "activateCloudAccountIfMember()" in script
    assert "localAuth('/cloud-member/activate'" in script
    assert "this.user.id === this.localIdentity.actorUserId" in script
    assert "error.status === 404" not in script
    assert "this.isUnregisteredDeviceError(error)" in script
    assert "typeof payload.detail === 'object'" in script
    assert "'core_installation_required'" in script
    assert "this.installationAccess = isDeviceCore ? 'manager' : 'member'" in script
    assert ':readonly="!handoffEntryEnabled"' in template
    assert ':readonly="!credentialEntryEnabled"' in template
    assert "ownerPassword: this.memberOwnerPassword" in script
    assert "localStorage" not in script


def test_account_sections_preserve_identity_and_step_up_flows():
    template = (WEB_ROOT / "templates" / "system_apps" / "account.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "account.js").read_text()

    for section in ("overview", "devices", "organization", "security", "activity"):
        assert f"setSection('{section}')" in template
    assert "activeSection: 'overview'" in script
    assert "installationAccess !== 'manager'" in script

    # Account navigation is presentation-only: every identity recovery and
    # privileged reauthentication path remains mounted and server-authorized.
    for action in (
        'login()',
        'register()',
        'verifyEmail()',
        'resendCode()',
        'requestReset()',
        'resetPassword()',
        'connectLocalMember()',
        'logoutLocal()',
        'verifyAdmin()',
    ):
        assert action in template
    for secret_field in (
        'deviceOwnerPassword',
        'policyOwnerPassword',
        'memberOwnerPassword',
        'adminPassword',
    ):
        assert secret_field in template
    assert "ownerPassword: this.deviceOwnerPassword" in script
    assert "ownerPassword: this.policyOwnerPassword" in script
    assert "ownerPassword: this.memberOwnerPassword" in script
    assert "cloud('/admin/reauth'" in script
    assert 'x-model.number="adminDurationMinutes"' in template
    assert 'durationMinutes: this.adminDurationMinutes' in script
    for duration in (5, 15, 60, 180):
        assert f'<option value="{duration}">' in template
    assert "localStorage" not in script


def test_account_profile_and_primary_device_use_cloud_projections():
    template = (WEB_ROOT / "templates" / "system_apps" / "account.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "account.js").read_text()

    assert "account.public_profile.title" in template
    assert "profileDraft.visibility==='private'" in template
    assert "profileDraft.discoverableByEmail=false" in template
    assert "account.primary_device.note" in template
    assert "coreDevices.filter(item => item.status==='active')" in template
    assert "profile?.socialLinks" in template
    assert "cloud('/profile')" in script
    assert "cloud('/profile/primary-device'" in script
    assert "cloud('/profile/social-link-platforms')" in script
    assert "'/profile/social-links/' + encodeURIComponent" in script
    assert "body: { deviceId: this.selectedPrimaryDeviceId || null }" in script
    assert "draft.visibility === 'public' && Boolean(draft.discoverableByEmail)" in script
    assert "primaryNode.publicOrigin" not in script


def test_messager_is_local_first_and_cloud_fallback_is_explicit():
    template = (WEB_ROOT / "templates" / "system_apps" / "messager.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "messager.js").read_text()
    stylesheet = (WEB_ROOT / "static" / "css" / "messager.css").read_text()

    assert 'data-app-id="ai2apps.messager"' in template
    assert "messager.privacy.local_first" in template
    assert "messager.status.local_first" in template
    assert "messager.transport.local_unknown" in template
    assert "messager.action.rotate_identity" in template
    assert "request('/social/friends?limit=50')" in script
    assert "request('/public/profiles/lookup'" in script
    assert "request('/system-messages?state=all&limit=50')" in script
    assert "this.selected = { ...friend }" in script
    assert "if (!this.draftAttachment)" in script
    assert "localRequest('/send'" in script
    assert "localRequest('/device-key/rotate'" in script
    assert "messager.error.local_result_unknown" in script
    assert "request('/system-messages/offline'" in script
    assert "this.draftClientMessageId = crypto.randomUUID()" in script
    assert "this.draftSnapshot !== body" in script
    assert "this.draftRecipientUserId !== this.selected.userId" in script
    assert "await this.loadConversation()" in script
    assert "uploadRequest(this.draftAttachment)" in script
    assert "SYSTEM_MESSAGE_ATTACHMENT_NOT_AVAILABLE" in script
    assert "URL.createObjectURL(await response.blob())" in script
    assert "URL.revokeObjectURL" in script
    assert 'accept="image/png,image/jpeg,image/webp"' in template
    assert "localStorage" not in script
    assert ".messager-search svg{display:block;width:15px;height:15px}" in stylesheet
    assert ".messager-send svg{display:block;width:17px;height:17px}" in stylesheet


def test_messager_i18n_keys_exist_in_english_and_simplified_chinese():
    template = (WEB_ROOT / "templates" / "system_apps" / "messager.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "messager.js").read_text()
    keys = set(re.findall(r"(?<![A-Za-z0-9_])(?:t|tr)\('([^']+)'", template + script))

    for language in ("en", "zh"):
        translations = json.loads((WEB_ROOT / "i18n" / f"{language}.json").read_text())
        missing = keys - translations.keys()
        assert not missing, f"{language}.json is missing Messager keys: {sorted(missing)}"


def test_account_app_i18n_keys_exist_in_english_and_simplified_chinese():
    template = (WEB_ROOT / "templates" / "system_apps" / "account.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "account.js").read_text()
    keys = set(re.findall(r"(?<![A-Za-z0-9_])(?:t|tr)\('([^']+)'", template + script))

    for language in ("en", "zh"):
        translations = json.loads((WEB_ROOT / "i18n" / f"{language}.json").read_text())
        missing = keys - translations.keys()
        assert not missing, f"{language}.json is missing Account keys: {sorted(missing)}"


def test_unsafe_app_identifier_is_not_rendered():
    with pytest.raises(admin_routes.HTTPException) as error:
        asyncio.run(
            admin_routes.system_app_shell(
                request=MagicMock(),
                app_id="unsafe$app",
                principal=CORE_PRINCIPAL,
            )
        )
    assert error.value.status_code == 404


@pytest.mark.parametrize(
    ("app_id", "template_name", "tab"),
    [
        ("ai2apps.dashboard", "system_apps/dashboard.html", "status"),
        ("ai2apps.account", "system_apps/account.html", "account"),
        ("ai2apps.ai-browser", "system_apps/ai_browser.html", "ai-browser"),
        ("ai2apps.messager", "system_apps/messager.html", "messager"),
        ("ai2apps.gallery", "system_apps/gallery.html", "gallery"),
        ("ai2apps.knowledge", "system_apps/knowledge.html", "knowledge"),
        ("ai2apps.readaloud", "system_apps/readaloud.html", "readaloud"),
        ("ai2apps.video-studio", "system_apps/video_studio.html", "video-studio"),
        ("ai2apps.imagine-studio", "system_apps/imagine_studio.html", "imagine-studio"),
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
        patch.object(admin_routes, "can_access_developer_surfaces", return_value=True),
    ):
        templates.TemplateResponse.return_value = MagicMock()
        asyncio.run(
            admin_routes.system_app_content(
                request=request,
                app_id=app_id,
                principal=CORE_PRINCIPAL,
            )
        )
        context = {
            "system_app": {
                "id": app_id,
                "name": admin_routes._SYSTEM_APPS_BY_ID[app_id]["name"],
                "tab": tab,
            },
            "principal_actor_user_id": CORE_PRINCIPAL.actor_user_id,
            "principal_is_core": True,
            "developer_surfaces_visible": True,
            "client_environment": "browser",
        }
        if app_id in {"ai2apps.gallery", "ai2apps.knowledge"}:
            context.update(
                {"t": ANY, "locale_json": ANY, "current_lang": ANY}
            )
        templates.TemplateResponse.assert_called_once_with(
            request, template_name, context
        )


def test_system_app_content_marks_authenticated_desktop_shell_environment():
    request = MagicMock()
    with (
        patch.object(admin_routes, "templates") as templates,
        patch.object(admin_routes, "is_desktop_shell_request", return_value=True),
    ):
        templates.TemplateResponse.return_value = MagicMock()
        asyncio.run(
            admin_routes.system_app_content(
                request=request,
                app_id="ai2apps.video-studio",
                principal=CORE_PRINCIPAL,
            )
        )

    context = templates.TemplateResponse.call_args.args[2]
    assert context["client_environment"] == "desktop"


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
    assert "principalIsCore" in base
    assert "developerSurfacesVisible" in base


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
            },
            principal_is_core=True,
            developer_surfaces_visible=True,
        )
        assert f'data-app-id="{app_id}"' in rendered
        assert "window.AI2APPS_SYSTEM_APP" in rendered
        assert 'principalIsCore: true' in rendered
        assert 'developerSurfacesVisible: true' in rendered


def test_agent_manager_is_an_independent_management_surface():
    source = (WEB_ROOT / "templates" / "system_apps" / "agents.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "agent_manager.js").read_text()
    assert 'data-app-id="ai2apps.agents"' in source
    assert "Build, connect and automate system-wide Agents" in source
    assert ">Studio<" in source
    assert ">Workflows<" in source
    assert ">Schedules<" in source
    assert "/agents/' + encodeURIComponent(key) + '/management" in script
    assert "/interactive-packages/install" in script
    assert "/agent-runs?" in script
    assert "/agent-workflows" in script
    assert "/agent-schedules" in script
    assert "implicit AI" in source


def test_account_is_an_independent_optional_cloud_surface():
    source = (WEB_ROOT / "templates" / "system_apps" / "account.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "account.js").read_text()
    shell = (WEB_ROOT / "templates" / "shell.html").read_text()
    shell_script = (WEB_ROOT / "static" / "js" / "shell.js").read_text()

    assert 'data-app-id="ai2apps.account"' in source
    assert "account.auth.create_description" in source
    assert "'/v1/platform/cloud'" in script
    assert "'/v1/platform/remote'" in script
    assert "account.remote.title" in source
    assert "account.action.pair_phone" in source
    assert "!device.proxyConnected" in source
    assert "account.success.remote_rotated_reconnecting" in script
    assert "account.action.register_again" in source
    assert "reregisterRemote" in script
    assert "account.remote.scan_phone" in source
    assert "pairingQrDataUrl" in script
    assert "/devices/reconcile" in script
    assert "device.proxyConnected?tr('account.common.online')" in source
    assert "tr('account.remote.connecting')" in source
    assert "refreshRemoteConnectionState" in script
    assert "localStorage" not in script
    assert "/auth/login" in script
    assert "/auth/password/reset" in script
    for path in (
        "/currency/assets",
        "/currency/balances",
        "/currency/provider-balances",
        "/currency/ledger?limit=50",
    ):
        assert path in script
    assert "cloud('/points/ledger" not in script
    assert "formatMinor(value, exponent)" in script
    assert "Number(entry?.amountMinor)" not in script
    assert "USD_PROVIDER_EARNINGS" in script
    assert "account.promotion.title" in source
    assert "redeemPromotionCode()" in source
    assert "^A2P(?:-[A-F0-9]{4}){8}$" in script
    assert "promotion-redeem:" in script
    assert "'Idempotency-Key': attempt.idempotencyKey" in script
    assert "cloud('/promotion-codes/redeem'" in script
    assert "PROMOTION_POINTS_BALANCE_LIMIT" in script
    assert "cloud('/points')" in script
    assert "Promise.allSettled" in script
    assert "console.warn('Promotion code redemption failed'" in script
    assert "normalizedCode" not in script.split("console.warn('Promotion code redemption failed'", 1)[1].split("});", 1)[0]
    assert 'data-shell-action="account"' in shell
    assert "/admin/api/shell/account-status" in shell_script
    assert "/v1/platform/auth/session/refresh" in shell_script
    assert "Session expired" in shell_script
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
    assert "discover.hero.description" in source
    assert "discover.hero.trust" in source
    assert "App Store" not in source
    assert "Marketplace" not in source
    assert "/catalog/recommendations" in script
    assert "'/installed'" in script
    assert "publisher_signature_invalid" in script
    assert "discover.publish.hero.title" in source
    assert "discover.publish.key.title" in source
    assert "discover.publish.workflow.title" in source
    assert "discover.publish.review.title" in source
    assert "canReviewPackages" in script
    assert "publishingSignedIn" in script
    assert "adminStepUpActive" in script
    assert "verifyAdministrator" in script
    assert "/publishing/admin/reauth" in script
    assert "rejectSubmission" in script
    assert "reviewNotes[item.id]" in source
    assert "discover.publish.workflow.reject" in source
    assert "discover.error.self_approval_not_allowed" in script
    assert "/publishing/review-submissions" in script
    assert ':disabled="Boolean(working)"' in source
    assert "/publishing/submissions" in script
    assert "registerSelectedKey" in script
    assert "installed?.modelConfigurationId" in script
    assert "install-operations" in script
    assert "discover.install.step_count" in source
    assert "install-progress" in source
    assert "ai2apps.pendingModelPackage" in script
    assert "'/apps/ai2apps.models'" in script
    assert ".discover-description { margin:14px 0 17px; color:#52525b; font-size:13px;" in source
    assert ".discover-meta { display:flex; gap:10px; align-items:center; margin-top:auto; color:#71717a; font-size:11px;" in source
    assert ".discover-hero p { margin:10px 0 0; max-width:700px; color:#52525b; font-size:14px;" in source


def test_discover_compares_local_and_cloud_versions_for_upgrades():
    source = (WEB_ROOT / "templates" / "system_apps" / "discover.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "discover.js").read_text()

    assert "function compareVersions(left, right)" in script
    assert "compareVersions(cloud, local) > 0" in script
    assert "localVersionLabel(item)" in source
    assert "cloudVersionLabel(item)" in source
    assert "isInstalled(item.packageId)&&hasUpgrade(item)" in source
    assert "discover.action.upgrade" in source
    assert "isInstalled(item.packageId)&&!hasUpgrade(item)" in source


def test_discover_blocks_target_for_restart_required_dependency():
    source = (WEB_ROOT / "templates" / "system_apps" / "discover.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "discover.js").read_text()

    assert "dependency_restart_required" in script
    assert "installRequiredDependency" in script
    assert "requiredDependencyActionLabel" in script
    assert "pendingRestart(item)" in source
    assert "/v1/platform/client/restart-local" in script
    assert "installDialog?.result?.restartRequired" in source
    assert "resumeInstallContinuation" in script
    assert "request('/install-continuation')" in script
    assert "request('/install-continuation', { method: 'DELETE' })" in script


def test_discover_i18n_keys_exist_in_english_and_simplified_chinese():
    template = (WEB_ROOT / "templates" / "system_apps" / "discover.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "discover.js").read_text()
    keys = {
        key
        for key in re.findall(
            r"(?:t|tr)\(['\"](discover\.[a-zA-Z0-9_.]+)", template + script
        )
        if not key.endswith(".")
    }

    for language in ("en", "zh"):
        translations = json.loads((WEB_ROOT / "i18n" / f"{language}.json").read_text())
        missing = keys - translations.keys()
        assert not missing, (
            f"{language}.json is missing Discover keys: {sorted(missing)}"
        )


def test_shell_recovers_from_a_stale_app_instance_on_open():
    shell_script = (WEB_ROOT / "static" / "js" / "shell.js").read_text()

    assert "error.status = response.status" in shell_script
    assert "staleInstanceId && error.status === 404" in shell_script
    assert "framePool.delete(staleInstanceId)" in shell_script
    assert "'/launch'" in shell_script


def test_home_entry_i18n_keys_exist_in_every_supported_locale():
    template = (WEB_ROOT / "templates" / "shell.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "shell.js").read_text()
    keys = set(re.findall(
        r"(?:t|tr)\(['\"](shell\.[a-zA-Z0-9_.]+)",
        template + script,
    ))

    assert "shell.home.hero.line1" in keys
    assert "shell.home.account.setup.title" in keys
    assert "shell.home.apps.signin_description" in keys
    for language in ("en", "zh", "zh-TW", "ja", "ko", "fr", "es", "pt-BR", "ru"):
        translations = json.loads(
            (WEB_ROOT / "i18n" / f"{language}.json").read_text()
        )
        missing = keys - translations.keys()
        assert not missing, f"{language}.json is missing Home keys: {sorted(missing)}"


def test_shell_chat_content_never_receives_the_local_api_key():
    source = Path(admin_routes.__file__).read_text()
    assert '"ai2apps.general-chat",' in source
    assert 'context["api_key"] = settings.auth.api_key if settings else ""' not in source
    assert '"api_key": ""' in source


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
    assert "/v1/platform/coder/projects/" in script
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


def test_chat_sidebar_header_keeps_only_conversation_controls():
    chat = (WEB_ROOT / "templates" / "chat.html").read_text()
    assert "navbar-logo-light.svg" not in chat
    assert "navbar-logo-dark.svg" not in chat
    assert "runtime: oMLX" not in chat
    assert '<div class="flex items-center gap-2">' in chat
    assert 'flex-1 min-w-0 flex items-center gap-2' in chat
    assert ':data-tooltip="window.t(\'chat.close_sidebar\')"' in chat
    assert ':data-tooltip="window.t(\'chat.show_sidebar\')"' in chat
    assert "width: 46px" in chat
    assert "border-radius: 14px" in chat
    assert "z-index: 120" in chat
    assert "z-index: 121" in chat
    assert 'x-show="!sidebarOpen"' in chat
    assert "showLeftToggle" not in chat


def test_base_template_does_not_inject_a_dock_reveal_button():
    base = (WEB_ROOT / "templates" / "base.html").read_text(encoding="utf-8")

    assert "ai2apps-shell-reveal" not in base
    assert "showDockReveal" not in base
    assert "show_dock_reveal" not in base


def test_chat_right_sidebar_consolidates_controls_and_keeps_runtime_options_discoverable():
    chat = (WEB_ROOT / "templates" / "chat.html").read_text()
    sidebar_markup, settings_tail = chat.split("<!-- Chat Settings Modal -->", 1)
    settings_markup = settings_tail.split("<!-- Keyboard Shortcuts Help -->", 1)[0]

    assert "rightSidebarTab: 'chat'" in chat
    assert "attachMiniEntry(mount, { focus = true } = {})" in chat
    assert "this.attachMiniEntry(mount, { focus: false })" in chat
    assert "rightSidebarTab === 'profile'" not in chat
    assert "rightSidebarTab === 'settings'" not in chat
    assert "rightSidebarTab = 'profile'" not in chat
    assert "rightSidebarTab = 'settings'" not in chat
    assert 'x-show="!rightSidebarOpen"' in chat
    assert "showRightToggle" not in chat
    assert ':data-tooltip="window.t(\'chat.show_settings_tooltip\')"' in chat
    assert ':data-tooltip="window.t(\'chat.close_settings_tooltip\')"' in chat
    assert ".chat-hover-tip:not(.absolute)" in chat
    assert "chatSettings.showScrollButton" not in chat
    assert "chat.show_jump_button" not in chat
    assert 'x-show="!autoScrollEnabled && isCurrentChatStreaming()"' in chat
    assert 'x-show="availableAudioModels.length > 0"' in sidebar_markup
    assert 'x-model="audioSettings.sttModel"' in sidebar_markup
    assert 'x-model="audioSettings.ttsModel"' in sidebar_markup
    assert 'x-model="audioSettings.voice"' in sidebar_markup
    assert '@change="onAudioTtsModelChange()"' in sidebar_markup
    assert "voiceSettingsExpanded: false" in chat
    assert 'x-show="voiceSettingsExpanded" x-collapse' in sidebar_markup
    assert 'x-model.number="audioSettings.speed"' in sidebar_markup
    assert ':disabled="!audioTtsFeatureSupported(\'speed\')"' in sidebar_markup
    assert 'x-model="audioSettings.emotion"' in sidebar_markup
    assert "voice_speed_unavailable_tooltip" in sidebar_markup
    assert "voice_emotion_unavailable_tooltip" in sidebar_markup
    assert "isQwen3Tts" in chat
    assert 'x-model="audioSettings.instructions"' in sidebar_markup
    assert "loadAudioReference" in sidebar_markup
    assert 'x-model="audioSettings.referenceText"' in sidebar_markup
    assert 'x-model="audioSettings.autoSpeak"' in sidebar_markup
    assert "loadAudioVoices" in chat
    assert "`/v1/audio/voices?model=${encodeURIComponent(modelId)}`" in chat

    for binding in (
        "modelSettings.temperature",
        "modelSettings.max_tokens",
        "modelSettings.top_p",
        "modelSettings.top_k",
        "modelSettings.min_p",
        "modelSettings.repetition_penalty",
        "modelSettings.presence_penalty",
        "activePromptProfile",
        "systemPrompt",
        "chatSettings.maxImages",
        "chatSettings.maxImageSizeMb",
        "allowSvg",
    ):
        assert binding in chat

    assert "chat.fusion_unavailable_tooltip" in chat
    assert "chat.cached_moe_unavailable_tooltip" in chat
    assert ':disabled="!isFusionMode"' in chat
    assert ':disabled="!isCacheMoeMode || isFusionMode"' in chat
    for runtime_control in (
        "modelSettings.fusion_gate_policy",
        "modelSettings.fusion_mid_generation_review",
        "modelSettings.fusion_thinking_audit",
        "modelSettings.fusion_reviewer_guidance",
        "setL1OptimizationMode",
        "setFusionCacheL1Mode",
        "setFusionCacheEngineBoost",
        "setKvPolicy",
        "setEngineBoostMode",
    ):
        assert runtime_control in settings_markup
        assert runtime_control not in sidebar_markup
    assert "beginRush" in sidebar_markup
    assert "beginRush" not in settings_markup
    assert "chat-hover-tip" in chat
    assert "chat-runtime-setting" in settings_markup
    assert ':data-tooltip="isFusionMode ?' in settings_markup
    assert "chat.save_profile_disabled_tooltip" in settings_markup
    assert "width: min(520px, calc(100vw - 32px))" in chat
    assert "height: 90dvh" in chat
    assert ".chat-settings-layer" in chat
    assert ".chat-settings-header" in chat
    assert ".chat-settings-body" in chat
    assert "overflow-y: auto" in chat


def test_first_party_apps_share_a_scoped_readability_floor():
    css = (WEB_ROOT / "static" / "css" / "app-readability.css").read_text()
    chat = (WEB_ROOT / "templates" / "chat.html").read_text()

    assert '[data-app-id^="ai2apps."]' in css
    assert "--app-readable-supporting-size: 13px" in css
    assert "--app-readable-caption-size: 12px" in css
    assert "--app-readable-meta-size: 11px" in css
    assert ".account-app" in css
    assert ".agent-manager" in css
    assert ".trust-app" in css
    assert ".discover-app" in css
    assert ".coder-app" in css
    assert ".terminal-app" in css
    assert 'data-app-id="ai2apps.general-chat"' in chat


def test_shell_assets_cover_dock_launcher_pinning_and_bridge():
    shell = (WEB_ROOT / "templates" / "shell.html").read_text()
    css = (WEB_ROOT / "static" / "css" / "shell.css").read_text()
    js = (WEB_ROOT / "static" / "js" / "shell.js").read_text()
    base = (WEB_ROOT / "templates" / "base.html").read_text()

    assert "dock-hot-zone" in shell
    assert "data-desktop-client-version" in shell
    assert "window.ai2appsDesktop?.getDesktopInfo" in js
    assert "navigator.userAgent.match" in js
    assert "AI2Apps\\/([^\\s]+)" in js
    assert "await applyDesktopClientVersion()" in js
    assert "rawVersion.toLowerCase().startsWith('v')" in js
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
    assert "css/app-readability.css" in base
    assert "targetInstanceId" in base
    assert "options.targetInstanceId" in js
    assert "dock-context-menu" in shell
    assert "dock-context-dismiss" in shell
    assert ".dock-context-dismiss" in css
    assert "dockContextDismiss.hidden = false" in js
    assert "dockContextDismiss.hidden = true" in js
    assert "dockContextDismiss.addEventListener('pointerdown'" in js
    assert "dockContextDismiss.addEventListener('click'" in js
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
        "setBadge", "navigate", "openEntry", "openGalleryPreview", "mountMiniEntry",
        "requestCapability", "createAgentRun", "exportArtifact", "close",
    ):
        assert bridge_call in base
    assert "ai2apps.host.mini-entry-mounted" in shell_js
    assert 'class="shell-gallery-preview"' in shell
    assert "ai2apps.shell.open-gallery-preview" in shell_js
    assert "revealGalleryPreview" in shell_js
    assert "galleryPreviewFrame?.focus()" in shell_js
    assert "galleryPreviewCloseTimer" in shell_js
    assert "ai2apps.gallery.preview-ready" in shell_js
    assert "ai2apps.gallery.preview-close" in shell_js
    assert '@click.stop="open = !open"' in chat
    assert 'class="mini-app-menu" x-show="open"' in chat
    assert ":data-tooltip=\"open ? '' : 'Open an App Mini-Entry'\"" in chat
    assert 'class="w-9 h-9 flex items-center justify-center' in chat
    assert ".mini-app-launcher {" in chat
    assert "position: absolute" in chat
    assert "z-index: 300" in chat
    assert "pointer-events: auto" in chat
    assert "z-[105]" not in chat
    assert ".chat-hover-tip:focus-within" not in chat
    assert "$el.closest('details')" not in chat
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
    assert '<div class="mini-app-launcher' in chat


def test_shell_template_renders_boot_catalog():
    rendered = admin_routes.templates.env.get_template("shell.html").render(
        system_apps=admin_routes.SYSTEM_APPS,
        initial_app_id="ai2apps.dashboard",
        initial_instance_id=None,
        desktop_client_version="153.0.4",
        desktop_client_build="2242",
    )
    assert 'id="ai2apps-shell"' in rendered
    assert 'initialAppId: "ai2apps.dashboard"' in rendered
    assert '"id": "ai2apps.general-chat"' in rendered
    assert "AI2Apps Local" in rendered
    assert "· v153.0.4 (Build 2242)" in rendered


def test_desktop_client_version_reads_supervised_native_app_bundle(
    tmp_path, monkeypatch
):
    instance_root = tmp_path / "instance"
    data_path = instance_root / "data"
    run_path = instance_root / "run"
    app_path = tmp_path / "AI2Apps.app"
    info_path = app_path / "Contents" / "Info.plist"
    data_path.mkdir(parents=True)
    run_path.mkdir(parents=True)
    info_path.parent.mkdir(parents=True)
    with info_path.open("wb") as info_file:
        plistlib.dump(
            {"CFBundleShortVersionString": "153.0.4", "CFBundleVersion": "2242"},
            info_file,
        )
    (run_path / "shell.json").write_text(
        json.dumps({"app_bundle_path": str(app_path)}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        admin_routes,
        "_get_global_settings",
        lambda: SimpleNamespace(base_path=data_path),
    )

    assert admin_routes._desktop_client_version() == "153.0.4"
    assert admin_routes._desktop_client_release() == ("153.0.4", "2242")


def test_chat_template_renders_member_principal_boundary():
    rendered = admin_routes.templates.env.get_template("chat.html").render(
        api_key="",
        terminal_assistant=False,
        principal_actor_user_id="member-user",
        principal_is_core=False,
        developer_surfaces_visible=False,
    )

    assert 'const CHAT_PRINCIPAL_ACTOR_ID = "member-user"' in rendered
    assert "const CHAT_PRINCIPAL_IS_CORE = false" in rendered
    assert "const CHAT_DEVELOPER_SURFACES_VISIBLE = false" in rendered
    assert "model.owned_by !== 'omlx'" in rendered
    assert ">Agent</button>" not in rendered
    assert "const useAgent = CHAT_PRINCIPAL_IS_CORE && this.agentMode" in rendered


def test_chat_template_keeps_agent_mode_for_core_only():
    rendered = admin_routes.templates.env.get_template("chat.html").render(
        api_key="core-key",
        terminal_assistant=False,
        principal_actor_user_id="core-user",
        principal_is_core=True,
        developer_surfaces_visible=True,
    )

    assert ">Agent</button>" in rendered


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
        catalog = asyncio.run(admin_routes.shell_apps(principal=CORE_PRINCIPAL))
        launched = asyncio.run(
            admin_routes.shell_launch_app(
                app_key="ai2apps.dashboard",
                principal=CORE_PRINCIPAL,
            )
        )
        entry = asyncio.run(
            admin_routes.shell_instance_entry(
                instance_id=launched["instance_id"],
                principal=CORE_PRINCIPAL,
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
                principal=CORE_PRINCIPAL,
            )
        )
        restored = asyncio.run(
            admin_routes.shell_session_mounts(
                session_id=chat_session_id,
                principal=CORE_PRINCIPAL,
            )
        )
        control = asyncio.run(admin_routes.shell_control_snapshot(is_admin=True))
        closed = asyncio.run(
            admin_routes.shell_unmount_app(
                mount_id=mounted["id"],
                principal=CORE_PRINCIPAL,
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
