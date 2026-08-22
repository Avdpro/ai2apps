"""Trusted Service package, publisher, audit, logs, and lifecycle APIs."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai2apps.api.errors import platform_error_response, repository_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import (
    PrincipalProvider,
    require_app_capability,
    resolve_request_principal,
)
from ai2apps.apps.access import APP_SYSTEM_MANAGE
from ai2apps.core import RepositoryError
from ai2apps.http_security import enforce_same_origin_cookie_request
from ai2apps.packages import PackageError, TrustStatus
from ai2apps.packages.contract_v1 import PackageContractError
from ai2apps.packages.registry import RegistryError


class PublisherRequest(BaseModel):
    display_name: str = Field(min_length=1)
    key_id: str = Field(min_length=1)
    public_key: str = Field(min_length=1)
    trust_status: TrustStatus
    source: str = "user"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PackageInspectRequest(BaseModel):
    archive_path: str = Field(min_length=1)


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


class RegistryUninstallRequest(BaseModel):
    force: bool = False


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
    password: str = Field(min_length=12, max_length=128)


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
        status = upstream_status if upstream_status in {400, 401, 403, 404, 409, 413, 422, 429, 503} else None
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
    model_ids = [
        model.get("id")
        for model in getattr(item, "manifest", {}).get("models", [])
        if isinstance(model, dict)
        and isinstance(model.get("id"), str)
        and isinstance(model.get("weights"), dict)
    ]
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
        "modelConfigurationId": model_ids[0] if model_ids else None,
        "restartRequired": pending_runtime_restart,
        "restartScope": "local" if pending_runtime_restart else None,
    }


def create_package_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
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
    ) -> None:
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
        except RegistryError as error:
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

    def publishing_registry_or_error(request: Request):
        """Return a Registry manager bound to this browser's Cloud session."""

        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        runtime = runtime_provider()
        enforce_same_origin_cookie_request(request)
        cookie_reader = getattr(
            runtime, "cloud_browser_session_from_cookies", None
        )
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
        publisher: str | None = None,
        sort: str = Query(default="recommended", pattern="^(recommended|relevance|rating|newest)$"),
        limit: int = Query(default=24, ge=1, le=100),
        cursor: str | None = None,
    ):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.search(q=q, type=type, publisher=publisher, sort=sort, limit=limit, cursor=cursor)
        except RegistryError as error:
            return _registry_error(error)

    @router.get("/packages/catalog/recommendations")
    async def registry_recommendations(
        type: str | None = Query(default=None, pattern="^(app|agent|service)$"),
        limit: int = Query(default=24, ge=1, le=100),
        cursor: str | None = None,
    ):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.recommendations(type=type, limit=limit, cursor=cursor)
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

    @router.get("/packages/installed")
    def registry_installed(locale: str | None = Query(default=None, max_length=64)):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        return {"items": manager.installed(locale=locale)}

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
            return platform_error_response(status_code=422, code="publisher_key_invalid", message=str(error))

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
            return await manager.create_publisher(request.display_name, request.namespace, request.kind)
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
            challenge = await manager.create_key_challenge(publisher_id, request.key_ref)
            challenge["proofSignature"] = manager.key_proof(challenge["proofPayload"], request.key_ref)
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
            return await manager.register_key(publisher_id, request.challenge_id, request.signature)
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
    async def registry_download(namespace: str, name: str, request: RegistryInstallRequest):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            item, _envelope, release, metadata_version = await manager.download_verified(namespace, name, request.version)
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
    async def registry_install(namespace: str, name: str, request: RegistryInstallRequest):
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
            run_install_operation(operation_id, manager, namespace, name, request)
        )
        install_tasks.add(task)
        task.add_done_callback(install_tasks.discard)
        return operation

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
    async def registry_uninstall(namespace: str, name: str, request: RegistryUninstallRequest):
        manager = registry_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            await manager.uninstall(f"{namespace}/{name}", force=request.force)
            return {"packageId": f"{namespace}/{name}", "status": "uninstalled"}
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
