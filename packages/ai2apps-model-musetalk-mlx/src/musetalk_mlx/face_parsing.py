"""Inference-only BiSeNet face parsing with MLX-native OHWI weights.

Architecture: zllrunning/face-parsing.PyTorch (MIT). No Torch/ONNX runtime.
"""

from pathlib import Path

import mlx.core as mx
import numpy as np
from PIL import Image


class FaceParser:
    def __init__(self, checkpoint):
        self.weights = {
            k: v.astype(mx.float32)
            for k, v in mx.load(str(Path(checkpoint) / "model.safetensors")).items()
        }
        mx.eval(self.weights)

    def conv(self, x, key, stride=1, padding=0):
        return mx.conv2d(
            x, self.weights[key + ".weight"], stride=stride, padding=padding
        )

    def bn(self, x, key):
        w = self.weights
        return (x - w[key + ".running_mean"]) * mx.rsqrt(
            w[key + ".running_var"] + 1e-5
        ) * w[key + ".weight"] + w[key + ".bias"]

    def cbr(self, x, key, padding=1):
        return mx.maximum(
            self.bn(self.conv(x, key + ".conv", padding=padding), key + ".bn"), 0
        )

    def block(self, x, key, stride):
        y = mx.maximum(
            self.bn(self.conv(x, key + ".conv1", stride, 1), key + ".bn1"), 0
        )
        y = self.bn(self.conv(y, key + ".conv2", padding=1), key + ".bn2")
        if key + ".downsample.conv.weight" in self.weights:
            x = self.bn(
                self.conv(x, key + ".downsample.conv", stride), key + ".downsample.bn"
            )
        return mx.maximum(x + y, 0)

    def arm(self, x, key):
        x = self.cbr(x, key + ".conv")
        attention = self.bn(
            self.conv(mx.mean(x, axis=(1, 2), keepdims=True), key + ".conv_atten"),
            key + ".bn_atten",
        )
        return x * mx.sigmoid(attention)

    @staticmethod
    def up(x, height, width):
        # All context-path nearest resizes have integer scale factors.
        return mx.repeat(
            mx.repeat(x, height // x.shape[1], axis=1), width // x.shape[2], axis=2
        )

    @staticmethod
    def bilinear(x, height, width):
        # Match torch interpolate(..., align_corners=True), including endpoints.
        yy = mx.linspace(0, x.shape[1] - 1, height)
        xx = mx.linspace(0, x.shape[2] - 1, width)
        y0, x0 = yy.astype(mx.int32), xx.astype(mx.int32)
        y1, x1 = mx.minimum(y0 + 1, x.shape[1] - 1), mx.minimum(x0 + 1, x.shape[2] - 1)
        dy, dx = (yy - y0)[None, :, None, None], (xx - x0)[None, None, :, None]
        return (
            x[:, y0[:, None], x0[None, :]] * (1 - dy) * (1 - dx)
            + x[:, y1[:, None], x0[None, :]] * dy * (1 - dx)
            + x[:, y0[:, None], x1[None, :]] * (1 - dy) * dx
            + x[:, y1[:, None], x1[None, :]] * dy * dx
        )

    def logits(self, x):
        height, width = x.shape[1:3]
        p = "cp.resnet"
        x = mx.maximum(self.bn(self.conv(x, p + ".conv1", 2, 3), p + ".bn1"), 0)
        x = mx.pad(x, ((0, 0), (1, 1), (1, 1), (0, 0)), constant_values=-float("inf"))
        h, w = (x.shape[1] - 3) // 2 + 1, (x.shape[2] - 3) // 2 + 1
        x = mx.max(
            mx.stack(
                [
                    x[:, dy : dy + 2 * h : 2, dx : dx + 2 * w : 2]
                    for dy in range(3)
                    for dx in range(3)
                ]
            ),
            axis=0,
        )
        features = []
        for layer in range(1, 5):
            for block in range(2):
                x = self.block(
                    x, f"{p}.layer{layer}.{block}", 2 if layer > 1 and block == 0 else 1
                )
            if layer > 1:
                features.append(x)
        f8, f16, f32 = features
        avg = self.cbr(
            mx.mean(f32, axis=(1, 2), keepdims=True), "cp.conv_avg", padding=0
        )
        up32 = self.cbr(
            self.up(self.arm(f32, "cp.arm32") + avg, *f16.shape[1:3]), "cp.conv_head32"
        )
        up16 = self.cbr(
            self.up(self.arm(f16, "cp.arm16") + up32, *f8.shape[1:3]), "cp.conv_head16"
        )
        fused = self.cbr(mx.concatenate([f8, up16], axis=-1), "ffm.convblk", padding=0)
        attention = self.conv(
            mx.maximum(
                self.conv(mx.mean(fused, axis=(1, 2), keepdims=True), "ffm.conv1"), 0
            ),
            "ffm.conv2",
        )
        fused = fused * (1 + mx.sigmoid(attention))
        out = self.conv(self.cbr(fused, "conv_out.conv"), "conv_out.conv_out")
        return self.bilinear(out, height, width)

    def parse(self, rgb):
        image = (
            np.asarray(
                Image.fromarray(rgb).resize((512, 512), Image.Resampling.BILINEAR),
                dtype=np.float32,
            )
            / 255
        )
        image = (image - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array(
            [0.229, 0.224, 0.225], dtype=np.float32
        )
        labels = mx.argmax(self.logits(mx.array(image[None])), axis=-1)[0]
        mx.eval(labels)
        return np.asarray(labels, dtype=np.uint8)
