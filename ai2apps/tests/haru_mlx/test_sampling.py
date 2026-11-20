import pytest

from ai2apps.model_worker.haru_mlx.sampling import DryConfig, DryState, StreamDetokenizer, dry_penalties, sample_token


def test_dry_penalizes_the_token_that_would_extend_a_repeat():
    config = DryConfig(multiplier=0.8, base=1.75, allowed_length=1)
    # "... 1 2 3 1 2": after the second "1 2", token 3 would repeat the earlier sequence.
    assert dry_penalties([1, 2, 3, 1, 2], config) == {3: pytest.approx(0.8 * 1.75)}
    assert dry_penalties([1, 2, 3, 4], config) == {}
    assert dry_penalties([], config) == {}


def test_dry_penalty_grows_with_the_match_and_is_capped():
    config = DryConfig(max_penalty=5.0)
    short = dry_penalties([7, 8, 9, 8], config)[9]
    longer = dry_penalties([6, 7, 8, 9, 6, 7, 8], config)[9]
    assert longer > short
    assert dry_penalties(list(range(20)) * 2, config)[0] == 5.0


def test_dry_state_skips_exempt_tokens_and_limits_history():
    config = DryConfig(lookback=4, max_match_length=2)
    state = DryState(config, exempt={0})
    for token in [1, 0, 2, 0, 3, 1, 2]:
        state.update(token)
    assert state.history == [1, 2, 3, 1, 2]
    assert set(state.penalties) == {3}
    for token in range(10, 30):
        state.update(token)
    assert len(state.history) == config.history_size


def test_dry_state_applies_penalties_in_place():
    mx = pytest.importorskip("mlx.core")
    state = DryState(DryConfig(), exempt=set())
    for token in [1, 2, 3, 1, 2]:
        state.update(token)
    logits = mx.zeros((1, 8))
    state.apply(logits)
    values = logits[0].tolist()
    assert values[3] < 0 and sum(v != 0 for v in values) == 1


def test_sample_token_greedy_top_k_and_top_p():
    mx = pytest.importorskip("mlx.core")
    logits = mx.array([[0.0, 3.0, 1.0, 2.0]])
    assert sample_token(logits, temperature=0).tolist() == [1]
    key = mx.random.key(0)
    drawn = set()
    for _ in range(200):
        key, sub = mx.random.split(key)
        drawn.add(int(sample_token(logits, 1.0, top_k=2, key=sub).item()))
    assert drawn == {1, 3}
    for _ in range(100):
        key, sub = mx.random.split(key)
        assert int(sample_token(logits, 1.0, top_k=0, top_p=0.5, key=sub).item()) == 1
    for _ in range(100):
        key, sub = mx.random.split(key)
        assert int(sample_token(logits, 1.0, top_k=3, top_p=0.9, key=sub).item()) in {1, 3}


class ByteTokenizer:
    """Tokens are UTF-8 bytes: a multi-byte character spans several tokens."""

    def decode(self, ids, skip_special_tokens=False):
        return bytes(ids).decode("utf-8", errors="replace")


def test_detokenizer_holds_back_incomplete_characters():
    detokenizer = StreamDetokenizer(ByteTokenizer(), silent_ids={0})
    pieces = [detokenizer.push(token) for token in "はい".encode("utf-8")]
    assert pieces == ["", "", "は", "", "", "い"]


def test_detokenizer_renders_a_silent_run_as_one_space():
    detokenizer = StreamDetokenizer(ByteTokenizer(), silent_ids={0, 1})
    pieces = [detokenizer.push(token) for token in [0, 1, 0, ord("a"), ord("b"), 1, 1, ord("c")]]
    assert "".join(pieces) == " ab c"
