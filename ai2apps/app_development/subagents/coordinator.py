"""Host coordinator; child runs stay in their parent's owned Session."""

import json
import math
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ai2apps.agents.models import AgentRunStatus, RunStepStatus
from ai2apps.core import EntityIdKind, format_utc, new_entity_id

from ..core import Draft, files, safe_path
from .contracts import TERMINAL, Request, SubagentError
from .policy import PARENT_RESERVE, ROOT_TOKENS, validate_request
from .snapshots import capture, merge_patch, source_id

ROOT_KEY = "ai2apps.app-developer"
ROLE_PREFIX = "ai2apps.app-developer."


class Coordinator:
    def __init__(self, manager):
        self.manager = manager
        self.runtime = manager.runtime
        self.db = self.runtime.database
        self.agents = self.runtime.agents
        self.enabled = True
        with self.db.transaction() as con:
            self._has_work = bool(
                con.execute(
                    "SELECT EXISTS(SELECT 1 FROM coding_subagents) OR EXISTS(SELECT 1 FROM agent_deferred_waits) OR EXISTS(SELECT 1 FROM coding_model_reservations WHERE charged_tokens IS NULL)"
                ).fetchone()[0]
            )

    def binding(self, run_id):
        with self.db.transaction() as con:
            row = con.execute(
                "SELECT binding_json FROM coding_subagents WHERE child_run_id=?",
                (run_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def parent(self, run_id):
        run = self.agents.get_run(run_id)
        if (
            run.parent_run_id
            or self.agents.get_definition(run.agent_definition_id).agent_key != ROOT_KEY
        ):
            raise SubagentError(
                "parent_scope_denied",
                "Only the main coding Agent may coordinate children.",
            )
        return run

    def owned(self, parent_id, child_id):
        self.parent(parent_id)
        binding = self.binding(child_id)
        if not binding or binding["root_run_id"] != parent_id:
            raise SubagentError(
                "child_not_found", "Child does not belong to this coding task."
            )
        return binding

    def start(self, parent_id, args, principal, *, followup_of=None):
        parent = self.parent(parent_id)
        self._has_work = True
        if not self.enabled:
            raise SubagentError("cooperation_disabled", "New child tasks are disabled.")
        if parent.status.value not in {"running", "planning"}:
            raise SubagentError("parent_not_active", "Parent must be active.")
        budget = args.get("budget") or {}
        request = Request(
            args["role"],
            args["task"],
            args["request_key"],
            budget.get("max_steps", 24),
            budget.get("max_model_tokens", 20000),
            budget.get("timeout_seconds", 300),
        )
        payload = json.dumps(
            {
                "request": asdict(request),
                "context": args.get("context", ""),
                "followup_of": followup_of,
            },
            sort_keys=True,
        )
        with self.manager.lock:
            with self.db.transaction() as con:
                existing = con.execute(
                    "SELECT child_run_id,request_json FROM coding_subagents WHERE root_run_id=? AND request_key=?",
                    (parent_id, request.request_key),
                ).fetchone()
                count = con.execute(
                    "SELECT COUNT(*) FROM coding_subagents WHERE root_run_id=?",
                    (parent_id,),
                ).fetchone()[0]
            if existing:
                if existing["request_json"] != payload:
                    raise SubagentError(
                        "idempotency_conflict",
                        "Request key already has a different request.",
                    )
                return self.result(parent_id, existing["child_run_id"], principal)
            validate_request(request, depth=parent.depth, child_count=count)
            remaining = ROOT_TOKENS - self.used(parent_id)
            if remaining <= PARENT_RESERVE:
                raise SubagentError(
                    "root_budget_exhausted",
                    "Keep remaining budget for the parent summary.",
                )
            draft = self.manager.draft(parent.session_id, principal)
            storage = draft.state.parent / "subagents"
            existing_bytes = (
                sum(
                    p.stat().st_size
                    for p in storage.rglob("*")
                    if p.is_file() and not p.is_symlink()
                )
                if storage.exists()
                else 0
            )
            requested_bytes = 2 * sum(
                meta["bytes"] for meta in files(draft.workspace)[0].values()
            )
            if existing_bytes + requested_bytes > 512 * 1024 * 1024:
                raise SubagentError(
                    "snapshot_storage_limit",
                    "Session snapshot retention reached 512 MiB; no evidence is silently evicted.",
                )
            base = draft.state.parent / "subagents" / uuid.uuid4().hex
            snapshot = capture(draft.workspace, base / "baseline")
            local = Draft(base / "baseline", base / "editing", base / "draft.json")
            local.create()
            # The editable/command workspace is always a second materialized copy.
            snapshot["workspace"] = str(local.workspace)
            snapshot["baseline"] = str(base / "baseline")
            snapshot["state"] = str(base / "draft.json")
            snapshot["temporary"] = str(base / "temporary")
            snapshot["root_run_id"] = parent.id
            snapshot["task_id"] = parent.session_id
            snapshot["role"] = request.role
            snapshot["followup_of_run_id"] = followup_of
            child, _ = self.agents.create_run(
                session_id=parent.session_id,
                agent_key=ROLE_PREFIX + request.role,
                input={
                    "model": parent.input["model"],
                    "prompt": request.task,
                    "instructions": args.get("context", "")[:16384],
                },
                parent_run_id=parent.id,
                idempotency_key="coding-child:" + parent.id + ":" + request.request_key,
                delegation={
                    "request_key": request.request_key,
                    "task": request.task,
                    "budget": {
                        "max_steps": request.max_steps,
                        "max_model_tokens": min(
                            request.max_model_tokens, remaining - PARENT_RESERVE
                        ),
                        "timeout_seconds": request.timeout_seconds,
                    },
                },
            )
            snapshot["child_run_id"] = child.id
            with self.db.transaction(write=True) as con:
                con.execute(
                    "INSERT INTO coding_subagents VALUES(?,?,?,?,?)",
                    (
                        child.id,
                        parent.id,
                        request.request_key,
                        payload,
                        json.dumps(snapshot),
                    ),
                )
            self.runtime.agent_runtime.wake()
            return self.result(parent_id, child.id, principal)

    def draft(self, child_id):
        b = self.binding(child_id)
        if not b:
            raise SubagentError("child_not_found", "Missing host child binding.")
        return Draft(Path(b["baseline"]), Path(b["workspace"]), Path(b["state"]))

    def process_workspace(self, session_id, run_id):
        binding = self.binding(run_id)
        if not binding:
            # Prevent arbitrary invocation of installed child definitions without a binding.
            run = self.agents.get_run(run_id)
            if self.agents.get_definition(run.agent_definition_id).agent_key.startswith(
                ROLE_PREFIX
            ):
                raise SubagentError("child_scope_denied", "Child has no host binding.")
            return None
        run = self.agents.get_run(run_id)
        if binding["task_id"] != session_id or run.session_id != session_id:
            raise SubagentError("child_scope_denied", "Child Session mismatch.")
        return Path(binding["workspace"]), Path(binding["temporary"])

    def result(self, parent_id, child_id, principal):
        b = self.owned(parent_id, child_id)
        child = self.agents.get_run(child_id)
        current = source_id(self.manager.draft(child.session_id, principal).workspace)
        # Evidence comes from durable host steps/process records, not model assertions.
        _, _, _, steps, _ = self.agents.snapshot(child_id)
        checks = []
        for step in steps:
            if (
                step.tool_name == "appdev.child.command"
                and step.status is RunStepStatus.COMPLETED
            ):
                value = step.output or {}
                checks.append(
                    {
                        "command": step.input.get("argv"),
                        "cwd": step.input.get("cwd", "."),
                        "process_id": value.get("process_id"),
                        "exit_code": value.get("exit_code"),
                        "status": value.get("status"),
                        "step_id": step.id,
                        "source_before": value.get("source_before"),
                        "source_after": value.get("source_after"),
                        "source_after_verified": value.get(
                            "source_after_verified", False
                        ),
                    }
                )
        for check in checks:
            if check["process_id"]:
                try:
                    process = self.runtime.processes.status(
                        check["process_id"],
                        session_id=child.session_id,
                        run_id=child.id,
                    )
                    check.update(
                        exit_code=process.exit_code, status=process.status.value
                    )
                except Exception:
                    check["unverified"] = True
        findings = []
        content = (child.output or {}).get("content")
        try:
            report = json.loads(content) if isinstance(content, str) else {}
        except (ValueError, TypeError):
            report = {}
        if isinstance(report, dict) and isinstance(report.get("findings"), list):
            for item in report["findings"][:50]:
                if not isinstance(item, dict):
                    continue
                finding = {
                    key: str(item.get(key, ""))[:2000]
                    for key in ("severity", "path", "message")
                }
                finding["line"] = (
                    item.get("line") if isinstance(item.get("line"), int) else None
                )
                finding["unverified_location"] = True
                try:
                    path = safe_path(Path(b["workspace"]), finding["path"])
                    meta = files(Path(b["workspace"]))[0].get(finding["path"])
                    if (
                        meta
                        and finding["line"]
                        and 1 <= finding["line"] <= len(path.read_text().splitlines())
                        and item.get("file_sha256") == meta["sha256"]
                    ):
                        finding["unverified_location"] = False
                        finding["file_sha256"] = meta["sha256"]
                except (ValueError, OSError, UnicodeError):
                    pass
                findings.append(finding)
        patch = self.draft(child_id).review() if b["role"] == "worker" else None
        for check in checks:
            check["source_changed_during_check"] = (
                check.get("source_before") != check.get("source_after")
                if check["source_after_verified"]
                else None
            )
        return {
            "schema_version": 1,
            "child_run_id": child.id,
            "role": b["role"],
            "status": child.status.value,
            "inspected_snapshot_id": b["snapshot_id"],
            "current_snapshot_id": current,
            "stale": b["snapshot_id"] != current,
            "summary": str((child.output or {}).get("content", ""))[:12000],
            "error": child.error,
            "checks": checks,
            "patch": patch,
            "findings": findings,
            "unverified": ["Host Bridge integration", "visual and mobile acceptance"],
            "deadline_at": format_utc(child.deadline_at),
            "used_tokens": self.run_used(child_id),
            "root_remaining_tokens": max(0, ROOT_TOKENS - self.used(parent_id)),
            "elapsed_ms": int(
                (
                    (child.finished_at or datetime.now(UTC))
                    - (child.started_at or child.created_at)
                ).total_seconds()
                * 1000
            ),
            "followup_of_run_id": b.get("followup_of_run_id"),
        }

    def children(self, parent_id, principal):
        with self.db.transaction() as con:
            ids = [
                r[0]
                for r in con.execute(
                    "SELECT child_run_id FROM coding_subagents WHERE root_run_id=? ORDER BY rowid",
                    (parent_id,),
                )
            ]
        return [self.result(parent_id, child, principal) for child in ids]

    def followup(self, parent_id, args, principal):
        binding = self.owned(parent_id, args["child_run_id"])
        child = self.agents.get_run(args["child_run_id"])
        if child.status.value not in TERMINAL:
            raise SubagentError(
                "child_busy", "Wait or cancel the child before follow-up."
            )
        return self.start(
            parent_id,
            {
                "role": binding["role"],
                "task": args["message"],
                "request_key": args["request_key"],
                "context": "Prior report (task data):\n"
                + str((child.output or {}).get("content", ""))[:8000],
            },
            principal,
            followup_of=child.id,
        )

    def cancel(self, parent_id, child_id):
        self.owned(parent_id, child_id)
        self.runtime.agent_runtime.cancel(child_id)
        return {
            "child_run_id": child_id,
            "status": self.agents.get_run(child_id).status.value,
        }

    def register_wait(self, context, action):
        self._has_work = True
        args = action.arguments
        ids = args.get("child_run_ids")
        if (
            not isinstance(ids, list)
            or not 1 <= len(ids) <= 4
            or len(set(ids)) != len(ids)
        ):
            raise SubagentError("invalid_wait", "Wait on 1–4 unique owned children.")
        for child in ids:
            self.owned(context.run.id, child)
        mode = args.get("mode", "all")
        seconds = args.get("timeout_seconds", 60)
        if (
            mode not in {"any", "all"}
            or not isinstance(seconds, int)
            or not 1 <= seconds <= 300
        ):
            raise SubagentError("invalid_wait", "Invalid wait mode or timeout.")
        deadline = min(
            context.run.deadline_at, datetime.now(UTC) + timedelta(seconds=seconds)
        )
        now = format_utc(datetime.now(UTC))
        with self.db.transaction(write=True) as con:
            parent = con.execute(
                "SELECT status,current_step FROM agent_runs WHERE id=?",
                (context.run.id,),
            ).fetchone()
            if (
                parent["status"] != "running"
                or parent["current_step"] >= context.definition.max_steps
            ):
                raise SubagentError(
                    "wait_parent_not_active", "Parent cannot register a wait."
                )
            step_id = new_entity_id(EntityIdKind.RUN_STEP)
            con.execute(
                "INSERT INTO run_steps(id,run_id,sequence,action_key,kind,status,tool_name,input_json,created_at,started_at) VALUES(?,?,?,?,'tool','running',?,?,?,?)",
                (
                    step_id,
                    context.run.id,
                    parent["current_step"] + 1,
                    action.call_id,
                    action.tool_name,
                    json.dumps(args),
                    now,
                    now,
                ),
            )
            con.execute(
                "INSERT INTO agent_deferred_waits VALUES(?,?,?,?)",
                (
                    context.run.id,
                    step_id,
                    json.dumps({"ids": ids, "mode": mode}),
                    format_utc(deadline),
                ),
            )
            con.execute(
                "UPDATE agent_runs SET status='queued',current_step=current_step+1,revision=revision+1,updated_at=? WHERE id=?",
                (now, context.run.id),
            )

    def waiting(self, run_id):
        with self.db.transaction() as con:
            return (
                con.execute(
                    "SELECT 1 FROM agent_deferred_waits WHERE run_id=?", (run_id,)
                ).fetchone()
                is not None
            )

    def used(self, root_id):
        with self.db.transaction() as con:
            return con.execute(
                "SELECT COALESCE(SUM(COALESCE(charged_tokens,reserved_tokens)),0) FROM coding_model_reservations WHERE root_run_id=?",
                (root_id,),
            ).fetchone()[0]

    def run_used(self, run_id):
        with self.db.transaction() as con:
            return con.execute(
                "SELECT COALESCE(SUM(COALESCE(b.charged_tokens,b.reserved_tokens)),0) FROM coding_model_reservations b JOIN run_steps s ON s.id=b.step_id WHERE s.run_id=?",
                (run_id,),
            ).fetchone()[0]

    def reserve_model(self, run, step_id, request):
        self._has_work = True
        definition = self.agents.get_definition(run.agent_definition_id)
        if definition.agent_key != ROOT_KEY and not definition.agent_key.startswith(
            ROLE_PREFIX
        ):
            return
        if run.parent_run_id and not self.binding(run.id):
            raise SubagentError("child_scope_denied", "No host child binding.")
        root_id = run.root_run_id
        input_bound = (
            math.ceil(len(json.dumps(request, ensure_ascii=False).encode()) / 4) + 128
        )
        with self.db.transaction(write=True) as con:
            if con.execute(
                "SELECT 1 FROM coding_model_reservations WHERE step_id=?", (step_id,)
            ).fetchone():
                return
            used = con.execute(
                "SELECT COALESCE(SUM(COALESCE(charged_tokens,reserved_tokens)),0) FROM coding_model_reservations WHERE root_run_id=?",
                (root_id,),
            ).fetchone()[0]
            allowance = (
                ROOT_TOKENS - used - (PARENT_RESERVE if run.parent_run_id else 0)
            )
            if run.parent_run_id:
                child_limit = run.delegation.get("budget", {}).get(
                    "max_model_tokens", 20000
                )
                child_used = con.execute(
                    "SELECT COALESCE(SUM(COALESCE(b.charged_tokens,b.reserved_tokens)),0) FROM coding_model_reservations b JOIN run_steps s ON s.id=b.step_id WHERE s.run_id=?",
                    (run.id,),
                ).fetchone()[0]
                allowance = min(allowance, child_limit - child_used)
            if allowance <= input_bound:
                raise SubagentError(
                    "child_budget_exhausted"
                    if run.parent_run_id and child_limit - child_used <= input_bound
                    else "root_budget_exhausted",
                    "Cumulative model budget cannot cover the next input. Input and output of every call count; preserve existing evidence.",
                )
            cap = min(
                int(request.get("max_tokens") or 2048), allowance - input_bound, 2048
            )
            request["max_tokens"] = max(1, cap)
            con.execute(
                "UPDATE run_steps SET input_json=? WHERE id=?",
                (json.dumps(request), step_id),
            )
            con.execute(
                "INSERT INTO coding_model_reservations(step_id,root_run_id,reserved_tokens) VALUES(?,?,?)",
                (step_id, root_id, input_bound + cap),
            )

    def settle_model(self, step_id, output):
        usage = output.get("usage", {}) if isinstance(output, dict) else {}
        total = usage.get("total_tokens") if isinstance(usage, dict) else None
        with self.db.transaction(write=True) as con:
            if isinstance(total, int) and total >= 0:
                con.execute(
                    "UPDATE coding_model_reservations SET charged_tokens=?,estimated=0 WHERE step_id=? AND charged_tokens IS NULL",
                    (total, step_id),
                )
            else:
                con.execute(
                    "UPDATE coding_model_reservations SET charged_tokens=reserved_tokens,estimated=1 WHERE step_id=? AND charged_tokens IS NULL",
                    (step_id,),
                )

    async def maintain(self):
        if not self._has_work:
            return
        with self.db.transaction() as con:
            waits = con.execute("SELECT * FROM agent_deferred_waits").fetchall()
            roots = [
                r[0]
                for r in con.execute(
                    "SELECT DISTINCT c.root_run_id FROM coding_subagents c JOIN agent_runs r ON r.id=c.child_run_id WHERE r.status NOT IN ('completed','failed','cancelled') OR EXISTS(SELECT 1 FROM process_executions p WHERE p.run_id=c.child_run_id AND p.status IN ('starting','running'))"
                )
            ]
        for row in waits:
            parent = self.agents.get_run(row["run_id"])
            binding = json.loads(row["binding_json"])
            states = [
                self.agents.get_run(i).status.value in TERMINAL for i in binding["ids"]
            ]
            timed_out = format_utc(datetime.now(UTC)) >= row["deadline_at"]
            ready = any(states) if binding["mode"] == "any" else all(states)
            if parent.status.value in TERMINAL or ready or timed_out:
                output = {
                    "schema_version": 1,
                    "child_run_ids": binding["ids"],
                    "ready": ready,
                    "timed_out": timed_out,
                    "root_remaining_tokens": max(
                        0, ROOT_TOKENS - self.used(parent.root_run_id)
                    ),
                    "instruction": "Read subagent_status for evidence and source freshness.",
                }
                status = (
                    RunStepStatus.CANCELLED
                    if parent.status.value in TERMINAL
                    else RunStepStatus.COMPLETED
                )
                self.agents.settle_step(row["step_id"], status=status, output=output)
                with self.db.transaction(write=True) as con:
                    con.execute(
                        "DELETE FROM agent_deferred_waits WHERE run_id=?", (parent.id,)
                    )
        # Reconcile completed responses after a process loss between step settlement and budget settlement.
        with self.db.transaction() as con:
            settlements = con.execute(
                "SELECT b.step_id,s.output_json FROM coding_model_reservations b JOIN run_steps s ON s.id=b.step_id WHERE b.charged_tokens IS NULL AND s.status='completed'"
            ).fetchall()
        for settlement in settlements:
            self.settle_model(
                settlement["step_id"], json.loads(settlement["output_json"] or "{}")
            )
        for process in self.runtime.processes.repository.active():
            binding = self.binding(process.run_id) if process.run_id else None
            if binding and self.agents.get_run(process.run_id).status.value in TERMINAL:
                await self.runtime.processes.cancel(
                    process.id, session_id=process.session_id, run_id=process.run_id
                )
        for root in roots:
            parent = self.agents.get_run(root)
            if parent.status.value in TERMINAL:
                for child in self.agents.list_children(root):
                    if child.status.value not in TERMINAL:
                        self.runtime.agent_runtime.cancel(child.id)
                    for process in self.runtime.processes.repository.active():
                        if process.run_id == child.id:
                            await self.runtime.processes.cancel(
                                process.id, session_id=child.session_id, run_id=child.id
                            )

    def merge(self, parent_id, child_id, revision, principal):
        binding = self.owned(parent_id, child_id)
        run = self.agents.get_run(child_id)
        if binding["role"] != "worker" or run.status is not AgentRunStatus.COMPLETED:
            raise SubagentError(
                "worker_not_complete", "Only a completed worker patch may be merged."
            )
        if self.runtime.processes.repository.active_for_run(child_id):
            raise SubagentError(
                "worker_process_active",
                "Finish worker processes before merging its patch.",
            )
        return merge_patch(
            self.manager.draft(run.session_id, principal),
            Path(binding["baseline"]),
            Path(binding["workspace"]),
            revision,
        )
