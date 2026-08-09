from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "profile_scope_prefill.py"
SPEC = importlib.util.spec_from_file_location("profile_scope_prefill", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_rank_layer_is_deterministic_and_frequency_led():
    ranking, scores = MODULE._rank_layer(
        Counter({7: 100, 3: 50}),
        Counter({7: 110, 3: 100}),
        Counter({7: 40.0, 3: 30.0}),
    )
    assert ranking[:3] == [7, 3, 0]
    assert scores[7] > scores[3] > scores[0]


def test_sample_windows_cover_corpus_endpoints():
    windows = MODULE._sample_windows(list(range(100)), 10, 3)
    assert [start for start, _ in windows] == [0, 45, 90]
    assert windows[0][1] == list(range(10))
    assert windows[-1][1] == list(range(90, 100))


def test_build_profile_preserves_full_route_aggregates():
    collector = MODULE._AggregateCollector()
    for layer in range(3, 43):
        collector.score_layers.add(layer)
        collector.token_rows[layer] = 2
        collector.top6_counts[layer].update({7: 2, 3: 1})
        collector.top10_counts[layer].update({7: 2, 3: 2})
        collector.weight_sums[layer].update({7: 1.25, 3: 0.5})
    profile = MODULE._build_profile(collector, scope="code.python", metadata={})
    stats = profile["metadata"]["layer_stats"]["3"]
    assert profile["scopes"]["code.python"]["3"][:2] == [7, 3]
    assert len(stats["top6_counts_by_expert"]) == 256
    assert stats["top6_counts_by_expert"][7] == 2
    assert stats["route_weight_by_expert"][3] == 0.5


def test_collector_selects_only_last_singleton_per_layer():
    class Singleton:
        shape = (1, 1, 6)

    collector = MODULE._AggregateCollector()
    singleton = Singleton()
    collector.capture(3, singleton, singleton, singleton, True)
    collector.capture(4, singleton, singleton, singleton, True)
    collector.capture(3, singleton, singleton, singleton, True)
    collector.capture(4, singleton, singleton, singleton, True)
    assert collector._last_singletons() == {2, 3}
