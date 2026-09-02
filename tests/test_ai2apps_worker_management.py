# SPDX-License-Identifier: Apache-2.0
"""Model Worker management API and Dashboard contract tests."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from ai2apps.api.workers import create_worker_router
from ai2apps.events import EventStore
from ai2apps.identity import RequestPrincipal
from ai2apps.packages.models import PackageStatus
from ai2apps.storage import PlatformDatabase
from ai2apps.worker_management import WorkerManagementRepository
from ai2apps.worker_resources import (
    GIB,
    SystemMemorySnapshot,
    WorkerResourceConfig,
    WorkerResourceManager,
)
from ai2apps.worker_scheduler import WorkerJobScheduler


class _Supervisor:
    def __init__(self, package):
        self.package = package
        self.generation = 3
        self.state = "stopped"
        self.draining = False
        self.idle_gate = None

    def assert_worker_generation(self, _service_key, expected):
        if expected != self.generation:
            from ai2apps.packages import PackageError

            raise PackageError("worker_generation_conflict", "stale generation")

    async def worker_snapshot(self, _package):
        return {
            "serviceKey": self.package.service_key,
            "packageVersion": self.package.package_version,
            "packageDigest": self.package.package_digest,
            "generation": self.generation,
            "state": "draining" if self.draining else self.state,
            "acceptingRequests": self.state == "ready" and not self.draining,
            "activeRequests": 0,
            "queuedRequests": 0,
            "pid": 123 if self.state != "stopped" else None,
            "residentMemoryBytes": 1024 if self.state != "stopped" else 0,
            "endpoint": None,
            "models": [],
            "lastError": None,
        }

    async def drain_worker(self, _service_key):
        self.draining = True

    async def wait_worker_idle(self, _package):
        if self.idle_gate is not None:
            await self.idle_gate.wait()
        return None

    async def resume_worker(self, _service_key):
        self.draining = False


class _Manager:
    def __init__(self, supervisor):
        self.supervisor = supervisor

    async def start(self, _service_key):
        self.supervisor.generation += 1
        self.supervisor.state = "ready"

    async def stop(self, _service_key):
        self.supervisor.state = "stopped"
        self.supervisor.draining = False


class _Resources:
    def __init__(self):
        self.pinned = set()

    def mark_started(self, _service_key):
        return None

    def set_pinned(self, service_key, pinned):
        if pinned:
            self.pinned.add(service_key)
        else:
            self.pinned.discard(service_key)

    def snapshot(self):
        return {
            "reservedByWorker": {},
            "reservedTransientBytes": 0,
            "availableMemoryBytes": 8 * 1024**3,
            "pinnedWorkers": sorted(self.pinned),
        }


def _app(worker_resources=None, worker_management=None):
    package = SimpleNamespace(
        service_key="example.worker",
        package_version="1.0.0",
        package_digest="sha256:example",
        protocol="ai2apps-model-worker/v1",
        status=PackageStatus.ACTIVE,
        manifest={"models": [{"model_type": "llm", "metadata": {}}]},
    )
    repository = SimpleNamespace(
        installed=lambda: (package,),
        active=lambda service_key: package if service_key == package.service_key else None,
    )
    supervisor = _Supervisor(package)
    resources = worker_resources or _Resources()
    runtime = SimpleNamespace(
        package_repository=repository,
        package_manager=_Manager(supervisor),
        worker_scheduler=WorkerJobScheduler(
            resource_manager=(
                resources if isinstance(resources, WorkerResourceManager) else None
            )
        ),
        worker_resources=resources,
        worker_management=worker_management,
    )
    app = FastAPI()
    app.include_router(
        create_worker_router(
            lambda: runtime,
            principal_provider=RequestPrincipal.legacy_local,
        ),
        prefix="/v1/platform",
    )
    return app, supervisor


def _low_memory_resources():
    return WorkerResourceManager(
        WorkerResourceConfig(admission_wait_seconds=0.01),
        sampler=lambda: SystemMemorySnapshot(
            total_bytes=8 * GIB,
            available_bytes=1 * GIB,
            used_bytes=7 * GIB,
            pressure_level="hard",
        ),
    )


def _durable_management(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    events = EventStore(database)
    return WorkerManagementRepository(database, events), events


@pytest.mark.asyncio
async def test_worker_api_lists_loads_and_safely_exits():
    app, supervisor = _app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        listed = await client.get("/v1/platform/workers")
        scheduler = await client.get("/v1/platform/worker-scheduler")
        resources = await client.get("/v1/platform/worker-resources")
        loaded = await client.post(
            "/v1/platform/workers/example.worker/load",
            json={"expectedGeneration": 3},
        )
        exited = await client.post(
            "/v1/platform/workers/example.worker/exit",
            json={"expectedGeneration": 4, "mode": "immediate"},
        )

    assert listed.status_code == 200
    assert scheduler.status_code == 200
    assert scheduler.json()["maxHeavyComputeSlots"] == 1
    assert resources.status_code == 200
    assert resources.json()["availableMemoryBytes"] == 8 * 1024**3
    assert listed.json()["items"][0]["state"] == "stopped"
    assert loaded.status_code == 200
    assert loaded.json()["state"] == "ready"
    assert exited.status_code == 200
    assert exited.json()["state"] == "stopped"
    assert supervisor.state == "stopped"


@pytest.mark.asyncio
async def test_worker_api_runs_drain_and_exit_as_operation():
    app, supervisor = _app()
    supervisor.state = "ready"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        started = await client.post(
            "/v1/platform/workers/example.worker/exit",
            json={"expectedGeneration": 3, "mode": "drain"},
        )
        assert started.status_code == 202
        operation_id = started.json()["operationId"]
        for _ in range(20):
            result = await client.get(
                f"/v1/platform/worker-operations/{operation_id}"
            )
            if result.json()["status"] == "completed":
                break
            await asyncio.sleep(0)

    assert result.json()["status"] == "completed"
    assert supervisor.state == "stopped"


@pytest.mark.asyncio
async def test_failed_drain_and_exit_resumes_worker(monkeypatch):
    from ai2apps.packages import PackageError

    app, supervisor = _app()
    supervisor.state = "ready"

    async def blocked_stop(self, _service_key):
        raise PackageError(
            "service_has_dependents",
            "Required dependents prevent stopping this Service",
        )

    monkeypatch.setattr(_Manager, "stop", blocked_stop)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        started = await client.post(
            "/v1/platform/workers/example.worker/exit",
            json={"expectedGeneration": 3, "mode": "drain"},
        )
        operation_id = started.json()["operationId"]
        for _ in range(20):
            result = await client.get(
                f"/v1/platform/worker-operations/{operation_id}"
            )
            if result.json()["status"] == "failed":
                break
            await asyncio.sleep(0)

    assert result.json()["error"]["code"] == "service_has_dependents"
    assert supervisor.draining is False
    assert supervisor.state == "ready"


@pytest.mark.asyncio
async def test_drain_operation_is_durable_and_idempotent(tmp_path):
    management, events = _durable_management(tmp_path)
    app, supervisor = _app(worker_management=management)
    supervisor.state = "ready"
    payload = {
        "expectedGeneration": 3,
        "mode": "drain",
        "idempotencyKey": "drain-operation-0001",
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        started = await client.post(
            "/v1/platform/workers/example.worker/exit", json=payload
        )
        replayed = await client.post(
            "/v1/platform/workers/example.worker/exit", json=payload
        )
        operation_id = started.json()["operationId"]
        for _ in range(20):
            result = await client.get(
                f"/v1/platform/worker-operations/{operation_id}"
            )
            if result.json()["status"] == "completed":
                break
            await asyncio.sleep(0)

    assert replayed.json()["operationId"] == operation_id
    assert result.json()["status"] == "completed"
    assert management.get(operation_id)["status"] == "completed"
    audit_types = {
        event.type for event in events.list_after(subject_id="example.worker")
    }
    assert "worker.operation.created" in audit_types
    assert "worker.operation.updated" in audit_types


@pytest.mark.asyncio
async def test_running_drain_operation_can_be_cancelled_and_resumes_worker(tmp_path):
    management, _events = _durable_management(tmp_path)
    app, supervisor = _app(worker_management=management)
    supervisor.state = "ready"
    supervisor.idle_gate = asyncio.Event()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        started = await client.post(
            "/v1/platform/workers/example.worker/exit",
            json={"expectedGeneration": 3, "mode": "drain"},
        )
        operation_id = started.json()["operationId"]
        for _ in range(20):
            if supervisor.draining:
                break
            await asyncio.sleep(0)
        cancelled = await client.post(
            f"/v1/platform/worker-operations/{operation_id}/cancel"
        )

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["error"]["code"] == "operator_cancelled"
    assert supervisor.draining is False
    assert supervisor.state == "ready"


@pytest.mark.asyncio
async def test_worker_api_pins_and_unpins_with_generation_guard():
    app, _supervisor = _app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        pinned = await client.post(
            "/v1/platform/workers/example.worker/pin",
            json={"expectedGeneration": 3, "pinned": True},
        )
        listed = await client.get("/v1/platform/workers")
        stale = await client.post(
            "/v1/platform/workers/example.worker/pin",
            json={"expectedGeneration": 2, "pinned": False},
        )
        unpinned = await client.post(
            "/v1/platform/workers/example.worker/pin",
            json={"expectedGeneration": 3, "pinned": False},
        )

    assert pinned.status_code == 200
    assert pinned.json()["pinned"] is True
    assert listed.json()["items"][0]["pinned"] is True
    assert stale.status_code == 409
    assert unpinned.status_code == 200
    assert unpinned.json()["pinned"] is False


@pytest.mark.asyncio
async def test_pin_preference_and_operation_survive_repository_recreation(tmp_path):
    management, _events = _durable_management(tmp_path)
    app, _supervisor = _app(worker_management=management)
    payload = {
        "expectedGeneration": 3,
        "pinned": True,
        "idempotencyKey": "pin-operation-0001",
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post(
            "/v1/platform/workers/example.worker/pin", json=payload
        )
        replay = await client.post(
            "/v1/platform/workers/example.worker/pin", json=payload
        )

    operation_id = first.json()["operationId"]
    restored = WorkerManagementRepository(management.database, management.events)
    assert replay.json()["operationId"] == operation_id
    assert restored.pinned_workers() == ("example.worker",)
    assert restored.get(operation_id)["status"] == "completed"


def test_running_operation_is_marked_interrupted_after_host_restart(tmp_path):
    management, _events = _durable_management(tmp_path)
    operation = management.begin(
        "example.worker",
        "drain_and_exit",
        expected_generation=3,
        idempotency_key="restart-operation-0001",
    )
    management.update(operation["operationId"], "running")

    restored = WorkerManagementRepository(management.database, management.events)
    assert restored.recover_interrupted() == 1
    recovered = restored.get(operation["operationId"])
    assert recovered["status"] == "interrupted"
    assert recovered["error"]["code"] == "runtime_restarted"


@pytest.mark.asyncio
async def test_manual_load_fails_closed_when_cold_start_memory_does_not_fit():
    resources = _low_memory_resources()
    app, supervisor = _app(resources)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/v1/platform/workers/example.worker/load",
            json={"expectedGeneration": 3},
        )

    assert result.status_code == 503
    assert result.headers["Retry-After"] == "5"
    assert result.json()["error"]["code"] == "worker_resource_unavailable"
    assert supervisor.state == "stopped"
    assert resources.snapshot()["activeReservations"] == 0


@pytest.mark.asyncio
async def test_manual_load_reserves_cold_start_memory_and_releases_it():
    resources = WorkerResourceManager(
        sampler=lambda: SystemMemorySnapshot(
            total_bytes=16 * GIB,
            available_bytes=12 * GIB,
            used_bytes=4 * GIB,
            pressure_level="ok",
        )
    )
    app, supervisor = _app(resources)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        loaded = await client.post(
            "/v1/platform/workers/example.worker/load",
            json={"expectedGeneration": 3},
        )
        already_ready = await client.post(
            "/v1/platform/workers/example.worker/load",
            json={"expectedGeneration": 4},
        )

    snapshot = resources.snapshot()
    assert loaded.status_code == 200
    assert already_ready.status_code == 200
    assert supervisor.state == "ready"
    assert snapshot["admitted"] == 1
    assert snapshot["activeReservations"] == 0
    assert snapshot["reservedTotalBytes"] == 0


@pytest.mark.asyncio
async def test_load_and_immediate_exit_are_persisted_and_listable(tmp_path):
    management, _events = _durable_management(tmp_path)
    resources = WorkerResourceManager(
        sampler=lambda: SystemMemorySnapshot(
            total_bytes=16 * GIB,
            available_bytes=12 * GIB,
            used_bytes=4 * GIB,
            pressure_level="ok",
        )
    )
    app, supervisor = _app(resources, management)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        loaded = await client.post(
            "/v1/platform/workers/example.worker/load",
            json={
                "expectedGeneration": 3,
                "idempotencyKey": "load-operation-0001",
            },
        )
        exited = await client.post(
            "/v1/platform/workers/example.worker/exit",
            json={
                "expectedGeneration": 4,
                "mode": "immediate",
                "idempotencyKey": "exit-operation-0001",
            },
        )
        listed = await client.get(
            "/v1/platform/worker-operations",
            params={"service_key": "example.worker"},
        )
        replayed_load = await client.post(
            "/v1/platform/workers/example.worker/load",
            json={
                "expectedGeneration": 3,
                "idempotencyKey": "load-operation-0001",
            },
        )
        conflicting_load = await client.post(
            "/v1/platform/workers/example.worker/load",
            json={
                "expectedGeneration": 4,
                "idempotencyKey": "load-operation-0001",
            },
        )

    assert loaded.status_code == 200
    assert exited.status_code == 200
    assert replayed_load.status_code == 200
    assert replayed_load.json()["state"] == "ready"
    assert conflicting_load.status_code == 409
    assert conflicting_load.json()["error"]["code"] == "worker_idempotency_conflict"
    assert supervisor.state == "stopped"
    operations = listed.json()["items"]
    assert {item["action"] for item in operations} == {"load", "exit"}
    assert all(item["status"] == "completed" for item in operations)


@pytest.mark.asyncio
async def test_failed_manual_load_is_persisted_without_reservation_leak(tmp_path):
    management, _events = _durable_management(tmp_path)
    resources = _low_memory_resources()
    app, supervisor = _app(resources, management)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        failed = await client.post(
            "/v1/platform/workers/example.worker/load",
            json={
                "expectedGeneration": 3,
                "idempotencyKey": "load-operation-low-memory",
            },
        )
        listed = await client.get("/v1/platform/worker-operations")

    assert failed.status_code == 503
    operation = listed.json()["items"][0]
    assert operation["action"] == "load"
    assert operation["status"] == "failed"
    assert operation["error"]["code"] == "worker_resource_unavailable"
    assert supervisor.state == "stopped"
    assert resources.snapshot()["activeReservations"] == 0


def test_dashboard_has_independent_model_worker_controls():
    root = Path(__file__).parents[1]
    template = (root / "ai2apps/web/templates/dashboard/_status.html").read_text()
    script = (root / "ai2apps/web/static/js/dashboard.js").read_text()

    assert "Model Workers" in template
    assert "Drain & Exit" in template
    assert "modelWorkerPin(worker)" in template
    assert "modelWorkerAction(worker, 'exit', 'immediate')" in template
    assert "modelWorkerCancelOperation(worker)" in template
    assert "backgroundPauseReasons" in template
    assert "'/v1/platform/workers'" in script
    assert "/v1/platform/worker-operations/" in script
    assert "operation.status === 'cancelled'" in script
    assert "/cancel`" in script
    assert "idempotencyKey" in script
