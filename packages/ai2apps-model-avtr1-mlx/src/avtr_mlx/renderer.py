"""Prepared MLX renderer: constant source work, fused sampling and packed mask conv."""

import mlx.core as mx

from .decoder import FastDecoder
from .mask_conv import (
    mask_conv3d_packed_2d,
    pack_mask_conv3d_weight_2d,
)
from .sampling import grid_sample_3d as grid_sample_3d_ncdhw


class FastRenderer:
    def __init__(self, graphs, feature, source, *, mixed=False):
        self.graph = graphs["warp_network"]
        self.stitch = graphs["stitch_network"]
        self.source = mx.array(source)
        self.decoder = FastDecoder(
            graphs["decoder"], dtype=mx.float16 if mixed else mx.float32
        )
        self.mask_weights = {}
        for node in self.graph.nodes:
            if node.op == "Conv":
                weight = self.graph.initializers.get(node.inputs[1])
                if (
                    weight is not None
                    and weight.ndim == 5
                    and weight.shape[2:] == (7, 7, 7)
                ):
                    a = node.attrs
                    if (
                        a.get("strides") != [1, 1, 1]
                        or a.get("dilations") != [1, 1, 1]
                        or a.get("group", 1) != 1
                        or a.get("pads") != [3] * 6
                    ):
                        raise ValueError("Unexpected mask convolution")
                    self.mask_weights[node.name] = pack_mask_conv3d_weight_2d(
                        weight.transpose(0, 2, 3, 4, 1)
                    )
        self.constants = dict(self.graph.initializers)
        self.constants.update(feature_3d=feature, kp_source=self.source)
        self.dynamic = []
        for node in self.graph.nodes:
            if all(not name or name in self.constants for name in node.inputs):
                args = [self.constants[name] if name else None for name in node.inputs]
                self.constants[node.outputs[0]] = self._run(node, args, self.constants)
            else:
                self.dynamic.append(node)
        mx.eval(self.constants, self.mask_weights)
        self.warp = mx.compile(self._warp)

    def _run(self, node, args, values):
        if node.op == "GridSample3D" and node.attrs.get("padding_mode", 0) in (
            0,
            "zeros",
            b"zeros",
        ):
            result = grid_sample_3d_ncdhw(
                args[0], args[1], align_corners=bool(node.attrs.get("align_corners", 0))
            )
            if result is not None:
                return result
        if node.name in self.mask_weights:
            out = mask_conv3d_packed_2d(
                args[0].transpose(0, 2, 3, 4, 1),
                self.mask_weights[node.name],
                args[2],
                depth_kernel=7,
                padding=3,
            )
            return out.transpose(0, 4, 1, 2, 3)
        return self.graph._run(node, args, values)

    def _warp(self, driving):
        driving = self.stitch({"kp_source": self.source, "kp_driving": driving})[0]
        values = dict(self.constants)
        values["kp_driving"] = driving
        for node in self.dynamic:
            args = [values[name] if name else None for name in node.inputs]
            values[node.outputs[0]] = self._run(node, args, values)
        return values[self.graph.outputs[0]]

    def render_batch(self, driving):
        """Warp each static-shape frame, then decode and transfer the batch once."""
        warped = mx.concatenate(
            [self.warp(driving[i : i + 1]) for i in range(driving.shape[0])], axis=0
        )
        return self.decoder(warped)

    def __call__(self, driving):
        return self.render_batch(driving)
