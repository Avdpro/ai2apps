# SPDX-License-Identifier: Apache-2.0
"""M4 capability policy, GrantLease, audit, and management contracts."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from ai2apps.api.router import create_ai2apps_router
from ai2apps.capabilities import GrantScope, PolicyEffect
from ai2apps.chat import ChatRepository
from ai2apps.config import PlatformConfig
from ai2apps.platform_runtime import PlatformRuntime


def _runtime(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    assert runtime.agents is not None
    assert runtime.capabilities is not None
    assert runtime.capability_policy is not None
    return runtime


def _session(runtime):
    thread, _ = ChatRepository(runtime.database, runtime.events).create_thread(
        title="Capability test"
    )
    return thread.session.id


def _run(runtime, session_id):
    return runtime.agents.create_run(
        session_id=session_id,
        agent_key="ai2apps.diagnostic-agent",
        input={},
    )[0]


@pytest.mark.asyncio
async def test_policy_is_ordered_deterministic_and_deny_wins_ties(tmp_path):
    runtime = _runtime(tmp_path)
    run = _run(runtime, _session(runtime))
    engine = runtime.capability_policy

    initial = await engine.evaluate(
        run_id=run.id,
        agent_key="ai2apps.diagnostic-agent",
        tool_name="secure.write",
        capabilities=("secure.write",),
        effects=("write",),
        arguments={"path": "a"},
    )
    assert initial.effect is PolicyEffect.REQUIRE_APPROVAL

    runtime.capabilities.upsert_policy(
        policy_key="local.allow-write",
        effect=PolicyEffect.ALLOW,
        capability_pattern="secure.*",
        tool_pattern="secure.*",
        priority=100,
    )
    allowed = await engine.evaluate(
        run_id=run.id,
        agent_key="ai2apps.diagnostic-agent",
        tool_name="secure.write",
        capabilities=("secure.write",),
        effects=("write",),
        arguments={},
    )
    assert allowed.effect is PolicyEffect.ALLOW

    runtime.capabilities.upsert_policy(
        policy_key="local.deny-write",
        effect=PolicyEffect.DENY,
        capability_pattern="secure.write",
        tool_pattern="secure.write",
        priority=100,
    )
    denied = await engine.evaluate(
        run_id=run.id,
        agent_key="ai2apps.diagnostic-agent",
        tool_name="secure.write",
        capabilities=("secure.write",),
        effects=("write",),
        arguments={},
    )
    assert denied.effect is PolicyEffect.DENY
    assert len(denied.matched_policy_ids) == 2


def test_session_lease_is_agent_bound_expiring_and_revocable(tmp_path):
    runtime = _runtime(tmp_path)
    session_id = _session(runtime)
    first = _run(runtime, session_id)
    lease = runtime.capabilities.create_lease(
        run_id=first.id,
        scope=GrantScope.SESSION,
        capabilities=("secure.write",),
        tool_pattern="secure.*",
        issued_by="test",
        evidence={"case": "session"},
    )
    second = _run(runtime, session_id)

    active = runtime.capabilities.active_leases_for_run(second.id, "secure.write")
    assert [item.id for item in active] == [lease.id]
    assert active[0].evidence == {"case": "session"}

    revoked = runtime.capabilities.revoke_lease(lease.id, reason="user changed mind")
    assert revoked.revoked_at is not None
    assert runtime.capabilities.active_leases_for_run(second.id, "secure.write") == ()
    events = runtime.events.list_after(subject_id=lease.id, limit=20)
    assert [event.type for event in events] == [
        "capability.grant.created",
        "capability.grant.revoked",
    ]


@pytest.mark.asyncio
async def test_grant_resource_selector_cannot_authorize_a_different_target(tmp_path):
    runtime = _runtime(tmp_path)
    run = _run(runtime, _session(runtime))
    runtime.capabilities.create_lease(
        run_id=run.id, scope=GrantScope.RUN,
        capabilities=("workspace.write",), tool_pattern="workspace.write",
        issued_by="test", evidence={"case": "resource-bound"},
        resource_selector={"arguments": {"path": "allowed.txt"}},
    )
    allowed = await runtime.capability_policy.evaluate(
        run_id=run.id, agent_key="ai2apps.diagnostic-agent",
        tool_name="workspace.write", capabilities=("workspace.write",),
        effects=("write",), arguments={"path": "allowed.txt"},
    )
    denied = await runtime.capability_policy.evaluate(
        run_id=run.id, agent_key="ai2apps.diagnostic-agent",
        tool_name="workspace.write", capabilities=("workspace.write",),
        effects=("write",), arguments={"path": "different.txt"},
    )
    assert allowed.effect is PolicyEffect.ALLOW
    assert allowed.source == "grant_lease"
    assert denied.effect is PolicyEffect.REQUIRE_APPROVAL


@pytest.mark.asyncio
async def test_ai_auditor_is_bounded_and_records_evidence(tmp_path):
    runtime = _runtime(tmp_path)
    run = _run(runtime, _session(runtime))

    async def auditor(request):
        assert request["tool_name"] == "secure.read"
        return {
            "decision": "allow",
            "reason": "read-only fixture",
            "evidence": {"review": "unit-test"},
        }

    runtime.bind_ai_capability_auditor(auditor)
    decision = await runtime.capability_policy.evaluate(
        run_id=run.id,
        agent_key="ai2apps.diagnostic-agent",
        tool_name="secure.read",
        capabilities=("secure.read",),
        effects=("read",),
        arguments={},
    )
    assert decision.effect is PolicyEffect.ALLOW
    assert decision.source == "ai_auditor"
    assert decision.evidence["ai_auditor"]["evidence"] == {"review": "unit-test"}

    runtime.bind_ai_capability_auditor(lambda _request: {"decision": "bogus"})
    failed_closed = await runtime.capability_policy.evaluate(
        run_id=run.id,
        agent_key="ai2apps.diagnostic-agent",
        tool_name="secure.read",
        capabilities=("secure.read",),
        effects=("read",),
        arguments={},
    )
    assert failed_closed.effect is PolicyEffect.REQUIRE_APPROVAL
    assert failed_closed.evidence["ai_auditor"]["error"] == "ValueError"


@pytest.mark.asyncio
async def test_policy_and_grant_management_api(tmp_path):
    runtime = _runtime(tmp_path)
    run = _run(runtime, _session(runtime))
    lease = runtime.capabilities.create_lease(
        run_id=run.id,
        scope=GrantScope.RUN,
        capabilities=("secure.write",),
        tool_pattern="secure.write",
        issued_by="test",
        evidence={},
    )
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        put = await client.put(
            "/v1/platform/capability-policies/local.read",
            json={"effect": "allow", "capability_pattern": "secure.read"},
        )
        assert put.status_code == 200
        policies = await client.get("/v1/platform/capability-policies")
        assert {item["policy_key"] for item in policies.json()["items"]} >= {
            "builtin.default-require-approval",
            "local.read",
        }
        grants = await client.get("/v1/platform/grant-leases")
        assert [item["id"] for item in grants.json()["items"]] == [lease.id]
        revoked = await client.post(
            f"/v1/platform/grant-leases/{lease.id}/revoke",
            json={"reason": "API test"},
        )
        assert revoked.status_code == 200
        assert revoked.json()["revoke_reason"] == "API test"


@pytest.mark.asyncio
async def test_app_capability_request_approval_grant_and_safe_mode_recovery(tmp_path):
    runtime = _runtime(tmp_path)
    session_id = _session(runtime)
    with runtime.database.transaction() as connection:
        app_instance_id = connection.execute(
            "SELECT app_instance_id FROM sessions WHERE id=?", (session_id,)
        ).fetchone()[0]

    request = runtime.capabilities.create_app_request(
        app_instance_id=app_instance_id,
        session_id=session_id,
        capabilities=("workspace.export",),
        tool_name="artifact.export",
        effects=("export", "write"),
        resource_selector={"artifact_id": "art_example"},
        reason="Export the selected artifact",
    )
    assert request.status.value == "pending"
    assert request.risk_level == "medium"
    assert runtime.capabilities.list_requests() == (request,)

    resolved, lease = runtime.capabilities.decide_app_request(
        request.id,
        decision="approve",
        scope="once",
    )
    assert resolved.status.value == "approved"
    assert lease is not None
    assert lease.agent_definition_id is None
    assert lease.scope.value == "app"
    assert lease.expires_at is not None
    assert lease.resource_selector == {"artifact_id": "art_example"}

    recovery = await runtime.set_safe_mode(True, "capability-test")
    assert recovery["revoked_grants"] == 1
    assert runtime.capabilities.list_leases() == ()
    repeated = await runtime.set_safe_mode(True, "repeated-request")
    assert repeated["active"] is True
    assert repeated["reason"] == "capability-test"
    assert repeated["revoked_grants"] == 0
    restored = await runtime.set_safe_mode(False, "capability-test-complete")
    assert restored["active"] is False
    assert runtime.capabilities.list_leases(include_inactive=False) == ()
    audit_types = [
        event.type for event in runtime.events.list_after(subject_id=request.id, limit=20)
    ]
    assert audit_types == [
        "capability.request.created",
        "capability.decision.allow",
    ]
