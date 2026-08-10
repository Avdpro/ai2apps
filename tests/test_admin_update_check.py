# SPDX-License-Identifier: Apache-2.0
"""Tests for the independent AI2Apps update-check endpoint."""

from pathlib import Path
from unittest.mock import patch

import pytest

import omlx.admin.routes as admin_routes


class _FakeResponse:
    """Minimal mock for requests.Response."""

    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self._data = data if data is not None else []

    def json(self):
        return self._data


def _reset_cache():
    """Reset module-level update cache between tests."""
    admin_routes._update_cache = {}
    admin_routes._update_cache_time = {}
    admin_routes._UPDATE_PREFS_PATH = Path("/tmp/omlx-test-missing-update-prefs.json")


class TestCheckUpdate:
    """Tests for /admin/api/update-check endpoint."""

    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()

    @pytest.mark.asyncio
    async def test_upstream_release_is_not_reported_as_product_update(self):
        """An oMLX release must never be presented as an AI2Apps update."""
        fake_resp = _FakeResponse(200, [{
            "tag_name": "v99.0.0",
            "html_url": "https://github.com/jundot/omlx/releases/tag/v99.0.0",
        }])

        with patch("omlx.admin.routes.asyncio") as mock_asyncio:
            mock_asyncio.to_thread = _make_async_return(fake_resp)

            result = await admin_routes.check_update(is_admin=True)

        assert result == {
            "update_available": False,
            "latest_version": None,
            "release_url": None,
            "update_channel": "ai2apps",
        }

    @pytest.mark.asyncio
    async def test_no_update(self):
        """Should return update_available=False when current version is latest."""
        fake_resp = _FakeResponse(200, [{
            "tag_name": "v0.0.1",
            "html_url": "https://github.com/jundot/omlx/releases/tag/v0.0.1",
        }])

        with patch("omlx.admin.routes.asyncio") as mock_asyncio:
            mock_asyncio.to_thread = _make_async_return(fake_resp)

            result = await admin_routes.check_update(is_admin=True)

        assert result["update_available"] is False
        assert result["latest_version"] is None

    @pytest.mark.asyncio
    async def test_github_api_failure(self):
        """Should return update_available=False on HTTP error."""
        fake_resp = _FakeResponse(403)

        with patch("omlx.admin.routes.asyncio") as mock_asyncio:
            mock_asyncio.to_thread = _make_async_return(fake_resp)

            result = await admin_routes.check_update(is_admin=True)

        assert result["update_available"] is False

    @pytest.mark.asyncio
    async def test_network_error(self):
        """Should return update_available=False on network exception."""

        async def raise_error(*args, **kwargs):
            raise ConnectionError("no network")

        with patch("omlx.admin.routes.asyncio") as mock_asyncio:
            mock_asyncio.to_thread = raise_error

            result = await admin_routes.check_update(is_admin=True)

        assert result["update_available"] is False

    @pytest.mark.asyncio
    async def test_update_check_does_not_call_upstream(self):
        """The independent endpoint is deterministic and performs no I/O."""
        fake_resp = _FakeResponse(200, [{
            "tag_name": "v99.0.0",
            "html_url": "https://github.com/jundot/omlx/releases/tag/v99.0.0",
        }])

        call_count = 0

        async def counting_to_thread(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return fake_resp

        with patch("omlx.admin.routes.asyncio") as mock_asyncio:
            mock_asyncio.to_thread = counting_to_thread

            await admin_routes.check_update(is_admin=True)
            result = await admin_routes.check_update(is_admin=True)
            assert call_count == 0
            assert result["update_channel"] == "ai2apps"


def _make_async_return(value):
    """Create an async function that returns the given value."""

    async def _async_return(*args, **kwargs):
        return value

    return _async_return
