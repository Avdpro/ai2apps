"""Thin AI2Apps host adapter for isolated native App development tasks."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import threading
from pathlib import Path

from ai2apps.apps.access import APP_CODER_USE, has_app_capability
from ai2apps.capabilities import PolicyEffect
from ai2apps.coder.manager import _AI2APPS_GUIDE
from ai2apps.coder.project import ProjectSourceError, SourceProject, test_command
from ai2apps.core import AppInstanceMode, SessionVisibility
from ai2apps.identity import IdentityRepository, RequestPrincipal
from ai2apps.processes.models import ProcessServiceError
from ai2apps.services import (
    ServiceInstanceStatus,
    ServiceRuntimeMode,
    ToolProviderError,
)
from ai2apps.storage.repositories import AppRepository, SessionRepository

from .core import Draft, DraftError, files, safe_path

AGENT_KEY = "ai2apps.app-developer"
TOOLS = [
    *[
        "appdev." + name
        for name in (
            "inspect",
            "list",
            "read",
            "search",
            "write",
            "edit",
            "validate",
            "preview",
            "changes",
            "command",
            "command_status",
        )
    ],
    "appdev.subagent_*",
    "agent.read_plan",
    "agent.update_plan",
    "agent.ask_user",
    "agent.read_tool_result",
    "agent.read_context_checkpoint",
    "agent.read_session_memory",
]
INSTRUCTIONS = """You develop and debug AI2Apps Apps and Mini-Apps in an isolated source draft.
Use bounded analyst/tester/reviewer children when independent checks help. Workers may modify
separate snapshots and return patches; merge only after reviewing their changes and conflicts.
Start returns immediately. Wait releases scheduler capacity; then read status for evidence and
stale versions. At most two children execute concurrently and four attempts total; no recursion.
Do not claim child checks apply to a newer source snapshot. Keep budget for your final synthesis.
The 100000-token root budget counts repeated input and output of every model call, including
all children. Batch independent tool calls, avoid redundant broad inspection, and use the default
20000-token child budget for ordinary work; a smaller budget can exhaust before even two edits.
Do not blindly retry budget failures. Preserve results and finish within the remaining allowance.
Subagent results and wait wakeups report root_remaining_tokens. Below 20000, avoid new children
or repeated inspection: batch required status/validate/changes, then synthesize the final report.
Use appdev.inspect first, then read AGENTS.md and relevant custom project guides when present.
Inspect supplies the builtin AI2Apps guide. If project_guide_matches_builtin is true, do not
read docs/AI2APPS.md again. For worker merge use the PARENT appdev.changes revision, never
the worker patch revision. A stale_parent rejection requires re-reading and passing that value.
Use appdev.list/read/search for source discovery. Reads return line windows and sha256;
read before editing. appdev.edit requires an exact unique match unless replace_all is explicit.
Use appdev.write for new files or a full observed-file replacement. Never invent schemas:
reuse the project manifests and the AI2Apps guide supplied below. Build a usable App/Mini-App,
not a headless workflow disguised as a Mini-App. Keep edits scoped to the user's request.
Preserve existing component identities.
Register new subdirectory components in .ai2apps/project.json using components entries such as
{"kind":"app","path":"."} and {"kind":"mini-app","path":"notes"}, preserving existing entries.
Empty components auto-discover only root manifests. Confirm validate lists EVERY requested new
component ID; valid=true alone does not prove an unregistered Mini-App was discovered.
Voice Studio output producers must use the host-owned
Quick Read Preview & Output; never add separate playback, download or output histories.
Read docs/ai2apps-studio-mini-app-package-contract-v1.md when available for that contract.
Run appdev.validate and appropriate tests using appdev.command. Nonzero exit codes are
normal command results: inspect logs and repair the cause. A running command returns a
process_id; use appdev.command_status to continue reading, never restart it just to get output.
Network is disabled; dependency/credential files and symlinks are excluded. Do not circumvent
sandbox denials. Do not publish, install, modify the original project or claim visual acceptance
from manifest validation. appdev.preview returns a safe local draft preview for the user.
Finish with appdev.changes and describe changed files, tests, failures and remaining limits.
The user reviews and applies changes in Coder. Say clearly when tests were not run.
"""


class AppDevelopmentManager:
    def __init__(self, runtime):
        self.runtime = runtime
        self.lock = threading.RLock()
        self.drafts = {}

    def _principal(self, principal):
        principal = principal or RequestPrincipal.legacy_local()
        if not has_app_capability(principal, APP_CODER_USE):
            raise DraftError("coder_access_denied", "Current account cannot use Coder.")
        return principal

    def _task(self, task_id, principal):
        principal = self._principal(principal)
        with self.runtime.database.transaction() as con:
            row = con.execute(
                'SELECT s.metadata_json,i.owner_user_id FROM sessions s JOIN app_instances i ON i.id=s.app_instance_id WHERE s.id=? AND s.status="active"',
                (task_id,),
            ).fetchone()
        if row is None or row["owner_user_id"] != (
            None
            if principal.authentication_type == "legacy_api_key"
            else principal.actor_user_id
        ):
            raise DraftError("task_not_found", "Development task not found.")
        binding = json.loads(row["metadata_json"]).get("app_development")
        if not isinstance(binding, dict):
            raise DraftError("task_not_found", "Development task not found.")
        project = self.runtime.coder._project_row(
            binding["project_id"], principal=principal
        )
        if Path(project["root_path"]).resolve() != Path(binding["source_root"]):
            raise DraftError(
                "project_binding_changed", "Project root changed; start a new draft."
            )
        return binding, project

    def draft(self, task_id, principal):
        binding, project = self._task(task_id, principal)
        workspace = self.runtime.workspace._root(task_id)
        with self.lock:
            draft = self.drafts.get(task_id)
            if draft is None:
                draft = Draft(
                    Path(project["root_path"]),
                    workspace,
                    workspace.parent / "app-development.json",
                )
                self.drafts[task_id] = draft
        return draft

    def latest_task(self, project_id, principal):
        principal = self._principal(principal)
        self.runtime.coder._project_row(project_id, principal=principal)
        owner = None if principal.authentication_type == "legacy_api_key" else principal.actor_user_id
        with self.runtime.database.transaction() as con:
            row = con.execute(
                "SELECT s.id FROM sessions s JOIN app_instances i ON i.id=s.app_instance_id "
                "WHERE s.status='active' AND i.owner_user_id IS ? "
                "AND json_extract(s.metadata_json,'$.app_development.project_id')=? "
                "ORDER BY s.created_at DESC,s.id DESC LIMIT 1", (owner, project_id),
            ).fetchone()
        return {"task_id": row["id"] if row else None}

    def start(self, project_id, prompt, model, principal, *, task_id=None):
        principal = self._principal(principal)
        project = self.runtime.coder._project_row(project_id, principal=principal)
        if project["kind"] != "ai2apps":
            raise DraftError(
                "not_ai2apps_project",
                "Native development targets AI2Apps source Projects.",
            )
        if not model or not model.strip():
            raise DraftError(
                "model_required", "Choose an AI2Apps model that supports tool calls."
            )
        if not prompt.strip() or len(prompt) > 32768:
            raise DraftError(
                "invalid_prompt",
                "Describe the App development task in 1–32768 characters.",
            )
        with self.lock:
            if task_id:
                binding, _ = self._task(task_id, principal)
                if binding["project_id"] != project_id:
                    raise DraftError(
                        "task_not_found",
                        "Development task does not belong to this Project.",
                    )
                if self.draft(task_id, principal)._load()["applied"]:
                    raise DraftError(
                        "draft_applied", "Create a new task after applying a draft."
                    )
                if self._active_runs(task_id):
                    raise DraftError(
                        "task_busy", "This development task is still running."
                    )
            else:
                repository = AppRepository(self.runtime.database, self.runtime.events)
                with self.runtime.database.transaction() as con:
                    definition = con.execute(
                        "SELECT id FROM app_definitions WHERE package_id=? AND package_version=?",
                        ("ai2apps.coder-draft", "1"),
                    ).fetchone()
                definition_id = (
                    definition["id"]
                    if definition
                    else repository.create_definition(
                        package_id="ai2apps.coder-draft",
                        package_version="1",
                        display_name="Coder development task",
                        instance_mode=AppInstanceMode.MULTIPLE,
                    ).id
                )
                instance = repository.create_instance(
                    app_definition_id=definition_id,
                    owner_user_id=(
                        None
                        if principal.authentication_type == "legacy_api_key"
                        else principal.actor_user_id
                    ),
                )
                session = SessionRepository(
                    self.runtime.database, self.runtime.events
                ).create(
                    app_instance_id=instance.id,
                    title=project["name"] + " · AI2Apps Agent",
                    visibility=SessionVisibility.UNLISTED,
                    metadata={
                        "app_development": {
                            "project_id": project_id,
                            "source_root": str(Path(project["root_path"]).resolve()),
                        }
                    },
                )
                task_id = session.id
                self.runtime.workspace.ensure_sandbox(task_id)
                self.draft(task_id, principal).create()
            run, _ = self.runtime.agents.create_run(
                session_id=task_id,
                agent_key=AGENT_KEY,
                input={"prompt": prompt, "model": model},
            )
            self.runtime.agent_runtime.wake()
            return {"task_id": task_id, "project_id": project_id, "run_id": run.id}

    def _runs(self, task_id):
        with self.runtime.database.transaction() as con:
            ids = con.execute(
                "SELECT id FROM agent_runs WHERE session_id=? ORDER BY created_at",
                (task_id,),
            ).fetchall()
        return [self.runtime.agents.get_run(row["id"]) for row in ids]

    def _active_runs(self, task_id):
        return [
            run
            for run in self._runs(task_id)
            if run.status.value not in {"completed", "failed", "cancelled"}
        ]

    def status(self, task_id, principal):
        binding, _ = self._task(task_id, principal)
        runs = [run for run in self._runs(task_id) if run.parent_run_id is None]
        run = runs[-1] if runs else None
        if run is None:
            return {
                "task_id": task_id,
                "project_id": binding["project_id"],
                "status": "empty",
            }
        steps = self.runtime.agents.list_steps(run.id)
        interactions = self.runtime.agents.list_interactions(run.id)
        return {
            "task_id": task_id,
            "project_id": binding["project_id"],
            "run_id": run.id,
            "status": (
                "waiting_subruns"
                if run.status.value == "queued" and self.cooperation.waiting(run.id)
                else run.status.value
            ),
            "children": self.cooperation.children(run.id, principal),
            "root_used_tokens": self.cooperation.used(run.id),
            "output": run.output,
            "error": run.error,
            "steps": [
                {
                    "sequence": step.sequence,
                    "kind": step.kind,
                    "tool": step.tool_name,
                    "status": step.status.value,
                    "error": step.error,
                }
                for step in steps
            ],
            "interactions": [
                {
                    "id": item.id,
                    "kind": item.kind.value,
                    "prompt": item.prompt,
                    "status": item.status.value,
                    "request": item.request,
                    "response_schema": item.response_schema,
                }
                for item in interactions
            ],
            "applied": self.draft(task_id, principal)._load()["applied"],
        }

    def stop(self, task_id, principal):
        self._task(task_id, principal)
        for run in self._active_runs(task_id):
            self.runtime.agent_runtime.cancel(run.id)
        return self.status(task_id, principal)

    def respond(self, task_id, interaction_id, response, principal):
        self._task(task_id, principal)
        run = self._runs(task_id)[-1]
        if not any(
            item.id == interaction_id
            for item in self.runtime.agents.list_interactions(run.id)
        ):
            raise DraftError(
                "interaction_not_found", "Interaction does not belong to this task."
            )
        self.runtime.agents.respond_interaction(
            run.id,
            interaction_id,
            response=response,
            response_id="appdev-" + interaction_id,
        )
        self.runtime.agent_runtime.wake()
        return self.status(task_id, principal)

    def inspect(self, task_id, principal):
        draft = self.draft(task_id, principal)
        inventory, _ = files(draft.workspace)
        report = SourceProject(draft.workspace).validate()
        return {
            "files": list(inventory),
            "excluded": draft._load()["excluded"],
            "validation": report,
            "test_command": test_command(draft.workspace),
            "guide": _AI2APPS_GUIDE,
            "project_guide_matches_builtin": inventory.get("docs/AI2APPS.md", {}).get("sha256") == hashlib.sha256(_AI2APPS_GUIDE.encode()).hexdigest(),
        }

    def review(self, task_id, principal):
        draft = self.draft(task_id, principal)
        return {
            **draft.review(),
            "validation": SourceProject(draft.workspace).validate(),
        }

    def apply(self, task_id, revision, principal):
        with self.lock:
            self._task(task_id, principal)
            if self._active_runs(task_id):
                raise DraftError(
                    "task_busy", "Stop or finish the task before applying changes."
                )
            draft = self.draft(task_id, principal)
            report = SourceProject(draft.workspace).validate()
            if not report["valid"] or not any(
                item["kind"] in {"app", "mini-app"} for item in report["components"]
            ):
                raise DraftError(
                    "validation_failed",
                    "A valid App or Mini-App component is required before applying.",
                )
            result = draft.apply(revision)
            self.runtime.events.append(
                event_type="coder.draft.applied",
                subject_id=task_id,
                session_id=task_id,
                app_instance_id=SessionRepository(self.runtime.database)
                .get(task_id)
                .app_instance_id,
                payload={"revision": revision, "paths": result["applied"]},
            )
            return result

    def resource(self, task_id, component_id, resource, principal):
        draft = self.draft(task_id, principal)
        source = SourceProject(draft.workspace)
        component = source.component(component_id)
        if not component.public()["runnable"]:
            raise DraftError("not_previewable", "Component has no safe HTML preview.")
        # SourceProject enforces its resource root; additionally reject all symlinks.
        path = source.resolve_resource(component, resource)
        safe_path(draft.workspace, path.relative_to(draft.workspace).as_posix())
        return path

    def tool_context(self, context):
        if not context.session_id or not context.trace_id:
            raise ToolProviderError("Development tools require a bound Agent Run.")
        run = self.runtime.agents.get_run(context.trace_id)
        definition = self.runtime.agents.get_definition(run.agent_definition_id)
        if run.session_id != context.session_id or definition.agent_key != AGENT_KEY:
            raise ToolProviderError("Development tool Run scope mismatch.")
        if context.actor_user_id in {None, "local"}:
            principal = RequestPrincipal.legacy_local()
        else:
            principal = IdentityRepository(self.runtime.database).local_principal_for(
                context.actor_user_id
            )
        self._task(context.session_id, principal)
        return context.session_id, principal

    async def command(self, task_id, argv, cwd, context):
        if argv[0] in {"python", "python3"}:
            argv = [sys.executable, *argv[1:]]
        record = await self.runtime.processes.start(
            session_id=task_id,
            run_id=context.trace_id,
            caller_id=context.caller_id,
            argv=argv,
            cwd=cwd,
            network_enabled=False,
        )
        return await self.command_status(task_id, record.id, 0, 1000, context)

    async def command_status(self, task_id, process_id, after, wait_ms, context):
        try:
            record = await self.runtime.processes.wait(
                process_id,
                session_id=task_id,
                run_id=context.trace_id,
                timeout_ms=wait_ms,
            )
        except ProcessServiceError as error:
            if error.code != "process_wait_timeout":
                raise
            record = self.runtime.processes.status(
                process_id, session_id=task_id, run_id=context.trace_id
            )
        logs = self.runtime.processes.logs(
            process_id,
            session_id=task_id,
            run_id=context.trace_id,
            after=after,
            limit=10,
        )
        return {
            "process_id": record.id,
            "status": record.status.value,
            "exit_code": record.exit_code,
            "error": record.error,
            "logs": [
                {
                    "sequence": item.sequence,
                    "stream": item.stream,
                    "content": item.content,
                    "encoding": item.encoding,
                }
                for item in logs
            ],
            "next_after": logs[-1].sequence if logs else after,
            "running": not record.status.terminal,
        }


def _migrate_builtin_executor(database):
    """Upgrade only the host-owned legacy App Developer definition."""
    with database.transaction(write=True) as connection:
        connection.execute(
            """UPDATE agent_definitions
               SET executor_key = 'builtin:coding-parent', revision = revision + 1
               WHERE agent_key = ? AND source = 'builtin'
                 AND executor_key = 'builtin:general-agent'""",
            (AGENT_KEY,),
        )


def install_app_development(runtime):
    _migrate_builtin_executor(runtime.database)
    manager = AppDevelopmentManager(runtime)
    runtime.app_development = manager
    runtime.agents.ensure_definition(
        agent_key=AGENT_KEY,
        package_version="1",
        display_name="AI2Apps App Developer",
        description="Develop and debug Apps and Mini-Apps in isolated source drafts.",
        executor_key="builtin:coding-parent",
        concurrency_group="app-development",
        concurrency_limit=1,
        max_steps=80,
        timeout_seconds=900,
        manifest={
            "builtin": True,
            "discoverable": False,
            "allowed_tools": TOOLS,
            "instructions": INSTRUCTIONS,
            "max_total_model_tokens": 100000,
            "max_repeated_tool_calls": 3,
        },
    )
    service = runtime.services.ensure_service(
        service_key="ai2apps.app-development",
        package_id="ai2apps.app-development",
        package_version="1",
        display_name="AI2Apps App development",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
    )
    runtime.services.ensure_instance(
        service_id=service.id,
        provider_key="builtin:app-development",
        status=ServiceInstanceStatus.RUNNING,
    )
    specs = {
        "inspect": ({}, [], (), manager.inspect),
        "list": ({"path": {"type": "string"}}, [], (), None),
        "read": (
            {
                "path": {"type": "string"},
                "offset": {"type": "integer", "minimum": 1},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            },
            ["path"],
            (),
            None,
        ),
        "search": (
            {
                "query": {"type": "string", "minLength": 1},
                "include": {"type": "string"},
            },
            ["query"],
            (),
            None,
        ),
        "write": (
            {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "expected_sha256": {"type": ["string", "null"]},
            },
            ["path", "content"],
            ("write",),
            None,
        ),
        "edit": (
            {
                "path": {"type": "string"},
                "old": {"type": "string", "minLength": 1},
                "new": {"type": "string"},
                "expected_sha256": {"type": "string"},
                "replace_all": {"type": "boolean"},
            },
            ["path", "old", "new", "expected_sha256"],
            ("write",),
            None,
        ),
        "validate": ({}, [], (), None),
        "preview": ({"component_id": {"type": "string"}}, ["component_id"], (), None),
        "changes": ({}, [], (), manager.review),
        "command": (
            {
                "argv": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 64,
                },
                "cwd": {"type": "string"},
            },
            ["argv"],
            ("process",),
            None,
        ),
        "command_status": (
            {
                "process_id": {"type": "string"},
                "after": {"type": "integer", "minimum": 0},
                "wait_ms": {"type": "integer", "minimum": 1, "maximum": 10000},
            },
            ["process_id"],
            (),
            None,
        ),
    }
    descriptions = {
        "inspect": "Inspect the bound draft, component validation, test command and AI2Apps guide.",
        "read": "Read line-numbered UTF-8 source with sha256 and bounded continuation.",
        "edit": "Replace exact observed text; stale or ambiguous edits return an error without modifying files.",
        "write": "Create directories/files or replace an observed UTF-8 file using its sha256.",
        "command": "Start an argv-only command in the isolated draft, network disabled. Nonzero exits are results. Poll a running process_id instead of relaunching.",
        "command_status": "Wait briefly and read the next bounded log page of a process owned by this Run.",
        "changes": "Review draft differences, conflicts and validation; never applies to the original Project.",
        "preview": "Return a protected local draft HTML preview URL; does not prove visual correctness.",
    }
    for name, (properties, required, effects, operation) in specs.items():
        qualified = "appdev." + name
        capability = (
            ("appdev.draft.write",)
            if effects == ("write",)
            else ("appdev.draft.execute",)
            if effects
            else ()
        )
        runtime.services.ensure_tool(
            service_id=service.id,
            qualified_name=qualified,
            display_name="App development " + name,
            description=descriptions.get(
                name, "Operate on the currently bound isolated App development draft."
            ),
            input_schema={
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
            effects=effects,
            required_capabilities=capability,
        )

        async def handler(args, context, name=name, operation=operation):
            task_id, principal = manager.tool_context(context)
            draft = manager.draft(task_id, principal)
            try:
                if operation:
                    return await asyncio.to_thread(operation, task_id, principal)
                if name == "read":
                    return await asyncio.to_thread(
                        draft.read,
                        args["path"],
                        args.get("offset", 1),
                        args.get("limit", 200),
                    )
                if name == "write":
                    return await asyncio.to_thread(
                        draft.write,
                        args["path"],
                        args["content"],
                        args.get("expected_sha256"),
                    )
                if name == "edit":
                    return await asyncio.to_thread(
                        draft.edit,
                        args["path"],
                        args["old"],
                        args["new"],
                        args["expected_sha256"],
                        args.get("replace_all", False),
                    )
                if name == "list":
                    inventory, _ = await asyncio.to_thread(files, draft.workspace)
                    prefix = args.get("path", ".").rstrip("/")
                    return {
                        "files": [
                            p
                            for p in inventory
                            if prefix == "." or p.startswith(prefix + "/")
                        ][:512]
                    }
                if name == "search":
                    import fnmatch

                    inventory, _ = await asyncio.to_thread(files, draft.workspace)
                    results = []
                    for path in inventory:
                        if not fnmatch.fnmatch(path, args.get("include", "*")):
                            continue
                        try:
                            text = safe_path(draft.workspace, path).read_text(
                                encoding="utf-8"
                            )
                        except UnicodeDecodeError:
                            continue
                        for number, line in enumerate(text.splitlines(), 1):
                            if args["query"] in line:
                                results.append(
                                    {"path": path, "line": number, "text": line[:1000]}
                                )
                                if len(results) >= 50:
                                    return {"matches": results, "truncated": True}
                    return {"matches": results, "truncated": False}
                if name == "validate":
                    return await asyncio.to_thread(
                        SourceProject(draft.workspace).validate
                    )
                if name == "preview":
                    component = SourceProject(draft.workspace).component(
                        args["component_id"]
                    )
                    if not component.public()["runnable"]:
                        raise DraftError(
                            "not_previewable",
                            "Choose an App or Mini-App with a safe HTML entry.",
                        )
                    from urllib.parse import quote

                    return {
                        "preview_url": f"/v1/platform/coder/tasks/{task_id}/preview/{quote(component.id, safe='')}",
                        "component_id": component.id,
                        "visual_acceptance": False,
                    }
                if name == "command":
                    return await manager.command(
                        task_id, args["argv"], args.get("cwd", "."), context
                    )
                if name == "command_status":
                    return await manager.command_status(
                        task_id,
                        args["process_id"],
                        args.get("after", 0),
                        args.get("wait_ms", 1000),
                        context,
                    )
            except (DraftError, ProjectSourceError) as error:
                # Only known checks before mutation become ordinary results.
                return {
                    "ok": False,
                    "error": {"code": error.code, "message": str(error)},
                }
            except ProcessServiceError as error:
                raise ToolProviderError(f"{error.code}: {error}") from error
            raise ToolProviderError("Unknown development operation.")

        runtime.service_registry.bind_tool(
            qualified, provider_key="builtin:app-development", handler=handler
        )
        for cap in capability:
            runtime.capabilities.upsert_policy(
                policy_key="builtin." + qualified,
                effect=PolicyEffect.ALLOW,
                capability_pattern=cap,
                agent_pattern=AGENT_KEY,
                tool_pattern=qualified,
                priority=100,
                source="builtin",
            )
    from .subagents.adapter import install

    install(manager)
    return manager
