from __future__ import annotations

from pathlib import Path

import yaml

from ai2apps.extensions.archive import InteractiveArchive
from ai2apps.extensions.models import UnitKind
from ai2apps.packages.contract_v1 import build_package, inspect_package

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages" / "ai2apps-media-voice-studio-suite"


def _app_manifest() -> dict:
    return yaml.safe_load((SOURCE / "app.yaml").read_text(encoding="utf-8"))


def test_media_voice_suite_builds_as_one_contract_package_with_six_mini_apps(tmp_path):
    artifact = tmp_path / "media-voice-studio-suite.ai2app"
    built = build_package(SOURCE, artifact)
    inspected = inspect_package(artifact)

    assert built.sha256 == inspected.sha256
    assert inspected.manifest["package"]["id"] == "ai2apps/media-voice-studio-suite"
    assert inspected.manifest["package"]["type"] == "app"
    assert inspected.manifest["package"]["version"] == "0.2.0"
    assert len(inspected.manifest["miniApps"]) == 6
    assert {item["componentId"] for item in inspected.manifest["miniApps"]} == {
        "ai2apps.media-voice.transcription",
        "ai2apps.media-voice.source-separation",
        "ai2apps.media-voice.audio-speaker-replacement",
        "ai2apps.media-voice.video-subtitles",
        "ai2apps.media-voice.video-audio-translation",
        "ai2apps.media-voice.video-speaker-replacement",
    }
    catalog = {
        item["componentId"]: item for item in inspected.manifest["miniApps"]
    }
    assert catalog["ai2apps.media-voice.transcription"]["categories"] == [
        "audio",
        "video",
    ]
    indexed = {item.path for item in inspected.files}
    assert {
        "app.yaml",
        "web/index.html",
        "web/transcription.html",
        "web/separation.html",
        "web/audio-voice-replacement.html",
        "web/video-subtitles.html",
        "web/video-audio-translation.html",
        "web/video-voice-replacement.html",
        "web/mini-app.css",
        "web/mini-app.js",
    }.issubset(indexed)


def test_media_voice_suite_legacy_cloud_build_keeps_signed_app_definition(tmp_path):
    artifact = tmp_path / "media-voice-studio-suite.ai2app"
    inspected = build_package(
        SOURCE,
        artifact,
        include_mini_app_catalog=False,
    )

    assert "miniApps" not in inspected.manifest
    assert any(item.path == "app.yaml" for item in inspected.files)


def test_media_voice_suite_app_manifest_passes_installed_app_validation():
    files = {
        path.relative_to(SOURCE).as_posix()
        for path in SOURCE.rglob("*")
        if path.is_file() and path.name != "ai2apps.json"
    }
    InteractiveArchive._validate_manifest(UnitKind.APP, _app_manifest(), files)


def test_media_voice_suite_uses_lazy_capability_dependencies():
    manifest = _app_manifest()
    mini_apps = {item["id"]: item for item in manifest["mini_apps"]}

    assert manifest["instances"] == {"mode": "singleton", "scope": "user"}
    assert manifest["navigation"]["launcher"] is False
    assert mini_apps["ai2apps.media-voice.transcription"]["requirements"][
        "capabilities"
    ] == ["audio.detailed_transcription", "audio.speaker_diarization"]
    assert mini_apps["ai2apps.media-voice.source-separation"]["requirements"][
        "capabilities"
    ] == ["audio.source_separation"]
    assert "audio.voice_conversion" in mini_apps[
        "ai2apps.media-voice.audio-speaker-replacement"
    ]["requirements"]["capabilities"]
    assert "audio.speaker_voice_replacement" in mini_apps[
        "ai2apps.media-voice.audio-speaker-replacement"
    ]["requirements"]["capabilities"]
    assert "media.video.subtitle_burn_in" in mini_apps[
        "ai2apps.media-voice.video-subtitles"
    ]["requirements"]["capabilities"]
    assert "media.video_subtitles" in mini_apps[
        "ai2apps.media-voice.video-subtitles"
    ]["requirements"]["capabilities"]
    assert "media.video.audio_mux" in mini_apps[
        "ai2apps.media-voice.video-speaker-replacement"
    ]["requirements"]["capabilities"]
    dubbing = mini_apps["ai2apps.media-voice.video-audio-translation"]
    assert dubbing["requirements"]["capabilities"][0] == "media.video_audio_translation"
    assert "audio.speech_generation" in dubbing["requirements"]["capabilities"]
    assert {"capability": "audio.voice_clone", "optional": True} in dubbing[
        "requirements"
    ]["capabilities"]
    assert "audio.speaker_diarization" not in dubbing["requirements"]["capabilities"]
    assert "media.video_speaker_voice_replacement" in mini_apps[
        "ai2apps.media-voice.video-speaker-replacement"
    ]["requirements"]["capabilities"]

    package_manifest = (SOURCE / "ai2apps.json").read_text(encoding="utf-8")
    assert '"dependencies": []' in package_manifest


def test_every_media_voice_mini_app_has_a_distinct_mounted_ui_and_help():
    for mini_app in _app_manifest()["mini_apps"]:
        resource = SOURCE / mini_app["entry"]["resource"]
        help_resource = SOURCE / mini_app["chat"]["help"]["resource"]
        assert resource.is_file()
        assert help_resource.is_file()
        assert mini_app["entry"]["kind"] == "sandbox"
        assert mini_app["chat"]["tools"] == []
        assert "当前 MVP" in help_resource.read_text(encoding="utf-8")


def test_executable_uis_use_the_mount_bound_capability_route():
    client = (SOURCE / "web/mini-app.js").read_text(encoding="utf-8")

    assert "mount_id" in client
    assert "studio_id" in client
    assert "audio.detailed_transcription" in client
    assert "audio.source_separation" in client
    assert "capabilities/${encodeURIComponent(capability)}/invoke" in client
    assert "开始本地转写" in client
    assert "开始本地分离" in client
    assert "开始生成字幕" in client
    assert "开始翻译并配音" in client
    assert "characters.list" in client
    assert "voice-clone-models.list" in client
    assert "原始音色" in client
    assert "安装更多模型" in client
    assert "voice_profile_id" in client
    assert "voice_clone_model_id" in client
    assert "asr_verification" in client
    assert "ASR 回听校验" in client
    assert "audio.detailed_transcription'" in client
    assert "subtitleFontSize" in client
    assert "subtitleBackground" in client
    assert "subtitle_font_size" in client
    assert "subtitle_background" in client
    assert "白字 + 黑色粗描边" in client
    assert "白字 + 半透明黑框" in client
    assert "先识别录音角色" in client
    assert "先识别视频角色" in client
    assert "ai2apps.model.detailed-transcription-mlx" not in client
    assert "ai2apps.model.demucs-mlx" not in client
    assert "checkpoint_path" not in client.casefold()
    assert "'/v1/audio" not in client


def test_media_voice_suite_uses_the_studio_native_visual_contract():
    styles = (SOURCE / "web/mini-app.css").read_text(encoding="utf-8")
    client = (SOURCE / "web/mini-app.js").read_text(encoding="utf-8")
    host_styles = (
        ROOT / "ai2apps/web/static/css/studio_mini_apps.css"
    ).read_text(encoding="utf-8")

    assert "Studio-native surface" in styles
    assert "color-scheme: light" in styles
    assert ".capability-disclosure" in styles
    assert ".panel { margin: 0; padding: 22px 0; border: 0; border-top:" in styles
    assert "background: #1c1917" in styles
    assert "capabilityDisclosure" in client
    assert "所需能力 ·" in client
    assert "notice.classList.toggle('ready'" in client
    assert "new ResizeObserver(reportHostHeight).observe(root)" in client
    assert "'ai2apps:mini-app-resize', version: 1, height" in client
    assert "package-active>.ra-pipeline-header" in host_styles
    assert "package-active>.vs-pipeline-header" in host_styles
    assert "flex-direction:column" in host_styles

    for mini_app in _app_manifest()["mini_apps"]:
        resource = (SOURCE / mini_app["entry"]["resource"]).read_text(
            encoding="utf-8"
        )
        assert "mini-app.css?v=original-voice-v7" in resource
        assert "mini-app.js?v=original-voice-v7" in resource
    assert "progress?.phasePercent ?? progress?.percent" in client

    for template_name in ("readaloud.html", "video_studio.html", "imagine_studio.html"):
        template = (
            ROOT / "ai2apps/web/templates/system_apps" / template_name
        ).read_text(encoding="utf-8")
        assert "studio_mini_apps.css') }}?v=studio-native-v2" in template

    readaloud = (
        ROOT / "ai2apps/web/templates/system_apps/readaloud.html"
    ).read_text(encoding="utf-8")
    imagine = (
        ROOT / "ai2apps/web/templates/system_apps/imagine_studio.html"
    ).read_text(encoding="utf-8")
    assert readaloud.index('class="ra-pipeline-header studio-mini-header"') < readaloud.index(
        'class="ra-package-mini-app"'
    )
    assert imagine.index('class="vs-pipeline-header studio-mini-header"') < imagine.index(
        'class="is-package-mini-app"'
    )
