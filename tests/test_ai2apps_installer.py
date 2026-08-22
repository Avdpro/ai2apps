import json
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai2apps.model_installer import (
    AI2AppsInstaller,
    _read_safetensors_header,
    build_backbone_checkpoint,
    build_storage_transition,
    commit_backbone_index,
    build_deepseek_offset_manifest,
    build_qwen36_offset_manifest,
    checkpoint_is_complete,
    link_cached_snapshot,
    reclaim_stream_shards,
    release_hf_cache_revision,
    resume_storage_transition,
)
from omlx.cache.moe_expert_store import ExpertMajorStore, create_expert_major_store
from omlx.model_discovery import cache_moe_engine_id, discover_models
from omlx.patches.qwen3_6_flesh.checkpoint import create_qwen36_fused_store
from omlx.patches.deepseek_v4.scope_policy import (
    clear_scope_policy_override,
    configure_scope_policy,
    load_scope_policy_from_env,
)

CACHED_MOE_PACKAGE_SRCS = tuple(
    Path(__file__).parents[1] / "packages" / name / "src"
    for name in (
        "omlx-model-deepseek-v4-flash",
        "omlx-model-deepseek-v4-flash-2bit",
        "omlx-model-qwen36-cached-moe",
    )
)
for package_src in CACHED_MOE_PACKAGE_SRCS:
    sys.path.insert(0, str(package_src))

from omlx_model_deepseek_v4_flash import DeepSeekV4FlashAdapter  # noqa: E402
from omlx_model_deepseek_v4_flash_2bit import DeepSeekV4Flash2BitAdapter  # noqa: E402
from omlx_model_qwen36_cached_moe import Qwen36CachedMoeAdapter  # noqa: E402


@pytest.fixture(autouse=True)
def _cached_moe_package_registry(monkeypatch):
    from omlx.model_adapters import ModelAdapterRegistry
    from omlx.model_adapters import registry as registry_module

    registry = ModelAdapterRegistry(load_entry_points=False)
    registry.register(DeepSeekV4FlashAdapter())
    registry.register(DeepSeekV4Flash2BitAdapter())
    registry.register(Qwen36CachedMoeAdapter())
    monkeypatch.setattr(registry_module, "_default_registry", registry)


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
    headers = {
        "model-00001-of-00002.safetensors": {},
        "model-00002-of-00002.safetensors": {},
    }
    weight_map = {}
    cursors = {name: 0 for name in headers}
    for projection in ("gate_proj", "down_proj", "up_proj"):
        shard = (
            "model-00002-of-00002.safetensors"
            if projection == "down_proj"
            else "model-00001-of-00002.safetensors"
        )
        for part, dtype, shape, size in (
            ("weight", "U32", [2, 1, 2], 16),
            ("scales", "BF16", [2, 1, 1], 4),
            ("biases", "BF16", [2, 1, 1], 4),
        ):
            name = f"model.layers.0.ffn.switch_mlp.{projection}.{part}"
            cursor = cursors[shard]
            headers[shard][name] = {
                "dtype": dtype,
                "shape": shape,
                "data_offsets": [cursor, cursor + size],
            }
            weight_map[name] = shard
            cursors[shard] += size
    for shard, header in headers.items():
        encoded = json.dumps(header, separators=(",", ":")).encode()
        (root / shard).write_bytes(
            struct.pack("<Q", len(encoded))
            + encoded
            + bytes(cursors[shard])
        )
    (root / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": weight_map})
    )


def _append_fake_backbone_tensor(root: Path) -> tuple[str, str]:
    index_path = root / "model.safetensors.index.json"
    index = json.loads(index_path.read_text())
    shard = "model-00001-of-00002.safetensors"
    data_start, header = _read_safetensors_header(root / shard)
    cursor = max(int(spec["data_offsets"][1]) for spec in header.values())
    name = "model.layers.0.attn.weight"
    header[name] = {"dtype": "U32", "shape": [1], "data_offsets": [cursor, cursor + 4]}
    encoded = json.dumps(header, separators=(",", ":")).encode()
    payload = (root / shard).read_bytes()[data_start:] + b"ABCD"
    (root / shard).write_bytes(struct.pack("<Q", len(encoded)) + encoded + payload)
    index["weight_map"][name] = shard
    index_path.write_text(json.dumps(index))
    return name, shard


def test_backbone_checkpoint_raw_copies_only_non_expert_tensors(tmp_path: Path):
    source = tmp_path / "source"
    _write_fake_stacked_checkpoint(source)
    name, shard = _append_fake_backbone_tensor(source)

    output = tmp_path / "backbone"
    manifest = build_backbone_checkpoint(source, output, "deepseek_v4")

    rebuilt_index = json.loads(
        (output / "model.safetensors.index.json").read_text()
    )
    assert rebuilt_index["weight_map"] == {name: shard}
    rebuilt_start, rebuilt_header = _read_safetensors_header(output / shard)
    assert set(rebuilt_header) == {name}
    assert (output / shard).read_bytes()[rebuilt_start:] == b"ABCD"
    assert manifest["shards"]["model-00002-of-00002.safetensors"]["backbone_file"] is None


def test_stream_reclaim_replaces_only_shards_past_their_last_layer(tmp_path: Path):
    source = tmp_path / "source"
    _write_fake_stacked_checkpoint(source)
    _append_fake_backbone_tensor(source)
    backbone = source / ".ai2apps" / "backbone-staging"
    build_backbone_checkpoint(source, backbone, "deepseek_v4")
    offsets = build_deepseek_offset_manifest(source, source / ".ai2apps" / "offsets")
    transition = build_storage_transition(
        source,
        backbone,
        offsets,
        repo_id="owner/model",
        revision="a" * 40,
        policy="stream_reclaim",
    )

    released = reclaim_stream_shards(source, transition, completed_layer=0)

    assert set(released) == {
        "model-00001-of-00002.safetensors",
        "model-00002-of-00002.safetensors",
    }
    committed = commit_backbone_index(source, transition)
    assert committed["state"] == "prepared"
    rebuilt = json.loads((source / "model.safetensors.index.json").read_text())
    assert all("switch_mlp" not in name for name in rebuilt["weight_map"])


def test_interrupted_stream_reclaim_is_resumable(tmp_path: Path):
    source = tmp_path / "source"
    _write_fake_stacked_checkpoint(source)
    _append_fake_backbone_tensor(source)
    backbone = source / ".ai2apps" / "backbone-staging"
    build_backbone_checkpoint(source, backbone, "deepseek_v4")
    offsets = build_deepseek_offset_manifest(source, source / ".ai2apps" / "offsets")
    transition = build_storage_transition(
        source,
        backbone,
        offsets,
        repo_id="owner/model",
        revision="a" * 40,
        policy="stream_reclaim",
    )
    reclaim_stream_shards(source, transition, completed_layer=0)

    assert not checkpoint_is_complete(source)
    assert resume_storage_transition(
        source,
        repo_id="owner/model",
        revision="a" * 40,
        policy="stream_reclaim",
    ) == transition


def test_release_hf_cache_materializes_links_and_deletes_exact_revision(
    tmp_path: Path, monkeypatch
):
    cache = tmp_path / "hub"
    repo_cache = cache / "models--owner--model"
    blob = repo_cache / "blobs" / "abc"
    blob.parent.mkdir(parents=True)
    blob.write_text("model metadata")
    source = tmp_path / "models" / "owner" / "model"
    source.mkdir(parents=True)
    (source / "config.json").symlink_to(blob)
    executed = []

    class Strategy:
        expected_freed_size = 14

        def execute(self):
            executed.append(True)

    fake_revision = SimpleNamespace(commit_hash="a" * 40)
    fake_repo = SimpleNamespace(
        repo_id="owner/model", repo_type="model", revisions=[fake_revision]
    )
    fake_cache = SimpleNamespace(
        repos=[fake_repo], delete_revisions=lambda revision: Strategy()
    )
    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "scan_cache_dir", lambda path: fake_cache)
    result = release_hf_cache_revision(
        source,
        "owner/model",
        "a" * 40,
        cache_linked=True,
    )

    assert result == {
        "attempted": True,
        "freed_bytes": 14,
        "materialized_files": 1,
        "completed": True,
    }
    assert executed == [True]
    assert not (source / "config.json").is_symlink()
    assert (source / "config.json").read_text() == "model metadata"


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
    output = source / ".ai2apps" / "offsets"
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
    output = source / ".ai2apps" / "offsets"
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
    assert layer["storage"] == "direct-safetensors-multifile"
    assert len(
        {
            tensor["file"]
            for expert in layer["experts"]
            for tensor in expert["tensors"]
        }
    ) == 2
    assert (
        second["gate_proj.weight"]["absolute_offset"]
        - first["gate_proj.weight"]["absolute_offset"]
        == 8
    )


def test_qwen_checkpoint_converts_cross_shard_experts_to_fused_store(
    tmp_path: Path,
):
    source = tmp_path / "qwen"
    offsets = source / ".ai2apps" / "offsets-qwen36"
    split = source / ".ai2apps" / "split" / "layer-000.moe"
    fused = source / ".ai2apps" / "fused" / "layer-000.moe"
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

    item = AI2AppsInstaller.catalog()[0]

    assert item["id"] == "deepseek-v4-flash"
    assert item["engine_ready"] is True
    assert item["engine"]["id"] == "deepseek-v4-flesh"
    assert item["memory_tiers"][2]["experts"] == 60
    assert AI2AppsInstaller.catalog()[1]["id"] == "deepseek-v4-flash-2bit"


def test_catalog_exposes_qwen_when_its_scope_pack_is_configured(
    tmp_path: Path, monkeypatch
):
    profile = tmp_path / "qwen-scope.json"
    profile.write_text("{}")
    monkeypatch.setenv("OMLX_QWEN36_SCOPE_PROFILE", str(profile))

    item = next(
        item
        for item in AI2AppsInstaller.catalog()
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


def test_model_package_config_exposes_weight_download():
    root = Path(__file__).parents[1]
    template = (
        root / "ai2apps/web/templates/dashboard/_modal_model_package.html"
    ).read_text()
    script = (root / "ai2apps/web/static/js/dashboard.js").read_text()

    assert "Download & Prepare" in template
    assert "Weight source" in template
    assert "Storage" in template
    assert "Memory" in template
    assert "Download activity" in template
    assert "models.package.complete.title" in template
    assert "models.package.complete.description" in template
    assert "models.package.complete.done" in template
    assert "openModelPackageConfig" in script
    assert "modelPackageTasks" in script
    assert "modelPackageLatestTask" in script
    assert "/admin/api/ai2apps/install" in script
    assert "/admin/api/ai2apps/preflight" in script
    assert "dynaPreflight?.ready" in template


def test_ai2apps_hf_preflight_accepts_anonymous_public_access(
    tmp_path: Path, monkeypatch
):
    from omlx.admin import routes

    monkeypatch.setattr(routes, "package_version", lambda _name: "1.19.0")
    monkeypatch.setattr(routes, "_hf_downloader", object())
    monkeypatch.setattr(routes, "_hf_downloader_error", "")
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf-home"))
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hf-home" / "hub"))
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)

    result = routes._ai2apps_hf_preflight()

    assert result["ready"] is True
    assert result["cli_required"] is False
    assert result["dependency"]["compatible"] is True
    assert result["cache"]["writable"] is True
    assert result["authentication"]["status"] == "anonymous"
    assert result["issues"] == []


def test_ai2apps_hf_preflight_explains_missing_dependency(
    tmp_path: Path, monkeypatch
):
    from omlx.admin import routes

    def missing(_name):
        raise routes.PackageNotFoundError

    monkeypatch.setattr(routes, "package_version", missing)
    monkeypatch.setattr(routes, "_hf_downloader", None)
    monkeypatch.setattr(routes, "_hf_downloader_error", "")
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf-home"))

    result = routes._ai2apps_hf_preflight()

    assert result["ready"] is False
    assert result["dependency"]["installed"] is False
    assert result["issues"][0]["code"] == "dependency_missing"
    assert "pip install" in result["issues"][0]["action"]


def test_ai2apps_hf_preflight_reports_unwritable_cache(
    tmp_path: Path, monkeypatch
):
    from omlx.admin import routes

    monkeypatch.setattr(routes, "package_version", lambda _name: "1.19.0")
    monkeypatch.setattr(routes, "_hf_downloader", object())
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    monkeypatch.setattr(routes.os, "access", lambda *_args: False)

    result = routes._ai2apps_hf_preflight()

    assert result["ready"] is False
    assert any(issue["code"] == "cache_not_writable" for issue in result["issues"])


def test_ai2apps_cli_explains_missing_huggingface_dependency(
    monkeypatch, capsys
):
    import sys
    from types import ModuleType

    from ai2apps import cli

    fake_runtime = ModuleType("omlx.cli")

    def missing_runtime():
        raise ModuleNotFoundError(
            "simulated missing huggingface_hub",
            name="huggingface_hub",
        )

    fake_runtime.main = missing_runtime
    monkeypatch.setitem(sys.modules, "omlx.cli", fake_runtime)

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2
    error = capsys.readouterr().err
    assert "huggingface-hub is missing" in error
    assert "pip install -U ai2apps" in error


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

    assert AI2AppsInstaller._prepare_cached_checkpoint(
        "owner/model", revision, "", destination
    )
    assert checkpoint_is_complete(destination)
    assert json.loads(
        (destination / ".ai2apps" / "source.json").read_text()
    )["revision"] == revision


@pytest.mark.asyncio
async def test_ai2apps_download_requests_global_hf_cache_mode(
    tmp_path: Path, monkeypatch
):
    captured = {}

    class FakeDownloader:
        def __init__(self):
            self.model_dir = tmp_path / "models"
            self._on_complete = None

        async def start_download(self, *_args, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                task_id="child",
                status=SimpleNamespace(value="failed"),
                error="expected test stop",
            )

    monkeypatch.setattr(
        AI2AppsInstaller,
        "_prepare_cached_checkpoint",
        staticmethod(lambda *_args: False),
    )
    installer = AI2AppsInstaller(FakeDownloader())
    task = await installer.start(
        "qwen3.6-35b-a3b-4bit", "huggingface", "auto", ""
    )
    await installer._runners[task.task_id]

    assert task.status.value == "failed"
    assert captured["cache_mode"] is True
    assert captured["revision"] == task.revision


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
                "format": "ai2apps-qwen36-scope-policy",
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
    (source / ".ai2apps").mkdir()
    (source / ".ai2apps" / "source.json").write_text(
        json.dumps(
            {
                "format": "ai2apps-hf-source",
                "version": 1,
                "repo_id": "mlx-community/Qwen3.6-35B-A3B-4bit",
                "revision": "38740b847e4cb78f352aba30aa41c76e08e6eb46",
            }
        )
    )
    installer = AI2AppsInstaller(downloader)

    task = await installer.start(
        "qwen3.6-35b-a3b-4bit", "huggingface", "compact", ""
    )
    await installer._runners[task.task_id]

    assert task.status.value == "completed"
    assert task.cache_hit is True
    manifest = json.loads((source / "ai2apps-model.json").read_text())
    assert manifest["family"] == "qwen3_6"
    assert manifest["engine"]["id"] == "qwen3.6-tiered"
    assert "scope_asset" not in manifest["engine"]
    assert "scope_pack" not in manifest["engine"]
    assert manifest["memory_tier"] == "compact"
    assert manifest["version"] == 2
    assert manifest["execution_modes"] == ["cached", "full"]
    assert manifest["source"]["revision"] == (
        "38740b847e4cb78f352aba30aa41c76e08e6eb46"
    )
    assert manifest["conversion"]["variant"] == (
        "qwen3.6-affine-q4-gate-up-fused-v2"
    )
    assert manifest["arena_tail_slots"] == 24
    runtime_scope = Path(manifest["scope"]["profile"])
    assert runtime_scope.parent == source / ".ai2apps" / "scope-assets"
    assert runtime_scope.is_file()
    assert runtime_scope != Path(
        next(
            recipe
            for recipe in AI2AppsInstaller._recipes()
            if recipe["id"] == "qwen3.6-35b-a3b-4bit"
        )["engine"]["scope_asset"]
    )
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
    assert discovered.source_type == "ai2apps"
    assert cache_moe_engine_id(discovered.cache_moe_config) == "qwen3.6-tiered"

    conversion_state = json.loads(
        (source / ".ai2apps" / "conversion.json").read_text()
    )
    assert conversion_state["completed_layers"] == [0]
    assert conversion_state["split_completed_layers"] == [0]
    fused_layer = Path(manifest["expert_store"]) / "layer-000.moe"
    split_layer = source / ".ai2apps" / "expert-store-split" / "layer-000.moe"
    mtimes = (fused_layer.stat().st_mtime_ns, split_layer.stat().st_mtime_ns)

    # Reinstalling the same pinned checkpoint must reuse each committed layer.
    # This is also the resume path after a conversion task is interrupted.
    resumed_installer = AI2AppsInstaller(downloader)
    resumed = await resumed_installer.start(
        "qwen3.6-35b-a3b-4bit", "huggingface", "compact", ""
    )
    await resumed_installer._runners[resumed.task_id]

    assert resumed.status.value == "completed"
    assert resumed.cache_hit is True
    assert (fused_layer.stat().st_mtime_ns, split_layer.stat().st_mtime_ns) == mtimes
