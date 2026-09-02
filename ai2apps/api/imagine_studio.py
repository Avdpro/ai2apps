"""Durable output history surface for the built-in Imagine Studio App."""

from __future__ import annotations

import json
from typing import Annotated
from urllib.parse import quote

from fastapi import (
    APIRouter,
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
from ai2apps.identity import RequestPrincipal
from ai2apps.images import ImagineStudioHistoryError, ImagineStudioHistoryRepository
from ai2apps.images.history import MAX_HISTORY_ITEMS, MAX_IMAGE_BYTES

APP_ID = "ai2apps.imagine-studio"


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


def create_imagine_studio_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(prefix="/imagine-studio", tags=["platform-imagine-studio"])
    principal_dependency = Depends(principal_provider)

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

    def public(record: dict, app_instance_id: str) -> dict:
        return record | {"contentUrl": f"/v1/platform/imagine-studio/results/{record['id']}/content?appInstanceId={quote(app_instance_id, safe='')}"}

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
            record = history(principal, app_instance_id).create(
                actor_id=principal.actor_user_id,
                installation_id=principal.installation_id,
                app_instance_id=app_instance_id,
                metadata=payload.model_dump(by_alias=True),
                data=data,
            )
            return public(record, app_instance_id)
        except (json.JSONDecodeError, ValidationError) as error:
            raise HTTPException(status_code=422, detail="Imagine Studio result metadata is invalid") from error
        except ImagineStudioHistoryError as error:
            raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": str(error)}) from error

    @router.get("/results/{result_id}/content")
    def result_content(
        result_id: str,
        app_instance_id: str = Query(alias="appInstanceId", min_length=1, max_length=200),
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = history(principal, app_instance_id).content_path(
            result_id, actor_id=principal.actor_user_id, installation_id=principal.installation_id, app_instance_id=app_instance_id
        )
        if selected is None:
            raise HTTPException(status_code=404, detail="Imagine Studio result not found")
        record, path = selected
        return FileResponse(path, media_type=record["mediaType"], filename=record["filename"], content_disposition_type="inline", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})

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
