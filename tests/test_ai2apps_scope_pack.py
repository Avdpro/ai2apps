import hashlib
import json
import sys
from pathlib import Path

from ai2apps.model_installer import AI2AppsInstaller
from omlx.model_discovery import _repair_package_owned_scope_profile

PACKAGE_ROOT = Path(__file__).parents[1] / "packages"
for name in ("omlx-model-deepseek-v4-flash", "omlx-model-deepseek-v4-flash-2bit", "omlx-model-qwen36-cached-moe"):
    sys.path.insert(0, str(PACKAGE_ROOT / name / "src"))
from omlx_model_deepseek_v4_flash import DeepSeekV4FlashAdapter  # noqa: E402
from omlx_model_deepseek_v4_flash_2bit import DeepSeekV4Flash2BitAdapter  # noqa: E402
from omlx_model_qwen36_cached_moe import Qwen36CachedMoeAdapter  # noqa: E402


def _install_cached_moe_registry(monkeypatch):
    from omlx.model_adapters import ModelAdapterRegistry
    from omlx.model_adapters import registry as registry_module

    registry = ModelAdapterRegistry(load_entry_points=False)
    for adapter in (DeepSeekV4FlashAdapter(), DeepSeekV4Flash2BitAdapter(), Qwen36CachedMoeAdapter()):
        registry.register(adapter)
    monkeypatch.setattr(registry_module, "_default_registry", registry)


def test_release_catalog_uses_packaged_scope_packs(monkeypatch):
    _install_cached_moe_registry(monkeypatch)
    monkeypatch.delenv("OMLX_DEEPSEEK_V4_SCOPE_PROFILE", raising=False)
    monkeypatch.delenv("OMLX_QWEN36_SCOPE_PROFILE", raising=False)

    catalog = AI2AppsInstaller.catalog()

    assert [item["id"] for item in catalog] == [
        "deepseek-v4-flash",
        "deepseek-v4-flash-2bit",
        "qwen3.6-35b-a3b-4bit",
    ]
    assert all(item["engine_ready"] for item in catalog)
    assert all(item["scope_pack"]["version"] == "2026.08.09.1" for item in catalog)
    assert all(len(item["sources"][0]["revision"]) == 40 for item in catalog)


def test_packaged_scope_pack_profiles_match_manifests():
    roots = (
        PACKAGE_ROOT / "omlx-model-deepseek-v4-flash" / "src" / "omlx_model_deepseek_v4_flash" / "assets",
        PACKAGE_ROOT / "omlx-model-qwen36-cached-moe" / "src" / "omlx_model_qwen36_cached_moe" / "assets",
    )
    for root in roots:
        manifest = json.loads((root / "scope-pack.json").read_text())
        profile = root / manifest["profile"]["file"]

        assert manifest["format"] == "ai2apps-scope-pack"
        assert manifest["version"] == 1
        assert hashlib.sha256(profile.read_bytes()).hexdigest() == (
            manifest["profile"]["sha256"]
        )
        for model_id in manifest["compatibility"]["model_ids"]:
            assert len(
                manifest["compatibility"]["source_revisions"][model_id]
            ) == 40


def test_packaged_profiles_cover_every_declared_scope_and_layer():
    deepseek_root = PACKAGE_ROOT / "omlx-model-deepseek-v4-flash" / "src" / "omlx_model_deepseek_v4_flash" / "assets"
    qwen_root = PACKAGE_ROOT / "omlx-model-qwen36-cached-moe" / "src" / "omlx_model_qwen36_cached_moe" / "assets"
    deepseek = json.loads(
        (deepseek_root / "scope-profile.json").read_text()
    )
    qwen = json.loads(
        (qwen_root / "scope-profile.json").read_text()
    )

    assert len(deepseek["scopes"]) == 10
    for layers in deepseek["scopes"].values():
        assert set(layers) == {str(layer) for layer in range(3, 43)}
        assert all(len(experts) >= 60 for experts in layers.values())

    assert set(qwen["phases"]) == {"prefill", "decode"}
    assert set(qwen["phases"]["prefill"]) == set(qwen["phases"]["decode"])
    assert len(qwen["phases"]["decode"]) == 10
    for phase in qwen["phases"].values():
        for layers in phase.values():
            assert set(layers) == {str(layer) for layer in range(40)}
            assert all(len(experts) >= 120 for experts in layers.values())


def test_legacy_package_asset_reference_is_repaired_into_model(tmp_path, monkeypatch):
    _install_cached_moe_registry(monkeypatch)
    model_dir = tmp_path / "DeepSeek-V4-Flash"
    model_dir.mkdir()
    manifest_path = model_dir / "ai2apps-model.json"
    candidate = {
        "format": "ai2apps-cache-moe-model",
        "version": 2,
        "model_id": "deepseek-v4-flash",
        "source": {
            "repo_id": "deepseek-ai/DeepSeek-V4-Flash",
            "revision": "60d8d70770c6776ff598c94bb586a859a38244f1",
        },
        "scope": {"profile": str(tmp_path / "removed-package" / "scope-profile.json"), "default": "general"},
    }
    manifest_path.write_text(json.dumps(candidate))

    _repair_package_owned_scope_profile(model_dir, manifest_path, candidate)

    repaired = json.loads(manifest_path.read_text())
    profile = Path(repaired["scope"]["profile"])
    assert profile.is_file()
    assert profile.parent == model_dir / ".ai2apps" / "scope-assets"
    assert repaired["scope"]["pack"]["sha256"] == profile.stem
    assert repaired["execution_modes"] == ["cached", "full"]
