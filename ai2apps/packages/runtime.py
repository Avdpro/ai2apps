"""Bind verified package runtimes and declared Tools to the Service gateway."""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ai2apps.services import (
    ServiceInstanceStatus,
    ServiceLifecycle,
    ServiceRegistry,
    ServiceRepository,
    ServiceRuntimeMode,
    ToolCallContext,
    ToolProviderError,
)

from .models import InstalledPackageRecord, PackageError
from .supervisor import ManagedServiceSupervisor


class PackageRuntimeBinder:
    def __init__(
        self,
        services: ServiceRepository,
        registry: ServiceRegistry,
        supervisor: ManagedServiceSupervisor,
    ) -> None:
        self.services = services
        self.registry = registry
        self.supervisor = supervisor
        self._embedded: dict[str, dict[str, Any]] = {}

    def register(self, package: InstalledPackageRecord) -> None:
        service = self.services.get_service(package.service_key)
        instance = self.services.get_instance_for_service(service.id)
        active_names: set[str] = set()
        for descriptor in package.manifest.get("tools", []):
            name = descriptor.get("name")
            if (
                not isinstance(name, str)
                or not name
                or not name.startswith(package.service_key + ".")
            ):
                raise PackageError(
                    "invalid_tool_name",
                    "Installed Tool names must be qualified by Service id",
                )
            active_names.add(name)
            self.services.ensure_tool(
                service_id=service.id,
                qualified_name=name,
                display_name=str(descriptor.get("display_name", name)),
                description=str(descriptor.get("description", "")),
                input_schema=descriptor.get("input_schema", {"type": "object"}),
                output_schema=descriptor.get("output_schema", {"type": "object"}),
                effects=tuple(descriptor.get("effects", [])),
                required_capabilities=tuple(
                    descriptor.get("required_capabilities", [])
                ),
                capability_rules=tuple(descriptor.get("capability_rules", [])),
                retry_policy=descriptor.get("retry_policy"),
                timeout_ms=min(
                    300_000, max(1, int(descriptor.get("timeout_ms", 30_000)))
                ),
            )
            self.registry.bind_tool(
                name,
                provider_key=instance.provider_key,
                handler=self._tool_handler(package, descriptor),
            )
        self.services.disable_unseen_tools(service.id, active_names)
        self.registry.bind_lifecycle(
            package.service_key,
            lifecycle=ServiceLifecycle(
                start=lambda: self.start(package),
                stop=lambda: self.stop(package),
                restart=lambda: self.restart(package),
            ),
        )

    def _tool_handler(
        self, package: InstalledPackageRecord, descriptor: dict[str, Any]
    ):
        async def invoke(arguments: dict[str, Any], context: ToolCallContext):
            if package.runtime_mode is ServiceRuntimeMode.IN_PROCESS:
                state = self._embedded.get(package.service_key)
                handlers = {} if state is None else state.get("tools", {})
                handler = handlers.get(descriptor["name"])
                if handler is None:
                    raise ToolProviderError(
                        "Embedded Service Tool handler is unavailable"
                    )
                value = handler(arguments, context)
                if inspect.isawaitable(value):
                    value = await value
                return value
            service = self.services.get_service(package.service_key)
            instance = self.services.get_instance_for_service(service.id)
            if not instance.endpoint:
                raise ToolProviderError("Service endpoint is unavailable")
            path = str(descriptor.get("path", f"/tools/{descriptor['name']}"))
            method = str(descriptor.get("method", "POST")).upper()
            return await asyncio.to_thread(
                self._http_json,
                instance.endpoint.rstrip("/") + "/" + path.lstrip("/"),
                method,
                arguments,
                context.trace_id,
            )

        return invoke

    @staticmethod
    def _http_json(
        url: str, method: str, arguments: dict[str, Any], trace_id: str | None
    ):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if trace_id:
            headers["X-AI2Apps-Trace-ID"] = trace_id
        request = urllib.request.Request(
            url,
            data=json.dumps(arguments).encode(),
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read(4 * 1024 * 1024 + 1)
        except urllib.error.URLError as error:
            raise ToolProviderError(f"Service request failed: {error}") from error
        if len(data) > 4 * 1024 * 1024:
            raise ToolProviderError("Service response exceeds 4 MiB")
        try:
            result = json.loads(data)
        except json.JSONDecodeError as error:
            raise ToolProviderError("Service returned invalid JSON") from error
        if not isinstance(result, dict):
            raise ToolProviderError("Service response must be a JSON object")
        return result

    async def start(self, package: InstalledPackageRecord) -> None:
        service = self.services.get_service(package.service_key)
        instance = self.services.get_instance_for_service(service.id)
        if package.runtime_mode is ServiceRuntimeMode.MANAGED_PROCESS:
            endpoint = await self.supervisor.start(package)
            self.services.ensure_instance(
                service_id=service.id,
                provider_key=instance.provider_key,
                status=ServiceInstanceStatus.RUNNING,
                endpoint=endpoint,
                health={"status": "ok", "mode": "managed_process"},
            )
        elif package.runtime_mode is ServiceRuntimeMode.EXTERNAL:
            endpoint = package.manifest["runtime"]["endpoint"]
            health = package.manifest.get("health", {})
            path = str(health.get("path", "/health"))
            healthy = await asyncio.to_thread(
                ManagedServiceSupervisor._health_request,
                endpoint.rstrip("/") + "/" + path.lstrip("/"),
            )
            if not healthy:
                raise PackageError("service_unhealthy", "External Service is not ready")
            self.services.ensure_instance(
                service_id=service.id,
                provider_key=instance.provider_key,
                status=ServiceInstanceStatus.RUNNING,
                endpoint=endpoint,
                health={"status": "ok", "mode": "external"},
            )
        else:
            await self._start_embedded(package)
            self.services.set_instance_status(
                instance.id,
                ServiceInstanceStatus.RUNNING,
                health={"status": "ok", "mode": "in_process"},
            )

    async def _start_embedded(self, package: InstalledPackageRecord) -> None:
        entrypoint = package.entrypoint
        if not entrypoint or ":" not in entrypoint:
            raise PackageError(
                "invalid_entrypoint", "Embedded entrypoint must be module:function"
            )
        module_name, function_name = entrypoint.split(":", 1)
        source = (
            Path(package.store_path) / "src" / (module_name.replace(".", "/") + ".py")
        )
        if not source.is_file():
            raise PackageError(
                "entrypoint_not_found", f"Embedded entrypoint not found: {source}"
            )
        unique_name = f"_ai2apps_service_{package.package_digest.split(':')[-1]}"
        spec = importlib.util.spec_from_file_location(unique_name, source)
        if spec is None or spec.loader is None:
            raise PackageError("entrypoint_load_failed", "Cannot load embedded Service")
        module = importlib.util.module_from_spec(spec)
        sys.modules[unique_name] = module
        try:
            spec.loader.exec_module(module)
            factory = getattr(module, function_name)
            state = factory()
            if inspect.isawaitable(state):
                state = await state
        except Exception:
            sys.modules.pop(unique_name, None)
            raise
        if not isinstance(state, dict) or not isinstance(state.get("tools", {}), dict):
            raise PackageError(
                "invalid_embedded_provider",
                "Embedded factory must return a provider object",
            )
        state["module_name"] = unique_name
        self._embedded[package.service_key] = state

    async def stop(self, package: InstalledPackageRecord) -> None:
        if package.runtime_mode is ServiceRuntimeMode.MANAGED_PROCESS:
            await self.supervisor.stop(package.service_key)
        elif package.runtime_mode is ServiceRuntimeMode.IN_PROCESS:
            state = self._embedded.pop(package.service_key, None)
            if state is not None:
                stop = state.get("stop")
                if stop is not None:
                    value = stop()
                    if inspect.isawaitable(value):
                        await value
                sys.modules.pop(state.get("module_name", ""), None)

    async def restart(self, package: InstalledPackageRecord) -> None:
        await self.stop(package)
        await self.start(package)

    async def shutdown(self) -> None:
        await self.supervisor.shutdown()
