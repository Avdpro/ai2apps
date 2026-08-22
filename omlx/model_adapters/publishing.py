# SPDX-License-Identifier: Apache-2.0
"""Offline tooling for building and verifying signed adapter release bundles."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ai2apps.packages.contract_v1 import (
    REPOSITORY_PREFIX,
    jcs_bytes,
    public_key_fingerprint,
    verify_repository_snapshot,
)
from ai2apps.packages.repository_config import AI2APPS_REPOSITORY_FINGERPRINT

from .catalog import validate_checkpoint_record
from .packages import ModelAdapterPackageError, ModelAdapterPackageManager


def _private_key(path: Path) -> Ed25519PrivateKey:
    path = path.expanduser().resolve(strict=True)
    if path.stat().st_mode & 0o077:
        raise ModelAdapterPackageError(
            "signing_key_permissions",
            "Repository private key must not be readable by group or others",
        )
    try:
        value = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (TypeError, ValueError) as exc:
        raise ModelAdapterPackageError(
            "signing_key_invalid", "Repository private key is invalid"
        ) from exc
    if not isinstance(value, Ed25519PrivateKey):
        raise ModelAdapterPackageError(
            "signing_key_invalid", "Repository private key must be Ed25519"
        )
    return value


def _public_pem(private: Ed25519PrivateKey) -> str:
    return (
        private.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )


def _atomic_write(path: Path, content: bytes, *, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_path = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    temporary = Path(raw_path)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def generate_repository_key(private_path: Path, public_path: Path) -> dict[str, str]:
    """Create a new offline Ed25519 trust root, refusing to overwrite files."""
    private_path = private_path.expanduser().resolve()
    public_path = public_path.expanduser().resolve()
    if private_path.exists() or public_path.exists():
        raise FileExistsError("Refusing to overwrite an existing repository key")
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = _public_pem(private)
    _atomic_write(private_path, private_pem, mode=0o600)
    _atomic_write(public_path, public_pem.encode("ascii"))
    return {
        "private_key": str(private_path),
        "public_key": str(public_path),
        "fingerprint": public_key_fingerprint(public_pem),
    }


def _signed_envelope(
    payload: dict[str, Any], private: Ed25519PrivateKey
) -> dict[str, Any]:
    public_pem = _public_pem(private)
    fingerprint = public_key_fingerprint(public_pem)
    signature = private.sign(REPOSITORY_PREFIX + jcs_bytes(payload))
    return {
        "schemaVersion": "ai2apps.repository-snapshot-envelope.v1",
        "payload": payload,
        "signature": {
            "keyId": fingerprint,
            "algorithm": "Ed25519",
            "value": base64.urlsafe_b64encode(signature).decode("ascii").rstrip("="),
        },
    }


def _previous_releases(
    path: Path | None,
    *,
    public_pem: str,
    fingerprint: str,
    metadata_version: int,
) -> list[dict[str, Any]]:
    if path is None:
        return []
    try:
        envelope = json.loads(path.expanduser().resolve(strict=True).read_text("utf-8"))
        payload = verify_repository_snapshot(
            envelope, public_pem, pinned_fingerprint=fingerprint
        )
    except (OSError, ValueError) as exc:
        raise ModelAdapterPackageError(
            "previous_catalog_invalid", "Previous catalog is invalid"
        ) from exc
    if metadata_version <= payload["version"]:
        raise ModelAdapterPackageError(
            "catalog_version_not_advanced",
            "New catalog version must be greater than the previous signed version",
            details={"previous": payload["version"], "requested": metadata_version},
        )
    return list(payload["releases"])


def _checkpoint_manifest(
    path: Path | None,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    if path is None:
        return {}
    try:
        value = json.loads(path.expanduser().resolve(strict=True).read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise ModelAdapterPackageError(
            "checkpoint_manifest_invalid", "Checkpoint manifest is invalid"
        ) from exc
    if not isinstance(value, dict):
        raise ModelAdapterPackageError(
            "checkpoint_manifest_invalid", "Checkpoint manifest must be an object"
        )
    output: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for identity, rows in value.items():
        if (
            not isinstance(identity, str)
            or "@" not in identity
            or not isinstance(rows, list)
        ):
            raise ModelAdapterPackageError(
                "checkpoint_manifest_invalid",
                "Checkpoint manifest keys must use package@version",
            )
        package_id, version = identity.rsplit("@", 1)
        normalized_rows = []
        for row in rows:
            checked = validate_checkpoint_record(row)
            normalized = {
                "source": checked["source"],
                "repoId": checked["repo_id"],
                "revision": checked["revision"],
                "displayName": checked["display_name"],
            }
            if checked["estimated_size_bytes"] is not None:
                normalized["estimatedSizeBytes"] = checked["estimated_size_bytes"]
            normalized_rows.append(normalized)
        output[(package_id, version)] = normalized_rows
    return output


def build_release_bundle(
    wheels: Iterable[Path],
    *,
    private_key_path: Path,
    output_dir: Path,
    metadata_version: int,
    artifact_url_prefix: str = ".",
    expires_days: int = 30,
    previous_catalog: Path | None = None,
    generated_at: datetime | None = None,
    expected_fingerprint: str | None = AI2APPS_REPOSITORY_FINGERPRINT,
    checkpoint_manifest: Path | None = None,
) -> dict[str, Any]:
    """Validate wheels and atomically emit deployable artifacts plus catalog."""
    if metadata_version < 1:
        raise ValueError("metadata_version must be positive")
    if not 1 <= expires_days <= 90:
        raise ValueError("expires_days must be between 1 and 90")
    wheel_paths = [path.expanduser().resolve(strict=True) for path in wheels]
    if not wheel_paths:
        raise ValueError("At least one wheel is required")

    private = _private_key(private_key_path)
    public_pem = _public_pem(private)
    fingerprint = public_key_fingerprint(public_pem)
    if (
        expected_fingerprint is not None
        and expected_fingerprint.removeprefix("sha256:") != fingerprint
    ):
        raise ModelAdapterPackageError(
            "repository_key_unpinned",
            "Signing key does not match the expected repository trust root",
            details={
                "expected": expected_fingerprint.removeprefix("sha256:"),
                "received": fingerprint,
            },
        )
    releases = _previous_releases(
        previous_catalog,
        public_pem=public_pem,
        fingerprint=fingerprint,
        metadata_version=metadata_version,
    )
    existing = {
        (item.get("packageId"), item.get("version")): item
        for item in releases
        if isinstance(item, dict)
    }

    with tempfile.TemporaryDirectory(prefix="omlx-adapter-release-check-") as base:
        manager = ModelAdapterPackageManager(base)
        additions: list[tuple[dict[str, Any], Path]] = []
        artifact_copies: list[tuple[dict[str, Any], Path]] = []
        for wheel in wheel_paths:
            inspected = manager.inspect(wheel)
            identity = (inspected["normalized_name"], inspected["version"])
            if identity in existing:
                prior = existing[identity]
                prior_digest = (
                    prior.get("artifact", {}).get("sha256")
                    if isinstance(prior.get("artifact"), dict)
                    else None
                )
                if prior_digest != inspected["sha256"]:
                    raise ModelAdapterPackageError(
                        "release_immutable",
                        "A published package version cannot be replaced with new bytes",
                        details={"package": identity[0], "version": identity[1]},
                    )
                artifact_copies.append((prior, wheel))
                continue
            url = f"{artifact_url_prefix.rstrip('/')}/{wheel.name}"
            release = {
                "packageId": inspected["normalized_name"],
                "packageType": "model-adapter",
                "version": inspected["version"],
                "status": "published",
                "displayName": inspected["name"],
                "artifact": {
                    "url": url,
                    "sha256": inspected["sha256"],
                    "size": wheel.stat().st_size,
                },
            }
            releases.append(release)
            existing[identity] = release
            additions.append((release, wheel))
            artifact_copies.append((release, wheel))

    checkpoint_updates = _checkpoint_manifest(checkpoint_manifest)
    for identity, checkpoints in checkpoint_updates.items():
        release = existing.get(identity)
        if release is None:
            raise ModelAdapterPackageError(
                "checkpoint_release_not_found",
                "Checkpoint manifest references an absent adapter release",
                details={"package": identity[0], "version": identity[1]},
            )
        release["checkpoints"] = checkpoints

    now = (generated_at or datetime.now(UTC)).astimezone(UTC)
    payload = {
        "domain": "ai2apps.repository-snapshot.v1",
        "version": metadata_version,
        "generatedAt": now.isoformat().replace("+00:00", "Z"),
        "expiresAt": (now + timedelta(days=expires_days))
        .isoformat()
        .replace("+00:00", "Z"),
        "releases": releases,
    }
    envelope = _signed_envelope(payload, private)
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for release, source in artifact_copies:
        destination = output_dir / source.name
        if destination.exists():
            digest = hashlib.sha256(destination.read_bytes()).hexdigest()
            if digest != release["artifact"]["sha256"]:
                raise ModelAdapterPackageError(
                    "artifact_conflict",
                    f"Output artifact already exists with different bytes: {destination.name}",
                )
        else:
            temporary = output_dir / f".{source.name}.{os.getpid()}.tmp"
            try:
                shutil.copy2(source, temporary)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)

    # A catalog is a complete snapshot. Refuse to publish it unless every
    # carried-forward artifact is present and still has the signed identity.
    with tempfile.TemporaryDirectory(prefix="omlx-adapter-release-final-") as base:
        manager = ModelAdapterPackageManager(base)
        for release in releases:
            if (
                not isinstance(release, dict)
                or release.get("packageType") != "model-adapter"
            ):
                raise ModelAdapterPackageError(
                    "catalog_metadata_invalid", "Catalog contains a non-adapter release"
                )
            checkpoint_rows = release.get("checkpoints", [])
            if not isinstance(checkpoint_rows, list):
                raise ModelAdapterPackageError(
                    "catalog_metadata_invalid", "Catalog checkpoints are invalid"
                )
            for checkpoint in checkpoint_rows:
                validate_checkpoint_record(checkpoint)
            artifact = release.get("artifact")
            if not isinstance(artifact, dict) or not isinstance(
                artifact.get("url"), str
            ):
                raise ModelAdapterPackageError(
                    "catalog_metadata_invalid", "Catalog artifact is invalid"
                )
            filename = Path(unquote(urlsplit(artifact["url"]).path)).name
            wheel = output_dir / filename
            if not filename.endswith(".whl") or not wheel.is_file():
                raise ModelAdapterPackageError(
                    "wheel_not_found", f"Catalog wheel is missing: {filename}"
                )
            content = wheel.read_bytes()
            if len(content) != artifact.get("size") or hashlib.sha256(
                content
            ).hexdigest() != artifact.get("sha256"):
                raise ModelAdapterPackageError(
                    "artifact_digest_mismatch",
                    f"Artifact does not match catalog: {filename}",
                )
            inspected = manager.inspect(wheel)
            if inspected["normalized_name"] != release.get("packageId") or inspected[
                "version"
            ] != release.get("version"):
                raise ModelAdapterPackageError(
                    "artifact_identity_mismatch",
                    f"Artifact identity is invalid: {filename}",
                )

    key_document = (
        json.dumps(
            {"publicKeyPem": public_pem}, ensure_ascii=False, indent=2, sort_keys=True
        ).encode("utf-8")
        + b"\n"
    )
    catalog_document = (
        json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True).encode(
            "utf-8"
        )
        + b"\n"
    )
    _atomic_write(output_dir / "repository-key.json", key_document)
    # Catalog is written last so a static-host deployment can expose artifacts
    # and its key before clients observe the new signed snapshot.
    _atomic_write(output_dir / "catalog.json", catalog_document)
    return {
        "output_dir": str(output_dir),
        "catalog": str(output_dir / "catalog.json"),
        "repository_key": str(output_dir / "repository-key.json"),
        "fingerprint": fingerprint,
        "metadata_version": metadata_version,
        "added": [
            {"package": item[0]["packageId"], "version": item[0]["version"]}
            for item in additions
        ],
        "release_count": len(releases),
        "checkpoint_release_count": len(checkpoint_updates),
    }


def verify_release_bundle(
    catalog_path: Path,
    public_key_path: Path,
    artifacts_dir: Path,
    *,
    pinned_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Verify signature, every artifact digest, and every wheel identity."""
    public_pem = public_key_path.expanduser().resolve(strict=True).read_text("ascii")
    fingerprint = public_key_fingerprint(public_pem)
    if pinned_fingerprint and pinned_fingerprint.removeprefix("sha256:") != fingerprint:
        raise ModelAdapterPackageError(
            "repository_key_unpinned", "Repository key does not match the supplied pin"
        )
    envelope = json.loads(
        catalog_path.expanduser().resolve(strict=True).read_text("utf-8")
    )
    payload = verify_repository_snapshot(
        envelope, public_pem, pinned_fingerprint=fingerprint
    )
    try:
        expires_at = datetime.fromisoformat(payload["expiresAt"].replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ModelAdapterPackageError(
            "catalog_metadata_invalid", "Catalog expiry is invalid"
        ) from exc
    if expires_at.tzinfo is None or expires_at.astimezone(UTC) <= datetime.now(UTC):
        raise ModelAdapterPackageError(
            "catalog_metadata_expired", "Catalog has expired"
        )
    artifacts_dir = artifacts_dir.expanduser().resolve(strict=True)
    verified = []
    with tempfile.TemporaryDirectory(prefix="omlx-adapter-release-verify-") as base:
        manager = ModelAdapterPackageManager(base)
        for release in payload["releases"]:
            if (
                not isinstance(release, dict)
                or release.get("packageType") != "model-adapter"
            ):
                raise ModelAdapterPackageError(
                    "catalog_metadata_invalid", "Catalog contains a non-adapter release"
                )
            checkpoint_rows = release.get("checkpoints", [])
            if not isinstance(checkpoint_rows, list):
                raise ModelAdapterPackageError(
                    "catalog_metadata_invalid", "Catalog checkpoints are invalid"
                )
            for checkpoint in checkpoint_rows:
                validate_checkpoint_record(checkpoint)
            artifact = release.get("artifact")
            if not isinstance(artifact, dict) or not isinstance(
                artifact.get("url"), str
            ):
                raise ModelAdapterPackageError(
                    "catalog_metadata_invalid", "Catalog artifact is invalid"
                )
            filename = Path(unquote(urlsplit(artifact["url"]).path)).name
            wheel = (artifacts_dir / filename).resolve()
            try:
                wheel.relative_to(artifacts_dir)
            except ValueError as exc:
                raise ModelAdapterPackageError(
                    "catalog_metadata_invalid", "Artifact path escapes its bundle"
                ) from exc
            if not filename.endswith(".whl") or not wheel.is_file():
                raise ModelAdapterPackageError(
                    "wheel_not_found", f"Catalog wheel is missing: {filename}"
                )
            content = wheel.read_bytes()
            if len(content) != artifact.get("size") or hashlib.sha256(
                content
            ).hexdigest() != artifact.get("sha256"):
                raise ModelAdapterPackageError(
                    "artifact_digest_mismatch",
                    f"Artifact does not match catalog: {filename}",
                )
            inspected = manager.inspect(wheel)
            if inspected["normalized_name"] != release.get("packageId") or inspected[
                "version"
            ] != release.get("version"):
                raise ModelAdapterPackageError(
                    "artifact_identity_mismatch",
                    f"Artifact identity is invalid: {filename}",
                )
            verified.append(
                {
                    "package": inspected["normalized_name"],
                    "version": inspected["version"],
                }
            )
    return {
        "fingerprint": fingerprint,
        "metadata_version": payload["version"],
        "verified": verified,
    }
