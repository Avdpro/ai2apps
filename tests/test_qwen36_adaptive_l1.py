from __future__ import annotations

from types import SimpleNamespace

from omlx.patches.deepseek_v4.adaptive_l1 import (
    AdaptiveL1Config,
    AdaptiveL1Manager,
)
from omlx.patches.qwen3_6_flesh.adaptive_l1 import Qwen36AdaptiveBank


class _Catalog:
    def experts(self, _scope: str, layer: int):
        return tuple((layer + value) % 256 for value in range(256))


def test_qwen_manager_uses_all_40_layers_and_configured_bank_size():
    config = AdaptiveL1Config(
        enabled=True,
        pinned_slots=2,
        max_promotions_per_layer=6,
        max_layers_per_commit=40,
        bank_size=8,
        layer_start=0,
        layer_count=40,
    )
    manager = AdaptiveL1Manager(_Catalog(), config)
    state = manager.begin("chat", "coding")

    assert len(state.layout) == 40
    assert all(len(layer) == 8 for layer in state.layout)

    manager.observe_routes(0, [0, 1, 40, 40, 40])
    plan = manager.plan(state, min_observations=1)
    assert any(item.layer == 0 and item.promote == 40 for item in plan)
    assert all(item.evict not in state.layout[item.layer][:2] for item in plan)


def test_manual_plan_can_exceed_auto_promotion_cap():
    config = AdaptiveL1Config(
        enabled=True,
        pinned_slots=2,
        max_promotions_per_layer=2,
        max_layers_per_commit=40,
        min_observations=1,
        bank_size=8,
        layer_start=0,
        layer_count=40,
    )
    manager = AdaptiveL1Manager(_Catalog(), config)
    state = manager.begin("chat", "coding")
    manager.observe_routes(0, [40, 41, 42, 43, 44, 45])

    assert len(manager.plan(state)) == 2
    assert len(manager.plan(state, max_promotions=6)) == 6


def test_qwen_tail_removes_promoted_duplicates_without_moving_retained_slots():
    desired = (0, 1, 8, 9)
    tail = Qwen36AdaptiveBank._tail(
        desired,
        current_tail=(8, 4, 5),
        old_l1=(0, 1, 2, 3),
        size=3,
    )

    assert tail == (2, 4, 5)
    assert not set(tail) & set(desired)
    assert len(set(tail)) == 3


def test_qwen_adaptive_bank_stats_start_empty():
    policy = SimpleNamespace(store_path="/tmp", backend="flesh")
    bank = Qwen36AdaptiveBank(SimpleNamespace(), policy)
    assert bank.stats() == {
        "commits": 0,
        "layers_rewritten": 0,
        "experts_loaded": 0,
        "experts_reused": 0,
        "slots_patched": 0,
        "bytes_loaded": 0,
        "ssd_read_seconds": 0.0,
        "gpu_snapshot_seconds": 0.0,
        "gpu_patch_seconds": 0.0,
        "sync_seconds": 0.0,
        "seconds": 0.0,
        "prefill_swaps": 0,
    }


def test_qwen_initial_tail_is_deterministic_and_disjoint():
    tail = Qwen36AdaptiveBank._initial_tail((0, 2, 4, 6), 3)

    assert tail == (1, 3, 5)
