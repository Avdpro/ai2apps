"""Durable output history surface for the built-in Imagine Studio App."""

from __future__ import annotations

import base64
import binascii
import json
import os
import tempfile
import time
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import PrincipalProvider, resolve_request_principal
from ai2apps.api.ownership import authorize_app_instance
from ai2apps.cloud_gateway import request_cloud_image
from ai2apps.gallery import GalleryRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.model_providers import list_package_models
from ai2apps.images import ImagineStudioHistoryError, ImagineStudioHistoryRepository
from ai2apps.images.history import MAX_HISTORY_ITEMS, MAX_IMAGE_BYTES
from ai2apps.studio import (
    StudioMiniAppRegistry,
    StudioRepository,
    StudioRepositoryError,
)

APP_ID = "ai2apps.imagine-studio"
STUDIO_ID = APP_ID
MINI_APPS = (
    {"id": "ai2apps.imagine.text-to-image", "version": "1.0.0", "kind": "clip", "category": "quick", "icon": "text-cursor-input", "source": "official", "entry": {"kind": "host-adapter", "adapter": "text-to-image"}, "inputs": ["text"], "outputs": ["image"]},
    {"id": "ai2apps.imagine.image-edit", "version": "1.0.0", "kind": "clip", "category": "edit", "icon": "scan-search", "source": "official", "entry": {"kind": "host-adapter", "adapter": "image-edit"}, "inputs": ["image", "text"], "outputs": ["image"]},
    {"id": "ai2apps.imagine.style-transfer", "version": "1.0.0", "kind": "clip", "category": "edit", "icon": "wand-sparkles", "source": "official", "entry": {"kind": "host-adapter", "adapter": "style-transfer"}, "inputs": ["image", "style", "text"], "outputs": ["image"]},
    {"id": "ai2apps.imagine.reference-creation", "version": "1.0.0", "kind": "clip", "category": "create", "icon": "images", "source": "official", "entry": {"kind": "host-adapter", "adapter": "reference-creation"}, "inputs": ["image", "text"], "outputs": ["image"]},
    {"id": "ai2apps.imagine.group-photo", "version": "1.0.0", "kind": "clip", "category": "create", "icon": "users-round", "source": "official", "entry": {"kind": "host-adapter", "adapter": "group-photo"}, "inputs": ["image", "background", "text"], "outputs": ["image"]},
    {"id": "ai2apps.imagine.adjust-image", "version": "1.0.0", "kind": "clip", "category": "edit", "icon": "sliders-horizontal", "source": "official", "entry": {"kind": "host-adapter", "adapter": "adjust-image"}, "inputs": ["image"], "outputs": ["image"]},
)
MINI_APP_BY_ID = {item["id"]: item for item in MINI_APPS}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def _matches_image_media_type(data: bytes, media_type: str) -> bool:
    if media_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if media_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if media_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


class ImagineResultMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    pipeline_id: str = Field(alias="pipelineId", min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=120)
    prompt: str = Field(max_length=32_000)
    model_id: str = Field(alias="modelId", min_length=1, max_length=255)
    model_label: str = Field(alias="modelLabel", min_length=1, max_length=120)
    size: str = Field(min_length=1, max_length=40)
    quality: str = Field(min_length=1, max_length=40)
    format: str = Field(min_length=1, max_length=20)
    filename: str = Field(min_length=1, max_length=255)
    run_id: str | None = Field(default=None, alias="runId", max_length=80)
    mini_app_id: str | None = Field(default=None, alias="miniAppId", max_length=200)


class StudioDraftRequest(BaseModel):
    draft: dict[str, Any] = Field(default_factory=dict)


class StudioRunCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mini_app_id: str = Field(alias="miniAppId", min_length=3, max_length=200)
    title: str = Field(min_length=1, max_length=160)
    input: dict[str, Any] = Field(default_factory=dict)
    retry_of: str | None = Field(default=None, alias="retryOf", max_length=80)


class StudioRunUpdateRequest(BaseModel):
    status: Literal["queued", "running", "waiting_input", "succeeded", "failed", "cancelled", "expired"]
    progress: int = Field(default=0, ge=0, le=100)
    detail: str = Field(default="", max_length=500)
    error: dict[str, Any] | None = None


class StudioRunExecuteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    model: str = Field(min_length=1, max_length=255)
    prompt: str = Field(min_length=1, max_length=32_000)
    size: str = Field(min_length=1, max_length=40)
    quality: str = Field(default="auto", max_length=40)
    output_format: str = Field(default="png", alias="outputFormat", max_length=20)
    image_data_urls: list[str] = Field(default_factory=list, alias="imageDataUrls", max_length=4)


class ArtifactGalleryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    collection_id: str | None = Field(default=None, alias="collectionId", max_length=200)


class ChunkedResultRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    upload_id: str = Field(alias="uploadId", min_length=8, max_length=100)
    index: int = Field(ge=0, lt=512)
    total: int = Field(ge=1, le=512)
    metadata: dict[str, Any]
    data: str = Field(min_length=1, max_length=400_000)


class BatchOutputTarget(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    kind: Literal["local", "gallery"]
    overwrite: bool = False
    source_path: str | None = Field(default=None, alias="sourcePath", max_length=4096)
    output_root: str | None = Field(default=None, alias="outputRoot", max_length=4096)
    relative_path: str | None = Field(default=None, alias="relativePath", max_length=4096)
    asset_id: str | None = Field(default=None, alias="assetId", max_length=200)
    collection_id: str | None = Field(default=None, alias="collectionId", max_length=200)
    name: str = Field(min_length=1, max_length=512)
    media_type: Literal["image/png", "image/jpeg", "image/webp"] = Field(alias="mediaType")


class ChunkedBatchOutputRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    upload_id: str = Field(alias="uploadId", min_length=8, max_length=100)
    index: int = Field(ge=0, lt=512)
    total: int = Field(ge=1, le=512)
    target: BatchOutputTarget
    data: str = Field(min_length=1, max_length=400_000)


def create_imagine_studio_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(prefix="/imagine-studio", tags=["platform-imagine-studio"])
    principal_dependency = Depends(principal_provider)
    chunk_uploads: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    batch_uploads: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    def history(principal: RequestPrincipal, app_instance_id: str) -> ImagineStudioHistoryRepository:
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        config = None if runtime is None else getattr(runtime, "config", None)
        paths = None if config is None else getattr(config, "paths", None)
        extension_manager = None if runtime is None else getattr(runtime, "extension_manager", None)
        if database is None or paths is None or extension_manager is None:
            raise HTTPException(status_code=503, detail="Imagine Studio history is not ready")
        authorize_app_instance(runtime, principal, app_instance_id)
        entry = extension_manager.instance_entry(app_instance_id, principal=principal)
        if entry.get("app_key") != APP_ID:
            raise HTTPException(status_code=404, detail="Imagine Studio history not found")
        return ImagineStudioHistoryRepository(database, paths.artifacts_path / "imagine-studio-history")

    def studio(principal: RequestPrincipal, app_instance_id: str) -> StudioRepository:
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        if database is None:
            raise HTTPException(status_code=503, detail="Imagine Studio Run storage is not ready")
        authorize_app_instance(runtime, principal, app_instance_id)
        entry = runtime.extension_manager.instance_entry(app_instance_id, principal=principal)
        if entry.get("app_key") != APP_ID:
            raise HTTPException(status_code=404, detail="Imagine Studio was not found")
        return StudioRepository(database)

    def scoped_kwargs(principal: RequestPrincipal, app_instance_id: str) -> dict[str, str]:
        return {
            "actor_id": principal.actor_user_id,
            "installation_id": principal.installation_id,
            "app_instance_id": app_instance_id,
            "studio_id": STUDIO_ID,
        }

    def public(record: dict, app_instance_id: str) -> dict:
        content_url = f"/v1/platform/imagine-studio/results/{record['id']}/content?appInstanceId={quote(app_instance_id, safe='')}"
        return record | {"contentUrl": content_url, "downloadUrl": content_url + "&download=true"}

    def studio_error(error: StudioRepositoryError):
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": str(error)},
        ) from error

    def persist_result(
        payload: ImagineResultMetadata,
        data: bytes,
        principal: RequestPrincipal,
        app_instance_id: str,
    ) -> dict:
        record = history(principal, app_instance_id).create(
            actor_id=principal.actor_user_id,
            installation_id=principal.installation_id,
            app_instance_id=app_instance_id,
            metadata=payload.model_dump(by_alias=True),
            data=data,
        )
        result = public(record, app_instance_id)
        if payload.run_id:
            artifact = studio(principal, app_instance_id).create_artifact(
                payload.run_id,
                kind="image",
                name=record["filename"],
                media_type=record["mediaType"],
                preview_url=result["contentUrl"],
                download_url=result["downloadUrl"],
                source_id=record["id"],
                metadata={
                    "historyResultId": record["id"],
                    "miniAppId": payload.mini_app_id,
                    "modelId": record["modelId"],
                    "modelRevision": None,
                    "size": record["size"],
                },
                **scoped_kwargs(principal, app_instance_id),
            )
            result["artifact"] = artifact
        return result

    @router.get("/models")
    def list_image_models(principal: RequestPrincipal = principal_dependency):
        # The OpenAI /v1/models catalog intentionally omits UI readiness and
        # image geometry. Share ACPF's Package resolver, without internal paths
        # or Worker authorization headers in the browser response.
        data = []
        for model in list_package_models(runtime_provider()):
            if model.model_type != "image_generation" or model.metadata.get("internal"):
                continue
            data.append({
                "id": model.id,
                "display_name": model.display_name,
                "model_type": model.model_type,
                "source_type": "package",
                "checkpoint_ready": model.checkpoint_ready,
                "is_hidden": not model.checkpoint_ready,
                "capabilities": list(model.capabilities),
                "image_capabilities": model.image_capabilities,
            })
        return {"data": data}

    @router.get("/mini-apps")
    def list_mini_apps(principal: RequestPrincipal = principal_dependency):
        runtime = runtime_provider()
        manager = None if runtime is None else getattr(runtime, "extension_manager", None)
        if manager is None:
            return {
                "schema": "ai2apps.studio-mini-app-list/v1",
                "studioId": STUDIO_ID,
                "items": list(MINI_APPS),
            }
        return StudioMiniAppRegistry(manager).list(
            STUDIO_ID, builtins=MINI_APPS, principal=principal
        )

    @router.get("/drafts/{mini_app_id:path}")
    def get_draft(
        mini_app_id: str,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        if mini_app_id not in MINI_APP_BY_ID:
            raise HTTPException(status_code=404, detail="Imagine Mini-App was not found")
        return studio(principal, app_instance_id).get_draft(
            mini_app_id=mini_app_id, **scoped_kwargs(principal, app_instance_id)
        ) or {"miniAppId": mini_app_id, "draft": {}}

    @router.put("/drafts/{mini_app_id:path}")
    def save_draft(
        mini_app_id: str,
        request: StudioDraftRequest,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        if mini_app_id not in MINI_APP_BY_ID:
            raise HTTPException(status_code=404, detail="Imagine Mini-App was not found")
        encoded = json.dumps(request.draft, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > 128 * 1024:
            raise HTTPException(status_code=413, detail="Imagine Mini-App draft is too large")
        return studio(principal, app_instance_id).save_draft(
            mini_app_id=mini_app_id, draft=request.draft,
            **scoped_kwargs(principal, app_instance_id),
        )

    @router.get("/runs")
    def list_runs(
        limit: int = Query(default=50, ge=1, le=100),
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        repository = studio(principal, app_instance_id)
        legacy_to_mini = {
            "text-image": "ai2apps.imagine.text-to-image",
            "image-edit": "ai2apps.imagine.image-edit",
            "style-transfer": "ai2apps.imagine.style-transfer",
            "reference-create": "ai2apps.imagine.reference-creation",
            "group-photo": "ai2apps.imagine.group-photo",
            "adjust-image": "ai2apps.imagine.adjust-image",
        }
        for record in history(principal, app_instance_id).list(
            actor_id=principal.actor_user_id, installation_id=principal.installation_id,
            app_instance_id=app_instance_id, limit=MAX_HISTORY_ITEMS,
        ):
            projected = public(record, app_instance_id)
            mini_app_id = legacy_to_mini.get(record["pipelineId"], "ai2apps.imagine.text-to-image")
            repository.import_legacy_artifact(
                mini_app_id=mini_app_id, mini_app_version="1.0.0", title=record["title"],
                input_data={"prompt": record["prompt"], "modelId": record["modelId"], "size": record["size"]},
                source_id=record["id"], name=record["filename"], media_type=record["mediaType"],
                preview_url=projected["contentUrl"], download_url=projected["downloadUrl"],
                created_at=record["createdAt"], metadata={"historyResultId": record["id"], "legacyPipelineId": record["pipelineId"], "modelId": record["modelId"]},
                **scoped_kwargs(principal, app_instance_id),
            )
        return {"items": list(repository.list_runs(
            limit=limit, **scoped_kwargs(principal, app_instance_id)
        ))}

    @router.post("/runs", status_code=201)
    def create_run(
        request: StudioRunCreateRequest,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        definition = MINI_APP_BY_ID.get(request.mini_app_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Imagine Mini-App was not found")
        try:
            return studio(principal, app_instance_id).create_run(
                mini_app_id=request.mini_app_id,
                mini_app_version=definition["version"],
                placement=STUDIO_ID,
                title=request.title,
                input_data=request.input,
                retry_of=request.retry_of,
                **scoped_kwargs(principal, app_instance_id),
            )
        except StudioRepositoryError as error:
            return studio_error(error)

    @router.patch("/runs/{run_id}")
    def update_run(
        run_id: str,
        request: StudioRunUpdateRequest,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return studio(principal, app_instance_id).update_run(
                run_id, status=request.status, progress=request.progress,
                detail=request.detail, error=request.error,
                **scoped_kwargs(principal, app_instance_id),
            )
        except StudioRepositoryError as error:
            return studio_error(error)

    @router.post("/runs/{run_id}/execute", status_code=202)
    async def execute_run(
        run_id: str,
        request: StudioRunExecuteRequest,
        background_tasks: BackgroundTasks,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = runtime_provider()
        repository = studio(principal, app_instance_id)
        history_repository = history(principal, app_instance_id)
        scope = scoped_kwargs(principal, app_instance_id)
        try:
            run = repository.get_run(run_id, **scope)
        except StudioRepositoryError as error:
            return studio_error(error)
        if run["status"] != "queued":
            raise HTTPException(status_code=409, detail="Imagine Studio Run is not queued")
        repository.update_run(
            run_id, status="running", progress=10, detail="Generating image", **scope
        )
        payload = request.model_dump(by_alias=True)
        if not payload["imageDataUrls"]:
            payload.pop("imageDataUrls")
        payload["idempotencyKey"] = f"imagine-run-{run_id}"
        mini_app_id = run["miniAppId"]
        legacy_id = {
            "ai2apps.imagine.text-to-image": "text-image",
            "ai2apps.imagine.image-edit": "image-edit",
            "ai2apps.imagine.style-transfer": "style-transfer",
            "ai2apps.imagine.reference-creation": "reference-create",
            "ai2apps.imagine.group-photo": "group-photo",
        }.get(mini_app_id, "text-image")

        async def generate_in_background() -> None:
            try:
                result = await request_cloud_image(
                    payload,
                    edit=bool(request.image_data_urls),
                    base_path=runtime.config.paths.base_path,
                    cloud_client=runtime.cloud,
                    cloud_headers=runtime.cloud_ai_authorization_headers(principal),
                )
                current = repository.get_run(run_id, **scope)
                if current["status"] == "cancelled":
                    return
                image = result.get("image") if isinstance(result, dict) else None
                data_url = str((image or {}).get("dataUrl") or "")
                header, separator, encoded = data_url.partition(",")
                media_type = header.removeprefix("data:").removesuffix(";base64")
                if not separator or media_type not in {"image/png", "image/jpeg", "image/webp"}:
                    raise ValueError("Cloud image response is invalid")
                response_format = str((image or {}).get("format") or media_type.split("/", 1)[1]).lower()
                if response_format == "jpg":
                    response_format = "jpeg"
                expected_media_type = {
                    "png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp",
                }.get(response_format)
                if expected_media_type != media_type:
                    raise ValueError("Cloud image format does not match its Data URL MIME")
                data = base64.b64decode(encoded, validate=True)
                extension = "jpg" if media_type == "image/jpeg" else media_type.split("/", 1)[1]
                filename = f"imagine-{run_id[-8:]}.{extension}"
                record = history_repository.create(
                    actor_id=principal.actor_user_id,
                    installation_id=principal.installation_id,
                    app_instance_id=app_instance_id,
                    metadata={
                        "pipelineId": legacy_id,
                        "miniAppId": mini_app_id,
                        "runId": run_id,
                        "title": run["title"],
                        "prompt": request.prompt,
                        "modelId": request.model,
                        "modelLabel": str(run["input"].get("modelLabel") or request.model)[:120],
                        "size": str((image or {}).get("size") or request.size),
                        "quality": request.quality,
                        "format": response_format,
                        "filename": filename,
                    },
                    data=data,
                )
                result_record = public(record, app_instance_id)
                repository.create_artifact(
                    run_id,
                    kind="image",
                    name=record["filename"],
                    media_type=record["mediaType"],
                    preview_url=result_record["contentUrl"],
                    download_url=result_record["downloadUrl"],
                    source_id=record["id"],
                    metadata={
                        "historyResultId": record["id"],
                        "miniAppId": mini_app_id,
                        "modelId": request.model,
                        "modelRevision": None,
                        "size": record["size"],
                        "requestedSize": request.size,
                        "format": response_format,
                        "requestedFormat": request.output_format,
                    },
                    **scope,
                )
                repository.update_run(
                    run_id, status="succeeded", progress=100, detail="Completed", **scope
                )
            except (binascii.Error, ValueError, HTTPException) as error:
                detail = error.detail if isinstance(error, HTTPException) else str(error)
                if isinstance(detail, dict):
                    message = str(detail.get("message") or detail.get("code") or "Image generation failed")
                    code = str(detail.get("code") or "image_generation_failed")
                else:
                    message, code = str(detail), "image_generation_failed"
                with suppress(StudioRepositoryError):
                    repository.update_run(
                        run_id, status="failed", progress=100, detail="Failed",
                        error={"code": code, "message": message}, **scope,
                    )
            except Exception as error:  # pragma: no cover - defensive task boundary
                with suppress(StudioRepositoryError):
                    repository.update_run(
                        run_id, status="failed", progress=100, detail="Failed",
                        error={"code": "image_generation_failed", "message": str(error)[:1000]},
                        **scope,
                    )

        background_tasks.add_task(generate_in_background)
        return repository.get_run(run_id, **scope)

    @router.get("/results")
    def list_results(
        limit: int = Query(default=MAX_HISTORY_ITEMS, ge=1, le=MAX_HISTORY_ITEMS),
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        repository = history(principal, app_instance_id)
        return {"items": [public(item, app_instance_id) for item in repository.list(actor_id=principal.actor_user_id, installation_id=principal.installation_id, app_instance_id=app_instance_id, limit=limit)]}

    @router.post("/results", status_code=201)
    async def create_result(
        metadata: Annotated[str, Form()],
        image: Annotated[UploadFile, File()],
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            payload = ImagineResultMetadata.model_validate(json.loads(metadata))
            data = await image.read(MAX_IMAGE_BYTES + 1)
            return persist_result(payload, data, principal, app_instance_id)
        except (json.JSONDecodeError, ValidationError) as error:
            raise HTTPException(status_code=422, detail="Imagine Studio result metadata is invalid") from error
        except ImagineStudioHistoryError as error:
            raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": str(error)}) from error

    @router.post("/results/chunks")
    def create_chunked_result(
        request: ChunkedResultRequest,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            history(principal, app_instance_id)
            payload = ImagineResultMetadata.model_validate(request.metadata)
            data = base64.b64decode(request.data, validate=True)
            if len(data) > 256 * 1024:
                raise HTTPException(status_code=413, detail="Imagine Studio result chunk is too large")
            now = time.monotonic()
            for key, value in list(chunk_uploads.items()):
                if now - value["updatedAt"] > 600:
                    chunk_uploads.pop(key, None)
            key = (principal.actor_user_id, principal.installation_id, app_instance_id, request.upload_id)
            entry = chunk_uploads.setdefault(key, {"total": request.total, "chunks": {}, "updatedAt": now})
            if entry["total"] != request.total:
                chunk_uploads.pop(key, None)
                raise HTTPException(status_code=409, detail="Imagine Studio result upload changed")
            entry["chunks"][request.index] = data
            entry["updatedAt"] = now
            if sum(len(chunk) for chunk in entry["chunks"].values()) > MAX_IMAGE_BYTES:
                chunk_uploads.pop(key, None)
                raise HTTPException(status_code=413, detail="Imagine Studio image is too large")
            if len(entry["chunks"]) != request.total:
                return {"complete": False, "received": len(entry["chunks"]), "total": request.total}
            image_data = b"".join(entry["chunks"][index] for index in range(request.total))
            chunk_uploads.pop(key, None)
            return persist_result(payload, image_data, principal, app_instance_id)
        except (binascii.Error, ValidationError) as error:
            raise HTTPException(status_code=422, detail="Imagine Studio result metadata is invalid") from error
        except ImagineStudioHistoryError as error:
            raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": str(error)}) from error

    @router.post("/batch-output/chunks")
    def create_chunked_batch_output(
        request: ChunkedBatchOutputRequest,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        history(principal, app_instance_id)
        try:
            data = base64.b64decode(request.data, validate=True)
        except binascii.Error as error:
            raise HTTPException(status_code=422, detail="Batch image chunk is invalid") from error
        if len(data) > 256 * 1024:
            raise HTTPException(status_code=413, detail="Batch image chunk is too large")
        now = time.monotonic()
        for key, value in list(batch_uploads.items()):
            if now - value["updatedAt"] > 600:
                batch_uploads.pop(key, None)
        key = (principal.actor_user_id, principal.installation_id, app_instance_id, request.upload_id)
        target = request.target.model_dump(by_alias=True)
        entry = batch_uploads.setdefault(
            key, {"total": request.total, "target": target, "chunks": {}, "updatedAt": now}
        )
        if entry["total"] != request.total or entry["target"] != target:
            batch_uploads.pop(key, None)
            raise HTTPException(status_code=409, detail="Batch image upload changed")
        entry["chunks"][request.index] = data
        entry["updatedAt"] = now
        if sum(len(chunk) for chunk in entry["chunks"].values()) > MAX_IMAGE_BYTES:
            batch_uploads.pop(key, None)
            raise HTTPException(status_code=413, detail="Batch image is too large")
        if len(entry["chunks"]) != request.total:
            return {"complete": False, "received": len(entry["chunks"]), "total": request.total}
        image_data = b"".join(entry["chunks"][index] for index in range(request.total))
        batch_uploads.pop(key, None)
        if not _matches_image_media_type(image_data, request.target.media_type):
            raise HTTPException(status_code=422, detail="Batch output is not a valid image of the declared type")
        selected = request.target
        if selected.kind == "local":
            source = Path(selected.source_path or "").expanduser()
            if not source.is_absolute() or not source.is_file() or source.suffix.lower() not in IMAGE_SUFFIXES:
                raise HTTPException(status_code=422, detail="Selected source file is unavailable")
            if selected.overwrite:
                destination = source.resolve()
            else:
                root = Path(selected.output_root or "").expanduser()
                if not root.is_absolute() or not root.is_dir():
                    raise HTTPException(status_code=422, detail="Selected output directory is unavailable")
                relative = Path(selected.relative_path or selected.name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise HTTPException(status_code=422, detail="Batch output path is invalid")
                destination = (root.resolve() / relative).resolve()
                try:
                    destination.relative_to(root.resolve())
                except ValueError as error:
                    raise HTTPException(status_code=422, detail="Batch output escapes the selected directory") from error
                if destination.exists():
                    raise HTTPException(status_code=409, detail=f"Output already exists: {destination.name}")
                destination.parent.mkdir(parents=True, exist_ok=True)
            allowed_suffixes = {
                "image/png": {".png"},
                "image/jpeg": {".jpg", ".jpeg"},
                "image/webp": {".webp"},
            }[selected.media_type]
            if destination.suffix.lower() not in allowed_suffixes:
                raise HTTPException(status_code=422, detail="Batch output extension does not match its image format")
            descriptor, temporary_name = tempfile.mkstemp(prefix=".ai2apps-adjust-", dir=destination.parent)
            try:
                with os.fdopen(descriptor, "wb") as output:
                    output.write(image_data)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary_name, destination)
            finally:
                Path(temporary_name).unlink(missing_ok=True)
            return {"complete": True, "kind": "local", "path": str(destination), "sizeBytes": len(image_data)}

        runtime = runtime_provider()
        gallery = GalleryRepository(
            runtime.database,
            runtime.config.paths.artifacts_path / "gallery",
            getattr(runtime, "events", None),
        )
        if selected.overwrite:
            if not selected.asset_id:
                raise HTTPException(status_code=422, detail="Gallery asset is required for overwrite")
            asset = gallery.replace_asset_stream(
                principal.actor_user_id, selected.asset_id, BytesIO(image_data),
                media_type=selected.media_type, source_app_id=APP_ID,
                metadata={"adjustment": "batch"}, max_bytes=MAX_IMAGE_BYTES,
            )
            return {"complete": True, "kind": "gallery", "asset": asset, "created": False}
        asset, created = gallery.import_stream(
            principal.actor_user_id, BytesIO(image_data), name=selected.name,
            media_type=selected.media_type, collection_id=selected.collection_id,
            source_app_id=APP_ID, source_ref="imagine-studio:batch-adjustment",
            metadata={"adjustment": "batch"}, max_bytes=MAX_IMAGE_BYTES,
        )
        return {"complete": True, "kind": "gallery", "asset": asset, "created": created}

    @router.get("/results/{result_id}/content")
    def result_content(
        result_id: str,
        app_instance_id: str = Query(alias="appInstanceId", min_length=1, max_length=200),
        download: bool = False,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = history(principal, app_instance_id).content_path(
            result_id, actor_id=principal.actor_user_id, installation_id=principal.installation_id, app_instance_id=app_instance_id
        )
        if selected is None:
            raise HTTPException(status_code=404, detail="Imagine Studio result not found")
        record, path = selected
        return FileResponse(path, media_type=record["mediaType"], filename=record["filename"], content_disposition_type="attachment" if download else "inline", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})

    @router.post("/artifacts/{artifact_id}/gallery", status_code=201)
    def add_artifact_to_gallery(
        artifact_id: str,
        request: ArtifactGalleryRequest,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = runtime_provider()
        try:
            artifact = studio(principal, app_instance_id).get_artifact(
                artifact_id, **scoped_kwargs(principal, app_instance_id)
            )
        except StudioRepositoryError as error:
            return studio_error(error)
        result_id = str(artifact["metadata"].get("historyResultId") or "")
        selected = history(principal, app_instance_id).content_path(
            result_id, actor_id=principal.actor_user_id,
            installation_id=principal.installation_id, app_instance_id=app_instance_id,
        )
        if selected is None:
            raise HTTPException(status_code=404, detail="Imagine Studio Artifact content was not found")
        record, path = selected
        gallery = GalleryRepository(runtime.database, runtime.config.paths.artifacts_path / "gallery", getattr(runtime, "events", None))
        with path.open("rb") as stream:
            asset, created = gallery.import_stream(
                principal.actor_user_id, stream, name=record["filename"],
                media_type=record["mediaType"], collection_id=request.collection_id,
                source_app_id=APP_ID, source_ref=artifact["uri"],
                metadata={"artifact_id": artifact_id, "artifact_run_id": artifact["runId"]},
                max_bytes=MAX_IMAGE_BYTES,
            )
        return {"asset": asset, "created": created}

    @router.delete("/results/{result_id}", status_code=204)
    def delete_result(
        result_id: str,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        if not history(principal, app_instance_id).delete(result_id, actor_id=principal.actor_user_id, installation_id=principal.installation_id, app_instance_id=app_instance_id):
            raise HTTPException(status_code=404, detail="Imagine Studio result not found")
        return Response(status_code=204)

    @router.delete("/results", status_code=204)
    def clear_results(
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        history(principal, app_instance_id).clear(actor_id=principal.actor_user_id, installation_id=principal.installation_id, app_instance_id=app_instance_id)
        return Response(status_code=204)

    return router
