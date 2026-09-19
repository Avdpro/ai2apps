#!/usr/bin/env python3
"""Convert ONNX floating tensors and interface types to float16."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper


def _convert_tensor(value: onnx.TensorProto) -> onnx.TensorProto:
    if value.data_type != onnx.TensorProto.FLOAT:
        return value
    return numpy_helper.from_array(
        np.asarray(numpy_helper.to_array(value), dtype=np.float16), name=value.name
    )


def _convert_type(value: onnx.ValueInfoProto) -> None:
    tensor = value.type.tensor_type
    if tensor.elem_type == onnx.TensorProto.FLOAT:
        tensor.elem_type = onnx.TensorProto.FLOAT16


def _convert_graph(graph: onnx.GraphProto) -> None:
    for index, value in enumerate(graph.initializer):
        graph.initializer[index].CopyFrom(_convert_tensor(value))
    for value in (*graph.input, *graph.output, *graph.value_info):
        _convert_type(value)
    for node in graph.node:
        for attribute in node.attribute:
            if attribute.type == onnx.AttributeProto.TENSOR:
                attribute.t.CopyFrom(_convert_tensor(attribute.t))
            elif attribute.type == onnx.AttributeProto.GRAPH:
                _convert_graph(attribute.g)
            elif attribute.type == onnx.AttributeProto.GRAPHS:
                for child in attribute.graphs:
                    _convert_graph(child)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    model = onnx.load(str(args.source), load_external_data=True)
    _convert_graph(model.graph)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, str(args.destination))
    onnx.checker.check_model(str(args.destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
