from __future__ import annotations

import hashlib
import sqlite3

import httpx
import pytest

from ai2apps.cloud_client import AI2AppsCloudClient, CloudSessionStore
from ai2apps.secrets import MemorySecretBackend
from scripts.publish_signed_registry_artifact import (
    browser_session_namespace,
    source_collection_path,
    source_response,
)


def test_browser_session_namespace_reads_newest_cookie_from_wal(tmp_path) -> None:
    security_instance_id = "local_" + "a" * 32
    cookie_name = "ai2apps_cloud_browser_" + hashlib.sha256(
        security_instance_id.encode("ascii")
    ).hexdigest()[:16]
    database = tmp_path / "cookies.sqlite"
    writer = sqlite3.connect(database)
    try:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        writer.execute(
            "CREATE TABLE moz_cookies "
            "(name TEXT NOT NULL, value TEXT NOT NULL, lastAccessed INTEGER NOT NULL)"
        )
        writer.execute(
            "INSERT INTO moz_cookies VALUES (?, ?, ?)",
            (cookie_name, "browser_session_old_1234567890123456", 1),
        )
        writer.commit()
        writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        writer.execute(
            "INSERT INTO moz_cookies VALUES (?, ?, ?)",
            (cookie_name, "browser_session_new_1234567890123456", 2),
        )
        writer.commit()

        assert browser_session_namespace(database, security_instance_id) == (
            "browser:browser_session_new_1234567890123456"
        )
    finally:
        writer.close()


def test_source_collection_path_encodes_release_identity() -> None:
    assert source_collection_path("ai2apps/runtime-omlx", "1.6.0") == (
        "/v1/admin/registry/packages/ai2apps/runtime-omlx/versions/1.6.0/sources"
    )
    with pytest.raises(ValueError):
        source_collection_path("runtime-omlx", "1.6.0")


@pytest.mark.asyncio
async def test_source_response_preserves_concurrency_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["if-match"] == '"sources-3"'
        assert request.headers["idempotency-key"] == "runtime-source-register-1"
        assert request.read() == b'{"kind":"github"}'
        return httpx.Response(
            202,
            headers={"etag": '"sources-4"'},
            json={"sourceId": "src_test", "status": "validating"},
        )

    cloud = AI2AppsCloudClient(
        base_url="https://cloud.example",
        session_store=CloudSessionStore(
            MemorySecretBackend(), "https://cloud.example"
        ),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await source_response(
            cloud,
            "POST",
            "/v1/admin/registry/packages/ai2apps/runtime/versions/1.0.0/sources",
            body={"kind": "github"},
            etag='"sources-3"',
            idempotency_key="runtime-source-register-1",
        )
    finally:
        await cloud.close()
    assert result == {
        "result": {"sourceId": "src_test", "status": "validating"},
        "etag": '"sources-4"',
    }


@pytest.mark.asyncio
async def test_source_response_revalidates_without_revision_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/sources/src_test/validate")
        assert request.headers["idempotency-key"] == "runtime-source-revalidate-1"
        assert "if-match" not in request.headers
        return httpx.Response(
            202,
            json={
                "sourceId": "src_test",
                "status": "validating",
                "validationId": "val_retry",
            },
        )

    cloud = AI2AppsCloudClient(
        base_url="https://cloud.example",
        session_store=CloudSessionStore(
            MemorySecretBackend(), "https://cloud.example"
        ),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await source_response(
            cloud,
            "POST",
            "/v1/admin/registry/packages/ai2apps/runtime/versions/1.0.0/"
            "sources/src_test/validate",
            idempotency_key="runtime-source-revalidate-1",
        )
    finally:
        await cloud.close()
    assert result["result"]["validationId"] == "val_retry"


@pytest.mark.asyncio
async def test_source_response_rejects_cloud_error() -> None:
    cloud = AI2AppsCloudClient(
        base_url="https://cloud.example",
        session_store=CloudSessionStore(
            MemorySecretBackend(), "https://cloud.example"
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                412,
                json={
                    "error": {
                        "code": "ARTIFACT_SOURCE_REVISION_STALE",
                        "message": "If-Match source revision is stale",
                    }
                },
            )
        ),
    )
    try:
        with pytest.raises(RuntimeError, match="ARTIFACT_SOURCE_REVISION_STALE"):
            await source_response(cloud, "POST", "/v1/source")
    finally:
        await cloud.close()
