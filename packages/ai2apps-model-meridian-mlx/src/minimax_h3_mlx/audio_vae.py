"""MLX port of the MiniMax-H3 audio VAE (``MiniMaxH3AudioVAE``).

A DAC-style waveform **encoder** (strides 2/4/4/5/5 = 800x, i.e. 40 latents per second at 32 kHz)
feeding a causal-attention projection down to 32 latent channels, and a **BigVGAN decoder**
(upsample rates 5/5/2/2/2/2/2 = 800x) back to the waveform. Mono: MiniMax-H3 carries the two stereo
channels as two batch items.

Notes on the port:

* **Channels-last.** MLX convolutions take ``(N, L, C)`` and weights ``(C_out, kL, C_in)``; torch
  uses ``(N, C, L)`` / ``(C_out, C_in, kL)``. Everything runs channels-last internally and the
  public :meth:`encode` / :meth:`decode` transpose at the boundary, so callers still see the
  reference's ``(B, C, L)``.
* **Weight norm is folded at load.** The checkpoint stores ``weight_g`` / ``weight_v`` and the
  effective weight is ``g * v / ||v||``. That is a reparametrization, not a distinct computation, so
  the port folds it once at load time and holds a plain ``weight`` — the only place the module tree
  deliberately departs from the checkpoint's names.
* **Anti-aliasing filters are recomputed**, not loaded. They are Kaiser-windowed sincs and the
  checkpoint stores them as buffers; :func:`kaiser_sinc_filter1d` reproduces them (checked against
  the shipped tensors in the parity test) so the module stays self-contained.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import mlx.core as mx
import mlx.nn as nn
import numpy as np


@dataclass
class AudioVAEConfig:
    encoder_dim: int = 64
    encoder_rates: tuple[int, ...] = (2, 4, 4, 5, 5)
    latent_dim: int = 2048
    latent_channels: int = 32
    num_attention_heads: int = 8
    decoder_dim: int = 1024
    decoder_rates: tuple[int, ...] = (5, 5, 2, 2, 2, 2, 2)
    decoder_kernel_sizes: tuple[int, ...] = (9, 9, 4, 4, 4, 4, 4)
    resblock_kernel_sizes: tuple[int, ...] = (3, 7, 11)
    resblock_dilation_sizes: tuple[tuple[int, ...], ...] = ((1, 3, 5), (1, 3, 5), (1, 3, 5))
    sampling_rate: int = 32000
    latents_mean: tuple[float, ...] = ()
    latents_std: tuple[float, ...] = ()

    @property
    def hop_length(self) -> int:
        return math.prod(self.encoder_rates)


def kaiser_sinc_filter1d(cutoff: float, half_width: float, kernel_size: int) -> mx.array:
    """Kaiser-windowed sinc low-pass filter, shape ``(1, kernel_size)``.

    Kept arithmetically identical to the ``alias-free-torch`` implementation the checkpoint was
    trained with, since the resulting tensor is stored there as a persistent buffer.
    """
    half_size = kernel_size // 2

    attenuation = 2.285 * (half_size - 1) * math.pi * (4 * half_width) + 7.95
    if attenuation > 50.0:
        beta = 0.1102 * (attenuation - 8.7)
    elif attenuation >= 21.0:
        beta = 0.5842 * (attenuation - 21) ** 0.4 + 0.07886 * (attenuation - 21.0)
    else:
        beta = 0.0
    window = np.kaiser(kernel_size, beta)  # symmetric, matching torch's periodic=False

    if kernel_size % 2 == 0:
        time = np.arange(-half_size, half_size, dtype=np.float64) + 0.5
    else:
        time = np.arange(kernel_size, dtype=np.float64) - half_size

    filt = 2 * cutoff * window * np.sinc(2 * cutoff * time)
    # Normalize to sum 1 so a constant input does not leak through the resampler.
    filt = filt / filt.sum()
    return mx.array(filt.astype(np.float32)).reshape(1, kernel_size)


def _depthwise(filt: mx.array, channels: int) -> mx.array:
    """``(1, k)`` filter -> MLX depthwise weight ``(channels, k, 1)``."""
    return mx.broadcast_to(filt.reshape(1, -1, 1), (channels, filt.shape[-1], 1))


def adaptive_avg_pool_last(x: mx.array, out_dim: int) -> mx.array:
    """``F.adaptive_avg_pool1d`` over the final axis.

    In MiniMax-H3 this always divides exactly (256 -> 32), which is a plain group mean; the general
    ragged-bin path is kept for other configurations.
    """
    in_dim = x.shape[-1]
    if in_dim % out_dim == 0:
        return x.reshape(*x.shape[:-1], out_dim, in_dim // out_dim).mean(axis=-1)
    bins = [
        x[..., (i * in_dim) // out_dim : -(-((i + 1) * in_dim) // out_dim)].mean(axis=-1, keepdims=True)
        for i in range(out_dim)
    ]
    return mx.concatenate(bins, axis=-1)


class WNConv1d(nn.Module):
    """Conv1d over ``(N, L, C)``. Weight norm is folded at load, so this holds a plain weight."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        stride: int = 1,
        padding: int = 0,
        dilation: int = 1,
        bias: bool = True,
    ):
        super().__init__()
        self.stride, self.padding, self.dilation = stride, padding, dilation
        scale = 1.0 / math.sqrt(in_channels * kernel_size)
        self.weight = mx.random.uniform(-scale, scale, (out_channels, kernel_size, in_channels))
        if bias:
            self.bias = mx.zeros((out_channels,))

    def __call__(self, x: mx.array) -> mx.array:
        out = mx.conv1d(x, self.weight, stride=self.stride, padding=self.padding, dilation=self.dilation)
        if "bias" in self:
            out = out + self.bias
        return out


class WNConvTranspose1d(nn.Module):
    """Transposed Conv1d over ``(N, L, C)``, weight ``(C_out, kL, C_in)``."""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, stride: int = 1, padding: int = 0):
        super().__init__()
        self.stride, self.padding = stride, padding
        scale = 1.0 / math.sqrt(in_channels * kernel_size)
        self.weight = mx.random.uniform(-scale, scale, (out_channels, kernel_size, in_channels))
        self.bias = mx.zeros((out_channels,))

    def __call__(self, x: mx.array) -> mx.array:
        out = mx.conv_transpose1d(x, self.weight, stride=self.stride, padding=self.padding)
        return out + self.bias


class Snake1d(nn.Module):
    """``x + (alpha + 1e-9)^-1 * sin(alpha * x)^2``, per-channel learnable alpha. DAC encoder."""

    def __init__(self, channels: int):
        super().__init__()
        self.alpha = mx.ones((1, 1, channels))

    def __call__(self, x: mx.array) -> mx.array:
        return x + mx.reciprocal(self.alpha + 1e-9) * mx.square(mx.sin(self.alpha * x))


class SnakeBeta(nn.Module):
    """``x + (exp(beta) + 1e-9)^-1 * sin(exp(alpha) * x)^2``.

    The BigVGAN activation: separate frequency (``alpha``) and magnitude (``beta``) parameters, both
    stored in log space as ``(channels,)`` vectors.
    """

    def __init__(self, channels: int):
        super().__init__()
        self.alpha = mx.zeros((channels,))
        self.beta = mx.zeros((channels,))

    def __call__(self, x: mx.array) -> mx.array:
        alpha = mx.exp(self.alpha).reshape(1, 1, -1)
        beta = mx.exp(self.beta).reshape(1, 1, -1)
        return x + mx.reciprocal(beta + 1e-9) * mx.square(mx.sin(alpha * x))


class LowPassFilter1d(nn.Module):
    """Depthwise Kaiser-sinc low-pass filter with a stride: the anti-aliased downsampler."""

    def __init__(self, cutoff: float, half_width: float, stride: int, kernel_size: int):
        super().__init__()
        even = kernel_size % 2 == 0
        self.pad_left = kernel_size // 2 - int(even)
        self.pad_right = kernel_size // 2
        self.stride = stride
        # Underscore-prefixed so MLX keeps this computed constant out of the parameter tree.
        self._filter = kaiser_sinc_filter1d(cutoff, half_width, kernel_size)

    def __call__(self, x: mx.array) -> mx.array:
        channels = x.shape[-1]
        x = mx.pad(x, ((0, 0), (self.pad_left, self.pad_right), (0, 0)), mode="edge")
        w = _depthwise(self._filter, channels).astype(x.dtype)
        return mx.conv1d(x, w, stride=self.stride, groups=channels)


class UpSample1d(nn.Module):
    """Anti-aliased ``ratio``x upsampler (transposed depthwise Kaiser-sinc convolution)."""

    def __init__(self, ratio: int, kernel_size: int):
        super().__init__()
        self.ratio = ratio
        self.stride = ratio
        self.pad = kernel_size // ratio - 1
        self.pad_left = self.pad * self.stride + (kernel_size - self.stride) // 2
        self.pad_right = self.pad * self.stride + (kernel_size - self.stride + 1) // 2
        self._filter = kaiser_sinc_filter1d(
            cutoff=0.5 / ratio, half_width=0.6 / ratio, kernel_size=kernel_size
        )

    def __call__(self, x: mx.array) -> mx.array:
        channels = x.shape[-1]
        x = mx.pad(x, ((0, 0), (self.pad, self.pad), (0, 0)), mode="edge")
        w = _depthwise(self._filter, channels).astype(x.dtype)
        x = self.ratio * mx.conv_transpose1d(x, w, stride=self.stride, groups=channels)
        return x[:, self.pad_left : x.shape[1] - self.pad_right, :]


class DownSample1d(nn.Module):
    def __init__(self, ratio: int, kernel_size: int):
        super().__init__()
        self.lowpass = LowPassFilter1d(
            cutoff=0.5 / ratio, half_width=0.6 / ratio, stride=ratio, kernel_size=kernel_size
        )

    def __call__(self, x: mx.array) -> mx.array:
        return self.lowpass(x)


class Activation1d(nn.Module):
    """Upsample -> activation -> downsample: the alias-free activation wrapper used by BigVGAN."""

    def __init__(self, activation: nn.Module, ratio: int = 2, kernel_size: int = 12):
        super().__init__()
        self.act = activation
        self.upsample = UpSample1d(ratio, kernel_size)
        self.downsample = DownSample1d(ratio, kernel_size)

    def __call__(self, x: mx.array) -> mx.array:
        return self.downsample(self.act(self.upsample(x)))


class ResidualUnit(nn.Module):
    """DAC residual unit: Snake -> dilated Conv1d(k=7) -> Snake -> Conv1d(k=1), with a shortcut that
    is centre-cropped when the dilated convolution shrinks the time axis."""

    def __init__(self, dim: int, dilation: int):
        super().__init__()
        self.block = [
            Snake1d(dim),
            WNConv1d(dim, dim, 7, dilation=dilation, padding=((7 - 1) * dilation) // 2),
            Snake1d(dim),
            WNConv1d(dim, dim, 1),
        ]

    def __call__(self, x: mx.array) -> mx.array:
        residual = x
        for layer in self.block:
            residual = layer(residual)
        pad = (x.shape[1] - residual.shape[1]) // 2
        if pad > 0:
            x = x[:, pad : x.shape[1] - pad, :]
        return x + residual


class EncoderBlock(nn.Module):
    """Three residual units at dilations 1/3/9, then a strided channel-doubling convolution."""

    def __init__(self, dim: int, stride: int):
        super().__init__()
        self.block = [
            ResidualUnit(dim // 2, dilation=1),
            ResidualUnit(dim // 2, dilation=3),
            ResidualUnit(dim // 2, dilation=9),
            Snake1d(dim // 2),
            WNConv1d(dim // 2, dim, 2 * stride, stride=stride, padding=math.ceil(stride / 2)),
        ]

    def __call__(self, x: mx.array) -> mx.array:
        for layer in self.block:
            x = layer(x)
        return x


class AudioEncoder(nn.Module):
    """DAC waveform encoder: ``(B, samples, 1) -> (B, samples / 800, latent_dim)``."""

    def __init__(self, d_model: int, strides: tuple[int, ...], d_latent: int):
        super().__init__()
        block: list[nn.Module] = [WNConv1d(1, d_model, 7, padding=3)]
        for stride in strides:
            d_model *= 2
            block.append(EncoderBlock(d_model, stride=stride))
        block += [Snake1d(d_model), WNConv1d(d_model, d_latent, 3, padding=1)]
        self.block = block

    def __call__(self, x: mx.array) -> mx.array:
        for layer in self.block:
            x = layer(x)
        return x


class GeGluMlp(nn.Module):
    """Pre-norm GeGLU MLP used inside the attention projection block."""

    def __init__(self, in_features: int, hidden_features: int):
        super().__init__()
        self.norm = nn.LayerNorm(in_features)
        self.w0 = nn.Linear(in_features, hidden_features)
        self.w1 = nn.Linear(in_features, hidden_features)
        self.w2 = nn.Linear(hidden_features, in_features)

    def __call__(self, x: mx.array) -> mx.array:
        x = self.norm(x)
        return self.w2(nn.gelu_approx(self.w0(x)) * self.w1(x))


class CausalAttention(nn.Module):
    """Causal self-attention that narrows the feature width from ``in_dim`` to ``out_dim``.

    QKV is a single bias-less projection; query and value biases are separate parameters and the key
    bias is a frozen zero buffer, exactly as stored in the checkpoint. Heads are ``in_dim //
    num_heads`` wide; instead of being concatenated they are **mean-pooled away**, and the remaining
    head dimension is adaptively average-pooled down to ``out_dim``.
    """

    def __init__(self, in_dim: int, out_dim: int, num_heads: int):
        super().__init__()
        self.out_dim = out_dim
        self.num_heads = num_heads
        self.head_dim = in_dim // num_heads
        self.qkv = nn.Linear(in_dim, in_dim * 3, bias=False)
        self.q_bias = mx.zeros((in_dim,))
        self.v_bias = mx.zeros((in_dim,))
        self.zero_k_bias = mx.zeros((in_dim,))
        self.proj = nn.Linear(out_dim, out_dim)

    def __call__(self, x: mx.array) -> mx.array:
        b, s, _ = x.shape
        bias = mx.concatenate([self.q_bias, self.zero_k_bias, self.v_bias])
        qkv = self.qkv(x) + bias
        qkv = qkv.reshape(b, s, 3, self.num_heads, self.head_dim)
        q, k, v = qkv[:, :, 0], qkv[:, :, 1], qkv[:, :, 2]

        q = q.transpose(0, 2, 1, 3)
        k = k.transpose(0, 2, 1, 3)
        v = v.transpose(0, 2, 1, 3)
        out = mx.fast.scaled_dot_product_attention(
            q, k, v, scale=self.head_dim**-0.5, mask="causal"
        )
        out = out.transpose(0, 2, 1, 3)  # (B, S, heads, head_dim)

        out = mx.mean(out, axis=2)  # heads are mean-pooled away, not concatenated
        out = adaptive_avg_pool_last(out, self.out_dim)
        return self.proj(out)


class AttnProjection(nn.Module):
    """``pre_block``: residual causal-attention + GeGLU block rewiring ``latent_dim -> latent_channels``."""

    def __init__(self, in_dim: int, out_dim: int, num_heads: int, mlp_ratio: int = 2):
        super().__init__()
        self.norm1 = nn.LayerNorm(in_dim)
        self.attn = CausalAttention(in_dim, out_dim, num_heads)
        self.proj = nn.Linear(in_dim, out_dim)
        self.norm3 = nn.LayerNorm(in_dim)
        self.norm2 = nn.LayerNorm(out_dim)
        self.mlp = GeGluMlp(out_dim, out_dim * mlp_ratio)

    def __call__(self, x: mx.array) -> mx.array:
        x = self.proj(self.norm3(x)) + self.attn(self.norm1(x))
        return x + self.mlp(self.norm2(x))


class AMPBlock(nn.Module):
    """BigVGAN anti-aliased multi-periodicity block.

    Each dilation contributes a ``(dilated conv, dilation-1 conv)`` pair, and every convolution is
    preceded by its own alias-free SnakeBeta activation.
    """

    def __init__(self, channels: int, kernel_size: int, dilation: tuple[int, ...]):
        super().__init__()
        self.convs1 = [
            WNConv1d(channels, channels, kernel_size, dilation=d, padding=(kernel_size * d - d) // 2)
            for d in dilation
        ]
        self.convs2 = [
            WNConv1d(channels, channels, kernel_size, dilation=1, padding=(kernel_size - 1) // 2)
            for _ in dilation
        ]
        self.activations = [Activation1d(SnakeBeta(channels)) for _ in range(2 * len(dilation))]

    def __call__(self, x: mx.array) -> mx.array:
        acts1, acts2 = self.activations[::2], self.activations[1::2]
        for conv1, conv2, act1, act2 in zip(self.convs1, self.convs2, acts1, acts2):
            residual = conv1(act1(x))
            residual = conv2(act2(residual))
            x = residual + x
        return x


class BigVGANDecoder(nn.Module):
    """``(B, num_frames, latent_dim) -> (B, num_frames * 800, 1)``."""

    def __init__(
        self,
        in_channels: int,
        upsample_initial_channel: int,
        upsample_rates: tuple[int, ...],
        upsample_kernel_sizes: tuple[int, ...],
        resblock_kernel_sizes: tuple[int, ...],
        resblock_dilation_sizes: tuple[tuple[int, ...], ...],
    ):
        super().__init__()
        self.num_kernels = len(resblock_kernel_sizes)
        self.num_upsamples = len(upsample_rates)

        self.conv_pre = WNConv1d(in_channels, upsample_initial_channel, 7, 1, padding=3)
        # Each upsampler is wrapped in a one-element list in the checkpoint (`ups.<i>.0`); the extra
        # nesting is kept so the state dict stays a passthrough.
        self.ups = [
            [
                WNConvTranspose1d(
                    upsample_initial_channel // (2**i),
                    upsample_initial_channel // (2 ** (i + 1)),
                    kernel,
                    rate,
                    padding=(kernel - rate) // 2,
                )
            ]
            for i, (rate, kernel) in enumerate(zip(upsample_rates, upsample_kernel_sizes))
        ]

        self.resblocks = []
        channels = upsample_initial_channel
        for i in range(self.num_upsamples):
            channels = upsample_initial_channel // (2 ** (i + 1))
            for kernel, dilation in zip(resblock_kernel_sizes, resblock_dilation_sizes):
                self.resblocks.append(AMPBlock(channels, kernel, tuple(dilation)))

        self.activation_post = Activation1d(SnakeBeta(channels))
        self.conv_post = WNConv1d(channels, 1, 7, 1, padding=3, bias=False)

    def __call__(self, x: mx.array) -> mx.array:
        x = self.conv_pre(x)
        for i in range(self.num_upsamples):
            x = self.ups[i][0](x)
            residual = None
            for j in range(self.num_kernels):
                block = self.resblocks[i * self.num_kernels + j](x)
                residual = block if residual is None else residual + block
            x = residual / self.num_kernels
        x = self.conv_post(self.activation_post(x))
        return mx.clip(x, -1.0, 1.0)


class AudioVAE(nn.Module):
    """The MiniMax-H3 audio autoencoder. Mono; stereo is carried as two batch items."""

    def __init__(self, config: AudioVAEConfig):
        super().__init__()
        self.config = config
        if math.prod(config.decoder_rates) != config.hop_length:
            raise ValueError(
                f"`decoder_rates` must upsample by the encoder hop length {config.hop_length}, "
                f"got {math.prod(config.decoder_rates)}."
            )
        self.encoder = AudioEncoder(config.encoder_dim, config.encoder_rates, config.latent_dim)
        self.pre_block = AttnProjection(
            config.latent_dim, config.latent_channels, config.num_attention_heads
        )
        self.mean_proj = WNConv1d(config.latent_channels, config.latent_channels, 1)
        self.logs_proj = WNConv1d(config.latent_channels, config.latent_channels, 1)
        self.dec_in_proj = WNConv1d(config.latent_channels, config.latent_dim, 1)
        self.decoder = BigVGANDecoder(
            in_channels=config.latent_dim,
            upsample_initial_channel=config.decoder_dim,
            upsample_rates=config.decoder_rates,
            upsample_kernel_sizes=config.decoder_kernel_sizes,
            resblock_kernel_sizes=config.resblock_kernel_sizes,
            resblock_dilation_sizes=config.resblock_dilation_sizes,
        )

    def encode(self, sample: mx.array) -> tuple[mx.array, mx.array]:
        """Encode ``(B, 1, samples)`` into the posterior ``(mean, logs)`` over ``(B, 32, samples/800)``.

        The waveform is right-padded to a multiple of the 800-sample hop first. MiniMax-H3 always
        consumes the posterior **mean** — ``logs_proj`` is never evaluated by the reference pipeline.
        """
        if sample.ndim != 3 or sample.shape[1] != 1:
            raise ValueError(f"`sample` must have shape (batch, 1, samples), got {sample.shape}.")
        hop = self.config.hop_length
        x = sample.transpose(0, 2, 1)  # -> (B, samples, 1)
        right_pad = math.ceil(x.shape[1] / hop) * hop - x.shape[1]
        if right_pad > 0:
            x = mx.pad(x, ((0, 0), (0, right_pad), (0, 0)))

        h = self.pre_block(self.encoder(x))
        mean, logs = self.mean_proj(h), self.logs_proj(h)
        return mean.transpose(0, 2, 1), logs.transpose(0, 2, 1)

    def decode(self, latents: mx.array) -> mx.array:
        """Decode ``(B, 32, num_frames)`` latents into ``(B, 1, num_frames * 800)``, clamped to [-1, 1]."""
        if latents.ndim != 3:
            raise ValueError(
                f"`latents` must have shape (batch, latent_channels, num_frames), got {latents.shape}."
            )
        x = latents.transpose(0, 2, 1)
        out = self.decoder(self.dec_in_proj(x))
        return out.transpose(0, 2, 1)
