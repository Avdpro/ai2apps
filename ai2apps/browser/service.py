"""Register managed-browser tools with the authoritative Tool Gateway."""

from __future__ import annotations

from typing import Any

from ai2apps.services import (
    ServiceInstanceStatus,
    ServiceRegistry,
    ServiceRepository,
    ServiceRuntimeMode,
    ToolCallContext,
    ToolProviderError,
)

from .manager import BrowserManager
from .models import BrowserError

OBJECT = {"type": "object"}


def install_browser_service(
    manager: BrowserManager,
    repository: ServiceRepository,
    registry: ServiceRegistry,
) -> None:
    engine = str(getattr(manager.backend, "engine", "unknown"))
    service = repository.ensure_service(
        service_key="ai2apps.browser",
        package_id="ai2apps.browser",
        package_version="0.1.0",
        display_name="AI2Apps Browser",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
        capabilities=(
            "browser.read",
            "browser.read_full_html",
            "browser.interact",
            "browser.clipboard",
            "browser.files",
            "browser.commit",
        ),
        config={
            "engine": engine,
            "transport": "webdriver-bidi",
            "visible": True,
            "authentication": "user-only",
            "password_storage": False,
        },
    )
    instance = repository.ensure_instance(
        service_id=service.id,
        provider_key=f"builtin:browser-{engine}",
        status=ServiceInstanceStatus.RUNNING,
        endpoint="/v1/platform/browser/status",
        health={"status": "ready", "browser_state": "stopped"},
    )

    async def call(operation, *args, **kwargs):
        try:
            return await operation(*args, **kwargs)
        except BrowserError as exc:
            raise ToolProviderError(f"{exc.code}: {exc}") from exc

    def bind(context: ToolCallContext) -> None:
        try:
            manager.bind_actor(context.session_id, context.actor_user_id)
        except BrowserError as exc:
            raise ToolProviderError(f"{exc.code}: {exc}") from exc

    async def status(_: dict[str, Any], __: ToolCallContext):
        return await call(manager.get_status)

    async def open_browser(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        result = await call(
            manager.start,
            session_id=context.session_id,
            actor_user_id=context.actor_user_id,
        )
        if arguments.get("url"):
            result = await call(
                manager.navigate, arguments["url"], session_id=context.session_id
            )
        return result

    async def navigate(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.navigate, arguments["url"], session_id=context.session_id
        )

    async def list_tabs(_: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(manager.list_tabs, session_id=context.session_id)

    async def open_tab(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.open_tab,
            session_id=context.session_id,
            url=arguments.get("url"),
        )

    async def switch_tab(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.switch_tab,
            arguments["tab_id"],
            session_id=context.session_id,
        )

    async def close_tab(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.close_tab,
            arguments["tab_id"],
            session_id=context.session_id,
        )

    async def snapshot(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.snapshot,
            session_id=context.session_id,
            max_items=arguments.get("max_items", 150),
            max_text=arguments.get("max_text", 20_000),
            html_mode=arguments.get("html_mode", "visible"),
            max_html=arguments.get("max_html", 60_000),
        )

    async def read_article(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.read_article,
            session_id=context.session_id,
            output_format=arguments.get("format", "markdown"),
            mode=arguments.get("mode", "auto"),
            selector=arguments.get("selector"),
            include_images=arguments.get("include_images", True),
            include_links=arguments.get("include_links", True),
            max_chars=arguments.get("max_chars", 100_000),
            char_threshold=arguments.get("char_threshold", 500),
        )

    async def click(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.click,
            arguments["target"],
            session_id=context.session_id,
            commit=arguments.get("commit", False),
            duration_ms=arguments.get("duration_ms"),
        )

    async def hover(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.hover,
            arguments["target"],
            session_id=context.session_id,
            duration_ms=arguments.get("duration_ms"),
        )

    async def move_pointer(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.move_pointer,
            session_id=context.session_id,
            target=arguments.get("target"),
            x=arguments.get("x"),
            y=arguments.get("y"),
            duration_ms=arguments.get("duration_ms"),
        )

    async def wait_for(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.wait_for,
            session_id=context.session_id,
            condition=arguments["condition"],
            target=arguments.get("target"),
            state=arguments.get("state", "visible"),
            text=arguments.get("text"),
            url_contains=arguments.get("url_contains"),
            timeout_ms=arguments.get("timeout_ms", 10_000),
            poll_ms=arguments.get("poll_ms", 100),
            stable_ms=arguments.get("stable_ms", 500),
        )

    async def observe_changes(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.observe_changes,
            session_id=context.session_id,
            reset=arguments.get("reset", False),
            max_items=arguments.get("max_items", 200),
            max_text=arguments.get("max_text", 20_000),
        )

    async def type_text(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.type_text,
            arguments["target"],
            arguments["text"],
            session_id=context.session_id,
            clear=arguments.get("clear", False),
            input_mode=arguments.get("input_mode", "natural"),
            delay_ms=arguments.get("delay_ms"),
        )

    async def key_press(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.key_press,
            arguments["key"],
            session_id=context.session_id,
            modifiers=tuple(arguments.get("modifiers", ())),
            target=arguments.get("target"),
            repeat=arguments.get("repeat", 1),
            commit=arguments.get("commit", False),
        )

    async def clipboard_action(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.clipboard_action,
            arguments["action"],
            session_id=context.session_id,
            target=arguments.get("target"),
        )

    async def upload_file(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.upload_file,
            arguments["target"],
            arguments["path"],
            session_id=context.session_id,
        )

    async def collect_downloads(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.collect_downloads,
            session_id=context.session_id,
            wait_ms=arguments.get("wait_ms", 0),
        )

    async def scroll(arguments: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(
            manager.scroll,
            arguments["delta_y"],
            session_id=context.session_id,
        )

    async def screenshot(_: dict[str, Any], context: ToolCallContext):
        bind(context)
        return await call(manager.screenshot, session_id=context.session_id)

    definitions = (
        (
            "browser.status",
            "Browser status",
            "Return managed-browser control and handoff state without reading page content.",
            {"type": "object", "additionalProperties": False},
            (),
            (),
            (),
            status,
        ),
        (
            "browser.open",
            "Open browser",
            "Open the visible managed Chrome browser, optionally at an HTTP(S) URL.",
            {
                "type": "object",
                "properties": {"url": {"type": "string", "format": "uri"}},
                "additionalProperties": False,
            },
            ("external_read", "network"),
            ("browser.read",),
            (),
            open_browser,
        ),
        (
            "browser.navigate",
            "Navigate browser",
            "Navigate visible Chrome to an HTTP(S) page. Authentication challenges are handed to the user.",
            {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "format": "uri", "pattern": "^https?://"}
                },
                "required": ["url"],
                "additionalProperties": False,
            },
            ("external_read", "network"),
            ("browser.read",),
            (),
            navigate,
        ),
        (
            "browser.tabs",
            "List browser tabs",
            "List visible browser tabs and identify the active tab.",
            {"type": "object", "additionalProperties": False},
            ("external_read",),
            ("browser.read",),
            (),
            list_tabs,
        ),
        (
            "browser.tab_open",
            "Open browser tab",
            "Open and activate a new browser tab, optionally navigating to an HTTP(S) URL.",
            {
                "type": "object",
                "properties": {"url": {"type": "string", "format": "uri", "pattern": "^https?://"}},
                "additionalProperties": False,
            },
            ("external_read", "network"),
            ("browser.read",),
            (),
            open_tab,
        ),
        (
            "browser.tab_switch",
            "Switch browser tab",
            "Activate a browser tab returned by browser.tabs or a click result.",
            {
                "type": "object",
                "properties": {"tab_id": {"type": "string", "minLength": 1, "maxLength": 256}},
                "required": ["tab_id"],
                "additionalProperties": False,
            },
            (),
            ("browser.read",),
            (),
            switch_tab,
        ),
        (
            "browser.tab_close",
            "Close browser tab",
            "Close a browser tab while preserving at least one visible tab.",
            {
                "type": "object",
                "properties": {"tab_id": {"type": "string", "minLength": 1, "maxLength": 256}},
                "required": ["tab_id"],
                "additionalProperties": False,
            },
            ("local_write",),
            ("browser.interact",),
            (),
            close_tab,
        ),
        (
            "browser.snapshot",
            "Read browser page",
            "Return rendered text, stable element references, and HTML. The default visible mode prunes hidden nodes and includes data-ai2apps-rect layout attributes; full mode returns credential-redacted complete HTML and requires separate approval.",
            {
                "type": "object",
                "properties": {
                    "max_items": {"type": "integer", "minimum": 1, "maximum": 300},
                    "max_text": {"type": "integer", "minimum": 1000, "maximum": 50000},
                    "html_mode": {
                        "type": "string",
                        "enum": ["visible", "full"],
                        "default": "visible",
                    },
                    "max_html": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 1000000,
                        "default": 60000,
                    },
                },
                "additionalProperties": False,
            },
            ("external_read",),
            ("browser.read",),
            (
                {
                    "when": {"property": "html_mode", "equals": "full"},
                    "require": ["browser.read_full_html"],
                },
            ),
            snapshot,
        ),
        (
            "browser.read_article",
            "Read article",
            "Extract the current rendered page as a reader-mode article. Hidden content and page chrome are removed; output is sanitized Markdown by default, sanitized HTML, or both.",
            {
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["markdown", "html", "both"],
                        "default": "markdown",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["auto", "strict"],
                        "default": "auto",
                    },
                    "selector": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 1000,
                    },
                    "include_images": {"type": "boolean", "default": True},
                    "include_links": {"type": "boolean", "default": True},
                    "max_chars": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 500000,
                        "default": 100000,
                    },
                    "char_threshold": {
                        "type": "integer",
                        "minimum": 100,
                        "maximum": 5000,
                        "default": 500,
                    },
                },
                "additionalProperties": False,
            },
            ("external_read",),
            ("browser.read",),
            (),
            read_article,
        ),
        (
            "browser.click",
            "Click browser control",
            "Click an element reference from browser.snapshot or a CSS selector. Set commit=true for publish, send, purchase, delete, or similar consequential controls.",
            {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "commit": {"type": "boolean", "default": False},
                    "duration_ms": {
                        "type": "integer",
                        "minimum": 50,
                        "maximum": 3000,
                    },
                },
                "required": ["target"],
                "additionalProperties": False,
            },
            ("external_write",),
            ("browser.interact",),
            (
                {
                    "when": {"property": "commit", "equals": True},
                    "require": ["browser.commit"],
                },
            ),
            click,
        ),
        (
            "browser.hover",
            "Hover browser control",
            "Move the pointer to an element along a smooth accelerated/decelerated path and leave it hovered.",
            {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "duration_ms": {"type": "integer", "minimum": 50, "maximum": 3000},
                },
                "required": ["target"],
                "additionalProperties": False,
            },
            (),
            ("browser.interact",),
            (),
            hover,
        ),
        (
            "browser.pointer_move",
            "Move browser pointer",
            "Move the pointer naturally to an element or viewport coordinate. Useful for hover menus and canvas controls.",
            {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "x": {"type": "integer", "minimum": 0, "maximum": 20000},
                    "y": {"type": "integer", "minimum": 0, "maximum": 20000},
                    "duration_ms": {"type": "integer", "minimum": 50, "maximum": 3000},
                },
                "anyOf": [
                    {"required": ["target"]},
                    {"required": ["x", "y"]},
                ],
                "additionalProperties": False,
            },
            (),
            ("browser.interact",),
            (),
            move_pointer,
        ),
        (
            "browser.wait",
            "Wait for browser state",
            "Wait for an element state, rendered text, URL change, or a quiet completed DOM. Timeouts return a fresh diagnostic snapshot instead of leaving the Agent blind.",
            {
                "type": "object",
                "properties": {
                    "condition": {
                        "type": "string",
                        "enum": ["element", "text", "url", "page_stable"],
                    },
                    "target": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "state": {
                        "type": "string",
                        "enum": ["present", "visible", "hidden", "enabled", "clickable", "absent"],
                        "default": "visible",
                    },
                    "text": {"type": "string", "maxLength": 10000},
                    "url_contains": {"type": "string", "maxLength": 4000},
                    "timeout_ms": {"type": "integer", "minimum": 0, "maximum": 120000, "default": 10000},
                    "poll_ms": {"type": "integer", "minimum": 25, "maximum": 2000, "default": 100},
                    "stable_ms": {"type": "integer", "minimum": 100, "maximum": 10000, "default": 500},
                },
                "required": ["condition"],
                "additionalProperties": False,
            },
            ("external_read",),
            ("browser.read",),
            (),
            wait_for,
        ),
        (
            "browser.observe",
            "Observe browser changes",
            "Return a compact per-tab diff since the last snapshot or observation: controls added, removed, changed, plus bounded text edits. Use reset=true to establish a new baseline.",
            {
                "type": "object",
                "properties": {
                    "reset": {"type": "boolean", "default": False},
                    "max_items": {"type": "integer", "minimum": 1, "maximum": 300, "default": 200},
                    "max_text": {"type": "integer", "minimum": 1000, "maximum": 50000, "default": 20000},
                },
                "additionalProperties": False,
            },
            ("external_read",),
            ("browser.read",),
            (),
            observe_changes,
        ),
        (
            "browser.type",
            "Type in browser",
            "Type non-secret text into a page element. Password and verification fields always require direct user control.",
            {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "text": {"type": "string", "maxLength": 100000},
                    "clear": {"type": "boolean", "default": False},
                    "input_mode": {
                        "type": "string",
                        "enum": ["natural", "instant"],
                        "default": "natural",
                    },
                    "delay_ms": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 500,
                    },
                },
                "required": ["target", "text"],
                "additionalProperties": False,
            },
            ("external_write",),
            ("browser.interact",),
            (),
            type_text,
        ),
        (
            "browser.key",
            "Press browser key",
            "Press a named key or character, optionally with modifiers. Enter on forms and consequential controls requires commit=true.",
            {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "minLength": 1, "maxLength": 32},
                    "modifiers": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["SHIFT", "CONTROL", "CTRL", "ALT", "META", "COMMAND", "CMD"],
                        },
                        "uniqueItems": True,
                        "maxItems": 4,
                    },
                    "target": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "repeat": {"type": "integer", "minimum": 1, "maximum": 100, "default": 1},
                    "commit": {"type": "boolean", "default": False},
                },
                "required": ["key"],
                "additionalProperties": False,
            },
            ("external_write",),
            ("browser.interact",),
            (
                {
                    "when": {"property": "commit", "equals": True},
                    "require": ["browser.commit"],
                },
            ),
            key_press,
        ),
        (
            "browser.clipboard",
            "Use browser clipboard shortcut",
            "Send the platform copy, cut, or paste shortcut without returning clipboard contents. This can expose or overwrite the user's system clipboard and therefore has a separate capability.",
            {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["copy", "cut", "paste"]},
                    "target": {"type": "string", "minLength": 1, "maxLength": 1000},
                },
                "required": ["action"],
                "additionalProperties": False,
            },
            ("local_write", "external_write"),
            ("browser.interact", "browser.clipboard"),
            (),
            clipboard_action,
        ),
        (
            "browser.upload",
            "Upload workspace file",
            "Select a file from the current Session workspace in a browser file input. Host paths and files outside the workspace are rejected.",
            {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "path": {"type": "string", "minLength": 1, "maxLength": 2000},
                },
                "required": ["target", "path"],
                "additionalProperties": False,
            },
            ("external_write",),
            ("browser.interact", "browser.files"),
            (),
            upload_file,
        ),
        (
            "browser.downloads",
            "Collect browser downloads",
            "Wait for completed browser downloads and move them from isolated staging into the current Session workspace downloads directory.",
            {
                "type": "object",
                "properties": {
                    "wait_ms": {"type": "integer", "minimum": 0, "maximum": 120000, "default": 0},
                },
                "additionalProperties": False,
            },
            ("external_read", "local_write"),
            ("browser.read", "browser.files"),
            (),
            collect_downloads,
        ),
        (
            "browser.scroll",
            "Scroll browser",
            "Scroll the visible browser viewport by a signed pixel delta.",
            {
                "type": "object",
                "properties": {
                    "delta_y": {"type": "integer", "minimum": -10000, "maximum": 10000}
                },
                "required": ["delta_y"],
                "additionalProperties": False,
            },
            (),
            ("browser.interact",),
            (),
            scroll,
        ),
        (
            "browser.screenshot",
            "Capture browser screenshot",
            "Capture the current page as PNG. Disabled whenever user authentication control is required or active.",
            {"type": "object", "additionalProperties": False},
            ("external_read",),
            ("browser.read",),
            (),
            screenshot,
        ),
    )
    for (
        name,
        title,
        description,
        schema,
        effects,
        capabilities,
        rules,
        handler,
    ) in definitions:
        repository.ensure_tool(
            service_id=service.id,
            qualified_name=name,
            display_name=title,
            description=description,
            input_schema=schema,
            output_schema=OBJECT,
            effects=effects,
            required_capabilities=capabilities,
            capability_rules=rules,
            timeout_ms=60_000,
        )
        registry.bind_tool(name, provider_key=instance.provider_key, handler=handler)
