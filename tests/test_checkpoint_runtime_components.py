import hashlib
import json
from pathlib import Path

import pytest

from ai2apps.checkpoints import checkpoint_is_complete, model_checkpoint_is_complete
from ai2apps.model_installer import AI2AppsInstaller, InstallTask
from ai2apps.packages.supervisor import ManagedServiceSupervisor
from omlx.ssd_checkpoint import ExternalTensorReader, inspect_ssd_checkpoint


def _write_ssd_checkpoint(root):
    experts = root / "experts"
    experts.mkdir(parents=True)
    payloads = {
        "config.json": json.dumps({"model_type": "deepseek_v4"}).encode(),
        "model.safetensors": b"backbone",
        "model.safetensors.index.json": json.dumps(
            {"weight_map": {"dense.weight": "model.safetensors"}}
        ).encode(),
        "external-tensors.json": json.dumps(
            {
                "model.layers.0.mlp.experts.weight": {
                    "file": "experts/layer-000.moe",
                    "offset": 0,
                    "count": 2,
                    "row_bytes": 1,
                    "stride": 1,
                    "dtype": "U8",
                    "shape": [2, 1],
                }
            }
        ).encode(),
        "experts/layer-000.moe": b"\x11\x22",
        "experts/manifest.json": json.dumps(
            {
                "format": "omlx-moe-expert-major-set",
                "version": 1,
                "variant": "deepseek-v4-expert-major-v1",
                "layers": {
                    "0": {
                        "file": "layer-000.moe",
                        "num_experts": 2,
                        "record_bytes": 1,
                        "file_bytes": 2,
                    }
                },
            }
        ).encode(),
    }
    for relative, value in payloads.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    files = {
        relative: {
            "size": len(value),
            "sha256": hashlib.sha256(value).hexdigest(),
        }
        for relative, value in payloads.items()
    }
    marker = {
        "schema": "ai2apps.ssd-checkpoint/v1",
        "family": "deepseek_v4",
        "layout": "deepseek-v4-expert-major-v1",
        "expert_store": "experts",
        "verification": "all_tensor_payloads_equal",
        "index_sha256": files["model.safetensors.index.json"]["sha256"],
        "files": files,
    }
    (root / "ssd-checkpoint.json").write_text(json.dumps(marker))
    return root


def _write_verified_overlay(root: Path, distribution_id: str) -> Path:
    payloads = {
        "LICENSE": b"terms",
        "stage-dmd-step-250/linear_branch/config.json": b"{}",
        "stage-dmd-step-250/linear_branch/model.safetensors": b"overlay",
    }
    for relative, payload in payloads.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        target.chmod(0o444)
    metadata = root / ".ai2apps" / "distribution.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(
        json.dumps(
            {
                "format": "ai2apps-checkpoint-distribution",
                "version": 1,
                "distributionId": distribution_id,
                "manifestDigest": "sha256:" + "a" * 64,
            }
        )
    )
    files = {}
    for relative in payloads:
        info = (root / relative).stat()
        files[relative] = {
            "device": info.st_dev,
            "inode": info.st_ino,
            "size": info.st_size,
            "mtimeNs": info.st_mtime_ns,
        }
    verification = root / ".ai2apps" / "verification.json"
    verification.write_text(
        json.dumps(
            {
                "format": "ai2apps-checkpoint-verification",
                "version": 1,
                "manifestDigest": "sha256:" + "a" * 64,
                "files": files,
            }
        )
    )
    metadata.chmod(0o444)
    verification.chmod(0o444)
    return root


def test_model_checkpoint_accepts_verified_registry_overlay(tmp_path):
    distribution_id = "dist_ai2apps_minimax_h3_openvdn_dmd8_overlay_test_v1"
    root = _write_verified_overlay(tmp_path / "overlay", distribution_id)
    model = {"weights": {"distribution_id": distribution_id}}

    assert not checkpoint_is_complete(root)
    assert model_checkpoint_is_complete(root, model)

    weights = root / "stage-dmd-step-250/linear_branch/model.safetensors"
    weights.chmod(0o644)
    weights.write_bytes(b"changed")
    weights.chmod(0o444)
    assert not model_checkpoint_is_complete(root, model)


def test_model_checkpoint_rejects_registry_overlay_for_another_distribution(tmp_path):
    root = _write_verified_overlay(tmp_path / "overlay", "dist_expected")

    assert not model_checkpoint_is_complete(
        root, {"weights": {"distribution_id": "dist_other"}}
    )


def test_ssd_checkpoint_requires_every_declared_file_and_reads_selected_rows(tmp_path):
    root = _write_ssd_checkpoint(tmp_path / "ssd")

    assert inspect_ssd_checkpoint(root)["family"] == "deepseek_v4"
    assert checkpoint_is_complete(root)
    reader = ExternalTensorReader(root, expected_family="deepseek_v4")
    assert reader.read("model.layers.0.mlp.experts.weight", [1]) == b"\x22"

    (root / "experts/layer-000.moe").unlink()
    assert not checkpoint_is_complete(root)
    with pytest.raises(ValueError, match="missing or truncated"):
        inspect_ssd_checkpoint(root)


def test_ssd_checkpoint_does_not_require_hub_repository_metadata(tmp_path):
    root = _write_ssd_checkpoint(tmp_path / "ssd")
    attributes = b"*.safetensors filter=lfs diff=lfs merge=lfs -text\n"
    marker_path = root / "ssd-checkpoint.json"
    marker = json.loads(marker_path.read_text())
    marker["files"][".gitattributes"] = {
        "size": len(attributes),
        "sha256": hashlib.sha256(attributes).hexdigest(),
    }
    marker_path.write_text(json.dumps(marker))

    assert not (root / ".gitattributes").exists()
    assert inspect_ssd_checkpoint(root)["family"] == "deepseek_v4"
    assert checkpoint_is_complete(root)


def test_ssd_checkpoint_activation_reuses_bundled_expert_store(tmp_path, monkeypatch):
    root = _write_ssd_checkpoint(tmp_path / "ssd")
    profile = tmp_path / "scope.json"
    profile.write_text(
        json.dumps(
            {
                "format": "dmoe-deepseek-tiered-policy",
                "scopes": {"general": {}},
            }
        )
    )
    validated = []
    monkeypatch.setattr(
        AI2AppsInstaller,
        "_validate",
        staticmethod(lambda *args, **kwargs: validated.append((args, kwargs))),
    )
    installer = AI2AppsInstaller(object())
    task = InstallTask(
        "task",
        "provider/model",
        "huggingface",
        "Avdpro/model-SSD",
        "a" * 40,
        memory_tier="optimal",
        storage_policy="keep_source",
    )
    recipe = {
        "id": task.model_id,
        "family": "deepseek_v4",
        "execution_modes": ("cached", "full"),
        "engine": {"id": "deepseek-v4-flesh", "version": 1},
        "scope_name": "general",
        "conversion": {
            "format": "omlx-moe-expert-major-set",
            "version": 1,
            "variant": "deepseek-v4-expert-major-v1",
        },
    }

    installer._activate_ssd_checkpoint(task, recipe, root, profile)

    installed = json.loads((root / "ai2apps-model.json").read_text())
    assert installed["expert_store"] == str((root / "experts").resolve())
    assert installed["checkpoint_layout"] == {
        "format": "ai2apps-ssd-checkpoint",
        "version": 1,
        "layout": "deepseek-v4-expert-major-v1",
        "source_retained": True,
        "storage_policy": "keep_source",
        "manifest_sha256": hashlib.sha256(
            (root / "ssd-checkpoint.json").read_bytes()
        ).hexdigest(),
    }
    assert validated[0][1] == {"ssd_ready": True}
    assert not (root / ".ai2apps" / "experts").exists()


def test_deepseek_v41_ssd_activation_needs_no_mlx_host_import(tmp_path, monkeypatch):
    root = _write_ssd_checkpoint(tmp_path / "ssd-v41")
    expert_manifest_path = root / "experts/manifest.json"
    expert_manifest_path.write_text(json.dumps({"status": "complete", "layers": [0]}))
    marker_path = root / "ssd-checkpoint.json"
    marker = json.loads(marker_path.read_text())
    marker["family"] = "deepseek_v41"
    marker["layout"] = "dsv41-original-fp4-six-segment-v1"
    expert_manifest = expert_manifest_path.read_bytes()
    marker["files"]["experts/manifest.json"] = {
        "size": len(expert_manifest),
        "sha256": hashlib.sha256(expert_manifest).hexdigest(),
    }
    marker_path.write_text(json.dumps(marker))
    profile = tmp_path / "scope-v41.json"
    profile.write_text(
        json.dumps(
            {
                "format": "ai2apps-deepseek-v41-runtime-profile",
                "version": 1,
            }
        )
    )
    task = InstallTask(
        "task-v41",
        "ai2apps.model.deepseek-v41-flash/deepseek-v41-flash",
        "huggingface",
        "Avdpro/DeepSeek-V4.1-Flash-SSD",
        "a" * 40,
        memory_tier="standard",
        storage_policy="keep_source",
    )
    recipe = {
        "id": task.model_id,
        "install_id": "deepseek-v41-flash",
        "family": "deepseek_v41",
        "execution_modes": ("cached",),
        "engine": {"id": "deepseek-v41-ssd", "version": 1},
        "scope_name": "standard",
        "conversion": {
            "format": "ai2apps-ssd-checkpoint",
            "version": 1,
            "variant": "dsv41-original-fp4-six-segment-v1",
        },
    }

    import builtins

    real_import = builtins.__import__

    def reject_mlx_host_import(name, *args, **kwargs):
        if name.startswith("omlx.cache") or name.startswith("mlx_lm"):
            raise AssertionError(f"control-plane imported inference dependency: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_mlx_host_import)
    AI2AppsInstaller(object())._activate_ssd_checkpoint(
        task, recipe, root, profile
    )

    installed = json.loads((root / "ai2apps-model.json").read_text())
    assert installed["family"] == "deepseek_v41"
    assert installed["main_slots"] == 40
    assert installed["hot_slots"] == 8
    assert installed["prefill_slots"] == 64


def test_deepseek_v41_ssd_activation_preserves_read_only_distribution_view(
    tmp_path,
):
    root = _write_ssd_checkpoint(tmp_path / "ssd-v41-read-only")
    expert_manifest_path = root / "experts/manifest.json"
    expert_manifest_path.write_text(json.dumps({"status": "complete", "layers": [0]}))
    marker_path = root / "ssd-checkpoint.json"
    marker = json.loads(marker_path.read_text())
    marker["family"] = "deepseek_v41"
    marker["layout"] = "dsv41-original-fp4-six-segment-v1"
    expert_manifest = expert_manifest_path.read_bytes()
    marker["files"]["experts/manifest.json"] = {
        "size": len(expert_manifest),
        "sha256": hashlib.sha256(expert_manifest).hexdigest(),
    }
    marker_path.write_text(json.dumps(marker))
    metadata = root / ".ai2apps"
    metadata.mkdir()
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)

    profile = tmp_path / "scope-v41-read-only.json"
    profile.write_text(
        json.dumps(
            {
                "format": "ai2apps-deepseek-v41-runtime-profile",
                "version": 1,
            }
        )
    )
    task = InstallTask(
        "task-v41-read-only",
        "ai2apps.model.deepseek-v41-flash/deepseek-v41-flash",
        "huggingface",
        "Avdpro/DeepSeek-V4.1-Flash-SSD",
        "a" * 40,
        memory_tier="standard",
        storage_policy="keep_source",
    )
    recipe = {
        "id": task.model_id,
        "install_id": "deepseek-v41-flash",
        "family": "deepseek_v41",
        "execution_modes": ("cached",),
        "engine": {"id": "deepseek-v41-ssd", "version": 1},
        "scope_name": "standard",
        "conversion": {
            "format": "ai2apps-ssd-checkpoint",
            "version": 1,
            "variant": "dsv41-original-fp4-six-segment-v1",
        },
    }

    AI2AppsInstaller(object())._activate_ssd_checkpoint(task, recipe, root, profile)

    installed = json.loads((root / "ai2apps-model.json").read_text())
    runtime_scope = Path(installed["scope"]["profile"])
    assert runtime_scope.is_file()
    assert runtime_scope.parent == root / ".ai2apps" / "scope-assets"
    assert root.stat().st_mode & 0o222 == 0
    assert metadata.stat().st_mode & 0o222 == 0
    assert (root / "ai2apps-model.json").stat().st_mode & 0o222 == 0
    assert runtime_scope.stat().st_mode & 0o222 == 0
    assert (root / "model.safetensors").stat().st_mode & 0o222 == 0


@pytest.mark.parametrize("family,implementation", [
    ("z-image", "mflux-mlx-metal-optimized"),
    ("z-image", "mflux-native-cfg"),
    ("flux2-klein", "mflux-mlx-optimized"),
    ("qwen-image", "mflux-mlx-optimized"),
])
def test_runtime_scheduler_does_not_hide_missing_weights(tmp_path, family, implementation):
    snapshot = tmp_path / "models--example--zimage" / "snapshots" / "revision"
    snapshot.mkdir(parents=True)
    index = {"_class_name": "ZImagePipeline", "scheduler": ["diffusers", "Scheduler"]}
    for name in ("transformer", "vae", "text_encoder", "tokenizer"):
        component = snapshot / name
        component.mkdir()
        (component / "config.json").write_text("{}")
        index[name] = ["diffusers", name]
    (snapshot / "model_index.json").write_text(json.dumps(index))
    shard = snapshot / "transformer" / "weights.safetensors"
    shard.write_bytes(b"fixture")
    (shard.parent / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": {"weight": shard.name}})
    )
    model = {
        "id": "example/zimage", "upstream_id": "example/zimage",
        "weights": {"provider": "huggingface", "repo_id": "example/zimage", "revision": "revision"},
        "metadata": {"family": family, "implementation": implementation},
    }

    def ready():
        rows, _ = ManagedServiceSupervisor._model_worker_checkpoints(
            {"models": [model]}, tmp_path
        )
        return rows[0]["path"] is not None

    assert ready()
    model["metadata"] = {}
    assert not ready()  # Other backends still require their scheduler files.
    model["metadata"] = {"family": family, "implementation": implementation}
    shard.unlink()
    assert not ready()  # Missing indexed weights must never be accepted.


@pytest.mark.parametrize("missing", [None, "conditional", "unconditional", "text", "vae"])
def test_ideogram_package_config_and_nested_weights(tmp_path, missing):
    import yaml
    from pathlib import Path
    manifest = yaml.safe_load((Path(__file__).parents[1] / "packages/ai2apps-model-ideogram4-mlx/service.yaml").read_text())
    from ai2apps.checkpoint_paths import checkpoint_distribution_cache_key
    model = manifest["models"][0]
    snapshot = tmp_path / "models--Comfy-Org--Ideogram-4" / "distributions" / checkpoint_distribution_cache_key(model["weights"]["distribution_id"])
    components = {
        "conditional": "diffusion_models/ideogram4_fp8_scaled.safetensors",
        "unconditional": "diffusion_models/ideogram4_unconditional_fp8_scaled.safetensors",
        "text": "text_encoders/qwen3vl_8b_fp8_scaled.safetensors",
        "vae": "vae/flux2-vae.safetensors",
    }
    for key, relative in components.items():
        if key != missing:
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"tensor fixture")
    rows, _ = ManagedServiceSupervisor._model_worker_checkpoints(manifest, tmp_path)
    assert (rows[0]["path"] is not None) == (missing is None)
    model["metadata"] = {}
    rows, _ = ManagedServiceSupervisor._model_worker_checkpoints(manifest, tmp_path)
    assert rows[0]["path"] is None
