"""Pinned, fail-closed frpc subprocess supervision."""

from __future__ import annotations

import asyncio
import hashlib
import os
import platform
import random
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from ai2apps.secrets import SecretBackend

from .models import RemoteDeviceRecord

PINNED_FRP_VERSION = "0.62.1"
PINNED_FRP_CA_SHA256 = "2c460459daae289916e999a03baa3b4658fdfc0fb6a92243a002a601ad5017c0"
PINNED_FRP_BINARY_SHA256 = {
    "darwin-arm64": "49afde483f55927c3eeac9141cae82857cb2f15b9e9d55f4ac45378e761eabcc",
    "darwin-x86_64": "5ce5258b6ff1a232e9eb8e29247a55badb127e7fc66b5a58c299b442aba2bcb2",
}


def _bundled_binary() -> Path | None:
    system = platform.system().lower()
    machine = platform.machine().lower()
    platform_key = f"{system}-{machine}"
    expected_digest = PINNED_FRP_BINARY_SHA256.get(platform_key)
    if expected_digest is None:
        return None
    candidate = Path(__file__).with_name("bin") / platform_key / "frpc"
    if not candidate.is_file():
        return None
    actual_digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    return candidate if actual_digest == expected_digest else None


def _read_bootstrap_token(runtime_directory: Path) -> str:
    value = os.environ.get("AI2APPS_FRP_BOOTSTRAP_TOKEN", "").strip()
    if value:
        return value
    configured_file = os.environ.get("AI2APPS_FRP_BOOTSTRAP_TOKEN_FILE", "").strip()
    path = (
        Path(configured_file).expanduser().resolve()
        if configured_file
        else (runtime_directory / "bootstrap-token").resolve()
    )
    if not path.exists() and not configured_file:
        return ""
    if not path.is_file():
        raise ValueError("AI2APPS_FRP_BOOTSTRAP_TOKEN_FILE is not a file")
    if path.stat().st_mode & 0o077:
        raise ValueError("AI2Apps FRP bootstrap token file must not be group/world accessible")
    return path.read_text(encoding="utf-8").strip()


@dataclass(frozen=True, slots=True)
class RemoteFrpcConfig:
    binary: Path
    ca_file: Path
    bootstrap_token: str = field(repr=False)
    mobile_gateway_port: int
    runtime_directory: Path

    @classmethod
    def unavailable_reason(cls, runtime_directory: Path) -> str:
        runtime_directory = runtime_directory.resolve()
        configured_binary = os.environ.get("AI2APPS_FRP_BINARY", "").strip()
        runtime_binary = runtime_directory / "bin" / "frpc"
        binary = (
            Path(configured_binary).expanduser().resolve()
            if configured_binary
            else runtime_binary if runtime_binary.is_file() else _bundled_binary()
        )
        if binary is None or not binary.is_file():
            return f"FRP client {PINNED_FRP_VERSION} is not installed"
        try:
            if not _read_bootstrap_token(runtime_directory):
                return "FRP bootstrap credential is not installed"
        except ValueError as error:
            return str(error)
        return "FRP runtime configuration is not installed"

    @classmethod
    def from_environment(cls, runtime_directory: Path) -> RemoteFrpcConfig | None:
        runtime_directory = runtime_directory.resolve()
        configured_binary = os.environ.get("AI2APPS_FRP_BINARY", "").strip()
        runtime_binary = runtime_directory / "bin" / "frpc"
        binary_path = (
            Path(configured_binary).expanduser().resolve()
            if configured_binary
            else runtime_binary if runtime_binary.is_file() else _bundled_binary()
        )
        configured_ca = os.environ.get("AI2APPS_FRP_CA_FILE", "").strip()
        ca_path = (
            Path(configured_ca).expanduser().resolve()
            if configured_ca
            else Path(__file__).with_name("frp-ca-2026.pem").resolve()
        )
        bootstrap = _read_bootstrap_token(runtime_directory)
        if binary_path is None or not bootstrap:
            return None
        port = int(os.environ.get("AI2APPS_MOBILE_GATEWAY_PORT", "8000"))
        if not 1 <= port <= 65535:
            raise ValueError("AI2APPS_MOBILE_GATEWAY_PORT is invalid")
        if not binary_path.is_file() or not os.access(binary_path, os.X_OK):
            raise ValueError("AI2APPS_FRP_BINARY is not an executable file")
        if not ca_path.is_file():
            raise ValueError("AI2APPS_FRP_CA_FILE is not a file")
        if hashlib.sha256(ca_path.read_bytes()).hexdigest() != PINNED_FRP_CA_SHA256:
            raise ValueError("AI2Apps Remote Access CA fingerprint does not match the pinned release")
        return cls(binary_path, ca_path, bootstrap, port, runtime_directory)


class RemoteFrpcSupervisor:
    def __init__(
        self,
        config: RemoteFrpcConfig | None,
        secret_backend: SecretBackend,
        *,
        unavailable_reason: str | None = None,
    ) -> None:
        self.config = config
        self.secret_backend = secret_backend
        self._task: asyncio.Task[None] | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._device: RemoteDeviceRecord | None = None
        self._stop = asyncio.Event()
        self.last_error = "" if config else (
            unavailable_reason or "FRP runtime configuration is not installed"
        )

    @property
    def available(self) -> bool:
        return self.config is not None

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    def status(self) -> dict:
        return {"available": self.available, "running": self.running,
                "deviceId": None if self._device is None else self._device.device_id,
                "lastError": self.last_error}

    async def start(self, device: RemoteDeviceRecord) -> None:
        if self.config is None:
            raise RuntimeError(self.last_error)
        if device.status != "active":
            raise RuntimeError("Remote device is not active")
        await self.stop()
        await self._verify_version()
        self._device = device
        self._stop = asyncio.Event()
        self._task = asyncio.create_task(self._supervise(), name="ai2apps-frpc")

    async def _verify_version(self) -> None:
        assert self.config is not None
        process = await asyncio.create_subprocess_exec(
            str(self.config.binary), "--version", stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output, _ = await asyncio.wait_for(process.communicate(), timeout=5)
        if process.returncode != 0 or PINNED_FRP_VERSION not in output.decode(errors="replace"):
            raise RuntimeError(f"Remote Access requires frpc {PINNED_FRP_VERSION}")

    async def _supervise(self) -> None:
        assert self.config is not None and self._device is not None
        template = Path(__file__).with_name("frpc-device.toml")
        self.config.runtime_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        runtime_template = self.config.runtime_directory / "frpc-device.toml"
        if not runtime_template.exists() or runtime_template.read_bytes() != template.read_bytes():
            runtime_template.write_bytes(template.read_bytes())
            runtime_template.chmod(0o600)
        delay = 1.0
        while not self._stop.is_set():
            try:
                secret = self.secret_backend.load(self._device.secret_backend_key)
                slug = self._device.subdomain.removeprefix("device-")
                environment = {
                    **os.environ,
                    "AI2APPS_FRP_SERVER_ADDR": self._device.server_addr,
                    "AI2APPS_FRP_SERVER_PORT": str(self._device.server_port),
                    "AI2APPS_FRP_CA_FILE": str(self.config.ca_file),
                    "AI2APPS_FRP_BOOTSTRAP_TOKEN": self.config.bootstrap_token,
                    "AI2APPS_REMOTE_DEVICE_ID": self._device.device_id,
                    "AI2APPS_REMOTE_CREDENTIAL_VERSION": str(self._device.credential_version),
                    "AI2APPS_REMOTE_CONNECTOR_SECRET": secret,
                    "AI2APPS_REMOTE_PUBLIC_SLUG": slug,
                    "AI2APPS_MOBILE_GATEWAY_PORT": str(self.config.mobile_gateway_port),
                }
                self._process = await asyncio.create_subprocess_exec(
                    str(self.config.binary), "-c", str(runtime_template), env=environment,
                    stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                code = await self._process.wait()
                self._process = None
                if self._stop.is_set():
                    break
                self.last_error = f"frpc exited with status {code}"
            except Exception as error:
                self._process = None
                self.last_error = str(error)
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=delay * random.uniform(0.8, 1.2))
            delay = min(60.0, delay * 2)

    async def stop(self) -> None:
        self._stop.set()
        process = self._process
        if process is not None and process.returncode is None:
            process.terminate()
            with suppress(TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=5)
            if process.returncode is None:
                process.kill()
                await process.wait()
        if self._task is not None:
            with suppress(asyncio.CancelledError):
                await self._task
        self._task = None
        self._process = None
