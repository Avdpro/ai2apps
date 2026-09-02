from omlx.patches.glm5_next_cache.runtime import (
    _VENDOR_MODELS,
    _compact_safetensors,
    _install_vendor_namespace,
)


def test_vendor_namespace_precedes_pinned_mlx_vlm_models():
    import mlx_vlm.models
    from mlx_vlm import prompt_utils

    _install_vendor_namespace()

    assert mlx_vlm.models.__path__[0] == str(_VENDOR_MODELS)
    assert (
        prompt_utils.MODEL_CONFIG["glm5_next"]
        == prompt_utils.MessageFormat.LIST_WITH_IMAGE_FIRST
    )


def test_compact_reader_keeps_nonexperts_and_one_aliased_placeholder():
    values = {
        "model.language_model.embed_tokens.weight": object(),
        "model.language_model.layers.3.mlp.experts.0.gate_proj.weight": object(),
        "model.language_model.layers.3.mlp.experts.1.gate_proj.weight": object(),
        "model.language_model.layers.45.mlp.experts.0.gate_proj.weight": object(),
    }
    compact = _compact_safetensors("ignored", lambda _path: values, slots=4)

    assert "model.language_model.embed_tokens.weight" in compact
    for slot in range(4):
        assert (
            f"model.language_model.layers.3.mlp.experts.{slot}.gate_proj.weight"
            in compact
        )
    assert not any("layers.45.mlp.experts" in key for key in compact)


def test_compact_reader_keeps_layer45_placeholder_when_mtp_enabled(monkeypatch):
    monkeypatch.setenv("OMLX_GLM5_MTP_ENABLED", "1")
    values = {
        "model.language_model.layers.45.mlp.experts.0.gate_proj.weight": object(),
        "model.language_model.layers.45.mlp.experts.1.gate_proj.weight": object(),
    }

    compact = _compact_safetensors("ignored", lambda _path: values, slots=2)

    assert (
        "model.language_model.layers.45.mlp.experts.0.gate_proj.weight" in compact
    )
    assert (
        "model.language_model.layers.45.mlp.experts.1.gate_proj.weight" in compact
    )
