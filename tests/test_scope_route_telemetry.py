from __future__ import annotations

import mlx.core as mx

from omlx.patches.deepseek_v4.scope_cache import ScopeFallbackLoader


class _SizedStore:
    def __init__(self, record_bytes: int):
        self.record_bytes = record_bytes

    def allocate_staging(self):
        return bytearray(self.record_bytes)

    def read_into(self, _expert_id, staging):
        assert len(staging) == self.record_bytes
        return memoryview(staging)

    def mlx_tensor_views(self, _record, *, copy_record):
        assert copy_record
        return {}


def test_staging_pool_resizes_for_mixed_bit_width_layers(tmp_path):
    loader = ScopeFallbackLoader(tmp_path)
    loader._stores[3] = _SizedStore(8 * 1024 * 1024)
    loader._stores[4] = _SizedStore(15 * 1024 * 1024 // 2)
    try:
        loader._read_records(3, [0])
        assert len(loader._staging_buffers[0]) == 8 * 1024 * 1024
        loader._read_records(4, [0])
        assert len(loader._staging_buffers[0]) == 15 * 1024 * 1024 // 2
    finally:
        if loader._io_pool is not None:
            loader._io_pool.shutdown(wait=True)


def test_device_route_window_accumulates_and_drains_once(tmp_path):
    loader = ScopeFallbackLoader(tmp_path)
    lookup = mx.array([0] * 100 + [-1] + [0] * 155, dtype=mx.int32)
    routes = mx.array([[[1, 2, 100, 2, 3, 4]]], dtype=mx.int32)
    loader.reset_route_telemetry(enabled=True)
    loader.record_decode_routes(7, routes, lookup)
    loader.record_decode_routes(7, routes, lookup)

    window = loader.drain_route_telemetry()

    assert window["layers"] == 1
    assert window["miss_layer_steps"] == 2
    assert window["histograms"][7][2] == 4
    assert window["histograms"][7][100] == 2
    assert loader.stats()["route_telemetry_drains"] == 1
    assert loader.stats()["route_telemetry_bytes_read"] == 1028


def test_device_route_window_off_does_not_collect(tmp_path):
    loader = ScopeFallbackLoader(tmp_path)
    lookup = mx.zeros((256,), dtype=mx.int32)
    routes = mx.array([[[1, 2, 3, 4, 5, 6]]], dtype=mx.int32)
    loader.reset_route_telemetry(enabled=False)
    loader.record_decode_routes(7, routes, lookup)
    assert loader.drain_route_telemetry()["layers"] == 0
