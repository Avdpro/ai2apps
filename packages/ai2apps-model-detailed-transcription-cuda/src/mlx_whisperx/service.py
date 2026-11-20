"""Standalone Detailed Transcription service, deliberately separate from Chat."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .aligners import MLXQwen3ForcedAligner
from .backends import MLXQwen3ASRBackend, MLXSortformerDiarizer
from .pipeline import MLXWhisperXPipeline, PipelineConfig
from .vad import EnergyVAD, FullAudioVAD, MeetingEnergyVAD

Profile = Literal["compact", "quality"]
UnsupportedPolicy = Literal["reject", "compatibility"]


class DetailedTranscriptionError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_request") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ModelReference:
    path: str
    revision: str


@dataclass(frozen=True)
class DetailedTranscriptionConfig:
    compact_asr: ModelReference
    quality_asr: ModelReference
    aligner: ModelReference
    diarizer: ModelReference


def capabilities() -> dict[str, Any]:
    return {
        "schema": "ai2apps.detailed-transcription-capabilities/v1",
        "operation": "audio_detailed_transcription",
        "chat_integration": False,
        "languages": ["zh", "yue", "en", "de", "es", "fr", "it", "pt", "ru", "ko", "ja"],
        "profiles": {
            "compact": {"asr": "Qwen3-ASR-0.6B-4bit"},
            "quality": {"asr": "Qwen3-ASR-1.7B-4bit"},
        },
        "features": {
            "segment_timestamps": {"mode": "pipeline"},
            "word_timestamps": {"mode": "pipeline", "provider": "Qwen3-ForcedAligner-0.6B-8bit"},
            "diarization": {
                "mode": "pipeline",
                "provider": "Sortformer-4spk-v2.1-fp16",
                "maximum_speakers": 4,
                "speaker_identity": "global_streaming",
            },
            "speech_rate": {"mode": "pipeline"},
            "emotion": {
                "mode": "fallback",
                "values": ["neutral"],
                "requires_unsupported_policy": "compatibility",
            },
            "speaker_recognition": {
                "mode": "unsupported",
                "reason": "authorized_voice_profiles_not_configured",
            },
            "streaming": {"mode": "unsupported"},
        },
    }


class DetailedTranscriptionService:
    def __init__(self, config: DetailedTranscriptionConfig) -> None:
        self.config = config
        self._transcribers: dict[Profile, MLXQwen3ASRBackend] = {}
        self._aligner: MLXQwen3ForcedAligner | None = None
        self._diarizer: MLXSortformerDiarizer | None = None
        self._lock = asyncio.Lock()

    def _components(self, profile: Profile):
        reference = (
            self.config.compact_asr if profile == "compact" else self.config.quality_asr
        )
        transcriber = self._transcribers.get(profile)
        if transcriber is None:
            transcriber = MLXQwen3ASRBackend(reference.path, revision=reference.revision)
            self._transcribers[profile] = transcriber
        if self._aligner is None:
            self._aligner = MLXQwen3ForcedAligner(
                self.config.aligner.path,
                revision=self.config.aligner.revision,
                max_window_seconds=240.0,
            )
        if self._diarizer is None:
            self._diarizer = MLXSortformerDiarizer(
                self.config.diarizer.path,
                revision=self.config.diarizer.revision,
                speaker_identity="global_streaming",
                streaming_chunk_seconds=5.0,
                threshold=0.20,
                speaker_bridge_gap_seconds=0.12,
            )
        return transcriber, self._aligner, self._diarizer, reference

    async def transcribe(
        self,
        audio_path: str | Path,
        *,
        profile: Profile = "quality",
        language: str | None = None,
        prompt: str | None = None,
        timestamps: Literal["segment", "word"] = "word",
        diarization: bool = True,
        speech_rate_analysis: bool = False,
        emotion_recognition: bool = False,
        speaker_recognition: bool = False,
        unsupported_policy: UnsupportedPolicy = "reject",
        vad: Literal["meeting-energy", "energy", "none"] = "meeting-energy",
    ) -> dict[str, Any]:
        if profile not in {"compact", "quality"}:
            raise DetailedTranscriptionError("profile must be compact or quality")
        if timestamps not in {"segment", "word"}:
            raise DetailedTranscriptionError("timestamps must be segment or word")
        if unsupported_policy not in {"reject", "compatibility"}:
            raise DetailedTranscriptionError(
                "unsupported_policy must be reject or compatibility"
            )
        if vad not in {"meeting-energy", "energy", "none"}:
            raise DetailedTranscriptionError(
                "vad must be meeting-energy, energy, or none"
            )
        if speaker_recognition:
            raise DetailedTranscriptionError(
                "Speaker recognition requires authorized Voice Profiles",
                code="unsupported_feature",
            )
        if emotion_recognition and unsupported_policy == "reject":
            raise DetailedTranscriptionError(
                "Emotion recognition is not implemented by this Package",
                code="unsupported_feature",
            )
        from .audio import read_audio

        if read_audio(audio_path).duration > 3600:
            raise DetailedTranscriptionError(
                "Audio exceeds the one-hour Package limit", code="audio_too_large"
            )
        transcriber, aligner, diarizer, asr_reference = self._components(profile)
        vad_backend = (
            MeetingEnergyVAD()
            if vad == "meeting-energy"
            else EnergyVAD()
            if vad == "energy"
            else FullAudioVAD()
        )
        pipeline = MLXWhisperXPipeline(
            transcriber,
            vad=vad_backend,
            aligner=aligner if timestamps == "word" else None,
            diarizer=diarizer if diarization else None,
        )
        async with self._lock:
            transcript = await asyncio.to_thread(
                pipeline.run,
                audio_path,
                config=PipelineConfig(
                    language=language,
                    prompt=prompt,
                    word_timestamps=timestamps == "word",
                ),
            )
        output = transcript.to_dict()
        output["schema"] = "ai2apps.detailed-transcription-result/v1"
        output["profile"] = profile
        output["features"]["transcription"]["revision"] = asr_reference.revision
        if timestamps == "word":
            output["features"]["alignment"]["revision"] = self.config.aligner.revision
        if diarization:
            output["features"]["diarization"]["revision"] = self.config.diarizer.revision
        output["features"]["emotion"] = (
            {
                "status": "fallback",
                "requested": True,
                "effective": "neutral",
                "reason": "compatibility_policy",
            }
            if emotion_recognition
            else {"status": "ignored", "requested": False}
        )
        output["features"]["speaker_recognition"] = {
            "status": "ignored",
            "requested": False,
        }
        if emotion_recognition:
            for segment in output["segments"]:
                segment["emotion"] = "neutral"
        output["features"]["speech_rate"] = self._speech_rates(
            output, enabled=speech_rate_analysis
        )
        return output

    @staticmethod
    def _speech_rates(output: dict[str, Any], *, enabled: bool) -> dict[str, Any]:
        if not enabled:
            return {"status": "ignored", "requested": False}
        language = str(output.get("language") or "").lower()
        unit = "characters_per_minute" if language.startswith("zh") else "words_per_minute"
        for segment in output.get("segments", []):
            duration = max(float(segment["end"]) - float(segment["start"]), 1e-6)
            if language.startswith("zh"):
                count = sum(1 for character in segment.get("text", "") if "\u3400" <= character <= "\u9fff")
            else:
                count = len(str(segment.get("text", "")).split())
            segment["speech_rate"] = {"value": count * 60.0 / duration, "unit": unit}
        return {"status": "pipeline", "requested": True, "unit": unit}
