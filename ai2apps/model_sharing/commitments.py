"""Domain-separated Ed25519 Compute commitment signatures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Mapping
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from ai2apps.peer.identity import b64url_decode, b64url_encode

from .manifests import canonical_json

COMMITMENT_DOMAIN = b"AI2APPS-COMPUTE-COMMITMENT-V1\n"
CommitmentKind = Literal["request_content", "input_acceptance", "result_content", "delivery_receipt"]


@dataclass(frozen=True, slots=True)
class SignedCommitment:
    object: dict[str, Any]
    signature: str

    def api_payload(self) -> dict[str, Any]:
        return {
            "installationId": self.object["installationId"],
            "signingKeyId": self.object["signingKeyId"],
            "deviceAccessEpoch": self.object["deviceAccessEpoch"],
            "digest": self.object["digest"],
            "committedAt": self.object["committedAt"],
            "signature": self.signature,
        }


class ComputeCommitmentSigner:
    """Uses the Installation Messager signing key; Peer protocol key IDs are not accepted."""

    def __init__(self, *, installation_id: str, signing_key_id: str, device_access_epoch: int, private_key: Ed25519PrivateKey) -> None:
        if device_access_epoch < 1:
            raise ValueError("device_access_epoch must be positive")
        self.installation_id = self._uuid(installation_id, "installation_id")
        self.signing_key_id = self._uuid(signing_key_id, "signing_key_id")
        self.device_access_epoch = device_access_epoch
        self.private_key = private_key

    @staticmethod
    def _uuid(value: str, field: str) -> str:
        try:
            parsed = UUID(value)
        except (ValueError, AttributeError) as error:
            raise ValueError(f"{field} must be a UUID") from error
        if str(parsed) != value:
            raise ValueError(f"{field} must be canonical")
        return value

    def sign(self, *, kind: CommitmentKind, contract_id: str, digest: str, committed_at: datetime | None = None) -> SignedCommitment:
        contract_id = self._uuid(contract_id, "contract_id")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("digest must be lowercase SHA-256 hex")
        timestamp = committed_at or datetime.now(UTC)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("committed_at must be timezone-aware")
        value = {
            "schemaVersion": "ai2apps.compute.commitment.v1",
            "kind": kind,
            "contractId": contract_id,
            "installationId": self.installation_id,
            "signingKeyId": self.signing_key_id,
            "deviceAccessEpoch": self.device_access_epoch,
            "digest": digest,
            "committedAt": timestamp.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        }
        signature = self.private_key.sign(COMMITMENT_DOMAIN + canonical_json(value))
        return SignedCommitment(value, b64url_encode(signature))


def verify_commitment(value: Mapping[str, Any], signature: str, public_key: Ed25519PublicKey) -> None:
    try:
        public_key.verify(b64url_decode(signature, size=64), COMMITMENT_DOMAIN + canonical_json(value))
    except (ValueError, InvalidSignature) as error:
        raise ValueError("Compute commitment signature is invalid") from error
