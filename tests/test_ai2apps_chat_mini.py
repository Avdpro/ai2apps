from pathlib import Path

from ai2apps.apps.system import SYSTEM_APP_MANIFESTS
from omlx.admin.routes import _shell_mount_payload

ROOT = Path(__file__).parents[1]


def test_chat_exposes_browser_sidebar_mini_entry():
    manifest = next(item for item in SYSTEM_APP_MANIFESTS if item["id"] == "ai2apps.general-chat")
    assert manifest["mini_entry"] == {
        "kind": "host",
        "resource": "ai2apps:system/chat-mini",
        "placements": ["sidebar"],
    }
    payload = _shell_mount_payload(None, {
        "id": "mount_chat_mini",
        "app_instance_id": "appi_chat",
        "renderer": "host",
        "resource": "ai2apps:system/chat-mini",
        "placement": "sidebar",
        "source": "builtin",
    })
    assert payload["content_url"] == "/admin/chat-mini"


def test_chat_mini_uses_current_page_and_selected_knowledge():
    template = (ROOT / "ai2apps/web/templates/system_apps/chat_mini.html").read_text()
    script = (ROOT / "ai2apps/web/static/js/chat_mini.js").read_text()
    assert "bidi_context" in script
    assert "browsingContext.getTree" in script
    assert "matches.length === 1" in script
    assert "/v1/platform/browser/webdriver-bidi" in script
    assert "script.callFunction" in script
    assert "browsingContext.captureScreenshot" in script
    assert "AI2AppsRequestBrowserContext" not in script
    assert "image_url" in script
    assert "modelSupportsVision" in script
    assert "modelSupportsConversation" in script
    assert "modelIsAvailable" in script
    assert "/v1/models/status" in script
    assert "status.load_failed !== true" in script
    assert "contexts/ai2apps.general-chat/search" in script
    assert "/v1/chat/completions" in script
    assert "data-prompt" in template
    assert "chat-mini-make-agent" not in template
    assert "Make Agent" not in template
    assert "chat-mini-page-title" not in template
    assert "chat-mini-page-domain" not in template
    assert "chat-mini-include-screenshot" in template
    assert "/agent-recipes" not in script
    assert "临时 Recipe" not in script


def test_browser_mini_entries_use_readable_typography_and_contrast():
    chat_template = (
        ROOT / "ai2apps/web/templates/system_apps/chat_mini.html"
    ).read_text()
    chat_css = (ROOT / "ai2apps/web/static/css/chat_mini.css").read_text()
    knowledge_css = (ROOT / "ai2apps/web/static/css/knowledge.css").read_text()
    agent_css = (ROOT / "ai2apps/web/static/css/agent_mini.css").read_text()
    agent_p0_css = (ROOT / "ai2apps/web/static/css/agent_mini_p0.css").read_text()

    assert "font-size:11px;font-weight:550" in chat_template
    assert ".chat-mini-screenshot svg{width:16px;height:16px;flex:none}" in chat_template
    assert "--cm-muted:#68645e" in chat_css
    assert ".chat-mini{font-size:13px;line-height:1.4}" in chat_css
    assert ".knowledge-mini{font-size:13px;line-height:1.4}" in knowledge_css
    assert ".knowledge-mini-context small{color:var(--kn-muted);font-size:11px}" in knowledge_css
    assert "--am-muted:#68645e" in agent_css
    assert ".agent-mini{font-size:13px;line-height:1.4}" in agent_css
    assert "font-size: 7px;" not in agent_p0_css
