"""Bind verified package runtimes and declared Tools to the Service gateway."""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
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

from .inference_runtime import is_inference_runtime_manifest
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

    @staticmethod
    def _require_isolated_runtime(package: InstalledPackageRecord) -> None:
        if package.runtime_mode is ServiceRuntimeMode.IN_PROCESS:
            raise PackageError(
                "third_party_in_process_denied",
                "Installed Service Packages cannot execute in the AI2Apps host process",
            )

    def register(self, package: InstalledPackageRecord) -> None:
        self._require_isolated_runtime(package)
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
        self._require_isolated_runtime(package)
        service = self.services.get_service(package.service_key)
        instance = self.services.get_instance_for_service(service.id)
        if is_inference_runtime_manifest(package.manifest):
            self.services.ensure_instance(
                service_id=service.id,
                provider_key=instance.provider_key,
                status=ServiceInstanceStatus.RUNNING,
                endpoint=None,
                health={
                    "status": "ready",
                    "mode": "inference_runtime",
                    "capabilities": package.manifest.get("capabilities", []),
                },
            )
            return
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
        else:  # pragma: no cover - guarded above and retained for enum exhaustiveness
            raise PackageError(
                "third_party_in_process_denied",
                "Installed Service Packages cannot execute in the AI2Apps host process",
            )

    async def stop(self, package: InstalledPackageRecord) -> None:
        if is_inference_runtime_manifest(package.manifest):
            return
        if package.runtime_mode is ServiceRuntimeMode.MANAGED_PROCESS:
            await self.supervisor.stop(package.service_key)

    async def restart(self, package: InstalledPackageRecord) -> None:
        await self.stop(package)
        await self.start(package)

    async def shutdown(self) -> None:
        await self.supervisor.shutdown()
