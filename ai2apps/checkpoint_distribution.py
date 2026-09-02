"""Trusted contracts and cache boundaries for checkpoint distribution."""

from __future__ import annotations

import asyncio
import base64
import ctypes
import errno
import hashlib
import itertools
import json
import os
import re
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol
from urllib.parse import quote, urlencode, urlsplit

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ai2apps.packages.contract_v1 import jcs_bytes, public_key_fingerprint

_DIGEST = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")
_HF_REVISION = re.compile(r"^[0-9a-f]{40}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$")
_MUTABLE_REVISIONS = frozenset({"main", "master", "latest", "head"})
_SOURCE_TYPES = frozenset({"huggingface", "modelscope"})
_ACCESS_POLICIES = frozenset(
    {"public_anonymous", "gated_user_token", "private_user_token"}
)
_REDISTRIBUTION_POLICIES = frozenset(
    {"allowed", "conditional", "prohibited", "unknown"}
)
_CONSENT_DECISIONS = frozenset(
    {"accepted_license_terms", "obtained_separate_license"}
)
_SIGNING_DOMAIN = b"AI2APPS-CHECKPOINT-DISTRIBUTION-V1\n"
_CONTENT_RANGE = re.compile(r"^bytes (\d+)-(\d+)/(\d+)$")
_ED25519_SIGNATURE = re.compile(r"^[A-Za-z0-9_-]{86}$")


class CheckpointManifestError(ValueError):
    """The Registry checkpoint distribution contract is invalid."""


class CheckpointDownloadError(RuntimeError):
    """A verified checkpoint cannot be completed from the enabled sources."""


class CheckpointConsentRequiredError(CheckpointDownloadError):
    """Checkpoint bytes are gated on an explicit, manifest-bound user decision."""

    def __init__(self, challenges: tuple[dict[str, Any], ...]):
        self.challenges = challenges
        super().__init__("checkpoint license consent is required before download")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _clone_or_copy_file(source: Path, destination: Path) -> None:
    """Prefer an APFS copy-on-write clone so imports do not duplicate huge weights."""

    if os.uname().sysname == "Darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        clonefile = libc.clonefile
        clonefile.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int)
        clonefile.restype = ctypes.c_int
        if clonefile(os.fsencode(source), os.fsencode(destination), 0) == 0:
            return
        error_number = ctypes.get_errno()
        if error_number not in {errno.ENOTSUP, errno.EXDEV, errno.EINVAL}:
            raise OSError(error_number, os.strerror(error_number), destination)
    shutil.copyfile(source, destination)


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CheckpointManifestError(f"{label} must be an object")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CheckpointManifestError(f"{label} must be a non-empty string")
    return value


def _identifier(value: Any, label: str) -> str:
    text = _string(value, label)
    if not _ID.fullmatch(text):
        raise CheckpointManifestError(f"{label} is invalid")
    return text


def _digest(value: Any, label: str) -> str:
    text = _string(value, label).lower()
    match = _DIGEST.fullmatch(text)
    if match is None:
        raise CheckpointManifestError(f"{label} must be a SHA-256 digest")
    return match.group(1)


def _https_url(value: Any, label: str) -> str:
    text = _string(value, label)
    parsed = urlsplit(text)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise CheckpointManifestError(f"{label} must be an HTTPS URL")
    return text


def _path(value: Any, label: str) -> str:
    text = _string(value, label)
    path = PurePosixPath(text)
    if (
        text.startswith("/")
        or "\\" in text
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise CheckpointManifestError(f"{label} must be a safe relative path")
    return text


def _immutable_revision(value: Any, provider: str, label: str) -> str:
    revision = _string(value, label)
    if revision.lower() in _MUTABLE_REVISIONS:
        raise CheckpointManifestError(f"{label} must be immutable")
    if provider == "huggingface" and not _HF_REVISION.fullmatch(revision):
        raise CheckpointManifestError(
            f"{label} must be a 40-character Hugging Face commit"
        )
    return revision


@dataclass(frozen=True)
class CheckpointFile:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class CheckpointSource:
    provider: str
    repo_id: str
    revision: str
    path: str
    access: str


@dataclass(frozen=True)
class CheckpointLicense:
    license_id: str
    name: str
    terms_url: str
    terms_hash: str
    usage_policy: str
    access_policy: str
    redistribution_policy: str
    terms_text: str | None = None
    redistribution_conditions: dict[str, Any] | None = None
    download_consent: dict[str, Any] | None = None


@dataclass(frozen=True)
class CheckpointDistributionManifest:
    raw: dict[str, Any]
    distribution_id: str
    model_id: str
    repo_id: str
    revision: str
    format: str
    quantization: str
    estimated_size_bytes: int
    license: CheckpointLicense
    files: tuple[CheckpointFile, ...]
    piece_size: int
    piece_hashes: tuple[str, ...]
    sources: tuple[CheckpointSource, ...]

    @property
    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_bytes()).hexdigest()

    def canonical_bytes(self) -> bytes:
        try:
            return jcs_bytes(self.raw)
        except (TypeError, ValueError) as error:
            raise CheckpointManifestError(
                "manifest cannot be canonically encoded"
            ) from error

    def signing_bytes(self) -> bytes:
        return _SIGNING_DOMAIN + self.canonical_bytes()


def parse_checkpoint_distribution_manifest(
    value: Any,
) -> CheckpointDistributionManifest:
    raw = _object(value, "manifest")
    if raw.get("schemaVersion") != 1:
        raise CheckpointManifestError("unsupported checkpoint manifest version")
    distribution_id = _identifier(raw.get("distributionId"), "distributionId")
    model_id = _identifier(raw.get("modelId"), "modelId")
    repo_id = _identifier(raw.get("repoId"), "repoId")
    if repo_id.count("/") != 1:
        raise CheckpointManifestError("repoId must use owner/model form")
    revision = _immutable_revision(raw.get("revision"), "huggingface", "revision")
    checkpoint_format = _identifier(raw.get("format"), "format")
    quantization = _identifier(raw.get("quantization"), "quantization")

    estimated_size = raw.get("estimatedSizeBytes")
    if (
        not isinstance(estimated_size, int)
        or isinstance(estimated_size, bool)
        or estimated_size <= 0
    ):
        raise CheckpointManifestError("estimatedSizeBytes must be a positive integer")

    license_raw = _object(raw.get("license"), "license")
    redistribution = _string(
        license_raw.get("redistributionPolicy"), "license.redistributionPolicy"
    )
    if redistribution not in _REDISTRIBUTION_POLICIES:
        raise CheckpointManifestError("unsupported redistribution policy")
    terms_text = license_raw.get("termsText")
    if terms_text is not None:
        terms_text = _string(terms_text, "license.termsText")
        if len(terms_text.encode("utf-8")) > 64 * 1024:
            raise CheckpointManifestError("license.termsText exceeds 64 KiB")
        if hashlib.sha256(terms_text.encode("utf-8")).hexdigest() != _digest(
            license_raw.get("termsHash"), "license.termsHash"
        ):
            raise CheckpointManifestError(
                "license.termsText does not match license.termsHash"
            )
    conditions = license_raw.get("redistributionConditions")
    consent = license_raw.get("downloadConsent")
    if redistribution == "conditional":
        conditions = _object(conditions, "license.redistributionConditions")
        if set(conditions) != {
            "termsAcceptance",
            "licenseDelivery",
            "downstreamTerms",
            "commercialUse",
            "attribution",
            "modifiedFilesNotice",
        }:
            raise CheckpointManifestError(
                "license.redistributionConditions fields are invalid"
            )
        if conditions.get("termsAcceptance") != "required":
            raise CheckpointManifestError(
                "conditional redistribution requires terms acceptance"
            )
        if conditions.get("licenseDelivery") != "required":
            raise CheckpointManifestError(
                "conditional redistribution requires license delivery"
            )
        if conditions.get("downstreamTerms") not in {
            "same_or_more_restrictive",
            "license_terms",
        }:
            raise CheckpointManifestError("downstreamTerms is invalid")
        if conditions.get("commercialUse") not in {
            "allowed",
            "prohibited",
            "separate_license_required",
        }:
            raise CheckpointManifestError("commercialUse is invalid")
        if conditions.get("modifiedFilesNotice") not in {
            "required",
            "not_required",
        }:
            raise CheckpointManifestError("modifiedFilesNotice is invalid")
        attribution = _object(
            conditions.get("attribution"),
            "license.redistributionConditions.attribution",
        )
        if set(attribution) != {
            "required",
            "noticeText",
            "noticeFile",
            "productDisplay",
        }:
            raise CheckpointManifestError("license attribution fields are invalid")
        if not isinstance(attribution.get("required"), bool):
            raise CheckpointManifestError("license attribution.required is invalid")
        if attribution["required"]:
            _string(attribution.get("noticeText"), "license attribution.noticeText")
            _path(attribution.get("noticeFile"), "license attribution.noticeFile")
        if attribution.get("productDisplay") not in {
            "required",
            "not_required",
        }:
            raise CheckpointManifestError("license attribution.productDisplay is invalid")
        consent = _object(consent, "license.downloadConsent")
        if set(consent) != {
            "required",
            "attestationText",
            "acceptanceOptions",
        }:
            raise CheckpointManifestError("license.downloadConsent fields are invalid")
        if consent.get("required") is not True:
            raise CheckpointManifestError(
                "conditional redistribution requires download consent"
            )
        _string(consent.get("attestationText"), "license.downloadConsent.attestationText")
        options = consent.get("acceptanceOptions")
        if (
            not isinstance(options, list)
            or not options
            or not all(isinstance(option, str) for option in options)
            or len(set(options)) != len(options)
            or not set(options).issubset(_CONSENT_DECISIONS)
        ):
            raise CheckpointManifestError(
                "license.downloadConsent.acceptanceOptions is invalid"
            )
    elif conditions is not None or consent is not None:
        raise CheckpointManifestError(
            "license consent fields require conditional redistribution"
        )
    license_info = CheckpointLicense(
        license_id=_identifier(license_raw.get("id"), "license.id"),
        name=_string(license_raw.get("name"), "license.name"),
        terms_url=_https_url(license_raw.get("termsUrl"), "license.termsUrl"),
        terms_hash=_digest(license_raw.get("termsHash"), "license.termsHash"),
        usage_policy=_identifier(license_raw.get("usagePolicy"), "license.usagePolicy"),
        access_policy=_identifier(
            license_raw.get("accessPolicy"), "license.accessPolicy"
        ),
        redistribution_policy=redistribution,
        terms_text=terms_text,
        redistribution_conditions=(
            json.loads(json.dumps(conditions)) if conditions is not None else None
        ),
        download_consent=(
            json.loads(json.dumps(consent)) if consent is not None else None
        ),
    )

    files_raw = raw.get("files")
    if not isinstance(files_raw, list) or not files_raw:
        raise CheckpointManifestError("files must be a non-empty array")
    files: list[CheckpointFile] = []
    seen_paths: set[str] = set()
    for index, item in enumerate(files_raw):
        entry = _object(item, f"files[{index}]")
        path = _path(entry.get("path"), f"files[{index}].path")
        size = entry.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise CheckpointManifestError(f"files[{index}].size is invalid")
        if path in seen_paths:
            raise CheckpointManifestError("checkpoint file paths must be unique")
        seen_paths.add(path)
        files.append(
            CheckpointFile(
                path=path,
                size=size,
                sha256=_digest(entry.get("sha256"), f"files[{index}].sha256"),
            )
        )
    total_size = sum(item.size for item in files)
    if estimated_size != total_size:
        raise CheckpointManifestError(
            "estimatedSizeBytes must equal the verified file size total"
        )

    piece_size = raw.get("pieceSize")
    if (
        not isinstance(piece_size, int)
        or isinstance(piece_size, bool)
        or piece_size < 1024 * 1024
        or piece_size > 64 * 1024 * 1024
        or piece_size & (piece_size - 1)
    ):
        raise CheckpointManifestError(
            "pieceSize must be a power of two between 1 MiB and 64 MiB"
        )
    hashes_raw = raw.get("pieceHashes")
    expected_pieces = (total_size + piece_size - 1) // piece_size
    if not isinstance(hashes_raw, list) or len(hashes_raw) != expected_pieces:
        raise CheckpointManifestError("pieceHashes count does not match file bytes")
    piece_hashes = tuple(
        _digest(item, f"pieceHashes[{index}]") for index, item in enumerate(hashes_raw)
    )

    distribution = _object(raw.get("distribution"), "distribution")
    p2p = _object(distribution.get("p2p"), "distribution.p2p")
    p2p_allowed = p2p.get("allowed")
    if not isinstance(p2p_allowed, bool):
        raise CheckpointManifestError("distribution.p2p.allowed must be boolean")
    if p2p_allowed and redistribution != "allowed":
        raise CheckpointManifestError(
            "P2P cannot be enabled when redistribution is not allowed"
        )
    if p2p_allowed and not isinstance(p2p.get("magnet"), str):
        raise CheckpointManifestError("P2P-enabled manifests require a magnet URI")

    sources_raw = distribution.get("sources")
    if not isinstance(sources_raw, list) or not sources_raw:
        raise CheckpointManifestError("distribution.sources must be non-empty")
    sources: list[CheckpointSource] = []
    covered: set[str] = set()
    identities: set[tuple[str, str, str, str]] = set()
    for index, item in enumerate(sources_raw):
        source = _object(item, f"distribution.sources[{index}]")
        provider = _string(source.get("type"), f"distribution.sources[{index}].type")
        if provider not in _SOURCE_TYPES:
            raise CheckpointManifestError("unsupported checkpoint source type")
        source_repo = _identifier(
            source.get("repoId"), f"distribution.sources[{index}].repoId"
        )
        if source_repo.count("/") != 1:
            raise CheckpointManifestError("source repoId must use owner/model form")
        source_path = _path(source.get("path"), f"distribution.sources[{index}].path")
        if source_path not in seen_paths:
            raise CheckpointManifestError("source path is absent from files")
        access = _string(source.get("access"), f"distribution.sources[{index}].access")
        if access not in _ACCESS_POLICIES:
            raise CheckpointManifestError("unsupported source access policy")
        if source.get("verified") is not True:
            raise CheckpointManifestError("all published sources must be verified")
        source_revision = _immutable_revision(
            source.get("revision"),
            provider,
            f"distribution.sources[{index}].revision",
        )
        identity = (provider, source_repo, source_revision, source_path)
        if identity in identities:
            raise CheckpointManifestError("checkpoint sources must be unique")
        identities.add(identity)
        covered.add(source_path)
        sources.append(
            CheckpointSource(
                provider=provider,
                repo_id=source_repo,
                revision=source_revision,
                path=source_path,
                access=access,
            )
        )
    if covered != seen_paths:
        raise CheckpointManifestError("every checkpoint file requires a source")

    managed = distribution.get("managedSources", [])
    if not isinstance(managed, list) or managed:
        raise CheckpointManifestError("managedSources are reserved for a later version")

    try:
        immutable_raw = json.loads(json.dumps(raw))
    except (TypeError, ValueError) as error:
        raise CheckpointManifestError(
            "manifest must contain JSON values only"
        ) from error

    return CheckpointDistributionManifest(
        raw=immutable_raw,
        distribution_id=distribution_id,
        model_id=model_id,
        repo_id=repo_id,
        revision=revision,
        format=checkpoint_format,
        quantization=quantization,
        estimated_size_bytes=estimated_size,
        license=license_info,
        files=tuple(files),
        piece_size=piece_size,
        piece_hashes=piece_hashes,
        sources=tuple(sources),
    )


def checkpoint_license_consent_challenge(
    manifest: CheckpointDistributionManifest,
) -> dict[str, Any] | None:
    """Return signed license facts safe for a first-party confirmation surface."""

    consent = manifest.license.download_consent
    if manifest.license.redistribution_policy != "conditional" or consent is None:
        return None
    return {
        "distributionId": manifest.distribution_id,
        "manifestDigest": manifest.digest,
        "modelId": manifest.model_id,
        "estimatedSizeBytes": manifest.estimated_size_bytes,
        "license": {
            "id": manifest.license.license_id,
            "name": manifest.license.name,
            "termsUrl": manifest.license.terms_url,
            "termsHash": "sha256:" + manifest.license.terms_hash,
            **(
                {"termsText": manifest.license.terms_text}
                if manifest.license.terms_text is not None
                else {}
            ),
            "usagePolicy": manifest.license.usage_policy,
            "redistributionConditions": manifest.license.redistribution_conditions,
        },
        "attestationText": consent["attestationText"],
        "acceptanceOptions": list(consent["acceptanceOptions"]),
    }


def require_checkpoint_license_consent(
    manifest: CheckpointDistributionManifest,
    consent: Any,
) -> None:
    """Fail closed unless consent matches this exact signed manifest and terms."""

    challenge = checkpoint_license_consent_challenge(manifest)
    if challenge is None:
        return
    if not isinstance(consent, dict) or set(consent) != {
        "distributionId",
        "manifestDigest",
        "termsHash",
        "decision",
        "confirmed",
    }:
        raise CheckpointConsentRequiredError((challenge,))
    if (
        consent.get("distributionId") != manifest.distribution_id
        or consent.get("manifestDigest") != manifest.digest
        or consent.get("termsHash") != "sha256:" + manifest.license.terms_hash
        or consent.get("confirmed") is not True
        or consent.get("decision")
        not in set(manifest.license.download_consent["acceptanceOptions"])
    ):
        raise CheckpointConsentRequiredError((challenge,))


def verify_checkpoint_manifest_signature(
    manifest: CheckpointDistributionManifest,
    signature: bytes,
    public_key_pem: str | bytes,
) -> None:
    try:
        key = serialization.load_pem_public_key(
            public_key_pem.encode("utf-8")
            if isinstance(public_key_pem, str)
            else public_key_pem
        )
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("not Ed25519")
        key.verify(signature, manifest.signing_bytes())
    except (TypeError, ValueError, InvalidSignature) as error:
        raise CheckpointManifestError(
            "checkpoint manifest signature is invalid"
        ) from error


def _b64url_decode(value: Any, label: str) -> bytes:
    if not isinstance(value, str) or not _ED25519_SIGNATURE.fullmatch(value):
        raise CheckpointManifestError(f"{label} must be base64url")
    try:
        return base64.urlsafe_b64decode(
            value.encode("ascii") + b"=" * (-len(value) % 4)
        )
    except (UnicodeEncodeError, ValueError) as error:
        raise CheckpointManifestError(f"{label} must be base64url") from error


def verify_checkpoint_distribution_envelope(
    envelope: Any,
    *,
    publisher_id: str,
    publisher_key_id: str,
    public_key_pem: str,
    expected_fingerprint: str | None = None,
) -> CheckpointDistributionManifest:
    """Bind a signed manifest to Registry-authenticated publisher metadata."""

    value = _object(envelope, "checkpoint envelope")
    if set(value) != {"schemaVersion", "payload", "signature"}:
        raise CheckpointManifestError("checkpoint envelope fields are invalid")
    if value.get("schemaVersion") != "ai2apps.checkpoint-distribution-envelope.v1":
        raise CheckpointManifestError("checkpoint envelope version is invalid")
    payload = _object(value.get("payload"), "checkpoint envelope payload")
    if set(payload) != {
        "domain",
        "publisherId",
        "publisherKeyId",
        "manifestDigest",
        "manifest",
    }:
        raise CheckpointManifestError("checkpoint envelope payload fields are invalid")
    if payload.get("domain") != "ai2apps.checkpoint-distribution.v1":
        raise CheckpointManifestError("checkpoint envelope domain is invalid")
    if (
        payload.get("publisherId") != publisher_id
        or payload.get("publisherKeyId") != publisher_key_id
    ):
        raise CheckpointManifestError(
            "checkpoint publisher identity does not match Registry metadata"
        )
    try:
        fingerprint = public_key_fingerprint(public_key_pem)
    except (TypeError, ValueError) as error:
        raise CheckpointManifestError(
            "checkpoint publisher public key is invalid"
        ) from error
    if expected_fingerprint is not None and fingerprint != expected_fingerprint:
        raise CheckpointManifestError(
            "checkpoint publisher key fingerprint does not match Registry metadata"
        )
    signature = _object(value.get("signature"), "checkpoint envelope signature")
    if set(signature) != {"keyId", "algorithm", "value"}:
        raise CheckpointManifestError("checkpoint signature fields are invalid")
    if (
        signature.get("keyId") != publisher_key_id
        or signature.get("algorithm") != "Ed25519"
    ):
        raise CheckpointManifestError("checkpoint signature key is invalid")
    manifest = parse_checkpoint_distribution_manifest(payload.get("manifest"))
    if payload.get("manifestDigest") != manifest.digest:
        raise CheckpointManifestError("checkpoint manifest digest is invalid")
    try:
        key = serialization.load_pem_public_key(public_key_pem.encode("ascii"))
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("not Ed25519")
        key.verify(
            _b64url_decode(signature.get("value"), "checkpoint signature"),
            _SIGNING_DOMAIN + jcs_bytes(payload),
        )
    except (TypeError, ValueError, UnicodeEncodeError, InvalidSignature) as error:
        raise CheckpointManifestError(
            "checkpoint publisher signature is invalid"
        ) from error
    return manifest


@dataclass(frozen=True)
class SourceCapability:
    available: bool
    range_supported: bool
    content_length: int | None = None
    latency_ms: float | None = None
    error_code: str | None = None


class PieceSource(Protocol):
    provider: str
    file_path: str

    async def probe(self) -> SourceCapability: ...

    async def fetch_piece(self, file_path: str, offset: int, length: int) -> bytes: ...


class HTTPRangePieceSource:
    """One signed source descriptor resolved to a current HTTPS object URL."""

    def __init__(
        self,
        source: CheckpointSource,
        endpoint_url: str,
        client: httpx.AsyncClient,
        *,
        headers: dict[str, str] | None = None,
        max_piece_size: int = 64 * 1024 * 1024,
    ) -> None:
        parsed = urlsplit(endpoint_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise CheckpointManifestError(
                "checkpoint source endpoint must be an HTTPS URL without credentials"
            )
        if max_piece_size <= 0 or max_piece_size > 64 * 1024 * 1024:
            raise ValueError("max_piece_size is invalid")
        self.provider = source.provider
        self.file_path = source.path
        self.source = source
        self.endpoint_url = endpoint_url
        self.client = client
        self.headers = dict(headers or {})
        self.max_piece_size = max_piece_size

    async def probe(self) -> SourceCapability:
        started = time.monotonic()
        try:
            response = await self.client.get(
                self.endpoint_url,
                headers={**self.headers, "Range": "bytes=0-0"},
                follow_redirects=True,
            )
        except httpx.TimeoutException:
            return SourceCapability(
                available=False,
                range_supported=False,
                error_code="timeout",
            )
        except httpx.TransportError:
            return SourceCapability(
                available=False,
                range_supported=False,
                error_code="unreachable",
            )
        if response.status_code == 206:
            parsed = self._content_range(response)
            if parsed is None or parsed[:2] != (0, 0) or len(response.content) != 1:
                return SourceCapability(
                    available=False,
                    range_supported=False,
                    error_code="invalid_range_response",
                )
            return SourceCapability(
                available=True,
                range_supported=True,
                content_length=parsed[2],
                latency_ms=(time.monotonic() - started) * 1000,
            )
        if response.status_code == 200:
            length = response.headers.get("Content-Length")
            return SourceCapability(
                available=True,
                range_supported=False,
                content_length=int(length) if length and length.isdigit() else None,
                latency_ms=(time.monotonic() - started) * 1000,
                error_code="range_unsupported",
            )
        return SourceCapability(
            available=False,
            range_supported=False,
            error_code=f"http_{response.status_code}",
        )

    async def fetch_piece(self, file_path: str, offset: int, length: int) -> bytes:
        if file_path != self.source.path:
            raise CheckpointManifestError("piece source is bound to another file")
        if offset < 0 or length <= 0 or length > self.max_piece_size:
            raise ValueError("piece range is invalid")
        end = offset + length - 1
        response = await self.client.get(
            self.endpoint_url,
            headers={**self.headers, "Range": f"bytes={offset}-{end}"},
            follow_redirects=True,
        )
        if response.status_code != 206:
            raise CheckpointManifestError(
                f"{self.provider} source did not honor the requested range"
            )
        parsed = self._content_range(response)
        if parsed is None or parsed[:2] != (offset, end):
            raise CheckpointManifestError(
                f"{self.provider} source returned a mismatched content range"
            )
        if len(response.content) != length:
            raise CheckpointManifestError(
                f"{self.provider} source returned a short piece"
            )
        return response.content

    @staticmethod
    def _content_range(response: httpx.Response) -> tuple[int, int, int] | None:
        match = _CONTENT_RANGE.fullmatch(response.headers.get("Content-Range", ""))
        if match is None:
            return None
        start, end, total = (int(value) for value in match.groups())
        if start > end or end >= total:
            return None
        return start, end, total


class HubSourceResolver:
    """Resolve trusted Hub descriptors without persisting temporary URLs."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        huggingface_endpoint: str = "https://huggingface.co",
        modelscope_endpoint: str = "https://modelscope.cn",
    ) -> None:
        self.client = client
        self.huggingface_endpoint = self._base_endpoint(
            huggingface_endpoint, "Hugging Face"
        )
        self.modelscope_endpoint = self._base_endpoint(
            modelscope_endpoint, "ModelScope"
        )

    @staticmethod
    def _base_endpoint(value: str, label: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise CheckpointManifestError(f"{label} endpoint is invalid")
        return value.rstrip("/")

    def resolve(
        self,
        source: CheckpointSource,
        *,
        user_token: str | None = None,
    ) -> HTTPRangePieceSource:
        if user_token is not None and (
            not user_token or "\r" in user_token or "\n" in user_token
        ):
            raise CheckpointManifestError("checkpoint source token is invalid")
        requires_token = source.access in {
            "gated_user_token",
            "private_user_token",
        }
        if requires_token and user_token is None:
            raise CheckpointDownloadError(
                f"{source.provider} source requires a user credential"
            )
        headers: dict[str, str] = {}
        if source.provider == "huggingface":
            from huggingface_hub import hf_hub_url

            endpoint_url = hf_hub_url(
                repo_id=source.repo_id,
                filename=source.path,
                revision=source.revision,
                endpoint=self.huggingface_endpoint,
            )
            if user_token is not None:
                headers["Authorization"] = f"Bearer {user_token}"
        elif source.provider == "modelscope":
            if requires_token:
                raise CheckpointDownloadError(
                    "authenticated ModelScope Range sources are not enabled in Phase 1"
                )
            # Public ModelScope repository files use a stable HTTP endpoint.
            # Build it directly so checkpoint acquisition does not depend on
            # the optional, heavyweight ModelScope Python SDK being installed
            # in the AI2Apps control-plane environment.
            endpoint_url = (
                f"{self.modelscope_endpoint}/api/v1/models/"
                f"{quote(source.repo_id, safe='/')}/repo?"
                + urlencode(
                    {"Revision": source.revision, "FilePath": source.path}
                )
            )
        else:
            raise CheckpointManifestError("unsupported checkpoint source provider")
        return HTTPRangePieceSource(
            source,
            endpoint_url,
            self.client,
            headers=headers,
        )


@dataclass(frozen=True)
class PieceSegment:
    file_path: str
    file_offset: int
    length: int


@dataclass(frozen=True)
class CheckpointPiece:
    index: int
    stream_offset: int
    length: int
    sha256: str
    segments: tuple[PieceSegment, ...]


def plan_checkpoint_pieces(
    manifest: CheckpointDistributionManifest,
) -> tuple[CheckpointPiece, ...]:
    """Map global manifest pieces onto one or more file-local ranges."""

    plans: list[CheckpointPiece] = []
    file_index = 0
    file_stream_start = 0
    total_size = manifest.estimated_size_bytes
    for piece_index, digest in enumerate(manifest.piece_hashes):
        stream_offset = piece_index * manifest.piece_size
        piece_end = min(stream_offset + manifest.piece_size, total_size)
        cursor = stream_offset
        while (
            file_index < len(manifest.files)
            and cursor >= file_stream_start + manifest.files[file_index].size
        ):
            file_stream_start += manifest.files[file_index].size
            file_index += 1
        current_index = file_index
        current_start = file_stream_start
        segments: list[PieceSegment] = []
        while cursor < piece_end and current_index < len(manifest.files):
            checkpoint_file = manifest.files[current_index]
            file_offset = cursor - current_start
            length = min(piece_end - cursor, checkpoint_file.size - file_offset)
            if length <= 0:
                raise CheckpointManifestError("piece plan does not cover file bytes")
            segments.append(
                PieceSegment(
                    file_path=checkpoint_file.path,
                    file_offset=file_offset,
                    length=length,
                )
            )
            cursor += length
            if file_offset + length == checkpoint_file.size:
                current_start += checkpoint_file.size
                current_index += 1
        if cursor != piece_end or not segments:
            raise CheckpointManifestError("piece plan does not cover manifest bytes")
        plans.append(
            CheckpointPiece(
                index=piece_index,
                stream_offset=stream_offset,
                length=piece_end - stream_offset,
                sha256=digest,
                segments=tuple(segments),
            )
        )
    return tuple(plans)


class CheckpointCache:
    """Source-agnostic cache paths with verified-only atomic promotion."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        for name in ("blobs", "snapshots", "partial", "manifests"):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    def blob_path(self, sha256: str) -> Path:
        digest = _digest(sha256, "blob digest")
        return self.root / "blobs" / digest[:2] / digest

    def partial_path(self, distribution_id: str, file_path: str) -> Path:
        identity = f"{_identifier(distribution_id, 'distributionId')}\0{_path(file_path, 'file path')}"
        key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return self.root / "partial" / key[:2] / f"{key}.partial"

    def manifest_path(self, manifest: CheckpointDistributionManifest) -> Path:
        key = hashlib.sha256(manifest.distribution_id.encode("utf-8")).hexdigest()
        return self.root / "manifests" / f"{key}.json"

    def piece_map_path(self, manifest: CheckpointDistributionManifest) -> Path:
        key = hashlib.sha256(
            f"{manifest.distribution_id}\0{manifest.digest}".encode()
        ).hexdigest()
        return self.root / "partial" / f"{key}.pieces.json"

    def snapshot_path(self, manifest: CheckpointDistributionManifest) -> Path:
        identity = f"{manifest.repo_id}\0{manifest.revision}\0{manifest.digest}"
        key = hashlib.sha256(identity.encode()).hexdigest()
        return self.root / "snapshots" / key[:2] / key

    def verified_snapshot(
        self, manifest: CheckpointDistributionManifest
    ) -> Path | None:
        snapshot = self.snapshot_path(manifest)
        return (
            snapshot
            if snapshot.is_dir() and self._snapshot_matches(manifest, snapshot)
            else None
        )

    def promote_verified_file(
        self, partial: str | Path, *, sha256: str, size: int
    ) -> Path:
        source = Path(partial)
        if not source.is_file() or source.stat().st_size != size:
            raise CheckpointManifestError("partial file size does not match manifest")
        expected = _digest(sha256, "file digest")
        actual = _sha256_file(source)
        if actual != expected:
            raise CheckpointManifestError("partial file digest does not match manifest")
        destination = self.blob_path(expected)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if (
                destination.stat().st_size != size
                or _sha256_file(destination) != expected
            ):
                raise CheckpointManifestError("verified cache blob is corrupt")
            source.unlink()
            return destination
        os.replace(source, destination)
        return destination

    def write_manifest(self, manifest: CheckpointDistributionManifest) -> Path:
        destination = self.manifest_path(manifest)
        partial = destination.with_suffix(".json.partial")
        partial.write_bytes(manifest.canonical_bytes() + b"\n")
        os.replace(partial, destination)
        return destination

    def materialize_snapshot(
        self,
        manifest: CheckpointDistributionManifest,
        blobs: dict[str, Path],
    ) -> Path:
        """Atomically publish a read-only file view backed by verified blobs."""

        expected_paths = {item.path for item in manifest.files}
        if set(blobs) != expected_paths:
            raise CheckpointManifestError(
                "snapshot blobs do not exactly match manifest files"
            )
        destination = self.snapshot_path(manifest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if self._snapshot_matches(manifest, destination):
                return destination
            raise CheckpointManifestError("existing checkpoint snapshot is corrupt")
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{destination.name}.",
                dir=destination.parent,
            )
        )
        try:
            for checkpoint_file in manifest.files:
                blob = Path(blobs[checkpoint_file.path])
                expected_blob = self.blob_path(checkpoint_file.sha256)
                if (
                    blob != expected_blob
                    or blob.is_symlink()
                    or not blob.is_file()
                    or blob.stat().st_size != checkpoint_file.size
                    or _sha256_file(blob) != checkpoint_file.sha256
                ):
                    raise CheckpointManifestError(
                        f"snapshot blob is not verified: {checkpoint_file.path}"
                    )
                target = staging / checkpoint_file.path
                target.parent.mkdir(parents=True, exist_ok=True)
                os.link(blob, target)
            metadata = staging / ".ai2apps" / "distribution.json"
            metadata.parent.mkdir(parents=True, exist_ok=True)
            metadata.write_text(
                json.dumps(
                    {
                        "format": "ai2apps-checkpoint-distribution",
                        "version": 1,
                        "distributionId": manifest.distribution_id,
                        "manifestDigest": manifest.digest,
                        "repoId": manifest.repo_id,
                        "revision": manifest.revision,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            for path in sorted(staging.rglob("*"), reverse=True):
                path.chmod(0o555 if path.is_dir() else 0o444)
            staging.chmod(0o555)
            os.replace(staging, destination)
        except Exception:
            if staging.exists():
                for path in staging.rglob("*"):
                    if path.is_dir():
                        path.chmod(0o755)
                    else:
                        path.chmod(0o644)
                staging.chmod(0o755)
                shutil.rmtree(staging, ignore_errors=True)
            raise
        return destination

    def import_local_snapshot(
        self,
        manifest: CheckpointDistributionManifest,
        source: str | Path,
    ) -> Path:
        """Verify and adopt an existing pinned Hub snapshot without network I/O."""

        snapshot = Path(source).expanduser().resolve(strict=True)
        if not snapshot.is_dir():
            raise CheckpointManifestError("local checkpoint snapshot is not a directory")
        blobs: dict[str, Path] = {}
        for checkpoint_file in manifest.files:
            candidate = snapshot / checkpoint_file.path
            try:
                resolved = candidate.resolve(strict=True)
            except OSError as error:
                raise CheckpointManifestError(
                    f"local checkpoint file is missing: {checkpoint_file.path}"
                ) from error
            if not resolved.is_file() or resolved.stat().st_size != checkpoint_file.size:
                raise CheckpointManifestError(
                    f"local checkpoint file size differs: {checkpoint_file.path}"
                )
            destination = self.blob_path(checkpoint_file.sha256)
            destination.parent.mkdir(parents=True, exist_ok=True)
            handle, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", dir=destination.parent
            )
            os.close(handle)
            temporary = Path(temporary_name)
            temporary.unlink()
            try:
                _clone_or_copy_file(resolved, temporary)
                blobs[checkpoint_file.path] = self.promote_verified_file(
                    temporary,
                    sha256=checkpoint_file.sha256,
                    size=checkpoint_file.size,
                )
            finally:
                temporary.unlink(missing_ok=True)
        self.write_manifest(manifest)
        return self.materialize_snapshot(manifest, blobs)

    def materialize_snapshot_view(
        self,
        manifest: CheckpointDistributionManifest,
        verified_snapshot: str | Path,
        destination: str | Path,
    ) -> Path:
        """Atomically hard-link a verified snapshot into another trusted tree."""

        source = Path(verified_snapshot).resolve(strict=True)
        if not self._snapshot_matches(manifest, source):
            raise CheckpointManifestError("source checkpoint snapshot is not verified")
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.is_dir() and self._snapshot_matches(manifest, target):
                return target.resolve()
            raise CheckpointManifestError(
                "existing Worker checkpoint distribution conflicts with Registry"
            )
        staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
        try:
            for path in sorted(source.rglob("*")):
                relative = path.relative_to(source)
                copied = staging / relative
                if path.is_dir():
                    copied.mkdir(parents=True, exist_ok=True)
                    continue
                if path.is_symlink() or not path.is_file():
                    raise CheckpointManifestError(
                        "verified checkpoint snapshot contains an unsafe entry"
                    )
                copied.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(path, copied)
                except OSError as error:
                    if error.errno != errno.EXDEV:
                        raise
                    shutil.copyfile(path, copied)
            if not self._snapshot_matches(manifest, staging):
                raise CheckpointManifestError(
                    "Worker checkpoint snapshot does not match Registry"
                )
            for path in sorted(staging.rglob("*"), reverse=True):
                path.chmod(0o555 if path.is_dir() else 0o444)
            staging.chmod(0o555)
            os.replace(staging, target)
        except Exception:
            if staging.exists():
                for path in staging.rglob("*"):
                    if path.is_dir():
                        path.chmod(0o755)
                    else:
                        path.chmod(0o644)
                staging.chmod(0o755)
                shutil.rmtree(staging, ignore_errors=True)
            raise
        return target.resolve()

    @staticmethod
    def _snapshot_matches(
        manifest: CheckpointDistributionManifest, snapshot: Path
    ) -> bool:
        try:
            metadata = json.loads(
                (snapshot / ".ai2apps" / "distribution.json").read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, json.JSONDecodeError):
            return False
        if metadata.get("manifestDigest") != manifest.digest:
            return False
        expected_files = {
            *(item.path for item in manifest.files),
            ".ai2apps/distribution.json",
        }
        actual_files = {
            path.relative_to(snapshot).as_posix()
            for path in snapshot.rglob("*")
            if path.is_file() or path.is_symlink()
        }
        if actual_files != expected_files:
            return False
        for checkpoint_file in manifest.files:
            target = snapshot / checkpoint_file.path
            if (
                target.is_symlink()
                or not target.is_file()
                or target.stat().st_size != checkpoint_file.size
                or _sha256_file(target) != checkpoint_file.sha256
            ):
                return False
        return True


class PieceCompletionMap:
    """Crash-safe record of pieces written and synced to partial files."""

    def __init__(
        self, cache: CheckpointCache, manifest: CheckpointDistributionManifest
    ):
        self.path = cache.piece_map_path(manifest)
        self.manifest_digest = manifest.digest
        self.piece_count = len(manifest.piece_hashes)
        self.completed: set[int] = set()

    def load(self) -> set[int]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return set()
        except (OSError, json.JSONDecodeError):
            self.reset()
            return set()
        completed = value.get("completed") if isinstance(value, dict) else None
        if (
            not isinstance(value, dict)
            or value.get("version") != 1
            or value.get("manifestDigest") != self.manifest_digest
            or value.get("pieceCount") != self.piece_count
            or not isinstance(completed, list)
            or any(
                not isinstance(item, int)
                or isinstance(item, bool)
                or item < 0
                or item >= self.piece_count
                for item in completed
            )
        ):
            self.reset()
            return set()
        self.completed = set(completed)
        return set(self.completed)

    def store(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        partial = self.path.with_suffix(".json.partial")
        partial.write_text(
            json.dumps(
                {
                    "version": 1,
                    "manifestDigest": self.manifest_digest,
                    "pieceCount": self.piece_count,
                    "completed": sorted(self.completed),
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(partial, self.path)

    def mark(self, piece_index: int) -> None:
        if piece_index < 0 or piece_index >= self.piece_count:
            raise ValueError("piece index is invalid")
        self.completed.add(piece_index)
        self.store()

    def reset(self) -> None:
        self.completed.clear()
        self.path.unlink(missing_ok=True)


class PieceDownloadScheduler:
    """Download verified global pieces with per-segment source fallback."""

    def __init__(
        self,
        manifest: CheckpointDistributionManifest,
        cache: CheckpointCache,
        sources: tuple[PieceSource, ...] | list[PieceSource],
        *,
        concurrency: int = 4,
        max_source_attempts: int = 16,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if concurrency < 1 or concurrency > 32:
            raise ValueError("concurrency must be between 1 and 32")
        if max_source_attempts < 1 or max_source_attempts > 256:
            raise ValueError("max_source_attempts must be between 1 and 256")
        self.manifest = manifest
        self.cache = cache
        self.sources = tuple(sources)
        self.concurrency = concurrency
        self.max_source_attempts = max_source_attempts
        self.pieces = plan_checkpoint_pieces(manifest)
        self.piece_map = PieceCompletionMap(cache, manifest)
        self.source_bytes: dict[str, int] = {}
        self.progress = progress
        self._completed_bytes_by_file: dict[str, int] = {}
        self._map_lock = asyncio.Lock()

    async def download(self) -> dict[str, Path]:
        candidates = await self._probe_sources()
        missing_sources = {
            item.path for item in self.manifest.files if not candidates.get(item.path)
        }
        if missing_sources:
            raise CheckpointDownloadError(
                f"no usable range source for: {', '.join(sorted(missing_sources))}"
            )
        self._prepare_partial_files()
        completed = await asyncio.to_thread(self._validated_completed_pieces)
        self.piece_map.completed = completed
        self.piece_map.store()
        self._completed_bytes_by_file = {
            checkpoint_file.path: 0 for checkpoint_file in self.manifest.files
        }
        for index in completed:
            for segment in self.pieces[index].segments:
                self._completed_bytes_by_file[segment.file_path] += segment.length

        semaphore = asyncio.Semaphore(self.concurrency)

        async def run(piece: CheckpointPiece) -> None:
            if piece.index in completed:
                return
            async with semaphore:
                await self._download_piece(piece, candidates)

        await asyncio.gather(*(run(piece) for piece in self.pieces))

        blobs: dict[str, Path] = {}
        for checkpoint_file in self.manifest.files:
            partial = self.cache.partial_path(
                self.manifest.distribution_id, checkpoint_file.path
            )
            blobs[checkpoint_file.path] = await asyncio.to_thread(
                self.cache.promote_verified_file,
                partial,
                sha256=checkpoint_file.sha256,
                size=checkpoint_file.size,
            )
        self.piece_map.reset()
        self.cache.write_manifest(self.manifest)
        return blobs

    async def _probe_sources(self) -> dict[str, list[PieceSource]]:
        results = await asyncio.gather(
            *(source.probe() for source in self.sources),
            return_exceptions=True,
        )
        file_sizes = {item.path: item.size for item in self.manifest.files}
        ranked: dict[str, list[tuple[float, PieceSource]]] = {}
        for source, result in zip(self.sources, results, strict=True):
            if (
                isinstance(result, Exception)
                or not result.available
                or not result.range_supported
                or result.content_length != file_sizes.get(source.file_path)
            ):
                continue
            ranked.setdefault(source.file_path, []).append(
                (
                    result.latency_ms
                    if result.latency_ms is not None
                    else float("inf"),
                    source,
                )
            )
        return {
            path: [
                source for _latency, source in sorted(items, key=lambda item: item[0])
            ]
            for path, items in ranked.items()
        }

    def _prepare_partial_files(self) -> None:
        reset_map = False
        for checkpoint_file in self.manifest.files:
            partial = self.cache.partial_path(
                self.manifest.distribution_id, checkpoint_file.path
            )
            partial.parent.mkdir(parents=True, exist_ok=True)
            if partial.exists() and partial.stat().st_size != checkpoint_file.size:
                partial.unlink()
                reset_map = True
            if not partial.exists():
                with partial.open("wb") as output:
                    output.truncate(checkpoint_file.size)
        if reset_map:
            self.piece_map.reset()

    def _validated_completed_pieces(self) -> set[int]:
        completed = self.piece_map.load()
        valid: set[int] = set()
        for index in completed:
            payload = self._read_piece(self.pieces[index])
            if (
                payload is not None
                and hashlib.sha256(payload).hexdigest() == self.pieces[index].sha256
            ):
                valid.add(index)
        return valid

    def _read_piece(self, piece: CheckpointPiece) -> bytes | None:
        payload = bytearray()
        try:
            for segment in piece.segments:
                partial = self.cache.partial_path(
                    self.manifest.distribution_id, segment.file_path
                )
                with partial.open("rb") as source:
                    source.seek(segment.file_offset)
                    chunk = source.read(segment.length)
                if len(chunk) != segment.length:
                    return None
                payload.extend(chunk)
        except OSError:
            return None
        return bytes(payload)

    async def _download_piece(
        self,
        piece: CheckpointPiece,
        candidates: dict[str, list[PieceSource]],
    ) -> None:
        choices_per_segment = [candidates[item.file_path] for item in piece.segments]
        vectors: list[tuple[int, ...]] = []
        seen_vectors: set[tuple[int, ...]] = set()
        for rotation in range(max(len(items) for items in choices_per_segment)):
            vector = tuple(
                (piece.index + rotation) % len(items) for items in choices_per_segment
            )
            if vector not in seen_vectors:
                seen_vectors.add(vector)
                vectors.append(vector)
        for vector in itertools.product(
            *(range(len(items)) for items in choices_per_segment)
        ):
            if len(vectors) >= self.max_source_attempts:
                break
            if vector not in seen_vectors:
                seen_vectors.add(vector)
                vectors.append(vector)
        errors: list[str] = []
        for vector in vectors[: self.max_source_attempts]:
            payload = bytearray()
            contributions: list[tuple[str, int]] = []
            try:
                for segment, source_index in zip(piece.segments, vector, strict=True):
                    source = candidates[segment.file_path][source_index]
                    chunk = await source.fetch_piece(
                        segment.file_path, segment.file_offset, segment.length
                    )
                    payload.extend(chunk)
                    contributions.append((source.provider, len(chunk)))
            except Exception as error:
                errors.append(str(error))
                continue
            if hashlib.sha256(payload).hexdigest() != piece.sha256:
                errors.append("piece digest mismatch")
                continue
            await asyncio.to_thread(self._write_piece, piece, bytes(payload))
            async with self._map_lock:
                self.piece_map.mark(piece.index)
                for segment in piece.segments:
                    self._completed_bytes_by_file[segment.file_path] += segment.length
                for provider, size in contributions:
                    self.source_bytes[provider] = self.source_bytes.get(provider, 0) + size
                if self.progress is not None:
                    current = piece.segments[-1]
                    file_sizes = {
                        item.path: item.size for item in self.manifest.files
                    }
                    completed_total = sum(self._completed_bytes_by_file.values())
                    total = sum(file_sizes.values())
                    self.progress(
                        {
                            "stage": "downloading_checkpoint",
                            "distributionId": self.manifest.distribution_id,
                            "fileName": current.file_path,
                            "bytesCompleted": self._completed_bytes_by_file[
                                current.file_path
                            ],
                            "bytesTotal": file_sizes[current.file_path],
                            "totalBytesCompleted": completed_total,
                            "totalBytesTotal": total,
                            "percent": (completed_total / total * 100) if total else 100,
                            "provider": contributions[-1][0],
                        }
                    )
            return
        detail = errors[-1] if errors else "no source attempt succeeded"
        raise CheckpointDownloadError(
            f"piece {piece.index} could not be verified: {detail}"
        )

    def _write_piece(self, piece: CheckpointPiece, payload: bytes) -> None:
        cursor = 0
        for segment in piece.segments:
            partial = self.cache.partial_path(
                self.manifest.distribution_id, segment.file_path
            )
            descriptor = os.open(partial, os.O_WRONLY)
            try:
                view = memoryview(payload)[cursor : cursor + segment.length]
                offset = segment.file_offset
                while view:
                    written = os.pwrite(descriptor, view, offset)
                    if written <= 0:
                        raise OSError("short partial piece write")
                    view = view[written:]
                    offset += written
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            cursor += segment.length
