from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import ai2apps.api.client as client_module
from ai2apps.api.client import create_client_router
from ai2apps.browser.profiles import BrowserProfileRepository
from ai2apps.browser.shell_window import (
    ShellBrowserWindowBroker,
    shell_browser_profile_key,
)
from ai2apps.identity import RequestPrincipal
from ai2apps.storage import PlatformDatabase


def test_browser_profile_repository_keeps_default_virtual_and_user_scoped(tmp_path) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    repository = BrowserProfileRepository(database)

    created = repository.create("user-1", "  Work   Account  ")
    assert created.name == "Work Account"
    assert [profile.key for profile in repository.list_for_user("user-2")] == ["default"]
    assert [profile.key for profile in repository.list_for_user("user-1")] == [
        "default",
        created.key,
    ]


def test_ai_browser_api_launches_and_deletes_exact_owned_profile(
    tmp_path, monkeypatch
) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    shell_calls = []
    monkeypatch.setattr(
        client_module,
        "_request_shell_browser_action",
        lambda actor, profile, profile_name, is_default, action, url: shell_calls.append(
            (actor, profile, profile_name, is_default, action, url)
        )
        or {
            "status": "deleted" if action == "delete" else "launched",
            "profile_id": profile,
            "pid": 42,
        },
    )
    principal = RequestPrincipal.legacy_local()
    app = FastAPI()
    app.include_router(
        create_client_router(
            runtime_provider=lambda: SimpleNamespace(database=database, browser=object()),
            principal_provider=lambda: principal,
        ),
        prefix="/v1/platform",
    )
    client = TestClient(app)

    initial = client.get("/v1/platform/client/browser-profiles")
    assert initial.status_code == 200
    assert initial.json() == [
        {"key": "default", "name": "Default", "is_default": True, "created_at": None}
    ]

    created = client.post(
        "/v1/platform/client/browser-profiles", json={"name": "Research"}
    )
    assert created.status_code == 201
    profile_key = created.json()["key"]

    launched = client.post(
        f"/v1/platform/client/browser-profiles/{profile_key}/launch", json={}
    )
    assert launched.status_code == 200
    assert shell_calls == [
        (principal.actor_user_id, profile_key, "Research", False, "open", None)
    ]

    deleted = client.delete(
        f"/v1/platform/client/browser-profiles/{profile_key}"
    )
    assert deleted.status_code == 204
    assert shell_calls[-1] == (
        principal.actor_user_id,
        profile_key,
        "Research",
        False,
        "delete",
        None,
    )
    assert [item["key"] for item in client.get(
        "/v1/platform/client/browser-profiles"
    ).json()] == ["default"]


def test_ai_browser_api_never_deletes_default_profile(tmp_path) -> None:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    deleted_calls = []
    app = FastAPI()
    app.include_router(
        create_client_router(
            runtime_provider=lambda: SimpleNamespace(database=database, browser=object()),
            principal_provider=RequestPrincipal.legacy_local,
        ),
        prefix="/v1/platform",
    )
    response = TestClient(app).delete(
        "/v1/platform/client/browser-profiles/default"
    )
    assert response.status_code == 409
    assert deleted_calls == []


def test_shell_browser_profile_keys_are_stable_and_user_scoped() -> None:
    default = shell_browser_profile_key("user-1", "default")
    custom = shell_browser_profile_key("user-1", "a" * 32)
    assert len(default) == 64
    assert default == shell_browser_profile_key("user-1", "default")
    assert custom != default
    assert custom != shell_browser_profile_key("user-2", "a" * 32)


def test_shell_browser_broker_returns_native_shell_result() -> None:
    broker = ShellBrowserWindowBroker()
    request_id = broker.enqueue(
        action="open",
        profile_key="a" * 64,
        profile_name="Research",
        is_default=False,
        initial_url="https://example.com/",
    )
    assert broker.claim_next() == {
        "request_id": request_id,
        "action": "open",
        "profile_key": "a" * 64,
        "profile_name": "Research",
        "is_default": False,
        "initial_url": "https://example.com/",
    }
    broker.finish(request_id, status="focused", pid=42)
    assert broker.wait(request_id) == {"status": "focused", "pid": 42}
