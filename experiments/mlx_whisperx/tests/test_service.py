from __future__ import annotations

import asyncio

import pytest

from experiments.mlx_whisperx.service import (
    DetailedTranscriptionConfig,
    DetailedTranscriptionError,
    DetailedTranscriptionService,
    ModelReference,
    capabilities,
)


def _service() -> DetailedTranscriptionService:
    reference = ModelReference("unused", "revision")
    return DetailedTranscriptionService(
        DetailedTranscriptionConfig(reference, reference, reference, reference)
    )


def test_capabilities_are_detailed_transcription_only():
    value = capabilities()
    assert value["operation"] == "audio_detailed_transcription"
    assert value["chat_integration"] is False
    assert value["features"]["diarization"]["maximum_speakers"] == 4
    assert value["features"]["streaming"]["mode"] == "unsupported"


def test_unsupported_emotion_rejects_before_loading_models():
    with pytest.raises(DetailedTranscriptionError, match="Emotion recognition"):
        asyncio.run(_service().transcribe("unused.wav", emotion_recognition=True))


def test_speaker_recognition_never_fakes_an_identity():
    with pytest.raises(DetailedTranscriptionError, match="Voice Profiles"):
        asyncio.run(_service().transcribe("unused.wav", speaker_recognition=True))


def test_invalid_vad_is_rejected_before_loading_audio():
    with pytest.raises(DetailedTranscriptionError, match="vad must be"):
        asyncio.run(_service().transcribe("unused.wav", vad="unknown"))


def test_speech_rate_analysis_uses_language_specific_units():
    output = {
        "language": "zh-CN",
        "segments": [{"start": 0.0, "end": 2.0, "text": "你好 AI"}],
    }
    feature = _service()._speech_rates(output, enabled=True)
    assert feature == {
        "status": "pipeline",
        "requested": True,
        "unit": "characters_per_minute",
    }
    assert output["segments"][0]["speech_rate"]["value"] == 60.0
