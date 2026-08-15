"""Offline Ed25519 publisher verification and independent local audit hook."""

from __future__ import annotations

import base64
import inspect
import re
import zipfile
from collections.abc import Awaitable, Callable
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ai2apps.core import ResourceNotFoundError

from .models import (
    AuditDecision,
    AuditRisk,
    InspectedServicePackage,
    PackageError,
    TrustStatus,
)
from .repository import PackageRepository

AuditHandler = Callable[[dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]


class PackageTrustVerifier:
    def __init__(self, repository: PackageRepository) -> None:
        self.repository = repository
        self._auditor: AuditHandler | None = None

    def bind_local_ai_auditor(self, auditor: AuditHandler) -> None:
        self._auditor = auditor

    def verify_signature(
        self, package: InspectedServicePackage, *, allow_untrusted: bool = False
    ) -> dict[str, Any]:
        try:
            publisher = self.repository.get_publisher(package.manifest.publisher_key)
        except ResourceNotFoundError as error:
            raise PackageError(
                "publisher_unknown", "Package publisher is not in the trust store"
            ) from error
        if publisher.trust_status is TrustStatus.REVOKED:
            raise PackageError(
                "publisher_revoked", "Package publisher has been revoked"
            )
        if publisher.trust_status is not TrustStatus.TRUSTED and not allow_untrusted:
            raise PackageError(
                "publisher_untrusted", "Package publisher is not trusted"
            )
        attestation_key = package.publisher_attestation.get("key_id")
        signature_key = package.signature.get("key_id", attestation_key)
        if attestation_key != publisher.key_id or signature_key != publisher.key_id:
            raise PackageError(
                "publisher_key_mismatch", "Publisher key id does not match trust store"
            )
        try:
            public_bytes = base64.b64decode(publisher.public_key, validate=True)
            signature = base64.b64decode(package.signature["signature"], validate=True)
            Ed25519PublicKey.from_public_bytes(public_bytes).verify(
                signature, package.digest.encode("ascii")
            )
        except (ValueError, InvalidSignature) as error:
            raise PackageError(
                "signature_invalid", "Publisher signature verification failed"
            ) from error
        return {
            "signature": "valid",
            "publisher": publisher.publisher_key,
            "key_id": publisher.key_id,
            "trust": publisher.trust_status.value,
        }

    async def audit(self, package: InspectedServicePackage) -> dict[str, Any]:
        sources, findings = self._source_review_input(package)
        if self._auditor is None:
            return {
                "decision": AuditDecision.REVIEW.value,
                "risk": AuditRisk.MEDIUM.value,
                "issuer": "ai2apps:static-gate",
                "model": None,
                "policy_version": "ai2apps.service-audit/v1",
                "evidence": {
                    "reason": "local_ai_auditor_not_configured",
                    "static_findings": findings,
                    "source_files_reviewed": sorted(sources),
                },
            }
        request = {
            "schema": "ai2apps.service-audit-request/v1",
            "package_digest": package.digest,
            "service_id": package.manifest.service_key,
            "version": package.manifest.version,
            "runtime_mode": package.manifest.runtime_mode.value,
            "permissions": package.manifest.permissions,
            "files": [
                {"path": item.path, "hash": item.content_hash, "size": item.size_bytes}
                for item in package.files
            ],
            "sbom": package.sbom,
            "source": sources,
            "static_findings": findings,
        }
        try:
            result = self._auditor(request)
            if inspect.isawaitable(result):
                result = await result
        except Exception as error:
            raise PackageError(
                "audit_failed_closed", "Local AI audit failed"
            ) from error
        if not isinstance(result, dict):
            raise PackageError(
                "invalid_audit", "Local AI audit returned invalid output"
            )
        try:
            decision = AuditDecision(result.get("decision"))
            risk = AuditRisk(result.get("risk"))
        except ValueError as error:
            raise PackageError(
                "invalid_audit", "Local AI audit decision/risk is invalid"
            ) from error
        if decision is AuditDecision.REJECT or risk is AuditRisk.CRITICAL:
            raise PackageError(
                "audit_rejected", "Local AI audit rejected the package", details=result
            )
        evidence = result.get("evidence", {})
        if not isinstance(evidence, dict):
            evidence = {"auditor_evidence": evidence}
        evidence = {
            **evidence,
            "static_findings": findings,
            "source_files_reviewed": sorted(sources),
        }
        return {
            "decision": decision.value,
            "risk": risk.value,
            "issuer": str(result.get("issuer", "ai2apps:local-ai")),
            "model": result.get("model"),
            "policy_version": str(
                result.get("policy_version", "ai2apps.service-audit/v1")
            ),
            "evidence": evidence,
        }

    @staticmethod
    def _source_review_input(
        package: InspectedServicePackage,
    ) -> tuple[dict[str, str], list[dict[str, str]]]:
        source: dict[str, str] = {}
        findings: list[dict[str, str]] = []
        patterns = {
            "process_execution": r"\b(?:os\.system|subprocess\.|popen\s*\()",
            "dynamic_code": r"\b(?:eval|exec)\s*\(",
            "native_bridge": r"\b(?:ctypes|cffi)\b",
            "outbound_network": r"\b(?:requests\.|urllib\.request|socket\.connect)",
        }
        remaining = 2 * 1024 * 1024
        with zipfile.ZipFile(package.archive_path) as archive:
            for item in package.files:
                if not item.path.lower().endswith(
                    (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".rs", ".go")
                ):
                    continue
                if remaining <= 0:
                    break
                content = archive.read(item.path)[: min(item.size_bytes, remaining)]
                remaining -= len(content)
                text = content.decode("utf-8", "replace")
                source[item.path] = text
                for kind, pattern in patterns.items():
                    if re.search(pattern, text, re.IGNORECASE):
                        findings.append(
                            {"kind": kind, "path": item.path, "severity": "review"}
                        )
        return source, findings
