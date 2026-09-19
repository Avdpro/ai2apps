"""Mini-App Chat declaration and UI contract tests."""

from pathlib import Path

import pytest

from ai2apps.studio import StudioMiniAppRegistry, validate_chat_declaration

ROOT = Path(__file__).parents[1] / "ai2apps"


def test_builtin_host_adapter_gets_chat_capability():
    class Manager:
        @staticmethod
        def list_studio_mini_apps(_studio_id, *, principal=None):
            del principal
            return ()

    result = StudioMiniAppRegistry(Manager()).list(
        "example.studio",
        builtins=(
            {"id": "example.mini", "entry": {"kind": "host-adapter"}},
        ),
    )

    assert result["items"][0]["chat"] == {
        "schema": "ai2apps.mini-app-chat/v1",
        "enabled": True,
        "provider": "host-adapter",
        "context": {"transport": "studio-bridge", "maxBytes": 65536},
        "help": {
            "resource": "help/mini_apps/example.mini/help.md",
            "format": "markdown",
            "maxBytes": 32768,
        },
    }


def test_package_chat_contract_requires_explicit_tool_schemas():
    valid = {
        "schema": "ai2apps.mini-app-chat/v1",
        "enabled": True,
        "system_prompt": "Help operate this Mini-App.",
        "context": {"transport": "studio-bridge"},
        "help": {"resource": "docs/help.md", "max_bytes": 32768},
        "tools": [
            {
                "name": "set_prompt",
                "description": "Set the current prompt.",
                "input_schema": {
                    "type": "object",
                    "properties": {"prompt": {"type": "string"}},
                },
            }
        ],
    }
    validate_chat_declaration(valid)

    help_only = {**valid, "tools": []}
    validate_chat_declaration(help_only)

    invalid = {**valid, "tools": [{"name": "set prompt", "description": "bad", "input_schema": {"type": "object"}}]}
    with pytest.raises(ValueError, match="unique identifiers"):
        validate_chat_declaration(invalid)

    without_help = {key: value for key, value in valid.items() if key != "help"}
    with pytest.raises(ValueError, match="chat.help"):
        validate_chat_declaration(without_help)


def test_all_current_studios_embed_capability_driven_chat_mini_entry():
    shared = (ROOT / "web/static/js/mini_app_chat.js").read_text()
    chat_entry = (ROOT / "web/static/js/chat_mini.js").read_text()
    chat_template = (ROOT / "web/templates/system_apps/chat_mini.html").read_text()
    chat_css = (ROOT / "web/static/css/chat_mini.css").read_text()
    integration_css = (ROOT / "web/static/css/mini_app_chat.css").read_text()
    assert "ai2apps.mini-app-chat.request" in shared
    assert "tool_choice: 'auto'" in shared
    assert "confirmation === 'always'" in shared
    assert "ai2apps.mini-app-chat.provider-request" in shared
    assert "createPackageBridge" in shared and "registerPackageProvider" in shared
    assert "read_mini_app_help" in shared
    assert "request('help'" in shared
    assert "loadBuiltinHelp" in shared
    assert "contract.help.content" not in shared
    assert "startChatEntry" in chat_entry
    assert 'class="chat-mini-model"' in chat_template
    assert "chat-mini-model select{display:block;width:100%;max-width:none" in chat_css
    assert "grid-auto-flow:column" in integration_css
    assert "white-space:nowrap" in integration_css

    for name in ("video_studio", "readaloud", "imagine_studio"):
        template = (ROOT / f"web/templates/system_apps/{name}.html").read_text()
        script = (ROOT / f"web/static/js/{name}.js").read_text()
        assert 'leftView===\'chat\'&&miniAppChatEnabled' in template
        assert 'class="mini-app-chat-frame"' in template
        assert "describeMiniAppChat" in script
        assert "invokeMiniAppChatTool" in script
        assert "readMiniAppHelp" in script
        assert "source !== 'package'" in script
        assert "chat?.enabled === true" in script


def test_every_builtin_mini_app_has_bounded_lazy_help():
    mini_app_ids = {
        "ai2apps.video.text-to-video",
        "ai2apps.video.image-to-video",
        "ai2apps.video.reference-to-video",
        "ai2apps.video.composer",
        "ai2apps.video.extract-audio",
        "ai2apps.audio.quick-read",
        "ai2apps.audio.audiobook",
        "ai2apps.audio.ensemble-drama",
        "ai2apps.audio.voice-design",
        "ai2apps.audio.character-training",
        "ai2apps.imagine.text-to-image",
        "ai2apps.imagine.image-edit",
        "ai2apps.imagine.style-transfer",
        "ai2apps.imagine.reference-creation",
        "ai2apps.imagine.group-photo",
        "ai2apps.imagine.adjust-image",
        "ai2apps.imagine.character-design",
        "ai2apps.imagine.product-poster",
        "ai2apps.imagine.comic-storyboard",
    }
    for mini_app_id in mini_app_ids:
        help_path = ROOT / "web/static/help/mini_apps" / mini_app_id / "help.md"
        content = help_path.read_text()
        assert content.startswith("# ")
        assert len(content.encode()) <= 32768
