"""Publisher verification and installation-local device signing."""

from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from ai2apps.core import ResourceNotFoundError
from ai2apps.packages import PackageRepository, TrustStatus

from .models import ExtensionError, InspectedBundle, UnitKind


class DeviceSigner:
    def __init__(self, root: Path) -> None:
        self.root = root / ".device"
        self.private_path = self.root / "ed25519.key"

    def _private(self) -> Ed25519PrivateKey:
        if self.private_path.exists():
            return Ed25519PrivateKey.from_private_bytes(self.private_path.read_bytes())
        self.root.mkdir(parents=True, exist_ok=True)
        key = Ed25519PrivateKey.generate()
        self.private_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
        )
        os.chmod(self.private_path, 0o600)
        return key

    @property
    def public_key(self) -> str:
        raw = (
            self._private()
            .public_key()
            .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        )
        return base64.b64encode(raw).decode()

    def sign(self, digest: str) -> str:
        return base64.b64encode(self._private().sign(digest.encode("ascii"))).decode()

    def verify(self, bundle: InspectedBundle) -> dict:
        if bundle.signature.get("public_key") != self.public_key:
            raise ExtensionError(
                "foreign_device_patch", "Patch is not signed by this device"
            )
        try:
            Ed25519PublicKey.from_public_bytes(
                base64.b64decode(self.public_key)
            ).verify(
                base64.b64decode(bundle.signature["signature"]),
                bundle.digest.encode("ascii"),
            )
        except (KeyError, ValueError, InvalidSignature) as error:
            raise ExtensionError(
                "invalid_device_signature", "Device Patch signature is invalid"
            ) from error
        return {
            "signature": "valid",
            "trust": "local-device",
            "public_key": self.public_key,
        }


class InteractiveTrustVerifier:
    def __init__(self, publishers: PackageRepository, device: DeviceSigner) -> None:
        self.publishers = publishers
        self.device = device

    def verify(self, bundle: InspectedBundle) -> dict:
        if bundle.kind == "patch":
            return self.device.verify(bundle)
        publisher_key = bundle.manifest["publisher"]["id"]
        try:
            publisher = self.publishers.get_publisher(publisher_key)
        except ResourceNotFoundError as error:
            raise ExtensionError(
                "publisher_unknown", "Package publisher is unknown"
            ) from error
        if publisher.trust_status is TrustStatus.REVOKED:
            raise ExtensionError("publisher_revoked", "Package publisher is revoked")
        if publisher.trust_status is not TrustStatus.TRUSTED:
            raise ExtensionError(
                "publisher_untrusted", "Package publisher is not trusted"
            )
        if bundle.kind is UnitKind.APP and publisher.source not in {"builtin", "user"}:
            raise ExtensionError(
                "publisher_not_install_authority",
                "Formal App installation requires the local owner or AI2Apps Root",
            )
        if bundle.signature.get("key_id") != publisher.key_id:
            raise ExtensionError("publisher_key_mismatch", "Publisher key ID mismatch")
        try:
            key = Ed25519PublicKey.from_public_bytes(
                base64.b64decode(publisher.public_key)
            )
            key.verify(
                base64.b64decode(bundle.signature["signature"]),
                bundle.digest.encode("ascii"),
            )
        except (KeyError, ValueError, InvalidSignature) as error:
            raise ExtensionError(
                "signature_invalid", "Publisher signature is invalid"
            ) from error
        return {
            "signature": "valid",
            "trust": "trusted",
            "publisher": publisher_key,
            "key_id": publisher.key_id,
        }
