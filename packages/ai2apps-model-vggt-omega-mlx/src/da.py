"""Experimental FP32 Depth Anything V2 Large inference; NHWC, MLX only.

Architecture follows DepthAnything/Depth-Anything-V2 (Apache-2.0 code).
Large checkpoint remains subject to its upstream non-commercial license.
Weights use original names/layout; conversion is an offline operation.
"""

import math
import mlx.core as mx
import mlx.nn as nn


def resize(x, size, *, cubic=False, offset=0.0):
    """Bilinear align_corners=True or PyTorch bicubic half-pixel interpolation."""
    for axis, target in zip((1, 2), size):
        old = x.shape[axis]
        if cubic:
            p = (mx.arange(target, dtype=mx.float32) + 0.5) * old / (
                target + offset
            ) - 0.5
            base = mx.floor(p).astype(mx.int32)
            result = 0
            for delta in (-1, 0, 1, 2):
                dist = mx.abs(p - (base + delta))
                a = -0.75
                weight = mx.where(
                    dist <= 1,
                    (a + 2) * dist**3 - (a + 3) * dist**2 + 1,
                    mx.where(
                        dist < 2,
                        a * dist**3 - 5 * a * dist**2 + 8 * a * dist - 4 * a,
                        0,
                    ),
                )
                shape = [1] * 4
                shape[axis] = target
                result = result + mx.take(
                    x, mx.clip(base + delta, 0, old - 1), axis=axis
                ) * weight.reshape(shape)
            x = result
        else:
            p = mx.arange(target, dtype=mx.float32) * (
                (old - 1) / (target - 1) if target > 1 else 0
            )
            lo = mx.floor(p).astype(mx.int32)
            shape = [1] * 4
            shape[axis] = target
            weight = (p - lo).reshape(shape)
            x = (
                mx.take(x, lo, axis=axis) * (1 - weight)
                + mx.take(x, mx.minimum(lo + 1, old - 1), axis=axis) * weight
            )
    return x


class DepthAnythingLarge:
    def __init__(self, weights):
        self.w = mx.load(str(weights))

    def infer_rgb(self, image, input_size=1036):
        """RGB uint8 HWC -> original-resolution relative inverse depth, no cv2."""
        h, w, _ = image.shape
        scale = max(input_size / h, input_size / w)

        def dimension(n):
            d = round(n * scale / 14) * 14
            return math.ceil(n * scale / 14) * 14 if d < input_size else d

        x = mx.array(image.astype("float32"))[None] / 255
        x = resize(x, (dimension(h), dimension(w)), cubic=True)
        x = (x - mx.array([0.485, 0.456, 0.406])) / mx.array([0.229, 0.224, 0.225])
        return resize(self(x)[..., None], (h, w))[0, ..., 0]

    def linear(self, x, name):
        y = x @ self.w[name + ".weight"].T
        return y + self.w[name + ".bias"] if name + ".bias" in self.w else y

    def norm(self, x, name):
        return mx.fast.layer_norm(
            x, self.w[name + ".weight"], self.w[name + ".bias"], 1e-6
        )

    def conv(self, x, name, stride=1, padding=0, transpose=False):
        w = self.w[name + ".weight"]
        if transpose:
            # These heads use non-overlapping kernel==stride upsampling.
            # Explicit FP32 projection avoids Metal transposed-conv precision loss.
            if padding or w.shape[2:] != (stride, stride):
                raise ValueError(
                    "Only non-overlapping transposed convolution is supported"
                )
            b, h, width, channels = x.shape
            oc = w.shape[1]
            y = x @ w.transpose(0, 2, 3, 1).reshape(channels, -1)
            y = (
                y.reshape(b, h, width, stride, stride, oc)
                .transpose(0, 1, 3, 2, 4, 5)
                .reshape(b, h * stride, width * stride, oc)
            )
        else:
            y = mx.conv2d(x, w.transpose(0, 2, 3, 1), stride=stride, padding=padding)
        return y + self.w[name + ".bias"] if name + ".bias" in self.w else y

    def residual(self, x, name):
        y = self.conv(mx.maximum(x, 0), name + ".conv1", padding=1)
        return x + self.conv(mx.maximum(y, 0), name + ".conv2", padding=1)

    def fusion(self, x, skip, name, size):
        if skip is not None:
            x = x + self.residual(skip, name + ".resConfUnit1")
        x = self.residual(x, name + ".resConfUnit2")
        return self.conv(resize(x, size), name + ".out_conv")

    def __call__(self, image):
        # Input is normalized RGB NHWC, spatial dimensions divisible by 14.
        b, h, w, c = image.shape
        if h % 14 or w % 14:
            raise ValueError("Input sides must be divisible by 14")
        ph, pw = h // 14, w // 14
        p = "pretrained"
        x = self.conv(image, p + ".patch_embed.proj", stride=14).reshape(
            b, ph * pw, 1024
        )
        x = mx.concatenate(
            [mx.broadcast_to(self.w[p + ".cls_token"], (b, 1, 1024)), x], axis=1
        )
        pos = self.w[p + ".pos_embed"]
        s = math.isqrt(pos.shape[1] - 1)
        if ph != s or pw != s:
            pp = resize(
                pos[:, 1:].reshape(1, s, s, 1024), (ph, pw), cubic=True, offset=0.1
            )
            pos = mx.concatenate([pos[:, :1], pp.reshape(1, ph * pw, 1024)], axis=1)
        x = x + pos
        features = []
        for i in range(24):
            n = f"{p}.blocks.{i}"
            y = self.norm(x, n + ".norm1")
            qkv = (
                self.linear(y, n + ".attn.qkv")
                .reshape(b, -1, 3, 16, 64)
                .transpose(2, 0, 3, 1, 4)
            )
            y = (
                mx.fast.scaled_dot_product_attention(
                    qkv[0], qkv[1], qkv[2], scale=1 / 8
                )
                .transpose(0, 2, 1, 3)
                .reshape(b, -1, 1024)
            )
            x = x + self.linear(y, n + ".attn.proj") * self.w[n + ".ls1.gamma"]
            y = self.linear(
                nn.gelu(self.linear(self.norm(x, n + ".norm2"), n + ".mlp.fc1")),
                n + ".mlp.fc2",
            )
            x = x + y * self.w[n + ".ls2.gamma"]
            mx.eval(x)
            if i in (4, 11, 17, 23):
                features.append(
                    self.norm(x, p + ".norm")[:, 1:].reshape(b, ph, pw, 1024)
                )
        layers = []
        p = "depth_head"
        for i, y in enumerate(features):
            y = self.conv(y, f"{p}.projects.{i}")
            if i < 2:
                y = self.conv(
                    y,
                    f"{p}.resize_layers.{i}",
                    stride=4 if i == 0 else 2,
                    transpose=True,
                )
            elif i == 3:
                y = self.conv(y, f"{p}.resize_layers.3", stride=2, padding=1)
            layers.append(self.conv(y, f"{p}.scratch.layer{i + 1}_rn", padding=1))
        p += ".scratch"
        x = self.fusion(layers[3], None, p + ".refinenet4", layers[2].shape[1:3])
        for i in (2, 1, 0):
            size = (
                layers[i - 1].shape[1:3]
                if i
                else (layers[0].shape[1] * 2, layers[0].shape[2] * 2)
            )
            x = self.fusion(x, layers[i], f"{p}.refinenet{i + 1}", size)
        x = resize(self.conv(x, p + ".output_conv1", padding=1), (h, w))
        x = mx.maximum(self.conv(x, p + ".output_conv2.0", padding=1), 0)
        return mx.maximum(self.conv(x, p + ".output_conv2.2"), 0)[..., 0]
