"""LAN discovery advertises endpoints without sharing credentials."""

from ai2apps.core import utc_now
from ai2apps.sharing.discovery import DISCOVERY_SCHEMA, GatewayDiscovery, SERVICE_TYPE
from ai2apps.sharing.models import LocalNetworkAccess


class _Info:
    properties = {
        b"schema": DISCOVERY_SCHEMA.encode(),
        b"gateway_id": b"remote-gateway",
        b"label": b"Family NAS",
        b"mode": b"share_only",
    }
    server = "remote.local."
    port = 8011

    @staticmethod
    def parsed_scoped_addresses():
        return ["192.168.1.22"]


class _Resolver:
    @staticmethod
    def get_service_info(*_args, **_kwargs):
        return _Info()


def _settings(mode: str = "share_only") -> LocalNetworkAccess:
    now = utc_now()
    return LocalNetworkAccess(
        mode=mode, bind_host="0.0.0.0", port=8011, revision=1,
        updated_by_user_id="core", created_at=now, updated_at=now,
    )


def test_discovery_projection_contains_no_credentials():
    discovery = GatewayDiscovery(gateway_id="local-gateway", label="This Mac")
    discovery._resolve(_Resolver(), SERVICE_TYPE, "Remote." + SERVICE_TYPE)

    item = discovery.snapshot()["items"][0]
    assert item["label"] == "Family NAS"
    assert item["openai_base_url"] == "http://192.168.1.22:8011/v1/share/openai/v1"
    assert item["mcp_url"] == "http://192.168.1.22:8011/v1/share/mcp"
    assert "token" not in str(item).lower()


def test_discovery_ignores_its_own_advertisement():
    discovery = GatewayDiscovery(gateway_id="local-gateway", label="This Mac")
    discovery._resolve(_Resolver(), SERVICE_TYPE, discovery.service_name)
    assert discovery.snapshot()["items"] == []


def test_disabled_network_does_not_publish(monkeypatch):
    calls = []

    class FakeZeroconf:
        def register_service(self, info, **_kwargs): calls.append(("register", info))
        def unregister_service(self, info): calls.append(("unregister", info))

    discovery = GatewayDiscovery(gateway_id="local-gateway", label="This Mac")
    discovery._zeroconf = FakeZeroconf()
    monkeypatch.setattr("ai2apps.sharing.discovery.discover_lan_host", lambda *_args: "192.168.1.20")
    discovery._apply_sync(_settings())
    assert calls[0][0] == "register"
    assert b"token" not in repr(calls[0][1].properties).lower().encode()

    discovery._apply_sync(_settings("disabled"))
    assert calls[-1][0] == "unregister"
