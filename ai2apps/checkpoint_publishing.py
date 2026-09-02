"""Offline builder for Publisher-signed checkpoint distributions."""

from __future__ import annotations

import base64
import fnmatch
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ai2apps.checkpoint_distribution import (
    CheckpointDistributionManifest,
    parse_checkpoint_distribution_manifest,
    verify_checkpoint_distribution_envelope,
)
from ai2apps.packages.contract_v1 import jcs_bytes, public_key_fingerprint

_DOMAIN = b"AI2APPS-CHECKPOINT-DISTRIBUTION-V1\n"
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
FULL_DUAL_DOWNLOAD_BUILDER = "ai2apps-local/checkpoint-full-dual-download-v1"
METADATA_VERIFIED_BUILDER = "ai2apps-local/checkpoint-metadata-verified-v1"
_SPEC_KEYS = {
    "schema",
    "distributionId",
    "modelId",
    "repoId",
    "revision",
    "format",
    "quantization",
    "pieceSize",
    "license",
    "includePatterns",
    "sourceRepositories",
}


class CheckpointPublishingError(ValueError):
    pass


@dataclass(frozen=True)
class BuiltCheckpointDistribution:
    manifest: CheckpointDistributionManifest
    envelope: dict[str, Any]
    file_count: int
    source_roots: dict[str, Path]
    verification_builder: str = FULL_DUAL_DOWNLOAD_BUILDER


def verification_receipt_for_envelope(
    envelope: Any, *, builder: str = FULL_DUAL_DOWNLOAD_BUILDER
) -> dict[str, Any]:
    """Derive the Cloud receipt from an envelope built after dual-source verification."""

    if not isinstance(envelope, dict):
        raise CheckpointPublishingError("checkpoint envelope must be an object")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise CheckpointPublishingError("checkpoint envelope payload is invalid")
    manifest = parse_checkpoint_distribution_manifest(payload.get("manifest"))
    if payload.get("manifestDigest") != manifest.digest:
        raise CheckpointPublishingError("checkpoint manifest digest does not match")
    providers = {
        source.get("type")
        for source in manifest.raw["distribution"]["sources"]
        if isinstance(source, dict)
    }
    if providers != {"huggingface", "modelscope"}:
        raise CheckpointPublishingError(
            "verification receipt requires Hugging Face and ModelScope sources"
        )
    return {
        "builder": builder,
        "fileCount": len(manifest.files),
        "pieceCount": len(manifest.piece_hashes),
        "estimatedSizeBytes": str(manifest.estimated_size_bytes),
        "verifiedProviders": ["huggingface", "modelscope"],
    }


@dataclass(frozen=True)
class CheckpointFileMetadata:
    path: str
    size: int
    sha256: str


def fetch_modelscope_file_metadata(
    repo_id: str,
    revision: str,
    *,
    include_patterns: tuple[str, ...] | None = None,
    api: Any | None = None,
) -> tuple[CheckpointFileMetadata, ...]:
    """Fetch authoritative final-file metadata without downloading model bytes."""

    if api is None:
        from modelscope_hub import HubApi

        api = HubApi()
    rows: list[CheckpointFileMetadata] = []
    for item in api.list_repo_files(
        repo_id=repo_id, repo_type="model", revision=revision, recursive=True
    ):
        if getattr(item, "is_dir", False) or getattr(item, "type", "blob") == "tree":
            continue
        path = _safe_relative_path(str(getattr(item, "path", "")))
        if include_patterns and not any(
            fnmatch.fnmatchcase(path, pattern) for pattern in include_patterns
        ):
            continue
        size = getattr(item, "size", 0)
        sha256 = getattr(item, "sha256", None)
        if (
            not isinstance(size, int)
            or isinstance(size, bool)
            or size <= 0
            or not isinstance(sha256, str)
            or not _SHA256.fullmatch(sha256)
        ):
            raise CheckpointPublishingError(
                f"ModelScope did not provide final-file SHA-256 metadata: {path}"
            )
        rows.append(
            CheckpointFileMetadata(path=path, size=size, sha256=sha256.lower())
        )
    if not rows:
        raise CheckpointPublishingError("ModelScope returned no file metadata")
    return tuple(rows)


def _safe_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise CheckpointPublishingError(f"unsafe checkpoint path: {value!r}")
    return value


def _source_repositories(spec: dict[str, Any]) -> tuple[dict[str, str], ...]:
    repositories = spec.get("sourceRepositories")
    if not isinstance(repositories, list) or len(repositories) != 2:
        raise CheckpointPublishingError(
            "Phase 1 distributions require exactly one Hugging Face and one ModelScope repository"
        )
    normalized: list[dict[str, str]] = []
    providers: set[str] = set()
    for source in repositories:
        if not isinstance(source, dict) or set(source) != {
            "type",
            "repoId",
            "revision",
            "access",
        }:
            raise CheckpointPublishingError("sourceRepositories entry is invalid")
        provider = source.get("type")
        if provider not in {"huggingface", "modelscope"} or provider in providers:
            raise CheckpointPublishingError("sourceRepositories providers are invalid")
        if not all(isinstance(source.get(key), str) and source[key] for key in source):
            raise CheckpointPublishingError("sourceRepositories entry is invalid")
        providers.add(provider)
        normalized.append(dict(source))
    if providers != {"huggingface", "modelscope"}:
        raise CheckpointPublishingError("both Hub providers are required")
    return tuple(normalized)


def _selected_paths(
    roots: dict[str, Path], patterns: tuple[str, ...]
) -> tuple[str, ...]:
    provider_paths: dict[str, set[str]] = {}
    for provider, root in roots.items():
        paths: set[str] = set()
        for candidate in root.rglob("*"):
            if not candidate.is_file():
                continue
            relative = _safe_relative_path(candidate.relative_to(root).as_posix())
            if relative.startswith(".cache/") or relative == ".gitattributes":
                continue
            if any(fnmatch.fnmatchcase(relative, pattern) for pattern in patterns):
                paths.add(relative)
        provider_paths[provider] = paths
    values = tuple(provider_paths.values())
    if not values or not values[0]:
        raise CheckpointPublishingError("includePatterns selected no checkpoint files")
    if any(paths != values[0] for paths in values[1:]):
        details = "; ".join(
            f"{provider}={len(paths)} files"
            for provider, paths in sorted(provider_paths.items())
        )
        raise CheckpointPublishingError(
            f"Hub source file sets are not identical ({details})"
        )
    return tuple(sorted(values[0]))


def _verify_files_and_pieces(
    roots: dict[str, Path], paths: tuple[str, ...], piece_size: int
) -> tuple[list[dict[str, Any]], list[str]]:
    file_rows: list[dict[str, Any]] = []
    piece_hashes: list[str] = []
    piece = bytearray()
    providers = tuple(sorted(roots))
    canonical_provider = "huggingface"
    for relative in paths:
        files = {provider: roots[provider] / relative for provider in providers}
        sizes = {provider: path.stat().st_size for provider, path in files.items()}
        if (
            not all(path.is_file() for path in files.values())
            or len(set(sizes.values())) != 1
        ):
            raise CheckpointPublishingError(f"Hub source sizes differ: {relative}")
        size = next(iter(sizes.values()))
        if size <= 0:
            raise CheckpointPublishingError(
                f"checkpoint files must be non-empty: {relative}"
            )
        digests = {provider: hashlib.sha256() for provider in providers}
        streams = {provider: path.open("rb") for provider, path in files.items()}
        try:
            while True:
                chunks = {
                    provider: streams[provider].read(8 * 1024 * 1024)
                    for provider in providers
                }
                lengths = {len(chunk) for chunk in chunks.values()}
                if len(lengths) != 1:
                    raise CheckpointPublishingError(
                        f"Hub source bytes differ: {relative}"
                    )
                if not next(iter(lengths)):
                    break
                for provider, chunk in chunks.items():
                    digests[provider].update(chunk)
                canonical = chunks[canonical_provider]
                cursor = 0
                while cursor < len(canonical):
                    take = min(piece_size - len(piece), len(canonical) - cursor)
                    piece.extend(canonical[cursor : cursor + take])
                    cursor += take
                    if len(piece) == piece_size:
                        piece_hashes.append(
                            "sha256:" + hashlib.sha256(piece).hexdigest()
                        )
                        piece.clear()
        finally:
            for stream in streams.values():
                stream.close()
        values = {digest.hexdigest() for digest in digests.values()}
        if len(values) != 1:
            raise CheckpointPublishingError(f"Hub source hashes differ: {relative}")
        file_rows.append(
            {"path": relative, "size": size, "sha256": "sha256:" + values.pop()}
        )
    if piece:
        piece_hashes.append("sha256:" + hashlib.sha256(piece).hexdigest())
    return file_rows, piece_hashes


def _verify_local_files_against_metadata(
    root: Path,
    paths: tuple[str, ...],
    metadata: dict[str, CheckpointFileMetadata],
    piece_size: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    file_rows: list[dict[str, Any]] = []
    piece_hashes: list[str] = []
    piece = bytearray()
    for relative in paths:
        path = root / relative
        expected = metadata[relative]
        if not path.is_file() or path.stat().st_size != expected.size:
            raise CheckpointPublishingError(
                f"Hugging Face bytes differ from ModelScope metadata: {relative}"
            )
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(8 * 1024 * 1024):
                digest.update(chunk)
                cursor = 0
                while cursor < len(chunk):
                    take = min(piece_size - len(piece), len(chunk) - cursor)
                    piece.extend(chunk[cursor : cursor + take])
                    cursor += take
                    if len(piece) == piece_size:
                        piece_hashes.append(
                            "sha256:" + hashlib.sha256(piece).hexdigest()
                        )
                        piece.clear()
        actual = digest.hexdigest()
        if actual != expected.sha256:
            raise CheckpointPublishingError(
                f"Hugging Face SHA-256 differs from ModelScope metadata: {relative}"
            )
        file_rows.append(
            {"path": relative, "size": expected.size, "sha256": "sha256:" + actual}
        )
    if piece:
        piece_hashes.append("sha256:" + hashlib.sha256(piece).hexdigest())
    return file_rows, piece_hashes


def _sign_distribution(
    spec: dict[str, Any],
    repositories: tuple[dict[str, str], ...],
    files: list[dict[str, Any]],
    piece_hashes: list[str],
    piece_size: int,
    *,
    private_key: Ed25519PrivateKey,
    publisher_id: str,
    publisher_key_id: str,
    source_roots: dict[str, Path],
    verification_builder: str,
) -> BuiltCheckpointDistribution:
    sources = [
        {
            "type": source["type"],
            "repoId": source["repoId"],
            "revision": source["revision"],
            "path": file["path"],
            "access": source["access"],
            "verified": True,
        }
        for file in files
        for source in repositories
    ]
    manifest_raw = {
        "schemaVersion": 1,
        "distributionId": spec["distributionId"],
        "modelId": spec["modelId"],
        "repoId": spec["repoId"],
        "revision": spec["revision"],
        "format": spec["format"],
        "quantization": spec["quantization"],
        "estimatedSizeBytes": sum(file["size"] for file in files),
        "license": spec["license"],
        "files": files,
        "pieceSize": piece_size,
        "pieceHashes": piece_hashes,
        "distribution": {
            "p2p": {"allowed": False},
            "sources": sources,
            "managedSources": [],
        },
    }
    manifest = parse_checkpoint_distribution_manifest(manifest_raw)
    payload = {
        "domain": "ai2apps.checkpoint-distribution.v1",
        "publisherId": publisher_id,
        "publisherKeyId": publisher_key_id,
        "manifestDigest": manifest.digest,
        "manifest": manifest.raw,
    }
    signature = (
        base64.urlsafe_b64encode(private_key.sign(_DOMAIN + jcs_bytes(payload)))
        .decode("ascii")
        .rstrip("=")
    )
    envelope = {
        "schemaVersion": "ai2apps.checkpoint-distribution-envelope.v1",
        "payload": payload,
        "signature": {
            "keyId": publisher_key_id,
            "algorithm": "Ed25519",
            "value": signature,
        },
    }
    public_pem = (
        private_key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    verify_checkpoint_distribution_envelope(
        envelope,
        publisher_id=publisher_id,
        publisher_key_id=publisher_key_id,
        public_key_pem=public_pem,
        expected_fingerprint=public_key_fingerprint(public_pem),
    )
    return BuiltCheckpointDistribution(
        manifest=manifest,
        envelope=envelope,
        file_count=len(files),
        source_roots=source_roots,
        verification_builder=verification_builder,
    )


def build_checkpoint_distribution(
    spec: Any,
    *,
    source_roots: dict[str, str | Path],
    private_key: Ed25519PrivateKey,
    publisher_id: str,
    publisher_key_id: str,
) -> BuiltCheckpointDistribution:
    """Verify two immutable Hub trees and build their signed distribution."""

    if not isinstance(spec, dict) or set(spec) != _SPEC_KEYS:
        raise CheckpointPublishingError("checkpoint build specification is invalid")
    if spec.get("schema") != "ai2apps.checkpoint-build/v1":
        raise CheckpointPublishingError("unsupported checkpoint build specification")
    repositories = _source_repositories(spec)
    expected_providers = {source["type"] for source in repositories}
    if set(source_roots) != expected_providers:
        raise CheckpointPublishingError("source roots must exactly match Hub providers")
    roots = {
        provider: Path(source_roots[provider]).expanduser().resolve(strict=True)
        for provider in expected_providers
    }
    if not all(path.is_dir() for path in roots.values()):
        raise CheckpointPublishingError("source roots must be directories")
    patterns_raw = spec.get("includePatterns")
    if (
        not isinstance(patterns_raw, list)
        or not patterns_raw
        or not all(isinstance(item, str) and item for item in patterns_raw)
    ):
        raise CheckpointPublishingError("includePatterns must be non-empty strings")
    patterns = tuple(_safe_relative_path(item) for item in patterns_raw)
    piece_size = spec.get("pieceSize")
    if (
        not isinstance(piece_size, int)
        or isinstance(piece_size, bool)
        or piece_size < 1024 * 1024
        or piece_size > 64 * 1024 * 1024
        or piece_size & (piece_size - 1)
    ):
        raise CheckpointPublishingError(
            "pieceSize must be a power of two between 1 MiB and 64 MiB"
        )
    paths = _selected_paths(roots, patterns)
    files, piece_hashes = _verify_files_and_pieces(roots, paths, piece_size)
    sources = [
        {
            "type": source["type"],
            "repoId": source["repoId"],
            "revision": source["revision"],
            "path": file["path"],
            "access": source["access"],
            "verified": True,
        }
        for file in files
        for source in repositories
    ]
    manifest_raw = {
        "schemaVersion": 1,
        "distributionId": spec["distributionId"],
        "modelId": spec["modelId"],
        "repoId": spec["repoId"],
        "revision": spec["revision"],
        "format": spec["format"],
        "quantization": spec["quantization"],
        "estimatedSizeBytes": sum(file["size"] for file in files),
        "license": spec["license"],
        "files": files,
        "pieceSize": piece_size,
        "pieceHashes": piece_hashes,
        "distribution": {
            "p2p": {"allowed": False},
            "sources": sources,
            "managedSources": [],
        },
    }
    manifest = parse_checkpoint_distribution_manifest(manifest_raw)
    payload = {
        "domain": "ai2apps.checkpoint-distribution.v1",
        "publisherId": publisher_id,
        "publisherKeyId": publisher_key_id,
        "manifestDigest": manifest.digest,
        "manifest": manifest.raw,
    }
    # The envelope signs its complete JCS payload, not the nested manifest alone.
    signature = (
        base64.urlsafe_b64encode(private_key.sign(_DOMAIN + jcs_bytes(payload)))
        .decode("ascii")
        .rstrip("=")
    )
    envelope = {
        "schemaVersion": "ai2apps.checkpoint-distribution-envelope.v1",
        "payload": payload,
        "signature": {
            "keyId": publisher_key_id,
            "algorithm": "Ed25519",
            "value": signature,
        },
    }
    # Self-verify the exact artifact before returning it to the release script.
    public_pem = (
        private_key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    verify_checkpoint_distribution_envelope(
        envelope,
        publisher_id=publisher_id,
        publisher_key_id=publisher_key_id,
        public_key_pem=public_pem,
        expected_fingerprint=public_key_fingerprint(public_pem),
    )
    return BuiltCheckpointDistribution(
        manifest=manifest,
        envelope=envelope,
        file_count=len(files),
        source_roots=roots,
        verification_builder=FULL_DUAL_DOWNLOAD_BUILDER,
    )


def build_checkpoint_distribution_from_metadata(
    spec: Any,
    *,
    huggingface_root: str | Path,
    modelscope_files: tuple[CheckpointFileMetadata, ...],
    private_key: Ed25519PrivateKey,
    publisher_id: str,
    publisher_key_id: str,
) -> BuiltCheckpointDistribution:
    """Build from one pinned HF snapshot and ModelScope final-file SHA-256 metadata."""

    if not isinstance(spec, dict) or set(spec) != _SPEC_KEYS:
        raise CheckpointPublishingError("checkpoint build specification is invalid")
    if spec.get("schema") != "ai2apps.checkpoint-build/v1":
        raise CheckpointPublishingError("unsupported checkpoint build specification")
    repositories = _source_repositories(spec)
    sources_by_provider = {source["type"]: source for source in repositories}
    requested_root = Path(huggingface_root).expanduser()
    revision = sources_by_provider["huggingface"]["revision"]
    if requested_root.name != revision:
        raise CheckpointPublishingError(
            "metadata verification requires the exact Hugging Face revision snapshot directory"
        )
    root = requested_root.resolve(strict=True)
    if not root.is_dir():
        raise CheckpointPublishingError("Hugging Face root must be a directory")
    patterns_raw = spec.get("includePatterns")
    if (
        not isinstance(patterns_raw, list)
        or not patterns_raw
        or not all(isinstance(item, str) and item for item in patterns_raw)
    ):
        raise CheckpointPublishingError("includePatterns must be non-empty strings")
    patterns = tuple(_safe_relative_path(item) for item in patterns_raw)
    piece_size = spec.get("pieceSize")
    if (
        not isinstance(piece_size, int)
        or isinstance(piece_size, bool)
        or piece_size < 1024 * 1024
        or piece_size > 64 * 1024 * 1024
        or piece_size & (piece_size - 1)
    ):
        raise CheckpointPublishingError(
            "pieceSize must be a power of two between 1 MiB and 64 MiB"
        )
    paths = _selected_paths({"huggingface": root}, patterns)
    selected_metadata = [
        row
        for row in modelscope_files
        if row.path != ".gitattributes"
        and not row.path.startswith(".cache/")
        and any(fnmatch.fnmatchcase(row.path, pattern) for pattern in patterns)
    ]
    metadata = {row.path: row for row in selected_metadata}
    if len(metadata) != len(selected_metadata):
        raise CheckpointPublishingError("ModelScope metadata paths must be unique")
    if set(metadata) != set(paths):
        raise CheckpointPublishingError(
            "Hugging Face files and ModelScope metadata file sets are not identical"
        )
    files, piece_hashes = _verify_local_files_against_metadata(
        root, paths, metadata, piece_size
    )
    return _sign_distribution(
        spec,
        repositories,
        files,
        piece_hashes,
        piece_size,
        private_key=private_key,
        publisher_id=publisher_id,
        publisher_key_id=publisher_key_id,
        source_roots={"huggingface": root},
        verification_builder=METADATA_VERIFIED_BUILDER,
    )


def write_checkpoint_distribution(
    built: BuiltCheckpointDistribution, output: str | Path
) -> dict[str, Any]:
    destination = Path(output).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = destination.with_suffix(".manifest.json")
    receipt_path = destination.with_suffix(".verification.json")
    receipt = verification_receipt_for_envelope(
        built.envelope, builder=built.verification_builder
    )
    for path, value in (
        (manifest_path, built.manifest.raw),
        (receipt_path, receipt),
        (destination, built.envelope),
    ):
        partial = path.with_suffix(path.suffix + ".partial")
        partial.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        partial.replace(path)
    return {
        "distributionId": built.manifest.distribution_id,
        "manifestDigest": built.manifest.digest,
        "estimatedSizeBytes": built.manifest.estimated_size_bytes,
        "fileCount": built.file_count,
        "pieceCount": len(built.manifest.piece_hashes),
        "verificationMode": built.verification_builder,
        "verificationReceipt": str(receipt_path),
        "manifest": str(manifest_path),
        "envelope": str(destination),
    }
