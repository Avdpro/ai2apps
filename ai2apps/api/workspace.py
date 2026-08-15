"""Session Workspace, ResourceHandle, and Artifact user APIs."""

from __future__ import annotations

import base64
import binascii
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from ai2apps.api.errors import platform_error_response, repository_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.core import RepositoryError
from ai2apps.workspace import ArtifactRecord, ResourceHandleRecord, WorkspaceError


class ResourceImportRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)
    media_type: str | None = None


class ResourceHandleResponse(BaseModel):
    id: str
    uri: str
    kind: str
    display_name: str
    capabilities: list[str]
    media_type: str | None
    size_bytes: int | None
    content_hash: str | None
    source: str

    @classmethod
    def from_record(cls, value: ResourceHandleRecord):
        return cls(
            id=value.id,
            uri=value.uri,
            kind=value.kind.value,
            display_name=value.display_name,
            capabilities=list(value.capabilities),
            media_type=value.media_type,
            size_bytes=value.size_bytes,
            content_hash=value.content_hash,
            source=value.source,
        )


class ResourceHandleListResponse(BaseModel):
    items: list[ResourceHandleResponse]


class WorkspaceWriteRequest(BaseModel):
    path: str = Field(min_length=1)
    content: str
    encoding: str = Field(default="utf-8", pattern="^(utf-8|base64)$")


class ArtifactCreateRequest(BaseModel):
    path: str = Field(min_length=1)
    name: str | None = None
    media_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactResponse(BaseModel):
    id: str
    uri: str
    name: str
    media_type: str
    content_hash: str
    size_bytes: int
    metadata: dict[str, Any]

    @classmethod
    def from_record(cls, value: ArtifactRecord):
        return cls(
            id=value.id,
            uri=value.uri,
            name=value.name,
            media_type=value.media_type,
            content_hash=value.content_hash,
            size_bytes=value.size_bytes,
            metadata=value.metadata,
        )


class ArtifactListResponse(BaseModel):
    items: list[ArtifactResponse]


def create_workspace_router(runtime_provider: PlatformRuntimeProvider) -> APIRouter:
    router = APIRouter()

    def workspace_or_error():
        runtime = runtime_provider()
        if runtime is None or runtime.workspace is None:
            return platform_error_response(
                status_code=503,
                code="workspace_runtime_not_ready",
                message="AI2Apps Workspace Runtime is not ready.",
                retryable=True,
            )
        return runtime.workspace

    def workspace_error(error: WorkspaceError):
        status = (
            413
            if error.code in {"resource_too_large", "workspace_quota_exceeded"}
            else 422
        )
        return platform_error_response(
            status_code=status, code=error.code, message=str(error)
        )

    @router.get("/sessions/{session_id}/workspace")
    def list_workspace(
        session_id: str,
        path: str = ".",
        offset: int = Query(0, ge=0),
        limit: int = Query(200, ge=1, le=1000),
    ):
        workspace = workspace_or_error()
        if isinstance(workspace, JSONResponse):
            return workspace
        try:
            return workspace.list(session_id, path, offset=offset, limit=limit)
        except RepositoryError as error:
            return repository_error_response(error)
        except WorkspaceError as error:
            return workspace_error(error)

    @router.get("/sessions/{session_id}/workspace/read")
    def read_workspace(
        session_id: str,
        path: str,
        offset: int = Query(0, ge=0),
        limit: int = Query(1024 * 1024, ge=1, le=1024 * 1024),
    ):
        workspace = workspace_or_error()
        if isinstance(workspace, JSONResponse):
            return workspace
        try:
            return workspace.read(session_id, path, offset=offset, limit=limit)
        except RepositoryError as error:
            return repository_error_response(error)
        except WorkspaceError as error:
            return workspace_error(error)

    @router.put("/sessions/{session_id}/workspace")
    def write_workspace(session_id: str, request: WorkspaceWriteRequest):
        workspace = workspace_or_error()
        if isinstance(workspace, JSONResponse):
            return workspace
        try:
            return workspace.write(
                session_id, request.path, request.content, encoding=request.encoding
            )
        except RepositoryError as error:
            return repository_error_response(error)
        except (WorkspaceError, binascii.Error, ValueError) as error:
            if isinstance(error, WorkspaceError):
                return workspace_error(error)
            return platform_error_response(
                status_code=422, code="invalid_content_encoding", message=str(error)
            )

    @router.post(
        "/sessions/{session_id}/resource-handles/import",
        response_model=ResourceHandleResponse,
        status_code=201,
    )
    def import_resource(session_id: str, request: ResourceImportRequest):
        workspace = workspace_or_error()
        if isinstance(workspace, JSONResponse):
            return workspace
        try:
            data = base64.b64decode(request.content_base64, validate=True)
            return ResourceHandleResponse.from_record(
                workspace.import_bytes(
                    session_id, request.filename, data, media_type=request.media_type
                )
            )
        except RepositoryError as error:
            return repository_error_response(error)
        except binascii.Error:
            return platform_error_response(
                status_code=422,
                code="invalid_base64",
                message="content_base64 is invalid.",
            )
        except WorkspaceError as error:
            return workspace_error(error)

    @router.get(
        "/sessions/{session_id}/resource-handles",
        response_model=ResourceHandleListResponse,
    )
    def list_handles(session_id: str):
        workspace = workspace_or_error()
        if isinstance(workspace, JSONResponse):
            return workspace
        return ResourceHandleListResponse(
            items=[
                ResourceHandleResponse.from_record(item)
                for item in workspace.list_handles(session_id)
            ]
        )

    @router.delete(
        "/sessions/{session_id}/resource-handles/{handle_id}", status_code=204
    )
    def revoke_handle(session_id: str, handle_id: str):
        workspace = workspace_or_error()
        if isinstance(workspace, JSONResponse):
            return workspace
        try:
            workspace.revoke_handle(session_id, handle_id)
            return Response(status_code=204)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post(
        "/sessions/{session_id}/artifacts",
        response_model=ArtifactResponse,
        status_code=201,
    )
    def create_artifact(session_id: str, request: ArtifactCreateRequest):
        workspace = workspace_or_error()
        if isinstance(workspace, JSONResponse):
            return workspace
        try:
            return ArtifactResponse.from_record(
                workspace.create_artifact(
                    session_id,
                    request.path,
                    request.name,
                    media_type=request.media_type,
                    metadata=request.metadata,
                )
            )
        except RepositoryError as error:
            return repository_error_response(error)
        except WorkspaceError as error:
            return workspace_error(error)

    @router.get("/sessions/{session_id}/artifacts", response_model=ArtifactListResponse)
    def list_artifacts(session_id: str):
        workspace = workspace_or_error()
        if isinstance(workspace, JSONResponse):
            return workspace
        return ArtifactListResponse(
            items=[
                ArtifactResponse.from_record(item)
                for item in workspace.list_artifacts(session_id)
            ]
        )

    @router.get("/sessions/{session_id}/artifacts/{artifact_id}/preview")
    def preview_artifact(
        session_id: str,
        artifact_id: str,
        limit: int = Query(256 * 1024, ge=1, le=1024 * 1024),
    ):
        workspace = workspace_or_error()
        if isinstance(workspace, JSONResponse):
            return workspace
        try:
            return workspace.preview_artifact(session_id, artifact_id, limit)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get("/sessions/{session_id}/artifacts/{artifact_id}/download")
    def download_artifact(session_id: str, artifact_id: str):
        workspace = workspace_or_error()
        if isinstance(workspace, JSONResponse):
            return workspace
        try:
            artifact = workspace.get_artifact(session_id, artifact_id)
            data = workspace.artifact_path(artifact).read_bytes()
            safe = artifact.name.replace('"', "")
            return Response(
                data,
                media_type=artifact.media_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{safe}"',
                    "ETag": artifact.content_hash,
                },
            )
        except RepositoryError as error:
            return repository_error_response(error)

    return router
