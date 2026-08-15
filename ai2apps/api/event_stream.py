"""HTTP transport for replayable AI2Apps platform Events."""

from __future__ import annotations

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse, StreamingResponse

from ai2apps.api.errors import platform_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.events.stream import stream_events


def create_event_stream_router(
    runtime_provider: PlatformRuntimeProvider,
) -> APIRouter:
    router = APIRouter()

    @router.get("/events", response_model=None)
    async def events(
        after: int | None = Query(default=None, ge=0),
        session_id: str | None = None,
        app_instance_id: str | None = None,
        subject_id: str | None = None,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse | JSONResponse:
        cursor = after
        if cursor is None and last_event_id is not None:
            try:
                cursor = int(last_event_id)
            except ValueError:
                return platform_error_response(
                    status_code=400,
                    code="invalid_event_cursor",
                    message="Last-Event-ID must be a non-negative integer.",
                )
            if cursor < 0:
                return platform_error_response(
                    status_code=400,
                    code="invalid_event_cursor",
                    message="Last-Event-ID must be a non-negative integer.",
                )
        runtime = runtime_provider()
        if (
            runtime is None
            or runtime.events is None
            or runtime.notifications is None
        ):
            return platform_error_response(
                status_code=503,
                code="platform_not_ready",
                message="AI2Apps Event transport is not ready.",
                retryable=True,
            )
        return StreamingResponse(
            stream_events(
                runtime.events,
                runtime.notifications,
                after_sequence=cursor or 0,
                session_id=session_id,
                app_instance_id=app_instance_id,
                subject_id=subject_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return router
