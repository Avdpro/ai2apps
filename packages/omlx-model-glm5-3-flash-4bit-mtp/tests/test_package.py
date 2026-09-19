import importlib.util
import hashlib
import json
from pathlib import Path

import yaml

from ai2apps.model_worker.protocol import ModelWorkerError


PACKAGE = Path(__file__).parents[1]


def test_manifest_id_version_and_runtime_dependency_match_service():
    manifest = json.loads((PACKAGE / "ai2apps.json").read_text())
    service = yaml.safe_load((PACKAGE / "service.yaml").read_text())
    assert manifest["package"]["id"] == "ai2apps/model-glm5-3-flash-4bit-mtp"
    assert manifest["package"]["version"] == service["version"] == "0.1.5"
    assert manifest["compatibility"]["ai2apps"] == ">=0.1.0 <2.0.0"
    assert manifest["dependencies"] == [
        {
            "packageId": "ai2apps/runtime-omlx",
            "version": ">=1.7.5 <2.0.0",
            "optional": False,
        }
    ]
    assert service["requires"]["services"][0]["version"] == ">=1.7.5,<2.0.0"
    assert service["models"][0]["metadata"]["reasoning"]["mode"] == "required"
    assert manifest["modelProfile"]["minimumMemoryBytes"] == 72 * 1024**3


def test_checkpoint_is_dual_source_and_immutable():
    distribution = json.loads(
        (PACKAGE / "META/checkpoint-distribution.json").read_text()
    )
    model = yaml.safe_load((PACKAGE / "service.yaml").read_text())["models"][0]
    sources = {item["type"]: item for item in distribution["sourceRepositories"]}
    assert set(sources) == {"huggingface", "modelscope"}
    assert all(len(item["revision"]) == 40 for item in sources.values())
    assert sources["modelscope"]["revision"] == (
        "f928d2572dc6d5706d61d43acf27e613cc28320a"
    )
    assert model["weights"]["distribution_id"] == distribution["distributionId"]


def test_glm_cache_recipe_and_product_defaults():
    model = yaml.safe_load((PACKAGE / "service.yaml").read_text())["models"][0]
    preparation = model["weights"]["preparation"]
    assert preparation["family"] == "glm5_next"
    assert preparation["conversion"]["variant"] == (
        "glm5-next-affine-q4-gate-up-fused-v2"
    )
    assert preparation["dynamic_slots"] == 96
    assert preparation["hot_slots"] == 16
    assert preparation["vision_l1_reserve_slots"] == 16
    assert preparation["execution_modes"] == ["cached"]
    assert model["metadata"]["execution_modes"] == ["cached"]


def test_worker_adapter_defaults_to_exact_dynamic_multimodal_path():
    path = PACKAGE / "src/worker_adapter.py"
    spec = importlib.util.spec_from_file_location("glm5_package_worker_adapter", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.Glm5DynamicChatAdapter._TIER_SLOTS == {
        "lean": 80,
        "balanced": 96,
    }
    source = path.read_text()
    assert 'os.environ["OMLX_GLM5_BOOST_MODE"] = "natural"' in source
    assert 'os.environ.setdefault("OMLX_GLM5_MTP_ENABLED", "0")' in source


def test_auto_memory_tier_preserves_balanced_and_downgrades_to_lean(monkeypatch):
    path = PACKAGE / "src/worker_adapter.py"
    spec = importlib.util.spec_from_file_location("glm5_auto_tier_adapter", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(module, "get_total_memory_bytes", lambda: 128 * 1024**3)
    assert module._resolve_memory_tier("auto") == "balanced"
    monkeypatch.setattr(module, "get_total_memory_bytes", lambda: 72 * 1024**3)
    assert module._resolve_memory_tier("auto") == "lean"


def test_auto_memory_tier_rejects_device_below_lean_floor(monkeypatch):
    path = PACKAGE / "src/worker_adapter.py"
    spec = importlib.util.spec_from_file_location("glm5_auto_tier_floor", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "get_total_memory_bytes", lambda: 64 * 1024**3)

    try:
        module._resolve_memory_tier("auto")
    except ModelWorkerError as exc:
        assert exc.code == "insufficient_memory"
    else:
        raise AssertionError("64 GiB must not pass the GLM Lean reserve floor")


def test_scope_pack_is_package_owned_and_matches_profile():
    profile_path = (
        PACKAGE
        / "src/omlx_model_glm5_3_flash_4bit_mtp/assets/scope-profile.json"
    )
    pack_path = profile_path.with_name("scope-pack.json")
    service = yaml.safe_load((PACKAGE / "service.yaml").read_text())
    engine = service["models"][0]["weights"]["preparation"]["engine"]
    assert engine["scope_asset"] == profile_path.relative_to(PACKAGE).as_posix()
    assert engine["scope_pack"] == pack_path.relative_to(PACKAGE).as_posix()

    profile = json.loads(profile_path.read_text())
    pack = json.loads(pack_path.read_text())
    assert profile_path.stat().st_size < 2 * 1024 * 1024
    assert profile["format"] == "omlx-glm5-dynamic-scope-profile"
    assert "general" in profile["scopes"]
    assert pack["format"] == "ai2apps-scope-pack"
    assert pack["profile"]["sha256"] == hashlib.sha256(
        profile_path.read_bytes()
    ).hexdigest()
    assert pack["compatibility"]["source_revisions"] == {
        "glm5-3-flash-mlx-4bit-mtp": "a4d3f3e489a12893e0056a5b9494cc76194a220a"
    }
