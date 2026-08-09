from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "bench_scope_review.py"
SPEC = importlib.util.spec_from_file_location("bench_scope_review", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_accumulate_counts_all_selected_experts_by_layer():
    counters = {3: Counter(), 4: Counter()}
    MODULE._accumulate([[1, 2, 2], [3, 4, 3]], [3, 4], counters)
    assert counters[3] == Counter({2: 2, 1: 1})
    assert counters[4] == Counter({3: 2, 4: 1})


def test_balanced_modes_have_equal_positions():
    assert MODULE.BALANCED_MODES.count("off") == 3
    assert MODULE.BALANCED_MODES.count("on") == 3
