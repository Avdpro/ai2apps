"""Core BrowserBackend operations over a Helper-managed AceFox BiDi session."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ai2apps.acefox_bidi import AceFoxAgentEndpoint, AceFoxBiDiConnection
from ai2apps.helper_control import HelperControlClient, HelperControlError

from .chrome import (
    _ARTICLE_SCRIPT,
    _AUTH_SCRIPT,
    _INSTALL_STABILITY_OBSERVER_SCRIPT,
    _READABILITY_SOURCE,
    _SNAPSHOT_SCRIPT,
    _TARGET_INFO_SCRIPT,
)
from .cookies import COOKIE_CONSENT_SCRIPT
from .models import (
    AuthenticationChallenge,
    BrowserArticle,
    BrowserError,
    BrowserRuntimeConfig,
    BrowserSnapshot,
)

HelperProvider = Callable[[], HelperControlClient | None]

_RENDER_BARRIER_SCRIPT = r"""
return new Promise(resolve => {
  let settled = false;
  let frames = 0;
  const finish = timedOut => {
    if (settled) return;
    settled = true;
    const root = document.documentElement;
    if (root) {
      void root.getBoundingClientRect();
      void getComputedStyle(root).display;
    }
    resolve({frames, timedOut, visibilityState: document.visibilityState});
  };
  const nextFrame = () => requestAnimationFrame(() => {
    frames += 1;
    if (frames < 2) {
      nextFrame();
      return;
    }
    setTimeout(() => requestAnimationFrame(() => {
      frames += 1;
      finish(false);
    }), 0);
  });
  nextFrame();
  setTimeout(() => finish(true), 2500);
});
"""


def _local_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean", "value": value}
    if isinstance(value, str):
        return {"type": "string", "value": value}
    if isinstance(value, (int, float)):
        return {"type": "number", "value": value}
    if isinstance(value, list | tuple):
        return {"type": "array", "value": [_local_value(item) for item in value]}
    if isinstance(value, dict):
        return {
            "type": "object",
            "value": [[str(key), _local_value(item)] for key, item in value.items()],
        }
    raise TypeError(f"Unsupported BiDi local value: {type(value).__name__}")


def _remote_value(value: dict[str, Any]) -> Any:
    value_type = value.get("type")
    if value_type in {"null", "undefined"}:
        return None
    if value_type in {"string", "boolean", "number", "bigint"}:
        return value.get("value")
    if value_type == "array":
        return [_remote_value(item) for item in value.get("value", [])]
    if value_type == "object":
        return {
            str(key): _remote_value(item)
            for key, item in value.get("value", [])
        }
    return value.get("value")


class AceFoxBrowserBackend:
    """Visible, actor-bound AceFox backend; interaction methods follow later."""

    engine = "firefox"

    def __init__(
        self,
        config: BrowserRuntimeConfig,
        helper_provider: HelperProvider = HelperControlClient.from_environment,
    ) -> None:
        self.config = config
        self.helper_provider = helper_provider
        self.connection: AceFoxBiDiConnection | None = None
        self._active_context: str | None = None
        self._actor_user_id: str | None = None
        self._download_directory: Path | None = None

    def start_for_actor(self, actor_user_id: str | None) -> None:
        if not actor_user_id:
            raise BrowserError(
                "browser_actor_required",
                "AceFox Agent requires an authenticated actor",
            )
        if self.connection is not None:
            if actor_user_id != self._actor_user_id:
                raise BrowserError(
                    "browser_actor_mismatch",
                    "The active AceFox Agent belongs to another actor",
                )
            return
        helper = self.helper_provider()
        if helper is None:
            raise BrowserError(
                "helper_unavailable", "AI2Apps Helper control channel is unavailable"
            )
        try:
            result = helper.launch_browser_agent(actor_user_id=actor_user_id)
        except HelperControlError as exc:
            raise BrowserError("helper_unavailable", str(exc)) from exc
        connection = AceFoxBiDiConnection(AceFoxAgentEndpoint.from_helper_result(result))
        try:
            deadline = time.monotonic() + self.config.page_load_timeout_seconds
            while True:
                try:
                    connection.connect()
                    break
                except Exception:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.1)
            self.connection = connection
            self._actor_user_id = actor_user_id
            contexts = self._contexts()
            if not contexts:
                raise BrowserError(
                    "active_tab_missing", "AceFox opened without a tab"
                )
            self._active_context = str(contexts[0]["context"])
            self._command(
                "session.subscribe",
                {
                    "events": [
                        "browsingContext.contextCreated",
                        "browsingContext.contextDestroyed",
                        "browsingContext.navigationStarted",
                        "browsingContext.load",
                    ]
                },
            )
            if self._download_directory is not None:
                self._apply_download_directory()
        except Exception:
            # Helper process creation and BiDi session setup form one logical
            # transaction. Never leave a visible actor-bound Agent behind when
            # its control connection or initial context setup fails.
            try:
                connection.close()
            except Exception:
                pass
            self.connection = None
            self._active_context = None
            self._actor_user_id = None
            try:
                helper.release_browser_agent(actor_user_id=actor_user_id)
            except HelperControlError:
                pass
            raise

    def start(self) -> None:
        self.start_for_actor(self._actor_user_id)

    def stop(self) -> None:
        actor_user_id = self._actor_user_id
        if self.connection is not None:
            self.connection.close()
        self.connection = None
        self._active_context = None
        self._actor_user_id = None
        if actor_user_id is None:
            return
        try:
            helper = self.helper_provider()
            if helper is not None:
                helper.release_browser_agent(actor_user_id=actor_user_id)
        except HelperControlError:
            # Local state is already closed. The Helper will still reap the
            # process on exit and its live table handles a later retry.
            pass

    def renew_lease(self) -> None:
        self._change_lease("renew_browser_agent")

    def pause_lease(self) -> None:
        self._change_lease("pause_browser_agent")

    def resume_lease(self) -> None:
        self._change_lease("resume_browser_agent")

    def _change_lease(self, operation: str) -> None:
        if self._actor_user_id is None or self.connection is None:
            raise BrowserError(
                "browser_not_running", "AceFox Agent is not running"
            )
        helper = self.helper_provider()
        if helper is None:
            raise BrowserError(
                "helper_unavailable", "AI2Apps Helper control channel is unavailable"
            )
        try:
            getattr(helper, operation)(actor_user_id=self._actor_user_id)
        except HelperControlError as exc:
            raise BrowserError("helper_unavailable", str(exc)) from exc

    @property
    def bidi_connected(self) -> bool:
        return self.connection is not None and self.connection.connected

    def recent_events(self) -> list[dict[str, Any]]:
        if self.connection is None:
            return []
        return [
            {
                "method": event.get("method"),
                "url": (event.get("params") or {}).get("url"),
                "timestamp": (event.get("params") or {}).get("timestamp"),
            }
            for event in self.connection.events
        ]

    def set_download_directory(self, path: str | Path) -> None:
        resolved = Path(path).expanduser().resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        self._download_directory = resolved
        if self.connection is not None:
            self._apply_download_directory()

    def _apply_download_directory(self) -> None:
        assert self._download_directory is not None
        self._command(
            "browser.setDownloadBehavior",
            {
                "downloadBehavior": {
                    "type": "allowed",
                    "destinationFolder": str(self._download_directory),
                }
            },
        )

    def navigate(self, url: str) -> None:
        self._command(
            "browsingContext.navigate",
            {"context": self._context(), "url": url, "wait": "complete"},
            timeout_seconds=self.config.page_load_timeout_seconds,
        )

    def current(self) -> tuple[str, str]:
        value = self._evaluate("({url: location.href, title: document.title})")
        return str(value["url"]), str(value["title"])

    def tabs(self) -> list[dict[str, Any]]:
        active = self._context()
        result = []
        for context in self._contexts():
            context_id = str(context["context"])
            try:
                title = self._evaluate("document.title", context=context_id)
            except BrowserError:
                title = ""
            result.append(
                {
                    "id": context_id,
                    "url": str(context.get("url") or ""),
                    "title": str(title or ""),
                    "active": context_id == active,
                }
            )
        return result

    def open_tab(self, url: str | None = None) -> str:
        result = self._command(
            "browsingContext.create",
            {"type": "tab", "referenceContext": self._context()},
        )
        self._active_context = str(result["context"])
        if url:
            self.navigate(url)
        return self._active_context

    def switch_tab(self, tab_id: str) -> None:
        if tab_id not in {str(item["context"]) for item in self._contexts()}:
            raise BrowserError("tab_not_found", f"Browser tab not found: {tab_id}")
        self._command("browsingContext.activate", {"context": tab_id})
        self._active_context = tab_id

    def close_tab(self, tab_id: str) -> str:
        contexts = [str(item["context"]) for item in self._contexts()]
        if tab_id not in contexts:
            raise BrowserError("tab_not_found", f"Browser tab not found: {tab_id}")
        if len(contexts) == 1:
            raise BrowserError("last_tab", "The final browser tab cannot be closed")
        self._command("browsingContext.close", {"context": tab_id})
        if self._active_context == tab_id:
            self._active_context = next(item for item in contexts if item != tab_id)
            self._command(
                "browsingContext.activate", {"context": self._active_context}
            )
        return self._context()

    def detect_authentication(self) -> AuthenticationChallenge | None:
        result = self._call_function(_AUTH_SCRIPT)
        if not result:
            return None
        return AuthenticationChallenge(str(result["kind"]), str(result["reason"]))

    def accept_cookie_consent(self, policy: str = "all") -> dict[str, Any]:
        return dict(self._call_function(COOKIE_CONSENT_SCRIPT, policy) or {})

    def snapshot(
        self,
        *,
        max_items: int,
        max_text: int,
        html_mode: str,
        max_html: int,
    ) -> BrowserSnapshot:
        url, title = self.current()
        result = self._call_function(
            _SNAPSHOT_SCRIPT,
            {
                "maxItems": max_items,
                "maxText": max_text,
                "htmlMode": html_mode,
                "maxHtml": max_html,
            },
        )
        return BrowserSnapshot(
            url=url,
            title=title,
            items=tuple(dict(item) for item in result["items"]),
            text=str(result["text"]),
            html=str(result["html"]),
            html_mode=str(result["htmlMode"]),
            html_truncated=bool(result["htmlTruncated"]),
        )

    def target_info(self, target: str | None) -> dict[str, Any]:
        result = self._call_function(_TARGET_INFO_SCRIPT, target)
        if result is None:
            raise BrowserError(
                "target_not_found", f"Browser target not found: {target or 'active element'}"
            )
        return dict(result)

    def _target_point(self, target: str) -> dict[str, int]:
        result = self._call_function(
            """
            const target=arguments[0];
            const selector=/^e\\d+$/.test(target)
              ? `[data-ai2apps-ref="${CSS.escape(target)}"]` : target;
            const deepFind=root => {
              const found=root.querySelector(selector); if(found) return found;
              for(const host of root.querySelectorAll('*')) if(host.shadowRoot){
                const nested=deepFind(host.shadowRoot); if(nested) return nested;
              }
              return null;
            };
            const el=deepFind(document); if(!el) return null;
            el.scrollIntoView({block:'center',inline:'center'});
            const rect=el.getBoundingClientRect();
            el.focus({preventScroll:true});
            return {x:Math.round(rect.left+rect.width/2),y:Math.round(rect.top+rect.height/2)};
            """,
            target,
        )
        if result is None:
            raise BrowserError("target_not_found", f"Browser target not found: {target}")
        return {"x": int(result["x"]), "y": int(result["y"])}

    def move_pointer(
        self,
        *,
        target: str | None,
        x: int | None = None,
        y: int | None = None,
        duration_ms: int | None = None,
    ) -> dict[str, int]:
        if target is not None:
            point = self._target_point(target)
            x, y = point["x"], point["y"]
        if x is None or y is None:
            raise BrowserError(
                "pointer_destination_required", "Provide a target or viewport x/y"
            )
        duration = max(0, min(duration_ms or 250, 2000))
        self._command(
            "input.performActions",
            {
                "context": self._context(),
                "actions": [
                    {
                        "type": "pointer",
                        "id": "ai2apps-mouse",
                        "parameters": {"pointerType": "mouse"},
                        "actions": [
                            {
                                "type": "pointerMove",
                                "x": int(x),
                                "y": int(y),
                                "duration": duration,
                                "origin": "viewport",
                            }
                        ],
                    }
                ],
            },
        )
        return {"x": int(x), "y": int(y), "duration_ms": duration}

    def hover(self, target: str, *, duration_ms: int | None = None) -> dict[str, int]:
        return self.move_pointer(target=target, duration_ms=duration_ms)

    def click(self, target: str, *, duration_ms: int | None = None) -> None:
        self.move_pointer(target=target, duration_ms=duration_ms)
        self._command(
            "input.performActions",
            {
                "context": self._context(),
                "actions": [
                    {
                        "type": "pointer",
                        "id": "ai2apps-mouse",
                        "parameters": {"pointerType": "mouse"},
                        "actions": [
                            {"type": "pointerDown", "button": 0},
                            {"type": "pause", "duration": 65},
                            {"type": "pointerUp", "button": 0},
                        ],
                    }
                ],
            },
        )

    def type_text(
        self,
        target: str,
        text: str,
        *,
        clear: bool,
        input_mode: str = "natural",
        delay_ms: int | None = None,
    ) -> None:
        self._target_point(target)
        if clear:
            self._call_function(
                """
                const target=arguments[0];
                const selector=/^e\\d+$/.test(target)
                  ? `[data-ai2apps-ref="${CSS.escape(target)}"]` : target;
                const el=document.querySelector(selector); if(!el) return false;
                el.value=''; el.dispatchEvent(new Event('input',{bubbles:true})); return true;
                """,
                target,
            )
        actions: list[dict[str, Any]] = []
        pause = max(0, min(delay_ms if delay_ms is not None else 32, 500))
        for character in text:
            actions.extend(
                [
                    {"type": "keyDown", "value": character},
                    {"type": "keyUp", "value": character},
                ]
            )
            if input_mode == "natural" and pause:
                actions.append({"type": "pause", "duration": pause})
        self._command(
            "input.performActions",
            {
                "context": self._context(),
                "actions": [{"type": "key", "id": "ai2apps-keyboard", "actions": actions}],
            },
        )

    @staticmethod
    def _key_value(key: str) -> str:
        aliases = {
            "BACKSPACE": "\ue003",
            "TAB": "\ue004",
            "ENTER": "\ue007",
            "RETURN": "\ue007",
            "SHIFT": "\ue008",
            "CONTROL": "\ue009",
            "CTRL": "\ue009",
            "ALT": "\ue00a",
            "META": "\ue03d",
            "CMD": "\ue03d",
            "COMMAND": "\ue03d",
            "ESCAPE": "\ue00c",
            "ESC": "\ue00c",
            "SPACE": " ",
            "ARROWLEFT": "\ue012",
            "ARROWUP": "\ue013",
            "ARROWRIGHT": "\ue014",
            "ARROWDOWN": "\ue015",
        }
        if len(key) == 1:
            return key
        normalized = key.upper().replace("-", "").replace("_", "")
        if normalized not in aliases:
            raise BrowserError("unsupported_key", f"Unsupported key: {key}")
        return aliases[normalized]

    def key_press(
        self,
        *,
        key: str,
        modifiers: tuple[str, ...],
        target: str | None,
        repeat: int,
    ) -> None:
        if target:
            self._target_point(target)
        modifier_values = [self._key_value(value) for value in modifiers]
        actions = [{"type": "keyDown", "value": value} for value in modifier_values]
        value = self._key_value(key)
        for _ in range(repeat):
            actions.extend(
                [{"type": "keyDown", "value": value}, {"type": "keyUp", "value": value}]
            )
        actions.extend(
            {"type": "keyUp", "value": value} for value in reversed(modifier_values)
        )
        self._command(
            "input.performActions",
            {
                "context": self._context(),
                "actions": [{"type": "key", "id": "ai2apps-keyboard", "actions": actions}],
            },
        )

    def clipboard_action(self, action: str, *, target: str | None) -> None:
        key = {"copy": "c", "cut": "x", "paste": "v"}[action]
        self.key_press(key=key, modifiers=("META",), target=target, repeat=1)

    def scroll(self, delta_y: int) -> None:
        self._call_function("window.scrollBy(0, arguments[0]); return true;", delta_y)

    def screenshot(self) -> str:
        result = self._command(
            "browsingContext.captureScreenshot", {"context": self._context()}
        )
        return str(result["data"])

    def staged_downloads(self, *, wait_ms: int = 0) -> dict[str, Any]:
        if self._download_directory is None:
            raise BrowserError(
                "downloads_unavailable", "No Session download directory is configured"
            )
        deadline = time.monotonic() + wait_ms / 1000
        while True:
            entries = [
                item
                for item in self._download_directory.iterdir()
                if item.is_file() and not item.is_symlink()
            ]
            in_progress = [item for item in entries if item.name.endswith(".part")]
            complete = [item for item in entries if not item.name.endswith(".part")]
            if complete or (entries and not in_progress) or time.monotonic() >= deadline:
                return {
                    "complete": [
                        {
                            "name": item.name,
                            "size_bytes": item.stat().st_size,
                            "modified_at": item.stat().st_mtime,
                        }
                        for item in sorted(complete, key=lambda value: value.stat().st_mtime)
                    ],
                    "in_progress": [item.name for item in in_progress],
                }
            time.sleep(0.1)

    def upload_file(self, target: str, path: str | Path) -> None:
        resolved = Path(path).resolve(strict=True)
        result = self._command(
            "script.callFunction",
            {
                "functionDeclaration": """function(target){
                  const selector=/^e\\d+$/.test(target)
                    ? `[data-ai2apps-ref="${CSS.escape(target)}"]` : target;
                  const deepFind=root => {
                    const found=root.querySelector(selector); if(found) return found;
                    for(const host of root.querySelectorAll('*')) if(host.shadowRoot){
                      const nested=deepFind(host.shadowRoot); if(nested) return nested;
                    }
                    return null;
                  };
                  return deepFind(document);
                }""",
                "target": {"context": self._context()},
                "awaitPromise": True,
                "resultOwnership": "root",
                "arguments": [_local_value(target)],
            },
        )
        remote = result.get("result") or {}
        shared_id = remote.get("sharedId")
        if not shared_id:
            raise BrowserError("target_not_found", f"Browser target not found: {target}")
        self._command(
            "input.setFiles",
            {
                "context": self._context(),
                "element": {"sharedId": shared_id},
                "files": [str(resolved)],
            },
        )

    def wait_for(
        self,
        *,
        condition: str,
        target: str | None,
        state: str,
        text: str | None,
        url_contains: str | None,
        timeout_ms: int,
        poll_ms: int,
        stable_ms: int,
    ) -> dict[str, Any]:
        started = time.monotonic()
        deadline = started + timeout_ms / 1000
        detail: dict[str, Any] = {}
        last_error: str | None = None
        while time.monotonic() <= deadline:
            try:
                satisfied = False
                if condition == "url":
                    url, _ = self.current()
                    satisfied = (url_contains or "") in url
                    detail = {"url": url, "url_contains": url_contains}
                elif condition == "text":
                    haystack = str(
                        self._call_function(
                            "return arguments[0] ? document.querySelector(arguments[0])?.textContent || '' : document.body?.innerText || '';",
                            target,
                        )
                    )
                    satisfied = (text or "") in haystack
                    detail = {"text": text, "target": target}
                elif condition == "element":
                    found = self._call_function(_TARGET_INFO_SCRIPT, target)
                    present = found is not None
                    satisfied = present if state not in {"hidden", "absent"} else not present
                    detail = {"state": state, "present": present}
                else:
                    stability = self._call_function(_INSTALL_STABILITY_OBSERVER_SCRIPT)
                    satisfied = (
                        stability["readyState"] == "complete"
                        and stability["quietMs"] >= stable_ms
                    )
                    detail = {
                        "ready_state": stability["readyState"],
                        "quiet_ms": round(stability["quietMs"]),
                        "mutations": stability["mutations"],
                    }
                    if satisfied:
                        barrier = self._call_function(_RENDER_BARRIER_SCRIPT)
                        stability = self._call_function(
                            _INSTALL_STABILITY_OBSERVER_SCRIPT
                        )
                        satisfied = (
                            not barrier["timedOut"]
                            and barrier["frames"] >= 3
                            and stability["readyState"] == "complete"
                            and stability["quietMs"] >= stable_ms
                        )
                        detail.update(
                            {
                                "quiet_ms": round(stability["quietMs"]),
                                "mutations": stability["mutations"],
                                "render_frames": barrier["frames"],
                                "render_timed_out": barrier["timedOut"],
                                "visibility_state": barrier["visibilityState"],
                            }
                        )
                if satisfied:
                    return {
                        "satisfied": True,
                        "condition": condition,
                        "elapsed_ms": round((time.monotonic() - started) * 1000),
                        "detail": detail,
                    }
            except Exception as exc:
                last_error = str(exc)
            time.sleep(poll_ms / 1000)
        return {
            "satisfied": False,
            "condition": condition,
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "detail": detail,
            "last_error": last_error,
        }

    def read_article(
        self,
        *,
        mode: str,
        selector: str | None,
        include_images: bool,
        include_links: bool,
        max_chars: int,
        char_threshold: int,
        max_elements: int,
    ) -> BrowserArticle:
        loaded = self._evaluate("typeof globalThis.__ai2appsReadability === 'function'")
        if not loaded:
            self._evaluate(f"(()=>{{{_READABILITY_SOURCE}\nsetReadablility();return true;}})()")
        result = self._call_function(
            _ARTICLE_SCRIPT,
            {
                "mode": mode,
                "selector": selector,
                "includeImages": include_images,
                "includeLinks": include_links,
                "maxChars": max_chars,
                "charThreshold": char_threshold,
                "maxElements": max_elements,
            },
        )
        return BrowserArticle(
            url=str(result["url"]),
            canonical_url=result.get("canonicalUrl"),
            title=result.get("title"),
            byline=result.get("byline"),
            site_name=result.get("siteName"),
            published_at=result.get("publishedAt"),
            language=result.get("language"),
            direction=result.get("direction"),
            excerpt=result.get("excerpt"),
            html=str(result.get("html") or ""),
            text=str(result.get("text") or ""),
            text_length=int(result.get("textLength") or 0),
            reading_time_minutes=int(result.get("readingTimeMinutes") or 1),
            extraction_method=str(result.get("extractionMethod") or "unknown"),
            confidence=str(result.get("confidence") or "low"),
            truncated=bool(result.get("truncated")),
            warnings=tuple(str(item) for item in result.get("warnings", ())),
            hidden_nodes_removed=int(result.get("hiddenNodesRemoved") or 0),
        )

    def _contexts(self) -> list[dict[str, Any]]:
        result = self._command("browsingContext.getTree", {"maxDepth": 0})
        return list(result.get("contexts", []))

    def _context(self) -> str:
        if self._active_context is None:
            raise BrowserError("browser_not_running", "AceFox Agent is not running")
        return self._active_context

    def _command(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if self.connection is None:
            raise BrowserError("browser_not_running", "AceFox Agent is not running")
        return self.connection.command(
            method, params, timeout_seconds=timeout_seconds
        )

    def _evaluate(self, expression: str, *, context: str | None = None) -> Any:
        result = self._command(
            "script.evaluate",
            {
                "expression": expression,
                "target": {"context": context or self._context()},
                "awaitPromise": True,
            },
        )
        if result.get("type") == "exception":
            raise BrowserError("script_failed", str(result.get("exceptionDetails")))
        return _remote_value(result["result"])

    def _call_function(self, body: str, *arguments: Any) -> Any:
        result = self._command(
            "script.callFunction",
            {
                "functionDeclaration": f"function(){{\n{body}\n}}",
                "target": {"context": self._context()},
                "awaitPromise": True,
                "arguments": [_local_value(value) for value in arguments],
            },
        )
        if result.get("type") == "exception":
            raise BrowserError("script_failed", str(result.get("exceptionDetails")))
        return _remote_value(result["result"])
