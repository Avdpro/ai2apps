"""Bonjour/mDNS publication and discovery for LAN AI2Apps gateways."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import socket
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf

from .models import LocalNetworkAccess
from .network import discover_lan_host


SERVICE_TYPE = "_ai2apps-gateway._tcp.local."
DISCOVERY_SCHEMA = "ai2apps.gateway/v1"


def _text(value: bytes | str | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def stable_gateway_id(database_path: str | Path) -> str:
    """Derive a non-secret, stable advertisement id for one Local instance."""
    digest = hashlib.sha256(str(Path(database_path).resolve()).encode("utf-8")).hexdigest()
    return digest[:16]


@dataclass(slots=True)
class DiscoveredGateway:
    service_name: str
    gateway_id: str
    label: str
    host: str
    address: str
    port: int
    mode: str
    schema: str
    last_seen_at: str

    def as_dict(self) -> dict[str, Any]:
        host = f"[{self.address}]" if ":" in self.address else self.address
        return {
            "service_name": self.service_name,
            "gateway_id": self.gateway_id,
            "label": self.label,
            "host": self.host,
            "address": self.address,
            "port": self.port,
            "mode": self.mode,
            "schema": self.schema,
            "openai_base_url": f"http://{host}:{self.port}/v1/share/openai/v1",
            "mcp_url": f"http://{host}:{self.port}/v1/share/mcp",
            "last_seen_at": self.last_seen_at,
        }


class GatewayDiscovery(ServiceListener):
    """Best-effort process-local mDNS browser and publisher.

    TXT records deliberately contain endpoint metadata only. Grant tokens never
    enter Bonjour packets and must still be transferred using the one-use QR or
    connection JSON shown by the upstream Core user.
    """

    def __init__(self, *, gateway_id: str, label: str | None = None) -> None:
        self.gateway_id = gateway_id
        self.label = (label or socket.gethostname() or "AI2Apps Local")[:63]
        self.service_name = f"AI2Apps-{gateway_id}.{SERVICE_TYPE}"
        self._zeroconf: Zeroconf | None = None
        self._browser: ServiceBrowser | None = None
        self._published: ServiceInfo | None = None
        self._items: dict[str, DiscoveredGateway] = {}
        self._lock = threading.RLock()
        self._lifecycle_lock = asyncio.Lock()
        self._error: str | None = None

    async def start(self) -> None:
        async with self._lifecycle_lock:
            if self._zeroconf is not None:
                return
            try:
                await asyncio.to_thread(self._start_sync)
                self._error = None
            except Exception as exc:  # discovery must never block Local startup
                self._error = str(exc)

    def _start_sync(self) -> None:
        zeroconf = Zeroconf()
        browser = ServiceBrowser(zeroconf, SERVICE_TYPE, self)
        self._zeroconf = zeroconf
        self._browser = browser

    async def apply(self, settings: LocalNetworkAccess) -> None:
        await self.start()
        async with self._lifecycle_lock:
            try:
                await asyncio.to_thread(self._apply_sync, settings)
                self._error = None
            except Exception as exc:  # LAN listener remains useful without mDNS
                self._error = str(exc)

    def _apply_sync(self, settings: LocalNetworkAccess) -> None:
        zeroconf = self._zeroconf
        if zeroconf is None:
            return
        if self._published is not None:
            zeroconf.unregister_service(self._published)
            self._published = None
        if settings.mode == "disabled":
            return
        address = discover_lan_host("127.0.0.1", settings.bind_host)
        try:
            packed = ipaddress.ip_address(address.split("%", 1)[0]).packed
        except ValueError:
            return
        info = ServiceInfo(
            SERVICE_TYPE,
            self.service_name,
            addresses=[packed],
            port=settings.port,
            properties={
                "schema": DISCOVERY_SCHEMA,
                "gateway_id": self.gateway_id,
                "label": self.label,
                "mode": settings.mode,
                "openai_path": "/v1/share/openai/v1",
                "mcp_path": "/v1/share/mcp",
            },
            server=f"ai2apps-{self.gateway_id}.local.",
        )
        zeroconf.register_service(info, allow_name_change=False)
        self._published = info

    async def refresh(self, wait_seconds: float = 1.25) -> dict[str, Any]:
        await self.start()
        await asyncio.sleep(max(0.0, min(wait_seconds, 3.0)))
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            items = sorted(
                (item.as_dict() for item in self._items.values()),
                key=lambda item: (item["label"].casefold(), item["gateway_id"]),
            )
        return {"available": self._zeroconf is not None, "error": self._error, "items": items}

    def add_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        self._resolve(zeroconf, service_type, name)

    def update_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        self._resolve(zeroconf, service_type, name)

    def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        with self._lock:
            self._items.pop(name, None)

    def _resolve(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        if name == self.service_name:
            return
        info = zeroconf.get_service_info(service_type, name, timeout=1500)
        if info is None:
            return
        properties = {_text(key): _text(value) for key, value in info.properties.items()}
        if properties.get("schema") != DISCOVERY_SCHEMA:
            return
        addresses = info.parsed_scoped_addresses()
        if not addresses:
            return
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        item = DiscoveredGateway(
            service_name=name,
            gateway_id=properties.get("gateway_id", ""),
            label=properties.get("label") or name.removesuffix("." + SERVICE_TYPE),
            host=(info.server or "").rstrip("."),
            address=addresses[0],
            port=int(info.port),
            mode=properties.get("mode", "share_only"),
            schema=properties["schema"],
            last_seen_at=now,
        )
        with self._lock:
            self._items[name] = item

    async def close(self) -> None:
        async with self._lifecycle_lock:
            await asyncio.to_thread(self._close_sync)

    def _close_sync(self) -> None:
        zeroconf = self._zeroconf
        if zeroconf is None:
            return
        if self._published is not None:
            try:
                zeroconf.unregister_service(self._published)
            except Exception:
                pass
        if self._browser is not None:
            self._browser.cancel()
        zeroconf.close()
        self._published = None
        self._browser = None
        self._zeroconf = None
