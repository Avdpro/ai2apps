from __future__ import annotations

import json

import pytest

from omlx.patches.qwen3_6_flesh.scope_policy import (
    MEMORY_TIER_EXPERTS,
    NUM_LAYERS,
    Qwen36ScopeCatalog,
    clear_qwen36_scope_policy,
    configure_qwen36_scope_policy,
    disable_qwen36_scope_policy,
    estimated_resident_bytes,
    load_qwen36_scope_policy,
)


@pytest.fixture(autouse=True)
def _clear_policy():
    clear_qwen36_scope_policy()
    yield
    clear_qwen36_scope_policy()


def _profile(tmp_path, *, experts=120):
    phases = {}
    for phase, shift in (("prefill", 1), ("decode", 0)):
        phases[phase] = {}
        for scope_index, scope in enumerate(("coding", "math_logic")):
            phases[phase][scope] = {
                str(layer): [
                    (expert + shift + scope_index + layer) % 256
                    for expert in range(experts)
                ]
                for layer in range(NUM_LAYERS)
            }
    path = tmp_path / "qwen-scope.json"
    path.write_text(json.dumps({"version": 1, "phases": phases}))
    return path


def test_loads_existing_dmoe_joint_hotset_shape(tmp_path):
    catalog = Qwen36ScopeCatalog.load(_profile(tmp_path))

    assert catalog.scope_ids == ("coding", "math_logic")
    assert len(catalog.experts("coding", 0, phase="decode")) == 120
    assert catalog.experts("coding", 0, phase="prefill")[0] == 1
    assert catalog.experts("coding", 39, phase="decode")[0] == 39


def test_qwen_policy_is_independent_and_has_all_40_moe_layers(tmp_path):
    profile = _profile(tmp_path)
    store = tmp_path / "experts"
    store.mkdir()
    configure_qwen36_scope_policy(profile, "coding", store, 96)

    policy = load_qwen36_scope_policy()

    assert policy is not None
    assert policy.resident_experts == 96
    assert len(policy.experts(0)) == 96
    assert len(policy.experts(39)) == 96
    assert policy.experts(0, phase="prefill") != policy.experts(0, phase="decode")


def test_full_execution_disables_configured_qwen_scope_policy(tmp_path):
    store = tmp_path / "experts"
    store.mkdir()
    configure_qwen36_scope_policy(_profile(tmp_path), "coding", store, 96)

    disable_qwen36_scope_policy()

    assert load_qwen36_scope_policy() is None


def test_qwen_tiers_do_not_reuse_deepseek_top20_40_60():
    assert MEMORY_TIER_EXPERTS == {"lean": 120, "compact": 160, "optimal": 192}
    assert estimated_resident_bytes(96) == 96 * 40 * 1_769_472


def test_tiered_policy_reports_separate_l1_and_execution_capacity(tmp_path):
    store = tmp_path / "experts"
    store.mkdir()
    configure_qwen36_scope_policy(
        _profile(tmp_path),
        "coding",
        store,
        120,
        backend="tiered",
        arena_tail_slots=24,
    )

    policy = load_qwen36_scope_policy()

    assert policy is not None
    assert policy.physical_experts == 144
    assert policy.execution_experts == 24


def test_rejects_profile_too_short_for_selected_bank(tmp_path):
    profile = _profile(tmp_path, experts=80)
    store = tmp_path / "experts"
    store.mkdir()
    configure_qwen36_scope_policy(profile, "coding", store, 96)

    with pytest.raises(ValueError, match="Top-96 requested"):
        load_qwen36_scope_policy()
