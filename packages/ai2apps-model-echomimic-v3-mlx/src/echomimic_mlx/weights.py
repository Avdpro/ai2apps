"""Safetensors checkpoint inspection and versioned model manifests."""

from __future__ import annotations

import hashlib
import json
import math
import re
import struct
import urllib.request
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

from safetensors import safe_open

MODEL_MANIFEST_NAME = "echomimic-mlx-model-manifest"
MODEL_MANIFEST_VERSION = 1

_BLOCK_INDEX = re.compile(r"(?:^|\.)blocks\.(\d+)\.")
_CONTENT_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+)")
_CONFIG_KEYS = {
    "dim": ("dim", "hidden_size"),
    "ffn_dim": ("ffn_dim", "intermediate_size"),
    "freq_dim": ("freq_dim",),
    "in_dim": ("in_dim", "in_channels"),
    "num_heads": ("num_heads", "num_attention_heads"),
    "num_layers": ("num_layers", "num_hidden_layers"),
    "out_dim": ("out_dim", "out_channels"),
    "patch_size": ("patch_size",),
    "text_dim": ("text_dim",),
}


@dataclass(frozen=True, slots=True)
class CheckpointFile:
    """One Safetensors shard used by a model manifest."""

    path: str
    size_bytes: int
    sha256: str | None
    tensor_count: int


@dataclass(frozen=True, slots=True)
class ModelTensor:
    """Header-only description of a checkpoint tensor."""

    name: str
    shape: list[int]
    dtype: str
    numel: int
    nbytes: int
    file: str


@dataclass(frozen=True, slots=True)
class ModelManifest:
    """Stable, serializable schema for a pinned model checkpoint."""

    protocol: dict[str, object]
    root: str
    config: dict[str, object]
    architecture: dict[str, object]
    files: list[CheckpointFile]
    tensors: list[ModelTensor]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ModelSchemaDifference:
    """Tensor coverage and compatibility between a base and overlay checkpoint."""

    shared: list[str]
    base_only: list[str]
    overlay_only: list[str]
    shape_mismatches: list[dict[str, object]]
    dtype_mismatches: list[dict[str, object]]


@dataclass(frozen=True, slots=True)
class EchoMimicOverlayValidation:
    """Verified relationship between the pinned Wan base and Flash checkpoint."""

    base_tensor_count: int
    flash_tensor_count: int
    shared_tensor_count: int
    audio_injection_tensor_count: int
    per_block_audio_tensor_count: int
    num_layers: int


@dataclass(frozen=True, slots=True)
class EchoMimicFlashValidation:
    """Exact tensor-name and shape validation for the complete Flash Transformer."""

    tensor_count: int
    block_tensor_count: int
    global_tensor_count: int
    num_layers: int


def _sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _numel(shape: list[int]) -> int:
    result = 1
    for extent in shape:
        if extent < 0:
            raise ValueError(f"negative tensor extent: {shape}")
        result *= extent
    return result


def _dtype_nbytes(dtype: str) -> int:
    sizes = {
        "BOOL": 1,
        "I8": 1,
        "U8": 1,
        "I16": 2,
        "U16": 2,
        "F16": 2,
        "BF16": 2,
        "I32": 4,
        "U32": 4,
        "F32": 4,
        "I64": 8,
        "U64": 8,
        "F64": 8,
    }
    try:
        return sizes[dtype]
    except KeyError as error:
        raise ValueError(f"unsupported Safetensors dtype in model manifest: {dtype}") from error


def discover_safetensors(path: Path) -> tuple[Path, list[Path]]:
    """Resolve a checkpoint file or directory to a deterministic shard list."""

    path = path.expanduser().resolve()
    if path.is_file():
        if path.suffix != ".safetensors":
            raise ValueError(f"checkpoint file must end in .safetensors: {path}")
        return path.parent, [path]
    if not path.is_dir():
        raise FileNotFoundError(f"checkpoint does not exist: {path}")
    shards = sorted(item for item in path.rglob("*.safetensors") if item.is_file())
    if not shards:
        raise ValueError(f"checkpoint directory contains no Safetensors files: {path}")
    return path, shards


def load_json_config(path: Path | None) -> dict[str, object]:
    """Load an optional JSON model config without accepting non-object roots."""

    if path is None:
        return {}
    value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("model config must contain a JSON object")
    return value


def load_remote_json(url: str) -> dict[str, object]:
    """Load a small pinned JSON config over HTTPS."""

    if not url.startswith("https://"):
        raise ValueError("remote model config must use HTTPS")
    request = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
    with urllib.request.urlopen(request, timeout=30) as response:
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise TypeError("remote model config must contain a JSON object")
    return value


def _fetch_http_range(url: str, start: int, end: int) -> tuple[bytes, int]:
    if not url.startswith("https://"):
        raise ValueError("remote Safetensors URL must use HTTPS")
    request = urllib.request.Request(
        url,
        headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        content_range = response.headers.get("Content-Range")
        match = _CONTENT_RANGE.fullmatch(content_range or "")
        if response.status != 206 or match is None:
            raise ValueError("remote server did not honor the requested byte range")
        actual_start, actual_end, total = (int(value) for value in match.groups())
        if actual_start != start or actual_end != end:
            raise ValueError("remote server returned an unexpected byte range")
        data = response.read()
    if len(data) != end - start + 1:
        raise ValueError("remote byte range was truncated")
    return data, total


def _models_from_header(header: object, file: str) -> list[ModelTensor]:
    if not isinstance(header, dict):
        raise ValueError("Safetensors header must contain a JSON object")
    result: list[ModelTensor] = []
    for name in sorted(header):
        if name == "__metadata__":
            continue
        descriptor = header[name]
        if not isinstance(descriptor, dict):
            raise ValueError(f"invalid Safetensors descriptor for {name}")
        shape = descriptor.get("shape")
        dtype = descriptor.get("dtype")
        offsets = descriptor.get("data_offsets")
        if (
            not isinstance(shape, list)
            or not all(isinstance(value, int) for value in shape)
            or not isinstance(dtype, str)
            or not isinstance(offsets, list)
            or len(offsets) != 2
            or not all(isinstance(value, int) for value in offsets)
        ):
            raise ValueError(f"invalid Safetensors schema for {name}")
        elements = _numel(shape)
        nbytes = elements * _dtype_nbytes(dtype)
        if offsets[1] - offsets[0] != nbytes:
            raise ValueError(f"Safetensors data offsets do not match {name} shape/dtype")
        result.append(ModelTensor(name, shape, dtype, elements, nbytes, file))
    if not result:
        raise ValueError("Safetensors header contains no tensors")
    return result


def build_remote_model_manifest(
    url: str,
    *,
    logical_path: str,
    config: Mapping[str, object] | None = None,
    expected_size: int | None = None,
    expected_sha256: str | None = None,
    maximum_header_bytes: int = 64 * 1024 * 1024,
) -> ModelManifest:
    """Build a real checkpoint manifest by downloading only its Safetensors header."""

    if not logical_path or logical_path.startswith("/") or ".." in Path(logical_path).parts:
        raise ValueError("logical_path must be a safe relative checkpoint path")
    if expected_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("expected_sha256 must be a lowercase SHA-256 digest")
    prefix, total_size = _fetch_http_range(url, 0, 7)
    header_size = struct.unpack("<Q", prefix)[0]
    if header_size <= 0 or header_size > maximum_header_bytes:
        raise ValueError(f"remote Safetensors header size is unsafe: {header_size}")
    header_bytes, repeated_total = _fetch_http_range(url, 8, 7 + header_size)
    if repeated_total != total_size:
        raise ValueError("remote Safetensors size changed between range requests")
    if expected_size is not None and total_size != expected_size:
        raise ValueError(f"remote checkpoint size mismatch: {total_size} != {expected_size}")
    tensors = _models_from_header(json.loads(header_bytes), logical_path)
    payload_bytes = total_size - 8 - header_size
    if sum(tensor.nbytes for tensor in tensors) != payload_bytes:
        raise ValueError("remote Safetensors payload size does not match its tensor schemas")
    normalized_config = dict(sorted((config or {}).items()))
    return ModelManifest(
        protocol={"name": MODEL_MANIFEST_NAME, "version": MODEL_MANIFEST_VERSION},
        root=".",
        config=normalized_config,
        architecture=_infer_architecture(normalized_config, tensors),
        files=[CheckpointFile(logical_path, total_size, expected_sha256, len(tensors))],
        tensors=tensors,
    )


def _first_present(config: Mapping[str, object], keys: tuple[str, ...]) -> object | None:
    for key in keys:
        if key in config:
            return config[key]
    return None


def _infer_architecture(
    config: Mapping[str, object], tensors: list[ModelTensor]
) -> dict[str, object]:
    architecture: dict[str, object] = {}
    for canonical, aliases in _CONFIG_KEYS.items():
        value = _first_present(config, aliases)
        if value is not None:
            architecture[canonical] = value

    block_indices = {
        int(match.group(1))
        for tensor in tensors
        if (match := _BLOCK_INDEX.search(tensor.name)) is not None
    }
    if block_indices:
        expected = set(range(max(block_indices) + 1))
        if block_indices != expected:
            missing = sorted(expected - block_indices)
            raise ValueError(f"checkpoint block indices are not contiguous; missing {missing}")
        inferred_layers = len(block_indices)
        configured_layers = architecture.get("num_layers")
        if configured_layers is not None and configured_layers != inferred_layers:
            raise ValueError(
                "configured transformer layer count does not match checkpoint: "
                f"{configured_layers} != {inferred_layers}"
            )
        architecture["num_layers"] = inferred_layers

    patch = next(
        (
            tensor
            for tensor in tensors
            if tensor.name.endswith("patch_embedding.weight") and len(tensor.shape) == 5
        ),
        None,
    )
    if patch is not None:
        inferred = {
            "dim": patch.shape[0],
            "in_dim": patch.shape[1],
            "patch_size": patch.shape[2:],
        }
        for key, value in inferred.items():
            configured = architecture.get(key)
            if configured is not None and configured != value:
                raise ValueError(
                    f"configured {key} does not match patch embedding: {configured} != {value}"
                )
            architecture[key] = value
    return dict(sorted(architecture.items()))


def build_model_manifest(
    checkpoint: Path,
    *,
    config: Mapping[str, object] | None = None,
    hash_files: bool = False,
) -> ModelManifest:
    """Inspect checkpoint headers without loading tensor payloads."""

    root, shards = discover_safetensors(checkpoint)
    tensors: list[ModelTensor] = []
    files: list[CheckpointFile] = []
    names: set[str] = set()
    for shard in shards:
        relative = shard.relative_to(root).as_posix()
        shard_tensors: list[ModelTensor] = []
        with safe_open(shard, framework="numpy", device="cpu") as handle:
            for name in sorted(handle.keys()):
                if name in names:
                    raise ValueError(f"duplicate tensor name across checkpoint shards: {name}")
                tensor_slice = handle.get_slice(name)
                shape = list(tensor_slice.get_shape())
                dtype = tensor_slice.get_dtype()
                elements = _numel(shape)
                shard_tensors.append(
                    ModelTensor(
                        name=name,
                        shape=shape,
                        dtype=dtype,
                        numel=elements,
                        nbytes=elements * _dtype_nbytes(dtype),
                        file=relative,
                    )
                )
                names.add(name)
        tensors.extend(shard_tensors)
        files.append(
            CheckpointFile(
                path=relative,
                size_bytes=shard.stat().st_size,
                sha256=_sha256_file(shard) if hash_files else None,
                tensor_count=len(shard_tensors),
            )
        )

    tensors.sort(key=lambda item: item.name)
    normalized_config = dict(sorted((config or {}).items()))
    return ModelManifest(
        protocol={"name": MODEL_MANIFEST_NAME, "version": MODEL_MANIFEST_VERSION},
        root=".",
        config=normalized_config,
        architecture=_infer_architecture(normalized_config, tensors),
        files=files,
        tensors=tensors,
    )


def write_model_manifest(manifest: ModelManifest, output: Path) -> Path:
    """Write canonical JSON plus a sidecar digest."""

    output = output.expanduser()
    digest_path = output.with_suffix(output.suffix + ".sha256")
    if output.exists() or digest_path.exists():
        raise FileExistsError(f"refusing to overwrite model manifest: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(manifest.as_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n"
    output.write_text(serialized, encoding="utf-8")
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    digest_path.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    return output


def compare_model_schemas(base: ModelManifest, overlay: ModelManifest) -> ModelSchemaDifference:
    """Describe how an EchoMimic overlay relates to its Wan base checkpoint."""

    base_tensors = {tensor.name: tensor for tensor in base.tensors}
    overlay_tensors = {tensor.name: tensor for tensor in overlay.tensors}
    shared = sorted(base_tensors.keys() & overlay_tensors.keys())
    shape_mismatches: list[dict[str, object]] = []
    dtype_mismatches: list[dict[str, object]] = []
    for name in shared:
        base_tensor = base_tensors[name]
        overlay_tensor = overlay_tensors[name]
        if base_tensor.shape != overlay_tensor.shape:
            shape_mismatches.append(
                {"name": name, "base": base_tensor.shape, "overlay": overlay_tensor.shape}
            )
        if base_tensor.dtype != overlay_tensor.dtype:
            dtype_mismatches.append(
                {"name": name, "base": base_tensor.dtype, "overlay": overlay_tensor.dtype}
            )
    return ModelSchemaDifference(
        shared=shared,
        base_only=sorted(base_tensors.keys() - overlay_tensors.keys()),
        overlay_only=sorted(overlay_tensors.keys() - base_tensors.keys()),
        shape_mismatches=shape_mismatches,
        dtype_mismatches=dtype_mismatches,
    )


def _expected_audio_overlay_shapes(*, dim: int, num_layers: int) -> dict[str, list[int]]:
    expected = {
        "audio_injection.norm.bias": [dim],
        "audio_injection.norm.weight": [dim],
        "audio_injection.proj1.bias": [512],
        "audio_injection.proj1.weight": [512, 5 * 12 * 768],
        "audio_injection.proj1_vf.bias": [512],
        "audio_injection.proj1_vf.weight": [512, 8 * 12 * 768],
        "audio_injection.proj2.bias": [512],
        "audio_injection.proj2.weight": [512, 512],
        "audio_injection.proj3.bias": [32 * dim],
        "audio_injection.proj3.weight": [32 * dim, 512],
    }
    for block in range(num_layers):
        prefix = f"blocks.{block}.cross_attn"
        for projection in ("q_audio", "k_audio", "v_audio"):
            expected[f"{prefix}.{projection}.bias"] = [dim]
            expected[f"{prefix}.{projection}.weight"] = [dim, dim]
        expected[f"{prefix}.norm_k_audio.weight"] = [dim]
    return expected


def validate_echomimic_overlay_schema(
    base: ModelManifest, flash: ModelManifest
) -> EchoMimicOverlayValidation:
    """Require Flash to be an exact Wan-base superset plus known audio tensors."""

    difference = compare_model_schemas(base, flash)
    if difference.base_only or difference.shape_mismatches or difference.dtype_mismatches:
        raise ValueError("Flash checkpoint is not a schema-compatible superset of Wan base")
    for field in ("dim", "num_layers"):
        if base.architecture.get(field) != flash.architecture.get(field):
            raise ValueError(f"Flash and Wan base architecture disagree on {field}")
    dim = flash.architecture.get("dim")
    num_layers = flash.architecture.get("num_layers")
    if not isinstance(dim, int) or not isinstance(num_layers, int):
        raise ValueError("Flash manifest must define integer dim and num_layers")
    expected = _expected_audio_overlay_shapes(dim=dim, num_layers=num_layers)
    if set(difference.overlay_only) != set(expected):
        missing = sorted(set(expected) - set(difference.overlay_only))
        unexpected = sorted(set(difference.overlay_only) - set(expected))
        raise ValueError(
            f"Flash audio overlay tensor set differs; missing={missing}, unexpected={unexpected}"
        )
    flash_tensors = {tensor.name: tensor for tensor in flash.tensors}
    for name, shape in expected.items():
        tensor = flash_tensors[name]
        if tensor.shape != shape or tensor.dtype != "BF16":
            raise ValueError(
                f"Flash audio tensor schema mismatch for {name}: {tensor.shape}/{tensor.dtype}"
            )
    return EchoMimicOverlayValidation(
        base_tensor_count=len(base.tensors),
        flash_tensor_count=len(flash.tensors),
        shared_tensor_count=len(difference.shared),
        audio_injection_tensor_count=10,
        per_block_audio_tensor_count=7,
        num_layers=num_layers,
    )


def _expected_flash_shapes(architecture: Mapping[str, object]) -> dict[str, list[int]]:
    required = (
        "dim",
        "ffn_dim",
        "freq_dim",
        "in_dim",
        "num_layers",
        "out_dim",
        "patch_size",
        "text_dim",
    )
    missing = [name for name in required if name not in architecture]
    if missing:
        raise ValueError(f"Flash architecture is missing fields: {missing}")
    dim = architecture["dim"]
    ffn_dim = architecture["ffn_dim"]
    freq_dim = architecture["freq_dim"]
    in_dim = architecture["in_dim"]
    num_layers = architecture["num_layers"]
    out_dim = architecture["out_dim"]
    patch_size = architecture["patch_size"]
    text_dim = architecture["text_dim"]
    if (
        not all(
            isinstance(value, int)
            for value in (dim, ffn_dim, freq_dim, in_dim, num_layers, out_dim, text_dim)
        )
        or not isinstance(patch_size, list)
        or len(patch_size) != 3
        or not all(isinstance(value, int) for value in patch_size)
    ):
        raise ValueError("Flash architecture fields have invalid types")
    assert isinstance(dim, int)
    assert isinstance(ffn_dim, int)
    assert isinstance(freq_dim, int)
    assert isinstance(in_dim, int)
    assert isinstance(num_layers, int)
    assert isinstance(out_dim, int)
    assert isinstance(text_dim, int)
    patch = [int(value) for value in patch_size]
    patch_volume = math.prod(patch)
    expected: dict[str, list[int]] = {
        "head.head.bias": [patch_volume * out_dim],
        "head.head.weight": [patch_volume * out_dim, dim],
        "head.modulation": [1, 2, dim],
        "img_emb.proj.0.bias": [1280],
        "img_emb.proj.0.weight": [1280],
        "img_emb.proj.1.bias": [1280],
        "img_emb.proj.1.weight": [1280, 1280],
        "img_emb.proj.3.bias": [dim],
        "img_emb.proj.3.weight": [dim, 1280],
        "img_emb.proj.4.bias": [dim],
        "img_emb.proj.4.weight": [dim],
        "patch_embedding.bias": [dim],
        "patch_embedding.weight": [dim, in_dim, *patch],
        "text_embedding.0.bias": [dim],
        "text_embedding.0.weight": [dim, text_dim],
        "text_embedding.2.bias": [dim],
        "text_embedding.2.weight": [dim, dim],
        "time_embedding.0.bias": [dim],
        "time_embedding.0.weight": [dim, freq_dim],
        "time_embedding.2.bias": [dim],
        "time_embedding.2.weight": [dim, dim],
        "time_projection.1.bias": [6 * dim],
        "time_projection.1.weight": [6 * dim, dim],
    }
    expected.update(_expected_audio_overlay_shapes(dim=dim, num_layers=0))
    attention_linears = (
        "self_attn.q",
        "self_attn.k",
        "self_attn.v",
        "self_attn.o",
        "cross_attn.q",
        "cross_attn.k",
        "cross_attn.v",
        "cross_attn.o",
        "cross_attn.k_img",
        "cross_attn.v_img",
        "cross_attn.q_audio",
        "cross_attn.k_audio",
        "cross_attn.v_audio",
    )
    for block in range(num_layers):
        prefix = f"blocks.{block}"
        for name in attention_linears:
            expected[f"{prefix}.{name}.weight"] = [dim, dim]
            expected[f"{prefix}.{name}.bias"] = [dim]
        expected[f"{prefix}.ffn.0.weight"] = [ffn_dim, dim]
        expected[f"{prefix}.ffn.0.bias"] = [ffn_dim]
        expected[f"{prefix}.ffn.2.weight"] = [dim, ffn_dim]
        expected[f"{prefix}.ffn.2.bias"] = [dim]
        for norm in (
            "self_attn.norm_q",
            "self_attn.norm_k",
            "cross_attn.norm_q",
            "cross_attn.norm_k",
            "cross_attn.norm_k_img",
            "cross_attn.norm_k_audio",
            "norm3",
        ):
            expected[f"{prefix}.{norm}.weight"] = [dim]
        expected[f"{prefix}.norm3.bias"] = [dim]
        expected[f"{prefix}.modulation"] = [1, 6, dim]
    return expected


def validate_echomimic_flash_schema(flash: ModelManifest) -> EchoMimicFlashValidation:
    """Validate every tensor in the pinned complete Flash Transformer schema."""

    architecture = dict(flash.architecture)
    if "freq_dim" not in architecture and isinstance(flash.config.get("freq_dim"), int):
        architecture["freq_dim"] = flash.config["freq_dim"]
    expected = _expected_flash_shapes(architecture)
    actual = {tensor.name: tensor for tensor in flash.tensors}
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        raise ValueError(f"Flash tensor set differs; missing={missing}, unexpected={unexpected}")
    for name, shape in expected.items():
        tensor = actual[name]
        if tensor.shape != shape or tensor.dtype != "BF16":
            raise ValueError(
                f"Flash tensor schema mismatch for {name}: {tensor.shape}/{tensor.dtype}"
            )
    num_layers = architecture["num_layers"]
    assert isinstance(num_layers, int)
    return EchoMimicFlashValidation(
        tensor_count=len(actual),
        block_tensor_count=39 * num_layers,
        global_tensor_count=len(actual) - 39 * num_layers,
        num_layers=num_layers,
    )


def write_schema_difference(difference: ModelSchemaDifference, output: Path) -> Path:
    """Write a deterministic base/overlay checkpoint report."""

    output = output.expanduser()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite schema difference: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(asdict(difference), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return output


def load_model_manifest(path: Path) -> ModelManifest:
    """Load a versioned model manifest for schema comparison."""

    value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    expected_protocol = {"name": MODEL_MANIFEST_NAME, "version": MODEL_MANIFEST_VERSION}
    if not isinstance(value, dict) or value.get("protocol") != expected_protocol:
        raise ValueError(f"unsupported model manifest protocol: {path}")
    try:
        files = [CheckpointFile(**item) for item in value["files"]]
        tensors = [ModelTensor(**item) for item in value["tensors"]]
        return ModelManifest(
            protocol=value["protocol"],
            root=value["root"],
            config=value["config"],
            architecture=value["architecture"],
            files=files,
            tensors=tensors,
        )
    except (KeyError, TypeError) as error:
        raise ValueError(f"invalid model manifest schema: {path}") from error
