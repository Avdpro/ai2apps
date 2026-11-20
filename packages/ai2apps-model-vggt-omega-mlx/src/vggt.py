"""Experimental single-image VGGT-Omega 1B MLX inference.

Architecture derived from facebookresearch/vggt-omega; upstream FAIR research
and DINOv3 terms apply to weights and derived components. Not release-ready.
"""

import math
import mlx.core as mx
import mlx.nn as nn
from da import DepthAnythingLarge, resize


class VGGTOmegaSingle(DepthAnythingLarge):
    def norm(self, x, name):
        return mx.fast.layer_norm(
            x, self.w[name + ".weight"], self.w[name + ".bias"], 1e-5
        )

    def linear(self, x, name):
        y = x @ self.w[name + ".weight"].T
        if name + ".bias" in self.w:
            b = self.w[name + ".bias"]
            if name + ".bias_mask" in self.w:
                b = b * self.w[name + ".bias_mask"]
            y = y + b
        return y

    def rope(self, h, w, name):
        yy, xx = mx.meshgrid(
            (mx.arange(h) + 0.5) / max(h, w),
            (mx.arange(w) + 0.5) / max(h, w),
            indexing="ij",
        )
        coords = mx.stack([yy, xx], -1).reshape(-1, 2) * 2 - 1
        a = (2 * math.pi * coords[..., None] / self.w[name + ".periods"]).reshape(
            h * w, -1
        )
        a = mx.concatenate([a, a], -1)
        return mx.sin(a), mx.cos(a)

    def block(self, x, name, rope=None):
        b, n, c = x.shape
        d = c // 16
        qkv = (
            self.linear(self.norm(x, name + ".norm1"), name + ".attn.qkv")
            .reshape(b, n, 3, 16, d)
            .transpose(2, 0, 3, 1, 4)
        )
        q, k, v = qkv[0], qkv[1], qkv[2]
        if name + ".attn.q_norm.weight" in self.w:
            q = self.norm(q, name + ".attn.q_norm")
            k = self.norm(k, name + ".attn.k_norm")
        if rope is not None:
            s, co = rope
            prefix = n - s.shape[0]

            def rotate(a):
                t = a[:, :, prefix:]
                u = mx.concatenate([-t[..., d // 2 :], t[..., : d // 2]], -1)
                return mx.concatenate([a[:, :, :prefix], t * co + u * s], axis=2)

            q, k = rotate(q), rotate(k)
        y = (
            mx.fast.scaled_dot_product_attention(q, k, v, scale=d**-0.5)
            .transpose(0, 2, 1, 3)
            .reshape(b, n, c)
        )
        x = x + self.linear(y, name + ".attn.proj") * self.w[name + ".ls1.gamma"]
        x = (
            x
            + self.linear(
                nn.gelu(self.linear(self.norm(x, name + ".norm2"), name + ".mlp.fc1")),
                name + ".mlp.fc2",
            )
            * self.w[name + ".ls2.gamma"]
        )
        mx.eval(x)
        return x

    def pos(self, x):
        _, h, w, c = x.shape
        span = 1 / math.sqrt(2)
        xx = mx.linspace(-span * (w - 1) / w, span * (w - 1) / w, w)
        yy = mx.linspace(-span * (h - 1) / h, span * (h - 1) / h, h)
        yy, xx = mx.meshgrid(yy, xx, indexing="ij")
        freq = 100 ** (-mx.arange(c // 4, dtype=mx.float32) / (c / 4))
        a = xx[..., None] * freq
        b = yy[..., None] * freq
        return x + 0.1 * mx.concatenate(
            [mx.sin(a), mx.cos(a), mx.sin(b), mx.cos(b)], -1
        )

    def __call__(self, image):
        if image.shape != (1, 512, 512, 3):
            raise ValueError("Single 512x512 RGB image required")
        p = "aggregator.patch_embed"
        x = (image - mx.array([0.485, 0.456, 0.406])) / mx.array([0.229, 0.224, 0.225])
        x = self.conv(x, p + ".patch_embed.proj", stride=16).reshape(1, 1024, 1024)
        x = mx.concatenate(
            [self.w[p + ".cls_token"], self.w[p + ".storage_tokens"], x], 1
        )
        rope = self.rope(32, 32, p + ".rope_embed")
        for i in range(24):
            x = self.block(x, f"{p}.blocks.{i}", rope)
        x = self.norm(x, p + ".norm")[:, 5:]
        p = "aggregator"
        x = mx.concatenate(
            [self.w[p + ".camera_token"][:, 0], self.w[p + ".register_token"][:, 0], x],
            1,
        )
        rope = self.rope(32, 32, p + ".rope_embed")
        features = []
        for i in range(24):
            frame = self.block(x, f"{p}.frame_blocks.{i}", rope)
            if i in (2, 6, 9, 14, 20):
                x = mx.concatenate(
                    [
                        self.block(frame[:, :17], f"{p}.inter_frame_blocks.{i}"),
                        frame[:, 17:],
                    ],
                    1,
                )
            else:
                x = self.block(frame, f"{p}.inter_frame_blocks.{i}")
            if i in (4, 11, 17, 23):
                features.append(mx.concatenate([frame, x], -1))
        p = "camera_head"
        camera = self.norm(features[-1][:, :17], p + ".token_norm")
        for i in range(4):
            camera = self.block(camera, f"{p}.trunk.{i}")
        camera = self.linear(
            nn.gelu(
                self.linear(
                    self.norm(camera[:, 0], p + ".trunk_norm"), p + ".camera_branch.0"
                )
            ),
            p + ".camera_branch.2",
        )
        camera = mx.concatenate(
            [camera[:, :7], mx.maximum(camera[:, 7:], 0) + 0.01], -1
        )
        p = "dense_head"
        layers = []
        for i, y in enumerate(features):
            y = self.norm(y[:, 17:], p + ".norm").reshape(1, 32, 32, 2048)
            y = self.pos(self.conv(y, f"{p}.projects.{i}"))
            if i < 2:
                y = self.conv(
                    y,
                    f"{p}.resize_layers.{i}",
                    stride=4 if i == 0 else 2,
                    transpose=True,
                )
            elif i == 3:
                y = self.conv(y, p + ".resize_layers.3", stride=2, padding=1)
            layers.append(self.conv(y, f"{p}.scratch.layer{i + 1}_rn", padding=1))
        x = self.fusion(
            layers[3], None, p + ".scratch.refinenet4", layers[2].shape[1:3]
        )
        for i in (2, 1, 0):
            x = self.fusion(
                x,
                layers[i],
                f"{p}.scratch.refinenet{i + 1}",
                layers[max(0, i - 1)].shape[1:3],
            )
        x = self.pos(x)

        def prediction(name):
            y = self.conv(x, name)
            b, h, w, c = y.shape
            return (
                y.reshape(b, h, w, 1, 4, 4)
                .transpose(0, 1, 4, 2, 5, 3)
                .reshape(b, h * 4, w * 4)
            )

        return {
            "pose_enc": camera,
            "depth": mx.exp(prediction(p + ".proj")),
            "depth_conf": 1 + mx.exp(prediction(p + ".proj_conf")),
        }
