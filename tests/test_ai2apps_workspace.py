# SPDX-License-Identifier: Apache-2.0
"""M5 Session Workspace, ResourceHandle, Artifact, and export contracts."""

from __future__ import annotations

import base64

import httpx
import pytest
from fastapi import FastAPI

from ai2apps.agents import InteractionKind
from ai2apps.api.router import create_ai2apps_router
from ai2apps.chat import ChatRepository
from ai2apps.config import PlatformConfig
from ai2apps.core import ResourceNotFoundError
from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.services import ToolCallContext, ToolGatewayError
from ai2apps.workspace import WorkspaceError


def _runtime(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / "data"))
    runtime.start()
    assert runtime.workspace is not None
    assert runtime.tools is not None
    return runtime


def _session(runtime, title="Workspace"):
    return (
        ChatRepository(runtime.database, runtime.events)
        .create_thread(title=title)[0]
        .session.id
    )


def _principal(user_id: str, role: MemberRole = MemberRole.MEMBER):
    return RequestPrincipal(
        actor_user_id=user_id,
        installation_id="installation-1",
        organization_id="organization-1",
        billing_account_id="billing-core",
        role=role,
        membership_epoch=1,
    )


def test_workspace_is_session_isolated_and_blocks_escape_and_symlink(tmp_path):
    runtime = _runtime(tmp_path)
    first = _session(runtime, "First")
    second = _session(runtime, "Second")
    workspace = runtime.workspace

    workspace.write(first, "notes/hello.txt", "secret")
    assert workspace.read(first, "notes/hello.txt")["content"] == "secret"
    with pytest.raises(FileNotFoundError):
        workspace.read(second, "notes/hello.txt")
    with pytest.raises(WorkspaceError, match="safe and relative"):
        workspace.read(first, "../outside.txt")
    with pytest.raises(WorkspaceError, match="safe and relative"):
        workspace.read(first, str(tmp_path / "outside.txt"))

    outside = tmp_path / "outside"
    outside.mkdir()
    root = workspace._root(first)  # qualify the security boundary itself
    (root / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(WorkspaceError, match="escapes"):
        workspace.write(first, "escape/pwned.txt", "no")
    assert not (outside / "pwned.txt").exists()


def test_workspace_atomic_write_patch_search_and_pagination(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    workspace = runtime.workspace
    workspace.write(session, "a.txt", "alpha\nbeta\n")
    workspace.write(session, "b.txt", "alpha\n")

    patched = workspace.apply_patch(
        session, "a.txt", [{"old": "beta", "new": "gamma", "count": 1}]
    )
    assert patched["replacements_applied"] == 1
    assert workspace.read(session, "a.txt")["content"] == "alpha\ngamma\n"
    with pytest.raises(WorkspaceError, match="Expected 1 occurrence"):
        workspace.apply_patch(session, "a.txt", [{"old": "missing", "new": "x"}])

    search = workspace.search(session, "alpha", limit=10)
    assert [item["path"] for item in search["matches"]] == ["a.txt", "b.txt"]
    page = workspace.list(session, limit=1)
    assert len(page["items"]) == 1
    assert page["has_more"] is True


def test_browser_upload_resolution_and_download_adoption_are_session_scoped(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    workspace = runtime.workspace
    workspace.write(session, "attachments/input.txt", "upload")
    resolved = workspace.resolve_browser_upload(session, "attachments/input.txt")
    assert resolved.read_text() == "upload"
    with pytest.raises(WorkspaceError, match="safe and relative"):
        workspace.resolve_browser_upload(session, "../outside.txt")

    staging = workspace.browser_download_directory(session)
    (staging / "result.txt").write_text("download")
    adopted = workspace.adopt_browser_download(session, "result.txt")
    assert adopted["path"] == "downloads/result.txt"
    assert workspace.read(session, adopted["path"])["content"] == "download"

    (staging / "partial.crdownload").write_text("partial")
    with pytest.raises(WorkspaceError, match="Incomplete download"):
        workspace.adopt_browser_download(session, "partial.crdownload")


def test_resource_handles_are_opaque_session_scoped_and_revocable(tmp_path):
    runtime = _runtime(tmp_path)
    first = _session(runtime, "First")
    second = _session(runtime, "Second")
    handle = runtime.workspace.import_bytes(
        first, "sample.svg", b"<svg/>\n", media_type="image/svg+xml"
    )

    assert handle.uri.startswith("resource://res_")
    assert "/" not in handle.locator.split("/")[-1]
    assert runtime.workspace.get_handle(first, handle.uri).id == handle.id
    with pytest.raises(ResourceNotFoundError):
        runtime.workspace.get_handle(second, handle.uri)
    runtime.workspace.revoke_handle(first, handle.id)
    with pytest.raises(ResourceNotFoundError):
        runtime.workspace.get_handle(first, handle.uri)


def test_file_interaction_accepts_only_a_live_handle_from_its_session(tmp_path):
    runtime = _runtime(tmp_path)
    first = _session(runtime, "First")
    second = _session(runtime, "Second")
    foreign = runtime.workspace.import_bytes(second, "foreign.txt", b"no")
    own = runtime.workspace.import_bytes(first, "own.txt", b"yes")
    run = runtime.agents.create_run(
        session_id=first, agent_key="ai2apps.diagnostic-agent", input={}
    )[0]
    interaction = runtime.agents.create_interaction(
        run.id,
        request_key="file",
        kind=InteractionKind.FILE,
        prompt="Choose",
        response_schema={
            "type": "object",
            "properties": {"resource_handle": {"type": "string"}},
            "required": ["resource_handle"],
            "additionalProperties": False,
        },
    )
    with pytest.raises(Exception, match="unavailable in this Session"):
        runtime.agents.respond_interaction(
            run.id,
            interaction.id,
            response={"resource_handle": foreign.uri},
            response_id="foreign",
        )
    accepted = runtime.agents.respond_interaction(
        run.id,
        interaction.id,
        response={"resource_handle": own.uri},
        response_id="own",
    )
    assert accepted.response == {"resource_handle": own.uri}


@pytest.mark.asyncio
async def test_svg_to_artifact_and_export_requires_capability(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    workspace = runtime.workspace
    handle = workspace.import_bytes(session, "app.svg", b"<svg><rect/></svg>")
    artifact = workspace.create_artifact(session, handle.locator, "app.svg")
    export_directory = tmp_path / "exports"
    export_directory.mkdir()
    destination = workspace.register_external_directory(session, export_directory)

    context = ToolCallContext(caller_id="agent:test", session_id=session)
    with pytest.raises(ToolGatewayError) as denied:
        await runtime.tools.execute(
            "artifact.export",
            {"artifact_id": artifact.id, "destination_handle": destination.uri},
            context=context,
        )
    assert denied.value.code == "capability_denied"
    assert not (export_directory / "app.svg").exists()

    result = await runtime.tools.execute(
        "artifact.export",
        {"artifact_id": artifact.id, "destination_handle": destination.uri},
        context=ToolCallContext(
            caller_id="agent:test",
            session_id=session,
            granted_capabilities=frozenset({"artifact.export"}),
        ),
    )
    assert result.output["content_hash"] == artifact.content_hash
    assert (export_directory / "app.svg").read_bytes() == b"<svg><rect/></svg>"
    assert not list(export_directory.glob("*.ai2apps-export"))


@pytest.mark.asyncio
async def test_resource_and_artifact_api_round_trip(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=RequestPrincipal.legacy_local))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        imported = await client.post(
            f"/v1/platform/sessions/{session}/resource-handles/import",
            json={
                "filename": "hello.txt",
                "media_type": "text/plain",
                "content_base64": base64.b64encode(b"hello artifact").decode(),
            },
        )
        assert imported.status_code == 201
        handle = runtime.workspace.get_handle(session, imported.json()["uri"])
        created = await client.post(
            f"/v1/platform/sessions/{session}/artifacts",
            json={"path": handle.locator, "name": "result.txt"},
        )
        assert created.status_code == 201
        artifact = created.json()
        preview = await client.get(
            f"/v1/platform/sessions/{session}/artifacts/{artifact['id']}/preview"
        )
        assert preview.json()["content"] == "hello artifact"
        download = await client.get(
            f"/v1/platform/sessions/{session}/artifacts/{artifact['id']}/download"
        )
        assert download.content == b"hello artifact"
        assert download.headers["content-type"].startswith("text/plain")


@pytest.mark.asyncio
async def test_member_apis_hide_foreign_session_resources_and_events(tmp_path):
    runtime = _runtime(tmp_path)
    alice = _principal("user-alice")
    bob = _principal("user-bob")
    alice_instance, alice_home, _ = runtime.extension_manager.launch_app(
        "ai2apps.general-chat", principal=alice
    )
    assert alice_home is not None

    alice_app = FastAPI()
    alice_app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: alice,
        )
    )
    bob_app = FastAPI()
    bob_app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: bob,
        )
    )

    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=alice_app), base_url="http://alice"
        ) as alice_client,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=bob_app), base_url="http://bob"
        ) as bob_client,
    ):
        written = await alice_client.put(
            f"/v1/platform/sessions/{alice_home.id}/workspace",
            json={"path": "private.txt", "content": "alice only"},
        )
        attached = await alice_client.post(
            f"/v1/platform/sessions/{alice_home.id}/attachments",
            json={
                "filename": "private.txt",
                "media_type": "text/plain",
                "data": base64.b64encode(b"alice attachment").decode(),
            },
        )
        message = await alice_client.post(
            f"/v1/platform/sessions/{alice_home.id}/messages",
            json={
                "role": "user",
                "parts": [
                    {"kind": "text", "content": {"text": "alice message"}}
                ],
            },
        )

        foreign_workspace = await bob_client.get(
            f"/v1/platform/sessions/{alice_home.id}/workspace"
        )
        foreign_attachments = await bob_client.get(
            f"/v1/platform/sessions/{alice_home.id}/attachments"
        )
        foreign_messages = await bob_client.get(
            f"/v1/platform/sessions/{alice_home.id}/messages"
        )
        foreign_instance = await bob_client.get(
            f"/v1/platform/app-instances/{alice_instance.id}/sessions"
        )
        foreign_events = await bob_client.get(
            "/v1/platform/events", params={"session_id": alice_home.id}
        )
        unscoped_events = await bob_client.get("/v1/platform/events")

    assert written.status_code == 200
    assert attached.status_code == 201
    assert message.status_code == 201
    assert {
        foreign_workspace.status_code,
        foreign_attachments.status_code,
        foreign_messages.status_code,
        foreign_instance.status_code,
        foreign_events.status_code,
    } == {404}
    assert unscoped_events.status_code == 403
    assert unscoped_events.json()["detail"]["code"] == "event_scope_required"


@pytest.mark.asyncio
async def test_agent_run_api_is_filtered_through_session_ownership(tmp_path):
    runtime = _runtime(tmp_path)
    alice = _principal("admin-alice", MemberRole.ADMIN)
    bob = _principal("admin-bob", MemberRole.ADMIN)
    _, alice_home, _ = runtime.extension_manager.launch_app(
        "ai2apps.general-chat", principal=alice
    )
    _, bob_home, _ = runtime.extension_manager.launch_app(
        "ai2apps.general-chat", principal=bob
    )
    assert alice_home is not None and bob_home is not None
    alice_run, _ = runtime.agents.create_run(
        session_id=alice_home.id,
        agent_key="ai2apps.diagnostic-agent",
        input={"private": "alice"},
    )
    bob_run, _ = runtime.agents.create_run(
        session_id=bob_home.id,
        agent_key="ai2apps.diagnostic-agent",
        input={"private": "bob"},
    )

    alice_app = FastAPI()
    alice_app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: alice,
        )
    )
    bob_app = FastAPI()
    bob_app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: bob,
        )
    )

    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=alice_app), base_url="http://alice"
        ) as alice_client,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=bob_app), base_url="http://bob"
        ) as bob_client,
    ):
        own = await alice_client.get(f"/v1/platform/agent-runs/{alice_run.id}")
        foreign = await bob_client.get(f"/v1/platform/agent-runs/{alice_run.id}")
        alice_list = await alice_client.get("/v1/platform/agent-runs")
        bob_list = await bob_client.get("/v1/platform/agent-runs")

    assert own.status_code == 200
    assert foreign.status_code == 404
    assert {item["id"] for item in alice_list.json()["items"]} == {alice_run.id}
    assert {item["id"] for item in bob_list.json()["items"]} == {bob_run.id}


def test_workspace_service_is_installed_with_expected_tools(tmp_path):
    runtime = _runtime(tmp_path)
    service = runtime.services.get_service("ai2apps.workspace")
    tools = {
        tool.qualified_name
        for tool in runtime.services.list_tools()
        if tool.service_id == service.id
    }
    assert tools == {
        "workspace.list",
        "workspace.stat",
        "workspace.read",
        "workspace.search",
        "workspace.write",
        "workspace.apply_patch",
        "resource.read",
        "artifact.create",
        "artifact.list",
        "artifact.preview",
        "artifact.export",
    }


@pytest.mark.asyncio
async def test_workspace_tools_use_harness_invocation_and_progress(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    progress = []
    written = await runtime.tools.execute(
        "workspace.write",
        {"path": "harness.txt", "content": "W6"},
        context=ToolCallContext(
            caller_id="agent:w6-fixture",
            session_id=session,
            trace_id="run_workspace_harness",
            granted_capabilities=frozenset({"workspace.write"}),
            progress_reporter=progress.append,
        ),
    )
    read = await runtime.tools.execute(
        "workspace.read",
        {"path": "harness.txt"},
        context=ToolCallContext(
            caller_id="agent:w6-fixture",
            session_id=session,
            trace_id="run_workspace_harness",
        ),
    )
    invocation = runtime.services.get_invocation(written.invocation_id)

    assert read.output["content"] == "W6"
    assert [item["progress"] for item in progress] == [0.25, 1.0]
    assert invocation.progress["text"] == "Workspace file written"
    assert len(runtime.services.list_invocations(trace_id="run_workspace_harness")) == 2
