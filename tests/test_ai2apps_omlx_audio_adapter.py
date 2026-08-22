# SPDX-License-Identifier: Apache-2.0
"""Reusable oMLX audio adapter contract tests without Metal."""

from __future__ import annotations

import io
import wave
from pathlib import Path

import pytest

from ai2apps.model_worker import (
    ModelWorkerCheckpoint,
    ModelWorkerContext,
    ModelWorkerError,
    ModelWorkerPart,
    ModelWorkerRequest,
    ModelWorkerResponse,
    OmlxSTTAdapter,
    OmlxTTSAdapter,
)


def _context(
    tmp_path: Path,
    model_id: str,
    *,
    model_type: str | None = None,
) -> ModelWorkerContext:
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    model_type = model_type or ("audio_stt" if model_id.endswith("/stt") else "audio_tts")
    audio_capabilities = (
        {
            "timestamps": {"mode": "native"},
            "diarization": {"mode": "unsupported"},
            "speaker_recognition": {"mode": "unsupported"},
            "speech_rate": {"mode": "unsupported"},
            "emotion": {"mode": "unsupported"},
        }
        if model_type == "audio_stt"
        else {
            "named_voices": {"mode": "native", "voices": ["narrator"]},
            "speed": {"mode": "unsupported"},
            "emotion": {"mode": "native", "values": ["neutral", "happy"]},
            "instructions": {"mode": "native"},
            "voice_profiles": {"mode": "unsupported"},
        }
    )
    return ModelWorkerContext(
        service_id="example.audio",
        package_root=tmp_path,
        data_root=tmp_path / "data",
        models=(
            {
                "id": model_id,
                "upstream_id": "upstream/audio",
                "model_type": model_type,
                "audio_capabilities": {
                    model_type.removeprefix("audio_"): audio_capabilities
                },
            },
        ),
        checkpoints=(
            ModelWorkerCheckpoint(
                model_id=model_id,
                upstream_id="upstream/audio",
                provider="huggingface",
                repo_id="upstream/audio",
                revision="a" * 40,
                path=checkpoint,
                preparation={"recipe": "native"},
            ),
        ),
    )


def _wav_bytes() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(24_000)
        target.writeframes(b"\x00\x00" * 2400)
    return output.getvalue()


class _STTEngine:
    async def start(self):
        return None

    async def stop(self):
        return None

    async def transcribe(self, path, **kwargs):
        assert Path(path).is_file()
        return {
            "text": "你好",
            "language": kwargs["language"],
            "segments": [{"id": 0, "start": 0.0, "end": 0.1, "text": "你好"}],
        }


class _STTAdapter(OmlxSTTAdapter):
    async def create_engine(self, checkpoint, runtime_options=None):
        return _STTEngine()


class _TTSEngine:
    async def start(self):
        return None

    async def stop(self):
        return None

    async def synthesize(self, text, **kwargs):
        self.text = text
        self.kwargs = kwargs
        return _wav_bytes()


class _TTSAdapter(OmlxTTSAdapter):
    async def create_engine(self, checkpoint, runtime_options=None):
        return _TTSEngine()


@pytest.mark.asyncio
async def test_omlx_stt_adapter_uses_authorized_request_part(tmp_path):
    path = tmp_path / "speech.wav"
    path.write_bytes(_wav_bytes())
    adapter = _STTAdapter(_context(tmp_path, "example.audio/stt"))
    result = await adapter.invoke(
        ModelWorkerRequest(
            operation="audio_transcription",
            request_id="request-1",
            payload={
                "model": "upstream/audio",
                "language": "zh",
                "word_timestamps": "false",
            },
            parts={
                "file": ModelWorkerPart(
                    name="file",
                    path=path,
                    media_type="audio/wav",
                    filename="speech.wav",
                    size=path.stat().st_size,
                    sha256="a" * 64,
                )
            },
        )
    )

    assert result["text"] == "你好"
    assert result["features"]["timestamps"]["status"] == "native"


@pytest.mark.asyncio
async def test_omlx_tts_adapter_returns_wav_metadata(tmp_path):
    adapter = _TTSAdapter(_context(tmp_path, "example.audio/tts"))
    result = await adapter.invoke(
        ModelWorkerRequest(
            operation="audio_speech",
            request_id="request-2",
            payload={
                "model": "upstream/audio",
                "input": "你好",
                "voice": "narrator",
                "response_format": "wav",
            },
        )
    )

    assert isinstance(result, ModelWorkerResponse)
    assert result.media_type == "audio/wav"
    assert result.headers["X-AI2Apps-Audio-Sample-Rate"] == "24000"


@pytest.mark.asyncio
async def test_omlx_tts_adapter_rejects_implicit_reference_audio(tmp_path):
    adapter = _TTSAdapter(_context(tmp_path, "example.audio/tts"))
    with pytest.raises(ModelWorkerError, match="authorized request part"):
        await adapter.invoke(
            ModelWorkerRequest(
                operation="audio_speech",
                request_id="request-3",
                payload={
                    "model": "upstream/audio",
                    "input": "你好",
                    "ref_audio": "base64-is-not-accepted",
                },
            )
        )


@pytest.mark.asyncio
async def test_omlx_stt_adapter_rejects_unimplemented_advanced_feature(tmp_path):
    path = tmp_path / "speech.wav"
    path.write_bytes(_wav_bytes())
    adapter = _STTAdapter(_context(tmp_path, "example.audio/stt"))
    with pytest.raises(ModelWorkerError, match="speaker recognition") as error:
        await adapter.invoke(
            ModelWorkerRequest(
                operation="audio_transcription",
                request_id="request-4",
                payload={
                    "model": "upstream/audio",
                    "speaker_recognition": {
                        "mode": "anonymous_or_match",
                        "candidate_profile_ids": ["vp_alice"],
                    },
                },
                parts={
                    "file": ModelWorkerPart(
                        name="file",
                        path=path,
                        media_type="audio/wav",
                        filename="speech.wav",
                        size=path.stat().st_size,
                        sha256="a" * 64,
                    )
                },
            )
        )
    assert error.value.code == "unsupported_feature"


@pytest.mark.asyncio
async def test_omlx_tts_adapter_maps_emotion_to_native_instructions(tmp_path):
    adapter = _TTSAdapter(_context(tmp_path, "example.audio/tts"))
    result = await adapter.invoke(
        ModelWorkerRequest(
            operation="audio_speech",
            request_id="request-5",
            payload={
                "model": "upstream/audio",
                "input": "你好",
                "voice": "narrator",
                "style": {"emotion": "happy"},
            },
        )
    )
    assert result.headers["X-AI2Apps-Feature-Emotion"] == "native"
    assert adapter._engine.kwargs["instructions"] == "Speak with a happy emotion."


@pytest.mark.asyncio
async def test_omlx_tts_adapter_rejects_unavailable_voice_and_speed(tmp_path):
    adapter = _TTSAdapter(_context(tmp_path, "example.audio/tts"))
    for payload, message in (
        ({"voice": "unknown"}, "Voice is not available"),
        ({"speed": 1.25}, "does not support speed"),
    ):
        with pytest.raises(ModelWorkerError, match=message):
            await adapter.invoke(
                ModelWorkerRequest(
                    operation="audio_speech",
                    request_id="request-6",
                    payload={
                        "model": "upstream/audio",
                        "input": "你好",
                        **payload,
                    },
                )
            )


@pytest.mark.asyncio
async def test_omlx_tts_adapter_authorizes_reference_audio_part(tmp_path):
    context = _context(tmp_path, "example.audio/tts")
    context.models[0]["audio_capabilities"]["tts"]["voice_profiles"] = {
        "mode": "native"
    }
    reference = tmp_path / "reference.wav"
    reference.write_bytes(_wav_bytes())
    adapter = _TTSAdapter(context)
    await adapter.invoke(
        ModelWorkerRequest(
            operation="audio_speech",
            request_id="request-reference",
            payload={
                "model": "upstream/audio",
                "input": "你好",
                "ref_text": "参考文本",
            },
            parts={
                "reference_audio": ModelWorkerPart(
                    name="reference_audio",
                    path=reference,
                    media_type="audio/wav",
                    filename="reference.wav",
                    size=reference.stat().st_size,
                    sha256="b" * 64,
                )
            },
        )
    )
    assert adapter._engine.kwargs["ref_audio"] == str(reference)
    assert adapter._engine.kwargs["ref_text"] == "参考文本"


@pytest.mark.asyncio
async def test_omlx_tts_adapter_maps_multi_speaker_dialogue(tmp_path):
    context = _context(tmp_path, "example.audio/tts")
    tts = context.models[0]["audio_capabilities"]["tts"]
    tts["multi_speaker"] = {"mode": "native"}
    tts["named_voices"]["voices"] = ["alice", "bob"]
    adapter = _TTSAdapter(context)
    await adapter.invoke(
        ModelWorkerRequest(
            operation="audio_speech",
            request_id="request-dialogue",
            payload={
                "model": "upstream/audio",
                "dialogue": [
                    {"voice": "alice", "text": "Hello"},
                    {"voice": "bob", "text": "Hi"},
                ],
            },
        )
    )
    assert adapter._engine.text == ["Hello", "Hi"]
    assert adapter._engine.kwargs["voice"] == ["alice", "bob"]


@pytest.mark.asyncio
async def test_omlx_tts_adapter_requires_voice_design_instructions(tmp_path):
    context = _context(tmp_path, "example.audio/tts")
    context.models[0]["audio_capabilities"]["tts"]["instructions"] = {
        "mode": "native",
        "required": True,
    }
    adapter = _TTSAdapter(context)
    with pytest.raises(ModelWorkerError, match="requires instructions"):
        await adapter.invoke(
            ModelWorkerRequest(
                operation="audio_speech",
                request_id="request-voice-design",
                payload={"model": "upstream/audio", "input": "你好"},
            )
        )
