"""Persistence and matching for capability policy and GrantLeases."""

from __future__ import annotations

import fnmatch
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from ai2apps.core import (
    EntityIdKind,
    ResourceConflictError,
    ResourceNotFoundError,
    new_entity_id,
    parse_utc,
    utc_now_text,
)
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase

from .models import (
    CapabilityPolicyRecord,
    CapabilityRequestRecord,
    CapabilityRequestStatus,
    GrantLeaseRecord,
    GrantScope,
    PolicyEffect,
)
from .risk import risk_level as classify_risk_level


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _time(value: str | None):
    return None if value is None else parse_utc(value)


class CapabilityRepository:
    def __init__(self, database: PlatformDatabase, events: EventStore) -> None:
        self.database = database
        self.events = events

    @staticmethod
    def _policy(row) -> CapabilityPolicyRecord:
        return CapabilityPolicyRecord(
            id=row["id"],
            policy_key=row["policy_key"],
            effect=PolicyEffect(row["effect"]),
            capability_pattern=row["capability_pattern"],
            agent_pattern=row["agent_pattern"],
            tool_pattern=row["tool_pattern"],
            priority=row["priority"],
            enabled=bool(row["enabled"]),
            source=row["source"],
            conditions=json.loads(row["conditions_json"]),
            revision=row["revision"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _lease(row) -> GrantLeaseRecord:
        return GrantLeaseRecord(
            id=row["id"],
            scope=GrantScope(row["scope"]),
            scope_id=row["scope_id"],
            agent_definition_id=row["agent_definition_id"],
            session_id=row["session_id"],
            app_instance_id=row["app_instance_id"],
            capabilities=tuple(json.loads(row["capabilities_json"])),
            tool_pattern=row["tool_pattern"],
            tool_service_digest=row["tool_service_digest"],
            resource_selector=json.loads(row["resource_selector_json"]),
            issued_by=row["issued_by"],
            evidence=json.loads(row["evidence_json"]),
            expires_at=_time(row["expires_at"]),
            revoked_at=_time(row["revoked_at"]),
            revoke_reason=row["revoke_reason"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _request(row) -> CapabilityRequestRecord:
        return CapabilityRequestRecord(
            id=row["id"],
            subject_kind=row["subject_kind"],
            app_instance_id=row["app_instance_id"],
            session_id=row["session_id"],
            run_id=row["run_id"],
            capabilities=tuple(json.loads(row["capabilities_json"])),
            tool_name=row["tool_name"],
            effects=tuple(json.loads(row["effects_json"])),
            resource_selector=json.loads(row["resource_selector_json"]),
            reason=row["reason"],
            risk_level=row["risk_level"],
            status=CapabilityRequestStatus(row["status"]),
            requested_by=row["requested_by"],
            decision_scope=row["decision_scope"],
            decision_evidence=json.loads(row["decision_evidence_json"]),
            grant_lease_id=row["grant_lease_id"],
            deadline_at=parse_utc(row["deadline_at"]),
            revision=row["revision"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
            resolved_at=_time(row["resolved_at"]),
        )

    def ensure_builtin_defaults(self) -> None:
        self.upsert_policy(
            policy_key="builtin.default-require-approval",
            effect=PolicyEffect.REQUIRE_APPROVAL,
            capability_pattern="*",
            agent_pattern="*",
            tool_pattern="*",
            priority=-1000,
            source="builtin",
        )

    def upsert_policy(
        self,
        *,
        policy_key: str,
        effect: PolicyEffect,
        capability_pattern: str,
        agent_pattern: str = "*",
        tool_pattern: str = "*",
        priority: int = 0,
        source: str = "local",
        conditions: dict[str, Any] | None = None,
    ) -> CapabilityPolicyRecord:
        if not all((policy_key, capability_pattern, agent_pattern, tool_pattern)):
            raise ValueError("Policy keys and patterns cannot be empty")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM capability_policies WHERE policy_key = ?", (policy_key,)
            ).fetchone()
            if row is None:
                policy_id = new_entity_id(EntityIdKind.CAPABILITY_POLICY)
                connection.execute(
                    """INSERT INTO capability_policies(
                        id, policy_key, effect, capability_pattern, agent_pattern,
                        tool_pattern, priority, source, conditions_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        policy_id,
                        policy_key,
                        effect.value,
                        capability_pattern,
                        agent_pattern,
                        tool_pattern,
                        priority,
                        source,
                        _json(conditions or {}),
                        now,
                        now,
                    ),
                )
            else:
                policy_id = row["id"]
                connection.execute(
                    """UPDATE capability_policies SET effect = ?, capability_pattern = ?,
                        agent_pattern = ?, tool_pattern = ?, priority = ?, source = ?,
                        conditions_json = ?, revision = revision + 1, updated_at = ?
                        WHERE id = ?""",
                    (
                        effect.value,
                        capability_pattern,
                        agent_pattern,
                        tool_pattern,
                        priority,
                        source,
                        _json(conditions or {}),
                        now,
                        policy_id,
                    ),
                )
            result = connection.execute(
                "SELECT * FROM capability_policies WHERE id = ?", (policy_id,)
            ).fetchone()
            assert result is not None
            return self._policy(result)

    def list_policies(self) -> tuple[CapabilityPolicyRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM capability_policies ORDER BY priority DESC, policy_key"
            ).fetchall()
        return tuple(self._policy(row) for row in rows)

    def matching_policies(
        self, *, agent_key: str, tool_name: str, capability: str
    ) -> tuple[CapabilityPolicyRecord, ...]:
        return tuple(
            policy
            for policy in self.list_policies()
            if policy.enabled
            and fnmatch.fnmatchcase(agent_key, policy.agent_pattern)
            and fnmatch.fnmatchcase(tool_name, policy.tool_pattern)
            and fnmatch.fnmatchcase(capability, policy.capability_pattern)
        )

    def create_lease(
        self,
        *,
        run_id: str,
        scope: GrantScope,
        capabilities: tuple[str, ...],
        tool_pattern: str,
        issued_by: str,
        evidence: dict[str, Any],
        expires_at: datetime | None = None,
        resource_selector: dict[str, Any] | None = None,
    ) -> GrantLeaseRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            run = connection.execute(
                """SELECT r.*, s.app_instance_id FROM agent_runs r
                   JOIN sessions s ON s.id = r.session_id WHERE r.id = ?""",
                (run_id,),
            ).fetchone()
            if run is None:
                raise ResourceNotFoundError("agent_run", run_id)
            scope_id = {
                GrantScope.RUN: run_id,
                GrantScope.SESSION: run["session_id"],
                GrantScope.AGENT: run["agent_definition_id"],
                GrantScope.APP: run["app_instance_id"],
            }[scope]
            lease_id = new_entity_id(EntityIdKind.GRANT_LEASE)
            tool_row = connection.execute(
                """SELECT s.active_package_digest FROM tool_descriptors t
                   JOIN service_descriptors s ON s.id = t.service_id
                   WHERE t.qualified_name = ?""",
                (tool_pattern,),
            ).fetchone()
            tool_service_digest = None if tool_row is None else tool_row[0]
            connection.execute(
                """INSERT INTO grant_leases(
                    id, scope, scope_id, agent_definition_id, session_id,
                    app_instance_id, capabilities_json, tool_pattern, tool_service_digest,
                    resource_selector_json, issued_by, evidence_json, expires_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    lease_id,
                    scope.value,
                    scope_id,
                    run["agent_definition_id"],
                    run["session_id"],
                    run["app_instance_id"],
                    _json(sorted(set(capabilities))),
                    tool_pattern,
                    tool_service_digest,
                    _json(resource_selector or {}),
                    issued_by,
                    _json(evidence),
                    None
                    if expires_at is None
                    else expires_at.isoformat().replace("+00:00", "Z"),
                    now,
                    now,
                ),
            )
            self.events.append_in_transaction(
                connection,
                event_type="capability.grant.created",
                subject_id=lease_id,
                app_instance_id=run["app_instance_id"],
                session_id=run["session_id"],
                trace_id=run_id,
                payload={
                    "run_id": run_id,
                    "scope": scope.value,
                    "capabilities": sorted(set(capabilities)),
                    "tool_pattern": tool_pattern,
                    "issued_by": issued_by,
                    "evidence": evidence,
                },
            )
            row = connection.execute(
                "SELECT * FROM grant_leases WHERE id = ?", (lease_id,)
            ).fetchone()
            assert row is not None
            return self._lease(row)

    def active_leases_for_run(
        self, run_id: str, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> tuple[GrantLeaseRecord, ...]:
        now = utc_now_text()
        with self.database.transaction() as connection:
            run = connection.execute(
                """SELECT r.id, r.agent_definition_id, r.session_id, s.app_instance_id
                   FROM agent_runs r JOIN sessions s ON s.id = r.session_id
                   WHERE r.id = ?""",
                (run_id,),
            ).fetchone()
            if run is None:
                raise ResourceNotFoundError("agent_run", run_id)
            rows = connection.execute(
                """SELECT * FROM grant_leases WHERE revoked_at IS NULL
                   AND (expires_at IS NULL OR expires_at > ?)
                   AND agent_definition_id = ?
                   AND ((scope = 'run' AND scope_id = ?)
                     OR (scope = 'session' AND scope_id = ?)
                     OR (scope = 'agent' AND scope_id = ?)
                     OR (scope = 'app' AND scope_id = ?))
                   ORDER BY created_at""",
                (
                    now,
                    run["agent_definition_id"],
                    run["id"],
                    run["session_id"],
                    run["agent_definition_id"],
                    run["app_instance_id"],
                ),
            ).fetchall()
        with self.database.transaction() as connection:
            tool_row = connection.execute(
                """SELECT s.active_package_digest FROM tool_descriptors t
                   JOIN service_descriptors s ON s.id = t.service_id
                   WHERE t.qualified_name = ?""",
                (tool_name,),
            ).fetchone()
        current_digest = None if tool_row is None else tool_row[0]
        stale_ids = [
            row["id"] for row in rows
            if row["tool_service_digest"] is not None
            and row["tool_service_digest"] != current_digest
        ]
        for lease_id in stale_ids:
            self.revoke_lease(lease_id, reason="tool-version-changed")

        def resource_matches(row) -> bool:
            selector = json.loads(row["resource_selector_json"])
            exact = selector.get("arguments", {})
            if not exact:
                return True
            supplied = arguments or {}
            return all(supplied.get(key) == value for key, value in exact.items())

        return tuple(
            self._lease(row)
            for row in rows
            if row["id"] not in stale_ids
            and fnmatch.fnmatchcase(tool_name, row["tool_pattern"])
            and resource_matches(row)
        )

    def consume_single_use_leases(self, lease_ids: tuple[str, ...]) -> tuple[str, ...]:
        """Atomically consume approval leases issued for exactly one invocation."""

        if not lease_ids:
            return ()
        now = utc_now_text()
        consumed: list[str] = []
        with self.database.transaction(write=True) as connection:
            for lease_id in lease_ids:
                row = connection.execute(
                    "SELECT * FROM grant_leases WHERE id = ? AND revoked_at IS NULL",
                    (lease_id,),
                ).fetchone()
                if row is None or not json.loads(row["evidence_json"]).get("single_use"):
                    continue
                connection.execute(
                    """UPDATE grant_leases SET revoked_at = ?, revoke_reason = 'consumed',
                       updated_at = ? WHERE id = ?""",
                    (now, now, lease_id),
                )
                self.events.append_in_transaction(
                    connection,
                    event_type="capability.grant.consumed",
                    subject_id=lease_id,
                    app_instance_id=row["app_instance_id"],
                    session_id=row["session_id"],
                    payload={"reason": "single-use"},
                )
                consumed.append(lease_id)
        return tuple(consumed)

    def expire_leases(self) -> int:
        """Materialize time-based expiry so it is visible in the audit trail."""

        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            rows = connection.execute(
                """SELECT * FROM grant_leases WHERE revoked_at IS NULL
                   AND expires_at IS NOT NULL AND expires_at <= ?""",
                (now,),
            ).fetchall()
            for row in rows:
                connection.execute(
                    """UPDATE grant_leases SET revoked_at = ?, revoke_reason = 'expired',
                       updated_at = ? WHERE id = ?""",
                    (now, now, row["id"]),
                )
                self.events.append_in_transaction(
                    connection,
                    event_type="capability.grant.expired",
                    subject_id=row["id"],
                    app_instance_id=row["app_instance_id"],
                    session_id=row["session_id"],
                    payload={"reason": "expired"},
                )
        return len(rows)

    def list_leases(
        self, *, include_inactive: bool = False
    ) -> tuple[GrantLeaseRecord, ...]:
        where = (
            ""
            if include_inactive
            else "WHERE revoked_at IS NULL AND (expires_at IS NULL OR expires_at > ?)"
        )
        params = () if include_inactive else (utc_now_text(),)
        with self.database.transaction() as connection:
            rows = connection.execute(
                f"SELECT * FROM grant_leases {where} ORDER BY created_at DESC", params
            ).fetchall()
        return tuple(self._lease(row) for row in rows)

    def revoke_lease(self, lease_id: str, *, reason: str) -> GrantLeaseRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM grant_leases WHERE id = ?", (lease_id,)
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("grant_lease", lease_id)
            if row["revoked_at"] is not None:
                if row["revoke_reason"] == reason:
                    return self._lease(row)
                raise ResourceConflictError("GrantLease is already revoked")
            connection.execute(
                """UPDATE grant_leases SET revoked_at = ?, revoke_reason = ?,
                   updated_at = ? WHERE id = ?""",
                (now, reason, now, lease_id),
            )
            self.events.append_in_transaction(
                connection,
                event_type="capability.grant.revoked",
                subject_id=lease_id,
                app_instance_id=row["app_instance_id"],
                session_id=row["session_id"],
                payload={"reason": reason},
            )
            result = connection.execute(
                "SELECT * FROM grant_leases WHERE id = ?", (lease_id,)
            ).fetchone()
            assert result is not None
            return self._lease(result)

    def revoke_all(self, *, reason: str) -> tuple[GrantLeaseRecord, ...]:
        """Revoke every currently active lease as one auditable recovery action."""
        now = utc_now_text()
        revoked_ids: list[str] = []
        with self.database.transaction(write=True) as connection:
            rows = connection.execute(
                """SELECT * FROM grant_leases WHERE revoked_at IS NULL
                   AND (expires_at IS NULL OR expires_at > ?)""",
                (now,),
            ).fetchall()
            for row in rows:
                connection.execute(
                    """UPDATE grant_leases SET revoked_at = ?, revoke_reason = ?,
                       updated_at = ? WHERE id = ?""",
                    (now, reason, now, row["id"]),
                )
                self.events.append_in_transaction(
                    connection,
                    event_type="capability.grant.revoked",
                    subject_id=row["id"],
                    app_instance_id=row["app_instance_id"],
                    session_id=row["session_id"],
                    payload={"reason": reason, "recovery": True},
                )
                revoked_ids.append(row["id"])
            return tuple(
                self._lease(
                    connection.execute(
                        "SELECT * FROM grant_leases WHERE id = ?", (lease_id,)
                    ).fetchone()
                )
                for lease_id in revoked_ids
            )

    @staticmethod
    def risk_level(effects: tuple[str, ...]) -> str:
        return classify_risk_level(effects)

    def create_app_request(
        self,
        *,
        app_instance_id: str,
        session_id: str,
        capabilities: tuple[str, ...],
        tool_name: str = "*",
        effects: tuple[str, ...] = (),
        resource_selector: dict[str, Any] | None = None,
        reason: str,
        requested_by: str = "app-bridge",
        timeout_seconds: int = 600,
    ) -> CapabilityRequestRecord:
        capabilities = tuple(sorted({item.strip() for item in capabilities if item.strip()}))
        if not capabilities:
            raise ValueError("At least one capability is required")
        if not reason.strip():
            raise ValueError("Capability reason cannot be empty")
        if timeout_seconds < 30 or timeout_seconds > 3600:
            raise ValueError("Capability request timeout must be between 30 and 3600 seconds")
        request_id = new_entity_id(EntityIdKind.CAPABILITY_REQUEST)
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat().replace("+00:00", "Z")
        deadline = (now_dt + timedelta(seconds=timeout_seconds)).isoformat().replace(
            "+00:00", "Z"
        )
        selector = resource_selector or {}
        with self.database.transaction(write=True) as connection:
            scope = connection.execute(
                """SELECT s.app_instance_id AS session_owner,
                          d.package_id, d.display_name
                   FROM app_instances i
                   JOIN app_definitions d ON d.id = i.app_definition_id
                   JOIN sessions s ON s.id = ?
                   WHERE i.id = ? AND i.status != 'closed' AND s.status = 'active'""",
                (session_id, app_instance_id),
            ).fetchone()
            if scope is None:
                raise ResourceNotFoundError("app_instance_or_session", app_instance_id)
            allowed = scope["session_owner"] == app_instance_id or connection.execute(
                """SELECT 1 FROM app_mounts WHERE app_instance_id = ?
                   AND interaction_session_id = ? AND status = 'mounted'""",
                (app_instance_id, session_id),
            ).fetchone()
            if not allowed:
                raise ResourceConflictError("Session is outside App scope")
            connection.execute(
                """INSERT INTO capability_requests(
                    id, subject_kind, app_instance_id, session_id,
                    capabilities_json, tool_name, effects_json,
                    resource_selector_json, reason, risk_level, requested_by,
                    deadline_at, created_at, updated_at
                ) VALUES (?, 'app', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    request_id,
                    app_instance_id,
                    session_id,
                    _json(capabilities),
                    tool_name or "*",
                    _json(sorted(set(effects))),
                    _json(selector),
                    reason.strip(),
                    self.risk_level(effects),
                    requested_by,
                    deadline,
                    now,
                    now,
                ),
            )
            self.events.append_in_transaction(
                connection,
                event_type="capability.request.created",
                subject_id=request_id,
                app_instance_id=app_instance_id,
                session_id=session_id,
                payload={
                    "subject_kind": "app",
                    "capabilities": capabilities,
                    "tool_name": tool_name or "*",
                    "effects": sorted(set(effects)),
                    "resource_selector": selector,
                    "reason": reason.strip(),
                    "risk_level": self.risk_level(effects),
                    "requested_by": requested_by,
                    "deadline_at": deadline,
                },
            )
            row = connection.execute(
                "SELECT * FROM capability_requests WHERE id = ?", (request_id,)
            ).fetchone()
            assert row is not None
            return self._request(row)

    def get_request(self, request_id: str) -> CapabilityRequestRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM capability_requests WHERE id = ?", (request_id,)
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("capability_request", request_id)
        return self._request(row)

    def list_requests(
        self, *, include_resolved: bool = False
    ) -> tuple[CapabilityRequestRecord, ...]:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            expired = connection.execute(
                """SELECT * FROM capability_requests
                   WHERE status = 'pending' AND deadline_at <= ?""",
                (now,),
            ).fetchall()
            for row in expired:
                connection.execute(
                    """UPDATE capability_requests SET status = 'expired',
                       revision = revision + 1, updated_at = ?, resolved_at = ?
                       WHERE id = ?""",
                    (now, now, row["id"]),
                )
                self.events.append_in_transaction(
                    connection,
                    event_type="capability.request.expired",
                    subject_id=row["id"],
                    app_instance_id=row["app_instance_id"],
                    session_id=row["session_id"],
                    payload={"deadline_at": row["deadline_at"]},
                )
            query = "SELECT * FROM capability_requests"
            if not include_resolved:
                query += " WHERE status = 'pending'"
            query += " ORDER BY created_at DESC"
            rows = connection.execute(query).fetchall()
        return tuple(self._request(row) for row in rows)

    def decide_app_request(
        self,
        request_id: str,
        *,
        decision: str,
        scope: str = "once",
        issued_by: str = "user",
        duration_seconds: int | None = None,
        resource_selector: dict[str, Any] | None = None,
    ) -> tuple[CapabilityRequestRecord, GrantLeaseRecord | None]:
        if decision not in {"approve", "deny"}:
            raise ValueError("Decision must be approve or deny")
        if scope not in {"once", "session", "app"}:
            raise ValueError("App approval scope must be once, session, or app")
        if duration_seconds is not None and not 60 <= duration_seconds <= 86400:
            raise ValueError("Grant duration must be between 60 and 86400 seconds")
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat().replace("+00:00", "Z")
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM capability_requests WHERE id = ?", (request_id,)
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("capability_request", request_id)
            if row["subject_kind"] != "app":
                raise ResourceConflictError("CapabilityRequest is not App-owned")
            if row["status"] != "pending":
                lease = None
                if row["grant_lease_id"] is not None:
                    lease_row = connection.execute(
                        "SELECT * FROM grant_leases WHERE id = ?",
                        (row["grant_lease_id"],),
                    ).fetchone()
                    lease = None if lease_row is None else self._lease(lease_row)
                return self._request(row), lease
            if row["deadline_at"] <= now:
                connection.execute(
                    """UPDATE capability_requests SET status='expired', resolved_at=?,
                       updated_at=?, revision=revision+1 WHERE id=?""",
                    (now, now, request_id),
                )
                raise ResourceConflictError("CapabilityRequest has expired")
            evidence = {
                "decision": decision,
                "scope": scope,
                "issued_by": issued_by,
                "requested_resource": json.loads(row["resource_selector_json"]),
            }
            if decision == "deny":
                connection.execute(
                    """UPDATE capability_requests SET status='denied',
                       decision_scope=?, decision_evidence_json=?, resolved_at=?,
                       updated_at=?, revision=revision+1 WHERE id=?""",
                    (scope, _json(evidence), now, now, request_id),
                )
                self.events.append_in_transaction(
                    connection,
                    event_type="capability.decision.deny",
                    subject_id=request_id,
                    app_instance_id=row["app_instance_id"],
                    session_id=row["session_id"],
                    payload=evidence,
                )
                resolved = connection.execute(
                    "SELECT * FROM capability_requests WHERE id = ?", (request_id,)
                ).fetchone()
                assert resolved is not None
                return self._request(resolved), None

            lease_id = new_entity_id(EntityIdKind.GRANT_LEASE)
            lease_scope = GrantScope.SESSION if scope == "session" else GrantScope.APP
            scope_id = (
                row["session_id"]
                if lease_scope is GrantScope.SESSION
                else row["app_instance_id"]
            )
            lifetime = 300 if scope == "once" and duration_seconds is None else duration_seconds
            expires_at = None
            if lifetime is not None:
                expires_at = (now_dt + timedelta(seconds=lifetime)).isoformat().replace(
                    "+00:00", "Z"
                )
            selector = resource_selector or json.loads(row["resource_selector_json"])
            tool_row = connection.execute(
                """SELECT s.active_package_digest FROM tool_descriptors t
                   JOIN service_descriptors s ON s.id = t.service_id
                   WHERE t.qualified_name = ?""",
                (row["tool_name"],),
            ).fetchone()
            tool_service_digest = None if tool_row is None else tool_row[0]
            evidence["expires_at"] = expires_at
            evidence["single_use"] = scope == "once"
            connection.execute(
                """INSERT INTO grant_leases(
                    id, scope, scope_id, agent_definition_id, session_id,
                    app_instance_id, capabilities_json, tool_pattern,
                    tool_service_digest, resource_selector_json, issued_by,
                    evidence_json, request_id, expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    lease_id,
                    lease_scope.value,
                    scope_id,
                    row["session_id"],
                    row["app_instance_id"],
                    row["capabilities_json"],
                    row["tool_name"],
                    tool_service_digest,
                    _json(selector),
                    issued_by,
                    _json(evidence),
                    request_id,
                    expires_at,
                    now,
                    now,
                ),
            )
            connection.execute(
                """UPDATE capability_requests SET status='approved',
                   decision_scope=?, decision_evidence_json=?, grant_lease_id=?,
                   resolved_at=?, updated_at=?, revision=revision+1 WHERE id=?""",
                (scope, _json(evidence), lease_id, now, now, request_id),
            )
            for event_type, subject_id, payload in (
                ("capability.decision.allow", request_id, evidence),
                (
                    "capability.grant.created",
                    lease_id,
                    {
                        "request_id": request_id,
                        "scope": lease_scope.value,
                        "approval_mode": scope,
                        "capabilities": json.loads(row["capabilities_json"]),
                        "tool_pattern": row["tool_name"],
                        "issued_by": issued_by,
                        "evidence": evidence,
                    },
                ),
            ):
                self.events.append_in_transaction(
                    connection,
                    event_type=event_type,
                    subject_id=subject_id,
                    app_instance_id=row["app_instance_id"],
                    session_id=row["session_id"],
                    payload=payload,
                )
            resolved = connection.execute(
                "SELECT * FROM capability_requests WHERE id = ?", (request_id,)
            ).fetchone()
            lease = connection.execute(
                "SELECT * FROM grant_leases WHERE id = ?", (lease_id,)
            ).fetchone()
            assert resolved is not None and lease is not None
            return self._request(resolved), self._lease(lease)

    def record_decision(
        self,
        *,
        run_id: str,
        interaction_id: str | None,
        decision: PolicyEffect,
        source: str,
        capabilities: tuple[str, ...],
        tool_name: str,
        effects: tuple[str, ...],
        matched_policy_ids: tuple[str, ...] = (),
        evidence: dict[str, Any] | None = None,
    ) -> None:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            decision_id = new_entity_id(EntityIdKind.CAPABILITY_DECISION)
            run = connection.execute(
                """SELECT r.session_id, s.app_instance_id FROM agent_runs r
                   JOIN sessions s ON s.id = r.session_id WHERE r.id = ?""",
                (run_id,),
            ).fetchone()
            if run is None:
                raise ResourceNotFoundError("agent_run", run_id)
            connection.execute(
                """INSERT INTO capability_decisions(
                    id, run_id, interaction_id, decision, decision_source,
                    capabilities_json, tool_name, effects_json,
                    matched_policy_ids_json, evidence_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    decision_id,
                    run_id,
                    interaction_id,
                    decision.value,
                    source,
                    _json(capabilities),
                    tool_name,
                    _json(effects),
                    _json(matched_policy_ids),
                    _json(evidence or {}),
                    now,
                ),
            )
            self.events.append_in_transaction(
                connection,
                event_type=f"capability.decision.{decision.value}",
                subject_id=run_id,
                app_instance_id=run["app_instance_id"],
                session_id=run["session_id"],
                trace_id=run_id,
                payload={
                    "decision_id": decision_id,
                    "source": source,
                    "capabilities": capabilities,
                    "tool_name": tool_name,
                    "matched_policy_ids": matched_policy_ids,
                    "evidence": evidence or {},
                },
            )
