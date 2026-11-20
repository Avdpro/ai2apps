"""AVTR-1 flow-matching network in MLX; no Torch at inference.

Architecture follows the pinned official scripted checkpoint. Tensor keys and
normalizers are preserved by the offline converter; config contains module types
and scalar attributes only, never executable serialized code.
"""

import json
import math
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn


class MotionModel:
    def __init__(self, root):
        root = Path(root)
        self.config = json.loads((root / "model_config.json").read_text())
        self.weights = mx.load(str(root / "motion.safetensors"))
        self.children = {}
        for name in self.config:
            parent, _, child = name.rpartition(".")
            if name:
                self.children.setdefault(parent, []).append(name)
        self.shape = self.config["model"]
        mx.eval(self.weights)

    def linear(self, name, x):
        y = x @ self.weights[name + ".weight"].T
        bias = self.weights.get(name + ".bias")
        return y if bias is None else y + bias

    def call(self, name, x, context=None):
        cfg = self.config[name]
        typ = cfg["type"]
        if typ in ("Linear", "VectorizedSplitLayer"):
            return self.linear(name, x)
        if typ == "Identity":
            return x
        if typ == "GELU":
            return nn.gelu(x)
        if typ == "SiLU":
            return nn.silu(x)
        if typ == "Mish":
            return nn.mish(x)
        if typ == "Sequential":
            for child in self.children.get(name, []):
                x = self.call(child, x)
            return x
        if typ == "SinusoidalPosEmb":
            half = cfg["dim"] // 2
            phase = (
                x.squeeze(-1)[..., None]
                * 1000
                * mx.exp(mx.arange(half) * (-math.log(10000) / (half - 1)))
            )
            return mx.concatenate([mx.sin(phase), mx.cos(phase)], axis=-1)
        if typ == "LayerNorm":
            return mx.fast.layer_norm(
                x,
                self.weights.get(name + ".weight"),
                self.weights.get(name + ".bias"),
                cfg["eps"],
            )
        if typ == "TransformerEncoderLayer":
            x = x + self.call(name + ".self_attn", self.call(name + ".norm1", x))
            return x + self.linear(
                name + ".linear2",
                nn.gelu(self.linear(name + ".linear1", self.call(name + ".norm2", x))),
            )
        if typ == "Attention":
            context = x if context is None else context
            b, n, _ = x.shape
            h, d = cfg["nhead"], cfg["inner_dim"]
            q = self.linear(name + ".to_q", x).reshape(b, n, h, d).transpose(0, 2, 1, 3)
            k = (
                self.linear(name + ".to_k", context)
                .reshape(b, -1, h, d)
                .transpose(0, 2, 1, 3)
            )
            v = (
                self.linear(name + ".to_v", context)
                .reshape(b, -1, h, d)
                .transpose(0, 2, 1, 3)
            )
            norm = name + ".norm"
            q = mx.fast.rms_norm(q, None, self.config[norm]["eps"]) * (
                self.weights[norm + ".q_weight"] + 1
            )
            k = mx.fast.rms_norm(k, None, self.config[norm]["eps"]) * (
                self.weights[norm + ".k_weight"] + 1
            )
            inv = self.weights[name + ".rotary.inv_freq"]

            def rotate(a):
                phase = mx.arange(a.shape[-2])[:, None] * inv[None, :]
                phase = mx.concatenate([phase, phase], axis=-1)
                left, right = mx.split(a, 2, axis=-1)
                return a * mx.cos(phase) + mx.concatenate(
                    [-right, left], axis=-1
                ) * mx.sin(phase)

            result = mx.fast.scaled_dot_product_attention(
                rotate(q), rotate(k), v, scale=d**-0.5
            ).transpose(0, 2, 1, 3)
            if cfg["use_gate"]:
                result = result * mx.sigmoid(self.linear(name + ".to_gate", x)).reshape(
                    b, n, h, d
                )
            return self.linear(name + ".proj", result.reshape(b, n, h * d))
        raise ValueError(f"Unsupported reviewed module: {name}: {typ}")

    def encode(self, past_cond, audio_cond, kp_cond, past_times):
        left, right = mx.split(audio_cond, 2, axis=-1)
        prefix = "model.audio_fusion_gate"
        left = self.call(prefix + ".ln_x", self.linear(prefix + ".proj_x", left))
        right = self.call(prefix + ".ln_y", self.linear(prefix + ".proj_y", right))
        gate = mx.sigmoid(
            self.call(prefix + ".gate", mx.concatenate([left, right], axis=-1))
        )
        audio_self = self.call("model.cond_encoder_self", left * gate)
        audio_other = self.call("model.cond_encoder_other", right * (1 - gate))
        kp = self.call(
            "model.norm_base_kp_cond", self.call("model.canon_projection", kp_cond)
        )
        past = self.call(
            "model.norm_past_cond", self.linear("model.input_projection", past_cond)
        )
        size = self.shape["chunk_size"]
        past = past + mx.repeat(
            self.call("model.quality_embed", past_times), size, axis=1
        )
        return kp, past[:, :-size], past[:, -size:], audio_self, audio_other

    def decode(
        self, x, condition, t, self_weights=3.0, other_weights=1.0, kp_weights=1.0
    ):
        batch = x.shape[0]
        cond = tuple(mx.tile(v, (4, 1, 1)) for v in condition)
        x = mx.tile(x, (4, 1, 1))
        t = self.call("model.time_mlp", mx.tile(t, (4, 1)))
        x = self.linear("model.input_projection", x)
        masks = [
            mx.repeat(mx.array(v), batch).reshape(-1, 1, 1)
            for v in ([0, 0, 0, 1], [0, 1, 0, 0], [0, 0, 1, 0])
        ]

        def modulate(prefix, n, value):
            scale, shift = mx.split(
                self.call(prefix + f".adaln{n}.adaln_proj", t)[:, None, :], 2, axis=-1
            )
            return self.call(prefix + f".norm{n}", value) * (1 + scale) + shift

        for index in range(self.shape["num_layers"]):
            p = f"model.seqTransDecoder.stack.{index}"
            x = x + self.call(p + ".self_attn", modulate(p, 1, x))
            mod = modulate(p, 2, x)
            delta = masks[0] * self.call(p + ".kp_cross", cond[0])
            delta = (
                delta
                + self.call(p + ".multihead_attn_last_past", mod, cond[2])
                + self.call(p + ".multihead_attn_past", mod, cond[1])
            )
            delta = delta + masks[1] * self.call(
                p + ".multihead_attn_audio_self", mod, cond[3]
            )
            delta = delta + masks[2] * self.call(
                p + ".multihead_attn_audio_other", mod, cond[4]
            )
            x = x + delta
            x = x + self.linear(
                p + ".linear2", nn.gelu(self.linear(p + ".linear1", modulate(p, 3, x)))
            )
        heads = self.linear("model.split_layer", x[:, -self.shape["chunk_size"] :])
        past, own, other, kp = mx.split(heads, 4, axis=0)
        guided = (
            past
            + self_weights * (own - past)
            + other_weights * (other - past)
            + kp_weights * (kp - past)
        )
        norm = (
            mx.sqrt(
                mx.sum(guided**2, axis=1) @ self.weights["model.last_layer.rms_proj"]
            )
            + 1e-8
        )
        return self.linear("model.last_layer", guided / norm[:, None, :])

    def sample(
        self,
        condition,
        noise,
        steps=5,
        self_weights=3.0,
        other_weights=1.0,
        kp_weights=1.0,
    ):
        if steps < 2:
            raise ValueError("steps must be at least two schedule points")
        x = noise
        for i in range(steps - 1):
            x = x + self.decode(
                x,
                condition,
                mx.full((x.shape[0], 1), i / (steps - 1)),
                self_weights,
                other_weights,
                kp_weights,
            ) / (steps - 1)
            mx.eval(x)
        return x
