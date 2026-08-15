"""Generic Session, Message, and Event snapshot APIs."""

from __future__ import annotations

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse

from ai2apps.api.errors import platform_error_response, repository_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.models import (
    EventListResponse,
    EventResponse,
    MessageCreateRequest,
    MessageListResponse,
    MessageResponse,
    SessionCreateRequest,
    SessionListResponse,
    SessionPatchRequest,
    SessionResponse,
)
from ai2apps.core import (
    RepositoryError,
    SessionKind,
    SessionRetention,
    SessionStatus,
    SessionVisibility,
    format_utc,
)
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.storage import MessagePartInput
from ai2apps.storage.repositories import MessageRepository, SessionRepository


def _runtime_or_error(
    runtime_provider: PlatformRuntimeProvider,
) -> PlatformRuntime | JSONResponse:
    runtime = runtime_provider()
    if runtime is None or runtime.database is None or runtime.events is None:
        return platform_error_response(
            status_code=503,
            code="platform_not_ready",
            message="AI2Apps platform persistence is not ready.",
            retryable=True,
        )
    return runtime


def _session_defaults(request: SessionCreateRequest):
    conversational_embed = request.kind in {
        SessionKind.MINI_CHAT,
        SessionKind.IN_APP_CHAT,
    }
    visibility = request.visibility or (
        SessionVisibility.UNLISTED
        if conversational_embed
        else SessionVisibility.LISTED
    )
    retention = request.retention or (
        SessionRetention.TEMPORARY
        if conversational_embed
        else SessionRetention.DURABLE
    )
    return visibility, retention


def create_resource_router(runtime_provider: PlatformRuntimeProvider) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/app-instances/{app_instance_id}/sessions",
        response_model=SessionResponse,
        status_code=201,
    )
    def create_session(
        app_instance_id: str,
        request: SessionCreateRequest,
        x_trace_id: str | None = Header(default=None),
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        visibility, retention = _session_defaults(request)
        try:
            record = SessionRepository(runtime.database, runtime.events).create(
                app_instance_id=app_instance_id,
                title=request.title,
                is_home=request.is_home,
                session_kind=request.kind,
                visibility=visibility,
                retention=retention,
                expires_at=(
                    None
                    if request.expires_at is None
                    else format_utc(request.expires_at)
                ),
                metadata=request.metadata,
                trace_id=x_trace_id,
            )
            return SessionResponse.from_record(record)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get(
        "/app-instances/{app_instance_id}/sessions",
        response_model=SessionListResponse,
    )
    def list_sessions(
        app_instance_id: str,
        kind: SessionKind | None = None,
        visibility: SessionVisibility | None = None,
        include_deleted: bool = False,
        limit: int = Query(default=100, ge=1, le=1_000),
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            records = SessionRepository(runtime.database, runtime.events).list_for_instance(
                app_instance_id,
                include_deleted=include_deleted,
                session_kind=kind,
                visibility=visibility,
                limit=limit,
            )
            return SessionListResponse(
                items=[SessionResponse.from_record(record) for record in records]
            )
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get(
        "/app-instances/{app_instance_id}/sessions/{session_id}",
        response_model=SessionResponse,
    )
    def get_session(app_instance_id: str, session_id: str):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            record = SessionRepository(runtime.database, runtime.events).get(
                session_id,
                app_instance_id=app_instance_id,
            )
            return SessionResponse.from_record(record)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.patch(
        "/app-instances/{app_instance_id}/sessions/{session_id}",
        response_model=SessionResponse,
    )
    def patch_session(
        app_instance_id: str,
        session_id: str,
        request: SessionPatchRequest,
        x_trace_id: str | None = Header(default=None),
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            record = SessionRepository(runtime.database, runtime.events).update(
                session_id,
                expected_revision=request.expected_revision,
                app_instance_id=app_instance_id,
                title=request.title,
                status=request.status,
                is_home=request.is_home,
                visibility=request.visibility,
                retention=request.retention,
                metadata=request.metadata,
                trace_id=x_trace_id,
            )
            return SessionResponse.from_record(record)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.delete(
        "/app-instances/{app_instance_id}/sessions/{session_id}",
        response_model=SessionResponse,
    )
    def delete_session(
        app_instance_id: str,
        session_id: str,
        expected_revision: int = Query(ge=1),
        x_trace_id: str | None = Header(default=None),
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            record = SessionRepository(runtime.database, runtime.events).update(
                session_id,
                expected_revision=expected_revision,
                app_instance_id=app_instance_id,
                status=SessionStatus.DELETED,
                trace_id=x_trace_id,
            )
            return SessionResponse.from_record(record)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post(
        "/sessions/{session_id}/messages",
        response_model=MessageResponse,
        status_code=201,
    )
    def append_message(
        session_id: str,
        request: MessageCreateRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_trace_id: str | None = Header(default=None),
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        if (
            idempotency_key is not None
            and request.idempotency_key is not None
            and idempotency_key != request.idempotency_key
        ):
            return platform_error_response(
                status_code=400,
                code="idempotency_key_mismatch",
                message="Header and body idempotency keys must match.",
            )
        try:
            result = MessageRepository(runtime.database, runtime.events).append(
                session_id=session_id,
                role=request.role,
                status=request.status,
                parts=tuple(
                    MessagePartInput(kind=part.kind, content=part.content)
                    for part in request.parts
                ),
                idempotency_key=idempotency_key or request.idempotency_key,
                metadata=request.metadata,
                trace_id=x_trace_id,
            )
            response = MessageResponse.from_record(
                result.value,
                created=result.created,
            )
            if not result.created:
                return JSONResponse(
                    status_code=200,
                    content=response.model_dump(mode="json"),
                )
            return response
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get(
        "/sessions/{session_id}/messages",
        response_model=MessageListResponse,
    )
    def list_messages(
        session_id: str,
        after: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=1_000),
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            records = MessageRepository(runtime.database, runtime.events).list_for_session(
                session_id,
                after_sequence=after,
                limit=limit,
            )
            return MessageListResponse(
                items=[MessageResponse.from_record(record) for record in records]
            )
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get(
        "/sessions/{session_id}/events",
        response_model=EventListResponse,
    )
    def list_session_events(
        session_id: str,
        after: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=1_000),
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        events = runtime.events.list_after(
            after,
            session_id=session_id,
            limit=limit,
        )
        return EventListResponse(
            items=[EventResponse.from_record(event) for event in events]
        )

    return router
