from omlx.patches.deepseek_v4.scope_runtime import DeepseekV4ScopeSelector
from omlx.patches.qwen3_6_flesh.scope_runtime import Qwen36ScopeSelector


def _selector(selector_type, max_tokens=1024):
    selector = object.__new__(selector_type)
    selector.max_tokens = max_tokens
    return selector


def test_deepseek_scope_probe_reads_up_to_1024_tokens():
    selector = _selector(DeepseekV4ScopeSelector)
    tokens = list(range(1024))

    assert selector._truncate(tokens) == tokens


def test_qwen_scope_probe_reads_up_to_1024_tokens():
    selector = _selector(Qwen36ScopeSelector)
    tokens = list(range(1024))

    assert selector._truncate(tokens) == tokens


def test_deepseek_long_scope_probe_keeps_initial_and_recent_context():
    selector = _selector(DeepseekV4ScopeSelector)
    tokens = list(range(1400))

    sampled = selector._truncate(tokens)

    assert sampled == tokens[:128] + tokens[-896:]


def test_qwen_long_scope_probe_keeps_initial_and_recent_context():
    selector = _selector(Qwen36ScopeSelector)
    tokens = list(range(1400))

    sampled = selector._truncate(tokens)

    assert sampled == tokens[:128] + tokens[-896:]


def test_smaller_probe_limits_scale_the_preserved_prefix():
    selector = _selector(Qwen36ScopeSelector, max_tokens=256)
    tokens = list(range(400))

    assert selector._truncate(tokens) == tokens[:32] + tokens[-224:]
