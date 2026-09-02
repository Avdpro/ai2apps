from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ai2apps.messager import (
    MessagerAssertionError,
    MessagerDeviceKeyManager,
    verify_peer_assertion,
)
from ai2apps.messager.identity import b64url_decode


class MemorySecrets:
    provider_name = "memory"

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def store(self, key: str, value: str) -> None:
        self.values[key] = value

    def load(self, key: str) -> str:
        return self.values[key]

    def delete(self, key: str) -> None:
        self.values.pop(key, None)


def _cloud_fixture() -> dict:
    path = Path(
        "/Users/avdpropang/sdk/ai2apps-cloud/fixtures/"
        "messager-peer-identity-v1/vectors.json"
    )
    if not path.exists():
        pytest.skip("AI2Apps Cloud contract fixture checkout is unavailable")
    return json.loads(path.read_text())


def test_device_keys_are_atomic_and_stable() -> None:
    backend = MemorySecrets()
    manager = MessagerDeviceKeyManager(backend)
    device_id = "11111111-1111-4111-8111-111111111111"

    first = manager.get_or_create(device_id)
    second = manager.get_or_create(device_id)

    assert first.identity_public == second.identity_public
    assert first.static_dh_public == second.static_dh_public
    assert len(backend.values) == 1


def test_cloud_proof_transcript_fixture() -> None:
    fixture = _cloud_fixture()["proofTranscript"]
    transcript = base64.b64decode(fixture["transcriptUtf8Base64"])
    expected = (
        "ai2apps-messager-device-key-registration-v1\n"
        f"{fixture['challengeId']}\n{fixture['challenge']}\n{fixture['deviceId']}\n"
        f"{fixture['accessEpoch']}\n{fixture['suite']}\n"
        f"{fixture['identitySigningPublicKey']}\n{fixture['staticDhPublicKey']}\n"
    ).encode()
    assert transcript == expected
    Ed25519PublicKey.from_public_bytes(
        b64url_decode(fixture["identitySigningPublicKey"], size=32)
    ).verify(b64url_decode(fixture["proof"], size=64), transcript)


def test_cloud_peer_assertion_fixture_and_mutation() -> None:
    fixture = _cloud_fixture()["peerAssertion"]
    verified = verify_peer_assertion(
        fixture["compactJwt"],
        {"keys": [fixture["publicJwk"]]},
        handshake_id=fixture["claims"]["handshake_id"],
        now=fixture["claims"]["iat"],
    )
    assert verified.claims == fixture["claims"]

    signature_mutation = fixture["compactJwt"][:-1] + (
        "A" if fixture["compactJwt"][-1] != "A" else "B"
    )
    with pytest.raises(MessagerAssertionError, match="signature"):
        verify_peer_assertion(
            signature_mutation,
            {"keys": [fixture["publicJwk"]]},
            handshake_id=fixture["claims"]["handshake_id"],
            now=fixture["claims"]["iat"],
        )
