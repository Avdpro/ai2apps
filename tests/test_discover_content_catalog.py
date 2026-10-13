from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from ai2apps.api.packages import create_package_router
from ai2apps.identity import RequestPrincipal
from ai2apps.packages.registry import RegistryError, RegistryPackageManager


@pytest.mark.asyncio
async def test_content_routes_forward_query_without_package_filtering():
    page = {"schemaVersion": "ai2apps.content-catalog.v1", "items": [],
            "catalogSnapshot": "snapshot", "nextCursor": "opaque"}
    manager = SimpleNamespace(
        discovery_capabilities=AsyncMock(return_value={"contentCatalog": {"schemaVersion": page["schemaVersion"]}}),
        content_catalog=AsyncMock(return_value=page),
    )
    app = FastAPI()
    app.include_router(create_package_router(lambda: SimpleNamespace(registry_packages=manager),
                                            principal_provider=RequestPrincipal.legacy_local))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        caps = await client.get("/packages/catalog/capabilities")
        assert caps.status_code == 200
        assert caps.headers["cache-control"] == "no-store"
        result = await client.get("/packages/catalog/content", params={
            "content": "mini-app", "mini_app_category": "audio", "studio": "ai2apps.readaloud",
            "q": "music", "limit": 24, "cursor": "opaque/+=", "sort": "relevance",
        })
        assert result.json() == page
        assert result.headers["cache-control"] == "no-store"
        forwarded = manager.content_catalog.call_args.kwargs
        assert forwarded["limit"] == 24
        assert forwarded["cursor"] == "opaque/+="
        assert forwarded["mini_app_category"] == "audio"
        assert forwarded["studio"] == "ai2apps.readaloud"
        manager.content_catalog.side_effect = RegistryError("catalog_cursor_expired", "Expired", details={"status": 410})
        expired = await client.get("/packages/catalog/content")
        assert expired.status_code == 410
        assert expired.json()["error"]["code"].lower() == "catalog_cursor_expired"


@pytest.mark.asyncio
async def test_manager_uses_fixed_public_capability_and_content_endpoints(tmp_path):
    manager = RegistryPackageManager(cloud=None, root=tmp_path, secrets=None,
                                     extension_manager=None, service_manager=None)
    manager._public_json = AsyncMock(return_value={"discoveryCapabilities": {"contentCatalog": {}}})
    assert await manager.discovery_capabilities() == {"contentCatalog": {}}
    manager._public_json.assert_awaited_once_with("GET", "/v1/registry")
    manager._json = AsyncMock(return_value={"items": [], "nextCursor": None})
    await manager.content_catalog(content="mini-app", limit=24, cursor="opaque", q="", studio=None)
    manager._json.assert_awaited_once_with("GET", "/v1/registry/content",
                                         params={"content": "mini-app", "limit": 24, "cursor": "opaque"})
