"""Gemma 3 all-layer features and the video text connector, entirely on MLX."""

import gc
import math

import mlx.core as mx
import mlx.nn as nn
import numpy as np
from mlx_lm.models.gemma3_text import Gemma3Model, ModelArgs
from transformers import AutoTokenizer

from .transformer import attention, rms
from .weights import config, linear, load_component


def gemma_args(cfg):
    cfg = dict(cfg)
    params = cfg.get("rope_parameters", {})
    if params:
        full = params["full_attention"]
        local = params["sliding_attention"]
        cfg["rope_theta"] = full["rope_theta"]
        cfg["rope_local_base_freq"] = local["rope_theta"]
        cfg["rope_scaling"] = {k: v for k, v in full.items() if k != "rope_theta"}
    return ModelArgs.from_dict(cfg)


def hidden_states(model, ids, mask, release_weights=False):
    h = model.embed_tokens(ids)
    h = h * mx.array(h.shape[-1] ** 0.5, mx.bfloat16).astype(h.dtype)
    if release_weights:
        mx.eval(h)
        model.embed_tokens = None
    states = []
    length = ids.shape[1]
    pos = mx.arange(length)
    causal = pos[:, None] >= pos[None, :]
    valid = mask[:, None, None, :].astype(mx.bool_)
    global_mask = causal[None, None] & valid
    local_mask = (
        global_mask
        & ((pos[:, None] - pos[None, :]) < model.args.sliding_window)[None, None]
    )
    for i, layer in enumerate(model.layers):
        states.append(h)
        layer_mask = (
            global_mask
            if (i + 1) % model.args.sliding_window_pattern == 0
            else local_mask
        )
        h = layer(h, mask=layer_mask, cache=None)
        mx.eval(h)
        if release_weights:
            model.layers[i] = None
    states.append(model.norm(h))
    return states


def encode_features(root, prompt, length=1024, release_weights=False):
    cfg = config(root, "text_encoder")["text_config"]
    cfg["model_type"] = "gemma3_text"
    args = gemma_args(cfg)
    model = Gemma3Model(args)
    weights = load_component(
        root, "text_encoder", lambda k: k.startswith("language_model.model.")
    )
    model.load_weights(
        [(k.removeprefix("language_model.model."), v) for k, v in weights.items()],
        strict=True,
    )
    del weights
    tokenizer = AutoTokenizer.from_pretrained(
        str(root / "tokenizer"), local_files_only=True
    )
    tokenizer.padding_side = "left"
    batch = tokenizer(
        [prompt.strip()],
        padding="max_length",
        truncation=True,
        max_length=length,
        return_tensors="np",
        add_special_tokens=True,
    )
    ids = mx.array(batch["input_ids"])
    mask = mx.array(batch["attention_mask"])
    states = hidden_states(model, ids, mask, release_weights=release_weights)
    # Normalize each hidden layer independently, preserving BF16 rounding.
    normalized = []
    for h in states:
        normalized.append(h * mx.rsqrt(mx.mean(h * h, axis=-1, keepdims=True) + 1e-6))
    features = mx.stack(normalized, axis=-1).reshape(1, length, -1)
    features = mx.where(
        mask[..., None].astype(mx.bool_), features, mx.zeros_like(features)
    )
    mx.eval(features)
    del model, states, normalized
    gc.collect()
    mx.clear_cache()
    return features, mask


class VideoConnector:
    def __init__(self, root):
        self.config = config(root, "connectors")
        self.w = load_component(
            root,
            "connectors",
            lambda k: k.startswith(("video_connector.", "video_text_proj_in.")),
        )

    def __call__(self, features, mask):
        c = self.config
        dim = c["video_hidden_dim"]
        heads = c["video_connector_num_attention_heads"]
        x = linear(
            features * math.sqrt(dim / c["caption_channels"]),
            self.w,
            "video_text_proj_in",
        )
        length = x.shape[1]
        registers = self.w["video_connector.learnable_registers"]
        if length % registers.shape[0]:
            raise ValueError("Text length must divide into whole register groups")
        # Inference currently handles one prompt; stable order without sorting ties.
        valid = np.flatnonzero(np.array(mask[0]).astype(bool))
        tokens = x[:, mx.array(valid), :]
        registers = mx.tile(registers, (length // registers.shape[0], 1))[None]
        x = mx.concatenate((tokens, registers[:, len(valid) :]), axis=1)
        frequencies = (
            10000 ** np.linspace(0, 1, dim // 2, dtype=np.float64) * np.pi / 2
        ).astype(np.float32)
        phase = (
            np.arange(length, dtype=np.float32) / c["connector_rope_base_seq_len"] * 2
            - 1
        )[:, None] * frequencies
        # Connectors use float32 rotary; SoL's BF16 override applies only to DiT.
        freqs = tuple(
            mx.array(v).reshape(1, length, heads, -1).transpose(0, 2, 1, 3)
            for v in (np.cos(phase), np.sin(phase))
        )
        for i in range(c["video_connector_num_layers"]):
            p = f"video_connector.transformer_blocks.{i}"
            n = rms(x)
            x = x + attention(
                n, n, self.w, p + ".attn1", heads, freqs, rotary_round=False
            )
            x = x + linear(
                nn.gelu_approx(linear(rms(x), self.w, p + ".ff.net.0.proj")),
                self.w,
                p + ".ff.net.2",
            )
            mx.eval(x)
        return rms(x)
