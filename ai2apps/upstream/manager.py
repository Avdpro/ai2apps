"""Secure downstream connections to explicitly shared upstream capabilities."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from ai2apps.core import parse_utc, utc_now, utc_now_text
from ai2apps.secrets import SecretBackend
from ai2apps.services.models import ServiceInstanceStatus, ServiceRuntimeMode, ServiceStatus, ToolCallContext, ToolProviderError
from ai2apps.services.registry import ServiceRegistry
from ai2apps.services.repository import ServiceRepository
from ai2apps.storage import PlatformDatabase

from .models import UpstreamGateway, UpstreamRouting
from .transport import (
    CloudRelayParentTransport, DirectParentTransport, ParentCallContext,
    ParentModelResponse, ParentTransport,
)


class UpstreamGatewayError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class UpstreamGatewayManager:
    def __init__(
        self,
        database: PlatformDatabase,
        secret_backend: SecretBackend,
        service_repository: ServiceRepository | None = None,
        service_registry: ServiceRegistry | None = None,
        local_node_id: str | None = None,
        transport: ParentTransport | None = None,
    ) -> None:
        self.database = database
        self.secret_backend = secret_backend
        self.service_repository = service_repository
        self.service_registry = service_registry
        self.local_node_id = local_node_id
        self.transports: dict[str, ParentTransport] = {
            "direct": transport or DirectParentTransport(),
            "cloud_relay": CloudRelayParentTransport(),
        }
        self._health_task: asyncio.Task[None] | None = None
        self._health_stop: asyncio.Event | None = None

    @staticmethod
    def _id() -> str:
        return "upg_" + secrets.token_hex(16)

    @staticmethod
    def _validate_url(value: str, *, mcp: bool = False) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise UpstreamGatewayError("invalid_upstream_url", "Use an HTTP or HTTPS gateway URL.")
        if parsed.username or parsed.password or parsed.fragment or parsed.query:
            raise UpstreamGatewayError("invalid_upstream_url", "Gateway URLs cannot contain credentials, query parameters or fragments.")
        path = parsed.path.rstrip("/")
        if "/v1/share/" not in path or (mcp and not path.endswith("/mcp")):
            raise UpstreamGatewayError("invalid_upstream_url", "This is not an AI2Apps Local sharing URL.")
        if not mcp and path.endswith("/mcp"):
            raise UpstreamGatewayError("invalid_upstream_url", "Use the OpenAI base URL, not the MCP URL.")
        return normalized

    @staticmethod
    def _record(row) -> UpstreamGateway:
        return UpstreamGateway(
            id=row["id"], label=row["label"],
            openai_base_url=row["openai_base_url"], mcp_url=row["mcp_url"],
            transport_kind=row["transport_kind"],
            downstream_installation_id=row["downstream_installation_id"],
            node_link_id=row["node_link_id"],
            remote_node_id=row["remote_node_id"],
            ancestor_node_ids=tuple(json.loads(row["ancestor_node_ids_json"])),
            is_parent=bool(row["is_parent"]), is_default=bool(row["is_default"]),
            priority=int(row["priority"]), route_models=bool(row["route_models"]),
            route_mcp=bool(row["route_mcp"]),
            status=row["status"], health_status=row["health_status"],
            capabilities=json.loads(row["capabilities_json"]),
            last_error=row["last_error"],
            last_checked_at=None if row["last_checked_at"] is None else parse_utc(row["last_checked_at"]),
            created_by_user_id=row["created_by_user_id"], revision=int(row["revision"]),
            created_at=parse_utc(row["created_at"]), updated_at=parse_utc(row["updated_at"]),
        )

    def _transport(self, gateway: UpstreamGateway) -> ParentTransport:
        try:
            return self.transports[gateway.transport_kind]
        except KeyError as exc:
            raise UpstreamGatewayError(
                "upstream_transport_unsupported",
                f"Unsupported upstream transport: {gateway.transport_kind}",
                status_code=503,
            ) from exc

    def list(self) -> tuple[UpstreamGateway, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM upstream_gateways ORDER BY is_default DESC,priority,created_at,id"
            ).fetchall()
        return tuple(self._record(row) for row in rows)

    def get(self, gateway_id: str) -> UpstreamGateway:
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM upstream_gateways WHERE id=?", (gateway_id,)).fetchone()
        if row is None:
            raise UpstreamGatewayError("upstream_not_found", "Upstream gateway not found.", status_code=404)
        return self._record(row)

    def get_by_node_link_id(self, node_link_id: str) -> UpstreamGateway:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM upstream_gateways WHERE node_link_id=? AND transport_kind='cloud_relay'",
                (node_link_id,),
            ).fetchone()
        if row is None:
            raise UpstreamGatewayError("node_link_not_connected", "This NodeLink is not connected on this Local.", status_code=404)
        return self._record(row)

    def replace_cloud_credential(self, node_link_id: str, credential: str) -> UpstreamGateway:
        gateway = self.get_by_node_link_id(node_link_id)
        if not credential.startswith(node_link_id + "."):
            raise UpstreamGatewayError("invalid_cloud_relay_credential", "NodeLink credential does not match the link.")
        secret_key = self._secret_key(gateway.id)
        self.secret_backend.store(secret_key, credential)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE upstream_gateways SET status='active',health_status='unknown',last_error=NULL,
                revision=revision+1,updated_at=? WHERE id=?""",
                (now, gateway.id),
            )
        self.record_activity(
            gateway_id=gateway.id, operation="probe", capability_id="credential.rotate",
            status="completed", duration_ms=0,
        )
        return self.get(gateway.id)

    def apply_cloud_link_states(self, items: list[dict[str, Any]]) -> None:
        """Disable locally saved relay credentials after Cloud revocation."""
        states = {str(item.get("nodeLinkId")): item.get("status") for item in items if item.get("nodeLinkId")}
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            for node_link_id, status in states.items():
                if status != "revoked":
                    continue
                connection.execute(
                    """UPDATE upstream_gateways SET status='disabled',health_status='offline',
                    last_error='NodeLink was revoked in Cloud',revision=revision+1,updated_at=?
                    WHERE node_link_id=? AND transport_kind='cloud_relay' AND status!='disabled'""",
                    (now, node_link_id),
                )

    def projected_models(self) -> tuple[dict[str, str], ...]:
        projected = []
        for gateway in self.list():
            if gateway.status != "active" or gateway.health_status != "online" or not gateway.route_models:
                continue
            for model in gateway.capabilities.get("models", []):
                remote_id = model.get("id") if isinstance(model, dict) else None
                if remote_id:
                    projected.append({
                        "id": f"gateway/{gateway.id}/{remote_id}",
                        "remote_id": remote_id,
                        "gateway_id": gateway.id,
                        "gateway_label": gateway.label,
                    })
        return tuple(projected)

    def resolve_model(self, projected_id: str) -> tuple[UpstreamGateway, str, str] | None:
        prefix = "gateway/"
        if not projected_id.startswith(prefix):
            if self.routing().model_policy != "parent_first":
                return None
            for gateway in self.list():
                if not gateway.is_parent or not gateway.route_models or gateway.status != "active" or gateway.health_status != "online":
                    continue
                allowed = {
                    item.get("id") for item in gateway.capabilities.get("models", [])
                    if isinstance(item, dict)
                }
                if projected_id in allowed:
                    return gateway, projected_id, self._load_token(gateway.id)
            return None
        parts = projected_id[len(prefix):].split("/", 1)
        if len(parts) != 2 or not parts[1]:
            return None
        gateway = self.get(parts[0])
        if gateway.status != "active" or gateway.health_status != "online":
            return None
        allowed = {item["remote_id"] for item in self.projected_models() if item["gateway_id"] == gateway.id}
        if parts[1] not in allowed:
            return None
        return gateway, parts[1], self._load_token(gateway.id)

    def _secret_key(self, gateway_id: str) -> str:
        with self.database.transaction() as connection:
            row = connection.execute("SELECT secret_backend_key FROM upstream_gateways WHERE id=?", (gateway_id,)).fetchone()
        if row is None:
            raise UpstreamGatewayError("upstream_not_found", "Upstream gateway not found.", status_code=404)
        return row["secret_backend_key"]

    def _load_token(self, gateway_id: str) -> str:
        try:
            return self.secret_backend.load(self._secret_key(gateway_id))
        except KeyError as exc:
            raise UpstreamGatewayError("upstream_credential_missing", "Upstream credential is unavailable.", status_code=503) from exc

    def create(
        self, *, label: str, openai_base_url: str, mcp_url: str, token: str,
        created_by_user_id: str, remote_node_id: str | None = None,
        ancestor_node_ids: tuple[str, ...] = (), is_parent: bool = True,
        priority: int = 100, route_models: bool = True, route_mcp: bool = True,
    ) -> UpstreamGateway:
        label = label.strip()
        if not label or not token:
            raise UpstreamGatewayError("invalid_upstream", "Label and Share Token are required.")
        openai_base_url = self._validate_url(openai_base_url)
        mcp_url = self._validate_url(mcp_url, mcp=True)
        if mcp_url != openai_base_url + "/mcp":
            raise UpstreamGatewayError("upstream_url_mismatch", "OpenAI and MCP URLs must belong to the same Share Grant.")
        remote_node_id = None if remote_node_id is None else remote_node_id.strip()
        ancestors = tuple(dict.fromkeys(str(item).strip() for item in ancestor_node_ids if str(item).strip()))
        if remote_node_id and len(remote_node_id) not in range(8, 129):
            raise UpstreamGatewayError("invalid_parent_identity", "Parent Node ID is invalid.")
        if len(ancestors) > 64 or any(len(item) not in range(8, 129) for item in ancestors):
            raise UpstreamGatewayError("invalid_parent_path", "Parent ancestry path is invalid.")
        if self.local_node_id and (remote_node_id == self.local_node_id or self.local_node_id in ancestors):
            raise UpstreamGatewayError("upstream_cycle_detected", "That parent already depends on this Local.", status_code=409)
        if not 1 <= priority <= 1000:
            raise UpstreamGatewayError("invalid_parent_priority", "Parent priority must be between 1 and 1000.")
        gateway_id = self._id()
        secret_key = f"ai2apps.upstream.{gateway_id}"
        now = utc_now_text()
        self.secret_backend.store(secret_key, token)
        try:
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    """INSERT INTO upstream_gateways(
                        id,label,openai_base_url,mcp_url,secret_backend_key,status,
                        health_status,capabilities_json,created_by_user_id,revision,
                        created_at,updated_at,remote_node_id,ancestor_node_ids_json,
                        is_parent,is_default,priority,route_models,route_mcp
                    ) VALUES (?,?,?,?,?,'active','unknown','{}',?,1,?,?,?,?,?,0,?,?,?)""",
                    (
                        gateway_id, label, openai_base_url, mcp_url, secret_key,
                        created_by_user_id, now, now, remote_node_id,
                        json.dumps(ancestors, separators=(",", ":")), int(is_parent),
                        priority, int(route_models), int(route_mcp),
                    ),
                )
                if is_parent:
                    connection.execute(
                        """UPDATE upstream_gateways SET is_default=1
                        WHERE id=? AND NOT EXISTS(
                            SELECT 1 FROM upstream_gateways WHERE is_default=1
                        )""",
                        (gateway_id,),
                    )
        except Exception:
            self.secret_backend.delete(secret_key)
            raise
        return self.get(gateway_id)

    def create_cloud_relay(
        self, *, label: str, cloud_base_url: str, credential: str,
        node_link_id: str, upstream_installation_id: str,
        downstream_installation_id: str, created_by_user_id: str,
        priority: int = 100, route_models: bool = True, route_mcp: bool = True,
    ) -> UpstreamGateway:
        label = label.strip()
        parsed = urlparse(cloud_base_url.strip().rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise UpstreamGatewayError("invalid_cloud_origin", "Cloud origin is invalid.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path.rstrip("/"):
            raise UpstreamGatewayError("invalid_cloud_origin", "Cloud Relay requires an origin URL.")
        if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise UpstreamGatewayError("invalid_cloud_origin", "Cloud Relay requires HTTPS.")
        if not label or not credential or not node_link_id:
            raise UpstreamGatewayError("invalid_cloud_relay", "Cloud Relay pairing is incomplete.")
        if not credential.startswith(node_link_id + "."):
            raise UpstreamGatewayError("invalid_cloud_relay_credential", "NodeLink credential does not match the link.")
        if not 1 <= priority <= 1000:
            raise UpstreamGatewayError("invalid_parent_priority", "Parent priority must be between 1 and 1000.")
        for value in (upstream_installation_id, downstream_installation_id):
            if len(value) not in range(8, 201):
                raise UpstreamGatewayError("invalid_parent_identity", "Federation installation identity is invalid.")
        if upstream_installation_id == downstream_installation_id:
            raise UpstreamGatewayError("upstream_cycle_detected", "A Local cannot be its own Cloud parent.", status_code=409)
        gateway_id = self._id()
        secret_key = f"ai2apps.upstream.{gateway_id}"
        origin = cloud_base_url.strip().rstrip("/")
        base = f"{origin}/v1/federation/nodes/{node_link_id}"
        now = utc_now_text()
        self.secret_backend.store(secret_key, credential)
        try:
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    """INSERT INTO upstream_gateways(
                        id,label,openai_base_url,mcp_url,secret_backend_key,status,
                        health_status,capabilities_json,created_by_user_id,revision,
                        created_at,updated_at,remote_node_id,ancestor_node_ids_json,
                        is_parent,is_default,priority,route_models,route_mcp,
                        transport_kind,downstream_installation_id,node_link_id
                    ) VALUES (?,?,?,?,?,'active','unknown','{}',?,1,?,?,?,?,1,0,?,?,?,'cloud_relay',?,?)""",
                    (gateway_id,label,base,base+"/mcp",secret_key,created_by_user_id,
                     now,now,upstream_installation_id,"[]",priority,int(route_models),
                     int(route_mcp),downstream_installation_id,node_link_id),
                )
                connection.execute(
                    """UPDATE upstream_gateways SET is_default=1
                    WHERE id=? AND NOT EXISTS(SELECT 1 FROM upstream_gateways WHERE is_default=1)""",
                    (gateway_id,),
                )
        except Exception:
            self.secret_backend.delete(secret_key)
            raise
        return self.get(gateway_id)

    def save_cloud_pairing(
        self, *, pairing_id: str, pairing_code: str, expires_at: str,
        created_by_user_id: str,
    ) -> None:
        secret_key = f"ai2apps.federation.pairing.{pairing_id}"
        self.secret_backend.store(secret_key, pairing_code)
        now = utc_now_text()
        try:
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    """INSERT INTO federation_pairing_attempts(
                        pairing_id,secret_backend_key,expires_at,status,
                        created_by_user_id,created_at,updated_at
                    ) VALUES (?,?,?,'pending',?,?,?)
                    ON CONFLICT(pairing_id) DO UPDATE SET
                        secret_backend_key=excluded.secret_backend_key,
                        expires_at=excluded.expires_at,status='pending',
                        updated_at=excluded.updated_at""",
                    (pairing_id,secret_key,expires_at,created_by_user_id,now,now),
                )
        except Exception:
            self.secret_backend.delete(secret_key)
            raise

    def load_cloud_pairing(self, pairing_id: str) -> str:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT secret_backend_key,status FROM federation_pairing_attempts WHERE pairing_id=?",
                (pairing_id,),
            ).fetchone()
        if row is None or row["status"] != "pending":
            raise UpstreamGatewayError("federation_pairing_not_found", "Pending Cloud pairing was not found.", status_code=404)
        try:
            return self.secret_backend.load(row["secret_backend_key"])
        except KeyError as exc:
            raise UpstreamGatewayError("federation_pairing_secret_missing", "Cloud pairing secret is unavailable.", status_code=409) from exc

    def list_cloud_pairings(self) -> tuple[dict[str, str], ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT pairing_id,secret_backend_key,expires_at,status
                FROM federation_pairing_attempts WHERE status='pending'
                ORDER BY created_at DESC"""
            ).fetchall()
        items = []
        for row in rows:
            if parse_utc(row["expires_at"]) <= utc_now():
                with self.database.transaction(write=True) as connection:
                    connection.execute(
                        "UPDATE federation_pairing_attempts SET status='expired',updated_at=? WHERE pairing_id=? AND status='pending'",
                        (utc_now_text(), row["pairing_id"]),
                    )
                self.secret_backend.delete(row["secret_backend_key"])
                continue
            try:
                code = self.secret_backend.load(row["secret_backend_key"])
            except KeyError:
                continue
            items.append({
                "pairingId": row["pairing_id"], "pairingCode": code,
                "expiresAt": row["expires_at"], "status": row["status"],
            })
        return tuple(items)

    def complete_cloud_pairing(self, pairing_id: str) -> None:
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT secret_backend_key FROM federation_pairing_attempts WHERE pairing_id=?",
                (pairing_id,),
            ).fetchone()
            if row is not None:
                connection.execute(
                    "UPDATE federation_pairing_attempts SET status='exchanged',updated_at=? WHERE pairing_id=?",
                    (utc_now_text(),pairing_id),
                )
        if row is not None:
            self.secret_backend.delete(row["secret_backend_key"])

    def routing(self) -> UpstreamRouting:
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM upstream_route_settings WHERE singleton_id=1").fetchone()
        return UpstreamRouting(
            model_policy=row["model_policy"], revision=int(row["revision"]),
            updated_by_user_id=row["updated_by_user_id"],
            created_at=parse_utc(row["created_at"]), updated_at=parse_utc(row["updated_at"]),
        )

    def update_routing(
        self, *, model_policy: str, expected_revision: int,
        updated_by_user_id: str,
    ) -> UpstreamRouting:
        if model_policy not in {"explicit_only", "parent_first"}:
            raise UpstreamGatewayError("invalid_model_route", "Invalid parent model route policy.")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            result = connection.execute(
                """UPDATE upstream_route_settings SET model_policy=?,revision=revision+1,
                updated_by_user_id=?,updated_at=? WHERE singleton_id=1 AND revision=?""",
                (model_policy, updated_by_user_id, now, expected_revision),
            )
        if result.rowcount != 1:
            raise UpstreamGatewayError("routing_version_mismatch", "Parent routing settings changed; refresh and retry.", status_code=409)
        return self.routing()

    def ancestor_node_ids(self) -> tuple[str, ...]:
        nodes: list[str] = []
        for gateway in self.list():
            if not gateway.is_parent or gateway.status != "active" or not gateway.remote_node_id:
                continue
            nodes.extend((gateway.remote_node_id, *gateway.ancestor_node_ids))
        return tuple(dict.fromkeys(nodes))[:64]

    async def start(self, interval_seconds: float | None = None) -> None:
        if self._health_task is not None:
            return
        if interval_seconds is None:
            interval_seconds = float(os.environ.get("AI2APPS_PARENT_HEALTH_INTERVAL_SECONDS", "30"))
        if interval_seconds <= 0:
            return
        self._health_stop = asyncio.Event()
        self._health_task = asyncio.create_task(
            self._health_loop(interval_seconds), name="ai2apps-parent-health"
        )

    async def stop(self) -> None:
        if self._health_stop is not None:
            self._health_stop.set()
        if self._health_task is not None:
            await self._health_task
        self._health_task = None
        self._health_stop = None

    async def _health_loop(self, interval_seconds: float) -> None:
        assert self._health_stop is not None
        while True:
            try:
                await asyncio.wait_for(self._health_stop.wait(), timeout=interval_seconds)
                return
            except TimeoutError:
                pass
            for gateway in self.list():
                if gateway.status != "active" or not gateway.is_parent:
                    continue
                try:
                    await self.probe(gateway.id)
                except Exception:
                    pass

    async def probe(self, gateway_id: str) -> UpstreamGateway:
        started = time.monotonic()
        gateway = self.get(gateway_id)
        if gateway.status != "active":
            raise UpstreamGatewayError("upstream_disabled", "Upstream gateway is disabled.", status_code=409)
        live_node_id: str | None = None
        live_ancestors: list[str] = []
        with self.database.transaction() as connection:
            row = connection.execute("SELECT secret_backend_key FROM upstream_gateways WHERE id=?", (gateway_id,)).fetchone()
        try:
            token = self.secret_backend.load(row["secret_backend_key"])
            projection = await self._transport(gateway).probe(gateway, token)
            models = projection.models
            tools = projection.tools
            live_node_id = projection.node_id
            live_ancestors = list(projection.ancestor_node_ids)
            if live_node_id is not None:
                if not isinstance(live_node_id, str) or len(live_node_id) not in range(8, 129):
                    raise UpstreamGatewayError("invalid_parent_identity", "Parent returned an invalid Node ID.")
                if not isinstance(live_ancestors, list) or len(live_ancestors) > 64 or any(
                    not isinstance(item, str) or len(item) not in range(8, 129)
                    for item in live_ancestors
                ):
                    raise UpstreamGatewayError("invalid_parent_path", "Parent returned an invalid ancestry path.")
                if gateway.remote_node_id is not None and gateway.remote_node_id != live_node_id:
                    raise UpstreamGatewayError("parent_identity_changed", "Parent Node ID no longer matches this connection.")
                if self.local_node_id and (
                    live_node_id == self.local_node_id or self.local_node_id in live_ancestors
                ):
                    raise UpstreamGatewayError("upstream_cycle_detected", "Parent routing would create a Local gateway cycle.")
            capabilities = {
                "models": [{"id": item.get("id")} for item in models if isinstance(item, dict) and item.get("id")],
                "tools": [{"name": item.get("name"), "description": item.get("description"), "inputSchema": item.get("inputSchema", {})} for item in tools if isinstance(item, dict) and item.get("name")],
            }
            health, error = "online", None
        except httpx.HTTPStatusError as exc:
            # A Cloud NodeGrant policy denial means the relay is reachable; it
            # must not turn an otherwise healthy parent into a transport outage.
            if gateway.transport_kind == "cloud_relay" and 400 <= exc.response.status_code < 500:
                capabilities = {"models": [], "tools": []}
                health, error = "online", f"Cloud policy rejected discovery (HTTP {exc.response.status_code})"
            else:
                capabilities = gateway.capabilities
                health, error = "offline", str(exc)[:1000]
        except Exception as exc:
            capabilities = gateway.capabilities
            health, error = "offline", str(exc)[:1000]
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE upstream_gateways SET health_status=?,capabilities_json=?,
                    last_error=?,last_checked_at=?,revision=revision+1,updated_at=?,
                    remote_node_id=COALESCE(?,remote_node_id),
                    ancestor_node_ids_json=CASE WHEN ? IS NULL THEN ancestor_node_ids_json ELSE ? END
                    WHERE id=?""",
                (
                    health, json.dumps(capabilities, separators=(",", ":")), error, now, now,
                    live_node_id if health == "online" else None,
                    live_node_id if health == "online" else None,
                    json.dumps(live_ancestors, separators=(",", ":")) if health == "online" and live_node_id else None,
                    gateway_id,
                ),
            )
        updated = self.get(gateway_id)
        self._sync_tool_projection(updated)
        self.record_activity(
            gateway_id=gateway_id,
            operation="probe",
            capability_id=None,
            status="completed" if health == "online" else "failed",
            duration_ms=int((time.monotonic() - started) * 1000),
            error_code=None if health == "online" else "probe_failed",
        )
        return updated

    def record_activity(
        self,
        *,
        gateway_id: str,
        operation: str,
        capability_id: str | None,
        status: str,
        duration_ms: int,
        error_code: str | None = None,
    ) -> None:
        """Store operational metadata only; never prompts, arguments or responses."""
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO upstream_gateway_activity(
                    id,gateway_id,operation,capability_id,status,duration_ms,
                    error_code,created_at
                ) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    "upa_" + secrets.token_hex(16), gateway_id, operation,
                    None if capability_id is None else capability_id[:500], status,
                    max(0, int(duration_ms)), error_code, utc_now_text(),
                ),
            )

    def list_activity(self, *, gateway_id: str | None = None, limit: int = 50) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 200:
            raise UpstreamGatewayError("invalid_limit", "Activity limit must be 1 to 200.")
        query = "SELECT * FROM upstream_gateway_activity"
        parameters: tuple[Any, ...]
        if gateway_id is None:
            query += " ORDER BY created_at DESC LIMIT ?"
            parameters = (limit,)
        else:
            self.get(gateway_id)
            query += " WHERE gateway_id=? ORDER BY created_at DESC LIMIT ?"
            parameters = (gateway_id, limit)
        with self.database.transaction() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return tuple({
            "id": row["id"], "gateway_id": row["gateway_id"],
            "operation": row["operation"], "capability_id": row["capability_id"],
            "status": row["status"], "duration_ms": int(row["duration_ms"]),
            "error_code": row["error_code"], "created_at": row["created_at"],
        } for row in rows)

    def mark_unavailable(
        self,
        *,
        gateway_id: str,
        operation: str,
        capability_id: str | None,
        started_at: float,
        error_code: str,
        message: str,
    ) -> None:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE upstream_gateways SET health_status='offline',last_error=?,
                    last_checked_at=?,revision=revision+1,updated_at=? WHERE id=?""",
                (message[:1000], now, now, gateway_id),
            )
        self.record_activity(
            gateway_id=gateway_id, operation=operation,
            capability_id=capability_id, status="failed",
            duration_ms=int((time.monotonic() - started_at) * 1000),
            error_code=error_code,
        )
        self._sync_tool_projection(self.get(gateway_id))

    def _sync_tool_projection(self, gateway: UpstreamGateway) -> None:
        repository, registry = self.service_repository, self.service_registry
        if repository is None or registry is None:
            return
        service_key = f"ai2apps.upstream.{gateway.id}"
        service = repository.ensure_service(
            service_key=service_key,
            package_id="ai2apps.upstream-gateway",
            package_version="1.0.0",
            display_name=f"Upstream · {gateway.label}",
            runtime_mode=ServiceRuntimeMode.IN_PROCESS,
            capabilities=("upstream.models", "upstream.tools"),
            config={"gateway_id": gateway.id, "openai_base_url": gateway.openai_base_url},
        )
        instance = repository.ensure_instance(
            service_id=service.id,
            provider_key=f"upstream:{gateway.id}",
            status=(ServiceInstanceStatus.RUNNING if gateway.status == "active" and gateway.health_status == "online" else ServiceInstanceStatus.DEGRADED),
            endpoint=gateway.mcp_url,
            health={"status": gateway.health_status, "last_error": gateway.last_error},
        )
        active_names: set[str] = set()
        remote_tools = (
            gateway.capabilities.get("tools", [])
            if gateway.status == "active" and gateway.health_status == "online" and gateway.route_mcp
            else []
        )
        for remote in remote_tools:
            if not isinstance(remote, dict) or not remote.get("name"):
                continue
            remote_name = remote["name"]
            qualified_name = f"gateway.{gateway.id[4:]}.{remote_name}"
            active_names.add(qualified_name)
            repository.ensure_tool(
                service_id=service.id,
                qualified_name=qualified_name,
                display_name=f"{gateway.label} · {remote_name}",
                description=remote.get("description") or f"Tool provided by upstream gateway {gateway.label}.",
                input_schema=remote.get("inputSchema") or {"type": "object"},
                output_schema={"type": "object"},
                effects=("network",),
                timeout_ms=30_000,
            )

            async def invoke(arguments: dict[str, Any], call_context: ToolCallContext, *, gid=gateway.id, name=remote_name):
                context = None
                if call_context.actor_user_id and call_context.installation_id and call_context.membership_epoch:
                    context = ParentCallContext(
                        call_context.actor_user_id, call_context.installation_id,
                        call_context.membership_epoch,
                    )
                return await self.invoke_tool(gid, name, arguments, context=context)

            registry.bind_tool(qualified_name, provider_key=instance.provider_key, handler=invoke)
        repository.disable_unseen_tools(service.id, active_names)

    async def invoke_tool(
        self, gateway_id: str, remote_name: str, arguments: dict[str, Any],
        *, context: ParentCallContext | None = None,
    ) -> dict[str, Any]:
        started = time.monotonic()
        gateway = self.get(gateway_id)
        if gateway.status != "active":
            raise ToolProviderError("Upstream gateway is disabled")
        try:
            transport = self._transport(gateway)
            if context is None:
                payload = await transport.invoke_tool(
                    gateway, self._load_token(gateway_id), remote_name, arguments
                )
            else:
                payload = await transport.invoke_tool(
                    gateway, self._load_token(gateway_id), remote_name, arguments,
                    context=context,
                )
            if payload.get("error"):
                raise ToolProviderError(str(payload["error"]))
            result = payload.get("result", {})
            structured = result.get("structuredContent")
            self.record_activity(
                gateway_id=gateway_id, operation="tool", capability_id=remote_name,
                status="completed", duration_ms=int((time.monotonic() - started) * 1000),
            )
            return structured if isinstance(structured, dict) else {"content": result.get("content", [])}
        except ToolProviderError:
            self.record_activity(
                gateway_id=gateway_id, operation="tool", capability_id=remote_name,
                status="failed", duration_ms=int((time.monotonic() - started) * 1000),
                error_code="upstream_tool_error",
            )
            raise
        except httpx.HTTPStatusError as exc:
            if gateway.transport_kind == "cloud_relay" and 400 <= exc.response.status_code < 500:
                self.record_activity(
                    gateway_id=gateway_id, operation="tool", capability_id=remote_name,
                    status="failed", duration_ms=int((time.monotonic() - started) * 1000),
                    error_code=f"cloud_policy_http_{exc.response.status_code}",
                )
                raise ToolProviderError(f"Cloud federation policy rejected the Tool call (HTTP {exc.response.status_code})") from exc
            self.mark_unavailable(
                gateway_id=gateway_id, operation="tool", capability_id=remote_name,
                started_at=started, error_code="upstream_unavailable", message=str(exc),
            )
            raise ToolProviderError(f"Upstream Tool call failed: {exc}") from exc
        except Exception as exc:
            self.mark_unavailable(
                gateway_id=gateway_id, operation="tool", capability_id=remote_name,
                started_at=started, error_code="upstream_unavailable", message=str(exc),
            )
            raise ToolProviderError(f"Upstream Tool call failed: {exc}") from exc

    async def open_model(
        self, gateway: UpstreamGateway, token: str, payload: dict[str, Any],
        *, stream: bool, context: ParentCallContext | None = None,
    ) -> ParentModelResponse:
        """Open a model response through the configured Parent transport."""

        transport = self._transport(gateway)
        if context is None:
            return await transport.open_model(gateway, token, payload, stream=stream)
        return await transport.open_model(
            gateway, token, payload, stream=stream, context=context
        )

    def update(
        self, gateway_id: str, *, expected_revision: int,
        status: str | None = None, is_default: bool | None = None,
        priority: int | None = None, route_models: bool | None = None,
        route_mcp: bool | None = None,
    ) -> UpstreamGateway:
        if status is not None and status not in {"active", "disabled"}:
            raise UpstreamGatewayError("invalid_upstream_status", "Invalid upstream status.")
        if priority is not None and not 1 <= priority <= 1000:
            raise UpstreamGatewayError("invalid_parent_priority", "Parent priority must be between 1 and 1000.")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            current = connection.execute(
                "SELECT revision,is_parent FROM upstream_gateways WHERE id=?", (gateway_id,)
            ).fetchone()
            if current is None:
                raise UpstreamGatewayError("upstream_not_found", "Upstream gateway not found.", status_code=404)
            if int(current["revision"]) != expected_revision:
                raise UpstreamGatewayError("upstream_version_mismatch", "Parent settings changed; refresh and retry.", status_code=409)
            if is_default and not bool(current["is_parent"]):
                raise UpstreamGatewayError("parent_required", "Only a parent Local can be the default parent.", status_code=409)
            if is_default:
                connection.execute(
                    "UPDATE upstream_gateways SET is_default=0,revision=revision+1,updated_at=? WHERE is_default=1 AND id!=?",
                    (now, gateway_id),
                )
            changes = {"updated_at": now}
            if status is not None:
                changes["status"] = status
            if is_default is not None:
                changes["is_default"] = int(is_default)
            if priority is not None:
                changes["priority"] = priority
            if route_models is not None:
                changes["route_models"] = int(route_models)
            if route_mcp is not None:
                changes["route_mcp"] = int(route_mcp)
            assignments = ",".join(f"{key}=?" for key in changes)
            result = connection.execute(
                f"UPDATE upstream_gateways SET {assignments},revision=revision+1 WHERE id=? AND revision=?",
                (*changes.values(), gateway_id, expected_revision),
            )
        if result.rowcount == 0:
            raise UpstreamGatewayError("upstream_version_mismatch", "Parent settings changed; refresh and retry.", status_code=409)
        updated = self.get(gateway_id)
        self._sync_tool_projection(updated)
        if status is not None and self.service_repository is not None:
            try:
                service = self.service_repository.get_service(f"ai2apps.upstream.{gateway_id}")
                desired = ServiceStatus.ENABLED if status == "active" else ServiceStatus.DISABLED
                if service.status is not desired:
                    self.service_repository.set_service_status(service.id, expected_revision=service.revision, status=desired)
            except Exception:
                pass
        return updated

    def set_status(self, gateway_id: str, status: str) -> UpstreamGateway:
        return self.update(
            gateway_id, expected_revision=self.get(gateway_id).revision, status=status
        )

    def delete(self, gateway_id: str) -> None:
        with self.database.transaction(write=True) as connection:
            row = connection.execute("SELECT secret_backend_key FROM upstream_gateways WHERE id=?", (gateway_id,)).fetchone()
            if row is None:
                raise UpstreamGatewayError("upstream_not_found", "Upstream gateway not found.", status_code=404)
            connection.execute("DELETE FROM upstream_gateways WHERE id=?", (gateway_id,))
            replacement = connection.execute(
                """SELECT id FROM upstream_gateways
                WHERE is_parent=1 AND status='active'
                ORDER BY priority,created_at,id LIMIT 1"""
            ).fetchone()
            if replacement is not None and not connection.execute(
                "SELECT 1 FROM upstream_gateways WHERE is_default=1"
            ).fetchone():
                connection.execute(
                    "UPDATE upstream_gateways SET is_default=1,revision=revision+1,updated_at=? WHERE id=?",
                    (utc_now_text(), replacement["id"]),
                )
        self.secret_backend.delete(row["secret_backend_key"])
        if self.service_repository is not None:
            try:
                self.service_repository.remove_service(f"ai2apps.upstream.{gateway_id}")
            except Exception:
                pass
