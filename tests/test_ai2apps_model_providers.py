# SPDX-License-Identifier: Apache-2.0
"""Installable multi-modal Model Provider contracts."""

from __future__ import annotations

import json
import platform
from pathlib import Path

import httpx
import pytest
import yaml

from ai2apps.config import PlatformConfig
from ai2apps.model_providers import (
    ModelProviderContractError,
    list_package_models,
    proxy_package_json,
    validate_package_models,
)
from ai2apps.packages.archive import ServicePackageArchive
from ai2apps.packages.supervisor import ManagedServiceSupervisor
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.services import ServiceInstanceStatus, ServiceRuntimeMode


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
    assert 'iokit-user-client-class "IOGPUDeviceUserClient"' in profile
    assert 'global-name "com.apple.MTLCompilerService"' in profile
