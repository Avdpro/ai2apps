"""Durable contracts for explicitly exported Local capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal


class CapabilityKind(StrEnum):
    MODEL = "model"
    TOOL = "tool"
    SERVICE = "service"
    AGENT = "agent"


@dataclass(frozen=True, slots=True)
class CapabilityExport:
    id: str
    kind: CapabilityKind
    target_id: str
    display_name: str
    protocols: tuple[str, ...]
    status: str
    created_by_user_id: str
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ShareGrant:
    id: str
    label: str
    status: str
    max_concurrency: int
    max_requests: int | None
    expires_at: datetime | None
    created_by_user_id: str
    request_count: int
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime
    exports: tuple[CapabilityExport, ...] = ()


@dataclass(frozen=True, slots=True)
class IssuedShareGrant:
    grant: ShareGrant
    token: str


@dataclass(frozen=True, slots=True)
class LocalNetworkAccess:
    mode: Literal["disabled", "share_only", "full"]
    bind_host: str
    port: int
    revision: int
    updated_by_user_id: str
    created_at: datetime
    updated_at: datetime
