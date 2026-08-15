from __future__ import annotations

from types import SimpleNamespace

from omlx.patches.deepseek_v4.adaptive_l1 import (
    AdaptiveL1Config,
    AdaptiveL1Manager,
)
from omlx.patches.qwen3_6_flesh.adaptive_l1 import (
    Qwen36AdaptiveBank,
    Qwen36AdaptiveController,
)


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
        prefill_max_promotions_per_layer=6,
        prefill_recheck_max_promotions_per_layer=4,
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
        prefill_max_promotions_per_layer=6,
        prefill_recheck_max_promotions_per_layer=4,
    )
    manager = AdaptiveL1Manager(_Catalog(), config)
    state = manager.begin("chat", "coding")
    manager.observe_routes(0, [40, 41, 42, 43, 44, 45])

    assert len(manager.plan(state)) == 2
    assert len(manager.plan(state, max_promotions=6)) == 6


def test_manual_request_can_be_cancelled_without_counting_as_trigger():
    config = AdaptiveL1Config(
        enabled=True,
        pinned_slots=2,
        max_promotions_per_layer=2,
        max_layers_per_commit=40,
        bank_size=8,
        layer_start=0,
        layer_count=40,
        prefill_max_promotions_per_layer=2,
        prefill_recheck_max_promotions_per_layer=1,
    )
    manager = AdaptiveL1Manager(_Catalog(), config)
    manager.request_manual("chat")

    assert manager.cancel_manual("chat") is True
    assert manager.manual_pending("chat") is False
    assert manager.manual_triggers == 0


def test_session_scope_is_sticky_and_separate_between_sessions():
    config = AdaptiveL1Config(
        enabled=True,
        pinned_slots=2,
        max_promotions_per_layer=2,
        max_layers_per_commit=40,
        bank_size=8,
        layer_start=0,
        layer_count=40,
        prefill_max_promotions_per_layer=2,
        prefill_recheck_max_promotions_per_layer=1,
    )
    manager = AdaptiveL1Manager(_Catalog(), config)
    first = manager.begin("first", "coding")
    first.layout[0] = (*first.layout[0][:-1], 200)
    second = manager.begin("second", "writing_creative")

    assert manager.session_scope("first") == "coding"
    assert manager.session_scope("second") == "writing_creative"
    assert manager.session_scope("missing") is None
    assert second.layout != first.layout


def test_qwen_prefill_uses_current_adaptive_l1_without_base_swap():
    controller = object.__new__(Qwen36AdaptiveController)
    controller.bank = SimpleNamespace(
        activate=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Prefill must not rebase L1")
        )
    )

    assert controller.stable_prefill(lambda: "current-layout") == "current-layout"


async def test_qwen_rebases_only_when_switching_sessions():
    catalog = _Catalog()
    catalog.scope_ids = {"coding": 0, "writing_creative": 1}
    config = AdaptiveL1Config(
        enabled=True,
        pinned_slots=2,
        max_promotions_per_layer=2,
        max_layers_per_commit=40,
        bank_size=8,
        layer_start=0,
        layer_count=40,
        prefill_max_promotions_per_layer=2,
        prefill_recheck_max_promotions_per_layer=1,
    )
    manager = AdaptiveL1Manager(catalog, config)
    activations = []
    controller = object.__new__(Qwen36AdaptiveController)
    controller.manager = manager
    controller.policy = SimpleNamespace(scope_name="coding", catalog=catalog)
    controller.owner = SimpleNamespace(
        _engine=SimpleNamespace(engine=SimpleNamespace(_mlx_executor=None))
    )
    controller.bank = SimpleNamespace(
        activate=lambda layout, *, reset_mutable: activations.append(
            (list(layout), reset_mutable)
        )
    )
    controller.stale_manual_cancellations = 0

    await controller.prepare({"flesh_session_id": "a"}, scope_name="coding")
    saved_a = manager.sessions["a"].layout
    saved_a[0] = (*saved_a[0][:-1], 200)
    await controller.prepare({"flesh_session_id": "a"}, scope_name="coding")
    await controller.prepare(
        {"flesh_session_id": "b"}, scope_name="writing_creative"
    )
    await controller.prepare({"flesh_session_id": "a"}, scope_name="coding")

    assert [reset for _, reset in activations] == [True, False, True, True]
    assert activations[-1][0] == saved_a


def test_qwen_rejects_manual_l1_when_no_decode_is_active():
    controller = object.__new__(Qwen36AdaptiveController)
    controller.manager = SimpleNamespace(
        cancel_manual=lambda _session_id: False,
        request_manual=lambda _session_id: (_ for _ in ()).throw(
            AssertionError("idle request must not be queued")
        ),
    )
    controller.owner = SimpleNamespace(has_active_requests=lambda: False)
    controller.idle_manual_rejections = 0

    assert controller.request("chat") == {
        "accepted": False,
        "reason": "no_active_decode",
    }
    assert controller.idle_manual_rejections == 1


def test_qwen_accepts_manual_l1_during_active_decode():
    queued = []
    controller = object.__new__(Qwen36AdaptiveController)
    controller.manager = SimpleNamespace(
        cancel_manual=lambda _session_id: False,
        request_manual=queued.append,
    )
    controller.owner = SimpleNamespace(has_active_requests=lambda: True)
    controller.idle_manual_rejections = 0

    assert controller.request("chat") == {
        "accepted": True,
        "queued": True,
        "session_id": "chat",
    }
    assert queued == ["chat"]


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
