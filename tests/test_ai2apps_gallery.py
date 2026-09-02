from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from ai2apps.api.gallery import create_gallery_router
from ai2apps.apps import SYSTEM_APP_MANIFESTS
from ai2apps.config import PlatformConfig
from ai2apps.gallery import GalleryRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.storage import PlatformDatabase
from omlx.admin.routes import _shell_mount_payload

WEB_ROOT = Path(__file__).parents[1] / "ai2apps" / "web"


def _gallery(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    return GalleryRepository(database, tmp_path / "gallery"), database


def test_gallery_repository_imports_deduplicates_indexes_and_deletes(tmp_path):
    gallery, _database = _gallery(tmp_path)
    owner = "owner"
    collections = gallery.list_collections(owner)
    assert [item["system_key"] for item in collections] == [
        "recent",
        "downloads",
        "public",
        "personal",
        "trash",
    ]
    project = gallery.create_collection(owner, name="Launch", kind="project")

    asset, created = gallery.import_stream(
        owner,
        BytesIO(b"gallery image"),
        name="hero.png",
        media_type="image/png",
        collection_id=project["id"],
        source_app_id="ai2apps.general-chat",
    )
    duplicate, duplicate_created = gallery.import_stream(
        owner,
        BytesIO(b"gallery image"),
        name="hero.png",
        media_type="image/png",
    )

    assert created is True
    assert duplicate_created is False
    assert duplicate["id"] == asset["id"]
    assert asset["kind"] == "image"
    renamed = gallery.rename_asset(owner, asset["id"], "hero-final.png")
    assert renamed["name"] == "hero-final.png"
    assert gallery.list_assets(owner, collection_id=project["id"])[0]["id"] == asset["id"]

    personal = next(
        item for item in gallery.list_collections(owner) if item["system_key"] == "personal"
    )
    gallery.add_to_collection(owner, personal["id"], asset["id"])
    assert gallery.list_assets(owner, collection_id=personal["id"])[0]["id"] == asset["id"]

    gallery.remove_from_collection(owner, project["id"], asset["id"])
    assert gallery.list_assets(owner, collection_id=project["id"]) == ()
    gallery.trash_asset(owner, asset["id"])
    trash = next(
        item for item in gallery.list_collections(owner) if item["system_key"] == "trash"
    )
    assert gallery.list_assets(owner, collection_id=trash["id"])[0]["id"] == asset["id"]
    gallery.restore_asset(owner, asset["id"])
    _record, path = gallery.asset_path(owner, asset["id"])
    assert path.read_bytes() == b"gallery image"
    gallery.delete_asset(owner, asset["id"])
    assert not path.exists()


def test_gallery_repository_isolates_users_and_preserves_shared_blob(tmp_path):
    gallery, _database = _gallery(tmp_path)
    first, _ = gallery.import_stream("first", BytesIO(b"same"), name="same.bin")
    second, _ = gallery.import_stream("second", BytesIO(b"same"), name="same.bin")
    _, shared_path = gallery.asset_path("first", first["id"])

    assert first["id"] != second["id"]
    assert first["storage_key"] == second["storage_key"]
    assert gallery.list_assets("third") == ()
    gallery.delete_asset("first", first["id"])
    assert shared_path.exists()
    gallery.delete_asset("second", second["id"])
    assert not shared_path.exists()


def test_gallery_api_import_and_content_are_principal_scoped(tmp_path):
    config = PlatformConfig.from_base_path(tmp_path)
    database = PlatformDatabase(config.paths.database_path)
    database.initialize()
    runtime = SimpleNamespace(config=config, database=database, events=None)
    principal = RequestPrincipal.legacy_local()
    app = FastAPI()
    app.include_router(create_gallery_router(lambda: runtime, lambda: principal))
    client = TestClient(app)

    collections = client.get("/gallery/collections").json()["items"]
    personal = next(item for item in collections if item["system_key"] == "personal")
    imported = client.post(
        "/gallery/assets/import",
        data={"collectionId": personal["id"]},
        files={"file": ("note.txt", b"hello gallery", "text/plain")},
    )

    assert imported.status_code == 201
    asset = imported.json()["asset"]
    assert asset["kind"] == "document"
    assert client.get(
        "/gallery/assets", params={"collectionId": personal["id"]}
    ).json()["items"][0]["id"] == asset["id"]
    content = client.get(f"/gallery/assets/{asset['id']}/content")
    assert content.content == b"hello gallery"
    assert content.headers["etag"] == asset["content_hash"]
    browser_transfer = client.post(
        f"/gallery/assets/{asset['id']}/browser-transfer"
    )
    assert browser_transfer.status_code == 200
    transfer_payload = browser_transfer.json()
    transfer_path = Path(transfer_payload["path"])
    assert transfer_path.read_bytes() == b"hello gallery"
    assert transfer_path.name == "note.txt"
    assert transfer_path.is_relative_to(
        config.paths.artifacts_path / "gallery-browser-transfers"
    )
    assert browser_transfer.headers["cache-control"] == "no-store"
    renamed = client.patch(
        f"/gallery/assets/{asset['id']}", json={"name": "renamed-note.txt"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "renamed-note.txt"

    project = client.post(
        "/gallery/collections", json={"name": "A very long project collection", "kind": "project"}
    ).json()
    assert client.post(
        f"/gallery/collections/{project['id']}/assets/{asset['id']}"
    ).status_code == 204
    assert client.delete(f"/gallery/collections/{project['id']}").status_code == 204
    assert client.get(f"/gallery/assets/{asset['id']}").status_code == 200
    protected = client.delete(f"/gallery/collections/{personal['id']}")
    assert protected.status_code == 422
    assert protected.json()["error"]["code"] == "gallery_system_collection_delete_forbidden"


def test_gallery_imports_authorized_workspace_artifact_into_active_collection(tmp_path):
    config = PlatformConfig.from_base_path(tmp_path)
    database = PlatformDatabase(config.paths.database_path)
    database.initialize()
    principal = RequestPrincipal.legacy_local()
    artifact_path = tmp_path / "generated.mp4"
    artifact_path.write_bytes(b"generated video")
    artifact = SimpleNamespace(
        id="art_video",
        session_id="ses_video",
        run_id="run_video",
        name="generated.mp4",
        media_type="video/mp4",
        uri="artifact://art_video",
    )

    class Workspace:
        def get_artifact(self, session_id, artifact_id):
            assert (session_id, artifact_id) == ("ses_video", "art_video")
            return artifact

        def artifact_path(self, selected):
            assert selected is artifact
            return artifact_path

    class ExtensionManager:
        sessions = SimpleNamespace(
            get=lambda session_id: SimpleNamespace(
                id=session_id, app_instance_id="appi_video"
            )
        )

        def require_instance_access(self, instance_id, selected_principal):
            assert instance_id == "appi_video"
            assert selected_principal.actor_user_id == principal.actor_user_id

    runtime = SimpleNamespace(
        config=config,
        database=database,
        events=None,
        workspace=Workspace(),
        extension_manager=ExtensionManager(),
    )
    app = FastAPI()
    app.include_router(create_gallery_router(lambda: runtime, lambda: principal))
    client = TestClient(app)
    personal = next(
        item
        for item in client.get("/gallery/collections").json()["items"]
        if item["system_key"] == "personal"
    )

    imported = client.post(
        "/gallery/assets/import-artifact/ses_video/art_video",
        json={
            "collectionId": personal["id"],
            "name": "final-cut.mp4",
            "sourceAppId": "ai2apps.video-studio",
        },
    )

    assert imported.status_code == 201
    asset = imported.json()["asset"]
    assert asset["name"] == "final-cut.mp4"
    assert asset["kind"] == "video"
    assert asset["source_ref"] == "artifact://art_video"
    assert client.get(
        "/gallery/assets", params={"collectionId": personal["id"]}
    ).json()["items"][0]["id"] == asset["id"]


def test_gallery_is_a_pinned_user_system_app_with_first_party_surface():
    manifest = next(item for item in SYSTEM_APP_MANIFESTS if item["id"] == "ai2apps.gallery")
    template = (WEB_ROOT / "templates/system_apps/gallery.html").read_text()
    mini_template = (WEB_ROOT / "templates/system_apps/gallery_mini.html").read_text()
    script = (WEB_ROOT / "static/js/gallery.js").read_text()
    bidi_script = (WEB_ROOT / "static/js/browser_bidi_client.js").read_text()
    stylesheet = (WEB_ROOT / "static/css/gallery.css").read_text()

    assert manifest["instances"] == {"mode": "singleton", "scope": "user"}
    assert manifest["entry"]["resource"] == "ai2apps:system/gallery"
    assert manifest["mini_entry"] == {
        "kind": "host",
        "resource": "ai2apps:system/gallery-mini",
        "placements": ["sidebar"],
    }
    assert manifest["navigation"]["pinned_default"] is True
    assert manifest["presentation"]["shell_sidebar"]["status"] == "active"
    assert 'data-app-id="ai2apps.gallery"' in template
    assert "data-client-environment" in template
    assert "gallery-preview-dialog" in template
    assert "openPreview(asset)" in template
    assert "movePreview(-1)" in template and "movePreview(1)" in template
    assert "startPreviewPan" in template and "wheelPreview" in template
    assert '@dblclick.prevent="togglePreviewZoom()"' in template
    assert "if (this.previewZoom <= 1) return;" in script
    assert "savePreviewName" in template
    assert "downloadAsset($event,previewAsset)" in template
    assert "previewAsset?.kind==='video'" in template
    assert "previewAsset?.kind==='audio'" in template
    assert 'data-gallery-surface="mini-entry"' in mini_template
    assert "browser_bidi_client.js" in mini_template
    assert "gallery.mini.browser_subtitle" in mini_template
    assert 'role="button" tabindex="0"' in mini_template
    assert '@dragend="finishBrowserAssetDrag(asset)"' in mini_template
    assert '@click="previewAssetFromMini(asset)"' in mini_template
    assert '@keydown.enter.prevent="previewAssetFromMini(asset)"' in mini_template
    assert '@dblclick="openAsset(asset)"' not in mini_template
    assert "/v1/platform/gallery" in script
    assert "openGalleryPreview(options)" in script
    assert "openRequestedPreview" in script
    assert "preloadPreviewAsset" in script
    assert "waitForPreviewPaint" in script
    assert "previewDialog" in template and "previewImage" in template
    assert "ai2apps.gallery.preview-ready" in script
    assert "if (event.key === 'Escape') { this.closePreview(); return; }" in script
    assert "ai2apps.gallery.preview-close" in script
    assert 'data-preview-asset-id' in template
    assert "Date.now() - this.dragStartedAt < 500" in script
    assert "application/x-ai2apps-gallery-asset" in script
    assert "application/x-ai2apps-gallery-drop-token" in script
    assert "beginPageResourceTransfer" in script
    assert "readPageResourceChunk" in script
    assert "browser-transfer" in script
    assert "applyGalleryAssetDrop" in script
    assert "this.ownsSession = false" in bidi_script
    assert "this.socket?.readyState === WebSocket.OPEN && this.ownsSession" in bidi_script
    assert r"audio)\\//i.test" in bidi_script
    assert r"replace(/\\n{3,}/g,'\\n\\n')" in bidi_script
    assert "Connect only when a page transfer starts" in script
    assert "syncBrowserPageContext" in script
    assert "Prefer the actual media element" in script
    assert "droppedMediaURLs" in script
    assert "data-lazy-src" in script and "data-srcset" in script
    assert "browserMediaImportPromise" in script
    assert "performBrowserPageMediaImport" in script
    assert "browserImportStatusText" in script
    assert "browserImportProgress" in script
    assert "gallery-mini-import-status" in mini_template
    assert '@click="dismissNotice()"' in mini_template
    assert "showNotice(message, tone, timeoutMs)" in script
    assert "this.showNotice(error?.message || String(error), 'error', 7000)" in script
    assert "this.pageClient === client" in script
    assert "media.currentSrc" in bidi_script
    assert "media.closest?.('a[href]')" in bidi_script
    assert "declaredFrequency.get(value)===1" in bidi_script
    assert "linkMatches.length?linkMatches:directMatches" in bidi_script
    assert "normalizeURL(requestedContext.url) === expected" in bidi_script
    assert "application/x-ai2apps-video-artifact" in script
    assert "importArtifactReference" in script
    assert "uri.startsWith('data:image/')" in script
    assert "'ai2apps.imagine-studio'" in script
    assert "imagine-studio\\/results\\/isr_" in script
    assert "ai2apps.gallery.collection-changed" in script
    assert "PATCH" in script and "previewImageTransform" in script
    assert "Desktop routes it to macOS Save As" in script
    assert "openFullGallery()" in mini_template
    assert "window.parent.ai2appsShell" in script
    assert "--gal-bg" in stylesheet
    assert 'class="gallery-selection-bar gallery-toolbar-selection"' in template
    assert ".gallery-toolbar{height:72px;min-height:72px;max-height:72px" in stylesheet
    assert ".gallery-toolbar-selection{position:static" in stylesheet
    assert "height:72px;min-height:72px;max-height:72px;display:flex" in stylesheet
    assert 'x-model="selectionOperation"' in template
    assert 'x-model="targetCollectionId"' in template
    assert "executeSelectedTransfer()" in template
    assert "ensureSelectionTarget()" in script
    assert "deleteCollection(collection)" in template
    assert "DELETE FROM gallery_collections" in (
        Path(__file__).parents[1] / "ai2apps/gallery/repository.py"
    ).read_text()
    assert ".gallery-collection-open span" in stylesheet
    assert "operation === 'move'" in script
    assert ".gallery-selection-actions button{height:38px" in stylesheet
    assert "--gal-type-body:13px" in stylesheet
    assert ".gallery-card-info strong{font-size:13px}" in stylesheet
    assert ".gallery-mini-tools select,.gallery-mini-tools input{font-size:12px}" in stylesheet
    assert ".gallery-preview-title strong{font-size:16px}" in stylesheet


def test_gallery_builtin_host_mini_entry_can_be_mounted():
    mount = {
        "id": "mount_gallery",
        "app_instance_id": "appi_gallery",
        "renderer": "host",
        "resource": "ai2apps:system/gallery-mini",
        "placement": "sidebar",
        "source": "builtin",
    }

    payload = _shell_mount_payload(None, mount)

    assert payload["content_url"] == "/admin/app-content/ai2apps.gallery?surface=mini"
    with pytest.raises(HTTPException, match="Unsupported host mount"):
        _shell_mount_payload(None, {**mount, "source": "package"})


def test_gallery_has_matching_english_and_chinese_translations():
    english = json.loads((WEB_ROOT / "i18n/en.json").read_text())
    chinese = json.loads((WEB_ROOT / "i18n/zh.json").read_text())
    english_keys = {key for key in english if key.startswith("gallery.")}
    chinese_keys = {key for key in chinese if key.startswith("gallery.")}
    source = "\n".join(
        (WEB_ROOT / path).read_text()
        for path in (
            "templates/system_apps/gallery.html",
            "templates/system_apps/gallery_mini.html",
            "static/js/gallery.js",
        )
    )

    assert english_keys == chinese_keys
    assert len(english_keys) >= 75
    assert all(f"gallery.collection.{key}" in english_keys for key in (
        "recent", "downloads", "public", "personal", "trash",
    ))
    assert all(f"gallery.kind.{key}" in english_keys for key in (
        "image", "video", "audio", "web", "document", "file",
    ))
    assert not any("\u4e00" <= character <= "\u9fff" for character in source)
