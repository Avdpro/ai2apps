from types import SimpleNamespace

import pytest

from omlx.engine.ssd_telemetry import SsdPressureTelemetry


def test_ssd_pressure_tracks_decode_window_and_turn_without_model_sync() -> None:
    counters = {"loads": 100, "bytes": 1000, "routed": 400}
    calls = 0

    def sample():
        nonlocal calls
        calls += 1
        return counters["loads"], counters["bytes"], counters["routed"]

    telemetry = SsdPressureTelemetry(sample)
    telemetry.reset("chat")
    for token in range(1, 16):
        counters["loads"] += 2
        counters["bytes"] += 100
        telemetry.record(token)

    live = telemetry.live("chat")
    assert live["ssd_recent_10_tokens"] == {
        "tokens": 10,
        "expert_loads": 20,
        "bytes_loaded": 1000,
        "pressure": 0.25,
        "pressure_percent": 25.0,
        "severity": "critical",
    }
    assert live["ssd_turn_average"]["tokens"] == 15
    assert live["ssd_turn_average"]["expert_loads"] == 30
    assert live["ssd_turn_average"]["bytes_loaded"] == 1500
    assert live["ssd_turn_average"]["pressure_percent"] == pytest.approx(25.0)
    assert calls == 16
    assert telemetry.stats()["ssd_turn_by_session"]["chat"] == live[
        "ssd_turn_average"
    ]


def test_scheduler_first_token_resets_prefill_reads() -> None:
    counters = {"loads": 0, "bytes": 0}
    telemetry = SsdPressureTelemetry(
        lambda: (counters["loads"], counters["bytes"], 100)
    )
    telemetry.reset("chat")
    counters.update(loads=50, bytes=5000)
    telemetry.record_scheduler_output(
        SimpleNamespace(outputs=[SimpleNamespace(completion_tokens=1)])
    )
    counters.update(loads=52, bytes=5025)
    telemetry.record_scheduler_output(
        SimpleNamespace(outputs=[SimpleNamespace(completion_tokens=2)])
    )

    live = telemetry.live("chat")
    assert live["ssd_recent_10_tokens"]["tokens"] == 1
    assert live["ssd_recent_10_tokens"]["expert_loads"] == 2
    assert live["ssd_recent_10_tokens"]["bytes_loaded"] == 25
    assert live["ssd_recent_10_tokens"]["pressure_percent"] == 25.0


def test_sessions_keep_independent_completed_turns() -> None:
    counters = {"loads": 0, "bytes": 0}
    telemetry = SsdPressureTelemetry(
        lambda: (counters["loads"], counters["bytes"], 100)
    )
    telemetry.reset("first")
    counters.update(loads=2, bytes=20)
    telemetry.record(1)
    telemetry.reset("second")
    counters.update(loads=5, bytes=50)
    telemetry.record(2)

    stats = telemetry.stats()
    assert stats["ssd_turn_by_session"]["first"]["bytes_loaded"] == 20
    assert stats["ssd_turn_by_session"]["second"]["bytes_loaded"] == 30
