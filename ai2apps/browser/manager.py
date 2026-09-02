"""Single-user browser ownership and mandatory authentication handoff."""

from __future__ import annotations

import asyncio
import re
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .article import article_html_to_markdown, canonical_article_html
from .models import BrowserControlState, BrowserError, BrowserRuntimeStatus

_COMMIT_TEXT = re.compile(
    r"\b(publish|post|send|submit|delete|remove|buy|purchase|checkout|pay|confirm)\b|"
    r"发布|发送|提交|删除|购买|付款|支付|确认",
    re.IGNORECASE,
)
_SENSITIVE_AUTOCOMPLETE = {"current-password", "new-password", "one-time-code"}


class BrowserManager:
    def __init__(self, backend, workspace=None) -> None:
        self.backend = backend
        self.workspace = workspace
        self.status = BrowserRuntimeStatus(engine=getattr(backend, "engine", "unknown"))
        self._lock = asyncio.Lock()
        self._actor_user_id: str | None = None
        self._io_session_id: str | None = None
        self._observations: dict[str, dict[str, Any]] = {}

    async def _active_tab_id(self) -> str:
        tabs = await asyncio.to_thread(self.backend.tabs)
        active = next((item for item in tabs if item.get("active")), None)
        if active is None:
            raise BrowserError("active_tab_missing", "No active browser tab")
        return str(active["id"])

    @staticmethod
    def _observation_value(snapshot) -> dict[str, Any]:
        return {
            "url": snapshot.url,
            "title": snapshot.title,
            "items": {str(item["ref"]): dict(item) for item in snapshot.items},
            "text": snapshot.text,
        }

    @staticmethod
    def _text_changes(before: str, after: str) -> list[dict[str, str]]:
        if before == after:
            return []
        if after.startswith(before):
            return [{"operation": "insert", "before": "", "after": after[len(before) :][:1000]}]
        if before.startswith(after):
            return [{"operation": "delete", "before": before[len(after) :][:1000], "after": ""}]
        changes = []
        matcher = SequenceMatcher(None, before, after)
        for operation, left_start, left_end, right_start, right_end in matcher.get_opcodes():
            if operation == "equal":
                continue
            changes.append(
                {
                    "operation": operation,
                    "before": before[left_start:left_end][:1000],
                    "after": after[right_start:right_end][:1000],
                }
            )
            if len(changes) >= 12:
                break
        return changes

    async def _prepare_session_io(self, session_id: str | None) -> None:
        if self.workspace is None or session_id is None:
            return
        if self._io_session_id not in {None, session_id}:
            raise BrowserError(
                "browser_io_in_use", "Browser file staging belongs to another Session"
            )
        directory = await asyncio.to_thread(
            self.workspace.browser_download_directory, session_id
        )
        await asyncio.to_thread(self.backend.set_download_directory, directory)
        self._io_session_id = session_id

    async def start(
        self,
        *,
        session_id: str | None,
        actor_user_id: str | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            self._claim(session_id)
            self._bind_actor(actor_user_id)
            if self.status.state is BrowserControlState.STOPPED:
                await self._prepare_session_io(session_id)
                start_for_actor = getattr(self.backend, "start_for_actor", None)
                if start_for_actor is None:
                    await asyncio.to_thread(self.backend.start)
                else:
                    await asyncio.to_thread(start_for_actor, self._actor_user_id)
                self.status.state = BrowserControlState.AGENT_CONTROL
            else:
                await self._update_backend_lease("renew_lease")
            await self._refresh()
            return self.status.to_dict()

    async def close(self) -> dict[str, Any]:
        async with self._lock:
            await asyncio.to_thread(self.backend.stop)
            self.status = BrowserRuntimeStatus(
                engine=getattr(self.backend, "engine", "unknown")
            )
            self._actor_user_id = None
            self._io_session_id = None
            self._observations.clear()
            return self.status.to_dict()

    async def navigate(self, url: str, *, session_id: str | None) -> dict[str, Any]:
        async with self._lock:
            await self._ensure_agent_control(session_id)
            self._validate_url(url)
            await asyncio.to_thread(self.backend.navigate, url)
            await self._refresh()
            challenge = await self._detect_challenge()
            return {
                **self.status.to_dict(),
                "user_action_required": challenge is not None,
            }

    async def list_tabs(self, *, session_id: str | None) -> dict[str, Any]:
        async with self._lock:
            await self._ensure_agent_control(session_id)
            tabs = await asyncio.to_thread(self.backend.tabs)
            await self._refresh()
            return {**self.status.to_dict(), "tabs": tabs}

    async def accept_cookie_consent(
        self, *, session_id: str | None, policy: str = "all"
    ) -> dict[str, Any]:
        if policy not in {"all", "necessary"}:
            raise BrowserError("invalid_cookie_policy", policy)
        async with self._lock:
            await self._ensure_agent_control(session_id)
            handler = getattr(self.backend, "accept_cookie_consent", None)
            result = (
                await asyncio.to_thread(handler, policy)
                if handler is not None
                else {"handled": False, "policy": policy, "label": None}
            )
            await self._refresh()
            return {**self.status.to_dict(), "cookie_consent": result}

    async def open_tab(
        self, *, session_id: str | None, url: str | None = None
    ) -> dict[str, Any]:
        if url:
            self._validate_url(url)
        async with self._lock:
            await self._ensure_agent_control(session_id)
            tab_id = await asyncio.to_thread(self.backend.open_tab, url)
            challenge = await self._detect_challenge()
            await self._refresh()
            return {
                **self.status.to_dict(),
                "opened_tab": tab_id,
                "user_action_required": challenge is not None,
            }

    async def switch_tab(
        self, tab_id: str, *, session_id: str | None
    ) -> dict[str, Any]:
        async with self._lock:
            await self._ensure_agent_control(session_id)
            await asyncio.to_thread(self.backend.switch_tab, tab_id)
            challenge = await self._detect_challenge()
            await self._refresh()
            return {
                **self.status.to_dict(),
                "active_tab": tab_id,
                "user_action_required": challenge is not None,
            }

    async def close_tab(
        self, tab_id: str, *, session_id: str | None
    ) -> dict[str, Any]:
        async with self._lock:
            await self._ensure_agent_control(session_id)
            active = await asyncio.to_thread(self.backend.close_tab, tab_id)
            await self._refresh()
            return {**self.status.to_dict(), "closed_tab": tab_id, "active_tab": active}

    async def snapshot(
        self,
        *,
        session_id: str | None,
        max_items: int = 150,
        max_text: int = 20_000,
        html_mode: str = "visible",
        max_html: int = 60_000,
    ) -> dict[str, Any]:
        async with self._lock:
            await self._ensure_agent_control(session_id)
            if await self._detect_challenge() is not None:
                return {**self.status.to_dict(), "user_action_required": True}
            snapshot = await asyncio.to_thread(
                self.backend.snapshot,
                max_items=max_items,
                max_text=max_text,
                html_mode=html_mode,
                max_html=max_html,
            )
            tab_id = await self._active_tab_id()
            self._observations[tab_id] = self._observation_value(snapshot)
            await self._refresh()
            return {
                **self.status.to_dict(),
                "snapshot": {
                    "url": snapshot.url,
                    "title": snapshot.title,
                    "items": list(snapshot.items),
                    "text": snapshot.text,
                    "html": snapshot.html,
                    "html_mode": snapshot.html_mode,
                    "html_truncated": snapshot.html_truncated,
                },
            }

    async def observe_changes(
        self,
        *,
        session_id: str | None,
        reset: bool = False,
        max_items: int = 200,
        max_text: int = 20_000,
    ) -> dict[str, Any]:
        async with self._lock:
            await self._ensure_agent_control(session_id)
            if await self._detect_challenge() is not None:
                return {**self.status.to_dict(), "user_action_required": True}
            tab_id = await self._active_tab_id()
            snapshot = await asyncio.to_thread(
                self.backend.snapshot,
                max_items=max_items,
                max_text=max_text,
                html_mode="visible",
                max_html=1_000,
            )
            current = self._observation_value(snapshot)
            previous = None if reset else self._observations.get(tab_id)
            self._observations[tab_id] = current
            if previous is None:
                changes: dict[str, Any] = {
                    "initial": True,
                    "added": list(current["items"].values()),
                    "removed": [],
                    "changed": [],
                    "text_changes": [],
                }
            else:
                old_items, new_items = previous["items"], current["items"]
                added = [new_items[ref] for ref in new_items.keys() - old_items.keys()]
                removed = [old_items[ref] for ref in old_items.keys() - new_items.keys()]
                changed = []
                for ref in old_items.keys() & new_items.keys():
                    fields = {}
                    for field in ("text", "href", "disabled", "role", "type", "rect"):
                        if old_items[ref].get(field) != new_items[ref].get(field):
                            fields[field] = {
                                "before": old_items[ref].get(field),
                                "after": new_items[ref].get(field),
                            }
                    if fields:
                        changed.append({"ref": ref, "fields": fields})
                changes = {
                    "initial": False,
                    "url_changed": previous["url"] != current["url"],
                    "title_changed": previous["title"] != current["title"],
                    "added": added,
                    "removed": removed,
                    "changed": changed,
                    "text_changes": self._text_changes(previous["text"], current["text"]),
                }
            await self._refresh()
            return {
                **self.status.to_dict(),
                "observation": {
                    "tab_id": tab_id,
                    "url": current["url"],
                    "title": current["title"],
                    "counts": {
                        "added": len(changes["added"]),
                        "removed": len(changes["removed"]),
                        "changed": len(changes["changed"]),
                        "text_changes": len(changes["text_changes"]),
                    },
                    **changes,
                },
            }

    async def read_article(
        self,
        *,
        session_id: str | None,
        output_format: str = "markdown",
        mode: str = "auto",
        selector: str | None = None,
        include_images: bool = True,
        include_links: bool = True,
        max_chars: int = 100_000,
        char_threshold: int = 500,
        max_elements: int = 100_000,
    ) -> dict[str, Any]:
        if output_format not in {"markdown", "html", "both"}:
            raise BrowserError("invalid_article_format", output_format)
        if mode not in {"auto", "strict"}:
            raise BrowserError("invalid_article_mode", mode)
        async with self._lock:
            await self._ensure_agent_control(session_id)
            if await self._detect_challenge() is not None:
                return {**self.status.to_dict(), "user_action_required": True}
            article = await asyncio.to_thread(
                self.backend.read_article,
                mode=mode,
                selector=selector,
                include_images=include_images,
                include_links=include_links,
                max_chars=max_chars,
                char_threshold=char_threshold,
                max_elements=max_elements,
            )
            html = canonical_article_html(
                article.html,
                title=article.title,
                byline=article.byline,
                published_at=article.published_at,
                language=article.language,
                direction=article.direction,
            )
            markdown = None
            if output_format in {"markdown", "both"}:
                markdown = await asyncio.to_thread(
                    article_html_to_markdown,
                    article.html,
                    title=article.title,
                    byline=article.byline,
                    published_at=article.published_at,
                )
            payload: dict[str, Any] = {
                "url": article.url,
                "canonical_url": article.canonical_url,
                "title": article.title,
                "byline": article.byline,
                "site_name": article.site_name,
                "published_at": article.published_at,
                "language": article.language,
                "direction": article.direction,
                "excerpt": article.excerpt,
                "text_length": article.text_length,
                "reading_time_minutes": article.reading_time_minutes,
                "extraction_method": article.extraction_method,
                "confidence": article.confidence,
                "truncated": article.truncated,
                "warnings": list(article.warnings),
                "hidden_nodes_removed": article.hidden_nodes_removed,
                "format": output_format,
            }
            if output_format == "html":
                payload["content"] = html
            elif output_format == "markdown":
                payload["content"] = markdown
            else:
                payload["content_html"] = html
                payload["content_markdown"] = markdown
            await self._refresh()
            return {**self.status.to_dict(), "article": payload}

    async def click(
        self,
        target: str,
        *,
        session_id: str | None,
        commit: bool,
        duration_ms: int | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            await self._ensure_agent_control(session_id)
            tabs_before = {
                item["id"] for item in await asyncio.to_thread(self.backend.tabs)
            }
            info = await asyncio.to_thread(self.backend.target_info, target)
            if self._sensitive(info):
                self._require_user(
                    "login", "Authentication fields require user control"
                )
                return {**self.status.to_dict(), "user_action_required": True}
            commit_target = bool(_COMMIT_TEXT.search(info.get("text", "")))
            if commit_target and not commit:
                raise BrowserError(
                    "commit_confirmation_required",
                    "This control may create an external side effect; retry with commit=true after user approval",
                )
            await asyncio.to_thread(
                self.backend.click, target, duration_ms=duration_ms
            )
            await asyncio.sleep(0.1)
            tabs_after = await asyncio.to_thread(self.backend.tabs)
            new_tabs = [item for item in tabs_after if item["id"] not in tabs_before]
            challenge = await self._detect_challenge()
            await self._refresh()
            return {
                **self.status.to_dict(),
                "clicked": True,
                "commit": commit_target,
                "new_tabs": new_tabs,
                "user_action_required": challenge is not None,
            }

    async def hover(
        self,
        target: str,
        *,
        session_id: str | None,
        duration_ms: int | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            await self._ensure_agent_control(session_id)
            result = await asyncio.to_thread(
                self.backend.hover, target, duration_ms=duration_ms
            )
            await self._refresh()
            return {**self.status.to_dict(), "hovered": True, "pointer": result}

    async def move_pointer(
        self,
        *,
        session_id: str | None,
        target: str | None = None,
        x: int | None = None,
        y: int | None = None,
        duration_ms: int | None = None,
    ) -> dict[str, Any]:
        if target is None and (x is None or y is None):
            raise BrowserError(
                "pointer_destination_required", "Provide target or both x and y"
            )
        async with self._lock:
            await self._ensure_agent_control(session_id)
            result = await asyncio.to_thread(
                self.backend.move_pointer,
                target=target,
                x=x,
                y=y,
                duration_ms=duration_ms,
            )
            await self._refresh()
            return {**self.status.to_dict(), "moved": True, "pointer": result}

    async def wait_for(
        self,
        *,
        session_id: str | None,
        condition: str,
        target: str | None = None,
        state: str = "visible",
        text: str | None = None,
        url_contains: str | None = None,
        timeout_ms: int = 10_000,
        poll_ms: int = 100,
        stable_ms: int = 500,
    ) -> dict[str, Any]:
        allowed_conditions = {"element", "text", "url", "page_stable"}
        allowed_states = {
            "present",
            "visible",
            "hidden",
            "enabled",
            "clickable",
            "absent",
        }
        if condition not in allowed_conditions:
            raise BrowserError("invalid_wait_condition", condition)
        if condition == "element" and (not target or state not in allowed_states):
            raise BrowserError(
                "invalid_element_wait", "Element waits require target and valid state"
            )
        if condition == "text" and text is None:
            raise BrowserError("invalid_text_wait", "Text waits require text")
        if condition == "url" and url_contains is None:
            raise BrowserError("invalid_url_wait", "URL waits require url_contains")
        async with self._lock:
            await self._ensure_agent_control(session_id)
            result = await asyncio.to_thread(
                self.backend.wait_for,
                condition=condition,
                target=target,
                state=state,
                text=text,
                url_contains=url_contains,
                timeout_ms=timeout_ms,
                poll_ms=poll_ms,
                stable_ms=stable_ms,
            )
            if not result["satisfied"]:
                diagnostic = await asyncio.to_thread(
                    self.backend.snapshot,
                    max_items=80,
                    max_text=8_000,
                    html_mode="visible",
                    max_html=20_000,
                )
                result["diagnostic_snapshot"] = {
                    "url": diagnostic.url,
                    "title": diagnostic.title,
                    "items": list(diagnostic.items),
                    "text": diagnostic.text,
                    "html": diagnostic.html,
                    "html_truncated": diagnostic.html_truncated,
                }
            await self._refresh()
            return {**self.status.to_dict(), "wait": result}

    async def type_text(
        self,
        target: str,
        text: str,
        *,
        session_id: str | None,
        clear: bool,
        input_mode: str = "natural",
        delay_ms: int | None = None,
    ) -> dict[str, Any]:
        if input_mode not in {"natural", "instant"}:
            raise BrowserError("invalid_input_mode", input_mode)
        async with self._lock:
            await self._ensure_agent_control(session_id)
            info = await asyncio.to_thread(self.backend.target_info, target)
            if self._sensitive(info):
                self._require_user(
                    "login",
                    "Passwords and verification codes must be entered by the user",
                )
                return {**self.status.to_dict(), "user_action_required": True}
            await asyncio.to_thread(
                self.backend.type_text,
                target,
                text,
                clear=clear,
                input_mode=input_mode,
                delay_ms=delay_ms,
            )
            await self._refresh()
            return {
                **self.status.to_dict(),
                "typed": True,
                "input_mode": input_mode,
            }

    async def key_press(
        self,
        key: str,
        *,
        session_id: str | None,
        modifiers: tuple[str, ...] = (),
        target: str | None = None,
        repeat: int = 1,
        commit: bool = False,
    ) -> dict[str, Any]:
        async with self._lock:
            await self._ensure_agent_control(session_id)
            info = await asyncio.to_thread(self.backend.target_info, target)
            if self._sensitive(info):
                self._require_user(
                    "login", "Authentication fields require user keyboard control"
                )
                return {**self.status.to_dict(), "user_action_required": True}
            normalized = key.upper().replace("-", "_")
            normalized_modifiers = {
                value.upper().replace("-", "_") for value in modifiers
            }
            if normalized.lower() in {"c", "x", "v"} and normalized_modifiers & {
                "META",
                "COMMAND",
                "CMD",
                "CONTROL",
                "CTRL",
            }:
                raise BrowserError(
                    "clipboard_capability_required",
                    "Use browser.clipboard for copy, cut, and paste shortcuts",
                )
            may_submit = normalized in {"ENTER", "RETURN"} and info.get("submits")
            consequential = bool(_COMMIT_TEXT.search(info.get("text", "")))
            if (may_submit or consequential) and not commit:
                raise BrowserError(
                    "commit_confirmation_required",
                    "This key may submit a form or activate a consequential control; retry with commit=true after user approval",
                )
            await asyncio.to_thread(
                self.backend.key_press,
                key=key,
                modifiers=modifiers,
                target=target,
                repeat=repeat,
            )
            challenge = await self._detect_challenge()
            await self._refresh()
            return {
                **self.status.to_dict(),
                "key_pressed": key,
                "repeat": repeat,
                "commit": bool(may_submit or consequential),
                "user_action_required": challenge is not None,
            }

    async def clipboard_action(
        self,
        action: str,
        *,
        session_id: str | None,
        target: str | None = None,
    ) -> dict[str, Any]:
        if action not in {"copy", "cut", "paste"}:
            raise BrowserError("invalid_clipboard_action", action)
        async with self._lock:
            await self._ensure_agent_control(session_id)
            info = await asyncio.to_thread(self.backend.target_info, target)
            if self._sensitive(info):
                self._require_user(
                    "login", "Clipboard access to authentication fields is user-only"
                )
                return {**self.status.to_dict(), "user_action_required": True}
            await asyncio.to_thread(
                self.backend.clipboard_action, action, target=target
            )
            await self._refresh()
            return {
                **self.status.to_dict(),
                "clipboard_action": action,
                "content_returned": False,
            }

    async def upload_file(
        self,
        target: str,
        path: str,
        *,
        session_id: str | None,
    ) -> dict[str, Any]:
        if self.workspace is None or session_id is None:
            raise BrowserError(
                "workspace_required", "Uploads require a Session workspace"
            )
        async with self._lock:
            await self._ensure_agent_control(session_id)
            info = await asyncio.to_thread(self.backend.target_info, target)
            if str(info.get("type") or "").lower() != "file":
                raise BrowserError("not_file_input", "Target is not a file input")
            try:
                resolved = await asyncio.to_thread(
                    self.workspace.resolve_browser_upload, session_id, path
                )
            except Exception as exc:
                raise BrowserError("invalid_upload_path", str(exc)) from exc
            await asyncio.to_thread(self.backend.upload_file, target, resolved)
            await self._refresh()
            return {
                **self.status.to_dict(),
                "uploaded": True,
                "workspace_path": path,
                "filename": resolved.name,
            }

    async def collect_downloads(
        self,
        *,
        session_id: str | None,
        wait_ms: int = 0,
    ) -> dict[str, Any]:
        if self.workspace is None or session_id is None:
            raise BrowserError(
                "workspace_required", "Downloads require a Session workspace"
            )
        async with self._lock:
            await self._ensure_agent_control(session_id)
            staged = await asyncio.to_thread(
                self.backend.staged_downloads, wait_ms=wait_ms
            )
            adopted = []
            for item in staged["complete"]:
                try:
                    adopted.append(
                        await asyncio.to_thread(
                            self.workspace.adopt_browser_download,
                            session_id,
                            item["name"],
                        )
                    )
                except Exception as exc:
                    raise BrowserError("download_adoption_failed", str(exc)) from exc
            await self._refresh()
            return {
                **self.status.to_dict(),
                "downloads": adopted,
                "in_progress": staged["in_progress"],
            }

    async def scroll(self, delta_y: int, *, session_id: str | None) -> dict[str, Any]:
        async with self._lock:
            await self._ensure_agent_control(session_id)
            await asyncio.to_thread(self.backend.scroll, delta_y)
            await self._refresh()
            return {**self.status.to_dict(), "scrolled": delta_y}

    async def screenshot(self, *, session_id: str | None) -> dict[str, Any]:
        async with self._lock:
            await self._ensure_agent_control(session_id)
            if await self._detect_challenge() is not None:
                return {**self.status.to_dict(), "user_action_required": True}
            image = await asyncio.to_thread(self.backend.screenshot)
            await self._refresh()
            return {**self.status.to_dict(), "format": "png", "base64": image}

    async def begin_user_control(self) -> dict[str, Any]:
        async with self._lock:
            if self.status.state not in {
                BrowserControlState.USER_REQUIRED,
                BrowserControlState.AGENT_CONTROL,
            }:
                raise BrowserError(
                    "invalid_browser_state",
                    f"Cannot enter user control from {self.status.state.value}",
                )
            await self._update_backend_lease("pause_lease")
            self.status.state = BrowserControlState.USER_CONTROL
            self.status.recent_events = []
            return self.status.to_dict()

    async def complete_user_control(self) -> dict[str, Any]:
        async with self._lock:
            if self.status.state is not BrowserControlState.USER_CONTROL:
                raise BrowserError(
                    "invalid_browser_state", "The browser is not under user control"
                )
            challenge = await asyncio.to_thread(self.backend.detect_authentication)
            if challenge is not None:
                self.status.state = BrowserControlState.USER_REQUIRED
                self.status.challenge = challenge
                return {**self.status.to_dict(), "completed": False}
            await self._update_backend_lease("resume_lease")
            self.status.state = BrowserControlState.AGENT_CONTROL
            self.status.challenge = None
            await self._refresh()
            return {**self.status.to_dict(), "completed": True}

    async def get_status(self) -> dict[str, Any]:
        async with self._lock:
            if self.status.state is BrowserControlState.AGENT_CONTROL:
                await self._refresh()
            return self.status.to_dict()

    async def _ensure_agent_control(self, session_id: str | None) -> None:
        self._claim(session_id)
        if self.status.state is BrowserControlState.STOPPED:
            await self._prepare_session_io(session_id)
            start_for_actor = getattr(self.backend, "start_for_actor", None)
            if start_for_actor is None:
                await asyncio.to_thread(self.backend.start)
            else:
                await asyncio.to_thread(start_for_actor, self._actor_user_id)
            self.status.state = BrowserControlState.AGENT_CONTROL
        if self.status.state in {
            BrowserControlState.USER_REQUIRED,
            BrowserControlState.USER_CONTROL,
        }:
            raise BrowserError(
                "user_control_active",
                "Authentication must be completed by the user before Agent control resumes",
            )
        await self._update_backend_lease("renew_lease")

    async def _update_backend_lease(self, operation: str) -> None:
        callback = getattr(self.backend, operation, None)
        if callback is not None:
            await asyncio.to_thread(callback)

    def _claim(self, session_id: str | None) -> None:
        if self.status.owner_session_id is None:
            self.status.owner_session_id = session_id
        elif session_id is not None and self.status.owner_session_id != session_id:
            raise BrowserError(
                "browser_in_use",
                "The managed browser belongs to another active Session",
            )

    def bind_actor(
        self, session_id: str | None, actor_user_id: str | None
    ) -> None:
        """Bind trusted Tool context before any operation can auto-start a backend."""
        self._claim(session_id)
        self._bind_actor(actor_user_id)

    def _bind_actor(self, actor_user_id: str | None) -> None:
        if actor_user_id is None:
            return
        if self._actor_user_id is None:
            self._actor_user_id = actor_user_id
        elif self._actor_user_id != actor_user_id:
            raise BrowserError(
                "browser_actor_mismatch",
                "The managed browser belongs to another authenticated actor",
            )

    async def _detect_challenge(self):
        challenge = await asyncio.to_thread(self.backend.detect_authentication)
        if challenge is not None:
            self.status.challenge = challenge
            self.status.state = BrowserControlState.USER_REQUIRED
            self.status.recent_events = []
            if self.status.url:
                parsed = urlsplit(self.status.url)
                self.status.url = urlunsplit(
                    (parsed.scheme, parsed.netloc, parsed.path, "", "")
                )
            self.status.title = "Authentication required"
        return challenge

    def _require_user(self, kind: str, reason: str) -> None:
        from .models import AuthenticationChallenge

        self.status.challenge = AuthenticationChallenge(kind, reason)
        self.status.state = BrowserControlState.USER_REQUIRED

    async def _refresh(self) -> None:
        if self.status.state in {
            BrowserControlState.USER_REQUIRED,
            BrowserControlState.USER_CONTROL,
        }:
            return
        url, title = await asyncio.to_thread(self.backend.current)
        self.status.url = url
        self.status.title = title
        self.status.bidi_connected = bool(self.backend.bidi_connected)
        self.status.recent_events = self.backend.recent_events()[-20:]

    @staticmethod
    def _sensitive(info: dict[str, Any]) -> bool:
        return (
            info.get("type") == "password"
            or info.get("autocomplete") in _SENSITIVE_AUTOCOMPLETE
        )

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise BrowserError(
                "unsafe_browser_url", "Managed browser navigation requires HTTP(S)"
            )
        if parsed.username is not None or parsed.password is not None:
            raise BrowserError(
                "unsafe_browser_url", "Credentials are not allowed in browser URLs"
            )
