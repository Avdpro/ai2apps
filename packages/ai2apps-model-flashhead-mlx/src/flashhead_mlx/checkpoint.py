"""Self-contained FlashHead checkpoint layout, independent of a user's cache."""

import json
from pathlib import Path

SCHEMA = "ai2apps.flashhead-mlx-checkpoint/v1"


def required_files(variant):
    if variant not in {"lite", "pro"}:
        raise ValueError("Unknown FlashHead variant")
    model = "Model_Lite" if variant == "lite" else "Model_Pro"
    common = [
        f"{model}/config.json",
        f"{model}/diffusion_pytorch_model.safetensors",
        "wav2vec2/config.json",
        "wav2vec2/preprocessor_config.json",
        "wav2vec2/model.safetensors",
    ]
    return common + (
        ["VAE_LTX/config.json", "VAE_LTX/diffusion_pytorch_model.safetensors"]
        if variant == "lite"
        else ["VAE_Wan/Wan2.1_VAE.safetensors"]
    )


def validate_checkpoint(root, variant):
    # Host supplies a canonical authorized root; resolving ancestors probes
    # directories outside the Managed Service sandbox.
    root = Path(root)
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("Expected an existing absolute Host checkpoint root")
    manifest = json.loads((root / "ai2apps-checkpoint.json").read_text())
    if manifest.get("schema") != SCHEMA or manifest.get("variant") != variant:
        raise ValueError("Checkpoint schema or variant mismatch")
    entries = manifest.get("files", [])
    if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
        raise ValueError("Invalid checkpoint file manifest")
    indexed = {e.get("path"): e for e in entries}
    if len(indexed) != len(entries) or set(indexed) != set(required_files(variant)):
        raise ValueError("Checkpoint file set mismatch")
    for name in required_files(variant):
        entry = indexed[name]
        digest = entry.get("sha256", "")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError("Invalid file digest")
        size = entry.get("size")
        if (
            isinstance(size, bool)
            or not isinstance(size, int)
            or size <= 0
            or (root / name).stat().st_size != size
        ):
            raise ValueError("Missing or wrong-sized checkpoint file: " + name)
    # Host's signed distribution downloader verifies SHA-256 before granting this root.
    return root
