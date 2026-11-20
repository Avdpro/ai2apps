"""Lazy real-model backends; importing this module does not initialize MLX."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Literal

from .audio import AudioBuffer, read_audio
from .schema import DiarizationSpan, TimeSpan


def _plain(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return vars(value)
    return value


def _primary_language(value: str) -> str:
    return value.strip().lower().replace("_", "-").split("-", 1)[0]


_QWEN_LANGUAGE_NAMES = {
    "zh": "Chinese",
    "yue": "Cantonese",
    "en": "English",
    "de": "German",
    "es": "Spanish",
    "fr": "French",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ko": "Korean",
    "ja": "Japanese",
}


def _qwen_language(value: str) -> str:
    primary = _primary_language(value)
    return _QWEN_LANGUAGE_NAMES.get(primary, value)


class MLXWhisperBackend:
    name = "mlx_audio_whisper"

    def __init__(self, model: str, *, revision: str | None = None) -> None:
        self.model_source = model
        self.revision = revision
        self._model: Any | None = None

    def _load(self) -> Any:
        if self._model is None:
            self._validate_local_checkpoint()
            from mlx_audio.stt.utils import load_model

            kwargs = {"revision": self.revision} if self.revision else {}
            self._model = load_model(self.model_source, strict=False, **kwargs)
            module = type(self._model).__module__.lower()
            if "whisper" not in module:
                raise TypeError(
                    f"Checkpoint is not an mlx-audio Whisper model: {module}"
                )
            processor = getattr(self._model, "_processor", None)
            tokenizer = getattr(processor, "tokenizer", None)
            if tokenizer is not None:
                tokenizer.clean_up_tokenization_spaces = False
        return self._model

    def _validate_local_checkpoint(self) -> None:
        """Reject legacy mlx-examples checkpoints before allocating the model."""

        path = Path(self.model_source).expanduser()
        if not path.is_dir():
            return
        required = ("config.json", "preprocessor_config.json")
        missing = [name for name in required if not (path / name).is_file()]
        tokenizer_present = any(
            (path / name).is_file()
            for name in ("tokenizer.json", "vocab.json", "multilingual.tiktoken")
        )
        if not tokenizer_present:
            missing.append("tokenizer assets")
        if missing:
            details = ", ".join(missing)
            raise ValueError(
                "Local checkpoint is not compatible with the current mlx-audio "
                f"Whisper loader (missing: {details}). Use an mlx-audio ASR "
                "conversion rather than a legacy mlx-examples Whisper checkpoint."
            )

    def transcribe(
        self,
        audio_path: str | Path,
        *,
        language: str | None,
        prompt: str | None,
        word_timestamps: bool,
    ) -> dict[str, Any]:
        model = self._load()
        kwargs: dict[str, Any] = {
            "word_timestamps": word_timestamps,
            "verbose": None,
            "temperature": 0.0,
        }
        if language:
            kwargs["language"] = _primary_language(language)
        if prompt:
            kwargs["initial_prompt"] = prompt
        result = _plain(model.generate(str(audio_path), **kwargs))
        if not isinstance(result, dict):
            raise TypeError(f"Unexpected Whisper result: {type(result).__name__}")
        result["segments"] = [
            _plain(item) for item in result.get("segments", [])
        ]
        return result


class MLXQwen3ASRBackend:
    """Qwen3-ASR adapter for the same pipeline transcriber contract."""

    name = "mlx_audio_qwen3_asr"

    def __init__(self, model: str, *, revision: str | None = None) -> None:
        self.model_source = model
        self.revision = revision
        self._model: Any | None = None

    def _load(self) -> Any:
        if self._model is None:
            from mlx_audio.stt.utils import load_model

            kwargs = {"revision": self.revision} if self.revision else {}
            self._model = load_model(self.model_source, strict=False, **kwargs)
            module = type(self._model).__module__.lower()
            if "qwen3_asr" not in module:
                raise TypeError(
                    f"Checkpoint is not an mlx-audio Qwen3-ASR model: {module}"
                )
        return self._model

    def transcribe(
        self,
        audio_path: str | Path,
        *,
        language: str | None,
        prompt: str | None,
        word_timestamps: bool,
    ) -> dict[str, Any]:
        del word_timestamps
        model = self._load()
        kwargs: dict[str, Any] = {
            "verbose": False,
            "temperature": 0.0,
        }
        if language:
            kwargs["language"] = _qwen_language(language)
        if prompt:
            kwargs["system_prompt"] = prompt
        result = _plain(model.generate(str(audio_path), **kwargs))
        if not isinstance(result, dict):
            raise TypeError(f"Unexpected Qwen3-ASR result: {type(result).__name__}")
        result["segments"] = [
            _plain(item) for item in result.get("segments", [])
        ]
        result_language = result.get("language")
        if isinstance(result_language, list):
            result["language"] = result_language[0] if result_language else language
        return result


class MLXSortformerDiarizer:
    name = "mlx_audio_sortformer"

    def __init__(
        self,
        model: str,
        *,
        revision: str | None = None,
        window_seconds: float | None = 120.0,
        speaker_identity: Literal["global_streaming", "window_local"] = (
            "global_streaming"
        ),
        streaming_chunk_seconds: float = 5.0,
        threshold: float = 0.20,
        speaker_bridge_gap_seconds: float = 0.12,
    ) -> None:
        if window_seconds is not None and window_seconds <= 0:
            raise ValueError("window_seconds must be positive or None")
        if speaker_identity not in {"global_streaming", "window_local"}:
            raise ValueError("speaker_identity must be global_streaming or window_local")
        if streaming_chunk_seconds <= 0:
            raise ValueError("streaming_chunk_seconds must be positive")
        if not 0.0 < threshold < 1.0:
            raise ValueError("threshold must be between 0 and 1")
        if speaker_bridge_gap_seconds < 0:
            raise ValueError("speaker_bridge_gap_seconds must be non-negative")
        self.model_source = model
        self.revision = revision
        self.window_seconds = window_seconds
        self.speaker_identity = speaker_identity
        self.streaming_chunk_seconds = streaming_chunk_seconds
        self.threshold = threshold
        self.speaker_bridge_gap_seconds = speaker_bridge_gap_seconds
        self._model: Any | None = None
        self._cached_spans: list[DiarizationSpan] | None = None

    def _load(self) -> Any:
        if self._model is None:
            from mlx_audio.vad import load_model

            kwargs = {"revision": self.revision} if self.revision else {}
            self._model = load_model(self.model_source, strict=False, **kwargs)
        return self._model

    def diarize(self, audio_path: str | Path) -> list[DiarizationSpan]:
        if self._cached_spans is not None:
            spans = self._cached_spans
            self._cached_spans = None
            return spans
        return self._generate(read_audio(audio_path))

    def detect(self, audio: AudioBuffer) -> list[TimeSpan]:
        """Use unioned Sortformer speaker activity as trained VAD output."""

        self._cached_spans = self._generate(audio)
        return self.speech_spans(self._cached_spans)

    def _generate(self, audio: AudioBuffer) -> list[DiarizationSpan]:
        model = self._load()
        if self.speaker_identity == "global_streaming":
            spans: list[DiarizationSpan] = []
            for result in model.generate_stream(
                audio.samples,
                sample_rate=audio.sample_rate,
                chunk_duration=self.streaming_chunk_seconds,
                threshold=self.threshold,
                min_duration=0.12,
                merge_gap=0.12,
                verbose=False,
            ):
                spans.extend(self._spans(result))
            return self._merge_same_speaker(
                spans, merge_gap=self.speaker_bridge_gap_seconds
            )

        window = self.window_seconds
        if window is None or audio.duration <= window:
            result = model.generate(
                audio.samples,
                sample_rate=audio.sample_rate,
                threshold=self.threshold,
                min_duration=0.12,
                merge_gap=0.12,
                verbose=False,
            )
            return self._spans(result)

        spans: list[DiarizationSpan] = []
        start = 0.0
        window_index = 0
        while start < audio.duration:
            end = min(audio.duration, start + window)
            chunk = audio.slice(start, end)
            result = model.generate(
                chunk.samples,
                sample_rate=chunk.sample_rate,
                threshold=self.threshold,
                min_duration=0.12,
                merge_gap=0.12,
                verbose=False,
            )
            spans.extend(
                self._spans(
                    result,
                    offset=start,
                    speaker_prefix=f"window_{window_index:04d}_",
                )
            )
            start = end
            window_index += 1
        return spans

    @staticmethod
    def _merge_same_speaker(
        spans: list[DiarizationSpan], *, merge_gap: float = 0.12
    ) -> list[DiarizationSpan]:
        by_speaker: dict[str, list[DiarizationSpan]] = {}
        for span in spans:
            by_speaker.setdefault(span.speaker, []).append(span)
        merged: list[DiarizationSpan] = []
        for speaker, speaker_spans in by_speaker.items():
            current: DiarizationSpan | None = None
            for span in sorted(speaker_spans, key=lambda item: (item.start, item.end)):
                if current is not None and span.start <= current.end + merge_gap:
                    current = DiarizationSpan(
                        current.start,
                        max(current.end, span.end),
                        speaker,
                        current.score,
                    )
                else:
                    if current is not None:
                        merged.append(current)
                    current = span
            if current is not None:
                merged.append(current)
        return sorted(merged, key=lambda item: (item.start, item.end, item.speaker))

    @staticmethod
    def _spans(
        result: Any,
        *,
        offset: float = 0.0,
        speaker_prefix: str = "",
    ) -> list[DiarizationSpan]:
        spans: list[DiarizationSpan] = []
        for item in getattr(result, "segments", []):
            value = _plain(item)
            speaker = value.get("speaker")
            spans.append(
                DiarizationSpan(
                    start=offset + float(value["start"]),
                    end=offset + float(value["end"]),
                    speaker=(
                        speaker_prefix + str(speaker)
                        if str(speaker).startswith("speaker_")
                        else f"{speaker_prefix}speaker_{speaker}"
                    ),
                    score=(float(value["score"]) if value.get("score") is not None else None),
                )
            )
        return spans

    @staticmethod
    def speech_spans(
        diarization: list[DiarizationSpan], *, merge_gap: float = 0.12
    ) -> list[TimeSpan]:
        """Union overlapping per-speaker spans into transcription regions."""

        ordered = sorted(diarization, key=lambda item: (item.start, item.end))
        if not ordered:
            return []
        merged = [TimeSpan(ordered[0].start, ordered[0].end)]
        for item in ordered[1:]:
            previous = merged[-1]
            if item.start <= previous.end + merge_gap:
                merged[-1] = TimeSpan(previous.start, max(previous.end, item.end))
            else:
                merged.append(TimeSpan(item.start, item.end))
        return merged
