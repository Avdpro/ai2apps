"""AVTR SPADE graph with persistent NHWC activations and prepacked weights."""

import mlx.core as mx


class FastDecoder:
    def __init__(self, graph, *, dtype=mx.float32):
        if dtype not in (mx.float32, mx.float16):
            raise ValueError("Decoder supports FP32 or scaled FP16 convolutions")
        self.nodes = graph.nodes
        self.inputs = graph.inputs
        self.outputs = graph.outputs
        self.dtype = dtype
        supported = {
            "Conv",
            "Add",
            "Relu",
            "Mul",
            "LeakyRelu",
            "InstanceNormalization",
            "Resize",
            "DepthToSpace",
            "Sigmoid",
        }
        if any(n.op not in supported for n in self.nodes):
            raise ValueError("Unexpected decoder architecture")
        self.weights = {}
        for k, v in graph.initializers.items():
            self.weights[k] = v.transpose(0, 2, 3, 1) if v.ndim == 4 else v
        for n in self.nodes:
            if n.op == "Conv":
                self.weights[n.inputs[1]] = self.weights[n.inputs[1]].astype(dtype)
        mx.eval(self.weights)
        self.forward = mx.compile(self._forward)

    def _forward(self, feature):
        values = dict(self.weights)
        values[self.inputs[0]] = feature.transpose(0, 2, 3, 1)
        for node in self.nodes:
            args = [values[k] if k else None for k in node.inputs]
            x = args[0]
            a = node.attrs
            op = node.op
            if op == "Conv":
                pads = a.get("pads", [0] * 4)
                if pads[:2] != pads[2:]:
                    raise ValueError("Asymmetric decoder padding")
                # Power-of-two scaling prevents the FP16 convolution output from
                # overflowing. Bias, residuals and normalization remain FP32.
                scale = 256.0 if self.dtype == mx.float16 else 1.0
                out = (
                    mx.conv2d(
                        (x / scale).astype(self.dtype),
                        args[1],
                        stride=tuple(a.get("strides", [1, 1])),
                        padding=tuple(pads[:2]),
                        dilation=tuple(a.get("dilations", [1, 1])),
                        groups=a.get("group", 1),
                    ).astype(mx.float32)
                    * scale
                )
                if len(args) > 2:
                    out = out + args[2]
            elif op == "Add":
                out = x + args[1]
            elif op == "Mul":
                out = x * args[1]
            elif op == "Relu":
                out = mx.maximum(x, 0)
            elif op == "LeakyRelu":
                out = mx.maximum(x, 0) + float(a.get("alpha", 0.01)) * mx.minimum(x, 0)
            elif op == "Sigmoid":
                out = mx.sigmoid(x)
            elif op == "InstanceNormalization":
                mean = mx.mean(x, axis=(1, 2), keepdims=True)
                out = (x - mean) * mx.rsqrt(
                    mx.mean((x - mean) ** 2, axis=(1, 2), keepdims=True)
                    + a.get("epsilon", 1e-5)
                )
                out = out * args[1] + args[2]
            elif op == "Resize":
                if a.get("mode", "nearest") not in {"nearest", b"nearest"}:
                    raise ValueError("Non-nearest decoder resize")
                scales = (
                    args[2].tolist()
                    if args[2] is not None
                    else [
                        1.0,
                        1.0,
                        args[3].tolist()[2] / x.shape[1],
                        args[3].tolist()[3] / x.shape[2],
                    ]
                )
                fh, fw = int(scales[2]), int(scales[3])
                if scales != [1.0, 1.0, float(fh), float(fw)]:
                    raise ValueError("Non-integer decoder resize")
                b, h, w, c = x.shape
                out = mx.broadcast_to(
                    x[:, :, None, :, None, :], (b, h, fh, w, fw, c)
                ).reshape(b, h * fh, w * fw, c)
            elif op == "DepthToSpace":
                b, h, w, c = x.shape
                r = a["blocksize"]
                c //= r * r
                if a.get("mode", "DCR") in {"CRD", b"CRD"}:
                    out = x.reshape(b, h, w, c, r, r).transpose(0, 1, 4, 2, 5, 3)
                else:
                    out = x.reshape(b, h, w, r, r, c).transpose(0, 1, 3, 2, 4, 5)
                out = out.reshape(b, h * r, w * r, c)
            values[node.outputs[0]] = out
        return values[self.outputs[0]].transpose(0, 3, 1, 2)

    def __call__(self, feature):
        return self.forward(feature)
