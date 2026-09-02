from types import SimpleNamespace

import mlx.core as mx
import pytest

from omlx.patches.glm5_next_cache.boost import (
    Glm5BoostController,
    available_experts,
    glm5_lossy_policy,
    normalize_glm5_boost,
    replace_missed_routes,
)


def test_glm5_natural_is_exact_and_modes_match_top8_contract():
    assert glm5_lossy_policy("natural") is None
    assert glm5_lossy_policy("turbo").replace_count == 3
    assert glm5_lossy_policy("blast").replace_count == 5
    assert glm5_lossy_policy("head3").replace_count == 5
    with pytest.raises(ValueError, match="natural, turbo, blast"):
        normalize_glm5_boost("warp")


def test_glm5_controller_product_default_is_natural_exact():
    controller = Glm5BoostController(SimpleNamespace())

    assert controller.default_mode == "natural"
    assert controller.mode == "natural"
    assert glm5_lossy_policy(controller.mode) is None


def test_glm5_available_mask_unions_l1_and_hot():
    l1 = mx.array([-1, 0, -1, -1], dtype=mx.int32)
    hot = mx.array([-1, -1, 0, -1], dtype=mx.int32)
    assert available_experts(l1, hot).tolist() == [False, True, True, False]


@pytest.mark.parametrize(
    ("mode", "replaced", "protected"),
    (("turbo", 3, (0, 1, 100, 101, 102)), ("blast", 5, (0, 1, 100))),
)
def test_glm5_boost_replaces_only_eligible_low_weight_misses(mode, replaced, protected):
    inds = mx.array([[[0, 1, 100, 101, 102, 103, 104, 105]]], dtype=mx.int32)
    weights = mx.array(
        [[[0.30, 0.25, 0.14, 0.11, 0.08, 0.06, 0.04, 0.02]]],
        dtype=mx.float32,
    )
    router = mx.zeros((1, 1, 288), dtype=mx.float32)
    candidate_ids = mx.arange(8, 20, dtype=mx.int32)
    router[..., candidate_ids] = mx.arange(12, 0, -1, dtype=mx.float32)
    available = mx.zeros((288,), dtype=mx.bool_)
    available[mx.array([0, 1, *range(8, 20)], dtype=mx.int32)] = True

    output, counters = replace_missed_routes(
        inds, weights, router, available, glm5_lossy_policy(mode)
    )
    mx.eval(output, *counters)

    assert int(counters[0].item()) == replaced
    assert int(counters[1].item()) == 6
    assert int(counters[2].item()) == 6 - replaced
    flat = tuple(int(value) for value in output.reshape(-1).tolist())
    assert flat[: len(protected)] == protected
    assert all(8 <= value < 20 for value in flat[len(protected) :])


def test_glm5_boost_keeps_high_weight_misses_for_ssd():
    inds = mx.array([[[100, 0, 1, 2, 3, 4, 5, 101]]], dtype=mx.int32)
    weights = mx.array(
        [[[0.40, 0.20, 0.12, 0.09, 0.07, 0.05, 0.04, 0.03]]],
        dtype=mx.float32,
    )
    router = mx.arange(288, dtype=mx.float32).reshape(1, 1, -1)
    available = mx.zeros((288,), dtype=mx.bool_)
    available[mx.array([*range(8, 32)], dtype=mx.int32)] = True

    output, counters = replace_missed_routes(
        inds, weights, router, available, glm5_lossy_policy("blast")
    )
    mx.eval(output, *counters)

    assert int(output[0, 0, 0].item()) == 100
    assert int(counters[0].item()) == 5
    assert int(counters[2].item()) == 3


def test_glm5_prefill_boost_falls_back_when_resident_candidates_are_short():
    inds = mx.array(
        [[[100, 101, 102, 103, 104, 105, 106, 107]]], dtype=mx.int32
    )
    weights = mx.array(
        [[[0.30, 0.25, 0.14, 0.11, 0.08, 0.06, 0.04, 0.02]]],
        dtype=mx.float32,
    )
    router = mx.zeros((1, 1, 288), dtype=mx.float32)
    router[..., 8] = 1.0
    available = mx.zeros((288,), dtype=mx.bool_)
    available[8] = True

    output, counters = replace_missed_routes(
        inds, weights, router, available, glm5_lossy_policy("turbo")
    )
    mx.eval(output, *counters)

    assert int(counters[0].item()) == 1
    assert int(counters[1].item()) == 8
    assert int(counters[2].item()) == 7
    assert sum(int(value) == 8 for value in output.reshape(-1).tolist()) == 1


@pytest.mark.asyncio
async def test_glm5_boost_modes_are_isolated_by_system_session():
    blocks = [
        SimpleNamespace(
            boost_policy=None,
            boost_stats={
                "routes_replaced": 0,
                "misses_before": 0,
                "misses_after": 0,
            },
        )
        for _ in range(2)
    ]
    owner = SimpleNamespace(
        _engine=SimpleNamespace(engine=SimpleNamespace(_mlx_executor=None)),
        _vlm_model=SimpleNamespace(
            language_model=SimpleNamespace(
                model=SimpleNamespace(
                    layers=[SimpleNamespace(mlp=block) for block in blocks]
                )
            )
        ),
        has_active_requests=lambda: False,
    )
    controller = Glm5BoostController(owner)

    await controller.prepare(
        {"flesh_session_id": "chat-a", "flesh_boost_mode": "turbo"}
    )
    await controller.prepare(
        {"flesh_session_id": "chat-b", "flesh_boost_mode": "natural"}
    )
    await controller.prepare({"flesh_session_id": "chat-a"})

    assert controller.session_id == "chat-a"
    assert controller.mode == "turbo"
    assert controller.modes == {"chat-a": "turbo", "chat-b": "natural"}
    assert all(block.boost_policy.replace_count == 3 for block in blocks)


@pytest.mark.asyncio
async def test_glm5_split_prefill_decode_modes_switch_at_final_chunk():
    block = SimpleNamespace(boost_policy=None)
    owner = SimpleNamespace(
        _engine=SimpleNamespace(engine=SimpleNamespace(_mlx_executor=None)),
        _vlm_model=SimpleNamespace(
            language_model=SimpleNamespace(
                model=SimpleNamespace(layers=[SimpleNamespace(mlp=block)])
            )
        ),
        has_active_requests=lambda: True,
    )
    controller = Glm5BoostController(owner)
    await controller.prepare(
        {
            "flesh_session_id": "chat-split",
            "flesh_prefill_boost_mode": "turbo",
            "flesh_decode_boost_mode": "blast",
        }
    )

    assert controller.mode == "turbo"
    controller.between_prefill_chunk(
        object(), tokens=1024, processed_tokens=1024, remaining_tokens=0
    )
    assert controller.mode == "blast"


def test_glm5_active_boost_switch_applies_at_scheduler_boundary():
    block = SimpleNamespace(boost_policy=None)
    owner = SimpleNamespace(
        _engine=SimpleNamespace(engine=SimpleNamespace()),
        _vlm_model=SimpleNamespace(
            language_model=SimpleNamespace(
                model=SimpleNamespace(layers=[SimpleNamespace(mlp=block)])
            )
        ),
        has_active_requests=lambda: True,
    )
    controller = Glm5BoostController(owner)
    controller._apply("chat-live", "natural")

    result = controller.request("chat-live", "blast")

    assert result["queued"] is True
    assert result["applies"] == "next_token"
    assert controller.mode == "natural"

    controller.on_scheduler_step(
        SimpleNamespace(outputs=[SimpleNamespace(completion_tokens=1)])
    )

    assert controller.mode == "blast"
    assert block.boost_policy.replace_count == 5
