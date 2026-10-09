import json

import httpx
import pytest
from fastapi import FastAPI
from test_ai2apps_agents import _runtime, _wait_status

from ai2apps.agents import AgentRunStatus
from ai2apps.api.coder import create_coder_router
from ai2apps.app_development.core import DraftError
from ai2apps.app_development.service import AGENT_KEY
from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.processes.sandbox import TestSandboxAdapter as ProcessTestSandbox

MINI = "schema: ai2apps.mini-app/v1\nid: test.native\nname: Native Mini\nversion: 1.0.0\nentry:\n  kind: safe-html\n  resource: index.html\n"


def project(runtime, tmp_path, empty=False):
    root = tmp_path / "source"
    root.mkdir()
    if not empty:
        (root / "mini-app.yaml").write_text(MINI)
        (root / "index.html").write_text("<h1>broken</h1>")
    return runtime.coder.create_project(
        name="Native fixture", root_path=str(root), kind="ai2apps", bootstrap=True
    ), root


def call(name, args, request, index):
    alias = next(
        tool["function"]["name"]
        for tool in request["tools"]
        if tool["function"]["name"].startswith(name.replace(".", "__") + "_")
    )
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call-" + str(index),
                            "type": "function",
                            "function": {"name": alias, "arguments": json.dumps(args)},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
    }


def finish():
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Draft repaired and tested; ready to review.",
                },
                "finish_reason": "stop",
            }
        ]
    }


@pytest.mark.asyncio
async def test_model_repairs_nonzero_test_validates_previews_and_review_applies(
    tmp_path,
):
    runtime = _runtime(tmp_path / "runtime")
    runtime.processes.sandbox = ProcessTestSandbox()
    selected, root = project(runtime, tmp_path)
    requests = []
    observed = None
    command = [
        "python3",
        "-c",
        "from pathlib import Path; print('checking'); assert 'fixed' in Path('index.html').read_text()",
    ]

    async def model(request):
        nonlocal observed
        requests.append(request)
        phase = len(requests)
        if phase == 1:
            return call("appdev.inspect", {}, request, phase)
        if phase == 2:
            return call("appdev.read", {"path": "index.html"}, request, phase)
        if phase == 3:
            observed = json.loads(request["messages"][-1]["content"])["sha256"]
            return call("appdev.command", {"argv": command}, request, phase)
        if phase == 4:
            result = json.loads(request["messages"][-1]["content"])
            assert result["exit_code"] != 0 and result["running"] is False
            return call(
                "appdev.edit",
                {
                    "path": "index.html",
                    "old": "broken",
                    "new": "fixed",
                    "expected_sha256": observed,
                },
                request,
                phase,
            )
        if phase == 5:
            return call("appdev.validate", {}, request, phase)
        if phase == 6:
            assert json.loads(request["messages"][-1]["content"])["valid"]
            return call("appdev.command", {"argv": command}, request, phase)
        if phase == 7:
            assert json.loads(request["messages"][-1]["content"])["exit_code"] == 0
            return call(
                "appdev.preview", {"component_id": "test.native"}, request, phase
            )
        if phase == 8:
            assert (
                "/preview/test.native"
                in json.loads(request["messages"][-1]["content"])["preview_url"]
            )
            return call("appdev.changes", {}, request, phase)
        return finish()

    runtime.agent_runtime.bind_model_provider(model)
    task = runtime.app_development.start(
        selected["id"],
        "Fix and test this Mini-App",
        "test",
        RequestPrincipal.legacy_local(),
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await _wait_status(
            runtime, task["run_id"], AgentRunStatus.COMPLETED, timeout=45
        )
        assert root.joinpath("index.html").read_text() == "<h1>broken</h1>"
        review = runtime.app_development.review(
            task["task_id"], RequestPrincipal.legacy_local()
        )
        assert review["validation"]["valid"] and len(review["changes"]) == 1
        result = runtime.app_development.apply(
            task["task_id"], review["revision"], RequestPrincipal.legacy_local()
        )
        assert result["ok"]
        assert root.joinpath("index.html").read_text() == "<h1>fixed</h1>"
    finally:
        await runtime.stop_background_tasks()
        runtime.stop()


@pytest.mark.asyncio
async def test_new_mini_app_can_be_generated_from_empty_project(tmp_path):
    runtime = _runtime(tmp_path / "runtime")
    selected, root = project(runtime, tmp_path, empty=True)
    requests = []

    async def model(request):
        requests.append(request)
        if len(requests) == 1:
            return call(
                "appdev.write", {"path": "mini-app.yaml", "content": MINI}, request, 1
            )
        if len(requests) == 2:
            return call(
                "appdev.write",
                {"path": "index.html", "content": "<h1>New App</h1>"},
                request,
                2,
            )
        if len(requests) == 3:
            return call("appdev.validate", {}, request, 3)
        assert json.loads(request["messages"][-1]["content"])["valid"]
        return finish()

    runtime.agent_runtime.bind_model_provider(model)
    task = runtime.app_development.start(
        selected["id"], "Create a Mini-App", "test", RequestPrincipal.legacy_local()
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await _wait_status(
            runtime, task["run_id"], AgentRunStatus.COMPLETED, timeout=30
        )
        review = runtime.app_development.review(
            task["task_id"], RequestPrincipal.legacy_local()
        )
        runtime.app_development.apply(
            task["task_id"], review["revision"], RequestPrincipal.legacy_local()
        )
        assert (root / "index.html").read_text() == "<h1>New App</h1>"
    finally:
        await runtime.stop_background_tasks()
        runtime.stop()


@pytest.mark.asyncio
async def test_owner_scoped_api_preview_and_conflict_guard(tmp_path):
    runtime = _runtime(tmp_path / "runtime")
    selected, root = project(runtime, tmp_path)
    app = FastAPI()
    app.include_router(
        create_coder_router(lambda: runtime, RequestPrincipal.legacy_local),
        prefix="/v1/platform",
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/v1/platform/coder/projects/" + selected["id"] + "/tasks",
            json={"prompt": "Fix", "model": "test"},
        )
        assert result.status_code == 201, result.text
        task = result.json()
        task_id = task["task_id"]
        draft = runtime.app_development.draft(task_id, RequestPrincipal.legacy_local())
        read = draft.read("index.html")
        draft.edit("index.html", "broken", "fixed", read["sha256"])
        runtime.agent_runtime.cancel(task["run_id"])
        review = (
            await client.get("/v1/platform/coder/tasks/" + task_id + "/changes")
        ).json()
        preview = await client.get(
            "/v1/platform/coder/tasks/" + task_id + "/preview/test.native",
            follow_redirects=True,
        )
        assert preview.status_code == 200 and "fixed" in preview.text
        assert "connect-src 'none'" in preview.headers["content-security-policy"]
        (root / "index.html").write_text("external modification")
        response = await client.post(
            "/v1/platform/coder/tasks/" + task_id + "/apply",
            json={"revision": review["revision"]},
        )
        assert response.status_code == 409
        assert (root / "index.html").read_text() == "external modification"
        other = RequestPrincipal("other", "local", "local", "local", MemberRole.CORE, 1)
        with pytest.raises(DraftError):
            runtime.app_development.status(task_id, other)
    runtime.stop()


@pytest.mark.asyncio
async def test_stale_edit_is_model_visible_without_terminating_task(tmp_path):
    runtime = _runtime(tmp_path / "runtime")
    selected, root = project(runtime, tmp_path)
    requests = []

    async def model(request):
        requests.append(request)
        if len(requests) == 1:
            return call(
                "appdev.write",
                {
                    "path": "index.html",
                    "content": "bad overwrite",
                    "expected_sha256": "0" * 64,
                },
                request,
                1,
            )
        result = json.loads(request["messages"][-1]["content"])
        assert result["error"]["code"] == "unobserved_or_changed"
        return finish()

    runtime.agent_runtime.bind_model_provider(model)
    task = runtime.app_development.start(
        selected["id"],
        "Do not overwrite stale files",
        "test",
        RequestPrincipal.legacy_local(),
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await _wait_status(
            runtime, task["run_id"], AgentRunStatus.COMPLETED, timeout=20
        )
        assert root.joinpath("index.html").read_text() == "<h1>broken</h1>"
    finally:
        await runtime.stop_background_tasks()
        runtime.stop()


def test_task_reload_preserves_observations_and_blocks_cross_project(tmp_path):
    runtime = _runtime(tmp_path / "runtime")
    selected, _ = project(runtime, tmp_path)
    task = runtime.app_development.start(
        selected["id"], "Edit later", "test", RequestPrincipal.legacy_local()
    )
    draft = runtime.app_development.draft(
        task["task_id"], RequestPrincipal.legacy_local()
    )
    read = draft.read("index.html")
    runtime.app_development.drafts.clear()
    fresh = runtime.app_development.draft(
        task["task_id"], RequestPrincipal.legacy_local()
    )
    fresh.edit("index.html", "broken", "fixed", read["sha256"])
    assert fresh.review()["changes"]
    assert (
        runtime.agents.get_definition(AGENT_KEY).executor_key == "builtin:coding-parent"
    )
    runtime.stop()


@pytest.mark.asyncio
async def test_followup_reuses_memory_after_restart_without_changing_original(tmp_path):
    runtime = _runtime(tmp_path / "runtime")
    selected, root = project(runtime, tmp_path)
    requests = []

    async def first(request):
        requests.append(request)
        if len(requests) == 1:
            return call(
                "appdev.write",
                {"path": "web/main.js", "content": "export const value = 1;"},
                request,
                1,
            )
        return finish()

    runtime.agent_runtime.bind_model_provider(first)
    task = runtime.app_development.start(
        selected["id"], "Add a script", "test", RequestPrincipal.legacy_local()
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await _wait_status(
            runtime, task["run_id"], AgentRunStatus.COMPLETED, timeout=20
        )
    finally:
        await runtime.stop_background_tasks()
        runtime.stop()

    restarted = _runtime(tmp_path / "runtime")
    seen = []

    async def followup(request):
        seen.append(request)
        assert "Add a script" in json.dumps(request["messages"])
        assert "web/main.js" in json.dumps(request["messages"])
        return finish()

    restarted.agent_runtime.bind_model_provider(followup)
    continued = restarted.app_development.start(
        selected["id"],
        "Check the draft",
        "test",
        RequestPrincipal.legacy_local(),
        task_id=task["task_id"],
    )
    await restarted.start_background_tasks(retention_interval_seconds=60)
    try:
        await _wait_status(
            restarted, continued["run_id"], AgentRunStatus.COMPLETED, timeout=20
        )
        assert seen and not (root / "web/main.js").exists()
    finally:
        await restarted.stop_background_tasks()
        restarted.stop()


def test_complete_app_manifest_and_missing_preview_resource(tmp_path):
    import yaml

    runtime = _runtime(tmp_path / "runtime")
    selected, root = project(runtime, tmp_path, empty=True)
    task = runtime.app_development.start(
        selected["id"], "Build an App", "test", RequestPrincipal.legacy_local()
    )
    draft = runtime.app_development.draft(
        task["task_id"], RequestPrincipal.legacy_local()
    )
    manifest = {
        "schema": "ai2apps.app/v1",
        "id": "test.app",
        "name": "Native App",
        "version": "1.0.0",
        "publisher": {"id": "test.publisher"},
        "instances": {"mode": "singleton", "scope": "system"},
        "entry": {"kind": "sandbox", "resource": "ui/index.html"},
    }
    draft.write("app.yaml", yaml.safe_dump(manifest))
    draft.write("ui/index.html", '<link rel="stylesheet" href="style.css"><h1>App</h1>')
    draft.write("ui/style.css", "h1 { color: green; }")
    runtime.agent_runtime.cancel(task["run_id"])
    review = runtime.app_development.review(
        task["task_id"], RequestPrincipal.legacy_local()
    )
    assert review["validation"]["valid"]
    assert runtime.app_development.resource(
        task["task_id"], "test.app", "ui/style.css", RequestPrincipal.legacy_local()
    ).is_file()
    runtime.app_development.apply(
        task["task_id"], review["revision"], RequestPrincipal.legacy_local()
    )
    assert (root / "app.yaml").exists()
    runtime.stop()


@pytest.mark.asyncio
async def test_long_command_returns_id_and_continues_same_process(tmp_path):
    runtime = _runtime(tmp_path / "runtime")
    runtime.processes.sandbox = ProcessTestSandbox()
    await runtime.processes.startup()
    selected, _ = project(runtime, tmp_path)
    task = runtime.app_development.start(
        selected["id"], "Command", "test", RequestPrincipal.legacy_local()
    )
    context = runtime.tools.context_for_session(
        caller_id="agent:" + AGENT_KEY,
        session_id=task["task_id"],
        trace_id=task["run_id"],
    )
    first = await runtime.app_development.command(
        task["task_id"],
        [
            "python3",
            "-c",
            "import time; print('start', flush=True); time.sleep(1.5); print('finish')",
        ],
        ".",
        context,
    )
    assert first["running"] and first["process_id"]
    second = await runtime.app_development.command_status(
        task["task_id"], first["process_id"], 0, 5000, context
    )
    assert second["process_id"] == first["process_id"] and second["exit_code"] == 0
    assert "finish" in "".join(log["content"] for log in second["logs"])
    await runtime.processes.shutdown()
    runtime.stop()
