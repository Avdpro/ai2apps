"""Request and response contracts for Session, Message, and Event APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from ai2apps.core import (
    MessageRole,
    MessageStatus,
    SessionKind,
    SessionRetention,
    SessionStatus,
    SessionVisibility,
)
from ai2apps.storage.models import EventRecord, MessageWithParts, SessionRecord


class SessionCreateRequest(BaseModel):
    title: str = ""
    is_home: bool = False
    kind: SessionKind = SessionKind.APP
    visibility: SessionVisibility | None = None
    retention: SessionRetention | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def expiry_matches_effective_retention(self) -> SessionCreateRequest:
        embedded_chat = self.kind in {
            SessionKind.MINI_CHAT,
            SessionKind.IN_APP_CHAT,
        }
        effective_retention = self.retention or (
            SessionRetention.TEMPORARY
            if embedded_chat
            else SessionRetention.DURABLE
        )
        if (
            self.expires_at is not None
            and effective_retention is SessionRetention.DURABLE
        ):
            raise ValueError("expires_at is valid only for temporary Sessions")
        return self


class SessionPatchRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    title: str | None = None
    status: SessionStatus | None = None
    is_home: bool | None = None
    visibility: SessionVisibility | None = None
    retention: SessionRetention | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_change(self) -> SessionPatchRequest:
        if all(
            value is None
            for value in (
                self.title,
                self.status,
                self.is_home,
                self.visibility,
                self.retention,
                self.metadata,
            )
        ):
            raise ValueError("At least one Session field must change")
        return self


class SessionResponse(BaseModel):
    id: str
    app_instance_id: str
    title: str
    status: SessionStatus
    is_home: bool
    kind: SessionKind
    visibility: SessionVisibility
    retention: SessionRetention
    revision: int
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    deleted_at: datetime | None
    expires_at: datetime | None

    @classmethod
    def from_record(cls, record: SessionRecord) -> SessionResponse:
        return cls(
            id=record.id,
            app_instance_id=record.app_instance_id,
            title=record.title,
            status=record.status,
            is_home=record.is_home,
            kind=record.session_kind,
            visibility=record.visibility,
            retention=record.retention,
            revision=record.revision,
            metadata=record.metadata,
            created_at=record.created_at,
            updated_at=record.updated_at,
            archived_at=record.archived_at,
            deleted_at=record.deleted_at,
            expires_at=record.expires_at,
        )


class SessionListResponse(BaseModel):
    items: list[SessionResponse]


class MessagePartRequest(BaseModel):
    kind: str = Field(min_length=1)
    content: dict[str, Any]


class MessageCreateRequest(BaseModel):
    role: MessageRole
    parts: list[MessagePartRequest] = Field(min_length=1)
    status: MessageStatus = MessageStatus.COMPLETED
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MessagePartResponse(BaseModel):
    id: str
    position: int
    kind: str
    content: dict[str, Any]
    created_at: datetime


class MessageResponse(BaseModel):
    id: str
    session_id: str
    sequence: int
    role: MessageRole
    status: MessageStatus
    idempotency_key: str | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    parts: list[MessagePartResponse]
    created: bool = True

    @classmethod
    def from_record(
        cls,
        value: MessageWithParts,
        *,
        created: bool = True,
    ) -> MessageResponse:
        message = value.message
        return cls(
            id=message.id,
            session_id=message.session_id,
            sequence=message.sequence,
            role=message.role,
            status=message.status,
            idempotency_key=message.idempotency_key,
            metadata=message.metadata,
            created_at=message.created_at,
            updated_at=message.updated_at,
            parts=[
                MessagePartResponse(
                    id=part.id,
                    position=part.position,
                    kind=part.kind,
                    content=part.content,
                    created_at=part.created_at,
                )
                for part in value.parts
            ],
            created=created,
        )


class MessageListResponse(BaseModel):
    items: list[MessageResponse]


class EventResponse(BaseModel):
    id: str
    sequence: int
    type: str
    occurred_at: datetime
    app_instance_id: str | None
    session_id: str | None
    subject_id: str
    trace_id: str | None
    schema_version: int
    payload: dict[str, Any]

    @classmethod
    def from_record(cls, event: EventRecord) -> EventResponse:
        return cls(
            id=event.id,
            sequence=event.sequence,
            type=event.type,
            occurred_at=event.occurred_at,
            app_instance_id=event.app_instance_id,
            session_id=event.session_id,
            subject_id=event.subject_id,
            trace_id=event.trace_id,
            schema_version=event.schema_version,
            payload=event.payload,
        )


class EventListResponse(BaseModel):
    items: list[EventResponse]
