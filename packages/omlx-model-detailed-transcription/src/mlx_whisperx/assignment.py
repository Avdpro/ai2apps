"""Deterministic diarization-to-transcript interval assignment."""

from __future__ import annotations

from .schema import DiarizationSpan, Segment


def overlap(start: float, end: float, span: DiarizationSpan) -> float:
    return max(0.0, min(end, span.end) - max(start, span.start))


def speaker_for(
    start: float | None,
    end: float | None,
    diarization: list[DiarizationSpan],
) -> str | None:
    if start is None or end is None or end < start:
        return None
    ranked = sorted(
        (
            (overlap(start, end, span), -(span.end - span.start), span.speaker)
            for span in diarization
        ),
        reverse=True,
    )
    if not ranked or ranked[0][0] <= 0:
        return None
    return ranked[0][2]


def assign_speakers(
    segments: list[Segment], diarization: list[DiarizationSpan]
) -> list[Segment]:
    for segment in segments:
        for word in segment.words:
            word.speaker = speaker_for(word.start, word.end, diarization)
        word_speakers = [word.speaker for word in segment.words if word.speaker]
        if word_speakers:
            segment.speaker = max(
                sorted(set(word_speakers)), key=word_speakers.count
            )
        else:
            segment.speaker = speaker_for(segment.start, segment.end, diarization)
        if segment.speaker:
            for word in segment.words:
                if word.speaker is None:
                    word.speaker = segment.speaker
    return segments
