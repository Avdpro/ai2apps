import hashlib
import json
from pathlib import Path

from ai2apps.model_installer import AI2AppsInstaller


def test_release_catalog_uses_packaged_scope_packs(monkeypatch):
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
    engines = Path(__file__).parents[1] / "ai2apps" / "engines"
    for family in ("deepseek_v4_flash", "qwen3_6_35b_a3b"):
        root = engines / family
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
    engines = Path(__file__).parents[1] / "ai2apps" / "engines"
    deepseek = json.loads(
        (engines / "deepseek_v4_flash" / "scope-profile.json").read_text()
    )
    qwen = json.loads(
        (engines / "qwen3_6_35b_a3b" / "scope-profile.json").read_text()
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
