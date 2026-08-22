import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai2apps.development import (
    can_access_developer_surfaces,
    is_source_development_runtime,
)
from ai2apps.model_manager import (
    BUILTIN_CLOUD_PROVIDERS,
    DEFAULT_MODEL_PURPOSES,
    ModelManagerStore,
)
from ai2apps.secrets import MemorySecretBackend

WEB_ROOT = Path(__file__).parents[1] / "ai2apps" / "web"


def test_developer_surfaces_require_a_git_source_checkout(tmp_path):
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    (project / "ai2apps").mkdir()
    (project / "omlx").mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='ai2apps'\n")

    assert is_source_development_runtime(project) is True
    assert can_access_developer_surfaces(
        SimpleNamespace(role=SimpleNamespace(value="core")), project
    ) is True
    assert can_access_developer_surfaces(
        SimpleNamespace(role=SimpleNamespace(value="owner")), project
    ) is False
    assert can_access_developer_surfaces(
        SimpleNamespace(role=SimpleNamespace(value="member")), project
    ) is False

    (project / ".git").rmdir()
    assert is_source_development_runtime(project) is False


def test_default_model_routes_are_complete_atomic_and_resolvable(tmp_path):
    store = ModelManagerStore(tmp_path)

    assert store.default_models() == {purpose: "" for purpose in DEFAULT_MODEL_PURPOSES}
    routes = store.put_default_models(
        {
            "work_simple": "local-small",
            "work_standard": "cloud/openai/gpt-standard",
            "image_recognition": "vision-model",
        },
        available_model_ids={
            "local-small",
            "cloud/openai/gpt-standard",
            "vision-model",
        },
    )

    assert routes["work_complex"] == ""
    assert store.resolve_default_model("work_standard") == "cloud/openai/gpt-standard"
    assert store.resolve_default_model("video_generation", "fallback") == "fallback"
    assert store.defaults_path.stat().st_mode & 0o777 == 0o600
    saved = json.loads(store.defaults_path.read_text())
    assert saved["schema"] == "ai2apps.model-defaults/v1"


def test_default_model_routes_reject_unknown_purpose_and_unavailable_model(tmp_path):
    store = ModelManagerStore(tmp_path)

    with pytest.raises(ValueError, match="Unknown default model purpose"):
        store.put_default_models({"unknown": "model"})
    with pytest.raises(ValueError, match="not available"):
        store.put_default_models(
            {"work_simple": "missing"},
            available_model_ids={"available"},
        )


def test_models_app_opens_with_default_model_routing_first():
    template = (WEB_ROOT / "templates" / "dashboard" / "_models.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "dashboard.js").read_text()

    assert template.index("setModelsTab('defaults')") < template.index(
        "setModelsTab('manager')"
    )
    assert "models.tab.default_usage" in template
    assert "models.tab.manager" in template
    assert "models.defaults.section_label" in template
    assert "models.defaults.work_simple.title" in template
    assert "models.defaults.speech_recognition.title" in template
    assert "defaultModels[route.id]" in template
    assert "'/admin/api/model-manager/defaults'" in script
    assert "modelsTab: 'defaults'" in script
    assert "speech_recognition" in script
    assert "speech_generation" in script
    assert "audio_processing" in script
    assert "image_generation" in script
    assert "Installed Model Providers" in template
    assert "packages: data.packages || []" in script


def test_default_model_routing_i18n_keys_exist_in_every_locale():
    i18n_dir = WEB_ROOT / "i18n"
    english = json.loads((i18n_dir / "en.json").read_text())
    required = {key for key in english if key.startswith("models.defaults.")}

    assert required
    for locale_path in i18n_dir.glob("*.json"):
        translations = json.loads(locale_path.read_text())
        missing = required - translations.keys()
        assert not missing, (
            f"{locale_path.name} is missing default-model keys: {sorted(missing)}"
        )


def test_cloud_provider_i18n_and_key_protection_notice_exist_in_every_locale():
    i18n_dir = WEB_ROOT / "i18n"
    english = json.loads((i18n_dir / "en.json").read_text())
    required = {
        key
        for key in english
        if key.startswith("models.cloud.")
        or key in {
            "models.manager.loading",
            "models.manager.section.cloud",
            "models.manager.section.packages",
        }
    }

    assert "models.cloud.key_security" in required
    for locale_path in i18n_dir.glob("*.json"):
        translations = json.loads(locale_path.read_text())
        missing = required - translations.keys()
        assert not missing, (
            f"{locale_path.name} is missing cloud-provider keys: {sorted(missing)}"
        )


def test_cloud_provider_disabled_bindings_require_explicit_true():
    template = (WEB_ROOT / "templates" / "dashboard" / "_models.html").read_text()

    assert ':disabled="provider.managed === true"' in template
    assert ':disabled="cloudRefreshing[provider.id] === true"' in template
    assert ':disabled="provider.managed"' not in template
    assert ':disabled="cloudRefreshing[provider.id]"' not in template


def test_model_manager_prioritizes_cloud_and_packages_for_members():
    template = (WEB_ROOT / "templates" / "dashboard" / "_models.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "dashboard.js").read_text()

    assert "managerSection: 'cloud'" in script
    cloud_section = "{ id: 'cloud', label: window.t('models.manager.section.cloud') }"
    package_section = (
        "{ id: 'packages', label: window.t('models.manager.section.packages') }"
    )
    assert script.index(cloud_section) < script.index(package_section)
    assert "window.AI2APPS_SYSTEM_APP?.developerSurfacesVisible" in script
    assert "'/v1/platform/auth/me'" not in script
    assert "modelManagerSections()" in template
    assert "modelManagerSectionCount(section.id)" in template
    assert 'x-for="model in modelManager.cached_moe"' in template
    assert "Model Package" in template
    assert "openModelPackageConfig(model)" in template
    assert "setModelsTab('downloader')" not in template
    assert "modelsTab === 'downloader'" not in template
    assert "{% if false %}" in template
    assert "['defaults', 'manager']" in script
    assert "setModelsTab('quantizer')" not in template
    assert "setModelsTab('uploader')" not in template
    assert "modelsTab === 'quantizer' || modelsTab === 'uploader'" in script
    assert "modelsTab === 'downloader'" in script
    assert "this.managerSection = 'packages'" in script
    assert "ai2apps.pendingModelPackage" in script
    assert "await this.openModelPackageConfig(recipe)" in script
    system_app = (WEB_ROOT / "templates" / "system_apps" / "models.html").read_text()
    assert 'dashboard/_modal_model_package.html' in system_app


def test_cloud_capabilities_route_work_and_dedicated_models_separately():
    from omlx.admin.routes import (
        _cloud_model_capabilities,
        _supports_default_model_purpose,
    )

    image = _cloud_model_capabilities({"id": "gpt-image-2"})
    work = _cloud_model_capabilities({"id": "gpt-5.6-sol"})
    speech = _cloud_model_capabilities({"id": "whisper-large-v3"})
    image_from_catalog = _cloud_model_capabilities(
        {
            "id": "provider/new-media-model",
            "capabilities": {
                "textInput": True,
                "imageInput": True,
                "imageOutput": True,
                "imageGeneration": True,
                "imageEdit": True,
                "streaming": False,
            },
        }
    )

    assert image == {"image_generation"}
    assert {"image_generation", "image_edit", "image_output"}.issubset(
        image_from_catalog
    )
    assert {"work", "image_recognition"}.issubset(work)
    assert speech == {"speech_recognition"}
    assert _supports_default_model_purpose(
        {
            "model_type": "image_generation",
            "config_model_type": "cloud",
            "capabilities": sorted(image),
        },
        "image_generation",
    )
    assert not _supports_default_model_purpose(
        {
            "model_type": "image_generation",
            "config_model_type": "cloud",
            "capabilities": sorted(image),
        },
        "work_standard",
    )
    assert _supports_default_model_purpose(
        {"model_type": "audio_tts", "capabilities": ["speech_generation"]},
        "speech_generation",
    )
    assert _supports_default_model_purpose(
        {"model_type": "audio_processing", "capabilities": ["audio_processing"]},
        "audio_processing",
    )


def test_fusion_editor_selects_from_managed_models():
    template = (WEB_ROOT / "templates" / "dashboard" / "_models.html").read_text()
    script = (WEB_ROOT / "static" / "js" / "dashboard.js").read_text()

    assert '<select x-model="fusionEditor.generator"' in template
    assert '<select x-model="fusionEditor.reviewer"' in template
    assert '<select x-model="fusionEditor.reviewerProvider"' in template
    assert 'x-model="fusionEditor.resolverEnabled"' in template
    assert '<select x-model="fusionEditor.resolverProvider"' in template
    assert '<select x-model="fusionEditor.resolver"' in template
    assert "$el.value = fusionEditor.resolver" in template
    assert (
        'FUSION MODEL ID <span class="font-normal text-neutral-400">automatic'
        in template
    )
    assert "fusionLocalModelOptions" in script
    assert "fusionCloudProviderOptions" in script
    assert "fusionResolverModelOptions" in script
    assert "changeFusionResolverEnabled" in script
    assert "credential_ref: `ai2apps-cloud:${provider.id}`" in script
    assert "this.fusionEditor.resolver = selectedResolver" in script
    assert 'x-model.number="fusionEditor.reviewerMaxTokens"' in template
    assert "reviewerMaxTokens: model.reviewer?.max_tokens ?? 8192" in script
    assert "max_tokens: Math.max(256, Number(f.reviewerMaxTokens) || 8192)" in script
    assert "syncFusionModelId" in script


def test_models_modals_are_not_trapped_by_a_transformed_ancestor():
    template = (WEB_ROOT / "templates" / "dashboard" / "_models.html").read_text()

    assert "<div data-models-root>" in template
    assert '<div data-models-root class="animate-fade-in-up">' not in template


def test_fusion_editor_is_viewport_bounded_and_scrollable():
    template = (WEB_ROOT / "templates" / "dashboard" / "_models.html").read_text()

    assert "max-height: calc(100dvh - 2rem)" in template
    assert "overscroll-behavior: contain" in template
    assert "max-w-lg flex flex-col overflow-hidden" in template
    assert "flex-1 min-h-0 overflow-y-auto" in template
    assert "border-b border-neutral-200 shrink-0" in template
    assert "border-t border-neutral-200 bg-white shrink-0" in template


def test_builtin_cloud_providers_are_always_visible(tmp_path):
    store = ModelManagerStore(tmp_path)

    providers = store.list_cloud()

    assert [item["id"] for item in providers] == [
        item["id"] for item in BUILTIN_CLOUD_PROVIDERS
    ]
    assert all(item["builtin"] for item in providers)
    assert all(not item["configured"] for item in providers)


def test_cloud_secret_is_persisted_but_never_returned(tmp_path):
    store = ModelManagerStore(tmp_path)

    public = store.put_cloud(
        "openai",
        {
            "base_url": "https://api.openai.com/v1",
            "protocol": "openai",
            "models": ["gpt-test"],
            "api_key": "sk-secret",
        },
    )

    assert public["configured"] is True
    assert "api_key" not in public
    assert "sk-secret" not in json.dumps(store.list_cloud())
    assert "sk-secret" not in store.cloud_path.read_text()
    assert "credential_ref" in store.cloud_path.read_text()
    assert b"sk-secret" not in store.secret_backend.vault_path.read_bytes()
    assert store.cloud_path.stat().st_mode & 0o777 == 0o600


def test_legacy_plaintext_cloud_key_migrates_to_secret_backend(tmp_path):
    backend = MemorySecretBackend()
    path = tmp_path / "ai2apps" / "cloud-providers.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "version": 1,
        "providers": {
            "openai": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "legacy-secret",
                "models": [],
            }
        },
    }))

    store = ModelManagerStore(tmp_path, secret_backend=backend)

    assert next(item for item in store.list_cloud() if item["id"] == "openai")[
        "configured"
    ] is True
    saved = path.read_text()
    assert "legacy-secret" not in saved
    assert '"version": 2' in saved
    assert store.resolve_credential("ai2apps-cloud:openai") == "legacy-secret"


def test_reset_builtin_and_delete_custom_provider(tmp_path):
    store = ModelManagerStore(tmp_path)
    store.put_cloud(
        "openai",
        {"base_url": "https://proxy.example/v1", "api_key": "secret"},
    )
    store.put_cloud(
        "office",
        {
            "name": "Office",
            "base_url": "https://models.example/v1",
            "api_key": "secret",
        },
    )

    assert store.delete_cloud("openai") is True
    assert store.delete_cloud("office") is True
    providers = store.list_cloud()
    openai = next(item for item in providers if item["id"] == "openai")
    assert openai["configured"] is False
    assert all(item["id"] != "office" for item in providers)


def test_fusion_profile_crud_and_validation(tmp_path):
    store = ModelManagerStore(tmp_path)
    profile = store.put_fusion(
        "local-review",
        {
            "fusion": {
                "generator": {"backend": "local", "model": "draft"},
                "reviewer": {"backend": "local", "model": "reviewer"},
                "resolver": {"enabled": False},
            }
        },
    )

    assert profile["valid"] is True
    assert profile["generator"]["model"] == "draft"
    assert store.delete_fusion("local-review") is True
    with pytest.raises(ValueError, match="Fusion model id"):
        store.put_fusion("../escape", {})


def test_fusion_profile_resolves_for_runtime_by_exact_id(tmp_path):
    store = ModelManagerStore(tmp_path)
    store.put_fusion(
        "local-review",
        {
            "fusion": {
                "generator": {"backend": "local", "model": "draft"},
                "reviewer": {"backend": "local", "model": "reviewer"},
            }
        },
    )

    resolved = store.resolve_fusion_profile("local-review")

    assert resolved is not None
    assert resolved.model_id == "local-review"
    assert resolved.generator.model == "draft"
    assert store.resolve_fusion_profile("missing") is None
    assert store.resolve_fusion_profile("../escape") is None


def test_fusion_credential_reference_resolves_privately(tmp_path):
    store = ModelManagerStore(tmp_path)
    store.put_cloud(
        "openai",
        {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-fusion-secret",
        },
    )

    assert store.resolve_credential("ai2apps-cloud:openai") == "sk-fusion-secret"
    assert "sk-fusion-secret" not in json.dumps(store.list_cloud())
    with pytest.raises(ValueError, match="Unsupported"):
        store.resolve_credential("environment:OPENAI_API_KEY")


def test_chat_model_picker_displays_fusion_aliases():
    template = (WEB_ROOT / "templates" / "chat.html").read_text()

    assert "['cloud', 'fusion'].includes(adminModel?.source_type)" in template


def test_fusion_profile_persists_optional_external_resolver(tmp_path):
    store = ModelManagerStore(tmp_path)

    profile = store.put_fusion(
        "three-stage",
        {
            "fusion": {
                "generator": {"backend": "local", "model": "draft"},
                "reviewer": {"backend": "local", "model": "reviewer"},
                "resolver": {
                    "enabled": True,
                    "backend": "openai-compatible",
                    "model": "external-model",
                    "base_url": "https://provider.example/v1",
                    "credential_ref": "ai2apps-cloud:provider",
                    "triggers": [
                        "reviewer_escalate",
                        "reviewer_uncertain",
                        "patch_failed",
                    ],
                    "max_tokens": 384,
                    "timeout_seconds": 30,
                    "failure_policy": "local_rebuild",
                },
            }
        },
    )

    assert profile["resolver"]["enabled"] is True
    assert profile["resolver"]["model"] == "external-model"
    assert profile["resolver"]["credential_ref"] == "ai2apps-cloud:provider"


def test_fusion_profile_exposes_review_and_cache_defaults(tmp_path):
    store = ModelManagerStore(tmp_path)

    profile = store.put_fusion(
        "review-policy",
        {
            "fusion": {
                "generator": {"backend": "local", "model": "draft"},
                "reviewer": {"backend": "local", "model": "reviewer"},
                "gate": {
                    "gate_policy": "always",
                    "mid_generation_review_enabled": True,
                    "thinking_audit_enabled": True,
                },
                "cache_moe": {
                    "generator": {"l1_mode": "off", "engine_boost": "turbo"},
                    "reviewer": {"l1_mode": "auto", "engine_boost": "blast"},
                },
            }
        },
    )

    assert profile["gate"]["gate_policy"] == "always"
    assert profile["gate"]["thinking_audit_enabled"] is True
    assert profile["cache_moe"]["generator"] == {
        "l1_mode": "off",
        "prefill_boost": "turbo",
        "decode_boost": "turbo",
    }
    assert profile["cache_moe"]["reviewer"]["prefill_boost"] == "blast"
    assert profile["cache_moe"]["reviewer"]["decode_boost"] == "blast"


def test_fusion_review_controls_are_available_in_manager_and_chat():
    manager = (WEB_ROOT / "templates" / "dashboard" / "_models.html").read_text()
    dashboard = (WEB_ROOT / "static" / "js" / "dashboard.js").read_text()
    chat = (WEB_ROOT / "templates" / "chat.html").read_text()

    assert 'x-model="fusionEditor.gatePolicy"' in manager
    assert 'x-model="fusionEditor.thinkingAuditEnabled"' in manager
    assert 'x-show="fusionGeneratorIsCachedMoe"' in manager
    assert 'x-show="fusionReviewerIsCachedMoe"' in manager
    assert "mid_generation_review_enabled" in dashboard
    assert 'x-show="isFusionMode"' in chat
    assert "ai2apps_fusion_gate_policy" in chat
    assert "fusion_generator_engine_boost" in chat
    assert "fusion_reviewer_engine_boost" in chat
    assert 'x-model="fusionEditor.generatorCacheMoePrefillBoost"' in manager
    assert 'x-model="fusionEditor.generatorCacheMoeDecodeBoost"' in manager
    assert 'x-model="fusionEditor.reviewerCacheMoePrefillBoost"' in manager
    assert 'x-model="fusionEditor.reviewerCacheMoeDecodeBoost"' in manager


def test_fusion_cached_moe_capability_is_reported_by_role():
    routes = (Path(__file__).parents[1] / "omlx" / "admin" / "routes.py").read_text()
    chat = (WEB_ROOT / "templates" / "chat.html").read_text()

    assert 'cached_role_ids.append("generator")' in routes
    assert 'cached_role_ids.append("reviewer")' in routes
    assert "adminModel?.fusion_cached_moe_roles || []" in chat
    assert "currentFusionCachedMoeRoles.includes('generator')" in chat
    assert "currentFusionCachedMoeRoles.includes('reviewer')" in chat


def test_chat_consumes_and_persists_fusion_stream_lifecycle():
    chat = (WEB_ROOT / "templates" / "chat.html").read_text()

    assert "if (delta?.ai2apps?.phase)" in chat
    assert "this.recordFusionEvent(stream, delta.ai2apps)" in chat
    assert "Fusion pipeline" in chat
    assert "Generator draft" in chat
    assert "Reviewer output" in chat
    assert "review_progress" in chat
    assert "reviewerPrefill" in chat
    assert "reviewerPrompt" in chat
    assert "Reviewer prompt" in chat
    assert "Preparing reviewer prefill" in chat
    assert "review_error" in chat
    assert "Checkpoint audit" in chat
    assert "Final review" in chat
    assert "_fusionTrace: stream.fusionTrace ? this.cloneData" in chat
    # Alpine evaluates descendants of x-show even when the parent is hidden.
    # x-if must keep Fusion-only expressions out of ordinary/Agent messages.
    assert '<template x-if="msg._fusionTrace">' in chat
    assert '<template x-if="currentStream()?.fusionTrace">' in chat
    assert 'x-show="msg._fusionTrace"' not in chat
    assert 'x-show="currentStream()?.fusionTrace"' not in chat


def test_fusion_alias_is_persisted_and_preferred_for_display(tmp_path):
    store = ModelManagerStore(tmp_path)
    profile = store.put_fusion(
        "local-review",
        {
            "fusion": {
                "alias": "Fast Review",
                "generator": {"backend": "local", "model": "draft"},
                "reviewer": {"backend": "local", "model": "reviewer"},
            }
        },
    )

    assert profile["alias"] == "Fast Review"
    assert profile["name"] == "Fast Review"
    stored = json.loads((store.fusion_dir / "local-review.json").read_text())
    assert stored["fusion"]["alias"] == "Fast Review"


def test_sync_openai_compatible_provider_models(tmp_path, monkeypatch):
    store = ModelManagerStore(tmp_path)
    store.put_cloud(
        "openai",
        {
            "base_url": "https://api.openai.com/v1",
            "protocol": "openai",
            "api_key": "sk-secret",
        },
    )
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {"id": "gpt-z", "owned_by": "openai", "created": 100},
                    {"id": "gpt-a", "owned_by": "openai", "created": 200},
                ]
            }

    def get(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr("ai2apps.model_manager.requests.get", get)
    provider = store.sync_cloud("openai")

    assert captured["url"] == "https://api.openai.com/v1/models"
    assert captured["headers"]["Authorization"] == "Bearer sk-secret"
    assert [model["id"] for model in provider["models"]] == ["gpt-a", "gpt-z"]
    assert provider["models_error"] == ""


def test_sync_anthropic_provider_uses_anthropic_headers(tmp_path, monkeypatch):
    store = ModelManagerStore(tmp_path)
    store.put_cloud(
        "anthropic",
        {
            "base_url": "https://api.anthropic.com",
            "protocol": "anthropic",
            "api_key": "ant-secret",
        },
    )
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"id": "claude-test", "display_name": "Claude Test"}]}

    def get(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr("ai2apps.model_manager.requests.get", get)
    provider = store.sync_cloud("anthropic")

    assert captured["url"] == "https://api.anthropic.com/v1/models"
    assert captured["headers"]["x-api-key"] == "ant-secret"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert provider["models"] == [
        {
            "id": "claude-test",
            "name": "Claude Test",
            "owned_by": "",
            "created": None,
            "capabilities": {},
            "enabled": False,
        }
    ]


def test_cloud_models_are_opt_in_and_resolve_only_when_enabled(tmp_path):
    store = ModelManagerStore(tmp_path)
    store.put_cloud(
        "openai",
        {
            "base_url": "https://api.openai.com/v1",
            "protocol": "openai",
            "models": ["gpt-new", "gpt-old"],
            "api_key": "sk-secret",
        },
    )

    assert store.enabled_cloud_models() == []
    assert store.resolve_cloud_model("cloud/openai/gpt-new") is None

    provider = store.set_cloud_model_enabled("openai", "gpt-new", True)
    assert provider["enabled_model_count"] == 1
    assert next(model for model in provider["models"] if model["id"] == "gpt-new")[
        "enabled"
    ]
    assert [model["gateway_id"] for model in store.enabled_cloud_models()] == [
        "cloud/openai/gpt-new"
    ]
    resolved = store.resolve_cloud_model("cloud/openai/gpt-new")
    assert resolved is not None
    assert resolved["api_key"] == "sk-secret"
    assert "sk-secret" not in json.dumps(store.list_cloud())
    assert store.model_source("cloud/openai/gpt-new") == "local_byok"
    assert store.model_shareable("cloud/openai/gpt-new") is True
    assert store.model_source("cloud/ai2apps/openai/gpt-new") == "ai2apps_cloud"
    assert store.model_shareable("cloud/ai2apps/openai/gpt-new") is False
    assert store.model_source("gateway/upg_test/model") == "upstream_gateway"
    assert store.model_source("local-model") == "local_runtime"

    store.set_cloud_model_enabled("openai", "gpt-new", False)
    assert store.enabled_cloud_models() == []


def test_cached_cloud_inventory_is_sorted_newest_first(tmp_path):
    store = ModelManagerStore(tmp_path)
    store.cloud_path.parent.mkdir(parents=True, exist_ok=True)
    store.cloud_path.write_text(
        json.dumps(
            {
                "version": 1,
                "providers": {
                    "openai": {
                        "name": "OpenAI",
                        "base_url": "https://api.openai.com/v1",
                        "protocol": "openai",
                        "enabled": True,
                        "api_key": "secret",
                        "models": [
                            {"id": "undated"},
                            {"id": "older", "created": 100},
                            {"id": "newer", "created": 200},
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    provider = next(item for item in store.list_cloud() if item["id"] == "openai")
    assert [model["id"] for model in provider["models"]] == [
        "newer",
        "older",
        "undated",
    ]
