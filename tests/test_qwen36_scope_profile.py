from omlx.patches.qwen3_6_flesh.scope_profile import Qwen36ScopeCollector


def test_qwen36_scope_profile_keeps_full_phase_rankings():
    collector = Qwen36ScopeCollector(num_layers=2, num_experts=4)
    for layer in range(2):
        collector.add_rows("coding", layer, "prefill", [2, 2, 1], [0.6, 0.5, 0.1])
        collector.add_rows("coding", layer, "decode", [3, 3, 0], [0.7, 0.6, 0.2])
    collector.finish("coding", samples=2, prompt_tokens=10, decode_tokens=4)

    profile = collector.build(metadata={"source": "unit"})

    assert profile["format"] == "ai2apps-qwen36-scope-policy"
    assert profile["phases"]["prefill"]["coding"]["0"] == [2, 1, 0, 3]
    assert profile["phases"]["decode"]["coding"]["1"] == [3, 0, 1, 2]
    stats = profile["stats"]["coding"]
    assert stats["samples"] == 2
    assert stats["phases"]["decode"]["0"]["counts_by_expert"] == [1, 0, 0, 2]
