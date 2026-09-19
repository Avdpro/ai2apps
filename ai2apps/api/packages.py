"""Trusted Service package, publisher, audit, logs, and lifecycle APIs."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai2apps.api.errors import platform_error_response, repository_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import (
    PrincipalProvider,
    require_app_capability,
    resolve_request_principal,
)
from ai2apps.api.ownership import authorize_app_instance
from ai2apps.apps.access import APP_SYSTEM_MANAGE
from ai2apps.core import RepositoryError
from ai2apps.http_security import enforce_same_origin_cookie_request
from ai2apps.identity import RequestPrincipal
from ai2apps.model_providers import (
    list_package_models,
    recommended_model_configuration_id,
)
from ai2apps.packages import PackageError, TrustStatus
from ai2apps.packages.contract_v1 import PackageContractError
from ai2apps.packages.discovery import MODEL_CATEGORIES, matches_model_category
from ai2apps.packages.install_continuations import (
    RegistryInstallContinuationRepository,
)
from ai2apps.packages.registry import RegistryError
from ai2apps.password_policy import PASSWORD_SCHEMA, Password
from ai2apps.provisioning.profiles import device_profile


class PublisherRequest(BaseModel):
    display_name: str = Field(min_length=1)
    key_id: str = Field(min_length=1)
    public_key: str = Field(min_length=1)
    trust_status: TrustStatus
    source: str = "user"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PackageInspectRequest(BaseModel):
    archive_path: str = Field(min_length=1)


class TestCandidateRequest(PackageInspectRequest):
    expected_digest: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")


class PackageInstallRequest(PackageInspectRequest):
    dependency_archives: list[str] = Field(default_factory=list)
    allow_untrusted: bool = False
    approve_audit_review: bool = False


class RegistryBuildRequest(BaseModel):
    source_path: str = Field(min_length=1)
    output_path: str = Field(min_length=1)


class PublisherKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class RegistrySignRequest(BaseModel):
    archive_path: str = Field(min_length=1)
    key_ref: str = Field(min_length=1)
    publisher_id: str = Field(min_length=1)
    publisher_key_id: str = Field(min_length=1)


class PublisherKeyProofRequest(BaseModel):
    key_ref: str = Field(min_length=1)
    payload: dict[str, Any]


class RegistryInstallRequest(BaseModel):
    version: str | None = None
    approve_review: bool = False


class RegistryModelInstallRequest(BaseModel):
    version: str | None = None
    model_id: str = Field(alias="modelId", min_length=1, max_length=255)


class RegistryUninstallRequest(BaseModel):
    force: bool = False
    delete_checkpoints: bool = False


class CloudPublisherCreateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    namespace: str = Field(min_length=3, max_length=80)
    kind: str = Field(default="personal", pattern="^(personal|organization)$")


class CloudKeyChallengeRequest(BaseModel):
    key_ref: str = Field(min_length=1)


class CloudKeyRegisterRequest(BaseModel):
    challenge_id: str = Field(min_length=1)
    signature: str = Field(min_length=1)


class CloudSubmissionRequest(BaseModel):
    archive_path: str = Field(min_length=1)
    envelope: dict[str, Any]


class CloudSubmissionReviewRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str = Field(min_length=1, max_length=2000)


class CloudAdminReauthRequest(BaseModel):
    password: Password = Field(json_schema_extra=PASSWORD_SCHEMA)


def _package(record) -> dict[str, Any]:
    return {
        "id": record.id,
        "service_key": record.service_key,
        "version": record.package_version,
        "digest": record.package_digest,
        "publisher": record.publisher_key,
        "runtime_mode": record.runtime_mode.value,
        "protocol": record.protocol,
        "status": record.status.value,
        "permissions": record.permissions,
        "compatibility": record.compatibility,
        "verification": record.verification,
        "store_path": record.store_path,
        "installed_at": record.installed_at.isoformat(),
        "activated_at": None
        if record.activated_at is None
        else record.activated_at.isoformat(),
    }


def _filter_catalog_content(
    value: Any,
    *,
    content: str | None,
    model_category: str | None,
    model_task: str | None,
    limit: int,
) -> Any:
    if (
        content not in {"model", "service"}
        and model_category is None
        and model_task is None
    ):
        return value

    def matches(item: Any) -> bool:
        if not isinstance(item, dict):
            return False
        discovery = item.get("discovery")
        is_model = isinstance(discovery, dict) and discovery.get("kind") == "model"
        if content == "model" and not is_model:
            return False
        if content == "service" and is_model:
            return False
        if model_category is not None and (
            not is_model or not matches_model_category(discovery, model_category)
        ):
            return False
        return model_task is None or (
            is_model and model_task in discovery.get("tasks", [])
        )

    if isinstance(value, list):
        return [item for item in value if matches(item)][:limit]
    if not isinstance(value, dict):
        return value
    for key in ("items", "packages", "results", "recommendations"):
        if isinstance(value.get(key), list):
            result = dict(value)
            result[key] = [item for item in value[key] if matches(item)][:limit]
            return result
    return value


def _error(error: PackageError) -> JSONResponse:
    status = {
        "archive_not_found": 404,
        "publisher_unknown": 403,
        "publisher_untrusted": 403,
        "publisher_revoked": 403,
        "signature_invalid": 403,
        "audit_rejected": 403,
        "audit_review_required": 409,
        "dependency_unresolved": 409,
        "dependency_conflict": 409,
        "dependency_cycle": 409,
        "service_has_dependents": 409,
        "platform_incompatible": 422,
        "os_version_unknown": 422,
        "os_version_too_old": 422,
        "os_version_too_new": 422,
        "accelerator_incompatible": 422,
    }.get(error.code, 422)
    return platform_error_response(
        status_code=status,
        code=error.code,
        message=str(error),
        details=error.details,
    )


def _registry_error(error: RegistryError | PackageContractError) -> JSONResponse:
    status = {
        "release_not_found": 404,
        "package_not_installed": 404,
        "repository_key_unpinned": 403,
        "repository_signature_invalid": 403,
        "publisher_signature_invalid": 403,
        "release_unavailable": 409,
        "repository_metadata_rollback": 409,
        "repository_metadata_expired": 503,
        "artifact_download_failed": 503,
        "artifact_download_stalled": 503,
        "artifact_sources_exhausted": 503,
        "audit_review_required": 409,
        "dependency_restart_required": 409,
        "app_has_instances": 409,
        "platform_incompatible": 422,
        "architecture_incompatible": 422,
        "os_version_unknown": 422,
        "os_version_too_old": 422,
        "os_version_too_new": 422,
        "ai2apps_incompatible": 422,
        "service_contract_adapter_required": 501,
    }.get(error.code)
    if status is None and isinstance(error, RegistryError):
        upstream_status = error.details.get("status")
        status = (
            upstream_status
            if upstream_status in {400, 401, 403, 404, 409, 413, 422, 429, 503}
            else None
        )
    status = status or 422
    return platform_error_response(
        status_code=status,
        code=error.code,
        message=str(error),
        details=error.details,
    )


def _registry_install_result(item, namespace: str, name: str) -> dict[str, Any]:
    if hasattr(item, "unit_key"):
        package_id = item.unit_key
        package_type = item.kind.value
        version = item.version
        digest = item.digest
    else:
        package_id = f"{namespace}/{name}"
        package_type = "service"
        version = item.package_version
        digest = item.package_digest
    models = [
        model
        for model in getattr(item, "manifest", {}).get("models", [])
        if isinstance(model, dict)
        and isinstance(model.get("id"), str)
        and isinstance(model.get("weights"), dict)
    ]
    model_ids = [model["id"] for model in models]
    recommended_model_id = recommended_model_configuration_id(models)
    pending_runtime_restart = bool(
        package_type == "service"
        and getattr(item, "service_key", None) == "ai2apps.runtime.omlx"
        and item.status.value == "installed"
    )
    return {
        "packageId": package_id,
        "packageType": package_type,
        "version": version,
        "digest": digest,
        "status": item.status.value,
        "runtimeKey": getattr(item, "service_key", None),
        "modelConfigurationId": recommended_model_id,
        "modelConfigurationIds": model_ids,
        "restartRequired": pending_runtime_restart,
        "restartScope": "local" if pending_runtime_restart else None,
    }


def create_package_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    principal_dependency = Depends(principal_provider)
    router = APIRouter(
        dependencies=[
            Depends(require_app_capability(principal_provider, APP_SYSTEM_MANAGE))
        ]
    )
    install_operations: dict[str, dict[str, Any]] = {}
    install_tasks: set[asyncio.Task] = set()

    def update_install_operation(operation_id: str, values: dict[str, Any]) -> None:
        operation = install_operations.get(operation_id)
        if operation is None:
            return
        operation.update(values)
        operation["updatedAt"] = datetime.now(UTC).isoformat()

    async def run_install_operation(
        operation_id: str,
        manager,
        namespace: str,
        name: str,
        install_request: RegistryInstallRequest,
        principal: RequestPrincipal,
    ) -> None:
        package_id = f"{namespace}/{name}"
        continuation = install_continuation_repository()
        update_install_operation(operation_id, {"status": "running"})
        try:
            item = await manager.install(
                namespace,
                name,
                install_request.version,
                approve_review=install_request.approve_review,
                progress=lambda values: update_install_operation(operation_id, values),
            )
            update_install_operation(
                operation_id,
                {
                    "status": "completed",
                    "currentStep": 6,
                    "stage": "completed",
                    "bytesCompleted": None,
                    "bytesTotal": None,
                    "result": _registry_install_result(item, namespace, name),
                },
            )
            if continuation is not None:
                continuation.delete(
                    principal.actor_user_id,
                    principal.installation_id,
                    package_id=package_id,
                )
        except RegistryError as error:
            if continuation is not None:
                if error.code == "dependency_restart_required":
                    continuation.save(
                        actor_id=principal.actor_user_id,
                        installation_id=principal.installation_id,
                        package_id=package_id,
                        version=install_request.version,
                        approve_review=install_request.approve_review,
                        dependency=error.details.get("dependency", {}),
                    )
                else:
                    continuation.delete(
                        principal.actor_user_id,
                        principal.installation_id,
                        package_id=package_id,
                    )
            update_install_operation(
                operation_id,
                {
                    "status": "failed",
                    "stage": "failed",
                    "error": {
                        "code": error.code,
                        "message": str(error),
                        "details": error.details,
                    },
                },
            )
        except Exception as error:
            if continuation is not None:
                continuation.delete(
                    principal.actor_user_id,
                    principal.installation_id,
                    package_id=package_id,
                )
            update_install_operation(
                operation_id,
                {
                    "status": "failed",
                    "stage": "failed",
                    "error": {
                        "code": "install_failed",
                        "message": str(error),
                        "details": {},
                    },
                },
            )

    def runtime_or_error():
        runtime = runtime_provider()
        if (
            runtime is None
            or runtime.package_repository is None
            or runtime.package_manager is None
        ):
            return platform_error_response(
                status_code=503,
                code="platform_not_ready",
                message="AI2Apps package runtime is not ready.",
                retryable=True,
            )
        return runtime

    def registry_or_error():
        runtime = runtime_provider()
        if runtime is None or runtime.registry_packages is None:
            return platform_error_response(
                status_code=503,
                code="platform_not_ready",
                message="AI2Apps Registry package runtime is not ready.",
                retryable=True,
            )
        return runtime.registry_packages

    def install_continuation_repository():
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        if database is None:
            return None
        return RegistryInstallContinuationRepository(database)

    def trusted_discover_instance(
        principal: RequestPrincipal, app_instance_id: str
    ) -> None:
        runtime = runtime_provider()
        if runtime is None or runtime.extension_manager is None:
            raise HTTPException(status_code=503, detail="App identity is not initialized")
        authorize_app_instance(runtime, principal, app_instance_id)
        entry = runtime.extension_manager.instance_entry(
            app_instance_id, principal=principal
        )
        if entry.get("app_key") != "ai2apps.discover":
            raise HTTPException(status_code=403, detail="Discover App instance required")

    def catalog_package_facts(value: dict[str, Any]) -> tuple[str, str]:
        manifest = value.get("manifest")
        latest_release = value.get("latestRelease")
        if not isinstance(latest_release, dict):
            latest_release = {}
        if not isinstance(manifest, dict):
            manifest = latest_release.get("manifest", {})
        manifest_package = (
            manifest.get("package", {}) if isinstance(manifest, dict) else {}
        )
        catalog_package = (
            value.get("package") if isinstance(value.get("package"), dict) else {}
        )
        version = (
            value.get("version")
            or value.get("latestVersion")
            or latest_release.get("version")
            or catalog_package.get("latestVersion")
            or catalog_package.get("version")
            or manifest_package.get("version")
        )
        display_name = (
            value.get("displayName")
            or catalog_package.get("displayName")
            or manifest_package.get("displayName")
        )
        if not isinstance(version, str) or not version:
            raise RegistryError(
                "release_not_found", "The catalog release version is unavailable"
            )
        return version, str(
            display_name
            or catalog_package.get("packageId")
            or manifest_package.get("id")
            or "Model"
        )

    def publishing_registry_or_error(request: Request):
        """Return a Registry manager bound to this browser's Cloud session."""

        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        runtime = runtime_provider()
        enforce_same_origin_cookie_request(request)
        cookie_reader = getattr(runtime, "cloud_browser_session_from_cookies", None)
        browser_session_id = (
            cookie_reader(request.cookies) if cookie_reader is not None else None
        )
        if not browser_session_id:
            return platform_error_response(
                status_code=409,
                code="cloud_browser_session_required",
                message=(
                    "Sign in to AI2Apps Cloud in this browser before publishing "
                    "Packages."
                ),
                retryable=False,
            )
        resolver = getattr(runtime, "cloud_for_browser", None)
        if resolver is None:
            return platform_error_response(
                status_code=503,
                code="cloud_client_not_ready",
                message="Browser-isolated Cloud publishing is not ready.",
                retryable=True,
            )
        try:
            cloud = resolver(browser_session_id)
        except (RuntimeError, ValueError) as error:
            return platform_error_response(
                status_code=409,
                code="cloud_browser_session_invalid",
                message=str(error),
                retryable=False,
            )
        return manager.for_cloud(cloud)

    @router.get("/packages/catalog/search")
    async def registry_search(
        q: str = "",
        type: str | None = Query(default=None, pattern="^(app|agent|service)$"),
        content: str | None = Query(default=None, pattern="^(model|service)$"),
        model_category: str | None = Query(
            default=None, pattern=f"^({'|'.join(sorted(MODEL_CATEGORIES))})$"
        ),
        model_task: str | None = Query(
            default=None, min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
        ),
        publisher: str | None = None,
        sort: str = Query(
            default="recommended", pattern="^(recommended|relevance|rating|newest)$"
        ),
        limit: int = Query(default=24, ge=1, le=100),
        cursor: str | None = None,
    ):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            result = await manager.search(
                q=q,
                type="service" if content in {"model", "service"} else type,
                publisher=publisher,
                sort=sort,
                limit=100 if content in {"model", "service"} else limit,
                cursor=cursor,
            )
            return _filter_catalog_content(
                result,
                content=content,
                model_category=model_category,
                model_task=model_task,
                limit=limit,
            )
        except RegistryError as error:
            return _registry_error(error)

    @router.get("/packages/catalog/recommendations")
    async def registry_recommendations(
        type: str | None = Query(default=None, pattern="^(app|agent|service)$"),
        content: str | None = Query(default=None, pattern="^(model|service)$"),
        model_category: str | None = Query(
            default=None, pattern=f"^({'|'.join(sorted(MODEL_CATEGORIES))})$"
        ),
        model_task: str | None = Query(
            default=None, min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
        ),
        limit: int = Query(default=24, ge=1, le=100),
        cursor: str | None = None,
    ):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            result = await manager.recommendations(
                type="service" if content in {"model", "service"} else type,
                limit=100 if content in {"model", "service"} else limit,
                cursor=cursor,
            )
            return _filter_catalog_content(
                result,
                content=content,
                model_category=model_category,
                model_task=model_task,
                limit=limit,
            )
        except RegistryError as error:
            return _registry_error(error)

    @router.get("/packages/catalog/{namespace}/{name}")
    async def registry_catalog(namespace: str, name: str):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.catalog(namespace, name)
        except RegistryError as error:
            return _registry_error(error)

    @router.get("/packages/{namespace}/{name}/model-install-plan")
    async def registry_model_install_plan(
        namespace: str,
        name: str,
        version: str | None = None,
        principal: RequestPrincipal = principal_dependency,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
    ):
        trusted_discover_instance(principal, app_instance_id)
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            item = await manager.catalog(namespace, name)
            package_version, display_name = catalog_package_facts(item)
            if version is not None and version != package_version:
                raise RegistryError(
                    "release_not_found",
                    "The selected model release is no longer the catalog release",
                )
            install = item.get("modelInstall")
            if not isinstance(install, dict):
                raise RegistryError(
                    "model_install_unavailable",
                    "This Package does not declare a trusted model installation plan",
                )
            profile = item.get("modelProfile") or {}
            minimum_bytes = profile.get("minimumMemoryBytes")
            device = device_profile()
            memory_bytes = int(float(device.get("system_memory_gib", 0)) * 1024**3)
            compatible = not isinstance(minimum_bytes, int) or memory_bytes >= minimum_bytes
            return {
                "schema": "ai2apps.provisioning-plan/v1",
                "appId": "ai2apps.discover",
                "capability": "model.package.install",
                "selectionMode": "single",
                "device": device,
                "presentation": {
                    "title": f"选择 {display_name} 模型",
                    "description": "选择要随 Package 一起下载并验证的 Checkpoint。",
                    "icon": "box",
                },
                "profileOptions": [
                    {
                        "profileId": model["id"],
                        "modelId": model["id"],
                        "label": model["label"],
                        "description": "",
                        "compatible": compatible,
                        "recommended": model["recommended"] and compatible,
                        "selected": model["recommended"] and compatible,
                        "disabledReasons": [] if compatible else ["设备内存低于 Package 声明的最低要求"],
                        "minimumMemoryGiB": (
                            minimum_bytes / 1024**3
                            if isinstance(minimum_bytes, int)
                            else None
                        ),
                    }
                    for model in install["models"]
                ],
            }
        except RegistryError as error:
            return _registry_error(error)

    @router.post("/packages/{namespace}/{name}/model-install-sessions")
    async def registry_model_install_session(
        namespace: str,
        name: str,
        request: RegistryModelInstallRequest,
        principal: RequestPrincipal = principal_dependency,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
    ):
        trusted_discover_instance(principal, app_instance_id)
        if not principal.is_core:
            raise HTTPException(status_code=403, detail="Installation owner required")
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        runtime = runtime_provider()
        if runtime is None or runtime.provisioning is None:
            return platform_error_response(
                status_code=503,
                code="platform_not_ready",
                message="ACPF is not initialized.",
                retryable=True,
            )
        try:
            item = await manager.catalog(namespace, name)
            package_version, display_name = catalog_package_facts(item)
            if request.version is not None and request.version != package_version:
                raise RegistryError("release_not_found", "The selected model release is no longer available")
            install = item.get("modelInstall")
            if not isinstance(install, dict):
                raise RegistryError(
                    "model_install_unavailable",
                    "This Package does not declare a trusted model installation plan",
                )
            return runtime.provisioning.ensure_model_package(
                actor_id=principal.actor_user_id,
                installation_id=principal.installation_id,
                app_instance_id=app_instance_id,
                package_id=f"{namespace}/{name}",
                package_version=package_version,
                display_name=display_name,
                service_key=install["serviceKey"],
                models=install["models"],
                selected_model_id=request.model_id,
                model_profile=item.get("modelProfile"),
            )
        except RegistryError as error:
            return _registry_error(error)
        except ValueError as error:
            return platform_error_response(
                status_code=422,
                code="model_install_invalid",
                message=str(error),
            )

    @router.get("/packages/installed")
    def registry_installed(locale: str | None = Query(default=None, max_length=64)):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        items = manager.installed(locale=locale)
        ready_model_ids = {
            model.id
            for model in list_package_models(runtime_provider())
            if model.checkpoint_ready
        }
        for item in items:
            model_install = item.get("modelInstall")
            if not isinstance(model_install, dict):
                continue
            declared_ids = {
                model.get("id")
                for model in model_install.get("models", [])
                if isinstance(model, dict) and isinstance(model.get("id"), str)
            }
            configured_ids = sorted(declared_ids & ready_model_ids)
            item["readyModelConfigurationIds"] = configured_ids
            item["modelReady"] = bool(configured_ids)
        return {"items": items}

    @router.get("/packages/test-candidates")
    def test_candidate_available():
        from ai2apps.packages.test_candidates import require_test_instance
        try:
            require_test_instance(runtime_provider())
            return {"enabled": True}
        except RegistryError:
            return {"enabled": False}

    @router.post("/packages/test-candidates")
    async def test_candidate_import(request: TestCandidateRequest):
        from ai2apps.extensions import ExtensionError
        from ai2apps.packages.test_candidates import import_candidate
        try:
            return await import_candidate(runtime_provider(), request.archive_path,
                                          expected_digest=request.expected_digest)
        except (RegistryError, PackageContractError, ExtensionError) as error:
            return _registry_error(error)
        except (OSError, ValueError, KeyError):
            return _registry_error(RegistryError("candidate_invalid", "Candidate or signature metadata is invalid"))

    @router.post("/packages/build")
    def registry_build(request: RegistryBuildRequest):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            item = manager.build(request.source_path, request.output_path)
            return {
                "archivePath": str(item.archive_path),
                "package": item.manifest["package"],
                "sha256": item.sha256,
                "size": item.size,
                "mediaType": item.media_type,
                "manifestSha256": item.manifest_sha256,
            }
        except (RegistryError, PackageContractError) as error:
            return _registry_error(error)

    @router.post("/packages/inspect")
    def registry_inspect(request: PackageInspectRequest):
        from ai2apps.packages.contract_v1 import inspect_package

        try:
            item = inspect_package(request.archive_path)
            return {
                "archivePath": str(item.archive_path),
                "manifest": item.manifest,
                "sha256": item.sha256,
                "size": item.size,
                "mediaType": item.media_type,
                "manifestSha256": item.manifest_sha256,
            }
        except PackageContractError as error:
            return _registry_error(error)

    @router.post("/packages/publisher-keys")
    def registry_create_key(request: PublisherKeyCreateRequest):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return manager.create_key(request.name)
        except (RegistryError, ValueError) as error:
            if isinstance(error, RegistryError):
                return _registry_error(error)
            return platform_error_response(
                status_code=422, code="publisher_key_invalid", message=str(error)
            )

    @router.get("/packages/publisher-keys")
    def registry_keys():
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        return manager.keys()

    @router.post("/packages/publisher-keys/proof")
    def registry_key_proof(request: PublisherKeyProofRequest):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return {"signature": manager.key_proof(request.payload, request.key_ref)}
        except (RegistryError, PackageContractError) as error:
            return _registry_error(error)

    @router.post("/packages/sign")
    def registry_sign(request: RegistrySignRequest):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return manager.sign(
                request.archive_path,
                request.key_ref,
                request.publisher_id,
                request.publisher_key_id,
            )
        except (RegistryError, PackageContractError) as error:
            return _registry_error(error)

    @router.get("/packages/publishing/publishers")
    async def registry_publishers(request: Request):
        manager = publishing_registry_or_error(request)
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.publishers()
        except RegistryError as error:
            return _registry_error(error)

    @router.post("/packages/publishing/publishers")
    async def registry_create_publisher(
        request: CloudPublisherCreateRequest, browser_request: Request
    ):
        manager = publishing_registry_or_error(browser_request)
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.create_publisher(
                request.display_name, request.namespace, request.kind
            )
        except RegistryError as error:
            return _registry_error(error)

    @router.post("/packages/publishing/publishers/{publisher_id}/key-challenges")
    async def registry_create_key_challenge(
        publisher_id: str,
        request: CloudKeyChallengeRequest,
        browser_request: Request,
    ):
        manager = publishing_registry_or_error(browser_request)
        if isinstance(manager, JSONResponse):
            return manager
        try:
            challenge = await manager.create_key_challenge(
                publisher_id, request.key_ref
            )
            challenge["proofSignature"] = manager.key_proof(
                challenge["proofPayload"], request.key_ref
            )
            return challenge
        except (RegistryError, PackageContractError) as error:
            return _registry_error(error)

    @router.post("/packages/publishing/publishers/{publisher_id}/keys")
    async def registry_register_key(
        publisher_id: str,
        request: CloudKeyRegisterRequest,
        browser_request: Request,
    ):
        manager = publishing_registry_or_error(browser_request)
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.register_key(
                publisher_id, request.challenge_id, request.signature
            )
        except RegistryError as error:
            return _registry_error(error)

    @router.post("/packages/publishing/submissions")
    async def registry_submit(
        request: CloudSubmissionRequest, browser_request: Request
    ):
        manager = publishing_registry_or_error(browser_request)
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.submit(request.archive_path, request.envelope)
        except (RegistryError, PackageContractError) as error:
            return _registry_error(error)

    @router.get("/packages/publishing/context")
    async def registry_publishing_context(request: Request):
        manager = publishing_registry_or_error(request)
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.publishing_context()
        except RegistryError as error:
            return _registry_error(error)

    @router.post("/packages/publishing/admin/reauth")
    async def registry_admin_reauth(
        request: CloudAdminReauthRequest, browser_request: Request
    ):
        manager = publishing_registry_or_error(browser_request)
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.reauthenticate_admin(request.password)
        except RegistryError as error:
            return _registry_error(error)

    @router.get("/packages/publishing/submissions")
    async def registry_submissions(
        request: Request,
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
    ):
        manager = publishing_registry_or_error(request)
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.publisher_submissions(status=status, limit=limit)
        except RegistryError as error:
            return _registry_error(error)

    @router.get("/packages/publishing/review-submissions")
    async def registry_review_submissions(
        request: Request,
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
    ):
        manager = publishing_registry_or_error(request)
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.review_submissions(status=status, limit=limit)
        except RegistryError as error:
            return _registry_error(error)

    @router.get("/packages/publishing/submissions/{submission_id}")
    async def registry_submission(submission_id: str, request: Request):
        manager = publishing_registry_or_error(request)
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.submission(submission_id)
        except RegistryError as error:
            return _registry_error(error)

    @router.get("/packages/publishing/submissions/{submission_id}/details")
    async def registry_submission_details(submission_id: str, request: Request):
        manager = publishing_registry_or_error(request)
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.submission_details(submission_id)
        except RegistryError as error:
            return _registry_error(error)

    @router.post("/packages/publishing/submissions/{submission_id}/review-request")
    async def registry_request_review(submission_id: str, request: Request):
        manager = publishing_registry_or_error(request)
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.request_review(submission_id)
        except RegistryError as error:
            return _registry_error(error)

    @router.post("/packages/publishing/submissions/{submission_id}/reviews")
    async def registry_review_submission(
        submission_id: str,
        request: CloudSubmissionReviewRequest,
        browser_request: Request,
    ):
        manager = publishing_registry_or_error(browser_request)
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.review_submission(
                submission_id, request.decision, request.note
            )
        except RegistryError as error:
            return _registry_error(error)

    @router.post("/packages/publishing/submissions/{submission_id}/publication")
    async def registry_publish_submission(submission_id: str, request: Request):
        manager = publishing_registry_or_error(request)
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.publish_submission(submission_id)
        except RegistryError as error:
            return _registry_error(error)

    @router.post("/packages/{namespace}/{name}/download")
    async def registry_download(
        namespace: str, name: str, request: RegistryInstallRequest
    ):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            (
                item,
                _envelope,
                release,
                metadata_version,
            ) = await manager.download_verified(namespace, name, request.version)
            return {
                "archivePath": str(item.archive_path),
                "package": item.manifest["package"],
                "sha256": item.sha256,
                "size": item.size,
                "repositoryMetadataVersion": metadata_version,
                "publisher": release["publisher"],
                "verified": True,
            }
        except RegistryError as error:
            return _registry_error(error)

    @router.post("/packages/{namespace}/{name}/install")
    async def registry_install(
        namespace: str, name: str, request: RegistryInstallRequest
    ):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            item = await manager.install(
                namespace,
                name,
                request.version,
                approve_review=request.approve_review,
            )
            return _registry_install_result(item, namespace, name)
        except RegistryError as error:
            return _registry_error(error)

    @router.post(
        "/packages/{namespace}/{name}/install-operations",
        status_code=202,
    )
    async def registry_start_install_operation(
        namespace: str,
        name: str,
        request: RegistryInstallRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        # Retain a bounded amount of terminal history for the Discover UI.
        terminal = [
            key
            for key, value in install_operations.items()
            if value.get("status") in {"completed", "failed"}
        ]
        for stale_id in terminal[:-32]:
            install_operations.pop(stale_id, None)
        operation_id = uuid4().hex
        now = datetime.now(UTC).isoformat()
        operation = {
            "operationId": operation_id,
            "packageId": f"{namespace}/{name}",
            "status": "pending",
            "currentStep": 1,
            "totalSteps": 6,
            "stage": "preparing",
            "bytesCompleted": None,
            "bytesTotal": None,
            "result": None,
            "error": None,
            "createdAt": now,
            "updatedAt": now,
        }
        install_operations[operation_id] = operation
        task = asyncio.create_task(
            run_install_operation(
                operation_id, manager, namespace, name, request, principal
            )
        )
        install_tasks.add(task)
        task.add_done_callback(install_tasks.discard)
        return operation

    @router.get("/packages/install-continuation")
    async def registry_install_continuation(
        principal: RequestPrincipal = principal_dependency,
    ):
        repository = install_continuation_repository()
        continuation = None
        if repository is not None:
            continuation = repository.get(
                principal.actor_user_id, principal.installation_id
            )
        return {"continuation": continuation}

    @router.delete("/packages/install-continuation")
    async def clear_registry_install_continuation(
        principal: RequestPrincipal = principal_dependency,
    ):
        repository = install_continuation_repository()
        if repository is not None:
            repository.delete(principal.actor_user_id, principal.installation_id)
        return {"cleared": True}

    @router.get("/packages/install-operations/{operation_id}")
    async def registry_install_operation(operation_id: str):
        operation = install_operations.get(operation_id)
        if operation is None:
            return platform_error_response(
                status_code=404,
                code="install_operation_not_found",
                message="Package install operation was not found.",
            )
        return operation

    @router.post("/packages/{namespace}/{name}/uninstall")
    async def registry_uninstall(
        namespace: str, name: str, request: RegistryUninstallRequest
    ):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            result = await manager.uninstall(
                f"{namespace}/{name}",
                force=request.force,
                delete_checkpoints=request.delete_checkpoints,
            )
            return {
                "packageId": f"{namespace}/{name}",
                "status": "uninstalled",
                **result,
            }
        except RegistryError as error:
            return _registry_error(error)

    @router.get("/publishers")
    def list_publishers():
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        return {
            "items": [
                {
                    "publisher_key": item.publisher_key,
                    "display_name": item.display_name,
                    "key_id": item.key_id,
                    "algorithm": item.algorithm,
                    "public_key": item.public_key,
                    "trust_status": item.trust_status.value,
                    "source": item.source,
                    "metadata": item.metadata,
                    "revision": item.revision,
                }
                for item in runtime.package_repository.list_publishers()
            ]
        }

    @router.put("/publishers/{publisher_key}")
    def put_publisher(publisher_key: str, request: PublisherRequest):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            item = runtime.package_repository.upsert_publisher(
                publisher_key=publisher_key,
                display_name=request.display_name,
                key_id=request.key_id,
                public_key=request.public_key,
                trust_status=request.trust_status,
                source=request.source,
                metadata=request.metadata,
            )
            return {
                "publisher_key": item.publisher_key,
                "trust_status": item.trust_status.value,
                "revision": item.revision,
            }
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/service-packages/inspect")
    def inspect_package(request: PackageInspectRequest):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            item = runtime.package_manager.inspect(Path(request.archive_path))
            return {
                "service_key": item.manifest.service_key,
                "name": item.manifest.name,
                "version": item.manifest.version,
                "digest": item.digest,
                "publisher": item.manifest.publisher_key,
                "runtime_mode": item.manifest.runtime_mode.value,
                "permissions": item.manifest.permissions,
                "compatibility": item.manifest.compatibility,
                "files": [
                    {
                        "path": file.path,
                        "hash": file.content_hash,
                        "size": file.size_bytes,
                    }
                    for file in item.files
                ],
                "sbom": item.sbom,
            }
        except PackageError as error:
            return _error(error)

    @router.post("/service-packages/audit")
    async def audit_package(request: PackageInspectRequest):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            return await runtime.package_manager.audit(request.archive_path)
        except PackageError as error:
            return _error(error)

    @router.get("/service-packages")
    def list_packages():
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        return {
            "items": [_package(item) for item in runtime.package_repository.installed()]
        }

    @router.get("/service-packages/{digest:path}")
    def get_package(digest: str):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        digest = digest if digest.startswith("sha256:") else f"sha256:{digest}"
        try:
            item = runtime.package_repository.get_by_digest(digest)
            return {
                **_package(item),
                "manifest": item.manifest,
                "sbom": item.sbom,
                "files": list(runtime.package_repository.files(digest)),
                "attestations": [
                    {
                        "id": value.id,
                        "kind": value.kind,
                        "issuer": value.issuer,
                        "decision": value.decision.value,
                        "risk": value.risk.value,
                        "model": value.model,
                        "policy_version": value.policy_version,
                        "evidence": value.evidence,
                        "created_at": value.created_at.isoformat(),
                    }
                    for value in runtime.package_repository.attestations(digest)
                ],
                "dependency_locks": [
                    {
                        "dependency_key": lock.dependency_key,
                        "version": lock.dependency_version,
                        "digest": lock.dependency_digest,
                        "optional": lock.optional,
                    }
                    for lock in runtime.package_repository.locks(digest)
                ],
            }
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/service-packages/install")
    async def install_package(request: PackageInstallRequest):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            item = await runtime.package_manager.install(
                request.archive_path,
                dependency_archives=tuple(request.dependency_archives),
                allow_untrusted=request.allow_untrusted,
                approve_audit_review=request.approve_audit_review,
            )
            return _package(item)
        except PackageError as error:
            return _error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/services/{service_key}/rollback")
    async def rollback(service_key: str):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            return _package(await runtime.package_manager.rollback(service_key))
        except PackageError as error:
            return _error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/services/{service_key}/start")
    async def start_service(service_key: str):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            await runtime.package_manager.start(service_key)
            return {"status": "running", "service_key": service_key}
        except PackageError as error:
            return _error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/services/{service_key}/stop")
    async def stop_service(service_key: str):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            await runtime.package_manager.stop(service_key)
            return {"status": "stopped", "service_key": service_key}
        except PackageError as error:
            return _error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.delete("/services/{service_key}/package")
    async def uninstall(service_key: str):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            await runtime.package_manager.uninstall(service_key)
            return {"status": "uninstalled", "service_key": service_key}
        except PackageError as error:
            return _error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get("/services/{service_key}/logs")
    def service_logs(service_key: str, after: int = 0, limit: int = 200):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        return {
            "items": runtime.package_repository.logs(
                service_key, after=max(0, after), limit=min(1000, max(1, limit))
            )
        }

    return router
