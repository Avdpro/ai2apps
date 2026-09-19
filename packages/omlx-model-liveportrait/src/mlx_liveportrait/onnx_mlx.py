"""Small, auditable ONNX inference subset implemented with MLX.

This is not a general ONNX runtime. It supports only the operators present in
the locked ArcFace, SCRFD, and InSwapper graphs used by this experiment. The
first goal is a trustworthy numerical reference; graph fusion and persistent
NHWC layouts come after parity.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


def _pair(value: Any, default: int = 1) -> tuple[int, int]:
    if value is None:
        return (default, default)
    if isinstance(value, (int, np.integer)):
        return (int(value), int(value))
    values = tuple(int(v) for v in value)
    if len(values) != 2:
        raise ValueError(f"expected a pair, got {values}")
    return values


def _ints(value: Any) -> list[int]:
    if isinstance(value, (int, float, np.integer, np.floating)):
        return [int(value)]
    return [int(v) for v in np.asarray(value).reshape(-1).tolist()]


@dataclass(frozen=True)
class Node:
    name: str
    op: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    attrs: dict[str, Any]


@dataclass(frozen=True)
class Subgraph:
    nodes: tuple[Node, ...]
    outputs: tuple[str, ...]
    initializers: dict[str, Any]


class MLXOnnxGraph:
    """Execute a constrained ONNX graph using MLX arrays."""

    SUPPORTED_OPS = {
        "Add",
        "AveragePool",
        "BatchNormalization",
        "Cast",
        "Clip",
        "Concat",
        "Constant",
        "ConstantOfShape",
        "Conv",
        "ConvTranspose",
        "DepthToSpace",
        "Div",
        "Equal",
        "Erf",
        "Exp",
        "Expand",
        "Flatten",
        "Gather",
        "Gemm",
        "GlobalAveragePool",
        "GridSample",
        "Identity",
        "If",
        "InstanceNormalization",
        "LeakyRelu",
        "MatMul",
        "Max",
        "MaxPool",
        "Mul",
        "Pad",
        "PRelu",
        "Pow",
        "ReduceMean",
        "ReduceL2",
        "ReduceSum",
        "Relu",
        "Reshape",
        "Resize",
        "Shape",
        "Sigmoid",
        "Slice",
        "Sqrt",
        "Softmax",
        "Split",
        "Squeeze",
        "Sub",
        "Tanh",
        "Tile",
        "Transpose",
        "Unsqueeze",
    }

    def __init__(self, model_path: str | Path):
        import mlx.core as mx

        self.mx = mx
        self.model_path = Path(model_path)
        if self.model_path.is_dir():
            self._load_bundle()
            return
        import onnx
        from onnx import numpy_helper

        model = onnx.load(str(self.model_path), load_external_data=True)
        self.opset = max((item.version for item in model.opset_import), default=0)
        self.inputs = tuple(item.name for item in model.graph.input)
        self.outputs = tuple(item.name for item in model.graph.output)
        self.initializers = {
            item.name: mx.array(np.asarray(numpy_helper.to_array(item)))
            for item in model.graph.initializer
        }
        self.nodes = tuple(
            Node(
                name=item.name or f"{item.op_type}_{index}",
                op=item.op_type,
                inputs=tuple(item.input),
                outputs=tuple(item.output),
                attrs={
                    attr.name: onnx.helper.get_attribute_value(attr)
                    for attr in item.attribute
                },
            )
            for index, item in enumerate(model.graph.node)
        )
        unsupported = sorted({node.op for node in self.nodes} - self.SUPPORTED_OPS)
        if unsupported:
            raise NotImplementedError(
                f"{self.model_path.name} contains unsupported operators: {unsupported}"
            )

    def _load_bundle(self) -> None:
        manifest = json.loads(
            (self.model_path / "graph.json").read_text(encoding="utf-8")
        )
        if manifest.get("schema_version") != 1:
            raise ValueError(f"unsupported graph bundle schema: {self.model_path}")
        # ``mx.load`` already returns MLX arrays. Re-wrapping them with
        # ``mx.array`` fails on some MLX/Metal configurations and needlessly
        # duplicates every model tensor.
        weights = self.mx.load(str(self.model_path / "weights.safetensors"))
        self.opset = int(manifest["opset"])
        self.inputs = tuple(manifest["inputs"])
        self.outputs = tuple(manifest["outputs"])
        self.initializers = {
            name: self._decode_attr(spec, weights)
            for name, spec in manifest["initializers"].items()
        }
        self.nodes = tuple(
            self._decode_node(item, weights) for item in manifest["nodes"]
        )
        unsupported = sorted({node.op for node in self.nodes} - self.SUPPORTED_OPS)
        if unsupported:
            raise NotImplementedError(
                f"bundle contains unsupported operators: {unsupported}"
            )

    def _decode_node(self, item: dict[str, Any], weights: dict[str, Any]) -> Node:
        return Node(
            name=item["name"],
            op=item["op"],
            inputs=tuple(item["inputs"]),
            outputs=tuple(item["outputs"]),
            attrs={
                key: self._decode_attr(value, weights)
                for key, value in item["attrs"].items()
            },
        )

    def _decode_attr(self, value: Any, weights: dict[str, Any]) -> Any:
        if isinstance(value, list):
            return [self._decode_attr(item, weights) for item in value]
        if not isinstance(value, dict):
            return value
        if "__tensor__" in value:
            tensor = weights[value["__tensor__"]]
            return self.mx.reshape(tensor, tuple(value.get("shape", tensor.shape)))
        if "__graph__" in value:
            graph = value["__graph__"]
            return Subgraph(
                nodes=tuple(
                    self._decode_node(item, weights) for item in graph["nodes"]
                ),
                outputs=tuple(graph["outputs"]),
                initializers={
                    name: self._decode_attr(spec, weights)
                    for name, spec in graph["initializers"].items()
                },
            )
        return {key: self._decode_attr(item, weights) for key, item in value.items()}

    def __call__(self, feeds: dict[str, Any]) -> list[Any]:
        mx = self.mx
        values = dict(self.initializers)
        for name, value in feeds.items():
            values[name] = value if isinstance(value, mx.array) else mx.array(value)
        missing = [name for name in self.inputs if name not in values]
        if missing:
            raise KeyError(f"missing graph inputs: {missing}")
        for node in self.nodes:
            args = [values[name] if name else None for name in node.inputs]
            try:
                result = self._run(node, args, values)
            except Exception as exc:
                shapes = [getattr(value, "shape", None) for value in args]
                raise RuntimeError(
                    f"failed at {node.name} ({node.op}), input shapes={shapes}"
                ) from exc
            results = result if isinstance(result, tuple) else (result,)
            if len(results) != len(node.outputs):
                raise RuntimeError(
                    f"{node.name} returned {len(results)} values for "
                    f"{len(node.outputs)} outputs"
                )
            values.update(zip(node.outputs, results, strict=True))
        return [values[name] for name in self.outputs]

    def _run(
        self, node: Node, args: list[Any], values: dict[str, Any] | None = None
    ) -> Any:  # noqa: C901
        mx = self.mx
        op, a = node.op, node.attrs
        x = args[0] if args else None

        if op == "Constant":
            if "value" in a:
                value = a["value"]
                if hasattr(value, "dims"):
                    from onnx import numpy_helper

                    value = np.asarray(numpy_helper.to_array(value))
                return mx.array(value)
            for name, dtype in (
                ("value_float", mx.float32),
                ("value_int", mx.int32),
                ("value_floats", mx.float32),
                ("value_ints", mx.int32),
            ):
                if name in a:
                    return mx.array(a[name], dtype=dtype)
            raise NotImplementedError(f"unsupported Constant attributes: {a.keys()}")
        if op == "ConstantOfShape":
            shape = tuple(_ints(x))
            if "value" in a:
                value = a["value"]
                if hasattr(value, "dims"):
                    from onnx import numpy_helper

                    value = mx.array(np.asarray(numpy_helper.to_array(value)))
                fill = value.reshape(-1)[0].item()
                dtype = value.dtype
            else:
                fill, dtype = 0.0, mx.float32
            return mx.full(shape, fill, dtype=dtype)
        if op == "Identity":
            return x
        if op == "Equal":
            return mx.equal(x, args[1])
        if op == "If":
            if values is None:
                raise ValueError("If requires its enclosing value scope")
            branch = a["then_branch"] if bool(x.item()) else a["else_branch"]
            return self._run_subgraph(branch, values)

        if op == "Add":
            return x + args[1]
        if op == "Sub":
            return x - args[1]
        if op == "Mul":
            return x * args[1]
        if op == "Max":
            return mx.maximum(x, args[1])
        if op == "Div":
            return x / args[1]
        if op == "Pow":
            return mx.power(x, args[1])
        if op == "Sqrt":
            return mx.sqrt(x)
        if op == "Exp":
            return mx.exp(x)
        if op == "Erf":
            return mx.erf(x)
        if op == "Relu":
            return mx.maximum(x, 0)
        if op == "LeakyRelu":
            alpha = float(a.get("alpha", 0.01))
            return mx.maximum(x, 0) + alpha * mx.minimum(x, 0)
        if op == "Sigmoid":
            return mx.sigmoid(x)
        if op == "Softmax":
            return mx.softmax(x, axis=int(a.get("axis", -1)))
        if op == "Tanh":
            return mx.tanh(x)
        if op == "Clip":
            minimum = a.get("min")
            maximum = a.get("max")
            if minimum is None and len(args) > 1 and args[1] is not None:
                minimum = args[1].item()
            if maximum is None and len(args) > 2 and args[2] is not None:
                maximum = args[2].item()
            return mx.clip(x, minimum, maximum)
        if op == "PRelu":
            slope = args[1]
            if slope.ndim == 1 and x.ndim >= 2:
                slope = mx.reshape(slope, (1, slope.shape[0], *([1] * (x.ndim - 2))))
            return mx.maximum(x, 0) + slope * mx.minimum(x, 0)
        if op == "Conv":
            return self._conv(x, args[1], args[2] if len(args) > 2 else None, a)
        if op == "ConvTranspose":
            return self._conv_transpose(
                x, args[1], args[2] if len(args) > 2 else None, a
            )
        if op in {"AveragePool", "MaxPool"}:
            return self._pool(x, a, average=op == "AveragePool")
        if op == "BatchNormalization":
            scale, bias, mean, variance = args[1:5]
            shape = (1, scale.shape[0], *([1] * (x.ndim - 2)))
            epsilon = float(a.get("epsilon", 1e-5))
            return (x - mx.reshape(mean, shape)) / mx.sqrt(
                mx.reshape(variance, shape) + epsilon
            ) * mx.reshape(scale, shape) + mx.reshape(bias, shape)
        if op == "InstanceNormalization":
            scale, bias = args[1:3]
            axes = tuple(range(2, x.ndim))
            mean = mx.mean(x, axis=axes, keepdims=True)
            variance = mx.mean((x - mean) ** 2, axis=axes, keepdims=True)
            shape = (1, scale.shape[0], *([1] * (x.ndim - 2)))
            return (x - mean) / mx.sqrt(
                variance + float(a.get("epsilon", 1e-5))
            ) * mx.reshape(scale, shape) + mx.reshape(bias, shape)
        if op == "Flatten":
            axis = int(a.get("axis", 1))
            if axis < 0:
                axis += x.ndim
            left = int(np.prod(x.shape[:axis], dtype=np.int64))
            right = int(np.prod(x.shape[axis:], dtype=np.int64))
            return mx.reshape(x, (left, right))
        if op == "Gemm":
            left, right = x, args[1]
            if int(a.get("transA", 0)):
                left = mx.swapaxes(left, -1, -2)
            if int(a.get("transB", 0)):
                right = mx.swapaxes(right, -1, -2)
            result = float(a.get("alpha", 1.0)) * (left @ right)
            if len(args) > 2 and args[2] is not None:
                result = result + float(a.get("beta", 1.0)) * args[2]
            return result
        if op == "MatMul":
            return x @ args[1]
        if op == "GlobalAveragePool":
            return mx.mean(x, axis=tuple(range(2, x.ndim)), keepdims=True)
        if op == "ReduceMean":
            axes = a.get("axes")
            if axes is None and len(args) > 1 and args[1] is not None:
                axes = _ints(args[1])
            axes_tuple = None if axes is None else tuple(int(v) for v in axes)
            return mx.mean(x, axis=axes_tuple, keepdims=bool(a.get("keepdims", 1)))
        if op == "ReduceSum":
            axes = a.get("axes")
            if axes is None and len(args) > 1 and args[1] is not None:
                axes = _ints(args[1])
            axes_tuple = None if axes is None else tuple(int(v) for v in axes)
            return mx.sum(x, axis=axes_tuple, keepdims=bool(a.get("keepdims", 1)))
        if op == "ReduceL2":
            axes = a.get("axes")
            if axes is None and len(args) > 1 and args[1] is not None:
                axes = _ints(args[1])
            axes_tuple = None if axes is None else tuple(int(v) for v in axes)
            return mx.sqrt(
                mx.sum(x * x, axis=axes_tuple, keepdims=bool(a.get("keepdims", 1)))
            )
        if op == "Unsqueeze":
            axes = a.get("axes")
            if axes is None:
                axes = _ints(args[1])
            result = x
            rank = x.ndim + len(axes)
            for axis in sorted(int(v) % rank for v in axes):
                result = mx.expand_dims(result, axis)
            return result
        if op == "Squeeze":
            axes = a.get("axes")
            if axes is None and len(args) > 1 and args[1] is not None:
                axes = _ints(args[1])
            return mx.squeeze(x, axis=None if axes is None else tuple(axes))
        if op == "Transpose":
            return mx.transpose(
                x, tuple(int(v) for v in a.get("perm", reversed(range(x.ndim))))
            )
        if op == "Concat":
            return mx.concatenate(args, axis=int(a.get("axis", 0)))
        if op == "Split":
            axis = int(a.get("axis", 0))
            sizes = a.get("split")
            if sizes is None and len(args) > 1 and args[1] is not None:
                sizes = _ints(args[1])
            if sizes is None:
                return tuple(mx.split(x, len(node.outputs), axis=axis))
            boundaries = np.cumsum([int(v) for v in sizes[:-1]]).tolist()
            return tuple(mx.split(x, boundaries, axis=axis))
        if op == "Reshape":
            shape = _ints(args[1])
            if int(a.get("allowzero", 0)) == 0:
                shape = [
                    x.shape[i] if size == 0 else size for i, size in enumerate(shape)
                ]
            return mx.reshape(x, tuple(shape))
        if op == "Expand":
            target = _ints(args[1])
            rank = max(x.ndim, len(target))
            source_shape = (1,) * (rank - x.ndim) + tuple(x.shape)
            target_shape = (1,) * (rank - len(target)) + tuple(target)
            result_shape = tuple(
                source if target_dim == 1 else target_dim
                for source, target_dim in zip(source_shape, target_shape, strict=True)
            )
            return mx.broadcast_to(mx.reshape(x, source_shape), result_shape)
        if op == "Tile":
            return mx.tile(x, tuple(_ints(args[1])))
        if op == "DepthToSpace":
            return self._depth_to_space(x, int(a["blocksize"]), a.get("mode", b"DCR"))
        if op == "GridSample":
            return self._grid_sample_3d(x, args[1], a)
        if op == "Shape":
            return mx.array(x.shape, dtype=mx.int32)
        if op == "Gather":
            return mx.take(x, args[1].astype(mx.int32), axis=int(a.get("axis", 0)))
        if op == "Slice":
            return self._slice(x, args, a)
        if op == "Pad":
            pads = a.get("pads") if len(args) < 2 or args[1] is None else _ints(args[1])
            if pads is None:
                raise ValueError("Pad requires pads")
            rank = x.ndim
            pad_width = tuple((int(pads[i]), int(pads[i + rank])) for i in range(rank))
            mode = a.get("mode", b"constant")
            mode = mode.decode() if isinstance(mode, bytes) else mode
            constant = 0 if len(args) < 3 or args[2] is None else args[2].item()
            if mode == "reflect":
                return self._reflect_pad(x, pad_width)
            return mx.pad(x, pad_width, mode=mode, constant_values=constant)
        if op == "Resize":
            return self._resize(x, args, a)
        if op == "Cast":
            return x.astype(self._dtype(int(a["to"])))
        raise NotImplementedError(f"operator {op} is not implemented")

    def _run_subgraph(self, graph: Any, outer_values: dict[str, Any]) -> Any:
        values = dict(outer_values)
        if isinstance(graph, Subgraph):
            values.update(graph.initializers)
            nodes = graph.nodes
            output_names = graph.outputs
        else:
            from onnx import helper, numpy_helper

            values.update(
                {
                    item.name: self.mx.array(np.asarray(numpy_helper.to_array(item)))
                    for item in graph.initializer
                }
            )
            nodes = tuple(
                Node(
                    name=item.name or f"{item.op_type}_{index}",
                    op=item.op_type,
                    inputs=tuple(item.input),
                    outputs=tuple(item.output),
                    attrs={
                        attr.name: helper.get_attribute_value(attr)
                        for attr in item.attribute
                    },
                )
                for index, item in enumerate(graph.node)
            )
            output_names = tuple(item.name for item in graph.output)
        for node in nodes:
            args = [values[name] if name else None for name in node.inputs]
            result = self._run(node, args, values)
            results = result if isinstance(result, tuple) else (result,)
            values.update(zip(node.outputs, results, strict=True))
        outputs = tuple(values[name] for name in output_names)
        return outputs[0] if len(outputs) == 1 else outputs

    def _conv(self, x: Any, weight: Any, bias: Any, attrs: dict[str, Any]) -> Any:
        mx = self.mx
        if x.ndim == 5:
            return self._conv3d(x, weight, bias, attrs)
        strides = _pair(attrs.get("strides"), 1)
        dilations = _pair(attrs.get("dilations"), 1)
        groups = int(attrs.get("group", 1))
        pads = tuple(int(v) for v in attrs.get("pads", (0, 0, 0, 0)))
        output_dtype = x.dtype
        # MLX's native fp16 convolution accumulation can overflow in the
        # InSwapper encoder before its following instance normalization. ORT
        # and PyTorch use a wider accumulator for this graph. Keep fp16 model
        # storage and graph outputs, but match that accumulation behavior.
        promote_accumulator = output_dtype == mx.float16
        if promote_accumulator:
            x = x.astype(mx.float32)
            weight = weight.astype(mx.float32)
            if bias is not None:
                bias = bias.astype(mx.float32)
        if attrs.get("auto_pad") in {b"SAME_UPPER", "SAME_UPPER"}:
            kh, kw = weight.shape[2:]
            effective = ((kh - 1) * dilations[0] + 1, (kw - 1) * dilations[1] + 1)
            pads = (
                effective[0] // 2,
                effective[1] // 2,
                (effective[0] - 1) // 2,
                (effective[1] - 1) // 2,
            )
        nhwc = mx.transpose(x, (0, 2, 3, 1))
        if pads[0] == pads[2] and pads[1] == pads[3]:
            padding: tuple[int, int] | int = (pads[0], pads[1])
        else:
            nhwc = mx.pad(
                nhwc, ((0, 0), (pads[0], pads[2]), (pads[1], pads[3]), (0, 0))
            )
            padding = 0
        ohwi = mx.transpose(weight, (0, 2, 3, 1))
        result = mx.conv2d(
            nhwc,
            ohwi,
            stride=strides,
            padding=padding,
            dilation=dilations,
            groups=groups,
        )
        if bias is not None:
            result = result + mx.reshape(bias, (1, 1, 1, -1))
        result = mx.transpose(result, (0, 3, 1, 2))
        if promote_accumulator:
            # ONNX Runtime's CPU fp16 path saturates conversion at the finite
            # fp16 boundary; an unchecked MLX cast produces infinities.
            result = mx.clip(result, -65504.0, 65504.0).astype(output_dtype)
        return result

    def _conv3d(self, x: Any, weight: Any, bias: Any, attrs: dict[str, Any]) -> Any:
        mx = self.mx

        def triple(value: Any, default: int) -> tuple[int, int, int]:
            if value is None:
                return (default, default, default)
            if isinstance(value, (int, np.integer)):
                return (int(value),) * 3
            result = tuple(int(item) for item in value)
            if len(result) != 3:
                raise ValueError(f"expected a triple, got {result}")
            return result

        strides = triple(attrs.get("strides"), 1)
        dilations = triple(attrs.get("dilations"), 1)
        groups = int(attrs.get("group", 1))
        pads = tuple(int(value) for value in attrs.get("pads", (0,) * 6))
        ndhwc = mx.transpose(x, (0, 2, 3, 4, 1))
        if pads[:3] == pads[3:]:
            padding: tuple[int, int, int] | int = pads[:3]
        else:
            ndhwc = mx.pad(
                ndhwc,
                (
                    (0, 0),
                    (pads[0], pads[3]),
                    (pads[1], pads[4]),
                    (pads[2], pads[5]),
                    (0, 0),
                ),
            )
            padding = 0
        odhwi = mx.transpose(weight, (0, 2, 3, 4, 1))
        result = mx.conv3d(
            ndhwc,
            odhwi,
            stride=strides,
            padding=padding,
            dilation=dilations,
            groups=groups,
        )
        if bias is not None:
            result = result + mx.reshape(bias, (1, 1, 1, 1, -1))
        return mx.transpose(result, (0, 4, 1, 2, 3))

    def _pool(self, x: Any, attrs: dict[str, Any], *, average: bool) -> Any:
        import mlx.nn as nn

        if x.ndim == 5:
            kernel = tuple(int(item) for item in attrs.get("kernel_shape", (1, 1, 1)))
            stride = tuple(int(item) for item in attrs.get("strides", kernel))
            pads = tuple(int(item) for item in attrs.get("pads", (0,) * 6))
            if pads[:3] != pads[3:]:
                raise NotImplementedError(f"asymmetric 3D pooling padding: {pads}")
            ndhwc = self.mx.transpose(x, (0, 2, 3, 4, 1))
            layer_cls = nn.AvgPool3d if average else nn.MaxPool3d
            result = layer_cls(kernel, stride=stride, padding=pads[:3])(ndhwc)
            return self.mx.transpose(result, (0, 4, 1, 2, 3))

        kernel = _pair(attrs.get("kernel_shape"), 1)
        stride = _pair(attrs.get("strides"), kernel[0])
        pads = tuple(int(v) for v in attrs.get("pads", (0, 0, 0, 0)))
        nhwc = self.mx.transpose(x, (0, 2, 3, 1))
        if int(attrs.get("ceil_mode", 0)):
            height, width = nhwc.shape[1:3]
            needed_h = max(
                0,
                (int(np.ceil((height - kernel[0]) / stride[0])) * stride[0] + kernel[0])
                - height,
            )
            needed_w = max(
                0,
                (int(np.ceil((width - kernel[1]) / stride[1])) * stride[1] + kernel[1])
                - width,
            )
            if needed_h or needed_w:
                fill = 0.0 if average else float("-inf")
                nhwc = self.mx.pad(
                    nhwc,
                    ((0, 0), (0, needed_h), (0, needed_w), (0, 0)),
                    constant_values=fill,
                )
        if pads[0] != pads[2] or pads[1] != pads[3]:
            raise NotImplementedError(f"asymmetric pooling padding: {pads}")
        layer_cls = nn.AvgPool2d if average else nn.MaxPool2d
        result = layer_cls(kernel, stride=stride, padding=(pads[0], pads[1]))(nhwc)
        return self.mx.transpose(result, (0, 3, 1, 2))

    def _conv_transpose(
        self, x: Any, weight: Any, bias: Any, attrs: dict[str, Any]
    ) -> Any:
        mx = self.mx
        strides = _pair(attrs.get("strides"), 1)
        dilations = _pair(attrs.get("dilations"), 1)
        groups = int(attrs.get("group", 1))
        pads = tuple(int(v) for v in attrs.get("pads", (0, 0, 0, 0)))
        output_padding = _pair(attrs.get("output_padding"), 0)
        nhwc = mx.transpose(x, (0, 2, 3, 1))
        # ONNX IOHW -> MLX OHWI.
        ohwi = mx.transpose(weight, (1, 2, 3, 0))
        result = mx.conv_transpose2d(
            nhwc,
            ohwi,
            stride=strides,
            padding=(pads[0], pads[1]),
            dilation=dilations,
            output_padding=output_padding,
            groups=groups,
        )
        # MLX accepts symmetric padding. Crop/pad the far edge to reproduce
        # ONNX's independent beginning/end padding values.
        crop_height = pads[2] - pads[0]
        crop_width = pads[3] - pads[1]
        if crop_height > 0:
            result = result[:, : result.shape[1] - crop_height]
        elif crop_height < 0:
            result = mx.pad(result, ((0, 0), (0, -crop_height), (0, 0), (0, 0)))
        if crop_width > 0:
            result = result[:, :, : result.shape[2] - crop_width]
        elif crop_width < 0:
            result = mx.pad(result, ((0, 0), (0, 0), (0, -crop_width), (0, 0)))
        if bias is not None:
            result = result + mx.reshape(bias, (1, 1, 1, -1))
        return mx.transpose(result, (0, 3, 1, 2))

    def _slice(self, x: Any, args: list[Any], attrs: dict[str, Any]) -> Any:
        starts = attrs.get("starts") if len(args) < 2 else _ints(args[1])
        ends = attrs.get("ends") if len(args) < 3 else _ints(args[2])
        axes = attrs.get("axes")
        if axes is None:
            axes = (
                list(range(len(starts)))
                if len(args) < 4 or args[3] is None
                else _ints(args[3])
            )
        steps = attrs.get("steps")
        if steps is None:
            steps = (
                [1] * len(starts)
                if len(args) < 5 or args[4] is None
                else _ints(args[4])
            )
        slices = [slice(None)] * x.ndim
        for start, end, axis, step in zip(starts, ends, axes, steps, strict=True):
            axis = int(axis)
            # Exporters use int64 extrema as open-ended sentinels, while MLX
            # requires 32-bit slice indices. Clamping preserves Python/ONNX
            # negative-step semantics (normalizing -1 would make it empty).
            lower, upper = -(2**31), 2**31 - 1
            start = max(lower, min(upper, int(start)))
            end = max(lower, min(upper, int(end)))
            slices[axis] = slice(start, end, int(step))
        return x[tuple(slices)]

    def _resize(self, x: Any, args: list[Any], attrs: dict[str, Any]) -> Any:
        import mlx.nn as nn

        scales = None
        sizes = None
        if len(args) >= 3 and args[2] is not None and int(np.prod(args[2].shape)):
            scales = [float(v) for v in args[2].tolist()]
        if len(args) >= 4 and args[3] is not None and int(np.prod(args[3].shape)):
            sizes = _ints(args[3])
        spatial_rank = x.ndim - 2
        if sizes is not None:
            scale = tuple(
                sizes[-spatial_rank + index] / x.shape[-spatial_rank + index]
                for index in range(spatial_rank)
            )
        elif scales is not None:
            scale = tuple(scales[-spatial_rank:])
        else:
            raise ValueError("Resize requires scales or sizes")
        mode = attrs.get("mode", b"nearest")
        mode = mode.decode() if isinstance(mode, bytes) else mode
        channels_last = self.mx.transpose(x, (0, *range(2, x.ndim), 1))
        result = nn.Upsample(
            scale_factor=scale,
            mode="linear" if mode == "linear" else "nearest",
            align_corners=False,
        )(channels_last)
        return self.mx.transpose(result, (0, x.ndim - 1, *range(1, x.ndim - 1)))

    def _depth_to_space(self, x: Any, block: int, mode: Any) -> Any:
        mode = mode.decode() if isinstance(mode, bytes) else mode
        batch, channels, height, width = x.shape
        output_channels = channels // (block * block)
        if mode == "CRD":
            value = self.mx.reshape(
                x, (batch, output_channels, block, block, height, width)
            )
            value = self.mx.transpose(value, (0, 1, 4, 2, 5, 3))
        else:
            value = self.mx.reshape(
                x, (batch, block, block, output_channels, height, width)
            )
            value = self.mx.transpose(value, (0, 3, 4, 1, 5, 2))
        return self.mx.reshape(
            value, (batch, output_channels, height * block, width * block)
        )

    def _grid_sample_3d(self, x: Any, grid: Any, attrs: dict[str, Any]) -> Any:
        mx = self.mx
        if x.ndim != 5 or grid.ndim != 5:
            raise NotImplementedError("the experiment currently supports 3D GridSample")
        mode = attrs.get("mode", b"linear")
        mode = mode.decode() if isinstance(mode, bytes) else mode
        padding = attrs.get("padding_mode", b"zeros")
        padding = padding.decode() if isinstance(padding, bytes) else padding
        if mode not in {"linear", "bilinear"} or padding != "zeros":
            raise NotImplementedError(f"GridSample mode={mode}, padding={padding}")
        from .metal_grid_sample import grid_sample_3d_ncdhw

        align_corners = bool(int(attrs.get("align_corners", 0)))
        accelerated = grid_sample_3d_ncdhw(x, grid, align_corners=align_corners)
        if accelerated is not None:
            return accelerated
        batch, channels, depth, height, width = x.shape
        out_depth, out_height, out_width = grid.shape[1:4]
        gx, gy, gz = grid[..., 0], grid[..., 1], grid[..., 2]
        if align_corners:
            px = (gx + 1) * (width - 1) / 2
            py = (gy + 1) * (height - 1) / 2
            pz = (gz + 1) * (depth - 1) / 2
        else:
            px = ((gx + 1) * width - 1) / 2
            py = ((gy + 1) * height - 1) / 2
            pz = ((gz + 1) * depth - 1) / 2
        x0, y0, z0 = mx.floor(px), mx.floor(py), mx.floor(pz)
        x1, y1, z1 = x0 + 1, y0 + 1, z0 + 1
        source = mx.transpose(x, (0, 2, 3, 4, 1)).reshape(-1, channels)
        batch_offsets = mx.arange(batch, dtype=mx.int32).reshape(batch, 1, 1, 1) * (
            depth * height * width
        )

        def corner(ix: Any, iy: Any, iz: Any) -> Any:
            valid = (
                (ix >= 0)
                & (ix < width)
                & (iy >= 0)
                & (iy < height)
                & (iz >= 0)
                & (iz < depth)
            )
            ix = mx.clip(ix, 0, width - 1).astype(mx.int32)
            iy = mx.clip(iy, 0, height - 1).astype(mx.int32)
            iz = mx.clip(iz, 0, depth - 1).astype(mx.int32)
            indices = batch_offsets + iz * (height * width) + iy * width + ix
            values = mx.take(source, indices.reshape(-1), axis=0)
            values = values.reshape(batch, out_depth, out_height, out_width, channels)
            return values * valid[..., None]

        wx, wy, wz = px - x0, py - y0, pz - z0
        result = (
            corner(x0, y0, z0) * ((1 - wx) * (1 - wy) * (1 - wz))[..., None]
            + corner(x1, y0, z0) * (wx * (1 - wy) * (1 - wz))[..., None]
            + corner(x0, y1, z0) * ((1 - wx) * wy * (1 - wz))[..., None]
            + corner(x1, y1, z0) * (wx * wy * (1 - wz))[..., None]
            + corner(x0, y0, z1) * ((1 - wx) * (1 - wy) * wz)[..., None]
            + corner(x1, y0, z1) * (wx * (1 - wy) * wz)[..., None]
            + corner(x0, y1, z1) * ((1 - wx) * wy * wz)[..., None]
            + corner(x1, y1, z1) * (wx * wy * wz)[..., None]
        )
        return mx.transpose(result, (0, 4, 1, 2, 3))

    def _reflect_pad(self, x: Any, pad_width: tuple[tuple[int, int], ...]) -> Any:
        """ONNX/Numpy-style reflection without repeating the edge value."""
        result = x
        for axis, (before, after) in enumerate(pad_width):
            if before > result.shape[axis] - 1 or after > result.shape[axis] - 1:
                raise ValueError(
                    f"reflection pad {(before, after)} exceeds axis {axis} "
                    f"length {result.shape[axis]}"
                )
            pieces = []
            if before:
                indices = self.mx.arange(before, 0, -1, dtype=self.mx.int32)
                pieces.append(self.mx.take(result, indices, axis=axis))
            pieces.append(result)
            if after:
                stop = result.shape[axis] - after - 2
                indices = self.mx.arange(
                    result.shape[axis] - 2, stop, -1, dtype=self.mx.int32
                )
                pieces.append(self.mx.take(result, indices, axis=axis))
            result = self.mx.concatenate(pieces, axis=axis)
        return result

    def _dtype(self, tensor_type: int) -> Any:
        mx = self.mx
        # ONNX TensorProto enum values. The selected graphs only use these.
        mapping = {
            1: mx.float32,
            2: mx.uint8,
            3: mx.int8,
            5: mx.int16,
            6: mx.int32,
            7: mx.int64,
            9: mx.bool_,
            10: mx.float16,
            11: mx.float64,
        }
        if tensor_type not in mapping:
            raise NotImplementedError(f"unsupported ONNX Cast target {tensor_type}")
        return mapping[tensor_type]

    def evaluate(self, values: Iterable[Any]) -> None:
        """Materialize one or more graph outputs on the Metal device."""
        self.mx.eval(*tuple(values))
