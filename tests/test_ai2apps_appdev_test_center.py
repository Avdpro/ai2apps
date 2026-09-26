from unittest.mock import patch
import ast
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.client import create_client_router


def test_full_native_auth_boundary(monkeypatch):
    # Execute the real server guard without importing its Metal runtime.
    from fastapi import Depends, HTTPException
    from starlette.requests import HTTPConnection
    from ai2apps.identity import RequestPrincipal
    source = Path(__file__).resolve().parents[1] / "omlx/server.py"
    tree = ast.parse(source.read_text())
    guard = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "verify_ai2apps_platform_access")
    namespace = {"HTTPConnection": HTTPConnection, "RequestPrincipal": RequestPrincipal, "HTTPException": HTTPException, "get_ai2apps_platform_runtime": lambda: None}
    exec(compile(ast.Module(body=[guard], type_ignores=[]), str(source), "exec"), namespace)
    app = FastAPI()
    app.include_router(create_client_router(), prefix="/v1/platform", dependencies=[Depends(namespace[guard.name])])
    client = TestClient(app)
    monkeypatch.setenv("AI2APPS_HELPER_TOKEN", "a" * 64)
    monkeypatch.setenv("AI2APPS_ALLOW_DEVELOPMENT_RUNTIME", "1")
    path = "/v1/platform/client/app-dev-test-environment"
    payload = {"initial_url": "http://127.0.0.1:12345/#example"}
    headers = {"Authorization": "Bearer " + "a" * 64}
    with patch("ai2apps.api.client.current_supervised_instance_id", return_value="app-dev"), patch("ai2apps.api.client.shell_browser_window_broker.enqueue", return_value="request"), patch("ai2apps.api.client.shell_browser_window_broker.wait", return_value={"status": "launched"}):
        assert client.post(path, json=payload, headers=headers).status_code == 200
        assert client.post(path, json=payload).status_code == 401
        assert client.post(path, json=payload, headers={**headers, "Origin": "http://127.0.0.1:12345"}).status_code == 401


def test_test_center_requires_helper_and_appdev(monkeypatch):
    monkeypatch.setenv("AI2APPS_HELPER_TOKEN", "a" * 64)
    monkeypatch.setenv("AI2APPS_ALLOW_DEVELOPMENT_RUNTIME", "1")
    app = FastAPI()
    app.include_router(create_client_router())
    client = TestClient(app)
    path = "/client/app-dev-test-environment"
    payload = {"initial_url": "http://127.0.0.1:12345/#example"}
    assert client.post(path, json=payload).status_code == 401
    headers = {"Authorization": "Bearer " + "a" * 64}
    for instance in ("test", "dev", "default"):
        with patch("ai2apps.api.client.current_supervised_instance_id", return_value=instance):
            assert client.post(path, json=payload, headers=headers).status_code == 403
    with patch("ai2apps.api.client.current_supervised_instance_id", return_value="app-dev"), patch("ai2apps.api.client.shell_browser_window_broker.enqueue", return_value="request") as enqueue, patch("ai2apps.api.client.shell_browser_window_broker.wait", return_value={"status": "launched"}):
        assert client.post(path, json=payload, headers=headers).status_code == 200
        assert enqueue.call_args.kwargs["profile_name"] == "Test Center"
        for url in ("https://example.com/#x", "http://localhost:123/#x", "http://127.0.0.1:123/", "http://u:p@127.0.0.1:123/#x"):
            assert client.post(path, json={"initial_url": url}, headers=headers).status_code == 422
        monkeypatch.setenv("AI2APPS_ALLOW_DEVELOPMENT_RUNTIME", "0")
        assert client.post(path, json=payload, headers=headers).status_code == 403
