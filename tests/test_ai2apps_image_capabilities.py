import pytest

from ai2apps.model_worker.image_capabilities import (
    IMAGE_CAPABILITIES_SCHEMA,
    ImageCapabilitiesError,
    default_image_capabilities,
    validate_image_capabilities,
)


def test_default_image_capabilities_are_valid():
    result = validate_image_capabilities(default_image_capabilities())
    assert result["schema"] == IMAGE_CAPABILITIES_SCHEMA
    assert result["operations"] == ["image_generation"]


def test_image_capabilities_normalize_runtime_optimizations():
    value = default_image_capabilities()
    value["operations"] = ["image_generation", "image_edit"]
    value["geometry"]["multiple_of"] = 32
    value["execution"] = {
        "quantizations": ["bf16", "q8", "q4"],
        "compiled_denoiser": True,
        "persistent_quantized_cache": True,
        "single_pass_guidance_one": True,
        "metal_rms_adaln_fusion": True,
        "edit_kv_cache": True,
        "max_concurrency_per_device": 1,
    }
    result = validate_image_capabilities(value)
    assert result["execution"]["compiled_denoiser"] is True
    assert result["execution"]["persistent_quantized_cache"] is True
    assert result["execution"]["single_pass_guidance_one"] is True
    assert result["execution"]["metal_rms_adaln_fusion"] is True
    assert result["execution"]["edit_kv_cache"] is True


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(schema="wrong"),
        lambda value: value.update(operations=["image_edit"]),
        lambda value: value["geometry"].update(multiple_of=0),
        lambda value: value["defaults"].update(width=4096),
    ],
)
def test_invalid_image_capabilities_are_rejected(mutation):
    value = default_image_capabilities()
    mutation(value)
    with pytest.raises(ImageCapabilitiesError):
        validate_image_capabilities(value)
