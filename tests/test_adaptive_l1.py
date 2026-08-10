from __future__ import annotations

import pytest

from omlx.patches.deepseek_v4.adaptive_l1 import (
    AdaptiveL1Config,
    AdaptiveL1Manager,
)


class _Catalog:
    def experts(self, scope, layer):
        assert scope == "coding"
        return tuple(range(256)) if layer < 3 else tuple(range(60))


def _manager(**kwargs):
    config = AdaptiveL1Config(enabled=True, **kwargs)
    return AdaptiveL1Manager(_Catalog(), config)


def test_default_policy_uses_128_token_review_and_retains_top20():
    config = AdaptiveL1Config(enabled=True)
    config.validate()
    assert config.early_check_tokens == 128
    assert config.pinned_slots == 20
    assert config.max_promotions_per_layer == 40


def test_session_observations_plan_bounded_tail_promotion():
    manager = _manager(
        min_observations=3,
        max_promotions_per_layer=2,
        max_layers_per_commit=2,
        pinned_slots=40,
    )
    state = manager.begin("chat-a", "coding")

    for _ in range(5):
        manager.observe_decode_miss(7, [91])
    for _ in range(4):
        manager.observe_decode_miss(8, [92])
    manager.observe_decode_miss(9, [93])

    plan = manager.plan(state)
    assert [(item.layer, item.promote) for item in plan] == [(7, 91), (8, 92)]
    assert all(item.evict >= 40 for item in plan)

    manager.commit(state, plan, reason="turn_end", seconds=0.25)
    assert 91 in state.layout[7]
    assert 92 in state.layout[8]
    assert tuple(state.layout[7][:40]) == tuple(range(40))
    assert state.epoch == 1
    assert state.turns == 1
    assert not state.observations


def test_large_plan_can_replace_all_but_retained_top20_in_one_layer():
    manager = _manager(
        min_observations=2,
        max_promotions_per_layer=40,
        max_layers_per_commit=40,
    )
    state = manager.begin("web", "coding")
    for expert in range(100, 140):
        manager.observe_decode_miss(7, [expert])
        manager.observe_decode_miss(7, [expert])
    plan = manager.plan(state)
    assert len(plan) == 40
    assert {item.layer for item in plan} == {7}
    manager.commit(state, plan, reason="early", seconds=0.1)
    assert set(range(100, 140)).issubset(state.layout[7])
    assert state.layout[7][:20] == tuple(range(20))


def test_gpu_route_window_updates_hit_utility_and_miss_candidates():
    manager = _manager(min_observations=2)
    state = manager.begin("web", "coding")
    histogram = [0] * 256
    histogram[21] = 9
    histogram[58] = 1
    histogram[100] = 7
    manager.observe_route_window(state, {7: histogram})
    assert state.utility[7][21] == 9
    assert state.utility[7][58] == 1
    assert state.observations[7][100] == 7
    plan = manager.plan(state)
    assert plan[0].promote == 100
    assert plan[0].evict == 59


def test_sessions_keep_independent_logical_layouts():
    manager = _manager(min_observations=2)
    first = manager.begin("one", "coding")
    manager.observe_decode_miss(3, [100])
    manager.observe_decode_miss(3, [100])
    manager.commit(first, manager.plan(first), reason="turn_end", seconds=0.1)

    second = manager.begin("two", "coding")
    assert 100 in first.layout[3]
    assert 100 not in second.layout[3]
    assert first.fingerprint() != second.fingerprint()


def test_manual_trigger_is_session_specific_and_one_shot():
    manager = _manager()
    manager.request_manual("one")
    assert manager.manual_pending("one")
    assert not manager.consume_manual("two")
    assert manager.consume_manual("one")
    assert not manager.consume_manual("one")


def test_session_mode_is_independent_and_off_is_persistent():
    manager = _manager()
    off = manager.begin("off-chat", "coding", mode="off")
    auto = manager.begin("auto-chat", "coding", mode="auto")
    assert off.mode == "off"
    assert auto.mode == "auto"
    assert manager.begin("off-chat", "coding").mode == "off"


def test_interval_gate_uses_tps_and_ssd_rate():
    manager = _manager(min_ssd_layer_rate=0.25, min_tps_ratio=0.9)
    assert manager.should_interval_optimize(
        tokens=256,
        seconds=32,
        ssd_publish_calls=3000,
        baseline_tps=10,
        predicted_savings_seconds=1.0,
        switch_cost_seconds=0.4,
        remaining_tokens=512,
    )
    assert not manager.should_interval_optimize(
        tokens=256,
        seconds=20,
        ssd_publish_calls=1000,
        baseline_tps=10,
        predicted_savings_seconds=1.0,
        switch_cost_seconds=0.4,
        remaining_tokens=512,
    )
    assert not manager.should_interval_optimize(
        tokens=256,
        seconds=32,
        ssd_publish_calls=3000,
        baseline_tps=10,
        predicted_savings_seconds=0.1,
        switch_cost_seconds=0.4,
        remaining_tokens=44,
    )


def test_early_gate_requires_gross_miss_rate_without_tps_baseline():
    manager = _manager(
        min_ssd_layer_rate=0.25,
        early_min_ssd_layer_rate=0.60,
    )
    common = dict(
        tokens=32,
        seconds=4,
        baseline_tps=None,
        predicted_savings_seconds=8.0,
        switch_cost_seconds=3.0,
        remaining_tokens=268,
        allow_without_tps=True,
        min_ssd_layer_rate=manager.config.early_min_ssd_layer_rate,
    )
    assert not manager.should_interval_optimize(ssd_publish_calls=700, **common)
    assert manager.should_interval_optimize(ssd_publish_calls=800, **common)


def test_post_commit_check_uses_stricter_miss_and_payback_gate():
    manager = _manager(
        min_ssd_layer_rate=0.25,
        post_commit_miss_multiplier=1.5,
        post_commit_payback_multiplier=2.0,
    )
    common = dict(
        tokens=256,
        seconds=32,
        ssd_publish_calls=3500,
        baseline_tps=10,
        predicted_savings_seconds=1.0,
        switch_cost_seconds=0.4,
        remaining_tokens=256,
    )
    assert manager.should_interval_optimize(**common)
    assert not manager.should_interval_optimize(**common, strict=True)


def test_exact_namespace_does_not_depend_on_l1_fingerprint(monkeypatch):
    from omlx.engine.flesh import DeepseekV4FleshEngine

    monkeypatch.setenv("OMLX_DEEPSEEK_V4_SCOPE_LOSSY_MODE", "exact")
    assert DeepseekV4FleshEngine._cache_namespace("coding", "abc") == (
        "deepseek-v4-flesh-v1",
        "coding",
        "exact",
    )


def test_lossy_namespace_includes_l1_fingerprint(monkeypatch):
    from omlx.engine.flesh import DeepseekV4FleshEngine

    monkeypatch.setenv("OMLX_DEEPSEEK_V4_SCOPE_LOSSY_MODE", "head2")
    assert DeepseekV4FleshEngine._cache_namespace("coding", "abc") == (
        "deepseek-v4-flesh-v1",
        "coding",
        "head2",
        "abc",
    )


def test_session_owned_namespace_is_stable_across_policy_changes():
    from omlx.engine.flesh import DeepseekV4FleshEngine

    assert DeepseekV4FleshEngine._cache_namespace(
        "coding", "old-layout", "tail2", "chat_123", True
    ) == (
        "deepseek-v4-flesh-v1",
        "coding",
        "session",
        "chat_123",
    )


def test_chat_request_accepts_ai2apps_session_id():
    from omlx.api.openai_models import ChatCompletionRequest

    request = ChatCompletionRequest(
        model="flesh",
        messages=[{"role": "user", "content": "hello"}],
        ai2apps_session_id="chat_123",
        ai2apps_l1_mode="off",
        ai2apps_engine_boost="turbo",
    )
    assert request.ai2apps_session_id == "chat_123"
    assert request.ai2apps_l1_mode == "off"
    assert request.ai2apps_engine_boost == "turbo"


def test_chat_request_rejects_unknown_engine_boost():
    from pydantic import ValidationError
    from omlx.api.openai_models import ChatCompletionRequest

    with pytest.raises(ValidationError, match="ai2apps_engine_boost"):
        ChatCompletionRequest(
            model="flesh",
            messages=[{"role": "user", "content": "hello"}],
            ai2apps_engine_boost="warp",
        )


def test_live_engine_boost_moves_kv_to_session_namespace():
    import threading
    from types import SimpleNamespace

    from omlx.engine.flesh import DeepseekV4FleshEngine

    engine = object.__new__(DeepseekV4FleshEngine)
    engine._engine_boost_session_id = "chat_123"
    engine._default_boost_mode = "natural"
    engine._engine_boost_modes = {}
    engine._pending_engine_boost = {}
    engine._session_owned_kv = set()
    engine._engine_boost_lock = threading.Lock()
    engine.has_active_requests = lambda: True
    applied = []
    engine._apply_engine_boost = lambda session_id, mode: applied.append(
        (session_id, mode)
    )
    request = SimpleNamespace(skip_cache_store=False, cache_extra_keys=None)
    engine._engine = SimpleNamespace(
        engine=SimpleNamespace(
            scheduler=SimpleNamespace(running={"req": request})
        )
    )
    engine._adaptive_l1 = None
    engine._adaptive_state = None
    engine._scope_bank = SimpleNamespace(current_scope="coding")
    engine._record_ssd_window = lambda token_count: None

    result = engine.request_engine_boost("chat_123", "blast")
    assert result["applies"] == "next_token"
    engine._between_decode_step(
        SimpleNamespace(
            outputs=[SimpleNamespace(completion_tokens=9, request_id="req")]
        )
    )
    assert applied == [("chat_123", "blast")]
    assert request.skip_cache_store is False
    assert request.cache_extra_keys == (
        "deepseek-v4-flesh-v1",
        "coding",
        "session",
        "chat_123",
    )


async def test_manual_optimize_endpoint_queues_without_engine_lease(monkeypatch):
    from types import SimpleNamespace

    from omlx.api.openai_models import AI2AppsL1OptimizeRequest
    from omlx import server

    calls = []
    engine = SimpleNamespace(
        request_l1_optimization=lambda session_id: (
            calls.append(session_id)
            or {"accepted": True, "queued": True, "session_id": session_id}
        )
    )
    pool = SimpleNamespace(
        resolve_model_id=lambda model, settings: "resolved",
        get_entry=lambda model: SimpleNamespace(engine=engine),
    )
    monkeypatch.setattr(server._server_state, "engine_pool", pool)
    result = await server.optimize_ai2apps_l1(
        AI2AppsL1OptimizeRequest(model="flesh", session_id="chat_123"), True
    )
    assert calls == ["chat_123"]
    assert result["status"] == "queued"
    assert result["model_id"] == "resolved"


async def test_engine_boost_endpoint_queues_without_engine_lease(monkeypatch):
    from types import SimpleNamespace

    from omlx.api.openai_models import AI2AppsEngineBoostRequest
    from omlx import server

    calls = []
    engine = SimpleNamespace(
        request_engine_boost=lambda session_id, mode: (
            calls.append((session_id, mode))
            or {
                "accepted": True,
                "queued": True,
                "session_id": session_id,
                "mode": mode,
            }
        )
    )
    pool = SimpleNamespace(
        resolve_model_id=lambda model, settings: "resolved",
        get_entry=lambda model: SimpleNamespace(engine=engine),
    )
    monkeypatch.setattr(server._server_state, "engine_pool", pool)
    result = await server.set_ai2apps_engine_boost(
        AI2AppsEngineBoostRequest(
            model="flesh", session_id="chat_123", mode="blast"
        ),
        True,
    )
    assert calls == [("chat_123", "blast")]
    assert result["status"] == "queued"
