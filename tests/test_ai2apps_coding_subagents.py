import asyncio
import json
from pathlib import Path

import pytest
from test_ai2apps_agents import _runtime, _wait_status
from test_ai2apps_app_development import call, finish, project

from ai2apps.agents.models import AgentRunStatus, DeferredToolAction, RunStepStatus
from ai2apps.app_development.subagents.contracts import Request, SubagentError
from ai2apps.app_development.subagents.policy import tools_for, validate_request
from ai2apps.app_development.subagents.snapshots import merge_patch
from ai2apps.identity import RequestPrincipal
from ai2apps.processes.sandbox import TestSandboxAdapter as Sandbox

PRINCIPAL = RequestPrincipal.legacy_local()


def task(tmp_path):
    r = _runtime(tmp_path / "runtime")
    p, root = project(r, tmp_path)
    t = r.app_development.start(p["id"], "Develop and check", "test", PRINCIPAL)
    return r, t, root


def active(r, t):
    r.agents.transition(
        t["run_id"], expected={AgentRunStatus.QUEUED}, status=AgentRunStatus.PLANNING
    )
    return r.agents.transition(
        t["run_id"], expected={AgentRunStatus.PLANNING}, status=AgentRunStatus.RUNNING
    )


def test_role_policy_and_recursion():
    validate_request(Request("tester", "test", "k"))
    for request, kwargs in [
        (Request("general", "x", "k"), {}),
        (Request("worker", "x", "k"), {"depth": 1}),
        (Request("analyst", "x", "k"), {"child_count": 4}),
    ]:
        with pytest.raises(SubagentError):
            validate_request(request, **kwargs)
    assert "appdev.child.write" not in tools_for("reviewer")
    assert "appdev.child.command" not in tools_for("analyst")
    assert "appdev.child.write" in tools_for("worker")


def test_snapshots_and_worker_merge_are_isolated(tmp_path):
    r, t, root = task(tmp_path)
    active(r, t)
    c = r.app_development.cooperation
    try:
        child = c.start(
            t["run_id"],
            {"role": "worker", "task": "fix", "request_key": "w"},
            PRINCIPAL,
        )
        d = c.draft(child["child_run_id"])
        read = d.read("index.html")
        d.edit("index.html", "broken", "fixed", read["sha256"])
        parent = r.app_development.draft(t["task_id"], PRINCIPAL)
        assert parent.workspace.joinpath("index.html").read_text() == "<h1>broken</h1>"
        binding = c.binding(child["child_run_id"])
        merged = merge_patch(
            parent, Path(binding["baseline"]), d.workspace, parent.review()["revision"]
        )
        assert merged["merged"] == ["index.html"]
        assert "fixed" in parent.workspace.joinpath("index.html").read_text()
        assert "broken" in root.joinpath("index.html").read_text()
        assert c.result(t["run_id"], child["child_run_id"], PRINCIPAL)["stale"]
    finally:
        r.stop()


def test_idempotency_ownership_limits_and_conflicts(tmp_path):
    r, t, root = task(tmp_path)
    active(r, t)
    c = r.app_development.cooperation
    try:
        args = {"role": "analyst", "task": "inspect", "request_key": "a"}
        a = c.start(t["run_id"], args, PRINCIPAL)
        assert (
            c.start(t["run_id"], args, PRINCIPAL)["child_run_id"] == a["child_run_id"]
        )
        with pytest.raises(SubagentError):
            c.start(t["run_id"], {**args, "task": "different"}, PRINCIPAL)
        with pytest.raises(SubagentError):
            c.owned(t["run_id"], "missing")
        for n in range(3):
            c.start(t["run_id"], {**args, "request_key": str(n)}, PRINCIPAL)
        with pytest.raises(SubagentError):
            c.start(t["run_id"], {**args, "request_key": "fifth"}, PRINCIPAL)
        with pytest.raises(SubagentError):
            c.followup(
                t["run_id"],
                {
                    "child_run_id": a["child_run_id"],
                    "message": "again",
                    "request_key": "again",
                },
                PRINCIPAL,
            )
    finally:
        r.stop()


@pytest.mark.asyncio
async def test_single_slot_parent_wait_child_runs_and_pairs_result(tmp_path):
    r, t, root = task(tmp_path)
    r.agent_runtime.global_concurrency = 1
    phases = {"parent": 0, "analyst": 0}
    child_id = None

    async def model(request):
        nonlocal child_id
        is_child = "bounded AI2Apps coding analyst" in request["messages"][0]["content"]
        key = "analyst" if is_child else "parent"
        phases[key] += 1
        if is_child:
            assert not any("Develop and check" in str(m) for m in request["messages"])
            assert not any(
                "subagent_start" in q["function"]["name"] for q in request["tools"]
            )
            return finish()
        if phases[key] == 1:
            return call(
                "appdev.subagent_start",
                {"role": "analyst", "task": "Inspect contracts", "request_key": "a"},
                request,
                1,
            )
        if phases[key] == 2:
            child_id = json.loads(request["messages"][-1]["content"])["child_run_id"]
            return call(
                "appdev.subagent_wait",
                {"child_run_ids": [child_id], "mode": "all", "timeout_seconds": 10},
                request,
                2,
            )
        assert json.loads(request["messages"][-1]["content"])["ready"]
        return finish()

    r.agent_runtime.bind_model_provider(model)
    await r.start_background_tasks(retention_interval_seconds=60)
    try:
        await _wait_status(r, t["run_id"], AgentRunStatus.COMPLETED, timeout=20)
        assert r.agents.get_run(child_id).status is AgentRunStatus.COMPLETED
        steps = [
            s
            for s in r.agents.list_steps(t["run_id"])
            if s.tool_name == "appdev.subagent_wait"
        ]
        assert len(steps) == 1 and steps[0].status is RunStepStatus.COMPLETED
        assert not r.app_development.cooperation.waiting(t["run_id"])
        assert (
            r.app_development.status(t["task_id"], PRINCIPAL)["run_id"] == t["run_id"]
        )
    finally:
        await r.stop_background_tasks()
        r.stop()


@pytest.mark.asyncio
async def test_child_command_workspace_host_evidence(tmp_path):
    r, t, root = task(tmp_path)
    r.processes.sandbox = Sandbox()
    active(r, t)
    c = r.app_development.cooperation
    child = c.start(
        t["run_id"],
        {"role": "tester", "task": "test", "request_key": "test"},
        PRINCIPAL,
    )
    command = [
        "python3",
        "-c",
        "from pathlib import Path; Path('index.html').write_text('child changed'); print('check')",
    ]
    phase = 0

    async def model(request):
        nonlocal phase
        phase += 1
        if phase == 1:
            return call("appdev.child.command", {"argv": command}, request, 1)
        return finish()

    r.agent_runtime.bind_model_provider(model)
    r.agents.transition(
        t["run_id"],
        expected={AgentRunStatus.RUNNING},
        status=AgentRunStatus.INTERRUPTED,
    )
    await r.start_background_tasks(retention_interval_seconds=60)
    try:
        await _wait_status(
            r, child["child_run_id"], AgentRunStatus.COMPLETED, timeout=20
        )
        parent = r.app_development.draft(t["task_id"], PRINCIPAL)
        assert "broken" in parent.workspace.joinpath("index.html").read_text()
        report = c.result(t["run_id"], child["child_run_id"], PRINCIPAL)
        assert report["checks"][0]["exit_code"] == 0
        assert report["checks"][0]["process_id"]
        assert "broken" in root.joinpath("index.html").read_text()
    finally:
        await r.stop_background_tasks()
        r.stop()


def test_budget_reservation_is_root_shared_and_missing_usage_conservative(tmp_path):
    r, t, root = task(tmp_path)
    parent = active(r, t)
    c = r.app_development.cooperation
    try:
        child = c.start(
            t["run_id"],
            {"role": "tester", "task": "test", "request_key": "test"},
            PRINCIPAL,
        )
        run = r.agents.get_run(child["child_run_id"])
        s, _ = r.agents.create_step(parent.id, action_key="p", kind="model", input={})
        request = {"messages": []}
        c.reserve_model(parent, s.id, request)
        used = c.used(parent.id)
        c.reserve_model(parent, s.id, request)
        assert c.used(parent.id) == used
        c.settle_model(s.id, {})
        assert c.used(parent.id) == used
        s2, _ = r.agents.create_step(run.id, action_key="c", kind="model", input={})
        c.reserve_model(run, s2.id, {"messages": []})
        assert c.used(parent.id) > used
        c.settle_model(s2.id, {"usage": {"total_tokens": 12}})
        assert c.used(parent.id) == used + 12
    finally:
        r.stop()


@pytest.mark.asyncio
async def test_wait_survives_runtime_restart_without_duplicate_start(tmp_path):
    r, t, root = task(tmp_path)
    blocked = asyncio.Event()
    phases = 0

    async def model(request):
        nonlocal phases
        if "bounded AI2Apps coding" in request["messages"][0]["content"]:
            await blocked.wait()
            return finish()
        phases += 1
        if phases == 1:
            return call(
                "appdev.subagent_start",
                {"role": "analyst", "task": "Inspect", "request_key": "one"},
                request,
                1,
            )
        child = json.loads(request["messages"][-1]["content"])["child_run_id"]
        return call(
            "appdev.subagent_wait",
            {"child_run_ids": [child], "timeout_seconds": 60},
            request,
            2,
        )

    r.agent_runtime.bind_model_provider(model)
    await r.start_background_tasks(retention_interval_seconds=60)
    for _ in range(200):
        if r.app_development.cooperation.waiting(t["run_id"]):
            break
        await asyncio.sleep(0.02)
    assert r.app_development.cooperation.waiting(t["run_id"])
    await r.stop_background_tasks()
    r.stop()
    restarted = _runtime(tmp_path / "runtime")
    restarted.agent_runtime.bind_model_provider(lambda request: finish())
    await restarted.start_background_tasks(retention_interval_seconds=60)
    try:
        await _wait_status(restarted, t["run_id"], AgentRunStatus.COMPLETED, timeout=20)
        assert len(restarted.agents.list_children(t["run_id"])) == 1
        waits = [
            s
            for s in restarted.agents.list_steps(t["run_id"])
            if s.tool_name == "appdev.subagent_wait"
        ]
        assert len(waits) == 1 and waits[0].status is RunStepStatus.COMPLETED
    finally:
        await restarted.stop_background_tasks()
        restarted.stop()


@pytest.mark.asyncio
async def test_wait_cancel_timeout_and_parent_failure_cleanup(tmp_path):
    from ai2apps.agents.models import AgentExecutionContext

    r, t, root = task(tmp_path)
    parent = active(r, t)
    c = r.app_development.cooperation
    try:
        child = c.start(
            parent.id,
            {"role": "analyst", "task": "inspect", "request_key": "x"},
            PRINCIPAL,
        )
        definition, run, _, steps, interactions = r.agents.snapshot(parent.id)
        context = AgentExecutionContext(definition, run, steps, interactions)
        c.register_wait(
            context,
            DeferredToolAction(
                "wait",
                "appdev.subagent_wait",
                {"child_run_ids": [child["child_run_id"]], "timeout_seconds": 1},
            ),
        )
        assert r.agents.claim_next().id == child["child_run_id"]
        with r.database.transaction(write=True) as con:
            con.execute(
                "UPDATE agent_deferred_waits SET deadline_at='2000-01-01T00:00:00.000000Z'"
            )
        await c.maintain()
        assert not c.waiting(parent.id)
        assert r.agents.list_steps(parent.id)[-1].output["timed_out"]
        r.agent_runtime.cancel(parent.id)
        await c.maintain()
        assert (
            r.agents.get_run(child["child_run_id"]).status is AgentRunStatus.CANCELLED
        )
    finally:
        r.stop()


def test_worker_conflict_is_preflighted_before_merge(tmp_path):
    r, t, root = task(tmp_path)
    active(r, t)
    c = r.app_development.cooperation
    try:
        child = c.start(
            t["run_id"],
            {"role": "worker", "task": "fix", "request_key": "w"},
            PRINCIPAL,
        )
        worker = c.draft(child["child_run_id"])
        a = worker.read("index.html")
        worker.write("index.html", "worker", a["sha256"])
        parent = r.app_development.draft(t["task_id"], PRINCIPAL)
        a = parent.read("index.html")
        parent.write("index.html", "parent", a["sha256"])
        b = c.binding(child["child_run_id"])
        with pytest.raises(SubagentError):
            merge_patch(
                parent,
                Path(b["baseline"]),
                worker.workspace,
                parent.review()["revision"],
            )
        assert parent.workspace.joinpath("index.html").read_text() == "parent"
        assert root.joinpath("index.html").read_text() == "<h1>broken</h1>"
    finally:
        r.stop()


@pytest.mark.asyncio
async def test_child_role_handler_rejects_write_and_foreign_process(tmp_path):
    from ai2apps.services import ToolGatewayError

    r, t, root = task(tmp_path)
    active(r, t)
    c = r.app_development.cooperation
    try:
        child = c.start(
            t["run_id"],
            {"role": "analyst", "task": "inspect", "request_key": "a"},
            PRINCIPAL,
        )
        context = r.tools.context_for_session(
            caller_id="test",
            session_id=t["task_id"],
            trace_id=child["child_run_id"],
            granted_capabilities=frozenset({"appdev.draft.write"}),
        )
        with pytest.raises(ToolGatewayError):
            await r.tools.execute(
                "appdev.child.write",
                {"path": "new.js", "content": "bad"},
                context=context,
            )
        assert not c.draft(child["child_run_id"]).workspace.joinpath("new.js").exists()
        with pytest.raises(SubagentError):
            c.process_workspace("other", child["child_run_id"])
    finally:
        r.stop()


@pytest.mark.asyncio
async def test_actual_child_sandbox_cannot_read_parent_baseline_or_network(tmp_path):
    import platform
    import sys

    if platform.system() != "Darwin":
        pytest.skip("Real Seatbelt test requires macOS")
    r, t, root = task(tmp_path)
    active(r, t)
    c = r.app_development.cooperation
    child = c.start(
        t["run_id"],
        {"role": "tester", "task": "boundary", "request_key": "boundary"},
        PRINCIPAL,
    )
    b = c.binding(child["child_run_id"])
    parent = r.app_development.draft(t["task_id"], PRINCIPAL)
    script = """from pathlib import Path
import socket
assert Path('index.html').exists()
for path in PATHS:
    try: Path(path).read_text()
    except PermissionError: pass
    else: raise AssertionError('Read foreign source: '+path)
s=socket.socket()
try: s.connect(('127.0.0.1',9))
except PermissionError: pass
else: raise AssertionError('Network allowed')
print('isolated child accepted')
""".replace(
        "PATHS",
        repr(
            [
                str(root / "index.html"),
                str(parent.workspace / "index.html"),
                str(Path(b["baseline"]) / "index.html"),
            ]
        ),
    )
    await r.processes.startup()
    try:
        record = await r.processes.start(
            session_id=t["task_id"],
            run_id=child["child_run_id"],
            caller_id="acceptance",
            argv=[sys.executable, "-I", "-c", script],
        )
        record = await r.processes.wait(
            record.id,
            session_id=t["task_id"],
            run_id=child["child_run_id"],
            timeout_ms=10000,
        )
        assert record.exit_code == 0, r.processes.logs(
            record.id, session_id=t["task_id"], run_id=child["child_run_id"]
        )
    finally:
        await r.processes.shutdown()
        r.stop()


@pytest.mark.asyncio
async def test_worker_patch_then_parallel_tester_and_reviewer_end_to_end(tmp_path):
    r, t, root = task(tmp_path)
    r.processes.sandbox = Sandbox()
    r.agent_runtime.global_concurrency = 1
    counts = {}
    worker = None
    tester = None
    reviewer = None
    observed = None
    revision = None

    async def model(request):
        nonlocal worker, tester, reviewer, observed, revision
        system = request["messages"][0]["content"]
        role = next(
            (
                role
                for role in ["worker", "tester", "reviewer"]
                if "coding " + role + "." in system
            ),
            "parent",
        )
        counts[role] = counts.get(role, 0) + 1
        n = counts[role]
        last = (
            json.loads(request["messages"][-1]["content"])
            if request["messages"][-1]["role"] == "tool"
            else {}
        )
        if role == "worker":
            if n == 1:
                response = call("appdev.child.read", {"path": "index.html"}, request, n)
            elif n == 2:
                observed = last["sha256"]
                response = call(
                    "appdev.child.edit",
                    {
                        "path": "index.html",
                        "old": "broken",
                        "new": "fixed",
                        "expected_sha256": observed,
                    },
                    request,
                    n,
                )
            elif n == 3:
                response = call("appdev.child.validate", {}, request, n)
            else:
                response = finish()
        elif role == "tester":
            if n == 1:
                response = call(
                    "appdev.child.command",
                    {
                        "argv": [
                            "python3",
                            "-c",
                            "from pathlib import Path; assert 'fixed' in Path('index.html').read_text(); print('pass')",
                        ]
                    },
                    request,
                    n,
                )
            else:
                response = finish()
        elif role == "reviewer":
            if n == 1:
                response = call("appdev.child.read", {"path": "index.html"}, request, n)
            else:
                response = finish()
        elif n == 1:
            response = call(
                "appdev.subagent_start",
                {"role": "worker", "task": "Fix index.html", "request_key": "worker"},
                request,
                n,
            )
        elif n == 2:
            worker = last["child_run_id"]
            response = call(
                "appdev.subagent_wait", {"child_run_ids": [worker]}, request, n
            )
        elif n == 3:
            response = call("appdev.changes", {}, request, n)
        elif n == 4:
            revision = last["revision"]
            response = call(
                "appdev.subagent_merge",
                {"child_run_id": worker, "revision": revision},
                request,
                n,
            )
        elif n == 5:
            response = call(
                "appdev.subagent_start",
                {
                    "role": "tester",
                    "task": "Test corrected HTML",
                    "request_key": "tester",
                },
                request,
                n,
            )
        elif n == 6:
            tester = last["child_run_id"]
            response = call(
                "appdev.subagent_start",
                {
                    "role": "reviewer",
                    "task": "Review corrected HTML",
                    "request_key": "reviewer",
                },
                request,
                n,
            )
        elif n == 7:
            reviewer = last["child_run_id"]
            response = call(
                "appdev.subagent_wait",
                {"child_run_ids": [tester, reviewer]},
                request,
                n,
            )
        elif n == 8:
            response = call(
                "appdev.subagent_status",
                {"child_run_ids": [tester, reviewer]},
                request,
                n,
            )
        else:
            assert all(
                not child["stale"] and child["status"] == "completed"
                for child in last["children"]
            )
            assert last["children"][0]["checks"][0]["exit_code"] == 0
            response = finish()
        response["usage"] = {"total_tokens": 100}
        return response

    r.agent_runtime.bind_model_provider(model)
    await r.start_background_tasks(retention_interval_seconds=60)
    try:
        await _wait_status(r, t["run_id"], AgentRunStatus.COMPLETED, timeout=90)
        assert len(r.agents.list_children(t["run_id"])) == 3
        assert "broken" in root.joinpath("index.html").read_text()
        report = r.app_development.review(t["task_id"], PRINCIPAL)
        assert "fixed" in report["changes"][0]["diff"]
        r.app_development.apply(t["task_id"], report["revision"], PRINCIPAL)
        assert "fixed" in root.joinpath("index.html").read_text()
    finally:
        await r.stop_background_tasks()
        r.stop()


def test_legacy_coding_definition_upgrade_preserves_tasks(tmp_path):
    import sqlite3

    from ai2apps.storage.migrations import MIGRATIONS, apply_migrations

    r, t, root = task(tmp_path)
    database = r.database.path
    r.stop()
    with sqlite3.connect(database) as con:
        con.execute(
            "UPDATE agent_definitions SET executor_key='builtin:general-agent' WHERE agent_key='ai2apps.app-developer'"
        )
        # Replay the data repair on legacy rows without corrupting the ledger
        # of later schema migrations already used by this runtime fixture.
        for statement in next(m for m in MIGRATIONS if m.version == 79).statements:
            con.execute(statement)
        con.commit()
        assert apply_migrations(con) == len(MIGRATIONS)
        assert (
            con.execute(
                "SELECT executor_key FROM agent_definitions WHERE agent_key='ai2apps.app-developer'"
            ).fetchone()[0]
            == "builtin:coding-parent"
        )
        assert (
            con.execute(
                "SELECT COUNT(*) FROM agent_runs WHERE id=?", (t["run_id"],)
            ).fetchone()[0]
            == 1
        )
    restarted = _runtime(tmp_path / "runtime")
    assert (
        restarted.app_development.status(t["task_id"], PRINCIPAL)["run_id"]
        == t["run_id"]
    )
    restarted.stop()


@pytest.mark.asyncio
async def test_worker_cannot_exceed_parent_capability_denial(tmp_path):
    from ai2apps.capabilities import PolicyEffect
    from ai2apps.services import ToolGatewayError

    r, t, _ = task(tmp_path)
    active(r, t)
    c = r.app_development.cooperation
    try:
        child = c.start(
            t["run_id"],
            {"role": "worker", "task": "edit", "request_key": "denied"},
            PRINCIPAL,
        )
        r.capabilities.upsert_policy(
            policy_key="acceptance:parent-denied",
            effect=PolicyEffect.DENY,
            capability_pattern="appdev.draft.write",
            agent_pattern="ai2apps.app-developer",
            tool_pattern="appdev.write",
            priority=999,
            source="local",
        )
        context = r.tools.context_for_session(
            caller_id="test",
            session_id=t["task_id"],
            trace_id=child["child_run_id"],
            granted_capabilities=frozenset({"appdev.draft.write"}),
        )
        with pytest.raises(ToolGatewayError):
            await r.tools.execute(
                "appdev.child.write",
                {"path": "new.js", "content": "blocked"},
                context=context,
            )
        assert not c.draft(child["child_run_id"]).workspace.joinpath("new.js").exists()
    finally:
        r.stop()


@pytest.mark.asyncio
async def test_local_budget_error_is_not_a_provider_failure(tmp_path):
    r, t, _ = task(tmp_path)
    requests = []
    r.agent_runtime.bind_model_provider(
        lambda request: requests.append(request) or finish()
    )

    def reject(*args):
        raise SubagentError("root_budget_exhausted", "No remaining model budget")

    r.app_development.cooperation.reserve_model = reject
    await r.start_background_tasks(retention_interval_seconds=60)
    try:
        await _wait_status(r, t["run_id"], AgentRunStatus.FAILED, timeout=15)
        run = r.agents.get_run(t["run_id"])
        assert run.error["code"] == "root_budget_exhausted"
        assert not run.error["retryable"]
        assert not requests
    finally:
        await r.stop_background_tasks()
        r.stop()


@pytest.mark.asyncio
async def test_two_children_capacity_and_any_wait_wakes_once(tmp_path):
    from ai2apps.agents.models import AgentExecutionContext

    r, t, _ = task(tmp_path)
    parent = active(r, t)
    c = r.app_development.cooperation
    try:
        children = [
            c.start(
                parent.id,
                {"role": "analyst", "task": "inspect", "request_key": str(i)},
                PRINCIPAL,
            )["child_run_id"]
            for i in range(3)
        ]
        first = r.agents.claim_next()
        second = r.agents.claim_next()
        assert first.id != second.id
        assert r.agents.claim_next() is None
        r.agent_runtime.cancel(first.id)
        assert r.agents.claim_next().id in children
        definition, run, _, steps, interactions = r.agents.snapshot(parent.id)
        c.register_wait(
            AgentExecutionContext(definition, run, steps, interactions),
            DeferredToolAction(
                "any",
                "appdev.subagent_wait",
                {"child_run_ids": [first.id, second.id], "mode": "any"},
            ),
        )
        await c.maintain()
        await c.maintain()
        assert not c.waiting(parent.id)
        waits = [
            s
            for s in r.agents.list_steps(parent.id)
            if s.tool_name == "appdev.subagent_wait"
        ]
        assert len(waits) == 1 and waits[0].output["ready"]
        assert r.agents.claim_next().id == parent.id
    finally:
        r.stop()


def test_latest_task_survives_restart_and_is_owner_scoped(tmp_path):
    from ai2apps.identity import MemberRole

    r, t, _ = task(tmp_path)
    project_id = t["project_id"]
    assert (
        r.app_development.latest_task(project_id, PRINCIPAL)["task_id"] == t["task_id"]
    )
    r.stop()
    r = _runtime(tmp_path / "runtime")
    try:
        assert (
            r.app_development.latest_task(project_id, PRINCIPAL)["task_id"]
            == t["task_id"]
        )
        other = RequestPrincipal("other", "local", "local", "local", MemberRole.CORE, 1)
        assert r.app_development.latest_task(project_id, other)["task_id"] is None
    finally:
        r.stop()


@pytest.mark.asyncio
async def test_child_api_rejects_foreign_ids_and_missing_process(tmp_path):
    import httpx
    from fastapi import FastAPI

    from ai2apps.api.coder import create_coder_router

    r, t, _ = task(tmp_path)
    active(r, t)
    c = r.app_development.cooperation
    child = c.start(
        t["run_id"], {"role": "tester", "task": "test", "request_key": "api"}, PRINCIPAL
    )["child_run_id"]
    app = FastAPI()
    app.include_router(
        create_coder_router(lambda: r, RequestPrincipal.legacy_local),
        prefix="/v1/platform",
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            base = "/v1/platform/coder/tasks/" + t["task_id"] + "/children/"
            denied = await client.post(base + "foreign/cancel")
            assert denied.status_code == 409
            missing = await client.get(base + child + "/logs/unknown")
            assert missing.status_code == 404
            cancelled = await client.post(base + child + "/cancel")
            assert (
                cancelled.status_code == 200
                and cancelled.json()["status"] == "cancelled"
            )
            latest = await client.get(
                "/v1/platform/coder/projects/" + t["project_id"] + "/tasks/latest"
            )
            assert latest.json()["task_id"] == t["task_id"]
    finally:
        r.stop()


@pytest.mark.asyncio
async def test_early_compaction_is_soft_and_does_not_drop_pinned_instructions(tmp_path):
    from dataclasses import replace

    from ai2apps.agents.models import AgentExecutionContext, ModelCallAction
    from ai2apps.app_development.subagents.adapter import CodingExecutor

    r, t, _ = task(tmp_path)
    try:
        definition, run, _, steps, interactions = r.agents.snapshot(t["run_id"])
        marker = "pinned-platform-contract-" * 2500
        manifest = dict(definition.manifest)
        manifest["instructions"] += marker
        context = AgentExecutionContext(
            replace(definition, manifest=manifest), run, steps, interactions
        )
        action = await CodingExecutor(r, r.app_development.cooperation)(context)
        assert isinstance(action, ModelCallAction)
        assert marker in action.request["messages"][0]["content"]
        assert len(json.dumps(action.request).encode()) > 32768
        assert action.context_audit["max_bytes"] == 524288
    finally:
        r.stop()


@pytest.mark.asyncio
async def test_native_preview_embeds_assets_without_login_or_same_origin_grants(
    tmp_path,
):
    import httpx
    from fastapi import FastAPI

    from ai2apps.api.coder import create_coder_router

    r, t, _ = task(tmp_path)
    try:
        draft = r.app_development.draft(t["task_id"], PRINCIPAL)
        observed = draft.read("index.html")
        draft.write(
            "index.html",
            '<h1>Preview</h1><script src="main.js"></script><link rel="stylesheet" href="main.css">',
            observed["sha256"],
        )
        draft.write("main.js", 'document.querySelector("h1").textContent="working";')
        draft.write("main.css", "h1{color:green;}")
        app = FastAPI()
        app.include_router(
            create_coder_router(lambda: r, RequestPrincipal.legacy_local),
            prefix="/v1/platform",
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            result = await client.get(
                "/v1/platform/coder/tasks/" + t["task_id"] + "/preview/test.native",
                follow_redirects=True,
            )
            assert result.status_code == 200
            assert (
                'textContent="working"' in result.text
                and "<style>h1{color:green;}</style>" in result.text
            )
            assert 'src="main.js"' not in result.text
            csp = result.headers["content-security-policy"]
            assert "connect-src 'none'" in csp and "form-action 'none'" in csp
            assert "allow-same-origin" not in csp and "unsafe-eval" not in csp
            assert (
                draft.workspace.joinpath("index.html")
                .read_text()
                .count('src="main.js"')
                == 1
            )
    finally:
        r.stop()
