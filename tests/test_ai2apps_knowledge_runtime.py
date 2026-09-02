# SPDX-License-Identifier: Apache-2.0
"""Knowledge indexing integration with the transparent model gateway."""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

import pytest

from ai2apps.knowledge.runtime import KnowledgePackageRuntime


class _Indexer:
    def __init__(self):
        self.sequence = 0
        self.sync_calls = 0

    def status(self):
        return SimpleNamespace(sequence=self.sequence, target_sequence=1)

    def sync(self):
        self.sync_calls += 1
        self.sequence = 1
        return SimpleNamespace(changed_items=1)


def _runtime(indexer, gateway):
    value = object.__new__(KnowledgePackageRuntime)
    value.indexer = indexer
    value.retriever = object()
    value.runtime = SimpleNamespace(model_invocations=gateway)
    value._worker_lock = threading.Lock()
    value._loop = None
    value._worker = None
    value._scheduled = False
    value._closing = False
    value._phase = "idle"
    return value


@pytest.mark.asyncio
async def test_vector_index_waits_for_background_model_gateway():
    admitted = asyncio.Event()
    allow = asyncio.Event()
    captured = {}

    class Gateway:
        async def run_background_sync(
            self, model_id, callback, *, request_id=None, on_admitted=None
        ):
            captured.update(
                model_id=model_id,
                request_id=request_id,
            )
            admitted.set()
            await allow.wait()
            on_admitted()
            result = await asyncio.to_thread(callback)
            captured["completed"] = True
            return result

    indexer = _Indexer()
    runtime = _runtime(indexer, Gateway())

    await runtime.startup()
    await asyncio.wait_for(admitted.wait(), timeout=1)
    assert indexer.sync_calls == 0
    allow.set()
    for _ in range(100):
        if captured.get("completed"):
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Knowledge index Attempt did not finish")

    assert captured["model_id"] == "ai2apps.model.multilingual-e5-small/default"
    assert captured["request_id"].startswith("knowledge-index-")
    assert indexer.sync_calls == 1
    await runtime.shutdown()


@pytest.mark.asyncio
async def test_shutdown_cancels_queued_vector_gateway_attempt():
    admitted = asyncio.Event()
    cancelled = {}

    class Gateway:
        async def run_background_sync(self, *_args, **_options):
            admitted.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled["value"] = True
                raise

    indexer = _Indexer()
    runtime = _runtime(indexer, Gateway())
    await runtime.startup()
    await asyncio.wait_for(admitted.wait(), timeout=1)

    await runtime.shutdown()

    assert cancelled["value"] is True
    assert indexer.sync_calls == 0
    assert runtime._worker is None


@pytest.mark.asyncio
async def test_shutdown_waits_for_active_index_chunk_inside_gateway():
    started = threading.Event()
    finish = threading.Event()
    completed = {}

    class BlockingIndexer(_Indexer):
        def sync(self):
            self.sync_calls += 1
            started.set()
            assert finish.wait(timeout=1)
            self.sequence = 1
            return SimpleNamespace(changed_items=1)

    class Gateway:
        async def run_background_sync(
            self, _model_id, callback, *, on_admitted=None, **_options
        ):
            on_admitted()
            result = await asyncio.to_thread(callback)
            completed["value"] = True
            return result

    runtime = _runtime(BlockingIndexer(), Gateway())
    await runtime.startup()
    assert await asyncio.to_thread(started.wait, 1)

    shutdown = asyncio.create_task(runtime.shutdown())
    await asyncio.sleep(0.02)
    assert shutdown.done() is False
    assert completed == {}

    finish.set()
    await asyncio.wait_for(shutdown, timeout=1)
    assert completed["value"] is True
