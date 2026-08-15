# SPDX-License-Identifier: Apache-2.0
"""Managed Chrome contracts, authentication handoff, and Tool registration."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai2apps.browser import (
    AuthenticationChallenge,
    BrowserArticle,
    BrowserControlState,
    BrowserError,
    BrowserManager,
    BrowserSnapshot,
)
from ai2apps.config import PlatformConfig
from ai2apps.platform_runtime import PlatformRuntime


class FakeBrowserBackend:
    def __init__(self):
        self.started = False
        self.url = "about:blank"
        self.title = ""
        self.challenge = None
        self.info = {
            "tag": "button",
            "type": "",
            "autocomplete": "",
            "text": "Continue",
            "submits": False,
        }
        self.typed = []
        self.clicked = []
        self.hovered = []
        self.pointer_moves = []
        self.keys = []
        self.clipboard = []
        self.wait_result = {
            "satisfied": True,
            "condition": "element",
            "elapsed_ms": 5,
            "detail": {"state": "visible"},
        }
        self.tab_items = [
            {"id": "tab-1", "url": self.url, "title": self.title, "active": True}
        ]
        self.download_directory = None
        self.uploads = []
        self.snapshot_text = "Safe page text"
        self.snapshot_items = [
            {"ref": "e1", "tag": "button", "text": "Continue"}
        ]
        self.bidi_connected = True

    def start(self):
        self.started = True

    def set_download_directory(self, path):
        self.download_directory = Path(path)

    def stop(self):
        self.started = False

    def current(self):
        return self.url, self.title

    def recent_events(self):
        return [{"method": "browsingContext.load", "url": self.url}]

    def navigate(self, url):
        self.url = url
        self.title = "Test"
        self.tab_items[0].update(url=url, title=self.title)

    def tabs(self):
        return [dict(item) for item in self.tab_items]

    def open_tab(self, url=None):
        for item in self.tab_items:
            item["active"] = False
        tab_id = f"tab-{len(self.tab_items) + 1}"
        self.tab_items.append(
            {"id": tab_id, "url": url or "about:blank", "title": "", "active": True}
        )
        self.url = url or "about:blank"
        self.title = ""
        return tab_id

    def switch_tab(self, tab_id):
        for item in self.tab_items:
            item["active"] = item["id"] == tab_id
            if item["active"]:
                self.url, self.title = item["url"], item["title"]

    def close_tab(self, tab_id):
        self.tab_items = [item for item in self.tab_items if item["id"] != tab_id]
        self.tab_items[-1]["active"] = True
        self.url, self.title = self.tab_items[-1]["url"], self.tab_items[-1]["title"]
        return self.tab_items[-1]["id"]

    def detect_authentication(self):
        return self.challenge

    def snapshot(self, *, max_items, max_text, html_mode, max_html):
        return BrowserSnapshot(
            self.url,
            self.title,
            tuple(self.snapshot_items),
            self.snapshot_text,
            '<body data-ai2apps-rect="0,0,800,600"><button data-ai2apps-ref="e1" data-ai2apps-rect="1,2,3,4">Continue</button></body>',
            html_mode,
            False,
        )

    def read_article(
        self,
        *,
        mode,
        selector,
        include_images,
        include_links,
        max_chars,
        char_threshold,
        max_elements,
    ):
        return BrowserArticle(
            url=self.url,
            canonical_url="https://example.test/article",
            title="Reader title",
            byline="Example Author",
            site_name="Example",
            published_at="2026-08-13",
            language="en",
            direction="ltr",
            excerpt="Opening paragraph.",
            html=(
                '<p>Opening <strong>paragraph</strong>.</p>'
                '<pre><code data-ai2apps-code-lang="python">print(&quot;hello&quot;)</code></pre>'
            ),
            text='Opening paragraph. print("hello")',
            text_length=33,
            reading_time_minutes=1,
            extraction_method="readability",
            confidence="high",
            hidden_nodes_removed=3,
        )

    def target_info(self, target):
        return dict(self.info)

    def click(self, target, *, duration_ms=None):
        self.clicked.append((target, duration_ms))

    def hover(self, target, *, duration_ms=None):
        self.hovered.append((target, duration_ms))
        return {"x": 10, "y": 20, "duration_ms": duration_ms or 300}

    def move_pointer(self, *, target, x, y, duration_ms):
        self.pointer_moves.append((target, x, y, duration_ms))
        return {"x": x or 10, "y": y or 20, "duration_ms": duration_ms or 300}

    def type_text(
        self, target, text, *, clear, input_mode="natural", delay_ms=None
    ):
        self.typed.append((target, text, clear, input_mode, delay_ms))

    def key_press(self, *, key, modifiers, target, repeat):
        self.keys.append((key, modifiers, target, repeat))

    def clipboard_action(self, action, *, target):
        self.clipboard.append((action, target))

    def upload_file(self, target, path):
        self.uploads.append((target, Path(path)))

    def staged_downloads(self, *, wait_ms=0):
        return {
            "complete": [{"name": "result.pdf", "size_bytes": 10}],
            "in_progress": [],
        }

    def wait_for(self, **_kwargs):
        return dict(self.wait_result)

    def scroll(self, delta_y):
        pass

    def screenshot(self):
        return "cG5n"


class FakeWorkspace:
    def __init__(self, root: Path):
        self.root = root

    def browser_download_directory(self, session_id):
        path = self.root / session_id / "temporary" / "browser-downloads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolve_browser_upload(self, session_id, path):
        return self.root / session_id / "workspace" / path

    def adopt_browser_download(self, session_id, filename):
        return {
            "name": filename,
            "path": f"downloads/{filename}",
            "size_bytes": 10,
            "media_type": "application/pdf",
        }


@pytest.mark.asyncio
async def test_authentication_requires_user_and_blocks_agent_observation():
    backend = FakeBrowserBackend()
    manager = BrowserManager(backend)
    await manager.start(session_id="session-1")
    backend.challenge = AuthenticationChallenge("login", "Password field")

    result = await manager.navigate(
        "https://example.test/login", session_id="session-1"
    )
    assert result["state"] == "user_required"
    assert result["user_action_required"] is True

    with pytest.raises(BrowserError, match="must be completed by the user"):
        await manager.snapshot(session_id="session-1")

    handoff = await manager.begin_user_control()
    assert handoff["state"] == "user_control"
    still_blocked = await manager.complete_user_control()
    assert still_blocked["completed"] is False
    assert still_blocked["state"] == "user_required"

    await manager.begin_user_control()
    backend.challenge = None
    completed = await manager.complete_user_control()
    assert completed["completed"] is True
    assert completed["state"] == "agent_control"


@pytest.mark.asyncio
async def test_password_and_otp_fields_can_never_be_typed_by_agent():
    backend = FakeBrowserBackend()
    manager = BrowserManager(backend)
    await manager.start(session_id="session-1")
    backend.info = {
        "tag": "input",
        "type": "password",
        "autocomplete": "current-password",
        "text": "",
    }

    result = await manager.type_text(
        "e1", "must-not-be-recorded", session_id="session-1", clear=True
    )
    assert result["state"] == BrowserControlState.USER_REQUIRED.value
    assert backend.typed == []


@pytest.mark.asyncio
async def test_consequential_click_requires_explicit_commit_flag():
    backend = FakeBrowserBackend()
    manager = BrowserManager(backend)
    await manager.start(session_id="session-1")
    backend.info["text"] = "Publish post"

    with pytest.raises(BrowserError, match="commit=true"):
        await manager.click("e1", session_id="session-1", commit=False)
    result = await manager.click("e1", session_id="session-1", commit=True)
    assert result["commit"] is True
    assert backend.clicked == [("e1", None)]


@pytest.mark.asyncio
async def test_pointer_hover_keyboard_and_clipboard_actions():
    backend = FakeBrowserBackend()
    manager = BrowserManager(backend)

    hovered = await manager.hover("e1", session_id="session-1", duration_ms=420)
    assert hovered["pointer"] == {"x": 10, "y": 20, "duration_ms": 420}
    moved = await manager.move_pointer(
        session_id="session-1", x=30, y=40, duration_ms=250
    )
    assert moved["pointer"]["x"] == 30

    await manager.key_press(
        "ARROW_DOWN",
        session_id="session-1",
        modifiers=("SHIFT",),
        target="e1",
        repeat=2,
    )
    assert backend.keys == [("ARROW_DOWN", ("SHIFT",), "e1", 2)]

    copied = await manager.clipboard_action(
        "copy", session_id="session-1", target="e1"
    )
    assert copied["content_returned"] is False
    assert backend.clipboard == [("copy", "e1")]


@pytest.mark.asyncio
async def test_wait_returns_success_or_diagnostic_snapshot_on_timeout():
    backend = FakeBrowserBackend()
    manager = BrowserManager(backend)
    success = await manager.wait_for(
        session_id="session-1", condition="element", target="e1"
    )
    assert success["wait"]["satisfied"] is True

    backend.wait_result = {
        "satisfied": False,
        "condition": "text",
        "elapsed_ms": 20,
        "detail": {"text": "never appears"},
    }
    timeout = await manager.wait_for(
        session_id="session-1",
        condition="text",
        text="never appears",
        timeout_ms=0,
    )
    diagnostic = timeout["wait"]["diagnostic_snapshot"]
    assert diagnostic["text"] == "Safe page text"
    assert diagnostic["items"][0]["ref"] == "e1"


@pytest.mark.asyncio
async def test_observe_returns_compact_changes_since_snapshot():
    backend = FakeBrowserBackend()
    manager = BrowserManager(backend)
    await manager.snapshot(session_id="session-1")
    backend.snapshot_text = "Safe page text New result"
    backend.snapshot_items[0] = {
        "ref": "e1",
        "tag": "button",
        "text": "Completed",
    }
    backend.snapshot_items.append(
        {"ref": "e2", "tag": "a", "text": "Open result", "href": "/result"}
    )
    observed = await manager.observe_changes(session_id="session-1")
    change = observed["observation"]
    assert change["counts"] == {
        "added": 1,
        "removed": 0,
        "changed": 1,
        "text_changes": 1,
    }
    assert change["added"][0]["ref"] == "e2"
    assert change["changed"][0]["fields"]["text"]["after"] == "Completed"


@pytest.mark.asyncio
async def test_enter_on_form_requires_commit_and_natural_typing_is_configurable():
    backend = FakeBrowserBackend()
    manager = BrowserManager(backend)
    backend.info["submits"] = True
    with pytest.raises(BrowserError, match="commit=true"):
        await manager.key_press("ENTER", session_id="session-1", target="e1")
    await manager.key_press(
        "ENTER", session_id="session-1", target="e1", commit=True
    )

    backend.info["submits"] = False
    await manager.type_text(
        "e1",
        "hello",
        session_id="session-1",
        clear=True,
        input_mode="instant",
    )
    assert backend.typed[-1] == ("e1", "hello", True, "instant", None)

    with pytest.raises(BrowserError, match="browser.clipboard"):
        await manager.key_press(
            "v", session_id="session-1", modifiers=("META",), target="e1"
        )


@pytest.mark.asyncio
async def test_browser_is_owned_by_one_session_until_closed():
    manager = BrowserManager(FakeBrowserBackend())
    await manager.start(session_id="session-1")
    with pytest.raises(BrowserError, match="another active Session"):
        await manager.snapshot(session_id="session-2")
    await manager.close()
    result = await manager.start(session_id="session-2")
    assert result["owner_session_id"] == "session-2"


@pytest.mark.asyncio
async def test_tab_lifecycle_and_click_popup_detection():
    backend = FakeBrowserBackend()
    manager = BrowserManager(backend)
    opened = await manager.open_tab(
        session_id="session-1", url="https://example.test/new"
    )
    assert opened["opened_tab"] == "tab-2"
    listed = await manager.list_tabs(session_id="session-1")
    assert len(listed["tabs"]) == 2
    await manager.switch_tab("tab-1", session_id="session-1")
    closed = await manager.close_tab("tab-2", session_id="session-1")
    assert closed["active_tab"] == "tab-1"

    original_click = backend.click

    def popup_click(target, *, duration_ms=None):
        original_click(target, duration_ms=duration_ms)
        backend.open_tab("https://example.test/popup")

    backend.click = popup_click
    result = await manager.click(
        "e1", session_id="session-1", commit=False
    )
    assert result["new_tabs"][0]["url"] == "https://example.test/popup"


@pytest.mark.asyncio
async def test_upload_and_download_are_scoped_to_session_workspace(tmp_path):
    backend = FakeBrowserBackend()
    manager = BrowserManager(backend, workspace=FakeWorkspace(tmp_path))
    await manager.start(session_id="session-1")
    assert backend.download_directory == (
        tmp_path / "session-1" / "temporary" / "browser-downloads"
    )

    backend.info["type"] = "file"
    uploaded = await manager.upload_file(
        "e1", "attachments/input.txt", session_id="session-1"
    )
    assert uploaded["filename"] == "input.txt"
    assert backend.uploads[0][1] == (
        tmp_path / "session-1" / "workspace" / "attachments" / "input.txt"
    )

    downloads = await manager.collect_downloads(
        session_id="session-1", wait_ms=100
    )
    assert downloads["downloads"][0]["path"] == "downloads/result.pdf"


@pytest.mark.asyncio
async def test_snapshot_returns_visible_html_layout_and_requested_mode():
    manager = BrowserManager(FakeBrowserBackend())
    result = await manager.snapshot(session_id="session-1")
    snapshot = result["snapshot"]
    assert snapshot["html_mode"] == "visible"
    assert snapshot["html_truncated"] is False
    assert 'data-ai2apps-ref="e1"' in snapshot["html"]
    assert 'data-ai2apps-rect="1,2,3,4"' in snapshot["html"]

    full = await manager.snapshot(session_id="session-1", html_mode="full")
    assert full["snapshot"]["html_mode"] == "full"


@pytest.mark.asyncio
async def test_read_article_returns_markdown_html_and_metadata():
    manager = BrowserManager(FakeBrowserBackend())

    markdown = await manager.read_article(session_id="session-1")
    article = markdown["article"]
    assert article["format"] == "markdown"
    assert article["title"] == "Reader title"
    assert article["canonical_url"] == "https://example.test/article"
    assert article["content"].startswith("# Reader title")
    assert "**paragraph**" in article["content"]
    assert "```python" in article["content"]
    assert article["hidden_nodes_removed"] == 3

    both = await manager.read_article(
        session_id="session-1", output_format="both"
    )
    assert '<article data-ai2apps-reader="true"' in both["article"]["content_html"]
    assert "# Reader title" in both["article"]["content_markdown"]


@pytest.mark.asyncio
async def test_browser_rejects_non_http_and_credential_bearing_urls():
    manager = BrowserManager(FakeBrowserBackend())
    await manager.start(session_id="session-1")
    with pytest.raises(BrowserError, match="requires HTTP"):
        await manager.navigate("file:///etc/passwd", session_id="session-1")
    with pytest.raises(BrowserError, match="Credentials are not allowed"):
        await manager.navigate(
            "https://user:secret@example.test/", session_id="session-1"
        )


def test_platform_registers_browser_tools_and_commit_capability(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()

    assert runtime.browser is not None
    service = runtime.services.get_service("ai2apps.browser")
    click = runtime.services.get_tool("browser.click")
    snapshot = runtime.services.get_tool("browser.snapshot")
    article = runtime.services.get_tool("browser.read_article")
    type_tool = runtime.services.get_tool("browser.type")
    hover = runtime.services.get_tool("browser.hover")
    key = runtime.services.get_tool("browser.key")
    clipboard = runtime.services.get_tool("browser.clipboard")
    wait = runtime.services.get_tool("browser.wait")
    tabs = runtime.services.get_tool("browser.tabs")
    tab_close = runtime.services.get_tool("browser.tab_close")
    upload = runtime.services.get_tool("browser.upload")
    downloads = runtime.services.get_tool("browser.downloads")
    observe = runtime.services.get_tool("browser.observe")

    assert service.config["transport"] == "webdriver-bidi"
    assert service.config["authentication"] == "user-only"
    assert service.config["password_storage"] is False
    assert click.required_capabilities == ("browser.interact",)
    assert click.capability_rules == (
        {
            "when": {"property": "commit", "equals": True},
            "require": ["browser.commit"],
        },
    )
    assert type_tool.description.startswith("Type non-secret text")
    assert type_tool.input_schema["properties"]["input_mode"]["default"] == "natural"
    assert hover.required_capabilities == ("browser.interact",)
    assert key.capability_rules[0]["require"] == ["browser.commit"]
    assert set(clipboard.required_capabilities) == {
        "browser.interact",
        "browser.clipboard",
    }
    assert wait.required_capabilities == ("browser.read",)
    assert wait.input_schema["properties"]["condition"]["enum"] == [
        "element",
        "text",
        "url",
        "page_stable",
    ]
    assert tabs.required_capabilities == ("browser.read",)
    assert tab_close.required_capabilities == ("browser.interact",)
    assert set(upload.required_capabilities) == {
        "browser.interact",
        "browser.files",
    }
    assert set(downloads.required_capabilities) == {
        "browser.read",
        "browser.files",
    }
    assert observe.required_capabilities == ("browser.read",)
    assert snapshot.capability_rules == (
        {
            "when": {"property": "html_mode", "equals": "full"},
            "require": ["browser.read_full_html"],
        },
    )
    assert runtime.tools.required_capabilities(
        snapshot, {"html_mode": "visible"}
    ) == frozenset({"browser.read"})
    assert runtime.tools.required_capabilities(
        snapshot, {"html_mode": "full"}
    ) == frozenset({"browser.read", "browser.read_full_html"})
    assert article.required_capabilities == ("browser.read",)
    assert article.input_schema["properties"]["format"]["default"] == "markdown"
    assert runtime.config.paths.browsers_path == tmp_path / "platform" / "browsers"
