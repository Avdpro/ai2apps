"""Worker cache policy across arbitrary providers and persisted Session leases."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from ai2apps.model_worker.omlx_chat import _generation_kwargs
from ai2apps.model_worker.prefix_cache import WorkerPrefixCache


def checkpoint(provider="arbitrary/one", revision="r1"):
    return SimpleNamespace(repo_id=provider, revision=revision, path=Path("/weights"))


def test_alternating_sessions_persistence_idle_expiry_and_paths(tmp_path):
    now = [100.0]
    cache = WorkerPrefixCache(
        tmp_path, checkpoint(), idle_seconds=10, clock=lambda: now[0]
    )
    a = cache.namespace("../../owner A")
    b = cache.namespace("B")
    assert a != b
    now[0] = 105
    assert cache.namespace("../../owner A") == a
    restarted = WorkerPrefixCache(
        tmp_path, checkpoint(), idle_seconds=10, clock=lambda: now[0]
    )
    assert restarted.namespace("../../owner A") == a
    now[0] = 111
    assert restarted.namespace("B") != b
    assert restarted.namespace("../../owner A") == a
    now[0] = 122
    assert restarted.namespace("../../owner A") != a
    assert cache.root.is_relative_to(tmp_path)
    assert b"owner A" not in cache.database.read_bytes()
    assert cache.root.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("provider", ["vendor/alpha", "unrelated/beta"])
def test_revision_and_provider_isolation_and_ssd_default(tmp_path, provider):
    from omlx.scheduler import SchedulerConfig

    cache = WorkerPrefixCache(tmp_path, checkpoint(provider))
    other = WorkerPrefixCache(tmp_path, checkpoint(provider, "r2"))
    assert cache.root != other.root
    existing = SchedulerConfig(
        max_num_seqs=3, chunked_prefill=True, hot_cache_only=True
    )
    engine = SimpleNamespace(_scheduler_config=existing)
    assert cache.configure(engine)
    config = engine._scheduler_config
    assert config.max_num_seqs == 3 and config.chunked_prefill
    assert config.paged_ssd_cache_dir == str(cache.root / "blocks")
    assert config.paged_ssd_cache_max_size == 20 * 1024**3
    assert config.hot_cache_max_size == 0 and not config.hot_cache_only
    assert existing.hot_cache_only  # Original settings object was not mutated.
    assert not cache.configure(SimpleNamespace())
    assert cache.namespace("A") != other.namespace("A")


def test_generation_keys_override_legacy_session_key():
    keys = ("owner", "lease")
    assert (
        _generation_kwargs({"ai2apps_session_id": "A", "_ai2apps_cache_keys": keys})[
            "cache_extra_keys"
        ]
        == keys
    )
    assert _generation_kwargs({"_ai2apps_cache_keys": keys})["cache_extra_keys"] == keys


def test_expiry_removes_only_idle_completed_blocks(tmp_path):
    import time

    from omlx.cache.paged_ssd_cache import PagedSSDBlockMetadata, PagedSSDCacheManager

    manager = PagedSSDCacheManager(tmp_path, 1024 * 1024)
    try:

        def entry(key, age):
            path = tmp_path / (key + ".safetensors")
            path.write_bytes(b"fixture")
            m = PagedSSDBlockMetadata(
                key.encode(), path, 7, 256, time.time() - age, time.time() - age, 1
            )
            manager._index.add(m)
            return m

        stale = entry("stale", 100)
        fresh = entry("fresh", 0)
        pending = entry("pending", 100)
        manager._pending_write_hashes.add(pending.block_hash)
        manager.configure_idle_expiry(10)
        assert not stale.file_path.exists()
        assert fresh.file_path.exists() and pending.file_path.exists()
        assert manager._index.get(stale.block_hash) is None
    finally:
        manager._pending_write_hashes.clear()
        manager.close()


def test_persistent_exact_boundaries_verify_tokens_lineage_and_expiry(tmp_path):
    now = [10.0]
    cache = WorkerPrefixCache(
        tmp_path, checkpoint(), idle_seconds=10, clock=lambda: now[0]
    )
    lineage = (cache.namespace("A"), None)
    tokens = [1, 2, 3]
    cache.save(lineage, tokens)
    restarted = WorkerPrefixCache(
        tmp_path, checkpoint(), idle_seconds=10, clock=lambda: now[0]
    )
    assert restarted.match(lineage, [1, 2, 3, 4]) == tokens
    assert restarted.match(lineage, [1, 2, 9, 4]) is None
    assert restarted.match((cache.namespace("B"), None), [1, 2, 3, 4]) is None
    assert restarted.match(lineage, tokens) is None
    assert restarted.match((lineage[0], (8, ("image-hash",))), [1, 2, 3, 4]) is None
    now[0] = 21
    assert restarted.match(lineage, [1, 2, 3, 4]) is None


@pytest.mark.asyncio
async def test_worker_lifecycle_and_transport_keys_are_owned(tmp_path):
    from types import SimpleNamespace

    from ai2apps.model_worker import (
        ModelWorkerCheckpoint,
        ModelWorkerContext,
        ModelWorkerRequest,
    )
    from ai2apps.model_worker.omlx_chat import OmlxChatAdapter
    from omlx.scheduler import SchedulerConfig

    selected = ModelWorkerCheckpoint(
        "test/model", "upstream", "hf", "vendor/model", "rev", tmp_path, {}
    )
    context = ModelWorkerContext(
        "provider", tmp_path, tmp_path, ({"id": "test/model"},), (selected,)
    )
    manager = SimpleNamespace(configure_idle_expiry=lambda seconds: None)
    scheduler = SimpleNamespace(paged_ssd_cache_manager=manager)

    class Engine:
        _scheduler_config = None
        prefix_cache_enabled = True

        async def start(self):
            assert isinstance(self._scheduler_config, SchedulerConfig)
            self._engine = SimpleNamespace(engine=SimpleNamespace(scheduler=scheduler))

        async def stop(self):
            pass

    class Adapter(OmlxChatAdapter):
        async def create_engine(self, *args):
            return Engine()

        async def _chat(self, engine, model, body, request_id):
            return _generation_kwargs(body)

    adapter = Adapter(context)

    async def invoke(session):
        return await adapter.invoke(
            ModelWorkerRequest(
                "chat_completions",
                {
                    "model": "test/model",
                    "ai2apps_session_id": session,
                    "_ai2apps_cache_keys": ("forged",),
                },
                "fixture",
            )
        )

    a = await invoke("A")
    b = await invoke("B")
    again = await invoke("A")
    assert a["cache_extra_keys"] == again["cache_extra_keys"] != b["cache_extra_keys"]
    assert a["cache_extra_keys"] != ("forged",)
    assert (await invoke(None))["cache_extra_keys"] != (await invoke(None))[
        "cache_extra_keys"
    ]
    assert scheduler.persistent_prefix_store is adapter._prefix_cache
    await adapter.stop()
    assert adapter._prefix_cache is None


def test_hybrid_partial_prefix_uses_its_own_boundary_after_ssd_restart(tmp_path):
    import mlx.core as mx

    from omlx.cache.hybrid_cache import ModelCacheConfig
    from omlx.cache.paged_cache import PagedCacheManager
    from omlx.cache.paged_ssd_cache import PagedSSDCacheManager
    from omlx.cache.prefix_cache import BlockAwarePrefixCache

    def create():
        pages = PagedCacheManager(
            block_size=4,
            max_blocks=100,
            initial_blocks=16,
            model_name="arbitrary-hybrid",
        )
        disk = PagedSSDCacheManager(tmp_path, 1024**2)
        pages.set_paged_ssd_cache_manager(disk)
        model = SimpleNamespace(layers=[None, None])
        cache = BlockAwarePrefixCache(model, pages, paged_ssd_cache_manager=disk)
        return cache, disk

    def state(count):
        k = mx.arange(count, dtype=mx.float32).reshape(1, 1, count, 1)
        recurrent = mx.ones((1, 2)) * count
        return [
            {
                "state": (k, k),
                "meta_state": (count,),
                "class_name": "KVCache",
                "cache_type": "KVCache",
            },
            {
                "state": (recurrent, recurrent),
                "meta_state": (),
                "class_name": "ArraysCache",
                "cache_type": "ArraysCache",
            },
        ]

    cache, disk = create()
    config = ModelCacheConfig.from_type_list(
        ["KVCache", "ArraysCache"], model_name="arbitrary-hybrid"
    )
    try:
        table = cache.store_exact_prefix(
            "seed",
            list(range(12)),
            state(12),
            model_cache_config=config,
            boundary_snapshots={4: state(4), 8: state(8)},
            extra_keys=("owner-A",),
        )
        assert table is not None
    finally:
        disk.close()
    cache, disk = create()
    try:
        table, remaining = cache.fetch_cache(
            "changed", [0, 1, 2, 3, 4, 99], extra_keys=("owner-A",)
        )
        assert table is not None and table.num_tokens == 4
        restored = cache.reconstruct_cache(table, promote_to_hot_cache=False)
        assert restored is not None
        assert mx.array_equal(restored[1][0], mx.ones((1, 2)) * 4).item()
        assert restored[0].state[0].shape[2] == 4
        assert remaining == [4, 99]
    finally:
        disk.close()
