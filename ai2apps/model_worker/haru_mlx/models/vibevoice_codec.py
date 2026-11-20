"""VibeVoice acoustic codec: 24 kHz audio <-> 64-dim latents at 7.5 Hz.

Both directions are causal convolution stacks. Every layer takes and returns
its left context explicitly, so the same code encodes a whole clip (zero
initial state) or one 3200-sample frame at a time with identical results.

The layers work on one stream, channel-last ``[T, C]``, laid out so that a
live frame is a short list of matmuls:

- a dense convolution is one matmul over its input windows: a strided one
  (kernel = 2 * stride) reads two adjacent hops, the stride-1 stem and head
  read their 7 taps side by side;
- a transposed convolution (kernel = 2 * stride) is one matmul and an
  overlap-add with the carried tail;
- the depthwise mixer of a block (causal 7-tap convolution, bias, layer scale,
  residual and next state) is one Metal kernel on Apple GPUs, accumulating in
  float32, and the same arithmetic with array operations elsewhere;
- encoding and decoding a frame are compiled functions of fixed shape.
"""

from __future__ import annotations

import mlx.core as mx
import mlx.nn as nn

from ..config import CodecConfig

State = list[mx.array]

_MIXER_KERNEL = 7

_MIXER_SOURCE = """
    uint c = thread_position_in_grid.x;
    uint r = thread_position_in_grid.y;
    if (c >= C) return;
    if (r < T) {
        float acc = float(bias[c]);
        for (int k = 0; k < K; ++k) {
            int i = int(r) + k - (K - 1);
            float v = i < 0 ? float(state[(i + K - 1) * C + c]) : float(n[i * C + c]);
            acc += float(w[c * K + k]) * v;
        }
        out[r * C + c] = static_cast<OutT>(float(x[r * C + c]) + float(gamma[c]) * acc);
    } else {
        int src = int(r);  // row of concat(state, n) that becomes row r - T of the next state
        new_state[(r - T) * C + c] = src < K - 1 ? state[src * C + c] : n[(src - (K - 1)) * C + c];
    }
"""

_mixer_kernel = None


def _mixer_metal(x, n, state, weight, bias, gamma):
    global _mixer_kernel
    if _mixer_kernel is None:
        _mixer_kernel = mx.fast.metal_kernel(
            name="causal_depthwise_mixer",
            input_names=["x", "n", "state", "w", "bias", "gamma"],
            output_names=["out", "new_state"],
            source=_MIXER_SOURCE,
        )
    steps, channels = x.shape
    kernel = weight.shape[1]
    return _mixer_kernel(
        inputs=[x, n, state, weight, bias, gamma],
        template=[("OutT", x.dtype), ("T", steps), ("C", channels), ("K", kernel)],
        grid=(channels, steps + kernel - 1, 1),
        threadgroup=(min(channels, 256), 1, 1),
        output_shapes=[(steps, channels), (kernel - 1, channels)],
        output_dtypes=[x.dtype, state.dtype],
    )


def _mixer_arrays(x, n, state, weight, bias, gamma):
    steps, kernel = x.shape[0], weight.shape[1]
    context = mx.concatenate([state, n], axis=0)
    taps = context.astype(mx.float32)
    weight = weight.astype(mx.float32)
    acc = bias.astype(mx.float32)
    for k in range(kernel):
        acc = acc + taps[k : k + steps] * weight[:, k]
    out = x.astype(mx.float32) + gamma.astype(mx.float32) * acc
    return out.astype(x.dtype), context[steps:]


def depthwise_mixer(
    x: mx.array, n: mx.array, state: mx.array, weight: mx.array, bias: mx.array, gamma: mx.array
) -> tuple[mx.array, mx.array]:
    """``x + gamma * (depthwise_conv(concat(state, n)) + bias)`` and the next state.

    ``x [T, C]`` is the block input, ``n`` its normalized copy (the convolution
    input), ``state [K - 1, C]`` the previous convolution inputs and
    ``weight [C, K]`` one filter per channel.
    """
    if mx.metal.is_available() and mx.default_device() == mx.gpu:
        return _mixer_metal(x, n, state, weight, bias, gamma)
    return _mixer_arrays(x, n, state, weight, bias, gamma)


class CausalConv1d(nn.Module):
    """Dense convolution over ``[T, C]`` whose left padding is an explicit state.

    ``weight [out, kernel * in]`` holds the taps side by side. A strided
    convolution must have ``kernel = 2 * stride``.
    """

    def __init__(self, in_channels: int, out_channels: int, kernel: int, stride: int = 1):
        super().__init__()
        if stride > 1 and kernel != 2 * stride:
            raise ValueError("a strided convolution needs kernel = 2 * stride")
        self.weight = mx.zeros((out_channels, kernel * in_channels))
        self.bias = mx.zeros((out_channels,))
        self.in_channels, self.kernel, self.stride = in_channels, kernel, stride
        self.context = kernel - stride

    def state_shape(self) -> tuple[int, int]:
        return (self.context, self.in_channels)

    def __call__(self, x: mx.array, state: mx.array) -> tuple[mx.array, mx.array]:
        tail = x.shape[0] % self.stride
        if tail:  # final partial hop of a whole-clip encode
            x = mx.pad(x, [(0, self.stride - tail), (0, 0)])
        context = mx.concatenate([state, x], axis=0)
        if self.stride == 1:
            steps = x.shape[0]
            windows = mx.concatenate([context[k : k + steps] for k in range(self.kernel)], axis=1)
        else:
            hops = context.reshape(-1, self.stride * self.in_channels)
            windows = mx.concatenate([hops[:-1], hops[1:]], axis=1)
        return mx.addmm(self.bias, windows, self.weight.T), context[context.shape[0] - self.context :]


class CausalConvTranspose1d(nn.Module):
    """Transposed convolution with kernel = 2 * stride; the state is the overlap tail.

    ``weight [out * kernel, in]`` maps one input position to its ``kernel``
    output samples per channel.
    """

    def __init__(self, in_channels: int, out_channels: int, stride: int):
        super().__init__()
        self.weight = mx.zeros((out_channels * 2 * stride, in_channels))
        self.bias = mx.zeros((out_channels,))
        self.out_channels, self.stride = out_channels, stride

    def state_shape(self) -> tuple[int, int]:
        return (self.stride, self.out_channels)

    def __call__(self, x: mx.array, state: mx.array) -> tuple[mx.array, mx.array]:
        y = (x @ self.weight.T).reshape(-1, self.out_channels, 2, self.stride)
        y = y.transpose(0, 2, 3, 1)  # [T, half, stride, out]
        first, second = y[:, 0], y[:, 1]
        overlap = mx.concatenate([state[None], second[:-1]], axis=0)
        out = (first + overlap).reshape(-1, self.out_channels) + self.bias
        return out, second[-1]


class _Gain(nn.Module):
    def __init__(self, dims: int):
        super().__init__()
        self.weight = mx.ones((dims,))


class _DepthwiseFilter(nn.Module):
    def __init__(self, dims: int):
        super().__init__()
        self.weight = mx.zeros((dims, _MIXER_KERNEL))
        self.bias = mx.zeros((dims,))


class Block(nn.Module):
    """Depthwise causal conv mixer and an MLP, each with a scaled residual."""

    def __init__(self, dim: int, eps: float):
        super().__init__()
        self.norm = _Gain(dim)
        self.conv = _DepthwiseFilter(dim)
        self.gamma = mx.ones((dim,))
        self.ffn_norm = _Gain(dim)
        self.fc1 = nn.Linear(dim, 4 * dim)
        self.fc2 = nn.Linear(4 * dim, dim)
        self.ffn_gamma = mx.ones((dim,))
        self.dim, self.eps = dim, eps

    def state_shape(self) -> tuple[int, int]:
        return (_MIXER_KERNEL - 1, self.dim)

    def __call__(self, x: mx.array, state: mx.array) -> tuple[mx.array, mx.array]:
        n = mx.fast.rms_norm(x, self.norm.weight, self.eps)
        x, state = depthwise_mixer(x, n, state, self.conv.weight, self.conv.bias, self.gamma)
        h = mx.fast.rms_norm(x, self.ffn_norm.weight, self.eps)
        h = self.fc2(nn.gelu(self.fc1(h)))
        return x + self.ffn_gamma * h, state


def _run(layers: list[nn.Module], x: mx.array, state: State) -> tuple[mx.array, State]:
    new_state = []
    for layer, s in zip(layers, state, strict=True):
        x, s = layer(x, s)
        new_state.append(s)
    return x, new_state


class Encoder(nn.Module):
    """``[T, 1]`` audio -> ``[T / 3200, latent]`` latent means."""

    def __init__(self, config: CodecConfig):
        super().__init__()
        c = config.base_channels
        strides = config.ratios[::-1]
        self.stem = CausalConv1d(1, c, 7)
        self.down = [CausalConv1d(c << i, c << (i + 1), 2 * s, stride=s) for i, s in enumerate(strides)]
        self.stages = [
            [Block(c << i, config.norm_eps) for _ in range(depth)] for i, depth in enumerate(config.encoder_depths)
        ]
        self.head = CausalConv1d(c << len(strides), config.latent_dim, 7)

    def sequence(self) -> list[nn.Module]:
        layers: list[nn.Module] = []
        for i, stage in enumerate(self.stages):
            layers.append(self.stem if i == 0 else self.down[i - 1])
            layers.extend(stage)
        return [*layers, self.head]


class Decoder(nn.Module):
    """``[T, latent]`` latents -> ``[T * 3200, 1]`` audio."""

    def __init__(self, config: CodecConfig):
        super().__init__()
        n = len(config.ratios)
        c = config.base_channels
        self.stem = CausalConv1d(config.latent_dim, c << n, 7)
        self.up = [CausalConvTranspose1d(c << (n - i), c << (n - i - 1), s) for i, s in enumerate(config.ratios)]
        self.stages = [
            [Block(c << (n - i), config.norm_eps) for _ in range(depth)]
            for i, depth in enumerate(config.decoder_depths)
        ]
        self.head = CausalConv1d(c, 1, 7)

    def sequence(self) -> list[nn.Module]:
        layers: list[nn.Module] = []
        for i, stage in enumerate(self.stages):
            layers.append(self.stem if i == 0 else self.up[i - 1])
            layers.extend(stage)
        return [*layers, self.head]


class VibeVoiceCodec(nn.Module):
    """Encoder and decoder for a single audio stream (no batch dimension inside)."""

    def __init__(self, config: CodecConfig):
        super().__init__()
        self.config = config
        self.encoder = Encoder(config)
        self.decoder = Decoder(config)
        # The encoder is split at its last downsampling: everything before it
        # (the front) can run on every `front_hop` samples while a frame's
        # audio is still arriving; the rest (the back) runs on whole frames.
        self.front_layers = len(self.encoder.sequence()) - 2 - len(self.encoder.stages[-1])
        self.frame_hop = config.frame_samples
        self.front_hop = self.frame_hop // self.encoder.down[-1].stride
        self._front = mx.compile(self._run_front)
        self._back = mx.compile(self._run_back)
        self._decode = mx.compile(self._run_decoder)

    @property
    def dtype(self) -> mx.Dtype:
        return self.encoder.head.weight.dtype

    # ------------------------------------------------------------ layers

    def _run_front(self, audio: mx.array, *state: mx.array):
        x = audio.astype(self.dtype).reshape(-1, 1)
        x, new_state = _run(self.encoder.sequence()[: self.front_layers], x, list(state))
        return (x, *new_state)

    def _run_back(self, x: mx.array, *state: mx.array):
        mean, new_state = _run(self.encoder.sequence()[self.front_layers :], x, list(state))
        return (mean.astype(mx.float32), *new_state)

    def _run_decoder(self, latents: mx.array, *state: mx.array):
        x, new_state = _run(self.decoder.sequence(), latents.astype(self.dtype), list(state))
        return (x.reshape(-1).astype(mx.float32), *new_state)

    def init_state(self) -> tuple[State, State]:
        """Zero left context for the encoder and the decoder layers."""
        dtype = self.dtype
        return (
            [mx.zeros(layer.state_shape(), dtype=dtype) for layer in self.encoder.sequence()],
            [mx.zeros(layer.state_shape(), dtype=dtype) for layer in self.decoder.sequence()],
        )

    # --------------------------------------------------------- whole clips

    def sample(self, mean: mx.array, key: mx.array | None = None) -> mx.array:
        """Draw latents around ``mean [B, T, D]`` (one noise scale per batch row)."""
        scale_key, noise_key = (None, None) if key is None else mx.random.split(key)
        scale = mx.random.normal((mean.shape[0], 1, 1), key=scale_key)
        noise = mx.random.normal(mean.shape, key=noise_key)
        return mean.astype(mx.float32) + scale * (self.config.latent_std / 0.8) * noise

    def encode(self, audio: mx.array) -> mx.array:
        """Whole clip ``[T]`` -> latent means ``[1, ceil(T / 3200), D]`` in float32."""
        x = audio.astype(self.dtype).reshape(-1, 1)
        mean, _ = _run(self.encoder.sequence(), x, self.init_state()[0])
        return mean.astype(mx.float32)[None]

    def decode(self, latents: mx.array) -> mx.array:
        """Whole sequence ``[1, T, D]`` -> audio ``[1, T * 3200]`` in float32."""
        x = latents.astype(self.dtype).reshape(-1, latents.shape[-1])
        audio, _ = _run(self.decoder.sequence(), x, self.init_state()[1])
        return audio.reshape(1, -1).astype(mx.float32)


class CodecStream:
    """Frame-by-frame encode and decode of one conversation.

    ``encode`` / ``decode`` take whole frames. A live client can instead
    ``feed`` microphone audio of any length as it arrives, which runs most of
    the encoder right away, and ``pop`` each frame once it is complete.
    """

    def __init__(self, codec: VibeVoiceCodec):
        self.codec = codec
        self.reset()

    def reset(self) -> None:
        self.encoder_state, self.decoder_state = self.codec.init_state()
        self._pending = mx.zeros((0,), dtype=mx.float32)  # audio short of one front hop
        self._front_out: list[mx.array] = []  # encoder-front output not yet popped
        self._front_steps = 0

    @property
    def _steps_per_frame(self) -> int:
        return self.codec.frame_hop // self.codec.front_hop

    def feed(self, audio: mx.array) -> None:
        """Run the encoder front over every whole front hop of new audio ``[n]``."""
        codec, split = self.codec, self.codec.front_layers
        audio = mx.concatenate([self._pending, audio.astype(mx.float32).reshape(-1)])
        hops = audio.shape[0] // codec.front_hop
        start = 0
        # Chunks of a frame, half, quarter, ... keep the number of compiled shapes small.
        size = self._steps_per_frame
        while hops:
            while size > hops:
                size //= 2
            end = start + size * codec.front_hop
            out, *self.encoder_state[:split] = codec._front(audio[start:end], *self.encoder_state[:split])
            self._front_out.append(out)
            self._front_steps += out.shape[0]
            start = end
            hops -= size
        self._pending = audio[start:]

    @property
    def frames_ready(self) -> int:
        """Whole frames fed and not yet popped."""
        return self._front_steps // self._steps_per_frame

    def pop(self) -> mx.array:
        """Finish encoding the oldest complete frame -> latent mean ``[1, 1, D]``."""
        steps, split = self._steps_per_frame, self.codec.front_layers
        if self._front_steps < steps:
            raise RuntimeError("no complete frame has been fed")
        x = mx.concatenate(self._front_out) if len(self._front_out) > 1 else self._front_out[0]
        rest = x[steps:]
        self._front_out = [rest] if rest.shape[0] else []
        self._front_steps -= steps
        mean, *self.encoder_state[split:] = self.codec._back(x[:steps], *self.encoder_state[split:])
        return mean[None]

    def encode(self, audio: mx.array) -> mx.array:
        """``[1, n * 3200]`` new audio -> latent means ``[1, n, D]``."""
        self.feed(audio)
        return mx.concatenate([self.pop() for _ in range(self.frames_ready)], axis=1)

    def decode(self, latents: mx.array) -> mx.array:
        """``[1, n, D]`` new latents -> audio ``[1, n * 3200]``."""
        x = latents.reshape(-1, latents.shape[-1])
        audio, *self.decoder_state = self.codec._decode(x, *self.decoder_state)
        return audio[None]

    def arrays(self) -> list[mx.array]:
        """Every array of the stream's state (to evaluate once per frame)."""
        return [*self.encoder_state, *self.decoder_state, self._pending, *self._front_out]
