import importlib.util
import json
from pathlib import Path

import mlx.core as mx
import safetensors

SCRIPT = Path(__file__).parents[1] / "scripts/build_ornith15_mlx_vision_checkpoint.py"
SPEC = importlib.util.spec_from_file_location("ornith15_vision_builder", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_extract_visual_sidecar_streams_and_renames(tmp_path):
    source = tmp_path / "source.safetensors"
    output = tmp_path / "vision.safetensors"
    mx.save_safetensors(
        str(source),
        {
            "model.visual.block.weight": mx.arange(16).reshape(4, 4),
            "model.visual.patch_embed.proj.weight": mx.arange(
                96, dtype=mx.float16
            ).reshape(2, 3, 2, 2, 4),
            "model.language_model.embed_tokens.weight": mx.ones((2, 2)),
        },
    )

    result = MODULE.extract_visual_sidecar(source, output)

    assert result["tensor_count"] == 2
    with safetensors.safe_open(str(output), framework="mlx") as handle:
        assert handle.metadata()["format"] == "mlx"
        assert list(handle.keys()) == [
            "vision_tower.block.weight",
            "vision_tower.patch_embed.proj.weight",
        ]
        assert mx.array_equal(
            handle.get_tensor("vision_tower.block.weight"),
            mx.arange(16).reshape(4, 4),
        ).item()
        expected = (
            mx.arange(96, dtype=mx.float16)
            .reshape(2, 3, 2, 2, 4)
            .transpose(0, 2, 3, 4, 1)
        )
        actual = handle.get_tensor("vision_tower.patch_embed.proj.weight")
        assert actual.shape == (2, 2, 2, 4, 3)
        assert mx.array_equal(actual, expected).item()


def test_build_checkpoint_merges_config_and_processor(tmp_path):
    text = tmp_path / "text"
    metadata = tmp_path / "official"
    output = tmp_path / "output"
    text.mkdir()
    metadata.mkdir()
    (text / "config.json").write_text(
        json.dumps({"model_type": "qwen3_5_moe", "quantization": {"bits": 4}})
    )
    (text / "tokenizer.json").write_text("{}")
    for filename in MODULE.PROCESSOR_FILES:
        (metadata / filename).write_text("{}")
    (metadata / "config.json").write_text(
        json.dumps({"vision_config": {"hidden_size": 1152}})
    )
    shard = tmp_path / "official.safetensors"
    mx.save_safetensors(
        str(shard), {"model.visual.patch_embed.weight": mx.ones((2, 2))}
    )

    manifest = MODULE.build_checkpoint(
        text, metadata, shard, output, source_revision="abc123"
    )

    config = json.loads((output / "config.json").read_text())
    assert config["quantization"]["bits"] == 4
    assert config["vision_config"]["hidden_size"] == 1152
    assert config["optiq_vision"]["revision"] == "abc123"
    assert (output / "tokenizer.json").is_file()
    assert manifest["vision"]["tensor_count"] == 1
    assert manifest["vision_sidecar_sha256"]
