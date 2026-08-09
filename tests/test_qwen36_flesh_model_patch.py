from __future__ import annotations

import json
from types import SimpleNamespace

import mlx.core as mx
import pytest

from omlx.patches.qwen3_6_flesh.model_patch import (
    _arena_route_ids,
    _exact_scope_moe,
    _lossy_replace_routes,
    apply_qwen36_flesh_model_patch,
)
from omlx.patches.qwen3_6_flesh.boost import (
    Qwen36BoostController,
    qwen36_lossy_policy,
)
from omlx.patches.qwen3_6_flesh.arena_cache import Qwen36DecodeArena
from omlx.patches.qwen3_6_flesh.tiered_cache import Qwen36TieredCache
from omlx.patches.qwen3_6_flesh.scope_policy import (
    Qwen36ScopeCatalog,
    clear_qwen36_scope_policy,
    configure_qwen36_scope_policy,
)
from omlx.patches.qwen3_6_flesh.scope_runtime import _Top8Collector


@pytest.fixture(autouse=True)
def _clear_policy():
    clear_qwen36_scope_policy()
    yield
    clear_qwen36_scope_policy()


def test_model_constructs_only_qwen_resident_experts(tmp_path):
    layers = {str(layer): list(range(120)) for layer in range(40)}
    profile = tmp_path / "scope.json"
    profile.write_text(
        json.dumps(
            {
                "phases": {
                    "prefill": {"coding": layers},
                    "decode": {"coding": layers},
                }
            }
        )
    )
    store = tmp_path / "experts"
    store.mkdir()
    configure_qwen36_scope_policy(profile, "coding", store, 96)
    assert apply_qwen36_flesh_model_patch()

    from mlx_lm.models.qwen3_next import Qwen3NextSparseMoeBlock

    args = SimpleNamespace(
        hidden_size=16,
        moe_intermediate_size=8,
        shared_expert_intermediate_size=8,
        norm_topk_prob=True,
        num_experts=256,
        num_experts_per_tok=8,
    )
    block = Qwen3NextSparseMoeBlock(args)

    assert block.num_experts == 256
    assert block.switch_mlp.gate_proj.weight.shape[0] == 96
    assert block.switch_mlp.up_proj.weight.shape[0] == 96
    assert block.switch_mlp.down_proj.weight.shape[0] == 96
    assert block.scope_policy.scope_name == "coding"


def test_qwen_scope_masks_follow_decode_bank_size(tmp_path):
    layers_a = {str(layer): list(range(120)) for layer in range(40)}
    layers_b = {str(layer): list(range(64, 184)) for layer in range(40)}
    profile = tmp_path / "scope.json"
    profile.write_text(
        json.dumps(
            {
                "phases": {
                    "prefill": {"a": layers_a, "b": layers_b},
                    "decode": {"a": layers_a, "b": layers_b},
                }
            }
        )
    )
    catalog = Qwen36ScopeCatalog.load(profile)
    masks = catalog.masks(96)

    assert sum(masks[0][0]) == 96
    assert masks[0][0][0] == 1
    assert masks[0][0][96] == 0
    assert masks[1][0][64] == 1
    assert masks[1][0][160] == 0


def test_qwen_top8_collector_scores_weighted_scope_coverage():
    masks = mx.zeros((2, 1, 256), dtype=mx.float32)
    masks[0, 0, mx.array([0, 1, 2, 3], dtype=mx.int32)] = 1
    masks[1, 0, mx.array([4, 5, 6, 7], dtype=mx.int32)] = 1
    collector = _Top8Collector(masks, 1)
    collector.capture(
        0,
        mx.array([[[0, 1, 2, 3, 4, 5, 6, 7]]], dtype=mx.int32),
        mx.array(
            [[[0.20, 0.20, 0.15, 0.15, 0.10, 0.08, 0.07, 0.05]]],
            dtype=mx.float32,
        ),
    )

    scores = collector.finish()
    assert scores[0] == pytest.approx(0.70, abs=1e-5)
    assert scores[1] == pytest.approx(0.30, abs=1e-5)


def test_arena_model_adds_independent_mutable_tail(tmp_path):
    layers = {str(layer): list(range(120)) for layer in range(40)}
    profile = tmp_path / "scope.json"
    profile.write_text(
        json.dumps(
            {
                "phases": {
                    "prefill": {"coding": layers},
                    "decode": {"coding": layers},
                }
            }
        )
    )
    store = tmp_path / "experts"
    store.mkdir()
    configure_qwen36_scope_policy(
        profile,
        "coding",
        store,
        96,
        backend="arena",
        arena_tail_slots=24,
    )
    assert apply_qwen36_flesh_model_patch()

    from mlx_lm.models.qwen3_next import Qwen3NextSparseMoeBlock

    args = SimpleNamespace(
        hidden_size=16,
        moe_intermediate_size=8,
        shared_expert_intermediate_size=8,
        norm_topk_prob=True,
        num_experts=256,
        num_experts_per_tok=8,
    )
    block = Qwen3NextSparseMoeBlock(args)

    assert block.scope_policy.backend == "arena"
    assert block.scope_policy.physical_experts == 120
    assert block.switch_mlp.down_proj.weight.shape[0] == 120


def test_tiered_model_has_separate_l1_and_tail_switches(tmp_path):
    layers = {str(layer): list(range(120)) for layer in range(40)}
    profile = tmp_path / "scope.json"
    profile.write_text(
        json.dumps(
            {
                "phases": {
                    "prefill": {"coding": layers},
                    "decode": {"coding": layers},
                }
            }
        )
    )
    store = tmp_path / "experts"
    store.mkdir()
    configure_qwen36_scope_policy(
        profile,
        "coding",
        store,
        96,
        backend="tiered",
        arena_tail_slots=24,
    )
    assert apply_qwen36_flesh_model_patch()

    from mlx_lm.models.qwen3_next import Qwen3NextSparseMoeBlock

    args = SimpleNamespace(
        hidden_size=16,
        moe_intermediate_size=8,
        shared_expert_intermediate_size=8,
        norm_topk_prob=True,
        num_experts=256,
        num_experts_per_tok=8,
    )
    block = Qwen3NextSparseMoeBlock(args)

    assert block.switch_mlp.down_proj.weight.shape[0] == 96
    assert block.tail_switch_mlp.down_proj.weight.shape[0] == 24


def test_arena_pins_hit_routes_while_loading_misses():
    requested, missing = _arena_route_ids(
        [171, 131, 83, 126, 8, 175, 178, 120],
        [63, -1, 104, -1, 109, 128, 130, -1],
    )

    # Expert 178 is already resident, but it must still be passed to resolve()
    # so its tail slot cannot be selected as a victim for 120/126/131.
    assert requested == (8, 83, 120, 126, 131, 171, 175, 178)
    assert missing == (120, 126, 131)


@pytest.mark.parametrize(
    ("mode", "expected_replaced", "protected"),
    (
        ("turbo", 2, (0, 1, 100, 101, 102, 103)),
        ("blast", 6, (0, 1)),
        ("tail3", 3, (0, 1, 100, 101, 102)),
        ("head3", 5, (0, 1, 100)),
    ),
)
def test_qwen_boost_replaces_only_the_configured_low_weight_misses(
    mode, expected_replaced, protected
):
    inds = mx.array([[[0, 1, 100, 101, 102, 103, 104, 105]]], dtype=mx.int32)
    scores = mx.array(
        [[[0.30, 0.25, 0.14, 0.11, 0.08, 0.06, 0.04, 0.02]]],
        dtype=mx.float32,
    )
    router = mx.zeros((1, 1, 256), dtype=mx.float32)
    candidate_ids = mx.arange(8, 20, dtype=mx.int32)
    router[..., candidate_ids] = mx.arange(12, 0, -1, dtype=mx.float32)
    available = mx.zeros((256,), dtype=mx.bool_)
    available[mx.array([0, 1, *range(8, 20)], dtype=mx.int32)] = True

    output, counters = _lossy_replace_routes(
        inds, scores, router, available, qwen36_lossy_policy(mode)
    )
    mx.eval(output, *counters)

    assert int(counters[0].item()) == expected_replaced
    assert tuple(int(value) for value in output.reshape(-1)[: len(protected)].tolist()) == protected
    assert all(
        8 <= int(value) < 20
        for value in output.reshape(-1)[len(protected) :].tolist()
    )


def test_qwen_boost_live_change_is_applied_at_next_decode_boundary():
    blocks = [SimpleNamespace(scope_lossy_policy=None) for _ in range(2)]
    owner = SimpleNamespace(
        _model=SimpleNamespace(
            language_model=SimpleNamespace(
                model=SimpleNamespace(
                    layers=[SimpleNamespace(mlp=block) for block in blocks]
                )
            )
        ),
        has_active_requests=lambda: True,
    )
    controller = Qwen36BoostController(owner)
    controller._apply("chat-1", "natural")

    result = controller.request("chat-1", "blast")
    assert result["queued"] is True
    assert all(block.scope_lossy_policy is None for block in blocks)

    controller.between_step()
    assert controller.mode == "blast"
    assert all(block.scope_lossy_policy.replace_count == 6 for block in blocks)


def test_dual_prefill_backend_never_captures_single_token_decode(
    tmp_path, monkeypatch
):
    class Switch:
        def __call__(self, x, inds):
            return mx.zeros((*inds.shape, x.shape[-1]), dtype=x.dtype)

    block = SimpleNamespace(
        scope_policy=SimpleNamespace(backend="flesh", store_path=tmp_path),
        scope_protected_expert_ids=tuple(range(8)),
        switch_mlp=Switch(),
    )
    monkeypatch.setenv("OMLX_QWEN36_PREFILL_BACKEND", "dual128-shared")
    x = mx.zeros((1, 1, 16), dtype=mx.float16)
    inds = mx.array([[[0, 1, 2, 3, 4, 5, 6, 7]]], dtype=mx.int32)
    scores = mx.ones((1, 1, 8), dtype=mx.float32) / 8

    output = _exact_scope_moe(block, x, inds, scores)
    mx.eval(output)
    assert output.shape == x.shape


def test_arena_resolve_does_not_evict_a_requested_hit(tmp_path, monkeypatch):
    arena = Qwen36DecodeArena(tmp_path)
    arena.initialize_layer(0, (0, 1, 2, 3, 4), protected_slots=2)
    store = SimpleNamespace(record_bytes=1)
    monkeypatch.setattr(arena, "_store", lambda _layer: store)
    monkeypatch.setattr(
        arena,
        "_read_records",
        lambda _store, ids: {expert_id: {} for expert_id in ids},
    )
    monkeypatch.setattr(arena, "_patch_switch", lambda *_args: None)

    try:
        lookup = arena.resolve(0, (3, 5), object(), expert_count=6)
    finally:
        arena._io_pool.shutdown(wait=True)

    assert lookup[3] == 3
    assert lookup[5] == 2


def test_tiered_cache_bypasses_l1_without_copying_to_tail(tmp_path, monkeypatch):
    cache = Qwen36TieredCache(tmp_path)
    cache.initialize_layer(0, (0, 1, 2, 3, 4, 5), (0, 1, 2))
    monkeypatch.setattr(
        cache,
        "_store",
        lambda _layer: (_ for _ in ()).throw(AssertionError("unexpected SSD read")),
    )

    try:
        lookup = cache.resolve(0, (1, 4), object(), expert_count=6)
    finally:
        cache._io_pool.shutdown(wait=True)

    assert lookup[1] == 1
    assert lookup[4] == -1
    assert cache.l1_bypass_routes == 2
    assert cache.tail_hit_routes == 0
    assert cache.ssd_experts_loaded == 0


def test_tiered_cache_evicts_least_frequently_used_tail_expert(
    tmp_path, monkeypatch
):
    cache = Qwen36TieredCache(tmp_path)
    cache.initialize_layer(0, (0, 1, 2, 3, 4, 5), (6, 7, 8))
    store = SimpleNamespace(record_bytes=1)
    monkeypatch.setattr(cache, "_store", lambda _layer: store)
    monkeypatch.setattr(
        cache,
        "_read_records",
        lambda _store, ids: {expert_id: {} for expert_id in ids},
    )
    monkeypatch.setattr(Qwen36DecodeArena, "_patch_switch", lambda *_args: None)

    try:
        cache.resolve(0, (6,), object(), expert_count=10)
        cache.resolve(0, (6,), object(), expert_count=10)
        cache.resolve(0, (7,), object(), expert_count=10)
        lookup = cache.resolve(0, (9,), object(), expert_count=10)
    finally:
        cache._io_pool.shutdown(wait=True)

    assert lookup[6] == 0
    assert lookup[7] == 1
    assert lookup[8] == -1
    assert lookup[9] == 2
