"""Request-level unified-memory admission for Model Worker execution."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

import psutil

MIB = 1024**2
GIB = 1024**3


@dataclass(frozen=True, slots=True)
class WorkerResourceConfig:
    soft_memory_ratio: float = 0.80
    hard_memory_ratio: float = 0.92
    safety_margin_ratio: float = 0.15
    min_safety_margin_bytes: int = 2 * GIB
    unknown_request_bytes: int = 512 * MIB
    admission_wait_seconds: float = 30.0
    idle_timeout_seconds: float = 300.0
    pressure_idle_grace_seconds: float = 30.0
    min_residency_seconds: float = 60.0
    sweep_interval_seconds: float = 30.0
    pause_background_on_battery: bool = True
    low_battery_percent: float = 20.0
    hot_temperature_celsius: float = 80.0
    max_pinned_workers: int = 2

    def __post_init__(self) -> None:
        if not 0 < self.soft_memory_ratio < self.hard_memory_ratio <= 1:
            raise ValueError("Memory watermarks are invalid")
        if not 0 <= self.safety_margin_ratio < 1:
            raise ValueError("Memory safety margin ratio is invalid")
        if self.min_safety_margin_bytes < 0 or self.unknown_request_bytes < 1:
            raise ValueError("Memory safety margins must be non-negative")
        if self.admission_wait_seconds <= 0:
            raise ValueError("Admission wait must be positive")
        if (
            self.idle_timeout_seconds < 0
            or self.pressure_idle_grace_seconds < 0
            or self.min_residency_seconds < 0
            or self.sweep_interval_seconds <= 0
        ):
            raise ValueError("Worker lifecycle intervals are invalid")
        if not 0 <= self.low_battery_percent <= 100:
            raise ValueError("Low battery threshold is invalid")
        if self.hot_temperature_celsius <= 0:
            raise ValueError("Temperature threshold is invalid")
        if self.max_pinned_workers < 1:
            raise ValueError("Pinned Worker limit must be positive")


@dataclass(frozen=True, slots=True)
class SystemMemorySnapshot:
    total_bytes: int
    available_bytes: int
    used_bytes: int
    pressure_level: str


@dataclass(frozen=True, slots=True)
class HostConditionSnapshot:
    on_battery: bool | None = None
    battery_percent: float | None = None
    temperature_celsius: float | None = None


def sample_host_conditions() -> HostConditionSnapshot:
    try:
        battery = psutil.sensors_battery()
    except (AttributeError, OSError, RuntimeError):
        battery = None
    temperature = None
    sensors = getattr(psutil, "sensors_temperatures", None)
    if callable(sensors):
        with suppress(Exception):
            values = sensors()
            readings = [
                float(item.current)
                for group in values.values()
                for item in group
                if item.current is not None
            ]
            temperature = max(readings, default=None)
    return HostConditionSnapshot(
        on_battery=None if battery is None else not bool(battery.power_plugged),
        battery_percent=None if battery is None else float(battery.percent),
        temperature_celsius=temperature,
    )


@dataclass(frozen=True, slots=True)
class MemoryReservation:
    ticket_id: str
    service_key: str
    resident_bytes: int
    transient_bytes: int
    created_at: float

    @property
    def total_bytes(self) -> int:
        return self.resident_bytes + self.transient_bytes


class WorkerResourceUnavailableError(RuntimeError):
    code = "worker_resource_unavailable"

    def __init__(self, message: str, *, retry_after_seconds: int = 5) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class WorkerPinnedLimitError(RuntimeError):
    code = "worker_pinned_limit"


def sample_system_memory() -> SystemMemorySnapshot:
    memory = psutil.virtual_memory()
    total = int(memory.total)
    available = int(memory.available)
    used = max(0, total - available)
    ratio = used / total if total else 1.0
    pressure = "hard" if ratio >= 0.92 else "soft" if ratio >= 0.80 else "ok"
    return SystemMemorySnapshot(total, available, used, pressure)


def _positive_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _geometry_bytes(value: Any, *, bytes_per_pixel: int) -> int:
    if not isinstance(value, str) or "x" not in value.lower():
        return 0
    try:
        width, height = (int(part) for part in value.lower().split("x", 1))
    except ValueError:
        return 0
    if not 1 <= width <= 16384 or not 1 <= height <= 16384:
        return 0
    return width * height * bytes_per_pixel


def estimate_request_transient_bytes(
    operation: str,
    payload: Mapping[str, Any],
    *,
    file_bytes: int = 0,
) -> int:
    """Derive a conservative Host-owned transient-memory estimate."""

    safe_file_bytes = max(0, int(file_bytes))
    if operation in {"chat_completions", "responses"}:
        max_tokens = _positive_int(
            payload.get("max_tokens", payload.get("max_output_tokens"))
        ) or 2048
        serialized_chars = len(str(payload.get("messages", payload.get("input", ""))))
        input_tokens = max(1, serialized_chars // 4)
        token_budget = min(131_072, input_tokens + max_tokens)
        return max(512 * MIB, token_budget * 256 * 1024 + safe_file_bytes * 4)
    if operation in {"image_generation", "image_edit"}:
        geometry = _geometry_bytes(payload.get("size"), bytes_per_pixel=32)
        return max(1536 * MIB, geometry + safe_file_bytes * 6)
    if operation == "video_generation":
        geometry = _geometry_bytes(
            payload.get("resolution", payload.get("size")), bytes_per_pixel=64
        )
        frames = min(2048, _positive_int(payload.get("frames")) or 81)
        return max(4 * GIB, geometry * min(frames, 32) + safe_file_bytes * 6)
    if operation in {"audio_transcription", "audio_speech", "audio_process"}:
        return max(512 * MIB, safe_file_bytes * 6)
    if operation == "embeddings":
        return max(256 * MIB, len(str(payload.get("input", ""))) * 1024)
    return max(512 * MIB, safe_file_bytes * 4)


class WorkerResourceManager:
    """Own transient-memory reservations and conservative admission decisions."""

    def __init__(
        self,
        config: WorkerResourceConfig | None = None,
        *,
        sampler: Callable[[], SystemMemorySnapshot] = sample_system_memory,
        condition_sampler: Callable[[], HostConditionSnapshot] = sample_host_conditions,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or WorkerResourceConfig()
        self._sampler = sampler
        self._condition_sampler = condition_sampler
        self._clock = clock
        self._reservations: dict[str, MemoryReservation] = {}
        self._admitted = 0
        self._rejected = 0
        self._peak_reserved_bytes = 0
        self._last_rejection: dict[str, Any] | None = None
        self._last_used: dict[str, float] = {}
        self._pinned: set[str] = set()
        self._evicting: set[str] = set()
        self._sweeper_task: asyncio.Task[None] | None = None
        self._sweeper_stop: asyncio.Event | None = None
        self._scheduler = None
        self._last_conditions = HostConditionSnapshot()

    @property
    def reserved_bytes(self) -> int:
        return sum(value.total_bytes for value in self._reservations.values())

    def try_reserve(
        self,
        ticket_id: str,
        service_key: str,
        estimated_transient_bytes: int | None,
        estimated_resident_bytes: int | None = None,
    ) -> MemoryReservation | None:
        existing = self._reservations.get(ticket_id)
        if existing is not None:
            return existing
        if service_key in self._evicting:
            self._rejected += 1
            return None
        estimate = (
            estimated_transient_bytes
            if isinstance(estimated_transient_bytes, int)
            and not isinstance(estimated_transient_bytes, bool)
            and estimated_transient_bytes > 0
            else self.config.unknown_request_bytes
        )
        resident_estimate = (
            estimated_resident_bytes
            if isinstance(estimated_resident_bytes, int)
            and not isinstance(estimated_resident_bytes, bool)
            and estimated_resident_bytes > 0
            else 0
        )
        total_estimate = estimate + resident_estimate
        memory = self._sampler()
        safety_margin = max(
            self.config.min_safety_margin_bytes,
            int(memory.total_bytes * self.config.safety_margin_ratio),
        )
        reserved = self.reserved_bytes
        soft_ceiling = int(memory.total_bytes * self.config.soft_memory_ratio)
        hard_ceiling = int(memory.total_bytes * self.config.hard_memory_ratio)
        projected = memory.used_bytes + reserved + total_estimate
        fits = (
            projected <= soft_ceiling
            and projected <= hard_ceiling
            and memory.available_bytes >= reserved + total_estimate + safety_margin
        )
        if not fits:
            self._rejected += 1
            self._last_rejection = {
                "serviceKey": service_key,
                "estimatedTransientBytes": estimate,
                "estimatedResidentBytes": resident_estimate,
                "projectedUsedBytes": projected,
                "softCeilingBytes": soft_ceiling,
                "availableBytes": memory.available_bytes,
                "safetyMarginBytes": safety_margin,
                "pressureLevel": memory.pressure_level,
            }
            return None
        reservation = MemoryReservation(
            ticket_id=ticket_id,
            service_key=service_key,
            resident_bytes=resident_estimate,
            transient_bytes=estimate,
            created_at=self._clock(),
        )
        self._reservations[ticket_id] = reservation
        self._last_used.setdefault(service_key, reservation.created_at)
        self._admitted += 1
        self._peak_reserved_bytes = max(self._peak_reserved_bytes, self.reserved_bytes)
        return reservation

    def release(self, ticket_id: str) -> bool:
        reservation = self._reservations.pop(ticket_id, None)
        if reservation is None:
            return False
        self._last_used[reservation.service_key] = self._clock()
        return True

    def mark_started(self, service_key: str) -> None:
        self._last_used.setdefault(service_key, self._clock())

    def bind_scheduler(self, scheduler) -> None:
        self._scheduler = scheduler

    def set_pinned(self, service_key: str, pinned: bool) -> None:
        self.assert_can_pin(service_key, pinned)
        if pinned:
            self._pinned.add(service_key)
        else:
            self._pinned.discard(service_key)

    def restore_pinned(self, service_key: str) -> None:
        """Restore a previously accepted preference without breaking upgrades."""

        self._pinned.add(service_key)

    def assert_can_pin(self, service_key: str, pinned: bool) -> None:
        if (
            pinned
            and service_key not in self._pinned
            and len(self._pinned) >= self.config.max_pinned_workers
        ):
            raise WorkerPinnedLimitError(
                f"At most {self.config.max_pinned_workers} Model Workers may be pinned"
            )

    def is_pinned(self, service_key: str) -> bool:
        return service_key in self._pinned

    def active_for_worker(self, service_key: str) -> int:
        return sum(
            reservation.service_key == service_key
            for reservation in self._reservations.values()
        )

    async def sweep_once(self, package_manager) -> tuple[str, ...]:
        """Evict idle Workers by TTL or one LRU victim under memory pressure."""

        memory = self._sampler()
        used_ratio = (
            memory.used_bytes / memory.total_bytes if memory.total_bytes else 1.0
        )
        pressure_level = (
            "hard"
            if used_ratio >= self.config.hard_memory_ratio
            or memory.pressure_level == "hard"
            else "soft"
            if used_ratio >= self.config.soft_memory_ratio
            or memory.pressure_level == "soft"
            else "ok"
        )
        under_pressure = pressure_level != "ok"
        conditions = self._condition_sampler()
        self._last_conditions = conditions
        if self._scheduler is not None:
            await self._scheduler.set_background_gate(
                "memory_pressure", under_pressure
            )
            await self._scheduler.set_background_gate(
                "battery",
                bool(
                    self.config.pause_background_on_battery
                    and conditions.on_battery
                ),
            )
            await self._scheduler.set_background_gate(
                "low_battery",
                bool(
                    conditions.battery_percent is not None
                    and conditions.battery_percent <= self.config.low_battery_percent
                ),
            )
            await self._scheduler.set_background_gate(
                "thermal",
                bool(
                    conditions.temperature_celsius is not None
                    and conditions.temperature_celsius
                    >= self.config.hot_temperature_celsius
                ),
            )
        if self.config.idle_timeout_seconds == 0 and not under_pressure:
            return ()
        idle_threshold = (
            self.config.pressure_idle_grace_seconds
            if under_pressure
            else self.config.idle_timeout_seconds
        )
        eviction_reason = (
            f"memory_pressure_{pressure_level}" if under_pressure else "idle_timeout"
        )
        now = self._clock()
        candidates: list[tuple[float, int, str, int]] = []
        for package in package_manager.packages.installed():
            if (
                package.status.value != "active"
                or package.protocol != "ai2apps-model-worker/v1"
                or package.service_key in self._pinned
                or package.service_key in self._evicting
                or self.active_for_worker(package.service_key)
            ):
                continue
            snapshot = await package_manager.supervisor.worker_snapshot(package)
            if snapshot["state"] != "ready":
                continue
            started_age = snapshot.get("startedAgeSeconds")
            if started_age is None or started_age < self.config.min_residency_seconds:
                continue
            last_used = self._last_used.get(
                package.service_key, now - float(started_age)
            )
            idle_age = max(0.0, now - last_used)
            if idle_age < idle_threshold:
                continue
            candidates.append(
                (
                    last_used,
                    -int(snapshot.get("residentMemoryBytes") or 0),
                    package.service_key,
                    int(snapshot["generation"]),
                )
            )
        evicted = []
        ordered_candidates = sorted(candidates)
        # Under pressure reclaim one LRU victim, then re-sample next sweep. This
        # avoids evicting every eligible Worker after a single stale sample.
        if under_pressure:
            ordered_candidates = ordered_candidates[:1]
        for _last_used, _memory, service_key, generation in ordered_candidates:
            if self.active_for_worker(service_key) or service_key in self._pinned:
                continue
            self._evicting.add(service_key)
            try:
                await package_manager.evict(
                    service_key,
                    reason=eviction_reason,
                    expected_generation=generation,
                )
                evicted.append(service_key)
            finally:
                self._evicting.discard(service_key)
                if self._scheduler is not None:
                    await self._scheduler.notify_resources_changed()
        return tuple(evicted)

    async def start(self, package_manager) -> None:
        if self._sweeper_task is not None:
            return
        self._sweeper_stop = asyncio.Event()

        async def sweep_loop() -> None:
            assert self._sweeper_stop is not None
            while not self._sweeper_stop.is_set():
                # Resource reclamation must never terminate the Base App.
                with suppress(Exception):
                    await self.sweep_once(package_manager)
                with suppress(TimeoutError):
                    await asyncio.wait_for(
                        self._sweeper_stop.wait(),
                        timeout=self.config.sweep_interval_seconds,
                    )

        self._sweeper_task = asyncio.create_task(
            sweep_loop(), name="ai2apps-worker-resource-sweeper"
        )

    async def shutdown(self) -> None:
        if self._sweeper_stop is not None:
            self._sweeper_stop.set()
        if self._sweeper_task is not None:
            await self._sweeper_task
        self._sweeper_task = None
        self._sweeper_stop = None

    def snapshot(self) -> dict[str, Any]:
        memory = self._sampler()
        safety_margin = max(
            self.config.min_safety_margin_bytes,
            int(memory.total_bytes * self.config.safety_margin_ratio),
        )
        reserved_by_worker: dict[str, int] = {}
        resident_reserved = 0
        transient_reserved = 0
        for reservation in self._reservations.values():
            reserved_by_worker[reservation.service_key] = (
                reserved_by_worker.get(reservation.service_key, 0)
                + reservation.total_bytes
            )
            resident_reserved += reservation.resident_bytes
            transient_reserved += reservation.transient_bytes
        return {
            "enabled": True,
            "totalMemoryBytes": memory.total_bytes,
            "availableMemoryBytes": memory.available_bytes,
            "usedMemoryBytes": memory.used_bytes,
            "pressureLevel": memory.pressure_level,
            "onBattery": self._last_conditions.on_battery,
            "batteryPercent": self._last_conditions.battery_percent,
            "temperatureCelsius": self._last_conditions.temperature_celsius,
            "softCeilingBytes": int(
                memory.total_bytes * self.config.soft_memory_ratio
            ),
            "hardCeilingBytes": int(
                memory.total_bytes * self.config.hard_memory_ratio
            ),
            "safetyMarginBytes": safety_margin,
            "reservedTotalBytes": self.reserved_bytes,
            "reservedTransientBytes": transient_reserved,
            "reservedRequestTransientBytes": transient_reserved,
            "reservedStartupResidentBytes": resident_reserved,
            "peakReservedTransientBytes": self._peak_reserved_bytes,
            "activeReservations": len(self._reservations),
            "reservedByWorker": reserved_by_worker,
            "admitted": self._admitted,
            "rejected": self._rejected,
            "lastRejection": self._last_rejection,
            "pinnedWorkers": sorted(self._pinned),
            "maxPinnedWorkers": self.config.max_pinned_workers,
            "evictingWorkers": sorted(self._evicting),
            "lastUsedAgeSecondsByWorker": {
                service_key: max(0.0, self._clock() - last_used)
                for service_key, last_used in sorted(self._last_used.items())
            },
        }
