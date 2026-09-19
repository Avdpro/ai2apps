"""Parser-free MLX implementation wrapper for exported GhostV2 graphs."""

from __future__ import annotations

from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np

from .onnx_mlx import MLXOnnxGraph


def _nchw(image_bgr: np.ndarray) -> np.ndarray:
    rgb = np.ascontiguousarray(image_bgr[..., ::-1], dtype=np.float32)
    return np.ascontiguousarray((rgb.transpose(2, 0, 1) / 127.5) - 1.0)


class MLXGhostV2:
    """CVLFace identity encoder plus GhostV2 256px generator."""

    def __init__(
        self,
        models: str | Path,
        *,
        precision: str = "fp16",
        compile_graphs: bool = True,
        native_generator: str | Path | None = None,
    ):
        if precision not in {"fp16", "bf16"}:
            raise ValueError("precision must be fp16 or bf16")
        self.dtype = mx.float16 if precision == "fp16" else mx.bfloat16
        storage_mode = "bf16" if precision == "bf16" else "fp16_compatible"
        root = Path(models)
        self.recognizer = MLXOnnxGraph(
            root / "ghostv2_cvlface.omlx", float16_mode=storage_mode
        )
        self.native_generator = None
        if native_generator is None:
            self.generator = MLXOnnxGraph(
                root / "ghostv2_generator.omlx", float16_mode=storage_mode
            )
        else:
            from .native_ghostv2.model import (  # noqa: PLC0415
                NativeGhostV2Generator,
            )

            self.generator = None
            self.native_generator = NativeGhostV2Generator(
                native_generator,
                precision=precision,
                compile_graph=compile_graphs,
            )
        self._recognize = self._recognize_graph
        self._generate = self._generate_graph
        if compile_graphs:
            self._recognize = mx.compile(self._recognize_graph)
            if self.native_generator is None:
                self._generate = mx.compile(self._generate_graph)

    def _recognize_graph(self, image):
        return tuple(self.recognizer({self.recognizer.inputs[0]: image}))

    def _generate_graph(self, target, identity):
        assert self.generator is not None
        return tuple(
            self.generator(
                {
                    self.generator.inputs[0]: target,
                    self.generator.inputs[1]: identity,
                }
            )
        )

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
        if self.native_generator is None:
            target = mx.array(
                np.stack([_nchw(image) for image in targets_bgr_256])
            ).astype(self.dtype)
            output = self._generate(target, batch_identity)[0]
            mx.eval(output)
            values = np.asarray(output, dtype=np.float32).transpose(0, 2, 3, 1)
        else:
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
            output = self.native_generator(target, batch_identity)
            mx.eval(output)
            values = np.asarray(output, dtype=np.float32)
        rgb = np.clip(np.rint((values + 1.0) * 127.5), 0, 255).astype(np.uint8)
        return [np.ascontiguousarray(image[..., ::-1]) for image in rgb]
