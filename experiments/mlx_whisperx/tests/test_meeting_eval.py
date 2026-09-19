from experiments.mlx_whisperx.evaluate_diarization import (
    transcript_speaker_metrics,
)
from experiments.mlx_whisperx.evaluate_meeting_transcript import (
    SpeakerWord,
    lexical_alignment,
    speaker_attributed_metrics,
)
from experiments.mlx_whisperx.schema import DiarizationSpan


def _word(value: str, speaker: str, index: int) -> SpeakerWord:
    return SpeakerWord(value, float(index), float(index) + 0.5, speaker)


def test_lexical_alignment_returns_exact_matches_and_edit_count():
    edits, matches = lexical_alignment(
        ["we", "build", "audio"], ["we", "ship", "audio"]
    )
    assert edits == 1
    assert matches == [(0, 0), (2, 2)]


def test_cpwer_is_invariant_to_anonymous_speaker_labels():
    reference = [
        _word("hello", "A", 0),
        _word("good", "B", 1),
        _word("world", "A", 2),
        _word("morning", "B", 3),
    ]
    hypothesis = [
        _word("hello", "speaker_1", 0),
        _word("good", "speaker_0", 1),
        _word("world", "speaker_1", 2),
        _word("morning", "speaker_0", 3),
    ]

    metrics = speaker_attributed_metrics(reference, hypothesis)

    assert metrics["speaker_attributed_method"] == "cpWER"
    assert metrics["speaker_attributed_wer"] == 0.0
    assert metrics["speaker_accuracy_on_correct_words"] == 1.0
    assert metrics["speaker_mapping"] == {"speaker_0": "B", "speaker_1": "A"}


def test_cpwer_charges_words_from_an_extra_hypothesis_speaker():
    reference = [_word("hello", "A", 0)]
    hypothesis = [
        _word("hello", "speaker_0", 0),
        _word("noise", "speaker_1", 1),
    ]

    metrics = speaker_attributed_metrics(reference, hypothesis)

    assert metrics["speaker_attributed_wer"] == 1.0


def test_transcript_speaker_metrics_assigns_words_from_diarization():
    reference = [_word("hello", "A", 0)]
    result = {
        "segments": [
            {
                "words": [
                    {"word": "hello", "start": 0.0, "end": 0.5}
                ]
            }
        ]
    }

    metrics = transcript_speaker_metrics(
        result, reference, [DiarizationSpan(0.0, 0.5, "speaker_0")]
    )

    assert metrics["speaker_attributed_wer"] == 0.0
    assert metrics["speaker_accuracy_on_correct_words"] == 1.0
