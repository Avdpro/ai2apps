"""AVTR-specific extensions to the existing LivePortrait MLX graph executor."""

import mlx.core as mx

from .onnx_mlx import MLXOnnxGraph
from .sampling import grid_sample_3d


class AvatarGraph(MLXOnnxGraph):
    SUPPORTED_OPS = MLXOnnxGraph.SUPPORTED_OPS | {
        "GridSample3D",
        "LayerNormalization",
        "ScatterND",
    }

    def _run(self, node, args, values):
        a = node.attrs
        x = args[0] if args else None
        if node.op == "GridSample3D":
            mode = a.get("padding_mode", 0)
            if isinstance(mode, int):
                mode = ["zeros", "border", "reflection"][mode]
            if isinstance(mode, bytes):
                mode = mode.decode()
            return grid_sample_3d(
                x,
                args[1],
                padding_mode=mode,
                align_corners=bool(a.get("align_corners", 0)),
            )
        if node.op == "LayerNormalization":
            axis = int(a.get("axis", -1))
            axes = tuple(range(axis % x.ndim, x.ndim))
            mean = mx.mean(x, axis=axes, keepdims=True)
            y = (x - mean) * mx.rsqrt(
                mx.mean((x - mean) ** 2, axis=axes, keepdims=True)
                + float(a.get("epsilon", 1e-5))
            )
            y = y * args[1]
            if len(args) > 2:
                y = y + args[2]
            return y
        if node.op == "ScatterND":
            idx = args[1].astype(mx.int32)
            y = mx.array(x)
            y[tuple(idx[..., i] for i in range(idx.shape[-1]))] = args[2]
            return y
        return super()._run(node, args, values)

    def _conv(self, x, w, b, a):
        if x.ndim != 3:
            return super()._conv(x, w, b, a)
        p = a.get("pads", [0, 0])
        v = x.transpose(0, 2, 1)
        if p[0] != p[1]:
            v = mx.pad(v, [(0, 0), (p[0], p[1]), (0, 0)])
            pad = 0
        else:
            pad = p[0]
        y = mx.conv1d(
            v,
            w.transpose(0, 2, 1),
            stride=a.get("strides", [1])[0],
            padding=pad,
            dilation=a.get("dilations", [1])[0],
            groups=a.get("group", 1),
        )
        if b is not None:
            y = y + b
        return y.transpose(0, 2, 1)
