"""Model discovery surface for the built-in Video Studio App."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Annotated, Any, Literal

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
from ai2apps.config import DEFAULT_COMPOSER_IMPORT_LIMIT_BYTES
from ai2apps.gallery import GalleryError, GalleryRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.model_identity import build_model_identity
from ai2apps.model_providers import list_package_models
from ai2apps.studio import (
    StudioMiniAppRegistry,
    StudioRepository,
    StudioRepositoryError,
)
from ai2apps.video import (
    MAX_FRAME_BYTES,
    VideoGenerationError,
    VideoStudioDraftError,
    VideoStudioDraftRepository,
)
from ai2apps.video.audio_extraction import extract_audio_to_wav
from ai2apps.video.composer import (
    ComposerError,
    ComposerProject,
    ComposerSourceStore,
    render_composition,
)
from ai2apps.video_policy import (
    effective_video_capabilities,
    is_temporarily_disabled_video_model,
)

APP_ID = "ai2apps.video-studio"
STUDIO_ID = APP_ID
EXTRACT_AUDIO_ID = "ai2apps.video.extract-audio"
COMPOSER_ID = "ai2apps.video.composer"
MINI_APPS = (
    {"schema": "ai2apps.mini-app/v1", "id": "ai2apps.video.text-to-video", "version": "1.0.0", "kind": "clip", "mode": "t2v", "icon": "type", "entry": {"kind": "host-adapter", "adapter": "text-to-video"}, "ui": {"minimum_width": 520, "drop_targets": [{"id": "prompt", "accepts": ["text"]}]}, "placements": [{"studio": STUDIO_ID, "category": "create", "order": 10}], "inputs": [{"id": "prompt", "kind": "text", "required": True}], "outputs": [{"id": "video", "kind": "video", "final": True}], "executor": {"pipelines": ["ai2apps.pipeline.video-generation"]}, "requirements": {"capabilities": ["video.generation"]}},
    {"schema": "ai2apps.mini-app/v1", "id": "ai2apps.video.image-to-video", "version": "1.0.0", "kind": "clip", "mode": "i2v", "icon": "image", "entry": {"kind": "host-adapter", "adapter": "image-to-video"}, "ui": {"minimum_width": 520, "drop_targets": [{"id": "first_frame", "accepts": ["image"]}]}, "placements": [{"studio": STUDIO_ID, "category": "create", "order": 20}], "inputs": [{"id": "first_frame", "kind": "image", "required": True}], "outputs": [{"id": "video", "kind": "video", "final": True}], "executor": {"pipelines": ["ai2apps.pipeline.video-generation"]}, "requirements": {"capabilities": ["video.generation"]}},
    {"schema": "ai2apps.mini-app/v1", "id": "ai2apps.video.reference-to-video", "version": "1.0.0", "kind": "clip", "mode": "r2v", "icon": "scan-search", "entry": {"kind": "host-adapter", "adapter": "reference-to-video"}, "ui": {"minimum_width": 520, "drop_targets": [{"id": "references", "accepts": ["image", "video", "audio"]}]}, "placements": [{"studio": STUDIO_ID, "category": "create", "order": 30}], "inputs": [{"id": "references", "kind": "asset-list", "required": True}], "outputs": [{"id": "video", "kind": "video", "final": True}], "executor": {"pipelines": ["ai2apps.pipeline.video-generation"]}, "requirements": {"capabilities": ["video.reference_generation"]}},
    {"schema": "ai2apps.mini-app/v1", "id": COMPOSER_ID, "version": "0.2.0", "kind": "project", "mode": "composer", "icon": "panels-top-left", "entry": {"kind": "host-adapter", "adapter": "video-composer"}, "ui": {"minimum_width": 760, "drop_targets": [{"id": "timeline", "accepts": ["image", "video", "audio"]}]}, "placements": [{"studio": STUDIO_ID, "category": "edit", "order": 35}], "inputs": [{"id": "sources", "kind": "asset-list", "required": False}], "outputs": [{"id": "video", "kind": "video", "media_types": ["video/mp4"], "final": True}], "executor": {"pipelines": ["ai2apps.pipeline.video-composition"]}, "requirements": {"capabilities": ["media.video.compose"]}},
    {"schema": "ai2apps.mini-app/v1", "id": EXTRACT_AUDIO_ID, "version": "1.0.0", "kind": "clip", "mode": "x2a", "icon": "audio-lines", "entry": {"kind": "host-adapter", "adapter": "extract-audio"}, "ui": {"minimum_width": 520, "drop_targets": [{"id": "video", "accepts": ["video"]}]}, "placements": [{"studio": STUDIO_ID, "category": "edit", "order": 40}], "inputs": [{"id": "video", "kind": "video", "required": True}], "outputs": [{"id": "audio", "kind": "audio", "media_types": ["audio/wav"], "final": True}], "executor": {"pipelines": ["ai2apps.pipeline.media-extraction"]}, "requirements": {"capabilities": ["media.audio_decode"]}},
)
MINI_APP_BY_ID = {item["id"]: item for item in MINI_APPS}


class VideoStudioDraftPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    action: str = Field(min_length=1, max_length=120)
    mode: Literal["t2v", "i2v", "r2v"]
    model_id: str = Field(alias="modelId", max_length=255)
    prompt: str = Field(max_length=8_000)
    resolution: str = Field(min_length=3, max_length=40)
    duration: float = Field(ge=0.5, le=60)
    preset: str = Field(min_length=1, max_length=80)
    steps: int = Field(ge=1, le=60)
    seed: int = Field(ge=0, le=2**31 - 1)
    label: str = Field(max_length=120)
    batch_text: str = Field(default="", alias="batchText", max_length=400_000)


class StudioDraftRequest(BaseModel):
    draft: dict[str, Any] = Field(default_factory=dict)


class StudioRunCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    mini_app_id: str = Field(alias="miniAppId", min_length=3, max_length=200)
    title: str = Field(min_length=1, max_length=160)
    input: dict[str, Any] = Field(default_factory=dict)
    retry_of: str | None = Field(default=None, alias="retryOf", max_length=80)


class ExtractAudioRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    resource_handle: str | None = Field(
        default=None, alias="resourceHandle", min_length=12, max_length=200
    )
    source_path: str | None = Field(default=None, alias="sourcePath", max_length=4096)
    source_name: str | None = Field(default=None, alias="sourceName", max_length=512)
    media_type: str | None = Field(default=None, alias="mediaType", max_length=255)
    output_name: str | None = Field(default=None, alias="outputName", max_length=255)


class ComposerSourceRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    source_path: str | None = Field(default=None, alias="sourcePath", max_length=4096)
    resource_handle: str | None = Field(
        default=None, alias="resourceHandle", min_length=12, max_length=200
    )
    name: str | None = Field(default=None, max_length=512)
    media_type: str | None = Field(default=None, alias="mediaType", max_length=255)


class ComposerRenderRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    project: ComposerProject
    output_name: str | None = Field(default=None, alias="outputName", max_length=255)


class ComposerProjectDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    schema_name: Literal["ai2apps.video-composer-project/v1"] = Field(
        default="ai2apps.video-composer-project/v1", alias="schema"
    )
    project: ComposerProject
    source_ids: list[str] = Field(default_factory=list, alias="sourceIds", max_length=600)


class ComposerProjectOpenRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    source_path: str = Field(alias="sourcePath", min_length=1, max_length=4096)


class ComposerProjectSaveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    target_path: str = Field(alias="targetPath", min_length=1, max_length=4096)
    project: ComposerProject
    source_ids: list[str] = Field(default_factory=list, alias="sourceIds", max_length=600)


def create_video_studio_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(prefix="/video-studio", tags=["platform-video-studio"])
    principal_dependency = Depends(principal_provider)

    def drafts(
        principal: RequestPrincipal, app_instance_id: str
    ) -> VideoStudioDraftRepository:
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        config = None if runtime is None else getattr(runtime, "config", None)
        paths = None if config is None else getattr(config, "paths", None)
        extension_manager = (
            None if runtime is None else getattr(runtime, "extension_manager", None)
        )
        if database is None or paths is None or extension_manager is None:
            raise HTTPException(status_code=503, detail="Video Studio drafts are not ready")
        authorize_app_instance(runtime, principal, app_instance_id)
        entry = extension_manager.instance_entry(app_instance_id, principal=principal)
        if entry.get("app_key") != APP_ID:
            raise HTTPException(status_code=404, detail="Video Studio draft not found")
        return VideoStudioDraftRepository(
            database, paths.artifacts_path / "video-studio-drafts"
        )

    def owned_draft(
        repository: VideoStudioDraftRepository,
        draft_id: str,
        principal: RequestPrincipal,
        app_instance_id: str,
    ):
        record = repository.get(
            draft_id,
            actor_id=principal.actor_user_id,
            installation_id=principal.installation_id,
            app_instance_id=app_instance_id,
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Video Studio draft not found")
        return record

    def public_draft(record: dict) -> dict:
        return {
            "resumeToken": record["id"],
            "actionId": record["actionId"],
            "draft": record["draft"],
            "frames": {
                which: {
                    key: value
                    for key, value in descriptor.items()
                    if key != "path"
                }
                | {
                    "contentUrl": f"/v1/platform/video-studio/drafts/{record['id']}/frames/{which}"
                }
                for which, descriptor in record["frames"].items()
            },
        }

    def studio(
        principal: RequestPrincipal, app_instance_id: str
    ) -> StudioRepository:
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        extension_manager = (
            None if runtime is None else getattr(runtime, "extension_manager", None)
        )
        if database is None or extension_manager is None:
            raise HTTPException(status_code=503, detail="Video Studio Run storage is not ready")
        authorize_app_instance(runtime, principal, app_instance_id)
        entry = extension_manager.instance_entry(app_instance_id, principal=principal)
        if entry.get("app_key") != APP_ID:
            raise HTTPException(status_code=404, detail="Video Studio was not found")
        return StudioRepository(database)

    def gallery() -> GalleryRepository:
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        paths = None if runtime is None else getattr(runtime.config, "paths", None)
        events = None if runtime is None else getattr(runtime, "events", None)
        if database is None or paths is None:
            raise HTTPException(status_code=503, detail="Gallery storage is not ready")
        return GalleryRepository(database, paths.artifacts_path / "gallery", events)

    def composer_sources() -> ComposerSourceStore:
        runtime = runtime_provider()
        paths = None if runtime is None else getattr(runtime.config, "paths", None)
        if paths is None:
            raise HTTPException(status_code=503, detail="Composer media storage is not ready")
        return ComposerSourceStore(paths.artifacts_path / "video-composer-sources")

    def composer_error(error: ComposerError):
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": str(error)},
        ) from error

    def scope(principal: RequestPrincipal, app_instance_id: str) -> dict[str, str]:
        return {
            "actor_id": principal.actor_user_id,
            "installation_id": principal.installation_id,
            "app_instance_id": app_instance_id,
            "studio_id": STUDIO_ID,
        }

    def studio_error(error: StudioRepositoryError):
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": str(error)},
        ) from error

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

    @router.get("/studio-drafts/{mini_app_id:path}")
    def get_studio_draft(
        mini_app_id: str,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        if mini_app_id not in MINI_APP_BY_ID:
            raise HTTPException(status_code=404, detail="Video Mini-App was not found")
        return studio(principal, app_instance_id).get_draft(
            mini_app_id=mini_app_id, **scope(principal, app_instance_id)
        ) or {"miniAppId": mini_app_id, "draft": {}}

    @router.put("/studio-drafts/{mini_app_id:path}")
    def save_studio_draft(
        mini_app_id: str,
        request: StudioDraftRequest,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        if mini_app_id not in MINI_APP_BY_ID:
            raise HTTPException(status_code=404, detail="Video Mini-App was not found")
        if len(str(request.draft).encode("utf-8")) > 128 * 1024:
            raise HTTPException(status_code=413, detail="Video Mini-App draft is too large")
        return studio(principal, app_instance_id).save_draft(
            mini_app_id=mini_app_id,
            draft=request.draft,
            **scope(principal, app_instance_id),
        )

    def prune_history(repository, run_scope):
        runtime = runtime_provider()
        workspace = getattr(runtime, "workspace", None)
        if workspace is not None:
            repository.prune_output_history(workspace, **run_scope)

    @router.get("/runs")
    def list_runs(
        limit: int = Query(default=50, ge=1, le=100),
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        repository = studio(principal, app_instance_id)
        prune_history(repository, scope(principal, app_instance_id))
        return {
            "items": list(
                repository.list_runs(
                    limit=limit, **scope(principal, app_instance_id)
                )
            )
        }

    @router.get("/runs/{run_id}")
    def get_run(
        run_id: str,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return studio(principal, app_instance_id).get_run(
                run_id, **scope(principal, app_instance_id)
            )
        except StudioRepositoryError as error:
            return studio_error(error)

    @router.post("/runs", status_code=201)
    def create_run(
        request: StudioRunCreateRequest,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        definition = MINI_APP_BY_ID.get(request.mini_app_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Video Mini-App was not found")
        try:
            return studio(principal, app_instance_id).create_run(
                mini_app_id=request.mini_app_id,
                mini_app_version=definition["version"],
                placement=STUDIO_ID,
                title=request.title,
                input_data=request.input,
                retry_of=request.retry_of,
                step_label=(
                    "Extract audio track"
                    if request.mini_app_id == EXTRACT_AUDIO_ID
                    else "Run Mini-App"
                ),
                **scope(principal, app_instance_id),
            )
        except StudioRepositoryError as error:
            return studio_error(error)

    @router.post("/composer/sources", status_code=201)
    def register_composer_source(
        request: ComposerSourceRequest,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        studio(principal, app_instance_id)
        if bool(request.source_path) == bool(request.resource_handle):
            raise HTTPException(
                status_code=422,
                detail="Provide exactly one selected local path or Gallery Resource Handle",
            )
        path: Path
        name = request.name
        media_type = request.media_type
        if request.resource_handle:
            try:
                asset, path = gallery().asset_handle_path(
                    request.resource_handle,
                    actor_id=principal.actor_user_id,
                    installation_id=principal.installation_id,
                    app_instance_id=app_instance_id,
                    consumer_app_id=APP_ID,
                )
            except GalleryError as error:
                raise HTTPException(
                    status_code=404,
                    detail={"code": error.code, "message": str(error)},
                ) from error
            if asset["kind"] not in {"image", "video", "audio"}:
                raise HTTPException(status_code=422, detail="Composer accepts image, video, or audio media")
            name, media_type = asset["name"], asset["media_type"]
        else:
            path = Path(request.source_path or "")
        try:
            return composer_sources().register(
                path,
                actor_id=principal.actor_user_id,
                installation_id=principal.installation_id,
                app_instance_id=app_instance_id,
                display_name=name,
                media_type=media_type,
            )
        except ComposerError as error:
            return composer_error(error)

    @router.post("/composer/sources/import", status_code=201)
    async def import_composer_source(
        file: Annotated[UploadFile, File()],
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        studio(principal, app_instance_id)
        name = Path(file.filename or "media").name
        media_type = str(file.content_type or "")
        if media_type and not media_type.startswith(("image/", "video/", "audio/")):
            raise HTTPException(
                status_code=422,
                detail="Composer accepts image, video, or audio media",
            )
        try:
            return await asyncio.to_thread(
                composer_sources().import_stream,
                file.file,
                actor_id=principal.actor_user_id,
                installation_id=principal.installation_id,
                app_instance_id=app_instance_id,
                display_name=name,
                media_type=media_type or None,
                max_bytes=DEFAULT_COMPOSER_IMPORT_LIMIT_BYTES,
            )
        except ComposerError as error:
            return composer_error(error)
        finally:
            await file.close()

    def composer_document_sources(
        source_ids: list[str],
        project: ComposerProject,
        principal: RequestPrincipal,
        app_instance_id: str,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        referenced = {clip.source_id for clip in project.clips}
        referenced.update(clip.mask_source_id for clip in project.clips if clip.mask_source_id)
        ordered = list(dict.fromkeys([*source_ids, *sorted(referenced)]))
        public_sources: list[dict[str, Any]] = []
        for source_id in ordered:
            try:
                record, _ = composer_sources().get(
                    source_id,
                    actor_id=principal.actor_user_id,
                    installation_id=principal.installation_id,
                    app_instance_id=app_instance_id,
                )
            except ComposerError as error:
                return composer_error(error)
            public_sources.append(ComposerSourceStore.public(record))
        return ordered, public_sources

    @router.post("/composer/projects/open")
    def open_composer_project(
        request: ComposerProjectOpenRequest,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        studio(principal, app_instance_id)
        source = Path(request.source_path)
        if not source.is_absolute() or source.suffix.lower() not in {".ai2video", ".json"}:
            raise HTTPException(status_code=422, detail="Select an AI2Apps Video Composer project file")
        try:
            source = source.resolve(strict=True)
            if not source.is_file() or source.stat().st_size > 4 * 1024 * 1024:
                raise OSError
            document = ComposerProjectDocument.model_validate_json(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValidationError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=422, detail="The selected Composer project is invalid") from error
        source_ids, public_sources = composer_document_sources(
            document.source_ids, document.project, principal, app_instance_id
        )
        return {
            "schema": document.schema_name,
            "path": str(source),
            "project": document.project.model_dump(by_alias=True),
            "sourceIds": source_ids,
            "sources": public_sources,
        }

    @router.post("/composer/projects/save")
    def save_composer_project(
        request: ComposerProjectSaveRequest,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        studio(principal, app_instance_id)
        requested = Path(request.target_path)
        if not requested.is_absolute() or requested.suffix.lower() not in {".ai2video", ".json"}:
            raise HTTPException(status_code=422, detail="Composer project names must end in .ai2video or .json")
        try:
            parent = requested.parent.resolve(strict=True)
        except OSError as error:
            raise HTTPException(status_code=422, detail="The selected project folder is unavailable") from error
        target = parent / requested.name
        if target.exists() and not target.is_file():
            raise HTTPException(status_code=422, detail="The selected project path is not a file")
        source_ids, public_sources = composer_document_sources(
            request.source_ids, request.project, principal, app_instance_id
        )
        document = ComposerProjectDocument(project=request.project, sourceIds=source_ids)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(
                document.model_dump_json(by_alias=True, indent=2), encoding="utf-8"
            )
            os.chmod(temporary, 0o600)
            temporary.replace(target)
        except OSError as error:
            with suppress(OSError):
                temporary.unlink()
            raise HTTPException(status_code=422, detail="The Composer project could not be saved") from error
        return {
            "schema": document.schema_name,
            "path": str(target),
            "project": request.project.model_dump(by_alias=True),
            "sourceIds": source_ids,
            "sources": public_sources,
        }

    @router.get("/composer/sources/{source_id}/content")
    def composer_source_content(
        source_id: str,
        app_instance_id: str = Query(alias="appInstanceId", min_length=1, max_length=200),
        principal: RequestPrincipal = principal_dependency,
    ):
        studio(principal, app_instance_id)
        try:
            source, path = composer_sources().get(
                source_id,
                actor_id=principal.actor_user_id,
                installation_id=principal.installation_id,
                app_instance_id=app_instance_id,
            )
        except ComposerError as error:
            return composer_error(error)
        return FileResponse(
            path,
            media_type=source["mediaType"],
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    @router.post("/runs/{run_id}/compose", status_code=202)
    async def execute_composition(
        run_id: str,
        request: ComposerRenderRequest,
        background_tasks: BackgroundTasks,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = runtime_provider()
        repository = studio(principal, app_instance_id)
        run_scope = scope(principal, app_instance_id)
        try:
            run = repository.get_run(run_id, **run_scope)
        except StudioRepositoryError as error:
            return studio_error(error)
        if run["miniAppId"] != COMPOSER_ID or run["status"] != "queued":
            raise HTTPException(status_code=409, detail="Composer Run is not queued")
        source_ids = {clip.source_id for clip in request.project.clips}
        source_ids.update(
            clip.mask_source_id for clip in request.project.clips if clip.mask_source_id
        )
        if not source_ids:
            raise HTTPException(status_code=422, detail="Add at least one clip before exporting")
        resolved: dict[str, tuple[dict[str, Any], Path]] = {}
        try:
            for source_id in source_ids:
                resolved[source_id] = composer_sources().get(
                    source_id,
                    actor_id=principal.actor_user_id,
                    installation_id=principal.installation_id,
                    app_instance_id=app_instance_id,
                )
        except ComposerError as error:
            return composer_error(error)
        for clip in request.project.clips:
            if clip.mask_source_id and not resolved[clip.mask_source_id][0].get("hasImage"):
                raise HTTPException(
                    status_code=422,
                    detail=f"Clip {clip.name!r} mask must be an image",
                )
            source_duration = float(resolved[clip.source_id][0].get("duration") or 0)
            source_end = clip.source_start + clip.duration * clip.speed
            if not resolved[clip.source_id][0].get("hasImage") and source_duration > 0 and source_end > source_duration + 0.1:
                raise HTTPException(
                    status_code=422,
                    detail=f"Clip {clip.name!r} extends beyond its source media",
                )
        video_tasks = None if runtime is None else getattr(runtime, "video_tasks", None)
        workspace = None if runtime is None else getattr(runtime, "workspace", None)
        paths = None if runtime is None else getattr(runtime.config, "paths", None)
        if video_tasks is None or workspace is None or paths is None:
            raise HTTPException(status_code=503, detail="Media Artifact storage is not ready")
        safe_stem = Path(request.output_name or request.project.title).stem.strip()[:180]
        safe_stem = "".join(
            character if character.isalnum() or character in " -_." else "-"
            for character in safe_stem
        ).strip(" .") or "composition"
        output_name = f"{safe_stem}.mp4"
        work_root = paths.artifacts_path / "video-composer-work" / run_id
        destination = work_root / output_name
        repository.update_run(
            run_id, status="running", progress=5, detail="Preparing composition", **run_scope
        )

        async def compose_in_background() -> None:
            stage = "render"
            try:
                repository.update_run(
                    run_id, status="running", progress=15,
                    detail="Rendering video and audio tracks", **run_scope,
                )
                await render_composition(request.project, resolved, destination)
                stage = "workspace_artifact"
                current = repository.get_run(run_id, **run_scope)
                if current["status"] == "cancelled":
                    return
                repository.update_run(
                    run_id, status="running", progress=90,
                    detail="Saving composition Artifact", **run_scope,
                )
                session_id = video_tasks.artifact_session()
                metadata = {
                    "generator": COMPOSER_ID,
                    "schema": request.project.schema_name,
                    "duration": request.project.duration,
                    "trackCount": len(request.project.tracks),
                    "clipCount": len(request.project.clips),
                    "width": request.project.settings.width,
                    "height": request.project.settings.height,
                    "fps": request.project.settings.fps,
                }
                artifact = workspace.import_artifact(
                    session_id, destination, output_name,
                    media_type="video/mp4", metadata=metadata,
                )
                stage = "studio_artifact"
                content_url = (
                    f"/v1/platform/sessions/{session_id}/artifacts/{artifact.id}/download"
                )
                repository.create_artifact(
                    run_id, kind="video", name=artifact.name,
                    media_type=artifact.media_type, preview_url=content_url,
                    download_url=content_url, source_id=artifact.id,
                    metadata={
                        "workspaceSessionId": session_id,
                        "workspaceArtifactId": artifact.id,
                        **metadata,
                    },
                    **run_scope,
                )
                repository.update_run(
                    run_id, status="succeeded", progress=100,
                    detail="Composition rendered", **run_scope,
                )
            except Exception as error:  # task boundary
                code = getattr(error, "code", "composition_failed")
                with suppress(StudioRepositoryError):
                    repository.update_run(
                        run_id, status="failed", progress=100, detail="Composition failed",
                        error={"code": code, "message": f"{stage}: {error}"[:1200]}, **run_scope,
                    )
            finally:
                shutil.rmtree(work_root, ignore_errors=True)
                prune_history(repository, run_scope)

        background_tasks.add_task(compose_in_background)
        return repository.get_run(run_id, **run_scope)

    @router.post("/runs/{run_id}/extract-audio", status_code=202)
    async def execute_audio_extraction(
        run_id: str,
        request: ExtractAudioRequest,
        background_tasks: BackgroundTasks,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = runtime_provider()
        repository = studio(principal, app_instance_id)
        run_scope = scope(principal, app_instance_id)
        try:
            run = repository.get_run(run_id, **run_scope)
        except StudioRepositoryError as error:
            return studio_error(error)
        if run["miniAppId"] != EXTRACT_AUDIO_ID or run["status"] != "queued":
            raise HTTPException(status_code=409, detail="Audio extraction Run is not queued")
        has_handle = bool(request.resource_handle)
        has_native_path = bool(request.source_path)
        if has_handle == has_native_path:
            raise HTTPException(
                status_code=422,
                detail="Provide exactly one Gallery Resource Handle or selected local file path",
            )
        if has_handle:
            try:
                asset, source = gallery().asset_handle_path(
                    request.resource_handle or "",
                    actor_id=principal.actor_user_id,
                    installation_id=principal.installation_id,
                    app_instance_id=app_instance_id,
                    consumer_app_id=APP_ID,
                )
            except GalleryError as error:
                raise HTTPException(
                    status_code=404,
                    detail={"code": error.code, "message": str(error)},
                ) from error
            if asset["kind"] != "video" or not asset["media_type"].startswith("video/"):
                raise HTTPException(status_code=422, detail="A Gallery video Asset is required")
            if run["input"].get("assetId") not in {None, asset["id"]}:
                raise HTTPException(status_code=409, detail="Run input does not match the Resource Handle")
            source_asset_id: str | None = asset["id"]
            source_name = asset["name"]
            source_media_type = asset["media_type"]
            source_kind = "gallery"
        else:
            candidate = Path(request.source_path or "").expanduser()
            if not candidate.is_absolute():
                raise HTTPException(status_code=422, detail="Selected local video path must be absolute")
            try:
                source = candidate.resolve(strict=True)
                source_size = source.stat().st_size
            except (OSError, RuntimeError) as error:
                raise HTTPException(status_code=422, detail="Selected local video is unavailable") from error
            if not source.is_file() or source_size <= 0:
                raise HTTPException(status_code=422, detail="Selected local video is unavailable")
            source_media_type = str(request.media_type or "")
            if not source_media_type.startswith("video/"):
                raise HTTPException(status_code=422, detail="Selected local file must be a video")
            if run["input"].get("sourceKind") not in {None, "local"}:
                raise HTTPException(status_code=409, detail="Run input does not match the local file")
            source_asset_id = None
            source_name = Path(request.source_name or source.name).name or source.name
            source_kind = "local"
        video_tasks = None if runtime is None else getattr(runtime, "video_tasks", None)
        workspace = None if runtime is None else getattr(runtime, "workspace", None)
        paths = None if runtime is None else getattr(runtime.config, "paths", None)
        if video_tasks is None or workspace is None or paths is None:
            raise HTTPException(status_code=503, detail="Media Artifact storage is not ready")
        safe_stem = Path(request.output_name or source_name).stem.strip()[:180]
        safe_stem = "".join(
            character if character.isalnum() or character in " -_." else "-"
            for character in safe_stem
        ).strip(" .") or "extracted-audio"
        output_name = f"{safe_stem}.wav"
        work_root = paths.artifacts_path / "video-studio-audio-work" / run_id
        destination = work_root / output_name
        repository.update_run(
            run_id, status="running", progress=10, detail="Decoding audio track", **run_scope
        )

        async def extract_in_background() -> None:
            try:
                metadata = await asyncio.to_thread(
                    extract_audio_to_wav, source, destination
                )
                current = repository.get_run(run_id, **run_scope)
                if current["status"] == "cancelled":
                    return
                repository.update_run(
                    run_id, status="running", progress=85,
                    detail="Saving audio Artifact", **run_scope,
                )
                session_id = video_tasks.artifact_session()
                artifact = workspace.import_artifact(
                    session_id,
                    destination,
                    output_name,
                    media_type="audio/wav",
                    metadata={
                        "generator": EXTRACT_AUDIO_ID,
                        "sourceKind": source_kind,
                        **({"sourceAssetId": source_asset_id} if source_asset_id else {}),
                        "sourceMediaType": source_media_type,
                        **metadata,
                    },
                )
                content_url = (
                    f"/v1/platform/sessions/{session_id}/artifacts/{artifact.id}/download"
                )
                repository.create_artifact(
                    run_id,
                    kind="audio",
                    name=artifact.name,
                    media_type=artifact.media_type,
                    preview_url=content_url,
                    download_url=content_url,
                    source_id=artifact.id,
                    metadata={
                        "workspaceSessionId": session_id,
                        "workspaceArtifactId": artifact.id,
                        "sourceKind": source_kind,
                        **({"sourceAssetId": source_asset_id} if source_asset_id else {}),
                        **metadata,
                    },
                    **run_scope,
                )
                repository.update_run(
                    run_id, status="succeeded", progress=100,
                    detail="Audio track extracted", **run_scope,
                )
            except Exception as error:  # task boundary
                code = getattr(error, "code", "audio_extraction_failed")
                with suppress(StudioRepositoryError):
                    repository.update_run(
                        run_id, status="failed", progress=100, detail="Extraction failed",
                        error={"code": code, "message": str(error)[:1000]}, **run_scope,
                    )
            finally:
                shutil.rmtree(work_root, ignore_errors=True)
                prune_history(repository, run_scope)

        background_tasks.add_task(extract_in_background)
        return repository.get_run(run_id, **run_scope)

    @router.post("/runs/{run_id}/cancel")
    def cancel_run(
        run_id: str,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        repository = studio(principal, app_instance_id)
        run_scope = scope(principal, app_instance_id)
        try:
            run = repository.get_run(run_id, **run_scope)
            if run["status"] in {"succeeded", "failed", "cancelled", "expired"}:
                return run
            return repository.update_run(
                run_id, status="cancelled", progress=run["progress"],
                detail="Cancelled", **run_scope,
            )
        except StudioRepositoryError as error:
            return studio_error(error)

    @router.get("/providers")
    def providers(_principal=principal_dependency):
        items = []
        for model in list_package_models(runtime_provider()):
            if model.model_type != "video_generation" or is_temporarily_disabled_video_model(model):
                continue
            identity = build_model_identity(
                source="package",
                provider_id=model.inference_provider_key or model.provider_key,
                model_id=model.id,
                display_name=model.display_name,
            )
            items.append(
                {
                    "id": model.id,
                    "displayName": identity["displayName"],
                    "identity": identity,
                    "modelType": model.model_type,
                    "capabilities": list(model.capabilities),
                    "videoCapabilities": effective_video_capabilities(model),
                    "ready": model.checkpoint_ready,
                    "family": model.metadata.get("family"),
                    "precision": model.metadata.get("precision"),
                    "residency": model.metadata.get("residency"),
                }
            )
        return {"items": items}

    @router.post("/drafts", status_code=201)
    async def create_draft(
        draft: Annotated[str, Form()],
        first_frame: Annotated[UploadFile | None, File()] = None,
        last_frame: Annotated[UploadFile | None, File()] = None,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            payload = VideoStudioDraftPayload.model_validate_json(draft)
            uploads = []
            for upload in (first_frame, last_frame):
                if upload is None:
                    uploads.append(None)
                    continue
                data = await upload.read(MAX_FRAME_BYTES + 1)
                uploads.append((upload.filename or "frame", data))
            repository = drafts(principal, app_instance_id)
            record = repository.create(
                actor_id=principal.actor_user_id,
                installation_id=principal.installation_id,
                app_instance_id=app_instance_id,
                action_id=payload.action,
                draft=payload.model_dump(by_alias=True),
                first_frame=uploads[0],
                last_frame=uploads[1],
            )
            return public_draft(record)
        except ValidationError as error:
            raise HTTPException(status_code=422, detail="Video Studio draft is invalid") from error
        except VideoStudioDraftError as error:
            raise HTTPException(
                status_code=error.status_code,
                detail={"code": error.code, "message": str(error)},
            ) from error

    @router.get("/drafts/{draft_id}")
    def get_draft(
        draft_id: str,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        repository = drafts(principal, app_instance_id)
        return public_draft(
            owned_draft(repository, draft_id, principal, app_instance_id)
        )

    @router.get("/drafts/{draft_id}/frames/{which}")
    def get_draft_frame(
        draft_id: str,
        which: Literal["first", "last"],
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        repository = drafts(principal, app_instance_id)
        result = repository.frame_path(
            draft_id,
            which,
            actor_id=principal.actor_user_id,
            installation_id=principal.installation_id,
            app_instance_id=app_instance_id,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Video Studio draft frame not found")
        descriptor, path = result
        return FileResponse(
            path,
            media_type=descriptor["mediaType"],
            filename=descriptor["name"],
            content_disposition_type="inline",
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    @router.delete("/drafts/{draft_id}", status_code=204)
    def delete_draft(
        draft_id: str,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        repository = drafts(principal, app_instance_id)
        if not repository.delete(
            draft_id,
            actor_id=principal.actor_user_id,
            installation_id=principal.installation_id,
            app_instance_id=app_instance_id,
        ):
            raise HTTPException(status_code=404, detail="Video Studio draft not found")
        return Response(status_code=204)

    @router.delete('/tasks/{task_id}', status_code=204)
    def delete_task(task_id: str, app_instance_id: str = Header(alias='X-AI2Apps-App-Instance'), principal: RequestPrincipal = principal_dependency):
        studio(principal, app_instance_id)
        try:
            runtime_provider().video_tasks.delete(task_id, actor_id=principal.actor_user_id)
        except VideoGenerationError as error:
            raise HTTPException(status_code=error.status_code, detail=str(error)) from error
        return Response(status_code=204)

    @router.delete('/runs/{run_id}', status_code=204)
    def delete_run(run_id: str, app_instance_id: str = Header(alias='X-AI2Apps-App-Instance'), principal: RequestPrincipal = principal_dependency):
        try:
            studio(principal, app_instance_id).delete_run(run_id, runtime_provider().workspace, **scope(principal, app_instance_id))
        except StudioRepositoryError as error:
            return studio_error(error)
        return Response(status_code=204)

    @router.post("/tasks/{task_id}/retry", status_code=202)
    async def retry_task(
        task_id: str,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = runtime_provider()
        manager = None if runtime is None else getattr(runtime, "video_tasks", None)
        extension_manager = (
            None if runtime is None else getattr(runtime, "extension_manager", None)
        )
        if manager is None or extension_manager is None:
            raise HTTPException(status_code=503, detail="Video Studio tasks are not ready")
        authorize_app_instance(runtime, principal, app_instance_id)
        entry = extension_manager.instance_entry(app_instance_id, principal=principal)
        if entry.get("app_key") != APP_ID:
            raise HTTPException(status_code=404, detail="Video Studio task not found")
        try:
            return await manager.retry(task_id, actor_id=principal.actor_user_id)
        except VideoGenerationError as error:
            raise HTTPException(
                status_code=error.status_code,
                detail={"code": error.code, "message": str(error)},
            ) from error

    return router
