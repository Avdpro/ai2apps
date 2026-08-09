from __future__ import annotations

import json
from types import SimpleNamespace

from omlx.engine.flesh import DeepseekV4FleshEngine
from omlx.patches.deepseek_v4.scope_runtime import DeepseekV4ScopeBank, ScopeCatalog


def _catalog(tmp_path):
    layers = {
        str(layer): list(range(offset, offset + 60))
        for layer in range(3, 43)
        for offset in (0,)
    }
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "format": "dmoe-deepseek-tiered-policy",
                "scopes": {
                    "alpha": layers,
                    "beta": {
                        str(layer): list(range(60, 120))
                        for layer in range(3, 43)
                    },
                },
            }
        )
    )
    return ScopeCatalog.load(profile)


def test_scope_catalog_is_dynamic_and_validated(tmp_path):
    catalog = _catalog(tmp_path)
    assert catalog.scope_ids == ("alpha", "beta")
    assert catalog.experts("beta", 17) == tuple(range(60, 120))
    assert len(catalog.masks()) == 2
    assert sum(catalog.masks()[1][0]) == 60


def test_scope_catalog_truncates_to_resident_capacity(tmp_path):
    full = _catalog(tmp_path)
    catalog = ScopeCatalog.load(full.profile_path, resident_experts=20)

    assert catalog.experts("alpha", 3) == tuple(range(20))
    assert catalog.experts("beta", 17) == tuple(range(60, 80))
    # Scope classification remains based on the full Top60 definition even
    # when only its leading Top20 are physically resident.
    assert sum(catalog.masks()[1][0]) == 60


def test_scope_bank_replaces_every_score_layer(tmp_path):
    catalog = _catalog(tmp_path)

    class Loader:
        def __init__(self):
            self.layers = []
            self.clears = 0

        def clear_hot(self):
            self.clears += 1

        def build_transient_switch(self, layer, expert_ids, resident):
            self.layers.append(layer)
            return f"beta-{layer}", tuple(expert_ids)

    layers = []
    for _ in range(43):
        ffn = SimpleNamespace(
            scope_expert_ids=tuple(range(60)),
            scope_expert_to_slot_values=None,
            switch_mlp="alpha",
            config=SimpleNamespace(n_routed_experts=256),
        )
        layers.append(SimpleNamespace(ffn=ffn))
    model = SimpleNamespace(model=SimpleNamespace(layers=layers))
    loader = Loader()
    bank = DeepseekV4ScopeBank(model, catalog, loader, "alpha")

    assert bank.activate("beta") is True
    assert bank.activate("beta") is False
    assert loader.layers == list(range(3, 43))
    assert loader.clears == 2
    assert layers[3].ffn.switch_mlp == "beta-3"
    assert layers[42].ffn.scope_expert_ids == tuple(range(60, 120))
    assert layers[20].ffn.scope_expert_to_slot_values[119] == 59
    assert bank.current_scope == "beta"


def test_scope_bank_adaptive_layout_rebuilds_only_changed_layers(
    tmp_path, monkeypatch
):
    catalog = _catalog(tmp_path)
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_L1_UPDATE_BACKEND", "atomic")

    class Loader:
        def __init__(self):
            self.layers = []
            self.clears = 0

        def clear_hot(self):
            self.clears += 1

        def rebuild_resident_switch(self, layer, expert_ids, resident):
            self.layers.append(layer)
            return f"adaptive-{layer}", tuple(expert_ids)

    layers = []
    for _ in range(43):
        ffn = SimpleNamespace(
            scope_expert_ids=tuple(range(60)),
            scope_expert_to_slot_values=None,
            switch_mlp="alpha",
            config=SimpleNamespace(n_routed_experts=256),
        )
        layers.append(SimpleNamespace(ffn=ffn))
    model = SimpleNamespace(model=SimpleNamespace(layers=layers))
    loader = Loader()
    bank = DeepseekV4ScopeBank(model, catalog, loader, "alpha")
    layout = [catalog.experts("alpha", layer) for layer in range(43)]
    changed = list(layout[7])
    changed[-1] = 91
    layout[7] = tuple(changed)

    assert bank.activate_layout("alpha", layout, adaptive=True) == 1
    assert loader.layers == [7]
    assert loader.clears == 1
    assert layers[7].ffn.scope_expert_ids[-1] == 91
    assert layers[7].ffn.scope_expert_to_slot_values[91] == 59
    assert bank.adaptive_commits == 1
    assert bank.adaptive_layers_rebuilt == 1


def test_scope_bank_streams_adaptive_layers_in_bounded_groups(
    tmp_path, monkeypatch
):
    import mlx.core as mx

    catalog = _catalog(tmp_path)
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_L1_UPDATE_BACKEND", "stream")
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_L1_STREAM_LAYERS", "2")
    monkeypatch.setattr(mx, "synchronize", lambda: None)
    monkeypatch.setattr(mx, "clear_cache", lambda: None)

    class Loader:
        def __init__(self):
            self.layers = []
            self.clears = 0

        def clear_hot(self):
            self.clears += 1

        def rebuild_resident_switch(self, layer, expert_ids, resident):
            self.layers.append(layer)
            return f"stream-{layer}", tuple(expert_ids)

    layers = []
    for _ in range(43):
        ffn = SimpleNamespace(
            scope_expert_ids=tuple(range(60)),
            scope_expert_to_slot_values=None,
            switch_mlp="alpha",
            config=SimpleNamespace(n_routed_experts=256),
        )
        layers.append(SimpleNamespace(ffn=ffn))
    model = SimpleNamespace(model=SimpleNamespace(layers=layers))
    loader = Loader()
    bank = DeepseekV4ScopeBank(model, catalog, loader, "alpha")
    layout = [catalog.experts("alpha", layer) for layer in range(43)]
    for layer in (7, 8, 9):
        changed = list(layout[layer])
        changed[-1] = 90 + layer
        layout[layer] = tuple(changed)

    assert bank.activate_layout("alpha", layout, adaptive=True) == 3
    assert loader.layers == [7, 8, 9]
    assert [layers[layer].ffn.switch_mlp for layer in (7, 8, 9)] == [
        "stream-7",
        "stream-8",
        "stream-9",
    ]
    assert bank.stats()["adaptive_backend"] == "stream"


def test_scope_bank_patches_only_changed_adaptive_slots(tmp_path, monkeypatch):
    import mlx.core as mx

    catalog = _catalog(tmp_path)
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_L1_UPDATE_BACKEND", "patch")
    monkeypatch.setattr(mx, "synchronize", lambda: None)
    monkeypatch.setattr(mx, "clear_cache", lambda: None)

    class Loader:
        def __init__(self):
            self.patches = []

        def clear_hot(self):
            pass

        def patch_resident_switch(self, layer, slots, expert_ids, resident):
            self.patches.append((layer, list(slots), list(expert_ids), resident))
            return resident, tuple(expert_ids)

    layers = []
    for _ in range(43):
        ffn = SimpleNamespace(
            scope_expert_ids=tuple(range(60)),
            scope_expert_to_slot_values=None,
            switch_mlp="alpha",
            config=SimpleNamespace(n_routed_experts=256),
        )
        layers.append(SimpleNamespace(ffn=ffn))
    model = SimpleNamespace(model=SimpleNamespace(layers=layers))
    loader = Loader()
    bank = DeepseekV4ScopeBank(model, catalog, loader, "alpha")
    layout = [catalog.experts("alpha", layer) for layer in range(43)]
    changed = list(layout[7])
    changed[3] = 91
    changed[59] = 92
    layout[7] = tuple(changed)

    assert bank.activate_layout("alpha", layout, adaptive=True) == 1
    assert loader.patches == [(7, [3, 59], [91, 92], "alpha")]
    assert layers[7].ffn.switch_mlp == "alpha"
    assert layers[7].ffn.scope_expert_to_slot_values[91] == 3
    assert layers[7].ffn.scope_expert_to_slot_values[92] == 59


def test_scope_bank_stream_rolls_back_published_layers(tmp_path, monkeypatch):
    import mlx.core as mx
    import pytest

    catalog = _catalog(tmp_path)
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_L1_UPDATE_BACKEND", "stream")
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_L1_STREAM_LAYERS", "1")
    monkeypatch.setattr(mx, "synchronize", lambda: None)
    monkeypatch.setattr(mx, "clear_cache", lambda: None)

    class Loader:
        def __init__(self):
            self.failed = False

        def clear_hot(self):
            pass

        def rebuild_resident_switch(self, layer, expert_ids, resident):
            if layer == 8 and not self.failed:
                self.failed = True
                raise OSError("injected SSD failure")
            return f"bank-{layer}-{expert_ids[-1]}", tuple(expert_ids)

    layers = []
    for _ in range(43):
        ffn = SimpleNamespace(
            scope_expert_ids=tuple(range(60)),
            scope_expert_to_slot_values=None,
            switch_mlp="alpha",
            config=SimpleNamespace(n_routed_experts=256),
        )
        layers.append(SimpleNamespace(ffn=ffn))
    bank = DeepseekV4ScopeBank(
        SimpleNamespace(model=SimpleNamespace(layers=layers)),
        catalog,
        Loader(),
        "alpha",
    )
    layout = [catalog.experts("alpha", layer) for layer in range(43)]
    for layer in (7, 8):
        changed = list(layout[layer])
        changed[-1] = 90 + layer
        layout[layer] = tuple(changed)

    with pytest.raises(OSError, match="injected SSD failure"):
        bank.activate_layout("alpha", layout, adaptive=True)
    assert layers[7].ffn.scope_expert_ids == tuple(range(60))
    assert layers[7].ffn.scope_expert_to_slot_values[59] == 59
    assert bank.current_scope == "alpha"


def test_scope_bank_patch_rolls_back_changed_slots(tmp_path, monkeypatch):
    import mlx.core as mx
    import pytest

    catalog = _catalog(tmp_path)
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_L1_UPDATE_BACKEND", "patch")
    monkeypatch.setattr(mx, "synchronize", lambda: None)
    monkeypatch.setattr(mx, "clear_cache", lambda: None)

    class Loader:
        def __init__(self):
            self.failed = False

        def clear_hot(self):
            pass

        def patch_resident_switch(self, layer, slots, expert_ids, resident):
            if layer == 8 and not self.failed:
                self.failed = True
                raise OSError("injected patch failure")
            return resident, tuple(expert_ids)

    layers = []
    for _ in range(43):
        ffn = SimpleNamespace(
            scope_expert_ids=tuple(range(60)),
            scope_expert_to_slot_values=None,
            switch_mlp="alpha",
            config=SimpleNamespace(n_routed_experts=256),
        )
        layers.append(SimpleNamespace(ffn=ffn))
    bank = DeepseekV4ScopeBank(
        SimpleNamespace(model=SimpleNamespace(layers=layers)),
        catalog,
        Loader(),
        "alpha",
    )
    layout = [catalog.experts("alpha", layer) for layer in range(43)]
    for layer in (7, 8):
        changed = list(layout[layer])
        changed[-1] = 90 + layer
        layout[layer] = tuple(changed)

    with pytest.raises(OSError, match="injected patch failure"):
        bank.activate_layout("alpha", layout, adaptive=True)
    for layer in (7, 8):
        assert layers[layer].ffn.scope_expert_ids == tuple(range(60))
        assert layers[layer].ffn.scope_expert_to_slot_values[59] == 59
    assert bank.current_scope == "alpha"


def test_flesh_cache_namespace_is_scope_and_policy_specific(monkeypatch):
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_SCOPE_LOSSY_MODE", "head2")
    assert DeepseekV4FleshEngine._cache_namespace("coding") == (
        "deepseek-v4-flesh-v1",
        "coding",
        "head2",
    )
