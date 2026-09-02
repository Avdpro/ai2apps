"""Actor-scoped persistence for browser Agent drafts and local generations."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

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
from ai2apps.storage import PlatformDatabase

from .models import (
    AgentDraftRecord,
    AgentDraftStatus,
    AgentRecipeRecord,
    AgentScheduleDispatchRecord,
    AgentScheduleKind,
    AgentScheduleRecord,
    AgentScheduleStatus,
    AgentType,
    AgentWorkflowRecord,
    CompileGenerationRecord,
    CompileGenerationStatus,
    StepEvidenceRecord,
    StepOutcome,
)
from .sites import (
    canonical_site_key,
    capability_from_legacy,
    normalize_site_agent_source,
    site_key_from_source,
    unique_capability_id,
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class AgentBuilderRepository:
    def __init__(self, database: PlatformDatabase) -> None:
        self.database = database

    @staticmethod
    def _draft(row) -> AgentDraftRecord:
        return AgentDraftRecord(
            id=row["id"],
            owner_user_id=row["owner_user_id"],
            agent_type=AgentType(row["agent_type"]),
            name=row["name"],
            description=row["description"],
            site_scope=tuple(json.loads(row["site_scope_json"])),
            source=json.loads(row["source_json"]),
            status=AgentDraftStatus(row["status"]),
            active_generation_id=row["active_generation_id"],
            revision=row["revision"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
            site_key=str(row["site_key"] or ""),
        )

    @staticmethod
    def _recipe(row) -> AgentRecipeRecord:
        return AgentRecipeRecord(
            id=row["id"], owner_user_id=row["owner_user_id"],
            site_key=row["site_key"], name=row["name"], description=row["description"],
            source=json.loads(row["source_json"]), page=json.loads(row["page_json"]),
            status=row["status"], committed_draft_id=row["committed_draft_id"],
            committed_capability_id=row["committed_capability_id"], revision=row["revision"],
            expires_at=parse_utc(row["expires_at"]), created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _generation(row) -> CompileGenerationRecord:
        return CompileGenerationRecord(
            id=row["id"],
            draft_id=row["draft_id"],
            source_revision=row["source_revision"],
            source_digest=row["source_digest"],
            compiler_version=row["compiler_version"],
            policy_version=row["policy_version"],
            ir=json.loads(row["ir_json"]),
            report=json.loads(row["report_json"]),
            status=CompileGenerationStatus(row["status"]),
            created_at=parse_utc(row["created_at"]),
            activated_at=(
                None if row["activated_at"] is None else parse_utc(row["activated_at"])
            ),
        )

    @staticmethod
    def _evidence(row) -> StepEvidenceRecord:
        return StepEvidenceRecord(
            id=row["id"],
            draft_id=row["draft_id"],
            generation_id=row["generation_id"],
            run_id=row["run_id"],
            step_name=row["step_name"],
            page_fingerprint=row["page_fingerprint"],
            outcome=StepOutcome(row["outcome"]),
            evidence=json.loads(row["evidence_json"]),
            user_feedback=row["user_feedback"],
            created_at=parse_utc(row["created_at"]),
        )

    @staticmethod
    def _workflow(row) -> AgentWorkflowRecord:
        return AgentWorkflowRecord(
            id=row["id"],
            owner_user_id=row["owner_user_id"],
            name=row["name"],
            description=row["description"],
            definition=json.loads(row["definition_json"]),
            status=row["status"],
            revision=row["revision"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _schedule(row) -> AgentScheduleRecord:
        return AgentScheduleRecord(
            id=row["id"],
            owner_user_id=row["owner_user_id"],
            draft_id=row["draft_id"],
            workflow_id=row["workflow_id"],
            session_id=row["session_id"],
            name=row["name"],
            kind=AgentScheduleKind(row["kind"]),
            status=AgentScheduleStatus(row["status"]),
            input=json.loads(row["input_json"]),
            knowledge_bucket_id=row["knowledge_bucket_id"],
            interval_seconds=row["interval_seconds"],
            run_at=None if row["run_at"] is None else parse_utc(row["run_at"]),
            next_run_at=(
                None if row["next_run_at"] is None else parse_utc(row["next_run_at"])
            ),
            last_run_at=(
                None if row["last_run_at"] is None else parse_utc(row["last_run_at"])
            ),
            revision=row["revision"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
            installation_id=str(row["installation_id"]),
            max_concurrent_runs=int(row["max_concurrent_runs"]),
            max_failures=int(row["max_failures"]),
        )

    @staticmethod
    def _dispatch(row) -> AgentScheduleDispatchRecord:
        return AgentScheduleDispatchRecord(
            id=row["id"],
            schedule_id=row["schedule_id"],
            run_id=row["run_id"],
            status=row["status"],
            error=None if row["error_json"] is None else json.loads(row["error_json"]),
            dispatched_at=parse_utc(row["dispatched_at"]),
            completed_at=(
                None if row["completed_at"] is None else parse_utc(row["completed_at"])
            ),
        )

    def create_draft(
        self,
        *,
        owner_user_id: str,
        name: str,
        description: str,
        site_scope: list[str],
        source: dict[str, Any],
        agent_type: AgentType = AgentType.WEB,
    ) -> AgentDraftRecord:
        name = name.strip()
        if not name:
            raise ValueError("Agent name must not be empty")
        draft_id = new_entity_id(EntityIdKind.AGENT_DRAFT)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO agent_drafts(
                    id,owner_user_id,name,description,site_scope_json,source_json,
                    agent_type,site_key,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    draft_id,
                    owner_user_id,
                    name,
                    description,
                    _json(site_scope),
                    _json(source),
                    agent_type.value,
                    site_key_from_source(source, site_scope),
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM agent_drafts WHERE id=?", (draft_id,)
            ).fetchone()
        return self._draft(row)

    def find_site_agent(self, owner_user_id: str, site_key: str) -> AgentDraftRecord | None:
        key = canonical_site_key(site_key)
        if not key:
            return None
        with self.database.transaction() as connection:
            row = connection.execute(
                """SELECT * FROM agent_drafts WHERE owner_user_id=? AND site_key=?
                   AND agent_type='web' AND status!='archived'
                   ORDER BY CASE WHEN active_generation_id IS NULL THEN 1 ELSE 0 END,
                            updated_at DESC,id LIMIT 1""",
                (owner_user_id, key),
            ).fetchone()
        return None if row is None else self._draft(row)

    def create_recipe(
        self, *, owner_user_id: str, name: str, description: str,
        source: dict[str, Any], page: dict[str, Any] | None = None,
        ttl_days: int = 7,
    ) -> AgentRecipeRecord:
        name = name.strip()
        if not name:
            raise ValueError("Recipe name must not be empty")
        recipe_id = new_entity_id(EntityIdKind.AGENT_RECIPE)
        now_dt = utc_now()
        now = format_utc(now_dt)
        page = dict(page or {})
        site_key = canonical_site_key(str(page.get("url") or "")) or site_key_from_source(source)
        expires_at = format_utc(now_dt + timedelta(days=max(1, min(ttl_days, 30))))
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO agent_recipes(
                    id,owner_user_id,site_key,name,description,source_json,page_json,
                    expires_at,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (recipe_id, owner_user_id, site_key, name, description,
                 _json(source), _json(page), expires_at, now, now),
            )
            row = connection.execute("SELECT * FROM agent_recipes WHERE id=?", (recipe_id,)).fetchone()
        return self._recipe(row)

    def get_recipe(self, recipe_id: str, owner_user_id: str) -> AgentRecipeRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM agent_recipes WHERE id=? AND owner_user_id=?",
                (recipe_id, owner_user_id),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("agent_recipe", recipe_id)
        return self._recipe(row)

    def list_recipes(self, owner_user_id: str) -> tuple[AgentRecipeRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT * FROM agent_recipes WHERE owner_user_id=?
                   AND status IN ('draft','tested') AND expires_at>?
                   ORDER BY updated_at DESC,id""",
                (owner_user_id, utc_now_text()),
            ).fetchall()
        return tuple(self._recipe(row) for row in rows)

    def revise_recipe(
        self,
        recipe_id: str,
        owner_user_id: str,
        *,
        expected_revision: int,
        source: dict[str, Any],
        status: str = "draft",
    ) -> AgentRecipeRecord:
        """Replace the complete Recipe Source and invalidate prior review approval."""

        if status not in {"draft", "tested"}:
            raise ValueError("Invalid Recipe review status")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute(
                """UPDATE agent_recipes SET source_json=?,status=?,revision=revision+1,
                   updated_at=? WHERE id=? AND owner_user_id=? AND revision=?
                   AND status!='committed'""",
                (
                    _json(source), status, now, recipe_id, owner_user_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                existing = connection.execute(
                    "SELECT id FROM agent_recipes WHERE id=? AND owner_user_id=?",
                    (recipe_id, owner_user_id),
                ).fetchone()
                if existing is None:
                    raise ResourceNotFoundError("agent_recipe", recipe_id)
                raise ResourceConflictError("Recipe revision or status changed")
            row = connection.execute(
                "SELECT * FROM agent_recipes WHERE id=?", (recipe_id,)
            ).fetchone()
        return self._recipe(row)

    def set_recipe_review_status(
        self,
        recipe_id: str,
        owner_user_id: str,
        *,
        expected_revision: int,
        status: str,
    ) -> AgentRecipeRecord:
        if status not in {"draft", "tested"}:
            raise ValueError("Invalid Recipe review status")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute(
                """UPDATE agent_recipes SET status=?,revision=revision+1,updated_at=?
                   WHERE id=? AND owner_user_id=? AND revision=?
                   AND status IN ('draft','tested')""",
                (status, now, recipe_id, owner_user_id, expected_revision),
            )
            if cursor.rowcount != 1:
                existing = connection.execute(
                    "SELECT id FROM agent_recipes WHERE id=? AND owner_user_id=?",
                    (recipe_id, owner_user_id),
                ).fetchone()
                if existing is None:
                    raise ResourceNotFoundError("agent_recipe", recipe_id)
                raise ResourceConflictError("Recipe revision or status changed")
            row = connection.execute(
                "SELECT * FROM agent_recipes WHERE id=?", (recipe_id,)
            ).fetchone()
        return self._recipe(row)

    def commit_recipe(
        self, recipe_id: str, owner_user_id: str, *, mode: str = "merge",
        draft_id: str | None = None,
    ) -> tuple[AgentRecipeRecord, AgentDraftRecord]:
        recipe = self.get_recipe(recipe_id, owner_user_id)
        if recipe.status == "committed" and recipe.committed_draft_id:
            return recipe, self.get_draft(recipe.committed_draft_id, owner_user_id)
        if recipe.status != "tested":
            raise ResourceConflictError("Recipe must pass Review before it can be committed")
        if mode not in {"merge", "create"}:
            raise ValueError("mode must be merge or create")
        target = self.get_draft(draft_id, owner_user_id) if draft_id else None
        if target is None and mode == "merge":
            target = self.find_site_agent(owner_user_id, recipe.site_key)
        capability = capability_from_legacy(recipe.source)
        if target is None:
            source = normalize_site_agent_source(
                recipe.source, site_key=recipe.site_key
            )
            target = self.create_draft(
                owner_user_id=owner_user_id, name=f"{recipe.site_key or recipe.name} Agent",
                description=f"Capabilities for {recipe.site_key}" if recipe.site_key else recipe.description,
                site_scope=list(source.get("site_scope") or []), source=source,
                agent_type=AgentType.WEB,
            )
            capability_id = str(source["capabilities"][0]["id"])
        else:
            if target.agent_type is not AgentType.WEB:
                raise ResourceConflictError("Recipes can only merge into Web Site Agents")
            if recipe.site_key and target.site_key and recipe.site_key != target.site_key:
                raise ResourceConflictError("Recipe and Site Agent belong to different sites")
            source = normalize_site_agent_source(
                target.source, site_key=target.site_key or recipe.site_key,
                legacy_draft_id=target.id,
            )
            capability_id = unique_capability_id(source, str(capability.get("id") or recipe.name))
            capability["id"] = capability_id
            used_names = {
                str(item.get("name") or "") for item in source["capabilities"]
                if isinstance(item, dict)
            }
            if str(capability.get("name") or "") in used_names:
                capability["name"] = f"site.{capability_id}"
            source["capabilities"].append(capability)
            target = self.update_draft(
                target.id, owner_user_id, expected_revision=target.revision,
                source=source, site_scope=list(source.get("site_scope") or target.site_scope),
            )
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE agent_recipes SET status='committed',committed_draft_id=?,
                   committed_capability_id=?,revision=revision+1,updated_at=? WHERE id=?""",
                (target.id, capability_id, now, recipe.id),
            )
            row = connection.execute("SELECT * FROM agent_recipes WHERE id=?", (recipe.id,)).fetchone()
        return self._recipe(row), target

    def get_draft(self, draft_id: str, owner_user_id: str) -> AgentDraftRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM agent_drafts WHERE id=? AND owner_user_id=?",
                (draft_id, owner_user_id),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("agent_draft", draft_id)
        return self._draft(row)

    def list_drafts(
        self, owner_user_id: str, *, include_archived: bool = False
    ) -> tuple[AgentDraftRecord, ...]:
        sql = "SELECT * FROM agent_drafts WHERE owner_user_id=?"
        args: list[Any] = [owner_user_id]
        if not include_archived:
            sql += " AND status!='archived'"
        sql += " ORDER BY updated_at DESC,id"
        with self.database.transaction() as connection:
            rows = connection.execute(sql, args).fetchall()
        return tuple(self._draft(row) for row in rows)

    def update_draft(
        self,
        draft_id: str,
        owner_user_id: str,
        *,
        expected_revision: int,
        name: str | None = None,
        description: str | None = None,
        site_scope: list[str] | None = None,
        source: dict[str, Any] | None = None,
        agent_type: AgentType | None = None,
    ) -> AgentDraftRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM agent_drafts WHERE id=? AND owner_user_id=?",
                (draft_id, owner_user_id),
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("agent_draft", draft_id)
            if row["revision"] != expected_revision:
                raise ResourceConflictError("Agent draft revision changed")
            next_name = row["name"] if name is None else name.strip()
            if not next_name:
                raise ValueError("Agent name must not be empty")
            connection.execute(
                """
                UPDATE agent_drafts SET name=?,description=?,site_scope_json=?,
                    source_json=?,agent_type=?,site_key=?,
                    status=CASE WHEN active_generation_id IS NULL
                        THEN 'editing' ELSE 'active' END,
                    revision=revision+1,updated_at=?
                WHERE id=?
                """,
                (
                    next_name,
                    row["description"] if description is None else description,
                    row["site_scope_json"] if site_scope is None else _json(site_scope),
                    row["source_json"] if source is None else _json(source),
                    row["agent_type"] if agent_type is None else agent_type.value,
                    site_key_from_source(
                        json.loads(row["source_json"]) if source is None else source,
                        json.loads(row["site_scope_json"]) if site_scope is None else site_scope,
                    ),
                    now,
                    draft_id,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM agent_drafts WHERE id=?", (draft_id,)
            ).fetchone()
        return self._draft(updated)

    def reconcile_site_agents(self, owner_user_id: str) -> dict[str, Any]:
        """Losslessly consolidate legacy same-site Web drafts into one Site Agent."""

        with self.database.transaction(write=True) as connection:
            rows = connection.execute(
                """SELECT * FROM agent_drafts WHERE owner_user_id=?
                   AND agent_type='web' AND status!='archived'
                   ORDER BY CASE WHEN active_generation_id IS NULL THEN 1 ELSE 0 END,
                            updated_at DESC,id""",
                (owner_user_id,),
            ).fetchall()
            groups: dict[str, list[Any]] = {}
            for row in rows:
                source = json.loads(row["source_json"])
                # Previewing and testing may need a durable record for evidence,
                # but it must not become a menu item or be merged into a Site
                # Agent until the user explicitly saves it.
                authoring = source.get("authoring")
                if isinstance(authoring, dict) and authoring.get("saved") is False:
                    continue
                key = canonical_site_key(str(row["site_key"] or "")) or site_key_from_source(
                    source, json.loads(row["site_scope_json"])
                )
                if key:
                    groups.setdefault(key, []).append(row)
            merged: list[dict[str, Any]] = []
            now = utc_now_text()
            for key, members in groups.items():
                primary = members[0]
                primary_source = normalize_site_agent_source(
                    json.loads(primary["source_json"]), site_key=key,
                    legacy_draft_id=primary["id"],
                )
                scopes = list(json.loads(primary["site_scope_json"]))
                archived: list[str] = []
                for duplicate in members[1:]:
                    duplicate_source = normalize_site_agent_source(
                        json.loads(duplicate["source_json"]), site_key=key,
                        legacy_draft_id=duplicate["id"],
                    )
                    for capability in duplicate_source.get("capabilities", []):
                        item = dict(capability)
                        item["id"] = unique_capability_id(
                            primary_source, str(item.get("id") or duplicate["name"])
                        )
                        primary_source["capabilities"].append(item)
                    for scope in json.loads(duplicate["site_scope_json"]):
                        if scope not in scopes:
                            scopes.append(scope)
                    connection.execute(
                        """UPDATE agent_drafts SET status='archived',revision=revision+1,
                           site_key=?,updated_at=? WHERE id=?""",
                        (key, now, duplicate["id"]),
                    )
                    archived.append(duplicate["id"])
                primary_source["site_scope"] = scopes
                primary_source = normalize_site_agent_source(primary_source, site_key=key)
                original_source = json.loads(primary["source_json"])
                changed = (
                    bool(archived) or primary["site_key"] != key
                    or original_source != primary_source
                )
                if changed:
                    connection.execute(
                        """UPDATE agent_drafts SET source_json=?,site_scope_json=?,site_key=?,
                           revision=revision+1,updated_at=? WHERE id=?""",
                        (_json(primary_source), _json(scopes), key, now, primary["id"]),
                    )
                if archived:
                    merged.append({"site_key": key, "site_agent_id": primary["id"], "archived_draft_ids": archived})
        return {"merged": merged, "site_count": len(groups)}

    def archive_draft(
        self, draft_id: str, owner_user_id: str, *, expected_revision: int
    ) -> AgentDraftRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            result = connection.execute(
                """
                UPDATE agent_drafts SET status='archived',revision=revision+1,
                    updated_at=? WHERE id=? AND owner_user_id=? AND revision=?
                """,
                (now, draft_id, owner_user_id, expected_revision),
            )
            if result.rowcount != 1:
                row = connection.execute(
                    "SELECT revision FROM agent_drafts WHERE id=? AND owner_user_id=?",
                    (draft_id, owner_user_id),
                ).fetchone()
                if row is None:
                    raise ResourceNotFoundError("agent_draft", draft_id)
                raise ResourceConflictError("Agent draft revision changed")
            row = connection.execute(
                "SELECT * FROM agent_drafts WHERE id=?", (draft_id,)
            ).fetchone()
        return self._draft(row)

    def create_generation(
        self,
        draft: AgentDraftRecord,
        *,
        source_digest: str,
        compiler_version: str,
        policy_version: str,
        ir: dict[str, Any],
        report: dict[str, Any],
        valid: bool,
    ) -> CompileGenerationRecord:
        generation_id = new_entity_id(EntityIdKind.AGENT_GENERATION)
        now = utc_now_text()
        status = "validated" if valid else "failed"
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO agent_compile_generations(
                    id,draft_id,source_revision,source_digest,compiler_version,
                    policy_version,ir_json,report_json,status,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    generation_id,
                    draft.id,
                    draft.revision,
                    source_digest,
                    compiler_version,
                    policy_version,
                    _json(ir),
                    _json(report),
                    status,
                    now,
                ),
            )
            if valid:
                connection.execute(
                    """
                    UPDATE agent_drafts SET status='compiled',
                        revision=revision+1,updated_at=? WHERE id=?
                    """,
                    (now, draft.id),
                )
            row = connection.execute(
                "SELECT * FROM agent_compile_generations WHERE id=?",
                (generation_id,),
            ).fetchone()
        return self._generation(row)

    def get_generation(
        self, generation_id: str, owner_user_id: str
    ) -> CompileGenerationRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT g.* FROM agent_compile_generations g
                JOIN agent_drafts d ON d.id=g.draft_id
                WHERE g.id=? AND d.owner_user_id=?
                """,
                (generation_id, owner_user_id),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("agent_generation", generation_id)
        return self._generation(row)

    def list_generations(
        self, draft_id: str, owner_user_id: str
    ) -> tuple[CompileGenerationRecord, ...]:
        self.get_draft(draft_id, owner_user_id)
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM agent_compile_generations WHERE draft_id=?
                ORDER BY created_at DESC,id DESC
                """,
                (draft_id,),
            ).fetchall()
        return tuple(self._generation(row) for row in rows)

    def activate_generation(
        self, draft_id: str, generation_id: str, owner_user_id: str
    ) -> AgentDraftRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                """
                SELECT g.status FROM agent_compile_generations g
                JOIN agent_drafts d ON d.id=g.draft_id
                WHERE g.id=? AND g.draft_id=? AND d.owner_user_id=?
                """,
                (generation_id, draft_id, owner_user_id),
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("agent_generation", generation_id)
            if row["status"] not in {"validated", "active"}:
                raise ResourceConflictError("Only a validated generation can activate")
            connection.execute(
                "UPDATE agent_compile_generations SET status='validated' "
                "WHERE draft_id=? AND status='active'",
                (draft_id,),
            )
            connection.execute(
                """
                UPDATE agent_compile_generations SET status='active',activated_at=?
                WHERE id=?
                """,
                (now, generation_id),
            )
            connection.execute(
                """
                UPDATE agent_drafts SET status='active',active_generation_id=?,
                    revision=revision+1,updated_at=? WHERE id=?
                """,
                (generation_id, now, draft_id),
            )
            draft = connection.execute(
                "SELECT * FROM agent_drafts WHERE id=?", (draft_id,)
            ).fetchone()
        return self._draft(draft)

    def add_evidence(
        self,
        *,
        draft_id: str,
        owner_user_id: str,
        step_name: str,
        outcome: StepOutcome,
        evidence: dict[str, Any],
        generation_id: str | None = None,
        run_id: str | None = None,
        page_fingerprint: str = "",
        user_feedback: str | None = None,
    ) -> StepEvidenceRecord:
        self.get_draft(draft_id, owner_user_id)
        evidence_id = new_entity_id(EntityIdKind.AGENT_EVIDENCE)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO agent_step_evidence(
                    id,draft_id,generation_id,run_id,step_name,page_fingerprint,
                    outcome,evidence_json,user_feedback,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    evidence_id,
                    draft_id,
                    generation_id,
                    run_id,
                    step_name,
                    page_fingerprint,
                    outcome.value,
                    _json(evidence),
                    user_feedback,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM agent_step_evidence WHERE id=?", (evidence_id,)
            ).fetchone()
        return self._evidence(row)

    def list_evidence(
        self, draft_id: str, owner_user_id: str
    ) -> tuple[StepEvidenceRecord, ...]:
        self.get_draft(draft_id, owner_user_id)
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM agent_step_evidence WHERE draft_id=?
                ORDER BY created_at,id
                """,
                (draft_id,),
            ).fetchall()
        return tuple(self._evidence(row) for row in rows)

    @staticmethod
    def _validate_workflow_definition(definition: dict[str, Any]) -> None:
        steps = definition.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError("Workflow requires at least one step")
        names: set[str] = set()
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValueError(f"Workflow step {index + 1} must be an object")
            name = str(step.get("name") or f"step-{index + 1}").strip()
            draft_id = str(step.get("draft_id") or "").strip()
            if not draft_id:
                raise ValueError(f"Workflow step {name} requires draft_id")
            if name in names:
                raise ValueError(f"Workflow step name is duplicated: {name}")
            names.add(name)

    def create_workflow(
        self,
        *,
        owner_user_id: str,
        name: str,
        description: str,
        definition: dict[str, Any],
    ) -> AgentWorkflowRecord:
        name = name.strip()
        if not name:
            raise ValueError("Workflow name must not be empty")
        self._validate_workflow_definition(definition)
        for step in definition["steps"]:
            self.get_draft(str(step["draft_id"]), owner_user_id)
        workflow_id = new_entity_id(EntityIdKind.AGENT_WORKFLOW)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO agent_workflows(
                    id,owner_user_id,name,description,definition_json,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (
                    workflow_id,
                    owner_user_id,
                    name,
                    description,
                    _json(definition),
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM agent_workflows WHERE id=?", (workflow_id,)
            ).fetchone()
        return self._workflow(row)

    def get_workflow(
        self, workflow_id: str, owner_user_id: str
    ) -> AgentWorkflowRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM agent_workflows WHERE id=? AND owner_user_id=?",
                (workflow_id, owner_user_id),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("agent_workflow", workflow_id)
        return self._workflow(row)

    def list_workflows(
        self, owner_user_id: str, *, include_archived: bool = False
    ) -> tuple[AgentWorkflowRecord, ...]:
        sql = "SELECT * FROM agent_workflows WHERE owner_user_id=?"
        arguments: list[Any] = [owner_user_id]
        if not include_archived:
            sql += " AND status!='archived'"
        sql += " ORDER BY updated_at DESC,id"
        with self.database.transaction() as connection:
            rows = connection.execute(sql, arguments).fetchall()
        return tuple(self._workflow(row) for row in rows)

    def update_workflow(
        self,
        workflow_id: str,
        owner_user_id: str,
        *,
        expected_revision: int,
        name: str | None = None,
        description: str | None = None,
        definition: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> AgentWorkflowRecord:
        if status not in {None, "active", "archived"}:
            raise ValueError("Invalid Workflow status")
        if definition is not None:
            self._validate_workflow_definition(definition)
            for step in definition["steps"]:
                self.get_draft(str(step["draft_id"]), owner_user_id)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM agent_workflows WHERE id=? AND owner_user_id=?",
                (workflow_id, owner_user_id),
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("agent_workflow", workflow_id)
            if row["revision"] != expected_revision:
                raise ResourceConflictError("Workflow revision changed")
            next_name = row["name"] if name is None else name.strip()
            if not next_name:
                raise ValueError("Workflow name must not be empty")
            connection.execute(
                """
                UPDATE agent_workflows SET name=?,description=?,definition_json=?,
                    status=?,revision=revision+1,updated_at=? WHERE id=?
                """,
                (
                    next_name,
                    row["description"] if description is None else description,
                    row["definition_json"] if definition is None else _json(definition),
                    row["status"] if status is None else status,
                    now,
                    workflow_id,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM agent_workflows WHERE id=?", (workflow_id,)
            ).fetchone()
        return self._workflow(updated)

    def create_schedule(
        self,
        *,
        owner_user_id: str,
        session_id: str,
        name: str,
        kind: AgentScheduleKind,
        input: dict[str, Any],
        draft_id: str | None = None,
        workflow_id: str | None = None,
        knowledge_bucket_id: str | None = None,
        interval_seconds: int | None = None,
        run_at: datetime | None = None,
        installation_id: str = "local",
        max_concurrent_runs: int = 1,
        max_failures: int = 5,
    ) -> AgentScheduleRecord:
        if (draft_id is None) == (workflow_id is None):
            raise ValueError("Schedule requires exactly one Agent or Workflow")
        if draft_id is not None:
            self.get_draft(draft_id, owner_user_id)
        if workflow_id is not None:
            self.get_workflow(workflow_id, owner_user_id)
        name = name.strip()
        if not name:
            raise ValueError("Schedule name must not be empty")
        if not 1 <= max_concurrent_runs <= 16:
            raise ValueError("Schedule concurrency must be between 1 and 16")
        if not 1 <= max_failures <= 100:
            raise ValueError("Schedule max_failures must be between 1 and 100")
        now_value = utc_now()
        if kind is AgentScheduleKind.ONCE:
            if run_at is None:
                raise ValueError("One-time Schedule requires run_at")
            interval_seconds = None
            next_run_at = run_at
        else:
            if interval_seconds is None or interval_seconds < 60:
                raise ValueError("Interval Schedule must be at least 60 seconds")
            run_at = None
            next_run_at = now_value + timedelta(seconds=interval_seconds)
        schedule_id = new_entity_id(EntityIdKind.AGENT_SCHEDULE)
        now = format_utc(now_value)
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO agent_schedules(
                    id,owner_user_id,draft_id,workflow_id,session_id,name,kind,status,
                    input_json,knowledge_bucket_id,interval_seconds,run_at,next_run_at,
                    created_at,updated_at,installation_id,max_concurrent_runs,max_failures
                ) VALUES (?,?,?,?,?,?,?,'enabled',?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    schedule_id,
                    owner_user_id,
                    draft_id,
                    workflow_id,
                    session_id,
                    name,
                    kind.value,
                    _json(input),
                    knowledge_bucket_id,
                    interval_seconds,
                    None if run_at is None else format_utc(run_at),
                    format_utc(next_run_at),
                    now,
                    now,
                    installation_id,
                    max_concurrent_runs,
                    max_failures,
                ),
            )
            row = connection.execute(
                "SELECT * FROM agent_schedules WHERE id=?", (schedule_id,)
            ).fetchone()
        return self._schedule(row)

    def get_schedule(
        self, schedule_id: str, owner_user_id: str
    ) -> AgentScheduleRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM agent_schedules WHERE id=? AND owner_user_id=?",
                (schedule_id, owner_user_id),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("agent_schedule", schedule_id)
        return self._schedule(row)

    def list_schedules(
        self, owner_user_id: str
    ) -> tuple[AgentScheduleRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM agent_schedules WHERE owner_user_id=?
                ORDER BY updated_at DESC,id
                """,
                (owner_user_id,),
            ).fetchall()
        return tuple(self._schedule(row) for row in rows)

    def set_schedule_status(
        self,
        schedule_id: str,
        owner_user_id: str,
        *,
        expected_revision: int,
        status: AgentScheduleStatus,
    ) -> AgentScheduleRecord:
        now_value = utc_now()
        next_run_at: str | None = None
        current = self.get_schedule(schedule_id, owner_user_id)
        if status is AgentScheduleStatus.ENABLED:
            if current.kind is AgentScheduleKind.INTERVAL:
                next_run_at = format_utc(
                    now_value + timedelta(seconds=current.interval_seconds or 60)
                )
            elif current.run_at is not None:
                next_run_at = format_utc(max(current.run_at, now_value))
        with self.database.transaction(write=True) as connection:
            result = connection.execute(
                """
                UPDATE agent_schedules SET status=?,next_run_at=?,
                    revision=revision+1,updated_at=?
                WHERE id=? AND owner_user_id=? AND revision=?
                """,
                (
                    status.value,
                    next_run_at,
                    format_utc(now_value),
                    schedule_id,
                    owner_user_id,
                    expected_revision,
                ),
            )
            if result.rowcount != 1:
                raise ResourceConflictError("Schedule revision changed")
            row = connection.execute(
                "SELECT * FROM agent_schedules WHERE id=?", (schedule_id,)
            ).fetchone()
        return self._schedule(row)

    def run_schedule_now(
        self, schedule_id: str, owner_user_id: str
    ) -> AgentScheduleRecord:
        self.get_schedule(schedule_id, owner_user_id)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                UPDATE agent_schedules SET status='enabled',next_run_at=?,
                    revision=revision+1,updated_at=? WHERE id=?
                """,
                (now, now, schedule_id),
            )
            row = connection.execute(
                "SELECT * FROM agent_schedules WHERE id=?", (schedule_id,)
            ).fetchone()
        return self._schedule(row)

    def claim_due_schedule(self) -> tuple[AgentScheduleRecord, AgentScheduleDispatchRecord] | None:
        now_value = utc_now()
        now = format_utc(now_value)
        dispatch_id = new_entity_id(EntityIdKind.AGENT_SCHEDULE_DISPATCH)
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                """
                SELECT * FROM agent_schedules
                WHERE status='enabled' AND next_run_at IS NOT NULL AND next_run_at<=?
                  AND (SELECT COUNT(*) FROM agent_schedule_dispatches d
                       WHERE d.schedule_id=agent_schedules.id
                         AND d.status IN ('claimed','dispatched')) < max_concurrent_runs
                  AND (SELECT COUNT(*) FROM agent_schedule_dispatches d
                       WHERE d.schedule_id=agent_schedules.id
                         AND d.status='failed') < max_failures
                ORDER BY next_run_at,id LIMIT 1
                """,
                (now,),
            ).fetchone()
            if row is None:
                return None
            if row["kind"] == AgentScheduleKind.ONCE.value:
                next_status = AgentScheduleStatus.COMPLETED.value
                next_run_at = None
            else:
                next_status = AgentScheduleStatus.ENABLED.value
                next_run_at = format_utc(
                    now_value + timedelta(seconds=int(row["interval_seconds"]))
                )
            connection.execute(
                """
                UPDATE agent_schedules SET status=?,next_run_at=?,last_run_at=?,
                    revision=revision+1,updated_at=? WHERE id=?
                """,
                (next_status, next_run_at, now, now, row["id"]),
            )
            connection.execute(
                """
                INSERT INTO agent_schedule_dispatches(
                    id,schedule_id,status,dispatched_at
                ) VALUES (?,?,'claimed',?)
                """,
                (dispatch_id, row["id"], now),
            )
            schedule_row = connection.execute(
                "SELECT * FROM agent_schedules WHERE id=?", (row["id"],)
            ).fetchone()
            dispatch_row = connection.execute(
                "SELECT * FROM agent_schedule_dispatches WHERE id=?", (dispatch_id,)
            ).fetchone()
        return self._schedule(schedule_row), self._dispatch(dispatch_row)

    def finish_dispatch(
        self,
        dispatch_id: str,
        *,
        run_id: str | None = None,
        error: dict[str, Any] | None = None,
    ) -> AgentScheduleDispatchRecord:
        status = "dispatched" if error is None else "failed"
        completed_at = None if error is None else utc_now_text()
        with self.database.transaction(write=True) as connection:
            result = connection.execute(
                """
                UPDATE agent_schedule_dispatches SET run_id=?,status=?,error_json=?,
                    completed_at=? WHERE id=? AND status='claimed'
                """,
                (
                    run_id,
                    status,
                    None if error is None else _json(error),
                    completed_at,
                    dispatch_id,
                ),
            )
            if result.rowcount != 1:
                raise ResourceConflictError("Schedule dispatch is no longer claimed")
            row = connection.execute(
                "SELECT * FROM agent_schedule_dispatches WHERE id=?", (dispatch_id,)
            ).fetchone()
        return self._dispatch(row)

    def list_dispatches(
        self, schedule_id: str, owner_user_id: str
    ) -> tuple[AgentScheduleDispatchRecord, ...]:
        self.get_schedule(schedule_id, owner_user_id)
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM agent_schedule_dispatches WHERE schedule_id=?
                ORDER BY dispatched_at DESC,id DESC
                """,
                (schedule_id,),
            ).fetchall()
        return tuple(self._dispatch(row) for row in rows)

    def reconcile_dispatches(self) -> int:
        """Mirror terminal AgentRun states into durable Schedule dispatches."""

        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            result = connection.execute(
                """
                UPDATE agent_schedule_dispatches
                SET status=(SELECT CASE WHEN r.status='completed' THEN 'completed'
                        ELSE 'failed' END FROM agent_runs r
                        WHERE r.id=agent_schedule_dispatches.run_id),
                    error_json=(SELECT CASE WHEN r.status='completed' THEN NULL
                        ELSE r.error_json END FROM agent_runs r
                        WHERE r.id=agent_schedule_dispatches.run_id),
                    completed_at=?
                WHERE status='dispatched' AND run_id IS NOT NULL
                  AND EXISTS(SELECT 1 FROM agent_runs r
                    WHERE r.id=agent_schedule_dispatches.run_id
                      AND r.status IN ('completed','failed','cancelled'))
                """,
                (now,),
            )
            connection.execute(
                """UPDATE agent_schedules SET status='paused',revision=revision+1,
                   updated_at=? WHERE status='enabled' AND
                   (SELECT COUNT(*) FROM agent_schedule_dispatches d
                    WHERE d.schedule_id=agent_schedules.id AND d.status='failed')
                   >= max_failures""",
                (now,),
            )
        return result.rowcount
