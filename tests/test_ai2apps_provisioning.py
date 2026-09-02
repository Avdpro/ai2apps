from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.provisioning import create_provisioning_router
from ai2apps.identity import RequestPrincipal
from ai2apps.provisioning.orchestrator import CapabilityProvisioner
from ai2apps.provisioning.profiles import (
    CapabilityProfileRegistry,
    profile_device_compatibility,
)
from ai2apps.provisioning.repository import ProvisioningSessionRepository
from ai2apps.storage import PlatformDatabase

APP_INSTANCE_ID = "appi_video_studio"


class _ExtensionManager:
    def __init__(self, app_id: str = "ai2apps.video-studio") -> None:
        self.app_id = app_id

    def require_instance_access(self, instance_id, _principal) -> None:
        if instance_id != APP_INSTANCE_ID:
            raise AssertionError(instance_id)

    def instance_entry(self, instance_id, *, principal):
        self.require_instance_access(instance_id, principal)
        return {"instance_id": instance_id, "app_key": self.app_id}


def _api_runtime(provisioning, app_id: str = "ai2apps.video-studio"):
    return SimpleNamespace(
        provisioning=provisioning,
        extension_manager=_ExtensionManager(app_id),
    )


def _app_headers() -> dict[str, str]:
    return {"X-AI2Apps-App-Instance": APP_INSTANCE_ID}


def _apple_device(memory_gib: float) -> dict:
    return {
        "schema": "ai2apps.device-profile/v1",
        "os": "macos",
        "architecture": "arm64",
        "system_memory_gib": memory_gib,
        "accelerator": {
            "vendor": "apple",
            "api": "metal",
            "unified_memory_gib": memory_gib,
        },
    }


def test_provisioner_binds_one_installer_to_both_checkpoint_downloaders(
    tmp_path,
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    provisioner = CapabilityProvisioner(
        runtime=SimpleNamespace(
            package_repository=SimpleNamespace(installed=lambda: ()),
            package_manager=None,
        ),
        repository=ProvisioningSessionRepository(database),
    )
    hf_downloader = SimpleNamespace(model_dir=tmp_path / "models")
    ms_downloader = SimpleNamespace(model_dir=tmp_path / "models")

    installer = provisioner.bind_checkpoint_downloaders(
        hf_downloader, ms_downloader
    )
    rebound = provisioner.refresh_model_installer()

    assert rebound is installer
    assert installer.hf_downloader is hf_downloader
    assert installer.ms_downloader is ms_downloader


def test_legacy_hf_binding_preserves_registered_modelscope_downloader(
    tmp_path,
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    provisioner = CapabilityProvisioner(
        runtime=SimpleNamespace(
            package_repository=SimpleNamespace(installed=lambda: ()),
            package_manager=None,
        ),
        repository=ProvisioningSessionRepository(database),
    )
    hf_downloader = SimpleNamespace(model_dir=tmp_path / "models")
    ms_downloader = SimpleNamespace(model_dir=tmp_path / "models")
    provisioner.bind_checkpoint_downloaders(hf_downloader, ms_downloader)

    installer = provisioner.bind_hf_downloader(hf_downloader)

    assert installer.ms_downloader is ms_downloader


def test_platform_registry_binds_trusted_checkpoint_acquisition(tmp_path) -> None:
    registry_packages = SimpleNamespace(
        root=tmp_path / "packages/registry-v1",
        cloud=SimpleNamespace(),
        repository_fingerprint="a" * 64,
    )
    provisioner = CapabilityProvisioner(
        runtime=SimpleNamespace(
            package_repository=SimpleNamespace(installed=lambda: ()),
            package_manager=None,
            registry_packages=registry_packages,
        ),
        repository=SimpleNamespace(),
    )

    installer = provisioner.bind_checkpoint_downloaders(
        SimpleNamespace(model_dir=tmp_path / "models")
    )

    assert installer.checkpoint_acquisition is provisioner.checkpoint_acquisition
    assert provisioner.checkpoint_acquisition.cache.root == (
        tmp_path / "packages/checkpoint-cache-v1"
    )


@pytest.mark.asyncio
async def test_acpf_checkpoint_activation_uses_service_lifecycle_not_inference_queue(
    tmp_path,
) -> None:
    restarted = []
    marked = []

    async def restart(service_key):
        restarted.append(service_key)

    runtime = SimpleNamespace(
        package_repository=SimpleNamespace(installed=lambda: ()),
        package_manager=SimpleNamespace(restart=restart),
        worker_resources=SimpleNamespace(mark_started=marked.append),
    )
    provisioner = CapabilityProvisioner(
        runtime=runtime,
        repository=ProvisioningSessionRepository(
            PlatformDatabase(tmp_path / "platform.sqlite3")
        ),
    )
    provisioner.repository.database.initialize()
    installer = provisioner.bind_checkpoint_downloaders(
        SimpleNamespace(model_dir=tmp_path / "models")
    )
    await installer.on_ready({"service_key": "ai2apps.model.qwen3-tts-0.6b"})

    assert restarted == ["ai2apps.model.qwen3-tts-0.6b"]
    assert marked == ["ai2apps.model.qwen3-tts-0.6b"]


@pytest.mark.asyncio
async def test_acpf_verification_starts_declared_service_without_model_inference(
    tmp_path,
) -> None:
    started = []

    async def start(service_key):
        started.append(service_key)

    runtime = SimpleNamespace(
        package_manager=SimpleNamespace(start=start),
        worker_resources=SimpleNamespace(mark_started=lambda _key: None),
    )
    provisioner = CapabilityProvisioner(
        runtime=runtime,
        repository=ProvisioningSessionRepository(
            PlatformDatabase(tmp_path / "platform.sqlite3")
        ),
    )
    provisioner.repository.database.initialize()
    session = {
        "plan": {
            "stack": {
                "components": [
                    {
                        "kind": "verify",
                        "service_key": "example.model",
                    }
                ]
            }
        },
    }

    await provisioner._start_verification_services(session)
    assert started == ["example.model"]


def test_video_studio_profile_recommends_quantization_by_memory() -> None:
    registry = CapabilityProfileRegistry()

    expected = (
        (48, "apple-metal-h3-q4"),
        (128, "apple-metal-h3-q8"),
        (192, "apple-metal-h3-q8"),
    )
    for memory, profile_id in expected:
        candidates = registry.candidates(
            "ai2apps.video-studio",
            "video.generation",
            _apple_device(memory),
            recommended=True,
        )
        assert candidates[0]["id"] == profile_id


def test_video_studio_compatible_profiles_exclude_bf16() -> None:
    registry = CapabilityProfileRegistry()
    candidates = registry.candidates(
        "ai2apps.video-studio",
        "video.generation",
        _apple_device(128),
        recommended=False,
    )
    assert {item["id"] for item in candidates} == {
        "apple-metal-h3-q4",
        "apple-metal-h3-q8",
    }


def test_capability_presentation_is_trusted_profile_metadata() -> None:
    capability = CapabilityProfileRegistry().capability(
        "ai2apps.video-studio", "video.generation"
    )

    assert capability is not None
    assert capability["presentation"]["title"] == "配置本地视频生成"
    assert capability["presentation"]["icon"] == "clapperboard"
    assert capability["presentation"]["steps"]["verify"] == "启动并验证视频生成服务"


def test_general_chat_local_model_is_optional_device_recommendation() -> None:
    registry = CapabilityProfileRegistry()
    capability = registry.capability("ai2apps.general-chat", "text.chat.local")

    assert capability is not None
    assert capability["trigger"] == "recommended_optional"
    assert capability["selection_mode"] == "multiple"
    assert capability["requirements"] == {"operations": ["conversation"]}
    assert capability["presentation"]["title"] == "选择并安装本地聊天模型"
    assert registry.candidates(
        "ai2apps.general-chat",
        "text.chat.local",
        _apple_device(16),
        recommended=True,
    )[0]["id"] == "apple-metal-qwen36-35b-4bit"
    assert registry.candidates(
        "ai2apps.general-chat",
        "text.chat.local",
        _apple_device(32),
        recommended=True,
    )[0]["id"] == "apple-metal-deepseek-v4-flash-2bit"
    assert registry.candidates(
        "ai2apps.general-chat",
        "text.chat.local",
        _apple_device(64),
        recommended=True,
    )[0]["id"] == "apple-metal-deepseek-v4-flash"
    assert not registry.candidates(
        "ai2apps.general-chat",
        "text.chat.local",
        _apple_device(15),
        recommended=True,
    )
    deepseek = next(
        profile
        for profile in capability["profiles"]
        if profile["id"] == "apple-metal-deepseek-v4-flash"
    )
    compatible, reasons = profile_device_compatibility(deepseek, _apple_device(8))
    assert compatible is False
    assert reasons == ("至少需要 48 GiB 统一内存",)
    profile_ids = {profile["id"] for profile in capability["profiles"]}
    assert {
        "apple-metal-qwen35-2b-4bit",
        "apple-metal-qwen35-08b-4bit",
        "apple-metal-qwen38-27b-nvfp4",
        "apple-metal-qwen38-flash-next-4bit",
        "apple-metal-ornith15-35b-vision-4bit",
        "apple-metal-glm53-flash-4bit-mtp",
    }.issubset(profile_ids)
    recommended_ids = {
        profile["id"]
        for profile in registry.candidates(
            "ai2apps.general-chat",
            "text.chat.local",
            _apple_device(128),
            recommended=True,
        )
    }
    assert recommended_ids == {"apple-metal-deepseek-v4-flash"}


def test_chat_multi_model_plan_merges_simple_and_component_profiles(
    tmp_path, monkeypatch
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    provisioner = CapabilityProvisioner(
        runtime=SimpleNamespace(
            package_repository=SimpleNamespace(active=lambda _key: None),
            registry_packages=None,
            package_manager=None,
        ),
        repository=ProvisioningSessionRepository(database),
    )
    monkeypatch.setattr(
        "ai2apps.provisioning.orchestrator.device_profile",
        lambda: _apple_device(16),
    )

    result = provisioner.ensure(
        actor_id="local",
        installation_id="local",
        app_instance_id=APP_INSTANCE_ID,
        app_id="ai2apps.general-chat",
        capability="text.chat.local",
        action_id="install-mixed-local-models",
        requirements={
            "operations": ["conversation"],
            "profileIds": [
                "apple-metal-qwen36-35b-4bit",
                "apple-metal-qwen35-08b-4bit",
            ],
        },
        intent={},
    )

    assert result["status"] == "setup_required"
    components = result["session"]["plan"]["stack"]["components"]
    assert {item.get("model_id") for item in components if item["kind"] == "checkpoint"} == {
        "ai2apps.model.qwen36-35b/qwen3.6-35b-a3b-4bit",
        "ai2apps.qwen35/qwen3.5-0.8b-4bit",
    }
    assert any(
        item["kind"] == "package" and item["service_key"] == "ai2apps.qwen35"
        for item in components
    )


def test_general_chat_audio_registry_includes_all_shipped_voice_models() -> None:
    registry = CapabilityProfileRegistry()
    asr = registry.capability(
        "ai2apps.general-chat", "audio.speech_recognition"
    )
    tts = registry.capability("ai2apps.general-chat", "audio.speech_generation")

    assert asr is not None
    assert tts is not None
    asr_models = {
        profile["stack"]["checkpoint"]["model_id"] for profile in asr["profiles"]
    }
    tts_models = {
        profile["stack"]["checkpoint"]["model_id"] for profile in tts["profiles"]
    }
    assert asr_models == {
        "ai2apps.model.qwen3-asr-0.6b/4bit",
        "ai2apps.model.sensevoice-small/default",
    }
    assert {
        "ai2apps.model.qwen3-tts-1.7b/custom-voice-8bit",
        "ai2apps.model.qwen3-tts-1.7b/base-5bit",
        "ai2apps.model.qwen3-tts-1.7b/voice-design-5bit",
        "ai2apps.model.qwen3-tts-0.6b/custom-voice-6bit",
        "ai2apps.model.cosyvoice3-0.5b/4bit",
        "ai2apps.model.cosyvoice3-0.5b/8bit",
        "ai2apps.model.vibevoice-0.5b/realtime-4bit",
        "ai2apps.model.fish-s2-pro/bf16",
    } == tts_models


def test_chat_can_plan_multiple_local_models_in_one_session(
    tmp_path, monkeypatch
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    provisioner = CapabilityProvisioner(
        runtime=SimpleNamespace(
            package_repository=SimpleNamespace(active=lambda _key: None),
            registry_packages=None,
            package_manager=None,
        ),
        repository=ProvisioningSessionRepository(database),
    )
    monkeypatch.setattr(
        "ai2apps.provisioning.orchestrator.device_profile",
        lambda: _apple_device(128),
    )
    profile_ids = [
        "apple-metal-deepseek-v4-flash",
        "apple-metal-deepseek-v4-flash-2bit",
        "apple-metal-qwen36-35b-4bit",
    ]

    result = provisioner.ensure(
        actor_id="local",
        installation_id="local",
        app_instance_id=APP_INSTANCE_ID,
        app_id="ai2apps.general-chat",
        capability="text.chat.local",
        action_id="install-local-models",
        requirements={"operations": ["conversation"], "profileIds": profile_ids},
        intent={},
    )

    assert result["status"] == "setup_required"
    plan = result["session"]["plan"]
    assert plan["selectionMode"] == "multiple"
    assert plan["profileIds"] == profile_ids
    assert [item["profileId"] for item in plan["profileOptions"] if item["selected"]] == profile_ids
    components = plan["stack"]["components"]
    assert sum(item["phase"] == "runtime" for item in components) == 1
    assert sum(item["phase"] == "provider" for item in components) == 3
    assert sum(item["kind"] == "checkpoint" for item in components) == 3
    assert sum(item["kind"] == "verify" for item in components) == 3


def test_chat_multi_model_plan_rejects_any_incompatible_selection(
    tmp_path, monkeypatch
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    provisioner = CapabilityProvisioner(
        runtime=SimpleNamespace(
            package_repository=SimpleNamespace(active=lambda _key: None),
            registry_packages=None,
            package_manager=None,
        ),
        repository=ProvisioningSessionRepository(database),
    )
    monkeypatch.setattr(
        "ai2apps.provisioning.orchestrator.device_profile",
        lambda: _apple_device(16),
    )

    result = provisioner.ensure(
        actor_id="local",
        installation_id="local",
        app_instance_id=APP_INSTANCE_ID,
        app_id="ai2apps.general-chat",
        capability="text.chat.local",
        action_id="install-local-models",
        requirements={
            "operations": ["conversation"],
            "profileIds": [
                "apple-metal-qwen36-35b-4bit",
                "apple-metal-deepseek-v4-flash",
            ],
        },
        intent={},
    )

    assert result["status"] == "unsupported"


def test_multi_model_plan_is_ready_only_when_every_provider_is_ready(
    tmp_path, monkeypatch
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    provisioner = CapabilityProvisioner(
        runtime=SimpleNamespace(),
        repository=ProvisioningSessionRepository(database),
    )
    plan = {
        "appId": "ai2apps.general-chat",
        "capability": "text.chat.local",
        "profileId": "model-a",
        "profileIds": ["model-a", "model-b"],
        "requirements": {"operations": ["conversation"]},
    }
    ready = {"model-a": {"modelId": "a"}, "model-b": None}
    monkeypatch.setattr(
        provisioner,
        "resolve_ready",
        lambda _app, _capability, _requirements, *, profile_id: ready[profile_id],
    )

    assert provisioner.resolve_plan_ready(plan) is None
    ready["model-b"] = {"modelId": "b"}
    result = provisioner.resolve_plan_ready(plan)
    assert result is not None
    assert result["providers"] == [{"modelId": "a"}, {"modelId": "b"}]


def test_knowledge_semantic_retrieval_uses_generic_acpf_component_stack() -> None:
    registry = CapabilityProfileRegistry()
    capability = registry.capability(
        "ai2apps.knowledge", "knowledge.semantic_retrieval"
    )

    assert capability is not None
    assert capability["trigger"] == "on_feature_request"
    components = capability["profiles"][0]["stack"]["components"]
    assert [item["kind"] for item in components] == [
        "package",
        "package",
        "package",
        "checkpoint",
        "verify",
        "verify",
    ]
    assert components[0]["service_key"] == "ai2apps.runtime.knowledge-rag"
    assert components[1]["service_key"] == "ai2apps.knowledge-vector.lancedb"


def test_acpf_repeated_render_tolerates_lucide_icon_replacement() -> None:
    script = (
        Path(__file__).parents[1]
        / "ai2apps/web/static/js/capability_provisioning.js"
    ).read_text(encoding="utf-8")

    assert "if (mark) mark.setAttribute('data-lucide', presentation.icon);" in script


def test_generic_acpf_profile_rejects_arbitrary_runtime_commands(tmp_path) -> None:
    profile = tmp_path / "unsafe.yaml"
    profile.write_text(
        """
schema: ai2apps.capability-profiles/v1
app_id: example.app
capabilities:
  example.capability:
    profiles:
      - id: unsafe
        stack:
          components:
            - id: runtime
              kind: package
              phase: runtime
              package_id: example/runtime
              service_key: example.runtime
              version: ">=1"
              command: [python, unsafe.py]
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid ACPF package component"):
        CapabilityProfileRegistry((tmp_path,))


def test_knowledge_semantic_probe_plan_has_no_install_side_effects(
    tmp_path, monkeypatch
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    provisioner = CapabilityProvisioner(
        runtime=SimpleNamespace(
            package_repository=SimpleNamespace(active=lambda _key: None),
            services=None,
            registry_packages=None,
            package_manager=None,
        ),
        repository=ProvisioningSessionRepository(database),
    )
    monkeypatch.setattr(
        "ai2apps.provisioning.orchestrator.device_profile",
        lambda: _apple_device(16),
    )

    plan = provisioner.plan(
        "ai2apps.knowledge",
        "knowledge.semantic_retrieval",
        {"operations": ["semantic_search"]},
    )

    assert plan is not None
    assert [step["id"] for step in plan["steps"]] == [
        "rag-native-runtime",
        "vector-service",
        "embedding-provider",
        "embedding-checkpoint",
        "vector-runtime-ready",
        "embedding-ready",
    ]
    assert all(step["status"] == "pending" for step in plan["steps"])
    assert provisioner.repository.list_active() == ()


def test_generic_service_only_stack_can_resolve_ready_without_a_model(
    tmp_path, monkeypatch
) -> None:
    profile = tmp_path / "service.yaml"
    profile.write_text(
        """
schema: ai2apps.capability-profiles/v1
app_id: example.app
capabilities:
  example.search:
    profiles:
      - id: local-service
        priority: 10
        device: {os: [macos], architectures: [arm64]}
        stack:
          components:
            - {id: runtime, kind: package, phase: runtime, package_id: example/runtime, service_key: example.runtime, version: ">=1,<2"}
            - {id: ready, kind: verify, phase: verify, service_key: example.runtime, capabilities: [example-search-v1]}
""",
        encoding="utf-8",
    )
    active = SimpleNamespace(package_version="1.2.0")
    service = SimpleNamespace(
        id="svc_example",
        status="enabled",
        capabilities=("example-search-v1",),
    )
    instance = SimpleNamespace(status="running", health={"status": "ready"})
    services = SimpleNamespace(
        get_service=lambda _key: service,
        get_instance_for_service=lambda _id: instance,
    )
    runtime = SimpleNamespace(
        package_repository=SimpleNamespace(active=lambda _key: active),
        services=services,
    )
    provisioner = CapabilityProvisioner(
        runtime=runtime,
        repository=ProvisioningSessionRepository(
            PlatformDatabase(tmp_path / "platform.sqlite3")
        ),
        profiles=CapabilityProfileRegistry((tmp_path,)),
    )
    provisioner.repository.database.initialize()
    monkeypatch.setattr(
        "ai2apps.provisioning.orchestrator.device_profile",
        lambda: _apple_device(16),
    )

    ready = provisioner.resolve_ready(
        "example.app", "example.search", {}, profile_id="local-service"
    )

    assert ready == {
        "serviceKey": "example.runtime",
        "profileId": "local-service",
        "capability": "example.search",
        "reused": True,
    }


def test_general_chat_audio_profiles_require_explicit_feature_request() -> None:
    registry = CapabilityProfileRegistry()
    expected = {
        "audio.speech_recognition": "speech_recognition",
        "audio.speech_generation": "speech_generation",
    }

    for capability_id, operation in expected.items():
        capability = registry.capability("ai2apps.general-chat", capability_id)
        assert capability is not None
        assert capability["trigger"] == "on_feature_request"
        assert capability["requirements"] == {"operations": [operation]}
        assert capability["presentation"]["confirm_label"] == "同意并配置"
    assert registry.candidates(
        "ai2apps.general-chat",
        "audio.speech_recognition",
        _apple_device(8),
        recommended=True,
    )[0]["id"] == "apple-metal-qwen3-asr-06b-4bit"
    assert registry.candidates(
        "ai2apps.general-chat",
        "audio.speech_generation",
        _apple_device(8),
        recommended=True,
    )[0]["id"] == "apple-metal-qwen3-tts-06b-custom-voice"
    assert registry.candidates(
        "ai2apps.general-chat",
        "audio.speech_generation",
        _apple_device(16),
        recommended=True,
    )[0]["id"] == "apple-metal-qwen3-tts-17b-custom-voice"

    high_tier = next(
        profile
        for profile in registry.capability(
            "ai2apps.general-chat", "audio.speech_generation"
        )["profiles"]
        if profile["id"] == "apple-metal-qwen3-tts-17b-custom-voice"
    )
    compatible, reasons = profile_device_compatibility(high_tier, _apple_device(8))
    assert compatible is False
    assert reasons == ("至少需要 16 GiB 统一内存",)


def test_video_studio_explicit_q4_selection_targets_q4_profile(
    tmp_path, monkeypatch
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    provisioner = CapabilityProvisioner(
        runtime=SimpleNamespace(
            package_repository=SimpleNamespace(active=lambda _key: None),
            registry_packages=None,
            package_manager=None,
        ),
        repository=ProvisioningSessionRepository(database),
    )
    monkeypatch.setattr(
        "ai2apps.provisioning.orchestrator.device_profile",
        lambda: _apple_device(128),
    )
    q4 = "ai2apps.model.minimax-h3/fl2va-4bit"

    result = provisioner.ensure(
        actor_id="local",
        installation_id="local",
        app_instance_id=APP_INSTANCE_ID,
        app_id="ai2apps.video-studio",
        capability="video.generation",
        action_id="configure-generation",
        requirements={"operations": ["text_to_video"], "modelId": q4},
        intent={},
    )

    assert result["status"] == "setup_required"
    assert result["session"]["profileId"] == "apple-metal-h3-q4"
    assert result["session"]["plan"]["stack"]["checkpoint"]["model_id"] == q4


def test_acpf_plan_recommends_tier_and_disables_impossible_choices(
    tmp_path, monkeypatch
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    provisioner = CapabilityProvisioner(
        runtime=SimpleNamespace(
            package_repository=SimpleNamespace(active=lambda _key: None),
            registry_packages=None,
            package_manager=None,
        ),
        repository=ProvisioningSessionRepository(database),
    )
    monkeypatch.setattr(
        "ai2apps.provisioning.orchestrator.device_profile",
        lambda: _apple_device(8),
    )

    result = provisioner.ensure(
        actor_id="local",
        installation_id="local",
        app_instance_id=APP_INSTANCE_ID,
        app_id="ai2apps.general-chat",
        capability="audio.speech_generation",
        action_id="configure-tts-8g",
        requirements={"operations": ["speech_generation"]},
        intent={},
    )

    options = {
        item["profileId"]: item for item in result["session"]["plan"]["profileOptions"]
    }
    low = options["apple-metal-qwen3-tts-06b-custom-voice"]
    high = options["apple-metal-qwen3-tts-17b-custom-voice"]
    assert low["selected"] is True
    assert low["recommended"] is True
    assert low["compatible"] is True
    assert high["compatible"] is False
    assert high["disabledReasons"] == ["至少需要 16 GiB 统一内存"]
    with pytest.raises(ValueError, match="至少需要 16 GiB"):
        provisioner.select_profile(result["sessionId"], high["profileId"])


def test_acpf_user_can_choose_compatible_non_recommended_tier(
    tmp_path, monkeypatch
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    repository = ProvisioningSessionRepository(database)
    provisioner = CapabilityProvisioner(
        runtime=SimpleNamespace(
            package_repository=SimpleNamespace(active=lambda _key: None),
            registry_packages=None,
            package_manager=None,
        ),
        repository=repository,
    )
    monkeypatch.setattr(
        "ai2apps.provisioning.orchestrator.device_profile",
        lambda: _apple_device(16),
    )
    initial = provisioner.ensure(
        actor_id="local",
        installation_id="local",
        app_instance_id=APP_INSTANCE_ID,
        app_id="ai2apps.general-chat",
        capability="audio.speech_generation",
        action_id="configure-tts-16g",
        requirements={"operations": ["speech_generation"]},
        intent={},
    )

    assert initial["session"]["profileId"] == (
        "apple-metal-qwen3-tts-17b-custom-voice"
    )
    selected = provisioner.select_profile(
        initial["sessionId"], "apple-metal-qwen3-tts-06b-custom-voice"
    )

    assert selected["status"] == "setup_required"
    assert selected["sessionId"] != initial["sessionId"]
    assert selected["session"]["profileId"] == (
        "apple-metal-qwen3-tts-06b-custom-voice"
    )
    assert selected["session"]["plan"]["requirements"]["profileId"] == (
        "apple-metal-qwen3-tts-06b-custom-voice"
    )
    assert repository.get(initial["sessionId"])["status"] == "cancelled"


def test_provisioning_session_is_durable_and_idempotent(tmp_path) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    repository = ProvisioningSessionRepository(database)
    values = dict(
        actor_id="user-1",
        installation_id="installation-1",
        app_instance_id=APP_INSTANCE_ID,
        app_id="ai2apps.video-studio",
        capability="video.generation",
        action_id="generate",
        status="awaiting_confirmation",
        profile_id="apple-metal-h3-q8",
        request_fingerprint="1" * 64,
        plan={"profileId": "apple-metal-h3-q8"},
        intent={"returnTo": "/apps/ai2apps.video-studio"},
    )

    created = repository.create(**values)
    duplicate = repository.create(**values)

    assert duplicate["id"] == created["id"]
    assert ProvisioningSessionRepository(database).get(created["id"]) == created
    ready = repository.update(created["id"], status="ready")
    assert ready["completedAt"] is not None
    assert repository.list_returnable(actor_id="user-1")[0]["id"] == created["id"]
    acknowledged = repository.acknowledge_return(created["id"])
    assert acknowledged["intent"]["returnAcknowledgedAt"]
    assert repository.list_returnable(actor_id="user-1") == ()


def test_provisioning_session_does_not_merge_different_request_fingerprints(
    tmp_path,
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    repository = ProvisioningSessionRepository(database)
    values = dict(
        actor_id="user-1",
        installation_id="installation-1",
        app_instance_id=APP_INSTANCE_ID,
        app_id="ai2apps.video-studio",
        capability="video.generation",
        action_id="configure-generation",
        status="awaiting_confirmation",
        profile_id="apple-metal-h3-q8",
        plan={},
        intent={},
    )

    q8 = repository.create(**values, request_fingerprint="8" * 64)
    q4 = repository.create(**values, request_fingerprint="4" * 64)

    assert q8["id"] != q4["id"]


def test_capability_ensure_api_carries_app_intent_and_principal() -> None:
    captured = {}

    class Provisioner:
        def ensure(self, **values):
            captured.update(values)
            return {"status": "ready", "provider": {"modelId": "h3/q8"}}

    app = FastAPI()
    app.include_router(
        create_provisioning_router(
            lambda: _api_runtime(Provisioner()),
            RequestPrincipal.legacy_local,
        )
    )
    response = TestClient(app).post(
        "/capabilities/ensure",
        json={
            "appId": "ai2apps.video-studio",
            "appInstanceId": APP_INSTANCE_ID,
            "capability": "video.generation",
            "actionId": "generate",
            "requirements": {"operations": ["text_to_video"]},
            "intent": {
                "returnTo": "/apps/ai2apps.video-studio",
                "resumeToken": "draft_video_1",
                "draft": {"prompt": "must not cross the ACPF boundary"},
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["provider"]["modelId"] == "h3/q8"
    assert captured["actor_id"] == "local"
    assert captured["installation_id"] == "local"
    assert captured["app_instance_id"] == APP_INSTANCE_ID
    assert captured["app_id"] == "ai2apps.video-studio"
    assert captured["intent"] == {
        "returnTo": "/apps/ai2apps.video-studio",
        "resumeToken": "draft_video_1",
        "completionPolicy": "configure_only",
    }


def test_capability_api_rejects_untrusted_app_identity() -> None:
    class Provisioner:
        def ensure(self, **_values):
            raise AssertionError("untrusted request reached provisioner")

    app = FastAPI()
    app.include_router(
        create_provisioning_router(
            lambda: _api_runtime(Provisioner()),
            RequestPrincipal.legacy_local,
        )
    )

    response = TestClient(app).post(
        "/capabilities/ensure",
        json={
            "appId": "ai2apps.general-chat",
            "appInstanceId": APP_INSTANCE_ID,
            "capability": "text.chat",
            "actionId": "send-message",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "app_identity_mismatch"


def test_profile_selection_api_is_scoped_to_owned_unconfirmed_session() -> None:
    captured = {}
    session = {
        "id": "prv_select_tier",
        "actorId": "local",
        "installationId": "local",
        "appInstanceId": APP_INSTANCE_ID,
    }

    class Provisioner:
        repository = SimpleNamespace(get=lambda _session_id: session)

        def select_profile(self, session_id, profile_id):
            captured.update(session_id=session_id, profile_id=profile_id)
            return {
                "status": "setup_required",
                "sessionId": session_id,
                "session": {**session, "profileId": profile_id},
            }

    app = FastAPI()
    app.include_router(
        create_provisioning_router(
            lambda: _api_runtime(Provisioner(), "ai2apps.general-chat"),
            RequestPrincipal.legacy_local,
        )
    )
    response = TestClient(app).post(
        "/provisioning/sessions/prv_select_tier/select-profile",
        headers=_app_headers(),
        json={"profileId": "apple-metal-qwen3-tts-06b-custom-voice"},
    )

    assert response.status_code == 200
    assert captured == {
        "session_id": "prv_select_tier",
        "profile_id": "apple-metal-qwen3-tts-06b-custom-voice",
    }


def test_resume_action_requires_stable_idempotency_key() -> None:
    class Provisioner:
        def ensure(self, **_values):
            return {"status": "ready", "provider": {"modelId": "h3/q8"}}

    app = FastAPI()
    app.include_router(
        create_provisioning_router(
            lambda: _api_runtime(Provisioner()),
            RequestPrincipal.legacy_local,
        )
    )
    request = {
        "appId": "ai2apps.video-studio",
        "appInstanceId": APP_INSTANCE_ID,
        "capability": "video.generation",
        "actionId": "generate",
        "intent": {
            "returnTo": "/apps/ai2apps.video-studio",
            "resumeToken": "draft_video_2",
            "completionPolicy": "resume_action",
        },
    }

    missing = TestClient(app).post("/capabilities/ensure", json=request)
    request["intent"]["idempotencyKey"] = "video-generation-request-1"
    accepted = TestClient(app).post("/capabilities/ensure", json=request)

    assert missing.status_code == 422
    assert accepted.status_code == 200


def test_resume_action_acknowledgement_requires_matching_key_and_is_idempotent(
    tmp_path,
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    repository = ProvisioningSessionRepository(database)
    session = repository.create(
        actor_id="local",
        installation_id="local",
        app_instance_id=APP_INSTANCE_ID,
        app_id="ai2apps.video-studio",
        capability="video.generation",
        action_id="generate",
        status="ready",
        profile_id="apple-metal-h3-q8",
        request_fingerprint="a" * 64,
        plan={"provider": {"modelId": "h3/q8"}},
        intent={
            "returnTo": "/apps/ai2apps.video-studio",
            "resumeToken": "draft_video_3",
            "completionPolicy": "resume_action",
            "idempotencyKey": "video-generation-request-2",
        },
    )

    class Provisioner:
        def __init__(self):
            self.repository = repository

        async def resume_if_possible(self, session_id):
            return repository.get(session_id)

    app = FastAPI()
    app.include_router(
        create_provisioning_router(
            lambda: _api_runtime(Provisioner()),
            RequestPrincipal.legacy_local,
        )
    )
    client = TestClient(app)
    path = f"/provisioning/sessions/{session['id']}/acknowledge-return"

    rejected = client.post(path, headers=_app_headers(), json={})
    accepted = client.post(
        path,
        headers=_app_headers(),
        json={"idempotencyKey": "video-generation-request-2"},
    )
    repeated = client.post(
        path,
        headers=_app_headers(),
        json={"idempotencyKey": "video-generation-request-2"},
    )

    assert rejected.status_code == 409
    assert accepted.status_code == 200
    assert repeated.status_code == 200
    assert (
        repeated.json()["intent"]["returnAcknowledgedAt"]
        == accepted.json()["intent"]["returnAcknowledgedAt"]
    )


def test_shared_client_stores_only_opaque_resume_metadata_and_defers_ack() -> None:
    script = (
        Path(__file__).parents[1]
        / "ai2apps/web/static/js/capability_provisioning.js"
    ).read_text()
    stylesheet = (
        Path(__file__).parents[1]
        / "ai2apps/web/static/css/capability_provisioning.css"
    ).read_text()

    assert "配置本地视频生成" not in script
    assert "request: body" not in script
    assert "requirements: session.plan" not in script
    assert "resumeToken: value.resumeToken || null" in script
    assert "outcome: 'configured'" in script
    assert "outcome: 'already_ready'" in script
    assert "async function resume(appId, { capability } = {})" in script
    assert "item.capability === capability" in script
    assert "profileOptions" in script
    assert "function chooseProfile(plan)" in script
    assert "AI2APPS CAPABILITY CHOICE" in script
    assert "data-choice-profile-id" in script
    assert "acpf-download-detail" in script
    assert "bytesCompleted ?? progressDetail.bytes_completed" in script
    assert "当前项目" in script
    assert "本次下载总计" in script
    assert "const probed = await probe(body)" in script
    assert "const profileSelection = await chooseProfile(probed.plan)" in script
    assert script.index("const profileSelection = await chooseProfile(probed.plan)") < script.index(
        "request('/capabilities/ensure'"
    )
    assert "plan?.selectionMode === 'multiple'" in script
    assert "{ profileIds: profileSelection }" in script
    assert 'class="acpf-choice-header"' in script
    assert 'class="acpf-actions acpf-choice-actions"' in script
    assert ".acpf-choice-sheet>.acpf-tiers" in stylesheet
    assert "overflow-y:auto" in stylesheet
    assert ".acpf-choice-actions{flex:0 0 auto" in stylesheet
    assert "/select-profile" not in script
    assert "acpf-selected-tier" in script
    assert (
        "window.AI2AppsCapabilities = { ensure, resume, probe, acknowledge, appInstanceId }"
        in script
    )


def test_chat_recommends_local_model_without_blocking_cloud_models() -> None:
    chat = (Path(__file__).parents[1] / "ai2apps/web/templates/chat.html").read_text()

    assert 'data-app-id="ai2apps.general-chat"' in chat
    assert "hasCloudConversationModel()" in chat
    assert "!['cloud', 'fusion'].includes(model.source_type)" in chat
    assert "localConversationModels().length === 0" in chat
    assert "capability: 'text.chat.local'" in chat
    assert "installRecommendedLocalModel()" in chat
    assert ":data-lucide=\"localModelRecommendation.status === 'installing'" not in chat
    assert "border-t-transparent animate-spin" in chat
    assert "localModelRecommendation.status !== 'installing'" in chat
    assert "await this.probeLocalModelRecommendation()" in chat
    assert "await this.resumeLocalModelRecommendation()" in chat
    assert '@click="requestSpeechRecognition()"' in chat
    assert '@click="requestSpeechSynthesis(msg)"' in chat
    assert "requestAudioCapabilitySetup(kind)" in chat
    assert "capability: 'audio.speech_recognition'" in chat
    assert "capability: 'audio.speech_generation'" in chat
    assert "awaiting_confirmation Session" in chat

    acpf = (
        Path(__file__).parents[1]
        / "ai2apps/web/static/js/capability_provisioning.js"
    ).read_text()
    assert "confirmLicenseChallenges" in acpf
    assert "checkpoint_license_consent_required" in acpf
    assert "licenseConsents" in acpf


def test_provisioning_confirm_api_starts_runner_on_asgi_event_loop(tmp_path) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    repository = ProvisioningSessionRepository(database)
    session = repository.create(
        actor_id="local",
        installation_id="local",
        app_instance_id=APP_INSTANCE_ID,
        app_id="ai2apps.video-studio",
        capability="video.generation",
        action_id="generate",
        status="awaiting_confirmation",
        profile_id="apple-metal-h3-q8",
        request_fingerprint="2" * 64,
        plan={"profileId": "apple-metal-h3-q8"},
        intent={},
    )
    provisioner = CapabilityProvisioner(
        runtime=SimpleNamespace(),
        repository=repository,
    )
    runner_started = asyncio.Event()

    async def run(_session_id: str) -> None:
        runner_started.set()

    provisioner._run = run
    app = FastAPI()
    app.include_router(
        create_provisioning_router(
            lambda: _api_runtime(provisioner),
            RequestPrincipal.legacy_local,
        )
    )

    response = TestClient(app).post(
        f"/provisioning/sessions/{session['id']}/confirm", headers=_app_headers()
    )

    assert response.status_code == 200
    assert response.json()["id"] == session["id"]
    assert runner_started.is_set()


def test_provisioning_confirm_persists_manifest_bound_license_consent(tmp_path) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    repository = ProvisioningSessionRepository(database)
    session = repository.create(
        actor_id="local",
        installation_id="local",
        app_instance_id=APP_INSTANCE_ID,
        app_id="ai2apps.imagine-studio",
        capability="image.generation",
        action_id="generate",
        status="awaiting_confirmation",
        profile_id="apple-metal-ideogram4",
        request_fingerprint="9" * 64,
        plan={"profileId": "apple-metal-ideogram4"},
        intent={},
    )
    provisioner = CapabilityProvisioner(
        runtime=SimpleNamespace(), repository=repository
    )

    async def run(_session_id: str) -> None:
        return None

    provisioner._run = run
    app = FastAPI()
    app.include_router(
        create_provisioning_router(
            lambda: _api_runtime(provisioner),
            RequestPrincipal.legacy_local,
        )
    )
    consent = {
        "distributionId": "dist_ideogram4_v1",
        "manifestDigest": "sha256:" + "1" * 64,
        "termsHash": "sha256:" + "2" * 64,
        "decision": "accepted_license_terms",
        "confirmed": True,
    }

    response = TestClient(app).post(
        f"/provisioning/sessions/{session['id']}/confirm",
        headers=_app_headers(),
        json={"licenseConsents": [consent]},
    )

    assert response.status_code == 200
    operation = repository.get(session["id"])["operations"][0]
    assert operation["kind"] == "checkpointLicenseConsent"
    assert operation["actorId"] == "local"
    assert operation["installationId"] == "local"
    assert operation["acceptedAt"]
    assert operation["consent"] == consent


@pytest.mark.asyncio
async def test_provisioner_startup_resumes_approved_restart_session(tmp_path) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    repository = ProvisioningSessionRepository(database)
    session = repository.create(
        actor_id="local",
        installation_id="local",
        app_instance_id=APP_INSTANCE_ID,
        app_id="ai2apps.video-studio",
        capability="video.generation",
        action_id="generate",
        status="awaiting_restart",
        profile_id="apple-metal-h3-q8",
        request_fingerprint="3" * 64,
        plan={"profileId": "apple-metal-h3-q8"},
        intent={"returnTo": "/apps/ai2apps.video-studio"},
    )
    repository.update(
        session["id"],
        progress={
            "phase": "awaiting_restart",
            "percent": 20,
            "runtimeEpoch": "prior-local-process",
        },
    )
    provisioner = CapabilityProvisioner(
        runtime=SimpleNamespace(),
        repository=repository,
    )
    resumed = asyncio.Event()

    async def run(_session_id: str) -> None:
        resumed.set()

    provisioner._run = run

    await provisioner.startup()
    await asyncio.sleep(0)

    assert resumed.is_set()
    await provisioner.shutdown()


@pytest.mark.asyncio
async def test_confirmed_acpf_plan_scopes_audit_approval_to_selected_release(
    tmp_path,
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    repository = ProvisioningSessionRepository(database)
    installs = []

    class RegistryPackages:
        async def trusted_snapshot(self):
            return {
                "releases": [
                    {
                        "packageId": "ai2apps/runtime-omlx",
                        "version": "1.4.0",
                        "status": "published",
                    }
                ]
            }

        async def install(
            self,
            namespace,
            name,
            version,
            *,
            approve_review,
            progress,
        ):
            installs.append(
                {
                    "packageId": f"{namespace}/{name}",
                    "version": version,
                    "approveReview": approve_review,
                }
            )
            progress(
                {
                    "stage": "downloading_package",
                    "fileName": "runtime-omlx-1.4.0.ai2service",
                    "bytesCompleted": 4,
                    "bytesTotal": 8,
                }
            )

    runtime = SimpleNamespace(
        package_repository=SimpleNamespace(active=lambda _key: None),
        registry_packages=RegistryPackages(),
    )
    provisioner = CapabilityProvisioner(runtime=runtime, repository=repository)
    session = repository.create(
        actor_id="local",
        installation_id="local",
        app_instance_id=APP_INSTANCE_ID,
        app_id="ai2apps.video-studio",
        capability="video.generation",
        action_id="generate",
        status="installing_runtime",
        profile_id="apple-metal-h3-q8",
        request_fingerprint="4" * 64,
        plan={},
        intent={},
    )

    ready = await provisioner._install_package(
        session["id"],
        {
            "package_id": "ai2apps/runtime-omlx",
            "service_key": "ai2apps.runtime.omlx",
            "version": ">=1.4.0,<2.0.0",
        },
        "installing_runtime",
    )

    assert ready is False
    assert installs == [
        {
            "packageId": "ai2apps/runtime-omlx",
            "version": "1.4.0",
            "approveReview": True,
        }
    ]
    assert repository.get(session["id"])["progress"]["detail"] == {
        "stage": "downloading_package",
        "fileName": "runtime-omlx-1.4.0.ai2service",
        "bytesCompleted": 4,
        "bytesTotal": 8,
    }
    assert repository.get(session["id"])["progress"]["percent"] == 7.5


def test_provisioner_does_not_substitute_ready_bf16_for_recommended_q8(
    tmp_path, monkeypatch
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    runtime = SimpleNamespace(
        package_repository=SimpleNamespace(active=lambda _key: None),
        registry_packages=None,
        package_manager=None,
    )
    provisioner = CapabilityProvisioner(
        runtime=runtime,
        repository=ProvisioningSessionRepository(database),
    )
    monkeypatch.setattr(
        "ai2apps.provisioning.orchestrator.device_profile",
        lambda: _apple_device(128),
    )

    def model(model_id):
        if not model_id.endswith("/fl2va-bf16"):
            return None
        return SimpleNamespace(
            id=model_id,
            service_key="ai2apps.model.minimax-h3",
            checkpoint_ready=True,
            capabilities=("text_to_video",),
            video_capabilities={},
        )

    monkeypatch.setattr(
        "ai2apps.provisioning.orchestrator.resolve_package_model",
        lambda _runtime, model_id: model(model_id),
    )

    result = provisioner.ensure(
        actor_id="local",
        installation_id="local",
        app_instance_id=APP_INSTANCE_ID,
        app_id="ai2apps.video-studio",
        capability="video.generation",
        action_id="generate",
        requirements={"operations": ["text_to_video"]},
        intent={},
    )

    assert result["status"] == "setup_required"
    assert result["session"]["profileId"] == "apple-metal-h3-q8"
    assert result["session"]["plan"]["stack"]["checkpoint"]["model_id"].endswith(
        "/fl2va-8bit"
    )


def test_provisioner_rejects_an_explicit_bf16_selection(
    tmp_path, monkeypatch
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    provisioner = CapabilityProvisioner(
        runtime=SimpleNamespace(
            package_repository=SimpleNamespace(active=lambda _key: None),
            registry_packages=None,
            package_manager=None,
        ),
        repository=ProvisioningSessionRepository(database),
    )
    monkeypatch.setattr(
        "ai2apps.provisioning.orchestrator.device_profile",
        lambda: _apple_device(128),
    )

    def model(model_id):
        if not model_id.endswith("/fl2va-bf16"):
            return None
        return SimpleNamespace(
            id=model_id,
            service_key="ai2apps.model.minimax-h3",
            checkpoint_ready=True,
            capabilities=("text_to_video",),
            video_capabilities={},
        )

    monkeypatch.setattr(
        "ai2apps.provisioning.orchestrator.resolve_package_model",
        lambda _runtime, model_id: model(model_id),
    )
    bf16 = "ai2apps.model.minimax-h3/fl2va-bf16"

    result = provisioner.ensure(
        actor_id="local",
        installation_id="local",
        app_instance_id=APP_INSTANCE_ID,
        app_id="ai2apps.video-studio",
        capability="video.generation",
        action_id="generate",
        requirements={"operations": ["text_to_video"], "modelId": bf16},
        intent={},
    )

    assert result["status"] == "unsupported"
    assert "当前设备" in result["reasons"][0]
