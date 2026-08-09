from __future__ import annotations

import json

import pytest

from omlx.patches.deepseek_v4.scope_policy import (
    DEFAULT_PROBE_DEPTH,
    LOSSY_MODE_ENV,
    LOSSY_THRESHOLD_ENV,
    PROBE_DEPTH_ENV,
    PROFILE_ENV,
    SCOPE_ENV,
    STORE_ENV,
    configure_scope_resident_experts,
    load_scope_lossy_policy_from_env,
    load_scope_policy_from_env,
    load_scope_probe_depth_from_env,
    parse_expert_key,
    scope_lossy_policy_for_mode,
)


@pytest.fixture(autouse=True)
def _clear_policy_cache():
    configure_scope_resident_experts(60)
    load_scope_lossy_policy_from_env.cache_clear()
    load_scope_policy_from_env.cache_clear()
    load_scope_probe_depth_from_env.cache_clear()
    yield
    configure_scope_resident_experts(60)
    load_scope_lossy_policy_from_env.cache_clear()
    load_scope_policy_from_env.cache_clear()
    load_scope_probe_depth_from_env.cache_clear()


def _profile(tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    layers = {str(layer): list(range(60)) for layer in range(3, 43)}
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "format": "dmoe-deepseek-tiered-policy",
                "scopes": {"coding": layers},
            }
        )
    )
    return profile, store


def test_scope_policy_keeps_hash_full_and_score_top60(tmp_path, monkeypatch):
    profile, store = _profile(tmp_path)
    monkeypatch.setenv(PROFILE_ENV, str(profile))
    monkeypatch.setenv(SCOPE_ENV, "coding")
    monkeypatch.setenv(STORE_ENV, str(store))

    policy = load_scope_policy_from_env()

    assert policy is not None
    assert policy.experts(0) == tuple(range(256))
    assert policy.experts(2) == tuple(range(256))
    assert policy.experts(3) == tuple(range(60))
    assert policy.scope_name == "coding"


def test_scope_policy_can_build_smaller_resident_bank(tmp_path, monkeypatch):
    profile, store = _profile(tmp_path)
    monkeypatch.setenv(PROFILE_ENV, str(profile))
    monkeypatch.setenv(SCOPE_ENV, "coding")
    monkeypatch.setenv(STORE_ENV, str(store))
    configure_scope_resident_experts(20)

    policy = load_scope_policy_from_env()

    assert policy is not None
    assert policy.resident_experts == 20
    assert policy.experts(3) == tuple(range(20))


def test_scope_policy_requires_all_three_environment_values(tmp_path, monkeypatch):
    profile, _ = _profile(tmp_path)
    monkeypatch.setenv(PROFILE_ENV, str(profile))

    with pytest.raises(ValueError, match="must be set together"):
        load_scope_policy_from_env()


def test_parse_expert_key():
    assert parse_expert_key("model.layers.17.ffn.experts.203.w1.weight") == (17, 203)
    assert parse_expert_key("model.layers.17.ffn.shared_experts.w1.weight") is None


@pytest.mark.parametrize(
    ("raw", "mode", "tail", "threshold"),
    [
        ("conservative", "conservative", 2, 0.10),
        ("tail1", "tail1", 1, None),
        ("aggressive-2", "tail2", 2, None),
        ("head2", "head2", 4, None),
    ],
)
def test_scope_lossy_policy_modes(monkeypatch, raw, mode, tail, threshold):
    monkeypatch.setenv(LOSSY_MODE_ENV, raw)
    policy = load_scope_lossy_policy_from_env()
    assert policy is not None
    assert policy.mode == mode
    assert policy.tail_count == tail
    assert policy.max_weight_share == threshold


def test_scope_lossy_policy_exact_is_default(monkeypatch):
    monkeypatch.delenv(LOSSY_MODE_ENV, raising=False)
    assert load_scope_lossy_policy_from_env() is None


def test_engine_boost_policy_mapping_does_not_mutate_environment(monkeypatch):
    monkeypatch.setenv(LOSSY_MODE_ENV, "exact")
    assert scope_lossy_policy_for_mode("exact") is None
    assert scope_lossy_policy_for_mode("tail2").mode == "tail2"
    assert scope_lossy_policy_for_mode("head2").mode == "head2"
    assert load_scope_lossy_policy_from_env() is None


def test_scope_lossy_policy_validates_threshold(monkeypatch):
    monkeypatch.setenv(LOSSY_MODE_ENV, "conservative")
    monkeypatch.setenv(LOSSY_THRESHOLD_ENV, "1.1")
    with pytest.raises(ValueError, match="between 0 and 1"):
        load_scope_lossy_policy_from_env()


def test_scope_probe_depth_defaults_to_16(monkeypatch):
    monkeypatch.delenv(PROBE_DEPTH_ENV, raising=False)
    assert DEFAULT_PROBE_DEPTH == 16
    assert load_scope_probe_depth_from_env() == 16


def test_scope_probe_depth_can_use_all_layers(monkeypatch):
    monkeypatch.setenv(PROBE_DEPTH_ENV, "43")
    assert load_scope_probe_depth_from_env() == 43


@pytest.mark.parametrize("raw", ["three", "3", "44"])
def test_scope_probe_depth_validates_value(monkeypatch, raw):
    monkeypatch.setenv(PROBE_DEPTH_ENV, raw)
    with pytest.raises(ValueError, match=PROBE_DEPTH_ENV):
        load_scope_probe_depth_from_env()
    load_scope_lossy_policy_from_env,
