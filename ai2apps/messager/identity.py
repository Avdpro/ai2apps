"""Device-bound Messager identity keys and Cloud registration."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from ai2apps.cloud_client import AI2AppsCloudClient
from ai2apps.secrets import SecretBackend

MESSAGER_SUITE = "noise_ik_25519_chachapoly_sha256_v1"
REGISTRATION_DOMAIN = "ai2apps-messager-device-key-registration-v1"


class MessagerIdentityError(RuntimeError):
    """A local key or Cloud key-registration contract was invalid."""

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


@dataclass(frozen=True, slots=True)
class MessagerDeviceKeys:
    device_id: str
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


class MessagerDeviceKeyManager:
    """Own a single atomic SecretBackend key bundle per Cloud Device."""

    def __init__(self, backend: SecretBackend) -> None:
        self.backend = backend

    @staticmethod
    def _validate_device_id(device_id: str) -> str:
        try:
            parsed = UUID(device_id)
        except (ValueError, AttributeError) as error:
            raise MessagerIdentityError(
                "MESSAGER_DEVICE_ID_INVALID", "Cloud Device ID is invalid."
            ) from error
        if str(parsed) != device_id:
            raise MessagerIdentityError(
                "MESSAGER_DEVICE_ID_INVALID", "Cloud Device ID is not canonical."
            )
        return device_id

    @classmethod
    def secret_key(cls, device_id: str) -> str:
        return f"ai2apps-messager-device-keys-{cls._validate_device_id(device_id)}"

    def generate(self, device_id: str) -> MessagerDeviceKeys:
        self._validate_device_id(device_id)
        keys = MessagerDeviceKeys(
            device_id=device_id,
            identity_private=Ed25519PrivateKey.generate(),
            static_dh_private=X25519PrivateKey.generate(),
        )
        payload = json.dumps(
            {
                "version": 1,
                "deviceId": device_id,
                "identitySigningPrivateKey": b64url_encode(
                    _raw_private(keys.identity_private)
                ),
                "staticDhPrivateKey": b64url_encode(_raw_private(keys.static_dh_private)),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        self.backend.store(self.secret_key(device_id), payload)
        return keys

    def load(self, device_id: str) -> MessagerDeviceKeys:
        try:
            payload = json.loads(self.backend.load(self.secret_key(device_id)))
            if set(payload) != {
                "version",
                "deviceId",
                "identitySigningPrivateKey",
                "staticDhPrivateKey",
            } or payload["version"] != 1 or payload["deviceId"] != device_id:
                raise ValueError("key bundle fields are invalid")
            return MessagerDeviceKeys(
                device_id=device_id,
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
            raise MessagerIdentityError(
                "MESSAGER_DEVICE_KEY_CORRUPT",
                "The local Messager Device key bundle is invalid.",
            ) from error

    def get_or_create(self, device_id: str) -> MessagerDeviceKeys:
        try:
            return self.load(device_id)
        except KeyError:
            return self.generate(device_id)
        except MessagerIdentityError as error:
            if error.code != "MESSAGER_DEVICE_KEY_CORRUPT":
                raise
            return self.generate(device_id)

    @staticmethod
    def registration_transcript(
        challenge: Mapping[str, Any], keys: MessagerDeviceKeys
    ) -> bytes:
        fields = (
            REGISTRATION_DOMAIN,
            challenge.get("challengeId"),
            challenge.get("challenge"),
            challenge.get("deviceId"),
            str(challenge.get("accessEpoch")),
            MESSAGER_SUITE,
            keys.identity_public,
            keys.static_dh_public,
        )
        if not all(isinstance(value, str) and value for value in fields):
            raise MessagerIdentityError(
                "MESSAGER_CHALLENGE_INVALID", "Cloud returned an invalid challenge."
            )
        return ("\n".join(fields) + "\n").encode("utf-8")

    @staticmethod
    async def _json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if response.status_code >= 400:
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            raise MessagerIdentityError(
                str(error.get("code") or "MESSAGER_CLOUD_REQUEST_FAILED"),
                str(error.get("message") or "Cloud rejected the Messager request."),
                status_code=response.status_code,
            )
        if not isinstance(payload, dict):
            raise MessagerIdentityError(
                "MESSAGER_CLOUD_RESPONSE_INVALID", "Cloud returned invalid JSON.", status_code=502
            )
        return payload

    async def register(
        self,
        *,
        cloud: AI2AppsCloudClient,
        device_id: str,
        headers: Mapping[str, str],
        rotate: bool = False,
    ) -> dict[str, Any]:
        keys = self.generate(device_id) if rotate else self.get_or_create(device_id)
        response = await cloud.request(
            "POST", "/v1/messager/device-key-challenges", headers=headers
        )
        try:
            challenge = await self._json(response)
        finally:
            await response.aclose()
        if challenge.get("deviceId") != device_id:
            raise MessagerIdentityError(
                "MESSAGER_CHALLENGE_INVALID", "Challenge Device binding does not match."
            )
        transcript = self.registration_transcript(challenge, keys)
        request = {
            "challengeId": challenge["challengeId"],
            "suite": MESSAGER_SUITE,
            "identitySigningPublicKey": keys.identity_public,
            "staticDhPublicKey": keys.static_dh_public,
            "proof": b64url_encode(keys.identity_private.sign(transcript)),
        }
        response = await cloud.request(
            "PUT", "/v1/messager/device-key", json=request, headers=headers
        )
        try:
            registered = await self._json(response)
        finally:
            await response.aclose()
        expected = {
            "deviceId": device_id,
            "deviceAccessEpoch": challenge["accessEpoch"],
            "suite": MESSAGER_SUITE,
            "identitySigningPublicKey": keys.identity_public,
            "staticDhPublicKey": keys.static_dh_public,
            "identitySigningFingerprintSha256": keys.identity_fingerprint,
            "staticDhFingerprintSha256": keys.static_dh_fingerprint,
            "status": "active",
        }
        if any(registered.get(name) != value for name, value in expected.items()):
            raise MessagerIdentityError(
                "MESSAGER_DEVICE_KEY_RESPONSE_MISMATCH",
                "Cloud key registration does not match the local key bundle.",
                status_code=502,
            )
        return registered
