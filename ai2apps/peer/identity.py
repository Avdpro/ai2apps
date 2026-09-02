"""Protocol-scoped Peer Device identities and Cloud registration."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from ai2apps.cloud_client import AI2AppsCloudClient
from ai2apps.secrets import SecretBackend

PEER_KEY_SUITE = "noise_ik_25519_chachapoly_sha256_v1"
REGISTRATION_DOMAIN = "ai2apps-peer-device-key-registration-v1"


class PeerProtocol(StrEnum):
    MESSAGER_V2 = "messager-v2"
    MODEL_SHARE_V1 = "model-share-v1"
    CHECKPOINT_V1 = "checkpoint-v1"

    @property
    def audience(self) -> str:
        return {
            PeerProtocol.MESSAGER_V2: "ai2apps-messager-peer-v2",
            PeerProtocol.MODEL_SHARE_V1: "ai2apps-model-share-peer-v1",
            PeerProtocol.CHECKPOINT_V1: "ai2apps-checkpoint-peer-v1",
        }[self]

    @property
    def purpose_type(self) -> str:
        return {
            PeerProtocol.MESSAGER_V2: "conversation",
            PeerProtocol.MODEL_SHARE_V1: "compute_contract",
            PeerProtocol.CHECKPOINT_V1: "checkpoint_distribution",
        }[self]


class PeerIdentityError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def b64url_decode(value: str, *, size: int | None = None) -> bytes:
    if not isinstance(value, str) or "=" in value:
        raise ValueError("base64url value is not canonical")
    try:
        decoded = base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
    except (ValueError, TypeError) as error:
        raise ValueError("base64url value is invalid") from error
    if b64url_encode(decoded) != value or (size is not None and len(decoded) != size):
        raise ValueError("base64url value is not canonical")
    return decoded


def _raw_private(key: Ed25519PrivateKey | X25519PrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )


def _raw_public(key: Ed25519PrivateKey | X25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )


def _canonical_uuid(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise PeerIdentityError("PEER_IDENTITY_INVALID", f"{field} must be a UUID")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise PeerIdentityError(
            "PEER_IDENTITY_INVALID", f"{field} must be a UUID"
        ) from error
    if str(parsed) != value:
        raise PeerIdentityError("PEER_IDENTITY_INVALID", f"{field} must be canonical")
    return value


@dataclass(frozen=True, slots=True)
class PeerDeviceKeys:
    device_id: str
    protocol: PeerProtocol
    identity_private: Ed25519PrivateKey
    static_dh_private: X25519PrivateKey

    @property
    def identity_public_bytes(self) -> bytes:
        return _raw_public(self.identity_private)

    @property
    def static_dh_public_bytes(self) -> bytes:
        return _raw_public(self.static_dh_private)

    @property
    def identity_public(self) -> str:
        return b64url_encode(self.identity_public_bytes)

    @property
    def static_dh_public(self) -> str:
        return b64url_encode(self.static_dh_public_bytes)

    @property
    def identity_fingerprint(self) -> str:
        return hashlib.sha256(self.identity_public_bytes).hexdigest()

    @property
    def static_dh_fingerprint(self) -> str:
        return hashlib.sha256(self.static_dh_public_bytes).hexdigest()


class PeerDeviceKeyManager:
    """Persist one independent Ed25519/X25519 bundle per Device and protocol."""

    def __init__(self, backend: SecretBackend) -> None:
        self.backend = backend

    @staticmethod
    def secret_key(device_id: str, protocol: PeerProtocol) -> str:
        _canonical_uuid(device_id, "device_id")
        return f"ai2apps-peer-device-keys-{protocol.value}-{device_id}"

    def generate(self, device_id: str, protocol: PeerProtocol) -> PeerDeviceKeys:
        _canonical_uuid(device_id, "device_id")
        keys = PeerDeviceKeys(
            device_id=device_id,
            protocol=protocol,
            identity_private=Ed25519PrivateKey.generate(),
            static_dh_private=X25519PrivateKey.generate(),
        )
        self.backend.store(
            self.secret_key(device_id, protocol),
            json.dumps(
                {
                    "version": 1,
                    "deviceId": device_id,
                    "protocol": protocol.value,
                    "identitySigningPrivateKey": b64url_encode(
                        _raw_private(keys.identity_private)
                    ),
                    "staticDhPrivateKey": b64url_encode(
                        _raw_private(keys.static_dh_private)
                    ),
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
        )
        return keys

    def load(self, device_id: str, protocol: PeerProtocol) -> PeerDeviceKeys:
        try:
            payload = json.loads(self.backend.load(self.secret_key(device_id, protocol)))
            expected = {
                "version",
                "deviceId",
                "protocol",
                "identitySigningPrivateKey",
                "staticDhPrivateKey",
            }
            if (
                not isinstance(payload, dict)
                or set(payload) != expected
                or payload["version"] != 1
                or payload["deviceId"] != device_id
                or payload["protocol"] != protocol.value
            ):
                raise ValueError("key bundle fields are invalid")
            return PeerDeviceKeys(
                device_id=device_id,
                protocol=protocol,
                identity_private=Ed25519PrivateKey.from_private_bytes(
                    b64url_decode(payload["identitySigningPrivateKey"], size=32)
                ),
                static_dh_private=X25519PrivateKey.from_private_bytes(
                    b64url_decode(payload["staticDhPrivateKey"], size=32)
                ),
            )
        except KeyError:
            raise
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            raise PeerIdentityError(
                "PEER_DEVICE_KEY_CORRUPT",
                "The local protocol-scoped Peer key bundle is invalid.",
            ) from error

    def get_or_create(self, device_id: str, protocol: PeerProtocol) -> PeerDeviceKeys:
        try:
            return self.load(device_id, protocol)
        except KeyError:
            return self.generate(device_id, protocol)

    @staticmethod
    def registration_transcript(
        challenge: Mapping[str, Any], keys: PeerDeviceKeys
    ) -> bytes:
        if challenge.get("protocol") != keys.protocol.value:
            raise PeerIdentityError(
                "PEER_DEVICE_KEY_CHALLENGE_INVALID",
                "Cloud challenge protocol does not match the local key domain.",
            )
        access_epoch = challenge.get("accessEpoch")
        if isinstance(access_epoch, bool) or not isinstance(access_epoch, int) or access_epoch < 1:
            raise PeerIdentityError(
                "PEER_DEVICE_KEY_CHALLENGE_INVALID", "Cloud challenge epoch is invalid."
            )
        fields = (
            REGISTRATION_DOMAIN,
            challenge.get("challengeId"),
            challenge.get("challenge"),
            challenge.get("deviceId"),
            keys.protocol.value,
            str(access_epoch),
            PEER_KEY_SUITE,
            keys.identity_public,
            keys.static_dh_public,
        )
        if not all(isinstance(value, str) and value for value in fields):
            raise PeerIdentityError(
                "PEER_DEVICE_KEY_CHALLENGE_INVALID", "Cloud challenge is invalid."
            )
        return ("\n".join(fields) + "\n").encode("utf-8")

    @staticmethod
    async def _json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if response.status_code >= 400:
            detail = payload.get("error", {}) if isinstance(payload, dict) else {}
            raise PeerIdentityError(
                str(detail.get("code") or "PEER_CLOUD_REQUEST_FAILED"),
                str(detail.get("message") or "Cloud rejected the Peer request."),
                status_code=response.status_code,
            )
        if not isinstance(payload, dict):
            raise PeerIdentityError(
                "PEER_CLOUD_RESPONSE_INVALID", "Cloud returned invalid JSON.", status_code=502
            )
        return payload

    async def register(
        self,
        *,
        cloud: AI2AppsCloudClient,
        device_id: str,
        protocol: PeerProtocol,
        headers: Mapping[str, str],
        rotate: bool = False,
    ) -> dict[str, Any]:
        keys = self.generate(device_id, protocol) if rotate else self.get_or_create(device_id, protocol)
        response = await cloud.request(
            "POST",
            "/v1/peer/device-key-challenges",
            json={"protocol": protocol.value},
            headers=headers,
        )
        try:
            challenge = await self._json(response)
        finally:
            await response.aclose()
        if challenge.get("deviceId") != device_id:
            raise PeerIdentityError(
                "PEER_DEVICE_KEY_CHALLENGE_INVALID", "Challenge Device binding does not match."
            )
        transcript = self.registration_transcript(challenge, keys)
        response = await cloud.request(
            "PUT",
            f"/v1/peer/device-keys/{protocol.value}",
            json={
                "challengeId": challenge["challengeId"],
                "suite": PEER_KEY_SUITE,
                "identitySigningPublicKey": keys.identity_public,
                "staticDhPublicKey": keys.static_dh_public,
                "proof": b64url_encode(keys.identity_private.sign(transcript)),
            },
            headers=headers,
        )
        try:
            registered = await self._json(response)
        finally:
            await response.aclose()
        expected = {
            "deviceId": device_id,
            "protocol": protocol.value,
            "deviceAccessEpoch": challenge["accessEpoch"],
            "suite": PEER_KEY_SUITE,
            "identitySigningPublicKey": keys.identity_public,
            "staticDhPublicKey": keys.static_dh_public,
            "status": "active",
        }
        if any(registered.get(name) != value for name, value in expected.items()):
            raise PeerIdentityError(
                "PEER_DEVICE_KEY_RESPONSE_MISMATCH",
                "Cloud key registration does not match the local key bundle.",
                status_code=502,
            )
        _canonical_uuid(registered.get("keyId"), "keyId")
        return registered
