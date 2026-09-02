from __future__ import annotations

import pytest

from omlx.cache.direct_l1 import direct_l1_mode, use_direct_l1
from omlx.patches.deepseek_v4 import scope_cache


@pytest.mark.parametrize("value", ["0", "off", "false"])
def test_direct_l1_off_forces_legacy(monkeypatch, value):
    monkeypatch.setenv("OMLX_MOE_DIRECT_L1", value)
    assert direct_l1_mode() == "off"
    assert not use_direct_l1(native_available=True)


def test_direct_l1_on_requires_native(monkeypatch):
    monkeypatch.setenv("OMLX_MOE_DIRECT_L1", "1")
    assert direct_l1_mode() == "on"
    with pytest.raises(RuntimeError, match="requires the native"):
        use_direct_l1(native_available=False)


def test_full_hot_bank_patches_only_missing_slot(monkeypatch, tmp_path):
    monkeypatch.setenv("OMLX_MOE_DIRECT_L1", "1")
    monkeypatch.setattr(
        scope_cache.glm_fast,
        "native_symbols",
        lambda: ("preadv_fused_experts",),
    )
    loader = scope_cache.ScopeFallbackLoader(tmp_path)

    class Store:
        record_bytes = 4096

    class Switch:
        pass

    hot_switch = Switch()
    hot_switch._omlx_direct_hot_capacity = 8
    resident = Switch()
    loader._hot[3] = scope_cache._HotBank(
        ids=(10, 11, 12, 13, 14, 15, 16, 17),
        recency=[10, 11, 12, 13, 14, 15, 16, 17],
        switch=hot_switch,
    )
    calls = []
    monkeypatch.setattr(loader, "_store", lambda _layer: Store())
    monkeypatch.setattr(
        loader,
        "_direct_load_slots",
        lambda store, switch, slots, ids: calls.append((slots, ids)) or True,
    )
    try:
        switch, ids = loader.resolve_hot_switch(3, [17, 42], resident)
    finally:
        if loader._io_pool is not None:
            loader._io_pool.shutdown(wait=True)
        loader._prefetch_pool.shutdown(wait=True)

    assert switch is hot_switch
    assert calls == [([0], [42])]
    assert ids == (42, 11, 12, 13, 14, 15, 16, 17)
    assert loader._hot[3].recency == [11, 12, 13, 14, 15, 16, 17, 42]
    assert loader.decode_experts_loaded == 1
    assert loader.bytes_loaded == 4096


def test_full_hot_bank_preserves_interleaved_legacy_recency(monkeypatch, tmp_path):
    monkeypatch.setenv("OMLX_MOE_DIRECT_L1", "1")
    monkeypatch.setattr(
        scope_cache.glm_fast,
        "native_symbols",
        lambda: ("preadv_fused_experts",),
    )
    loader = scope_cache.ScopeFallbackLoader(tmp_path)

    class Store:
        record_bytes = 4096

    class Switch:
        pass

    hot_switch = Switch()
    hot_switch._omlx_direct_hot_capacity = 8
    loader._hot[3] = scope_cache._HotBank(
        ids=(10, 11, 12, 13, 14, 15, 16, 17),
        recency=[10, 11, 12, 13, 14, 15, 16, 17],
        switch=hot_switch,
    )
    monkeypatch.setattr(loader, "_store", lambda _layer: Store())
    monkeypatch.setattr(loader, "_direct_load_slots", lambda *args: True)
    try:
        loader.resolve_hot_switch(3, [42, 17], Switch())
    finally:
        if loader._io_pool is not None:
            loader._io_pool.shutdown(wait=True)
        loader._prefetch_pool.shutdown(wait=True)

    assert loader._hot[3].recency == [11, 12, 13, 14, 15, 16, 42, 17]


def test_partial_hot_bank_fills_empty_slot_without_rebuild(monkeypatch, tmp_path):
    monkeypatch.setenv("OMLX_MOE_DIRECT_L1", "1")
    monkeypatch.setattr(
        scope_cache.glm_fast,
        "native_symbols",
        lambda: ("preadv_fused_experts",),
    )
    loader = scope_cache.ScopeFallbackLoader(tmp_path)

    class Store:
        record_bytes = 4096

    class Switch:
        pass

    hot_switch = Switch()
    hot_switch._omlx_direct_hot_capacity = 8
    loader._hot[3] = scope_cache._HotBank(
        ids=(10, 11), recency=[10, 11], switch=hot_switch
    )
    calls = []
    monkeypatch.setattr(loader, "_store", lambda _layer: Store())
    monkeypatch.setattr(
        loader,
        "_direct_load_slots",
        lambda store, switch, slots, ids: calls.append((slots, ids)) or True,
    )
    try:
        switch, ids = loader.resolve_hot_switch(3, [11, 42], Switch())
    finally:
        if loader._io_pool is not None:
            loader._io_pool.shutdown(wait=True)
        loader._prefetch_pool.shutdown(wait=True)

    assert switch is hot_switch
    assert calls == [([2], [42])]
    assert ids == (10, 11, 42)
    assert loader._hot[3].recency == [10, 11, 42]


def test_direct_prefill_bypasses_staging_and_stack(monkeypatch, tmp_path):
    monkeypatch.setenv("OMLX_MOE_DIRECT_L1", "1")
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_DIRECT_PREFILL", "1")
    monkeypatch.setattr(
        scope_cache.glm_fast,
        "native_symbols",
        lambda: ("preadv_fused_experts",),
    )
    loader = scope_cache.ScopeFallbackLoader(tmp_path)

    class Tensor:
        def __init__(self, name):
            self.name = name

    class Store:
        record_bytes = 4096
        tensors = [
            Tensor(name)
            for name in (
                "gate_proj.weight",
                "gate_proj.scales",
                "down_proj.weight",
                "down_proj.scales",
                "up_proj.weight",
                "up_proj.scales",
            )
        ]

    class Switch:
        pass

    fallback = Switch()
    calls = []
    monkeypatch.setattr(loader, "_store", lambda _layer: Store())
    monkeypatch.setattr(
        loader, "_make_empty_direct_switch", lambda resident, ids: fallback
    )
    monkeypatch.setattr(
        loader,
        "_direct_load_slots",
        lambda store, switch, slots, ids: calls.append((slots, ids)) or True,
    )
    monkeypatch.setattr(
        loader,
        "_read_records",
        lambda *args: pytest.fail("direct Prefill used staging"),
    )
    try:
        switch, ids = loader.build_transient_switch(3, [7, 9], Switch())
    finally:
        if loader._io_pool is not None:
            loader._io_pool.shutdown(wait=True)
        loader._prefetch_pool.shutdown(wait=True)

    assert switch is fallback
    assert ids == (7, 9)
    assert calls == [([0, 1], [7, 9])]
    assert loader.transient_experts_loaded == 2
