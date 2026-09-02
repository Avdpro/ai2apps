#!/usr/bin/env python3
"""Convert Ideogram 4 scalar-scaled FP8 weights to native MLX Q8/Q4 files."""

from __future__ import annotations

import argparse
import gc
import json
import mmap
import struct
import time
from pathlib import Path

import mlx.core as mx
import numpy as np

COMPONENTS = {
    "conditional": "diffusion_models/ideogram4_fp8_scaled.safetensors",
    "unconditional": "diffusion_models/ideogram4_unconditional_fp8_scaled.safetensors",
    "text_encoder": "text_encoders/qwen3vl_8b_fp8_scaled.safetensors",
    "vae": "vae/flux2-vae.safetensors",
}
NUMPY_DTYPES = {
    "F32": np.dtype("<f4"),
    "F16": np.dtype("<f2"),
    "I64": np.dtype("<i8"),
    "U8": np.dtype("u1"),
}


def decode_float8_e4m3fn(buffer: memoryview) -> np.ndarray:
    """Decode safetensors F8_E4M3 without adding a runtime dtype dependency."""
    encoded = np.frombuffer(buffer, dtype=np.uint8)
    sign = np.where(encoded & 0x80, -1.0, 1.0).astype(np.float32)
    exponent = (encoded >> 3) & 0x0F
    mantissa = encoded & 0x07
    subnormal = mantissa.astype(np.float32) * (2.0**-9)
    normal = np.exp2(exponent.astype(np.float32) - 7.0) * (
        1.0 + mantissa.astype(np.float32) / 8.0
    )
    decoded = np.where(exponent == 0, subnormal, normal).astype(np.float32)
    decoded *= sign
    decoded[(exponent == 0x0F) & (mantissa == 0x07)] = np.nan
    return decoded


class SafeTensorReader:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._stream = path.open("rb")
        self._mapping = mmap.mmap(self._stream.fileno(), 0, access=mmap.ACCESS_READ)
        header_size = struct.unpack("<Q", self._mapping[:8])[0]
        self.data_offset = 8 + header_size
        self.header = json.loads(self._mapping[8 : self.data_offset])

    def close(self) -> None:
        self._mapping.close()
        self._stream.close()

    def array(self, name: str) -> np.ndarray:
        record = self.header[name]
        start, end = record["data_offsets"]
        buffer = memoryview(self._mapping)[self.data_offset + start : self.data_offset + end]
        dtype = record["dtype"]
        if dtype == "BF16":
            bits = np.frombuffer(buffer, dtype="<u2").astype(np.uint32)
            result = (bits << 16).view(np.float32)
        elif dtype == "F8_E4M3":
            result = decode_float8_e4m3fn(buffer)
        else:
            try:
                result = np.frombuffer(buffer, dtype=NUMPY_DTYPES[dtype])
            except KeyError as exc:
                raise ValueError(f"unsupported safetensors dtype {dtype}") from exc
        return result.reshape(record["shape"])

    def tensor_names(self) -> list[str]:
        return sorted(name for name in self.header if name != "__metadata__")


def output_tensor_name(source: Path, name: str) -> str | None:
    if source.name != "qwen3vl_8b_fp8_scaled.safetensors":
        return name
    retained_prefixes = ("model.embed_tokens.", "model.layers.", "model.norm.")
    if not name.startswith(retained_prefixes):
        return None
    return name.removeprefix("model.")


def convert_component(
    source: Path,
    output: Path,
    *,
    bits: int,
    group_size: int,
) -> dict[str, object]:
    reader = SafeTensorReader(source)
    converted: dict[str, mx.array] = {}
    quantized_layers = 0
    started = time.perf_counter()
    try:
        names = reader.tensor_names()
        fp8_weights = [
            name
            for name in names
            if reader.header[name]["dtype"] == "F8_E4M3"
            and name.endswith(".weight")
            and output_tensor_name(source, name) is not None
        ]
        for index, name in enumerate(fp8_weights, start=1):
            scale_name = name.removesuffix(".weight") + ".weight_scale"
            if scale_name not in reader.header:
                raise RuntimeError(f"missing FP8 scale for {name}")
            weight = reader.array(name)
            scale = float(reader.array(scale_name).item())
            weight = np.asarray(weight * scale, dtype=np.float32)
            mlx_weight = mx.array(weight).astype(mx.bfloat16)
            output_name = output_tensor_name(source, name)
            assert output_name is not None
            if bits == 16:
                converted[output_name] = mlx_weight
                mx.eval(mlx_weight)
            else:
                packed, scales, biases = mx.quantize(
                    mlx_weight,
                    group_size=group_size,
                    bits=bits,
                )
                prefix = output_name.removesuffix(".weight")
                converted[output_name] = packed
                converted[prefix + ".scales"] = scales
                converted[prefix + ".biases"] = biases
                mx.eval(packed, scales, biases)
                quantized_layers += 1
                del packed, scales, biases
            del weight, mlx_weight
            if index % 16 == 0 or index == len(fp8_weights):
                print(f"{source.name}: converted {index}/{len(fp8_weights)}", flush=True)

        skip = {
            name.removesuffix(".weight") + ".weight_scale" for name in fp8_weights
        }
        skip.update(
            name.removesuffix(".weight") + ".comfy_quant" for name in fp8_weights
        )
        for name in names:
            output_name = output_tensor_name(source, name)
            if output_name is None or output_name in converted or name in skip:
                continue
            dtype = reader.header[name]["dtype"]
            if dtype == "U8" and name.endswith(".comfy_quant"):
                continue
            array = mx.array(np.array(reader.array(name), copy=True))
            if dtype == "BF16":
                array = array.astype(mx.bfloat16)
            converted[output_name] = array
            mx.eval(array)

        output.parent.mkdir(parents=True, exist_ok=True)
        metadata = {
            "format": (
                "ai2apps.ideogram4-mlx-bf16/v1"
                if bits == 16
                else "ai2apps.ideogram4-mlx-quantized/v1"
            ),
            "source": source.name,
            "bits": str(bits),
            "group_size": str(group_size),
        }
        mx.save_safetensors(str(output), converted, metadata=metadata)
        size = output.stat().st_size
    finally:
        reader.close()
        converted.clear()
        gc.collect()
        mx.clear_cache()
    return {
        "source": str(source),
        "output": str(output),
        "bits": bits,
        "group_size": group_size,
        "quantized_layers": quantized_layers,
        "output_bytes": size,
        "seconds": time.perf_counter() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bits", type=int, choices=(4, 8, 16), default=8)
    parser.add_argument("--group-size", type=int, choices=(32, 64, 128), default=64)
    parser.add_argument("--component", choices=COMPONENTS, action="append")
    args = parser.parse_args()

    selected = args.component or list(COMPONENTS)
    reports = []
    for component in selected:
        source = args.source / COMPONENTS[component]
        if not source.is_file():
            raise FileNotFoundError(source)
        reports.append(
            convert_component(
                source,
                args.output / f"{component}-q{args.bits}.safetensors",
                bits=args.bits,
                group_size=args.group_size,
            )
        )
    report = {
        "format": "ai2apps.ideogram4-mlx-conversion/v1",
        "components": reports,
    }
    (args.output / "conversion.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
