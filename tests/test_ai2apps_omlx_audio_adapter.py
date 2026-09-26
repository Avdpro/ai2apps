# SPDX-License-Identifier: Apache-2.0
"""Reusable oMLX audio adapter contract tests without Metal."""

from __future__ import annotations

import io
import importlib.util
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


def _context_with_tts_dependency(tmp_path: Path) -> ModelWorkerContext:
    context = _context(tmp_path, "example.audio/tts")
    dependency = tmp_path / "s3tokenizer"
    dependency.mkdir()
    model = dict(context.models[0])
    model["metadata"] = {
        "required_model_ids": ["example.audio/s3tokenizer-v3"]
    }
    return ModelWorkerContext(
        service_id=context.service_id,
        package_root=context.package_root,
        data_root=context.data_root,
        models=(model,),
        checkpoints=context.checkpoints
        + (
            ModelWorkerCheckpoint(
                model_id="example.audio/s3tokenizer-v3",
                upstream_id="mlx-community/S3TokenizerV3",
                provider="huggingface",
                repo_id="mlx-community/S3TokenizerV3",
                revision="b" * 40,
                path=dependency,
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
    def __init__(self):
        self.kwargs = None

    async def start(self):
        return None

    async def stop(self):
        return None

    async def transcribe(self, path, **kwargs):
        assert Path(path).is_file()
        self.kwargs = kwargs
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


class _StructuredTTSAdapter(_TTSAdapter):
    def synthesis_options(
        self, model_id, body, *, speed, emotion, emotion_strength, instructions
    ):
        return {
            "speed": 1.0,
            "duration_factor": 1.0 / speed,
            "emotion_vector": [0.8, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            if emotion == "happy"
            else None,
            "language": "ZH",
            "instructions": instructions,
        }


def test_omlx_tts_adapter_resolves_only_declared_dependency_paths(tmp_path):
    context = _context_with_tts_dependency(tmp_path)
    adapter = OmlxTTSAdapter(context)
    assert adapter.dependency_checkpoint_paths(context.checkpoints[0]) == {
        "mlx-community/S3TokenizerV3": str(context.checkpoints[1].path)
    }


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
    assert "max_tokens" not in adapter._engine.kwargs


@pytest.mark.asyncio
async def test_omlx_stt_adapter_forwards_explicit_max_tokens(tmp_path):
    path = tmp_path / "speech.wav"
    path.write_bytes(_wav_bytes())
    adapter = _STTAdapter(_context(tmp_path, "example.audio/stt"))

    await adapter.invoke(
        ModelWorkerRequest(
            operation="audio_transcription",
            request_id="request-max-tokens",
            payload={"model": "upstream/audio", "max_tokens": "4096"},
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

    assert adapter._engine.kwargs["max_tokens"] == 4096


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
async def test_omlx_tts_adapter_allows_package_structured_controls(tmp_path):
    context = _context(tmp_path, "example.audio/tts")
    context.models[0]["audio_capabilities"]["tts"]["speed"] = {
        "mode": "native",
        "minimum": 0.5,
        "maximum": 2.0,
    }
    context.models[0]["audio_capabilities"]["tts"]["instructions"] = {
        "mode": "unsupported"
    }
    adapter = _StructuredTTSAdapter(context)

    await adapter.invoke(
        ModelWorkerRequest(
            operation="audio_speech",
            request_id="request-structured-controls",
            payload={
                "model": "upstream/audio",
                "input": "你好",
                "speed": 1.25,
                "style": {"emotion": "happy"},
            },
        )
    )

    assert adapter._engine.kwargs["speed"] == 1.0
    assert adapter._engine.kwargs["duration_factor"] == pytest.approx(0.8)
    assert adapter._engine.kwargs["emotion_vector"] == [
        0.8,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ]
    assert adapter._engine.kwargs["instructions"] is None


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
async def test_omlx_tts_adapter_allows_optional_reference_transcript(tmp_path):
    context = _context(tmp_path, "example.audio/tts")
    context.models[0]["audio_capabilities"]["tts"]["voice_profiles"] = {
        "mode": "native",
        "reference_audio": True,
        "reference_transcript": "optional",
    }
    reference = tmp_path / "reference.wav"
    reference.write_bytes(_wav_bytes())
    adapter = _TTSAdapter(context)
    await adapter.invoke(
        ModelWorkerRequest(
            operation="audio_speech",
            request_id="request-reference-no-transcript",
            payload={"model": "upstream/audio", "input": "你好"},
            parts={
                "reference_audio": ModelWorkerPart(
                    name="reference_audio",
                    path=reference,
                    media_type="audio/wav",
                    filename="reference.wav",
                    size=reference.stat().st_size,
                    sha256="c" * 64,
                )
            },
        )
    )
    assert adapter._engine.kwargs["ref_audio"] == str(reference)
    assert adapter._engine.kwargs["ref_text"] is None


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


def test_voxcpm2_package_adapter_combines_controls_with_standard_priority():
    path = (
        Path(__file__).resolve().parents[1]
        / "packages/omlx-model-voxcpm2/src/worker_adapter.py"
    )
    spec = importlib.util.spec_from_file_location("voxcpm2_worker_adapter", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    adapter = module.VoxCPM2Adapter.__new__(module.VoxCPM2Adapter)

    options = adapter.synthesis_options(
        "ai2apps.model.voxcpm2/4bit",
        {"language": "zh"},
        speed=1.25,
        emotion="happy",
        emotion_strength=1.0,
        instructions="Speak slowly and sadly.",
    )

    assert options["speed"] == 1.0
    assert options["language"] == "zh"
    assert options["instructions"].startswith("Speak slowly and sadly.")
    assert options["instructions"].endswith(
        "Mandatory delivery controls override conflicting earlier style: "
        "sound genuinely happy and warm; speak faster than normal."
    )
