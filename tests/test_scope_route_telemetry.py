from __future__ import annotations

import mlx.core as mx

from omlx.patches.deepseek_v4.scope_cache import ScopeFallbackLoader


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
