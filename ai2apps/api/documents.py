"""Session-scoped durable attachment APIs."""

from __future__ import annotations

import base64
import binascii
import asyncio
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai2apps.api.errors import platform_error_response, repository_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.resources import _runtime_or_error
from ai2apps.core import RepositoryError


class AttachmentUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=512)
    media_type: str = Field(
        default="application/octet-stream", min_length=1, max_length=255
    )
    data: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _attachment(item) -> dict[str, Any]:
    return {
        "id": item.id,
        "session_id": item.session_id,
        "filename": item.filename,
        "media_type": item.media_type,
        "size_bytes": item.size_bytes,
        "sha256": item.sha256,
        "status": item.status.value,
        "error": item.error,
        "metadata": item.metadata,
        "created_at": item.created_at,
    }


def _decode(value: str) -> bytes:
    payload = (
        value.split(",", 1)[1] if value.startswith("data:") and "," in value else value
    )
    try:
        return base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Attachment data must be valid base64") from exc


def create_document_router(runtime_provider: PlatformRuntimeProvider) -> APIRouter:
    router = APIRouter(prefix="/sessions/{session_id}/attachments")

    def runtime_or_error():
        return _runtime_or_error(runtime_provider)

    @router.post("", status_code=201)
    async def upload(session_id: str, request: AttachmentUploadRequest):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            record = await asyncio.to_thread(
                runtime.documents.create,
                session_id,
                filename=request.filename,
                media_type=request.media_type,
                data=_decode(request.data),
                metadata=request.metadata,
            )
            runtime.document_manager.enqueue(session_id, record.id)
            return _attachment(record)
        except RepositoryError as exc:
            return repository_error_response(exc)
        except ValueError as exc:
            return platform_error_response(
                status_code=400, code="invalid_attachment", message=str(exc)
            )

    @router.get("")
    def list_attachments(session_id: str):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        return {
            "items": [_attachment(item) for item in runtime.documents.list(session_id)]
        }

    @router.get("/{attachment_id}")
    def get_attachment(session_id: str, attachment_id: str):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            return _attachment(runtime.documents.get(session_id, attachment_id))
        except RepositoryError as exc:
            return repository_error_response(exc)

    @router.get("/{attachment_id}/blocks")
    def read_blocks(
        session_id: str, attachment_id: str, offset: int = 0, limit: int = 50
    ):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            items = runtime.documents.blocks(
                session_id, attachment_id, offset=offset, limit=limit
            )
            return {
                "items": [
                    (
                        item.__dict__
                        if hasattr(item, "__dict__")
                        else {
                            "id": item.id,
                            "ordinal": item.ordinal,
                            "kind": item.kind,
                            "text": item.text,
                            "page": item.page,
                            "section": item.section,
                            "sheet": item.sheet,
                            "slide": item.slide,
                            "cell_range": item.cell_range,
                            "metadata": item.metadata or {},
                        }
                    )
                    for item in items
                ]
            }
        except RepositoryError as exc:
            return repository_error_response(exc)

    return router
