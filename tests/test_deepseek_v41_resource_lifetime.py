from __future__ import annotations

from omlx.patches.deepseek_v41 import model as model_module
from omlx.patches.deepseek_v41.model import Model
from omlx.patches.deepseek_v41.resident_bank import MetalBank


def _empty_bank(*values):
    bank = object.__new__(MetalBank)
    bank.pending = list(values)
    bank.fence_calls = 0
    return bank


def test_bank_releases_materialized_outputs_without_adding_a_fence():
    bank = _empty_bank(*range(12_000))

    bank.release_completed_uses()

    assert bank.pending == []
    assert bank.fence_calls == 0


def test_complete_forward_materializes_persistent_state_before_releasing_banks(
    monkeypatch,
):
    evaluated = []
    monkeypatch.setattr(model_module.mx, "eval", lambda *values: evaluated.extend(values))
    first = _empty_bank("old-output-1")
    second = _empty_bank("old-output-2")
    model = object.__new__(Model)
    model.cache_counters = "cache-counters"
    model.ages = {0: "ages-0", 1: "ages-1"}
    model.banks = {0: first, 1: second}

    model.complete_forward("logits")

    assert evaluated == ["logits", "cache-counters", "ages-0", "ages-1"]
    assert first.pending == []
    assert second.pending == []


def test_complete_forward_keeps_each_token_boundary_bounded(monkeypatch):
    monkeypatch.setattr(model_module.mx, "eval", lambda *_values: None)
    model = object.__new__(Model)
    model.cache_counters = "cache-counters"
    model.ages = {}
    model.banks = {layer: _empty_bank() for layer in range(40)}

    for token in range(12_500):
        for bank in model.banks.values():
            bank.track((token, object()))
        model.complete_forward("logits")
        assert all(not bank.pending for bank in model.banks.values())
