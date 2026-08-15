# SPDX-License-Identifier: Apache-2.0
"""Contract tests for the initial AI2Apps platform API seam."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.errors import platform_error_response
from ai2apps.api.router import create_ai2apps_router
from ai2apps.config import (
    PLATFORM_DATABASE_FILENAME,
    PLATFORM_DATABASE_SCHEMA_VERSION,
    PlatformConfig,
    resolve_projects_path,
)
from ai2apps.platform_runtime import PlatformRuntime


def _standalone_app(config: PlatformConfig | None = None) -> FastAPI:
    test_app = FastAPI()
    provider = None if config is None else lambda: config
    test_app.include_router(create_ai2apps_router(config_provider=provider))
    return test_app


def test_platform_paths_are_derived_without_creating_files(tmp_path):
    base_path = tmp_path / "ai2apps-data"

    config = PlatformConfig.from_base_path(base_path)

    assert config.paths is not None
    assert config.paths.base_path == base_path.resolve()
    assert config.paths.database_path == (
        base_path.resolve() / "platform" / PLATFORM_DATABASE_FILENAME
    )
    assert config.paths.artifacts_path == base_path.resolve() / "platform" / "artifacts"
    assert config.paths.sandboxes_path == base_path.resolve() / "platform" / "sandboxes"
    assert config.paths.packages_path == base_path.resolve() / "platform" / "packages"
    assert config.paths.projects_path == base_path.resolve() / "projects"
    assert not base_path.exists()


def test_legacy_omlx_root_uses_ai2apps_project_namespace(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    assert resolve_projects_path(tmp_path / ".omlx") == (
        tmp_path / ".ai2apps" / "projects"
    ).resolve()


def test_project_root_can_be_overridden(monkeypatch, tmp_path):
    override = tmp_path / "source-projects"
    monkeypatch.setenv("AI2APPS_PROJECTS_DIR", str(override))

    assert resolve_projects_path(tmp_path / "data") == override.resolve()


def test_standalone_platform_health_has_stable_bootstrap_contract():
    response = TestClient(_standalone_app()).get("/v1/platform/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["product"] == "ai2apps"
    assert body["api_version"] == "v1"
    assert body["version"]
    assert body["runtime"] == {"provider": "omlx", "attached": True}
    assert body["database"] == {
        "configured": False,
        "status": "unconfigured",
        "schema_version": 0,
        "target_schema_version": PLATFORM_DATABASE_SCHEMA_VERSION,
        "filename": PLATFORM_DATABASE_FILENAME,
        "journal_mode": None,
    }


def test_embedded_platform_health_uses_existing_omlx_data_root(tmp_path):
    from omlx.server import ServerState, app

    state = ServerState(global_settings=SimpleNamespace(base_path=tmp_path))

    with patch("omlx.server._server_state", state):
        response = TestClient(app).get("/v1/platform/health")

    assert response.status_code == 200
    assert response.json()["database"] == {
        "configured": True,
        "status": "not_initialized",
        "schema_version": 0,
        "target_schema_version": PLATFORM_DATABASE_SCHEMA_VERSION,
        "filename": PLATFORM_DATABASE_FILENAME,
        "journal_mode": None,
    }
    assert not (tmp_path / "platform").exists()


def test_embedded_platform_router_reuses_existing_api_key_authentication():
    from omlx.server import ServerState, app

    state = ServerState(api_key="platform-secret")

    with patch("omlx.server._server_state", state):
        client = TestClient(app)
        unauthorized = client.get("/v1/platform/health")
        authorized = client.get(
            "/v1/platform/health",
            headers={"Authorization": "Bearer platform-secret"},
        )

    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "authentication_required"
    assert authorized.status_code == 200


def test_embedded_platform_validation_uses_platform_error_envelope(tmp_path):
    from omlx.server import ServerState, app

    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    state = ServerState(ai2apps_platform_runtime=runtime)
    with patch("omlx.server._server_state", state):
        response = TestClient(app).get(
            "/v1/platform/app-instances/appi_missing/sessions",
            params={"limit": 0},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_platform_health_is_published_in_openapi_schema():
    schema = _standalone_app().openapi()

    operation = schema["paths"]["/v1/platform/health"]["get"]
    assert operation["tags"] == ["platform"]
    assert "200" in operation["responses"]


def test_platform_error_response_has_stable_machine_readable_envelope():
    response = platform_error_response(
        status_code=409,
        code="resource_conflict",
        message="The resource already exists.",
        details={"resource_id": "example"},
    )

    assert response.status_code == 409
    assert json.loads(response.body) == {
        "error": {
            "code": "resource_conflict",
            "message": "The resource already exists.",
            "retryable": False,
            "details": {"resource_id": "example"},
        }
    }
