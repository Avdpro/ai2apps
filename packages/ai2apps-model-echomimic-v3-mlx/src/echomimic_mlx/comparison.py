"""Chunked numerical comparison for M0/M1 reference tensor exports."""

from __future__ import annotations

import json
import math
import mmap
import struct
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .config import Block0AcceptanceThresholds
from .torch_capture import AUDIO_PROJECTION_REFERENCE_NAMES, BLOCK0_REFERENCE_NAMES

_NUMPY_DTYPES = {
    "BOOL": np.dtype("?"),
    "I8": np.dtype("i1"),
    "U8": np.dtype("u1"),
    "I16": np.dtype("<i2"),
    "U16": np.dtype("<u2"),
    "F16": np.dtype("<f2"),
    "I32": np.dtype("<i4"),
    "U32": np.dtype("<u4"),
    "F32": np.dtype("<f4"),
    "I64": np.dtype("<i8"),
    "U64": np.dtype("<u8"),
    "F64": np.dtype("<f8"),
    "BF16": np.dtype("<u2"),
}


@dataclass(frozen=True, slots=True)
class TensorComparison:
    """Comparison result for one logical tensor."""

    name: str
    status: str
    left_shape: list[int] | None = None
    right_shape: list[int] | None = None
    left_dtype: str | None = None
    right_dtype: str | None = None
    elements: int | None = None
    max_absolute: float | None = None
    mean_absolute: float | None = None
    relative_l2: float | None = None
    cosine: float | None = None
    finite_fraction_left: float | None = None
    finite_fraction_right: float | None = None


def _read_manifest(directory: Path) -> dict[str, Any]:
    value = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("tensors"), list):
        raise ValueError(f"invalid reference manifest: {directory / 'manifest.json'}")
    return value


def _tensor_records(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in manifest["tensors"]:
        if not isinstance(value, dict) or not isinstance(value.get("name"), str):
            raise ValueError("reference manifest has an invalid tensor record")
        name = value["name"]
        if name in result:
            raise ValueError(f"reference manifest has duplicate tensor name: {name}")
        result[name] = value
    return result


class _Payload:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._stream = path.open("rb")
        header_size_bytes = self._stream.read(8)
        if len(header_size_bytes) != 8:
            raise ValueError(f"truncated Safetensors header: {path}")
        header_size = struct.unpack("<Q", header_size_bytes)[0]
        header = json.loads(self._stream.read(header_size))
        tensor_names = [name for name in header if name != "__metadata__"]
        if tensor_names != ["tensor"]:
            raise ValueError(f"reference payload must contain exactly the 'tensor' key: {path}")
        descriptor = header["tensor"]
        self.dtype_name = descriptor["dtype"]
        if self.dtype_name not in _NUMPY_DTYPES:
            raise ValueError(f"unsupported payload dtype {self.dtype_name}: {path}")
        self.shape = [int(value) for value in descriptor["shape"]]
        self.elements = math.prod(self.shape)
        start, end = descriptor["data_offsets"]
        self.data_offset = 8 + header_size + int(start)
        self.data_bytes = int(end) - int(start)
        expected_bytes = self.elements * _NUMPY_DTYPES[self.dtype_name].itemsize
        if self.data_bytes != expected_bytes:
            raise ValueError(f"payload byte length does not match shape/dtype: {path}")
        self._mapping = mmap.mmap(self._stream.fileno(), 0, access=mmap.ACCESS_READ)

    def close(self) -> None:
        self._mapping.close()
        self._stream.close()

    def chunk(self, start: int, count: int) -> np.ndarray[Any, Any]:
        dtype = _NUMPY_DTYPES[self.dtype_name]
        offset = self.data_offset + start * dtype.itemsize
        values = np.frombuffer(self._mapping, dtype=dtype, count=count, offset=offset)
        if self.dtype_name == "BF16":
            bits = values.astype(np.uint32) << 16
            return bits.view(np.float32)
        return values

    def __enter__(self) -> _Payload:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _compare_payloads(
    name: str,
    left_path: Path,
    right_path: Path,
    left_record: dict[str, Any],
    right_record: dict[str, Any],
    chunk_elements: int,
) -> TensorComparison:
    with _Payload(left_path) as left, _Payload(right_path) as right:
        if left.shape != right.shape:
            return TensorComparison(
                name,
                "shape_mismatch",
                left.shape,
                right.shape,
                left_record.get("dtype"),
                right_record.get("dtype"),
            )
        count = left.elements
        maximum = 0.0
        absolute_sum = 0.0
        error_square_sum = 0.0
        right_square_sum = 0.0
        dot_sum = 0.0
        left_square_sum = 0.0
        finite_left = 0
        finite_right = 0
        comparable_count = 0
        for start in range(0, count, chunk_elements):
            length = min(chunk_elements, count - start)
            left_values = left.chunk(start, length).astype(np.float64)
            right_values = right.chunk(start, length).astype(np.float64)
            left_finite = np.isfinite(left_values)
            right_finite = np.isfinite(right_values)
            finite_left += int(left_finite.sum())
            finite_right += int(right_finite.sum())
            comparable = left_finite & right_finite
            comparable_count += int(comparable.sum())
            if not comparable.any():
                continue
            left_numbers = left_values[comparable]
            right_numbers = right_values[comparable]
            difference = left_numbers - right_numbers
            absolute = np.abs(difference)
            maximum = max(maximum, float(absolute.max(initial=0.0)))
            absolute_sum += float(absolute.sum())
            error_square_sum += float(np.dot(difference, difference))
            right_square_sum += float(np.dot(right_numbers, right_numbers))
            left_square_sum += float(np.dot(left_numbers, left_numbers))
            dot_sum += float(np.dot(left_numbers, right_numbers))
        denominator = math.sqrt(left_square_sum * right_square_sum)
        status = (
            "dtype_mismatch"
            if left_record.get("dtype") != right_record.get("dtype")
            else "compared"
        )
        return TensorComparison(
            name=name,
            status=status,
            left_shape=left.shape,
            right_shape=right.shape,
            left_dtype=left_record.get("dtype"),
            right_dtype=right_record.get("dtype"),
            elements=count,
            max_absolute=maximum,
            mean_absolute=absolute_sum / comparable_count if comparable_count else None,
            relative_l2=(
                math.sqrt(error_square_sum / right_square_sum)
                if right_square_sum
                else (0.0 if error_square_sum == 0.0 else None)
            ),
            cosine=dot_sum / denominator if denominator else None,
            finite_fraction_left=finite_left / count if count else 1.0,
            finite_fraction_right=finite_right / count if count else 1.0,
        )


def compare_reference_exports(
    left_directory: Path,
    right_directory: Path,
    *,
    chunk_elements: int = 1_048_576,
) -> dict[str, object]:
    """Compare common payloads and report missing/schema-only tensors."""

    if chunk_elements <= 0:
        raise ValueError("chunk_elements must be positive")
    left_directory = left_directory.expanduser().resolve()
    right_directory = right_directory.expanduser().resolve()
    left_records = _tensor_records(_read_manifest(left_directory))
    right_records = _tensor_records(_read_manifest(right_directory))
    comparisons: list[TensorComparison] = []
    for name in sorted(left_records.keys() | right_records.keys()):
        left = left_records.get(name)
        right = right_records.get(name)
        if left is None:
            comparisons.append(TensorComparison(name, "missing_left"))
            continue
        if right is None:
            comparisons.append(TensorComparison(name, "missing_right"))
            continue
        left_shape = left.get("shape")
        right_shape = right.get("shape")
        if left_shape != right_shape:
            comparisons.append(
                TensorComparison(
                    name,
                    "shape_mismatch",
                    left_shape,
                    right_shape,
                    left.get("dtype"),
                    right.get("dtype"),
                )
            )
            continue
        left_file = left.get("file")
        right_file = right.get("file")
        if not isinstance(left_file, str) or not isinstance(right_file, str):
            comparisons.append(
                TensorComparison(
                    name,
                    "payload_missing",
                    left_shape,
                    right_shape,
                    left.get("dtype"),
                    right.get("dtype"),
                )
            )
            continue
        comparisons.append(
            _compare_payloads(
                name,
                left_directory / left_file,
                right_directory / right_file,
                left,
                right,
                chunk_elements,
            )
        )
    counts: dict[str, int] = {}
    for comparison in comparisons:
        counts[comparison.status] = counts.get(comparison.status, 0) + 1
    return {
        "protocol": {"name": "echomimic-mlx-comparison", "version": 1},
        "left": str(left_directory),
        "right": str(right_directory),
        "summary": dict(sorted(counts.items())),
        "tensors": [asdict(value) for value in comparisons],
    }


def write_comparison_report(report: dict[str, object], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return output


def validate_complete_block0_comparison(report: dict[str, object]) -> dict[str, object]:
    """Require complete, finite, and numerically accepted real block-0 parity."""

    values = report.get("tensors")
    if not isinstance(values, list):
        raise ValueError("comparison report tensors must be a list")
    records: dict[str, dict[str, object]] = {}
    for value in values:
        if not isinstance(value, dict) or not isinstance(value.get("name"), str):
            raise ValueError("comparison report contains an invalid tensor record")
        name = value["name"]
        if name in records:
            raise ValueError(f"comparison report contains duplicate tensor: {name}")
        records[name] = value
    required_names = BLOCK0_REFERENCE_NAMES | AUDIO_PROJECTION_REFERENCE_NAMES
    missing = sorted(required_names - records.keys())
    if missing:
        raise ValueError(f"comparison report is missing required block-0 stages: {missing}")

    exact_inputs = {
        "transformer.block_00.input",
        "transformer.block_00.timestep_modulation",
        "transformer.block_00.sequence_lengths",
        "transformer.block_00.grid_sizes",
        "transformer.block_00.context",
        "transformer.block_00.audio_context",
        "transformer.audio_projection.first_frame_input",
        "transformer.audio_projection.later_frame_input",
    }
    thresholds = Block0AcceptanceThresholds()
    observed_relative_l2: list[float] = []
    observed_cosine: list[float] = []
    for name in sorted(required_names):
        record = records[name]
        if record.get("status") != "compared":
            raise ValueError(f"block-0 tensor is not numerically comparable: {name}")
        if record.get("finite_fraction_left") != 1.0 or record.get("finite_fraction_right") != 1.0:
            raise ValueError(f"block-0 tensor contains non-finite values: {name}")
        if not isinstance(record.get("max_absolute"), (float, int)):
            raise ValueError(f"block-0 tensor has no numerical metrics: {name}")
        if name in exact_inputs and record.get("max_absolute") != 0.0:
            raise ValueError(f"MLX did not preserve the exact reference input payload: {name}")
        if name not in exact_inputs:
            relative_l2 = record.get("relative_l2")
            cosine = record.get("cosine")
            if not isinstance(relative_l2, (float, int)) or not isinstance(cosine, (float, int)):
                raise ValueError(f"block-0 tensor has incomplete acceptance metrics: {name}")
            relative_limit = (
                thresholds.max_output_relative_l2
                if name == "transformer.block_00.output"
                else thresholds.max_stage_relative_l2
            )
            cosine_limit = (
                thresholds.min_output_cosine
                if name == "transformer.block_00.output"
                else thresholds.min_stage_cosine
            )
            if relative_l2 > relative_limit or cosine < cosine_limit:
                raise ValueError(
                    f"block-0 tensor exceeds BF16 acceptance threshold: {name} "
                    f"(relative_l2={relative_l2}, cosine={cosine})"
                )
            observed_relative_l2.append(float(relative_l2))
            observed_cosine.append(float(cosine))
    return {
        "required_stage_count": len(required_names),
        "exact_input_count": len(exact_inputs),
        "all_finite": True,
        "all_stages_comparable": True,
        "acceptance_thresholds": thresholds.as_dict(),
        "max_observed_relative_l2": max(observed_relative_l2),
        "min_observed_cosine": min(observed_cosine),
    }
