"""Model discovery surface for the built-in Video Studio App."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import PrincipalProvider, resolve_request_principal
from ai2apps.api.ownership import authorize_app_instance
from ai2apps.identity import RequestPrincipal
from ai2apps.model_providers import list_package_models
from ai2apps.video import (
    MAX_FRAME_BYTES,
    VideoStudioDraftError,
    VideoStudioDraftRepository,
)
from ai2apps.video_policy import (
    effective_video_capabilities,
    is_temporarily_disabled_video_model,
)

APP_ID = "ai2apps.video-studio"


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

    @router.get("/providers")
    def providers(_principal=principal_dependency):
        items = []
        for model in list_package_models(runtime_provider()):
            if model.model_type != "video_generation" or is_temporarily_disabled_video_model(model):
                continue
            items.append(
                {
                    "id": model.id,
                    "displayName": model.display_name,
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

    return router
