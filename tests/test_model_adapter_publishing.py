# SPDX-License-Identifier: Apache-2.0
"""Tests for offline model-adapter catalog publication tooling."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from ai2apps.packages.registry import DEFAULT_REPOSITORY_FINGERPRINT
from ai2apps.packages.repository_config import AI2APPS_REPOSITORY_FINGERPRINT
from omlx.model_adapters import ModelAdapterPackageError
from omlx.model_adapters.catalog import DEFAULT_CATALOG_FINGERPRINT
from omlx.model_adapters.publishing import (
    build_release_bundle,
    generate_repository_key,
    verify_release_bundle,
)


def _wheel(root: Path, version: str = "1.0.0") -> Path:
    path = root / f"demo_adapter-{version}-py3-none-any.whl"
    dist_info = f"demo_adapter-{version}.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("demo_adapter/__init__.py", "class Adapter: pass\n")
        archive.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.4\nName: demo-adapter\nVersion: {version}\n",
        )
        archive.writestr(
            f"{dist_info}/WHEEL", "Wheel-Version: 1.0\nTag: py3-none-any\n"
        )
        archive.writestr(
            f"{dist_info}/entry_points.txt",
            "[omlx.model_adapters]\ndemo = demo_adapter:Adapter\n",
        )
    return path


def _keys(tmp_path: Path):
    private = tmp_path / "repository-private.pem"
    public = tmp_path / "repository-public.pem"
    report = generate_repository_key(private, public)
    return private, public, report


def test_model_adapters_share_ai2apps_repository_trust_root():
    assert DEFAULT_CATALOG_FINGERPRINT == AI2APPS_REPOSITORY_FINGERPRINT
    assert DEFAULT_REPOSITORY_FINGERPRINT == AI2APPS_REPOSITORY_FINGERPRINT


def test_build_and_verify_signed_release_bundle(tmp_path):
    private, public, key_report = _keys(tmp_path)
    output = tmp_path / "release"
    built = build_release_bundle(
        [_wheel(tmp_path)],
        private_key_path=private,
        output_dir=output,
        metadata_version=1,
        expected_fingerprint=None,
    )

    assert built["fingerprint"] == key_report["fingerprint"]
    assert built["added"] == [{"package": "demo-adapter", "version": "1.0.0"}]
    assert (output / "demo_adapter-1.0.0-py3-none-any.whl").is_file()
    verified = verify_release_bundle(
        output / "catalog.json",
        public,
        output,
        pinned_fingerprint=key_report["fingerprint"],
    )
    assert verified["verified"] == [{"package": "demo-adapter", "version": "1.0.0"}]


def test_release_builder_embeds_pinned_checkpoint_guidance(tmp_path):
    private, _, _ = _keys(tmp_path)
    manifest = tmp_path / "checkpoints.json"
    manifest.write_text(
        json.dumps(
            {
                "demo-adapter@1.0.0": [
                    {
                        "source": "huggingface",
                        "repoId": "example/demo-27b-mlx",
                        "revision": "a" * 40,
                        "displayName": "Demo 27B MLX",
                        "estimatedSizeBytes": 15_000_000_000,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "release"
    build_release_bundle(
        [_wheel(tmp_path)],
        private_key_path=private,
        output_dir=output,
        metadata_version=1,
        expected_fingerprint=None,
        checkpoint_manifest=manifest,
    )
    envelope = json.loads((output / "catalog.json").read_text("utf-8"))
    checkpoint = envelope["payload"]["releases"][0]["checkpoints"][0]
    assert checkpoint["repoId"] == "example/demo-27b-mlx"
    assert checkpoint["revision"] == "a" * 40


def test_release_carries_forward_versions_and_requires_version_advance(tmp_path):
    private, public, _ = _keys(tmp_path)
    output = tmp_path / "release"
    build_release_bundle(
        [_wheel(tmp_path, "1.0.0")],
        private_key_path=private,
        output_dir=output,
        metadata_version=3,
        expected_fingerprint=None,
    )
    previous = output / "catalog.json"
    build_release_bundle(
        [_wheel(tmp_path, "1.1.0")],
        private_key_path=private,
        output_dir=output,
        metadata_version=4,
        previous_catalog=previous,
        expected_fingerprint=None,
    )
    verified = verify_release_bundle(output / "catalog.json", public, output)
    assert verified["metadata_version"] == 4
    assert {item["version"] for item in verified["verified"]} == {"1.0.0", "1.1.0"}

    with pytest.raises(ModelAdapterPackageError) as exc_info:
        build_release_bundle(
            [_wheel(tmp_path, "1.2.0")],
            private_key_path=private,
            output_dir=output,
            metadata_version=4,
            previous_catalog=previous,
            expected_fingerprint=None,
        )
    assert exc_info.value.code == "catalog_version_not_advanced"


def test_published_version_is_immutable(tmp_path):
    private, _, _ = _keys(tmp_path)
    output = tmp_path / "release"
    wheel = _wheel(tmp_path)
    build_release_bundle(
        [wheel],
        private_key_path=private,
        output_dir=output,
        metadata_version=1,
        expected_fingerprint=None,
    )
    previous = output / "catalog.json"
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("demo_adapter/changed.py", "changed = True\n")

    with pytest.raises(ModelAdapterPackageError) as exc_info:
        build_release_bundle(
            [wheel],
            private_key_path=private,
            output_dir=output,
            metadata_version=2,
            previous_catalog=previous,
            expected_fingerprint=None,
        )
    assert exc_info.value.code == "release_immutable"


def test_verify_rejects_modified_artifact(tmp_path):
    private, public, _ = _keys(tmp_path)
    output = tmp_path / "release"
    wheel = _wheel(tmp_path)
    build_release_bundle(
        [wheel],
        private_key_path=private,
        output_dir=output,
        metadata_version=1,
        expected_fingerprint=None,
    )
    published = output / wheel.name
    published.write_bytes(published.read_bytes() + b"tampered")

    with pytest.raises(ModelAdapterPackageError) as exc_info:
        verify_release_bundle(output / "catalog.json", public, output)
    assert exc_info.value.code == "artifact_digest_mismatch"


def test_key_generation_refuses_overwrite_and_uses_private_permissions(tmp_path):
    private, public, _ = _keys(tmp_path)
    assert private.stat().st_mode & 0o777 == 0o600
    assert public.read_text("ascii").startswith("-----BEGIN PUBLIC KEY-----")
    with pytest.raises(FileExistsError):
        generate_repository_key(private, public)


def test_build_rejects_readable_private_key(tmp_path):
    private, _, _ = _keys(tmp_path)
    private.chmod(0o644)
    with pytest.raises(ModelAdapterPackageError) as exc_info:
        build_release_bundle(
            [_wheel(tmp_path)],
            private_key_path=private,
            output_dir=tmp_path / "release",
            metadata_version=1,
            expected_fingerprint=None,
        )
    assert exc_info.value.code == "signing_key_permissions"


def test_build_defaults_to_ai2apps_production_trust_root(tmp_path):
    private, _, _ = _keys(tmp_path)
    with pytest.raises(ModelAdapterPackageError) as exc_info:
        build_release_bundle(
            [_wheel(tmp_path)],
            private_key_path=private,
            output_dir=tmp_path / "release",
            metadata_version=1,
        )
    assert exc_info.value.code == "repository_key_unpinned"
    assert not (tmp_path / "release" / "catalog.json").exists()


def test_carried_catalog_requires_complete_artifact_snapshot(tmp_path):
    private, _, _ = _keys(tmp_path)
    first = tmp_path / "first"
    build_release_bundle(
        [_wheel(tmp_path, "1.0.0")],
        private_key_path=private,
        output_dir=first,
        metadata_version=1,
        expected_fingerprint=None,
    )
    second = tmp_path / "second"
    with pytest.raises(ModelAdapterPackageError) as exc_info:
        build_release_bundle(
            [_wheel(tmp_path, "1.1.0")],
            private_key_path=private,
            output_dir=second,
            metadata_version=2,
            previous_catalog=first / "catalog.json",
            expected_fingerprint=None,
        )
    assert exc_info.value.code == "wheel_not_found"
    assert not (second / "catalog.json").exists()
