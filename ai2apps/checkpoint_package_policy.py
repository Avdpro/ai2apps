"""Release gate for model Packages using trusted checkpoint distributions."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

import yaml

from ai2apps.checkpoint_paths import checkpoint_distribution_cache_key


class CheckpointPackagePolicyError(ValueError):
    pass


def require_checkpoint_distributions(service_manifest: Any) -> None:
    """Reject publishable model weights that bypass the trusted Registry path."""

    if not isinstance(service_manifest, dict):
        raise CheckpointPackagePolicyError("service.yaml must be an object")
    models = service_manifest.get("models", ())
    if not isinstance(models, list):
        raise CheckpointPackagePolicyError("service.yaml models must be an array")
    missing: list[str] = []
    for index, model in enumerate(models):
        if not isinstance(model, dict):
            continue
        weights = model.get("weights")
        if not isinstance(weights, dict):
            continue
        distribution_id = weights.get("distribution_id")
        try:
            checkpoint_distribution_cache_key(distribution_id)
        except (TypeError, ValueError):
            missing.append(str(model.get("id") or f"models[{index}]"))
    if missing:
        raise CheckpointPackagePolicyError(
            "Model Packages published after the distribution upgrade require "
            "weights.distribution_id: " + ", ".join(missing)
        )


def require_checkpoint_distributions_from_source(source: str | Path) -> None:
    service = Path(source) / "service.yaml"
    if not service.is_file():
        return
    require_checkpoint_distributions(
        yaml.safe_load(service.read_text(encoding="utf-8"))
    )


def require_checkpoint_distributions_from_artifact(artifact: str | Path) -> None:
    with zipfile.ZipFile(artifact) as archive:
        try:
            payload = archive.read("service.yaml")
        except KeyError:
            return
    require_checkpoint_distributions(yaml.safe_load(payload.decode("utf-8")))
