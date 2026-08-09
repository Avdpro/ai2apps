from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "simulate_dynamic_l1.py"
SPEC = importlib.util.spec_from_file_location("simulate_dynamic_l1", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_frequency_swap_promotes_repeated_l2_expert():
    banks = {layer: list(range(60)) for layer in range(3, 43)}
    token = [[100, 0, 1, 2, 3, 4] for _ in range(40)]
    routes = [token for _ in range(32)]
    static = MODULE.replay(
        routes, banks, l2_slots=8, interval=16, dynamic=False
    )
    dynamic = MODULE.replay(
        routes,
        banks,
        l2_slots=8,
        interval=16,
        dynamic=True,
        min_candidate=3,
        margin=2,
        ratio=1.5,
        pinned=4,
        cooldown=16,
    )
    assert dynamic["swaps"] == 40
    assert dynamic["l1_route_hit_rate"] > static["l1_route_hit_rate"]
    assert dynamic["ssd_loads"] == static["ssd_loads"]


def test_lru_reloads_when_working_set_exceeds_l2():
    banks = {layer: list(range(60)) for layer in range(3, 43)}
    routes = [
        [[100 + token % 3, 0, 1, 2, 3, 4] for _ in range(40)]
        for token in range(9)
    ]
    result = MODULE.replay(routes, banks, l2_slots=2, interval=16, dynamic=False)
    assert result["reloads"] > 0
