"""Model Worker observability and safe lifecycle management APIs."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

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
from ai2apps.model_providers import estimate_service_models_resident_bytes
from ai2apps.packages import PackageError
from ai2apps.packages.models import PackageStatus
from ai2apps.worker_management import WorkerOperationIdempotencyConflictError
from ai2apps.worker_resources import MIB, WorkerPinnedLimitError
from ai2apps.worker_scheduler import WorkloadClass


class WorkerLoadRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    expected_generation: int | None = Field(
        default=None, alias="expectedGeneration", ge=0
    )
    idempotency_key: str | None = Field(
        default=None, alias="idempotencyKey", min_length=8, max_length=128
    )


class WorkerExitRequest(WorkerLoadRequest):
    mode: str = Field(default="drain", pattern="^(drain|immediate)$")


class WorkerPinRequest(WorkerLoadRequest):
    pinned: bool


def create_worker_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(
        dependencies=[
            Depends(require_app_capability(principal_provider, APP_SYSTEM_MANAGE))
        ]
    )
    operations: dict[str, dict[str, Any]] = {}
    operation_tasks: dict[str, asyncio.Task[None]] = {}

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

    def worker_package(runtime, service_key: str):
        package = runtime.package_repository.active(service_key)
        if package is None or package.protocol != "ai2apps-model-worker/v1":
            raise PackageError(
                "model_worker_not_found",
                f"Active Model Worker Package was not found: {service_key}",
            )
        return package

    def worker_error(error: PackageError) -> JSONResponse:
        status = {
            "model_worker_not_found": 404,
            "worker_generation_conflict": 409,
            "worker_busy": 409,
            "worker_state_unavailable": 503,
        }.get(error.code, 422)
        return platform_error_response(
            status_code=status,
            code=error.code,
            message=str(error),
            details=error.details,
            retryable=error.code == "worker_state_unavailable",
        )

    def idempotency_error(error: WorkerOperationIdempotencyConflictError):
        return platform_error_response(
            status_code=409,
            code="worker_idempotency_conflict",
            message=str(error),
        )

    async def snapshots(runtime) -> list[dict[str, Any]]:
        packages = [
            package
            for package in runtime.package_repository.installed()
            if package.status is PackageStatus.ACTIVE
            and package.protocol == "ai2apps-model-worker/v1"
        ]
        items = list(
            await asyncio.gather(
                *(
                    runtime.package_manager.supervisor.worker_snapshot(package)
                    for package in packages
                )
            )
        )
        scheduler = getattr(runtime, "worker_scheduler", None)
        scheduler_workers = {}
        if scheduler is not None:
            scheduler_workers = (await scheduler.snapshot()).get("workers", {})
        resource_manager = getattr(runtime, "worker_resources", None)
        resource_snapshot = (
            resource_manager.snapshot() if resource_manager is not None else {}
        )
        reserved_by_worker = resource_snapshot.get("reservedByWorker", {})
        pinned_workers = set(resource_snapshot.get("pinnedWorkers", []))
        evicting_workers = set(resource_snapshot.get("evictingWorkers", []))
        idle_ages = resource_snapshot.get("lastUsedAgeSecondsByWorker", {})
        for item in items:
            item["scheduler"] = scheduler_workers.get(
                item["serviceKey"],
                {
                    "queued": 0,
                    "running": 0,
                    "queuedByClass": {},
                    "runningByClass": {},
                },
            )
            item["resources"] = {
                "reservedTransientBytes": reserved_by_worker.get(
                    item["serviceKey"], 0
                ),
                "idleAgeSeconds": idle_ages.get(item["serviceKey"]),
            }
            item["pinned"] = item["serviceKey"] in pinned_workers
            if item["serviceKey"] in evicting_workers:
                item["state"] = "evicting"
        return items

    def operation(
        runtime,
        service_key: str,
        action: str,
        *,
        expected_generation: int | None,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        management = getattr(runtime, "worker_management", None)
        if management is not None:
            return management.begin(
                service_key,
                action,
                expected_generation=expected_generation,
                idempotency_key=idempotency_key,
            )
        now = datetime.now(UTC).isoformat()
        value = {
            "operationId": f"worker-operation-{uuid4().hex}",
            "serviceKey": service_key,
            "action": action,
            "status": "pending",
            "createdAt": now,
            "updatedAt": now,
            "error": None,
            "_reused": False,
        }
        operations[value["operationId"]] = value
        return value

    def update_operation(runtime, value: dict[str, Any], **changes: Any) -> None:
        management = getattr(runtime, "worker_management", None)
        if management is not None:
            updated = management.update(
                value["operationId"],
                changes["status"],
                result=changes.get("result"),
                error=changes.get("error"),
            )
            value.clear()
            value.update(updated)
            return
        value.update(changes)
        value["updatedAt"] = datetime.now(UTC).isoformat()

    async def run_drain_exit(runtime, package, value: dict[str, Any]) -> None:
        update_operation(runtime, value, status="running")
        supervisor = runtime.package_manager.supervisor
        try:
            await supervisor.drain_worker(package.service_key)
            await asyncio.wait_for(supervisor.wait_worker_idle(package), timeout=300)
            await runtime.package_manager.stop(package.service_key)
            update_operation(
                runtime,
                value,
                status="completed",
                result=await supervisor.worker_snapshot(package),
            )
        except asyncio.CancelledError:
            with suppress(Exception):
                await supervisor.resume_worker(package.service_key)
            update_operation(
                runtime,
                value,
                status="cancelled",
                error={
                    "code": "operator_cancelled",
                    "message": "Drain and exit was cancelled by an administrator",
                },
            )
            raise
        except TimeoutError:
            with suppress(Exception):
                await supervisor.resume_worker(package.service_key)
            update_operation(
                runtime,
                value,
                status="failed",
                error={
                    "code": "worker_drain_timeout",
                    "message": "Model Worker did not become idle within 300 seconds",
                },
            )
        except Exception as error:
            with suppress(Exception):
                await supervisor.resume_worker(package.service_key)
            update_operation(
                runtime,
                value,
                status="failed",
                error={
                    "code": getattr(error, "code", "worker_exit_failed"),
                    "message": str(error),
                },
            )

    @router.get("/workers")
    async def list_workers():
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            return {"items": await snapshots(runtime)}
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get("/worker-scheduler")
    async def get_worker_scheduler():
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        scheduler = getattr(runtime, "worker_scheduler", None)
        if scheduler is None:
            return platform_error_response(
                status_code=503,
                code="worker_scheduler_not_ready",
                message="Model Worker scheduler is not ready.",
                retryable=True,
            )
        return await scheduler.snapshot()

    @router.get("/worker-resources")
    def get_worker_resources():
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        resource_manager = getattr(runtime, "worker_resources", None)
        if resource_manager is None:
            return platform_error_response(
                status_code=503,
                code="worker_resources_not_ready",
                message="Model Worker resource manager is not ready.",
                retryable=True,
            )
        return resource_manager.snapshot()

    @router.get("/workers/{service_key}")
    async def get_worker(service_key: str):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            package = worker_package(runtime, service_key)
            return await runtime.package_manager.supervisor.worker_snapshot(package)
        except PackageError as error:
            return worker_error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/workers/{service_key}/load")
    async def load_worker(
        service_key: str,
        control: WorkerLoadRequest,
        browser_request: Request,
    ):
        enforce_same_origin_cookie_request(browser_request)
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        value = None
        try:
            package = worker_package(runtime, service_key)
            supervisor = runtime.package_manager.supervisor
            management = getattr(runtime, "worker_management", None)
            if management is not None:
                replayed = management.replay(
                    service_key,
                    "load",
                    expected_generation=control.expected_generation,
                    idempotency_key=control.idempotency_key,
                )
                if replayed is not None:
                    if replayed["status"] == "completed" and isinstance(
                        replayed.get("result"), dict
                    ):
                        return replayed["result"]
                    return JSONResponse(status_code=202, content=replayed)
            supervisor.assert_worker_generation(service_key, control.expected_generation)
            value = operation(
                runtime,
                service_key,
                "load",
                expected_generation=control.expected_generation,
                idempotency_key=control.idempotency_key,
            )
            reused = value.pop("_reused", False)
            if reused:
                if value["status"] == "completed" and isinstance(
                    value.get("result"), dict
                ):
                    return value["result"]
                return JSONResponse(status_code=202, content=value)
            snapshot = await supervisor.worker_snapshot(package)
            if snapshot["state"] in {"ready", "busy"}:
                update_operation(runtime, value, status="completed", result=snapshot)
                return snapshot
            update_operation(runtime, value, status="running")
            scheduler = getattr(runtime, "worker_scheduler", None)
            lease = None
            if scheduler is not None:
                try:
                    lease = await scheduler.acquire(
                        service_key,
                        WorkloadClass.MAINTENANCE,
                        request_id=f"manual-load-{uuid4().hex}",
                        estimated_resident_bytes=estimate_service_models_resident_bytes(
                            package.manifest.get("models", [])
                        ),
                        estimated_transient_bytes=256 * MIB,
                    )
                except TimeoutError:
                    update_operation(
                        runtime,
                        value,
                        status="failed",
                        error={
                            "code": "worker_resource_unavailable",
                            "message": "Worker resources are temporarily unavailable",
                        },
                    )
                    response = platform_error_response(
                        status_code=503,
                        code="worker_resource_unavailable",
                        message="Worker resources are temporarily unavailable.",
                        retryable=True,
                    )
                    response.headers["Retry-After"] = "5"
                    return response
            try:
                # State may have changed while waiting for a scheduler slot.
                supervisor.assert_worker_generation(
                    service_key, control.expected_generation
                )
                await runtime.package_manager.start(service_key)
            except BaseException as error:
                update_operation(
                    runtime,
                    value,
                    status="failed",
                    error={
                        "code": getattr(error, "code", "worker_start_failed"),
                        "message": str(error),
                    },
                )
                raise
            finally:
                if lease is not None:
                    await lease.release()
            resources = getattr(runtime, "worker_resources", None)
            if resources is not None:
                resources.mark_started(service_key)
            result = await supervisor.worker_snapshot(package)
            update_operation(runtime, value, status="completed", result=result)
            return result
        except PackageError as error:
            return worker_error(error)
        except WorkerOperationIdempotencyConflictError as error:
            return idempotency_error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/workers/{service_key}/exit")
    async def exit_worker(
        service_key: str,
        control: WorkerExitRequest,
        browser_request: Request,
    ):
        enforce_same_origin_cookie_request(browser_request)
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        immediate_value = None
        try:
            package = worker_package(runtime, service_key)
            supervisor = runtime.package_manager.supervisor
            supervisor.assert_worker_generation(service_key, control.expected_generation)
            if control.mode == "immediate":
                immediate_value = operation(
                    runtime,
                    service_key,
                    "exit",
                    expected_generation=control.expected_generation,
                    idempotency_key=control.idempotency_key,
                )
                reused = immediate_value.pop("_reused", False)
                if reused:
                    if immediate_value["status"] == "completed" and isinstance(
                        immediate_value.get("result"), dict
                    ):
                        return immediate_value["result"]
                    return JSONResponse(status_code=202, content=immediate_value)
            value = None
            if control.mode == "drain":
                value = operation(
                    runtime,
                    service_key,
                    "drain_and_exit",
                    expected_generation=control.expected_generation,
                    idempotency_key=control.idempotency_key,
                )
                reused = value.pop("_reused", False)
                if reused:
                    return JSONResponse(status_code=202, content=value)
            snapshot = await supervisor.worker_snapshot(package)
            if snapshot["state"] == "stopped":
                if immediate_value is not None:
                    update_operation(
                        runtime,
                        immediate_value,
                        status="completed",
                        result=snapshot,
                    )
                    return snapshot
                if value is not None:
                    update_operation(
                        runtime, value, status="completed", result=snapshot
                    )
                    return JSONResponse(status_code=202, content=value)
                return snapshot
            if control.mode == "immediate":
                if snapshot["activeRequests"] is None or snapshot["queuedRequests"] is None:
                    raise PackageError(
                        "worker_state_unavailable",
                        "Cannot verify that the Model Worker is idle",
                    )
                if snapshot["activeRequests"] or snapshot["queuedRequests"]:
                    update_operation(
                        runtime,
                        immediate_value,
                        status="failed",
                        error={
                            "code": "worker_busy",
                            "message": "Model Worker has active or queued requests",
                        },
                    )
                    raise PackageError(
                        "worker_busy",
                        "Model Worker has active or queued requests; use drain-and-exit",
                        details={
                            "activeRequests": snapshot["activeRequests"],
                            "queuedRequests": snapshot["queuedRequests"],
                        },
                    )
                update_operation(runtime, immediate_value, status="running")
                try:
                    await runtime.package_manager.stop(service_key)
                except BaseException as error:
                    update_operation(
                        runtime,
                        immediate_value,
                        status="failed",
                        error={
                            "code": getattr(error, "code", "worker_exit_failed"),
                            "message": str(error),
                        },
                    )
                    raise
                result = await supervisor.worker_snapshot(package)
                update_operation(
                    runtime, immediate_value, status="completed", result=result
                )
                return result
            assert value is not None
            task = asyncio.create_task(
                run_drain_exit(runtime, package, value),
                name=f"worker-drain-{service_key}",
            )
            operation_tasks[value["operationId"]] = task
            task.add_done_callback(
                lambda _task, operation_id=value["operationId"]: operation_tasks.pop(
                    operation_id, None
                )
            )
            return JSONResponse(status_code=202, content=value)
        except PackageError as error:
            return worker_error(error)
        except WorkerOperationIdempotencyConflictError as error:
            return idempotency_error(error)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/workers/{service_key}/pin")
    async def pin_worker(
        service_key: str,
        control: WorkerPinRequest,
        browser_request: Request,
    ):
        enforce_same_origin_cookie_request(browser_request)
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            worker_package(runtime, service_key)
            runtime.package_manager.supervisor.assert_worker_generation(
                service_key, control.expected_generation
            )
            resources = getattr(runtime, "worker_resources", None)
            if resources is None:
                return platform_error_response(
                    status_code=503,
                    code="worker_resources_not_ready",
                    message="Model Worker resource manager is not ready.",
                    retryable=True,
                )
            management = getattr(runtime, "worker_management", None)
            operation_id = None
            assert_can_pin = getattr(resources, "assert_can_pin", None)
            if assert_can_pin is not None:
                assert_can_pin(service_key, control.pinned)
            if management is not None:
                value = management.apply_pin(
                    service_key,
                    control.pinned,
                    expected_generation=control.expected_generation,
                    idempotency_key=control.idempotency_key,
                )
                operation_id = value["operationId"]
            resources.set_pinned(service_key, control.pinned)
            return {
                "serviceKey": service_key,
                "pinned": control.pinned,
                "operationId": operation_id,
            }
        except PackageError as error:
            return worker_error(error)
        except WorkerOperationIdempotencyConflictError as error:
            return idempotency_error(error)
        except WorkerPinnedLimitError as error:
            return platform_error_response(
                status_code=409,
                code=error.code,
                message=str(error),
            )
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get("/worker-operations")
    def list_worker_operations(
        service_key: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        management = getattr(runtime, "worker_management", None)
        if management is not None:
            return {
                "items": list(
                    management.list(service_key=service_key, limit=limit)
                )
            }
        values = list(operations.values())
        if service_key is not None:
            values = [
                value for value in values if value["serviceKey"] == service_key
            ]
        return {"items": values[-limit:][::-1]}

    @router.get("/worker-operations/{operation_id}")
    def get_worker_operation(operation_id: str):
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        management = getattr(runtime, "worker_management", None)
        value = (
            management.get(operation_id)
            if management is not None
            else operations.get(operation_id)
        )
        if value is None:
            return platform_error_response(
                status_code=404,
                code="worker_operation_not_found",
                message="Model Worker operation was not found.",
            )
        return value

    @router.post("/worker-operations/{operation_id}/cancel")
    async def cancel_worker_operation(operation_id: str, browser_request: Request):
        enforce_same_origin_cookie_request(browser_request)
        runtime = runtime_or_error()
        if isinstance(runtime, JSONResponse):
            return runtime
        management = getattr(runtime, "worker_management", None)
        value = (
            management.get(operation_id)
            if management is not None
            else operations.get(operation_id)
        )
        if value is None:
            return platform_error_response(
                status_code=404,
                code="worker_operation_not_found",
                message="Model Worker operation was not found.",
            )
        task = operation_tasks.get(operation_id)
        if value["status"] not in {"pending", "running"} or task is None:
            return platform_error_response(
                status_code=409,
                code="worker_operation_not_cancellable",
                message="Model Worker operation cannot be cancelled in its current state.",
            )
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        return (
            management.get(operation_id)
            if management is not None
            else operations[operation_id]
        )

    return router
