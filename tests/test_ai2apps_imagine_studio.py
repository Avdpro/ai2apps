import base64
import json
import sqlite3
import subprocess
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from ai2apps.api.imagine_studio import create_imagine_studio_router
from ai2apps.apps import SYSTEM_APP_MANIFESTS
from ai2apps.config import PlatformConfig
from ai2apps.gallery import GalleryRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.provisioning.profiles import CapabilityProfileRegistry
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.migrations import MIGRATIONS, apply_migrations
from omlx.admin import routes as admin_routes

WEB_ROOT = Path(__file__).parents[1] / "ai2apps" / "web"


def test_imagine_studio_is_registered_as_a_first_party_user_app():
    manifest = next(
        item for item in SYSTEM_APP_MANIFESTS if item["id"] == "ai2apps.imagine-studio"
    )

    assert manifest["name"] == "Imagine Studio"
    assert manifest["instances"] == {"mode": "singleton", "scope": "user"}
    assert manifest["entry"]["resource"] == "ai2apps:system/imagine-studio"
    assert manifest["navigation"]["icon"] == "palette"
    assert manifest["navigation"]["pinned_default"] is True
    assert manifest["localizations"]["zh"]["name"] == "创意画坊"
    assert admin_routes._DASHBOARD_APP_TABS[manifest["id"]] == "imagine-studio"
    assert admin_routes._DASHBOARD_APP_TEMPLATES[manifest["id"]] == "system_apps/imagine_studio.html"
    assert admin_routes._HOST_APP_ENTRIES[manifest["entry"]["resource"]] == "/admin/app-content/ai2apps.imagine-studio"


def test_imagine_studio_uses_studio_shell_with_builtin_mini_apps():
    template = (WEB_ROOT / "templates/system_apps/imagine_studio.html").read_text()
    script = (WEB_ROOT / "static/js/imagine_studio.js").read_text()
    stylesheet = (WEB_ROOT / "static/css/imagine_studio.css").read_text()

    assert 'data-app-id="ai2apps.imagine-studio"' in template
    assert 'data-lucide="palette"' in template
    assert 'data-lucide="wand-sparkles"' in template
    assert "x-text=\"tr('appName')\"" in template
    assert "appName: '创意画坊'" in script
    assert "appName: 'Imagine Studio'" in script
    assert "ai2apps:host-context" in script
    assert "normalizedLocale(document.documentElement.lang)" in script
    assert 'class="vs-studio-sidebar"' in template
    assert "is-mini-app-workspace" in template
    assert "vs-render-workspace" in template
    assert "Gallery Mini Entry" in template
    assert "文生图" in script and "图片编辑" in script and "参考图创作" in script and "合影" in script
    assert "ai2apps.imagine.text-to-image" in script
    assert "ai2apps.imagine.image-edit" in script
    assert "ai2apps.imagine.style-transfer" in script
    assert "ai2apps.imagine.reference-creation" in script
    assert "ai2apps.imagine.group-photo" in script
    assert "ai2apps.imagine.adjust-image" in script
    assert "STYLE_TRANSFER_INSTRUCTION" in script
    assert "preferOpenAIStyleModel" in script
    assert "isStyleTransferMode ? Boolean(this.selectedStyle)" in script
    assert "group-photo-1" in template
    assert "GROUP_PHOTO_INSTRUCTION" in script
    assert "groupPersonFiles.length >= 2" in script
    assert "referenceSlotLabel(slot-1)" in template
    assert "groupBackgroundDescription" in template
    assert "groupAtmosphere" in template
    assert "groupPose" in template
    assert ".is-group-photo-fields" in stylesheet
    assert "CURRENT MINI-APP" in script
    assert "Mini-Apps 与素材" in script
    assert "filteredMiniApps" in template
    assert 'class="is-mini-search"' not in template and 'class="is-mini-filters"' not in template
    assert "favoriteMiniApps" in script and "recentMiniApps" in script
    assert "mobileSurface" in template and "is-mobile-nav" in template
    assert "leftCollapsed" in template and "rightCollapsed" in template
    assert "handleGalleryDrop($event,slot-1)" in template
    assert "@drop.stop.prevent" in template
    assert "gallerySlotTarget" in script
    assert "mountMiniEntry" in script and "appId: 'ai2apps.gallery'" in script
    assert "GALLERY_MINI_FALLBACK_URL" in script
    assert "AI2Apps Host did not respond|Unsupported host mount" in script
    assert "if (this.leftView === 'assets') this.mountGalleryMini()" in script
    assert "--vs-accent" in stylesheet
    assert ".is-logo{background:#18181b;box-shadow:0 7px 18px #18181b26}" in stylesheet
    assert ".is-app>.vs-notice{width:calc(100% - 36px);max-width:1724px}" in stylesheet
    assert ".is-app>.vs-notice.neutral" in stylesheet
    assert '@click="dismissNotice()"' in template
    assert "showNotice(message, tone = 'error', timeoutMs = null)" in script


def test_imagine_studio_notice_auto_dismisses_by_tone():
    script = (WEB_ROOT / "static/js/imagine_studio.js").read_text()
    methods = script.split("        dismissNotice() {", 1)[1].split(
        "        setupMiniAppChat", 1
    )[0]
    program = "const methods = {dismissNotice() {" + methods + r"""
setupMiniAppChat() {}};
const assert = require('node:assert/strict');
let nextTimer = 0;
const timers = new Map();
global.setTimeout = (callback, delay) => {
  const id = ++nextTimer;
  timers.set(id, {callback, delay});
  return id;
};
global.clearTimeout = id => timers.delete(id);
const state = {notice: '', noticeTone: 'error', noticeTimer: null, icons() {}, ...methods};
state.fail(new Error('已取消能力配置'));
assert.equal(state.noticeTone, 'neutral');
assert.equal(timers.get(state.noticeTimer).delay, 4000);
timers.get(state.noticeTimer).callback();
assert.equal(state.notice, '');
state.success('Saved');
assert.equal(state.noticeTone, 'success');
assert.equal(timers.get(state.noticeTimer).delay, 4500);
state.fail(new Error('Network failed'));
assert.equal(state.noticeTone, 'error');
assert.equal(timers.get(state.noticeTimer).delay, 8000);
const pending = state.noticeTimer;
state.dismissNotice();
assert.equal(state.notice, '');
assert.equal(timers.has(pending), false);
"""
    subprocess.run(["node", "-e", program], check=True, capture_output=True, text=True)


def test_imagine_studio_has_a_cross_mini_app_categorized_visual_style_picker():
    template = (WEB_ROOT / "templates/system_apps/imagine_studio.html").read_text()
    script = (WEB_ROOT / "static/js/imagine_studio.js").read_text()
    catalog = (WEB_ROOT / "static/js/imagine_style_catalog.js").read_text()
    stylesheet = (WEB_ROOT / "static/css/imagine_studio.css").read_text()
    style_images = list((WEB_ROOT / "static/images/imagine-studio/styles").glob("*.webp"))

    assert "imagine_style_catalog.js" in template
    assert template.index("imagine_style_catalog.js") < template.index("imagine_studio.js")
    assert '<section class="is-style-control"' in template
    assert 'x-show="currentMiniApp.mode===\'generate\'" class="is-style-control"' not in template
    assert "openStyleDialog()" in template
    assert 'role="dialog"' in template and 'aria-modal="true"' in template
    assert "styleCategories" in template and "activeStyleCategory.styles" in template
    assert "pendingStyle===''" in template and "tr('noStyle')" in template
    assert "applyStyle()" in template and "closeStyleDialog()" in template
    assert "window.IMAGINE_STYLE_CATALOG" in catalog
    assert '"EN":"Modern / Digital"' in catalog
    assert '"CN":"巴洛克"' in catalog and '"CN":"哥特风格"' in catalog
    assert '"image":"8bit_256.png"' in catalog
    assert len(style_images) == 51
    assert "const STYLE_KEY = 'ai2apps.imagine-studio.image-style.v1'" in script
    assert "persistStylePreference()" in script
    assert "this.applyDraft(run.input, true)" in script
    assert "STYLE_TRANSFER_INSTRUCTION : '', this.selectedStyle?.prompt || '', this.prompt.trim()" in script
    assert "所有图片 Mini-App 共用的核心设置" in script
    assert "LEGACY_STYLE_IDS" in script
    assert ".is-style-dialog-backdrop" in stylesheet
    assert ".is-style-grid" in stylesheet


def test_imagine_studio_adjust_image_is_a_local_non_ai_mini_app():
    template = (WEB_ROOT / "templates/system_apps/imagine_studio.html").read_text()
    script = (WEB_ROOT / "static/js/imagine_studio.js").read_text()
    engine = (WEB_ROOT / "static/js/imagine_adjust.js").read_text()
    stylesheet = (WEB_ROOT / "static/css/imagine_studio.css").read_text()

    assert "imagine_adjust.js" in template
    assert template.index("imagine_adjust.js") < template.index("imagine_studio.js")
    assert "isAdjustMode" in script and "localAdjustments" in script
    assert "exportAdjustment" in script and "local/image-adjustments" in script
    assert "window.ImagineAdjustEngine" in engine
    assert "fetch(dataUrl)" not in script
    assert "atob(match[3])" in script
    assert "canvas.toBlob" in script
    assert "imageFile = await canvasFile" in script
    assert "result.imageFile.arrayBuffer()" in script
    assert "fetch(`${HISTORY_API}/chunks`" in script
    assert "cropRect" in engine and "context.rotate" in engine
    assert "flipX" in engine and "flipY" in engine
    assert "OpenAI / Google · 1024×1024 (1:1)" in engine
    assert "OpenAI · 1536×1024 (3:2)" in engine
    assert "OpenAI · 1024×1536 (2:3)" in engine
    assert "Google · 1264×848" in engine and "value: '1264:848'" in engine
    assert "Google · 848×1264" in engine and "value: '848:1264'" in engine
    assert "model-crop-presets-1" in template
    for control in (
        "exposure", "brilliance", "highlights", "shadows", "contrast",
        "brightness", "saturation", "vibrance", "blackPoint", "colorBalance",
        "warmth", "tint", "sharpness", "definition", "noiseReduction", "vignette",
    ):
        assert f"['{control}'," in engine
    assert "undoAdjustment" in script and "redoAdjustment" in script
    assert "materializeAssetReference(assetReference, index, preserveAdjustments = false)" in script
    assert "materializeAssetReference(values[index], index, true)" in script
    assert "adjustState.cropRatio" in template
    assert "transformAdjustment('rotate-left')" in template
    assert "transformAdjustment('flip-x')" in template
    assert ".is-adjust-stage" in stylesheet and ".is-adjust-controls" in stylesheet
    assert "ADJUSTMENT_PRESETS_KEY" in script and "saveAdjustmentPreset" in script
    assert "preservesAdjustmentsForNewImage" in script
    assert "adjustmentLocked" in template and "lockAdjustment" in template
    assert "adjustmentPresetDialogOpen" in template and "deleteAdjustmentPreset" in template
    assert "adjustmentBatchOpen" in template and "runAdjustmentBatch" in script
    assert 'webkitdirectory multiple' in template
    assert "mozAI2AppsFullPath" in script
    assert "/batch-output/chunks" in script
    assert ".is-adjust-preset-bar" in stylesheet and ".is-batch-dialog" in stylesheet


def test_imagine_studio_uses_cloud_and_local_image_models_with_capability_aware_sizes():
    template = (WEB_ROOT / "templates/system_apps/imagine_studio.html").read_text()
    script = (WEB_ROOT / "static/js/imagine_studio.js").read_text()

    assert "const DEFAULT_CLOUD_MODEL = 'cloud/ai2apps/openai/gpt-image-2'" in script
    assert "function managedCloudModelId(value)" in script
    assert "id: managedCloudModelId(model.id)" in script
    assert "const managedModelId = managedCloudModelId(savedModelId)" in script
    assert "model.source === 'cloud' && model.id === managedModelId" in script
    assert "/v1/platform/cloud/ai/models" in script
    assert "const LOCAL_MODELS_API = '/v1/platform/imagine-studio/models'" in script
    assert "const IMAGE_API = '/v1/images'" in script
    assert "executeCloudRun" in script
    assert "waitForRun" in script and "monitorActiveRun" in script
    assert "`${STUDIO_API}/runs/${encodeURIComponent(runId)}/execute`" in script
    assert "model_type === 'image_generation'" in script
    assert "source_type === 'package'" in script
    assert "model.image_capabilities?.operations" in script
    assert 'x-for="model in compatibleModels"' in template
    assert "bounded-custom" in script
    assert "imageOptions?.size" in script
    assert "model.imageOptions?.quality" in script
    assert "model.imageOptions?.outputFormat" in script
    assert "qualityOptions" in script
    assert 'x-for="value in qualityOptions"' in template
    assert "sizeOptions" in script and "requestedSize" in script
    assert "values.push('custom')" in script
    assert "customWidth" in template and "customHeight" in template
    assert "总像素不能超过" in script
    assert "长短边比例不能超过" in script
    assert "2K+ 实验性输出" in script and "tr('experimentalSize')" in template
    assert "const GOOGLE_SIZE_LABELS" in script
    assert "'1536x1024': { size: '1264×848', ratio: '3:2' }" in script
    assert "'1024x1536': { size: '848×1264', ratio: '2:3' }" in script
    assert "Google 当前真实 1K 输出尺寸" in script
    assert "artifact.metadata?.size" in template
    assert "`${IMAGE_API}/${editing ? 'edits' : 'generations'}`" in script
    assert "'Idempotency-Key': `imagine-${id}`" in script
    assert "credentials: 'same-origin'" in script
    assert "imageDataUrls" in script
    assert "window.confirm" in script
    assert "上传到 AI2Apps Cloud 图像模型处理" in script
    assert "每次发送图片前都会请求确认" in script
    assert "localDisclosure" in script and "usingLocalModel?'localDisclosure':'cloudDisclosure'" in template
    assert "selectedModel.source === 'cloud'" in script
    assert "configureLocalModel" in script and "tr(configuringLocal?'configuringLocal':'configureLocal')" in template
    assert '<option value="__install_more__"' in template
    assert '<option x-show="!compatibleModels.length" value="" disabled' in template
    assert template.index("tr('noModelsAvailable')") < template.index("tr('installMoreModels')")
    assert "x-text=\"tr('installMoreModels')\"" in template
    assert "onModelSelect($event.target)" in template
    assert "configureLocalModel(installMore = false)" in script
    assert "{ installMore }" in script
    assert "window.AI2AppsCapabilities.ensure" in script
    assert "completionPolicy: 'configure_only'" in script
    assert "globalThis.crypto?.randomUUID?.()" in script
    assert "capability: this.requiredOperation === 'image_edit' ? 'image.edit' : 'image.generation'" in script
    assert "requirements: { operations: [this.requiredOperation]" in script
    assert "capability_provisioning.js" in template
    assert "加入 Gallery" in script and "tr('addGallery')" in template
    assert "galleryActiveCollectionId" in script
    assert "resource-handles" in script
    assert "resourceHandle" in script
    assert "consumerAppId: APP_ID" in script
    assert "handleWorkspaceDrag" in script
    assert "const HISTORY_API = '/v1/platform/imagine-studio/results'" in script
    assert "createRun" in script and "updateRun" in script and "refreshRuns" in script
    assert "steps" in template and "artifacts" in template
    assert "scheduleDraftSave" in script and "saveDraft" in script
    assert "addArtifactToGallery" in script
    assert "downloadArtifact" in script and "downloadUrl" in template
    assert "X-AI2Apps-App-Instance" in script
    assert "永久清空 Imagine Studio 的全部生成历史" in script
    assert "async function imageDimensions" in script
    assert "matchEditAspect" in script
    assert "referenceDimensions" in script
    assert "Math.abs(Math.log((width / height) / sourceRatio))" in script
    assert "已匹配原图比例" in script and "tr('matchedRatio')" in template
    assert "object-fit:contain" in template
    assert "referenceSlotStyle" in script
    assert "aspect-ratio:${dimensions.width}/${dimensions.height}" in script
    assert ':style="referenceSlotStyle(slot-1)"' in template


def test_imagine_studio_completed_artifact_controls():
    template = (WEB_ROOT / "templates/system_apps/imagine_studio.html").read_text()
    assert '<h2>Output</h2>' in template
    css = (WEB_ROOT / "static/css/imagine_studio.css").read_text()
    assert '.vs-render-workspace>.is-image-preview:not(.empty){position:sticky;top:0;z-index:5;max-height:calc(100% - 20px)' in css
    assert ':disabled="!activeArtifact?.id || !!(activeArtifact?.adding || activeArtifact?.galleryAssetId)"' in template
    assert ':aria-busy="!!activeArtifact?.adding"' in template
    assert 'class="is-run-progress" x-show="isActiveRun(selectedRun)"' in template
    expression = "!activeArtifact?.id || !!(activeArtifact?.adding || activeArtifact?.galleryAssetId)"
    program = """const assert = require('node:assert/strict');
const disabled = activeArtifact => """ + expression + """;
assert.equal(disabled({id: 'ready'}), false);
assert.equal(disabled({id: 'ready', galleryAssetId: ''}), false);
assert.equal(disabled({id: 'busy', adding: true}), true);
assert.equal(disabled({id: 'saved', galleryAssetId: 'asset-1'}), true);
assert.equal(disabled(null), true);
"""
    subprocess.run(["node", "-e", program], check=True, capture_output=True, text=True)


def test_flux_edit_disables_reference_cache_only_for_local_edits():
    script = (WEB_ROOT / "static/js/imagine_studio.js").read_text()
    method = script.split("        localEditParameters(model, editing) {", 1)[1].split("\n        },", 1)[0]
    program = "const params = function(model, editing) {" + method + "};" + """
const assert = require('node:assert/strict');
for (const variant of ['4b', '9b']) {
  const model = {source:'local',id:'ai2apps.model.flux2-klein-mlx/'+variant};
  assert.deepEqual(params(model,true),{use_kv_cache:false});
  assert.deepEqual(params(model,false),{});
  assert.deepEqual(params({...model,source:'cloud'},true),{});
}
assert.deepEqual(params({source:'local',id:'ai2apps.model.z-image-mlx'},true),{});
assert.deepEqual(params(null,true),{});
"""
    subprocess.run(["node", "-e", program], check=True, capture_output=True, text=True)
    assert "...this.localEditParameters(selectedModel, editing)" in script


def test_z_image_redraw_parameter_direction():
    script = (WEB_ROOT / "static/js/imagine_studio.js").read_text()
    method = script.split("        zImageParameters() {", 1)[1].split("\n        },", 1)[0]
    program = "const params = function() {" + method + "};" + """
const assert = require('node:assert/strict');
const state = {usingZImage:true,zImageSteps:8,zImageRedraw:75,currentMiniApp:{mode:'edit'}};
assert.deepEqual(params.call(state),{num_inference_steps:8,strength:0.25});
assert.equal(8-Math.max(1,Math.floor(8*params.call(state).strength)),6);
state.currentMiniApp.mode='generate';
assert.deepEqual(params.call(state),{num_inference_steps:8});
state.usingZImage=false;
assert.deepEqual(params.call(state),{});
"""
    subprocess.run(["node", "-e", program], check=True, capture_output=True, text=True)


def test_imagine_studio_install_more_action_preserves_selected_model():
    script = (WEB_ROOT / "static/js/imagine_studio.js").read_text()
    method = script.split("        onModelSelect(select) {", 1)[1].split(
        "        async configureLocalModel", 1
    )[0].strip().removesuffix(",")
    program = "const change = function(select) {" + method + ";\n" + r"""
const assert = require('node:assert/strict');
const calls = [];
const state = {
  modelId: 'cloud/ai2apps/openai/gpt-image-2',
  configureLocalModel: value => calls.push(['install', value]),
  scheduleDraftSave: () => calls.push(['save']),
};
const install = {value: '__install_more__'};
change.call(state, install);
assert.equal(install.value, 'cloud/ai2apps/openai/gpt-image-2');
assert.equal(state.modelId, 'cloud/ai2apps/openai/gpt-image-2');
assert.deepEqual(calls, [['install', true]]);
change.call(state, {value: 'local/image-model'});
assert.equal(state.modelId, 'local/image-model');
assert.deepEqual(calls, [['install', true], ['save']]);
const emptyState = {...state, modelId: ''};
const emptyInstall = {value: '__install_more__'};
change.call(emptyState, emptyInstall);
assert.equal(emptyInstall.value, '');
assert.equal(emptyState.modelId, '');
"""
    subprocess.run(["node", "-e", program], check=True, capture_output=True, text=True)


def test_imagine_studio_durable_run_step_artifact_and_draft_api(tmp_path, monkeypatch):
    config = PlatformConfig.from_base_path(tmp_path)
    database = PlatformDatabase(config.paths.database_path)
    database.initialize()
    principal = RequestPrincipal.legacy_local()
    app_instance_id = "appi_" + "b" * 32

    class ExtensionManager:
        def require_instance_access(self, instance_id, selected):
            assert instance_id == app_instance_id
            assert selected.actor_user_id == principal.actor_user_id

        def instance_entry(self, instance_id, *, principal):
            assert instance_id == app_instance_id
            return {"app_key": "ai2apps.imagine-studio"}

    runtime = SimpleNamespace(
        database=database,
        config=config,
        extension_manager=ExtensionManager(),
        events=None,
        cloud=object(),
        cloud_ai_authorization_headers=lambda selected: {"X-AI2Apps-Device-Authorization": "device-proof"},
    )
    app = FastAPI()
    app.include_router(create_imagine_studio_router(lambda: runtime, lambda: principal))
    client = TestClient(app)
    headers = {"X-AI2Apps-App-Instance": app_instance_id}

    mini_apps = client.get("/imagine-studio/mini-apps").json()["items"]
    assert [item["id"] for item in mini_apps] == [
        "ai2apps.imagine.text-to-image",
        "ai2apps.imagine.image-edit",
        "ai2apps.imagine.style-transfer",
        "ai2apps.imagine.reference-creation",
        "ai2apps.imagine.group-photo",
        "ai2apps.imagine.adjust-image",
    ]
    draft_url = "/imagine-studio/drafts/ai2apps.imagine.text-to-image"
    assert client.put(draft_url, headers=headers, json={"draft": {"prompt": "durable"}}).status_code == 200
    assert client.get(draft_url, headers=headers).json()["draft"] == {"prompt": "durable"}

    created = client.post(
        "/imagine-studio/runs",
        headers=headers,
        json={"miniAppId": mini_apps[0]["id"], "title": "Text to Image", "input": {"prompt": "durable"}},
    )
    assert created.status_code == 201
    run = created.json()
    assert run["status"] == "queued" and run["steps"][0]["status"] == "pending"

    cloud_image = BytesIO()
    Image.new("RGB", (2, 2), "blue").save(cloud_image, format="JPEG")
    image_data_url = "data:image/jpeg;base64," + base64.b64encode(cloud_image.getvalue()).decode("ascii")
    captured = {}

    async def fake_request_cloud_image(payload, **kwargs):
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"image": {"dataUrl": image_data_url, "size": "1264x848", "format": "jpeg"}}

    monkeypatch.setattr("ai2apps.api.imagine_studio.request_cloud_image", fake_request_cloud_image)
    executed = client.post(
        f"/imagine-studio/runs/{run['id']}/execute",
        headers=headers,
        json={
            "model": "cloud/ai2apps/google/gemini-3.1-flash-image",
            "prompt": "durable background run",
            "size": "1536x1024",
            "quality": "auto",
            "outputFormat": "png",
        },
    )
    assert executed.status_code == 202
    completed = client.get("/imagine-studio/runs", headers=headers).json()["items"][0]
    assert completed["status"] == "succeeded"
    assert completed["steps"][0]["status"] == "succeeded"
    assert completed["artifacts"][0]["previewUrl"].startswith("/v1/platform/imagine-studio/results/")
    assert completed["artifacts"][0]["name"].endswith(".jpg")
    assert completed["artifacts"][0]["mediaType"] == "image/jpeg"
    assert completed["artifacts"][0]["metadata"]["size"] == "1264x848"
    assert completed["artifacts"][0]["metadata"]["requestedSize"] == "1536x1024"
    assert completed["artifacts"][0]["metadata"]["format"] == "jpeg"
    assert completed["artifacts"][0]["metadata"]["requestedFormat"] == "png"
    assert captured["payload"]["model"] == "cloud/ai2apps/google/gemini-3.1-flash-image"
    assert "imageDataUrls" not in captured["payload"]
    assert captured["kwargs"]["base_path"] == config.paths.base_path
    assert captured["kwargs"]["cloud_headers"] == {"X-AI2Apps-Device-Authorization": "device-proof"}

    image = BytesIO()
    Image.new("RGB", (2, 2), "blue").save(image, format="PNG")
    created = client.post(
        "/imagine-studio/runs",
        headers=headers,
        json={"miniAppId": mini_apps[0]["id"], "title": "Text to Image", "input": {"prompt": "manual"}},
    )
    run = created.json()
    running = client.patch(
        f"/imagine-studio/runs/{run['id']}", headers=headers,
        json={"status": "running", "progress": 25, "detail": "Generating"},
    ).json()
    assert running["status"] == "running"
    assert running["steps"][0]["status"] == "running"
    assert running["steps"][0]["progress"] == 25

    metadata = {
        "pipelineId": "text-image", "miniAppId": mini_apps[0]["id"], "runId": run["id"],
        "title": "Text to Image", "prompt": "durable", "modelId": "openai/gpt-image-2",
        "modelLabel": "GPT Image 2", "size": "1024x1024", "quality": "auto",
        "format": "png", "filename": "artifact.png",
    }
    result = client.post(
        "/imagine-studio/results", headers=headers,
        files={"metadata": (None, json.dumps(metadata), "application/json"), "image": ("artifact.png", image.getvalue(), "image/png")},
    )
    assert result.status_code == 201
    artifact = result.json()["artifact"]
    assert artifact["uri"].startswith("artifact://sta_")
    assert artifact["downloadUrl"].endswith("&download=true")
    succeeded = client.patch(
        f"/imagine-studio/runs/{run['id']}", headers=headers,
        json={"status": "succeeded", "progress": 100, "detail": "Completed"},
    ).json()
    assert succeeded["artifacts"][0]["id"] == artifact["id"]

    gallery = client.post(
        f"/imagine-studio/artifacts/{artifact['id']}/gallery",
        headers=headers,
        json={"collectionId": None},
    )
    assert gallery.status_code == 201
    assert gallery.json()["asset"]["source_ref"] == artifact["uri"]
    listed = client.get("/imagine-studio/runs", headers=headers).json()["items"]
    assert listed[0]["id"] == run["id"]
    assert listed[0]["steps"][0]["status"] == "succeeded"

    chunk_metadata = metadata | {"runId": None, "filename": "chunk-artifact.png"}
    encoded_image = base64.b64encode(image.getvalue()).decode("ascii")
    first_chunk = client.post(
        "/imagine-studio/results/chunks", headers=headers,
        json={"uploadId": "upload-test", "index": 0, "total": 2, "metadata": chunk_metadata, "data": encoded_image[:40]},
    )
    assert first_chunk.status_code == 200 and first_chunk.json()["complete"] is False
    chunk_result = client.post(
        "/imagine-studio/results/chunks", headers=headers,
        json={"uploadId": "upload-test", "index": 1, "total": 2, "metadata": chunk_metadata, "data": encoded_image[40:]},
    )
    assert chunk_result.status_code == 200
    assert chunk_result.json()["filename"] == "chunk-artifact.png"

    source_path = tmp_path / "source.png"
    source_path.write_bytes(image.getvalue())
    output_root = tmp_path / "adjusted"
    output_root.mkdir()
    batch_target = {
        "kind": "local", "overwrite": False, "sourcePath": str(source_path),
        "outputRoot": str(output_root), "relativePath": "nested/source.png",
        "name": "source.png", "mediaType": "image/png",
    }
    batch_saved = client.post(
        "/imagine-studio/batch-output/chunks", headers=headers,
        json={"uploadId": "batch-save-as", "index": 0, "total": 1, "target": batch_target, "data": encoded_image},
    )
    assert batch_saved.status_code == 200
    assert (output_root / "nested/source.png").read_bytes() == image.getvalue()

    replacement = BytesIO()
    Image.new("RGB", (2, 2), "green").save(replacement, format="PNG")
    replacement_encoded = base64.b64encode(replacement.getvalue()).decode("ascii")
    batch_overwrite = client.post(
        "/imagine-studio/batch-output/chunks", headers=headers,
        json={"uploadId": "batch-overwrite", "index": 0, "total": 1,
              "target": batch_target | {"overwrite": True}, "data": replacement_encoded},
    )
    assert batch_overwrite.status_code == 200
    assert source_path.read_bytes() == replacement.getvalue()

    gallery_asset_id = gallery.json()["asset"]["id"]
    gallery_overwrite = client.post(
        "/imagine-studio/batch-output/chunks", headers=headers,
        json={"uploadId": "batch-gallery-overwrite", "index": 0, "total": 1,
              "target": {"kind": "gallery", "overwrite": True,
                         "assetId": gallery_asset_id, "collectionId": None,
                         "name": "artifact.png", "mediaType": "image/png"},
              "data": replacement_encoded},
    )
    assert gallery_overwrite.status_code == 200
    assert gallery_overwrite.json()["asset"]["id"] == gallery_asset_id
    gallery_repository = GalleryRepository(database, config.paths.artifacts_path / "gallery")
    _, gallery_path = gallery_repository.asset_path(principal.actor_user_id, gallery_asset_id)
    assert gallery_path.read_bytes() == replacement.getvalue()


def test_imagine_studio_history_persists_latest_twenty_images(tmp_path):
    config = PlatformConfig.from_base_path(tmp_path)
    database = PlatformDatabase(config.paths.database_path)
    database.initialize()
    principal = RequestPrincipal.legacy_local()
    app_instance_id = "appi_" + "a" * 32

    class ExtensionManager:
        def require_instance_access(self, instance_id, selected):
            assert instance_id == app_instance_id
            assert selected.actor_user_id == principal.actor_user_id

        def instance_entry(self, instance_id, *, principal):
            assert instance_id == app_instance_id
            return {"app_key": "ai2apps.imagine-studio"}

    runtime = SimpleNamespace(database=database, config=config, extension_manager=ExtensionManager())
    app = FastAPI()
    app.include_router(create_imagine_studio_router(lambda: runtime, lambda: principal))
    client = TestClient(app)
    headers = {"X-AI2Apps-App-Instance": app_instance_id}
    image = BytesIO()
    Image.new("RGB", (2, 2), "purple").save(image, format="PNG")
    metadata = {
        "pipelineId": "text-image", "title": "文生图", "prompt": "private prompt",
        "modelId": "openai/gpt-image-2", "modelLabel": "GPT Image 2",
        "size": "1024x1024", "quality": "auto", "format": "png", "filename": "result.png",
    }

    created_ids = []
    for index in range(22):
        metadata["prompt"] = f"private prompt {index}"
        response = client.post(
            "/imagine-studio/results", headers=headers,
            files={"metadata": (None, json.dumps(metadata), "application/json"), "image": ("result.png", image.getvalue(), "image/png")},
        )
        assert response.status_code == 201
        created_ids.append(response.json()["id"])

    items = client.get("/imagine-studio/results?limit=20", headers=headers).json()["items"]
    assert len(items) == 20
    assert items[0]["prompt"] == "private prompt 21"
    assert created_ids[0] not in {item["id"] for item in items}
    content = client.get(f"/imagine-studio/results/{items[0]['id']}/content?appInstanceId={app_instance_id}")
    assert content.status_code == 200 and content.content == image.getvalue()
    assert client.delete(f"/imagine-studio/results/{items[0]['id']}", headers=headers).status_code == 204
    assert len(client.get("/imagine-studio/results", headers=headers).json()["items"]) == 19


def test_schema_v45_upgrades_to_imagine_studio_history(tmp_path):
    path = tmp_path / "platform.sqlite3"
    with sqlite3.connect(path) as connection:
        assert apply_migrations(connection, MIGRATIONS[:45]) == 45
    state = PlatformDatabase(path).initialize()
    assert state.schema_version == len(MIGRATIONS)
    with sqlite3.connect(path) as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='imagine_studio_results'"
        ).fetchone()
    assert table == ("imagine_studio_results",)


def test_imagine_studio_acpf_profiles_choose_a_local_image_stack_by_device_memory():
    capability = CapabilityProfileRegistry().capability(
        "ai2apps.imagine-studio", "image.generation"
    )

    assert capability is not None
    assert capability["requirements"]["operations"] == [
        "image_generation"
    ]
    profiles = {item["id"]: item for item in capability["profiles"]}
    editing = CapabilityProfileRegistry().capability("ai2apps.imagine-studio", "image.edit")
    assert editing["requirements"]["operations"] == ["image_edit"]
    assert {p["id"] for p in editing["profiles"]} == {
        "apple-metal-flux2-klein-4b",
        "apple-metal-flux2-klein-9b",
        "apple-metal-qwen-image-edit-2511",
    }
    # Every checkpoint must have an install option for its supported operation.
    import yaml

    offered = set()
    for profile in [*profiles.values(), *editing["profiles"]]:
        stack = profile["stack"]
        if "checkpoint" in stack:
            offered.add(stack["checkpoint"]["model_id"])
        offered.update(
            item["model_id"] for item in stack.get("components", [])
            if item["kind"] == "checkpoint"
        )
    expected = set()
    for path in (Path(__file__).parents[1] / "packages").glob("*/service.yaml"):
        manifest = yaml.safe_load(path.read_text())
        expected.update(
            model["id"] for model in manifest.get("models", [])
            if model.get("model_type") == "image_generation"
        )
    assert expected <= offered, f"Missing image install options: {expected - offered}"
    assert profiles["apple-metal-z-image-turbo"]["stack"] == {
        "runtime": {
            "package_id": "ai2apps/runtime-omlx",
            "service_key": "ai2apps.runtime.omlx",
            "version": ">=1.5.2,<2.0.0",
        },
        "provider": {
            "package_id": "ai2apps/model-z-image-mlx",
            "service_key": "ai2apps.model.z-image-mlx",
            "version": ">=0.1.1,<1.0.0",
        },
        "checkpoint": {"model_id": "ai2apps.model.z-image-mlx/turbo"},
    }
    assert profiles["apple-metal-flux2-klein-4b"]["recommendation_memory_gib"] == {
        "minimum": 16, "maximum_exclusive": 24
    }
