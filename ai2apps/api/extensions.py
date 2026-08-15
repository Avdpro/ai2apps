"""M9 Agent/App/Patch package, Effective definition, App mount, and Safe Mode API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai2apps.api.errors import repository_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.core import RepositoryError
from ai2apps.extensions import ExtensionError, UnitKind


class InstallRequest(BaseModel):
    archive_path: str
    approve_review: bool = False


class PatchCreateRequest(BaseModel):
    target_kind: UnitKind
    target_key: str
    intent: str
    operations: list[dict[str, Any]]
    rebase_policy: str = "strict"
    tests: list[dict[str, Any]] = Field(default_factory=list)
    resources: dict[str, str] = Field(default_factory=dict)
    version: str = "1.0.0"


class PatchResolutionRequest(BaseModel):
    resolution: str
    candidate_digest: str | None = None


class AppLaunchRequest(BaseModel):
    singleton_identity: str = "local"
    state: dict[str, Any] = Field(default_factory=dict)


class MountRequest(BaseModel):
    mini: bool = False
    placement: str = "entry"
    interaction_session_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class SafeModeRequest(BaseModel):
    active: bool
    reason: str = "user-request"


def _error(error: ExtensionError) -> JSONResponse:
    status = 409 if error.code.endswith(("conflict", "unavailable")) else 422
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": error.code,
                "message": str(error),
                "details": error.details,
            }
        },
    )


def _package(item):
    return {
        "id": item.id,
        "kind": item.kind.value,
        "key": item.unit_key,
        "version": item.version,
        "digest": item.digest,
        "publisher": item.publisher_key,
        "status": item.status.value,
        "manifest": item.manifest,
        "file_index": item.file_index,
        "sbom": item.sbom,
        "verification": item.verification,
    }


def _effective(item):
    return {
        "id": item.id,
        "kind": item.kind.value,
        "key": item.unit_key,
        "upstream_digest": item.upstream_digest,
        "patch_set_digest": item.patch_set_digest,
        "effective_digest": item.effective_digest,
        "effective_version": item.effective_version,
        "manifest": item.manifest,
        "resources": item.resources,
        "audit": item.audit,
        "status": item.status,
    }


def create_extension_router(runtime_provider: PlatformRuntimeProvider) -> APIRouter:
    router = APIRouter(tags=["interactive-packages"])

    def runtime():
        value = runtime_provider()
        if value is None or value.extension_manager is None:
            return JSONResponse(
                status_code=503, content={"error": {"code": "platform_unavailable"}}
            )
        return value

    @router.post("/interactive-packages/inspect")
    def inspect(request: InstallRequest):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            bundle, verification = value.extension_manager.inspect(request.archive_path)
            return {
                "kind": str(bundle.kind),
                "key": bundle.key,
                "version": bundle.version,
                "digest": bundle.digest,
                "manifest": bundle.manifest,
                "files": [
                    item.__dict__
                    if hasattr(item, "__dict__")
                    else {
                        "path": item.path,
                        "content_hash": item.content_hash,
                        "size_bytes": item.size_bytes,
                    }
                    for item in bundle.files
                ],
                "sbom": bundle.sbom,
                "verification": verification,
            }
        except ExtensionError as error:
            return _error(error)

    @router.post("/interactive-packages/install")
    async def install(request: InstallRequest):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            item = await value.extension_manager.install(
                request.archive_path, approve_review=request.approve_review
            )
            if hasattr(item, "unit_key"):
                return _package(item)
            return {
                "id": item.id,
                "kind": item.target_kind.value,
                "key": item.target_key,
                "digest": item.digest,
                "status": item.status.value,
            }
        except ExtensionError as error:
            return _error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get("/interactive-packages")
    def packages(kind: UnitKind | None = None, key: str | None = None):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        return {
            "items": [
                _package(item)
                for item in value.extension_repository.installed(kind, key)
            ]
        }

    @router.get("/interactive-operations")
    def operations(kind: UnitKind | None = None, key: str | None = None):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        return {"items": value.extension_repository.operations(kind, key)}

    @router.post("/interactive-packages/{digest:path}/activate")
    def activate(digest: str):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            return _package(
                value.extension_manager.activate_candidate(
                    "sha256:" + digest.removeprefix("sha256:")
                )
            )
        except ExtensionError as error:
            return _error(error)

    @router.get("/effective-definitions/{kind}/{key}")
    def effective(kind: UnitKind, key: str):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        item = value.extension_repository.effective(kind, key)
        if item is None:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "effective_definition_not_found"}},
            )
        return _effective(item)

    @router.get("/local-patches/{kind}/{key}")
    def patches(kind: UnitKind, key: str):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        return {
            "items": [
                {
                    "id": item.id,
                    "digest": item.digest,
                    "base_digest": item.base_digest,
                    "intent": item.intent,
                    "rebase_policy": item.rebase_policy.value,
                    "operations": item.operations,
                    "tests": item.tests,
                    "audit": item.audit,
                    "status": item.status.value,
                    "conflict": item.conflict,
                    "stack_order": item.stack_order,
                }
                for item in value.extension_repository.patches(kind, key)
            ]
        }

    @router.post("/local-patches/create")
    def create_patch(request: PatchCreateRequest):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            exports = value.config.paths.packages_path / "exports"
            filename = f"{request.target_key}-{request.version}.ai2patch"
            path = value.extension_manager.create_patch(
                exports / filename,
                target_kind=request.target_kind,
                target_key=request.target_key,
                intent=request.intent,
                operations=request.operations,
                rebase_policy=request.rebase_policy,
                tests=request.tests,
                resources=request.resources,
                version=request.version,
            )
            return {"archive_path": str(path)}
        except ExtensionError as error:
            return _error(error)

    @router.post("/local-patches/{patch_id}/resolve")
    def resolve(patch_id: str, request: PatchResolutionRequest):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            item = value.extension_manager.resolve_patch(
                patch_id, request.resolution, candidate_digest=request.candidate_digest
            )
            return {
                "id": item.id,
                "status": item.status.value,
                "base_digest": item.base_digest,
            }
        except ExtensionError as error:
            return _error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/apps/{app_key}/launch")
    def launch(app_key: str, request: AppLaunchRequest):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            instance, home, created = value.extension_manager.launch_app(
                app_key,
                singleton_identity=request.singleton_identity,
                state=request.state,
            )
            return {
                "created": created,
                "instance_id": instance.id,
                "home_session_id": None if home is None else home.id,
                "state": instance.state,
                "state_schema_version": instance.state_schema_version,
                "entry_url": f"/apps/{app_key}/instances/{instance.id}",
            }
        except ExtensionError as error:
            return _error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get("/apps")
    def apps():
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        return {"items": value.extension_manager.list_apps()}

    @router.get("/app-instances/{instance_id}/entry")
    def instance_entry(instance_id: str):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            return value.extension_manager.instance_entry(instance_id)
        except ExtensionError as error:
            return _error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/app-instances/{instance_id}/focus")
    def focus(instance_id: str):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            instance = value.extension_manager.focus_instance(instance_id)
            return {"instance_id": instance.id, "status": instance.status.value}
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/app-instances/{instance_id}/suspend")
    def suspend(instance_id: str):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            instance = value.extension_manager.suspend_instance(instance_id)
            return {"instance_id": instance.id, "status": instance.status.value}
        except RepositoryError as error:
            return repository_error_response(error)

    @router.delete("/app-instances/{instance_id}")
    def close(instance_id: str):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            instance = value.extension_manager.close_instance(instance_id)
            return {"instance_id": instance.id, "status": instance.status.value}
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/app-instances/{instance_id}/mounts")
    def mount(instance_id: str, request: MountRequest):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            return value.extension_manager.mount(
                instance_id,
                mini=request.mini,
                placement=request.placement,
                interaction_session_id=request.interaction_session_id,
                context=request.context,
            )
        except ExtensionError as error:
            return _error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/definitions/{kind}/{key}/enable")
    def enable(kind: UnitKind, key: str):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            value.extension_manager.set_enabled(kind, key, True)
            return {"status": "enabled"}
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/definitions/{kind}/{key}/disable")
    def disable(kind: UnitKind, key: str):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            value.extension_manager.set_enabled(kind, key, False)
            return {"status": "disabled"}
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/definitions/{kind}/{key}/rollback")
    def rollback(kind: UnitKind, key: str):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            return _package(value.extension_manager.rollback(kind, key))
        except ExtensionError as error:
            return _error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.delete("/definitions/{kind}/{key}")
    def uninstall(kind: UnitKind, key: str, force: bool = False):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            value.extension_manager.uninstall(kind, key, force=force)
            return {"status": "uninstalled"}
        except ExtensionError as error:
            return _error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/safe-mode")
    async def safe_mode(request: SafeModeRequest):
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        try:
            return await value.set_safe_mode(request.active, request.reason)
        except ExtensionError as error:
            return _error(error)

    @router.get("/safe-mode")
    def safe_mode_status():
        value = runtime()
        if isinstance(value, JSONResponse):
            return value
        return value.extension_manager.safe_mode_status()

    return router
