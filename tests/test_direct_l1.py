from __future__ import annotations

from concurrent.futures import Future

import mlx.core as mx
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
    monkeypatch.setattr(
        loader,
        "_read_transient_records_detached",
        lambda *args: pytest.fail("direct Prefill used detached prefetch"),
    )
    try:
        prepared = loader.prefetch_transient_records(3, [7, 9])
        assert isinstance(prepared.result(), scope_cache._PreparedDirectRequest)
        switch, ids = loader.build_transient_switch(
            3, [7, 9], Switch(), prepared=prepared
        )
    finally:
        if loader._io_pool is not None:
            loader._io_pool.shutdown(wait=True)
        loader._prefetch_pool.shutdown(wait=True)

    assert switch is fallback
    assert ids == (7, 9)
    assert calls == [([0, 1], [7, 9])]
    assert loader.transient_experts_loaded == 2


def test_direct_prefill_uses_async_legacy_for_bias_store(monkeypatch, tmp_path):
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

    names = tuple(
        f"{projection}.{tensor}"
        for projection in ("gate_proj", "down_proj", "up_proj")
        for tensor in ("weight", "scales", "biases")
    )

    class Store:
        record_bytes = 8192
        tensors = [Tensor(name) for name in names]

        @staticmethod
        def allocate_staging():
            return bytearray(1)

        @staticmethod
        def read_into(expert_id, staging):
            staging[0] = expert_id
            return staging

        @staticmethod
        def mlx_tensor_views(record, *, copy_record):
            assert copy_record
            return {
                name: mx.array([record[0] * 10 + offset], dtype=mx.int32)
                for offset, name in enumerate(names)
            }

    class Switch:
        pass

    store = Store()
    built = []
    monkeypatch.setattr(loader, "_store", lambda _layer: store)
    monkeypatch.setattr(
        loader,
        "_direct_load_slots",
        lambda *args: pytest.fail("bias store used direct Prefill"),
    )
    monkeypatch.setattr(
        loader,
        "_make_switch",
        lambda resident, ids, tensors: built.append(
            {name: value.tolist() for name, value in tensors.items()}
        )
        or Switch(),
    )
    try:
        prepared = loader.prefetch_transient_records(3, [7, 9])
        assert isinstance(prepared.result(), scope_cache._PreparedTransientRecords)
        loader.build_transient_switch(3, [7, 9], Switch(), prepared=prepared)

        loader.direct_prefill = False
        loader.build_transient_switch(3, [7, 9], Switch())
    finally:
        if loader._io_pool is not None:
            loader._io_pool.shutdown(wait=True)
        loader._prefetch_pool.shutdown(wait=True)

    assert built[0] == built[1]
    assert {name for name in built[0] if name.endswith(".biases")} == {
        "gate_proj.biases",
        "down_proj.biases",
        "up_proj.biases",
    }
    assert loader.prefetch_hits == 1


def test_stale_direct_prefill_marker_falls_back_for_bias_store(
    monkeypatch, tmp_path
):
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

    names = tuple(
        f"{projection}.{tensor}"
        for projection in ("gate_proj", "down_proj", "up_proj")
        for tensor in ("weight", "scales", "biases")
    )

    class Store:
        record_bytes = 8192
        tensors = [Tensor(name) for name in names]

    class Switch:
        pass

    reads = []
    records = {
        expert_id: {
            name: mx.array([expert_id * 10 + offset], dtype=mx.int32)
            for offset, name in enumerate(names)
        }
        for expert_id in (7, 9)
    }
    monkeypatch.setattr(loader, "_store", lambda _layer: Store())
    monkeypatch.setattr(
        loader,
        "_read_records",
        lambda layer, ids: reads.append((layer, tuple(ids))) or (records, 8192),
    )
    monkeypatch.setattr(loader, "_make_switch", lambda *args: Switch())

    prepared = Future()
    prepared.set_result(scope_cache._PreparedDirectRequest(layer=3, ids=(7, 9)))
    mismatched = Future()
    mismatched.set_result(scope_cache._PreparedDirectRequest(layer=4, ids=(7, 9)))
    try:
        switch, ids = loader.build_transient_switch(
            3, [7, 9], Switch(), prepared=prepared
        )
        with pytest.raises(ValueError, match="does not match request"):
            loader.build_transient_switch(3, [7, 9], Switch(), prepared=mismatched)
    finally:
        if loader._io_pool is not None:
            loader._io_pool.shutdown(wait=True)
        loader._prefetch_pool.shutdown(wait=True)

    assert isinstance(switch, Switch)
    assert ids == (7, 9)
    assert reads == [(3, (7, 9))]
