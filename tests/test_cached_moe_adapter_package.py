"""Coverage for independently publishable one-model adapter packages."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from omlx.model_adapters import ModelAdapterRegistry, adapter_context

ROOT = Path(__file__).parents[1]
PACKAGES = (
    ("omlx-model-deepseek-v4-flash", "omlx_model_deepseek_v4_flash", "DeepSeekV4FlashAdapter", "deepseek-v4-flash"),
    ("omlx-model-deepseek-v4-flash-2bit", "omlx_model_deepseek_v4_flash_2bit", "DeepSeekV4Flash2BitAdapter", "deepseek-v4-flash-2bit"),
    ("omlx-model-qwen36-cached-moe", "omlx_model_qwen36_cached_moe", "Qwen36CachedMoeAdapter", "qwen3.6-35b-a3b-4bit"),
)
for package, _, _, _ in PACKAGES:
    sys.path.insert(0, str(ROOT / "packages" / package / "src"))

from omlx_model_deepseek_v4_flash import DeepSeekV4FlashAdapter  # noqa: E402
from omlx_model_deepseek_v4_flash_2bit import DeepSeekV4Flash2BitAdapter  # noqa: E402
from omlx_model_qwen36_cached_moe import Qwen36CachedMoeAdapter  # noqa: E402

ADAPTERS = (DeepSeekV4FlashAdapter, DeepSeekV4Flash2BitAdapter, Qwen36CachedMoeAdapter)


def test_each_package_exposes_exactly_one_recipe_and_self_contained_assets():
    for adapter_type, (package, _, _, recipe_id) in zip(ADAPTERS, PACKAGES, strict=True):
        recipes = adapter_type().installation_recipes()
        assert len(recipes) == 1
        recipe = recipes[0]
        assert recipe["id"] == recipe_id
        assert recipe["execution_modes"] == ("cached", "full")
        if recipe_id.startswith("deepseek-"):
            assert recipe["storage_policies"] == (
                "keep_source",
                "delete_after",
                "stream_reclaim",
            )
        else:
            assert recipe["storage_policies"] == ("keep_source",)
        profile = Path(recipe["engine"]["scope_asset"])
        pack_path = Path(recipe["engine"]["scope_pack"])
        pack = json.loads(pack_path.read_text())
        assert profile.is_file() and pack_path.is_file()
        assert hashlib.sha256(profile.read_bytes()).hexdigest() == pack["profile"]["sha256"]
        manifest = json.loads((ROOT / "packages" / package / "release-checkpoints.json").read_text())
        checkpoints = manifest[f"{package}@0.1.0"]
        assert len(checkpoints) == 1
        assert checkpoints[0]["recipeId"] == recipe_id
        assert checkpoints[0]["installMode"] == "cache-moe"


def test_registry_combines_three_independent_packages_without_match_overlap():
    registry = ModelAdapterRegistry(load_entry_points=False)
    for adapter in ADAPTERS:
        registry.register(adapter())
    assert len(registry.installation_recipes()) == 3
    assert [item.adapter_id for item in registry.matching(adapter_context("/tmp/ds", {"model_type": "deepseek_v4"}))] == ["deepseek-v4-flash"]
    assert [item.adapter_id for item in registry.matching(adapter_context("/tmp/ds2", {"model_type": "deepseek_v4", "quantization": {"bits": 2}}))] == ["deepseek-v4-flash-2bit"]


def test_package_discovery_does_not_import_mlx():
    python_path = ":".join(str(ROOT / "packages" / item[0] / "src") for item in PACKAGES) + f":{ROOT}"
    imports = "; ".join(f"from {module} import {class_name}; assert len({class_name}().installation_recipes()) == 1" for _, module, class_name, _ in PACKAGES)
    result = subprocess.run([sys.executable, "-c", f"import sys; {imports}; assert 'mlx.core' not in sys.modules"], env={"PYTHONPATH": python_path}, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
