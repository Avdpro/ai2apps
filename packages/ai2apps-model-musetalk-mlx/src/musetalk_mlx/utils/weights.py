"""Weight loading: PyTorch/diffusers safetensors -> MLX module trees.

Because the MLX modules mirror the diffusers state_dict names 1:1, the only
transform needed is the conv weight layout: PT (O, I, kH, kW) -> MLX (O, kH, kW, I).
A 4-D `.weight` is always a conv here (Linear weights are 2-D).
"""

from __future__ import annotations

from pathlib import Path

import mlx.core as mx

# the raw sd-vae-ft-mse checkpoint predates the diffusers attention rename
# (from_pretrained remaps these on load; the safetensors file keeps the old names)
_ATTN_RENAME = {
    ".query.": ".to_q.",
    ".key.": ".to_k.",
    ".value.": ".to_v.",
    ".proj_attn.": ".to_out.0.",
}


def _rename(key: str) -> str:
    for old, new in _ATTN_RENAME.items():
        if old in key:
            return key.replace(old, new)
    return key


def _convert(key: str, w: mx.array) -> mx.array:
    if key.endswith(".weight") and w.ndim == 4:  # conv2d: (O,I,kH,kW) -> (O,kH,kW,I)
        return w.transpose(0, 2, 3, 1)
    if key.endswith(".weight") and w.ndim == 3:  # conv1d: (O,I,k) -> (O,k,I)
        return w.transpose(0, 2, 1)
    return w


def save_native(model, path: str | Path):
    """Materialize + save a model's MLX-native params as safetensors (torch-free reload)."""
    from mlx.utils import tree_flatten

    weights = dict(tree_flatten(model.parameters()))
    mx.eval(weights)
    mx.save_safetensors(str(path), weights)


def load_native(model, path: str | Path):
    """Load MLX-native safetensors saved by save_native (no transpose, names already MLX)."""
    model.load_weights(str(path))
    mx.eval(model.parameters())
    return model


def load_unet_weights(model, ckpt_path: str | Path, strict: bool = True):
    """Load the MuseTalk UNet. Accepts .safetensors (runtime) or .pth (dev, needs torch).

    Names already match (to_q/to_k/to_v/to_out.0); only conv weights need transpose.
    """
    ckpt_path = Path(ckpt_path)
    if ckpt_path.suffix == ".safetensors":
        raw = mx.load(str(ckpt_path))
    else:  # .pth torch state_dict (dev/parity path)
        import numpy as np
        import torch

        sd = torch.load(ckpt_path, map_location="cpu", weights_only=True)
        raw = {k: mx.array(v.float().numpy().astype(np.float32)) for k, v in sd.items()}
    converted = [(k, _convert(k, v)) for k, v in raw.items()]
    model.load_weights(converted, strict=strict)
    mx.eval(model.parameters())
    return model


def load_whisper_encoder_weights(model, weights_dir: str | Path, strict: bool = True):
    """Load HF whisper-tiny encoder.* tensors into the MLX WhisperEncoder."""
    weights_dir = Path(weights_dir)
    st = weights_dir / "model.safetensors"
    raw = mx.load(str(st))
    prefix = "model.encoder."  # full WhisperForConditionalGeneration ckpt
    converted = []
    for k, v in raw.items():
        if not k.startswith(prefix):
            continue
        rk = k[len(prefix) :]
        converted.append((rk, _convert(rk, v)))
    model.load_weights(converted, strict=strict)
    mx.eval(model.parameters())
    return model


def load_vae_weights(model, weights_dir: str | Path, strict: bool = True):
    """Load sd-vae-ft-mse safetensors into the MLX AutoencoderKL."""
    weights_dir = Path(weights_dir)
    st = weights_dir / "diffusion_pytorch_model.safetensors"
    if not st.exists():
        cands = list(weights_dir.glob("*.safetensors"))
        if not cands:
            raise FileNotFoundError(f"no safetensors in {weights_dir}")
        st = cands[0]
    raw = mx.load(str(st))
    converted = [(rk, _convert(rk, v)) for k, v in raw.items() for rk in (_rename(k),)]
    model.load_weights(converted, strict=strict)
    mx.eval(model.parameters())
    return model
