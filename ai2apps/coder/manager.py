"""Durable Project/Thread orchestration on top of the Terminal Service."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from ai2apps.core import EntityIdKind, new_entity_id, utc_now_text
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.records import canonical_json
from ai2apps.terminal import TerminalManager, TerminalServiceError
from ai2apps.testflight import TestFlightError, TestFlightManager

from .project import (
    DevSession,
    ProjectSourceError,
    SourceProject,
    media_type,
    new_dev_session_id,
    test_command,
)

_AGENTS = ("codex", "opencode", "claude")
_FILE_IGNORES = {".git", "node_modules", "__pycache__", ".pytest_cache"}
_MAX_EDITOR_FILE_BYTES = 2 * 1024 * 1024
_AI2APPS_GUIDE = """# AI2Apps Development Guide

This directory is an AI2Apps source Project. A Project may contain Apps,
Mini-Apps, Agents, and Services. Read `.ai2apps/project.json` first.

## Development workflow

- Use Coder's Validate action to check manifests and source resources.
- Use Coder's Run/Preview action for App and Mini-App development.
- Run the Project tests before declaring work complete.
- Do not package or install a Project merely to preview or test it.
- Build a Project Bundle only when the user asks for a distributable artifact.
- Submit the development Bundle to TestFlight when the user needs to exercise
  the App through the real Launcher and Shell. TestFlight is local-only and
  does not make an unsigned App formally installed.
- The floating Dock reveal is optional presentation chrome. Apps may set
  `presentation.dock_reveal: false` and may call the Shell Bridge from their
  own appropriately placed control instead.

## Mobile-ready App requirements

Treat `mobile.ready: true` as a tested compatibility claim, not as a request
for the Mobile Shell to convert a desktop UI. Mobile resolves entries in this
order: `mobile_entry`, `mini_entry`, then `entry`. Keep `mobile.ready` false or
absent until the selected entry has passed phone-sized and remote-session tests.

- Prefer a dedicated `mobile_entry` when the normal App entry is desktop-sized.
- Package every stylesheet, script, font, image, and other UI asset and use
  relative URLs from the entry document. Do not depend on `/admin/static/*`,
  `/mobile/static/*`, localhost URLs, external CDNs, or the desktop Shell.
- Keep UI code compatible with the restrictive Mobile CSP. Do not require
  inline `<style>`, inline `<script>`, inline event handlers, `eval`, or dynamic
  code generation. Load indexed CSS and JavaScript as external resources.
- Use the constrained Mobile Bridge and documented `/v1/mobile/*` APIs. Never
  call `/admin/*`, unrestricted `/v1/platform/*`, arbitrary local Services, or
  embed credentials and local API keys in phone JavaScript.
- Design for a narrow portrait viewport, safe-area insets, touch targets,
  virtual-keyboard resizing, full-height scrolling, and landscape fallback.
  Keyboard submission must ignore Enter while an IME composition is active.
- Before setting `mobile.ready: true`, validate the manifest, run Project tests,
  preview at a phone viewport, and exercise the App through an authenticated
  Mobile session. The browser console and network log must contain no CSP,
  blocked-frame, missing-asset, MIME-type, or forbidden-route failures.

Built-in host-rendered system Apps are the only exception to package-relative
assets. They must extend the Mobile App base template and explicitly add every
required asset to the local Mobile static allowlist; they still must not emit
`/admin/static/*` URLs or CSP-dependent inline CSS and JavaScript.

## Component package formats

- App: `app.yaml` with schema `ai2apps.app/v1`, packaged as `.ai2app`.
- Mini-App: an App `mini_entry`, or a standalone `mini-app.yaml` source component.
- Agent: `agent.yaml` with schema `ai2apps.agent/v1`, packaged as `.ai2agent`.
- Service: `service.yaml` with schema `ai2apps.service/v1`, packaged as `.ai2service`.

App and Agent archives contain `META/files.json`, `META/sbom.spdx.json`, a
publisher attestation, and publisher signature. Services use the same indexed,
attested archive layout. Never put API keys or other credentials in manifests.
Formal App installation accepts only a trusted signature from the local owner
or AI2Apps Root. Unsigned development Apps remain isolated in TestFlight.

Use existing manifests and tests in the checked-out AI2Apps SDK as the source of
truth. In particular, inspect `ai2apps/extensions/archive.py` for App/Agent
validation and `ai2apps/packages/archive.py` for Service validation. Run the
smallest relevant tests before packaging and validate an archive through the
platform inspect endpoint before installation.
"""


class CoderError(RuntimeError):
    """Stable Coder error suitable for an HTTP response."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class CoderManager:
    def __init__(
        self,
        database: PlatformDatabase,
        terminal: TerminalManager,
        *,
        project_root: str | Path | None = None,
        managed_cli_root: str | Path | None = None,
        codex_home: str | Path | None = None,
        testflight_root: str | Path | None = None,
    ) -> None:
        self.database = database
        self.terminal = terminal
        self.project_root = Path(project_root or terminal.default_cwd).expanduser().resolve()
        self.managed_cli_root = Path(
            managed_cli_root or (Path.home() / ".ai2apps")
        ).expanduser().resolve()
        self.codex_home = Path(
            codex_home or os.environ.get("CODEX_HOME") or (Path.home() / ".codex")
        ).expanduser().resolve()
        self._codex_start_lock = asyncio.Lock()
        self._codex_capture_tasks: dict[str, asyncio.Task[str | None]] = {}
        self._dev_sessions: dict[str, DevSession] = {}
        self.testflight = TestFlightManager(
            database,
            testflight_root or (self.managed_cli_root / "testflight"),
        )
        self.project_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _project(row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "root_path": row["root_path"],
            "kind": row["project_kind"],
            "metadata": json.loads(row["metadata_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _thread(self, row) -> dict[str, Any]:
        status = row["status"]
        terminal_id = row["terminal_session_id"]
        if terminal_id:
            try:
                terminal = self.terminal.get(terminal_id)
                status = "running" if terminal.status == "running" else "stopped"
            except TerminalServiceError:
                status = "stopped"
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "parent_thread_id": row["parent_thread_id"],
            "title": row["title"],
            "agent": row["agent"],
            "model_source": row["model_source"],
            "model": row["model"],
            "terminal_session_id": terminal_id,
            "native_session_id": row["native_session_id"],
            "status": status,
            "metadata": json.loads(row["metadata_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def snapshot(self) -> dict[str, Any]:
        with self.database.transaction() as connection:
            projects = connection.execute(
                "SELECT * FROM coder_projects ORDER BY updated_at DESC"
            ).fetchall()
            threads = connection.execute(
                "SELECT * FROM coder_threads WHERE status != 'archived' "
                "ORDER BY updated_at DESC"
            ).fetchall()
        project_items = [self._decorate_project(self._project(item)) for item in projects]
        return {
            "projects": project_items,
            "threads": [self._thread(item) for item in threads],
            "agents": self.agents(),
            "default_project_root": str(self.project_root),
        }

    @staticmethod
    def _source(project: dict[str, Any]) -> SourceProject:
        return SourceProject(project["root_path"])

    def _decorate_project(self, project: dict[str, Any]) -> dict[str, Any]:
        project["components"] = self._project_components(project)
        project["dev_sessions"] = [
            session.public()
            for session in self._dev_sessions.values()
            if session.project_id == project["id"]
        ]
        return project

    def _project_row(self, project_id: str) -> dict[str, Any]:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM coder_projects WHERE id=?", (project_id,)
            ).fetchone()
        if row is None:
            raise CoderError("project_not_found", "Project not found")
        return self._decorate_project(self._project(row))

    def _project_components(self, project: dict[str, Any]) -> list[dict[str, Any]]:
        if project["kind"] != "ai2apps":
            return []
        try:
            return [item.public() for item in self._source(project).components()]
        except ProjectSourceError as error:
            return [{"id": "project-error", "kind": "error", "name": str(error), "runnable": False}]

    def validate_project(self, project_id: str) -> dict[str, Any]:
        project = self._project_row(project_id)
        if project["kind"] != "ai2apps":
            raise CoderError("not_ai2apps_project", "Validation is available for AI2Apps Projects")
        return self._source(project).validate()

    async def test_project(self, project_id: str) -> dict[str, Any]:
        project = self._project_row(project_id)
        command = test_command(Path(project["root_path"]))
        if command is None:
            return {"ok": True, "skipped": True, "command": [], "output": "No Project test runner was discovered."}
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=project["root_path"],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            output, _ = await asyncio.wait_for(process.communicate(), timeout=120)
        except TimeoutError as error:
            process.kill()
            await process.wait()
            raise CoderError("test_timeout", "Project tests exceeded 120 seconds") from error
        text = output[-256_000:].decode("utf-8", errors="replace")
        return {"ok": process.returncode == 0, "skipped": False, "command": command, "exit_code": process.returncode, "output": text}

    def start_dev_session(self, project_id: str, component_id: str) -> dict[str, Any]:
        project = self._project_row(project_id)
        if project["kind"] != "ai2apps":
            raise CoderError("not_ai2apps_project", "Development runtime requires an AI2Apps Project")
        try:
            component = self._source(project).component(component_id)
        except ProjectSourceError as error:
            raise CoderError(error.code, str(error)) from error
        if not component.public()["runnable"]:
            raise CoderError(
                "component_not_previewable",
                "First-version preview supports App and Mini-App sandbox or safe-html entries",
            )
        report = self._source(project).validate()
        failed = next(
            (item for item in report["checks"] if not item["ok"] and item.get("component_id") == component_id),
            None,
        )
        if failed:
            raise CoderError("validation_failed", failed["message"])
        existing = next(
            (
                session
                for session in self._dev_sessions.values()
                if session.project_id == project_id and session.component.id == component_id
            ),
            None,
        )
        if existing is not None:
            return existing.public()
        session = DevSession(new_dev_session_id(), project_id, component)
        self._dev_sessions[session.id] = session
        return session.public()

    def stop_dev_session(self, session_id: str) -> dict[str, Any]:
        session = self._dev_sessions.pop(session_id, None)
        if session is None:
            raise CoderError("dev_session_not_found", "Development Session not found")
        return {**session.public(), "status": "stopped"}

    def dev_session(self, session_id: str) -> DevSession:
        session = self._dev_sessions.get(session_id)
        if session is None:
            raise CoderError("dev_session_not_found", "Development Session not found")
        return session

    def resolve_dev_resource(self, session_id: str, resource: str) -> tuple[Path, str]:
        session = self.dev_session(session_id)
        try:
            path = SourceProject(session.component.root).resolve_resource(
                session.component, resource
            )
        except ProjectSourceError as error:
            raise CoderError(error.code, str(error)) from error
        return path, media_type(path)

    def build_project(self, project_id: str) -> dict[str, Any]:
        project = self._project_row(project_id)
        if project["kind"] != "ai2apps":
            raise CoderError("not_ai2apps_project", "Project Bundle requires an AI2Apps Project")
        try:
            path = self._source(project).build()
        except ProjectSourceError as error:
            raise CoderError(error.code, str(error)) from error
        return {"ok": True, "path": str(path), "development": True, "installable": False}

    def submit_project_testflight(self, project_id: str) -> dict[str, Any]:
        built = self.build_project(project_id)
        try:
            return self.testflight.submit(built["path"])
        except TestFlightError as error:
            raise CoderError(error.code, str(error)) from error

    def _project_file(
        self, project_id: str, relative_path: str, *, missing: bool = False
    ) -> tuple[dict[str, Any], Path]:
        project = self._project_row(project_id)
        pure = PurePosixPath(relative_path)
        if (
            not relative_path
            or pure.is_absolute()
            or ".." in pure.parts
            or "\\" in relative_path
            or "\x00" in relative_path
        ):
            raise CoderError("unsafe_file_path", "Project file path must be safe and relative")
        root = Path(project["root_path"]).resolve(strict=True)
        candidate = root.joinpath(*pure.parts)
        try:
            resolved = candidate.resolve(strict=not missing)
        except FileNotFoundError as error:
            raise CoderError("file_not_found", "Project file not found") from error
        if not resolved.is_relative_to(root):
            raise CoderError("unsafe_file_path", "Project file leaves the Project directory")
        if candidate.is_symlink() or any(part in _FILE_IGNORES for part in pure.parts):
            raise CoderError("unsafe_file_path", "Project file is not editable")
        return project, resolved

    def list_project_files(self, project_id: str, path: str = ".") -> dict[str, Any]:
        project, directory = self._project_file(project_id, path)
        if not directory.is_dir():
            raise CoderError("not_directory", "Project path is not a directory")
        root = Path(project["root_path"]).resolve()
        items: list[dict[str, Any]] = []
        for item in sorted(directory.iterdir(), key=lambda value: (not value.is_dir(), value.name.lower())):
            if item.name in _FILE_IGNORES or item.is_symlink():
                continue
            stat = item.stat()
            items.append(
                {
                    "name": item.name,
                    "path": item.relative_to(root).as_posix(),
                    "kind": "directory" if item.is_dir() else "file",
                    "size_bytes": None if item.is_dir() else stat.st_size,
                }
            )
            if len(items) >= 1000:
                break
        return {"path": path, "items": items, "truncated": len(items) >= 1000}

    def read_project_file(self, project_id: str, path: str) -> dict[str, Any]:
        _project, item = self._project_file(project_id, path)
        if not item.is_file():
            raise CoderError("not_file", "Project path is not a file")
        size = item.stat().st_size
        if size > _MAX_EDITOR_FILE_BYTES:
            raise CoderError("file_too_large", "Editor files are limited to 2 MiB")
        try:
            content = item.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise CoderError("binary_file", "Binary files cannot be edited") from error
        return {"path": path, "content": content, "size_bytes": size}

    def write_project_file(self, project_id: str, path: str, content: str) -> dict[str, Any]:
        if len(content.encode("utf-8")) > _MAX_EDITOR_FILE_BYTES:
            raise CoderError("file_too_large", "Editor files are limited to 2 MiB")
        _project, item = self._project_file(project_id, path, missing=True)
        if item.exists() and not item.is_file():
            raise CoderError("not_file", "Project path is not a file")
        if not item.parent.is_dir():
            raise CoderError("parent_not_found", "Parent directory does not exist")
        mode = item.stat().st_mode if item.exists() else None
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=item.parent, delete=False
        ) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        try:
            if mode is not None:
                temporary.chmod(mode)
            temporary.replace(item)
        finally:
            temporary.unlink(missing_ok=True)
        return self.read_project_file(project_id, path)

    async def delete_thread(self, thread_id: str) -> dict[str, Any]:
        stopped = await self.stop_thread(thread_id)
        with self.database.transaction(write=True) as connection:
            connection.execute("DELETE FROM coder_threads WHERE id=?", (thread_id,))
        capture = self._codex_capture_tasks.pop(thread_id, None)
        if capture is not None:
            capture.cancel()
        return {"id": stopped["id"], "deleted": True}

    async def remove_project(self, project_id: str) -> dict[str, Any]:
        project = self._project_row(project_id)
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT id FROM coder_threads WHERE project_id=?", (project_id,)
            ).fetchall()
        for row in rows:
            try:
                await self.stop_thread(row["id"])
            except CoderError as error:
                if error.code != "thread_not_found":
                    raise
        self._dev_sessions = {
            key: value
            for key, value in self._dev_sessions.items()
            if value.project_id != project_id
        }
        with self.database.transaction(write=True) as connection:
            connection.execute("DELETE FROM coder_projects WHERE id=?", (project_id,))
        return {"id": project["id"], "deleted": True, "directory_deleted": False}

    def _agent_executable(self, agent: str) -> str | None:
        managed = self.managed_cli_root / "node_modules" / ".bin" / agent
        if managed.is_file() and os.access(managed, os.X_OK):
            return str(managed)
        return shutil.which(agent)

    def agents(self) -> list[dict[str, Any]]:
        labels = {"codex": "Codex", "opencode": "OpenCode", "claude": "Claude Code"}
        return [
            {
                "id": agent,
                "name": labels[agent],
                "installed": self._agent_executable(agent) is not None,
            }
            for agent in _AGENTS
        ]

    def create_project(
        self,
        *,
        name: str,
        root_path: str,
        kind: str = "general",
        create_directory: bool = False,
        bootstrap: bool = False,
    ) -> dict[str, Any]:
        label = name.strip()
        if not label or len(label) > 120:
            raise CoderError("invalid_name", "Project name is invalid")
        if kind not in {"general", "ai2apps"}:
            raise CoderError("invalid_kind", "Project kind is invalid")
        requested_path = Path(root_path).expanduser()
        path = (
            requested_path.resolve()
            if requested_path.is_absolute()
            else (self.project_root / requested_path).resolve()
        )
        if create_directory:
            path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            raise CoderError("invalid_path", "Project directory does not exist")
        project_id = new_entity_id(EntityIdKind.CODER_PROJECT)
        now = utc_now_text()
        try:
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    "INSERT INTO coder_projects(id,name,root_path,project_kind,"
                    "metadata_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                    (project_id, label, str(path), kind, "{}", now, now),
                )
                row = connection.execute(
                    "SELECT * FROM coder_projects WHERE id=?", (project_id,)
                ).fetchone()
        except Exception as error:
            if "UNIQUE constraint failed" in str(error):
                raise CoderError("project_exists", "Project directory is already added") from error
            raise
        if kind == "ai2apps" and bootstrap:
            self._bootstrap_ai2apps(path, label)
        return self._decorate_project(self._project(row))

    @staticmethod
    def _bootstrap_ai2apps(path: Path, name: str) -> None:
        metadata_dir = path / ".ai2apps"
        metadata_dir.mkdir(exist_ok=True)
        manifest = metadata_dir / "project.json"
        if not manifest.exists():
            manifest.write_text(
                json.dumps(
                    {"schema": "ai2apps.project/v1", "name": name, "components": []},
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
        instructions = path / "AGENTS.md"
        if not instructions.exists():
            instructions.write_text(
                "# AI2Apps Project\n\n"
                "Read `.ai2apps/project.json` and `docs/AI2APPS.md` before "
                "changing components.\n"
                "Use the repository's tests and existing manifests as the source of truth.\n"
                "Never place credentials in manifests or generated artifacts.\n",
                encoding="utf-8",
            )
        docs = path / "docs"
        docs.mkdir(exist_ok=True)
        guide = docs / "AI2APPS.md"
        if not guide.exists():
            guide.write_text(_AI2APPS_GUIDE, encoding="utf-8")

    def create_thread(
        self,
        *,
        project_id: str,
        title: str,
        agent: str,
        model_source: str = "default",
        model: str = "",
        parent_thread_id: str | None = None,
    ) -> dict[str, Any]:
        label = title.strip()
        if not label or len(label) > 160:
            raise CoderError("invalid_title", "Thread title is invalid")
        if agent not in _AGENTS:
            raise CoderError("invalid_agent", "Unsupported coding Agent")
        if model_source not in {"default", "ai2apps"}:
            raise CoderError("invalid_model_source", "Invalid model source")
        if model_source == "ai2apps" and not model.strip():
            raise CoderError("model_required", "Choose an AI2Apps model")
        thread_id = new_entity_id(EntityIdKind.CODER_THREAD)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            project = connection.execute(
                "SELECT id FROM coder_projects WHERE id=?", (project_id,)
            ).fetchone()
            if project is None:
                raise CoderError("project_not_found", "Project not found")
            if parent_thread_id:
                parent = connection.execute(
                    "SELECT project_id FROM coder_threads WHERE id=?", (parent_thread_id,)
                ).fetchone()
                if parent is None or parent["project_id"] != project_id:
                    raise CoderError("invalid_parent", "Parent Thread is invalid")
            connection.execute(
                "INSERT INTO coder_threads(id,project_id,parent_thread_id,title,agent,"
                "model_source,model,metadata_json,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    thread_id,
                    project_id,
                    parent_thread_id,
                    label,
                    agent,
                    model_source,
                    model.strip(),
                    canonical_json({"fork_mode": "structural"} if parent_thread_id else {}),
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM coder_threads WHERE id=?", (thread_id,)
            ).fetchone()
        return self._thread(row)

    def fork_thread(self, thread_id: str, *, title: str | None = None) -> dict[str, Any]:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM coder_threads WHERE id=?", (thread_id,)
            ).fetchone()
        if row is None:
            raise CoderError("thread_not_found", "Thread not found")
        return self.create_thread(
            project_id=row["project_id"],
            title=title or f"{row['title']} (fork)",
            agent=row["agent"],
            model_source=row["model_source"],
            model=row["model"],
            parent_thread_id=thread_id,
        )

    @staticmethod
    def _ai2apps_command(
        agent: str, model: str, native_session_id: str | None = None
    ) -> list[str]:
        executable = shutil.which("ai2apps")
        command = [executable] if executable else [sys.executable, "-m", "ai2apps.cli"]
        agent_args: list[str] = []
        if agent == "codex":
            if native_session_id:
                agent_args.extend(("resume", native_session_id))
            agent_args.append("--no-alt-screen")
        return [*command, "launch", agent, "--model", model, *agent_args]

    def _default_agent_command(
        self, agent: str, native_session_id: str | None = None
    ) -> list[str]:
        executable = self._agent_executable(agent)
        if executable is None:
            raise CoderError("agent_not_installed", f"{agent} is not installed")
        command = [executable]
        if agent == "codex":
            if native_session_id:
                command.extend(("resume", native_session_id))
            command.append("--no-alt-screen")
        return command

    def _codex_sessions(self, root_path: str) -> list[tuple[str, float]]:
        sessions_root = self.codex_home / "sessions"
        if not sessions_root.is_dir():
            return []
        expected_cwd = str(Path(root_path).resolve())
        matches: list[tuple[str, float]] = []
        for path in sessions_root.rglob("*.jsonl"):
            try:
                with path.open(encoding="utf-8") as handle:
                    first = json.loads(handle.readline())
                payload = first.get("payload", {})
                source = payload.get("source")
                if source != "cli" or str(Path(payload.get("cwd", "")).resolve()) != expected_cwd:
                    continue
                session_id = payload.get("session_id") or payload.get("id")
                if isinstance(session_id, str) and session_id:
                    matches.append((session_id, path.stat().st_mtime))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return sorted(matches, key=lambda item: item[1], reverse=True)

    def _recover_legacy_codex_session(self, row) -> str | None:
        if row["agent"] != "codex" or row["native_session_id"]:
            return row["native_session_id"]
        # Only infer old data when this is the sole Codex Thread in its Project.
        # New Threads are captured by the launch watcher below.
        with self.database.transaction() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM coder_threads WHERE project_id=? AND agent='codex'",
                (row["project_id"],),
            ).fetchone()[0]
        if count != 1:
            return None
        try:
            created_at = datetime.fromisoformat(
                row["created_at"].replace("Z", "+00:00")
            ).timestamp()
        except (AttributeError, TypeError, ValueError):
            created_at = 0.0
        sessions = [
            item
            for item in self._codex_sessions(row["root_path"])
            if item[1] >= created_at - 5.0
        ]
        return sessions[0][0] if sessions else None

    async def _capture_codex_session(
        self, thread_id: str, root_path: str, previous_ids: set[str]
    ) -> str | None:
        # Codex does not create its rollout file until the first user prompt.
        # Keep watching in the background so a freshly opened Thread is still
        # bound to its native session after the user begins working.
        for _ in range(3_600):
            created = [
                item for item in self._codex_sessions(root_path) if item[0] not in previous_ids
            ]
            if created:
                session_id = created[0][0]
                now = utc_now_text()
                with self.database.transaction(write=True) as connection:
                    connection.execute(
                        "UPDATE coder_threads SET native_session_id=?,updated_at=? WHERE id=?",
                        (session_id, now, thread_id),
                    )
                return session_id
            await asyncio.sleep(1.0)
        return None

    def _schedule_codex_capture(
        self, thread_id: str, root_path: str, previous_ids: set[str]
    ) -> None:
        existing = self._codex_capture_tasks.get(thread_id)
        if existing is not None and not existing.done():
            return
        task = asyncio.create_task(
            self._capture_codex_session(thread_id, root_path, previous_ids),
            name=f"coder-codex-session-{thread_id}",
        )
        self._codex_capture_tasks[thread_id] = task

        def discard(completed: asyncio.Task[str | None]) -> None:
            if self._codex_capture_tasks.get(thread_id) is completed:
                self._codex_capture_tasks.pop(thread_id, None)

        task.add_done_callback(discard)

    async def start_thread(self, thread_id: str) -> dict[str, Any]:
        async with self._codex_start_lock:
            return await self._start_thread_locked(thread_id)

    async def _start_thread_locked(self, thread_id: str) -> dict[str, Any]:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT t.*, p.root_path FROM coder_threads t "
                "JOIN coder_projects p ON p.id=t.project_id WHERE t.id=?",
                (thread_id,),
            ).fetchone()
        if row is None:
            raise CoderError("thread_not_found", "Thread not found")
        if row["terminal_session_id"]:
            try:
                terminal = self.terminal.get(row["terminal_session_id"])
                if terminal.status == "running":
                    return self._thread(row)
            except TerminalServiceError:
                pass
        native_session_id = self._recover_legacy_codex_session(row)
        if native_session_id and native_session_id != row["native_session_id"]:
            now = utc_now_text()
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    "UPDATE coder_threads SET native_session_id=?,updated_at=? WHERE id=?",
                    (native_session_id, now, thread_id),
                )
        previous_codex_ids = (
            {item[0] for item in self._codex_sessions(row["root_path"])}
            if row["agent"] == "codex" and not native_session_id
            else set()
        )
        if row["model_source"] == "ai2apps":
            command = self._ai2apps_command(
                row["agent"], row["model"], native_session_id
            )
        else:
            command = self._default_agent_command(row["agent"], native_session_id)
        managed_bin = self.managed_cli_root / "node_modules" / ".bin"
        environment = {
            "PATH": os.pathsep.join(
                (str(managed_bin), os.environ.get("PATH", ""))
            ).rstrip(os.pathsep)
        }
        try:
            terminal = await self.terminal.create(
                title=row["title"],
                cwd=row["root_path"],
                command=command,
                environment=environment,
                owner="coder",
                owner_id=thread_id,
            )
        except TerminalServiceError as error:
            raise CoderError(error.code, str(error)) from error
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE coder_threads SET terminal_session_id=?,status='running',"
                "updated_at=? WHERE id=?",
                (terminal.id, now, thread_id),
            )
            updated = connection.execute(
                "SELECT * FROM coder_threads WHERE id=?", (thread_id,)
            ).fetchone()
        if row["agent"] == "codex" and not native_session_id:
            self._schedule_codex_capture(
                thread_id, row["root_path"], previous_codex_ids
            )
        return self._thread(updated)

    async def stop_thread(self, thread_id: str) -> dict[str, Any]:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM coder_threads WHERE id=?", (thread_id,)
            ).fetchone()
        if row is None:
            raise CoderError("thread_not_found", "Thread not found")
        if row["terminal_session_id"]:
            try:
                await self.terminal.close(row["terminal_session_id"])
            except TerminalServiceError as error:
                if error.code != "not_found":
                    raise CoderError(error.code, str(error)) from error
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE coder_threads SET terminal_session_id=NULL,status='stopped',"
                "updated_at=? WHERE id=?",
                (now, thread_id),
            )
            updated = connection.execute(
                "SELECT * FROM coder_threads WHERE id=?", (thread_id,)
            ).fetchone()
        return self._thread(updated)
