"""Local-first APIs for the built-in Voice Studio App."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Literal

from fastapi import Request, APIRouter, Depends, Header, HTTPException, Query, UploadFile, File
from fastapi.responses import JSONResponse, Response, FileResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ai2apps.api.errors import platform_error_response, repository_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import PrincipalProvider, resolve_request_principal
from ai2apps.api.ownership import authorize_app_instance
from ai2apps.core import RepositoryError, ResourceNotFoundError, utc_now_text
from ai2apps.gallery import GalleryRepository
from ai2apps.readaloud.source_analysis import SourceAnalysisRequest, SourceApplyRequest, analysis_messages, parse_completion, validate_proposal, dialogue_issues
from ai2apps.readaloud.speech import invoke_speech, speech_verifier
from ai2apps.readaloud.materials import VoiceMaterials
from ai2apps.readaloud.training import requirements as training_requirements, prepare as prepare_training, combined_reference
from ai2apps.identity import RequestPrincipal
from ai2apps.model_identity import build_model_identity
from ai2apps.model_providers import list_package_models
from ai2apps.readaloud import (
    ReadAloudRenderError,
    ReadAloudRepository,
    ReadAloudTaskManager,
)
from ai2apps.studio import (
    StudioMiniAppRegistry,
    StudioRepository,
    StudioRepositoryError,
)

ProjectPurpose = Literal["private", "noncommercial", "commercial"]
SourceRights = Literal["user_owned", "licensed", "public_domain", "personal_use"]
VoiceSource = Literal["synthetic_designed", "self_voice", "authorized_person"]
ReviewStatus = Literal["suggested", "needs_review", "approved"]
VOICE_RIGHTS_POLICY_VERSION = "ai2apps.voice-rights/v1"
READALOUD_STUDIO_ID = "ai2apps.readaloud"
READALOUD_MINI_APPS: tuple[dict[str, Any], ...] = (
    {"schema": "ai2apps.mini-app/v1", "id": "ai2apps.audio.quick-read", "version": "1.0.0", "kind": "clip", "mode": "quick", "icon": "volume-2", "title_key": "readaloud.mini_app.quick.name", "summary_key": "readaloud.mini_app.quick.summary", "description_key": "readaloud.mini_app.quick.description", "entry": {"kind": "host-adapter", "adapter": "quick-read"}, "ui": {"minimum_width": 520, "drop_targets": [{"id": "script", "accepts": ["text"]}]}, "placements": [{"studio": READALOUD_STUDIO_ID, "category": "quick", "order": 10}], "inputs": [{"id": "script", "kind": "text", "required": True}], "outputs": [{"id": "speech", "kind": "audio", "final": True}], "executor": {"pipelines": ["ai2apps.pipeline.speech-generation"]}, "requirements": {"capabilities": ["audio.speech_generation"]}},
    {"schema": "ai2apps.mini-app/v1", "id": "ai2apps.audio.audiobook", "version": "1.0.0", "kind": "project", "mode": "audiobook", "icon": "book-headphones", "title_key": "readaloud.mini_app.audiobook.name", "summary_key": "readaloud.mini_app.audiobook.summary", "description_key": "readaloud.mini_app.audiobook.description", "entry": {"kind": "host-adapter", "adapter": "audiobook"}, "ui": {"minimum_width": 520, "drop_targets": [{"id": "book", "accepts": ["text"]}]}, "placements": [{"studio": READALOUD_STUDIO_ID, "category": "projects", "order": 30}], "inputs": [{"id": "book", "kind": "text", "required": True}], "outputs": [{"id": "chapters", "kind": "audio", "final": True}], "executor": {"pipelines": ["ai2apps.pipeline.speech-generation"]}, "requirements": {"capabilities": ["audio.speech_generation"]}},
    {"schema": "ai2apps.mini-app/v1", "id": "ai2apps.audio.ensemble-drama", "version": "1.0.0", "kind": "project", "mode": "drama", "icon": "users-round", "title_key": "readaloud.mini_app.drama.name", "summary_key": "readaloud.mini_app.drama.summary", "description_key": "readaloud.mini_app.drama.description", "entry": {"kind": "host-adapter", "adapter": "ensemble-drama"}, "ui": {"minimum_width": 520, "drop_targets": [{"id": "script", "accepts": ["text", "project"]}]}, "placements": [{"studio": READALOUD_STUDIO_ID, "category": "projects", "order": 30}], "inputs": [{"id": "script", "kind": "project", "required": True}], "outputs": [{"id": "dialogue", "kind": "audio", "final": True}], "executor": {"pipelines": ["ai2apps.pipeline.speech-generation"]}, "requirements": {"capabilities": ["audio.speech_generation"]}},
    {"schema": "ai2apps.mini-app/v1", "id": "ai2apps.audio.voice-design", "version": "1.0.0", "kind": "project", "mode": "voice", "icon": "users-round", "title_key": "readaloud.mini_app.voice.name", "summary_key": "readaloud.mini_app.voice.summary", "description_key": "readaloud.mini_app.voice.description", "entry": {"kind": "host-adapter", "adapter": "voice-design"}, "ui": {"minimum_width": 520, "drop_targets": [{"id": "reference", "accepts": ["audio", "voice-profile"]}]}, "placements": [{"studio": READALOUD_STUDIO_ID, "category": "voices", "order": 20}], "inputs": [{"id": "voice_spec", "kind": "project", "required": True}], "outputs": [{"id": "voice_profile", "kind": "voice-profile", "final": True}], "executor": {"pipelines": ["ai2apps.pipeline.voice-design"]}, "requirements": {"capabilities": ["audio.voice_clone"]}},
    {"schema": "ai2apps.mini-app/v1", "id": "ai2apps.audio.character-training", "version": "1.0.0", "kind": "project", "mode": "training", "icon": "mic-2", "title_key": "readaloud.mini_app.training.name", "summary_key": "readaloud.mini_app.training.summary", "description_key": "readaloud.mini_app.training.description", "entry": {"kind": "host-adapter", "adapter": "character-training"}, "ui": {"minimum_width": 520, "drop_targets": [{"id": "reference_audio", "accepts": ["audio"]}]}, "placements": [{"studio": READALOUD_STUDIO_ID, "category": "voices", "order": 50}], "inputs": [{"id": "reference_audio", "kind": "audio", "required": True}], "outputs": [{"id": "training_material", "kind": "voice-profile", "final": True}], "executor": {"pipelines": ["ai2apps.pipeline.voice-training"]}, "requirements": {"capabilities": ["audio.voice_clone"]}},
)
READALOUD_MINI_APP_BY_ID = {item["id"]: item for item in READALOUD_MINI_APPS}
# Keep the legacy ID valid for saved drafts, but expose one character entry.
READALOUD_MINI_APPS = tuple(sorted((item for item in READALOUD_MINI_APPS if item["id"] not in {"ai2apps.audio.character-training", "ai2apps.audio.ensemble-drama"}), key=lambda item: item["placements"][0]["order"]))


class QuickReadRequest(BaseModel):
    speed: float = Field(default=1.0, ge=0.5, le=2.0, allow_inf_nan=False)
    asr_verification: bool = False
    asr_model_id: str | None = Field(default=None, max_length=255)
    voice_profile_id: str | None = Field(default=None, max_length=255)
    text: str = Field(min_length=1, max_length=10_000)
    model_id: str = Field(min_length=1, max_length=255)
    voice: str | None = Field(default=None, max_length=255)


class ProjectCreateRequest(BaseModel):
    mini_app_id: Literal["ai2apps.audio.quick-read", "ai2apps.audio.audiobook", "ai2apps.audio.ensemble-drama"] = "ai2apps.audio.audiobook"
    title: str = Field(min_length=1, max_length=160)
    purpose: ProjectPurpose = "private"
    source_rights: SourceRights = "user_owned"
    source_text: str = Field(default="", max_length=200_000)


class ProjectUpdateRequest(BaseModel):
    asr_verification: bool | None = None
    asr_model_id: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    purpose: ProjectPurpose | None = None
    source_rights: SourceRights | None = None
    source_text: str | None = Field(default=None, max_length=200_000)
    status: Literal["draft", "ready", "archived"] | None = None


class VoiceProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source_type: VoiceSource
    model_id: str | None = Field(default=None, max_length=255)
    provider_voice_id: str | None = Field(default=None, max_length=255)
    reference_transcript: str = Field(default="", max_length=20_000)
    reference_asset_id: str | None = Field(default=None, max_length=255)
    rights_scope: dict[str, Any] = Field(default_factory=dict)


class DesignRequest(BaseModel):
    emotion: str = Field(default='neutral', min_length=1, max_length=80)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    profile_id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    model_id: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=2000)
    text: str = Field(min_length=1, max_length=2000)


class DesignConversionRequest(BaseModel):
    model_id: str = Field(min_length=1, max_length=255)


class TrainingSample(BaseModel):
    asset_id: str = Field(min_length=1, max_length=255)
    transcript: str = Field(default="", max_length=20000)
    confirmed: bool = False
    selected: bool = True


class TrainingRequest(VoiceProfileCreateRequest):
    emotion: str = Field(default='neutral', min_length=1, max_length=80)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    source_type: Literal["self_voice", "authorized_person", "synthetic_designed"]
    profile_id: str | None = Field(default=None, max_length=255)
    model_revision: str | None = Field(default=None, max_length=255)
    model_id: str = Field(min_length=1, max_length=255)
    samples: list[TrainingSample] = Field(min_length=1, max_length=50)
    preview_text: str = Field(default="Hello. This is a preview of my character voice.", min_length=1, max_length=2000)


class CharacterCreateRequest(BaseModel):
    role: Literal['auto', 'narrator', 'female_lead', 'male_lead', 'default_male', 'default_female'] = 'auto'
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2_000)
    voice_profile_id: str | None = None


class SegmentCreateRequest(BaseModel):
    speaker_id: str | None = None
    text: str = Field(min_length=1, max_length=10_000)
    emotion: str = Field(default="neutral", min_length=1, max_length=80)
    emotion_strength: float = Field(default=1.0, ge=0.0, le=2.0)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pause_after_ms: int = Field(default=300, ge=0, le=10_000)


class SegmentUpdateRequest(BaseModel):
    speaker_id: str | None = None
    text: str | None = Field(default=None, min_length=1, max_length=10_000)
    emotion: str | None = Field(default=None, min_length=1, max_length=80)
    emotion_strength: float | None = Field(default=None, ge=0.0, le=2.0)
    speed: float | None = Field(default=None, ge=0.5, le=2.0)
    pause_after_ms: int | None = Field(default=None, ge=0, le=10_000)
    review_status: ReviewStatus | None = None


class RenderCreateRequest(BaseModel):
    model_id: str = Field(min_length=1, max_length=255)
    segment_ids: list[str] | None = Field(default=None, max_length=10_000)
    mini_app_id: str = Field(
        default="ai2apps.audio.audiobook", min_length=1, max_length=255
    )
    placement: str = Field(default=READALOUD_STUDIO_ID, min_length=1, max_length=255)


class StudioDraftRequest(BaseModel):
    draft: dict[str, Any] = Field(default_factory=dict)


class StudioRunCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mini_app_id: str = Field(alias="miniAppId", min_length=3, max_length=255)
    project_id: str = Field(alias="projectId", min_length=1, max_length=255)
    model_id: str = Field(alias="modelId", min_length=1, max_length=255)
    segment_ids: list[str] | None = Field(default=None, alias="segmentIds")
    title: str = Field(default="Voice Studio", min_length=1, max_length=160)
    retry_of: str | None = Field(default=None, alias="retryOf", max_length=80)
    merge_output: bool = Field(default=False, alias="mergeOutput")


def _camel(value: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "owner_user_id": "ownerUserId",
        "source_rights": "sourceRights",
        "source_text": "sourceText",
        "asr_verification": "asrVerification",
        "asr_model_id": "asrModelId",
        "created_at": "createdAt",
        "updated_at": "updatedAt",
        "character_count": "characterCount",
        "segment_count": "segmentCount",
        "source_type": "sourceType",
        "model_id": "modelId",
        "provider_voice_id": "providerVoiceId",
        "reference_transcript": "referenceTranscript",
        "reference_asset_id": "referenceAssetId",
        "rights_scope": "rightsScope",
        "project_id": "projectId",
        "voice_profile_id": "voiceProfileId",
        "sort_order": "sortOrder",
        "speaker_id": "speakerId",
        "emotion_strength": "emotionStrength",
        "pause_after_ms": "pauseAfterMs",
        "review_status": "reviewStatus",
        "project_revision": "projectRevision",
        "total_segments": "totalSegments",
        "completed_segments": "completedSegments",
        "cancel_requested_at": "cancelRequestedAt",
        "started_at": "startedAt",
        "completed_at": "completedAt",
        "segment_id": "segmentId",
        "output_path": "outputPath",
        "artifact_id": "artifactId",
        "artifact_session_id": "artifactSessionId",
        "mini_app_id": "miniAppId",
        "model_revision": "modelRevision",
        "download_url": "downloadUrl",
        "media_type": "mediaType",
        "session_id": "sessionId",
        "resource_handle": "resourceHandle",
        "asset_id": "assetId",
    }
    result = {mapping.get(key, key): item for key, item in value.items()}
    if isinstance(result.get("characters"), list):
        result["characters"] = [_camel(item) for item in result["characters"]]
    if isinstance(result.get("segments"), list):
        result["segments"] = [_camel(item) for item in result["segments"]]
    if isinstance(result.get("artifact"), dict):
        result["artifact"] = _camel(result["artifact"])
    return result


def _preview_expression(model, emotion, speed):
    tts = (getattr(model, 'audio_capabilities', None) or {}).get('tts', {})
    result = {}
    speed_caps = tts.get('speed', {})
    if speed_caps.get('mode', 'unsupported') != 'unsupported':
        result['speed'] = max(float(speed_caps.get('minimum', 0.5)), min(float(speed_caps.get('maximum', 2)), speed))
    emotion_caps = tts.get('emotion', {})
    if emotion != 'neutral' and emotion_caps.get('mode', 'unsupported') != 'unsupported' and emotion in emotion_caps.get('values', []):
        result['style'] = {'emotion': emotion, 'emotion_strength': 1.0}
    return result


def _voice_rights_scope(
    request: VoiceProfileCreateRequest,
    principal: RequestPrincipal,
) -> dict[str, Any]:
    scope = dict(request.rights_scope)
    if request.source_type != "synthetic_designed":
        required = (
            "consent_confirmed",
            "usage_rights_confirmed",
            "prohibited_impersonation_acknowledged",
        )
        missing = [field for field in required if scope.get(field) is not True]
        if missing:
            raise ValueError(
                "Real-person voice profiles require consent, usage-rights, "
                "and anti-impersonation acknowledgements."
            )
    scope.update(
        {
            "policy_version": VOICE_RIGHTS_POLICY_VERSION,
            "accepted_by_user_id": principal.actor_user_id,
            "accepted_at": utc_now_text(),
        }
    )
    return scope


def create_readaloud_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(prefix="/readaloud", tags=["platform-readaloud"])
    principal_dependency = Depends(principal_provider)

    def repository() -> ReadAloudRepository | JSONResponse:
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        events = None if runtime is None else getattr(runtime, "events", None)
        if database is None:
            return platform_error_response(
                status_code=503,
                code="platform_not_ready",
                message="Voice Studio persistence is not ready.",
                retryable=True,
            )
        return ReadAloudRepository(database, events)

    def materials():
        runtime = runtime_provider()
        return VoiceMaterials(runtime.database, runtime.config.paths.artifacts_path)

    @router.post('/training/materials', status_code=201)
    async def upload_reference(file: UploadFile = File(...), principal: RequestPrincipal = principal_dependency):
        content = await file.read(64 * 1024 * 1024 + 1)
        try:
            return {'asset': materials().save(principal.actor_user_id, content, file.filename or 'reference.wav', file.content_type or 'audio/wav')}
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        finally:
            await file.close()

    @router.post('/training/materials/from-gallery/{asset_id}', status_code=201)
    def copy_gallery_reference(asset_id: str, principal: RequestPrincipal = principal_dependency):
        return guarded(lambda: {'asset': materials().import_gallery(principal.actor_user_id, asset_id)})

    @router.get('/training/materials/{asset_id}/content')
    def reference_content(asset_id: str, principal: RequestPrincipal = principal_dependency):
        try:
            store = materials()
            store.import_gallery(principal.actor_user_id, asset_id)
            asset, path = store.asset_path(principal.actor_user_id, asset_id)
            return FileResponse(path, media_type=asset['media_type'])
        except RepositoryError as error:
            return repository_error_response(error)

    def render_manager() -> ReadAloudTaskManager | JSONResponse:
        runtime = runtime_provider()
        manager = None if runtime is None else getattr(runtime, "readaloud_tasks", None)
        if manager is None:
            return platform_error_response(
                status_code=503,
                code="platform_not_ready",
                message="Voice Studio render queue is not ready.",
                retryable=True,
            )
        return manager

    def studio(principal: RequestPrincipal, app_instance_id: str) -> StudioRepository:
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        extension_manager = (
            None if runtime is None else getattr(runtime, "extension_manager", None)
        )
        if database is None or extension_manager is None:
            raise HTTPException(
                status_code=503, detail="Voice Studio storage is not ready"
            )
        authorize_app_instance(runtime, principal, app_instance_id)
        entry = extension_manager.instance_entry(app_instance_id, principal=principal)
        if entry.get("app_key") != READALOUD_STUDIO_ID:
            raise HTTPException(status_code=404, detail="Voice Studio was not found")
        return StudioRepository(database)

    def scoped_kwargs(
        principal: RequestPrincipal, app_instance_id: str
    ) -> dict[str, str]:
        return {
            "actor_id": principal.actor_user_id,
            "installation_id": principal.installation_id,
            "app_instance_id": app_instance_id,
            "studio_id": READALOUD_STUDIO_ID,
        }

    def studio_error(error: StudioRepositoryError):
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": str(error)},
        ) from error

    def guarded(call):
        try:
            return call()
        except RepositoryError as error:
            return repository_error_response(error)
        except ValueError as error:
            return platform_error_response(
                status_code=422,
                code="readaloud_request_invalid",
                message=str(error),
            )

    @router.get("/mini-apps")
    def mini_apps(principal: RequestPrincipal = principal_dependency):
        runtime = runtime_provider()
        manager = None if runtime is None else getattr(runtime, "extension_manager", None)
        if manager is None:
            return {
                "schema": "ai2apps.studio-mini-app-list/v1",
                "studioId": READALOUD_STUDIO_ID,
                "items": list(READALOUD_MINI_APPS),
            }
        return StudioMiniAppRegistry(manager).list(
            READALOUD_STUDIO_ID,
            builtins=READALOUD_MINI_APPS,
            principal=principal,
        )

    @router.get("/drafts/{mini_app_id:path}")
    def get_studio_draft(
        mini_app_id: str,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        if mini_app_id not in READALOUD_MINI_APP_BY_ID:
            raise HTTPException(status_code=404, detail="Voice Studio Mini-App was not found")
        return studio(principal, app_instance_id).get_draft(
            mini_app_id=mini_app_id,
            **scoped_kwargs(principal, app_instance_id),
        ) or {"miniAppId": mini_app_id, "draft": {}}

    @router.put("/drafts/{mini_app_id:path}")
    def save_studio_draft(
        mini_app_id: str,
        request: StudioDraftRequest,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        if mini_app_id not in READALOUD_MINI_APP_BY_ID:
            raise HTTPException(status_code=404, detail="Voice Studio Mini-App was not found")
        if len(json.dumps(request.draft, ensure_ascii=False).encode("utf-8")) > 128 * 1024:
            raise HTTPException(status_code=413, detail="Voice Studio Mini-App draft is too large")
        return studio(principal, app_instance_id).save_draft(
            mini_app_id=mini_app_id,
            draft=request.draft,
            **scoped_kwargs(principal, app_instance_id),
        )

    @router.get("/runs")
    def list_studio_runs(
        limit: int = Query(default=50, ge=1, le=100),
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        manager = render_manager()
        if not isinstance(manager, JSONResponse):
            manager.prune_studio_history(scoped_kwargs(principal, app_instance_id))
        return {
            "items": list(
                studio(principal, app_instance_id).list_runs(
                    limit=limit, **scoped_kwargs(principal, app_instance_id)
                )
            )
        }

    @router.delete('/runs/{run_id}', status_code=204)
    def delete_studio_run(run_id: str, app_instance_id: str = Header(alias='X-AI2Apps-App-Instance'), principal: RequestPrincipal = principal_dependency):
        selected = studio(principal,app_instance_id)
        scope = scoped_kwargs(principal,app_instance_id)
        try:
            run = selected.get_run(run_id, **scope)
            if run['status'] not in {'draft','succeeded','failed','cancelled','expired'}:
                raise HTTPException(status_code=409,detail='Stop the task before deleting it')
            manager = render_manager()
            if isinstance(manager,JSONResponse): return manager
            try:
                manager.get(run_id,owner_user_id=principal.actor_user_id)
            except RepositoryError:
                pass
            else:
                manager.delete(run_id,owner_user_id=principal.actor_user_id)
            selected.delete_run(run_id, **scope)
        except StudioRepositoryError as error:
            return studio_error(error)
        except ReadAloudRenderError as error:
            raise HTTPException(status_code=error.status_code,detail=str(error)) from error
        return Response(status_code=204)

    @router.get("/runs/{run_id}")
    def get_studio_run(
        run_id: str,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return studio(principal, app_instance_id).get_run(
                run_id, **scoped_kwargs(principal, app_instance_id)
            )
        except StudioRepositoryError as error:
            return studio_error(error)

    @router.post("/runs", status_code=202)
    async def create_studio_run(
        request: StudioRunCreateRequest,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        definition = READALOUD_MINI_APP_BY_ID.get(request.mini_app_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Voice Studio Mini-App was not found")
        selected_studio = studio(principal, app_instance_id)
        scope = scoped_kwargs(principal, app_instance_id)
        try:
            run = selected_studio.create_run(
                mini_app_id=request.mini_app_id,
                mini_app_version=definition["version"],
                placement=READALOUD_STUDIO_ID,
                title=request.title,
                input_data={
                    "projectId": request.project_id,
                    "modelId": request.model_id,
                    "segmentIds": request.segment_ids,
                    "mergeOutput": request.merge_output,
                },
                retry_of=request.retry_of,
                step_label="Render audio",
                **scope,
            )
            manager = render_manager()
            if isinstance(manager, JSONResponse):
                raise ReadAloudRenderError(
                    "platform_not_ready", "Voice Studio render queue is not ready", status_code=503
                )
            await manager.create(
                owner_user_id=principal.actor_user_id,
                project_id=request.project_id,
                model_id=request.model_id,
                segment_ids=request.segment_ids,
                mini_app_id=request.mini_app_id,
                placement=READALOUD_STUDIO_ID,
                run_id=run["id"],
                merge_output=request.merge_output,
            )
            return selected_studio.get_run(run["id"], **scope)
        except StudioRepositoryError as error:
            return studio_error(error)
        except (RepositoryError, ReadAloudRenderError) as error:
            if "run" in locals():
                selected_studio.update_run(
                    run["id"],
                    status="failed",
                    progress=0,
                    detail=str(error),
                    error={"code": getattr(error, "code", "render_failed"), "message": str(error)},
                    **scope,
                )
            if isinstance(error, RepositoryError):
                return repository_error_response(error)
            return platform_error_response(
                status_code=error.status_code,
                code=error.code,
                message=str(error),
                retryable=error.status_code >= 500,
            )

    @router.post("/runs/{run_id}/cancel")
    async def cancel_studio_run(
        run_id: str,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        selected_studio = studio(principal, app_instance_id)
        try:
            selected_studio.get_run(
                run_id, **scoped_kwargs(principal, app_instance_id)
            )
            manager = render_manager()
            if isinstance(manager, JSONResponse):
                return manager
            await manager.cancel(run_id, owner_user_id=principal.actor_user_id)
            return selected_studio.get_run(
                run_id, **scoped_kwargs(principal, app_instance_id)
            )
        except StudioRepositoryError as error:
            return studio_error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    def reference_audio_asset(
        asset_id: str | None,
        principal: RequestPrincipal,
    ) -> str | None:
        if not asset_id:
            return None
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        config = None if runtime is None else getattr(runtime, "config", None)
        paths = None if config is None else getattr(config, "paths", None)
        if database is None or paths is None:
            raise ValueError("Gallery persistence is not ready.")
        asset = materials().import_gallery(principal.actor_user_id, asset_id)
        if not str(asset.get("media_type") or "").startswith("audio/"):
            raise ValueError("Voice training reference must be an audio asset.")
        return asset_id

    @router.get("/outputs")
    def studio_outputs(principal: RequestPrincipal = principal_dependency):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        return {"items": manager.output_history(principal.actor_user_id)}

    @router.get("/separation/history")
    def separation_history(principal: RequestPrincipal = principal_dependency):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        return {"items": manager.quick_history(principal.actor_user_id, mini_app_id="ai2apps.media-voice.source-separation")}

    @router.get("/quick-read/history")
    def quick_read_history(principal: RequestPrincipal = principal_dependency):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return {"items": manager.quick_history(principal.actor_user_id)}
        except (RepositoryError, ReadAloudRenderError) as error:
            raise HTTPException(status_code=503, detail="Could not load audio history") from error

    @router.post("/quick-read")
    async def quick_read(
        request: QuickReadRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        text = request.text.strip()
        if not text:
            raise HTTPException(status_code=422, detail="Enter text to read")
        runtime = runtime_provider()
        invocations = getattr(runtime, "model_invocations", None)
        if invocations is None:
            raise HTTPException(status_code=503, detail="Speech service is not ready")
        profile = None
        if request.voice_profile_id:
            try:
                profile = repository().get_voice_profile(principal.actor_user_id, request.voice_profile_id)
            except RepositoryError as error:
                raise HTTPException(status_code=404, detail="Character not found") from error
        model = invocations.model(profile['model_id'] if profile else request.model_id)
        if model is None or model.model_type != "audio_tts":
            raise HTTPException(status_code=422, detail="Select a speech model")
        if not model.checkpoint_ready:
            raise HTTPException(status_code=503, detail="Speech model is not ready")
        named = (model.audio_capabilities or {}).get("tts", {}).get("named_voices", {})
        voices = named.get("voices", [])
        voice = None if profile else request.voice or (voices[0] if voices else None)
        if not profile and request.voice and request.voice not in voices:
            raise HTTPException(status_code=422, detail="Select an actor supported by this model")
        payload = {"model": model.id, "input": text, "response_format": "wav"}
        speed_caps = (model.audio_capabilities or {}).get('tts', {}).get('speed', {})
        native_speed = (speed_caps.get('mode') == 'native'
                        and float(speed_caps.get('minimum', 0.5)) <= request.speed <= float(speed_caps.get('maximum', 2.0)))
        if native_speed:
            payload['speed'] = request.speed
        if voice:
            payload["voice"] = voice
        request_id = f"quick-read-{uuid.uuid4().hex}"
        options = dict(request_id=request_id, context=invocations.context_for_actor(
            principal.actor_user_id, session_id=request_id, consumer_app_id=READALOUD_STUDIO_ID))
        warnings = []
        verifier = None
        if request.asr_verification:
            asr_model = next((item for item in list_package_models(runtime)
                              if item.model_type == 'audio_stt' and item.checkpoint_ready
                              and (not request.asr_model_id or item.id == request.asr_model_id)), None)
            if asr_model is None:
                warnings.append('所选 ASR 模型不可用，本次未校验朗读内容；请重新选择或安装语音识别模型。' if request.asr_model_id else '未找到可用的 ASR 模型，本次未校验朗读内容；请安装语音识别模型后重试。')
            else:
                verifier = speech_verifier(invocations.invoke_foreground_multipart, asr_model.id,
                                           request_id=request_id, context=options['context'])
        options.update(verifier=verifier, warnings=warnings)
        training = (profile or {}).get('training') or {}
        if training.get('samples'):
            try:
                spec, samples, files = await asyncio.to_thread(prepare_training, model, training['samples'], materials(), principal.actor_user_id, for_execution=True)
                if not spec['executable']:
                    raise ValueError('Character reference model is not executable')
                if training.get('model_revision') is not None and training['model_revision'] != spec['revision']:
                    raise ValueError('Character model changed; rebind and preview the character first')
                reference_audio, reference_text = combined_reference(samples, files)
            except (ValueError, RepositoryError, ResourceNotFoundError) as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            if reference_text:
                payload['ref_text'] = reference_text
            response = await invoke_speech(invocations.invoke_foreground_multipart, model.id, 'audio_speech', data=payload,
                files={'reference_audio': ('reference.wav', reference_audio, 'audio/wav')}, **options)
        else:
            description = training.get('design', {}).get('description')
            if profile and not description:
                raise HTTPException(status_code=422, detail="Character has no usable voice configuration")
            if description:
                payload['instructions'] = description
            response = await invoke_speech(invocations.invoke_foreground_json, model.id, 'audio_speech', payload, **options)
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail="Speech generation failed; please try again")
        content = bytes(response.body)
        if not content or len(content) > 64 * 1024 * 1024:
            raise HTTPException(status_code=502, detail="Speech output is empty or too large")
        if not native_speed and request.speed != 1.0:
            from ai2apps.audio_codecs import change_speech_tempo
            try:
                content = await asyncio.to_thread(change_speech_tempo, content, request.speed)
            except Exception as error:
                raise HTTPException(status_code=502, detail="Could not adjust speech speed") from error
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            download_url = manager.save_quick_audio(principal.actor_user_id, content, title=text[:80], model_label=getattr(model, "display_name", model.id), voice=profile["name"] if profile else voice or "", warnings=warnings)
        except (RepositoryError, ReadAloudRenderError) as error:
            raise HTTPException(status_code=503, detail="Could not save generated audio") from error
        return Response(content, media_type="audio/wav", headers={
            "X-AI2Apps-Download-URL": download_url,
            "Cache-Control": "no-store",
            "Content-Disposition": 'attachment; filename="quick-read.wav"',
        })

    @router.get("/providers")
    def providers(principal: RequestPrincipal = principal_dependency):
        del principal
        runtime = runtime_provider()
        installed = []
        for model in list_package_models(runtime):
            if model.model_type not in {"audio_tts", "audio_stt", "audio_processing"}:
                continue
            identity = build_model_identity(
                source="package",
                provider_id=model.inference_provider_key or model.provider_key,
                model_id=model.id,
                display_name=model.display_name,
            )
            installed.append(
                {
                    "id": model.id,
                    "displayName": identity["displayName"],
                    "identity": identity,
                    "modelType": model.model_type,
                    "capabilities": list(model.capabilities),
                    "audioCapabilities": dict(model.audio_capabilities or {}),
                    "trainingRequirements": training_requirements(model),
                    "ready": model.checkpoint_ready,
                    "family": model.metadata.get("family"),
                }
            )
        return {
            "strategy": {
                "ideal": "ai2apps.model.fish-s2-pro/bf16",
                "fallbacks": [
                    "ai2apps.model.cosyvoice3-0.5b/4bit",
                    "ai2apps.model.cosyvoice3-0.5b/8bit",
                    "ai2apps.model.qwen3-tts-1.7b/custom-voice-8bit",
                ],
                "cloudApiEnabled": False,
            },
            "items": installed,
        }

    @router.get("/projects")
    def list_projects(principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return {"items": [_camel(item) for item in selected.list_projects(principal.actor_user_id)]}

    @router.post("/projects", status_code=201)
    def create_project(
        request: ProjectCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        title = request.title.strip()
        if not title:
            return platform_error_response(
                status_code=422,
                code="readaloud_request_invalid",
                message="Project title must contain visible characters.",
            )
        return guarded(
            lambda: _camel(
                selected.create_project(
                    principal.actor_user_id,
                    title=title,
                    purpose=request.purpose,
                    source_rights=request.source_rights,
                    source_text=request.source_text,
                    mini_app_id=request.mini_app_id,
                )
            )
        )

    @router.get("/projects/{project_id}")
    def get_project(
        project_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(lambda: _camel(selected.get_project(principal.actor_user_id, project_id)))

    @router.patch("/projects/{project_id}")
    def update_project(
        project_id: str,
        request: ProjectUpdateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(
            lambda: _camel(
                selected.update_project(
                    principal.actor_user_id,
                    project_id,
                    request.model_dump(exclude_none=True),
                )
            )
        )

    def design_model(model_id):
        invocations = getattr(runtime_provider(), 'model_invocations', None)
        model = invocations.model(model_id) if invocations else None
        if model is None or model.model_type != 'audio_tts' or 'voice_design' not in (model.capabilities or []):
            raise HTTPException(status_code=422, detail='Select a Voice Design model')
        return model

    def save_design(request, principal):
        design_model(request.model_id)
        if not all(value.strip() for value in [request.name, request.description, request.text]):
            raise HTTPException(status_code=422, detail='Enter a name, voice description and preview text')
        try:
            return repository().save_design_profile(principal.actor_user_id, request.profile_id,
                name=request.name.strip(), model_id=request.model_id,
                description=request.description.strip(), text=request.text.strip())
        except (ValueError, RepositoryError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post('/design/profiles')
    def save_designed_voice(request: DesignRequest, principal: RequestPrincipal = principal_dependency):
        return _camel(save_design(request, principal))

    @router.post('/design/preview')
    async def preview_designed_voice(request: DesignRequest, principal: RequestPrincipal = principal_dependency):
        model = design_model(request.model_id)
        if not model.checkpoint_ready:
            raise HTTPException(status_code=409, detail='Configure the selected Voice Design model first')
        profile = save_design(request, principal)
        runtime = runtime_provider()
        invocations = runtime.model_invocations
        request_id = 'design-preview-' + uuid.uuid4().hex
        response = await invoke_speech(invocations.invoke_foreground_json, model.id, 'audio_speech',
            {'model':model.id,'input':request.text.strip(),'instructions':request.description.strip(),'response_format':'wav', **_preview_expression(model, request.emotion, request.speed)},
            request_id=request_id, context=invocations.context_for_actor(principal.actor_user_id, session_id=request_id, consumer_app_id=READALOUD_STUDIO_ID))
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail='Voice Design generation failed')
        content = bytes(response.body)
        if not content or len(content)>64*1024*1024:
            raise HTTPException(status_code=502, detail='Invalid voice preview output')
        from io import BytesIO
        import wave
        try:
            with wave.open(BytesIO(content)) as audio:
                if audio.getnframes() <= 0:
                    raise ValueError('Empty audio')
        except (ValueError, wave.Error, EOFError) as error:
            raise HTTPException(status_code=502, detail='Voice Design returned invalid WAV audio') from error
        url = runtime.readaloud_tasks.save_quick_audio(principal.actor_user_id, content,
            title=request.name.strip(), model_label=getattr(model,'display_name',model.id),mini_app_id='ai2apps.audio.voice-design')
        session_id, artifact_id = url.split('/')[4], url.split('/')[-2]
        preview = {'emotion':request.emotion,'speed':request.speed,'session_id':session_id,'artifact_id':artifact_id,'download_url':url,'text':request.text.strip(),'model_id':model.id,
                   'model_revision':str((model.weights or {}).get('revision') or ''),'description':request.description.strip()}
        if not repository().attach_design_preview(principal.actor_user_id, profile['id'], (model.id,request.description.strip(),request.text.strip()), preview):
            raise HTTPException(status_code=409, detail='The character changed while generating. Generate a new preview.')
        return _camel(repository().get_voice_profile(principal.actor_user_id, profile['id']))

    @router.post('/design/profiles/{profile_id}/convert')
    def convert_designed_voice(profile_id: str, request: DesignConversionRequest, principal: RequestPrincipal = principal_dependency):
        runtime = runtime_provider()
        try:
            profile = repository().get_voice_profile(principal.actor_user_id, profile_id)
            preview = profile.get('training', {}).get('design', {}).get('preview')
            if not preview:
                raise ValueError('Generate and select a voice preview before converting')
            model = runtime.model_invocations.model(request.model_id)
            if model is None:
                raise ValueError('Select a reference-voice model')
            spec = training_requirements(model)
            if not spec or spec['method'] != 'reference':
                raise ValueError('Select a reference-voice model')
            gallery = materials()
            artifact = runtime.workspace.get_artifact(preview['session_id'],preview['artifact_id'])
            asset = gallery.save(principal.actor_user_id, runtime.workspace.artifact_path(artifact).read_bytes(), profile['name']+'.wav', 'audio/wav')
            preview = {**preview,'asset_id':asset['id']}
            spec, samples, _ = prepare_training(model,[{'asset_id':preview['asset_id'],'transcript':preview['text'],'selected':True,'confirmed':False}],gallery,principal.actor_user_id)
            return _camel(repository().create_voice_profile(principal.actor_user_id,
                name=profile['name']+' · Clone', source_type='synthetic_designed',model_id=model.id,provider_voice_id=None,
                reference_asset_id=preview['asset_id'],reference_transcript=preview['text'],rights_scope={'synthetic_origin':profile_id},
                training={'requirements':spec,'samples':samples,'model_revision':spec['revision'],'state':'materials_saved','origin':{'design_profile_id':profile_id,'asset_id':preview['asset_id']}}))
        except OSError as error:
            raise HTTPException(status_code=409, detail='The preview is no longer available. Generate a new preview before converting.') from error
        except (ValueError, RepositoryError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.delete('/audio-history/{artifact_id}', status_code=204)
    def delete_audio_history(artifact_id: str, principal: RequestPrincipal = principal_dependency):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        session_id = manager._artifact_session(principal.actor_user_id)
        workspace = runtime_provider().workspace
        try:
            artifact = workspace.get_artifact(session_id, artifact_id)
            if artifact.metadata.get('studioId') != READALOUD_STUDIO_ID and not artifact.metadata.get('dialogueJobId'):
                raise HTTPException(status_code=404, detail='Audio task not found')
            workspace.retire_artifact(session_id, artifact_id)
            repo = repository()
            profiles = repo.list_voice_profiles(principal.actor_user_id)
            with repo.database.transaction(write=True) as connection:
                for profile in profiles:
                    training = profile.get('training', {})
                    design = training.get('design', {})
                    if design.get('preview', {}).get('artifact_id') == artifact_id:
                        design.pop('preview', None)
                        connection.execute("UPDATE readaloud_voice_profiles SET training_json=?,status='unverified' WHERE id=?", (json.dumps(training),profile['id']))
        except RepositoryError as error:
            raise HTTPException(status_code=404, detail='Audio task not found') from error
        return Response(status_code=204)

    @router.get("/training/history")
    def training_history(principal: RequestPrincipal = principal_dependency):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        return {'items': manager.quick_history(principal.actor_user_id, mini_app_id='ai2apps.audio.voice-design')}

    def training_input(request, principal, *, execute=False):
        runtime = runtime_provider()
        if not request.name.strip():
            raise HTTPException(status_code=422, detail="Enter a character name")
        if getattr(runtime, 'model_invocations', None) is None:
            raise HTTPException(status_code=503, detail="Voice service is not ready")
        model = runtime.model_invocations.model(request.model_id)
        if model is None:
            raise HTTPException(status_code=422, detail="Select an installed voice model")
        try:
            _voice_rights_scope(request, principal)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        # Synthetic is a user-declared source type, not a required import route.
        # Gallery imports and uploads receive the same owner/audio validation below.
        gallery = materials()
        try:
            for sample in request.samples:
                gallery.import_gallery(principal.actor_user_id, sample.asset_id)
            spec, samples, files = prepare_training(model, [sample.model_dump() for sample in request.samples], gallery, principal.actor_user_id, for_execution=execute)
        except (ValueError, RepositoryError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if request.model_revision is not None and request.model_revision != spec["revision"]:
            raise HTTPException(status_code=409, detail="The model version changed. Rebind the current version and preview it again.")
        return runtime, model, spec, samples, files

    @router.post("/training/profiles", status_code=201)
    def save_training_profile(request: TrainingRequest, principal: RequestPrincipal = principal_dependency):
        runtime, model, spec, samples, _ = training_input(request, principal)
        selected = next(sample for sample in samples if sample['selected'])
        if request.profile_id:
            return guarded(lambda: _camel(repository().update_training_profile(
                principal.actor_user_id, request.profile_id, name=request.name.strip(),
                source_type=request.source_type, model_id=model.id,
                reference_transcript=selected['transcript'], reference_asset_id=selected['asset_id'],
                rights_scope=_voice_rights_scope(request, principal),
                training={'requirements': spec, 'samples': samples, 'model_revision': spec['revision'], 'state': 'materials_saved', 'origin': repository().get_voice_profile(principal.actor_user_id,request.profile_id).get('training',{}).get('origin',{})},
            )))
        return _camel(repository().create_voice_profile(
            principal.actor_user_id, name=request.name.strip(), source_type=request.source_type,
            model_id=model.id, provider_voice_id=None, reference_transcript=selected['transcript'],
            reference_asset_id=selected['asset_id'], rights_scope=_voice_rights_scope(request, principal),
            training={'requirements': spec, 'samples': samples, 'model_revision': spec['revision'], 'state': 'materials_saved'},
        ))

    @router.post("/training/preview")
    async def preview_training(request: TrainingRequest, principal: RequestPrincipal = principal_dependency):
        runtime, model, spec, samples, files = await asyncio.to_thread(training_input, request, principal, execute=True)
        if not spec['executable']:
            raise HTTPException(status_code=409, detail="This model’s training or multi-reference execution adapter is not connected. Materials can be saved.")
        if not model.checkpoint_ready:
            raise HTTPException(status_code=409, detail="Configure the selected model before previewing")
        reference_audio, reference_text = combined_reference(samples, files)
        payload = {'model': model.id, 'input': request.preview_text.strip(), 'response_format': 'wav', **_preview_expression(model, request.emotion, request.speed)}
        if not payload['input']:
            raise HTTPException(status_code=422, detail="Enter preview text")
        if reference_text:
            payload['ref_text'] = reference_text
        # Multipart speech fields are scalar; nested style belongs to JSON requests.
        style = payload.pop('style', None)
        if style:
            payload['emotion'] = style['emotion']
            payload['emotion_strength'] = style['emotion_strength']
        invocations = runtime.model_invocations
        request_id = 'voice-preview-' + uuid.uuid4().hex
        response = await invoke_speech(invocations.invoke_foreground_multipart,
            model.id, 'audio_speech', data=payload,
            files={'reference_audio': ('reference.wav', reference_audio, 'audio/wav')},
            request_id=request_id,
            context=invocations.context_for_actor(principal.actor_user_id, session_id=request_id, consumer_app_id=READALOUD_STUDIO_ID),
        )
        if response.status_code >= 400:
            detail = ''
            try:
                body = json.loads(response.body)
                error = body.get('error')
                detail = error.get('message', '') if isinstance(error, dict) else body.get('detail', '')
            except (ValueError, TypeError, AttributeError):
                pass
            raise HTTPException(status_code=502, detail=f'Voice preview failed (HTTP {response.status_code})' + (f': {str(detail)[:500]}' if detail else ''))
        content = bytes(response.body)
        if not content or len(content) > 64 * 1024 * 1024:
            raise HTTPException(status_code=502, detail="Invalid voice preview output")
        url = runtime.readaloud_tasks.save_quick_audio(principal.actor_user_id, content,
            title=request.name, model_label=getattr(model, 'display_name', model.id),
            mini_app_id='ai2apps.audio.voice-design')
        if request.profile_id:
            repository().verify_training_preview(principal.actor_user_id, request.profile_id, {
                'model_id': model.id, 'source_type': request.source_type,
                'rights_scope': _voice_rights_scope(request, principal),
                'training': {'samples': samples, 'model_revision': spec['revision']},
            })
        return Response(content, media_type='audio/wav', headers={'Cache-Control': 'no-store', 'X-AI2Apps-Download-URL': url})

    @router.delete('/voice-profiles/{profile_id}')
    def delete_voice_profile(profile_id: str, principal: RequestPrincipal = principal_dependency):
        return guarded(lambda: repository().delete_voice_profile(principal.actor_user_id, profile_id))

    @router.get("/voice-profiles")
    def list_voice_profiles(principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return {
            "items": [
                _camel(item)
                for item in selected.list_voice_profiles(principal.actor_user_id)
            ]
        }

    @router.post("/voice-profiles", status_code=201)
    def create_voice_profile(
        request: VoiceProfileCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        if request.source_type == "synthetic_designed" and request.model_id:
            invocations = getattr(runtime_provider(), "model_invocations", None)
            model = invocations.model(request.model_id) if invocations else None
            if model is None or model.model_type != "audio_tts" or "voice_design" not in (model.capabilities or []):
                raise HTTPException(status_code=422, detail="Select a model that supports Voice Design")
        return guarded(
            lambda: _camel(
                selected.create_voice_profile(
                    principal.actor_user_id,
                    name=request.name.strip(),
                    source_type=request.source_type,
                    model_id=request.model_id,
                    provider_voice_id=request.provider_voice_id,
                    reference_transcript=request.reference_transcript,
                    rights_scope=_voice_rights_scope(request, principal),
                    reference_asset_id=reference_audio_asset(
                        request.reference_asset_id,
                        principal,
                    ),
                )
            )
        )

    @router.post("/projects/{project_id}/characters", status_code=201)
    def create_character(
        project_id: str,
        request: CharacterCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        name = request.name.strip()
        if not name:
            return platform_error_response(
                status_code=422,
                code="readaloud_request_invalid",
                message="Character name must contain visible characters.",
            )
        return guarded(
            lambda: _camel(
                selected.create_character(
                    principal.actor_user_id,
                    project_id,
                    name=name,
                    description=request.description,
                    voice_profile_id=request.voice_profile_id,
                    role=request.role,
                )
            )
        )

    @router.post('/projects/{project_id}/source/analyze')
    async def analyze_source(project_id: str, request: SourceAnalysisRequest, http_request: Request,
                             principal: RequestPrincipal = principal_dependency):
        runtime = runtime_provider()
        try:
            project = repository().get_project(principal.actor_user_id, project_id)
            if not request.text.strip():
                raise ValueError('Enter source text.')
            messages = analysis_messages(project, request.text, request.after_id)
        except RepositoryError as error:
            return repository_error_response(error)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        manager = getattr(runtime, 'model_manager', None)
        model_id = request.model_id or (manager.resolve_default_model('work_standard') if manager else None)
        if not model_id:
            raise HTTPException(409, 'No model is configured for Standard tasks. Configure it in Models first.')
        payload = {'model':model_id, 'messages':messages, 'max_tokens':16000, 'stream':False}
        request_id = 'readaloud-source-' + uuid.uuid4().hex
        try:
            async with asyncio.timeout(180):
                invocations = getattr(runtime, 'model_invocations', None)
                model = invocations.model(model_id) if invocations else None
                for attempt in range(2):
                    if model is not None and 'chat_completions' in getattr(model, 'endpoints', {}):
                        response = await invocations.invoke_foreground_json(model.id, 'chat_completions', payload, request_id=request_id,
                            context=invocations.context_for_actor(principal.actor_user_id, session_id=request_id, consumer_app_id=READALOUD_STUDIO_ID))
                        content = bytes(response.body)
                    else:
                        import httpx
                        headers = {key:value for key,value in http_request.headers.items() if key.lower() in {'authorization','cookie','x-api-key','x-ai2apps-app-id','x-ai2apps-installation-id'}}
                        headers['x-request-id'] = request_id
                        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=http_request.app), base_url='http://ai2apps.internal', timeout=180) as client:
                            response = await client.post('/v1/chat/completions', json=payload, headers=headers)
                        content = response.content
                    if response.status_code >= 400:
                        raise HTTPException(502, f'Standard tasks AI returned HTTP {response.status_code}.')
                    proposal = parse_completion(content, [actor['id'] for actor in project['characters']])
                    validate_proposal(proposal, project)
                    issues = dialogue_issues(proposal, project)
                    if not issues:
                        break
                    if attempt:
                        raise ValueError('AI repeated dialogue in narration. Please try another analysis model.')
                    payload['messages'] = messages + [
                        {'role':'assistant', 'content':proposal.model_dump_json()},
                        {'role':'user', 'content':'Correct the complete proposal. Preserve all non-duplicated dialogue and meaningful narration. Remove redundant attribution tags. Fix these issues and return the full JSON only: ' + json.dumps(issues, ensure_ascii=False)},
                    ]
                    request_id += '-repair'
        except TimeoutError as error:
            raise HTTPException(504, 'AI analysis timed out. Try a smaller section.') from error
        except ValidationError as error:
            issues = error.errors(include_url=False, include_input=False)
            details = '; '.join('.'.join(map(str, issue['loc'])) + ': ' + issue['msg'] for issue in issues[:3])
            raise HTTPException(422, 'AI returned an incomplete or invalid proposal. Please analyze again. ' + details) from error
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
            raise HTTPException(422, 'Invalid AI analysis: ' + str(error)[:300]) from error
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(502, 'Standard tasks AI could not complete the analysis. Please retry.') from error
        return {**proposal.model_dump(), 'revision':project['revision'], 'after_id':request.after_id, 'batch_id':uuid.uuid4().hex, 'model_id':model_id}

    @router.post('/projects/{project_id}/source/apply')
    def apply_source(project_id: str, request: SourceApplyRequest, principal: RequestPrincipal = principal_dependency):
        return guarded(lambda: repository().apply_source_proposal(principal.actor_user_id, project_id, request))

    @router.patch('/projects/{project_id}/characters/{character_id}')
    def edit_character(project_id: str, character_id: str, request: CharacterCreateRequest,
                       principal: RequestPrincipal = principal_dependency):
        return guarded(lambda: _camel(repository().edit_character(principal.actor_user_id, project_id, character_id, changes=request.model_dump())))

    @router.delete('/projects/{project_id}/characters/{character_id}')
    def delete_character(project_id: str, character_id: str, principal: RequestPrincipal = principal_dependency):
        return guarded(lambda: _camel(repository().edit_character(principal.actor_user_id, project_id, character_id, delete=True)))

    @router.post("/projects/{project_id}/segments", status_code=201)
    def create_segment(
        project_id: str,
        request: SegmentCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        text = request.text.strip()
        if not text:
            return platform_error_response(
                status_code=422,
                code="readaloud_request_invalid",
                message="Segment text must contain visible characters.",
            )
        return guarded(
            lambda: _camel(
                selected.create_segment(
                    principal.actor_user_id,
                    project_id,
                    speaker_id=request.speaker_id,
                    text=text,
                    emotion=request.emotion.strip(),
                    emotion_strength=request.emotion_strength,
                    speed=request.speed,
                    pause_after_ms=request.pause_after_ms,
                )
            )
        )

    @router.patch("/projects/{project_id}/segments/{segment_id}")
    def update_segment(
        project_id: str,
        segment_id: str,
        request: SegmentUpdateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(
            lambda: _camel(
                selected.update_segment(
                    principal.actor_user_id,
                    project_id,
                    segment_id,
                    request.model_dump(exclude_unset=True),
                )
            )
        )

    @router.post("/projects/{project_id}/dialogue", status_code=202)
    async def create_dialogue(project_id: str, request: RenderCreateRequest, principal: RequestPrincipal = principal_dependency):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return _camel(await manager.create(owner_user_id=principal.actor_user_id, project_id=project_id, model_id=request.model_id, merge_output=True))
        except (ReadAloudRenderError, RepositoryError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/projects/{project_id}/dialogue")
    def latest_dialogue(project_id: str, principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        def load():
            selected.get_project(principal.actor_user_id, project_id)
            with runtime_provider().database.transaction() as connection:
                row = connection.execute("SELECT id FROM readaloud_render_jobs WHERE project_id=? AND owner_user_id=? AND merge_output=1 ORDER BY created_at DESC LIMIT 1", (project_id, principal.actor_user_id)).fetchone()
            return {"job": _camel(render_manager().get(row['id'], owner_user_id=principal.actor_user_id)) if row else None}
        return guarded(load)

    @router.get("/projects/{project_id}/segments/{segment_id}/audio/content")
    def line_audio_content(project_id: str, segment_id: str, model_id: str, principal: RequestPrincipal = principal_dependency):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        return guarded(lambda: FileResponse(manager.line_audio_path(principal.actor_user_id, project_id, segment_id, model_id), media_type="audio/wav", filename="line.wav"))

    @router.get("/projects/{project_id}/segments/{segment_id}/audio")
    def cached_segment_audio(project_id: str, segment_id: str, model_id: str, principal: RequestPrincipal = principal_dependency):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        return guarded(lambda: {"audio": manager.cached_segment(principal.actor_user_id, project_id, segment_id, model_id)})

    @router.post("/projects/{project_id}/segments/{segment_id}/move/{direction}")
    def move_segment(project_id: str, segment_id: str, direction: Literal["up", "down"], principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(lambda: _camel(selected.change_segment_position(principal.actor_user_id, project_id, segment_id, action=direction)))

    @router.delete("/projects/{project_id}/segments/{segment_id}")
    def delete_segment(project_id: str, segment_id: str, principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(lambda: _camel(selected.change_segment_position(principal.actor_user_id, project_id, segment_id, action="delete")))

    @router.post("/projects/{project_id}/render", status_code=202)
    async def create_render_job(
        project_id: str,
        request: RenderCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            job = await manager.create(
                owner_user_id=principal.actor_user_id,
                project_id=project_id,
                model_id=request.model_id,
                segment_ids=request.segment_ids,
                mini_app_id=request.mini_app_id,
                placement=request.placement,
            )
            return _camel(job)
        except RepositoryError as error:
            return repository_error_response(error)
        except ReadAloudRenderError as error:
            return platform_error_response(
                status_code=error.status_code,
                code=error.code,
                message=str(error),
                retryable=error.status_code >= 500,
            )

    @router.get("/render-jobs")
    def list_render_jobs(
        project_id: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        principal: RequestPrincipal = principal_dependency,
    ):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        return {
            "items": [
                _camel(item)
                for item in manager.list(
                    owner_user_id=principal.actor_user_id,
                    project_id=project_id,
                    limit=limit,
                )
            ]
        }

    @router.get("/render-jobs/{job_id}")
    def get_render_job(
        job_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return _camel(manager.get(job_id, owner_user_id=principal.actor_user_id))
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/render-jobs/{job_id}/cancel")
    async def cancel_render_job(
        job_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return _camel(
                await manager.cancel(job_id, owner_user_id=principal.actor_user_id)
            )
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/render-jobs/{job_id}/retry", status_code=202)
    async def retry_render_job(
        job_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return _camel(
                await manager.retry(job_id, owner_user_id=principal.actor_user_id)
            )
        except RepositoryError as error:
            return repository_error_response(error)
        except ReadAloudRenderError as error:
            return platform_error_response(
                status_code=error.status_code,
                code=error.code,
                message=str(error),
            )

    return router
