"""Versioned tensor export protocol for PyTorch-to-MLX parity work."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, cast

import numpy as np
from safetensors.numpy import save_file as save_numpy_file

from .config import ReferenceConfiguration

PROTOCOL_NAME = "echomimic-mlx-reference"
PROTOCOL_VERSION = 1
UPSTREAM_REPOSITORY = "https://github.com/antgroup/echomimic_v3"
UPSTREAM_COMMIT = "7e89489ca51c0d008fc1963ec6c03fc5bd0b9397"

_TENSOR_NAME = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*$")


@dataclass(frozen=True, slots=True)
class TensorStatistics:
    """Portable summary used to diagnose parity before loading tensor payloads."""

    minimum: float | None
    maximum: float | None
    mean: float | None
    standard_deviation: float | None
    finite_fraction: float | None


@dataclass(frozen=True, slots=True)
class TensorRecord:
    """One tensor entry in a reference manifest."""

    name: str
    shape: list[int]
    dtype: str
    numel: int
    nbytes: int
    tensor_sha256: str
    file: str | None
    file_sha256: str | None
    statistics: TensorStatistics


def _is_torch_tensor(value: object) -> bool:
    return any(
        value_type.__module__.startswith("torch") and value_type.__name__ == "Tensor"
        for value_type in type(value).__mro__
    )


def _is_mlx_array(value: object) -> bool:
    return type(value).__module__ == "mlx.core" and type(value).__name__ == "array"


def _numpy_array(value: object, *, for_statistics: bool = False) -> np.ndarray[Any, Any]:
    if isinstance(value, np.ndarray):
        array = value
    elif _is_torch_tensor(value):
        tensor = value.detach().cpu().contiguous()  # type: ignore[attr-defined]
        if for_statistics:
            tensor = tensor.float()
        # PyTorch 2.13 on ARM64 exposes a scalar through NumPy as shape ``(1,)``
        # even though the tensor and its Safetensors payload are zero-dimensional.
        # Restore the authoritative Torch shape so manifest and payload agree.
        array = tensor.numpy().reshape(tuple(tensor.shape))
    elif _is_mlx_array(value):
        import mlx.core as mx

        mlx_value = cast(Any, value)
        array = np.asarray(mlx_value.astype(mx.float32) if for_statistics else mlx_value)
    else:
        array = np.asarray(value)
    # NumPy's ascontiguousarray also promotes a zero-dimensional array to `(1,)`.
    # Reshape back after materializing contiguous storage to preserve scalar schema.
    return np.ascontiguousarray(array).reshape(array.shape)


def _tensor_bytes(value: object) -> bytes:
    if _is_torch_tensor(value):
        tensor = value.detach().cpu().contiguous()  # type: ignore[attr-defined]
        # PyTorch forbids changing element size through ``view(dtype=...)`` on a
        # zero-dimensional tensor. Flattening preserves the same contiguous bytes
        # while supporting scalar scheduler timesteps.
        return cast(
            bytes,
            tensor.reshape(-1).view(dtype=__import__("torch").uint8).numpy().tobytes(),
        )
    if _is_mlx_array(value):
        import mlx.core as mx

        flattened = mx.reshape(cast(Any, value), (-1,))
        return np.asarray(mx.view(flattened, mx.uint8)).tobytes()
    return _numpy_array(value).tobytes(order="C")


def _dtype_name(value: object) -> str:
    if _is_torch_tensor(value):
        return str(value.dtype).removeprefix("torch.")  # type: ignore[attr-defined]
    if _is_mlx_array(value):
        return str(value.dtype).removeprefix("mlx.core.")  # type: ignore[attr-defined]
    return str(_numpy_array(value).dtype)


def _statistics(value: object) -> TensorStatistics:
    array = _numpy_array(value, for_statistics=True)
    if array.size == 0 or not np.issubdtype(array.dtype, np.number):
        return TensorStatistics(None, None, None, None, None)
    numeric = array.astype(np.float64, copy=False)
    finite = np.isfinite(numeric)
    finite_fraction = float(finite.mean())
    if not finite.any():
        return TensorStatistics(None, None, None, None, finite_fraction)
    finite_values = numeric[finite]
    return TensorStatistics(
        minimum=float(finite_values.min()),
        maximum=float(finite_values.max()),
        mean=float(finite_values.mean()),
        standard_deviation=float(finite_values.std()),
        finite_fraction=finite_fraction,
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _payload_filename(name: str) -> str:
    prefix = hashlib.sha256(name.encode()).hexdigest()[:12]
    return f"tensors/{prefix}-{name}.safetensors"


def _validate_sha256(value: object, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{field} must be a 64-character SHA-256")
    try:
        int(value, 16)
    except ValueError as error:
        raise ValueError(f"{field} must contain hexadecimal SHA-256 characters") from error


def validate_run_metadata(value: object) -> dict[str, Any]:
    """Validate and normalize metadata for the fixed M0 reference run."""

    if not isinstance(value, dict):
        raise TypeError("metadata must be a JSON object")
    required = {"input", "configuration", "model_artifacts"}
    missing = sorted(required - value.keys())
    if missing:
        raise ValueError(f"metadata is missing required fields: {', '.join(missing)}")

    configuration = value["configuration"]
    if not isinstance(configuration, dict):
        raise TypeError("metadata.configuration must be a JSON object")
    expected_configuration = ReferenceConfiguration().as_dict()
    missing_configuration = sorted(expected_configuration.keys() - configuration.keys())
    if missing_configuration:
        raise ValueError(
            "metadata.configuration is missing fixed fields: " + ", ".join(missing_configuration)
        )
    parsed_configuration = ReferenceConfiguration(**configuration)
    if parsed_configuration.as_dict() != expected_configuration:
        raise ValueError("metadata.configuration does not match the fixed M0 reference run")

    input_hashes = value["input"]
    if not isinstance(input_hashes, dict):
        raise TypeError("metadata.input must be a JSON object")
    for field in ("image_sha256", "audio_sha256", "prompt_sha256"):
        _validate_sha256(input_hashes.get(field), f"metadata.input.{field}")

    model_artifacts = value["model_artifacts"]
    if not isinstance(model_artifacts, dict) or not model_artifacts:
        raise ValueError("metadata.model_artifacts must be a non-empty JSON object")
    for artifact, digest in model_artifacts.items():
        _validate_sha256(digest, f"metadata.model_artifacts.{artifact}")
    return value


def _save_tensor(path: Path, name: str, value: object) -> None:
    metadata = {"logical_name": name, "protocol_version": str(PROTOCOL_VERSION)}
    if _is_torch_tensor(value):
        from safetensors.torch import save_file as save_torch_file

        tensor = value.detach().cpu().contiguous()  # type: ignore[attr-defined]
        save_torch_file({"tensor": tensor}, str(path), metadata=metadata)
        return
    if _is_mlx_array(value):
        import mlx.core as mx

        mx.save_safetensors(path, {"tensor": value}, metadata)  # type: ignore[dict-item]
        return
    save_numpy_file({"tensor": _numpy_array(value)}, str(path), metadata=metadata)


class ReferenceWriter:
    """Write a self-describing, immutable directory of parity tensors.

    The destination must not already exist. This prevents a rerun from silently mixing
    tensors produced by different environments or configurations.
    """

    def __init__(
        self,
        destination: Path,
        *,
        run: Mapping[str, Any],
        source: Mapping[str, Any] | None = None,
        environment: Mapping[str, Any] | None = None,
        store_payloads: bool = True,
    ) -> None:
        if destination.exists():
            raise FileExistsError(f"reference destination already exists: {destination}")
        self.destination = destination
        self.destination.mkdir(parents=True)
        (self.destination / "tensors").mkdir()
        self.run = dict(run)
        self.source = dict(
            source
            or {
                "repository": UPSTREAM_REPOSITORY,
                "commit": UPSTREAM_COMMIT,
                "model": "EchoMimicV3-Flash",
            }
        )
        self.environment = dict(environment or collect_environment())
        self.store_payloads = store_payloads
        self._records: list[TensorRecord] = []
        self._names: set[str] = set()
        self._finalized = False

    def add(self, name: str, value: object, *, store: bool | None = None) -> TensorRecord:
        """Record a tensor and optionally persist its exact payload."""

        if self._finalized:
            raise RuntimeError("cannot add tensors after finalizing a reference export")
        if not _TENSOR_NAME.fullmatch(name):
            raise ValueError(f"invalid canonical tensor name: {name!r}")
        if name in self._names:
            raise ValueError(f"duplicate tensor name: {name}")
        if (
            not isinstance(value, np.ndarray)
            and not _is_torch_tensor(value)
            and not _is_mlx_array(value)
        ):
            raise TypeError(f"{name} must be a NumPy array, torch.Tensor, or MLX array")

        raw = _tensor_bytes(value)
        array = _numpy_array(value, for_statistics=True)
        relative_file: str | None = None
        file_sha256: str | None = None
        if self.store_payloads if store is None else store:
            relative_file = _payload_filename(name)
            payload_path = self.destination / relative_file
            _save_tensor(payload_path, name, value)
            file_sha256 = _sha256(payload_path.read_bytes())

        record = TensorRecord(
            name=name,
            shape=list(array.shape),
            dtype=_dtype_name(value),
            numel=int(array.size),
            nbytes=len(raw),
            tensor_sha256=_sha256(raw),
            file=relative_file,
            file_sha256=file_sha256,
            statistics=_statistics(value),
        )
        self._records.append(record)
        self._names.add(name)
        return record

    def finalize(self) -> Path:
        """Write the canonical manifest and return its path."""

        if self._finalized:
            raise RuntimeError("reference export was already finalized")
        if not self._records:
            raise ValueError("refusing to finalize an empty reference export")
        manifest = {
            "protocol": {"name": PROTOCOL_NAME, "version": PROTOCOL_VERSION},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": self.source,
            "run": self.run,
            "environment": self.environment,
            "tensors": [
                asdict(record) for record in sorted(self._records, key=lambda item: item.name)
            ],
        }
        manifest_path = self.destination / "manifest.json"
        serialized = json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
        manifest_path.write_text(serialized, encoding="utf-8")
        (self.destination / "manifest.sha256").write_text(
            f"{_sha256(serialized.encode())}  manifest.json\n", encoding="ascii"
        )
        self._finalized = True
        return manifest_path


def collect_environment() -> dict[str, Any]:
    """Collect reproducibility metadata without importing optional ML frameworks."""

    result: dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "pid": os.getpid(),
        "numpy": np.__version__,
    }
    try:
        import torch  # type: ignore[import-not-found, unused-ignore]

        result["torch"] = torch.__version__
        result["cuda"] = torch.version.cuda
        result["cudnn"] = torch.backends.cudnn.version()  # type: ignore[no-untyped-call]
        if torch.cuda.is_available():
            result["gpu"] = torch.cuda.get_device_name(torch.cuda.current_device())
    except ImportError:
        result["torch"] = None
    try:
        import mlx.core as mx

        result["mlx"] = version("mlx")
        try:
            result["mlx_device"] = mx.device_info()
        except RuntimeError:
            result["mlx_device"] = None
    except (ImportError, PackageNotFoundError):
        result["mlx"] = None
        result["mlx_device"] = None
    return result


def load_mlx_reference_tensors(
    directory: Path, names: set[str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify an immutable reference export and load selected payloads into MLX."""

    from .safetensors_io import SelectiveSafeTensorReader

    root = directory.expanduser().resolve()
    manifest_path = root / "manifest.json"
    serialized = manifest_path.read_bytes()
    digest_line = (root / "manifest.sha256").read_text(encoding="ascii").strip()
    expected_digest_line = f"{_sha256(serialized)}  manifest.json"
    if digest_line != expected_digest_line:
        raise ValueError("reference manifest SHA-256 sidecar mismatch")
    manifest = json.loads(serialized)
    expected_protocol = {"name": PROTOCOL_NAME, "version": PROTOCOL_VERSION}
    if not isinstance(manifest, dict) or manifest.get("protocol") != expected_protocol:
        raise ValueError("unsupported reference manifest protocol")
    records = manifest.get("tensors")
    if not isinstance(records, list):
        raise ValueError("reference manifest tensors must be a list")
    by_name: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("name"), str):
            raise ValueError("reference manifest contains an invalid tensor record")
        if record["name"] in by_name:
            raise ValueError(f"duplicate reference tensor record: {record['name']}")
        by_name[record["name"]] = record
    missing = sorted(names - by_name.keys())
    if missing:
        raise KeyError(f"reference export is missing tensors: {missing}")

    dtype_names = {
        "BOOL": "bool",
        "I8": "int8",
        "U8": "uint8",
        "I16": "int16",
        "U16": "uint16",
        "F16": "float16",
        "BF16": "bfloat16",
        "I32": "int32",
        "U32": "uint32",
        "F32": "float32",
        "I64": "int64",
        "U64": "uint64",
        "F64": "float64",
    }
    tensors: dict[str, Any] = {}
    for name in sorted(names):
        record = by_name[name]
        relative = record.get("file")
        if not isinstance(relative, str):
            raise ValueError(f"reference tensor has no stored payload: {name}")
        path = (root / relative).resolve()
        if root not in path.parents:
            raise ValueError(f"reference tensor payload escapes export directory: {name}")
        reader = SelectiveSafeTensorReader(path)
        file_sha256 = record.get("file_sha256")
        if not isinstance(file_sha256, str):
            raise ValueError(f"reference tensor has no file SHA-256: {name}")
        reader.verify_sha256(file_sha256)
        location = reader.location("tensor")
        if (
            list(location.shape) != record.get("shape")
            or dtype_names.get(location.dtype) != record.get("dtype")
            or location.nbytes != record.get("nbytes")
        ):
            raise ValueError(f"reference payload schema disagrees with manifest: {name}")
        value = reader.read("tensor")
        if _sha256(_tensor_bytes(value)) != record.get("tensor_sha256"):
            raise ValueError(f"reference logical tensor SHA-256 mismatch: {name}")
        tensors[name] = value
    return manifest, tensors
