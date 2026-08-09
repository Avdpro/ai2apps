import json
import struct
from pathlib import Path

import pytest

from dynamoe.model_installer import (
    DynaMoeInstaller,
    build_deepseek_offset_manifest,
    build_qwen36_offset_manifest,
    checkpoint_is_complete,
    link_cached_snapshot,
)
from omlx.cache.moe_expert_store import ExpertMajorStore, create_expert_major_store
from omlx.model_discovery import cache_moe_engine_id, discover_models
from omlx.patches.qwen3_6_flesh.checkpoint import create_qwen36_fused_store
from omlx.patches.deepseek_v4.scope_policy import (
    clear_scope_policy_override,
    configure_scope_policy,
    load_scope_policy_from_env,
)


def _write_fake_checkpoint(root: Path) -> None:
    root.mkdir()
    config = {
        "model_type": "deepseek_v4",
        "num_hidden_layers": 1,
        "n_routed_experts": 2,
    }
    (root / "config.json").write_text(json.dumps(config))
    header = {}
    weight_map = {}
    cursor = 0
    for expert in range(2):
        for projection in ("w1", "w2", "w3"):
            for part, dtype, shape, size in (
                ("weight", "I8", [1, 4], 4),
                ("scale", "F8_E8M0", [1, 1], 1),
            ):
                name = f"layers.0.ffn.experts.{expert}.{projection}.{part}"
                header[name] = {
                    "dtype": dtype,
                    "shape": shape,
                    "data_offsets": [cursor, cursor + size],
                }
                weight_map[name] = "model-00001-of-00001.safetensors"
                cursor += size
    encoded = json.dumps(header, separators=(",", ":")).encode()
    (root / "model-00001-of-00001.safetensors").write_bytes(
        struct.pack("<Q", len(encoded)) + encoded + bytes(cursor)
    )
    (root / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": weight_map})
    )


def _write_fake_stacked_checkpoint(root: Path) -> None:
    root.mkdir()
    (root / "config.json").write_text(
        json.dumps(
            {
                "model_type": "deepseek_v4",
                "num_hidden_layers": 1,
                "n_routed_experts": 2,
                "quantization": {"group_size": 64, "bits": 2, "mode": "affine"},
            }
        )
    )
    header = {}
    weight_map = {}
    cursor = 0
    for projection in ("gate_proj", "down_proj", "up_proj"):
        for part, dtype, shape, size in (
            ("weight", "U32", [2, 1, 2], 16),
            ("scales", "BF16", [2, 1, 1], 4),
            ("biases", "BF16", [2, 1, 1], 4),
        ):
            name = f"model.layers.0.ffn.switch_mlp.{projection}.{part}"
            header[name] = {
                "dtype": dtype,
                "shape": shape,
                "data_offsets": [cursor, cursor + size],
            }
            weight_map[name] = "model-00001-of-00001.safetensors"
            cursor += size
    encoded = json.dumps(header, separators=(",", ":")).encode()
    (root / "model-00001-of-00001.safetensors").write_bytes(
        struct.pack("<Q", len(encoded)) + encoded + bytes(cursor)
    )
    (root / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": weight_map})
    )


def _write_fake_qwen_checkpoint(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "config.json").write_text(
        json.dumps(
            {
                "model_type": "qwen3_5_moe",
                "text_config": {"num_hidden_layers": 1, "num_experts": 2},
                "quantization": {"group_size": 64, "bits": 4, "mode": "affine"},
            }
        )
    )
    specs = {
        "gate_proj": {
            "weight": ("U32", [2, 512, 256], 2 * 512 * 256 * 4),
            "scales": ("BF16", [2, 512, 32], 2 * 512 * 32 * 2),
            "biases": ("BF16", [2, 512, 32], 2 * 512 * 32 * 2),
        },
        "up_proj": {
            "weight": ("U32", [2, 512, 256], 2 * 512 * 256 * 4),
            "scales": ("BF16", [2, 512, 32], 2 * 512 * 32 * 2),
            "biases": ("BF16", [2, 512, 32], 2 * 512 * 32 * 2),
        },
        "down_proj": {
            "weight": ("U32", [2, 2048, 64], 2 * 2048 * 64 * 4),
            "scales": ("BF16", [2, 2048, 8], 2 * 2048 * 8 * 2),
            "biases": ("BF16", [2, 2048, 8], 2 * 2048 * 8 * 2),
        },
    }
    headers = {"model-00001.safetensors": {}, "model-00002.safetensors": {}}
    cursors = {name: 0 for name in headers}
    weight_map = {}
    for projection, parts in specs.items():
        shard = (
            "model-00002.safetensors"
            if projection == "down_proj"
            else "model-00001.safetensors"
        )
        for part, (dtype, shape, size) in parts.items():
            name = (
                "language_model.model.layers.0.mlp.switch_mlp."
                f"{projection}.{part}"
            )
            cursor = cursors[shard]
            headers[shard][name] = {
                "dtype": dtype,
                "shape": shape,
                "data_offsets": [cursor, cursor + size],
            }
            cursors[shard] += size
            weight_map[name] = shard
    for shard, header in headers.items():
        encoded = json.dumps(header, separators=(",", ":")).encode()
        (root / shard).write_bytes(
            struct.pack("<Q", len(encoded)) + encoded + bytes(cursors[shard])
        )
    (root / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": weight_map})
    )


def test_build_deepseek_offset_manifest(tmp_path: Path):
    source = tmp_path / "model"
    output = source / ".dynamoe" / "offsets"
    _write_fake_checkpoint(source)

    path = build_deepseek_offset_manifest(source, output)
    manifest = json.loads(path.read_text())

    assert manifest["format"] == "dmoe-offset-manifest"
    assert manifest["num_layers"] == 1
    assert manifest["num_experts"] == 2
    layer = manifest["layers"]["0"]
    assert layer["expert_count"] == 2
    assert layer["experts"][0]["expert_bytes"] == 15
    tensors = {item["name"]: item for item in layer["experts"][0]["tensors"]}
    assert tensors["gate_proj.weight"]["dtype"] == "U32"
    assert tensors["gate_proj.weight"]["shape"] == [1, 1]


def test_build_stacked_affine_2bit_offset_manifest(tmp_path: Path):
    source = tmp_path / "model"
    output = source / ".dynamoe" / "offsets"
    _write_fake_stacked_checkpoint(source)

    manifest = json.loads(
        build_deepseek_offset_manifest(source, output).read_text()
    )
    layer = manifest["layers"]["0"]
    first = {item["name"]: item for item in layer["experts"][0]["tensors"]}
    second = {item["name"]: item for item in layer["experts"][1]["tensors"]}

    assert layer["expert_bytes"] == 36
    assert first["gate_proj.weight"]["dtype"] == "U32"
    assert first["gate_proj.scales"]["dtype"] == "BF16"
    assert first["gate_proj.biases"]["shape"] == [1, 1]
    assert (
        second["gate_proj.weight"]["absolute_offset"]
        - first["gate_proj.weight"]["absolute_offset"]
        == 8
    )


def test_qwen_checkpoint_converts_cross_shard_experts_to_fused_store(
    tmp_path: Path,
):
    source = tmp_path / "qwen"
    offsets = source / ".dynamoe" / "offsets-qwen36"
    split = source / ".dynamoe" / "split" / "layer-000.moe"
    fused = source / ".dynamoe" / "fused" / "layer-000.moe"
    _write_fake_qwen_checkpoint(source)

    manifest_path = build_qwen36_offset_manifest(source, offsets)
    manifest = json.loads(manifest_path.read_text())
    layer = manifest["layers"]["0"]
    files = {
        tensor["file"]
        for expert in layer["experts"]
        for tensor in expert["tensors"]
    }
    assert len(files) == 2
    assert layer["expert_count"] == 2
    assert layer["expert_bytes"] == 1769472

    create_expert_major_store(manifest_path, 0, split)
    create_qwen36_fused_store(split, fused)

    with ExpertMajorStore(fused) as store:
        assert store.num_experts == 2
        assert store.record_bytes == 1769472
        assert {tensor.name for tensor in store.tensors} == {
            "gate_up_proj.weight",
            "gate_up_proj.scales",
            "gate_up_proj.biases",
            "down_proj.weight",
            "down_proj.scales",
            "down_proj.biases",
        }


def test_catalog_only_reports_complete_engine_packages(tmp_path: Path, monkeypatch):
    profile = tmp_path / "scope.json"
    profile.write_text("{}")
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_SCOPE_PROFILE", str(profile))

    item = DynaMoeInstaller.catalog()[0]

    assert item["id"] == "deepseek-v4-flash"
    assert item["engine_ready"] is True
    assert item["engine"]["id"] == "deepseek-v4-flesh"
    assert item["memory_tiers"][2]["experts"] == 60
    assert DynaMoeInstaller.catalog()[1]["id"] == "deepseek-v4-flash-2bit"


def test_catalog_exposes_qwen_when_its_scope_pack_is_configured(
    tmp_path: Path, monkeypatch
):
    profile = tmp_path / "qwen-scope.json"
    profile.write_text("{}")
    monkeypatch.setenv("OMLX_QWEN36_SCOPE_PROFILE", str(profile))

    item = next(
        item
        for item in DynaMoeInstaller.catalog()
        if item["id"] == "qwen3.6-35b-a3b-4bit"
    )

    assert item["engine"]["id"] == "qwen3.6-tiered"
    assert item["sources"][0]["repo_id"] == (
        "mlx-community/Qwen3.6-35B-A3B-4bit"
    )
    assert [tier["experts"] for tier in item["memory_tiers"]] == [80, 96, 120]


def test_model_local_scope_policy_override(tmp_path: Path):
    profile = tmp_path / "scope.json"
    store = tmp_path / "store"
    store.mkdir()
    experts = list(range(60))
    profile.write_text(
        json.dumps(
            {
                "format": "dmoe-deepseek-tiered-policy",
                "scopes": {"general": {str(layer): experts for layer in range(3, 43)}},
            }
        )
    )

    try:
        configure_scope_policy(profile, "general", store, 20)
        policy = load_scope_policy_from_env()

        assert policy is not None
        assert policy.scope_name == "general"
        assert policy.resident_experts == 20
        assert policy.experts(3) == tuple(range(20))
    finally:
        clear_scope_policy_override()


def test_downloader_ui_exposes_dynamoe_source():
    root = Path(__file__).parents[1]
    template = (root / "omlx/admin/templates/dashboard/_models.html").read_text()
    script = (root / "omlx/admin/static/js/dashboard.js").read_text()

    assert "downloaderSource = 'dynamoe'" in template
    assert "Download & Prepare" in template
    assert "/admin/api/dynamoe/install" in script


def test_hf_snapshot_is_reused_as_a_no_copy_model_view(tmp_path: Path):
    snapshot = tmp_path / "hub" / "snapshots" / "abc"
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text("{}")
    (snapshot / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": {"weight": "model-00001.safetensors"}})
    )
    shard = snapshot / "model-00001.safetensors"
    shard.write_bytes(b"weights")
    destination = tmp_path / "models" / "owner" / "model"

    link_cached_snapshot(snapshot, destination)

    assert checkpoint_is_complete(destination)
    assert (destination / "config.json").is_symlink()
    assert (destination / "model-00001.safetensors").resolve() == shard


def test_prepare_checkpoint_prefers_hf_cache(tmp_path: Path, monkeypatch):
    revision = "a" * 40
    snapshot = tmp_path / "snapshots" / revision
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text("{}")
    (snapshot / "model.safetensors").write_bytes(b"weights")
    destination = tmp_path / "models" / "owner" / "model"

    monkeypatch.setattr(
        "huggingface_hub.snapshot_download", lambda **_: str(snapshot)
    )

    assert DynaMoeInstaller._prepare_cached_checkpoint(
        "owner/model", revision, "", destination
    )
    assert checkpoint_is_complete(destination)
    assert json.loads(
        (destination / ".dynamoe" / "source.json").read_text()
    )["revision"] == revision


@pytest.mark.asyncio
async def test_qwen_catalog_install_reuses_checkpoint_and_writes_runtime_manifest(
    tmp_path: Path, monkeypatch
):
    scope = tmp_path / "qwen-scope.json"
    phase = {
        "general": {str(layer): list(range(8)) for layer in range(40)}
    }
    scope.write_text(
        json.dumps(
            {
                "format": "dynamoe-qwen36-scope-policy",
                "version": 1,
                "phases": {"prefill": phase, "decode": phase},
            }
        )
    )
    monkeypatch.setenv("OMLX_QWEN36_SCOPE_PROFILE", str(scope))

    class FakeDownloader:
        def __init__(self):
            self.model_dir = tmp_path / "models"
            self._on_complete = None

        async def start_download(self, *_args, **_kwargs):
            raise AssertionError("complete local checkpoint should not download")

    downloader = FakeDownloader()
    source = downloader.model_dir / "mlx-community/Qwen3.6-35B-A3B-4bit"
    _write_fake_qwen_checkpoint(source)
    (source / ".dynamoe").mkdir()
    (source / ".dynamoe" / "source.json").write_text(
        json.dumps(
            {
                "format": "dynamoe-hf-source",
                "version": 1,
                "repo_id": "mlx-community/Qwen3.6-35B-A3B-4bit",
                "revision": "38740b847e4cb78f352aba30aa41c76e08e6eb46",
            }
        )
    )
    installer = DynaMoeInstaller(downloader)

    task = await installer.start(
        "qwen3.6-35b-a3b-4bit", "huggingface", "compact", ""
    )
    await installer._runners[task.task_id]

    assert task.status.value == "completed"
    assert task.cache_hit is True
    manifest = json.loads((source / "dynamoe-model.json").read_text())
    assert manifest["family"] == "qwen3_6"
    assert manifest["engine"]["id"] == "qwen3.6-tiered"
    assert manifest["memory_tier"] == "compact"
    assert manifest["version"] == 2
    assert manifest["source"]["revision"] == (
        "38740b847e4cb78f352aba30aa41c76e08e6eb46"
    )
    assert manifest["conversion"]["variant"] == (
        "qwen3.6-affine-q4-gate-up-fused-v2"
    )
    assert manifest["arena_tail_slots"] == 24
    assert Path(manifest["expert_store"]).name == "expert-store-fused"
    store_manifest = json.loads(
        (Path(manifest["expert_store"]) / "manifest.json").read_text()
    )
    assert store_manifest["source"]["revision"] == task.revision
    assert store_manifest["conversion"] == manifest["conversion"]
    with ExpertMajorStore(
        Path(manifest["expert_store"]) / "layer-000.moe"
    ) as store:
        assert "gate_up_proj.weight" in {tensor.name for tensor in store.tensors}
    discovered = discover_models(downloader.model_dir)["Qwen3.6-35B-A3B-4bit"]
    assert discovered.source_type == "dynamoe"
    assert cache_moe_engine_id(discovered.cache_moe_config) == "qwen3.6-tiered"
