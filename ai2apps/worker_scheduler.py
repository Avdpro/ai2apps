"""Host-owned Model Worker queueing, QoS, and execution-slot admission."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from ai2apps.worker_resources import WorkerResourceManager


class WorkloadClass(StrEnum):
    LOCAL_INTERACTIVE = "local_interactive"
    LOCAL_FOREGROUND = "local_foreground"
    REMOTE_COMMITTED = "remote_committed"
    LOCAL_BACKGROUND = "local_background"
    MAINTENANCE = "maintenance"


class QueueTicketStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


_CLASS_RANK = {
    WorkloadClass.LOCAL_INTERACTIVE: 0,
    WorkloadClass.LOCAL_FOREGROUND: 1,
    WorkloadClass.REMOTE_COMMITTED: 2,
    WorkloadClass.LOCAL_BACKGROUND: 3,
    WorkloadClass.MAINTENANCE: 4,
}


@dataclass(slots=True)
class QueueTicket:
    id: str
    request_id: str
    service_key: str
    workload_class: WorkloadClass
    created_at: float
    sequence: int
    deadline: float | None
    estimated_duration_ms: int | None
    estimated_resident_bytes: int | None
    estimated_transient_bytes: int | None
    actor_id: str | None
    app_id: str | None
    session_id: str | None
    status: QueueTicketStatus = QueueTicketStatus.QUEUED
    started_at: float | None = None
    completed_at: float | None = None


class SchedulerLease:
    """Exactly-once release handle for one admitted QueueTicket."""

    def __init__(self, scheduler: WorkerJobScheduler, ticket: QueueTicket) -> None:
        self.scheduler = scheduler
        self.ticket = ticket
        self._released = False

    async def release(self, *, failed: bool = False) -> None:
        if self._released:
            return
        self._released = True
        await self.scheduler._release(self.ticket.id, failed=failed)

    async def __aenter__(self) -> SchedulerLease:
        return self

    async def __aexit__(self, exc_type, _exc, _traceback) -> None:
        await self.release(failed=exc_type is not None)


class WorkerJobScheduler:
    """Deterministic priority scheduler for serial Model Worker processes."""

    def __init__(
        self,
        *,
        max_heavy_compute_slots: int = 1,
        default_worker_slots: int = 1,
        max_queue_depth: int = 1024,
        aging_interval_seconds: float = 30.0,
        max_active_per_actor: int = 1,
        max_queued_per_actor: int = 32,
        max_queued_per_app: int = 128,
        clock: Callable[[], float] = time.monotonic,
        resource_manager: WorkerResourceManager | None = None,
    ) -> None:
        if max_heavy_compute_slots < 1 or default_worker_slots < 1:
            raise ValueError("Scheduler slot limits must be positive")
        if max_queue_depth < 1 or aging_interval_seconds <= 0:
            raise ValueError("Scheduler queue limits must be positive")
        if min(max_active_per_actor, max_queued_per_actor, max_queued_per_app) < 1:
            raise ValueError("Scheduler actor/App limits must be positive")
        self.max_heavy_compute_slots = max_heavy_compute_slots
        self.default_worker_slots = default_worker_slots
        self.max_queue_depth = max_queue_depth
        self.aging_interval_seconds = aging_interval_seconds
        self.max_active_per_actor = max_active_per_actor
        self.max_queued_per_actor = max_queued_per_actor
        self.max_queued_per_app = max_queued_per_app
        self._clock = clock
        self.resource_manager = resource_manager
        self._lock = asyncio.Lock()
        self._queued: dict[str, QueueTicket] = {}
        self._active: dict[str, QueueTicket] = {}
        self._waiters: dict[str, asyncio.Future[SchedulerLease]] = {}
        self._worker_slots: dict[str, int] = {}
        self._sequence = 0
        self._closed = False
        self._completed = 0
        self._failed = 0
        self._cancelled = 0
        self._expired = 0
        self._actor_dispatches: dict[str, int] = {}
        self._background_gate_reasons: set[str] = set()

    def set_worker_slots(self, service_key: str, slots: int) -> None:
        if slots < 1:
            raise ValueError("Worker slot limit must be positive")
        self._worker_slots[service_key] = slots

    def _effective_rank(self, ticket: QueueTicket, now: float) -> int:
        base = _CLASS_RANK[ticket.workload_class]
        if base == 0:
            return 0
        aged = int(max(0.0, now - ticket.created_at) / self.aging_interval_seconds)
        return max(1, base - aged)

    def _priority(self, ticket: QueueTicket, now: float) -> tuple:
        return (
            self._effective_rank(ticket, now),
            ticket.deadline if ticket.deadline is not None else float("inf"),
            self._actor_dispatches.get(ticket.actor_id, 0)
            if ticket.actor_id is not None
            else 0,
            ticket.created_at,
            ticket.sequence,
            ticket.id,
        )

    def _worker_running(self, service_key: str) -> int:
        return sum(
            ticket.service_key == service_key for ticket in self._active.values()
        )

    def _runnable(self, ticket: QueueTicket) -> bool:
        if ticket.workload_class in {
            WorkloadClass.LOCAL_BACKGROUND,
            WorkloadClass.MAINTENANCE,
        } and (
            self._background_gate_reasons
            or any(
                queued.workload_class
                in {WorkloadClass.LOCAL_INTERACTIVE, WorkloadClass.LOCAL_FOREGROUND}
                for queued in self._queued.values()
                if queued.id != ticket.id
            )
        ):
            return False
        if ticket.actor_id is not None and sum(
            active.actor_id == ticket.actor_id for active in self._active.values()
        ) >= self.max_active_per_actor:
            return False
        limit = self._worker_slots.get(
            ticket.service_key, self.default_worker_slots
        )
        return self._worker_running(ticket.service_key) < limit

    def _expire_locked(self, now: float) -> None:
        for ticket_id, ticket in tuple(self._queued.items()):
            if ticket.deadline is None or ticket.deadline > now:
                continue
            self._queued.pop(ticket_id, None)
            ticket.status = QueueTicketStatus.EXPIRED
            ticket.completed_at = now
            self._expired += 1
            waiter = self._waiters.pop(ticket_id, None)
            if waiter is not None and not waiter.done():
                waiter.set_exception(TimeoutError("Worker queue deadline expired"))

    def _dispatch_locked(self) -> None:
        now = self._clock()
        self._expire_locked(now)
        while len(self._active) < self.max_heavy_compute_slots:
            candidates = [
                ticket for ticket in self._queued.values() if self._runnable(ticket)
            ]
            if not candidates:
                return
            ticket = None
            for candidate in sorted(
                candidates, key=lambda value: self._priority(value, now)
            ):
                if self.resource_manager is None or self.resource_manager.try_reserve(
                    candidate.id,
                    candidate.service_key,
                    candidate.estimated_transient_bytes,
                    candidate.estimated_resident_bytes,
                ) is not None:
                    ticket = candidate
                    break
            if ticket is None:
                return
            self._queued.pop(ticket.id)
            ticket.status = QueueTicketStatus.RUNNING
            ticket.started_at = now
            self._active[ticket.id] = ticket
            if ticket.actor_id is not None:
                self._actor_dispatches[ticket.actor_id] = (
                    self._actor_dispatches.get(ticket.actor_id, 0) + 1
                )
            waiter = self._waiters.pop(ticket.id, None)
            if waiter is not None and not waiter.done():
                waiter.set_result(SchedulerLease(self, ticket))

    async def acquire(
        self,
        service_key: str,
        workload_class: WorkloadClass | str,
        *,
        request_id: str | None = None,
        timeout_seconds: float | None = None,
        estimated_duration_ms: int | None = None,
        estimated_resident_bytes: int | None = None,
        estimated_transient_bytes: int | None = None,
        actor_id: str | None = None,
        app_id: str | None = None,
        session_id: str | None = None,
    ) -> SchedulerLease:
        workload_class = WorkloadClass(workload_class)
        if timeout_seconds is None and self.resource_manager is not None:
            timeout_seconds = self.resource_manager.config.admission_wait_seconds
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise TimeoutError("Worker queue deadline expired")
        loop = asyncio.get_running_loop()
        now = self._clock()
        async with self._lock:
            if self._closed:
                raise RuntimeError("Worker scheduler is shutting down")
            if len(self._queued) >= self.max_queue_depth:
                raise RuntimeError("Worker scheduler queue is full")
            if actor_id is not None and sum(
                ticket.actor_id == actor_id for ticket in self._queued.values()
            ) >= self.max_queued_per_actor:
                raise RuntimeError("Worker scheduler actor queue is full")
            if app_id is not None and sum(
                ticket.app_id == app_id for ticket in self._queued.values()
            ) >= self.max_queued_per_app:
                raise RuntimeError("Worker scheduler App queue is full")
            self._sequence += 1
            ticket = QueueTicket(
                id=f"queue-ticket-{uuid.uuid4().hex}",
                request_id=request_id or f"request-{uuid.uuid4().hex}",
                service_key=service_key,
                workload_class=workload_class,
                created_at=now,
                sequence=self._sequence,
                deadline=None if timeout_seconds is None else now + timeout_seconds,
                estimated_duration_ms=estimated_duration_ms,
                estimated_resident_bytes=estimated_resident_bytes,
                estimated_transient_bytes=estimated_transient_bytes,
                actor_id=actor_id,
                app_id=app_id,
                session_id=session_id,
            )
            waiter: asyncio.Future[SchedulerLease] = loop.create_future()
            self._queued[ticket.id] = ticket
            self._waiters[ticket.id] = waiter
            self._dispatch_locked()
        try:
            if timeout_seconds is None:
                return await waiter
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except TimeoutError:
            await self._expire_ticket(ticket.id)
            raise
        except BaseException:
            if not await self.cancel(ticket.id):
                await self._release(ticket.id, failed=True)
            raise

    async def _expire_ticket(self, ticket_id: str) -> bool:
        async with self._lock:
            ticket = self._queued.pop(ticket_id, None)
            if ticket is None:
                return False
            ticket.status = QueueTicketStatus.EXPIRED
            ticket.completed_at = self._clock()
            self._expired += 1
            waiter = self._waiters.pop(ticket_id, None)
            if waiter is not None and not waiter.done():
                waiter.cancel()
            self._dispatch_locked()
            return True

    async def cancel(self, ticket_id: str) -> bool:
        async with self._lock:
            ticket = self._queued.pop(ticket_id, None)
            if ticket is None:
                return False
            ticket.status = QueueTicketStatus.CANCELLED
            ticket.completed_at = self._clock()
            self._cancelled += 1
            waiter = self._waiters.pop(ticket_id, None)
            if waiter is not None and not waiter.done():
                waiter.cancel()
            self._dispatch_locked()
            return True

    async def _release(self, ticket_id: str, *, failed: bool) -> None:
        async with self._lock:
            ticket = self._active.pop(ticket_id, None)
            if ticket is None:
                return
            if self.resource_manager is not None:
                self.resource_manager.release(ticket_id)
            ticket.status = (
                QueueTicketStatus.FAILED if failed else QueueTicketStatus.SUCCEEDED
            )
            ticket.completed_at = self._clock()
            if failed:
                self._failed += 1
            else:
                self._completed += 1
            self._dispatch_locked()

    async def snapshot(self) -> dict:
        async with self._lock:
            now = self._clock()
            self._expire_locked(now)
            queued_by_class = {value.value: 0 for value in WorkloadClass}
            running_by_class = {value.value: 0 for value in WorkloadClass}
            for ticket in self._queued.values():
                queued_by_class[ticket.workload_class.value] += 1
            for ticket in self._active.values():
                running_by_class[ticket.workload_class.value] += 1
            worker_keys = {
                ticket.service_key
                for ticket in (*self._queued.values(), *self._active.values())
            }
            workers = {}
            for service_key in sorted(worker_keys):
                worker_queued = [
                    ticket
                    for ticket in self._queued.values()
                    if ticket.service_key == service_key
                ]
                worker_running = [
                    ticket
                    for ticket in self._active.values()
                    if ticket.service_key == service_key
                ]
                workers[service_key] = {
                    "queued": len(worker_queued),
                    "running": len(worker_running),
                    "queuedByClass": {
                        value.value: sum(
                            ticket.workload_class is value
                            for ticket in worker_queued
                        )
                        for value in WorkloadClass
                    },
                    "runningByClass": {
                        value.value: sum(
                            ticket.workload_class is value
                            for ticket in worker_running
                        )
                        for value in WorkloadClass
                    },
                }
            queued = sorted(
                self._queued.values(), key=lambda value: self._priority(value, now)
            )
            return {
                "queued": len(queued),
                "running": len(self._active),
                "maxHeavyComputeSlots": self.max_heavy_compute_slots,
                "availableHeavyComputeSlots": max(
                    0, self.max_heavy_compute_slots - len(self._active)
                ),
                "queuedByClass": queued_by_class,
                "runningByClass": running_by_class,
                "completed": self._completed,
                "failed": self._failed,
                "cancelled": self._cancelled,
                "expired": self._expired,
                "workers": workers,
                "tickets": [
                    {
                        "ticketId": ticket.id,
                        "requestId": ticket.request_id,
                        "serviceKey": ticket.service_key,
                        "workloadClass": ticket.workload_class.value,
                        "status": ticket.status.value,
                        "waitingSeconds": max(0.0, now - ticket.created_at),
                        "estimatedDurationMs": ticket.estimated_duration_ms,
                        "estimatedResidentBytes": ticket.estimated_resident_bytes,
                        "estimatedTransientBytes": ticket.estimated_transient_bytes,
                        "actorId": ticket.actor_id,
                        "appId": ticket.app_id,
                        "sessionId": ticket.session_id,
                    }
                    for ticket in queued
                ],
                "backgroundPaused": bool(self._background_gate_reasons),
                "backgroundPauseReasons": sorted(self._background_gate_reasons),
                "maxActivePerActor": self.max_active_per_actor,
                "maxQueuedPerActor": self.max_queued_per_actor,
                "maxQueuedPerApp": self.max_queued_per_app,
            }

    async def set_background_gate(self, reason: str, paused: bool) -> None:
        """Pause only new background/maintenance admission for a Host reason."""

        if not reason:
            raise ValueError("Background gate reason is required")
        async with self._lock:
            if paused:
                self._background_gate_reasons.add(reason)
            else:
                self._background_gate_reasons.discard(reason)
            self._dispatch_locked()

    async def notify_resources_changed(self) -> None:
        async with self._lock:
            self._dispatch_locked()

    async def shutdown(self) -> None:
        async with self._lock:
            self._closed = True
            now = self._clock()
            for ticket in self._queued.values():
                ticket.status = QueueTicketStatus.CANCELLED
                ticket.completed_at = now
            self._cancelled += len(self._queued)
            self._queued.clear()
            for waiter in self._waiters.values():
                if not waiter.done():
                    waiter.cancel()
            self._waiters.clear()
