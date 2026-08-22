"""Principal-aware Coder Project and Thread APIs."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import (
    PrincipalProvider,
    require_app_capability,
    resolve_request_principal,
)
from ai2apps.apps.access import APP_CODER_USE
from ai2apps.coder import CoderError
from ai2apps.identity import RequestPrincipal


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    root_path: str = Field(min_length=1, max_length=4096)
    kind: str = "general"
    create_directory: bool = False
    bootstrap: bool = False


class ThreadCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    agent: str
    model_source: str = "default"
    model: str = ""
    parent_thread_id: str | None = None


class ForkRequest(BaseModel):
    title: str | None = Field(default=None, max_length=160)


class ProjectFileWriteRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    content: str


class DevSessionCreateRequest(BaseModel):
    component_id: str = Field(min_length=1, max_length=500)


def _manager(runtime_provider: PlatformRuntimeProvider):
    runtime = runtime_provider()
    manager = None if runtime is None else runtime.coder
    if manager is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "coder_unavailable", "message": "Coder is unavailable"},
        )
    return manager


def _raise(error: CoderError) -> None:
    status = (
        404
        if error.code
        in {
            "project_not_found",
            "thread_not_found",
            "dev_session_not_found",
            "resource_not_found",
            "file_not_found",
        }
        else 409
        if error.code in {"project_exists", "session_limit"}
        else 422
    )
    raise HTTPException(
        status_code=status,
        detail={"code": error.code, "message": str(error)},
    ) from error


def _preview_headers(*, entry: bool = False) -> dict[str, str]:
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    if entry:
        headers["Content-Security-Policy"] = (
            "sandbox allow-scripts allow-forms allow-downloads; "
            "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
            "font-src 'self' data:; connect-src 'none'; form-action 'none'; "
            "base-uri 'none'"
        )
    return headers


def create_coder_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(
        prefix="/coder",
        tags=["coder"],
        dependencies=[
            Depends(require_app_capability(principal_provider, APP_CODER_USE))
        ],
    )
    principal_dependency = Depends(principal_provider)

    @router.get("")
    def snapshot(principal: RequestPrincipal = principal_dependency):
        return _manager(runtime_provider).snapshot(principal=principal)

    @router.post("/projects", status_code=201)
    def create_project(
        request: ProjectCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return _manager(runtime_provider).create_project(
                **request.model_dump(), principal=principal
            )
        except CoderError as error:
            _raise(error)

    @router.delete("/projects/{project_id}")
    async def remove_project(
        project_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return await _manager(runtime_provider).remove_project(
                project_id, principal=principal
            )
        except CoderError as error:
            _raise(error)

    @router.post("/projects/{project_id}/threads", status_code=201)
    def create_thread(
        project_id: str,
        request: ThreadCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return _manager(runtime_provider).create_thread(
                project_id=project_id,
                **request.model_dump(),
                principal=principal,
            )
        except CoderError as error:
            _raise(error)

    @router.post("/threads/{thread_id}/fork", status_code=201)
    def fork_thread(
        thread_id: str,
        request: ForkRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return _manager(runtime_provider).fork_thread(
                thread_id, title=request.title, principal=principal
            )
        except CoderError as error:
            _raise(error)

    @router.post("/threads/{thread_id}/start")
    async def start_thread(
        thread_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return await _manager(runtime_provider).start_thread(
                thread_id, principal=principal
            )
        except CoderError as error:
            _raise(error)

    @router.post("/threads/{thread_id}/stop")
    async def stop_thread(
        thread_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return await _manager(runtime_provider).stop_thread(
                thread_id, principal=principal
            )
        except CoderError as error:
            _raise(error)

    @router.delete("/threads/{thread_id}")
    async def delete_thread(
        thread_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return await _manager(runtime_provider).delete_thread(
                thread_id, principal=principal
            )
        except CoderError as error:
            _raise(error)

    @router.get("/projects/{project_id}/files")
    def list_files(
        project_id: str,
        path: str = ".",
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return _manager(runtime_provider).list_project_files(
                project_id, path, principal=principal
            )
        except CoderError as error:
            _raise(error)

    @router.get("/projects/{project_id}/file")
    def read_file(
        project_id: str,
        path: str = Query(min_length=1, max_length=4096),
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return _manager(runtime_provider).read_project_file(
                project_id, path, principal=principal
            )
        except CoderError as error:
            _raise(error)

    @router.put("/projects/{project_id}/file")
    def write_file(
        project_id: str,
        request: ProjectFileWriteRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return _manager(runtime_provider).write_project_file(
                project_id,
                request.path,
                request.content,
                principal=principal,
            )
        except CoderError as error:
            _raise(error)

    @router.post("/projects/{project_id}/validate")
    def validate_project(
        project_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return _manager(runtime_provider).validate_project(
                project_id, principal=principal
            )
        except CoderError as error:
            _raise(error)

    @router.post("/projects/{project_id}/test")
    async def test_project(
        project_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return await _manager(runtime_provider).test_project(
                project_id, principal=principal
            )
        except CoderError as error:
            _raise(error)

    @router.post("/projects/{project_id}/build")
    def build_project(
        project_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return _manager(runtime_provider).build_project(
                project_id, principal=principal
            )
        except CoderError as error:
            _raise(error)

    @router.post("/projects/{project_id}/testflight")
    def submit_testflight(
        project_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return _manager(runtime_provider).submit_project_testflight(
                project_id, principal=principal
            )
        except CoderError as error:
            _raise(error)

    @router.post("/projects/{project_id}/dev-sessions", status_code=201)
    def start_dev_session(
        project_id: str,
        request: DevSessionCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return _manager(runtime_provider).start_dev_session(
                project_id,
                request.component_id,
                principal=principal,
            )
        except CoderError as error:
            _raise(error)

    @router.delete("/dev-sessions/{session_id}")
    def stop_dev_session(
        session_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return _manager(runtime_provider).stop_dev_session(
                session_id, principal=principal
            )
        except CoderError as error:
            _raise(error)

    @router.get("/dev-sessions/{session_id}/preview")
    def preview(
        session_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        manager = _manager(runtime_provider)
        try:
            session = manager.dev_session(session_id, principal=principal)
            entry = session.component.manifest.get("entry", {})
            if not isinstance(entry, dict):
                raise CoderError(
                    "invalid_dev_entry", "Component has no previewable Entry"
                )
            resource = entry.get("resource")
            if entry.get("kind") not in {"sandbox", "safe-html"} or not isinstance(
                resource, str
            ):
                raise CoderError(
                    "invalid_dev_entry", "Component has no previewable Entry"
                )
            manager.resolve_dev_resource(
                session_id, resource, principal=principal
            )
        except CoderError as error:
            _raise(error)
        return RedirectResponse(
            "/v1/platform/coder/dev-sessions/"
            f"{quote(session_id, safe='')}/resources/{quote(resource, safe='/')}",
            status_code=307,
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/dev-sessions/{session_id}/resources/{resource:path}")
    def preview_resource(
        session_id: str,
        resource: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        manager = _manager(runtime_provider)
        try:
            session = manager.dev_session(session_id, principal=principal)
            path, media = manager.resolve_dev_resource(
                session_id, resource, principal=principal
            )
            entry = session.component.manifest.get("entry")
            is_entry = isinstance(entry, dict) and entry.get("resource") == resource
        except CoderError as error:
            _raise(error)
        return FileResponse(
            path,
            media_type=media,
            headers=_preview_headers(entry=is_entry),
        )

    return router
