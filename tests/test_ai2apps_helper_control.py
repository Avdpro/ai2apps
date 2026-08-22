from __future__ import annotations

import json
import socket
import tempfile
import threading
from pathlib import Path

import pytest

from ai2apps.helper_control import HelperControlClient, HelperControlError


def _tcp_listener(endpoint_path: Path) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    endpoint_path.write_text(
        json.dumps({"version": 1, "host": "127.0.0.1", "port": listener.getsockname()[1]})
    )
    return listener


def test_helper_control_client_round_trips_authenticated_request() -> None:
    temporary_directory = tempfile.TemporaryDirectory(dir="/tmp")
    endpoint_path = Path(temporary_directory.name) / "helper-control.json"
    listener = _tcp_listener(endpoint_path)
    captured: dict[str, object] = {}

    def serve() -> None:
        with listener, listener.accept()[0] as connection:
            request = json.loads(connection.recv(65536).split(b"\n", 1)[0])
            captured.update(request)
            response = {
                "request_id": request["request_id"],
                "ok": True,
                "result": {
                    "status": "launched",
                    "profile_id": "a" * 64,
                    "pid": 42,
                    "automation": {
                        "transport": "webdriver-bidi",
                        "web_socket_url": "ws://127.0.0.1:49152/session",
                        "authorization": "Bearer " + "c" * 64,
                    },
                },
            }
            connection.sendall(json.dumps(response).encode() + b"\n")

    thread = threading.Thread(target=serve)
    thread.start()
    client = HelperControlClient(str(endpoint_path), "b" * 64)
    result = client.launch_browser_agent(
        actor_user_id="user-123",
        initial_url="https://example.com/",
    )
    thread.join(timeout=2)
    temporary_directory.cleanup()

    assert result["pid"] == 42
    assert result["automation"]["transport"] == "webdriver-bidi"
    assert captured["token"] == "b" * 64
    assert captured["actor_user_id"] == "user-123"


def test_helper_control_client_rejects_unsafe_url() -> None:
    client = HelperControlClient("/tmp/missing-helper-control.json", "b" * 64)
    with pytest.raises(HelperControlError, match="http or https"):
        client.launch_browser_agent(actor_user_id="user-123", initial_url="file:///etc/passwd")


def test_helper_control_client_releases_actor_without_automation_secret() -> None:
    temporary_directory = tempfile.TemporaryDirectory(dir="/tmp")
    endpoint_path = Path(temporary_directory.name) / "helper-control.json"
    listener = _tcp_listener(endpoint_path)
    captured: dict[str, object] = {}

    def serve() -> None:
        with listener, listener.accept()[0] as connection:
            request = json.loads(connection.recv(65536).split(b"\n", 1)[0])
            captured.update(request)
            response = {
                "request_id": request["request_id"],
                "ok": True,
                "result": {
                    "status": "released",
                    "profile_id": "a" * 64,
                    "pid": 42,
                },
            }
            connection.sendall(json.dumps(response).encode() + b"\n")

    thread = threading.Thread(target=serve)
    thread.start()
    client = HelperControlClient(str(endpoint_path), "b" * 64)
    result = client.release_browser_agent(actor_user_id="user-123")
    thread.join(timeout=2)
    temporary_directory.cleanup()

    assert result == {"status": "released", "profile_id": "a" * 64, "pid": 42}
    assert captured["operation"] == "browser.release"
    assert captured["actor_user_id"] == "user-123"


def test_helper_control_client_requests_local_restart_without_secrets() -> None:
    temporary_directory = tempfile.TemporaryDirectory(dir="/tmp")
    endpoint_path = Path(temporary_directory.name) / "helper-control.json"
    listener = _tcp_listener(endpoint_path)
    captured: dict[str, object] = {}

    def serve() -> None:
        with listener, listener.accept()[0] as connection:
            request = json.loads(connection.recv(65536).split(b"\n", 1)[0])
            captured.update(request)
            response = {
                "request_id": request["request_id"],
                "ok": True,
                "result": {"status": "restarting"},
            }
            connection.sendall(json.dumps(response).encode() + b"\n")

    thread = threading.Thread(target=serve)
    thread.start()
    client = HelperControlClient(str(endpoint_path), "b" * 64)
    result = client.restart_local(actor_user_id="user-123")
    thread.join(timeout=2)
    temporary_directory.cleanup()

    assert result == {"status": "restarting"}
    assert captured["operation"] == "local.restart"
    assert captured["actor_user_id"] == "user-123"
    assert captured["token"] == "b" * 64


def test_helper_control_client_rejects_release_automation_secret() -> None:
    with pytest.raises(HelperControlError, match="leaked automation"):
        HelperControlClient._validate_browser_release_result(
            {
                "status": "released",
                "profile_id": "a" * 64,
                "pid": 42,
                "automation": {"authorization": "Bearer " + "c" * 64},
            }
        )


def test_helper_control_client_rejects_non_loopback_automation_endpoint() -> None:
    result = {
        "status": "launched",
        "profile_id": "a" * 64,
        "pid": 42,
        "automation": {
            "transport": "webdriver-bidi",
            "web_socket_url": "ws://example.com:49152/session",
            "authorization": "Bearer " + "c" * 64,
        },
    }
    with pytest.raises(HelperControlError, match="not safe"):
        HelperControlClient._validate_browser_agent_result(result)


@pytest.mark.parametrize("status", ["renewed", "paused", "resumed"])
def test_helper_control_client_validates_secret_free_lease_response(status: str) -> None:
    HelperControlClient._validate_browser_lease_result(
        {
            "status": status,
            "profile_id": "a" * 64,
            "pid": 42,
        },
        expected_status=status,
    )

    with pytest.raises(HelperControlError, match="leaked automation"):
        HelperControlClient._validate_browser_lease_result(
            {
                "status": status,
                "profile_id": "a" * 64,
                "pid": 42,
                "automation": {"authorization": "Bearer " + "c" * 64},
            },
            expected_status=status,
        )
