from __future__ import annotations

import pytest

import ai2apps.browser.acefox as acefox_module
from ai2apps.browser.acefox import AceFoxBrowserBackend, _local_value, _remote_value
from ai2apps.browser.models import BrowserRuntimeConfig


def test_acefox_bidi_value_conversion_round_trips_json_values() -> None:
    value = {"name": "AI2Apps", "ready": True, "ports": [49152, None]}
    assert _remote_value(_local_value(value)) == value


def test_acefox_stop_releases_the_actor_managed_agent() -> None:
    class FakeConnection:
        closed = False

        def close(self) -> None:
            self.closed = True

    class FakeHelper:
        released_actor: str | None = None

        def release_browser_agent(self, *, actor_user_id: str):
            self.released_actor = actor_user_id
            return {"status": "released", "profile_id": "a" * 64, "pid": 42}

    helper = FakeHelper()
    connection = FakeConnection()
    backend = AceFoxBrowserBackend(
        BrowserRuntimeConfig(profile_path="/tmp/unused"),
        helper_provider=lambda: helper,
    )
    backend.connection = connection  # type: ignore[assignment]
    backend._actor_user_id = "user-123"
    backend._active_context = "tab-1"

    backend.stop()

    assert connection.closed is True
    assert helper.released_actor == "user-123"
    assert backend.connection is None
    assert backend._actor_user_id is None


def test_acefox_failed_bidi_start_releases_the_actor_managed_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConnection:
        closed = False

        def __init__(self, endpoint: object) -> None:
            pass

        def connect(self) -> None:
            raise ConnectionError("not ready")

        def close(self) -> None:
            self.closed = True

    class FakeHelper:
        released_actor: str | None = None

        def launch_browser_agent(self, *, actor_user_id: str):
            return {
                "status": "launched",
                "profile_id": "a" * 64,
                "pid": 42,
                "automation": {
                    "transport": "webdriver-bidi",
                    "web_socket_url": "ws://127.0.0.1:49152/session",
                    "authorization": f"Bearer {'b' * 64}",
                },
            }

        def release_browser_agent(self, *, actor_user_id: str):
            self.released_actor = actor_user_id
            return {"status": "released", "profile_id": "a" * 64, "pid": 42}

    helper = FakeHelper()
    monkeypatch.setattr(acefox_module, "AceFoxBiDiConnection", FakeConnection)
    backend = AceFoxBrowserBackend(
        BrowserRuntimeConfig(
            profile_path="/tmp/unused",
            page_load_timeout_seconds=0.0,
        ),
        helper_provider=lambda: helper,
    )

    with pytest.raises(ConnectionError, match="not ready"):
        backend.start_for_actor("user-123")

    assert helper.released_actor == "user-123"
    assert backend.connection is None
    assert backend._actor_user_id is None
