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
from ai2apps.extensions import ExtensionError
from ai2apps.gallery import GalleryError, GalleryRepository
from ai2apps.gallery.characters import Characters, CharacterInput
from ai2apps.gallery.sticker_packs import Character, StickerEntry, StickerPacks
from ai2apps.gallery.repository import STICKER_PACK_MIME
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
    name: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = Field(default=None, max_length=4000)
    source_app_id: str = Field(default="ai2apps.video-studio", alias="sourceAppId")


class AssetUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = Field(default=None, max_length=4000)


class AssetHandleRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    consumer_app_id: str = Field(alias="consumerAppId", min_length=3, max_length=200)
    app_instance_id: str = Field(alias="appInstanceId", min_length=1, max_length=200)


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

    @router.get("/characters")
    def list_characters(principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse): return selected
        return guarded(lambda: {"items": Characters(selected, principal.actor_user_id).list()})

    @router.get("/characters/definitions")
    def character_definitions(principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse): return selected
        return guarded(lambda: {"items": Characters(selected, principal.actor_user_id).definitions()})

    @router.get('/characters/{character_id}/archive')
    def export_character_archive(character_id: str, appearance_id: str | None = None, principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse): return selected
        def export():
            from ai2apps.gallery.character_archive import export_character
            try: data = export_character(Characters(selected,principal.actor_user_id),character_id,appearance_id)
            except ValueError as error: raise GalleryError('character_archive_invalid',str(error)) from error
            return Response(data,media_type='application/zip',headers={'Cache-Control':'private, no-store'})
        return guarded(export)

    @router.post('/characters/archive/{action}')
    async def import_character_archive(action: str, file: UploadFile = File(), principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse): return selected
        from ai2apps.gallery.character_archive import preview_character, import_character
        from ai2apps.studio.portable_archive import MAX_BYTES
        data = await file.read(MAX_BYTES+1)
        def perform():
            try:
                if action=='inspect': return preview_character(data)
                if action=='import': return import_character(Characters(selected,principal.actor_user_id),data)
                raise ValueError('Unknown archive action')
            except (ValueError, OSError, TypeError, KeyError) as error: raise GalleryError('character_archive_invalid',str(error)) from error
        return guarded(perform)

    @router.post("/characters", status_code=201)
    def create_character(request: CharacterInput, principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse): return selected
        return guarded(lambda: Characters(selected, principal.actor_user_id).save(request))

    @router.put("/characters/{character_id}")
    def update_character(character_id: str, request: CharacterInput, principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse): return selected
        return guarded(lambda: Characters(selected, principal.actor_user_id).save(request, character_id))

    @router.post("/sticker-packs", status_code=201)
    def create_sticker_pack(request: Character, principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(lambda: StickerPacks(selected, principal.actor_user_id).create(request))

    @router.post("/sticker-packs/{pack_id}/stickers", status_code=201)
    def append_sticker(pack_id: str, request: StickerEntry,
                       principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(lambda: StickerPacks(selected, principal.actor_user_id).append(pack_id, request))

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
            from ai2apps.gallery.materials import save_artifact
            return save_artifact(selected, workspace, principal.actor_user_id, session_id,
                                 artifact_id, name=request.name, description=request.description,
                                 collection_id=request.collection_id,
                                 source_app_id=request.source_app_id)

        result = guarded(import_artifact)
        if isinstance(result, JSONResponse):
            return result
        asset, created = result
        return {"asset": asset, "created": created}

    @router.post('/assets/import-attachment/{session_id}/{attachment_id}',status_code=201)
    def import_session_attachment(session_id:str,attachment_id:str,request:ArtifactImportRequest,
        principal:RequestPrincipal=principal_dependency,_session_access:None=session_access_dependency):
        runtime=runtime_provider();selected=repository()
        if isinstance(selected,JSONResponse):return selected
        def adopt():
            item=runtime.documents.get(session_id,attachment_id)
            path=runtime.documents.source_path(session_id,attachment_id)
            with path.open('rb') as stream:
                return selected.import_stream(principal.actor_user_id,stream,name=request.name if request.name is not None else item.filename,
                    description=request.description,
                    media_type=item.media_type,collection_id=request.collection_id,
                    source_app_id=request.source_app_id,source_ref='attachment:'+session_id+':'+attachment_id,
                    metadata={'attachment_id':attachment_id,'attachment_session_id':session_id},
                    max_bytes=DEFAULT_RESOURCE_IMPORT_LIMIT_BYTES)
        try:result=guarded(adopt)
        except ValueError:
            return platform_error_response(status_code=409,code='attachment_unavailable',message='The selected attachment changed or is no longer available.')
        if isinstance(result,JSONResponse):return result
        asset,created=result
        return {'asset':asset,'created':created}

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
            lambda: selected.update_asset(
                principal.actor_user_id, asset_id, name=request.name, description=request.description
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
        if asset["media_type"] == STICKER_PACK_MIME:
            manifest = guarded(lambda: StickerPacks.manifest(asset))
            if isinstance(manifest, JSONResponse):
                return manifest
            from urllib.parse import quote
            return JSONResponse(manifest, media_type=STICKER_PACK_MIME, headers={
                "Cache-Control": "private, no-store",
                "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(asset['name'], safe='')}",
                "X-Content-Type-Options": "nosniff",
            })
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

    @router.post("/assets/{asset_id}/resource-handles", status_code=201)
    def create_asset_resource_handle(
        asset_id: str,
        request: AssetHandleRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        runtime = runtime_provider()
        if isinstance(selected, JSONResponse):
            return selected
        if runtime is None:
            return platform_error_response(
                status_code=503,
                code="platform_not_ready",
                message="Gallery handle service is not ready.",
                retryable=True,
            )
        try:
            runtime.extension_manager.require_instance_access(
                request.app_instance_id, principal
            )
            entry = runtime.extension_manager.instance_entry(
                request.app_instance_id, principal=principal
            )
            if entry.get("app_key") != request.consumer_app_id:
                return platform_error_response(
                    status_code=404,
                    code="app_instance_not_found",
                    message="The target AppInstance was not found.",
                )
        except (RepositoryError, ExtensionError, ValueError):
            return platform_error_response(
                status_code=404,
                code="app_instance_not_found",
                message="The target AppInstance was not found.",
            )
        return guarded(
            lambda: selected.create_asset_handle(
                principal.actor_user_id,
                asset_id,
                actor_id=principal.actor_user_id,
                installation_id=principal.installation_id,
                app_instance_id=request.app_instance_id,
                consumer_app_id=request.consumer_app_id,
            )
        )

    @router.get("/resource-handles/{handle_id}/content")
    def resource_handle_content(
        handle_id: str,
        app_instance_id: str = Query(alias="appInstanceId", min_length=1, max_length=200),
        consumer_app_id: str = Query(alias="consumerAppId", min_length=3, max_length=200),
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        runtime = runtime_provider()
        if isinstance(selected, JSONResponse):
            return selected
        if runtime is None:
            return platform_error_response(
                status_code=503, code="platform_not_ready",
                message="Gallery handle service is not ready.", retryable=True,
            )
        try:
            runtime.extension_manager.require_instance_access(app_instance_id, principal)
            entry = runtime.extension_manager.instance_entry(app_instance_id, principal=principal)
            if entry.get("app_key") != consumer_app_id:
                raise ValueError("consumer mismatch")
            asset, path = selected.asset_handle_path(
                handle_id,
                actor_id=principal.actor_user_id,
                installation_id=principal.installation_id,
                app_instance_id=app_instance_id,
                consumer_app_id=consumer_app_id,
            )
        except (RepositoryError, ExtensionError, GalleryError, ValueError):
            return platform_error_response(
                status_code=404,
                code="gallery_resource_handle_not_found",
                message="Gallery Resource Handle was not found or has expired.",
            )
        return FileResponse(
            path,
            media_type=asset["media_type"],
            filename=None,
            content_disposition_type="inline",
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
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
