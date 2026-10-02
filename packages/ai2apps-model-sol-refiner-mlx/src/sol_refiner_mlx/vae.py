"""LTX-2.3 convolutional video VAE, native MLX, original checkpoint names."""

import mlx.core as mx
import mlx.nn as nn

from .weights import conv_layout, load_component


def pixel_norm(x):
    return x / mx.sqrt(mx.mean(x * x, axis=-1, keepdims=True) + 1e-8)


def conv(x, w, name, causal=True):
    weight = w[name + ".weight"]
    k = weight.shape[1]
    left = k - 1 if causal else (k - 1) // 2
    right = 0 if causal else (k - 1) // 2
    if left:
        x = mx.concatenate((mx.repeat(x[:, :1], left, axis=1), x), axis=1)
    if right:
        x = mx.concatenate((x, mx.repeat(x[:, -1:], right, axis=1)), axis=1)
    x = mx.conv3d(x, weight, padding=(0, weight.shape[2] // 2, weight.shape[3] // 2))
    return x + w[name + ".bias"]


def conv2d_chunked(x, w, name, causal=True, chunk_frames=8):
    """Temporal taps become input channels; chunks bound temporary storage.

    This is algebraically equivalent to conv3d, but changes reduction order.
    Temporal context is taken from the whole tensor, so chunk edges do not pad.
    """
    if chunk_frames < 1:
        raise ValueError("chunk_frames must be positive")
    weight = w[name + ".weight"]
    k = weight.shape[1]
    left = k - 1 if causal else (k - 1) // 2
    right = 0 if causal else (k - 1) // 2
    if left:
        x = mx.concatenate((mx.repeat(x[:, :1], left, axis=1), x), axis=1)
    if right:
        x = mx.concatenate((x, mx.repeat(x[:, -1:], right, axis=1)), axis=1)
    b, t, h, width, c = x.shape
    count = t - k + 1
    key = name + ".weight2d"
    if key not in w:
        w[key] = weight.transpose(0, 2, 3, 1, 4).reshape(
            weight.shape[0], weight.shape[2], weight.shape[3], -1
        )
    chunks = []
    for lo in range(0, count, chunk_frames):
        length = min(chunk_frames, count - lo)
        window = mx.concatenate(
            [x[:, lo + i : lo + i + length] for i in range(k)], axis=-1
        )
        window = window.reshape(b * length, h, width, k * c)
        y = mx.conv2d(
            window, w[key], padding=(weight.shape[2] // 2, weight.shape[3] // 2)
        )
        y = y.reshape(b, length, y.shape[1], y.shape[2], y.shape[3])
        mx.eval(y)
        chunks.append(y)
    return mx.concatenate(chunks, axis=1) + w[name + ".bias"]


def space_to_depth(x, stride):
    b, t, h, w, c = x.shape
    st, sh, sw = stride
    return (
        x.reshape(b, t // st, st, h // sh, sh, w // sw, sw, c)
        .transpose(0, 1, 3, 5, 7, 2, 4, 6)
        .reshape(b, t // st, h // sh, w // sw, -1)
    )


def depth_to_space(x, stride):
    b, t, h, w, c = x.shape
    st, sh, sw = stride
    return (
        x.reshape(b, t, h, w, c // (st * sh * sw), st, sh, sw)
        .transpose(0, 1, 5, 2, 6, 3, 7, 4)
        .reshape(b, t * st, h * sh, w * sw, -1)
    )


class VideoVAE:
    def __init__(self, root, mode, conv_backend="conv3d", chunk_frames=8):
        if mode not in ("encoder", "decoder"):
            raise ValueError(mode)
        if conv_backend not in ("conv3d", "conv2d") or chunk_frames < 1:
            raise ValueError("Invalid convolution backend or chunk size")
        self.conv_backend = conv_backend
        self.chunk_frames = chunk_frames
        self.mode = mode
        self.w = {
            k: conv_layout(v)
            for k, v in load_component(
                root,
                "vae",
                lambda k: (
                    k.startswith(mode + ".") or k in ("latents_mean", "latents_std")
                ),
            ).items()
        }

    def conv(self, x, w, name, causal=True):
        if self.conv_backend == "conv2d":
            return conv2d_chunked(x, w, name, causal, self.chunk_frames)
        return conv(x, w, name, causal)

    def resnets(self, x, prefix, causal):
        i = 0
        while prefix + f".resnets.{i}.conv1.conv.weight" in self.w:
            p = prefix + f".resnets.{i}"
            y = self.conv(nn.silu(pixel_norm(x)), self.w, p + ".conv1.conv", causal)
            y = self.conv(nn.silu(pixel_norm(y)), self.w, p + ".conv2.conv", causal)
            x = x + y
            i += 1
            mx.eval(x)
        if i == 0:
            raise ValueError("Missing resnets: " + prefix)
        return x

    def stats(self):
        return [
            self.w[k].reshape(1, -1, 1, 1, 1) for k in ("latents_mean", "latents_std")
        ]

    def encode(self, pixels):
        b, c, t, h, w = pixels.shape
        if h % 32 or w % 32 or t % 8 != 1:
            raise ValueError("VAE input requires H,W multiples of 32 and 8k+1 frames")
        x = pixels.transpose(0, 2, 3, 4, 1)
        x = (
            x.reshape(b, t, h // 4, 4, w // 4, 4, c)
            .transpose(0, 1, 2, 4, 6, 5, 3)
            .reshape(b, t, h // 4, w // 4, 48)
        )
        x = self.conv(x, self.w, "encoder.conv_in.conv")
        for i, stride in enumerate(((1, 2, 2), (2, 1, 1), (2, 2, 2), (2, 2, 2))):
            p = f"encoder.down_blocks.{i}"
            x = self.resnets(x, p, True)
            if stride[0] > 1:
                x = mx.concatenate((x[:, :1], x), axis=1)
            skip = space_to_depth(x, stride)
            y = space_to_depth(
                self.conv(x, self.w, p + ".downsamplers.0.conv.conv"), stride
            )
            group = skip.shape[-1] // y.shape[-1]
            x = y + skip.reshape(*skip.shape[:-1], y.shape[-1], group).mean(axis=-1)
            mx.eval(x)
        x = self.resnets(x, "encoder.mid_block", True)
        x = self.conv(nn.silu(pixel_norm(x)), self.w, "encoder.conv_out.conv")[
            ..., :128
        ]
        return x.transpose(0, 4, 1, 2, 3)

    def decode(self, raw):
        x = self.conv(
            raw.transpose(0, 2, 3, 4, 1), self.w, "decoder.conv_in.conv", False
        )
        x = self.resnets(x, "decoder.mid_block", False)
        for i, stride in enumerate(((2, 2, 2), (2, 2, 2), (2, 1, 1), (1, 2, 2))):
            p = f"decoder.up_blocks.{i}"
            x = self.conv(x, self.w, p + ".upsamplers.0.conv.conv", False)
            x = depth_to_space(x, stride)[:, stride[0] - 1 :]
            x = self.resnets(x, p, False)
        x = self.conv(nn.silu(pixel_norm(x)), self.w, "decoder.conv_out.conv", False)
        b, t, h, w, c = x.shape
        x = (
            x.reshape(b, t, h, w, 3, 4, 4)
            .transpose(0, 1, 2, 6, 3, 5, 4)
            .reshape(b, t, h * 4, w * 4, 3)
        )
        return x.transpose(0, 4, 1, 2, 3)
