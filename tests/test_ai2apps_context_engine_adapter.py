"""Host-boundary contracts after independent context-engine acceptance."""

import json

from ai2apps.agents.context_engine_adapter import compactable_end, validates_replacement


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def groups():
    return [
        {"origin": "run", "messages": [{"role": "tool", "content": "x" * 2100}]}
        for _ in range(6)
    ]


def test_pressure_selection_preserves_recent_complete_rounds():
    end = compactable_end(
        groups(), 0, request_bytes=15000, max_bytes=12000, run_id="run", encode=encode
    )
    assert 0 < end <= 4
    assert (
        compactable_end(
            groups()[:2],
            0,
            request_bytes=5000,
            max_bytes=12000,
            run_id="run",
            encode=encode,
        )
        == 0
    )


def test_replay_replacement_rejects_growth_and_recent_tail():
    assert validates_replacement(
        groups(),
        4,
        {"role": "assistant", "content": "memory"},
        run_id="run",
        encode=encode,
    )
    assert not validates_replacement(
        groups(),
        5,
        {"role": "assistant", "content": "memory"},
        run_id="run",
        encode=encode,
    )
    assert not validates_replacement(
        groups(),
        4,
        {"role": "assistant", "content": "x" * 20000},
        run_id="run",
        encode=encode,
    )
