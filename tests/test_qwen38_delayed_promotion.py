from __future__ import annotations

from omlx.patches.qwen38_next_cache.runtime import (
    Qwen4DynamicCache,
    _promotion_enable_after,
)


def test_delayed_promotion_stays_off_through_threshold(tmp_path):
    cache = Qwen4DynamicCache(
        tmp_path,
        capacity=16,
        tail_slots=10,
        l1_promotions_per_layer=4,
        num_experts=32,
        promotion_enable_after=3,
    )

    assert [cache.decode_promotion_limit(7) for _ in range(4)] == [0, 0, 0, 4]
    assert cache.decode_promotion_limit(8) == 0


def test_prefill_reset_restarts_delayed_promotion(tmp_path):
    cache = Qwen4DynamicCache(
        tmp_path,
        capacity=16,
        tail_slots=10,
        l1_promotions_per_layer=4,
        num_experts=32,
        promotion_enable_after=1,
    )

    assert cache.decode_promotion_limit(3) == 0
    assert cache.decode_promotion_limit(3) == 4
    cache.reset_hot(3)
    assert cache.decode_promotion_limit(3) == 0
    assert cache.stats()["decode_steps_by_layer"] == {3: 1}


def test_zero_delay_enables_configured_limit_immediately(tmp_path):
    cache = Qwen4DynamicCache(
        tmp_path,
        capacity=16,
        tail_slots=10,
        l1_promotions_per_layer=2,
        num_experts=32,
        promotion_enable_after=0,
    )

    assert cache.decode_promotion_limit(0) == 2


def test_promotion_delay_environment(monkeypatch):
    monkeypatch.delenv("OMLX_QWEN4_L1_PROMOTION_ENABLE_AFTER", raising=False)
    assert _promotion_enable_after() == 128
    monkeypatch.setenv("OMLX_QWEN4_L1_PROMOTION_ENABLE_AFTER", "64")
    assert _promotion_enable_after() == 64


def test_prefill_canonical_reuse_and_l1_retention_default_on(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("OMLX_QWEN4_PREFILL_CANONICAL_REUSE", raising=False)
    monkeypatch.delenv("OMLX_QWEN4_PREFILL_RETAIN_L1", raising=False)
    cache = Qwen4DynamicCache(
        tmp_path,
        capacity=16,
        tail_slots=10,
        l1_promotions_per_layer=0,
        num_experts=32,
    )

    assert cache.prefill_canonical_reuse is True
    assert cache.prefill_retain_l1 is True


def test_prefill_reuse_defaults_can_be_disabled_for_ab(tmp_path, monkeypatch):
    monkeypatch.setenv("OMLX_QWEN4_PREFILL_CANONICAL_REUSE", "0")
    monkeypatch.setenv("OMLX_QWEN4_PREFILL_RETAIN_L1", "0")
    cache = Qwen4DynamicCache(
        tmp_path,
        capacity=16,
        tail_slots=10,
        l1_promotions_per_layer=0,
        num_experts=32,
    )

    assert cache.prefill_canonical_reuse is False
    assert cache.prefill_retain_l1 is False
