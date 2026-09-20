import json
import sqlite3
import wave
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from ai2apps.api.video_studio import create_video_studio_router
from ai2apps.config import PLATFORM_DATABASE_SCHEMA_VERSION, PlatformConfig
from ai2apps.gallery import GalleryRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.model_providers import PackageModel
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.migrations import MIGRATIONS, apply_migrations
from ai2apps.video_policy import H3_RATIOS, H3_RESOLUTIONS

WEB_ROOT = Path(__file__).parents[1] / "ai2apps" / "web"


def test_video_studio_uses_first_party_surface_and_async_video_api():
    template = (WEB_ROOT / "templates/system_apps/video_studio.html").read_text()
    script = (WEB_ROOT / "static/js/video_studio.js").read_text()
    stylesheet = (WEB_ROOT / "static/css/video_studio.css").read_text()
    english = json.loads((WEB_ROOT / "i18n/en.json").read_text())
    chinese = json.loads((WEB_ROOT / "i18n/zh.json").read_text())
    provisioning_script = (
        WEB_ROOT / "static/js/capability_provisioning.js"
    ).read_text()

    assert 'data-app-id="ai2apps.video-studio"' in template
    assert 'x-init="init()"' not in template
    assert "data-client-environment" in template
    assert 'class="vs-studio-sidebar"' in template
    assert 'class="vs-mini-app-workspace"' in template
    assert "vs-render-workspace" in template
    assert "video_studio.mini_apps" in template and "Gallery Mini Entry" in template
    assert "video_studio.live.title" in template and "video_studio.animation.title" in template
    assert "vs-mode-tabs" not in template
    assert "selectMiniApp(miniApp.id)" in template
    assert "MINI_APPS" in script and "miniAppDrafts" in script
    assert "saveCurrentMiniAppDraft" in script and "restoreMiniAppDraft" in script
    assert "SHELL_STATE_KEY" in script and "persistShellState" in script
    assert "if (typeof state.modelId === 'string') this.modelId = state.modelId" in script
    assert "leftView: this.leftView, mode: this.mode, modelId: this.modelId" in script
    assert "const restoredModelId = this.modelId" in script
    assert "if (restoredModelId) this.modelId = restoredModelId" in script
    assert "left-collapsed" in template and "right-collapsed" in template
    assert "toggleLeftPanel()" in template and "toggleRightPanel()" in template
    assert ".vs-shell.left-collapsed" in stylesheet
    assert ".vs-run-detail" in stylesheet and "video_studio.current_run" in template
    assert "video_studio.history" in template and "retry(activeTask)" in template
    assert "`${STUDIO_API}/tasks/${encodeURIComponent(task.id)}/retry`" in script
    assert "ai2apps.video.text-to-video" in script
    assert "ai2apps.video.image-to-video" in script
    assert "ai2apps.video.reference-to-video" in script
    assert "ai2apps.video.extract-audio" in script
    assert 'class="vs-mini-app-header studio-mini-header"' in template
    assert "extractAudio()" in template
    assert "activeAudioArtifact" in template
    assert "/resource-handles" in script
    assert "/extract-audio" in script
    assert "mozAI2AppsFullPath" in script
    assert "sourcePath: this.extractAsset.nativePath" in script
    assert "pipeline_id" in script
    assert "mountMiniEntry" in script
    assert "appId: 'ai2apps.gallery'" in script
    assert "GALLERY_MINI_FALLBACK_URL" in script
    assert "AI2Apps Host did not respond|Unsupported host mount" in script
    assert "if (this.leftView === 'assets') this.mountGalleryMini()" in script
    assert "if (force) { this.galleryMiniUrl = ''; this.galleryMiniMountId = ''; }" in script
    assert "application/x-ai2apps-gallery-asset" in script
    assert "application/x-ai2apps-video-artifact" in script
    assert "video_studio.add_gallery" in template
    assert "dragGeneratedVideo" in script
    assert "addActiveVideoToGallery" in script
    assert "galleryActiveCollectionId" in script
    assert "/v1/platform/gallery/assets/import-artifact/" in script
    assert "handleGalleryDrop" in script and "routeDroppedFile" in script
    assert "handleGalleryDrop($event,'first')" in template
    assert "handleGalleryDrop($event,'last')" in template
    assert "@drop.stop.prevent" in template
    assert "gallerySlotTarget" in script
    assert "video_studio.error.image_slot_type" in script
    assert "this.success(`已将“${file.name}”放入" not in script
    assert ".vs-drop.drag-target" in stylesheet
    assert "video_studio.error.gallery_asset_only" in script
    assert "/v1/videos/generations" in script
    assert "/v1/videos/joins" in script
    assert "first_frame" in script and "last_frame" in script
    assert "video_studio.batch_title" in template
    assert "capability_provisioning.js" in template
    assert "AI2AppsCapabilities.ensure" in script
    assert "/capabilities/ensure" in provisioning_script
    assert "/client/restart-local" in provisioning_script
    assert "/acknowledge-return" in provisioning_script
    assert "session.plan?.requirements" not in provisioning_script
    assert "resumeToken: value.resumeToken || null" in provisioning_script
    assert "AI2AppsCapabilities = { ensure, resume, probe, acknowledge, appInstanceId, chooseProfile, runSession, createTransferMeter, formatDownloadProgress }" in provisioning_script
    assert "returnTo: `/apps/${APP_ID}`" in script
    assert "resumed.session?.intent?.draft" not in script
    assert "draft: this.provisioningDraft(action)" not in script
    assert "completionPolicy: 'configure_only'" in script
    assert "persistProvisioningDraft" in script
    assert "loadProvisioningDraft" in script
    assert "action, pipelineId: this.currentMiniApp.id" not in script
    assert "AI2AppsCapabilities.acknowledge" in script
    assert "['video.reference_generation', 'video.generation']" in script
    assert "reference_to_video" in script
    assert "referenceImages" in script and "referenceVideos" in script
    assert "video_studio.mini_app.r2v" in script
    assert "synchronizedAudio: true" in script
    assert "DRAFT_KEY" not in script
    restore_position = script.index("await this.loadProvisioningDraft(resumeToken)")
    acknowledge_position = script.index("await window.AI2AppsCapabilities.acknowledge")
    cleanup_position = script.index("await this.deleteProvisioningDraft(resumeToken)")
    assert restore_position < acknowledge_position < cleanup_position
    assert "modelId: this.modelId" in script
    assert "{ modelId: preferredModelId }" in script
    assert template.count('value="__install_more__"') == 1
    assert 'x-text="tr(\'chat.install_more_models\')"' in template
    assert 'x-show="!modeProviders.length"' in template
    assert "onModelSelect($event.target)" in template
    assert "x-model=\"modelId\"" not in template
    assert "select.value = this.modelId || ''" in script
    assert "this.capabilityRequest('install-more-video-models', '', stored.resumeToken)" in script
    assert "{ installMore: true }" in script
    assert "preserveModelId: originalModelId" in script
    assert "if (requestId !== this.refreshRequestId) return" in script
    assert "model: overrides.model || this.modelId" in script
    assert "AI2AppsCapabilities?.probe" in script
    assert "probe?.plan?.stack?.checkpoint?.model_id" in script
    assert "function preferredProviderId(providers, recommendedId = '')" in script
    assert "recommended?.ready ? recommended : providers.find(item => item.ready)" in script
    assert "preferredProviderId(this.modeProviders, recommendedId)" in script
    assert "item.id === this.modelId && item.ready" in script
    assert "video_studio.configure" in template
    assert "video_studio.submit_setup" in template
    assert "await this.generate()" not in script
    assert "if (capability.configured)" in script
    assert "video_studio.success.configured" in script
    assert 'get canPrimaryAction()' in script
    assert ':disabled="submitting||!canPrimaryAction"' in template
    assert "无可用视频模型" not in template
    assert "providerLabel(provider)" in template
    assert "task.status==='running'" in template
    assert "downloadArtifact($event, activeVideoUrl)" in template
    assert "video_studio.success.download_started" in script
    assert "this.clientEnvironment !== 'desktop'" in script
    assert "resolutionRatio(overrides.resolution || this.resolution)" in script
    assert "--vs-bg" in stylesheet
    assert "{{ t('video_studio.title') }}" in template
    assert "function tr(key, values = {})" in script
    assert "localizedMiniApp" in script
    english_keys = {key for key in english if key.startswith("video_studio.")}
    chinese_keys = {key for key in chinese if key.startswith("video_studio.")}
    assert english_keys == chinese_keys
    assert english["video_studio.mini_app.t2v.name"] == "Text to Video"
    assert chinese["video_studio.mini_app.t2v.name"] == "文生视频"
    assert english["video_studio.mini_app.x2a.name"] == "Extract Audio"
    assert chinese["video_studio.mini_app.x2a.name"] == "提取音轨"


def test_video_studio_extract_audio_run_materializes_wav_artifact(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    config = PlatformConfig.from_base_path(tmp_path / "data")
    principal = RequestPrincipal.legacy_local()
    app_instance_id = "appi_video_studio"

    class ExtensionManager:
        def require_instance_access(self, instance_id, _principal):
            assert instance_id == app_instance_id

        def instance_entry(self, instance_id, *, principal):
            self.require_instance_access(instance_id, principal)
            return {"app_key": "ai2apps.video-studio"}

    class VideoTasks:
        def artifact_session(self):
            return "sess_media"

    captured = {}

    class Workspace:
        def import_artifact(self, session_id, source, name, **kwargs):
            captured["data"] = source.read_bytes()
            captured["metadata"] = kwargs["metadata"]
            return SimpleNamespace(
                id="arti_audio", name=name, media_type=kwargs["media_type"]
            )

    runtime = SimpleNamespace(
        database=database,
        config=config,
        events=None,
        extension_manager=ExtensionManager(),
        video_tasks=VideoTasks(),
        workspace=Workspace(),
    )
    gallery = GalleryRepository(database, config.paths.artifacts_path / "gallery")
    source = BytesIO()
    with wave.open(source, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8_000)
        output.writeframes(b"\0\0" * 800)
    asset, _created = gallery.import_stream(
        principal.actor_user_id,
        BytesIO(source.getvalue()),
        name="interview.mp4",
        media_type="video/mp4",
    )
    reference = gallery.create_asset_handle(
        principal.actor_user_id,
        asset["id"],
        actor_id=principal.actor_user_id,
        installation_id=principal.installation_id,
        app_instance_id=app_instance_id,
        consumer_app_id="ai2apps.video-studio",
    )
    app = FastAPI()
    app.include_router(create_video_studio_router(lambda: runtime, lambda: principal))
    client = TestClient(app)
    headers = {"X-AI2Apps-App-Instance": app_instance_id}

    catalog = client.get("/video-studio/mini-apps").json()
    definition = next(
        item for item in catalog["items"] if item["id"] == "ai2apps.video.extract-audio"
    )
    assert definition["schema"] == "ai2apps.mini-app/v1"
    assert definition["kind"] == "clip"
    assert definition["inputs"][0]["kind"] == "video"
    assert definition["outputs"][0]["kind"] == "audio"

    run = client.post(
        "/video-studio/runs",
        headers=headers,
        json={
            "miniAppId": definition["id"],
            "title": "interview.wav",
            "input": {"assetId": asset["id"], "assetName": asset["name"]},
        },
    ).json()
    started = client.post(
        f"/video-studio/runs/{run['id']}/extract-audio",
        headers=headers,
        json={"resourceHandle": reference["resourceHandle"], "outputName": "interview.wav"},
    )
    assert started.status_code == 202
    completed = client.get(f"/video-studio/runs/{run['id']}", headers=headers).json()
    assert completed["status"] == "succeeded"
    assert completed["steps"][0]["status"] == "succeeded"
    assert completed["artifacts"][0]["kind"] == "audio"
    assert completed["artifacts"][0]["mediaType"] == "audio/wav"
    assert completed["artifacts"][0]["downloadUrl"].endswith(
        "/sessions/sess_media/artifacts/arti_audio/download"
    )
    assert captured["data"].startswith(b"RIFF")
    assert captured["metadata"]["sourceAssetId"] == asset["id"]

    local_source = tmp_path / "local-interview.mp4"
    local_source.write_bytes(source.getvalue())
    local_run = client.post(
        "/video-studio/runs",
        headers=headers,
        json={
            "miniAppId": definition["id"],
            "title": "local-interview.wav",
            "input": {
                "sourceKind": "local",
                "assetName": local_source.name,
                "mediaType": "video/mp4",
            },
        },
    ).json()
    local_started = client.post(
        f"/video-studio/runs/{local_run['id']}/extract-audio",
        headers=headers,
        json={
            "sourcePath": str(local_source),
            "sourceName": local_source.name,
            "mediaType": "video/mp4",
            "outputName": "local-interview.wav",
        },
    )
    assert local_started.status_code == 202
    local_completed = client.get(
        f"/video-studio/runs/{local_run['id']}", headers=headers
    ).json()
    assert local_completed["status"] == "succeeded"
    assert captured["metadata"]["sourceKind"] == "local"
    assert "sourceAssetId" not in captured["metadata"]
    assert str(local_source) not in json.dumps(local_completed)

    invalid_run = client.post(
        "/video-studio/runs",
        headers=headers,
        json={
            "miniAppId": definition["id"],
            "title": "invalid.wav",
            "input": {"sourceKind": "local", "assetName": "missing.mp4"},
        },
    ).json()
    invalid = client.post(
        f"/video-studio/runs/{invalid_run['id']}/extract-audio",
        headers=headers,
        json={"sourcePath": "relative.mp4", "mediaType": "video/mp4"},
    )
    assert invalid.status_code == 422


def test_video_studio_draft_api_persists_private_form_and_keyframe(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    config = PlatformConfig.from_base_path(tmp_path / "data")
    app_instance_id = "appi_video_studio"

    class ExtensionManager:
        def require_instance_access(self, instance_id, _principal):
            assert instance_id == app_instance_id

        def instance_entry(self, instance_id, *, principal):
            self.require_instance_access(instance_id, principal)
            return {"app_key": "ai2apps.video-studio"}

    class VideoTasks:
        async def retry(self, task_id, *, actor_id):
            assert task_id == "vgt_failed"
            assert actor_id == RequestPrincipal.legacy_local().actor_user_id
            return {"id": "vgt_retried", "status": "queued"}

    runtime = SimpleNamespace(
        database=database,
        config=config,
        extension_manager=ExtensionManager(),
        video_tasks=VideoTasks(),
    )
    app = FastAPI()
    app.include_router(
        create_video_studio_router(lambda: runtime, RequestPrincipal.legacy_local)
    )
    client = TestClient(app)
    image = BytesIO()
    Image.new("RGB", (2, 2), "red").save(image, format="PNG")
    draft = {
        "action": "configure-generation",
        "mode": "i2v",
        "modelId": "ai2apps.model.minimax-h3/fl2va-8bit",
        "prompt": "private cat prompt",
        "resolution": "512x512",
        "duration": 5,
        "preset": "strict",
        "steps": 20,
        "seed": 42,
        "label": "shot one",
        "batchText": "",
    }
    headers = {"X-AI2Apps-App-Instance": app_instance_id}

    created = client.post(
        "/video-studio/drafts",
        headers=headers,
        files={
            "draft": (None, json.dumps(draft), "application/json"),
            "first_frame": ("cat.png", image.getvalue(), "image/png"),
        },
    )

    assert created.status_code == 201
    token = created.json()["resumeToken"]
    assert token.startswith("vsd_") and "cat" not in token
    restored = client.get(f"/video-studio/drafts/{token}", headers=headers)
    assert restored.json()["draft"]["prompt"] == "private cat prompt"
    assert restored.json()["frames"]["first"]["mediaType"] == "image/png"
    frame = client.get(
        f"/video-studio/drafts/{token}/frames/first", headers=headers
    )
    assert frame.status_code == 200 and frame.content == image.getvalue()
    assert client.delete(f"/video-studio/drafts/{token}", headers=headers).status_code == 204
    assert client.get(f"/video-studio/drafts/{token}", headers=headers).status_code == 404
    retried = client.post("/video-studio/tasks/vgt_failed/retry", headers=headers)
    assert retried.status_code == 202
    assert retried.json() == {"id": "vgt_retried", "status": "queued"}


def test_schema_v44_upgrades_to_private_video_studio_drafts(tmp_path):
    path = tmp_path / "platform.sqlite3"
    with sqlite3.connect(path) as connection:
        assert apply_migrations(connection, MIGRATIONS[:44]) == 44

    state = PlatformDatabase(path).initialize()

    assert state.schema_version == PLATFORM_DATABASE_SCHEMA_VERSION
    with sqlite3.connect(path) as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='video_studio_drafts'"
        ).fetchone()
    assert table == ("video_studio_drafts",)


def test_video_studio_provider_catalog_exposes_signed_video_capabilities(monkeypatch):
    caps = {
        "schema": "ai2apps.video-capabilities/v1",
        "geometry": {"resolutions": ["512x512"]},
        "presets": [{"id": "strict"}],
    }
    model = PackageModel(
        id="ai2apps.model.h3/4bit",
        display_name="H3 4-bit",
        model_type="video_generation",
        upstream_id="H3",
        capabilities=("video_generation",),
        endpoints={},
        context_window=None,
        metadata={"family": "minimax-h3", "precision": "q4", "residency": "staged"},
        audio_capabilities=None,
        image_capabilities=None,
        video_capabilities=caps,
        service_key="h3",
        provider_key="h3",
        endpoint="http://127.0.0.1:1",
        checkpoint_ready=True,
    )
    monkeypatch.setattr(
        "ai2apps.api.video_studio.list_package_models", lambda runtime: (model,)
    )
    app = FastAPI()
    app.include_router(
        create_video_studio_router(
            lambda: SimpleNamespace(), lambda: RequestPrincipal.legacy_local()
        )
    )
    payload = TestClient(app).get("/video-studio/providers").json()

    effective_caps = payload["items"][0]["videoCapabilities"]
    assert effective_caps["schema"] == caps["schema"]
    assert effective_caps["presets"] == caps["presets"]
    assert effective_caps["geometry"]["resolutions"] == list(H3_RESOLUTIONS)
    assert effective_caps["geometry"]["ratios"] == list(H3_RATIOS)
    assert payload["items"][0]["precision"] == "q4"
    assert payload["items"][0]["ready"] is True


def test_video_studio_provider_catalog_hides_h3_bf16(monkeypatch):
    bf16 = PackageModel(
        id="ai2apps.model.minimax-h3/fl2va-bf16",
        display_name="H3 BF16",
        model_type="video_generation",
        upstream_id="H3",
        capabilities=("video_generation",),
        endpoints={},
        context_window=None,
        metadata={"family": "minimax-h3", "precision": "bf16"},
        audio_capabilities=None,
        image_capabilities=None,
        video_capabilities={},
        service_key="h3",
        provider_key="h3",
        endpoint="http://127.0.0.1:1",
        checkpoint_ready=True,
    )
    monkeypatch.setattr(
        "ai2apps.api.video_studio.list_package_models", lambda runtime: (bf16,)
    )
    app = FastAPI()
    app.include_router(
        create_video_studio_router(
            lambda: SimpleNamespace(), lambda: RequestPrincipal.legacy_local()
        )
    )

    assert TestClient(app).get("/video-studio/providers").json() == {"items": []}
