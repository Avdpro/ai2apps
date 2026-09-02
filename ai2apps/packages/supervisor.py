"""Managed-process Service sandbox, health gate, logs, and restart supervision."""

from __future__ import annotations

import asyncio
import functools
import json
import os
import platform
import resource
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from ai2apps.checkpoint_paths import checkpoint_distribution_cache_key
from ai2apps.checkpoints import checkpoint_is_complete
from ai2apps.core import EntityIdKind, new_entity_id, utc_now_text
from ai2apps.services import ServiceInstanceStatus, ServiceRepository

from .inference_runtime import InferenceRuntimeResolver, ResolvedInferenceRuntime
from .models import InstalledPackageRecord, PackageError
from .repository import PackageRepository


@dataclass(slots=True)
class _Managed:
    package: InstalledPackageRecord
    process_id: str
    process: asyncio.subprocess.Process
    endpoint: str
    desired: bool
    restart_count: int
    tasks: tuple[asyncio.Task[None], ...]
    internal_token: str | None = None
    proxy_server: asyncio.AbstractServer | None = None
    unix_socket: Path | None = None
    started_monotonic: float = 0.0


class ManagedServiceSupervisor:
    def __init__(
        self,
        packages: PackageRepository,
        services: ServiceRepository,
        packages_root: Path,
        *,
        inference_runtimes: InferenceRuntimeResolver | None = None,
        model_root: Path | None = None,
    ) -> None:
        self.packages = packages
        self.services = services
        self.packages_root = packages_root
        self.model_root = model_root
        self.inference_runtimes = inference_runtimes
        self._live: dict[str, _Managed] = {}
        self._generations: dict[str, int] = {}
        self._draining: set[str] = set()
        self._evicted: dict[str, str] = {}
        self._stopping = False

    @staticmethod
    def _port() -> int:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            return int(listener.getsockname()[1])

    def internal_headers(self, service_key: str) -> dict[str, str] | None:
        """Return ephemeral Host-to-Worker authentication headers."""
        managed = self._live.get(service_key)
        if managed is None or managed.internal_token is None:
            return None
        return {"Authorization": f"Bearer {managed.internal_token}"}

    @staticmethod
    def _worker_json_request(
        endpoint: str,
        path: str,
        token: str,
        *,
        method: str = "GET",
    ) -> dict[str, Any]:
        request = urllib.request.Request(
            endpoint.rstrip("/") + "/" + path.lstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            method=method,
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            content = response.read(256 * 1024)
        value = json.loads(content or b"{}")
        if not isinstance(value, dict):
            raise ValueError("Model Worker returned a non-object status")
        return value

    async def worker_snapshot(
        self, package: InstalledPackageRecord, *, probe: bool = True
    ) -> dict[str, Any]:
        """Return the Host-authoritative state of one Model Worker package."""

        service_key = package.service_key
        managed = self._live.get(service_key)
        generation = self._generations.get(service_key, 0)
        models = [
            {
                "id": model.get("id"),
                "displayName": model.get("display_name", model.get("id")),
                "capabilities": list(model.get("capabilities", [])),
            }
            for model in package.manifest.get("models", [])
            if isinstance(model, dict)
        ]
        snapshot: dict[str, Any] = {
            "serviceKey": service_key,
            "packageVersion": package.package_version,
            "packageDigest": package.package_digest,
            "generation": generation,
            "state": "stopped",
            "acceptingRequests": False,
            "activeRequests": 0,
            "queuedRequests": 0,
            "pid": None,
            "residentMemoryBytes": 0,
            "endpoint": None,
            "models": models,
            "lastError": None,
            "startedAgeSeconds": None,
            "evictionReason": self._evicted.get(service_key),
        }
        if managed is None:
            if service_key in self._evicted:
                snapshot["state"] = "evicted"
            return snapshot
        snapshot["pid"] = managed.process.pid
        snapshot["endpoint"] = managed.endpoint
        snapshot["startedAgeSeconds"] = max(
            0.0, time.monotonic() - managed.started_monotonic
        )
        if managed.process.returncode is not None:
            snapshot["state"] = "failed" if managed.desired else "stopped"
            return snapshot
        snapshot["state"] = "draining" if service_key in self._draining else "ready"
        snapshot["acceptingRequests"] = service_key not in self._draining
        with suppress(psutil.Error, ProcessLookupError):
            snapshot["residentMemoryBytes"] = psutil.Process(
                managed.process.pid
            ).memory_info().rss
        if not probe or managed.internal_token is None:
            snapshot["activeRequests"] = None
            snapshot["queuedRequests"] = None
            return snapshot
        try:
            status = await asyncio.to_thread(
                self._worker_json_request,
                managed.endpoint,
                "/v1/status",
                managed.internal_token,
            )
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
            snapshot["state"] = (
                "draining" if service_key in self._draining else "starting"
            )
            snapshot["acceptingRequests"] = False
            snapshot["activeRequests"] = None
            snapshot["queuedRequests"] = None
            snapshot["lastError"] = str(error)
            return snapshot
        snapshot["activeRequests"] = int(status.get("active_requests", 0))
        snapshot["queuedRequests"] = int(status.get("queued_requests", 0))
        snapshot["acceptingRequests"] = bool(status.get("accepting_requests", True))
        if service_key in self._draining or not snapshot["acceptingRequests"]:
            snapshot["state"] = "draining"
        elif snapshot["activeRequests"] or snapshot["queuedRequests"]:
            snapshot["state"] = "busy"
        return snapshot

    def assert_worker_generation(self, service_key: str, expected: int | None) -> None:
        if expected is None:
            return
        current = self._generations.get(service_key, 0)
        if expected != current:
            raise PackageError(
                "worker_generation_conflict",
                "Model Worker state changed; refresh the Dashboard and retry",
                details={"expectedGeneration": expected, "currentGeneration": current},
            )

    async def drain_worker(self, service_key: str) -> None:
        managed = self._live.get(service_key)
        if managed is None:
            return
        if managed.internal_token is None:
            raise PackageError("not_model_worker", "Service is not a Model Worker")
        await asyncio.to_thread(
            self._worker_json_request,
            managed.endpoint,
            "/v1/control/drain",
            managed.internal_token,
            method="POST",
        )
        self._draining.add(service_key)

    async def resume_worker(self, service_key: str) -> None:
        managed = self._live.get(service_key)
        if managed is None:
            self._draining.discard(service_key)
            return
        if managed.internal_token is None:
            raise PackageError("not_model_worker", "Service is not a Model Worker")
        await asyncio.to_thread(
            self._worker_json_request,
            managed.endpoint,
            "/v1/control/resume",
            managed.internal_token,
            method="POST",
        )
        self._draining.discard(service_key)

    async def wait_worker_idle(self, package: InstalledPackageRecord) -> None:
        while package.service_key in self._live:
            snapshot = await self.worker_snapshot(package)
            active = snapshot["activeRequests"]
            queued = snapshot["queuedRequests"]
            if active is None or queued is None:
                await asyncio.sleep(0.25)
                continue
            if active == 0 and queued == 0:
                return
            await asyncio.sleep(0.25)

    @staticmethod
    def _trusted_framework_site_packages() -> Path | None:
        configured = os.environ.get("AI2APPS_TRUSTED_FRAMEWORK_SITE_PACKAGES")
        if not configured:
            return None
        try:
            candidate = Path(configured).expanduser().resolve(strict=True)
        except OSError as error:
            raise PackageError(
                "invalid_runtime_layer",
                "AI2Apps trusted framework site-packages does not exist",
            ) from error
        if not candidate.is_dir():
            raise PackageError(
                "invalid_runtime_layer",
                "AI2Apps trusted framework site-packages is not a directory",
            )
        host_import_roots = {
            Path(value).expanduser().resolve()
            for value in sys.path
            if isinstance(value, str) and value
        }
        if candidate not in host_import_roots:
            raise PackageError(
                "invalid_runtime_layer",
                "AI2Apps trusted framework site-packages is not a Host import root",
            )
        return candidate

    @staticmethod
    def _model_worker_command(
        package_root: Path,
        data_root: Path,
        manifest: dict[str, Any],
        port: int,
        checkpoints: tuple[dict[str, Any], ...] = (),
        inference_runtime: ResolvedInferenceRuntime | None = None,
    ) -> tuple[tuple[str, ...], str]:
        runtime = manifest["runtime"]
        adapter = str(runtime["adapter"])
        adapter_path, separator, factory = adapter.partition(":")
        if not separator or not factory:
            raise PackageError("invalid_model_worker", "Model Worker adapter is invalid")
        candidate = (package_root / adapter_path).resolve()
        try:
            candidate.relative_to(package_root)
        except ValueError as error:
            raise PackageError(
                "invalid_model_worker", "Model Worker adapter escapes the Package"
            ) from error
        if not candidate.is_file():
            raise PackageError(
                "missing_model_adapter", f"Model Worker adapter does not exist: {adapter_path}"
            )
        config_path = data_root / "model-worker.json"
        config = {
            "protocol": "ai2apps-model-worker/v1",
            "service_id": manifest["id"],
            "package_root": str(package_root),
            "data_root": str(data_root),
            "adapter_path": str(candidate),
            "adapter_factory": factory,
            "models": manifest.get("models", []),
            "checkpoints": list(checkpoints),
        }
        config_path.write_text(json.dumps(config, sort_keys=True), encoding="utf-8")
        config_path.chmod(0o600)
        launcher = (
            inference_runtime.launcher
            if inference_runtime is not None
            else Path(__file__).resolve().parents[1] / "model_worker" / "launcher.py"
        )
        python = (
            inference_runtime.python
            if inference_runtime is not None
            else Path(sys.executable).absolute()
        )
        return (
            (
                str(python),
                "-I",
                str(launcher),
                "--config",
                str(config_path),
                "--port",
                str(port),
            ),
            str(config_path),
        )

    @staticmethod
    def _huggingface_hub_cache() -> Path:
        if configured := os.environ.get("HF_HUB_CACHE"):
            return Path(configured).expanduser().resolve()
        if configured := os.environ.get("HF_HOME"):
            return (Path(configured).expanduser() / "hub").resolve()
        return (Path.home() / ".cache" / "huggingface" / "hub").resolve()

    @staticmethod
    def _model_worker_checkpoints(
        manifest: dict[str, Any],
        hub_cache: Path,
        model_root: Path | None = None,
    ) -> tuple[tuple[dict[str, Any], ...], tuple[Path, ...]]:
        checkpoints: list[dict[str, Any]] = []
        roots: list[Path] = []
        for model in manifest.get("models", []):
            weights = model.get("weights") if isinstance(model, dict) else None
            if not isinstance(weights, dict):
                continue
            repo_id = str(weights["repo_id"])
            revision = str(weights["revision"])
            repo_root = (hub_cache / ("models--" + repo_id.replace("/", "--"))).resolve()
            try:
                repo_root.relative_to(hub_cache)
            except ValueError as exc:
                raise PackageError(
                    "invalid_model_weights", "Model weight repository escapes the cache"
                ) from exc
            distribution_id = weights.get("distribution_id")
            preparation = weights.get("preparation", {})
            if distribution_id is not None:
                if not isinstance(distribution_id, str):
                    raise PackageError(
                        "invalid_model_weights", "Model distribution ID is invalid"
                    )
                try:
                    cache_key = checkpoint_distribution_cache_key(distribution_id)
                except ValueError as exc:
                    raise PackageError(
                        "invalid_model_weights", "Model distribution ID is invalid"
                    ) from exc
                snapshot = repo_root / "distributions" / cache_key
            else:
                snapshot = repo_root / "snapshots" / revision
            snapshot_path = (
                snapshot.resolve()
                if snapshot.is_dir()
                and ManagedServiceSupervisor._checkpoint_is_complete(snapshot)
                else None
            )
            if (
                model_root is not None
                and isinstance(preparation, dict)
                and preparation.get("recipe", "native") != "native"
            ):
                prepared = (model_root / repo_id).resolve()
                try:
                    prepared.relative_to(model_root.resolve())
                except ValueError as exc:
                    raise PackageError(
                        "invalid_model_weights",
                        "Prepared model path escapes the model directory",
                    ) from exc
                if (
                    (prepared / "ai2apps-model.json").is_file()
                    and ManagedServiceSupervisor._checkpoint_is_complete(prepared)
                ):
                    snapshot_path = prepared
                    roots.append(model_root.resolve())
                    # Prepared checkpoint files can be no-copy symlinks into
                    # the pinned Hub snapshot, so grant the Worker read-only
                    # access to that repository as well.
                    if repo_root.is_dir():
                        roots.append(repo_root)
            if snapshot_path is not None:
                if model_root is None or not snapshot_path.is_relative_to(
                    model_root.resolve()
                ):
                    try:
                        snapshot_path.relative_to(repo_root)
                    except ValueError as exc:
                        raise PackageError(
                            "invalid_model_weights",
                            "Model snapshot escapes its repository cache",
                        ) from exc
                    roots.append(repo_root)
            checkpoints.append(
                {
                    "model_id": model["id"],
                    "upstream_id": model["upstream_id"],
                    "provider": weights["provider"],
                    "repo_id": repo_id,
                    "revision": revision,
                    "distribution_id": distribution_id,
                    "path": str(snapshot_path) if snapshot_path is not None else None,
                    "preparation": preparation,
                }
            )
        return tuple(checkpoints), tuple(dict.fromkeys(roots))

    @staticmethod
    def _checkpoint_is_complete(snapshot: Path) -> bool:
        """Require a complete supported checkpoint before granting it to a Worker."""

        return checkpoint_is_complete(snapshot)

    def _sandbox_command(
        self,
        command: tuple[str, ...],
        package_root: Path,
        data_root: Path,
        temporary: Path,
        *,
        network: bool,
        read_only_roots: tuple[Path, ...] = (),
        metal: bool = False,
        cuda: bool = False,
        host_loopback_transport: bool = False,
        port: int | None = None,
        unix_socket: Path | None = None,
    ) -> tuple[str, ...]:
        system = platform.system()
        if system == "Darwin":
            executable = Path("/usr/bin/sandbox-exec")
            if not executable.is_file():
                raise PackageError(
                    "sandbox_unavailable", "macOS sandbox-exec is unavailable"
                )
            profile = data_root / "service.sb"
            lines = [
                "(version 1)",
                "(deny default)",
                '(import "system.sb")',
                "(allow process*)",
                "(allow sysctl-read)",
                f"(allow file-read* (subpath {json.dumps(str(package_root))}))",
                f"(allow file-read* (subpath {json.dumps(str(data_root))}))",
                f"(allow file-read* (subpath {json.dumps(str(temporary))}))",
                f"(allow file-write* (subpath {json.dumps(str(data_root))}))",
                f"(allow file-write* (subpath {json.dumps(str(temporary))}))",
            ]
            if Path("/Applications/Xcode.app").exists():
                lines.append('(allow file-read* (subpath "/Applications/Xcode.app"))')
            python_roots = {
                Path(sys.prefix).resolve(),
                Path(sys.executable).resolve().parent.parent,
            }
            for python_root in python_roots:
                if not python_root.exists():
                    continue
                lines.append(
                    f"(allow file-read* (subpath {json.dumps(str(python_root))}))"
                )
            for read_root in read_only_roots:
                if read_root.exists():
                    lines.append(
                        f"(allow file-read* (subpath {json.dumps(str(read_root))}))"
                    )
            if metal:
                # Minimal rules used by Apple's own Metal GPU task sandbox.
                # Keep this opt-in because IOKit access is inappropriate for
                # ordinary tool Services.
                lines.extend(
                    (
                        "(allow iokit-open",
                        '  (iokit-user-client-class "IOSurfaceRootUserClient")',
                        '  (iokit-user-client-class "IOGPUDeviceUserClient")',
                        '  (iokit-user-client-class "IOAccelDevice2")',
                        '  (iokit-user-client-class "IOAccelSharedUserClient2")',
                        '  (iokit-user-client-class "IOAccelCommandQueue"))',
                        "(allow mach-lookup",
                        '  (global-name "com.apple.MTLCompilerService")',
                        '  (global-name "com.apple.gpumemd.source")',
                        '  (global-name "com.apple.CoreServices.coreservicesd")',
                        '  (global-name "com.apple.DiskArbitration.diskarbitrationd"))',
                        "(allow user-preference-read",
                        '  (preference-domain "kCFPreferencesAnyApplication"))',
                    )
                )
            if network:
                lines.append("(allow network*)")
            else:
                lines.extend(
                    (
                        "(deny network*)",
                        '(allow network-bind (local ip "localhost:*"))',
                        '(allow network-inbound (local ip "localhost:*"))',
                    )
                )
            profile.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return (str(executable), "-f", str(profile), "--", *command)
        if system == "Linux":
            docker = shutil.which("docker")
            if cuda and docker is not None and host_loopback_transport:
                if port is None:
                    raise PackageError(
                        "sandbox_configuration_invalid",
                        "Docker Model Worker sandbox requires a Host proxy port",
                    )
                if unix_socket is None:
                    raise PackageError(
                        "sandbox_configuration_invalid",
                        "Docker Model Worker sandbox requires a Unix socket",
                    )
                return self._docker_sandbox_command(
                    docker,
                    command,
                    package_root,
                    data_root,
                    temporary,
                    network=network,
                    read_only_roots=read_only_roots,
                    unix_socket=unix_socket,
                )
            bwrap = shutil.which("bwrap")
            if bwrap is None:
                raise PackageError(
                    "sandbox_unavailable", "Managed Services require bubblewrap"
                )
            value = [
                bwrap,
                "--die-with-parent",
                "--new-session",
                "--unshare-user",
                "--unshare-pid",
                "--unshare-ipc",
                "--unshare-uts",
            ]
            # Model Worker v1 currently exposes a random loopback HTTP port to
            # its Host supervisor. A private network namespace would make that
            # endpoint unreachable even when bubblewrap can configure its own
            # loopback device. Keep the host namespace only for this trusted
            # transport; ordinary no-network Services remain fully unshared.
            if not network and not host_loopback_transport:
                value.append("--unshare-net")
            for root in ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc"):
                if Path(root).exists():
                    value.extend(("--ro-bind", root, root))
            python_roots = {
                Path(sys.prefix).resolve(),
                Path(sys.executable).resolve().parent.parent,
            }
            for python_path in python_roots:
                python_root = str(python_path)
                if python_path.exists() and not any(
                    python_root == root or python_root.startswith(root + "/")
                    for root in ("/usr", "/bin", "/sbin", "/lib", "/lib64")
                ):
                    value.extend(("--ro-bind", python_root, python_root))
            for read_path in read_only_roots:
                read_root = str(read_path)
                if read_path.exists() and not any(
                    read_root == root or read_root.startswith(root + "/")
                    for root in ("/usr", "/bin", "/sbin", "/lib", "/lib64")
                ):
                    value.extend(("--ro-bind", read_root, read_root))
            value.extend(("--dev", "/dev"))
            if cuda:
                cuda_devices = tuple(
                    path
                    for path in (
                        *sorted(Path("/dev").glob("nvidia*")),
                        Path("/dev/dri"),
                    )
                    if path.exists()
                )
                if not cuda_devices:
                    raise PackageError(
                        "accelerator_unavailable",
                        "CUDA access was requested but no NVIDIA device is available",
                    )
                for device in cuda_devices:
                    value.extend(("--dev-bind", str(device), str(device)))
            value.extend(
                (
                    "--proc",
                    "/proc",
                    "--tmpfs",
                    "/tmp",
                    "--ro-bind",
                    str(package_root),
                    str(package_root),
                    "--bind",
                    str(data_root),
                    str(data_root),
                    "--bind",
                    str(temporary),
                    str(temporary),
                    "--chdir",
                    str(package_root),
                    "--",
                    *command,
                )
            )
            return tuple(value)
        raise PackageError(
            "sandbox_unavailable", f"No managed Service sandbox for {system}"
        )

    @staticmethod
    def _docker_sandbox_command(
        docker: str,
        command: tuple[str, ...],
        package_root: Path,
        data_root: Path,
        temporary: Path,
        *,
        network: bool,
        read_only_roots: tuple[Path, ...],
        unix_socket: Path,
    ) -> tuple[str, ...]:
        image = os.environ.get("AI2APPS_CUDA_WORKER_IMAGE", "ubuntu:24.04")
        inspected = subprocess.run(
            (docker, "image", "inspect", image),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if inspected.returncode:
            raise PackageError(
                "sandbox_image_unavailable",
                f"CUDA Worker sandbox image is not installed: {image}",
            )
        value = [
            docker,
            "run",
            "--rm",
            "--init",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "1024",
            "--ipc",
            "private",
            "--shm-size",
            "1g",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--network",
            "bridge" if network else "none",
            "--gpus",
            "all",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,noexec,size=1g",
        ]
        for name in (
            "PATH",
            "HOME",
            "TMPDIR",
            "PYTHONHOME",
            "PYTHONPATH",
            "LD_LIBRARY_PATH",
            "AI2APPS_SERVICE_ID",
            "AI2APPS_SERVICE_PORT",
            "AI2APPS_PACKAGE_ROOT",
            "AI2APPS_DATA_ROOT",
            "AI2APPS_MODEL_WORKER_TOKEN",
            "AI2APPS_TRUSTED_FRAMEWORK_SITE_PACKAGES",
            "AI2APPS_INFERENCE_RUNTIME",
            "AI2APPS_HF_CACHE_ROOT",
        ):
            value.extend(("--env", name))
        roots = tuple(
            dict.fromkeys(
                (
                    package_root,
                    *read_only_roots,
                    Path("/usr/local/cuda"),
                    Path(f"/lib/{platform.machine().lower()}-linux-gnu"),
                    Path(f"/usr/lib/{platform.machine().lower()}-linux-gnu"),
                )
            )
        )
        for root in roots:
            if root.exists():
                value.extend(
                    (
                        "--mount",
                        f"type=bind,src={root},dst={root},readonly",
                    )
                )
        for root in dict.fromkeys((data_root, temporary, unix_socket.parent)):
            value.extend(("--mount", f"type=bind,src={root},dst={root}"))
        container_command = list(command)
        try:
            port_index = container_command.index("--port")
            del container_command[port_index : port_index + 2]
        except ValueError as error:
            raise PackageError(
                "sandbox_configuration_invalid",
                "Docker Model Worker command does not declare a port",
            ) from error
        container_command.extend(("--uds", str(unix_socket)))
        value.extend(("--workdir", str(package_root), image, *container_command))
        return tuple(value)

    @staticmethod
    async def _proxy_unix_connection(
        unix_socket: Path,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            unix_reader, unix_writer = await asyncio.open_unix_connection(unix_socket)
        except OSError:
            writer.close()
            await writer.wait_closed()
            return

        async def relay(source: asyncio.StreamReader, target: asyncio.StreamWriter):
            try:
                while data := await source.read(64 * 1024):
                    target.write(data)
                    await target.drain()
            except (ConnectionError, OSError):
                pass
            finally:
                target.close()

        await asyncio.gather(
            relay(reader, unix_writer),
            relay(unix_reader, writer),
        )
        await asyncio.gather(
            writer.wait_closed(), unix_writer.wait_closed(), return_exceptions=True
        )

    @staticmethod
    def _limit_resources(*, model_worker: bool = False) -> None:
        with suppress(OSError, ValueError):
            resource.setrlimit(resource.RLIMIT_CPU, (3600, 3600))
        with suppress(OSError, ValueError):
            # mlx_lm raises its soft limit to 2048 during import and expects a
            # 4096 hard ceiling. Keep the Service bounded while allowing model
            # providers with sharded checkpoints to initialize.
            resource.setrlimit(resource.RLIMIT_NOFILE, (4096, 4096))
        if platform.system() != "Darwin" and not model_worker:
            with suppress(OSError, ValueError):
                resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))

    async def start(self, package: InstalledPackageRecord) -> str:
        service_key = package.service_key
        existing = self._live.get(service_key)
        if existing is not None and existing.process.returncode is None:
            return existing.endpoint
        self._generations[service_key] = self._generations.get(service_key, 0) + 1
        self._draining.discard(service_key)
        self._evicted.pop(service_key, None)
        manifest = package.manifest
        runtime = manifest["runtime"]
        command = runtime.get("command", [])
        is_model_worker = package.protocol == "ai2apps-model-worker/v1"
        runtime_provider = manifest.get("runtime", {}).get("provider")
        resolved_runtime = None
        if runtime_provider is not None:
            if self.inference_runtimes is None:
                raise PackageError(
                    "runtime_resolver_unavailable",
                    "Inference Runtime Resolver is unavailable",
                )
            resolved_runtime = self.inference_runtimes.resolve(package)
            framework_site = resolved_runtime.framework_site_packages
        else:
            framework_site = (
                self._trusted_framework_site_packages() if is_model_worker else None
            )
        if (not isinstance(command, list) or not command) and not is_model_worker:
            raise PackageError(
                "missing_entrypoint", "Managed Service command is missing"
            )
        package_root = Path(package.store_path).resolve(strict=True)
        service_root = self.packages_root / "runtime" / service_key
        data_root = service_root / "data"
        temporary = service_root / "temporary"
        data_root.mkdir(parents=True, exist_ok=True)
        temporary.mkdir(parents=True, exist_ok=True)
        port = self._port()
        internal_token = secrets.token_urlsafe(32) if is_model_worker else None
        replacements = {
            "{port}": str(port),
            "{package}": str(package_root),
            "{data}": str(data_root),
            "{temporary}": str(temporary),
            # Preserve the virtual-environment entrypoint. Resolving this
            # symlink selects the base interpreter and silently drops the
            # venv's site-packages for every Python Service Package.
            "{python}": str(Path(sys.executable).absolute()),
            "{runtime_python}": (
                str(resolved_runtime.python)
                if resolved_runtime is not None
                else str(Path(sys.executable).absolute())
            ),
            "{variant}": str(
                package.verification.get("signature", {}).get("selected_variant") or ""
            ),
        }
        replacements["{variant_root}"] = str(
            package_root / "variants" / (replacements["{variant}"] or "portable")
        )
        hf_hub_cache = self._huggingface_hub_cache()
        worker_checkpoints: tuple[dict[str, Any], ...] = ()
        worker_weight_roots: tuple[Path, ...] = ()
        has_checkpoint_models = any(
            isinstance(model, dict) and isinstance(model.get("weights"), dict)
            for model in manifest.get("models", [])
        )
        if is_model_worker or has_checkpoint_models:
            declared_weight_permission = manifest.get("permissions", {}).get(
                "model_weights", {}
            )
            if has_checkpoint_models and not (
                isinstance(declared_weight_permission, dict)
                and declared_weight_permission.get("huggingface_cache") == "read"
            ):
                raise PackageError(
                    "missing_model_weight_permission",
                    "Declared Hugging Face weights require model_weights.huggingface_cache: read",
                )
            worker_checkpoints, worker_weight_roots = self._model_worker_checkpoints(
                manifest, hf_hub_cache, self.model_root
            )
        expanded: list[str]
        if is_model_worker:
            worker_command, _ = self._model_worker_command(
                package_root,
                data_root,
                manifest,
                port,
                worker_checkpoints,
                resolved_runtime,
            )
            expanded = list(worker_command)
        else:
            expanded = []
            for argument in command:
                value = argument
                for marker, replacement in replacements.items():
                    value = value.replace(marker, replacement)
                expanded.append(value)
        executable = Path(expanded[0])
        if "/" not in expanded[0]:
            resolved = shutil.which(
                expanded[0],
                path="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin",
            )
            if resolved is None:
                raise PackageError(
                    "executable_not_found",
                    f"Service executable not found: {expanded[0]}",
                )
            expanded[0] = resolved
        elif not executable.is_absolute():
            candidate = (package_root / executable).resolve()
            try:
                candidate.relative_to(package_root)
            except ValueError as error:
                raise PackageError(
                    "executable_denied", "Service executable escapes package"
                ) from error
            expanded[0] = str(candidate)
        endpoint = str(runtime.get("endpoint") or f"http://127.0.0.1:{port}").replace(
            "{port}", str(port)
        )
        from .archive import _validate_external_endpoint

        _validate_external_endpoint(endpoint)
        permissions = manifest.get("permissions", {})
        network = bool(permissions.get("network", {}).get("outbound", False))
        model_weights = permissions.get("model_weights", {})
        allow_hf_cache = bool(
            isinstance(model_weights, dict)
            and model_weights.get("huggingface_cache") == "read"
        )
        read_only_roots: list[Path] = []
        if framework_site is not None:
            read_only_roots.append(framework_site)
        if resolved_runtime is not None:
            read_only_roots.append(resolved_runtime.root)
        hf_cache_root: Path | None = None
        if allow_hf_cache:
            if has_checkpoint_models:
                read_only_roots.extend(worker_weight_roots)
            else:
                hf_cache_root = hf_hub_cache
                if hf_cache_root.exists():
                    read_only_roots.append(hf_cache_root)
        accelerator = permissions.get("accelerator", {})
        allow_metal = bool(
            isinstance(accelerator, dict) and accelerator.get("metal") is True
        )
        allow_cuda = bool(
            isinstance(accelerator, dict) and accelerator.get("cuda") is True
        )
        docker_socket = (
            Path(
                os.environ.get(
                    "XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"
                )
            )
            / "ai2apps-workers"
            / f"worker-{port}.sock"
            if platform.system() == "Linux"
            and is_model_worker
            and allow_cuda
            and shutil.which("docker") is not None
            else None
        )
        if docker_socket is not None:
            docker_socket.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            docker_socket.parent.chmod(0o700)
            docker_socket.unlink(missing_ok=True)

        # Editable development installs keep ai2apps/omlx outside sys.prefix.
        # Installed wheels resolve this path inside site-packages, where it is
        # already covered by the Python roots above.
        platform_source_root = Path(__file__).resolve().parents[2]
        if platform_source_root.exists():
            read_only_roots.append(platform_source_root)
        sandboxed = self._sandbox_command(
            tuple(expanded),
            package_root,
            data_root,
            temporary,
            network=network,
            read_only_roots=tuple(dict.fromkeys(read_only_roots)),
            metal=allow_metal,
            cuda=allow_cuda,
            host_loopback_transport=is_model_worker,
            port=port,
            unix_socket=docker_socket,
        )
        environment = {
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin",
            "HOME": str(data_root),
            "TMPDIR": str(temporary),
            "AI2APPS_SERVICE_ID": service_key,
            "AI2APPS_SERVICE_PORT": str(port),
            "AI2APPS_PACKAGE_ROOT": str(package_root),
            "AI2APPS_DATA_ROOT": str(data_root),
        }
        if internal_token is not None:
            environment["AI2APPS_MODEL_WORKER_TOKEN"] = internal_token
        if framework_site is not None:
            environment["AI2APPS_TRUSTED_FRAMEWORK_SITE_PACKAGES"] = str(
                framework_site
            )
        if resolved_runtime is not None:
            environment["PYTHONHOME"] = str(resolved_runtime.python_home)
            environment["AI2APPS_INFERENCE_RUNTIME"] = str(resolved_runtime.root)
            if not is_model_worker:
                # Generic native Runtime workers execute their Package-owned
                # command directly, so no trusted launcher is present to add
                # the immutable framework layer to sys.path. Model Worker v1
                # performs this bootstrap inside its Host-owned launcher.
                environment["PYTHONPATH"] = str(
                    resolved_runtime.framework_site_packages
                )
        if allow_cuda and Path("/usr/local/cuda").is_dir():
            environment["LD_LIBRARY_PATH"] = (
                "/usr/local/cuda/targets/sbsa-linux/lib:/usr/local/cuda/lib64"
            )
        if hf_cache_root is not None:
            environment["AI2APPS_HF_CACHE_ROOT"] = str(hf_cache_root)
        if worker_checkpoints and not is_model_worker:
            # Generic HTTP model providers receive only Host-resolved,
            # immutable checkpoint paths. They cannot select arbitrary cache
            # content and the corresponding repository roots are read-only in
            # the process sandbox.
            environment["AI2APPS_MODEL_CHECKPOINTS_JSON"] = json.dumps(
                worker_checkpoints, separators=(",", ":"), sort_keys=True
            )
        process_id = new_entity_id(EntityIdKind.MANAGED_SERVICE_PROCESS)
        now = utc_now_text()
        with self.packages.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO managed_service_processes(
                    id, service_key, package_digest, status, endpoint, created_at, updated_at
                ) VALUES (?, ?, ?, 'starting', ?, ?, ?)""",
                (process_id, service_key, package.package_digest, endpoint, now, now),
            )
        proxy_server = None
        if docker_socket is not None:
            proxy_server = await asyncio.start_server(
                functools.partial(self._proxy_unix_connection, docker_socket),
                "127.0.0.1",
                port,
            )
        try:
            process = await asyncio.create_subprocess_exec(
                *sandboxed,
                cwd=package_root,
                env=environment,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
                preexec_fn=functools.partial(
                    self._limit_resources, model_worker=is_model_worker
                ),
            )
        except BaseException:
            if proxy_server is not None:
                proxy_server.close()
                await proxy_server.wait_closed()
            if docker_socket is not None:
                docker_socket.unlink(missing_ok=True)
            raise
        readers = (
            asyncio.create_task(
                self._logs(service_key, process_id, "stdout", process.stdout)
            ),
            asyncio.create_task(
                self._logs(service_key, process_id, "stderr", process.stderr)
            ),
        )
        managed = _Managed(
            package,
            process_id,
            process,
            endpoint,
            True,
            0,
            readers,
            internal_token,
            proxy_server,
            docker_socket,
            time.monotonic(),
        )
        self._live[service_key] = managed
        with self.packages.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE managed_service_processes SET status = 'running', pid = ?,
                   started_at = ?, updated_at = ? WHERE id = ?""",
                (process.pid, now, now, process_id),
            )
        try:
            await self._wait_ready(package, endpoint, process, internal_token)
        except Exception:
            await self.stop(service_key)
            raise
        asyncio.create_task(
            self._watch(service_key, managed), name=f"service-watch-{service_key}"
        )
        self.packages.append_log(
            service_key,
            "info",
            "system",
            "Service became ready",
            process_id=process_id,
            fields={"endpoint": endpoint},
        )
        return endpoint

    async def _wait_ready(
        self,
        package: InstalledPackageRecord,
        endpoint: str,
        process: asyncio.subprocess.Process,
        internal_token: str | None = None,
    ) -> None:
        health = package.manifest.get("health", {})
        path = str(health.get("path", "/health"))
        timeout = min(120, max(1, int(health.get("startup_timeout_seconds", 30))))
        deadline = asyncio.get_running_loop().time() + timeout
        url = endpoint.rstrip("/") + "/" + path.lstrip("/")
        while asyncio.get_running_loop().time() < deadline:
            if process.returncode is not None:
                raise PackageError(
                    "service_start_failed", "Managed Service exited before readiness"
                )
            try:
                status = await asyncio.to_thread(
                    self._health_request, url, internal_token
                )
                if status:
                    return
            except (OSError, urllib.error.URLError):
                pass
            await asyncio.sleep(0.1)
        raise PackageError(
            "service_readiness_timeout", f"Service did not become ready: {url}"
        )

    @staticmethod
    def _health_request(url: str, token: str | None = None) -> bool:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=1) as response:
            if response.status < 200 or response.status >= 300:
                return False
            content = response.read(64 * 1024)
        if not content:
            return True
        try:
            value = json.loads(content)
        except json.JSONDecodeError:
            return True
        return value.get("status", "ok") in {"ok", "ready", "healthy"}

    async def _logs(
        self,
        service_key: str,
        process_id: str,
        stream: str,
        reader: asyncio.StreamReader | None,
    ) -> None:
        if reader is None:
            return
        while line := await reader.readline():
            text = line[:65536].decode("utf-8", "replace").rstrip("\r\n")
            level = "error" if stream == "stderr" else "info"
            fields: dict[str, Any] = {}
            message = text
            try:
                structured = json.loads(text)
                if isinstance(structured, dict) and isinstance(
                    structured.get("message"), str
                ):
                    message = structured.pop("message")
                    candidate = structured.pop("level", level)
                    if candidate in {
                        "trace",
                        "debug",
                        "info",
                        "warning",
                        "error",
                        "critical",
                    }:
                        level = candidate
                    fields = structured
            except json.JSONDecodeError:
                pass
            await asyncio.to_thread(
                self.packages.append_log,
                service_key,
                level,
                stream,
                message,
                process_id=process_id,
                fields=fields,
            )

    async def _watch(self, service_key: str, managed: _Managed) -> None:
        return_code = await managed.process.wait()
        if managed.proxy_server is not None:
            managed.proxy_server.close()
            await managed.proxy_server.wait_closed()
        if managed.unix_socket is not None:
            managed.unix_socket.unlink(missing_ok=True)
        if self._live.get(service_key) is not managed:
            return
        if not managed.desired or self._stopping:
            return
        restart = managed.package.manifest.get("restart", {})
        maximum = min(10, max(0, int(restart.get("max_attempts", 3))))
        if managed.restart_count >= maximum:
            self.packages.append_log(
                service_key,
                "critical",
                "system",
                "Restart budget exhausted",
                process_id=managed.process_id,
                fields={"return_code": return_code},
            )
            service = self.services.get_service(service_key)
            instance = self.services.get_instance_for_service(service.id)
            self.services.set_instance_status(
                instance.id,
                ServiceInstanceStatus.FAILED,
                last_error=f"managed process exited {return_code}",
            )
            return
        delay = min(
            30.0,
            float(restart.get("base_delay_seconds", 0.5)) * 2**managed.restart_count,
        )
        await asyncio.sleep(delay)
        if managed.desired and not self._stopping:
            self._live.pop(service_key, None)
            try:
                endpoint = await self.start(managed.package)
                replacement = self._live[service_key]
                replacement.restart_count = managed.restart_count + 1
                service = self.services.get_service(service_key)
                instance = self.services.get_instance_for_service(service.id)
                self.services.ensure_instance(
                    service_id=service.id,
                    provider_key=instance.provider_key,
                    status=ServiceInstanceStatus.RUNNING,
                    endpoint=endpoint,
                    health={"status": "ok", "mode": "managed_process"},
                )
            except Exception as error:
                self.packages.append_log(
                    service_key,
                    "error",
                    "system",
                    "Service restart failed",
                    fields={"error": str(error)},
                )

    async def stop(self, service_key: str) -> None:
        managed = self._live.pop(service_key, None)
        self._draining.discard(service_key)
        self._evicted.pop(service_key, None)
        if managed is None:
            return
        managed.desired = False
        if managed.proxy_server is not None:
            managed.proxy_server.close()
            await managed.proxy_server.wait_closed()
        if managed.process.returncode is None:
            with suppress(ProcessLookupError):
                os.killpg(managed.process.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(managed.process.wait(), 5)
            except TimeoutError:
                with suppress(ProcessLookupError):
                    os.killpg(managed.process.pid, signal.SIGKILL)
                await managed.process.wait()
        if managed.unix_socket is not None:
            managed.unix_socket.unlink(missing_ok=True)
        for task in managed.tasks:
            with suppress(asyncio.CancelledError):
                await task
        now = utc_now_text()
        with self.packages.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE managed_service_processes SET status = 'stopped',
                   stopped_at = ?, updated_at = ? WHERE id = ?""",
                (now, now, managed.process_id),
            )

    async def evict(
        self,
        service_key: str,
        *,
        reason: str,
        expected_generation: int,
    ) -> dict[str, Any]:
        """Stop an idle Worker without disabling its active Package."""

        self.assert_worker_generation(service_key, expected_generation)
        managed = self._live.get(service_key)
        if managed is None:
            self._evicted[service_key] = reason
            return {"serviceKey": service_key, "state": "evicted", "reason": reason}
        if managed.package.protocol != "ai2apps-model-worker/v1":
            raise PackageError("not_model_worker", "Service is not a Model Worker")
        snapshot = await self.worker_snapshot(managed.package)
        if snapshot["activeRequests"] is None or snapshot["queuedRequests"] is None:
            raise PackageError(
                "worker_state_unavailable", "Cannot verify that the Model Worker is idle"
            )
        if snapshot["activeRequests"] or snapshot["queuedRequests"]:
            raise PackageError(
                "worker_busy",
                "Active or queued requests prevent Worker eviction",
                details={
                    "activeRequests": snapshot["activeRequests"],
                    "queuedRequests": snapshot["queuedRequests"],
                },
            )
        await self.stop(service_key)
        self._evicted[service_key] = reason
        self.packages.append_log(
            service_key,
            "info",
            "system",
            "Model Worker was evicted",
            fields={"reason": reason, "generation": expected_generation},
        )
        return {
            "serviceKey": service_key,
            "state": "evicted",
            "reason": reason,
            "generation": expected_generation,
        }

    async def restart(self, package: InstalledPackageRecord) -> str:
        await self.stop(package.service_key)
        return await self.start(package)

    async def shutdown(self) -> None:
        self._stopping = True
        await asyncio.gather(
            *(self.stop(key) for key in tuple(self._live)), return_exceptions=True
        )

    def recover_orphans(self) -> int:
        now = utc_now_text()
        count = 0
        live_process_ids = {
            managed.process.pid
            for managed in self._live.values()
            if managed.process.returncode is None
        }
        with self.packages.database.transaction(write=True) as connection:
            rows = connection.execute(
                """SELECT id, pid, started_at FROM managed_service_processes
                   WHERE status IN ('starting', 'running')"""
            ).fetchall()
            for row in rows:
                if row["pid"] in live_process_ids:
                    continue
                if row["pid"] and row["started_at"]:
                    with suppress(
                        psutil.Error, ProcessLookupError, PermissionError, OSError
                    ):
                        process = psutil.Process(row["pid"])
                        from ai2apps.core import parse_utc

                        started = parse_utc(row["started_at"]).timestamp()
                        if (
                            abs(process.create_time() - started) < 5.0
                            and os.getpgid(row["pid"]) == row["pid"]
                        ):
                            os.killpg(row["pid"], signal.SIGKILL)
                connection.execute(
                    """UPDATE managed_service_processes SET status = 'orphaned',
                       stopped_at = ?, updated_at = ? WHERE id = ?""",
                    (now, now, row["id"]),
                )
                count += 1
        return count
