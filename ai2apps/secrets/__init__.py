"""Keychain-backed secret management."""

from .backends import (
    EncryptedFileSecretBackend,
    LinuxSecretServiceBackend,
    MacOSKeychainBackend,
    MemorySecretBackend,
    NamespacedSecretBackend,
    SecretBackend,
    SecretBackendError,
)
from .factory import (
    create_secret_backend,
    register_secret_backend,
    select_secret_backend_name,
)
from .models import SecretInjection, SecretRecord
from .repository import SecretRepository

__all__ = [
    "EncryptedFileSecretBackend", "LinuxSecretServiceBackend",
    "MacOSKeychainBackend", "MemorySecretBackend", "NamespacedSecretBackend", "SecretBackend",
    "SecretBackendError", "create_secret_backend", "register_secret_backend",
    "select_secret_backend_name",
    "SecretInjection", "SecretRecord", "SecretRepository",
]
