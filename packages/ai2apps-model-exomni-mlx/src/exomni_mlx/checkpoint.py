"""Strict offline loading of the released Ex-Omni teacher's checkpoint stack."""

import json
from pathlib import Path

import mlx.core as mx

from .video import WanModel, convert_weights


def merge_lora(base, overlays, *, alpha=64.0, rank=128):
    """Overlay the same adapter in source order, then merge once in FP32.

    Upstream loads OmniAvatar followed by Ex-Omni into one named adapter.
    Adding both adapters independently would produce a different model.
    """
    state = dict(base)
    for overlay in overlays:
        state.update(overlay)
    output = {
        k.replace(".base_layer.", "."): v for k, v in state.items() if ".lora_" not in k
    }
    consumed = set()
    for name, a in state.items():
        if ".lora_A.default.weight" not in name:
            continue
        prefix = name.removesuffix(".lora_A.default.weight")
        bkey = prefix + ".lora_B.default.weight"
        target = prefix + ".weight"
        if bkey not in state or target not in output:
            raise ValueError("Incomplete LoRA pair: " + prefix)
        b = state[bkey]
        weight = output[target]
        if (
            a.ndim != 2
            or b.ndim != 2
            or a.shape[0] != rank
            or b.shape[1] != rank
            or (b.shape[0], a.shape[1]) != weight.shape
        ):
            raise ValueError("LoRA dimensions do not match: " + prefix)
        output[target] = weight.astype(mx.float32) + (
            b.astype(mx.float32) @ a.astype(mx.float32)
        ) * (alpha / rank)
        mx.eval(output[target])
        consumed.update((name, bkey))
    unknown = {k for k in state if ".lora_" in k} - consumed
    if unknown:
        raise ValueError("Unsupported LoRA keys: " + str(sorted(unknown)))
    return output


def load_teacher(
    base_dir, omniavatar_checkpoint, teacher_checkpoint, *, dtype=mx.bfloat16
):
    root = Path(base_dir)
    config = json.loads((root / "config.json").read_text())
    if (config.get("dim"), config.get("num_layers")) != (1536, 30):
        raise ValueError("Expected released Wan 1.3B teacher base")
    state = merge_lora(
        mx.load(str(root / "diffusion_pytorch_model.safetensors")),
        [mx.load(str(omniavatar_checkpoint)), mx.load(str(teacher_checkpoint))],
    )
    model = WanModel(
        dim=1536,
        in_dim=33,
        ffn_dim=8960,
        out_dim=16,
        text_dim=4096,
        freq_dim=256,
        eps=1e-6,
        patch_size=(1, 2, 2),
        num_heads=12,
        num_layers=30,
        has_image_input=False,
        audio_hidden_size=32,
        speech_embedding_dim=256,
    )
    state = convert_weights({k: v.astype(dtype) for k, v in state.items()})
    model.load_weights(list(state.items()), strict=True)
    model.eval()
    mx.eval(model.parameters())
    return model
