"""Stable browser-runtime contracts and safety states."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class BrowserControlState(StrEnum):
    STOPPED = "stopped"
    AGENT_CONTROL = "agent_control"
    USER_REQUIRED = "user_required"
    USER_CONTROL = "user_control"


class BrowserError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class AuthenticationChallenge:
    kind: str
    reason: str


@dataclass(frozen=True, slots=True)
class BrowserRuntimeConfig:
    profile_path: str
    binary_path: str | None = None
    driver_path: str | None = None
    headless: bool = False
    page_load_timeout_seconds: float = 45.0


@dataclass(frozen=True, slots=True)
class BrowserSnapshot:
    url: str
    title: str
    items: tuple[dict[str, Any], ...]
    text: str
    html: str = ""
    html_mode: str = "visible"
    html_truncated: bool = False


@dataclass(frozen=True, slots=True)
class BrowserArticle:
    url: str
    canonical_url: str | None
    title: str | None
    byline: str | None
    site_name: str | None
    published_at: str | None
    language: str | None
    direction: str | None
    excerpt: str | None
    html: str
    text: str
    text_length: int
    reading_time_minutes: int
    extraction_method: str
    confidence: str
    truncated: bool = False
    warnings: tuple[str, ...] = ()
    hidden_nodes_removed: int = 0


@dataclass(slots=True)
class BrowserRuntimeStatus:
    state: BrowserControlState = BrowserControlState.STOPPED
    owner_session_id: str | None = None
    url: str | None = None
    title: str | None = None
    challenge: AuthenticationChallenge | None = None
    transport: str = "webdriver-bidi"
    engine: str = "chromium"
    bidi_connected: bool = False
    recent_events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "owner_session_id": self.owner_session_id,
            "url": self.url,
            "title": self.title,
            "challenge": (
                None
                if self.challenge is None
                else {
                    "kind": self.challenge.kind,
                    "reason": self.challenge.reason,
                }
            ),
            "transport": self.transport,
            "engine": self.engine,
            "bidi_connected": self.bidi_connected,
            "recent_events": self.recent_events[-20:],
        }
