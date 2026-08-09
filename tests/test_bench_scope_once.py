from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "bench_scope_once.py"


def test_benchmark_script_exposes_runtime_scope_alias():
    text = SCRIPT.read_text()
    assert '"--runtime-scope"' in text
    assert "expected_scope = args.runtime_scope or sample[\"scope\"]" in text
    assert '"dataset_scope": sample["scope"]' in text
