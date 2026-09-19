"""MLX wrapper for the GhostV2 identity encoder and native generator."""

from __future__ import annotations

from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np

from .native_ghostv2 import NativeGhostV2Generator
from .onnx_mlx import MLXOnnxGraph


def _nchw(image_bgr: np.ndarray) -> np.ndarray:
    rgb = np.ascontiguousarray(image_bgr[..., ::-1], dtype=np.float32)
    return np.ascontiguousarray((rgb.transpose(2, 0, 1) / 127.5) - 1.0)


class MLXGhostV2:
    """CVLFace identity encoder plus the native NHWC GhostV2 generator."""

    def __init__(self, models: str | Path, *, compile_graphs: bool = True):
        root = Path(models)
        self.dtype = mx.float16
        self.recognizer = MLXOnnxGraph(
            root / "ghostv2_cvlface.omlx", float16_mode="fp16_compatible"
        )
        self.generator = NativeGhostV2Generator(
            root / "ghostv2_generator.native",
            compile_graph=compile_graphs,
        )
        self._recognize = self._recognize_graph
        if compile_graphs:
            self._recognize = mx.compile(self._recognize_graph)

    def _recognize_graph(self, image):
        return tuple(self.recognizer({self.recognizer.inputs[0]: image}))

    def encode_aligned(self, source_bgr_256: np.ndarray):
        source = mx.array(_nchw(source_bgr_256)[None]).astype(self.dtype)
        source = mx.transpose(
            nn.Upsample(
                scale_factor=(112 / 256, 112 / 256),
                mode="linear",
                align_corners=False,
            )(mx.transpose(source, (0, 2, 3, 1))),
            (0, 3, 1, 2),
        )
        embedding = self._recognize(source)[0]
        embedding = embedding / mx.maximum(
            mx.sqrt(mx.sum(embedding * embedding, axis=1, keepdims=True)), 1e-12
        )
        mx.eval(embedding)
        return embedding

    def generate_aligned_batch(
        self, targets_bgr_256: list[np.ndarray], identity
    ) -> list[np.ndarray]:
        if not targets_bgr_256:
            return []
        batch_identity = mx.broadcast_to(
            identity, (len(targets_bgr_256), identity.shape[1])
        )
        target = mx.array(
            np.stack(
                [
                    np.ascontiguousarray(image[..., ::-1], dtype=np.float32)
                    / 127.5
                    - 1.0
                    for image in targets_bgr_256
                ]
            )
        ).astype(self.dtype)
        output = self.generator(target, batch_identity)
        mx.eval(output)
        values = np.asarray(output, dtype=np.float32)
        rgb = np.clip(np.rint((values + 1.0) * 127.5), 0, 255).astype(np.uint8)
        return [np.ascontiguousarray(image[..., ::-1]) for image in rgb]
