# SPDX-License-Identifier: Apache-2.0
"""Host Model Worker scheduler priority and slot-admission tests."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ai2apps.identity import RequestPrincipal
from ai2apps.model_invocation import ModelInvocationContext, ModelInvocationService
from ai2apps.worker_scheduler import WorkerJobScheduler, WorkloadClass


def test_chat_package_routes_are_host_classified_as_interactive():
    source = (Path(__file__).parents[1] / "omlx/server.py").read_text(
        encoding="utf-8"
    )

    assert source.count("model_invocations.invoke_interactive_json") >= 2
    assert 'request_id=http_request.headers.get("x-request-id")' in source


def test_business_modules_cannot_cross_worker_scheduling_boundary():
    root = Path(__file__).parents[1] / "ai2apps"
    business_roots = [
        root / "images",
        root / "knowledge",
        root / "provisioning",
        root / "readaloud",
        root / "video",
    ]
    forbidden = (
        "worker_scheduler",
        "scheduler.acquire",
        "WorkloadClass",
        "ensure_package_model_ready",
        "proxy_package_json",
        "proxy_package_multipart",
    )
    violations = []
    for directory in business_roots:
        for source_path in directory.rglob("*.py"):
            source = source_path.read_text(encoding="utf-8")
            for token in forbidden:
                if token in source:
                    violations.append(f"{source_path.relative_to(root)}: {token}")
    assert violations == []


@pytest.mark.asyncio
async def test_scheduler_enforces_global_heavy_compute_slot():
    scheduler = WorkerJobScheduler(max_heavy_compute_slots=1)
    first = await scheduler.acquire(
        "worker.image", WorkloadClass.LOCAL_FOREGROUND, request_id="image-1"
    )
    waiting = asyncio.create_task(
        scheduler.acquire(
            "worker.video", WorkloadClass.LOCAL_FOREGROUND, request_id="video-1"
        )
    )
    await asyncio.sleep(0)

    snapshot = await scheduler.snapshot()
    assert snapshot["running"] == 1
    assert snapshot["queued"] == 1
    assert snapshot["availableHeavyComputeSlots"] == 0
    assert snapshot["workers"]["worker.image"]["running"] == 1
    assert snapshot["workers"]["worker.video"]["queued"] == 1
    assert not waiting.done()

    await first.release()
    second = await asyncio.wait_for(waiting, timeout=1)
    assert second.ticket.request_id == "video-1"
    await second.release()


@pytest.mark.asyncio
async def test_interactive_job_overtakes_queued_background_job():
    scheduler = WorkerJobScheduler()
    blocker = await scheduler.acquire(
        "worker.chat", WorkloadClass.LOCAL_INTERACTIVE, request_id="blocker"
    )
    background = asyncio.create_task(
        scheduler.acquire(
            "worker.embedding",
            WorkloadClass.LOCAL_BACKGROUND,
            request_id="background",
        )
    )
    interactive = asyncio.create_task(
        scheduler.acquire(
            "worker.chat",
            WorkloadClass.LOCAL_INTERACTIVE,
            request_id="interactive",
        )
    )
    await asyncio.sleep(0)
    await blocker.release()

    admitted = await asyncio.wait_for(interactive, timeout=1)
    assert admitted.ticket.request_id == "interactive"
    assert not background.done()
    await admitted.release()
    background_lease = await asyncio.wait_for(background, timeout=1)
    await background_lease.release()


@pytest.mark.asyncio
async def test_worker_slot_does_not_block_another_worker_when_device_has_capacity():
    scheduler = WorkerJobScheduler(max_heavy_compute_slots=2)
    first = await scheduler.acquire(
        "worker.a", WorkloadClass.LOCAL_FOREGROUND, request_id="a-1"
    )
    same_worker = asyncio.create_task(
        scheduler.acquire(
            "worker.a", WorkloadClass.LOCAL_FOREGROUND, request_id="a-2"
        )
    )
    other_worker = asyncio.create_task(
        scheduler.acquire(
            "worker.b", WorkloadClass.LOCAL_FOREGROUND, request_id="b-1"
        )
    )
    await asyncio.sleep(0)

    other = await asyncio.wait_for(other_worker, timeout=1)
    assert not same_worker.done()
    await first.release()
    same = await asyncio.wait_for(same_worker, timeout=1)
    await other.release()
    await same.release()


@pytest.mark.asyncio
async def test_queue_timeout_removes_ticket_without_releasing_running_job():
    scheduler = WorkerJobScheduler()
    blocker = await scheduler.acquire(
        "worker.a", WorkloadClass.LOCAL_FOREGROUND, request_id="running"
    )

    with pytest.raises(TimeoutError):
        await scheduler.acquire(
            "worker.b",
            WorkloadClass.MAINTENANCE,
            request_id="expires",
            timeout_seconds=0.01,
        )

    snapshot = await scheduler.snapshot()
    assert snapshot["running"] == 1
    assert snapshot["queued"] == 0
    assert snapshot["expired"] == 1
    await blocker.release()


@pytest.mark.asyncio
async def test_aging_never_promotes_background_above_interactive():
    now = [100.0]
    scheduler = WorkerJobScheduler(
        clock=lambda: now[0], aging_interval_seconds=10.0
    )
    blocker = await scheduler.acquire(
        "worker.a", WorkloadClass.LOCAL_FOREGROUND, request_id="blocker"
    )
    background = asyncio.create_task(
        scheduler.acquire(
            "worker.b", WorkloadClass.LOCAL_BACKGROUND, request_id="old-background"
        )
    )
    await asyncio.sleep(0)
    now[0] += 1000
    interactive = asyncio.create_task(
        scheduler.acquire(
            "worker.c", WorkloadClass.LOCAL_INTERACTIVE, request_id="interactive"
        )
    )
    await asyncio.sleep(0)
    await blocker.release()

    admitted = await asyncio.wait_for(interactive, timeout=1)
    assert not background.done()
    await admitted.release()
    background_lease = await asyncio.wait_for(background, timeout=1)
    await background_lease.release()


@pytest.mark.asyncio
async def test_actor_fairness_and_trusted_context_are_visible_to_host():
    scheduler = WorkerJobScheduler(max_heavy_compute_slots=1)
    blocker = await scheduler.acquire(
        "worker.a", WorkloadClass.LOCAL_FOREGROUND, request_id="blocker"
    )
    actor_a = asyncio.create_task(
        scheduler.acquire(
            "worker.a",
            WorkloadClass.LOCAL_FOREGROUND,
            request_id="actor-a",
            actor_id="alice",
            app_id="appi_alice",
            session_id="session-alice",
        )
    )
    actor_b = asyncio.create_task(
        scheduler.acquire(
            "worker.b",
            WorkloadClass.LOCAL_FOREGROUND,
            request_id="actor-b",
            actor_id="bob",
            app_id="appi_bob",
            session_id="session-bob",
        )
    )
    await asyncio.sleep(0)
    snapshot = await scheduler.snapshot()
    alice = next(item for item in snapshot["tickets"] if item["actorId"] == "alice")
    assert alice["appId"] == "appi_alice"
    assert alice["sessionId"] == "session-alice"

    await blocker.release()
    first = await asyncio.wait_for(actor_a, timeout=1)
    await first.release()
    second = await asyncio.wait_for(actor_b, timeout=1)
    await second.release()


@pytest.mark.asyncio
async def test_background_gate_pauses_new_background_but_allows_foreground():
    scheduler = WorkerJobScheduler()
    await scheduler.set_background_gate("thermal", True)
    background = asyncio.create_task(
        scheduler.acquire("worker.bg", WorkloadClass.LOCAL_BACKGROUND)
    )
    await asyncio.sleep(0)
    assert not background.done()

    foreground = await scheduler.acquire(
        "worker.fg", WorkloadClass.LOCAL_FOREGROUND
    )
    snapshot = await scheduler.snapshot()
    assert snapshot["backgroundPaused"] is True
    assert snapshot["backgroundPauseReasons"] == ["thermal"]
    await foreground.release()
    assert not background.done()

    await scheduler.set_background_gate("thermal", False)
    admitted = await asyncio.wait_for(background, timeout=1)
    await admitted.release()


@pytest.mark.asyncio
async def test_actor_queue_limit_fails_closed():
    scheduler = WorkerJobScheduler(max_queued_per_actor=1)
    blocker = await scheduler.acquire(
        "worker.a", WorkloadClass.LOCAL_FOREGROUND
    )
    queued = asyncio.create_task(
        scheduler.acquire(
            "worker.b", WorkloadClass.LOCAL_FOREGROUND, actor_id="alice"
        )
    )
    await asyncio.sleep(0)
    with pytest.raises(RuntimeError, match="actor queue is full"):
        await scheduler.acquire(
            "worker.c", WorkloadClass.LOCAL_FOREGROUND, actor_id="alice"
        )
    queued.cancel()
    with pytest.raises(asyncio.CancelledError):
        await queued
    await blocker.release()


@pytest.mark.asyncio
async def test_model_invocation_service_forwards_only_trusted_scheduling_identity(
    monkeypatch,
):
    model = SimpleNamespace(id="worker/chat")
    service = ModelInvocationService(SimpleNamespace())
    monkeypatch.setattr(service, "_require_model", lambda _model_id: model)
    proxy = AsyncMock(return_value=SimpleNamespace(status_code=200))
    monkeypatch.setattr("ai2apps.model_invocation.proxy_package_json", proxy)
    context = ModelInvocationContext.from_principal(
        RequestPrincipal.legacy_local(),
        session_id="session-trusted",
        app_instance_id="app-trusted",
    )

    await service.invoke_interactive_json(
        model.id,
        "chat_completions",
        {"messages": []},
        request_id="request-trusted",
        context=context,
    )

    assert proxy.await_args.kwargs["actor_id"] == "local"
    assert proxy.await_args.kwargs["app_id"] == "app-trusted"
    assert proxy.await_args.kwargs["session_id"] == "session-trusted"
    assert proxy.await_args.kwargs["queue_timeout_seconds"] == 30.0


@pytest.mark.asyncio
async def test_background_video_multipart_preserves_structured_fields(tmp_path, monkeypatch):
    import json
    from email.parser import BytesParser
    from email.policy import default
    import httpx

    model = SimpleNamespace(id="avatar/lite", upstream_id="lite", internal_headers={},
                            endpoint="http://127.0.0.1:1234", endpoints={"video_generation": "/video"})
    service = ModelInvocationService(SimpleNamespace())
    monkeypatch.setattr(service, "_require_model", lambda _: model)
    monkeypatch.setattr(service, "request_progress", AsyncMock(return_value=None))
    monkeypatch.setattr("ai2apps.model_invocation.ensure_package_model_ready", AsyncMock(return_value=model))
    seen = {}

    async def handle(request):
        message = BytesParser(policy=default).parsebytes(
            f"Content-Type: {request.headers['content-type']}\r\n\r\n".encode() + await request.aread())
        for part in message.iter_parts():
            seen[part.get_param("name", header="content-disposition")] = part.get_payload(decode=True)
        return httpx.Response(200, content=b"video")

    client_type = httpx.AsyncClient
    monkeypatch.setattr("ai2apps.model_invocation.httpx.AsyncClient",
                        lambda **kw: client_type(transport=httpx.MockTransport(handle), **kw))
    source = tmp_path / "portrait.png"
    source.write_bytes(b"portrait")
    references = [{"kind": "image", "part_name": "reference_00_image"}]
    output = tmp_path / "result.mp4"
    await service.invoke_background_to_file(model.id, "video_generation",
        {"reference_parts": references, "parameters": {"label": "照片"}, "flag": False, "seed": 0},
        output, files={"reference_00_image": (source.name, source, "image/png")}, request_id="test")
    assert json.loads(seen["reference_parts"]) == references
    assert json.loads(seen["parameters"]) == {"label": "照片"}
    assert seen["flag"] == b"false" and seen["seed"] == b"0"
    assert seen["reference_00_image"] == b"portrait"
    assert output.read_bytes() == b"video"


@pytest.mark.asyncio
async def test_active_cancellation_releases_once_and_admits_next_request():
    scheduler=WorkerJobScheduler()
    first=await scheduler.acquire('test',WorkloadClass.LOCAL_FOREGROUND)
    pending=asyncio.create_task(scheduler.acquire('test',WorkloadClass.LOCAL_FOREGROUND))
    await asyncio.sleep(0)
    assert not pending.done()
    await first.release(cancelled=True)
    await first.release(failed=True)
    second=await asyncio.wait_for(pending,1)
    await second.release()
    state=await scheduler.snapshot()
    assert state['cancelled']==1 and state['completed']==1 and state['failed']==0
    assert state['running']==state['queued']==0


@pytest.mark.asyncio
async def test_queued_request_cancel_is_bound_to_service_actor_app_and_session():
    scheduler=WorkerJobScheduler()
    owner=dict(actor_id='alice',app_id='studio',session_id='session-a')
    blocker=await scheduler.acquire('worker',WorkloadClass.LOCAL_FOREGROUND,request_id='active-id',**owner)
    queued=asyncio.create_task(scheduler.acquire('worker',WorkloadClass.LOCAL_FOREGROUND,request_id='same-id',**owner))
    await asyncio.sleep(0)
    for field,value in [('actor_id','bob'),('app_id','other'),('session_id','other')]:
        wrong={**owner,field:value}
        assert not await scheduler.cancel_queued_request('worker','same-id',**wrong)
        assert not await scheduler.owns_active_request('worker','same-id',**wrong)
    assert not await scheduler.cancel_queued_request('other-worker','same-id',**owner)
    assert await scheduler.cancel_queued_request('worker','same-id',**owner)
    with pytest.raises(asyncio.CancelledError):await queued
    assert await scheduler.owns_active_request('worker','active-id',**owner)
    state=await scheduler.snapshot()
    assert state['running']==1 and state['queued']==0 and state['cancelled']==1
    await blocker.release()


@pytest.mark.asyncio
async def test_reused_active_request_id_cannot_be_reported_as_queue_only_cancel():
    scheduler=WorkerJobScheduler()
    owner=dict(actor_id='alice',app_id='studio',session_id='session')
    lease=await scheduler.acquire('worker',WorkloadClass.LOCAL_FOREGROUND,request_id='same',**owner)
    queued=asyncio.create_task(scheduler.acquire('worker',WorkloadClass.LOCAL_FOREGROUND,request_id='same',**owner))
    await asyncio.sleep(0)
    assert not await scheduler.cancel_queued_request('worker','same',**owner)
    state=await scheduler.snapshot();assert state['running']==state['queued']==1
    queued.cancel()
    with pytest.raises(asyncio.CancelledError):await queued
    await lease.release()
