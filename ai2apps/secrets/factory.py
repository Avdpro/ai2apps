"""Provider registry and platform-aware SecretBackend selection."""

from __future__ import annotations

import os
import platform
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path

from .backends import (
    EncryptedFileSecretBackend,
    LinuxSecretServiceBackend,
    MacOSKeychainBackend,
    NamespacedSecretBackend,
    SecretBackend,
    SecretBackendError,
)

BackendFactory = Callable[[Path], SecretBackend]
_PROVIDERS: dict[str, BackendFactory] = {
    "macos-keychain": lambda _: MacOSKeychainBackend(),
    "linux-secret-service": lambda _: LinuxSecretServiceBackend(),
    "encrypted-file": lambda path: EncryptedFileSecretBackend(path),
}


def register_secret_backend(
    name: str, factory: BackendFactory, *, replace: bool = False
) -> None:
    """Register a Credential Manager, TPM, KMS, or plugin-owned provider."""

    normalized = name.strip().lower()
    if not normalized:
        raise ValueError("Secret backend name cannot be empty")
    if normalized in _PROVIDERS and not replace:
        raise ValueError(f"Secret backend is already registered: {normalized}")
    _PROVIDERS[normalized] = factory


def select_secret_backend_name(
    configured: str = "auto",
    *,
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
    executable_lookup: Callable[[str], str | None] = shutil.which,
) -> str:
    environment = os.environ if environ is None else environ
    requested = environment.get("AI2APPS_SECRET_BACKEND", configured).strip().lower()
    if requested != "auto":
        return requested
    host = (system or platform.system()).lower()
    if host == "darwin":
        return "macos-keychain"
    if host == "linux":
        has_session_bus = bool(environment.get("DBUS_SESSION_BUS_ADDRESS"))
        if has_session_bus and executable_lookup("secret-tool"):
            return "linux-secret-service"
    return "encrypted-file"


def create_secret_backend(
    directory: str | Path,
    *,
    configured: str = "auto",
    namespace: str | None = None,
) -> SecretBackend:
    name = select_secret_backend_name(configured)
    factory = _PROVIDERS.get(name)
    if factory is None:
        available = ", ".join(sorted(_PROVIDERS))
        raise SecretBackendError(
            f"Unknown Secret backend '{name}'. Available providers: {available}"
        )
    backend = factory(Path(directory).expanduser().resolve())
    if namespace is not None:
        return NamespacedSecretBackend(backend, namespace)
    return backend
