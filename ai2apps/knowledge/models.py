"""Value objects for the model-free Knowledge Core."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class KnowledgeScope(StrEnum):
    """User-selectable scopes in the first Knowledge release."""

    PRIVATE = "private"
    INSTALLATION = "installation"


@dataclass(frozen=True, slots=True)
class KnowledgeSpace:
    id: str
    kind: KnowledgeScope
    installation_id: str
    owner_user_id: str | None
    display_name: str
    shareability: str
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class KnowledgeItem:
    id: str
    space_id: str
    installation_id: str
    owner_user_id: str
    created_by_user_id: str
    visibility: KnowledgeScope
    kind: str
    title: str
    text: str
    source_time: datetime | None
    source_app_id: str | None
    source_session_id: str | None
    source_url: str | None
    status: str
    revision: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class KnowledgeTag:
    id: str
    namespace: str
    normalized_key: str
    display_name: str
    owner_user_id: str
    visibility: KnowledgeScope


@dataclass(frozen=True, slots=True)
class KnowledgeSearchHit:
    item: KnowledgeItem
    excerpt: str
    rank: float
    tags: tuple[KnowledgeTag, ...]
    source_facets: tuple[tuple[str, str], ...]
