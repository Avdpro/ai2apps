"""Authorization, persistence, quotas, and audit for LAN capability sharing."""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import timedelta
from uuid import uuid4

from ai2apps.core import parse_utc, utc_now, utc_now_text
from ai2apps.core import (
    MessageRole,
    ResourceNotFoundError,
    SessionKind,
    SessionRetention,
    SessionStatus,
    SessionVisibility,
    format_utc,
)
from ai2apps.agents import AgentDefinitionStatus
from ai2apps.services import ToolCallContext, ToolGatewayError
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.repositories import AppRepository, MessageRepository, SessionRepository

from .models import (
    CapabilityExport,
    CapabilityKind,
    IssuedShareGrant,
    LocalNetworkAccess,
    ShareGrant,
)


class SharingError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class SharingManager:
    """Keep the management plane separate from share-token data access."""

    def __init__(
        self,
        database: PlatformDatabase,
        tools,
        *,
        model_source_resolver: Callable[[str], str] | None = None,
    ) -> None:
        self.database = database
        self.tools = tools
        self._active: dict[str, int] = {}
        self._lock = asyncio.Lock()
        self._network_apply: Callable[[LocalNetworkAccess], Awaitable[None]] | None = None
        self._model_source_resolver = model_source_resolver
        self.agents = None
        self.agent_runtime = None

    def bind_agents(self, agents, agent_runtime) -> None:
        self.agents = agents
        self.agent_runtime = agent_runtime

    @staticmethod
    def _safe_tool(tool) -> bool:
        return not (tool.effects or tool.required_capabilities or tool.capability_rules)

    def list_shareable_services(self):
        services = []
        for service in self.tools.repository.list_services():
            tools = tuple(
                item
                for item in self.tools.repository.list_tools()
                if item.service_id == service.id and item.enabled and self._safe_tool(item)
            )
            if service.status.value == "enabled" and tools:
                services.append((service, tools))
        return tuple(services)

    def list_shareable_agents(self):
        if self.agents is None:
            return ()
        return tuple(
            item
            for item in self.agents.list_definitions()
            if item.status is AgentDefinitionStatus.ENABLED
            and bool((item.manifest or {}).get("discoverable", item.agent_key != "ai2apps.diagnostic-agent"))
        )

    def model_source(self, model_id: str) -> str:
        if self._model_source_resolver is not None:
            return self._model_source_resolver(model_id)
        if model_id.startswith("gateway/"):
            return "upstream_gateway"
        if model_id.startswith("cloud/"):
            return "ai2apps_cloud"
        return "local_runtime"

    def bind_network_apply(
        self, callback: Callable[[LocalNetworkAccess], Awaitable[None]] | None
    ) -> None:
        self._network_apply = callback

    def network_access(self) -> LocalNetworkAccess:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM local_network_access WHERE singleton_id=1"
            ).fetchone()
        return LocalNetworkAccess(
            mode=row["mode"],
            bind_host=row["bind_host"],
            port=int(row["port"]),
            revision=int(row["revision"]),
            updated_by_user_id=row["updated_by_user_id"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    async def update_network_access(
        self,
        *,
        mode: str,
        bind_host: str,
        port: int,
        expected_revision: int,
        updated_by_user_id: str,
    ) -> LocalNetworkAccess:
        if mode not in {"disabled", "share_only", "full"}:
            raise SharingError("invalid_network_mode", "Invalid LAN access mode.")
        if bind_host not in {"0.0.0.0", "::"}:
            raise SharingError(
                "invalid_bind_host", "LAN listener must bind to 0.0.0.0 or ::."
            )
        if not 1024 <= port <= 65535:
            raise SharingError("invalid_port", "LAN port must be 1024 to 65535.")
        with self.database.transaction(write=True) as connection:
            result = connection.execute(
                """
                UPDATE local_network_access
                SET mode=?,bind_host=?,port=?,revision=revision+1,
                    updated_by_user_id=?,updated_at=?
                WHERE singleton_id=1 AND revision=?
                """,
                (mode, bind_host, port, updated_by_user_id, utc_now_text(), expected_revision),
            )
            if result.rowcount != 1:
                raise SharingError(
                    "network_version_mismatch",
                    "LAN settings changed; refresh and try again.",
                    status_code=409,
                )
        settings = self.network_access()
        if self._network_apply is not None:
            try:
                await self._network_apply(settings)
            except Exception as exc:
                self.disable_network_after_failure()
                raise SharingError(
                    "lan_listener_failed", str(exc), status_code=503
                ) from exc
        return settings

    def disable_network_after_failure(self) -> LocalNetworkAccess:
        """Fail closed without invoking a listener callback recursively."""
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                UPDATE local_network_access
                SET mode='disabled',revision=revision+1,updated_at=?
                WHERE singleton_id=1
                """,
                (utc_now_text(),),
            )
        return self.network_access()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _id(prefix: str) -> str:
        return f"{prefix}{uuid4().hex}"

    @staticmethod
    def _export(row) -> CapabilityExport:
        return CapabilityExport(
            id=row["id"],
            kind=CapabilityKind(row["kind"]),
            target_id=row["target_id"],
            display_name=row["display_name"],
            protocols=tuple(json.loads(row["protocols_json"])),
            status=row["status"],
            created_by_user_id=row["created_by_user_id"],
            revision=int(row["revision"]),
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    def _grant(self, connection, row) -> ShareGrant:
        export_rows = connection.execute(
            """
            SELECT e.* FROM capability_exports e
            JOIN capability_share_grant_exports ge ON ge.export_id=e.id
            WHERE ge.grant_id=? ORDER BY e.created_at, e.id
            """,
            (row["id"],),
        ).fetchall()
        return ShareGrant(
            id=row["id"],
            label=row["label"],
            status=row["status"],
            max_concurrency=int(row["max_concurrency"]),
            max_requests=(None if row["max_requests"] is None else int(row["max_requests"])),
            expires_at=(None if row["expires_at"] is None else parse_utc(row["expires_at"])),
            created_by_user_id=row["created_by_user_id"],
            request_count=int(row["request_count"]),
            last_used_at=(None if row["last_used_at"] is None else parse_utc(row["last_used_at"])),
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
            exports=tuple(self._export(item) for item in export_rows),
        )

    def _validate_export(self, kind: CapabilityKind, target_id: str) -> tuple[str, ...]:
        if kind is CapabilityKind.MODEL:
            source = self.model_source(target_id)
            if source == "ai2apps_cloud":
                raise SharingError(
                    "cloud_model_not_shareable",
                    "AI2Apps Cloud models cannot be shared by the LAN gateway.",
                    status_code=403,
                )
            if source == "upstream_gateway":
                raise SharingError(
                    "upstream_model_not_shareable",
                    "Models received from another gateway cannot be re-exported.",
                    status_code=403,
                )
            return ("openai",)
        if kind is CapabilityKind.AGENT:
            if self.agents is None:
                raise SharingError("agent_runtime_unavailable", "Agent runtime is unavailable.", status_code=503)
            try:
                agent = self.agents.get_definition(target_id)
            except Exception as exc:
                raise SharingError("agent_not_found", f"Agent not found: {target_id}", status_code=404) from exc
            discoverable = bool((agent.manifest or {}).get("discoverable", agent.agent_key != "ai2apps.diagnostic-agent"))
            if agent.status is not AgentDefinitionStatus.ENABLED or not discoverable:
                raise SharingError("agent_not_shareable", "Only enabled, discoverable Agents can be shared.", status_code=403)
            return ("mcp",)
        if kind is CapabilityKind.SERVICE:
            try:
                service = self.tools.repository.get_service(target_id)
            except Exception as exc:
                raise SharingError("service_not_found", f"Service not found: {target_id}", status_code=404) from exc
            safe = [
                item for item in self.tools.repository.list_tools()
                if item.service_id == service.id and item.enabled and self._safe_tool(item)
            ]
            if service.status.value != "enabled" or not safe:
                raise SharingError("service_not_shareable", "The Service has no enabled, effect-free MCP methods.", status_code=403)
            return ("mcp",)
        try:
            tool = self.tools.repository.get_tool(target_id)
        except Exception as exc:
            raise SharingError("tool_not_found", f"Tool not found: {target_id}", status_code=404) from exc
        if not self._safe_tool(tool):
            raise SharingError(
                "unsafe_tool_not_shareable",
                "The LAN MVP only exports Tools with no effects or required capabilities.",
                status_code=403,
            )
        return ("mcp", "endpoint")

    def tools_for_export(self, export: CapabilityExport):
        if export.kind is CapabilityKind.TOOL:
            return (self.tools.repository.get_tool(export.target_id),)
        if export.kind is CapabilityKind.SERVICE:
            service = self.tools.repository.get_service(export.target_id)
            return tuple(
                item for item in self.tools.repository.list_tools()
                if item.service_id == service.id and item.enabled and self._safe_tool(item)
            )
        return ()

    def find_tool_export(self, grant: ShareGrant, qualified_name: str) -> CapabilityExport:
        for export in grant.exports:
            if export.status != "active" or export.kind not in {CapabilityKind.TOOL, CapabilityKind.SERVICE}:
                continue
            if any(item.qualified_name == qualified_name for item in self.tools_for_export(export)):
                return export
        raise SharingError("capability_not_shared", "Tool is not included in this grant.", status_code=403)

    def create_export(
        self,
        *,
        kind: CapabilityKind,
        target_id: str,
        display_name: str,
        created_by_user_id: str,
    ) -> CapabilityExport:
        protocols = self._validate_export(kind, target_id)
        export_id = self._id("exp_")
        now = utc_now_text()
        try:
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    """
                    INSERT INTO capability_exports(
                        id,kind,target_id,display_name,protocols_json,status,
                        created_by_user_id,revision,created_at,updated_at
                    ) VALUES (?,?,?,?,?,'active',?,1,?,?)
                    """,
                    (export_id, kind.value, target_id, display_name, json.dumps(protocols), created_by_user_id, now, now),
                )
                row = connection.execute(
                    "SELECT * FROM capability_exports WHERE id=?", (export_id,)
                ).fetchone()
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise SharingError("export_exists", "That capability is already exported.", status_code=409) from exc
            raise
        return self._export(row)

    def list_exports(self) -> tuple[CapabilityExport, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM capability_exports ORDER BY created_at DESC"
            ).fetchall()
        return tuple(self._export(row) for row in rows)

    def list_shareable_tools(self) -> tuple:
        context = ToolCallContext(caller_id="sharing:discovery")
        return tuple(
            tool
            for tool in self.tools.list_tools(context)
            if not tool.effects
            and not tool.required_capabilities
            and not tool.capability_rules
        )

    def set_export_status(self, export_id: str, status: str) -> CapabilityExport:
        if status not in {"active", "paused", "revoked"}:
            raise SharingError("invalid_status", "Invalid export status.")
        with self.database.transaction(write=True) as connection:
            result = connection.execute(
                """
                UPDATE capability_exports SET status=?,revision=revision+1,updated_at=?
                WHERE id=? AND status!='revoked'
                """,
                (status, utc_now_text(), export_id),
            )
            if result.rowcount != 1:
                raise SharingError("export_not_found", "Active export not found.", status_code=404)
            row = connection.execute("SELECT * FROM capability_exports WHERE id=?", (export_id,)).fetchone()
        export = self._export(row)
        if export.kind is CapabilityKind.AGENT and status != "active":
            self._close_agent_sessions(export_id=export.id)
        return export

    def create_grant(
        self,
        *,
        label: str,
        export_ids: tuple[str, ...],
        max_concurrency: int,
        expires_in_seconds: int | None,
        created_by_user_id: str,
        max_requests: int | None = None,
    ) -> IssuedShareGrant:
        if not export_ids:
            raise SharingError("empty_grant", "Select at least one export.")
        if not 1 <= max_concurrency <= 100:
            raise SharingError("invalid_concurrency", "max_concurrency must be between 1 and 100.")
        if max_requests is not None and not 1 <= max_requests <= 1_000_000:
            raise SharingError("invalid_request_budget", "max_requests must be between 1 and 1000000.")
        token = secrets.token_urlsafe(32)
        grant_id = self._id("shr_")
        now = utc_now()
        expires_at = None if expires_in_seconds is None else now + timedelta(seconds=expires_in_seconds)
        with self.database.transaction(write=True) as connection:
            found = connection.execute(
                f"SELECT id FROM capability_exports WHERE status='active' AND id IN ({','.join('?' for _ in export_ids)})",
                export_ids,
            ).fetchall()
            if {row["id"] for row in found} != set(export_ids):
                raise SharingError("export_not_available", "One or more exports are unavailable.", status_code=409)
            connection.execute(
                """
                INSERT INTO capability_share_grants(
                    id,label,token_digest,status,max_concurrency,expires_at,
                    created_by_user_id,request_count,created_at,updated_at,max_requests
                ) VALUES (?,?,?,'active',?,?,?,0,?,?,?)
                """,
                (
                    grant_id,
                    label,
                    self._digest(token),
                    max_concurrency,
                    None
                    if expires_at is None
                    else expires_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    created_by_user_id,
                    now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    max_requests,
                ),
            )
            connection.executemany(
                "INSERT INTO capability_share_grant_exports(grant_id,export_id) VALUES (?,?)",
                ((grant_id, export_id) for export_id in dict.fromkeys(export_ids)),
            )
            row = connection.execute("SELECT * FROM capability_share_grants WHERE id=?", (grant_id,)).fetchone()
            grant = self._grant(connection, row)
        return IssuedShareGrant(grant=grant, token=token)

    def list_grants(self) -> tuple[ShareGrant, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM capability_share_grants ORDER BY created_at DESC"
            ).fetchall()
            return tuple(self._grant(connection, row) for row in rows)

    def list_audit(self, *, limit: int = 100) -> tuple[dict, ...]:
        if not 1 <= limit <= 500:
            raise SharingError("invalid_limit", "Audit limit must be 1 to 500.")
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT id,grant_id,export_id,operation,status,duration_ms,
                       error_code,created_at
                FROM capability_share_audit
                ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def rotate_grant(self, grant_id: str) -> IssuedShareGrant:
        token = secrets.token_urlsafe(32)
        with self.database.transaction(write=True) as connection:
            result = connection.execute(
                "UPDATE capability_share_grants SET token_digest=?,updated_at=? WHERE id=? AND status='active'",
                (self._digest(token), utc_now_text(), grant_id),
            )
            if result.rowcount != 1:
                raise SharingError("grant_not_found", "Active grant not found.", status_code=404)
            row = connection.execute("SELECT * FROM capability_share_grants WHERE id=?", (grant_id,)).fetchone()
            grant = self._grant(connection, row)
        return IssuedShareGrant(grant=grant, token=token)

    def revoke_grant(self, grant_id: str) -> ShareGrant:
        with self.database.transaction(write=True) as connection:
            result = connection.execute(
                "UPDATE capability_share_grants SET status='revoked',updated_at=? WHERE id=? AND status='active'",
                (utc_now_text(), grant_id),
            )
            if result.rowcount != 1:
                raise SharingError("grant_not_found", "Active grant not found.", status_code=404)
            row = connection.execute("SELECT * FROM capability_share_grants WHERE id=?", (grant_id,)).fetchone()
            grant = self._grant(connection, row)
        self._close_agent_sessions(grant_id=grant_id)
        return grant

    def _close_agent_sessions(
        self, *, grant_id: str | None = None, export_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        if self.agent_runtime is None:
            return
        clauses = ["status='active'", "json_type(metadata_json, '$.sharing')='object'"]
        params: list[str] = []
        if grant_id is not None:
            clauses.append("json_extract(metadata_json, '$.sharing.grant_id')=?")
            params.append(grant_id)
        if export_id is not None:
            clauses.append("json_extract(metadata_json, '$.sharing.export_id')=?")
            params.append(export_id)
        if session_id is not None:
            clauses.append("id=?")
            params.append(session_id)
        with self.database.transaction() as connection:
            sessions = connection.execute(
                f"SELECT id,revision FROM sessions WHERE {' AND '.join(clauses)}", params
            ).fetchall()
            session_ids = [str(item["id"]) for item in sessions]
            runs = [] if not session_ids else connection.execute(
                f"""SELECT id FROM agent_runs WHERE session_id IN ({','.join('?' for _ in session_ids)})
                AND status NOT IN ('completed','failed','cancelled')""", session_ids
            ).fetchall()
        for run in runs:
            try:
                self.agent_runtime.cancel(str(run["id"]))
            except Exception:
                pass
        repository = SessionRepository(self.database)
        for session in sessions:
            try:
                repository.update(
                    str(session["id"]), expected_revision=int(session["revision"]),
                    status=SessionStatus.DELETED,
                )
            except Exception:
                pass

    def authenticate(self, grant_id: str, token: str) -> ShareGrant:
        if not token:
            raise SharingError("share_token_required", "Share token required.", status_code=401)
        digest = self._digest(token)
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM capability_share_grants WHERE id=? AND token_digest=?",
                (grant_id, digest),
            ).fetchone()
            if row is None or not secrets.compare_digest(row["token_digest"], digest):
                raise SharingError("invalid_share_token", "Invalid share token.", status_code=401)
            grant = self._grant(connection, row)
        if grant.status != "active":
            raise SharingError("share_revoked", "Share grant is revoked.", status_code=401)
        if grant.expires_at is not None and grant.expires_at <= utc_now():
            raise SharingError("share_expired", "Share grant has expired.", status_code=401)
        if grant.max_requests is not None and grant.request_count >= grant.max_requests:
            raise SharingError("share_request_limit", "Share grant request budget reached.", status_code=429)
        return grant

    @asynccontextmanager
    async def acquire(self, grant: ShareGrant) -> AsyncIterator[None]:
        async with self._lock:
            active = self._active.get(grant.id, 0)
            if active >= grant.max_concurrency:
                raise SharingError("share_concurrency_limit", "Share concurrency limit reached.", status_code=429)
            self._active[grant.id] = active + 1
        try:
            with self.database.transaction(write=True) as connection:
                result = connection.execute(
                    """UPDATE capability_share_grants
                    SET request_count=request_count+1,last_used_at=?,updated_at=?
                    WHERE id=? AND status='active'
                      AND (max_requests IS NULL OR request_count < max_requests)""",
                    (utc_now_text(), utc_now_text(), grant.id),
                )
                if result.rowcount != 1:
                    raise SharingError(
                        "share_request_limit",
                        "Share grant request budget reached.",
                        status_code=429,
                    )
            yield
        finally:
            async with self._lock:
                remaining = self._active.get(grant.id, 1) - 1
                if remaining:
                    self._active[grant.id] = remaining
                else:
                    self._active.pop(grant.id, None)

    def find_export(self, grant: ShareGrant, *, kind: CapabilityKind, target_id: str | None = None) -> CapabilityExport:
        matches = [item for item in grant.exports if item.kind is kind and item.status == "active" and (target_id is None or item.target_id == target_id)]
        if not matches:
            raise SharingError("capability_not_shared", "Capability is not included in this grant.", status_code=403)
        if target_id is None and len(matches) != 1:
            raise SharingError("capability_ambiguous", "Select a shared capability.")
        return matches[0]

    async def invoke_tool(self, grant: ShareGrant, qualified_name: str, arguments: dict):
        export = self.find_tool_export(grant, qualified_name)
        started = time.monotonic()
        audit_id = self.start_audit(
            grant.id, export.id, operation=f"tool:{qualified_name}"
        )
        try:
            result = await self.tools.execute(
                qualified_name,
                arguments,
                context=ToolCallContext(caller_id=f"share:{grant.id}"),
            )
        except ToolGatewayError as exc:
            self.finish_audit(
                audit_id,
                status="failed",
                duration_ms=int((time.monotonic() - started) * 1000),
                error_code=exc.code,
            )
            raise SharingError(exc.code, str(exc), status_code=422) from exc
        self.finish_audit(
            audit_id,
            status="completed",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return result

    def _agent_export(self, grant: ShareGrant, agent_key: str) -> CapabilityExport:
        return self.find_export(grant, kind=CapabilityKind.AGENT, target_id=agent_key)

    def _sharing_app_instance(self) -> str:
        with self.database.transaction() as connection:
            row = connection.execute(
                """SELECT i.id FROM app_instances i
                JOIN app_definitions d ON d.id=i.app_definition_id
                WHERE d.package_id='ai2apps.agents' AND i.status='active'
                ORDER BY i.created_at LIMIT 1"""
            ).fetchone()
            definition = connection.execute(
                "SELECT id FROM app_definitions WHERE package_id='ai2apps.agents' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if row is not None:
            return str(row["id"])
        if definition is None:
            raise SharingError("agent_runtime_unavailable", "Sharing Agent App is unavailable.", status_code=503)
        try:
            return AppRepository(self.database).create_instance(
                app_definition_id=str(definition["id"]), singleton_key="system"
            ).id
        except Exception:
            with self.database.transaction() as connection:
                row = connection.execute(
                    """SELECT i.id FROM app_instances i JOIN app_definitions d ON d.id=i.app_definition_id
                    WHERE d.package_id='ai2apps.agents' AND i.status='active' ORDER BY i.created_at LIMIT 1"""
                ).fetchone()
            if row is None:
                raise
            return str(row["id"])

    def create_agent_session(self, grant: ShareGrant, agent_key: str, *, title: str = "") -> dict:
        export = self._agent_export(grant, agent_key)
        if self.agents is None:
            raise SharingError("agent_runtime_unavailable", "Agent runtime is unavailable.", status_code=503)
        self.agents.get_definition(agent_key)
        session = SessionRepository(self.database).create(
            app_instance_id=self._sharing_app_instance(),
            title=(title.strip()[:200] if title else f"Shared {export.display_name}"),
            session_kind=SessionKind.AGENT_CHILD,
            visibility=SessionVisibility.UNLISTED,
            retention=SessionRetention.TEMPORARY,
            metadata={"sharing": {"grant_id": grant.id, "agent_key": agent_key, "export_id": export.id}},
        )
        return {"session_id": session.id, "agent": agent_key, "status": session.status.value}

    def _agent_session(self, grant: ShareGrant, agent_key: str, session_id: str):
        self._agent_export(grant, agent_key)
        try:
            session = SessionRepository(self.database).get(session_id)
        except ResourceNotFoundError as exc:
            raise SharingError("agent_session_not_found", "Shared Agent Session not found.", status_code=404) from exc
        sharing = session.metadata.get("sharing", {}) if isinstance(session.metadata, dict) else {}
        if session.status is not SessionStatus.ACTIVE or sharing.get("grant_id") != grant.id or sharing.get("agent_key") != agent_key:
            raise SharingError("agent_session_not_found", "Shared Agent Session not found.", status_code=404)
        return session

    def send_agent_message(
        self, grant: ShareGrant, agent_key: str, session_id: str, *, prompt: str,
        parameters: dict | None = None, model: str | None = None,
        instructions: str | None = None, idempotency_key: str | None = None,
    ) -> dict:
        self._agent_session(grant, agent_key, session_id)
        if self.agents is None or self.agent_runtime is None:
            raise SharingError("agent_runtime_unavailable", "Agent runtime is unavailable.", status_code=503)
        if not isinstance(prompt, str) or not prompt.strip():
            raise SharingError("agent_prompt_required", "Agent prompt must be non-empty.", status_code=422)
        payload = {
            "prompt": prompt.strip(),
            "parameters": parameters or {},
            "invocation": {"source": "shared_mcp"},
        }
        if model:
            payload["model"] = model
        if instructions:
            payload["instructions"] = instructions
        try:
            run, created = self.agents.create_run(
                session_id=session_id, agent_key=agent_key, input=payload,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:
            raise SharingError("agent_run_rejected", "Agent Run could not be created.", status_code=422) from exc
        self.agent_runtime.wake()
        return {"run_id": run.id, "session_id": session_id, "agent": agent_key, "status": run.status.value, "created": created}

    def agent_run_status(self, grant: ShareGrant, agent_key: str, session_id: str, run_id: str) -> dict:
        self._agent_session(grant, agent_key, session_id)
        if self.agents is None:
            raise SharingError("agent_runtime_unavailable", "Agent runtime is unavailable.", status_code=503)
        try:
            run = self.agents.get_run(run_id)
        except Exception as exc:
            raise SharingError("agent_run_not_found", "Shared Agent Run not found.", status_code=404) from exc
        definition = self.agents.get_definition(run.agent_definition_id)
        if run.session_id != session_id or definition.agent_key != agent_key:
            raise SharingError("agent_run_not_found", "Shared Agent Run not found.", status_code=404)
        return {
            "run_id": run.id, "session_id": run.session_id, "agent": agent_key,
            "status": run.status.value, "output": run.output, "error": run.error,
            "current_step": run.current_step, "created_at": format_utc(run.created_at),
            "updated_at": format_utc(run.updated_at),
            "finished_at": None if run.finished_at is None else format_utc(run.finished_at),
        }

    def agent_messages(self, grant: ShareGrant, agent_key: str, session_id: str, *, after: int = 0, limit: int = 100) -> dict:
        self._agent_session(grant, agent_key, session_id)
        limit = max(1, min(int(limit), 200))
        items = MessageRepository(self.database).list_for_session(session_id, after_sequence=max(0, int(after)), limit=limit)
        return {
            "session_id": session_id,
            "messages": [
                {
                    "id": item.message.id, "sequence": item.message.sequence,
                    "role": item.message.role.value, "status": item.message.status.value,
                    "parts": [{"kind": part.kind, "content": part.content} for part in item.parts],
                }
                for item in items
            ],
        }

    def cancel_agent_run(self, grant: ShareGrant, agent_key: str, session_id: str, run_id: str) -> dict:
        self.agent_run_status(grant, agent_key, session_id, run_id)
        run = self.agent_runtime.cancel(run_id)
        return {"run_id": run.id, "status": run.status.value}

    def close_agent_session(self, grant: ShareGrant, agent_key: str, session_id: str) -> dict:
        self._agent_session(grant, agent_key, session_id)
        self._close_agent_sessions(session_id=session_id)
        updated = SessionRepository(self.database).get(session_id)
        return {"session_id": updated.id, "status": updated.status.value}

    def start_audit(
        self, grant_id: str, export_id: str | None, *, operation: str
    ) -> str:
        audit_id = self._id("sha_")
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO capability_share_audit(
                    id,grant_id,export_id,operation,status,created_at
                ) VALUES (?,?,?,?,?,?)
                """,
                (audit_id, grant_id, export_id, operation, "started", utc_now_text()),
            )
        return audit_id

    def finish_audit(
        self,
        audit_id: str,
        *,
        status: str,
        duration_ms: int,
        error_code: str | None = None,
    ) -> None:
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                UPDATE capability_share_audit
                SET status=?,duration_ms=?,error_code=? WHERE id=?
                """,
                (status, duration_ms, error_code, audit_id),
            )
