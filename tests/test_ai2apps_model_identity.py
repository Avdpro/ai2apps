from ai2apps.model_identity import build_model_identity, with_model_identity
from omlx.api.openai_models import ModelInfo


def test_cloud_openai_identity_uses_three_part_display_name():
    identity = build_model_identity(
        source="ai2apps_cloud",
        provider_id="openai",
        model_id="openai/gpt-5.6-luna",
        display_name="OpenAI GPT-5.6 Luna",
    )

    assert identity == {
        "source": "cloud",
        "sourceLabel": "Cloud",
        "providerId": "openai",
        "providerName": "OpenAI",
        "modelId": "openai/gpt-5.6-luna",
        "modelName": "ChatGPT 5.6 Luna",
        "displayName": "(Cloud) OpenAI · ChatGPT 5.6 Luna",
    }


def test_byok_and_managed_cloud_are_visibly_distinct():
    managed = build_model_identity(
        source="ai2apps_cloud",
        provider_id="openrouter",
        model_id="openrouter/deepseek-v4-flash-0731",
        display_name="OpenRouter DeepSeek V4 Flash 0731",
    )
    byok = build_model_identity(
        source="local_byok",
        provider_id="openai",
        model_id="gpt-5.6-terra",
        display_name="gpt-5.6-terra",
    )

    assert managed["displayName"] == "(Cloud) OpenRouter · DeepSeek V4 Flash 0731"
    assert byok["displayName"] == "(BYOK) OpenAI · ChatGPT 5.6 Terra"


def test_deepseek_model_family_name_is_not_stripped():
    identity = build_model_identity(
        source="cloud",
        provider_id="deepseek",
        model_id="deepseek/deepseek-v4-pro",
        display_name="DeepSeek V4 Pro",
    )

    assert identity["displayName"] == "(Cloud) DeepSeek · DeepSeek V4 Pro"


def test_local_runtime_id_is_humanized_without_changing_route_id():
    route_id = "ai2apps.model.qwen38/qwen3.8-27b-nvfp4"
    entry = with_model_identity(
        {"id": route_id},
        source="local_runtime",
        provider_id="ai2apps.runtime.omlx",
        model_id=route_id,
        display_name=route_id,
    )

    assert entry["id"] == route_id
    assert entry["display_name"] == "(Local) AI2Apps-MLX · Qwen 3.8 27B NVFP4"


def test_fusion_and_cuda_runtime_provider_names_are_stable():
    fusion = build_model_identity(
        source="fusion",
        provider_id="ai2apps-fusion",
        model_id="my-fusion-fast",
        display_name="MyFusion-Fast",
    )
    cuda = build_model_identity(
        source="package",
        provider_id="ai2apps.runtime.cuda-torch",
        model_id="ai2apps.model.example/fp8",
        display_name="Example FP8",
    )

    assert fusion["displayName"] == "(Local) AI2Apps-Fusion · MyFusion-Fast"
    assert cuda["displayName"] == "(Local) AI2Apps-CUDA · Example FP8"


def test_knowledge_runtime_provider_name_is_stable():
    identity = build_model_identity(
        source="package",
        provider_id="ai2apps.runtime.knowledge-rag",
        model_id="ai2apps.model.multilingual-e5-small/default",
        display_name="Multilingual E5 Small",
    )

    assert identity["displayName"] == (
        "(Local) AI2Apps-Knowledge · Multilingual E5 Small"
    )


def test_openai_model_info_serializes_identity_extensions():
    identity = build_model_identity(
        source="local_byok",
        provider_id="openai",
        model_id="gpt-5.6-sol",
    )
    model = ModelInfo(
        id="cloud/openai/gpt-5.6-sol",
        name=identity["displayName"],
        display_name=identity["displayName"],
        identity=identity,
    )

    payload = model.model_dump()
    assert payload["id"] == "cloud/openai/gpt-5.6-sol"
    assert payload["name"] == "(BYOK) OpenAI · ChatGPT 5.6 Sol"
    assert payload["identity"]["source"] == "byok"
