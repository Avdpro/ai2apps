from __future__ import annotations

from types import SimpleNamespace

import mlx.core as mx

from omlx.patches.glm5_next_cache.boost import replace_missed_routes
from omlx.patches.qwen38_next_cache.boost import (
    normalize_qwen4_boost,
    qwen4_boost_policy,
    set_qwen4_boost_mode,
)


def test_qwen4_product_and_experimental_boost_policies():
    assert qwen4_boost_policy("natural") is None
    assert qwen4_boost_policy("turbo").protected_top == 5
    assert qwen4_boost_policy("turbo").replace_count == 5
    assert qwen4_boost_policy("blast").protected_top == 3
    assert qwen4_boost_policy("top5").replace_count == 5
    assert qwen4_boost_policy("top6").replace_count == 4
    assert qwen4_boost_policy("top3").replace_count == 7


def test_qwen4_boost_replaces_only_low_weight_misses():
    inds = mx.array([[[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]]], dtype=mx.int32)
    scores = mx.array([[[0.40, 0.20, 0.10, 0.08, 0.06, 0.05, 0.04, 0.03, 0.02, 0.02]]])
    router = mx.array([[[0.40, 0.20, 0.10, 0.08, 0.06, 0.05, 0.04, 0.03,
                         0.02, 0.02, 0.09, 0.07, 0.01]]])
    available = mx.array(
        [True, True, True, True, True, True, True, False, False, False,
         True, True, False]
    )
    output, counters = replace_missed_routes(
        inds, scores, router, available, qwen4_boost_policy("top7")
    )
    mx.eval(output, *counters)
    routed = output.reshape(-1).tolist()
    assert routed[:7] == list(range(7))
    assert set(routed[7:]) & {7, 8, 9}
    assert {10, 11}.issubset(routed[7:])
    assert tuple(int(value.item()) for value in counters) == (2, 3, 1)


def test_qwen4_runtime_mode_switch_updates_all_layers():
    blocks = [SimpleNamespace(boost_policy=None, boost_mode="natural") for _ in range(3)]
    model = SimpleNamespace(
        language_model=SimpleNamespace(
            model=SimpleNamespace(
                layers=[SimpleNamespace(mlp=block) for block in blocks]
            )
        )
    )
    assert set_qwen4_boost_mode(model, "top4") == 3
    assert all(block.boost_mode == "top4" for block in blocks)
    assert all(block.boost_policy.protected_top == 4 for block in blocks)


def test_qwen4_boost_validation():
    assert normalize_qwen4_boost(None) == "natural"
    try:
        normalize_qwen4_boost("top2")
    except ValueError as error:
        assert "top2" not in str(error).split(":", 1)[-1]
    else:
        raise AssertionError("invalid Qwen4 Boost mode was accepted")
