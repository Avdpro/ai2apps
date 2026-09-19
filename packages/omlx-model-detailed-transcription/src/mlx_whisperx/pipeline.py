"""Standalone WhisperX-compatible pipeline orchestration."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from .assignment import assign_speakers
from .audio import read_audio
from .schema import (
    DiarizationSpan,
    Segment,
    TimeSpan,
    Transcript,
    segment_from_mapping,
)
from .vad import EnergyVAD, VoiceActivityDetector


class Transcriber(Protocol):
    name: str

    def transcribe(
        self,
        audio_path: str | Path,
        *,
        language: str | None,
        prompt: str | None,
        word_timestamps: bool,
    ) -> dict[str, Any]: ...


class Diarizer(Protocol):
    name: str

    def diarize(self, audio_path: str | Path) -> list[DiarizationSpan]: ...


class Aligner(Protocol):
    name: str

    def align(
        self,
        audio_path: str | Path,
        segments: list[Segment],
        *,
        language: str | None,
    ) -> list[Segment]: ...


@dataclass(frozen=True)
class PipelineConfig:
    language: str | None = None
    prompt: str | None = None
    word_timestamps: bool = True
    alignment_fallback: Literal["reject", "native"] = "reject"
    max_transcription_chunk_seconds: float | None = 30.0


def split_spans(
    spans: list[TimeSpan], max_duration: float | None
) -> list[TimeSpan]:
    if max_duration is None:
        return spans
    if max_duration <= 0:
        raise ValueError("max_transcription_chunk_seconds must be positive or None")
    result: list[TimeSpan] = []
    for span in spans:
        start = span.start
        while start < span.end:
            end = min(span.end, start + max_duration)
            result.append(TimeSpan(start, end))
            start = end
    return result


def clip_segments(segments: list[Segment], duration: float) -> list[Segment]:
    """Keep the public timeline inside the source audio boundary."""

    clipped: list[Segment] = []
    for segment in segments:
        start = max(0.0, segment.start)
        end = min(duration, segment.end)
        if start >= duration or end <= start:
            continue
        segment.start = start
        segment.end = end
        valid_words = []
        for word in segment.words:
            if word.start is None or word.end is None:
                valid_words.append(word)
                continue
            word_start = max(start, word.start)
            word_end = min(end, word.end)
            if word_end <= word_start:
                continue
            word.start = word_start
            word.end = word_end
            valid_words.append(word)
        segment.words = valid_words
        clipped.append(segment)
    return clipped


class MLXWhisperXPipeline:
    def __init__(
        self,
        transcriber: Transcriber,
        *,
        vad: VoiceActivityDetector | None = None,
        aligner: Aligner | None = None,
        diarizer: Diarizer | None = None,
    ) -> None:
        self.transcriber = transcriber
        self.vad = vad or EnergyVAD()
        self.aligner = aligner
        self.diarizer = diarizer

    def run(
        self, audio_path: str | Path, *, config: PipelineConfig | None = None
    ) -> Transcript:
        settings = config or PipelineConfig()
        source_path = Path(audio_path).expanduser()
        audio = read_audio(source_path)
        speech = split_spans(
            self.vad.detect(audio), settings.max_transcription_chunk_seconds
        )
        segments: list[Segment] = []
        languages: list[str] = []
        with tempfile.TemporaryDirectory(prefix="mlx-whisperx-") as temporary:
            temporary_root = Path(temporary)
            for index, span in enumerate(speech):
                chunk_path = temporary_root / f"speech-{index:05d}.wav"
                audio.slice(span.start, span.end).write_wav(chunk_path)
                result = self.transcriber.transcribe(
                    chunk_path,
                    language=settings.language,
                    prompt=settings.prompt,
                    word_timestamps=settings.word_timestamps,
                )
                language = result.get("language")
                if language:
                    languages.append(str(language))
                local_fallback = TimeSpan(0.0, span.duration)
                raw_segments = result.get("segments") or []
                if raw_segments:
                    for item in raw_segments:
                        if not isinstance(item, dict):
                            continue
                        segment = segment_from_mapping(
                            item, fallback=local_fallback
                        )
                        segment.start = max(0.0, segment.start)
                        segment.end = min(span.duration, segment.end)
                        has_content = segment.text.strip() or any(
                            word.word.strip() for word in segment.words
                        )
                        if has_content and segment.end > segment.start:
                            segments.append(segment.offset(span.start))
                elif str(result.get("text", "")).strip():
                    segments.append(
                        Segment(
                            start=span.start,
                            end=span.end,
                            text=str(result["text"]),
                        )
                    )

        language = settings.language or (languages[0] if languages else None)
        alignment_error: str | None = None
        if self.aligner is not None:
            try:
                segments = self.aligner.align(
                    source_path, segments, language=language
                )
            except Exception as error:
                if settings.alignment_fallback != "native":
                    raise
                alignment_error = f"{type(error).__name__}: {error}"

        segments = clip_segments(segments, audio.duration)

        diarization: list[DiarizationSpan] = []
        if self.diarizer is not None:
            diarization = self.diarizer.diarize(source_path)
            assign_speakers(segments, diarization)

        text = " ".join(
            segment.text.strip() for segment in segments if segment.text.strip()
        ).strip()
        if self.aligner is not None and alignment_error is None:
            alignment_feature = {
                "status": "pipeline",
                "provider": self.aligner.name,
                "method": getattr(
                    self.aligner, "alignment_method", "forced_alignment"
                ),
            }
            minimum_score = getattr(self.aligner, "min_word_score", None)
            if minimum_score is not None:
                alignment_feature["minimum_word_score"] = minimum_score
            unknown_character_policy = getattr(
                self.aligner, "unknown_character_policy", None
            )
            if unknown_character_policy is not None:
                alignment_feature["unknown_character_policy"] = (
                    unknown_character_policy
                )
            skipped_characters = getattr(
                self.aligner, "skipped_characters", None
            )
            if skipped_characters:
                alignment_feature["skipped_characters"] = dict(
                    sorted(skipped_characters.items())
                )
            alignment_stats = getattr(self.aligner, "alignment_stats", None)
            if alignment_stats:
                alignment_feature.update(alignment_stats)
            forced_alignment_feature = {
                "status": "pipeline",
                "provider": self.aligner.name,
            }
        elif self.aligner is not None:
            alignment_feature = {
                "status": "fallback",
                "provider": "whisper_attention",
                "requested_provider": self.aligner.name,
                "method": "native_attention",
                "reason": alignment_error,
            }
            forced_alignment_feature = {
                "status": "rejected",
                "provider": self.aligner.name,
                "reason": alignment_error,
            }
        else:
            alignment_feature = {
                "status": "native" if settings.word_timestamps else "ignored",
                "provider": (
                    "whisper_attention" if settings.word_timestamps else None
                ),
                "method": "native_attention" if settings.word_timestamps else None,
            }
            forced_alignment_feature = {
                "status": "rejected",
                "reason": "independent_aligner_not_configured",
            }
        features = {
            "transcription": {
                "status": "native",
                "provider": self.transcriber.name,
            },
            "vad": {"status": "pipeline", "provider": self.vad.name},
            "alignment": alignment_feature,
            "diarization": (
                {
                    "status": "pipeline",
                    "provider": self.diarizer.name,
                    "speaker_identity": getattr(
                        self.diarizer, "speaker_identity", "global_model_slots"
                    ),
                    "threshold": getattr(self.diarizer, "threshold", None),
                    "speaker_bridge_gap_seconds": getattr(
                        self.diarizer, "speaker_bridge_gap_seconds", None
                    ),
                    **(
                        {
                            "streaming_chunk_seconds": (
                                self.diarizer.streaming_chunk_seconds
                            )
                        }
                        if getattr(self.diarizer, "speaker_identity", None)
                        == "global_streaming"
                        else {
                            "window_seconds": getattr(
                                self.diarizer, "window_seconds", None
                            )
                        }
                    ),
                }
                if self.diarizer is not None
                else {"status": "rejected", "reason": "not_configured"}
            ),
            "forced_alignment": forced_alignment_feature,
        }
        return Transcript(
            text=text,
            language=language,
            duration=audio.duration,
            segments=segments,
            features=features,
        )
