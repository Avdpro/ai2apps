"""Built-in Agent-to-Agent delegation Service and Tool."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ai2apps.services import (
    ServiceInstanceStatus,
    ServiceRegistry,
    ServiceRepository,
    ServiceRuntimeMode,
    ToolCallContext,
    ToolProviderError,
)

from .models import AgentRunStatus
from .repository import AgentRepository
from .runtime import AgentRuntime


def install_delegation_service(
    agents: AgentRepository,
    runtime: AgentRuntime,
    services: ServiceRepository,
    registry: ServiceRegistry,
) -> None:
    """Expose durable child AgentRuns as the ``agent.delegate`` Tool."""

    service = services.ensure_service(
        service_key="ai2apps.agent-runtime",
        package_id="ai2apps.agent-runtime",
        package_version="1.0.0",
        display_name="Agent Runtime",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
        capabilities=("agent.delegation",),
    )
    instance = services.ensure_instance(
        service_id=service.id,
        provider_key="builtin:agent-runtime",
        status=ServiceInstanceStatus.RUNNING,
        endpoint="/v1/platform/tools/agent.delegate/invoke",
        health={"status": "ok", "max_depth": agents.MAX_DELEGATION_DEPTH},
    )
    services.ensure_tool(
        service_id=service.id,
        qualified_name="agent.delegate",
        display_name="Delegate to Agent",
        description=(
            "Run a bounded child Agent in the current Session and return its "
            "durable result to the parent Agent."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "agent": {"type": "string", "minLength": 1},
                "task": {"type": "string", "minLength": 1, "maxLength": 32768},
                "request_key": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 128,
                },
                "parameters": {"type": "object"},
                "context": {"type": "string", "maxLength": 16384},
                "budget": {
                    "type": "object",
                    "properties": {
                        "max_steps": {"type": "integer", "minimum": 1, "maximum": 24},
                        "max_model_tokens": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100000,
                        },
                        "timeout_seconds": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 900,
                        },
                    },
                    "additionalProperties": False,
                },
            },
            "required": ["agent", "task", "request_key"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        effects=(),
        timeout_ms=910_000,
    )

    async def delegate(
        arguments: dict[str, Any], context: ToolCallContext
    ) -> dict[str, Any]:
        if context.trace_id is None or context.session_id is None:
            raise ToolProviderError("Delegation requires an Agent Run and Session")
        parent = agents.get_run(context.trace_id)
        if parent.session_id != context.session_id:
            raise ToolProviderError("Delegation Session does not match parent Run")
        request_key = arguments["request_key"]
        child = agents.get_delegated_child(parent.id, request_key)
        if child is None:
            budget = dict(arguments.get("budget") or {})
            delegation_context = {
                "instructions": arguments.get("context", ""),
                "parent_message_id": parent.input.get("message_id"),
            }
            child_input = {
                "model": parent.input.get("model", ""),
                "prompt": arguments["task"],
                "parameters": dict(arguments.get("parameters") or {}),
                "instructions": arguments.get("context", ""),
                "invocation": {"source": "delegation"},
            }
            child, _ = agents.create_run(
                session_id=parent.session_id,
                agent_key=arguments["agent"],
                input=child_input,
                idempotency_key=f"delegate:{parent.id}:{request_key}",
                priority=parent.priority,
                trace_id=parent.id,
                parent_run_id=parent.id,
                delegation={
                    "request_key": request_key,
                    "task": arguments["task"],
                    "parameters": dict(arguments.get("parameters") or {}),
                    "context": delegation_context,
                    "budget": budget,
                },
            )
            runtime.wake()
        definition = agents.get_definition(child.agent_definition_id)
        await context.report_progress(
            f"Waiting for {definition.display_name}",
            phase="waiting_subruns",
            content={
                "child_run_id": child.id,
                "agent_key": definition.agent_key,
                "depth": child.depth,
            },
        )
        remaining = max(
            0.1, (child.deadline_at - datetime.now(UTC)).total_seconds() + 1
        )
        child = await runtime.wait_for_terminal(child.id, timeout=remaining)
        await context.report_progress(
            f"{definition.display_name} {child.status.value}",
            phase="subrun_completed",
            content={"child_run_id": child.id, "status": child.status.value},
        )
        if child.status is not AgentRunStatus.COMPLETED:
            raise ToolProviderError(
                f"Delegated AgentRun {child.id} ended as {child.status.value}: "
                f"{(child.error or {}).get('message', '')}"
            )
        return {
            "child_run_id": child.id,
            "agent_key": definition.agent_key,
            "status": child.status.value,
            "output": child.output or {},
        }

    registry.bind_tool(
        "agent.delegate", provider_key=instance.provider_key, handler=delegate
    )
