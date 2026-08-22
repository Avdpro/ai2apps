"""Managed-process Service sandbox, health gate, logs, and restart supervision."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import resource
import secrets
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


class ManagedServiceSupervisor:
    def __init__(
        self,
        packages: PackageRepository,
        services: ServiceRepository,
        packages_root: Path,
        *,
        inference_runtimes: InferenceRuntimeResolver | None = None,
    ) -> None:
        self.packages = packages
        self.services = services
        self.packages_root = packages_root
        self.inference_runtimes = inference_runtimes
        self._live: dict[str, _Managed] = {}
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
        manifest: dict[str, Any], hub_cache: Path
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
            snapshot = repo_root / "snapshots" / revision
            snapshot_path = (
                snapshot.resolve()
                if snapshot.is_dir()
                and ManagedServiceSupervisor._checkpoint_is_complete(snapshot)
                else None
            )
            if snapshot_path is not None:
                try:
                    snapshot_path.relative_to(repo_root)
                except ValueError as exc:
                    raise PackageError(
                        "invalid_model_weights", "Model snapshot escapes its repository cache"
                    ) from exc
                roots.append(repo_root)
            checkpoints.append(
                {
                    "model_id": model["id"],
                    "upstream_id": model["upstream_id"],
                    "provider": weights["provider"],
                    "repo_id": repo_id,
                    "revision": revision,
                    "path": str(snapshot_path) if snapshot_path is not None else None,
                    "preparation": weights.get("preparation", {}),
                }
            )
        return tuple(checkpoints), tuple(dict.fromkeys(roots))

    @staticmethod
    def _checkpoint_is_complete(snapshot: Path) -> bool:
        """Require a complete native checkpoint before granting it to a Worker.

        MLX checkpoints use safetensors, while signed helper Packages may pin
        native ONNX checkpoints (for example the CT-Transformer punctuation
        dependency).  Both formats are immutable Hugging Face snapshots and
        are safe to expose after their required model file is present.
        """

        onnx_files = tuple(snapshot.glob("*.onnx"))
        if onnx_files:
            native_config = next(
                (
                    snapshot / name
                    for name in ("config.json", "config.yaml", "config.yml")
                    if (snapshot / name).is_file()
                ),
                None,
            )
            return native_config is not None and any(
                path.is_file() for path in onnx_files
            )

        if not (snapshot / "config.json").is_file():
            return False
        indexes = sorted(snapshot.glob("*.safetensors.index.json"))
        if indexes:
            try:
                payload = json.loads(indexes[0].read_text(encoding="utf-8"))
                weight_map = payload.get("weight_map", {})
                shards = set(weight_map.values())
            except (OSError, json.JSONDecodeError, AttributeError):
                return False
            if not shards:
                return False
            for shard in shards:
                if (
                    not isinstance(shard, str)
                    or shard.startswith("/")
                    or ".." in shard.split("/")
                    or not (snapshot / shard).is_file()
                ):
                    return False
            return True
        return any(path.is_file() for path in snapshot.glob("*.safetensors"))

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
        is_model_worker = package.protocol == "ai2apps-model-worker/v1"
        runtime_provider = manifest.get("runtime", {}).get("provider")
        resolved_runtime = None
        if is_model_worker and runtime_provider is not None:
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
        if is_model_worker:
            declared_weight_permission = manifest.get("permissions", {}).get(
                "model_weights", {}
            )
            if any(
                isinstance(model, dict) and isinstance(model.get("weights"), dict)
                for model in manifest.get("models", [])
            ) and not (
                isinstance(declared_weight_permission, dict)
                and declared_weight_permission.get("huggingface_cache") == "read"
            ):
                raise PackageError(
                    "missing_model_weight_permission",
                    "Declared Hugging Face weights require model_weights.huggingface_cache: read",
                )
            worker_checkpoints, worker_weight_roots = self._model_worker_checkpoints(
                manifest, hf_hub_cache
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
            if is_model_worker:
                read_only_roots.extend(worker_weight_roots)
            else:
                hf_cache_root = hf_hub_cache
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
        if internal_token is not None:
            environment["AI2APPS_MODEL_WORKER_TOKEN"] = internal_token
        if framework_site is not None:
            environment["AI2APPS_TRUSTED_FRAMEWORK_SITE_PACKAGES"] = str(
                framework_site
            )
        if resolved_runtime is not None:
            environment["PYTHONHOME"] = str(resolved_runtime.python_home)
            environment["AI2APPS_INFERENCE_RUNTIME"] = str(resolved_runtime.root)
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
        managed = _Managed(
            package,
            process_id,
            process,
            endpoint,
            True,
            0,
            readers,
            internal_token,
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
