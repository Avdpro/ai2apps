# SPDX-License-Identifier: Apache-2.0
"""Model Worker request-memory estimation and admission tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from ai2apps.model_providers import PackageModel, proxy_package_json
from ai2apps.worker_resources import (
    GIB,
    MIB,
    HostConditionSnapshot,
    SystemMemorySnapshot,
    WorkerResourceConfig,
    WorkerResourceManager,
    estimate_request_transient_bytes,
)
from ai2apps.worker_scheduler import WorkerJobScheduler, WorkloadClass


def _memory(*, total: int = 16 * GIB, available: int = 10 * GIB):
    return SystemMemorySnapshot(
        total_bytes=total,
        available_bytes=available,
        used_bytes=total - available,
        pressure_level="ok",
    )


def test_request_estimates_are_host_derived_and_conservative():
    short_chat = estimate_request_transient_bytes(
        "chat_completions", {"messages": [{"content": "hi"}], "max_tokens": 32}
    )
    long_chat = estimate_request_transient_bytes(
        "chat_completions",
        {"messages": [{"content": "x" * 100_000}], "max_tokens": 8192},
    )
    image = estimate_request_transient_bytes(
        "image_generation", {"size": "2048x2048"}
    )
    video = estimate_request_transient_bytes(
        "video_generation", {"resolution": "1280x720", "frames": 81}
    )

    assert short_chat >= 512 * MIB
    assert long_chat > short_chat
    assert image >= 1536 * MIB
    assert video >= 4 * GIB


def test_resource_manager_reserves_releases_and_fails_closed():
    manager = WorkerResourceManager(sampler=_memory)

    first = manager.try_reserve("ticket-1", "worker.a", 1 * GIB)
    duplicate = manager.try_reserve("ticket-1", "worker.a", 1 * GIB)
    rejected = manager.try_reserve("ticket-2", "worker.b", 6 * GIB)

    assert first is not None
    assert duplicate is first
    assert rejected is None
    snapshot = manager.snapshot()
    assert snapshot["activeReservations"] == 1
    assert snapshot["reservedTransientBytes"] == 1 * GIB
    assert snapshot["reservedByWorker"] == {"worker.a": 1 * GIB}
    assert snapshot["rejected"] == 1
    assert manager.release("ticket-1") is True
    assert manager.release("ticket-1") is False


@pytest.mark.asyncio
async def test_scheduler_releases_memory_reservation_with_execution_lease():
    manager = WorkerResourceManager(sampler=_memory)
    scheduler = WorkerJobScheduler(resource_manager=manager)

    lease = await scheduler.acquire(
        "worker.a",
        WorkloadClass.LOCAL_FOREGROUND,
        request_id="request-1",
        estimated_transient_bytes=768 * MIB,
    )
    assert manager.snapshot()["reservedTransientBytes"] == 768 * MIB

    await lease.release()
    await lease.release()
    assert manager.snapshot()["reservedTransientBytes"] == 0
    assert (await scheduler.snapshot())["completed"] == 1


@pytest.mark.asyncio
async def test_scheduler_times_out_when_memory_admission_never_fits():
    manager = WorkerResourceManager(
        WorkerResourceConfig(
            min_safety_margin_bytes=2 * GIB,
            admission_wait_seconds=0.01,
        ),
        sampler=lambda: _memory(total=8 * GIB, available=1 * GIB),
    )
    scheduler = WorkerJobScheduler(resource_manager=manager)

    with pytest.raises(TimeoutError):
        await scheduler.acquire(
            "worker.large",
            WorkloadClass.LOCAL_FOREGROUND,
            request_id="request-rejected",
            estimated_transient_bytes=1 * GIB,
        )

    assert (await scheduler.snapshot())["queued"] == 0
    resource_snapshot = manager.snapshot()
    assert resource_snapshot["activeReservations"] == 0
    assert resource_snapshot["rejected"] >= 1


@pytest.mark.asyncio
async def test_model_proxy_maps_admission_timeout_to_retryable_503():
    manager = WorkerResourceManager(
        WorkerResourceConfig(admission_wait_seconds=0.01),
        sampler=lambda: _memory(total=8 * GIB, available=1 * GIB),
    )
    scheduler = WorkerJobScheduler(resource_manager=manager)
    model = PackageModel(
        id="worker.large/chat",
        display_name="Large Chat",
        model_type="llm",
        upstream_id="large-chat",
        capabilities=("conversation",),
        endpoints={"chat_completions": "/v1/chat/completions"},
        context_window=8192,
        metadata={},
        audio_capabilities=None,
        video_capabilities=None,
        image_capabilities=None,
        service_key="worker.large",
        provider_key="package:worker.large",
        endpoint="http://worker.invalid",
        scheduler=scheduler,
    )

    with pytest.raises(HTTPException) as error:
        await proxy_package_json(
            model,
            "chat_completions",
            {"messages": [{"role": "user", "content": "hello"}]},
        )

    assert error.value.status_code == 503
    assert error.value.detail["code"] == "worker_resource_unavailable"
    assert error.value.headers == {"Retry-After": "5"}


@pytest.mark.asyncio
async def test_ttl_sweeper_protects_reserved_and_pinned_workers():
    now = [0.0]
    manager = WorkerResourceManager(
        WorkerResourceConfig(
            idle_timeout_seconds=10,
            min_residency_seconds=5,
            sweep_interval_seconds=1,
        ),
        sampler=_memory,
        clock=lambda: now[0],
    )
    packages = (
        SimpleNamespace(
            service_key="worker.a",
            protocol="ai2apps-model-worker/v1",
            status=SimpleNamespace(value="active"),
        ),
        SimpleNamespace(
            service_key="worker.b",
            protocol="ai2apps-model-worker/v1",
            status=SimpleNamespace(value="active"),
        ),
    )
    evictions = []

    class Supervisor:
        async def worker_snapshot(self, package):
            return {
                "state": "ready",
                "generation": 2,
                "startedAgeSeconds": 100,
                "residentMemoryBytes": (
                    2 * GIB if package.service_key == "worker.a" else 1 * GIB
                ),
            }

    class Packages:
        @staticmethod
        def installed():
            return packages

    class PackageManager:
        supervisor = Supervisor()
        packages = Packages()

        @staticmethod
        async def evict(service_key, **options):
            evictions.append((service_key, options))

    package_manager = PackageManager()
    manager.mark_started("worker.a")
    manager.mark_started("worker.b")
    manager.set_pinned("worker.b", True)
    reservation = manager.try_reserve("active-ticket", "worker.a", 512 * MIB)
    assert reservation is not None
    now[0] = 100

    assert await manager.sweep_once(package_manager) == ()
    assert evictions == []

    manager.release("active-ticket")
    now[0] = 120
    assert await manager.sweep_once(package_manager) == ("worker.a",)
    assert evictions == [
        (
            "worker.a",
            {"reason": "idle_timeout", "expected_generation": 2},
        )
    ]


@pytest.mark.asyncio
async def test_host_conditions_pause_only_new_background_admission():
    manager = WorkerResourceManager(
        sampler=_memory,
        condition_sampler=lambda: HostConditionSnapshot(
            on_battery=True,
            battery_percent=15,
            temperature_celsius=85,
        ),
    )
    scheduler = WorkerJobScheduler(resource_manager=manager)
    manager.bind_scheduler(scheduler)

    class Packages:
        @staticmethod
        def installed():
            return ()

    await manager.sweep_once(SimpleNamespace(packages=Packages()))

    snapshot = await scheduler.snapshot()
    assert snapshot["backgroundPaused"] is True
    assert snapshot["backgroundPauseReasons"] == [
        "battery",
        "low_battery",
        "thermal",
    ]
    foreground = await scheduler.acquire(
        "worker.fg", WorkloadClass.LOCAL_FOREGROUND
    )
    await foreground.release()
    resource_snapshot = manager.snapshot()
    assert resource_snapshot["onBattery"] is True
    assert resource_snapshot["batteryPercent"] == 15
    assert resource_snapshot["temperatureCelsius"] == 85


def test_pinned_worker_limit_is_host_owned():
    manager = WorkerResourceManager(
        WorkerResourceConfig(max_pinned_workers=1), sampler=_memory
    )
    manager.set_pinned("worker.a", True)
    with pytest.raises(RuntimeError, match="At most 1"):
        manager.set_pinned("worker.b", True)


@pytest.mark.asyncio
async def test_pressure_sweeper_evicts_one_lru_worker_before_normal_ttl():
    now = [0.0]
    manager = WorkerResourceManager(
        WorkerResourceConfig(
            idle_timeout_seconds=1_000,
            pressure_idle_grace_seconds=10,
            min_residency_seconds=5,
        ),
        sampler=lambda: _memory(total=10 * GIB, available=1 * GIB),
        clock=lambda: now[0],
    )
    packages = tuple(
        SimpleNamespace(
            service_key=service_key,
            protocol="ai2apps-model-worker/v1",
            status=SimpleNamespace(value="active"),
        )
        for service_key in ("worker.old", "worker.new")
    )
    evictions = []

    class Supervisor:
        async def worker_snapshot(self, package):
            return {
                "state": "ready",
                "generation": 4,
                "startedAgeSeconds": 100,
                "residentMemoryBytes": 2 * GIB,
            }

    class Packages:
        @staticmethod
        def installed():
            return packages

    class PackageManager:
        supervisor = Supervisor()
        packages = Packages()

        @staticmethod
        async def evict(service_key, **options):
            evictions.append((service_key, options))

    manager.mark_started("worker.old")
    now[0] = 80
    manager.mark_started("worker.new")
    now[0] = 100

    assert await manager.sweep_once(PackageManager()) == ("worker.old",)
    assert evictions == [
        (
            "worker.old",
            {"reason": "memory_pressure_soft", "expected_generation": 4},
        )
    ]
