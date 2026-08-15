"""Register first-party read-only web research Tools."""

from __future__ import annotations

import asyncio
from typing import Any

from ai2apps.services import (
    ServiceInstanceStatus,
    ServiceRegistry,
    ServiceRepository,
    ServiceRuntimeMode,
    ToolCallContext,
    ToolProviderError,
)

from .provider import BingWebProvider, WebProvider, WebProviderError

OBJECT = {"type": "object"}


def install_web_research_service(
    repository: ServiceRepository,
    registry: ServiceRegistry,
    provider: WebProvider | None = None,
) -> WebProvider:
    provider = provider or BingWebProvider()
    service = repository.ensure_service(
        service_key="ai2apps.web-research",
        package_id="ai2apps.web-research",
        package_version="1.0.0",
        display_name="AI2Apps Web Research",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
        capabilities=("web.search", "web.fetch"),
        config={"provider": provider.name, "read_only": True},
    )
    instance = repository.ensure_instance(
        service_id=service.id,
        provider_key="builtin:web-research",
        status=ServiceInstanceStatus.RUNNING,
        endpoint="/v1/platform/tools/web.search/invoke",
        health={"status": "ok", "provider": provider.name},
    )

    async def invoke(operation, *args, **kwargs):
        try:
            return await asyncio.to_thread(operation, *args, **kwargs)
        except WebProviderError as exc:
            raise ToolProviderError(str(exc)) from exc

    async def search(arguments: dict[str, Any], context: ToolCallContext) -> dict:
        await context.report_progress("Searching the web", progress=0.2)
        result = await invoke(
            provider.search,
            arguments["query"],
            limit=arguments.get("limit", 5),
        )
        await context.report_progress(
            f"Found {result['count']} web sources",
            progress=1.0,
            content={"provider": result["provider"], "count": result["count"]},
        )
        return result

    async def fetch(arguments: dict[str, Any], context: ToolCallContext) -> dict:
        await context.report_progress("Reading web source", progress=0.2)
        result = await invoke(
            provider.fetch,
            arguments["url"],
            max_chars=arguments.get("max_chars", 60_000),
        )
        await context.report_progress(
            "Web source ready",
            progress=1.0,
            content={"source_id": result["source_id"], "url": result["url"]},
        )
        return result

    definitions = (
        (
            "web.search",
            "Search the web",
            "Search the public web and return structured source records. Read relevant sources with web.fetch before citing factual claims.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 1024},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            search,
        ),
        (
            "web.fetch",
            "Read web source",
            "Fetch and extract bounded text from a public HTTP(S) source. Local, private, reserved, credential-bearing, and oversized targets are blocked.",
            {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "minLength": 1, "maxLength": 8192},
                    "max_chars": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 100000,
                    },
                },
                "required": ["url"],
                "additionalProperties": False,
            },
            fetch,
        ),
    )
    for name, title, description, schema, handler in definitions:
        repository.ensure_tool(
            service_id=service.id,
            qualified_name=name,
            display_name=title,
            description=description,
            input_schema=schema,
            output_schema=OBJECT,
            effects=("external_read", "network"),
            required_capabilities=("network.outbound",),
            timeout_ms=30_000,
        )
        registry.bind_tool(name, provider_key=instance.provider_key, handler=handler)
    return provider
