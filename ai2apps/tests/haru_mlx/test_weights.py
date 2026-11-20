"""The checkpoint -> parameter mapping, checked on names and shapes alone (no MLX)."""

import pytest

from ai2apps.model_worker.haru_mlx import weights
from ai2apps.model_worker.haru_mlx.config import HaruConfig


def test_fused_projections_stack_in_a_fixed_order():
    shapes = {
        "lm.layers.0.linear_attn.in_proj_a.weight": (4, 64),
        "lm.layers.0.linear_attn.in_proj_z.weight": (64, 64),
        "lm.layers.0.linear_attn.in_proj_qkv.weight": (192, 64),
        "lm.layers.0.linear_attn.in_proj_b.weight": (4, 64),
        "lm.layers.3.self_attn.v_proj.weight": (32, 64),
        "lm.layers.3.self_attn.q_proj.weight": (128, 64),
        "lm.layers.3.self_attn.k_proj.weight": (32, 64),
        "lm.layers.3.mlp.up_proj.weight": (128, 64),
        "lm.layers.3.mlp.gate_proj.weight": (128, 64),
        "head.final.ada.weight": (128, 64),
        "head.layers.1.ada.weight": (192, 64),
        "head.layers.0.ada.weight": (192, 64),
    }
    plan = weights.conversion_plan(shapes)
    in_proj = plan["lm.layers.0.linear_attn.in_proj.weight"]
    assert [s.split(".")[-2] for s in in_proj.sources] == ["in_proj_qkv", "in_proj_z", "in_proj_b", "in_proj_a"]
    assert in_proj.shape == (264, 64) and in_proj.layout == weights.COPY
    assert [s.split(".")[-2] for s in plan["lm.layers.3.self_attn.qkv.weight"].sources] == ["q_proj", "k_proj", "v_proj"]
    assert [s.split(".")[-2] for s in plan["lm.layers.3.mlp.gate_up.weight"].sources] == ["gate_proj", "up_proj"]
    assert plan["head.ada.weight"].sources == (
        "head.layers.0.ada.weight", "head.layers.1.ada.weight", "head.final.ada.weight",
    )
    assert plan["head.ada.weight"].shape == (512, 64)
    assert len(plan) == 4


def test_layouts():
    shapes = {
        "lm.norm.weight": (64,),
        "lm.layers.0.input_layernorm.weight": (64,),
        "lm.layers.0.post_attention_layernorm.weight": (64,),
        "lm.layers.3.self_attn.q_norm.weight": (16,),
        "lm.layers.3.self_attn.k_norm.weight": (16,),
        "lm.layers.0.linear_attn.norm.weight": (16,),
        "lm.layers.0.linear_attn.conv1d.weight": (192, 1, 4),
        "latent_scale": (),
        "codec.encoder.stem.weight": (4, 1, 7),
        "codec.encoder.down.0.weight": (8, 4, 4),
        "codec.encoder.stages.0.0.conv.weight": (4, 1, 7),
        "codec.encoder.stages.0.0.norm.weight": (4,),
        "codec.decoder.up.0.weight": (256, 128, 16),
        "model_audio_proj.norm.weight": (64,),
    }
    plan = weights.conversion_plan(shapes)
    layout = {name: (conversion.layout, conversion.shape) for name, conversion in plan.items()}
    for name in ("lm.norm.weight", "lm.layers.0.input_layernorm.weight", "lm.layers.0.post_attention_layernorm.weight",
                 "lm.layers.3.self_attn.q_norm.weight", "lm.layers.3.self_attn.k_norm.weight"):
        assert layout[name][0] == weights.GAMMA, name
    # Gains that are not zero-centred stay as they are.
    for name in ("lm.layers.0.linear_attn.norm.weight", "codec.encoder.stages.0.0.norm.weight", "model_audio_proj.norm.weight"):
        assert layout[name][0] == weights.COPY, name
    assert layout["lm.layers.0.linear_attn.conv1d.weight"] == (weights.CHANNELS_LAST, (192, 4, 1))
    assert layout["latent_scale"] == (weights.SCALAR, ())
    assert layout["codec.encoder.stem.weight"] == (weights.CONV_MATRIX, (4, 7))
    assert layout["codec.encoder.down.0.weight"] == (weights.CONV_MATRIX, (8, 16))
    assert layout["codec.encoder.stages.0.0.conv.weight"] == (weights.CONV_MATRIX, (4, 7))
    assert layout["codec.decoder.up.0.weight"] == (weights.CONV_TRANSPOSE_MATRIX, (128 * 16, 256))


def test_check_plan_names_what_is_wrong(tiny_config):
    expected = weights.parameter_shapes(tiny_config)
    plan = {name: weights.Conversion((name,), weights.COPY, shape) for name, shape in expected.items()}
    weights.check_plan(plan, expected)
    broken = dict(plan)
    del broken["lm.norm.weight"]
    broken["lm.extra.weight"] = weights.Conversion(("lm.extra.weight",), weights.COPY, (1,))
    broken["latent_scale"] = weights.Conversion(("latent_scale",), weights.SCALAR, (2,))
    with pytest.raises(ValueError) as error:
        weights.check_plan(broken, expected)
    message = str(error.value)
    assert "missing from the checkpoint: lm.norm.weight" in message
    assert "not a model parameter: lm.extra.weight" in message
    assert "latent_scale: checkpoint gives (2,)" in message


def test_every_checkpoint_tensor_is_consumed_exactly_once(checkpoint_shapes):
    plan = weights.conversion_plan(checkpoint_shapes)
    consumed = [source for conversion in plan.values() for source in conversion.sources]
    assert len(consumed) == len(set(consumed))
    assert set(consumed) == set(checkpoint_shapes)


def test_every_model_parameter_is_covered(checkpoint, checkpoint_shapes):
    config = HaruConfig.from_file(checkpoint / "config.json")
    plan = weights.conversion_plan(checkpoint_shapes)
    expected = weights.parameter_shapes(config)
    weights.check_plan(plan, expected)
    assert {name: conversion.shape for name, conversion in plan.items()} == expected


def test_a_missing_or_unknown_tensor_is_named(checkpoint, checkpoint_shapes):
    expected = weights.parameter_shapes(HaruConfig.from_file(checkpoint / "config.json"))
    shapes = dict(checkpoint_shapes)
    del shapes["lm.layers.0.linear_attn.in_proj_z.weight"]  # one part of a stacked projection
    shapes["lm.layers.0.linear_attn.unknown.weight"] = (1,)
    with pytest.raises(ValueError) as error:
        weights.check_plan(weights.conversion_plan(shapes), expected)
    assert "lm.layers.0.linear_attn.in_proj.weight: checkpoint gives" in str(error.value)
    assert "not a model parameter: lm.layers.0.linear_attn.unknown.weight" in str(error.value)
