"""Test-instance-only import of signed, unpublished App candidates.

This does not register a release or modify Registry installation state.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from .contract_v1 import public_key_fingerprint, verify_signed_package
from .registry import RegistryError


def require_test_instance(runtime) -> None:
    expected = Path.home() / "Library/Application Support/AI2Apps/instances/test/data"
    paths = getattr(getattr(runtime, "config", None), "paths", None)
    if (
        os.environ.get("AI2APPS_INSTANCE_ID") != "test"
        or os.environ.get("AI2APPS_SUPERVISED") != "helper"
        or paths is None
        or expected.resolve() != expected
        or paths.base_path.resolve() != expected.resolve()
    ):
        raise RegistryError("test_only", "Candidate import is available only in the isolated Test instance")


async def import_candidate(runtime, archive_path: str, *, expected_digest: str | None = None):
    require_test_instance(runtime)
    source = Path(archive_path).expanduser().resolve(strict=True)
    if source.suffix != ".ai2app" or source.stat().st_size > 128 * 1024 * 1024:
        raise RegistryError("candidate_type", "Only App candidates up to 128 MiB are supported")
    sidecar = source.with_suffix(source.suffix + ".envelope.json")
    if sidecar.stat().st_size > 64 * 1024:
        raise RegistryError("candidate_envelope", "Signature envelope is too large")
    envelope = json.loads(sidecar.read_text())
    registry = runtime.registry_packages
    snapshot = await registry.trusted_snapshot()
    payload = envelope.get("payload", {})
    package_id = payload.get("package", {}).get("id", "")
    publisher_id = payload.get("publisherId")
    key_id = payload.get("publisherKeyId")
    key = None
    for release in snapshot["releases"]:
        publisher = release.get("publisher", {})
        candidate_key = publisher.get("key", {})
        if (release.get("status") == "published"
                and candidate_key.get("status", "active") == "active"
                and publisher.get("id") == publisher_id and candidate_key.get("id") == key_id
                and release.get("packageId", "").split("/")[0] == package_id.split("/")[0]):
            key = candidate_key
            break
    if not key or public_key_fingerprint(key["publicKeyPem"]) != key["fingerprintSha256"]:
        raise RegistryError("candidate_publisher", "Publisher key and namespace must be bound by trusted Registry metadata")
    # Stage once so the reviewed bytes cannot change while audit/install awaits.
    with tempfile.TemporaryDirectory(prefix="ai2apps-test-candidate-") as directory:
        staged = Path(directory) / source.name
        shutil.copyfile(source, staged)
        inspected = verify_signed_package(staged, envelope, key["publicKeyPem"])
        if inspected.manifest["package"]["type"] != "app":
            raise RegistryError("candidate_type", "Only App candidates are supported")
        if any(not dep["optional"] for dep in inspected.manifest["dependencies"]):
            raise RegistryError("candidate_dependencies", "Candidates with required Package dependencies need Registry installation")
        registry._check_compatibility(inspected.manifest["compatibility"])
        bundle = registry._interactive_bundle(inspected, envelope)
        audit = await runtime.extension_manager._audit(bundle)
        result = {"packageId": package_id, "version": bundle.version,
                  "sha256": inspected.sha256, "audit": audit,
                  "published": False, "installed": False}
        if expected_digest is not None:
            if expected_digest != inspected.sha256:
                raise RegistryError("candidate_changed", "Candidate changed since review; inspect again")
            record = await runtime.extension_manager.install_verified_bundle(
                bundle, {"trust": "test-only-publisher-signed-candidate", "envelope": envelope,
                         "repository_metadata_version": snapshot["version"]},
                approve_review=True,
            )
            result.update(installed=True, status=record.status.value)
        return result
