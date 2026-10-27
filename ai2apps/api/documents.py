"""Session-scoped durable attachment APIs."""

from __future__ import annotations

import asyncio
import base64
import binascii
from pathlib import Path
import uuid
from typing import Any

from fastapi import APIRouter, Depends, UploadFile, File, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field

from ai2apps.api.errors import platform_error_response, repository_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import PrincipalProvider, resolve_request_principal
from ai2apps.api.ownership import require_session_access
from ai2apps.api.resources import _runtime_or_error
from ai2apps.core import RepositoryError


class AttachmentUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=512)
    media_type: str = Field(
        default="application/octet-stream", min_length=1, max_length=255
    )
    data: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AttachmentReferenceRequest(BaseModel):
    source_path: str = Field(min_length=1,max_length=4096)
    filename: str | None = Field(default=None,max_length=512)
    media_type: str | None = Field(default=None,max_length=255)


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


async def store_uploaded_reference(runtime, session_id, file):
    name=Path(file.filename or 'attachment').name.strip()
    if name in {'','.','..'}:name='attachment'
    target=runtime.documents.root/'uploads'/uuid.uuid4().hex/name
    target.parent.mkdir(parents=True,exist_ok=True)
    try:
        with target.open('xb') as output:
            target.chmod(0o600)
            while chunk:=await file.read(1024*1024):
                await asyncio.to_thread(output.write,chunk)
        return runtime.documents.create_reference(session_id,target,filename=file.filename,media_type=file.content_type,source='uploaded_file')
    except BaseException:
        target.unlink(missing_ok=True);raise


def create_document_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(
        prefix="/sessions/{session_id}/attachments",
        dependencies=[
            Depends(require_session_access(runtime_provider, principal_provider))
        ],
    )

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

    @router.post('/reference',status_code=201)
    def reference(session_id: str, body: AttachmentReferenceRequest, request: Request, principal=Depends(principal_provider)):
        # Native paths are accepted only from the core Desktop's authenticated
        # loopback surface, never from a Mobile/remote owner lease or a model Tool.
        if not principal.is_core or principal.client_scope!='desktop' or not request.client or request.client.host not in {'127.0.0.1','::1','testclient'}:
            raise HTTPException(403,'Choose local files on Desktop; remote clients must upload files')
        runtime=runtime_or_error()
        if isinstance(runtime,JSONResponse):return runtime
        try:return _attachment(runtime.documents.create_reference(session_id,Path(body.source_path),filename=body.filename,media_type=body.media_type))
        except RepositoryError as error:return repository_error_response(error)
        except ValueError as error:raise HTTPException(422,str(error)) from error

    @router.post('/upload',status_code=201)
    async def stream_upload(session_id: str, file: UploadFile=File(...)):
        runtime=runtime_or_error()
        if isinstance(runtime,JSONResponse):return runtime
        try:return _attachment(await store_uploaded_reference(runtime,session_id,file))
        finally:await file.close()

    @router.get('/{attachment_id}/content')
    def content(session_id: str, attachment_id: str):
        runtime=runtime_or_error()
        if isinstance(runtime,JSONResponse):return runtime
        try:
            item=runtime.documents.get(session_id,attachment_id)
            path=runtime.documents.source_path(session_id,attachment_id)
            return FileResponse(path,filename=item.filename,media_type=item.media_type)
        except RepositoryError as error:return repository_error_response(error)
        except ValueError as error:raise HTTPException(409,str(error)) from error

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
            item=runtime.documents.get(session_id, attachment_id)
            return {**_attachment(item),**runtime.documents.reference_status(session_id,attachment_id)}
        except RepositoryError as exc:
            return repository_error_response(exc)
        except ValueError as error:
            raise HTTPException(422,str(error)) from error

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
        except ValueError as error:
            raise HTTPException(422,str(error)) from error

    from ai2apps.api.attachment_uploads import install
    install(router, runtime_provider, principal_provider)
    return router
