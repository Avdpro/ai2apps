from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.client import create_client_router
from ai2apps.platform_runtime import PlatformDatabaseStatus


def test_bootstrap_reports_supervised_instance_and_boot(monkeypatch) -> None:
    boot_id = uuid4()
    monkeypatch.setenv("AI2APPS_INSTANCE_ID", "customer-a")
    monkeypatch.setenv("AI2APPS_BOOT_ID", str(boot_id))
    monkeypatch.setattr("ai2apps.api.client._hardware_device_name", lambda: "")
    monkeypatch.setattr("ai2apps.api.client.platform.node", lambda: "MyMacBook")
    runtime = SimpleNamespace(
        database_status=PlatformDatabaseStatus(
            configured=True,
            status="ready",
            schema_version=35,
            target_schema_version=35,
            filename="ai2apps-platform.sqlite3",
            journal_mode="wal",
        ),
        security_identity=SimpleNamespace(security_instance_id="local_" + "a" * 32),
        browser=object(),
    )
    app = FastAPI()
    app.include_router(
        create_client_router(lambda: runtime),
        prefix="/v1/platform",
    )

    response = TestClient(app).get("/v1/platform/client/bootstrap")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["instance_id"] == "customer-a"
    assert payload["installation_id"] == "local_" + "a" * 32
    assert payload["device_name"] == "MyMacBook"
    assert payload["boot_id"] == str(boot_id)
    assert payload["shell_path"] == "/v1/platform/client/shell"
    assert payload["capabilities"] == ["shell", "browser.agent"]


def test_bootstrap_stays_starting_before_runtime_is_ready(monkeypatch) -> None:
    monkeypatch.delenv("AI2APPS_INSTANCE_ID", raising=False)
    monkeypatch.delenv("AI2APPS_BOOT_ID", raising=False)
    monkeypatch.setattr(
        "ai2apps.api.client._hardware_device_name", lambda: "M5Max-128G"
    )
    app = FastAPI()
    app.include_router(create_client_router(lambda: None), prefix="/v1/platform")

    response = TestClient(app).get("/v1/platform/client/bootstrap")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "starting"
    assert payload["instance_id"] == "unconfigured"
    assert payload["installation_id"] is None
    assert payload["device_name"] == "M5Max-128G"
    assert payload["capabilities"] == ["shell"]


def test_bootstrap_falls_back_to_hostname_when_hardware_is_unknown(monkeypatch) -> None:
    monkeypatch.setattr("ai2apps.api.client._hardware_device_name", lambda: "")
    monkeypatch.setattr("ai2apps.api.client.platform.node", lambda: "MyMacBook")
    app = FastAPI()
    app.include_router(create_client_router(lambda: None), prefix="/v1/platform")

    payload = TestClient(app).get("/v1/platform/client/bootstrap").json()

    assert payload["device_name"] == "MyMacBook"


def test_hardware_device_name_compacts_chip_and_memory(monkeypatch) -> None:
    monkeypatch.setattr("omlx.utils.hardware.get_chip_name", lambda: "Apple M5 Max")
    monkeypatch.setattr("omlx.utils.hardware.get_total_memory_gb", lambda: 128.0)

    from ai2apps.api.client import _hardware_device_name

    assert _hardware_device_name() == "M5Max-128G"


def test_login_uses_local_bootstrap_device_name_instead_of_browser_platform() -> None:
    repository = Path(__file__).resolve().parents[1]
    script = (repository / "ai2apps/web/static/js/login.js").read_text()

    assert 'json("/v1/platform/client/bootstrap")' in script
    assert "navigator.platform" not in script


def test_bootstrap_uses_registered_device_display_name(monkeypatch) -> None:
    monkeypatch.setenv("AI2APPS_INSTANCE_ID", "customer-a")
    monkeypatch.setenv("AI2APPS_BOOT_ID", str(uuid4()))
    installation = SimpleNamespace(cloud_device_id="device-a")
    database = object()
    remote = SimpleNamespace(
        require_device=lambda device_id: SimpleNamespace(
            display_name="  Living   Room Mac  "
        )
    )
    runtime = SimpleNamespace(
        database_status=PlatformDatabaseStatus(
            configured=True,
            status="ready",
            schema_version=35,
            target_schema_version=35,
            filename="ai2apps-platform.sqlite3",
            journal_mode="wal",
        ),
        security_identity=SimpleNamespace(security_instance_id="local_" + "a" * 32),
        browser=None,
        database=database,
        remote=remote,
    )
    monkeypatch.setattr(
        "ai2apps.api.client.IdentityRepository",
        lambda value: SimpleNamespace(get_installation=lambda: installation),
    )
    app = FastAPI()
    app.include_router(create_client_router(lambda: runtime), prefix="/v1/platform")

    payload = TestClient(app).get("/v1/platform/client/bootstrap").json()

    assert payload["device_name"] == "Living Room Mac"


def test_desktop_shell_session_requires_helper_credential(monkeypatch) -> None:
    monkeypatch.setenv("AI2APPS_INSTANCE_ID", "desktop-a")
    monkeypatch.setenv("AI2APPS_BOOT_ID", str(uuid4()))
    monkeypatch.setenv("AI2APPS_HELPER_TOKEN", "a" * 64)
    app = FastAPI()
    app.include_router(create_client_router(lambda: None), prefix="/v1/platform")
    client = TestClient(app)

    rejected = client.post(
        "/v1/platform/client/shell-session",
        headers={"Authorization": f"Bearer {'b' * 64}"},
    )
    assert rejected.status_code == 401

    established = client.post(
        "/v1/platform/client/shell-session",
        headers={"Authorization": f"Bearer {'a' * 64}"},
    )
    assert established.status_code == 200
    shell_session = established.json()
    assert shell_session["shell_path"] == "/v1/platform/client/shell"
    assert shell_session["cookie_name"].startswith("ai2apps_desktop_shell_")
    assert "." in shell_session["cookie_value"]
    assert shell_session["expires_at_ms"] > 0
    assert "ai2apps_desktop_shell_" in established.headers["set-cookie"]
    assert "HttpOnly" in established.headers["set-cookie"]
    assert "SameSite=strict" in established.headers["set-cookie"]

    entry = client.get("/v1/platform/client/shell", follow_redirects=False)
    assert entry.status_code == 303
    assert entry.headers["location"] == "/"


def test_desktop_shell_session_rejects_browser_origin(monkeypatch) -> None:
    monkeypatch.setenv("AI2APPS_INSTANCE_ID", "desktop-a")
    monkeypatch.setenv("AI2APPS_BOOT_ID", str(uuid4()))
    monkeypatch.setenv("AI2APPS_HELPER_TOKEN", "a" * 64)
    app = FastAPI()
    app.include_router(create_client_router(lambda: None), prefix="/v1/platform")

    response = TestClient(app).post(
        "/v1/platform/client/shell-session",
        headers={
            "Authorization": f"Bearer {'a' * 64}",
            "Origin": "http://127.0.0.1:8000",
        },
    )
    assert response.status_code == 401


def test_managed_browser_empty_poll_is_privileged_json(monkeypatch) -> None:
    monkeypatch.setenv("AI2APPS_HELPER_TOKEN", "a" * 64)
    app = FastAPI()
    app.include_router(create_client_router(lambda: None), prefix="/v1/platform")

    response = TestClient(app).get(
        "/v1/platform/client/managed-browser/next",
        headers={"Authorization": f"Bearer {'a' * 64}"},
    )

    assert response.status_code == 200
    assert response.json() is None
    assert response.headers["cache-control"] == "no-store"
