"""Trusted offline conversion from legacy RVC pickle files to safetensors."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from .config import RVCConfig
from .mlx_layers import weight_norm


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def export_legacy_checkpoint(
    source: str | Path, destination: str | Path
) -> dict[str, Any]:
    """Convert one trusted RVC ``.pth`` into a non-executable model artifact.

    PyTorch pickle loading is intentionally confined to this offline developer
    tool. It must never be called on an untrusted user upload or from the MLX
    Runtime. Production inference consumes only the emitted safetensors/JSON.
    """

    try:
        import torch
    except ImportError as error:
        raise RuntimeError(
            "PyTorch is required only by the offline RVC converter"
        ) from error
    try:
        from safetensors.numpy import save_file
    except ImportError as error:
        raise RuntimeError(
            "safetensors is required by the offline RVC converter"
        ) from error

    source_path = Path(source)
    package = torch.load(source_path, map_location="cpu", weights_only=True)
    if not isinstance(package, dict) or not isinstance(package.get("weight"), dict):
        raise ValueError("unsupported RVC checkpoint container")
    legacy_config = package.get("config")
    if not isinstance(legacy_config, (list, tuple)):
        raise ValueError("RVC checkpoint is missing its legacy config array")
    version = str(package.get("version", "v1"))
    uses_f0 = bool(package.get("f0", 1))
    weights = package["weight"]
    speaker_weight = weights.get("emb_g.weight")
    if speaker_weight is None or getattr(speaker_weight, "ndim", None) != 2:
        raise ValueError("RVC checkpoint is missing emb_g.weight")
    config = RVCConfig.from_legacy(
        legacy_config,
        version=version,
        uses_f0=uses_f0,
        speaker_count=int(speaker_weight.shape[0]),
    )

    arrays: dict[str, np.ndarray] = {}
    for name, tensor in weights.items():
        if not isinstance(name, str) or not hasattr(tensor, "detach"):
            raise ValueError(f"invalid RVC tensor entry: {name!r}")
        if name.startswith("enc_q."):
            continue
        array = tensor.detach().cpu().float().numpy()
        if not np.isfinite(array).all():
            raise ValueError(f"RVC tensor contains non-finite values: {name}")
        arrays[name] = array
    if not arrays:
        raise ValueError("RVC checkpoint contains no inference tensors")

    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "format": "ai2apps.mlx-rvc.weights/v1",
        "source_revision": "legacy-rvc-pth",
        "feature_version": config.feature_version,
        "uses_f0": "true" if config.uses_f0 else "false",
    }
    save_file(arrays, destination_path, metadata=metadata)
    manifest = {
        "schema": "ai2apps.mlx-rvc-checkpoint/v1",
        "source": {
            "name": source_path.name,
            "sha256": sha256(source_path),
        },
        "weights": {
            "name": destination_path.name,
            "sha256": sha256(destination_path),
            "tensor_count": len(arrays),
            "parameter_count": sum(int(array.size) for array in arrays.values()),
            "dtype": "float32",
        },
        "model": config.to_dict(),
    }
    manifest_path = destination_path.with_suffix(".json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def export_hubert_checkpoint(
    source: str | Path,
    config_source: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Convert the pinned Transformers HuBERT weights to safetensors.

    The source is the official RVC ``pytorch_model.bin``. As with legacy RVC
    conversion, this is a trusted, offline-only operation.
    """

    try:
        import torch
    except ImportError as error:
        raise RuntimeError(
            "PyTorch is required only by the offline HuBERT converter"
        ) from error
    try:
        from safetensors.numpy import save_file
    except ImportError as error:
        raise RuntimeError(
            "safetensors is required by the offline HuBERT converter"
        ) from error

    source_path = Path(source)
    config_path = Path(config_source)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("model_type") != "hubert" or int(config.get("hidden_size", 0)) != 768:
        raise ValueError("unsupported HuBERT configuration")
    package = torch.load(source_path, map_location="cpu", weights_only=True)
    if not isinstance(package, dict):
        raise ValueError("unsupported HuBERT checkpoint container")

    arrays: dict[str, np.ndarray] = {}
    for name, tensor in package.items():
        if name == "masked_spec_embed":
            continue
        if not isinstance(name, str) or not hasattr(tensor, "detach"):
            raise ValueError(f"invalid HuBERT tensor entry: {name!r}")
        array = tensor.detach().cpu().float().numpy()
        if not np.isfinite(array).all():
            raise ValueError(f"HuBERT tensor contains non-finite values: {name}")
        arrays[name] = array

    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    save_file(
        arrays,
        destination_path,
        metadata={
            "format": "ai2apps.mlx-rvc.hubert/v1",
            "source_model_type": "hubert",
        },
    )
    output_config = destination_path.with_name("config.json")
    output_config.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema": "ai2apps.mlx-rvc-hubert/v1",
        "source": {"name": source_path.name, "sha256": sha256(source_path)},
        "weights": {
            "name": destination_path.name,
            "sha256": sha256(destination_path),
            "tensor_count": len(arrays),
            "parameter_count": sum(int(array.size) for array in arrays.values()),
            "dtype": "float32",
        },
        "config": {"name": output_config.name, "sha256": sha256(output_config)},
    }
    destination_path.with_name("manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def export_rmvpe_checkpoint(
    source: str | Path, destination: str | Path
) -> dict[str, Any]:
    """Convert trusted RMVPE weights and persist its fixed mel basis."""

    try:
        import torch
        from librosa.filters import mel
        from safetensors.numpy import save_file
    except ImportError as error:
        raise RuntimeError(
            "Torch, librosa, and safetensors are converter-only requirements"
        ) from error
    source_path = Path(source)
    package = torch.load(source_path, map_location="cpu", weights_only=True)
    if not isinstance(package, dict):
        raise ValueError("unsupported RMVPE checkpoint container")
    arrays = {}
    for name, tensor in package.items():
        if name.endswith("num_batches_tracked"):
            continue
        array = tensor.detach().cpu().float().numpy()
        if not np.isfinite(array).all():
            raise ValueError(f"RMVPE tensor contains non-finite values: {name}")
        arrays[name] = array
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    save_file(arrays, destination_path, metadata={"format": "ai2apps.mlx-rvc.rmvpe/v1"})
    mel_basis_path = destination_path.with_name("mel_basis.safetensors")
    mel_basis = mel(
        sr=16000, n_fft=1024, n_mels=128, fmin=30, fmax=8000, htk=True
    ).astype(np.float32)
    save_file({"mel_basis": mel_basis}, mel_basis_path)
    manifest = {
        "schema": "ai2apps.mlx-rvc-rmvpe/v1",
        "source": {"name": source_path.name, "sha256": sha256(source_path)},
        "weights": {"name": destination_path.name, "sha256": sha256(destination_path)},
        "mel_basis": {"name": mel_basis_path.name, "sha256": sha256(mel_basis_path)},
    }
    destination_path.with_name("manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def export_faiss_index(source: str | Path, destination: str | Path) -> dict[str, Any]:
    """Convert one trusted legacy FAISS index into an exact-search vector bank."""

    try:
        import faiss
        from safetensors.numpy import save_file
    except ImportError as error:
        raise RuntimeError(
            "FAISS and safetensors are converter-only requirements"
        ) from error
    source_path = Path(source)
    index = faiss.read_index(str(source_path))
    if index.ntotal < 8 or index.d not in {256, 768}:
        raise ValueError("unsupported RVC retrieval index shape")
    vectors = index.reconstruct_n(0, index.ntotal).astype(np.float32)
    if vectors.shape != (index.ntotal, index.d) or not np.isfinite(vectors).all():
        raise ValueError("invalid vectors reconstructed from RVC retrieval index")
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    save_file(
        {"vectors": vectors},
        destination_path,
        metadata={"format": "ai2apps.mlx-rvc.retrieval/v1", "metric": "squared_l2"},
    )
    manifest = {
        "schema": "ai2apps.mlx-rvc-retrieval/v1",
        "source": {"name": source_path.name, "sha256": sha256(source_path)},
        "vectors": {
            "name": destination_path.name,
            "sha256": sha256(destination_path),
            "count": int(vectors.shape[0]),
            "dimensions": int(vectors.shape[1]),
            "dtype": "float32",
        },
        "search": {"implementation": "mlx-exact-top-k", "neighbors": 8},
    }
    destination_path.with_suffix(".json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def export_training_checkpoint(
    generator_source: str | Path,
    discriminator_source: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Convert trusted RVC trainer initialization weights for native MLX.

    Weight normalization is materialized once at this trusted boundary. The
    Package therefore trains ordinary safetensors arrays and never loads a
    pickle container or depends on Torch.
    """

    try:
        import torch
        from safetensors.numpy import save_file
    except ImportError as error:
        raise RuntimeError(
            "Torch and safetensors are offline converter requirements"
        ) from error

    output = Path(destination)
    output.mkdir(parents=True, exist_ok=True)

    def convert(source: str | Path, name: str) -> dict[str, Any]:
        source_path = Path(source)
        package = torch.load(source_path, map_location="cpu", weights_only=True)
        state = package.get("model") if isinstance(package, dict) else None
        if not isinstance(state, dict):
            raise ValueError(f"unsupported RVC training checkpoint: {source_path.name}")
        raw = {
            key: value.detach().cpu().float().numpy()
            for key, value in state.items()
            if isinstance(key, str) and hasattr(value, "detach")
        }
        arrays: dict[str, np.ndarray] = {}
        for key, value in raw.items():
            if key.endswith(".weight_g") or key.endswith(".weight_v"):
                continue
            arrays[key] = value
        for key, direction in raw.items():
            if not key.endswith(".weight_v"):
                continue
            base = key.removesuffix(".weight_v")
            gain = raw.get(f"{base}.weight_g")
            if gain is None:
                raise ValueError(f"weight normalization gain is missing: {base}")
            arrays[f"{base}.weight"] = weight_norm(gain, direction)
        if not arrays or not all(np.isfinite(value).all() for value in arrays.values()):
            raise ValueError(f"invalid RVC training arrays: {source_path.name}")
        target = output / f"{name}.safetensors"
        save_file(
            arrays,
            target,
            metadata={"format": f"ai2apps.mlx-rvc.training-{name}/v1"},
        )
        return {
            "source": {"name": source_path.name, "sha256": sha256(source_path)},
            "weights": {
                "name": target.name,
                "sha256": sha256(target),
                "tensor_count": len(arrays),
                "parameter_count": sum(int(value.size) for value in arrays.values()),
                "dtype": "float32",
            },
        }

    manifest = {
        "schema": "ai2apps.mlx-rvc-training-checkpoint/v1",
        "version": "v2",
        "sample_rate": 48_000,
        "uses_f0": True,
        "generator": convert(generator_source, "generator"),
        "discriminator": convert(discriminator_source, "discriminator"),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
