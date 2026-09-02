"""Local-first Messager persistence, identity, and transport contracts."""

from .assertion import (
    MessagerAssertionError,
    VerifiedPeerAssertion,
    verify_peer_assertion,
)
from .identity import (
    MESSAGER_SUITE,
    MessagerDeviceKeyManager,
    MessagerDeviceKeys,
    MessagerIdentityError,
)
from .noise_transport import (
    InitiatorExchange,
    MessagerNoiseError,
    ResponderExchange,
    handshake_fingerprint,
)
from .repository import MessagerIdempotencyConflictError, MessagerRepository
from .peer_v2 import MessagerV2SessionCoordinator

__all__ = [
    "MESSAGER_SUITE",
    "MessagerAssertionError",
    "MessagerDeviceKeyManager",
    "MessagerDeviceKeys",
    "MessagerIdentityError",
    "MessagerIdempotencyConflictError",
    "MessagerRepository",
    "MessagerV2SessionCoordinator",
    "InitiatorExchange",
    "MessagerNoiseError",
    "ResponderExchange",
    "VerifiedPeerAssertion",
    "verify_peer_assertion",
    "handshake_fingerprint",
]
