# SPDX-License-Identifier: Apache-2.0
"""M7 sandboxed Process Service, ownership, limits, and broker contracts."""

from __future__ import annotations

import asyncio
import os
import platform

import pytest

from ai2apps.chat import ChatRepository
from ai2apps.config import PlatformConfig
from ai2apps.core import ResourceNotFoundError
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.processes import (
    BrokerAuthority,
    LinuxBubblewrapAdapter,
    MacOSSandboxAdapter,
    ProcessManager,
    ProcessServiceError,
    ProcessStatus,
)
from ai2apps.processes import (
    TestSandboxAdapter as ProcessTestSandboxAdapter,
)
from ai2apps.services import ToolCallContext, ToolGatewayError


def _runtime(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / "data"))
    runtime.start()
    assert runtime.workspace is not None
    assert runtime.processes is not None
    return runtime


def _session(runtime, title="Process"):
    return (
        ChatRepository(runtime.database, runtime.events)
        .create_thread(title=title)[0]
        .session.id
    )


async def _manager(runtime, *, session_limit=4):
    manager = ProcessManager(
        runtime.database,
        runtime.events,
        runtime.workspace,
        sandbox=ProcessTestSandboxAdapter(),
        session_limit=session_limit,
    )
    await manager.startup()
    return manager


async def _terminal(manager, process_id, session_id, run_id=None, timeout=3):
    async def wait():
        while True:
            record = manager.status(process_id, session_id=session_id, run_id=run_id)
            if record.status.terminal:
                return record
            await asyncio.sleep(0.01)

    return await asyncio.wait_for(wait(), timeout)


@pytest.mark.asyncio
async def test_process_argv_output_status_and_broker_audit(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    manager = await _manager(runtime)
    try:
        started = await manager.start(
            session_id=session,
            run_id=None,
            caller_id="test",
            argv=["/bin/echo", "hello process"],
        )
        finished = await manager.wait(
            started.id, session_id=session, run_id=None, timeout_ms=3_000
        )
        logs = manager.logs(started.id, session_id=session, run_id=None)

        assert finished.status is ProcessStatus.EXITED
        assert finished.exit_code == 0
        assert "".join(item.content for item in logs) == "hello process\n"
        with runtime.database.connect() as connection:
            broker = connection.execute(
                "SELECT operation, status, token_digest FROM host_broker_requests"
            ).fetchone()
        assert broker[0:2] == ("process.spawn", "accepted")
        assert broker[2].startswith("sha256:")
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_process_stdin_and_environment_are_bounded(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    manager = await _manager(runtime)
    monkeypatch.setenv("AI2APPS_HOST_SECRET", "must-not-leak")
    try:
        started = await manager.start(
            session_id=session, run_id=None, caller_id="test", argv=["/bin/cat"]
        )
        await manager.write_stdin(
            started.id, "ping\n", session_id=session, run_id=None, close=True
        )
        finished = await _terminal(manager, started.id, session)
        assert finished.status is ProcessStatus.EXITED
        assert (
            manager.logs(started.id, session_id=session, run_id=None)[0].content
            == "ping\n"
        )
        assert "AI2APPS_HOST_SECRET" not in finished.environment_keys

        with pytest.raises(ProcessServiceError, match="not allowed"):
            await manager.start(
                session_id=session,
                run_id=None,
                caller_id="test",
                argv=["/bin/echo", "x"],
                environment={"LD_PRELOAD": "bad"},
            )
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_process_output_wall_idle_and_session_limits(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    manager = await _manager(runtime, session_limit=1)
    try:
        noisy = await manager.start(
            session_id=session,
            run_id=None,
            caller_id="test",
            argv=["/usr/bin/yes"],
            limits={"output_bytes": 2048},
        )
        noisy_done = await _terminal(manager, noisy.id, session)
        assert noisy_done.status is ProcessStatus.OUTPUT_LIMIT
        assert noisy_done.output_bytes == 2048

        sleeping = await manager.start(
            session_id=session,
            run_id=None,
            caller_id="test",
            argv=["/bin/sleep", "5"],
            limits={"idle_time_seconds": 1},
        )
        with pytest.raises(ProcessServiceError, match="limit reached"):
            await manager.start(
                session_id=session,
                run_id=None,
                caller_id="test",
                argv=["/bin/echo", "blocked"],
            )
        sleeping_done = await _terminal(manager, sleeping.id, session, timeout=2)
        assert sleeping_done.status is ProcessStatus.IDLE_TIMEOUT
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_process_is_scoped_to_session_and_originating_run(tmp_path):
    runtime = _runtime(tmp_path)
    first = _session(runtime, "First")
    second = _session(runtime, "Second")
    first_run = runtime.agents.create_run(
        session_id=first, agent_key="ai2apps.diagnostic-agent", input={}
    )[0]
    second_run = runtime.agents.create_run(
        session_id=first, agent_key="ai2apps.diagnostic-agent", input={}
    )[0]
    manager = await _manager(runtime)
    try:
        started = await manager.start(
            session_id=first,
            run_id=first_run.id,
            caller_id="agent:test",
            argv=["/bin/sleep", "5"],
        )
        with pytest.raises(ResourceNotFoundError):
            manager.status(started.id, session_id=second, run_id=first_run.id)
        with pytest.raises(ProcessServiceError, match="Process not found"):
            manager.status(started.id, session_id=first, run_id=second_run.id)
        await manager.cancel_run(first_run.id)
        assert (
            await _terminal(manager, started.id, first, first_run.id)
        ).status is ProcessStatus.CANCELLED
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_agent_run_cancel_terminates_process_group(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    run = runtime.agents.create_run(
        session_id=session, agent_key="ai2apps.diagnostic-agent", input={}
    )[0]
    manager = await _manager(runtime)
    runtime.agent_runtime.bind_run_terminal_handler(manager.schedule_cancel_by_run)
    try:
        script = (
            "import subprocess,time; "
            "p=subprocess.Popen(['/bin/sleep','30']); "
            "print(p.pid,flush=True); time.sleep(30)"
        )
        started = await manager.start(
            session_id=session,
            run_id=run.id,
            caller_id="agent:test",
            argv=["/usr/bin/python3", "-c", script],
        )
        child_pid = None
        for _ in range(100):
            logs = manager.logs(started.id, session_id=session, run_id=run.id)
            for item in logs:
                candidate = item.content.strip()
                if item.stream == "stdout" and candidate.isdigit():
                    child_pid = int(candidate)
                    break
            if child_pid is not None:
                break
            await asyncio.sleep(0.01)
        assert child_pid is not None

        runtime.agent_runtime.cancel(run.id)
        assert (
            await _terminal(manager, started.id, session, run.id)
        ).status is ProcessStatus.CANCELLED
        alive = True
        for _ in range(100):
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                alive = False
                break
            await asyncio.sleep(0.01)
        assert alive is False
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_startup_reaps_verified_orphan_process_group(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    original = await _manager(runtime)
    recovered = await _manager(runtime)
    try:
        started = await original.start(
            session_id=session,
            run_id=None,
            caller_id="test",
            argv=["/bin/sleep", "30"],
        )
        live = original._live.pop(started.id)
        for task in live.tasks:
            task.cancel()
        await asyncio.gather(*live.tasks, return_exceptions=True)
        # Simulate a fresh runtime observing durable state while the old child
        # remains. PID birth-time matching prevents killing a reused PID.
        orphan_count = await recovered.startup()
        assert orphan_count == 1
        await asyncio.wait_for(live.process.wait(), 1)
        record = recovered.status(started.id, session_id=session, run_id=None)
        assert record.status is ProcessStatus.ORPHANED
        with pytest.raises(ProcessLookupError):
            os.kill(started.pid, 0)
    finally:
        await original.shutdown()
        await recovered.shutdown()


def test_broker_tokens_are_signed_scoped_and_expiring(monkeypatch):
    authority = BrokerAuthority(b"x" * 32)
    envelope = authority.issue(
        request_id="brq_test",
        session_id="ses_one",
        run_id="run_one",
        operation="process.spawn",
    )
    assert (
        authority.verify(
            envelope.token,
            session_id="ses_one",
            run_id="run_one",
            operation="process.spawn",
        )["nonce"]
        == envelope.nonce
    )
    with pytest.raises(PermissionError, match="scope mismatch"):
        authority.verify(
            envelope.token,
            session_id="ses_two",
            run_id="run_one",
            operation="process.spawn",
        )
    tampered = envelope.token[:-1] + ("0" if envelope.token[-1] != "0" else "1")
    with pytest.raises(PermissionError, match="Invalid"):
        authority.verify(
            tampered,
            session_id="ses_one",
            run_id="run_one",
            operation="process.spawn",
        )


def test_linux_bubblewrap_contract_denies_network_by_default(tmp_path):
    root = tmp_path / "workspace"
    temporary = tmp_path / "temporary"
    root.mkdir()
    temporary.mkdir()
    adapter = LinuxBubblewrapAdapter("/usr/bin/true")
    launch = adapter.wrap(
        ("/bin/echo", "ok"), root, temporary, root, network_enabled=False
    )
    assert "--die-with-parent" in launch.argv
    assert "--unshare-net" in launch.argv
    assert launch.enforced is True


@pytest.mark.asyncio
async def test_process_tools_require_capabilities_and_network_is_dynamic(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    tool = runtime.services.get_tool("process.start")
    assert runtime.tools.required_capabilities(
        tool, {"argv": ["/bin/echo", "x"]}
    ) == frozenset({"process.execute"})
    assert runtime.tools.required_capabilities(
        tool, {"argv": ["/bin/echo", "x"], "network": True}
    ) == frozenset({"process.execute", "network.outbound"})
    with pytest.raises(ToolGatewayError) as denied:
        await runtime.tools.execute(
            "process.start",
            {"argv": ["/bin/echo", "x"]},
            context=ToolCallContext(caller_id="test", session_id=session),
        )
    assert denied.value.code == "capability_denied"


@pytest.mark.asyncio
@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS Seatbelt contract")
async def test_macos_sandbox_allows_own_workspace_and_denies_another_session(tmp_path):
    if not os.path.isfile("/usr/bin/sandbox-exec"):
        pytest.skip("sandbox-exec unavailable")
    runtime = _runtime(tmp_path)
    first = _session(runtime, "Sandbox owner")
    second = _session(runtime, "Sandbox foreign")
    runtime.workspace.write(first, "own.txt", "own")
    runtime.workspace.write(second, "foreign.txt", "foreign")
    manager = ProcessManager(
        runtime.database,
        runtime.events,
        runtime.workspace,
        sandbox=MacOSSandboxAdapter(),
    )
    await manager.startup()
    try:
        own_path = str(runtime.workspace._resolve(first, "own.txt"))
        own = await manager.start(
            session_id=first,
            run_id=None,
            caller_id="test",
            argv=["/bin/cat", own_path],
        )
        own_done = await _terminal(manager, own.id, first)
        if own_done.status is ProcessStatus.FAILED:
            diagnostic = "".join(
                item.content
                for item in manager.logs(own.id, session_id=first, run_id=None)
            )
            if "sandbox_apply: Operation not permitted" in diagnostic:
                pytest.skip(
                    "test runner itself forbids applying a nested Seatbelt profile"
                )
        assert own_done.status is ProcessStatus.EXITED

        foreign_path = str(runtime.workspace._resolve(second, "foreign.txt"))
        foreign = await manager.start(
            session_id=first,
            run_id=None,
            caller_id="test",
            argv=["/bin/cat", foreign_path],
        )
        denied = await _terminal(manager, foreign.id, first)
        assert denied.status is ProcessStatus.FAILED
        assert "foreign" not in "".join(
            item.content
            for item in manager.logs(foreign.id, session_id=first, run_id=None)
            if item.stream == "stdout"
        )
    finally:
        await manager.shutdown()
