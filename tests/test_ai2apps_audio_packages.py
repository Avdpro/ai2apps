# SPDX-License-Identifier: Apache-2.0
"""Audio Package protocol fixtures and signed static capability contracts."""

from __future__ import annotations

import io
import wave
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from ai2apps.model_worker.server import create_app
from ai2apps.packages.archive import ServicePackageArchive
from ai2apps.packages.contract_v1 import build_package
from ai2apps.packages.supervisor import ManagedServiceSupervisor

ROOT = Path(__file__).resolve().parents[1]


def _manifest(package: str):
    return yaml.safe_load(
        (ROOT / "packages" / package / "service.yaml").read_text(encoding="utf-8")
    )


def _wav_bytes() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(b"\x00\x00" * 800)
    return output.getvalue()


def _app(tmp_path: Path, package: str):
    package_root = ROOT / "packages" / package
    data_root = tmp_path / package
    data_root.mkdir()
    _, config = ManagedServiceSupervisor._model_worker_command(
        package_root,
        data_root,
        _manifest(package),
        9123,
    )
    return create_app(config, token="audio-worker-secret")


def test_mock_audio_manifests_have_valid_signed_capabilities():
    stt = ServicePackageArchive._manifest(_manifest("mock-audio-stt"))
    tts = ServicePackageArchive._manifest(_manifest("mock-audio-tts"))

    assert stt.models[0]["audio_capabilities"]["operations"] == [
        "audio_transcription"
    ]
    assert tts.models[0]["audio_capabilities"]["tts"]["named_voices"][
        "voices"
    ] == ["mock"]


def test_real_audio_packages_pin_runtime_checkpoint_and_platform_contracts():
    stt = ServicePackageArchive._manifest(_manifest("omlx-model-sensevoice-small"))
    tts = ServicePackageArchive._manifest(_manifest("omlx-model-qwen3-tts-0.6b"))

    assert stt.models[0]["model_type"] == "audio_stt"
    assert stt.models[0]["weights"]["revision"] == (
        "8ddd966bd96243cff196422f81f0c5d955814792"
    )
    assert tts.models[0]["model_type"] == "audio_tts"
    assert tts.models[0]["weights"]["revision"] == (
        "7dc92af14613355896fcab13b268c19ede233139"
    )
    assert "serena" in tts.models[0]["audio_capabilities"]["tts"][
        "named_voices"
    ]["voices"]
    for package in (stt, tts):
        assert package.compatibility["minimum_os_version"] == "26.2"
    assert stt.dependencies[0].version_spec == ">=1.3.1,<2.0.0"
    assert stt.dependencies[1].service_key == "ai2apps.model.punctuation-restorer"
    assert stt.models[0]["metadata"]["punctuation_required"] is True
    assert stt.models[0]["metadata"]["required_model_ids"] == [
        "ai2apps.model.punctuation-restorer/default"
    ]
    assert tts.dependencies[0].version_spec == ">=1.3.0,<2.0.0"
    assert set(stt.models[0]["audio_capabilities"]["formats"]["input"]) == {
        "wav", "pcm", "mp3", "m4a", "aac", "flac", "ogg", "opus", "webm"
    }
    assert set(tts.models[0]["audio_capabilities"]["formats"]["output"]) == {
        "wav", "pcm", "mp3", "m4a", "aac", "flac", "ogg", "opus", "webm"
    }


def test_advanced_audio_packages_pin_real_checkpoints_and_capabilities():
    punctuation = ServicePackageArchive._manifest(
        _manifest("omlx-punctuation-restorer")
    )
    asr = ServicePackageArchive._manifest(_manifest("omlx-model-qwen3-asr-0.6b"))
    tts = ServicePackageArchive._manifest(_manifest("omlx-model-qwen3-tts-1.7b"))
    vibe = ServicePackageArchive._manifest(_manifest("omlx-model-vibevoice-0.5b"))

    assert punctuation.models[0]["metadata"]["internal"] is True
    assert punctuation.models[0]["weights"]["revision"] == (
        "5cccf43af83e4fc50d1d55b8410312e87709be70"
    )
    assert asr.models[0]["audio_capabilities"]["stt"]["punctuation"]["mode"] == "native"
    assert asr.models[0]["weights"]["revision"] == (
        "313d850181767edf09f00a9c289becca70e58cd0"
    )
    variants = {model["metadata"]["variant"]: model for model in tts.models}
    assert set(variants) == {"custom_voice", "base", "voice_design"}
    assert (
        variants["base"]["audio_capabilities"]["tts"]["voice_profiles"]["mode"]
        == "native"
    )
    assert (
        variants["voice_design"]["audio_capabilities"]["tts"]["instructions"]
        ["required"]
        is True
    )
    assert (
        vibe.models[0]["audio_capabilities"]["tts"]["multi_speaker"]["mode"]
        == "native"
    )

    for name in (
        "omlx-punctuation-restorer",
        "omlx-model-qwen3-asr-0.6b",
        "omlx-model-qwen3-tts-1.7b",
        "omlx-model-vibevoice-0.5b",
    ):
        outer = __import__("json").loads(
            (ROOT / "packages" / name / "ai2apps.json").read_text(encoding="utf-8")
        )
        assert outer["dependencies"][0]["packageId"] == "ai2apps/runtime-omlx"


def test_sensevoice_package_retains_model_license_and_attribution(tmp_path):
    package_root = ROOT / "packages" / "omlx-model-sensevoice-small"
    manifest = yaml.safe_load((package_root / "service.yaml").read_text(encoding="utf-8"))
    notice = (package_root / "META" / "NOTICE.md").read_text(encoding="utf-8")
    license_text = (
        package_root
        / "META"
        / "licenses"
        / "FunASR-MODEL-LICENSE-1.1.txt"
    ).read_text(encoding="utf-8")

    assert manifest["license"]["id"] == "LicenseRef-FunASR-Model-1.1"
    assert "SenseVoiceSmall" in notice
    assert "FunAudioLLM / FunASR" in notice
    assert "FunASR Model Open Source License Agreement" in license_text
    assert "必须注明出处以及作者信息" in license_text

    output = tmp_path / "sensevoice.ai2service"
    inspected = build_package(package_root, output)
    assert "FunASR Model License 1.1" in inspected.manifest["package"]["description"]
    indexed = {item.path for item in inspected.files}
    assert "META/NOTICE.md" in indexed
    assert "META/licenses/FunASR-MODEL-LICENSE-1.1.txt" in indexed


def test_runtime_builder_preserves_audio_capabilities():
    builder = (ROOT / "scripts" / "build_omlx_runtime_package.py").read_text(
        encoding="utf-8"
    )
    for capability in (
        "audio-stt",
        "audio-tts",
        "audio-processing",
        "audio-codecs",
    ):
        assert f'"{capability}"' in builder
    assert '"av==18.0.0"' in (ROOT / "pyproject.toml").read_text()
    assert 'variant / "AI2AppsOmlxRuntime.dmg"' in builder


def test_chat_exposes_wav_voice_input_and_package_tts_controls():
    chat = (ROOT / "ai2apps" / "web" / "templates" / "chat.html").read_text(
        encoding="utf-8"
    )

    assert "navigator.mediaDevices.getUserMedia" in chat
    assert "audioInputStarting: false" in chat
    assert "Starting microphone…" in chat
    assert "encodePcmWav" in chat
    assert "'/v1/audio/transcriptions'" in chat
    assert "'/v1/audio/speech'" in chat
    assert "availableAudioModelsByType('audio_stt')" in chat
    assert "availableAudioModelsByType('audio_tts')" in chat
    assert "audioEmotionOptions" in chat
    assert "const settings = pipeline?.speechSettings || this.audioSettings" in chat
    assert "const voice = settings.voice || voices[0] || ''" in chat
    assert "if (voice) payload.voice = voice" in chat
    assert "payload.style = { emotion: settings.emotion }" in chat
    assert "payload.instructions = instructions" in chat
    assert "payload.ref_audio = pipeline.referenceData" in chat
    assert "payload.ref_audio_format = pipeline.referenceFormat" in chat
    assert "Reference transcript is required for voice cloning." in chat
    assert "maybeAutoSpeak(message)" in chat


def test_chat_pipelines_streaming_text_into_ordered_tts_segments():
    chat = (ROOT / "ai2apps" / "web" / "templates" / "chat.html").read_text(
        encoding="utf-8"
    )
    segmenter = (
        ROOT / "ai2apps" / "web" / "static" / "js" / "streaming_tts.js"
    ).read_text(encoding="utf-8")

    assert 'src="/admin/static/js/streaming_tts.js"' in chat
    assert "const speechPipeline = this.beginStreamingAutoSpeak(context, stream);" in chat
    assert "this.appendStreamingSpeech(speechPipeline, deltaText);" in chat
    assert "const streamingSpeechFinished = this.finishSpeechPipeline(speechPipeline);" in chat
    assert "pipeline.synthesisTail" in chat
    assert "pipeline.playbackTail" in chat
    assert "pipeline.prepared >= pipeline.maxPrepared" in chat
    assert "signal: pipeline.controller.signal" in chat
    assert "speechSettings: { ...this.audioSettings }" in chat
    assert "JSON.stringify(this.speechPayload(input, pipeline))" in chat
    assert "this.stopSpeechOutput();" in chat
    assert "class StreamingTextSegmenter" in segmenter
    assert "HARD_BOUNDARY" in segmenter
    assert "flushSoft()" in segmenter
    assert "finish()" in segmenter


def test_mock_stt_accepts_wav_part_and_cleans_it(tmp_path):
    app = _app(tmp_path, "mock-audio-stt")
    with TestClient(app) as client:
        response = client.post(
            "/v1/audio/transcriptions",
            headers={"Authorization": "Bearer audio-worker-secret"},
            data={"model": "ai2apps/mock-audio-stt", "language": "zh"},
            files={"file": ("speech.wav", _wav_bytes(), "audio/wav")},
        )

    assert response.status_code == 200
    assert response.json()["text"] == "AI2Apps mock transcription"
    assert response.json()["input"]["media_type"] == "audio/wav"
    assert not any((tmp_path / "mock-audio-stt" / "requests").iterdir())


def test_mock_tts_returns_playable_wav_and_audio_metadata(tmp_path):
    app = _app(tmp_path, "mock-audio-tts")
    with TestClient(app) as client:
        response = client.post(
            "/v1/audio/speech",
            headers={"Authorization": "Bearer audio-worker-secret"},
            json={
                "model": "ai2apps/mock-audio-tts",
                "input": "你好，AI2Apps",
                "voice": "mock",
                "response_format": "wav",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.headers["x-ai2apps-audio-sample-rate"] == "16000"
    with wave.open(io.BytesIO(response.content), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 16_000
        assert audio.getnframes() > 0
