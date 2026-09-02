# SPDX-License-Identifier: Apache-2.0
"""Audio Package protocol fixtures and signed static capability contracts."""

from __future__ import annotations

import io
import json
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
        variants["base"]["audio_capabilities"]["tts"]["voice_profiles"]
        ["reference_transcript"]
        == "optional"
    )
    assert (
        variants["voice_design"]["audio_capabilities"]["tts"]["instructions"]
        ["required"]
        is True
    )
    assert (
        vibe.models[0]["audio_capabilities"]["tts"]["multi_speaker"]["mode"]
        == "unsupported"
    )
    assert vibe.models[0]["metadata"]["multi_speaker"] is False
    assert (
        vibe.models[0]["audio_capabilities"]["tts"]["long_form"]
        ["max_duration_minutes"]
        == 10
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


def test_fish_and_cosyvoice_packages_use_native_mlx_runtime_contracts():
    fish = ServicePackageArchive._manifest(
        _manifest("omlx-model-fish-s2-pro")
    )
    cosy = ServicePackageArchive._manifest(
        _manifest("omlx-model-cosyvoice3-0.5b")
    )

    assert fish.raw["runtime"]["provider"] == "ai2apps.runtime.omlx"
    assert fish.dependencies[0].version_spec == ">=1.3.9,<2.0.0"
    assert fish.models[0]["weights"]["revision"] == (
        "eccd57bf5c1ebc13cb2f993df867f4e49931a36a"
    )
    assert fish.raw["version"] == "0.1.1"
    assert fish.models[0]["weights"]["distribution_id"] == (
        "dist_ai2apps_fish_s2_pro_bf16_eccd57bf_v1"
    )
    assert fish.models[0]["audio_capabilities"]["tts"]["multi_speaker"] == {
        "mode": "native",
        "maximum_speakers": 5,
        "control": "inline_speaker_tags",
    }
    assert fish.models[0]["metadata"]["commercial_license_required"] is True

    assert cosy.raw["runtime"]["provider"] == "ai2apps.runtime.omlx"
    assert cosy.dependencies[0].version_spec == ">=1.3.9,<2.0.0"
    public_cosy_models = [
        model for model in cosy.models if not model["metadata"].get("internal")
    ]
    assert {model["metadata"]["variant"] for model in public_cosy_models} == {
        "0.5b-2512-4bit",
        "0.5b-2512-8bit",
    }
    assert all(
        model["audio_capabilities"]["tts"]["voice_profiles"]["mode"]
        == "native"
        for model in public_cosy_models
    )
    tokenizer = next(
        model for model in cosy.models if model["metadata"].get("internal")
    )
    assert tokenizer["id"] == "ai2apps.model.cosyvoice3-0.5b/s3tokenizer-v3"
    assert tokenizer["weights"]["revision"] == (
        "b143914b3e912278104824da706edc9c2d317c4e"
    )
    assert all(
        model["metadata"]["required_model_ids"] == [tokenizer["id"]]
        for model in public_cosy_models
    )

    fish_license = (
        ROOT
        / "packages/omlx-model-fish-s2-pro/META/licenses/Fish-Audio-Research-License.md"
    ).read_text(encoding="utf-8")
    fish_notice = (
        ROOT / "packages/omlx-model-fish-s2-pro/META/NOTICE.md"
    ).read_text(encoding="utf-8")
    assert "requires a separate written license" in fish_license
    assert "Built with Fish Audio" in fish_notice


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
    runtime_manifest = (ROOT / "packages/ai2apps-runtime-omlx/service.yaml").read_text(
        encoding="utf-8"
    )
    for capability in (
        "audio-stt",
        "audio-tts",
        "audio-processing",
        "audio-codecs",
        "fish-s2",
        "cosyvoice3",
    ):
        assert f"  - {capability}" in runtime_manifest
    assert 'list(manifest.get("capabilities", []))' in builder
    assert '"av==18.0.0"' in (ROOT / "pyproject.toml").read_text()
    assert '"AI2AppsOmlxRuntime.dmg"' in builder


def test_standard_runtime_builder_supports_release_signed_knowledge_runtime():
    package_builder = (
        ROOT / "scripts" / "build_omlx_runtime_package.py"
    ).read_text(encoding="utf-8")
    dmg_builder = (ROOT / "scripts" / "build_omlx_runtime_dmg.py").read_text(
        encoding="utf-8"
    )

    assert "create_knowledge_bundle" in package_builder
    assert '"ai2apps.runtime.knowledge-rag"' in package_builder
    assert '"AI2AppsKnowledgeRagRuntime.dmg"' in package_builder
    assert 'choices=("omlx", "knowledge-rag")' in dmg_builder
    assert "_signing_image_size_kib" in dmg_builder
    assert "512 * 1024" in dmg_builder
    assert 'package_slug = "knowledge-rag" if knowledge_runtime else "omlx"' in (
        package_builder
    )
    assert 'f"ai2apps-runtime-{package_slug}-{version}.ai2service"' in package_builder
    assert 'running `hdiutil verify` on that signed' in package_builder.lower()
    contract_manifest = json.loads(
        (
            ROOT
            / "packages/ai2apps-runtime-knowledge-rag/ai2apps.json"
        ).read_text(encoding="utf-8")
    )
    assert contract_manifest["package"] == {
        "id": "ai2apps/runtime-knowledge-rag",
        "type": "service",
        "version": "0.1.1",
        "displayName": "AI2Apps Knowledge RAG Runtime",
        "description": (
            "Official on-demand native Runtime for LanceDB and local MLX text "
            "embeddings."
        ),
    }


def test_runtime_build_overlays_only_cosyvoice_backend_modules():
    build = (ROOT / "packaging" / "build.py").read_text(encoding="utf-8")
    assert '_MLX_AUDIO_PLUS_VERSION = "0.1.8"' in build
    assert (
        '_MLX_AUDIO_PLUS_WHEEL_SHA256 = '
        '"2e44ad5a65d46391db59b694ad4b9e9b1a739ea79c1e6013ad8f7db5cea9472b"'
        in build
    )
    assert '"mlx_audio/tts/models/cosyvoice3/"' in build
    assert '"mlx_audio/tts/models/cosyvoice2/speaker_encoder.py"' in build
    assert '"mlx_audio/codec/models/s3gen/"' in build
    assert '"mlx_audio/codec/models/s3tokenizer/"' in build
    assert "wheel.extractall(fw_site, members=members)" in build


def test_chat_exposes_wav_voice_input_and_package_tts_controls():
    chat = (ROOT / "ai2apps" / "web" / "templates" / "chat.html").read_text(
        encoding="utf-8"
    )

    assert "navigator.mediaDevices.getUserMedia" in chat
    assert "audioInputStarting: false" in chat
    assert "Starting microphone…" in chat
    assert ':aria-busy="audioInputStarting || audioInputBusy"' in chat
    assert 'x-show="audioInputStarting || audioInputBusy"' in chat
    assert "border-t-transparent animate-spin" in chat
    assert "encodePcmWav" in chat
    assert "'/v1/audio/transcriptions'" in chat
    assert "'/v1/audio/speech'" in chat
    assert "availableAudioModelsByType('audio_stt')" in chat
    assert "availableAudioModelsByType('audio_tts')" in chat
    assert 'x-show="availableAudioModels.length > 0"' in chat
    assert 'x-model="audioSettings.sttModel"' in chat
    assert 'x-model="audioSettings.ttsModel"' in chat
    assert 'x-model="audioSettings.voice"' in chat
    assert "voiceSettingsExpanded: false" in chat
    assert 'x-show="voiceSettingsExpanded" x-collapse' in chat
    assert 'x-model.number="audioSettings.speed"' in chat
    assert 'x-model="audioSettings.emotion"' in chat
    assert "voice_speed_unavailable_tooltip" in chat
    assert "voice_emotion_unavailable_tooltip" in chat
    assert "isQwen3Tts" in chat
    assert 'x-model="audioSettings.instructions"' in chat
    assert 'x-model="audioSettings.referenceText"' in chat
    assert 'x-model="audioSettings.autoSpeak"' in chat
    assert "audioVoiceCatalog: {}" in chat
    assert "loadAudioVoices" in chat
    assert '<button x-show="availableAudioModelsByType(\'audio_stt\')' not in chat
    assert '<button x-show="availableAudioModelsByType(\'audio_tts\')' not in chat
    assert "chat.install_stt_tooltip" in chat
    assert "chat.install_tts_tooltip" in chat
    assert '@click="requestSpeechRecognition()"' in chat
    assert '@click="requestSpeechSynthesis(msg)"' in chat
    assert ':aria-disabled="availableAudioModelsByType(\'audio_stt\').length === 0"' not in chat
    assert ':aria-disabled="availableAudioModelsByType(\'audio_tts\').length === 0"' not in chat
    assert "opacity-40 cursor-not-allowed' : ''" not in chat
    assert "chat-hover-tip chat-hover-tip-top" in chat
    assert "chat-hover-tip-align-left" in chat
    assert "chat-hover-tip-align-right" in chat
    assert "chat.voice_input_streaming_tooltip" in chat
    assert "chat.voice_input_starting_tooltip" in chat
    assert "chat.voice_input_busy_tooltip" in chat
    assert "chat.tts_busy_tooltip" in chat
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
