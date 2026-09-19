import pytest
import json
from types import SimpleNamespace
from scripts import registry_browser_session as live

SECURITY_ID = "local_" + "a" * 32

from scripts.registry_browser_session import select_session_cookie, live_browser_session_namespace


def cookie(**changes):
    return {"name": "scoped", "domain": "127.0.0.1", "path": "/",
            "value": {"type": "string", "value": "private-session"}, **changes}


def test_exact_cookie_only():
    assert select_session_cookie({"cookies": [cookie(), cookie(name="unrelated")]}, "scoped") == "browser:private-session"


@pytest.mark.parametrize("cookies", [[], [cookie(), cookie()], [cookie(domain="other")],
                                       [cookie(path="/other")], [cookie(value={"type": "base64", "value": "secret"})],
                                       [cookie(value={"type": "string", "value": ""})]])
def test_rejects_ambiguous_or_wrong_scope(cookies):
    with pytest.raises(ValueError) as error:
        select_session_cookie({"cookies": cookies}, "scoped")
    assert "private-session" not in str(error.value)


@pytest.mark.asyncio
async def test_failure_is_sanitized_without_fallback(tmp_path):
    with pytest.raises(RuntimeError) as error:
        await live_browser_session_namespace(tmp_path, "local_test")
    assert error.value.__suppress_context__
    assert "no database fallback" in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("wrong_profile", [False, True])
async def test_live_cookie_uses_exact_profile_and_filtered_bidi(tmp_path, monkeypatch, wrong_profile):
    base = tmp_path / "dev" / "data"
    base.mkdir(parents=True)
    run = base.parent / "run"
    run.mkdir()
    (run / "local.json").write_text(json.dumps({"actual_port": 54321, "instance_id": "dev"}))
    profile = base.parent / "browser-profiles" / ("other" if wrong_profile else "app-shell")
    calls = []

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url):
            assert url == "http://127.0.0.1:54321/v1/platform/client/bootstrap"
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"installation_id": SECURITY_ID, "instance_id": "dev"})

    async def ensure(self, endpoint, connector):
        assert self._state_path() == run / "shell-bidi-session.json"
        return SimpleNamespace(capabilities={"moz:profile": str(profile)}, web_socket_url="ws://127.0.0.1:54322/session/existing")

    class Socket:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass

    def connector(url, **kwargs):
        assert kwargs["additional_headers"] == {"Authorization": "Bearer private"}
        assert kwargs["proxy"] is None
        return Socket()

    async def command(socket, command_id, method, params):
        calls.append(method)
        assert params == {"filter": {"name": live.cloud_browser_cookie_name(SECURITY_ID), "domain": "127.0.0.1", "path": "/"}, "partition": {"type": "storageKey", "userContext": "default"}}
        return {"cookies": [cookie(name=params["filter"]["name"])]}

    monkeypatch.setattr(live.httpx, "AsyncClient", Client)
    monkeypatch.setattr(live.ShellBiDiEndpoint, "load", lambda path: SimpleNamespace(authorization="Bearer private"))
    monkeypatch.setattr(live.ShellBiDiSessionBroker, "ensure", ensure)
    monkeypatch.setattr(live, "connect", connector)
    monkeypatch.setattr(live, "_bootstrap_command", command)
    if wrong_profile:
        with pytest.raises(RuntimeError, match="Profile validation"):
            await live.live_browser_session_namespace(base, SECURITY_ID)
        assert calls == []
    else:
        assert await live.live_browser_session_namespace(base, SECURITY_ID) == "browser:private-session"
        assert calls == ["storage.getCookies"]
