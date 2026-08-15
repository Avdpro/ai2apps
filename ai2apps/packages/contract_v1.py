"""AI2Apps Cloud package contract v1.

This module is deliberately independent from the older embedded-signature
Service/App archives.  Registry artifacts are authenticated before ZIP parsing
and carry a detached publisher signature.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

PACKAGE_PREFIX = b"AI2APPS-PACKAGE-RELEASE-V1\n"
REPOSITORY_PREFIX = b"AI2APPS-REPOSITORY-SNAPSHOT-V1\n"
KEY_PROOF_PREFIX = b"AI2APPS-PUBLISHER-KEY-PROOF-V1\n"
MAX_ARTIFACT_BYTES = 1_073_741_824
MAX_MANIFEST_BYTES = 1_048_576
MAX_FILES = 10_000

PACKAGE_TYPES = {
    "app": (".ai2app", "application/vnd.ai2apps.app+zip"),
    "agent": (".ai2agent", "application/vnd.ai2apps.agent+zip"),
    "service": (".ai2service", "application/vnd.ai2apps.service+zip"),
}
_PACKAGE_ID = re.compile(
    r"^[a-z][a-z0-9-]{1,78}[a-z0-9]/[a-z][a-z0-9-]{1,118}[a-z0-9]$"
)
_SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_B64URL_SIGNATURE = re.compile(r"^[A-Za-z0-9_-]{86}$")


class PackageContractError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ContractFile:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class InspectedContractPackage:
    archive_path: Path
    sha256: str
    size: int
    media_type: str
    manifest_sha256: str
    manifest: dict[str, Any]
    files: tuple[ContractFile, ...]


def _json_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def jcs(value: Any) -> str:
    """Canonicalize the contract's JSON subset using RFC 8785 ordering.

    Contract payloads contain strings, booleans, nulls, arrays, objects and
    integral counters/sizes.  Floats are rejected instead of approximating the
    ECMAScript number serialization required by full RFC 8785.
    """

    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        raise PackageContractError("unsupported_jcs_number", "Floating-point JSON is forbidden")
    if isinstance(value, str):
        return _json_string(value)
    if isinstance(value, list):
        return "[" + ",".join(jcs(item) for item in value) + "]"
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise PackageContractError("invalid_json_object", "JSON object keys must be strings")
        # Contract keys are ASCII. UTF-16 ordering is therefore identical to
        # Python's ordering, while still producing byte-compatible fixtures.
        return "{" + ",".join(
            f"{_json_string(key)}:{jcs(value[key])}" for key in sorted(value)
        ) + "}"
    raise PackageContractError("invalid_json_value", f"Unsupported JSON value: {type(value).__name__}")


def jcs_bytes(value: Any) -> bytes:
    return jcs(value).encode("utf-8")


def _exact_keys(value: dict, required: set[str], optional: set[str] = set()) -> None:
    keys = set(value)
    missing = required - keys
    extra = keys - required - optional
    if missing or extra:
        raise PackageContractError(
            "schema_invalid",
            "JSON object does not match the package contract",
            details={"missing": sorted(missing), "extra": sorted(extra)},
        )


def _safe_archive_path(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 240:
        raise PackageContractError("unsafe_archive_path", "Archive path is invalid")
    path = PurePosixPath(value)
    if value.startswith("/") or "\\" in value or "//" in value or any(
        item in {"", ".", ".."} for item in path.parts
    ):
        raise PackageContractError("unsafe_archive_path", f"Unsafe archive path: {value!r}")
    if not re.fullmatch(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*", value):
        raise PackageContractError("unsafe_archive_path", f"Unsupported archive path: {value!r}")
    return value


def validate_manifest(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PackageContractError("manifest_invalid", "ai2apps.json must be an object")
    _exact_keys(
        value,
        {"schemaVersion", "package", "compatibility", "entrypoints", "permissions", "dependencies", "files"},
        {"sbom"},
    )
    if value["schemaVersion"] != "ai2apps.package-manifest.v1":
        raise PackageContractError("manifest_schema_unsupported", "Unsupported package manifest schema")
    package = value["package"]
    if not isinstance(package, dict):
        raise PackageContractError("manifest_invalid", "package must be an object")
    _exact_keys(package, {"id", "type", "version", "displayName"}, {"description"})
    if not isinstance(package["id"], str) or not _PACKAGE_ID.fullmatch(package["id"]):
        raise PackageContractError("package_id_invalid", "Package ID is invalid")
    if package["type"] not in PACKAGE_TYPES:
        raise PackageContractError("package_type_invalid", "Package type is invalid")
    if not isinstance(package["version"], str) or not _SEMVER.fullmatch(package["version"]):
        raise PackageContractError("package_version_invalid", "Package version is invalid")
    if not isinstance(package["displayName"], str) or not 1 <= len(package["displayName"]) <= 160:
        raise PackageContractError("manifest_invalid", "displayName is invalid")
    if "description" in package and (
        not isinstance(package["description"], str) or len(package["description"]) > 2000
    ):
        raise PackageContractError("manifest_invalid", "description is invalid")
    compatibility = value["compatibility"]
    if not isinstance(compatibility, dict):
        raise PackageContractError("manifest_invalid", "compatibility must be an object")
    _exact_keys(compatibility, {"ai2apps"}, {"platforms", "architectures"})
    if not isinstance(compatibility["ai2apps"], str) or not compatibility["ai2apps"].strip():
        raise PackageContractError("manifest_invalid", "compatibility.ai2apps is invalid")
    for key, accepted in (
        ("platforms", {"darwin", "linux", "win32"}),
        ("architectures", {"arm64", "x64"}),
    ):
        if key in compatibility and (
            not isinstance(compatibility[key], list)
            or len(set(compatibility[key])) != len(compatibility[key])
            or not set(compatibility[key]).issubset(accepted)
        ):
            raise PackageContractError("manifest_invalid", f"compatibility.{key} is invalid")
    entrypoints = value["entrypoints"]
    if not isinstance(entrypoints, list) or not 1 <= len(entrypoints) <= 64:
        raise PackageContractError("manifest_invalid", "At least one entrypoint is required")
    entry_names: set[str] = set()
    for entry in entrypoints:
        if not isinstance(entry, dict):
            raise PackageContractError("manifest_invalid", "Entrypoint is invalid")
        _exact_keys(entry, {"name", "kind", "path"})
        if not isinstance(entry["name"], str) or not re.fullmatch(r"[a-z](?:[a-z0-9-]{0,62}[a-z0-9])?", entry["name"]):
            raise PackageContractError("manifest_invalid", "Entrypoint name is invalid")
        if entry["name"] in entry_names:
            raise PackageContractError("manifest_invalid", "Entrypoint names must be unique")
        entry_names.add(entry["name"])
        if entry["kind"] != package["type"]:
            raise PackageContractError("manifest_invalid", "Entrypoint kind must match package type")
        _safe_archive_path(entry["path"])
    permissions = value["permissions"]
    if not isinstance(permissions, list) or len(permissions) > 256:
        raise PackageContractError("manifest_invalid", "permissions is invalid")
    capabilities: set[str] = set()
    for permission in permissions:
        if not isinstance(permission, dict):
            raise PackageContractError("manifest_invalid", "Permission is invalid")
        _exact_keys(permission, {"capability", "reason", "required"})
        capability = permission["capability"]
        if not isinstance(capability, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*", capability):
            raise PackageContractError("manifest_invalid", "Permission capability is invalid")
        if capability in capabilities:
            raise PackageContractError("manifest_invalid", "Permission capabilities must be unique")
        capabilities.add(capability)
        if not isinstance(permission["reason"], str) or not 1 <= len(permission["reason"]) <= 500 or not isinstance(permission["required"], bool):
            raise PackageContractError("manifest_invalid", "Permission is invalid")
    dependencies = value["dependencies"]
    if not isinstance(dependencies, list) or len(dependencies) > 256:
        raise PackageContractError("manifest_invalid", "dependencies is invalid")
    dependency_ids: set[str] = set()
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            raise PackageContractError("manifest_invalid", "Dependency is invalid")
        _exact_keys(dependency, {"packageId", "version", "optional"})
        if not isinstance(dependency["packageId"], str) or not _PACKAGE_ID.fullmatch(dependency["packageId"]):
            raise PackageContractError("manifest_invalid", "Dependency ID is invalid")
        if dependency["packageId"] in dependency_ids:
            raise PackageContractError("manifest_invalid", "Dependency IDs must be unique")
        dependency_ids.add(dependency["packageId"])
        if not isinstance(dependency["version"], str) or not dependency["version"] or not isinstance(dependency["optional"], bool):
            raise PackageContractError("manifest_invalid", "Dependency is invalid")
    files = value["files"]
    if not isinstance(files, list) or len(files) > MAX_FILES:
        raise PackageContractError("manifest_invalid", "files is invalid")
    file_paths: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise PackageContractError("manifest_invalid", "File entry is invalid")
        _exact_keys(item, {"path", "sha256", "size"})
        path = _safe_archive_path(item["path"])
        if path == "ai2apps.json" or path in file_paths:
            raise PackageContractError("manifest_invalid", "Manifest file index is invalid")
        file_paths.add(path)
        if not isinstance(item["sha256"], str) or not _SHA256.fullmatch(item["sha256"]):
            raise PackageContractError("manifest_invalid", "File digest is invalid")
        if not isinstance(item["size"], int) or isinstance(item["size"], bool) or not 0 <= item["size"] <= MAX_ARTIFACT_BYTES:
            raise PackageContractError("manifest_invalid", "File size is invalid")
    for entry in entrypoints:
        if entry["path"] not in file_paths:
            raise PackageContractError("manifest_invalid", "Entrypoint is not indexed")
    if "sbom" in value:
        sbom = value["sbom"]
        if not isinstance(sbom, dict):
            raise PackageContractError("manifest_invalid", "SBOM is invalid")
        _exact_keys(sbom, {"format", "path"})
        if sbom["format"] not in {"spdx-json-2.3", "cyclonedx-json-1.6"} or _safe_archive_path(sbom["path"]) not in file_paths:
            raise PackageContractError("manifest_invalid", "SBOM is invalid")
    return value


def hash_artifact(path: str | Path, *, max_bytes: int = MAX_ARTIFACT_BYTES) -> tuple[str, int]:
    source = Path(path).resolve(strict=True)
    if not source.is_file():
        raise PackageContractError("artifact_invalid", "Package artifact must be a regular file")
    size = source.stat().st_size
    if not 1 <= size <= max_bytes:
        raise PackageContractError("artifact_size_limit", "Package artifact size is outside limits")
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest(), size


def inspect_package(path: str | Path) -> InspectedContractPackage:
    source = Path(path).resolve(strict=True)
    artifact_sha256, artifact_size = hash_artifact(source)
    try:
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_FILES + 1:
                raise PackageContractError("archive_file_limit", "Package has too many files")
            files: dict[str, ContractFile] = {}
            manifest_bytes: bytes | None = None
            expanded = 0
            for info in infos:
                name = info.filename
                if name.endswith("/"):
                    _safe_archive_path(name[:-1])
                    continue
                name = _safe_archive_path(name)
                if name in files or (name == "ai2apps.json" and manifest_bytes is not None):
                    raise PackageContractError("duplicate_archive_path", f"Duplicate archive path: {name}")
                mode = info.external_attr >> 16
                file_type = mode & 0o170000
                if file_type == stat.S_IFLNK or file_type not in {0, stat.S_IFREG}:
                    raise PackageContractError("archive_entry_forbidden", f"Non-regular entry: {name}")
                if info.flag_bits & 0x1:
                    raise PackageContractError("archive_encrypted", f"Encrypted entry: {name}")
                expanded += info.file_size
                if expanded > MAX_ARTIFACT_BYTES:
                    raise PackageContractError("archive_expansion_limit", "Expanded package is too large")
                content = archive.read(info)
                if name == "ai2apps.json":
                    if len(content) > MAX_MANIFEST_BYTES:
                        raise PackageContractError("manifest_size_limit", "ai2apps.json exceeds 1 MiB")
                    manifest_bytes = content
                else:
                    files[name] = ContractFile(name, hashlib.sha256(content).hexdigest(), len(content))
    except zipfile.BadZipFile as error:
        raise PackageContractError("archive_invalid", "Package is not a valid ZIP archive") from error
    if manifest_bytes is None:
        raise PackageContractError("manifest_missing", "Archive must contain root ai2apps.json")
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8", "strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackageContractError("manifest_invalid", "ai2apps.json must be valid UTF-8 JSON") from error
    manifest = validate_manifest(manifest)
    indexed = {item["path"]: item for item in manifest["files"]}
    if set(indexed) != set(files):
        raise PackageContractError("file_index_incomplete", "Manifest file index is not complete")
    for name, actual in files.items():
        expected = indexed[name]
        if expected["sha256"] != actual.sha256 or expected["size"] != actual.size:
            raise PackageContractError("file_digest_mismatch", f"File hash/size mismatch: {name}")
    kind = manifest["package"]["type"]
    extension, media_type = PACKAGE_TYPES[kind]
    if source.suffix.lower() != extension:
        raise PackageContractError("artifact_extension_mismatch", f"Package type {kind} requires {extension}")
    return InspectedContractPackage(
        source,
        artifact_sha256,
        artifact_size,
        media_type,
        hashlib.sha256(jcs_bytes(manifest)).hexdigest(),
        manifest,
        tuple(sorted(files.values(), key=lambda item: item.path)),
    )


def _b64url_decode(value: str) -> bytes:
    if not _B64URL_SIGNATURE.fullmatch(value):
        raise PackageContractError("signature_invalid", "Signature is not unpadded Base64url Ed25519")
    return base64.urlsafe_b64decode(value + "==")


def _public_key(pem: str) -> Ed25519PublicKey:
    try:
        key = serialization.load_pem_public_key(pem.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError) as error:
        raise PackageContractError("public_key_invalid", "Publisher public key is invalid") from error
    if not isinstance(key, Ed25519PublicKey):
        raise PackageContractError("public_key_invalid", "Publisher key must be Ed25519")
    return key


def public_key_fingerprint(pem: str) -> str:
    key = _public_key(pem)
    der = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(der).hexdigest()


def _validate_signature_envelope(envelope: Any) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        raise PackageContractError("envelope_invalid", "Signature envelope must be an object")
    _exact_keys(envelope, {"schemaVersion", "payload", "signature"})
    if envelope["schemaVersion"] != "ai2apps.signature-envelope.v1":
        raise PackageContractError("envelope_invalid", "Unsupported signature envelope")
    payload = envelope["payload"]
    signature = envelope["signature"]
    if not isinstance(payload, dict) or not isinstance(signature, dict):
        raise PackageContractError("envelope_invalid", "Signature envelope is invalid")
    _exact_keys(payload, {"domain", "publisherId", "publisherKeyId", "package", "artifact", "manifest"})
    _exact_keys(signature, {"algorithm", "value"})
    if payload["domain"] != "ai2apps.package-release.v1" or signature["algorithm"] != "Ed25519":
        raise PackageContractError("envelope_invalid", "Signature domain/algorithm is invalid")
    _b64url_decode(signature["value"])
    package = payload["package"]
    artifact = payload["artifact"]
    manifest = payload["manifest"]
    if not all(isinstance(item, dict) for item in (package, artifact, manifest)):
        raise PackageContractError("envelope_invalid", "Signed payload is invalid")
    _exact_keys(package, {"id", "type", "version"})
    _exact_keys(artifact, {"mediaType", "sha256", "size"})
    _exact_keys(manifest, {"sha256"})
    if not isinstance(package["id"], str) or not _PACKAGE_ID.fullmatch(package["id"]):
        raise PackageContractError("envelope_invalid", "Signed package ID is invalid")
    if package["type"] not in PACKAGE_TYPES or not isinstance(package["version"], str) or not _SEMVER.fullmatch(package["version"]):
        raise PackageContractError("envelope_invalid", "Signed package identity is invalid")
    if artifact["mediaType"] != PACKAGE_TYPES[package["type"]][1] or not isinstance(artifact["sha256"], str) or not _SHA256.fullmatch(artifact["sha256"]):
        raise PackageContractError("envelope_invalid", "Signed artifact identity is invalid")
    if not isinstance(artifact["size"], int) or isinstance(artifact["size"], bool) or not 1 <= artifact["size"] <= MAX_ARTIFACT_BYTES:
        raise PackageContractError("envelope_invalid", "Signed artifact size is invalid")
    if not isinstance(manifest["sha256"], str) or not _SHA256.fullmatch(manifest["sha256"]):
        raise PackageContractError("envelope_invalid", "Signed manifest digest is invalid")
    return envelope


def verify_signed_package(
    path: str | Path,
    envelope: Any,
    public_key_pem: str,
    *,
    precomputed_hash: tuple[str, int] | None = None,
) -> InspectedContractPackage:
    """Verify publisher/authored bytes before opening the archive."""

    envelope = _validate_signature_envelope(envelope)
    try:
        _public_key(public_key_pem).verify(
            _b64url_decode(envelope["signature"]["value"]),
            PACKAGE_PREFIX + jcs_bytes(envelope["payload"]),
        )
    except InvalidSignature as error:
        raise PackageContractError("publisher_signature_invalid", "Publisher signature verification failed") from error
    actual_sha256, actual_size = precomputed_hash or hash_artifact(path)
    artifact = envelope["payload"]["artifact"]
    if actual_sha256 != artifact["sha256"] or actual_size != artifact["size"]:
        raise PackageContractError("artifact_digest_mismatch", "Signed artifact digest or size does not match bytes")
    inspected = inspect_package(path)
    payload = envelope["payload"]
    identity = inspected.manifest["package"]
    if (
        inspected.manifest_sha256 != payload["manifest"]["sha256"]
        or inspected.media_type != artifact["mediaType"]
        or any(identity[key] != payload["package"][key] for key in ("id", "type", "version"))
    ):
        raise PackageContractError("signed_metadata_mismatch", "Signed metadata does not match package manifest")
    return inspected


def create_signature_envelope(
    inspected: InspectedContractPackage,
    private_key_pem: str,
    *,
    publisher_id: str,
    publisher_key_id: str,
) -> dict[str, Any]:
    try:
        key = serialization.load_pem_private_key(private_key_pem.encode("ascii"), password=None)
    except (ValueError, TypeError, UnicodeEncodeError) as error:
        raise PackageContractError("private_key_invalid", "Publisher private key is invalid") from error
    if not isinstance(key, Ed25519PrivateKey):
        raise PackageContractError("private_key_invalid", "Publisher key must be Ed25519")
    package = inspected.manifest["package"]
    payload = {
        "domain": "ai2apps.package-release.v1",
        "publisherId": publisher_id,
        "publisherKeyId": publisher_key_id,
        "package": {name: package[name] for name in ("id", "type", "version")},
        "artifact": {"mediaType": inspected.media_type, "sha256": inspected.sha256, "size": inspected.size},
        "manifest": {"sha256": inspected.manifest_sha256},
    }
    signature = base64.urlsafe_b64encode(key.sign(PACKAGE_PREFIX + jcs_bytes(payload))).decode("ascii").rstrip("=")
    return {"schemaVersion": "ai2apps.signature-envelope.v1", "payload": payload, "signature": {"algorithm": "Ed25519", "value": signature}}


def generate_publisher_key() -> tuple[str, str, str]:
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return private_pem, public_pem, public_key_fingerprint(public_pem)


def create_key_proof(payload: dict[str, Any], private_key_pem: str) -> str:
    key = serialization.load_pem_private_key(private_key_pem.encode("ascii"), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise PackageContractError("private_key_invalid", "Publisher key must be Ed25519")
    return base64.urlsafe_b64encode(key.sign(KEY_PROOF_PREFIX + jcs_bytes(payload))).decode("ascii").rstrip("=")


def verify_repository_snapshot(
    envelope: Any,
    public_key_pem: str,
    *,
    pinned_fingerprint: str,
) -> dict[str, Any]:
    if public_key_fingerprint(public_key_pem) != pinned_fingerprint:
        raise PackageContractError("repository_key_unpinned", "Repository key does not match the local pin")
    if not isinstance(envelope, dict):
        raise PackageContractError("repository_metadata_invalid", "Repository metadata must be an object")
    _exact_keys(envelope, {"schemaVersion", "payload", "signature"})
    signature = envelope["signature"]
    payload = envelope["payload"]
    if envelope["schemaVersion"] != "ai2apps.repository-snapshot-envelope.v1" or not isinstance(signature, dict) or not isinstance(payload, dict):
        raise PackageContractError("repository_metadata_invalid", "Repository metadata is invalid")
    _exact_keys(signature, {"keyId", "algorithm", "value"})
    if signature["keyId"] != pinned_fingerprint or signature["algorithm"] != "Ed25519":
        raise PackageContractError("repository_metadata_invalid", "Repository signature metadata is invalid")
    try:
        _public_key(public_key_pem).verify(
            _b64url_decode(signature["value"]),
            REPOSITORY_PREFIX + jcs_bytes(payload),
        )
    except InvalidSignature as error:
        raise PackageContractError("repository_signature_invalid", "Repository snapshot signature is invalid") from error
    _exact_keys(payload, {"domain", "version", "generatedAt", "expiresAt", "releases"})
    if payload["domain"] != "ai2apps.repository-snapshot.v1" or not isinstance(payload["version"], int) or payload["version"] < 1 or not isinstance(payload["releases"], list):
        raise PackageContractError("repository_metadata_invalid", "Repository snapshot payload is invalid")
    return payload


def build_package(source: str | Path, output: str | Path) -> InspectedContractPackage:
    source_path = Path(source).resolve(strict=True)
    manifest_path = source_path / "ai2apps.json"
    if not source_path.is_dir() or not manifest_path.is_file():
        raise PackageContractError("source_invalid", "Package source must contain ai2apps.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackageContractError("manifest_invalid", "ai2apps.json is invalid") from error
    rows = []
    for file in sorted(item for item in source_path.rglob("*") if item.is_file() and item != manifest_path):
        relative = file.relative_to(source_path).as_posix()
        _safe_archive_path(relative)
        content = file.read_bytes()
        rows.append({"path": relative, "sha256": hashlib.sha256(content).hexdigest(), "size": len(content)})
    manifest["files"] = rows
    manifest = validate_manifest(manifest)
    output_path = Path(output).expanduser().resolve()
    expected_extension = PACKAGE_TYPES[manifest["package"]["type"]][0]
    if output_path.suffix.lower() != expected_extension:
        raise PackageContractError("artifact_extension_mismatch", f"Output requires {expected_extension}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            info = zipfile.ZipInfo("ai2apps.json")
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.external_attr = 0o100644 << 16
            archive.writestr(info, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
            for row in rows:
                info = zipfile.ZipInfo(row["path"])
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.external_attr = 0o100644 << 16
                archive.writestr(info, (source_path / row["path"]).read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
        os.replace(temporary, output_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return inspect_package(output_path)
