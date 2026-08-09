from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_regularized_scope_profile.py"
SPEC = importlib.util.spec_from_file_location("regularized_scope", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_regularized_bank_retains_base_prefix_and_fills_leaf():
    base = list(range(60))
    leaf = list(range(100, 160))
    bank = MODULE.regularized_bank(base, leaf, 40)
    assert bank[:40] == list(range(40))
    assert bank[40:] == list(range(100, 120))
    assert len(bank) == 60
    assert len(set(bank)) == 60


def test_regularized_bank_rejects_invalid_keep():
    try:
        MODULE.regularized_bank(list(range(60)), list(range(60)), 61)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid keep should fail")
