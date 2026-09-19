#!/usr/bin/env python3
"""Convert ONNX graph metadata and tensors into a parser-free MLX bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from onnx import numpy_helper
from safetensors.numpy import save_file


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_model(
    source: Path, destination: Path, *, expected_sha256: str | None = None
) -> None:
    source_sha256 = _sha256(source)
    if expected_sha256 is not None and source_sha256 != expected_sha256:
        raise ValueError(
            f"source hash mismatch for {source}: "
            f"expected {expected_sha256}, got {source_sha256}"
        )
    model = onnx.load(str(source), load_external_data=True)
    tensors: dict[str, np.ndarray] = {}

    def tensor(value: Any, key: str) -> dict[str, Any]:
        array = np.asarray(numpy_helper.to_array(value))
        tensors[key] = np.ascontiguousarray(
            array.reshape(1) if array.ndim == 0 else array
        )
        return {"__tensor__": key, "shape": list(array.shape)}

    def attr(value: Any, key: str) -> Any:
        if isinstance(value, onnx.TensorProto):
            return tensor(value, key)
        if isinstance(value, onnx.GraphProto):
            return {"__graph__": graph(value, key)}
        if isinstance(value, bytes):
            return value.decode("utf-8")
        if isinstance(value, tuple):
            return [attr(item, f"{key}.{index}") for index, item in enumerate(value)]
        if isinstance(value, list):
            return [attr(item, f"{key}.{index}") for index, item in enumerate(value)]
        if isinstance(value, np.generic):
            return value.item()
        return value

    def graph(value: onnx.GraphProto, prefix: str) -> dict[str, Any]:
        initializers = {}
        for index, item in enumerate(value.initializer):
            key = f"{prefix}.initializer.{index}"
            initializers[item.name] = tensor(item, key)
        nodes = []
        for index, item in enumerate(value.node):
            nodes.append(
                {
                    "name": item.name or f"{item.op_type}_{index}",
                    "op": item.op_type,
                    "inputs": list(item.input),
                    "outputs": list(item.output),
                    "attrs": {
                        entry.name: attr(
                            onnx.helper.get_attribute_value(entry),
                            f"{prefix}.node.{index}.attr.{entry.name}",
                        )
                        for entry in item.attribute
                    },
                }
            )
        return {
            "inputs": [item.name for item in value.input],
            "outputs": [item.name for item in value.output],
            "initializers": initializers,
            "nodes": nodes,
        }

    payload = graph(model.graph, "graph")
    payload["schema_version"] = 1
    payload["opset"] = max((item.version for item in model.opset_import), default=0)
    payload["source_filename"] = source.name
    destination.mkdir(parents=True, exist_ok=True)
    save_file(tensors, destination / "weights.safetensors")
    (destination / "graph.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    graph_path = destination / "graph.json"
    weights_path = destination / "weights.safetensors"
    bundle_manifest = {
        "schema_version": 1,
        "format": "ai2apps.omlx.graph",
        "source_filename": source.name,
        "source_sha256": source_sha256,
        "graph": {
            "filename": graph_path.name,
            "sha256": _sha256(graph_path),
            "size": graph_path.stat().st_size,
        },
        "weights": {
            "filename": weights_path.name,
            "sha256": _sha256(weights_path),
            "size": weights_path.stat().st_size,
        },
    }
    (destination / "bundle.json").write_text(
        json.dumps(bundle_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    export_model(args.source, args.destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
