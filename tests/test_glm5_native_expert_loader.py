from __future__ import annotations

import os

import mlx.core as mx
import pytest

from omlx.custom_kernels.glm_moe_dsa import fast as glm_fast
from omlx.patches.deepseek_v4.switch_layers import SwitchGLU
from omlx.patches.glm5_next_cache.dynamic_cache import Glm5DynamicCache
from omlx.patches.glm5_next_cache.policy import LayerState, PROBATION


def test_preadv_fused_experts_writes_final_mlx_slots(tmp_path):
    if "preadv_fused_experts" not in glm_fast.native_symbols():
        pytest.skip("native fused expert loader is not built")

    segment_bytes = (1024, 256, 256, 2048, 256, 256)
    record_bytes = sum(segment_bytes)
    data_offset = 4096
    records = []
    for expert in range(3):
        records.append(
            b"".join(
                bytes([expert * 16 + segment]) * size
                for segment, size in enumerate(segment_bytes)
            )
        )
    path = tmp_path / "layer-003.moe"
    path.write_bytes(bytes(data_offset) + b"".join(records))

    capacity = 4
    arrays = [
        mx.zeros((capacity, size), dtype=mx.uint8) for size in segment_bytes
    ]
    mx.eval(*arrays)
    mx.synchronize()
    fd = os.open(path, os.O_RDONLY)
    try:
        loaded = glm_fast.preadv_fused_experts(
            fd,
            data_offset,
            record_bytes,
            [2, 0],
            [1, 3],
            *arrays,
            io_workers=2,
        )
    finally:
        os.close(fd)

    assert loaded == 2 * record_bytes
    checks = []
    for segment, array in enumerate(arrays):
        checks.extend(
            (
                mx.all(array[0] == 0),
                mx.all(array[1] == 32 + segment),
                mx.all(array[2] == 0),
                mx.all(array[3] == segment),
            )
        )
    mx.eval(*checks)
    assert all(bool(check.item()) for check in checks)


def test_decode_resolve_publishes_native_direct_load(monkeypatch, tmp_path):
    cache = Glm5DynamicCache(tmp_path, capacity=2, num_experts=4, io_workers=1)

    class Store:
        record_bytes = 4096

    class Switch:
        _omlx_glm5_mutable = True

    calls = []
    monkeypatch.setattr(cache, "_store", lambda _layer: Store())
    monkeypatch.setattr(
        cache,
        "_direct_load",
        lambda store, switch, slots, ids: calls.append((slots, ids)) or True,
    )
    try:
        lookup = cache.resolve(3, (2,), Switch())
    finally:
        cache._read_pool.shutdown(wait=True)
        cache._prefetch_pool.shutdown(wait=True)

    assert lookup[2] >= 0
    assert calls == [((0,), (2,))]
    assert cache.stats()["bytes_loaded"] == 4096


def test_partial_miss_overlap_matches_full_bank(monkeypatch, tmp_path):
    mx.random.seed(41)
    reference = SwitchGLU(
        input_dims=8,
        hidden_dims=16,
        num_experts=8,
        global_num_experts=8,
        fused_gate_up=True,
    )
    cache = Glm5DynamicCache(tmp_path, capacity=4, num_experts=8, io_workers=1)
    primary = cache._make_fixed_switch(reference, 4)
    cache._copy_switch_slots(reference, (0, 1, 2, 3), primary, (0, 1, 2, 3))
    cache.policy.install(
        3,
        LayerState(
            expert_ids=[0, 1, 2, 3],
            segments=[PROBATION] * 4,
            last_used=[1, 2, 3, 4],
            clock=4,
        ),
    )

    class Store:
        record_bytes = 4096

    def fake_direct(_store, scratch, slots, ids):
        cache._copy_switch_slots(reference, tuple(ids), scratch, tuple(slots))
        return True

    monkeypatch.setattr(cache, "_store", lambda _layer: Store())
    monkeypatch.setattr(cache, "_direct_load", fake_direct)
    x = mx.random.normal((1, 1, 8))
    inds = mx.array([[[0, 5, 1]]], dtype=mx.int32)
    scores = mx.softmax(mx.random.normal((1, 1, 3)), axis=-1)
    lookup = mx.array(cache.lookup(3), dtype=mx.int32)
    mapped = lookup[inds]
    expected_routes = reference(x, inds)
    expected = (
        expected_routes * scores[..., None].astype(expected_routes.dtype)
    ).sum(axis=-2)
    try:
        actual, updated = cache.resolve_split(
            3, (0, 5, 1), primary, x, inds, scores, mapped
        )
        mx.eval(actual, expected)
    finally:
        cache._read_pool.shutdown(wait=True)
        cache._prefetch_pool.shutdown(wait=True)

    assert mx.allclose(actual, expected, rtol=1e-5, atol=1e-5)
    assert updated[5] >= 0
    assert cache.stats()["overlap_calls"] == 1


def test_double_buffered_direct_prefill_matches_full_bank(monkeypatch, tmp_path):
    monkeypatch.setenv("OMLX_GLM5_PREFILL_BANK_SLOTS", "2")
    mx.random.seed(43)
    reference = SwitchGLU(
        input_dims=8,
        hidden_dims=16,
        num_experts=8,
        global_num_experts=8,
        fused_gate_up=True,
    )
    cache = Glm5DynamicCache(tmp_path, capacity=4, num_experts=8, io_workers=1)
    primary = cache._make_fixed_switch(reference, 4)

    class Store:
        record_bytes = 4096

    def fake_direct(_store, scratch, slots, ids):
        cache._copy_switch_slots(reference, tuple(ids), scratch, tuple(slots))
        return True

    monkeypatch.setattr(cache, "direct_enabled", lambda: True)
    monkeypatch.setattr(cache, "_store", lambda _layer: Store())
    monkeypatch.setattr(cache, "_direct_load", fake_direct)
    x = mx.random.normal((1, 2, 8))
    inds = mx.array([[[0, 5], [1, 6]]], dtype=mx.int32)
    scores = mx.softmax(mx.random.normal((1, 2, 2)), axis=-1)
    expected_routes = reference(x, inds)
    expected = (
        expected_routes * scores[..., None].astype(expected_routes.dtype)
    ).sum(axis=-2)
    try:
        actual = cache.prefill(3, primary, x, inds, scores)
        mx.eval(actual, expected)
    finally:
        cache._read_pool.shutdown(wait=True)
        cache._prefetch_pool.shutdown(wait=True)

    assert mx.allclose(actual, expected, rtol=1e-5, atol=1e-5)
    assert cache.stats()["prefill_direct_calls"] == 1
    assert cache.stats()["prefill_direct_groups"] == 2


def test_direct_prefill_reuses_main_before_ssd(monkeypatch, tmp_path):
    monkeypatch.setenv("OMLX_GLM5_PREFILL_BANK_SLOTS", "2")
    mx.random.seed(45)
    reference = SwitchGLU(
        input_dims=8,
        hidden_dims=16,
        num_experts=8,
        global_num_experts=8,
        fused_gate_up=True,
    )
    cache = Glm5DynamicCache(
        tmp_path, capacity=4, tail_slots=2, num_experts=8, io_workers=1
    )
    primary = cache._make_fixed_switch(reference, 4)
    cache._copy_switch_slots(reference, (0, 1, 2, 3), primary, (0, 1, 2, 3))
    cache.policy.install(
        3,
        LayerState(
            expert_ids=[0, 1, 2, 3],
            segments=[PROBATION] * 4,
            last_used=[1, 2, 3, 4],
            clock=4,
        ),
    )
    class Store:
        record_bytes = 4096

    loads = []

    def fake_direct(_store, scratch, slots, ids):
        loads.append(tuple(ids))
        cache._copy_switch_slots(reference, tuple(ids), scratch, tuple(slots))
        return True

    monkeypatch.setattr(cache, "direct_enabled", lambda: True)
    monkeypatch.setattr(cache, "_store", lambda _layer: Store())
    monkeypatch.setattr(cache, "_direct_load", fake_direct)
    x = mx.random.normal((1, 2, 8))
    inds = mx.array([[[0, 6], [1, 7]]], dtype=mx.int32)
    scores = mx.softmax(mx.random.normal((1, 2, 2)), axis=-1)
    expected_routes = reference(x, inds)
    expected = (
        expected_routes * scores[..., None].astype(expected_routes.dtype)
    ).sum(axis=-2)
    try:
        actual = cache.prefill(3, primary, x, inds, scores)
        mx.eval(actual, expected)
    finally:
        cache._read_pool.shutdown(wait=True)
        cache._prefetch_pool.shutdown(wait=True)

    stats = cache.stats()
    assert mx.allclose(actual, expected, rtol=1e-5, atol=1e-5)
    assert loads == [(6, 7)]
    assert stats["prefill_main_routes"] == 2
    assert stats["prefill_tail_routes"] == 0
    assert stats["prefill_miss_routes"] == 2
    assert stats["prefill_unique_misses"] == 2
    assert stats["prefill_experts_avoided"] == 2


def test_persistent_tail_reuses_misses_without_promotion(monkeypatch, tmp_path):
    mx.random.seed(47)
    reference = SwitchGLU(
        input_dims=8,
        hidden_dims=16,
        num_experts=8,
        global_num_experts=8,
        fused_gate_up=True,
    )
    cache = Glm5DynamicCache(
        tmp_path, capacity=4, tail_slots=2, num_experts=8, io_workers=1
    )
    primary = cache._make_fixed_switch(reference, 4)
    cache._copy_switch_slots(reference, (0, 1, 2, 3), primary, (0, 1, 2, 3))
    cache.policy.install(
        3,
        LayerState(
            expert_ids=[0, 1, 2, 3],
            segments=[PROBATION] * 4,
            last_used=[1, 2, 3, 4],
            clock=4,
        ),
    )

    class Store:
        record_bytes = 4096

    loads = []

    def fake_direct(_store, tail, slots, ids):
        loads.append(tuple(ids))
        cache._copy_switch_slots(reference, tuple(ids), tail, tuple(slots))
        return True

    monkeypatch.setattr(cache, "_store", lambda _layer: Store())
    monkeypatch.setattr(cache, "_direct_load", fake_direct)
    # Two verifier positions exercise the MTP microdecode scatter path: route
    # contributions must remain separated per token while sharing one Tail load.
    x = mx.random.normal((1, 2, 8))
    inds = mx.array([[[0, 5, 1, 6], [6, 1, 5, 0]]], dtype=mx.int32)
    scores = mx.softmax(mx.random.normal((1, 2, 4)), axis=-1)
    mapped = mx.array(cache.lookup(3), dtype=mx.int32)[inds]
    expected_routes = reference(x, inds)
    expected = (
        expected_routes * scores[..., None].astype(expected_routes.dtype)
    ).sum(axis=-2)
    try:
        first, _, tail_lookup = cache.decode_tiered(
            3, (0, 5, 1, 6), primary, x, inds, scores, mapped
        )
        second, _, _ = cache.decode_tiered(
            3, (0, 5, 1, 6), primary, x, inds, scores, mapped
        )
        cache.l1_promotions_per_layer = 1
        third, _, _ = cache.decode_tiered(
            3, (0, 5, 1, 6), primary, x, inds, scores, mapped
        )
        fourth, main_lookup, _ = cache.decode_tiered(
            3, (0, 5, 1, 6), primary, x, inds, scores, mapped
        )
        mx.eval(first, second, third, fourth, expected)
    finally:
        cache._read_pool.shutdown(wait=True)
        cache._prefetch_pool.shutdown(wait=True)

    assert mx.allclose(first, expected, rtol=1e-5, atol=1e-5)
    assert mx.allclose(second, expected, rtol=1e-5, atol=1e-5)
    assert mx.allclose(third, expected, rtol=1e-5, atol=1e-5)
    assert mx.allclose(fourth, expected, rtol=1e-5, atol=1e-5)
    assert tail_lookup[5] >= 0 and tail_lookup[6] >= 0
    assert loads == [(5, 6)]
    assert main_lookup[5] >= 0 or main_lookup[6] >= 0
    assert cache.stats()["l1_promotions"] == 1


def test_native_weighted_sum_matches_route_materialization(monkeypatch):
    from omlx.patches.glm5_next_cache.runtime import _weighted_switch

    monkeypatch.setenv("OMLX_GLM5_WEIGHTED_SUM", "1")
    mx.random.seed(53)
    switch = SwitchGLU(
        input_dims=8,
        hidden_dims=16,
        num_experts=8,
        global_num_experts=8,
        fused_gate_up=True,
    )
    switch.set_dtype(mx.float16)
    x = mx.random.normal((1, 2, 8)).astype(mx.float16)
    inds = mx.array(
        [[[7, 0, 5, 2, 4, 1, 6, 3], [1, 6, 2, 7, 0, 3, 5, 4]]],
        dtype=mx.int32,
    )
    scores = mx.softmax(mx.random.normal((1, 2, 8)), axis=-1)
    routes = switch(x, inds)
    expected = (routes * scores[..., None].astype(routes.dtype)).sum(axis=-2)
    actual = _weighted_switch(switch, x, inds, scores)
    mx.eval(actual, expected)

    # The native reducer accumulates Top-8 in a different (more fused) order.
    assert mx.allclose(actual, expected, rtol=2e-3, atol=2e-4)
