"""Managed-process Service sandbox, health gate, logs, and restart supervision."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import resource
import shutil
import signal
import socket
import sys
import urllib.error
import urllib.request
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from ai2apps.core import EntityIdKind, new_entity_id, utc_now_text
from ai2apps.services import ServiceInstanceStatus, ServiceRepository

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


class ManagedServiceSupervisor:
    def __init__(
        self,
        packages: PackageRepository,
        services: ServiceRepository,
        packages_root: Path,
    ) -> None:
        self.packages = packages
        self.services = services
        self.packages_root = packages_root
        self._live: dict[str, _Managed] = {}
        self._stopping = False

    @staticmethod
    def _port() -> int:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            return int(listener.getsockname()[1])

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
                "(allow mach-lookup)",
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
            if not network:
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
            value.extend(
                (
                    "--dev",
                    "/dev",
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
    def _limit_resources() -> None:
        with suppress(OSError, ValueError):
            resource.setrlimit(resource.RLIMIT_CPU, (3600, 3600))
        with suppress(OSError, ValueError):
            # mlx_lm raises its soft limit to 2048 during import and expects a
            # 4096 hard ceiling. Keep the Service bounded while allowing model
            # providers with sharded checkpoints to initialize.
            resource.setrlimit(resource.RLIMIT_NOFILE, (4096, 4096))
        if platform.system() != "Darwin":
            with suppress(OSError, ValueError):
                resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))

    async def start(self, package: InstalledPackageRecord) -> str:
        service_key = package.service_key
        existing = self._live.get(service_key)
        if existing is not None and existing.process.returncode is None:
            return existing.endpoint
        manifest = package.manifest
        runtime = manifest["runtime"]
        command = runtime.get("command", [])
        if not isinstance(command, list) or not command:
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
        replacements = {
            "{port}": str(port),
            "{package}": str(package_root),
            "{data}": str(data_root),
            "{temporary}": str(temporary),
            # Preserve the virtual-environment entrypoint. Resolving this
            # symlink selects the base interpreter and silently drops the
            # venv's site-packages for every Python Service Package.
            "{python}": str(Path(sys.executable).absolute()),
            "{variant}": str(
                package.verification.get("signature", {}).get("selected_variant") or ""
            ),
        }
        replacements["{variant_root}"] = str(
            package_root / "variants" / (replacements["{variant}"] or "portable")
        )
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
        permissions = manifest.get("permissions", {})
        network = bool(permissions.get("network", {}).get("outbound", False))
        model_weights = permissions.get("model_weights", {})
        allow_hf_cache = bool(
            isinstance(model_weights, dict)
            and model_weights.get("huggingface_cache") == "read"
        )
        read_only_roots: list[Path] = []
        hf_cache_root: Path | None = None
        if allow_hf_cache:
            configured_hf_home = os.environ.get("HF_HOME")
            hf_cache_root = Path(
                configured_hf_home
                if configured_hf_home
                else Path.home() / ".cache" / "huggingface"
            ).expanduser().resolve()
            if hf_cache_root.exists():
                read_only_roots.append(hf_cache_root)
        accelerator = permissions.get("accelerator", {})
        allow_metal = bool(
            isinstance(accelerator, dict) and accelerator.get("metal") is True
        )

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
        if hf_cache_root is not None:
            environment["AI2APPS_HF_CACHE_ROOT"] = str(hf_cache_root)
        process_id = new_entity_id(EntityIdKind.MANAGED_SERVICE_PROCESS)
        now = utc_now_text()
        with self.packages.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO managed_service_processes(
                    id, service_key, package_digest, status, endpoint, created_at, updated_at
                ) VALUES (?, ?, ?, 'starting', ?, ?, ?)""",
                (process_id, service_key, package.package_digest, endpoint, now, now),
            )
        process = await asyncio.create_subprocess_exec(
            *sandboxed,
            cwd=package_root,
            env=environment,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
            preexec_fn=self._limit_resources,
        )
        readers = (
            asyncio.create_task(
                self._logs(service_key, process_id, "stdout", process.stdout)
            ),
            asyncio.create_task(
                self._logs(service_key, process_id, "stderr", process.stderr)
            ),
        )
        managed = _Managed(package, process_id, process, endpoint, True, 0, readers)
        self._live[service_key] = managed
        with self.packages.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE managed_service_processes SET status = 'running', pid = ?,
                   started_at = ?, updated_at = ? WHERE id = ?""",
                (process.pid, now, now, process_id),
            )
        try:
            await self._wait_ready(package, endpoint, process)
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
                status = await asyncio.to_thread(self._health_request, url)
                if status:
                    return
            except (OSError, urllib.error.URLError):
                pass
            await asyncio.sleep(0.1)
        raise PackageError(
            "service_readiness_timeout", f"Service did not become ready: {url}"
        )

    @staticmethod
    def _health_request(url: str) -> bool:
        with urllib.request.urlopen(url, timeout=1) as response:
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
                await self.start(managed.package)
                replacement = self._live[service_key]
                replacement.restart_count = managed.restart_count + 1
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
        if managed is None:
            return
        managed.desired = False
        if managed.process.returncode is None:
            with suppress(ProcessLookupError):
                os.killpg(managed.process.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(managed.process.wait(), 5)
            except TimeoutError:
                with suppress(ProcessLookupError):
                    os.killpg(managed.process.pid, signal.SIGKILL)
                await managed.process.wait()
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
        with self.packages.database.transaction(write=True) as connection:
            rows = connection.execute(
                """SELECT id, pid, started_at FROM managed_service_processes
                   WHERE status IN ('starting', 'running')"""
            ).fetchall()
            for row in rows:
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
