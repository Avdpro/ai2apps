"""Create a portable AVTR MLX checkpoint: graph JSON + safetensors, no ONNX at runtime."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper
from safetensors.numpy import save_file


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def convert(source, output):
    model = onnx.load(str(source))
    weights = {}

    def tensor(value):
        array = np.array(numpy_helper.to_array(value), copy=True)
        key = f"tensor_{len(weights)}"
        weights[key] = array.reshape(1) if array.ndim == 0 else array
        return {"__tensor__": key, "shape": list(array.shape)}

    def attribute(value):
        if isinstance(value, onnx.TensorProto):
            return tensor(value)
        if isinstance(value, onnx.GraphProto):
            return {"__graph__": graph(value)}
        if isinstance(value, bytes):
            return value.decode("utf-8")
        if isinstance(value, (tuple, list)):
            return [attribute(v) for v in value]
        return value

    def graph(value):
        return {
            "inputs": [v.name for v in value.input],
            "outputs": [v.name for v in value.output],
            "initializers": {v.name: tensor(v) for v in value.initializer},
            "nodes": [
                {
                    "name": n.name or f"{n.op_type}_{i}",
                    "op": n.op_type,
                    "inputs": list(n.input),
                    "outputs": list(n.output),
                    "attrs": {
                        a.name: attribute(onnx.helper.get_attribute_value(a))
                        for a in n.attribute
                    },
                }
                for i, n in enumerate(value.node)
            ],
        }

    manifest = graph(model.graph)
    manifest.update(schema_version=1, opset=max(v.version for v in model.opset_import))
    output.mkdir(parents=True)
    (output / "graph.json").write_text(json.dumps(manifest))
    save_file(weights, str(output / "weights.safetensors"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    package = Path(__file__).resolve().parents[1]
    lock = json.loads((package / "checkpoint-assets.json").read_text())
    for asset in lock["assets"]:
        if not asset["path"].endswith(".onnx"):
            continue
        source = args.source / asset["path"]
        if digest(source) != asset["sha256"]:
            raise ValueError("Source hash mismatch: " + asset["path"])
        name = "hubert" if source.name.startswith("hubert") else source.stem
        convert(source, args.output / "graphs" / name)
    for name in ("motion.safetensors", "model_config.json", "conversion.json"):
        shutil.copyfile(args.source / name, args.output / name)
    conversion = json.loads((args.output / "conversion.json").read_text())
    for name, field in [
        ("motion.safetensors", "weights_sha256"),
        ("model_config.json", "config_sha256"),
    ]:
        if digest(args.output / name) != conversion[field]:
            raise ValueError("Converted motion digest mismatch")
    (args.output / "config.json").write_text(
        json.dumps({"model_type": "avtr1-mlx", "layout_version": 1})
    )
    files = [
        {
            "path": str(p.relative_to(args.output)),
            "size": p.stat().st_size,
            "sha256": digest(p),
        }
        for p in sorted(args.output.rglob("*"))
        if p.is_file()
    ]
    manifest = {
        "schema": "ai2apps.avtr1-mlx-checkpoint/v1",
        "files": files,
        "sources": lock,
        "conversion": conversion,
    }
    (args.output / "ai2apps-checkpoint.json").write_text(json.dumps(manifest, indent=2))
    print(
        json.dumps(
            {
                "files": len(files),
                "size": sum(f["size"] for f in files),
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
