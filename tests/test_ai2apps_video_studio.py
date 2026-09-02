import json
import sqlite3
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from ai2apps.api.video_studio import create_video_studio_router
from ai2apps.config import PLATFORM_DATABASE_SCHEMA_VERSION, PlatformConfig
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
    assert "data-client-environment" in template
    assert 'class="vs-studio-sidebar"' in template
    assert 'class="vs-pipeline-workspace"' in template
    assert "vs-render-workspace" in template
    assert "Pipeline" in template and "Gallery Mini Entry" in template
    assert "video_studio.live.title" in template and "video_studio.animation.title" in template
    assert "vs-mode-tabs" not in template
    assert "selectPipeline(pipeline.id)" in template
    assert "ai2apps.video.text-to-video" in script
    assert "ai2apps.video.image-to-video" in script
    assert "ai2apps.video.reference-to-video" in script
    assert "pipeline_id" in script
    assert "mountMiniEntry" in script
    assert "appId: 'ai2apps.gallery'" in script
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
    assert "AI2AppsCapabilities = { ensure, resume, probe, acknowledge, appInstanceId }" in provisioning_script
    assert "returnTo: `/apps/${APP_ID}`" in script
    assert "resumed.session?.intent?.draft" not in script
    assert "draft: this.provisioningDraft(action)" not in script
    assert "completionPolicy: 'configure_only'" in script
    assert "persistProvisioningDraft" in script
    assert "loadProvisioningDraft" in script
    assert "AI2AppsCapabilities.acknowledge" in script
    assert "['video.reference_generation', 'video.generation']" in script
    assert "reference_to_video" in script
    assert "referenceImages" in script and "referenceVideos" in script
    assert "video_studio.pipeline.r2v" in script
    assert "synchronizedAudio: true" in script
    assert "DRAFT_KEY" not in script
    restore_position = script.index("await this.loadProvisioningDraft(resumeToken)")
    acknowledge_position = script.index("await window.AI2AppsCapabilities.acknowledge")
    cleanup_position = script.index("await this.deleteProvisioningDraft(resumeToken)")
    assert restore_position < acknowledge_position < cleanup_position
    assert "modelId: this.modelId" in script
    assert "{ modelId: preferredModelId }" in script
    assert "AI2AppsCapabilities?.probe" in script
    assert "probe?.plan?.stack?.checkpoint?.model_id" in script
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
    assert "localizedPipeline" in script
    english_keys = {key for key in english if key.startswith("video_studio.")}
    chinese_keys = {key for key in chinese if key.startswith("video_studio.")}
    assert english_keys == chinese_keys
    assert english["video_studio.pipeline.t2v.name"] == "Text to Video"
    assert chinese["video_studio.pipeline.t2v.name"] == "文生视频"


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

    runtime = SimpleNamespace(
        database=database,
        config=config,
        extension_manager=ExtensionManager(),
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
