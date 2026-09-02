"""Trusted Registry retrieval for checkpoint distribution manifests."""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ai2apps.checkpoint_distribution import (
    CheckpointDistributionManifest,
    CheckpointManifestError,
    verify_checkpoint_distribution_envelope,
)
from ai2apps.packages.contract_v1 import (
    PackageContractError,
    jcs_bytes,
    public_key_fingerprint,
)

_INDEX_PREFIX = b"AI2APPS-CHECKPOINT-INDEX-V1\n"
_SIGNATURE = re.compile(r"^[A-Za-z0-9_-]{86}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_MAX_INDEX_BYTES = 16 * 1024 * 1024
_MAX_ENVELOPE_BYTES = 16 * 1024 * 1024


class CheckpointRegistryError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise CheckpointRegistryError("index_invalid", f"{label} is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise CheckpointRegistryError("index_invalid", f"{label} is invalid") from error
    if parsed.tzinfo is None:
        raise CheckpointRegistryError("index_invalid", f"{label} requires timezone")
    return parsed.astimezone(UTC)


def _decode_signature(value: Any) -> bytes:
    if not isinstance(value, str) or not _SIGNATURE.fullmatch(value):
        raise CheckpointRegistryError("index_invalid", "Index signature is invalid")
    return base64.urlsafe_b64decode(value.encode("ascii") + b"==")


@dataclass(frozen=True)
class CheckpointRegistryRecord:
    distribution_id: str
    envelope_url: str
    manifest_digest: str
    publisher_id: str
    publisher_key_id: str
    publisher_fingerprint: str
    publisher_public_key_pem: str


@dataclass(frozen=True)
class TrustedCheckpointIndex:
    version: int
    generated_at: datetime
    expires_at: datetime
    records: tuple[CheckpointRegistryRecord, ...]

    def record(self, distribution_id: str) -> CheckpointRegistryRecord:
        matches = [
            item for item in self.records if item.distribution_id == distribution_id
        ]
        if not matches:
            raise CheckpointRegistryError(
                "distribution_not_found",
                "Checkpoint distribution is absent from the trusted index",
            )
        return matches[0]


def verify_checkpoint_index(
    envelope: Any,
    repository_public_key_pem: str,
    *,
    pinned_fingerprint: str,
    now: datetime | None = None,
) -> TrustedCheckpointIndex:
    try:
        repository_fingerprint = public_key_fingerprint(repository_public_key_pem)
    except (TypeError, ValueError, PackageContractError) as error:
        raise CheckpointRegistryError(
            "repository_key_invalid", "Checkpoint index key is invalid"
        ) from error
    if repository_fingerprint != pinned_fingerprint:
        raise CheckpointRegistryError(
            "repository_key_unpinned", "Checkpoint index key is not pinned"
        )
    if not isinstance(envelope, dict) or set(envelope) != {
        "schemaVersion",
        "payload",
        "signature",
    }:
        raise CheckpointRegistryError("index_invalid", "Checkpoint index is invalid")
    payload = envelope.get("payload")
    signature = envelope.get("signature")
    if (
        envelope.get("schemaVersion") != "ai2apps.checkpoint-index-envelope.v1"
        or not isinstance(payload, dict)
        or not isinstance(signature, dict)
        or set(signature) != {"keyId", "algorithm", "value"}
        or signature.get("keyId") != pinned_fingerprint
        or signature.get("algorithm") != "Ed25519"
    ):
        raise CheckpointRegistryError("index_invalid", "Checkpoint index is invalid")
    if (
        set(payload)
        != {
            "domain",
            "version",
            "generatedAt",
            "expiresAt",
            "distributions",
        }
        or payload.get("domain") != "ai2apps.checkpoint-index.v1"
    ):
        raise CheckpointRegistryError(
            "index_invalid", "Checkpoint index payload is invalid"
        )
    try:
        key = serialization.load_pem_public_key(
            repository_public_key_pem.encode("ascii")
        )
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("not Ed25519")
        key.verify(
            _decode_signature(signature.get("value")),
            _INDEX_PREFIX + jcs_bytes(payload),
        )
    except (TypeError, ValueError, UnicodeEncodeError, InvalidSignature) as error:
        raise CheckpointRegistryError(
            "index_signature_invalid", "Checkpoint index signature is invalid"
        ) from error
    version = payload.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise CheckpointRegistryError("index_invalid", "Index version is invalid")
    generated_at = _timestamp(payload.get("generatedAt"), "generatedAt")
    expires_at = _timestamp(payload.get("expiresAt"), "expiresAt")
    current = (now or datetime.now(UTC)).astimezone(UTC)
    if expires_at <= current:
        raise CheckpointRegistryError("index_expired", "Checkpoint index has expired")
    if generated_at > current and (generated_at - current).total_seconds() > 300:
        raise CheckpointRegistryError(
            "index_future", "Checkpoint index is dated in the future"
        )
    rows = payload.get("distributions")
    if not isinstance(rows, list):
        raise CheckpointRegistryError("index_invalid", "Distributions are invalid")
    records: list[CheckpointRegistryRecord] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "distributionId",
            "status",
            "envelopeUrl",
            "manifestDigest",
            "publisher",
        }:
            raise CheckpointRegistryError(
                "index_invalid", "Distribution record is invalid"
            )
        distribution_id = row.get("distributionId")
        if (
            not isinstance(distribution_id, str)
            or not distribution_id
            or distribution_id in seen
            or row.get("status") != "published"
            or not isinstance(row.get("envelopeUrl"), str)
            or not _DIGEST.fullmatch(str(row.get("manifestDigest")))
        ):
            raise CheckpointRegistryError(
                "index_invalid", "Distribution identity is invalid"
            )
        publisher = row.get("publisher")
        key_info = publisher.get("key") if isinstance(publisher, dict) else None
        if (
            not isinstance(publisher, dict)
            or set(publisher) != {"id", "key"}
            or not isinstance(publisher.get("id"), str)
            or not isinstance(key_info, dict)
            or set(key_info)
            != {
                "id",
                "fingerprintSha256",
                "publicKeyPem",
            }
            or not all(
                isinstance(key_info.get(name), str)
                for name in ("id", "fingerprintSha256", "publicKeyPem")
            )
        ):
            raise CheckpointRegistryError(
                "publisher_key_invalid", "Distribution publisher key is invalid"
            )
        try:
            publisher_fingerprint = public_key_fingerprint(key_info["publicKeyPem"])
        except (TypeError, ValueError, PackageContractError) as error:
            raise CheckpointRegistryError(
                "publisher_key_invalid", "Distribution publisher key is invalid"
            ) from error
        if publisher_fingerprint != key_info["fingerprintSha256"]:
            raise CheckpointRegistryError(
                "publisher_key_invalid", "Distribution publisher key is invalid"
            )
        seen.add(distribution_id)
        records.append(
            CheckpointRegistryRecord(
                distribution_id=distribution_id,
                envelope_url=row["envelopeUrl"],
                manifest_digest=row["manifestDigest"],
                publisher_id=publisher["id"],
                publisher_key_id=key_info["id"],
                publisher_fingerprint=key_info["fingerprintSha256"],
                publisher_public_key_pem=key_info["publicKeyPem"],
            )
        )
    return TrustedCheckpointIndex(
        version=version,
        generated_at=generated_at,
        expires_at=expires_at,
        records=tuple(records),
    )


class CheckpointRegistryClient:
    """Fetch distributions only through a current, pinned Registry index."""

    def __init__(
        self,
        *,
        cloud: Any,
        root: str | Path,
        repository_fingerprint: str,
    ) -> None:
        self.cloud = cloud
        self.root = Path(root) / "checkpoint-registry-v1"
        self.repository_fingerprint = repository_fingerprint.removeprefix("sha256:")
        self.state_path = self.root / "state.json"
        self.index_cache_path = self.root / "index-cache.json"

    async def distribution(
        self, distribution_id: str
    ) -> CheckpointDistributionManifest:
        index = await self.trusted_index()
        record = index.record(distribution_id)
        envelope_path = self._registry_path(
            record.envelope_url,
            f"/v1/checkpoint-distributions/{distribution_id}",
        )
        cache_path = self.root / "envelopes" / f"{record.manifest_digest[7:]}.json"
        envelope = self._read_json(cache_path, _MAX_ENVELOPE_BYTES)
        if envelope is not None:
            try:
                return self._verify_distribution(envelope, record)
            except CheckpointManifestError:
                cache_path.unlink(missing_ok=True)
        envelope = await self._json("GET", envelope_path, limit=_MAX_ENVELOPE_BYTES)
        manifest = self._verify_distribution(envelope, record)
        self._atomic_json(cache_path, envelope)
        return manifest

    async def trusted_index(self) -> TrustedCheckpointIndex:
        try:
            key_info = await self._json(
                "GET", "/v1/registry/repository-key", limit=1024 * 1024
            )
            public_key = (
                key_info.get("publicKeyPem") if isinstance(key_info, dict) else None
            )
            if not isinstance(public_key, str):
                raise CheckpointRegistryError(
                    "repository_key_invalid", "Registry key is invalid"
                )
            envelope = await self._json(
                "GET",
                "/v1/checkpoint-distributions/index/latest",
                limit=_MAX_INDEX_BYTES,
            )
        except (
            httpx.TransportError,
            httpx.TimeoutException,
            TimeoutError,
            OSError,
        ) as error:
            cached = self._read_json(self.index_cache_path, _MAX_INDEX_BYTES)
            if not isinstance(cached, dict):
                raise CheckpointRegistryError(
                    "index_unavailable", "Checkpoint index is unavailable"
                ) from error
            public_key = cached.get("publicKeyPem")
            envelope = cached.get("envelope")
            if not isinstance(public_key, str):
                raise CheckpointRegistryError(
                    "index_unavailable", "Cached checkpoint index is invalid"
                ) from error
        index = verify_checkpoint_index(
            envelope,
            public_key,
            pinned_fingerprint=self.repository_fingerprint,
        )
        previous = self._state_version()
        if index.version < previous:
            raise CheckpointRegistryError(
                "index_rollback", "Checkpoint index version moved backwards"
            )
        if index.version > previous:
            self._atomic_json(self.state_path, {"version": index.version})
        self._atomic_json(
            self.index_cache_path,
            {"publicKeyPem": public_key, "envelope": envelope},
        )
        return index

    def _verify_distribution(
        self, envelope: Any, record: CheckpointRegistryRecord
    ) -> CheckpointDistributionManifest:
        manifest = verify_checkpoint_distribution_envelope(
            envelope,
            publisher_id=record.publisher_id,
            publisher_key_id=record.publisher_key_id,
            public_key_pem=record.publisher_public_key_pem,
            expected_fingerprint=record.publisher_fingerprint,
        )
        if manifest.distribution_id != record.distribution_id:
            raise CheckpointManifestError(
                "checkpoint distribution ID does not match Registry metadata"
            )
        if manifest.digest != record.manifest_digest:
            raise CheckpointManifestError(
                "checkpoint manifest digest does not match Registry metadata"
            )
        return manifest

    async def _json(self, method: str, path: str, *, limit: int) -> Any:
        response = await self.cloud.request(method, path)
        try:
            if response.status_code >= 400:
                raise CheckpointRegistryError(
                    "registry_request_failed",
                    f"Checkpoint Registry request failed ({response.status_code})",
                )
            content = await response.aread()
            if len(content) > limit:
                raise CheckpointRegistryError(
                    "registry_response_too_large",
                    "Checkpoint Registry response exceeds its size limit",
                )
            return json.loads(content)
        except json.JSONDecodeError as error:
            raise CheckpointRegistryError(
                "registry_response_invalid", "Checkpoint Registry returned invalid JSON"
            ) from error
        finally:
            await response.aclose()

    def _registry_path(self, value: str, fallback: str) -> str:
        parsed = urlparse(value)
        cloud = urlparse(self.cloud.base_url)
        if parsed.query or parsed.fragment:
            raise CheckpointRegistryError(
                "distribution_url_invalid", "Distribution URL contains metadata"
            )
        if parsed.scheme and (parsed.scheme, parsed.netloc) != (
            cloud.scheme,
            cloud.netloc,
        ):
            raise CheckpointRegistryError(
                "distribution_url_invalid", "Distribution URL changes Cloud origin"
            )
        path = parsed.path if parsed.scheme else value
        if not path.startswith("/v1/checkpoint-distributions/"):
            raise CheckpointRegistryError(
                "distribution_url_invalid", "Distribution URL is outside Registry"
            )
        return path or fallback

    def _state_version(self) -> int:
        value = self._read_json(self.state_path, 1024 * 1024)
        version = value.get("version") if isinstance(value, dict) else 0
        return (
            version if isinstance(version, int) and not isinstance(version, bool) else 0
        )

    @staticmethod
    def _read_json(path: Path, limit: int) -> Any | None:
        try:
            if path.stat().st_size > limit:
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _atomic_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        payload = jcs_bytes(value) + b"\n"
        temporary.write_bytes(payload)
        os.replace(temporary, path)
