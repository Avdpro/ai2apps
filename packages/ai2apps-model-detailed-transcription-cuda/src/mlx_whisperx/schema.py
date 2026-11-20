"""Versioned, dependency-free result types for the standalone experiment."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class TimeSpan:
    start: float
    end: float

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"Invalid time span: {self.start}..{self.end}")

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class DiarizationSpan(TimeSpan):
    speaker: str
    score: float | None = None


@dataclass
class Word:
    word: str
    start: float | None = None
    end: float | None = None
    score: float | None = None
    speaker: str | None = None

    def offset(self, seconds: float) -> Word:
        return Word(
            word=self.word,
            start=None if self.start is None else self.start + seconds,
            end=None if self.end is None else self.end + seconds,
            score=self.score,
            speaker=self.speaker,
        )


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)
    speaker: str | None = None
    score: float | None = None

    def offset(self, seconds: float) -> Segment:
        return Segment(
            start=self.start + seconds,
            end=self.end + seconds,
            text=self.text,
            words=[word.offset(seconds) for word in self.words],
            speaker=self.speaker,
            score=self.score,
        )


@dataclass
class Transcript:
    text: str
    language: str | None
    duration: float
    segments: list[Segment]
    features: dict[str, dict[str, Any]]
    schema: str = "ai2apps.mlx-whisperx-result/v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def word_from_mapping(value: dict[str, Any]) -> Word:
    return Word(
        word=str(value.get("word", value.get("text", ""))),
        start=_optional_float(value.get("start")),
        end=_optional_float(value.get("end")),
        score=_optional_float(value.get("score", value.get("probability"))),
        speaker=(str(value["speaker"]) if value.get("speaker") is not None else None),
    )


def segment_from_mapping(value: dict[str, Any], *, fallback: TimeSpan) -> Segment:
    start = _optional_float(value.get("start"))
    end = _optional_float(value.get("end"))
    return Segment(
        start=fallback.start if start is None else start,
        end=fallback.end if end is None else end,
        text=str(value.get("text", "")),
        words=[
            word_from_mapping(item)
            for item in value.get("words", [])
            if isinstance(item, dict)
        ],
        speaker=(str(value["speaker"]) if value.get("speaker") is not None else None),
        score=_optional_float(value.get("score")),
    )
