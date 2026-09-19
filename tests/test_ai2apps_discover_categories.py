from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from ai2apps.api.packages import _filter_catalog_content
from ai2apps.packages.contract_v1 import PackageContractError, build_package
from ai2apps.packages.discovery import (
    LEGACY_MODEL_DISCOVERY,
    LEGACY_MODEL_INSTALLS,
    LEGACY_MODEL_PROFILES,
    catalog_discovery,
    catalog_model_install,
    catalog_model_profile,
    matches_model_category,
)
from ai2apps.packages.registry import RegistryPackageManager


def _model_source(tmp_path, *, package_id="example/new-model", version="1.0.0"):
    source = tmp_path / package_id.replace("/", "-")
    source.mkdir()
    (source / "service.json").write_text(
        json.dumps(
            {
                "schema": "ai2apps.service/v1",
                "id": package_id.replace("/", "."),
                "runtime": {"mode": "process", "protocol": "ai2apps-model-worker/v1"},
                "models": [{
                    "id": package_id.replace("/", ".") + "/default",
                    "model_type": "llm",
                    "weights": {
                        "provider": "huggingface",
                        "repo_id": "example/model",
                        "revision": "a" * 40,
                    },
                }],
            }
        ),
        encoding="utf-8",
    )
    (source / "ai2apps.json").write_text(
        json.dumps(
            {
                "schemaVersion": "ai2apps.package-manifest.v1",
                "package": {
                    "id": package_id,
                    "type": "service",
                    "version": version,
                    "displayName": "Model fixture",
                },
                "compatibility": {"ai2apps": ">=0.1.0 <2.0.0"},
                "entrypoints": [
                    {"name": "service", "kind": "service", "path": "service.json"}
                ],
                "permissions": [],
                "dependencies": [],
                "files": [],
            }
        ),
        encoding="utf-8",
    )
    return source


def _add_model_metadata(manifest):
    manifest["discovery"] = {
        "kind": "model",
        "categories": ["text"],
        "tasks": ["text-generation"],
    }
    manifest["modelProfile"] = {
        "sizeBytes": 4_000_000_000,
        "minimumMemoryBytes": 8_000_000_000,
        "scores": {"speed": 4, "capability": 3},
        "benchmark": {
            "label": "Publisher benchmark v1",
            "device": "Apple M4 Max 64 GB",
        },
    }
    service_key = manifest["package"]["id"].replace("/", ".")
    manifest["modelInstall"] = {
        "serviceKey": service_key,
        "models": [{
            "id": service_key + "/default",
            "label": "Default",
            "recommended": True,
        }],
    }


def _mini_app_source(tmp_path):
    source = tmp_path / "mini-app-package"
    source.mkdir()
    (source / "web").mkdir()
    (source / "web" / "index.html").write_text("<main>App</main>", encoding="utf-8")
    (source / "web" / "transcribe.html").write_text(
        "<main>Transcribe</main>", encoding="utf-8"
    )
    (source / "app.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "ai2apps.app/v1",
                "id": "example.studio-suite",
                "name": "Studio Suite",
                "version": "1.0.0",
                "entry": {"kind": "sandbox", "resource": "web/index.html"},
                "mini_apps": [
                    {
                        "schema": "ai2apps.mini-app/v1",
                        "id": "example.audio.transcribe",
                        "name": "Detailed Transcription",
                        "version": "1.0.0",
                        "kind": "project",
                        "icon": "captions",
                        "entry": {
                            "kind": "sandbox",
                            "resource": "web/transcribe.html",
                        },
                        "placements": [
                            {
                                "studio": "ai2apps.video-studio",
                                "category": "audio",
                            }
                        ],
                        "catalog": {"categories": ["audio", "document"]},
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (source / "ai2apps.json").write_text(
        json.dumps(
            {
                "schemaVersion": "ai2apps.package-manifest.v1",
                "package": {
                    "id": "example/studio-suite",
                    "type": "app",
                    "version": "1.0.0",
                    "displayName": "Studio Suite",
                },
                "compatibility": {"ai2apps": ">=0.1.0 <2.0.0"},
                "entrypoints": [
                    {"name": "app", "kind": "app", "path": "web/index.html"}
                ],
                "permissions": [],
                "dependencies": [],
                "files": [],
            }
        ),
        encoding="utf-8",
    )
    return source


def test_app_package_builds_signed_mini_app_catalog_from_app_yaml(tmp_path):
    inspected = build_package(_mini_app_source(tmp_path), tmp_path / "suite.ai2app")

    assert inspected.manifest["package"]["type"] == "app"
    assert inspected.manifest["miniApps"] == [
        {
            "componentId": "example.audio.transcribe",
            "displayName": "Detailed Transcription",
            "version": "1.0.0",
            "lifecycleKind": "project",
            "categories": ["audio", "document"],
            "placements": ["ai2apps.video-studio"],
            "icon": "captions",
        }
    ]


def test_app_package_rejects_mismatched_manual_mini_app_catalog(tmp_path):
    source = _mini_app_source(tmp_path)
    manifest_path = source / "ai2apps.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["miniApps"] = [{"componentId": "example.wrong"}]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PackageContractError) as error:
        build_package(source, tmp_path / "suite.ai2app")

    assert error.value.code == "mini_app_catalog_mismatch"


def test_discover_client_exposes_mini_apps_as_parallel_catalog():
    script = (Path(__file__).parents[1] / "ai2apps/web/static/js/discover.js").read_text()
    template = (
        Path(__file__).parents[1]
        / "ai2apps/web/templates/system_apps/discover.html"
    ).read_text()

    assert "{ value: 'mini-app'" in script
    assert "function expandPackages" in script
    assert "item.packageId + '#' + component.componentId" in script
    assert "type==='mini-app'" in template


def test_discover_client_text_filter_keeps_conversational_multimodal_models():
    script = (Path(__file__).parents[1] / "ai2apps/web/static/js/discover.js").read_text()

    assert "this.modelCategory === 'text'" in script
    assert "(discovery.tasks || []).includes('multimodal-conversation')" in script


def test_discover_client_uses_shared_cursor_pagination():
    script = (Path(__file__).parents[1] / "ai2apps/web/static/js/discover.js").read_text()
    template = (
        Path(__file__).parents[1]
        / "ai2apps/web/templates/system_apps/discover.html"
    ).read_text()

    assert "function catalogPage" in script
    assert "nextCursor" in script
    assert "const CATALOG_PAGE_SIZE = 24" in script
    assert "new URLSearchParams({ limit: String(CATALOG_PAGE_SIZE) })" in script
    assert "params.set('cursor', cursor)" in script
    assert "async loadMore()" in script
    assert "mergeCards" in script
    assert "LOCAL_PAGE_CURSOR" in script
    assert "legacyParams.set('limit', '100')" in script
    assert "item.packageId + '#' + component.componentId" in script
    assert "@click=\"loadMore()\"" in template


def test_installed_legacy_app_projects_mini_apps_without_reinstall(tmp_path):
    app_manifest = yaml.safe_load(
        (_mini_app_source(tmp_path) / "app.yaml").read_text(encoding="utf-8")
    )
    extension_manager = SimpleNamespace(
        repository=SimpleNamespace(
            effective=lambda _kind, _key: SimpleNamespace(manifest=app_manifest)
        )
    )
    manager = RegistryPackageManager(
        cloud=None,
        root=tmp_path / "state",
        secrets=None,
        extension_manager=extension_manager,
        service_manager=None,
    )
    manager._save_state(
        {
            "metadataVersion": 1,
            "installed": {
                "example/studio-suite": {
                    "packageId": "example/studio-suite",
                    "packageType": "app",
                    "runtimeKey": "example.studio-suite",
                    "displayName": "Studio Suite",
                    "version": "1.0.0",
                }
            },
        }
    )

    installed = manager.installed()

    assert installed[0]["miniApps"][0]["componentId"] == "example.audio.transcribe"


def test_new_model_package_requires_signed_discovery_metadata(tmp_path):
    source = _model_source(tmp_path)

    with pytest.raises(PackageContractError) as error:
        build_package(source, tmp_path / "model.ai2service")

    assert error.value.code == "model_discovery_required"


def test_new_model_package_accepts_valid_discovery_metadata(tmp_path):
    source = _model_source(tmp_path)
    manifest_path = source / "ai2apps.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _add_model_metadata(manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    inspected = build_package(source, tmp_path / "model.ai2service")

    assert inspected.manifest["discovery"] == manifest["discovery"]
    assert inspected.manifest["modelProfile"] == manifest["modelProfile"]
    assert inspected.manifest["modelInstall"] == manifest["modelInstall"]


def test_version_bounded_model_install_can_be_omitted_for_cloud_compatibility(
    tmp_path,
):
    source = _model_source(
        tmp_path,
        package_id="ai2apps/model-minimax-h3",
        version="0.9.0",
    )
    manifest_path = source / "ai2apps.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _add_model_metadata(manifest)
    manifest["discovery"] = {
        key: value
        for key, value in LEGACY_MODEL_DISCOVERY[
            "ai2apps/model-minimax-h3"
        ].items()
        if key != "throughVersion"
    }
    manifest["modelProfile"] = {
        key: value
        for key, value in LEGACY_MODEL_PROFILES[
            "ai2apps/model-minimax-h3"
        ].items()
        if key != "throughVersion"
    }
    manifest["modelInstall"] = {
        key: value
        for key, value in LEGACY_MODEL_INSTALLS[
            "ai2apps/model-minimax-h3"
        ].items()
        if key != "throughVersion"
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    inspected = build_package(
        source,
        tmp_path / "model.ai2service",
        include_model_install_catalog=False,
    )

    assert "modelInstall" not in inspected.manifest
    assert inspected.manifest["discovery"] == manifest["discovery"]


def test_new_model_package_requires_signed_model_profile(tmp_path):
    source = _model_source(tmp_path)
    manifest_path = source / "ai2apps.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["discovery"] = {
        "kind": "model",
        "categories": ["text"],
        "tasks": ["text-generation"],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PackageContractError) as error:
        build_package(source, tmp_path / "model.ai2service")

    assert error.value.code == "model_profile_required"


def test_new_model_package_requires_signed_model_install(tmp_path):
    source = _model_source(tmp_path)
    manifest_path = source / "ai2apps.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _add_model_metadata(manifest)
    manifest.pop("modelInstall")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PackageContractError) as error:
        build_package(source, tmp_path / "model.ai2service")

    assert error.value.code == "model_install_required"


def test_published_legacy_model_release_can_use_bounded_install_metadata(tmp_path):
    source = _model_source(
        tmp_path,
        package_id="ai2apps/model-demucs-mlx",
        version="0.1.0",
    )
    manifest_path = source / "ai2apps.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["discovery"] = {
        key: value
        for key, value in LEGACY_MODEL_DISCOVERY[
            "ai2apps/model-demucs-mlx"
        ].items()
        if key != "throughVersion"
    }
    manifest["modelProfile"] = {
        key: value
        for key, value in LEGACY_MODEL_PROFILES[
            "ai2apps/model-demucs-mlx"
        ].items()
        if key != "throughVersion"
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    built = build_package(source, tmp_path / "legacy-demucs.ai2service")

    assert built.manifest["package"]["version"] == "0.1.0"
    assert "modelInstall" not in built.manifest


def test_model_profile_rejects_out_of_range_scores(tmp_path):
    source = _model_source(tmp_path)
    manifest_path = source / "ai2apps.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _add_model_metadata(manifest)
    manifest["modelProfile"]["scores"]["speed"] = 6
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PackageContractError) as error:
        build_package(source, tmp_path / "model.ai2service")

    assert error.value.code == "manifest_invalid"


def test_non_model_service_cannot_claim_model_discovery(tmp_path):
    source = _model_source(tmp_path)
    service_path = source / "service.json"
    service = json.loads(service_path.read_text(encoding="utf-8"))
    service["models"] = []
    service_path.write_text(json.dumps(service), encoding="utf-8")
    manifest_path = source / "ai2apps.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _add_model_metadata(manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PackageContractError) as error:
        build_package(source, tmp_path / "service.ai2service")

    assert error.value.code == "model_discovery_invalid"


def test_legacy_model_release_is_classified_without_manifest_upgrade(tmp_path):
    source = _model_source(
        tmp_path,
        package_id="ai2apps/model-qwen3-asr-06b",
        version="0.1.1",
    )

    inspected = build_package(source, tmp_path / "legacy.ai2service")
    row = RegistryPackageManager._decorate_catalog_compatibility(
        {"manifest": inspected.manifest}
    )

    assert row["discovery"]["categories"] == ["speech"]
    assert row["discovery"]["tasks"] == ["speech-recognition"]
    assert row["discovery"]["source"] == "legacy-map"
    assert row["modelProfile"]["scores"] == {"speed": 5, "capability": 4}
    assert row["modelProfile"]["source"] == "legacy-map"
    assert row["modelInstall"]["source"] == "legacy-map"


def test_legacy_package_next_release_must_adopt_discovery_metadata(tmp_path):
    source = _model_source(
        tmp_path,
        package_id="ai2apps/model-qwen3-asr-06b",
        version="0.1.2",
    )

    with pytest.raises(PackageContractError) as error:
        build_package(source, tmp_path / "legacy-next.ai2service")

    assert error.value.code == "model_discovery_required"


def test_catalog_content_filter_separates_models_from_other_services():
    rows = [
        {
            "packageId": "ai2apps/model-qwen-image-mlx",
            "packageType": "service",
            "version": "0.1.1",
        },
        {
            "packageId": "ai2apps/runtime-omlx",
            "packageType": "service",
            "version": "1.5.7",
        },
    ]
    decorated = RegistryPackageManager._decorate_catalog_compatibility(rows)

    models = _filter_catalog_content(
        decorated, content="model", model_category="image", model_task=None, limit=48
    )
    services = _filter_catalog_content(
        decorated, content="service", model_category=None, model_task=None, limit=48
    )

    assert [item["packageId"] for item in models] == [
        "ai2apps/model-qwen-image-mlx"
    ]
    assert [item["packageId"] for item in services] == ["ai2apps/runtime-omlx"]
    assert catalog_discovery(models[0])["kind"] == "model"


def test_catalog_model_task_filter_distinguishes_tts_from_asr():
    rows = RegistryPackageManager._decorate_catalog_compatibility(
        [
            {
                "packageId": "ai2apps/model-qwen3-tts-17b",
                "packageType": "service",
                "version": "0.1.1",
            },
            {
                "packageId": "ai2apps/model-qwen3-asr-06b",
                "packageType": "service",
                "version": "0.1.1",
            },
        ]
    )

    tts = _filter_catalog_content(
        rows,
        content="model",
        model_category="speech",
        model_task="speech-synthesis",
        limit=48,
    )
    asr = _filter_catalog_content(
        rows,
        content="model",
        model_category="speech",
        model_task="speech-recognition",
        limit=48,
    )

    assert [item["packageId"] for item in tts] == ["ai2apps/model-qwen3-tts-17b"]
    assert [item["packageId"] for item in asr] == ["ai2apps/model-qwen3-asr-06b"]


def test_text_category_includes_multimodal_conversation_models():
    rows = RegistryPackageManager._decorate_catalog_compatibility(
        [
            {
                "packageId": "ai2apps/model-qwen36-35b",
                "packageType": "service",
                "version": "0.3.2",
            },
            {
                "packageId": "ai2apps/model-qwen38",
                "packageType": "service",
                "version": "0.3.2",
            },
            {
                "packageId": "ai2apps/model-qwen-image-mlx",
                "packageType": "service",
                "version": "0.1.1",
            },
        ]
    )

    text_models = _filter_catalog_content(
        rows,
        content="model",
        model_category="text",
        model_task=None,
        limit=48,
    )

    assert [item["packageId"] for item in text_models] == [
        "ai2apps/model-qwen36-35b",
        "ai2apps/model-qwen38",
    ]
    assert matches_model_category(rows[1]["discovery"], "multimodal") is True
    assert matches_model_category(rows[2]["discovery"], "text") is False


def test_internal_legacy_table_covers_every_current_model_package():
    package_root = Path(__file__).parents[1] / "packages"
    missing = []
    for manifest_path in package_root.glob("*/ai2apps.json"):
        service_path = manifest_path.with_name("service.yaml")
        if not service_path.is_file():
            continue
        service = yaml.safe_load(service_path.read_text(encoding="utf-8"))
        if not isinstance(service, dict) or not service.get("models"):
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        package = manifest["package"]
        if all(key in manifest for key in ("discovery", "modelProfile", "modelInstall")):
            # Signed source metadata supersedes legacy fallback tables.
            from ai2apps.packages.discovery import validate_discovery, validate_model_profile, validate_model_install
            validate_discovery(manifest["discovery"], package_type=package["type"])
            validate_model_profile(manifest["modelProfile"])
            validate_model_install(manifest["modelInstall"])
            continue
        discovery = LEGACY_MODEL_DISCOVERY.get(package["id"])
        profile = LEGACY_MODEL_PROFILES.get(package["id"])
        install = LEGACY_MODEL_INSTALLS.get(package["id"])
        if (
            discovery is None
            or discovery["throughVersion"] != package["version"]
            or profile is None
            or profile["throughVersion"] != package["version"]
            or install is None
            or install["throughVersion"] != package["version"]
        ):
            missing.append(f"{package['id']}@{package['version']}")

    assert missing == []


def test_chat_profile_uses_checkpoint_payload_and_cached_memory():
    expected = {
        "deepseek-v4-flash": (159635168163, 48),
        "deepseek-v4-flash-2bit": (96531568280, 32),
        "deepseek-v41-flash": (510320301313, 96),
        "glm5-3-flash-4bit-mtp": (181750094029, 72),
        "ornith15-35b-a3b-4bit-vision": (20422831594, 32),
        "qwen38": (23444503536, 24),
        "qwen38-flash-next-4bit": (111602367013, 64),
    }
    for name, (size, memory) in expected.items():
        row = LEGACY_MODEL_PROFILES["ai2apps/model-" + name]
        profile = catalog_model_profile({"package": {
            "id": "ai2apps/model-" + name, "version": row["throughVersion"],
        }})
        assert profile["sizeBytes"] == size
        assert profile["minimumMemoryBytes"] == memory * 1024**3
        assert profile["source"] == "legacy-map"
        assert profile["runtimeMemoryBytes"] < profile["minimumMemoryBytes"]
        # Catalog enrichment may run twice; runtime facts must survive normalization.
        assert catalog_model_profile({"modelProfile": profile}) == profile


def test_runtime_memory_is_separate_from_install_minimum():
    from ai2apps.packages.discovery import validate_model_profile

    profile = dict(LEGACY_MODEL_PROFILES["ai2apps/model-glm5-3-flash-4bit-mtp"])
    profile.pop("throughVersion")
    assert validate_model_profile(profile)["runtimeMemoryBytes"] == 55 * 1024**3
    assert profile["minimumMemoryBytes"] == 72 * 1024**3
    profile["runtimeMemoryBytes"] = True
    with pytest.raises(ValueError):
        validate_model_profile(profile)


def test_catalog_model_profile_rejects_legacy_mapping_after_version_cap():
    assert catalog_model_profile(
        {
            "packageId": "ai2apps/model-qwen3-asr-06b",
            "packageType": "service",
            "version": "0.1.1",
        }
    ) is not None
    assert catalog_model_profile(
        {
            "packageId": "ai2apps/model-qwen3-asr-06b",
            "packageType": "service",
            "version": "0.1.2",
        }
    ) is None


def test_catalog_model_install_rejects_legacy_mapping_after_version_cap():
    assert catalog_model_install({
        "packageId": "ai2apps/model-qwen3-asr-06b",
        "packageType": "service",
        "version": "0.1.1",
    }) is not None
    assert catalog_model_install({
        "packageId": "ai2apps/model-qwen3-asr-06b",
        "packageType": "service",
        "version": "0.1.2",
    }) is None


@pytest.mark.parametrize("package_id,row", LEGACY_MODEL_INSTALLS.items())
def test_catalog_install_mapping_does_not_depend_on_discovery(package_id, row):
    value = {"package": {"packageId": package_id,
                         "packageType": "service",
                         "latestVersion": row["throughVersion"]}}
    decorated = RegistryPackageManager._decorate_catalog_compatibility(value)
    assert decorated["modelInstall"] == catalog_model_install(value)


@pytest.mark.parametrize("package_id,version", [
    ("ai2apps/model-flux2-klein-mlx", "99.0.0"),
    ("example/unknown-model", "0.1.0"),
])
def test_catalog_compatibility_does_not_invent_install_plan(package_id, version):
    decorated = RegistryPackageManager._decorate_catalog_compatibility({
        "package": {"packageId": package_id, "packageType": "service",
                    "latestVersion": version},
    })
    assert "modelInstall" not in decorated
