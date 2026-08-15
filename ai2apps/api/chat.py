"""Chat-friendly aliases over the singleton Chat App's generic resources."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from ai2apps.api.errors import repository_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.resources import _runtime_or_error
from ai2apps.chat import ChatContentRecord, ChatRepository, LegacyChatMessageInput
from ai2apps.core import MessageRole, RepositoryError, SessionStatus
from ai2apps.storage import BuiltinChatRecord, ChatCollectionRecord, ChatThreadRecord


class ChatAppResponse(BaseModel):
    package_id: str
    app_instance_id: str
    status: str
    selected_thread_id: str | None
    collection_revision: int

    @classmethod
    def from_record(cls, record: BuiltinChatRecord) -> ChatAppResponse:
        return cls(
            package_id=record.definition.package_id,
            app_instance_id=record.instance.id,
            status=record.instance.status.value,
            selected_thread_id=record.collection.selected_session_id,
            collection_revision=record.collection.revision,
        )


class ChatCollectionResponse(BaseModel):
    app_instance_id: str
    selected_thread_id: str | None
    revision: int

    @classmethod
    def from_record(cls, record: ChatCollectionRecord) -> ChatCollectionResponse:
        return cls(
            app_instance_id=record.app_instance_id,
            selected_thread_id=record.selected_session_id,
            revision=record.revision,
        )


class ChatThreadResponse(BaseModel):
    id: str
    app_instance_id: str
    title: str
    status: SessionStatus
    is_home: bool
    pinned: bool
    sort_order: int
    legacy_thread_id: str | None
    revision: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: ChatThreadRecord) -> ChatThreadResponse:
        session = record.session
        return cls(
            id=session.id,
            app_instance_id=session.app_instance_id,
            title=session.title,
            status=session.status,
            is_home=session.is_home,
            pinned=record.pinned,
            sort_order=record.sort_order,
            legacy_thread_id=record.legacy_thread_id,
            revision=session.revision,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )


class ChatThreadListResponse(BaseModel):
    items: list[ChatThreadResponse]


class LegacyChatMessageRequest(BaseModel):
    role: MessageRole
    content: Any
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatThreadCreateRequest(BaseModel):
    title: str = ""
    pinned: bool = False
    legacy_thread_id: str | None = Field(default=None, min_length=1, max_length=512)
    session_metadata: dict[str, Any] = Field(default_factory=dict)
    legacy_messages: list[LegacyChatMessageRequest] = Field(
        default_factory=list,
        max_length=10_000,
    )

    @model_validator(mode="after")
    def legacy_messages_require_identity(self) -> ChatThreadCreateRequest:
        if self.legacy_messages and self.legacy_thread_id is None:
            raise ValueError("legacy_messages require legacy_thread_id")
        return self


class ChatThreadPatchRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    title: str | None = None
    pinned: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> ChatThreadPatchRequest:
        if self.title is None and self.pinned is None:
            raise ValueError("At least one Chat thread field must change")
        return self


class ExpectedRevisionRequest(BaseModel):
    expected_revision: int = Field(ge=1)


class ChatContentRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    title: str | None = None
    session_metadata: dict[str, Any] = Field(default_factory=dict)
    messages: list[LegacyChatMessageRequest] = Field(max_length=10_000)


class ChatContentResponse(BaseModel):
    thread: ChatThreadResponse
    session_metadata: dict[str, Any]
    messages: list[LegacyChatMessageRequest]

    @classmethod
    def from_record(cls, record: ChatContentRecord) -> ChatContentResponse:
        return cls(
            thread=ChatThreadResponse.from_record(record.thread),
            session_metadata=record.metadata,
            messages=[
                LegacyChatMessageRequest(
                    role=message.role,
                    content=message.content,
                    metadata=message.metadata,
                )
                for message in record.messages
            ],
        )


def create_chat_router(runtime_provider: PlatformRuntimeProvider) -> APIRouter:
    router = APIRouter(prefix="/chat")

    def repository_or_error():
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        return ChatRepository(runtime.database, runtime.events)

    @router.get("", response_model=ChatAppResponse)
    def get_chat_app():
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        try:
            return ChatAppResponse.from_record(repository.ensure_builtin())
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/threads", response_model=ChatThreadResponse, status_code=201)
    def create_thread(
        request: ChatThreadCreateRequest,
        x_trace_id: str | None = Header(default=None),
    ):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        try:
            record, created = repository.create_thread(
                title=request.title,
                pinned=request.pinned,
                legacy_thread_id=request.legacy_thread_id,
                metadata=request.session_metadata,
                legacy_messages=tuple(
                    LegacyChatMessageInput(
                        role=message.role,
                        content=message.content,
                        metadata=message.metadata,
                    )
                    for message in request.legacy_messages
                ),
                trace_id=x_trace_id,
            )
            response = ChatThreadResponse.from_record(record)
            if not created:
                return JSONResponse(
                    status_code=200,
                    content=response.model_dump(mode="json"),
                )
            return response
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get("/threads", response_model=ChatThreadListResponse)
    def list_threads(
        include_archived: bool = False,
        include_deleted: bool = False,
        limit: int = Query(default=100, ge=1, le=1_000),
    ):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        records = repository.list_threads(
            include_archived=include_archived,
            include_deleted=include_deleted,
            limit=limit,
        )
        return ChatThreadListResponse(
            items=[ChatThreadResponse.from_record(record) for record in records]
        )

    @router.get("/threads/{thread_id}", response_model=ChatThreadResponse)
    def get_thread(thread_id: str):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        try:
            return ChatThreadResponse.from_record(repository.get_thread(thread_id))
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get(
        "/threads/{thread_id}/content",
        response_model=ChatContentResponse,
    )
    def get_thread_content(thread_id: str):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        try:
            return ChatContentResponse.from_record(repository.get_content(thread_id))
        except RepositoryError as error:
            return repository_error_response(error)

    @router.put(
        "/threads/{thread_id}/content",
        response_model=ChatContentResponse,
    )
    def replace_thread_content(
        thread_id: str,
        request: ChatContentRequest,
        x_trace_id: str | None = Header(default=None),
    ):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        try:
            record = repository.replace_content(
                thread_id,
                expected_revision=request.expected_revision,
                title=request.title,
                metadata=request.session_metadata,
                messages=tuple(
                    LegacyChatMessageInput(
                        role=message.role,
                        content=message.content,
                        metadata=message.metadata,
                    )
                    for message in request.messages
                ),
                trace_id=x_trace_id,
            )
            return ChatContentResponse.from_record(record)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.patch("/threads/{thread_id}", response_model=ChatThreadResponse)
    def patch_thread(
        thread_id: str,
        request: ChatThreadPatchRequest,
        x_trace_id: str | None = Header(default=None),
    ):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        try:
            record = repository.update_thread(
                thread_id,
                expected_revision=request.expected_revision,
                title=request.title,
                pinned=request.pinned,
                trace_id=x_trace_id,
            )
            return ChatThreadResponse.from_record(record)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/threads/{thread_id}/select", response_model=ChatCollectionResponse)
    def select_thread(
        thread_id: str,
        request: ExpectedRevisionRequest,
        x_trace_id: str | None = Header(default=None),
    ):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        try:
            record = repository.select_thread(
                thread_id,
                expected_revision=request.expected_revision,
                trace_id=x_trace_id,
            )
            return ChatCollectionResponse.from_record(record)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/threads/{thread_id}/home", response_model=ChatThreadResponse)
    def set_home_thread(
        thread_id: str,
        request: ExpectedRevisionRequest,
        x_trace_id: str | None = Header(default=None),
    ):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        try:
            record = repository.set_home_thread(
                thread_id,
                expected_revision=request.expected_revision,
                trace_id=x_trace_id,
            )
            return ChatThreadResponse.from_record(record)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/threads/{thread_id}/archive", response_model=ChatThreadResponse)
    def archive_thread(
        thread_id: str,
        request: ExpectedRevisionRequest,
        x_trace_id: str | None = Header(default=None),
    ):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        try:
            record = repository.update_thread(
                thread_id,
                expected_revision=request.expected_revision,
                status=SessionStatus.ARCHIVED,
                trace_id=x_trace_id,
            )
            return ChatThreadResponse.from_record(record)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.delete("/threads/{thread_id}", response_model=ChatThreadResponse)
    def delete_thread(
        thread_id: str,
        expected_revision: int = Query(ge=1),
        x_trace_id: str | None = Header(default=None),
    ):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        try:
            record = repository.update_thread(
                thread_id,
                expected_revision=expected_revision,
                status=SessionStatus.DELETED,
                trace_id=x_trace_id,
            )
            return ChatThreadResponse.from_record(record)
        except RepositoryError as error:
            return repository_error_response(error)

    return router
