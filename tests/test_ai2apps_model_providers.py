# SPDX-License-Identifier: Apache-2.0
"""Installable multi-modal Model Provider contracts."""

from __future__ import annotations

import hashlib
import json
import platform
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import yaml

from ai2apps.config import PlatformConfig
from ai2apps.model_installer import (
    AI2AppsInstaller,
    checkpoint_is_complete,
    import_local_checkpoint_to_hf_cache,
    reconcile_installed_shared_model_references,
)
from ai2apps.model_providers import (
    ModelProviderContractError,
    installed_model_preparation_recipes,
    list_package_models,
    proxy_package_json,
    validate_package_models,
)
from ai2apps.packages.archive import ServicePackageArchive
from ai2apps.packages.contract_v1 import build_package
from ai2apps.packages.registry import RegistryPackageManager
from ai2apps.packages.supervisor import ManagedServiceSupervisor
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.services import ServiceInstanceStatus, ServiceRuntimeMode
from ai2apps.shared_model_cache import (
    list_shared_model_references,
    publish_shared_model_reference,
)


def _model(service: str, suffix: str, model_type: str) -> dict:
    return {
        "id": f"{service}/{suffix}",
        "display_name": suffix,
        "model_type": model_type,
        "upstream_id": f"upstream-{suffix}",
    }


def test_model_manifest_supports_conversation_image_audio_and_video():
    models = validate_package_models(
        "example.multimodal",
        [
            _model("example.multimodal", "chat", "llm"),
            _model("example.multimodal", "image", "image_generation"),
            _model("example.multimodal", "stt", "audio_stt"),
            _model("example.multimodal", "tts", "audio_tts"),
            _model("example.multimodal", "audio", "audio_processing"),
            _model("example.multimodal", "video", "video_generation"),
        ],
        runtime_mode="managed_process",
        protocol="openai-compatible",
    )

    assert {item["model_type"] for item in models} == {
        "llm",
        "image_generation",
        "audio_stt",
        "audio_tts",
        "audio_processing",
        "video_generation",
    }
    assert next(item for item in models if item["model_type"] == "audio_tts")[
        "capabilities"
    ] == ["speech_generation"]
    assert next(item for item in models if item["model_type"] == "audio_stt")[
        "audio_capabilities"
    ]["schema"] == "ai2apps.audio-capabilities/v1"


def test_audio_model_manifest_validates_signed_capability_profile():
    model = _model("example.audio", "tts", "audio_tts")
    model["audio_capabilities"] = {
        "schema": "ai2apps.audio-capabilities/v1",
        "operations": ["audio_speech"],
        "languages": ["zh", "en", "zh"],
        "formats": {"input": [], "output": ["wav", "pcm"]},
        "streaming": {"mode": "unsupported", "formats": []},
        "tts": {
            "named_voices": {
                "mode": "native",
                "voices": ["narrator", "assistant"],
            },
            "speed": {"mode": "native", "minimum": 0.5, "maximum": 2.0},
            "emotion": {"mode": "fallback"},
        },
    }

    normalized = validate_package_models(
        "example.audio",
        [model],
        runtime_mode="process",
        protocol="ai2apps-model-worker/v1",
    )

    profile = normalized[0]["audio_capabilities"]
    assert profile["languages"] == ["en", "zh"]
    assert profile["tts"]["named_voices"]["voices"] == [
        "narrator",
        "assistant",
    ]


def test_audio_model_manifest_rejects_unknown_codec_claim():
    model = _model("example.audio", "stt", "audio_stt")
    model["audio_capabilities"] = {
        "schema": "ai2apps.audio-capabilities/v1",
        "operations": ["audio_transcription"],
        "formats": {"input": ["caf"], "output": []},
        "streaming": {"mode": "unsupported", "formats": []},
    }

    with pytest.raises(ModelProviderContractError, match="unsupported format"):
        validate_package_models(
            "example.audio",
            [model],
            runtime_mode="process",
            protocol="ai2apps-model-worker/v1",
        )


@pytest.mark.parametrize(
    ("models", "runtime_mode", "message"),
    [
        ([_model("other", "chat", "llm")], "managed_process", "must start"),
        ([_model("example.provider", "chat", "unknown")], "managed_process", "unsupported"),
        ([_model("example.provider", "chat", "llm")], "in_process", "managed_process"),
    ],
)
def test_model_manifest_fails_closed(models, runtime_mode, message):
    with pytest.raises(ModelProviderContractError, match=message):
        validate_package_models(
            "example.provider",
            models,
            runtime_mode=runtime_mode,
            protocol="openai-compatible",
        )


def test_model_manifest_normalizes_pinned_worker_weights():
    model = _model("example.provider", "chat", "llm")
    model["weights"] = {
        "provider": "huggingface",
        "repo_id": "mlx-community/Example-4bit",
        "revision": "A" * 40,
        "preparation": {"recipe": "native"},
    }

    normalized = validate_package_models(
        "example.provider",
        [model],
        runtime_mode="process",
        protocol="ai2apps-model-worker/v1",
    )

    assert normalized[0]["weights"] == {
        "provider": "huggingface",
        "repo_id": "mlx-community/Example-4bit",
        "revision": "a" * 40,
        "preparation": {"recipe": "native"},
    }


def test_model_manifest_rejects_mutable_weight_revision():
    model = _model("example.provider", "chat", "llm")
    model["weights"] = {
        "provider": "huggingface",
        "repo_id": "mlx-community/Example-4bit",
        "revision": "main",
    }
    with pytest.raises(ModelProviderContractError, match="immutable"):
        validate_package_models(
            "example.provider",
            [model],
            runtime_mode="process",
            protocol="ai2apps-model-worker/v1",
        )


def test_enabled_service_models_enter_and_leave_the_live_catalog(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    normalized = validate_package_models(
        "example.provider",
        [_model("example.provider", "image-v1", "image_generation")],
        runtime_mode="external",
        protocol="openai-compatible",
    )
    service = runtime.services.ensure_service(
        service_key="example.provider",
        package_id="example.provider",
        package_version="1.0.0",
        display_name="Example Provider",
        runtime_mode=ServiceRuntimeMode.EXTERNAL,
        source="installed",
        config={"models": list(normalized), "protocol": "openai-compatible"},
    )
    runtime.services.ensure_instance(
        service_id=service.id,
        provider_key="package:example.provider",
        status=ServiceInstanceStatus.RUNNING,
        endpoint="http://127.0.0.1:9876",
    )

    catalog = list_package_models(runtime)
    assert [model.id for model in catalog] == ["example.provider/image-v1"]
    assert catalog[0].public_catalog_entry()["model_type"] == "image_generation"

    runtime.services.set_instance_status(
        runtime.services.get_instance_for_service(service.id).id,
        ServiceInstanceStatus.DISABLED,
    )
    assert list_package_models(runtime) == ()


@pytest.mark.asyncio
async def test_json_proxy_rewrites_public_id_to_provider_upstream(monkeypatch, tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    normalized = validate_package_models(
        "example.chat",
        [_model("example.chat", "assistant", "llm")],
        runtime_mode="external",
        protocol="openai-compatible",
    )
    service = runtime.services.ensure_service(
        service_key="example.chat",
        package_id="example.chat",
        package_version="1.0.0",
        display_name="Chat Provider",
        runtime_mode=ServiceRuntimeMode.EXTERNAL,
        source="installed",
        config={"models": list(normalized)},
    )
    runtime.services.ensure_instance(
        service_id=service.id,
        provider_key="package:example.chat",
        status=ServiceInstanceStatus.RUNNING,
        endpoint="http://provider.test",
    )
    model = list_package_models(runtime)[0]
    original_client = httpx.AsyncClient

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        assert body["model"] == "upstream-assistant"
        return httpx.Response(200, json={"model": body["model"], "choices": []})

    monkeypatch.setattr(
        "ai2apps.model_providers.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    response = await proxy_package_json(
        model,
        "chat_completions",
        {"model": model.id, "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200
    assert json.loads(response.body)["model"] == "upstream-assistant"


def test_qwen35_provider_is_a_standalone_model_package():
    source = Path(__file__).resolve().parents[1] / "packages" / "qwen35-provider"
    manifest = yaml.safe_load((source / "service.yaml").read_text(encoding="utf-8"))
    parsed = ServicePackageArchive._manifest(manifest)

    assert parsed.service_key == "ai2apps.qwen35"
    assert parsed.protocol == "openai-compatible"
    assert {item["upstream_id"] for item in parsed.models} == {
        "mlx-community/Qwen3.5-0.8B-4bit",
        "mlx-community/Qwen3.5-2B-4bit",
    }
    assert parsed.permissions["model_weights"]["huggingface_cache"] == "read"
    assert parsed.permissions["accelerator"]["metal"] is True
    assert not list(source.rglob("*.safetensors"))


def test_host_reads_cache_moe_recipe_from_worker_manifest_without_importing_package():
    package_root = (
        Path(__file__).resolve().parents[1]
        / "packages"
        / "omlx-model-deepseek-v4-flash-2bit"
    )
    manifest = yaml.safe_load((package_root / "service.yaml").read_text())
    record = SimpleNamespace(
        status=SimpleNamespace(value="active"),
        protocol="ai2apps-model-worker/v1",
        store_path=str(package_root),
        manifest=manifest,
    )
    runtime = SimpleNamespace(
        package_repository=SimpleNamespace(installed=lambda: (record,))
    )

    recipes = installed_model_preparation_recipes(runtime)

    assert len(recipes) == 1
    assert recipes[0]["id"] == "deepseek-v4-flash-2bit"
    assert recipes[0]["sources"][0]["revision"] == (
        "722bf559b7de93575b2320973cf2002e05bfe6c9"
    )
    assert Path(recipes[0]["engine"]["scope_asset"]).is_file()
    assert Path(recipes[0]["engine"]["scope_pack"]).is_file()


def test_host_exposes_native_worker_checkpoint_as_downloadable_package_recipe(
    tmp_path, monkeypatch
):
    package_root = (
        Path(__file__).resolve().parents[1] / "packages" / "omlx-model-qwen38"
    )
    manifest = yaml.safe_load((package_root / "service.yaml").read_text())
    record = SimpleNamespace(
        status=SimpleNamespace(value="active"),
        protocol="ai2apps-model-worker/v1",
        service_key="ai2apps.model.qwen38",
        store_path=str(package_root),
        manifest=manifest,
    )
    runtime = SimpleNamespace(
        package_repository=SimpleNamespace(installed=lambda: (record,))
    )
    hub = tmp_path / "hub"
    monkeypatch.setattr(
        ManagedServiceSupervisor, "_huggingface_hub_cache", lambda: hub
    )

    recipe = installed_model_preparation_recipes(runtime)[0]
    assert recipe["recipe"] == "native"
    assert recipe["service_key"] == "ai2apps.model.qwen38"
    assert recipe["installed"] is False
    assert recipe["sources"][0]["repo_id"] == "unsloth/Qwen3.8-27B-NVFP4"

    snapshot = (
        hub
        / "models--unsloth--Qwen3.8-27B-NVFP4"
        / "snapshots"
        / recipe["sources"][0]["revision"]
    )
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text("{}")
    (snapshot / "model.safetensors").write_bytes(b"weights")

    assert installed_model_preparation_recipes(runtime)[0]["installed"] is True


def test_sensevoice_recipe_keeps_hidden_punctuation_checkpoint_dependency(
    tmp_path,
    monkeypatch,
):
    package_root = Path(__file__).resolve().parents[1] / "packages"
    records = []
    for name in ("omlx-model-sensevoice-small", "omlx-punctuation-restorer"):
        root = package_root / name
        manifest = yaml.safe_load((root / "service.yaml").read_text())
        records.append(
            SimpleNamespace(
                status=SimpleNamespace(value="active"),
                protocol="ai2apps-model-worker/v1",
                service_key=manifest["id"],
                store_path=str(root),
                manifest=manifest,
            )
        )
    monkeypatch.setattr(
        ManagedServiceSupervisor,
        "_huggingface_hub_cache",
        lambda: tmp_path / "hub",
    )
    runtime = SimpleNamespace(
        package_repository=SimpleNamespace(installed=lambda: tuple(records))
    )

    recipes = {
        recipe["id"]: recipe
        for recipe in installed_model_preparation_recipes(runtime)
    }
    sensevoice = recipes["ai2apps.model.sensevoice-small/default"]
    punctuation = recipes["ai2apps.model.punctuation-restorer/default"]

    assert sensevoice["required_model_ids"] == (punctuation["id"],)
    assert punctuation["internal"] is True
    assert punctuation["id"] not in {
        item["id"] for item in AI2AppsInstaller.catalog(tuple(recipes.values()))
    }
    assert sensevoice["installed"] is False


def test_sensevoice_recipe_is_ready_only_after_required_checkpoint(
    tmp_path,
    monkeypatch,
):
    package_root = Path(__file__).resolve().parents[1] / "packages"
    records = []
    for name in ("omlx-model-sensevoice-small", "omlx-punctuation-restorer"):
        root = package_root / name
        manifest = yaml.safe_load((root / "service.yaml").read_text())
        records.append(
            SimpleNamespace(
                status=SimpleNamespace(value="active"),
                protocol="ai2apps-model-worker/v1",
                service_key=manifest["id"],
                store_path=str(root),
                manifest=manifest,
            )
        )
    hub = tmp_path / "hub"
    monkeypatch.setattr(
        ManagedServiceSupervisor,
        "_huggingface_hub_cache",
        lambda: hub,
    )
    runtime = SimpleNamespace(
        package_repository=SimpleNamespace(installed=lambda: tuple(records))
    )

    for record in records:
        model = record.manifest["models"][0]
        weights = model["weights"]
        snapshot = (
            hub
            / ("models--" + weights["repo_id"].replace("/", "--"))
            / "snapshots"
            / weights["revision"]
        )
        snapshot.mkdir(parents=True)
        if model["id"] == "ai2apps.model.punctuation-restorer/default":
            (snapshot / "config.yaml").write_text("model: ct-transformer\n")
            (snapshot / "model.int8.onnx").write_bytes(b"onnx")
        else:
            (snapshot / "config.json").write_text("{}")
            (snapshot / "model.safetensors").write_bytes(b"weights")

    recipes = {
        recipe["id"]: recipe
        for recipe in installed_model_preparation_recipes(runtime)
    }
    assert recipes["ai2apps.model.punctuation-restorer/default"]["installed"] is True
    assert recipes["ai2apps.model.sensevoice-small/default"]["installed"] is True


@pytest.mark.asyncio
async def test_native_package_recipe_downloads_pinned_cache_and_activates_worker(
    tmp_path,
    monkeypatch,
):
    model_root = tmp_path / "shared" / "model-weights"
    hub = model_root / "huggingface" / "hub"
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_MODE", "shared")
    monkeypatch.setenv("AI2APPS_INSTANCE_ID", "app-one")
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_ROOT", str(model_root))
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    completed = SimpleNamespace(
        task_id="hf-native",
        status=SimpleNamespace(value="completed"),
        progress=100.0,
        downloaded_size=42,
        total_size=42,
        error="",
    )

    class Downloader:
        model_dir = tmp_path / "models"

        async def start_download(self, repo_id, token, **options):
            assert repo_id == "unsloth/Qwen3.8-27B-NVFP4"
            assert token == "hf_fixture"
            assert options == {
                "revision": "a" * 40,
                "notify_complete": False,
                "cache_mode": True,
            }
            return completed

    activated = []

    async def on_ready(recipe):
        activated.append(recipe["service_key"])

    recipe = {
        "id": "ai2apps.model.qwen38/qwen3.8-27b-nvfp4",
        "name": "Qwen3.8 27B NVFP4",
        "recipe": "native",
        "service_key": "ai2apps.model.qwen38",
        "sources": (
            {
                "id": "huggingface",
                "label": "HuggingFace",
                "repo_id": "unsloth/Qwen3.8-27B-NVFP4",
                "revision": "a" * 40,
            },
        ),
        "storage_policies": ("keep_source",),
        "memory_tiers": (),
        "engine": {},
    }
    installer = AI2AppsInstaller(
        Downloader(), package_recipes=(recipe,), on_ready=on_ready
    )

    task = await installer.start(
        recipe["id"], "huggingface", "auto", "hf_fixture", "keep_source"
    )
    await installer._runners[task.task_id]

    assert task.status.value == "completed"
    assert task.progress == 100.0
    assert activated == ["ai2apps.model.qwen38"]
    references = list_shared_model_references(hub)
    assert [(item.instance_id, item.repo_id, item.revision) for item in references] == [
        ("app-one", "unsloth/Qwen3.8-27B-NVFP4", "a" * 40)
    ]


@pytest.mark.asyncio
async def test_native_recipe_prepares_hidden_required_model_before_primary(
    tmp_path,
    monkeypatch,
):
    model_root = tmp_path / "shared" / "model-weights"
    hub = model_root / "huggingface" / "hub"
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_MODE", "shared")
    monkeypatch.setenv("AI2APPS_INSTANCE_ID", "app-one")
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_ROOT", str(model_root))
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    downloads = []

    class Downloader:
        model_dir = tmp_path / "models"

        async def start_download(self, repo_id, token, **options):
            downloads.append((repo_id, options["revision"]))
            return SimpleNamespace(
                task_id=f"hf-{len(downloads)}",
                status=SimpleNamespace(value="completed"),
                progress=100.0,
                downloaded_size=42,
                total_size=42,
                error="",
                cache_hit=False,
            )

    punctuation = {
        "id": "ai2apps.model.punctuation-restorer/default",
        "name": "Punctuation Restorer",
        "recipe": "native",
        "service_key": "ai2apps.model.punctuation-restorer",
        "internal": True,
        "sources": (
            {
                "id": "huggingface",
                "repo_id": "owner/punctuation",
                "revision": "a" * 40,
            },
        ),
        "storage_policies": ("keep_source",),
        "memory_tiers": (),
        "engine": {},
    }
    sensevoice = {
        "id": "ai2apps.model.sensevoice-small/default",
        "name": "SenseVoice Small",
        "recipe": "native",
        "service_key": "ai2apps.model.sensevoice-small",
        "required_model_ids": (punctuation["id"],),
        "sources": (
            {
                "id": "huggingface",
                "repo_id": "owner/sensevoice",
                "revision": "b" * 40,
            },
        ),
        "storage_policies": ("keep_source",),
        "memory_tiers": (),
        "engine": {},
    }
    activated = []

    async def on_ready(recipe):
        activated.append(recipe["service_key"])

    installer = AI2AppsInstaller(
        Downloader(),
        package_recipes=(punctuation, sensevoice),
        on_ready=on_ready,
    )

    assert [item["id"] for item in installer.catalog((punctuation, sensevoice))] == [
        sensevoice["id"]
    ]
    task = await installer.start(
        sensevoice["id"], "huggingface", "auto", "", "keep_source"
    )
    await installer._runners[task.task_id]

    assert task.status.value == "completed"
    assert downloads == [
        ("owner/punctuation", "a" * 40),
        ("owner/sensevoice", "b" * 40),
    ]
    assert activated == [
        "ai2apps.model.punctuation-restorer",
        "ai2apps.model.sensevoice-small",
    ]


def test_cold_start_reconciles_native_recipe_and_removes_stale_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    model_root = tmp_path / "shared" / "model-weights"
    hub = model_root / "huggingface" / "hub"
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_MODE", "shared")
    monkeypatch.setenv("AI2APPS_INSTANCE_ID", "app-one")
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_ROOT", str(model_root))
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    publish_shared_model_reference(
        hub, instance_id="app-one", repo_id="owner/stale", revision="a" * 40
    )
    recipes = (
        {
            "id": "native-ready",
            "recipe": "native",
            "installed": True,
            "sources": (
                {"repo_id": "owner/ready", "revision": "b" * 40},
            ),
        },
        {
            "id": "native-absent",
            "recipe": "native",
            "installed": False,
            "sources": (
                {"repo_id": "owner/absent", "revision": "c" * 40},
            ),
        },
    )

    result = reconcile_installed_shared_model_references(tmp_path / "models", recipes)

    assert result.expected_references == 1
    assert result.published_references == 1
    assert result.removed_references == 1
    references = list_shared_model_references(hub)
    assert [(item.repo_id, item.revision) for item in references] == [
        ("owner/ready", "b" * 40)
    ]


def test_cold_start_uses_converted_install_manifest_source_retention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    model_root = tmp_path / "shared" / "model-weights"
    hub = model_root / "huggingface" / "hub"
    models = tmp_path / "models"
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_MODE", "shared")
    monkeypatch.setenv("AI2APPS_INSTANCE_ID", "app-one")
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_ROOT", str(model_root))
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    recipe = {
        "id": "converted",
        "recipe": "ai2apps/cache-moe/v1",
        "sources": ({"repo_id": "owner/converted", "revision": "d" * 40},),
    }
    install = models / "owner" / "converted" / "ai2apps-model.json"
    install.parent.mkdir(parents=True)
    manifest = {
        "format": "ai2apps-cache-moe-model",
        "version": 2,
        "source": {"repo_id": "owner/converted", "revision": "d" * 40},
    }
    install.write_text(json.dumps(manifest))

    retained = reconcile_installed_shared_model_references(models, (recipe,))
    assert retained.expected_references == 1
    assert len(list_shared_model_references(hub)) == 1

    manifest["checkpoint_layout"] = {"source_retained": False}
    install.write_text(json.dumps(manifest))
    released = reconcile_installed_shared_model_references(models, (recipe,))
    assert released.expected_references == 0
    assert released.removed_references == 1
    assert list_shared_model_references(hub) == ()


def test_existing_pinned_local_checkout_is_imported_without_copying(tmp_path):
    source = tmp_path / "models" / "owner" / "model"
    source.mkdir(parents=True)
    revision = "a" * 40
    contents = {
        "config.json": b"{}",
        "model.safetensors": b"weights",
    }
    tree_files = {}
    for name, content in contents.items():
        path = source / name
        path.write_bytes(content)
        tree_files[name] = {
            "size": len(content),
            "lfs_sha256": hashlib.sha256(content).hexdigest(),
            "blob_id": "b" * 40,
        }
    trees = source / ".cache" / "huggingface" / "trees"
    trees.mkdir(parents=True)
    (trees / f"{revision}.json").write_text(
        json.dumps({"format_version": 1, "files": tree_files})
    )

    snapshot = import_local_checkpoint_to_hf_cache(
        source, "owner/model", revision, tmp_path / "hub"
    )

    assert snapshot is not None
    assert (snapshot / "config.json").read_bytes() == b"{}"
    assert (snapshot / "model.safetensors").read_bytes() == b"weights"
    blob = (snapshot / "model.safetensors").resolve()
    assert blob.stat().st_ino == (source / "model.safetensors").stat().st_ino


def test_local_checkout_import_rejects_damaged_existing_cache_blob(tmp_path):
    source = tmp_path / "models" / "owner" / "model"
    source.mkdir(parents=True)
    revision = "a" * 40
    content = b"trusted weights"
    digest = hashlib.sha256(content).hexdigest()
    (source / "model.safetensors").write_bytes(content)
    trees = source / ".cache" / "huggingface" / "trees"
    trees.mkdir(parents=True)
    (trees / f"{revision}.json").write_text(
        json.dumps(
            {
                "format_version": 1,
                "files": {
                    "model.safetensors": {
                        "size": len(content),
                        "lfs_sha256": digest,
                    }
                },
            }
        )
    )
    blob = tmp_path / "hub" / "models--owner--model" / "blobs" / digest
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"tampered bytes")

    assert (
        import_local_checkpoint_to_hf_cache(
            source, "owner/model", revision, tmp_path / "hub"
        )
        is None
    )


def test_concurrent_local_checkout_import_publishes_one_complete_snapshot(tmp_path):
    source = tmp_path / "models" / "owner" / "model"
    source.mkdir(parents=True)
    revision = "c" * 40
    contents = {
        "config.json": b"{}",
        "model.safetensors": b"concurrent weights",
    }
    tree_files = {}
    for name, content in contents.items():
        path = source / name
        path.write_bytes(content)
        tree_files[name] = {
            "size": len(content),
            "lfs_sha256": hashlib.sha256(content).hexdigest(),
        }
    trees = source / ".cache" / "huggingface" / "trees"
    trees.mkdir(parents=True)
    (trees / f"{revision}.json").write_text(
        json.dumps({"format_version": 1, "files": tree_files})
    )
    hub = tmp_path / "hub"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda _: import_local_checkpoint_to_hf_cache(
                    source, "owner/model", revision, hub
                ),
                range(16),
            )
        )

    expected = hub / "models--owner--model" / "snapshots" / revision
    assert results == [expected] * 16
    assert checkpoint_is_complete(expected)
    assert not list(expected.parent.glob(f".{revision}.*.partial"))
    lock_root = hub / ".ai2apps-locks"
    assert lock_root.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in lock_root.iterdir())


def test_local_checkout_import_revalidates_an_existing_complete_snapshot(tmp_path):
    source = tmp_path / "models" / "owner" / "model"
    source.mkdir(parents=True)
    revision = "d" * 40
    contents = {
        "config.json": b"{}",
        "model.safetensors": b"trusted weights",
    }
    tree_files = {}
    for name, content in contents.items():
        (source / name).write_bytes(content)
        tree_files[name] = {
            "size": len(content),
            "lfs_sha256": hashlib.sha256(content).hexdigest(),
        }
    trees = source / ".cache" / "huggingface" / "trees"
    trees.mkdir(parents=True)
    (trees / f"{revision}.json").write_text(
        json.dumps({"format_version": 1, "files": tree_files})
    )
    hub = tmp_path / "hub"

    snapshot = import_local_checkpoint_to_hf_cache(
        source, "owner/model", revision, hub
    )
    assert snapshot is not None
    (snapshot / "model.safetensors").resolve().write_bytes(b"tampered bytes")

    assert (
        import_local_checkpoint_to_hf_cache(
            source, "owner/model", revision, hub
        )
        is None
    )


def test_registry_model_service_build_preserves_runtime_identity_and_policy(tmp_path):
    package_root = (
        Path(__file__).resolve().parents[1] / "packages" / "omlx-model-qwen38"
    )
    archive = tmp_path / "model-qwen38.ai2service"
    inspected = build_package(package_root, archive)
    indexed = {item.path for item in inspected.files}

    assert "service.yaml" in indexed
    assert "README.md" not in indexed
    assert not any("__pycache__" in item or item.endswith(".pyc") for item in indexed)

    manager = RegistryPackageManager(
        cloud=None,
        root=tmp_path / "registry",
        secrets=None,
        extension_manager=None,
        service_manager=None,
    )
    bundle = manager._service_bundle(
        inspected,
        {"payload": {"publisherId": "ai2apps"}, "signature": {"value": "fixture"}},
    )

    assert bundle.manifest.service_key == "ai2apps.model.qwen38"
    assert bundle.manifest.models[0]["id"].startswith("ai2apps.model.qwen38/")
    assert bundle.manifest.permissions["model_weights"]["huggingface_cache"] == "read"
    assert bundle.manifest.permissions["accelerator"]["metal"] is True
    assert bundle.manifest.compatibility["os"] == ["macos"]
    assert bundle.manifest.compatibility["architectures"] == ["arm64"]
    runtime_dependency = bundle.manifest.raw["requires"]["services"][0]
    assert runtime_dependency["id"] == "ai2apps.runtime.omlx"
    assert {"mlx", "model-worker-v1", "vlm", "nvfp4"}.issubset(
        runtime_dependency["capabilities"]
    )


def test_package_conversation_route_precedes_legacy_local_alias_resolution():
    source = (Path(__file__).parents[1] / "omlx" / "server.py").read_text()
    package_route = source.index(
        "package_model = resolve_package_model(\n"
        "        _server_state.ai2apps_platform_runtime, request.model"
    )
    legacy_local_route = source.index(
        "resolved_local = resolve_model_id(request.model) or request.model"
    )

    assert package_route < legacy_local_route


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS sandbox profile")
def test_metal_model_service_gets_explicit_gpu_sandbox_rules(tmp_path):
    package = tmp_path / "package"
    data = tmp_path / "data"
    temporary = tmp_path / "temporary"
    package.mkdir()
    data.mkdir()
    temporary.mkdir()
    supervisor = object.__new__(ManagedServiceSupervisor)

    command = supervisor._sandbox_command(
        ("/usr/bin/true",),
        package,
        data,
        temporary,
        network=False,
        metal=True,
    )
    profile = (data / "service.sb").read_text(encoding="utf-8")

    assert command[:2] == ("/usr/bin/sandbox-exec", "-f")
    assert "(allow mach-lookup)" not in profile
    assert 'iokit-user-client-class "IOGPUDeviceUserClient"' in profile
    assert 'global-name "com.apple.MTLCompilerService"' in profile
