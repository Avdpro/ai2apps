from omlx.patches.glm5_next_cache.scope_profile import Glm5ScopeCollector


def test_scope_profile_blends_prefill_and_decode_and_keeps_raw_counts():
    collector = Glm5ScopeCollector(num_experts=6, capacity=2)
    collector.add_rows("coding", 3, "prefill", [0, 0, 1], [0.5, 0.4, 0.1])
    collector.add_rows("coding", 3, "decode", [2, 2, 3], [0.6, 0.3, 0.1])
    collector.finish_sample("coding", 42, source_samples=3)

    profile = collector.build(metadata={})

    scope = profile["scopes"]["coding"]
    assert scope["layers"]["3"] == [2, 0]
    assert scope["samples"] == 3
    assert scope["packs"] == 1
    assert scope["prompt_tokens"] == 42
    stats = scope["layer_stats"]["3"]["phases"]
    assert stats["prefill"]["counts_by_expert"] == [2, 1, 0, 0, 0, 0]
    assert stats["decode"]["counts_by_expert"] == [0, 0, 2, 1, 0, 0]
    assert scope["phase_layers"]["prefill"] == {"3": [0, 1]}
    assert scope["phase_layers"]["decode"] == {"3": [2, 3]}


def test_scope_profile_renormalizes_when_only_prefill_is_observed():
    collector = Glm5ScopeCollector(num_experts=4, capacity=2)
    collector.add_rows("general", 3, "prefill", [1, 1, 2], [0.6, 0.3, 0.1])

    profile = collector.build(metadata={})

    assert profile["scopes"]["general"]["layers"]["3"] == [1, 2]
    decode = profile["scopes"]["general"]["layer_stats"]["3"]["phases"]["decode"]
    assert decode["routes"] == 0
    assert decode["selected_route_coverage"] is None


def test_scope_profile_keeps_decode_sequences_and_sparse_transitions():
    collector = Glm5ScopeCollector(num_experts=6, capacity=2)
    collector.add_rows("coding", 3, "decode", [0, 1], [0.7, 0.3])
    collector.add_decode_step("coding", 3, [0, 1])
    collector.add_rows("coding", 3, "decode", [1, 2], [0.6, 0.4])
    collector.add_decode_step("coding", 3, [1, 2])
    collector.add_rows("coding", 3, "decode", [2, 3], [0.8, 0.2])
    collector.add_decode_step("coding", 3, [2, 3])
    collector.finish_sample("coding", 12)

    profile = collector.build(metadata={})

    assert profile["version"] == 2
    scope = profile["scopes"]["coding"]
    assert scope["decode_sequences"][0]["layers"]["3"] == [
        [0, 1],
        [1, 2],
        [2, 3],
    ]
    transitions = scope["decode_transitions"]["3"]
    assert transitions["steps"] == 2
    assert transitions["pair_count"] == 8
    assert transitions["sources"]["0"] == {
        "observations": 1,
        "targets": [[1, 1], [2, 1]],
    }
    assert transitions["sources"]["1"] == {
        "observations": 2,
        "targets": [[2, 2], [1, 1], [3, 1]],
    }


def test_scope_profile_resets_transition_chain_between_packs():
    collector = Glm5ScopeCollector(num_experts=4, capacity=2)
    collector.add_rows("general", 3, "decode", [0, 1], [0.5, 0.5])
    collector.add_decode_step("general", 3, [0, 1])
    collector.finish_sample("general", 5)
    collector.add_rows("general", 3, "decode", [2, 3], [0.5, 0.5])
    collector.add_decode_step("general", 3, [2, 3])
    collector.finish_sample("general", 6)

    profile = collector.build(metadata={})

    assert profile["scopes"]["general"]["decode_transitions"] == {}
    assert len(profile["scopes"]["general"]["decode_sequences"]) == 2
