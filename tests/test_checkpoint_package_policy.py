from __future__ import annotations

import zipfile

import pytest
import yaml

from ai2apps.checkpoint_package_policy import (
    CheckpointPackagePolicyError,
    require_checkpoint_distributions,
    require_checkpoint_distributions_from_artifact,
)


def test_release_gate_requires_distribution_for_model_weights():
    with pytest.raises(CheckpointPackagePolicyError, match="model/default"):
        require_checkpoint_distributions(
            {"models": [{"id": "model/default", "weights": {"repo_id": "a/b"}}]}
        )
    with pytest.raises(CheckpointPackagePolicyError, match="model/default"):
        require_checkpoint_distributions(
            {
                "models": [
                    {
                        "id": "model/default",
                        "weights": {"repo_id": "a/b", "distribution_id": "../bad"},
                    }
                ]
            }
        )


def test_release_gate_allows_non_model_service_and_distribution_model():
    require_checkpoint_distributions({"models": []})
    require_checkpoint_distributions(
        {
            "models": [
                {
                    "id": "model/default",
                    "weights": {
                        "repo_id": "a/b",
                        "distribution_id": "dist_model_v1",
                    },
                }
            ]
        }
    )


def test_release_gate_checks_already_built_artifact(tmp_path):
    artifact = tmp_path / "model.ai2service"
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr(
            "service.yaml",
            yaml.safe_dump(
                {"models": [{"id": "model/default", "weights": {"repo_id": "a/b"}}]}
            ),
        )

    with pytest.raises(CheckpointPackagePolicyError):
        require_checkpoint_distributions_from_artifact(artifact)
