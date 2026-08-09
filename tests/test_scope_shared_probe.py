from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def probe_module():
    path = Path(__file__).parents[1] / "scripts" / "bench_scope_shared_probe.py"
    spec = importlib.util.spec_from_file_location("bench_scope_shared_probe_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_profile_masks_accept_dynamic_scope_count(probe_module):
    profile = {
        "scopes": {
            name: {str(layer): list(range(offset, offset + 60)) for layer in range(3, 43)}
            for name, offset in (("alpha", 0), ("beta", 60), ("gamma", 120))
        }
    }
    ids, masks = probe_module._profile_masks(profile)
    assert ids == ["alpha", "beta", "gamma"]
    assert len(masks) == 3
    assert len(masks[0]) == 40
    assert sum(masks[1][0]) == 60
    assert masks[2][39][120] == 1


def test_parse_probe_depths(probe_module):
    assert probe_module._parse_probe_depths("43,10,6,10") == [6, 10, 43]
    with pytest.raises(ValueError):
        probe_module._parse_probe_depths("3,10")
    with pytest.raises(ValueError):
        probe_module._parse_probe_depths("44")


def test_scope_score_collector_finds_top6_and_head2_scope(probe_module):
    mx = pytest.importorskip("mlx.core")
    masks = mx.zeros((2, 40, 256), dtype=mx.float32)
    # Scope zero covers experts 0..59; scope one covers 60..119.
    masks = mx.concatenate(
        (
            mx.concatenate(
                (mx.ones((1, 40, 60)), mx.zeros((1, 40, 196))), axis=-1
            ),
            mx.concatenate(
                (
                    mx.zeros((1, 40, 60)),
                    mx.ones((1, 40, 60)),
                    mx.zeros((1, 40, 136)),
                ),
                axis=-1,
            ),
        ),
        axis=0,
    )
    collector = probe_module.ScopeScoreCollector(masks)
    for layer in range(3, 43):
        inds = mx.array([[[61, 62, 1, 2, 3, 4]]], dtype=mx.int32)
        weights = mx.array(
            [[[0.21, 0.20, 0.18, 0.16, 0.14, 0.11]]], dtype=mx.float32
        )
        collector.capture(layer, inds, weights)
    scores = collector.finish()
    assert scores["top6"][0] > scores["top6"][1]
    assert scores["head2"][1] == pytest.approx(1.0)
    assert scores["head2"][0] == pytest.approx(0.0)


def test_shared_only_wrapper_skips_routed_switch(probe_module):
    calls = []

    class Inner:
        sharding_group = None

        @staticmethod
        def shared_experts(x):
            calls.append("shared")
            return x + 1

        @staticmethod
        def gate(x, input_ids):
            calls.append("gate")
            return "ids", "weights"

        @staticmethod
        def switch_mlp(*args, **kwargs):
            raise AssertionError("routed experts must not execute")

    class Collector:
        @staticmethod
        def capture(layer, inds, weights):
            calls.append((layer, inds, weights))

    wrapper = probe_module._SharedOnlyFFN(Inner(), 7, Collector())
    assert wrapper(3, None) == 4
    assert calls == ["shared", "gate", (7, "ids", "weights")]
