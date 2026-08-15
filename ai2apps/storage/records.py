"""SQLite row decoding kept separate from repository behavior."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ai2apps.core import parse_utc
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
from ai2apps.storage.models import (
    AppDefinitionRecord,
    AppInstanceRecord,
    ChatCollectionRecord,
    ChatThreadRecord,
    EventRecord,
    MessagePartRecord,
    MessageRecord,
    SessionRecord,
)


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _optional_time(value: str | None):
    return None if value is None else parse_utc(value)


def app_definition_from_row(row: sqlite3.Row) -> AppDefinitionRecord:
    scope = row["singleton_scope"]
    return AppDefinitionRecord(
        id=row["id"],
        package_id=row["package_id"],
        package_version=row["package_version"],
        display_name=row["display_name"],
        instance_mode=AppInstanceMode(row["instance_mode"]),
        singleton_scope=None if scope is None else SingletonScope(scope),
        source=row["source"],
        status=AppDefinitionStatus(row["status"]),
        manifest_schema_version=row["manifest_schema_version"],
        manifest=json.loads(row["manifest_json"]),
        revision=row["revision"],
        created_at=parse_utc(row["created_at"]),
        updated_at=parse_utc(row["updated_at"]),
    )


def app_instance_from_row(row: sqlite3.Row) -> AppInstanceRecord:
    return AppInstanceRecord(
        id=row["id"],
        app_definition_id=row["app_definition_id"],
        singleton_key=row["singleton_key"],
        status=AppInstanceStatus(row["status"]),
        state_schema_version=row["state_schema_version"],
        state=json.loads(row["state_json"]),
        revision=row["revision"],
        created_at=parse_utc(row["created_at"]),
        updated_at=parse_utc(row["updated_at"]),
        closed_at=_optional_time(row["closed_at"]),
    )


def session_from_row(row: sqlite3.Row) -> SessionRecord:
    return SessionRecord(
        id=row["id"],
        app_instance_id=row["app_instance_id"],
        title=row["title"],
        status=SessionStatus(row["status"]),
        is_home=bool(row["is_home"]),
        session_kind=SessionKind(row["session_kind"]),
        visibility=SessionVisibility(row["visibility"]),
        retention=SessionRetention(row["retention"]),
        revision=row["revision"],
        metadata=json.loads(row["metadata_json"]),
        created_at=parse_utc(row["created_at"]),
        updated_at=parse_utc(row["updated_at"]),
        archived_at=_optional_time(row["archived_at"]),
        deleted_at=_optional_time(row["deleted_at"]),
        expires_at=_optional_time(row["expires_at"]),
    )


def chat_collection_from_row(row: sqlite3.Row) -> ChatCollectionRecord:
    return ChatCollectionRecord(
        app_instance_id=row["app_instance_id"],
        selected_session_id=row["selected_session_id"],
        revision=row["revision"],
        created_at=parse_utc(row["created_at"]),
        updated_at=parse_utc(row["updated_at"]),
    )


def chat_thread_from_joined_row(row: sqlite3.Row) -> ChatThreadRecord:
    return ChatThreadRecord(
        session=session_from_row(row),
        pinned=bool(row["chat_pinned"]),
        sort_order=row["chat_sort_order"],
        legacy_thread_id=row["chat_legacy_thread_id"],
        collection_created_at=parse_utc(row["chat_created_at"]),
        collection_updated_at=parse_utc(row["chat_updated_at"]),
    )


def message_from_row(row: sqlite3.Row) -> MessageRecord:
    return MessageRecord(
        id=row["id"],
        session_id=row["session_id"],
        sequence=row["sequence"],
        role=MessageRole(row["role"]),
        status=MessageStatus(row["status"]),
        idempotency_key=row["idempotency_key"],
        metadata=json.loads(row["metadata_json"]),
        created_at=parse_utc(row["created_at"]),
        updated_at=parse_utc(row["updated_at"]),
    )


def message_part_from_row(row: sqlite3.Row) -> MessagePartRecord:
    return MessagePartRecord(
        id=row["id"],
        message_id=row["message_id"],
        position=row["position"],
        kind=row["kind"],
        content=json.loads(row["content_json"]),
        created_at=parse_utc(row["created_at"]),
    )


def event_from_row(row: sqlite3.Row) -> EventRecord:
    return EventRecord(
        id=row["id"],
        sequence=row["sequence"],
        type=row["type"],
        occurred_at=parse_utc(row["occurred_at"]),
        app_instance_id=row["app_instance_id"],
        session_id=row["session_id"],
        subject_id=row["subject_id"],
        trace_id=row["trace_id"],
        schema_version=row["schema_version"],
        payload=json.loads(row["payload_json"]),
    )
