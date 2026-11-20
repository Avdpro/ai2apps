"""Validate the exact portable checkpoint layout selected by Host."""

import json
from pathlib import Path

GRAPH_NAMES = (
    "hubert",
    "landmark106",
    "landmark203",
    "motion_extractor",
    "appearance_extractor",
    "stitch_network",
    "warp_network",
    "decoder",
    "insightface_det",
)


def validate_checkpoint(root):
    root = Path(root)
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("Expected absolute Host checkpoint root")
    manifest = json.loads((root / "ai2apps-checkpoint.json").read_text())
    if manifest.get("schema") != "ai2apps.avtr1-mlx-checkpoint/v1":
        raise ValueError("Unsupported AVTR checkpoint")
    expected = {
        "config.json",
        "conversion.json",
        "model_config.json",
        "motion.safetensors",
    }
    expected.update(
        f"graphs/{name}/{file}"
        for name in GRAPH_NAMES
        for file in ("graph.json", "weights.safetensors")
    )
    entries = manifest.get("files", [])
    indexed = {entry["path"]: entry for entry in entries}
    if set(indexed) != expected or len(entries) != len(expected):
        raise ValueError("Checkpoint file set mismatch")
    for name, entry in indexed.items():
        digest = entry.get("sha256", "")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid digest")
        if (root / name).stat().st_size != entry.get("size"):
            raise ValueError("Checkpoint size mismatch: " + name)
    return root
