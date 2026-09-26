from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from experiments.mlx_whisperx.aligners import (
    MLXCTCAligner,
    MLXQwen3ForcedAligner,
    UnsupportedAlignmentLanguageError,
)
from experiments.mlx_whisperx.ctc import ctc_viterbi_align, log_softmax
from experiments.mlx_whisperx.schema import Segment, Word


def test_ctc_viterbi_aligns_two_tokens_to_expected_frames():
    logits = np.full((5, 3), -8.0)
    logits[0, 0] = 8.0
    logits[1, 1] = 8.0
    logits[2, 0] = 8.0
    logits[3, 2] = 8.0
    logits[4, 0] = 8.0
    aligned = ctc_viterbi_align(
        log_softmax(logits), [1, 2], duration=1.0, blank_id=0
    )
    assert (aligned[0].start, aligned[0].end) == pytest.approx((0.2, 0.4))
    assert (aligned[1].start, aligned[1].end) == pytest.approx((0.6, 0.8))
    assert all(item.score > 0.99 for item in aligned)


def test_ctc_repeated_tokens_require_intervening_blank():
    logits = np.full((5, 2), -8.0)
    logits[0, 0] = 8.0
    logits[1, 1] = 8.0
    logits[2, 0] = 8.0
    logits[3, 1] = 8.0
    logits[4, 0] = 8.0
    aligned = ctc_viterbi_align(
        log_softmax(logits), [1, 1], duration=1.0, blank_id=0
    )
    assert aligned[0].end <= aligned[1].start


def test_english_target_uses_vocab_and_ignores_punctuation(tmp_path: Path):
    aligner = MLXCTCAligner(str(tmp_path))
    words = [Word("Hello,"), Word("world!")]
    vocab = {"|": 1, "H": 2, "E": 3, "L": 4, "O": 5, "W": 6, "R": 7, "D": 8}
    target, ranges = aligner._target(words, vocab)
    assert target == [2, 3, 4, 4, 5, 1, 6, 5, 7, 4, 8]
    assert ranges == [(0, 5), (6, 11)]


def test_non_english_alignment_fails_before_model_loading(tmp_path: Path):
    (tmp_path / "config.json").write_text(
        '{"ai2apps_alignment_languages":["en"]}'
    )
    aligner = MLXCTCAligner(str(tmp_path))
    segments = [Segment(0.0, 1.0, "你好", words=[Word("你好")])]
    with pytest.raises(UnsupportedAlignmentLanguageError, match="got zh"):
        aligner.align(tmp_path / "unused.wav", segments, language="zh")


def test_target_marks_punctuation_only_word_as_unalignable(tmp_path: Path):
    aligner = MLXCTCAligner(str(tmp_path))
    target, ranges = aligner._target(
        [Word("HELLO"), Word("¶")],
        {"H": 1, "E": 2, "L": 3, "O": 4, "|": 5},
    )
    assert target == [1, 2, 3, 3, 4]
    assert ranges == [(0, 5), (5, 5)]


def test_alignment_score_threshold_is_validated(tmp_path: Path):
    with pytest.raises(ValueError, match="between 0 and 1"):
        MLXCTCAligner(str(tmp_path), min_word_score=1.1)


def test_ctc_groups_segments_into_bounded_windows(tmp_path: Path):
    aligner = MLXCTCAligner(str(tmp_path), max_window_seconds=10.0)
    segments = [
        Segment(0.0, 4.0, "one"),
        Segment(4.2, 9.0, "two"),
        Segment(10.0, 14.0, "three"),
    ]
    assert aligner._groups(segments) == [segments[:2], segments[2:]]


def test_checkpoint_declares_chinese_language(tmp_path: Path):
    (tmp_path / "config.json").write_text(
        '{"ai2apps_alignment_languages":["zh"]}'
    )
    assert MLXCTCAligner(str(tmp_path))._supported_languages() == {"zh"}


def test_chinese_segments_are_split_into_character_words(tmp_path: Path):
    aligner = MLXCTCAligner(str(tmp_path), supported_languages={"zh"})
    segment = Segment(0.0, 1.0, "你好，世界")
    words = aligner._ensure_words([segment], language="zh")
    assert [word.word for word in words] == ["你", "好", "，", "世", "界"]


def test_chinese_target_does_not_insert_word_delimiters(tmp_path: Path):
    aligner = MLXCTCAligner(str(tmp_path), supported_languages={"zh"})
    target, ranges = aligner._target(
        [Word("你"), Word("好")],
        {"|": 0, "你": 1, "好": 2},
        use_delimiter=False,
    )
    assert target == [1, 2]
    assert ranges == [(0, 1), (1, 2)]


def test_semantic_characters_missing_from_vocab_can_fail_closed(tmp_path: Path):
    aligner = MLXCTCAligner(
        str(tmp_path), unknown_character_policy="reject"
    )
    with pytest.raises(ValueError, match="cannot align characters: A1"):
        aligner._normalize("你，A1！", {"你": 1})


def test_semantic_characters_missing_from_vocab_are_skipped_and_reported(
    tmp_path: Path,
):
    aligner = MLXCTCAligner(str(tmp_path))
    assert aligner._normalize("你，A1A！", {"你": 1}) == ["你"]
    assert aligner.skipped_characters == {"A": 2, "1": 1}


def test_segment_with_no_aligned_words_keeps_text_and_segment_timing(
    tmp_path: Path,
):
    aligner = MLXCTCAligner(str(tmp_path))
    segment = Segment(2.0, 3.0, "2026", words=[Word("2"), Word("0")])
    assert aligner._finalize_group([segment], set()) == [segment]
    assert (segment.start, segment.end, segment.text, segment.words) == (
        2.0,
        3.0,
        "2026",
        [],
    )


def test_qwen_language_names_and_window_limit(tmp_path: Path):
    assert MLXQwen3ForcedAligner._language_name("zh-CN") == "Chinese"
    assert MLXQwen3ForcedAligner._language_name("en_US") == "English"
    assert MLXQwen3ForcedAligner._language_name("English") == "English"
    assert MLXQwen3ForcedAligner._language_name("Cantonese") == "Cantonese"
    with pytest.raises(UnsupportedAlignmentLanguageError, match="got ar"):
        MLXQwen3ForcedAligner._language_name("ar")
    with pytest.raises(ValueError, match="in \\(0, 300\\]"):
        MLXQwen3ForcedAligner(str(tmp_path), max_window_seconds=301)


def test_qwen_items_are_partitioned_back_to_segments(tmp_path: Path):
    from types import SimpleNamespace

    aligner = MLXQwen3ForcedAligner(str(tmp_path))
    segments = [Segment(2.0, 3.0, "你好"), Segment(3.0, 4.0, "AI2Apps")]
    items = [
        SimpleNamespace(text="你", start_time=0.1, end_time=0.2),
        SimpleNamespace(text="好", start_time=0.2, end_time=0.4),
        SimpleNamespace(text="AI2Apps", start_time=1.1, end_time=1.6),
    ]
    result = aligner._apply_items(
        segments, [2, 1], items, offset=1.9, language_name="Chinese"
    )
    assert [word.word for word in result[0].words] == ["你", "好"]
    assert result[0].text == "你好"
    assert result[1].text == "AI2Apps"
    assert (result[0].start, result[0].end) == pytest.approx((2.0, 2.3))
    assert (result[1].start, result[1].end) == pytest.approx((3.0, 3.5))
    assert aligner.alignment_stats == {
        "total_units": 3,
        "aligned_units": 3,
        "discarded_unaligned_units": 0,
        "coverage": 1.0,
        "rewritten_segments": 0,
        "removed_text_characters": 0,
    }


def test_qwen_alignment_preserves_asr_punctuation_and_casing(tmp_path: Path):
    from types import SimpleNamespace

    aligner = MLXQwen3ForcedAligner(str(tmp_path))
    segments = [
        Segment(0.0, 1.0, "Come on, Joey!"),
        Segment(1.0, 2.0, "你好，世界！"),
    ]
    items = [
        SimpleNamespace(text="come", start_time=0.1, end_time=0.3),
        SimpleNamespace(text="on", start_time=0.3, end_time=0.5),
        SimpleNamespace(text="joey", start_time=0.5, end_time=0.9),
        SimpleNamespace(text="你", start_time=1.1, end_time=1.2),
        SimpleNamespace(text="好", start_time=1.2, end_time=1.3),
        SimpleNamespace(text="世", start_time=1.3, end_time=1.4),
        SimpleNamespace(text="界", start_time=1.4, end_time=1.5),
    ]

    aligner._apply_items(segments, [3, 4], items, offset=0.0)

    assert segments[0].text == "Come on, Joey!"
    assert segments[1].text == "你好，世界！"
    assert [word.word for word in segments[0].words] == ["come", "on", "joey"]
    assert aligner.alignment_stats["rewritten_segments"] == 0


def test_qwen_alignment_replaces_unalignable_hallucinated_text(tmp_path: Path):
    from types import SimpleNamespace

    aligner = MLXQwen3ForcedAligner(str(tmp_path))
    segment = Segment(0.0, 30.0, "yeah " * 1000)
    items = [SimpleNamespace(text="yeah", start_time=1.0, end_time=1.2)]

    aligner._apply_items([segment], [1], items, offset=0.0)

    assert segment.text == "yeah"
    assert aligner.alignment_stats["rewritten_segments"] == 1
    assert aligner.alignment_stats["removed_text_characters"] > 4000


def test_qwen_alignment_discards_zero_duration_units(tmp_path: Path):
    from types import SimpleNamespace

    aligner = MLXQwen3ForcedAligner(str(tmp_path))
    segment = Segment(0.0, 2.0, "hello repeated repeated")
    items = [
        SimpleNamespace(text="hello", start_time=0.1, end_time=0.5),
        SimpleNamespace(text="repeated", start_time=0.0, end_time=0.0),
    ]

    aligner._apply_items([segment], [2], items, offset=0.0)

    assert segment.text == "hello"
    assert [word.word for word in segment.words] == ["hello"]
    assert aligner.alignment_stats["discarded_unaligned_units"] == 1
