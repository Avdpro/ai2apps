import json
import sqlite3
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from ai2apps.api.imagine_studio import create_imagine_studio_router
from ai2apps.apps import SYSTEM_APP_MANIFESTS
from ai2apps.config import PlatformConfig
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


def test_imagine_studio_copies_the_studio_shell_and_exposes_three_image_pipelines():
    template = (WEB_ROOT / "templates/system_apps/imagine_studio.html").read_text()
    script = (WEB_ROOT / "static/js/imagine_studio.js").read_text()
    stylesheet = (WEB_ROOT / "static/css/imagine_studio.css").read_text()

    assert 'data-app-id="ai2apps.imagine-studio"' in template
    assert 'data-lucide="palette"' in template
    assert 'data-lucide="wand-sparkles"' not in template
    assert "x-text=\"tr('appName')\"" in template
    assert "appName: '创意画坊'" in script
    assert "appName: 'Imagine Studio'" in script
    assert "ai2apps:host-context" in script
    assert "normalizedLocale(document.documentElement.lang)" in script
    assert 'class="vs-studio-sidebar"' in template
    assert 'class="vs-pipeline-workspace"' in template
    assert "vs-render-workspace" in template
    assert "Gallery Mini Entry" in template
    assert "文生图" in script and "图片编辑" in script and "参考图创作" in script
    assert "maxImages: 1" in script and "maxImages: 4" in script
    assert "handleGalleryDrop($event,slot-1)" in template
    assert "@drop.stop.prevent" in template
    assert "gallerySlotTarget" in script
    assert "mountMiniEntry" in script and "appId: 'ai2apps.gallery'" in script
    assert "--vs-accent" in stylesheet
    assert ".is-logo{background:#18181b;box-shadow:0 7px 18px #18181b26}" in stylesheet


def test_imagine_studio_uses_cloud_and_local_image_models_with_capability_aware_sizes():
    template = (WEB_ROOT / "templates/system_apps/imagine_studio.html").read_text()
    script = (WEB_ROOT / "static/js/imagine_studio.js").read_text()

    assert "const DEFAULT_CLOUD_MODEL = 'openai/gpt-image-2'" in script
    assert "const GOOGLE_FLASH_MODEL = 'google/gemini-3.1-flash-image'" in script
    assert "/v1/platform/cloud/ai/models" in script
    assert "const LOCAL_MODELS_API = '/v1/models'" in script
    assert "const IMAGE_API = '/v1/images'" in script
    assert "model_type === 'image_generation'" in script
    assert "source_type === 'package'" in script
    assert "model.image_capabilities?.operations" in script
    assert 'x-for="model in compatibleModels"' in template
    assert "bounded-custom" in script
    assert "imageOptions?.size" in script
    assert "sizeOptions" in script and "requestedSize" in script
    assert "values.push('custom')" in script
    assert "customWidth" in template and "customHeight" in template
    assert "总像素不能超过" in script
    assert "长短边比例不能超过" in script
    assert "2K+ 实验性输出" in script and "tr('experimentalSize')" in template
    assert "固定尺寸 · 1:1 / 3:2 / 2:3" in script
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
    assert "window.AI2AppsCapabilities.ensure" in script
    assert "completionPolicy: 'configure_only'" in script
    assert "globalThis.crypto?.randomUUID?.()" in script
    assert "capability: 'image.generation'" in script
    assert "capability_provisioning.js" in template
    assert "加入 Gallery" in script and "tr('addGallery')" in template
    assert "galleryActiveCollectionId" in script
    assert "assets/import" in script
    assert "sourceAppId" in script
    assert "dragGeneratedImage" in script
    assert "dragFileFromDataUrl" in script
    assert "event.dataTransfer.items?.add?.(dragFile)" in script
    assert "event.dataTransfer.setData('text/uri-list', result.imageUrl)" in script
    assert "application/x-ai2apps-image-result" in script
    assert "handleWorkspaceDrag" in script
    assert "types.includes('application/x-ai2apps-image-result')" in script
    assert '@dragstart="dragGeneratedImage($event,activeResult)"' in template
    assert '@dragstart="dragGeneratedImage($event,result)"' in template
    assert "const HISTORY_API = '/v1/platform/imagine-studio/results'" in script
    assert "loadHistory" in script and "persistResult" in script
    assert "?limit=20" in script
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
        "image_generation", "image_edit"
    ]
    profiles = {item["id"]: item for item in capability["profiles"]}
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
