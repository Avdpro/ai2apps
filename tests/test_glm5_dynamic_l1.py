from omlx.patches.glm5_next_cache.policy import (
    EMPTY,
    PROBATION,
    PROTECTED,
    DynamicL1Policy,
)


def test_cold_dynamic_l1_starts_empty_and_fills_top8():
    policy = DynamicL1Policy(capacity=16, num_experts=288)
    assert policy.state(3).expert_ids == [-1] * 16

    plan = policy.plan(3, tuple(range(8)))
    assert plan.missing == tuple(range(8))
    assert plan.slots == tuple(range(8))
    assert policy.lookup(3) == (-1,) * 288

    policy.publish(3, plan)
    assert policy.state(3).expert_ids[:8] == list(range(8))
    assert policy.state(3).segments[:8] == [PROBATION] * 8


def test_dynamic_l1_defaults_to_80_slots():
    policy = DynamicL1Policy()
    assert policy.capacity == 80
    assert policy.state(3).expert_ids == [-1] * 80


def test_glm5_multimodal_runtime_defaults_to_top64_hot16(monkeypatch):
    from omlx.patches.glm5_next_cache.runtime import _slots, _tail_slots

    for name in (
        "OMLX_GLM5_DYNAMIC_SLOTS",
        "OMLX_GLM5_TAIL_SLOTS",
        "OMLX_GLM5_VISION_L1_RESERVE_SLOTS",
        "OMLX_GLM5_MTP_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)

    assert _tail_slots() == 16
    assert _slots() == 64


def test_glm5_text_runtime_can_restore_top80_hot16(monkeypatch):
    from omlx.patches.glm5_next_cache.runtime import _slots, _tail_slots

    monkeypatch.setenv("OMLX_GLM5_DYNAMIC_SLOTS", "96")
    monkeypatch.setenv("OMLX_GLM5_TAIL_SLOTS", "16")
    monkeypatch.setenv("OMLX_GLM5_VISION_L1_RESERVE_SLOTS", "0")
    monkeypatch.delenv("OMLX_GLM5_MTP_ENABLED", raising=False)

    assert _tail_slots() == 16
    assert _slots() == 80


def test_hits_are_pinned_while_batch_misses_reserve_victims():
    policy = DynamicL1Policy(capacity=4, num_experts=16, protected_ratio=0.5)
    first = policy.plan(0, (0, 1, 2, 3))
    policy.publish(0, first)

    plan = policy.plan(0, (0, 4, 5))
    assert plan.next_state.expert_ids[0] == 0
    assert set(plan.missing) == {4, 5}
    assert 0 not in plan.slots
    policy.publish(0, plan)
    lookup = policy.lookup(0)
    assert lookup[0] == 0
    assert lookup[4] >= 0 and lookup[5] >= 0


def test_second_hit_promotes_to_protected_and_probation_evicts_first():
    policy = DynamicL1Policy(capacity=4, num_experts=16, protected_ratio=0.5)
    policy.publish(0, policy.plan(0, (0, 1, 2, 3)))
    policy.publish(0, policy.plan(0, (2,)))
    state = policy.state(0)
    assert state.segments[state.expert_ids.index(2)] == PROTECTED

    policy.publish(0, policy.plan(0, (4,)))
    state = policy.state(0)
    assert 2 in state.expert_ids
    assert 0 not in state.expert_ids
    assert EMPTY not in state.segments


def test_publish_is_atomic_from_policy_perspective():
    policy = DynamicL1Policy(capacity=4, num_experts=8)
    plan = policy.plan(1, (6, 7))
    assert all(slot == -1 for slot in policy.lookup(1))
    policy.publish(1, plan)
    assert policy.lookup(1)[6:] == (0, 1)


def test_replay_preserves_each_topk_batch_capacity():
    policy = DynamicL1Policy(capacity=4, num_experts=12)
    final = policy.replay(2, [(0, 1), (1, 2), (2, 3), (3, 4)])
    assert 3 in final.expert_ids and 4 in final.expert_ids


def test_device_slot_counts_promote_hot_entry_without_changing_tags():
    policy = DynamicL1Policy(capacity=4, num_experts=12, protected_ratio=0.5)
    policy.publish(0, policy.plan(0, (3, 4, 5, 6)))
    before = policy.state(0).expert_ids
    policy.observe_slot_counts(0, (0, 7, 1, 0))
    state = policy.state(0)
    assert state.expert_ids == before
    assert state.segments[1] == PROTECTED
    assert state.last_used[1] == max(state.last_used)
