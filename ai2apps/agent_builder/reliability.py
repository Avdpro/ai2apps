"""P3 health, drift, incremental state, and repair lifecycle for Site Agents."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ai2apps.core import (
    EntityIdKind,
    ResourceConflictError,
    ResourceNotFoundError,
    format_utc,
    new_entity_id,
    parse_utc,
    utc_now,
    utc_now_text,
)

from .compiler import COMPILER_VERSION, compile_source
from .models import (
    AgentCapabilityHealthRecord,
    AgentHealthStatus,
    AgentRepairCandidateRecord,
    AgentSiteStateRecord,
)
from .repository import AgentBuilderRepository, _json

STRUCTURAL_ERRORS = frozenset({
    "browser_agent_output_invalid",
    "browser_agent_step_failed",
    "browser_agent_unknown_step",
    "selector_not_found",
    "validation_failed",
    "pipeline_drift",
})
USER_ERRORS = frozenset({
    "browser_agent_needs_user", "login_required", "captcha_required",
    "terms_consent_required", "access_restricted", "paywall_detected",
})
TRANSIENT_ERRORS = frozenset({
    "network_error", "dns_error", "tls_error", "navigation_timeout",
    "render_timeout", "browser_context_unavailable", "service_unavailable",
})


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def _canonical_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value.strip()
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return value.strip()
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))


def classify_failure(error: dict[str, Any] | None) -> str:
    code = str((error or {}).get("code") or "unknown_error").lower()
    if code in USER_ERRORS or any(token in code for token in ("captcha", "login", "paywall", "consent")):
        return "needs_user"
    if code in TRANSIENT_ERRORS or any(token in code for token in ("network", "timeout", "unavailable", "5xx")):
        return "transient"
    if code in STRUCTURAL_ERRORS or any(token in code for token in ("selector", "schema", "validation", "drift")):
        return "structural"
    if "permission" in code or "capability" in code:
        return "policy"
    return "execution"


class AgentReliabilityService:
    CIRCUIT_FAILURES = 3
    CIRCUIT_COOLDOWN = timedelta(hours=1)

    def __init__(self, store: AgentBuilderRepository) -> None:
        self.store = store
        self.database = store.database

    @staticmethod
    def _health(row) -> AgentCapabilityHealthRecord:
        return AgentCapabilityHealthRecord(
            id=row["id"], owner_user_id=row["owner_user_id"], draft_id=row["draft_id"],
            capability_name=row["capability_name"], status=AgentHealthStatus(row["status"]),
            consecutive_failures=row["consecutive_failures"], success_count=row["success_count"],
            failure_count=row["failure_count"], last_error_class=row["last_error_class"],
            last_error=None if row["last_error_json"] is None else json.loads(row["last_error_json"]),
            structure_fingerprint=row["structure_fingerprint"],
            circuit_open_until=None if row["circuit_open_until"] is None else parse_utc(row["circuit_open_until"]),
            metrics=json.loads(row["metrics_json"]), last_run_id=row["last_run_id"],
            last_success_at=None if row["last_success_at"] is None else parse_utc(row["last_success_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _state(row) -> AgentSiteStateRecord:
        return AgentSiteStateRecord(
            id=row["id"], owner_user_id=row["owner_user_id"], draft_id=row["draft_id"],
            capability_name=row["capability_name"], source_identity=row["source_identity"],
            generation_id=row["generation_id"], checkpoint=json.loads(row["checkpoint_json"]),
            item_index=json.loads(row["item_index_json"]),
            structure_fingerprint=row["structure_fingerprint"],
            calibration_status=row["calibration_status"], updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _repair(row) -> AgentRepairCandidateRecord:
        return AgentRepairCandidateRecord(
            id=row["id"], owner_user_id=row["owner_user_id"], draft_id=row["draft_id"],
            capability_name=row["capability_name"], base_generation_id=row["base_generation_id"],
            candidate_generation_id=row["candidate_generation_id"], strategy=row["strategy"],
            source=json.loads(row["source_json"]), report=json.loads(row["report_json"]),
            status=row["status"], created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    def health(self, owner_user_id: str, draft_id: str, capability_name: str) -> AgentCapabilityHealthRecord | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM agent_capability_health WHERE owner_user_id=? AND draft_id=? AND capability_name=?",
                (owner_user_id, draft_id, capability_name),
            ).fetchone()
        return None if row is None else self._health(row)

    def list_health(self, owner_user_id: str) -> tuple[AgentCapabilityHealthRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_capability_health WHERE owner_user_id=? ORDER BY updated_at DESC,id",
                (owner_user_id,),
            ).fetchall()
        return tuple(self._health(row) for row in rows)

    def require_circuit_closed(self, owner_user_id: str, draft_id: str, capability_name: str) -> None:
        record = self.health(owner_user_id, draft_id, capability_name)
        if record and record.circuit_open_until and record.circuit_open_until > utc_now():
            raise ResourceConflictError(
                f"Agent capability circuit is open until {format_utc(record.circuit_open_until)}"
            )

    @staticmethod
    def _result(run) -> dict[str, Any]:
        output = dict(run.output or {})
        result = output.get("result")
        return result if isinstance(result, dict) else output

    @staticmethod
    def _item_index(result: dict[str, Any]) -> dict[str, str]:
        items = result.get("items")
        if not isinstance(items, list):
            return {}
        indexed: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            key = str(item.get("id") or _canonical_url(str(item.get("url") or ""))).strip()
            if not key:
                continue
            indexed[key] = _digest({k: item.get(k) for k in ("title", "url", "published_at", "summary", "content")})
        return indexed

    def _commit_state(
        self, *, owner_user_id: str, draft_id: str, capability_name: str,
        generation_id: str, result: dict[str, Any], structure_fingerprint: str,
        source_identity: str,
    ) -> dict[str, Any]:
        current = self._item_index(result)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                """SELECT * FROM agent_site_states WHERE owner_user_id=? AND draft_id=?
                   AND capability_name=? AND source_identity=?""",
                (owner_user_id, draft_id, capability_name, source_identity),
            ).fetchone()
            previous = {} if row is None else json.loads(row["item_index_json"])
            generation_changed = row is not None and row["generation_id"] != generation_id
            new_keys = sorted(set(current) - set(previous))
            updated_keys = sorted(key for key in set(current) & set(previous) if current[key] != previous[key])
            missing_keys = sorted(set(previous) - set(current))
            calibration = "pending" if row is None or generation_changed else "passed"
            if generation_changed and previous:
                overlap = len(set(previous) & set(current)) / max(1, len(previous))
                calibration = "passed" if overlap >= 0.5 else "failed"
            checkpoint = {
                "item_count": len(current), "new": new_keys, "updated": updated_keys,
                "missing": missing_keys, "committed_at": now,
            }
            if row is None:
                state_id = new_entity_id(EntityIdKind.AGENT_SITE_STATE)
                connection.execute(
                    """INSERT INTO agent_site_states(id,owner_user_id,draft_id,capability_name,
                       source_identity,generation_id,checkpoint_json,item_index_json,
                       structure_fingerprint,calibration_status,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (state_id, owner_user_id, draft_id, capability_name, source_identity,
                     generation_id, _json(checkpoint), _json(current), structure_fingerprint,
                     calibration, now),
                )
            elif calibration != "failed":
                connection.execute(
                    """UPDATE agent_site_states SET generation_id=?,checkpoint_json=?,item_index_json=?,
                       structure_fingerprint=?,calibration_status=?,updated_at=? WHERE id=?""",
                    (generation_id, _json(checkpoint), _json(current), structure_fingerprint,
                     calibration, now, row["id"]),
                )
        return {**checkpoint, "calibration": calibration, "suppressed_new": row is None or generation_changed}

    def record_terminal_run(self, run) -> AgentCapabilityHealthRecord | None:
        parameters = run.input.get("parameters") if isinstance(run.input, dict) else None
        if not isinstance(parameters, dict):
            return None
        draft_id = str(parameters.get("draft_id") or "")
        generation_id = str(parameters.get("generation_id") or "")
        owner_user_id = str(parameters.get("owner_user_id") or "")
        capability_name = str(parameters.get("capability_name") or "site.run")
        if not draft_id or not generation_id or not owner_user_id:
            return None
        existing_health = self.health(owner_user_id, draft_id, capability_name)
        if existing_health is not None and existing_health.last_run_id == run.id:
            return existing_health
        now_dt = utc_now()
        now = format_utc(now_dt)
        result = self._result(run)
        browser_context = parameters.get("browser_context") if isinstance(parameters.get("browser_context"), dict) else {}
        source_identity = _canonical_url(str(browser_context.get("url") or "")) or "default"
        structure_fingerprint = str(result.get("structure_fingerprint") or "")
        if not structure_fingerprint:
            structure_fingerprint = _digest({"keys": sorted(result), "items": len(result.get("items", [])) if isinstance(result.get("items"), list) else None})
        success = str(getattr(run.status, "value", run.status)) == "completed"
        error = None if success else dict(run.error or {})
        error_class = None if success else classify_failure(error)
        state_diff = None
        if success:
            state_diff = self._commit_state(
                owner_user_id=owner_user_id, draft_id=draft_id,
                capability_name=capability_name, generation_id=generation_id,
                result=result, structure_fingerprint=structure_fingerprint,
                source_identity=source_identity,
            )
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM agent_capability_health WHERE owner_user_id=? AND draft_id=? AND capability_name=?",
                (owner_user_id, draft_id, capability_name),
            ).fetchone()
            failures = 0 if success else (0 if row is None else int(row["consecutive_failures"])) + 1
            if success:
                status = "healthy"
                circuit = None
            elif error_class == "needs_user":
                status, circuit = "needs_user", None
            elif error_class == "structural" and failures >= self.CIRCUIT_FAILURES:
                status, circuit = "drifted", format_utc(now_dt + self.CIRCUIT_COOLDOWN)
            elif error_class == "structural":
                status, circuit = "suspect", None
            elif error_class == "transient":
                status, circuit = "degraded", None
            else:
                status, circuit = "failed", None
            metrics = {} if row is None else json.loads(row["metrics_json"])
            if state_diff is not None:
                metrics["last_diff"] = state_diff
            next_success_count = (0 if row is None else int(row["success_count"])) + int(success)
            next_failure_count = (0 if row is None else int(row["failure_count"])) + int(not success)
            metrics["health_score"] = round(
                next_success_count / max(1, next_success_count + next_failure_count), 4
            )
            health_id = new_entity_id(EntityIdKind.AGENT_HEALTH) if row is None else row["id"]
            values = (
                status, failures,
                next_success_count,
                next_failure_count,
                error_class, None if error is None else _json(error), structure_fingerprint,
                circuit, _json(metrics), run.id, now if success else (None if row is None else row["last_success_at"]), now,
            )
            if row is None:
                connection.execute(
                    """INSERT INTO agent_capability_health(id,owner_user_id,draft_id,capability_name,
                       status,consecutive_failures,success_count,failure_count,last_error_class,
                       last_error_json,structure_fingerprint,circuit_open_until,metrics_json,
                       last_run_id,last_success_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (health_id, owner_user_id, draft_id, capability_name, *values),
                )
            else:
                connection.execute(
                    """UPDATE agent_capability_health SET status=?,consecutive_failures=?,success_count=?,
                       failure_count=?,last_error_class=?,last_error_json=?,structure_fingerprint=?,
                       circuit_open_until=?,metrics_json=?,last_run_id=?,last_success_at=?,updated_at=? WHERE id=?""",
                    (*values, health_id),
                )
            updated = connection.execute("SELECT * FROM agent_capability_health WHERE id=?", (health_id,)).fetchone()
        return self._health(updated)

    def site_states(self, owner_user_id: str, draft_id: str) -> tuple[AgentSiteStateRecord, ...]:
        self.store.get_draft(draft_id, owner_user_id)
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_site_states WHERE owner_user_id=? AND draft_id=? ORDER BY updated_at DESC",
                (owner_user_id, draft_id),
            ).fetchall()
        return tuple(self._state(row) for row in rows)

    def create_repair(
        self, *, owner_user_id: str, draft_id: str, capability_name: str,
        source: dict[str, Any], strategy: str,
    ) -> AgentRepairCandidateRecord:
        if strategy not in {"deterministic", "lightweight", "advanced", "manual"}:
            raise ValueError("Invalid repair strategy")
        draft = self.store.get_draft(draft_id, owner_user_id)
        if not draft.active_generation_id:
            raise ResourceConflictError("Agent has no active generation to repair")
        self._validate_repair_boundary(draft.source, source)
        result = compile_source(source)
        generation = self.store.create_generation(
            draft, source_digest=result.source_digest, compiler_version=COMPILER_VERSION,
            policy_version=str(result.report.get("policy_version") or "agent-builder-policy-p0/1"),
            ir=result.ir, report={**result.report, "repair": True, "calibration_required": True},
            valid=result.valid,
        )
        repair_id = new_entity_id(EntityIdKind.AGENT_REPAIR)
        status = "validated" if result.valid else "failed"
        now = utc_now_text()
        report = {
            **result.report,
            "candidate_generation_id": generation.id,
            "repair_id": repair_id,
        }
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE agent_compile_generations SET report_json=? WHERE id=?",
                (_json({**generation.report, "repair_id": repair_id}), generation.id),
            )
            connection.execute(
                """INSERT INTO agent_repair_candidates(id,owner_user_id,draft_id,capability_name,
                   base_generation_id,candidate_generation_id,strategy,source_json,report_json,status,
                   created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (repair_id, owner_user_id, draft_id, capability_name, draft.active_generation_id,
                 generation.id, strategy, _json(source), _json(report), status, now, now),
            )
            connection.execute(
                """INSERT INTO agent_capability_health(id,owner_user_id,draft_id,capability_name,status,updated_at)
                   VALUES (?,?,?,?, 'repairing',?) ON CONFLICT(owner_user_id,draft_id,capability_name)
                   DO UPDATE SET status='repairing',updated_at=excluded.updated_at""",
                (new_entity_id(EntityIdKind.AGENT_HEALTH), owner_user_id, draft_id, capability_name, now),
            )
            row = connection.execute("SELECT * FROM agent_repair_candidates WHERE id=?", (repair_id,)).fetchone()
        return self._repair(row)

    @staticmethod
    def _validate_repair_boundary(base: dict[str, Any], candidate: dict[str, Any]) -> None:
        if set(base.get("site_scope") or []) != set(candidate.get("site_scope") or []):
            raise ResourceConflictError("Repair cannot expand or change Site scope")
        base_capabilities = {
            str(item.get("id") or ""): item
            for item in base.get("capabilities", []) if isinstance(item, dict)
        }
        candidate_capabilities = {
            str(item.get("id") or ""): item
            for item in candidate.get("capabilities", []) if isinstance(item, dict)
        }
        if set(base_capabilities) != set(candidate_capabilities):
            raise ResourceConflictError("Repair cannot add or remove Capabilities")
        effect_rank = {"read": 0, "interact": 1, "transfer": 2, "commit": 3, "restricted": 4}
        for capability_id, item in candidate_capabilities.items():
            base_item = base_capabilities[capability_id]
            base_effects = {
                str(step.get("effect") or "read")
                for step in base_item.get("steps", []) if isinstance(step, dict)
            }
            for step in item.get("steps", []):
                if not isinstance(step, dict):
                    continue
                effect = str(step.get("effect") or "read")
                if effect not in base_effects and effect_rank.get(effect, 99) > max(
                    (effect_rank.get(value, 99) for value in base_effects), default=0
                ):
                    raise ResourceConflictError("Repair cannot increase effect level")

    def get_repair(self, repair_id: str, owner_user_id: str) -> AgentRepairCandidateRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM agent_repair_candidates WHERE id=? AND owner_user_id=?",
                (repair_id, owner_user_id),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("agent_repair", repair_id)
        return self._repair(row)

    def activate_repair(self, repair_id: str, owner_user_id: str) -> AgentRepairCandidateRecord:
        repair = self.get_repair(repair_id, owner_user_id)
        if repair.status != "validated" or not repair.candidate_generation_id:
            raise ResourceConflictError("Only a validated repair can activate")
        draft = self.store.get_draft(repair.draft_id, owner_user_id)
        self.store.update_draft(
            draft.id, owner_user_id, expected_revision=draft.revision, source=repair.source,
            site_scope=list(repair.source.get("site_scope") or draft.site_scope),
        )
        self.store.activate_generation(draft.id, repair.candidate_generation_id, owner_user_id)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE agent_repair_candidates SET status='activated',updated_at=? WHERE id=?",
                (now, repair.id),
            )
            connection.execute(
                """UPDATE agent_capability_health SET status='local_patched',
                   consecutive_failures=0,circuit_open_until=NULL,updated_at=?
                   WHERE owner_user_id=? AND draft_id=? AND capability_name=?""",
                (now, owner_user_id, repair.draft_id, repair.capability_name),
            )
            connection.execute(
                """UPDATE agent_site_states SET calibration_status='pending',updated_at=?
                   WHERE owner_user_id=? AND draft_id=? AND capability_name=?""",
                (now, owner_user_id, repair.draft_id, repair.capability_name),
            )
            row = connection.execute("SELECT * FROM agent_repair_candidates WHERE id=?", (repair.id,)).fetchone()
        return self._repair(row)
