"""Built-in adapters around existing AI2Apps/oMLX capabilities."""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from .models import (
    ServiceInstanceStatus,
    ServiceRuntimeMode,
    ToolCallContext,
    ToolProviderError,
)
from .registry import ServiceLifecycle, ServiceRegistry
from .repository import ServiceRepository

OBJECT_SCHEMA = {"type": "object"}


def install_echo_service(
    repository: ServiceRepository, registry: ServiceRegistry
) -> None:
    service = repository.ensure_service(
        service_key="ai2apps.diagnostics",
        package_id="ai2apps.diagnostics",
        package_version="1.0.0",
        display_name="AI2Apps Diagnostics",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
        capabilities=("diagnostics",),
    )
    instance = repository.ensure_instance(
        service_id=service.id,
        provider_key="builtin:diagnostics",
        status=ServiceInstanceStatus.RUNNING,
        endpoint="/v1/platform/tools/system.echo/invoke",
        health={"status": "ok"},
    )
    repository.ensure_tool(
        service_id=service.id,
        qualified_name="system.echo",
        display_name="Echo",
        description="Return the supplied JSON value for Service gateway diagnostics.",
        input_schema={
            "type": "object",
            "properties": {"value": {}},
            "required": ["value"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {"value": {}},
            "required": ["value"],
            "additionalProperties": False,
        },
        effects=(),
        timeout_ms=5_000,
    )

    async def echo(arguments: dict[str, Any], _: ToolCallContext) -> dict[str, Any]:
        return {"value": arguments["value"]}

    registry.bind_tool("system.echo", provider_key=instance.provider_key, handler=echo)


class OmlxModelServiceAdapter:
    """Expose the existing EnginePool without moving model-runtime ownership."""

    def __init__(self, engine_pool_provider: Callable[[], Any | None]) -> None:
        self.engine_pool_provider = engine_pool_provider

    def bind(self, repository: ServiceRepository, registry: ServiceRegistry) -> None:
        pool = self.engine_pool_provider()
        service = repository.ensure_service(
            service_key="ai2apps.model-runtime",
            package_id="ai2apps.model-runtime",
            package_version="1.0.0",
            display_name="Model Runtime",
            runtime_mode=ServiceRuntimeMode.IN_PROCESS,
            capabilities=("model.discovery", "model.lifecycle", "model.inference"),
            config={
                "compatibility_endpoints": [
                    "/v1/chat/completions",
                    "/v1/responses",
                    "/v1/embeddings",
                    "/v1/rerank",
                ],
                "inference_contract": "openai-compatible",
            },
        )
        instance = repository.ensure_instance(
            service_id=service.id,
            provider_key="builtin:omlx-model-runtime",
            status=(
                ServiceInstanceStatus.RUNNING
                if pool is not None
                else ServiceInstanceStatus.STOPPED
            ),
            endpoint="/v1",
            health={"runtime": "omlx", "available": pool is not None},
        )
        tools = (
            (
                "model.status",
                "Model Status",
                "Return the existing oMLX EnginePool status.",
                {"type": "object", "additionalProperties": False},
                (),
                self._status,
            ),
            (
                "model.load",
                "Load Model",
                "Load a discovered model into the existing oMLX runtime.",
                {
                    "type": "object",
                    "properties": {"model_id": {"type": "string", "minLength": 1}},
                    "required": ["model_id"],
                    "additionalProperties": False,
                },
                ("model.manage",),
                self._load,
            ),
            (
                "model.unload",
                "Unload Model",
                "Unload a model from the existing oMLX runtime.",
                {
                    "type": "object",
                    "properties": {"model_id": {"type": "string", "minLength": 1}},
                    "required": ["model_id"],
                    "additionalProperties": False,
                },
                ("model.manage",),
                self._unload,
            ),
        )
        for name, title, description, input_schema, capabilities, handler in tools:
            repository.ensure_tool(
                service_id=service.id,
                qualified_name=name,
                display_name=title,
                description=description,
                input_schema=input_schema,
                output_schema=OBJECT_SCHEMA,
                effects=("memory",) if name != "model.status" else (),
                required_capabilities=capabilities,
                timeout_ms=300_000 if name == "model.load" else 30_000,
            )
            registry.bind_tool(
                name, provider_key=instance.provider_key, handler=handler
            )
        registry.bind_lifecycle(
            service.service_key,
            lifecycle=ServiceLifecycle(
                start=lambda: self.bind(repository, registry),
                restart=lambda: self.bind(repository, registry),
            ),
        )

    def _pool(self):
        pool = self.engine_pool_provider()
        if pool is None:
            raise ToolProviderError("oMLX EnginePool is not initialized")
        return pool

    async def _status(self, _: dict[str, Any], __: ToolCallContext) -> dict[str, Any]:
        return dict(self._pool().get_status())

    async def _load(
        self, arguments: dict[str, Any], _: ToolCallContext
    ) -> dict[str, Any]:
        model_id = arguments["model_id"]
        pool = self._pool()
        if pool.get_entry(model_id) is None:
            raise ToolProviderError(f"Model not found: {model_id}")
        await pool.get_engine(model_id)
        return {"status": "ok", "model_id": model_id}

    async def _unload(
        self, arguments: dict[str, Any], _: ToolCallContext
    ) -> dict[str, Any]:
        model_id = arguments["model_id"]
        pool = self._pool()
        entry = pool.get_entry(model_id)
        if entry is None:
            raise ToolProviderError(f"Model not found: {model_id}")
        if entry.engine is None:
            return {"status": "ok", "model_id": model_id, "already_unloaded": True}
        await pool._unload_engine(model_id)
        return {"status": "ok", "model_id": model_id}


class MCPServiceAdapter:
    """Project discovered MCP servers/tools through the shared Tool Registry."""

    def __init__(self, manager_provider: Callable[[], Any | None]) -> None:
        self.manager_provider = manager_provider

    def bind(self, repository: ServiceRepository, registry: ServiceRegistry) -> None:
        manager = self.manager_provider()
        service = repository.ensure_service(
            service_key="ai2apps.mcp",
            package_id="ai2apps.mcp",
            package_version="1.0.0",
            display_name="MCP Service",
            runtime_mode=ServiceRuntimeMode.IN_PROCESS,
            capabilities=("mcp.discovery", "mcp.execution"),
        )
        statuses = [] if manager is None else manager.get_server_status()
        instance = repository.ensure_instance(
            service_id=service.id,
            provider_key="builtin:omlx-mcp",
            status=(
                ServiceInstanceStatus.RUNNING
                if manager is not None
                else ServiceInstanceStatus.STOPPED
            ),
            endpoint="/v1/mcp",
            health={
                "available": manager is not None,
                "servers": [status.to_dict() for status in statuses],
            },
        )
        active_names: set[str] = set()
        if manager is not None:
            for mcp_tool in manager.get_all_tools():
                qualified_name = f"mcp.{mcp_tool.full_name}"
                active_names.add(qualified_name)
                repository.ensure_tool(
                    service_id=service.id,
                    qualified_name=qualified_name,
                    display_name=mcp_tool.name,
                    description=mcp_tool.description,
                    input_schema=mcp_tool.input_schema or OBJECT_SCHEMA,
                    output_schema=OBJECT_SCHEMA,
                    effects=("external",),
                    timeout_ms=60_000,
                )

                async def execute(
                    arguments: dict[str, Any],
                    _: ToolCallContext,
                    *,
                    full_name: str = mcp_tool.full_name,
                ) -> dict[str, Any]:
                    current = self.manager_provider()
                    if current is None:
                        raise ToolProviderError("MCP manager is not initialized")
                    result = await current.execute_tool(full_name, arguments)
                    if result.is_error:
                        raise ToolProviderError(
                            result.error_message or f"MCP tool failed: {full_name}"
                        )
                    return {"content": result.content, "is_error": False}

                registry.bind_tool(
                    qualified_name,
                    provider_key=instance.provider_key,
                    handler=execute,
                )
        repository.disable_unseen_tools(service.id, active_names)
        if manager is not None:

            async def start() -> None:
                current = self.manager_provider()
                if current is None:
                    raise ToolProviderError("MCP manager is not initialized")
                await current.start()
                self.bind(repository, registry)

            async def stop() -> None:
                current = self.manager_provider()
                if current is not None:
                    await current.stop()

            async def restart() -> None:
                await stop()
                await start()

            registry.bind_lifecycle(
                service.service_key,
                lifecycle=ServiceLifecycle(
                    start=start,
                    stop=stop,
                    restart=restart,
                ),
            )


class ExternalJsonToolProvider:
    """Bind an external JSON-over-HTTP endpoint behind a stable Tool identity."""

    def __init__(self, endpoint: str, *, headers: dict[str, str] | None = None) -> None:
        self.endpoint = endpoint
        self.headers = dict(headers or {})

    async def __call__(
        self,
        arguments: dict[str, Any],
        _: ToolCallContext,
    ) -> dict[str, Any]:
        def request() -> dict[str, Any]:
            payload = json.dumps(arguments).encode("utf-8")
            headers = {"Content-Type": "application/json", **self.headers}
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(
                        self.endpoint,
                        data=payload,
                        headers=headers,
                        method="POST",
                    )
                ) as response:
                    value = json.loads(response.read().decode("utf-8"))
            except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
                raise ToolProviderError(
                    f"External Service request failed: {exc}"
                ) from exc
            if not isinstance(value, dict):
                raise ToolProviderError(
                    "External Service response must be a JSON object"
                )
            return value

        return await asyncio.to_thread(request)
