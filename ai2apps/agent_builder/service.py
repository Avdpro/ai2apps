"""P1 orchestration helpers shared by Apps, Workflows, and Schedules."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator

from ai2apps.agents import BROWSER_BUILDER_AGENT_KEY
from ai2apps.core import ResourceConflictError

from .models import AgentDraftRecord, AgentType, AgentWorkflowRecord
from .repository import AgentBuilderRepository


def active_generation(
    store: AgentBuilderRepository, draft: AgentDraftRecord
):
    if draft.active_generation_id is None:
        raise ResourceConflictError("Agent has no active compiled generation")
    return store.get_generation(draft.active_generation_id, draft.owner_user_id)


def capability_ir(ir: dict[str, Any], capability_name: str | None) -> dict[str, Any]:
    """Select one executable capability while retaining legacy IR compatibility."""

    capabilities = ir.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        return ir
    if capability_name:
        for item in capabilities:
            if isinstance(item, dict) and capability_name in {
                str(item.get("id") or ""), str(item.get("name") or "")
            }:
                return item
        raise ResourceConflictError(f"Unknown Agent capability: {capability_name}")
    return capabilities[0]


def workflow_ir(
    store: AgentBuilderRepository,
    workflow: AgentWorkflowRecord,
) -> dict[str, Any]:
    """Compose active Web generations into one deterministic sequential IR."""

    source_steps = workflow.definition.get("steps")
    if not isinstance(source_steps, list) or not source_steps:
        raise ResourceConflictError("Workflow has no steps")
    groups: list[tuple[str, dict[str, Any], dict[str, str], list[dict[str, Any]]]] = []
    for index, reference in enumerate(source_steps):
        draft = store.get_draft(
            str(reference.get("draft_id") or ""), workflow.owner_user_id
        )
        if draft.agent_type is not AgentType.WEB:
            raise ResourceConflictError(
                "P1 Workflow execution currently supports Web Agent steps"
            )
        generation = active_generation(store, draft)
        steps = [
            deepcopy(item)
            for item in generation.ir.get("steps", [])
            if isinstance(item, dict) and item.get("operation") != "complete"
        ]
        if not steps:
            raise ResourceConflictError(f"Workflow Agent {draft.name} has no runnable steps")
        prefix = str(reference.get("name") or f"step-{index + 1}")
        mapping = {str(item["id"]): f"{prefix}::{item['id']}" for item in steps}
        groups.append((prefix, generation.ir, mapping, steps))

    compiled: list[dict[str, Any]] = []
    for index, (_prefix, _ir, mapping, steps) in enumerate(groups):
        next_start = (
            groups[index + 1][2][str(groups[index + 1][3][0]["id"])]
            if index + 1 < len(groups)
            else "done"
        )
        for source in steps:
            item = deepcopy(source)
            item["id"] = mapping[str(source["id"])]
            transitions = source.get("on") if isinstance(source.get("on"), dict) else {}
            item["on"] = {
                outcome: mapping.get(
                    target, next_start if target == "done" else target
                )
                for outcome, target in transitions.items()
            }
            compiled.append(item)

    return {
        "schema": "ai2apps.compiled-agent/v1",
        "agent_type": "workflow",
        "name": workflow.name,
        "workflow_id": workflow.id,
        "start": compiled[0]["id"],
        "effects": sorted(
            {str(step.get("effect") or "read") for step in compiled}
        ),
        "site_scope": sorted(
            {
                str(scope)
                for _prefix, group_ir, _mapping, _steps in groups
                for scope in group_ir.get("site_scope", [])
            }
        ),
        "inputs": dict(
            workflow.definition.get("inputs")
            or {"type": "object", "properties": {}}
        ),
        "outputs": dict(
            workflow.definition.get("outputs")
            or {"type": "object", "properties": {}}
        ),
        "steps": compiled,
    }


def create_ir_run(
    runtime,
    *,
    session_id: str,
    ir: dict[str, Any],
    invocation_input: dict[str, Any],
    draft_id: str | None = None,
    generation_id: str | None = None,
    workflow_id: str | None = None,
    browser_context: dict[str, Any] | None = None,
    caller_app_id: str | None = None,
    knowledge_bucket_id: str | None = None,
    idempotency_key: str | None = None,
    owner_user_id: str | None = None,
    installation_id: str | None = None,
    capability_name: str | None = None,
    preview: bool = False,
):
    schema = ir.get("inputs")
    if isinstance(schema, dict):
        Draft202012Validator(schema).validate(invocation_input)
    model_manager = getattr(runtime, "model_manager", None)
    ai_model_routes = {
        tier: (
            None
            if model_manager is None
            else model_manager.resolve_default_model(f"work_{tier}")
        )
        for tier in ("simple", "standard", "complex")
    }
    run, _ = runtime.agents.create_run(
        session_id=session_id,
        agent_key=BROWSER_BUILDER_AGENT_KEY,
        input={
            "parameters": {
                "draft_id": draft_id,
                "generation_id": generation_id,
                "workflow_id": workflow_id,
                "ir": ir,
                "preview": preview,
                "browser_context": dict(browser_context or {}),
                "invocation_input": invocation_input,
                "caller_app_id": caller_app_id,
                "knowledge_bucket_id": knowledge_bucket_id,
                "owner_user_id": owner_user_id,
                "installation_id": installation_id,
                "capability_name": capability_name,
                "ai_model_routes": ai_model_routes,
            }
        },
        idempotency_key=idempotency_key,
        budget={"max_steps": 100, "timeout_seconds": 86_400},
    )
    runtime.agent_runtime.wake()
    return run


def create_active_draft_run(
    runtime,
    store: AgentBuilderRepository,
    *,
    owner_user_id: str,
    draft_id: str,
    session_id: str,
    invocation_input: dict[str, Any],
    browser_context: dict[str, Any] | None = None,
    caller_app_id: str | None = None,
    knowledge_bucket_id: str | None = None,
    idempotency_key: str | None = None,
    capability_name: str | None = None,
    installation_id: str | None = None,
):
    draft = store.get_draft(draft_id, owner_user_id)
    if draft.agent_type is not AgentType.WEB:
        raise ResourceConflictError(
            f"The {draft.agent_type.value} Agent runtime is not installed"
        )
    generation = active_generation(store, draft)
    selected = capability_ir(generation.ir, capability_name)
    selected_name = str(
        capability_name or selected.get("capability_name")
        or selected.get("name") or f"agent.{draft.id}.run"
    )
    reliability = getattr(runtime, "agent_reliability", None)
    if reliability is not None:
        reliability.require_circuit_closed(
            owner_user_id, draft.id, selected_name
        )
    return create_ir_run(
        runtime,
        session_id=session_id,
        ir=selected,
        invocation_input=invocation_input,
        draft_id=draft.id,
        generation_id=generation.id,
        browser_context=browser_context,
        caller_app_id=caller_app_id,
        knowledge_bucket_id=knowledge_bucket_id,
        idempotency_key=idempotency_key,
        owner_user_id=owner_user_id,
        installation_id=installation_id,
        capability_name=selected_name,
    )


def create_workflow_run(
    runtime,
    store: AgentBuilderRepository,
    *,
    owner_user_id: str,
    workflow_id: str,
    session_id: str,
    invocation_input: dict[str, Any],
    browser_context: dict[str, Any] | None = None,
    caller_app_id: str | None = None,
    knowledge_bucket_id: str | None = None,
    idempotency_key: str | None = None,
    installation_id: str | None = None,
):
    workflow = store.get_workflow(workflow_id, owner_user_id)
    return create_ir_run(
        runtime,
        session_id=session_id,
        ir=workflow_ir(store, workflow),
        invocation_input=invocation_input,
        workflow_id=workflow.id,
        browser_context=browser_context,
        caller_app_id=caller_app_id,
        knowledge_bucket_id=knowledge_bucket_id,
        idempotency_key=idempotency_key,
        owner_user_id=owner_user_id,
        installation_id=installation_id,
        capability_name=f"workflow.{workflow.id}.run",
    )
