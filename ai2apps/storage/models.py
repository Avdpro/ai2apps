"""Typed records returned by AI2Apps persistence repositories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ai2apps.core.models import (
    AppDefinitionStatus,
    AppInstanceMode,
    AppInstanceStatus,
    MessageRole,
    MessageStatus,
    SessionKind,
    SessionRetention,
    SessionStatus,
    SessionVisibility,
    SingletonScope,
)

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class AppDefinitionRecord:
    id: str
    package_id: str
    package_version: str
    display_name: str
    instance_mode: AppInstanceMode
    singleton_scope: SingletonScope | None
    source: str
    status: AppDefinitionStatus
    manifest_schema_version: int
    manifest: JsonObject
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AppInstanceRecord:
    id: str
    app_definition_id: str
    singleton_key: str | None
    status: AppInstanceStatus
    state_schema_version: int
    state: JsonObject
    revision: int
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


@dataclass(frozen=True, slots=True)
class SessionRecord:
    id: str
    app_instance_id: str
    title: str
    status: SessionStatus
    is_home: bool
    session_kind: SessionKind
    visibility: SessionVisibility
    retention: SessionRetention
    revision: int
    metadata: JsonObject
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    deleted_at: datetime | None
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class ChatCollectionRecord:
    app_instance_id: str
    selected_session_id: str | None
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ChatThreadRecord:
    session: SessionRecord
    pinned: bool
    sort_order: int
    legacy_thread_id: str | None
    collection_created_at: datetime
    collection_updated_at: datetime


@dataclass(frozen=True, slots=True)
class BuiltinChatRecord:
    definition: AppDefinitionRecord
    instance: AppInstanceRecord
    collection: ChatCollectionRecord


@dataclass(frozen=True, slots=True)
class MessageRecord:
    id: str
    session_id: str
    sequence: int
    role: MessageRole
    status: MessageStatus
    idempotency_key: str | None
    metadata: JsonObject
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class MessagePartInput:
    kind: str
    content: JsonObject


@dataclass(frozen=True, slots=True)
class MessagePartRecord:
    id: str
    message_id: str
    position: int
    kind: str
    content: JsonObject
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MessageWithParts:
    message: MessageRecord
    parts: tuple[MessagePartRecord, ...]


@dataclass(frozen=True, slots=True)
class EventRecord:
    id: str
    sequence: int
    type: str
    occurred_at: datetime
    app_instance_id: str | None
    session_id: str | None
    subject_id: str
    trace_id: str | None
    schema_version: int
    payload: JsonObject


@dataclass(frozen=True, slots=True)
class AppendMessageResult:
    value: MessageWithParts
    event: EventRecord | None
    created: bool
