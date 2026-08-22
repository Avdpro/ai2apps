"""Platform-independent secret-value backend contract and built-in providers."""

from __future__ import annotations

import base64
import ctypes
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import threading
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SecretBackendError(RuntimeError):
    """A provider is unavailable, locked, or cannot complete an operation."""


class SecretBackend(Protocol):
    provider_name: str

    def store(self, key: str, value: str) -> None: ...
    def load(self, key: str) -> str: ...
    def delete(self, key: str) -> None: ...


class NamespacedSecretBackend:
    """Scope backend account names to one immutable Local security identity.

    The wrapper is intentionally backend-independent. Safe legacy records are
    copied on first read and verified before use; globally ambiguous Cloud
    browser sessions are not migrated because they cannot be attributed to one
    Local instance.
    """

    _NAMESPACE = re.compile(r"^[A-Za-z0-9._~-]{1,200}$")
    _AMBIGUOUS_LEGACY_PREFIXES = ("ai2apps-cloud-session-",)

    def __init__(self, backend: SecretBackend, namespace: str) -> None:
        if not self._NAMESPACE.fullmatch(namespace):
            raise ValueError("Secret namespace is invalid")
        self.backend = backend
        self.namespace = namespace
        self.provider_name = backend.provider_name
        self._prefix = f"ai2apps.v1.{namespace}."

    def __getattr__(self, name: str):
        # Preserve diagnostics such as vault_path without exposing an alternate
        # unscoped SecretBackend through the normal runtime interface.
        return getattr(self.backend, name)

    def scoped_key(self, key: str) -> str:
        if not isinstance(key, str) or not key:
            raise ValueError("Secret key cannot be empty")
        return self._prefix + key

    def _can_migrate_legacy(self, key: str) -> bool:
        return not key.startswith(self._AMBIGUOUS_LEGACY_PREFIXES)

    def store(self, key: str, value: str) -> None:
        self.backend.store(self.scoped_key(key), value)

    def load(self, key: str) -> str:
        scoped = self.scoped_key(key)
        try:
            return self.backend.load(scoped)
        except KeyError:
            if not self._can_migrate_legacy(key):
                raise
        value = self.backend.load(key)
        self.backend.store(scoped, value)
        if self.backend.load(scoped) != value:
            raise SecretBackendError("Secret migration read-back verification failed")
        return value

    def delete(self, key: str) -> None:
        self.backend.delete(self.scoped_key(key))
        if self._can_migrate_legacy(key):
            # Prevent a later read from resurrecting a migrated legacy value.
            self.backend.delete(key)


class MacOSKeychainBackend:
    provider_name = "macos-keychain"

    _ERR_SEC_ITEM_NOT_FOUND = -25300
    _ERR_SEC_DUPLICATE_ITEM = -25299

    def __init__(self, *, service: str = "AI2Apps Secret Store") -> None:
        self.service = service
        if platform.system() != "Darwin":
            raise SecretBackendError("macOS Keychain is only available on Darwin")
        self._security = ctypes.CDLL(
            "/System/Library/Frameworks/Security.framework/Security"
        )
        self._core_foundation = ctypes.CDLL(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )
        self._configure_functions()

    def _configure_functions(self) -> None:
        void_p = ctypes.c_void_p
        uint32 = ctypes.c_uint32
        self._security.SecKeychainAddGenericPassword.argtypes = [
            void_p, uint32, void_p, uint32, void_p, uint32, void_p,
            ctypes.POINTER(void_p),
        ]
        self._security.SecKeychainAddGenericPassword.restype = ctypes.c_int32
        self._security.SecKeychainFindGenericPassword.argtypes = [
            void_p, uint32, void_p, uint32, void_p,
            ctypes.POINTER(uint32), ctypes.POINTER(void_p), ctypes.POINTER(void_p),
        ]
        self._security.SecKeychainFindGenericPassword.restype = ctypes.c_int32
        self._security.SecKeychainItemModifyAttributesAndData.argtypes = [
            void_p, void_p, uint32, void_p,
        ]
        self._security.SecKeychainItemModifyAttributesAndData.restype = ctypes.c_int32
        self._security.SecKeychainItemDelete.argtypes = [void_p]
        self._security.SecKeychainItemDelete.restype = ctypes.c_int32
        self._security.SecKeychainItemFreeContent.argtypes = [void_p, void_p]
        self._security.SecKeychainItemFreeContent.restype = ctypes.c_int32
        self._core_foundation.CFRelease.argtypes = [void_p]
        self._core_foundation.CFRelease.restype = None

    @staticmethod
    def _buffer(value: str) -> tuple[bytes, ctypes.Array[ctypes.c_char]]:
        encoded = value.encode("utf-8")
        return encoded, ctypes.create_string_buffer(encoded)

    def _find_item(
        self, key: str, *, include_password: bool = False
    ) -> tuple[int, ctypes.c_void_p, bytes | None]:
        service, service_buffer = self._buffer(self.service)
        account, account_buffer = self._buffer(key)
        item = ctypes.c_void_p()
        password_length = ctypes.c_uint32()
        password_data = ctypes.c_void_p()
        status = self._security.SecKeychainFindGenericPassword(
            None,
            len(service), ctypes.cast(service_buffer, ctypes.c_void_p),
            len(account), ctypes.cast(account_buffer, ctypes.c_void_p),
            ctypes.byref(password_length) if include_password else None,
            ctypes.byref(password_data) if include_password else None,
            ctypes.byref(item),
        )
        password = None
        if status == 0 and include_password:
            try:
                password = ctypes.string_at(password_data, password_length.value)
            finally:
                self._security.SecKeychainItemFreeContent(None, password_data)
        return status, item, password

    def _release(self, item: ctypes.c_void_p) -> None:
        if item.value:
            self._core_foundation.CFRelease(item)

    def store(self, key: str, value: str) -> None:
        status, item, _ = self._find_item(key)
        secret, secret_buffer = self._buffer(value)
        if status == 0:
            try:
                status = self._security.SecKeychainItemModifyAttributesAndData(
                    item, None, len(secret),
                    ctypes.cast(secret_buffer, ctypes.c_void_p),
                )
            finally:
                self._release(item)
        elif status == self._ERR_SEC_ITEM_NOT_FOUND:
            service, service_buffer = self._buffer(self.service)
            account, account_buffer = self._buffer(key)
            created_item = ctypes.c_void_p()
            status = self._security.SecKeychainAddGenericPassword(
                None,
                len(service), ctypes.cast(service_buffer, ctypes.c_void_p),
                len(account), ctypes.cast(account_buffer, ctypes.c_void_p),
                len(secret), ctypes.cast(secret_buffer, ctypes.c_void_p),
                ctypes.byref(created_item),
            )
            self._release(created_item)
        else:
            self._release(item)
        if status == self._ERR_SEC_DUPLICATE_ITEM:
            # Another process may have created the item between find and add.
            return self.store(key, value)
        if status:
            raise SecretBackendError(
                f"Unable to store secret in macOS Keychain (OSStatus {status})"
            )

    def load(self, key: str) -> str:
        status, item, password = self._find_item(key, include_password=True)
        self._release(item)
        if status == self._ERR_SEC_ITEM_NOT_FOUND:
            raise KeyError("Secret value is unavailable in macOS Keychain")
        if status or password is None:
            raise SecretBackendError(
                f"Unable to load secret from macOS Keychain (OSStatus {status})"
            )
        return password.decode("utf-8")

    def delete(self, key: str) -> None:
        status, item, _ = self._find_item(key)
        if status == self._ERR_SEC_ITEM_NOT_FOUND:
            return
        if status:
            self._release(item)
            raise SecretBackendError(
                f"Unable to find secret in macOS Keychain (OSStatus {status})"
            )
        try:
            status = self._security.SecKeychainItemDelete(item)
        finally:
            self._release(item)
        if status:
            raise SecretBackendError(
                f"Unable to delete secret from macOS Keychain (OSStatus {status})"
            )


class LinuxSecretServiceBackend:
    """Freedesktop Secret Service adapter using the standard secret-tool CLI."""

    provider_name = "linux-secret-service"

    def __init__(self, *, service: str = "ai2apps") -> None:
        executable = shutil.which("secret-tool")
        if executable is None:
            raise SecretBackendError("secret-tool is not installed")
        self.executable = executable
        self.service = service

    def _run(
        self, arguments: list[str], *, input_text: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.executable, *arguments], input=input_text,
            capture_output=True, text=True, check=False,
        )

    def store(self, key: str, value: str) -> None:
        result = self._run(
            ["store", "--label", "AI2Apps Secret", "service", self.service,
             "account", key],
            input_text=value + "\n",
        )
        if result.returncode:
            raise SecretBackendError("Unable to store secret using Secret Service")

    def load(self, key: str) -> str:
        result = self._run(
            ["lookup", "service", self.service, "account", key]
        )
        if result.returncode:
            raise KeyError("Secret value is unavailable in Secret Service")
        return result.stdout.rstrip("\n")

    def delete(self, key: str) -> None:
        result = self._run(
            ["clear", "service", self.service, "account", key]
        )
        if result.returncode:
            raise SecretBackendError("Unable to delete secret from Secret Service")


class EncryptedFileSecretBackend:
    """AES-GCM vault for headless systems such as NVIDIA DGX Spark.

    A deployment may inject ``AI2APPS_SECRET_VAULT_KEY``. When absent, a
    random machine-local key is generated with mode 0600. TPM/systemd/KMS
    integrations can provide the environment key without changing this class.
    """

    provider_name = "encrypted-file"
    _AAD = b"AI2Apps Secret Vault v1"

    def __init__(
        self,
        directory: str | Path,
        *,
        key_material: str | bytes | None = None,
    ) -> None:
        self.directory = Path(directory).expanduser().resolve()
        self.vault_path = self.directory / "vault.aesgcm"
        self.key_path = self.directory / "vault.key"
        self._provided_key = key_material
        self._lock = threading.RLock()

    @staticmethod
    def _normalize_key(value: str | bytes) -> bytes:
        raw = value.encode("utf-8") if isinstance(value, str) else value
        try:
            decoded = base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
            if len(decoded) == 32:
                return decoded
        except ValueError:
            pass
        return sha256(raw).digest()

    def _key(self) -> bytes:
        supplied = self._provided_key or os.environ.get("AI2APPS_SECRET_VAULT_KEY")
        if supplied:
            return self._normalize_key(supplied)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.key_path.exists():
            return base64.urlsafe_b64decode(self.key_path.read_bytes())
        key = AESGCM.generate_key(bit_length=256)
        descriptor = os.open(
            self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(base64.urlsafe_b64encode(key))
        return key

    def _read(self) -> dict[str, str]:
        if not self.vault_path.exists():
            return {}
        payload = self.vault_path.read_bytes()
        if len(payload) < 13 or payload[:1] != b"1":
            raise SecretBackendError("Secret vault has an unsupported format")
        try:
            plaintext = AESGCM(self._key()).decrypt(
                payload[1:13], payload[13:], self._AAD
            )
            values = json.loads(plaintext)
        except Exception as exc:
            raise SecretBackendError("Secret vault is locked or corrupted") from exc
        if not isinstance(values, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in values.items()
        ):
            raise SecretBackendError("Secret vault contains invalid data")
        return values

    def _write(self, values: dict[str, str]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        nonce = secrets.token_bytes(12)
        plaintext = json.dumps(
            values, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        payload = b"1" + nonce + AESGCM(self._key()).encrypt(
            nonce, plaintext, self._AAD
        )
        temporary = self.vault_path.with_suffix(".tmp")
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.vault_path)

    def store(self, key: str, value: str) -> None:
        with self._lock:
            values = self._read()
            values[key] = value
            self._write(values)

    def load(self, key: str) -> str:
        with self._lock:
            try:
                return self._read()[key]
            except KeyError as exc:
                raise KeyError("Secret value is unavailable in encrypted vault") from exc

    def delete(self, key: str) -> None:
        with self._lock:
            values = self._read()
            if key in values:
                del values[key]
                self._write(values)


class MemorySecretBackend:
    """Test backend; never selected by the production composition root."""

    provider_name = "memory"

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def store(self, key: str, value: str) -> None:
        self.values[key] = value

    def load(self, key: str) -> str:
        return self.values[key]

    def delete(self, key: str) -> None:
        self.values.pop(key, None)
