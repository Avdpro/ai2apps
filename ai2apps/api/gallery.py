"""Authenticated resource API for the built-in Gallery system App."""

from __future__ import annotations

import hashlib
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from ai2apps.api.errors import (
    platform_error_response,
    repository_error_response,
)
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import PrincipalProvider, resolve_request_principal
from ai2apps.api.ownership import require_session_access
from ai2apps.config import DEFAULT_RESOURCE_IMPORT_LIMIT_BYTES
from ai2apps.core import RepositoryError
from ai2apps.gallery import GalleryError, GalleryRepository
from ai2apps.identity import RequestPrincipal


class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["custom", "project"] = "custom"
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollectionOrderRequest(BaseModel):
    asset_ids: list[str] = Field(default_factory=list, max_length=500)


class ArtifactImportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    collection_id: str | None = Field(default=None, alias="collectionId")
    name: str | None = Field(default=None, max_length=255)
    source_app_id: str = Field(default="ai2apps.video-studio", alias="sourceAppId")


class AssetUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=512)


_BROWSER_TRANSFER_TTL_SECONDS = 24 * 60 * 60


def _browser_transfer_name(value: str) -> str:
    """Keep the page-visible File name while staying under filesystem limits."""

    source = Path(value).name.replace("\x00", "").strip() or "Gallery asset"
    suffix = Path(source).suffix[:24]
    stem = source[: max(1, 96 - len(suffix))]
    return f"{stem}{suffix}" if not stem.endswith(suffix) else stem


def _prune_browser_transfers(root: Path, *, now: float) -> None:
    if not root.exists():
        return
    cutoff = now - _BROWSER_TRANSFER_TTL_SECONDS
    for owner_directory in root.iterdir():
        if not owner_directory.is_dir():
            continue
        for transfer_directory in owner_directory.iterdir():
            try:
                if not transfer_directory.is_dir() or transfer_directory.stat().st_mtime >= cutoff:
                    continue
                for child in transfer_directory.iterdir():
                    if child.is_file() or child.is_symlink():
                        child.unlink(missing_ok=True)
                transfer_directory.rmdir()
            except OSError:
                # A live browser may still be reading the export; retry later.
                continue
        try:
            owner_directory.rmdir()
        except OSError:
            pass


def create_gallery_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(prefix="/gallery", tags=["platform-gallery"])
    principal_dependency = Depends(principal_provider)
    session_access_dependency = Depends(
        require_session_access(runtime_provider, principal_provider)
    )

    def repository() -> GalleryRepository | JSONResponse:
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        events = None if runtime is None else getattr(runtime, "events", None)
        paths = None if runtime is None else getattr(runtime.config, "paths", None)
        if database is None or paths is None:
            return platform_error_response(
                status_code=503,
                code="platform_not_ready",
                message="Gallery persistence is not ready.",
                retryable=True,
            )
        return GalleryRepository(database, paths.artifacts_path / "gallery", events)

    def guarded(call):
        try:
            return call()
        except RepositoryError as error:
            return repository_error_response(error)
        except GalleryError as error:
            return platform_error_response(
                status_code=422,
                code=error.code,
                message=str(error),
            )

    @router.get("/collections")
    def list_collections(principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return {
            "items": list(selected.list_collections(principal.actor_user_id))
        }

    @router.post("/collections", status_code=201)
    def create_collection(
        request: CollectionCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(
            lambda: selected.create_collection(
                principal.actor_user_id,
                name=request.name,
                kind=request.kind,
                metadata=request.metadata,
            )
        )

    @router.delete("/collections/{collection_id}", status_code=204)
    def delete_collection(
        collection_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.delete_collection(
                principal.actor_user_id, collection_id
            )
        )
        return result if isinstance(result, JSONResponse) else Response(status_code=204)

    @router.get("/assets")
    def list_assets(
        collection_id: str | None = Query(default=None, alias="collectionId"),
        kind: str | None = None,
        search: str | None = None,
        limit: int = Query(default=200, ge=1, le=500),
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.list_assets(
                principal.actor_user_id,
                collection_id=collection_id,
                kind=kind,
                search=search,
                limit=limit,
            )
        )
        return result if isinstance(result, JSONResponse) else {"items": list(result)}

    @router.post("/assets/import", status_code=201)
    def import_asset(
        file: Annotated[UploadFile, File()],
        collection_id: Annotated[str | None, Form(alias="collectionId")] = None,
        source_app_id: Annotated[str | None, Form(alias="sourceAppId")] = None,
        source_ref: Annotated[str | None, Form(alias="sourceRef")] = None,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.import_stream(
                principal.actor_user_id,
                file.file,
                name=file.filename or "Untitled",
                media_type=file.content_type,
                collection_id=collection_id,
                source_app_id=source_app_id,
                source_ref=source_ref,
                max_bytes=DEFAULT_RESOURCE_IMPORT_LIMIT_BYTES,
            )
        )
        if isinstance(result, JSONResponse):
            return result
        asset, created = result
        return {"asset": asset, "created": created}

    @router.post(
        "/assets/import-artifact/{session_id}/{artifact_id}", status_code=201
    )
    def import_workspace_artifact(
        session_id: str,
        artifact_id: str,
        request: ArtifactImportRequest,
        principal: RequestPrincipal = principal_dependency,
        _session_access: None = session_access_dependency,
    ):
        del _session_access
        runtime = runtime_provider()
        workspace = None if runtime is None else getattr(runtime, "workspace", None)
        selected = repository()
        if workspace is None:
            return platform_error_response(
                status_code=503,
                code="workspace_runtime_not_ready",
                message="AI2Apps Workspace Runtime is not ready.",
                retryable=True,
            )
        if isinstance(selected, JSONResponse):
            return selected

        def import_artifact():
            artifact = workspace.get_artifact(session_id, artifact_id)
            path = workspace.artifact_path(artifact)
            with path.open("rb") as stream:
                return selected.import_stream(
                    principal.actor_user_id,
                    stream,
                    name=request.name or artifact.name,
                    media_type=artifact.media_type,
                    collection_id=request.collection_id,
                    source_app_id=request.source_app_id,
                    source_ref=artifact.uri,
                    metadata={
                        "artifact_id": artifact.id,
                        "artifact_session_id": artifact.session_id,
                        "artifact_run_id": artifact.run_id,
                    },
                    max_bytes=DEFAULT_RESOURCE_IMPORT_LIMIT_BYTES,
                )

        result = guarded(import_artifact)
        if isinstance(result, JSONResponse):
            return result
        asset, created = result
        return {"asset": asset, "created": created}

    @router.get("/assets/{asset_id}")
    def get_asset(
        asset_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(lambda: selected.get_asset(principal.actor_user_id, asset_id))

    @router.patch("/assets/{asset_id}")
    def update_asset(
        asset_id: str,
        request: AssetUpdateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(
            lambda: selected.rename_asset(
                principal.actor_user_id, asset_id, request.name
            )
        )

    @router.get("/assets/{asset_id}/content")
    def asset_content(
        asset_id: str,
        download: bool = False,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.asset_path(principal.actor_user_id, asset_id)
        )
        if isinstance(result, JSONResponse):
            return result
        asset, path = result
        disposition = "attachment" if download else "inline"
        return FileResponse(
            path,
            media_type=asset["media_type"],
            filename=asset["name"] if download else None,
            content_disposition_type=disposition,
            headers={
                "Cache-Control": "private, max-age=3600",
                "ETag": asset["content_hash"],
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.post("/assets/{asset_id}/browser-transfer")
    def create_browser_transfer(
        asset_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        """Materialize an owned Asset for native WebDriver BiDi input.setFiles."""

        selected = repository()
        runtime = runtime_provider()
        paths = None if runtime is None else getattr(runtime.config, "paths", None)
        if isinstance(selected, JSONResponse):
            return selected
        if paths is None:
            return platform_error_response(
                status_code=503,
                code="platform_not_ready",
                message="Gallery browser transfer storage is not ready.",
                retryable=True,
            )
        result = guarded(
            lambda: selected.asset_path(principal.actor_user_id, asset_id)
        )
        if isinstance(result, JSONResponse):
            return result
        asset, source = result
        transfer_root = paths.artifacts_path / "gallery-browser-transfers"
        now = time.time()
        _prune_browser_transfers(transfer_root, now=now)
        owner_key = hashlib.sha256(
            principal.actor_user_id.encode("utf-8")
        ).hexdigest()[:24]
        transfer_directory = transfer_root / owner_key / uuid.uuid4().hex
        transfer_directory.mkdir(parents=True, exist_ok=False)
        destination = transfer_directory / _browser_transfer_name(asset["name"])
        try:
            os.link(source, destination)
        except OSError:
            shutil.copyfile(source, destination)
        os.utime(transfer_directory, (now, now))
        return JSONResponse(
            {
                "asset_id": asset["id"],
                "name": asset["name"],
                "media_type": asset["media_type"],
                "path": str(destination.resolve(strict=True)),
                "expires_in": _BROWSER_TRANSFER_TTL_SECONDS,
            },
            headers={"Cache-Control": "no-store"},
        )

    @router.post(
        "/collections/{collection_id}/assets/{asset_id}", status_code=204
    )
    def add_to_collection(
        collection_id: str,
        asset_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.add_to_collection(
                principal.actor_user_id, collection_id, asset_id
            )
        )
        return result if isinstance(result, JSONResponse) else Response(status_code=204)

    @router.delete(
        "/collections/{collection_id}/assets/{asset_id}", status_code=204
    )
    def remove_from_collection(
        collection_id: str,
        asset_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.remove_from_collection(
                principal.actor_user_id, collection_id, asset_id
            )
        )
        return result if isinstance(result, JSONResponse) else Response(status_code=204)

    @router.put("/collections/{collection_id}/order", status_code=204)
    def reorder_collection(
        collection_id: str,
        request: CollectionOrderRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.reorder_collection(
                principal.actor_user_id, collection_id, request.asset_ids
            )
        )
        return result if isinstance(result, JSONResponse) else Response(status_code=204)

    @router.post("/assets/{asset_id}/trash")
    def trash_asset(
        asset_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(
            lambda: selected.trash_asset(principal.actor_user_id, asset_id)
        )

    @router.post("/assets/{asset_id}/restore")
    def restore_asset(
        asset_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(
            lambda: selected.restore_asset(principal.actor_user_id, asset_id)
        )

    @router.delete("/assets/{asset_id}", status_code=204)
    def delete_asset(
        asset_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.delete_asset(principal.actor_user_id, asset_id)
        )
        return result if isinstance(result, JSONResponse) else Response(status_code=204)

    return router
