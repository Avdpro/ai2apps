import importlib.util
from pathlib import Path

import pytest


def _load_module():
    path = Path(__file__).parents[1] / "scripts" / "bench_router_parity.py"
    spec = importlib.util.spec_from_file_location("bench_router_parity_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _collector(module, rows):
    collector = module._Collector()
    collector.top6[3] = [list(row) for row in rows]
    collector.top10[3] = [list(row) + [6, 7, 8, 9] for row in rows]
    collector.weights[3] = [[0.6, 0.5, 0.4, 0.3, 0.2, 0.1] for _ in rows]
    collector.score_layers.add(3)
    return collector


def test_identical_router_traces_have_zero_scope_coverage_loss():
    module = _load_module()
    rows = [[0, 1, 2, 3, 4, 5] for _ in range(64)]

    result = module.compare_router_traces(
        _collector(module, rows),
        _collector(module, rows),
    )

    assert result["top6_set_rate"] == 1.0
    assert result["top10_set_rate"] == 1.0
    assert result["scope_frequency_mean_cosine"] == pytest.approx(1.0)
    assert result["scope_top60_mean_overlap"] == 60
    assert result["prefill_top60_decode_mean_coverage_loss"] == 0.0


def test_boundary_expert_change_reduces_top6_overlap():
    module = _load_module()
    prefill_rows = [[0, 1, 2, 3, 4, 5]]
    decode_rows = [[0, 1, 2, 3, 4, 10]]

    result = module.compare_router_traces(
        _collector(module, prefill_rows),
        _collector(module, decode_rows),
    )

    assert result["top6_set_rate"] == 0.0
    assert result["top6_mean_overlap"] == 5.0
    assert result["mismatch_examples"][0]["overlap"] == 5
