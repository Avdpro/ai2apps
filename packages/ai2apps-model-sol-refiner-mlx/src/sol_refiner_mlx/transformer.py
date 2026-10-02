"""Video-only LTX-2.3 DiT with SoL's BF16 coordinate/rotation semantics.

The source pipeline sets isolate_modalities=True; audio modules cannot affect
video output and are deliberately neither loaded nor evaluated here.
"""

import math

import mlx.core as mx
import numpy as np

from .precision import gelu_approx, silu
from .weights import config, linear, load_component


def rms(x, weight=None, eps=1e-6):
    # torch.nn.RMSNorm: reduce/multiply in fp32, round output to input dtype.
    y = x.astype(mx.float32) * mx.rsqrt(
        mx.mean(mx.square(x.astype(mx.float32)), axis=-1, keepdims=True) + eps
    )
    if weight is not None:
        y = y * weight.astype(mx.float32)
    return y.astype(x.dtype)


def rope(grid, fps, dim, heads, dtype=mx.bfloat16):
    f, h, w = grid
    axes = np.stack(
        np.meshgrid(np.arange(f), np.arange(h), np.arange(w), indexing="ij"), axis=0
    ).reshape(3, -1)
    bounds = np.stack((axes, axes + 1), axis=-1).astype(np.float32)
    bounds *= np.array([8, 32, 32], np.float32)[:, None, None]
    bounds[0] = np.maximum(bounds[0] - 7, 0) / fps
    coords = mx.array(bounds).astype(dtype)
    mid = ((coords[..., 0] + coords[..., 1]) / 2).astype(dtype)
    grid01 = mx.stack([mid[i] / p for i, p in enumerate((20, 2048, 2048))], axis=-1)
    frequencies = mx.array(
        (10000 ** np.linspace(0, 1, dim // 6, dtype=np.float64) * np.pi / 2).astype(
            np.float32
        )
    )
    phase = (
        ((grid01[..., None] * 2 - 1).astype(dtype).astype(mx.float32) * frequencies)
        .transpose(0, 2, 1)
        .reshape(-1, (dim // 6) * 3)
    )
    pad = dim // 2 - phase.shape[-1]
    cos = mx.concatenate((mx.ones((phase.shape[0], pad)), mx.cos(phase)), axis=-1)
    sin = mx.concatenate((mx.zeros((phase.shape[0], pad)), mx.sin(phase)), axis=-1)
    return tuple(
        v.reshape(1, -1, heads, dim // heads // 2).transpose(0, 2, 1, 3).astype(dtype)
        for v in (cos, sin)
    )


def rotate(x, freqs, heads):
    b, t, dim = x.shape
    a = x.reshape(b, t, heads, 2, dim // heads // 2).transpose(0, 2, 1, 3, 4)
    c, s = (v[..., None, :] for v in freqs)
    product = a * c
    # addcmul accumulates into the already rounded multiplication output.
    first = (
        product[..., 0, :].astype(mx.float32)
        - s[..., 0, :].astype(mx.float32) * a[..., 1, :].astype(mx.float32)
    ).astype(x.dtype)
    second = (
        product[..., 1, :].astype(mx.float32)
        + s[..., 0, :].astype(mx.float32) * a[..., 0, :].astype(mx.float32)
    ).astype(x.dtype)
    return (
        mx.stack((first, second), axis=-2).transpose(0, 2, 1, 3, 4).reshape(b, t, dim)
    )


def attention(
    x, context, weights, name, heads, freqs=None, mask=None, rotary_round=True
):
    q = rms(linear(x, weights, name + ".to_q"), weights[name + ".norm_q.weight"])
    k = rms(linear(context, weights, name + ".to_k"), weights[name + ".norm_k.weight"])
    v = linear(context, weights, name + ".to_v")
    if freqs is not None:
        if rotary_round:
            q, k = rotate(q, freqs, heads), rotate(k, freqs, heads)
        else:

            def standard_rotate(z):
                b, t, d = z.shape
                a = z.reshape(b, t, heads, 2, d // heads // 2).transpose(0, 2, 1, 3, 4)
                c, s = freqs
                first = a[..., 0, :] * c - a[..., 1, :] * s
                second = a[..., 1, :] * c + a[..., 0, :] * s
                return (
                    mx.stack((first, second), axis=-2)
                    .transpose(0, 2, 1, 3, 4)
                    .reshape(b, t, d)
                    .astype(z.dtype)
                )

            q, k = standard_rotate(q), standard_rotate(k)
    b, t, dim = q.shape
    q, k, v = [
        z.reshape(b, -1, heads, dim // heads).transpose(0, 2, 1, 3) for z in (q, k, v)
    ]
    y = mx.fast.scaled_dot_product_attention(
        q, k, v, scale=(dim // heads) ** -0.5, mask=mask
    )
    y = y.transpose(0, 2, 1, 3)
    if name + ".to_gate_logits.weight" in weights:
        y = (
            y
            * (2 * mx.sigmoid(linear(x, weights, name + ".to_gate_logits")))[..., None]
        )
    return linear(y.reshape(b, t, dim), weights, name + ".to_out.0")


def time_embedding(weights, name, sigma, dtype):
    half = 128
    freq = mx.exp(-math.log(10000) * mx.arange(half).astype(mx.float32) / half)
    phase = mx.array([sigma * 1000], mx.float32)[:, None] * freq
    x = mx.concatenate((mx.cos(phase), mx.sin(phase)), axis=-1).astype(dtype)
    x = linear(
        silu(linear(x, weights, name + ".emb.timestep_embedder.linear_1")),
        weights,
        name + ".emb.timestep_embedder.linear_2",
    )
    return linear(silu(x), weights, name + ".linear")[:, None, :], x[:, None, :]


def block(x, context, weights, prefix, temb, prompt_temb, freqs, heads):
    dim = x.shape[-1]
    mod = weights[prefix + ".scale_shift_table"][None, None] + temb.reshape(
        1, -1, 9, dim
    )
    shift, scale, gate, fs, fc, fg, ts, tc, tg = [mod[:, :, i] for i in range(9)]
    x = (
        x
        + attention(
            rms(x) * (1 + scale) + shift,
            rms(x) * (1 + scale) + shift,
            weights,
            prefix + ".attn1",
            heads,
            freqs,
        )
        * gate
    )
    p = weights[prefix + ".prompt_scale_shift_table"][None, None] + prompt_temb.reshape(
        1, -1, 2, dim
    )
    ctx = context * (1 + p[:, :, 1]) + p[:, :, 0]
    x = (
        x
        + attention(rms(x) * (1 + tc) + ts, ctx, weights, prefix + ".attn2", heads) * tg
    )
    y = rms(x) * (1 + fc) + fs
    y = linear(
        gelu_approx(linear(y, weights, prefix + ".ff.net.0.proj")),
        weights,
        prefix + ".ff.net.2",
    )
    return x + y * fg


def video_key(key):
    if key.startswith(
        ("proj_in.", "proj_out.", "time_embed.", "prompt_adaln.", "scale_shift_table")
    ):
        return True
    if key.startswith("transformer_blocks."):
        part = key.split(".")[2]
        return part in {
            "attn1",
            "attn2",
            "ff",
            "scale_shift_table",
            "prompt_scale_shift_table",
        }
    return False


class VideoTransformer:
    def __init__(self, root, release_weights=False):
        self.release_weights = release_weights
        self.consumed = False
        self.config = config(root, "transformer")
        self.weights = load_component(root, "transformer", video_key)
        self.heads = self.config["num_attention_heads"]
        self.layers = self.config["num_layers"]

    def __call__(self, latent, context, sigma, fps, progress=None):
        if getattr(self, "consumed", False):
            raise RuntimeError(
                "Released weights: construct a new VideoTransformer for another call"
            )
        self.consumed = getattr(self, "release_weights", False)
        b, c, f, h, w = latent.shape
        if b != 1:
            raise ValueError("This prototype supports one video per invocation")
        x = latent.transpose(0, 2, 3, 4, 1).reshape(b, -1, c).astype(mx.bfloat16)
        context = context.astype(x.dtype)
        x = linear(x, self.weights, "proj_in")
        temb, embedded = time_embedding(self.weights, "time_embed", sigma, x.dtype)
        prompt_temb, _ = time_embedding(self.weights, "prompt_adaln", sigma, x.dtype)
        frequencies = rope((f, h, w), fps, x.shape[-1], self.heads, x.dtype)
        for i in range(self.layers):
            x = block(
                x,
                context,
                self.weights,
                f"transformer_blocks.{i}",
                temb,
                prompt_temb,
                frequencies,
                self.heads,
            )
            mx.eval(x)
            if getattr(self, "release_weights", False):
                prefix = f"transformer_blocks.{i}."
                for key in list(self.weights):
                    if key.startswith(prefix):
                        del self.weights[key]
            if progress:
                progress(i + 1, self.layers)
        mod = self.weights["scale_shift_table"][None, None] + embedded[:, :, None]
        x = mx.fast.layer_norm(x, None, None, 1e-6) * (1 + mod[:, :, 1]) + mod[:, :, 0]
        return (
            linear(x, self.weights, "proj_out")
            .reshape(b, f, h, w, c)
            .transpose(0, 4, 1, 2, 3)
        )
