"""Coder Project/Thread orchestration contracts."""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from ai2apps.apps import SYSTEM_APP_MANIFESTS
from ai2apps.coder import CoderError, CoderManager
from ai2apps.storage import PlatformDatabase
from ai2apps.terminal import TerminalManager


def test_coder_terminal_grid_cannot_grow_to_scrollback_height():
    css = (
        Path(__file__).parents[1]
        / "ai2apps/web/static/css/coder.css"
    ).read_text(encoding="utf-8")

    assert "grid-template-rows: 54px minmax(0, 1fr)" in css
    assert ".coder-main { min-width: 0; min-height: 0;" in css
    assert "grid-template-columns: var(--coder-sidebar) minmax(0, 1fr)" in css


def test_coder_editor_uses_compact_dark_scrollbars():
    css = (
        Path(__file__).parents[1] / "ai2apps/web/static/css/coder.css"
    ).read_text(encoding="utf-8")

    assert "#coder-editor .ace_scrollbar-v { width: 9px !important" in css
    assert "#coder-editor .ace_scrollbar-h { height: 9px !important" in css
    assert "scrollbar-color: #4b4e58 transparent" in css
    assert "background-clip: padding-box" in css


def test_xterm_uses_the_same_compact_dark_scrollbar():
    css = (
        Path(__file__).parents[1] / "ai2apps/web/static/css/xterm.css"
    ).read_text(encoding="utf-8")

    assert "scrollbar-color: #4b4e58 transparent" in css
    assert ".xterm .xterm-viewport::-webkit-scrollbar { width: 9px; height: 9px; }" in css
    assert "border-radius: 999px" in css


def test_coder_uses_ai2apps_model_catalog_instead_of_freeform_model_id():
    web_root = Path(__file__).parents[1] / "ai2apps/web"
    template = (web_root / "templates/system_apps/coder.html").read_text(
        encoding="utf-8"
    )
    script = (web_root / "static/js/coder.js").read_text(encoding="utf-8")

    assert 'select name="model" data-model-select' in template
    assert 'input name="model"' not in template
    assert "api('/admin/api/models')" in script
    assert "model.source_type === 'cloud'" in script
    assert "model.source_type === 'fusion'" in script
    assert "model.exposed_profiles" in script


def test_coder_has_collapsible_sidebar_context_actions_and_local_ide():
    root = Path(__file__).parents[1]
    web_root = root / "ai2apps/web"
    template = (web_root / "templates/system_apps/coder.html").read_text(
        encoding="utf-8"
    )
    script = (web_root / "static/js/coder.js").read_text(encoding="utf-8")
    routes = (root / "omlx/admin/routes.py").read_text(encoding="utf-8")

    assert 'data-action="toggle-sidebar"' in template
    assert 'data-context-menu' in template
    assert 'data-coder-ide' in template
    assert "vendor/ace/ace.js" in template
    assert (web_root / "static/vendor/ace/LICENSE").is_file()
    assert "showFoldWidgets: true" in script
    assert "saveProjectFile" in script
    assert "contextmenu" in script
    assert '@router.get("/api/coder/projects/{project_id}/files")' in routes
    assert '@router.put("/api/coder/projects/{project_id}/file")' in routes
    assert '@router.delete("/api/coder/threads/{thread_id}")' in routes
    assert 'data-action="testflight"' in template
    assert '@router.post("/api/coder/projects/{project_id}/testflight")' in routes


def test_coder_opts_out_of_optional_floating_dock_reveal():
    root = Path(__file__).parents[1]
    coder = next(
        item
        for item in SYSTEM_APP_MANIFESTS
        if item["id"] == "ai2apps.coder"
    )
    base = (root / "ai2apps/web/templates/base.html").read_text(encoding="utf-8")

    assert coder["presentation"] == {"dock_reveal": False}
    assert "show_dock_reveal | default(true)" in base
    assert "if (showDockReveal)" in base


@pytest.fixture
def coder(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    terminal = TerminalManager(default_cwd=tmp_path)
    return CoderManager(
        database,
        terminal,
        project_root=tmp_path / "projects",
        managed_cli_root=tmp_path / "managed-cli",
        codex_home=tmp_path / "codex-home",
    ), terminal


def test_coder_resolves_relative_paths_from_default_project_root(coder, tmp_path):
    manager, _terminal = coder

    project = manager.create_project(
        name="Relative",
        root_path="group/example",
        create_directory=True,
    )

    assert manager.project_root == (tmp_path / "projects").resolve()
    assert project["root_path"] == str((tmp_path / "projects/group/example").resolve())
    assert (tmp_path / "projects/group/example").is_dir()
    assert manager.snapshot()["default_project_root"] == str(
        (tmp_path / "projects").resolve()
    )


def test_coder_keeps_absolute_project_paths(coder, tmp_path):
    manager, _terminal = coder
    absolute = tmp_path / "elsewhere"

    project = manager.create_project(
        name="Absolute",
        root_path=str(absolute),
        create_directory=True,
    )

    assert project["root_path"] == str(absolute.resolve())


def test_coder_prefers_ai2apps_managed_agent_cli(coder):
    manager, _terminal = coder
    managed = manager.managed_cli_root / "node_modules" / ".bin" / "codex"
    managed.parent.mkdir(parents=True)
    managed.write_text("#!/bin/sh\n", encoding="utf-8")
    managed.chmod(0o755)

    with patch("ai2apps.coder.manager.shutil.which", return_value="/usr/local/bin/codex"):
        assert manager._agent_executable("codex") == str(managed)


def test_coder_disables_codex_alternate_screen(coder):
    manager, _terminal = coder

    with patch(
        "ai2apps.coder.manager.shutil.which", return_value="/usr/local/bin/codex"
    ):
        assert manager._default_agent_command("codex") == [
            "/usr/local/bin/codex",
            "--no-alt-screen",
        ]
        assert manager._default_agent_command("codex", "session-1") == [
            "/usr/local/bin/codex",
            "resume",
            "session-1",
            "--no-alt-screen",
        ]
    assert manager._ai2apps_command("codex", "local-model")[-1] == "--no-alt-screen"
    assert "--no-alt-screen" not in manager._ai2apps_command(
        "opencode", "local-model"
    )
    assert manager._ai2apps_command("codex", "local-model", "session-1")[-3:] == [
        "resume",
        "session-1",
        "--no-alt-screen",
    ]


def test_coder_discovers_codex_cli_sessions_by_project(coder, tmp_path):
    manager, _terminal = coder
    session_file = manager.codex_home / "sessions/2026/08/13/rollout.jsonl"
    session_file.parent.mkdir(parents=True)
    session_file.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {
                    "id": "native-session",
                    "cwd": str(tmp_path),
                    "source": "cli",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert manager._codex_sessions(str(tmp_path))[0][0] == "native-session"


def test_coder_recovers_stopped_legacy_thread_by_project_and_creation_time(
    coder, tmp_path
):
    manager, _terminal = coder
    project = manager.create_project(name="Example", root_path=str(tmp_path))
    thread = manager.create_thread(
        project_id=project["id"], title="Existing work", agent="codex"
    )
    session_file = manager.codex_home / "sessions/2026/08/13/rollout.jsonl"
    session_file.parent.mkdir(parents=True)
    session_file.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {
                    "id": "native-session",
                    "cwd": str(tmp_path),
                    "source": "cli",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    os.utime(session_file, None)
    with manager.database.transaction() as connection:
        row = connection.execute(
            "SELECT t.*, p.root_path FROM coder_threads t "
            "JOIN coder_projects p ON p.id=t.project_id WHERE t.id=?",
            (thread["id"],),
        ).fetchone()

    assert row["terminal_session_id"] is None
    assert manager._recover_legacy_codex_session(row) == "native-session"


def test_coder_persists_project_thread_and_structural_fork(coder, tmp_path):
    manager, _terminal = coder
    root = tmp_path / "project"
    project = manager.create_project(
        name="Example",
        root_path=str(root),
        kind="ai2apps",
        create_directory=True,
        bootstrap=True,
    )
    thread = manager.create_thread(
        project_id=project["id"],
        title="Build the App",
        agent="codex",
    )
    fork = manager.fork_thread(thread["id"])

    snapshot = manager.snapshot()
    assert snapshot["projects"] == [project]
    assert {item["id"] for item in snapshot["threads"]} == {
        thread["id"],
        fork["id"],
    }
    assert fork["parent_thread_id"] == thread["id"]
    assert (root / ".ai2apps" / "project.json").is_file()
    assert (root / "AGENTS.md").is_file()
    guide = (root / "docs" / "AI2APPS.md").read_text()
    assert "ai2apps.app/v1" in guide
    assert "ai2apps.agent/v1" in guide
    assert "ai2apps.service/v1" in guide
    assert "Mobile-ready App requirements" in guide
    assert "mobile.ready: true" in guide
    assert "/admin/static/*" in guide
    assert "/v1/mobile/*" in guide
    assert "IME composition" in guide


def test_coder_requires_model_for_ai2apps_model_source(coder, tmp_path):
    manager, _terminal = coder
    project = manager.create_project(name="Example", root_path=str(tmp_path))
    with pytest.raises(CoderError, match="Choose an AI2Apps model"):
        manager.create_thread(
            project_id=project["id"],
            title="Missing model",
            agent="opencode",
            model_source="ai2apps",
        )


def test_ai2apps_project_discovers_validates_previews_and_bundles_all_components(
    coder, tmp_path
):
    manager, _terminal = coder
    root = tmp_path / "multi-component"
    (root / ".ai2apps").mkdir(parents=True)
    (root / "app/ui").mkdir(parents=True)
    (root / "agent").mkdir()
    (root / "service").mkdir()
    (root / ".ai2apps/project.json").write_text(
        json.dumps(
            {
                "schema": "ai2apps.project/v1",
                "id": "example.workspace",
                "name": "Example Workspace",
                "version": "1.0.0-dev",
                "components": [
                    {"type": "app", "manifest": "app/app.yaml"},
                    {"type": "agent", "manifest": "agent/agent.yaml"},
                    {"type": "service", "manifest": "service/service.yaml"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "app/app.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "ai2apps.app/v1",
                "id": "example.game",
                "name": "Game",
                "version": "1.0.0",
                "publisher": {"id": "example.publisher"},
                "instances": {"mode": "singleton", "scope": "system"},
                "entry": {"kind": "sandbox", "resource": "ui/index.html"},
                "mini_entry": {
                    "kind": "schema",
                    "resource": "ui/mini.json",
                    "placements": ["sidebar"],
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "app/ui/index.html").write_text(
        '<!doctype html><link rel="stylesheet" href="style.css"><h1>DEV</h1>',
        encoding="utf-8",
    )
    (root / "app/ui/style.css").write_text("h1 { color: green; }", encoding="utf-8")
    (root / "app/ui/mini.json").write_text('{"type":"text"}', encoding="utf-8")
    (root / "agent/agent.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "ai2apps.agent/v1",
                "id": "example.helper",
                "name": "Helper",
                "version": "1.0.0",
                "publisher": {"id": "example.publisher"},
                "executor": {"key": "builtin:diagnostic-agent"},
            }
        ),
        encoding="utf-8",
    )
    (root / "service/service.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "ai2apps.service/v1",
                "id": "example.echo",
                "name": "Echo",
                "version": "1.0.0",
                "publisher": {"id": "example.publisher"},
                "runtime": {"mode": "external", "endpoint": "http://127.0.0.1:9999"},
                "capabilities": [],
                "requires": {"services": []},
                "permissions": {},
                "compatibility": {},
                "health": {},
                "restart": {},
                "tools": [],
            }
        ),
        encoding="utf-8",
    )

    project = manager.create_project(
        name="Multi", root_path=str(root), kind="ai2apps"
    )
    assert {item["kind"] for item in project["components"]} == {
        "app",
        "mini-app",
        "agent",
        "service",
    }
    report = manager.validate_project(project["id"])
    assert report["valid"] is True

    session = manager.start_dev_session(project["id"], "example.game")
    assert session["preview_url"].endswith("/preview")
    path, media = manager.resolve_dev_resource(session["id"], "ui/style.css")
    assert path == root / "app/ui/style.css"
    assert media == "text/css"
    with pytest.raises(CoderError, match="Unsafe development resource"):
        manager.resolve_dev_resource(session["id"], "../service/service.yaml")

    bundle = Path(manager.build_project(project["id"])["path"])
    with zipfile.ZipFile(bundle) as archive:
        package = json.loads(archive.read("META/package.json"))
        names = archive.namelist()
    assert package["development"] is True
    assert package["installable"] is False
    assert {item["type"] for item in package["components"]} == {
        "app",
        "mini-app",
        "agent",
        "service",
    }
    assert str(root) not in json.dumps(package)
    assert any(name.endswith("ui/index.html") for name in names)
    assert len(names) == len(set(names))

    flight = manager.submit_project_testflight(project["id"])
    assert flight["channel"] == "testflight"
    assert flight["apps"][0]["id"] == "testflight.example.game"
    assert flight["apps"][0]["entry_url"] == "/apps/testflight.example.game"
    assert manager.submit_project_testflight(project["id"])["apps"] == flight["apps"]
    with manager.database.transaction() as connection:
        definition = connection.execute(
            "SELECT source,manifest_json FROM app_definitions WHERE package_id=? "
            "AND status='enabled'",
            ("testflight.example.game",),
        ).fetchone()
    assert definition["source"] == "local"
    flight_manifest = json.loads(definition["manifest_json"])
    assert flight_manifest["navigation"]["category"] == "TestFlight"
    assert flight_manifest["testflight"]["signed"] is False


def test_coder_project_file_editor_is_bounded_and_cannot_escape(coder, tmp_path):
    manager, _terminal = coder
    root = tmp_path / "editable"
    (root / "config").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "config/settings.yaml").write_text("enabled: false\n", encoding="utf-8")
    project = manager.create_project(name="Editable", root_path=str(root))

    listing = manager.list_project_files(project["id"])
    assert [item["name"] for item in listing["items"]] == ["config"]
    assert manager.read_project_file(project["id"], "config/settings.yaml")[
        "content"
    ] == "enabled: false\n"

    saved = manager.write_project_file(
        project["id"], "config/settings.yaml", "enabled: true\n"
    )
    assert saved["content"] == "enabled: true\n"
    assert (root / "config/settings.yaml").read_text() == "enabled: true\n"
    with pytest.raises(CoderError, match="safe and relative"):
        manager.read_project_file(project["id"], "../outside.txt")
    with pytest.raises(CoderError, match="not editable"):
        manager.list_project_files(project["id"], ".git")


@pytest.mark.asyncio
async def test_coder_deletes_thread_and_removes_project_without_deleting_directory(
    coder, tmp_path
):
    manager, _terminal = coder
    root = tmp_path / "kept-source"
    root.mkdir()
    project = manager.create_project(name="Keep", root_path=str(root))
    thread = manager.create_thread(
        project_id=project["id"], title="Disposable", agent="codex"
    )

    assert (await manager.delete_thread(thread["id"]))["deleted"] is True
    assert manager.snapshot()["threads"] == []
    result = await manager.remove_project(project["id"])
    assert result == {
        "id": project["id"],
        "deleted": True,
        "directory_deleted": False,
    }
    assert root.is_dir()
    assert manager.snapshot()["projects"] == []


@pytest.mark.asyncio
async def test_coder_thread_owns_a_real_terminal_session(coder, tmp_path):
    manager, terminal = coder
    await terminal.startup()
    project = manager.create_project(name="Example", root_path=str(tmp_path))
    thread = manager.create_thread(
        project_id=project["id"], title="CLI", agent="opencode"
    )
    try:
        with patch("ai2apps.coder.manager.shutil.which", return_value="/bin/sh"):
            running = await manager.start_thread(thread["id"])
        assert running["status"] == "running"
        session = terminal.get(running["terminal_session_id"])
        assert session.cwd == str(tmp_path)
        assert session.owner == "coder"
        assert session.owner_id == thread["id"]
        assert terminal.list(owner="terminal") == []

        stopped = await manager.stop_thread(thread["id"])
        assert stopped["status"] == "stopped"
        assert stopped["terminal_session_id"] is None
    finally:
        await terminal.shutdown()
