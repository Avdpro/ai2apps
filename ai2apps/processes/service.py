"""Built-in Process Service Tool descriptors and provider bindings."""

from __future__ import annotations

from typing import Any

from ai2apps.services import (
    ServiceInstanceStatus,
    ServiceRegistry,
    ServiceRepository,
    ServiceRuntimeMode,
    ToolCallContext,
    ToolProviderError,
)

from .manager import ProcessManager
from .models import ProcessServiceError

OBJECT = {"type": "object"}


def _scope(context: ToolCallContext) -> tuple[str, str | None]:
    if context.session_id is None:
        raise ToolProviderError("Process Tools require a Session")
    run_id = (
        context.trace_id
        if context.trace_id and context.trace_id.startswith("run_")
        else None
    )
    return context.session_id, run_id


def _record(record) -> dict[str, Any]:
    return {
        "id": record.id,
        "session_id": record.session_id,
        "run_id": record.run_id,
        "status": record.status.value,
        "argv": list(record.argv),
        "cwd": record.cwd,
        "sandbox_backend": record.sandbox_backend,
        "network_enabled": record.network_enabled,
        "pid": record.pid,
        "exit_code": record.exit_code,
        "limits": record.limits,
        "stdin_open": record.stdin_open,
        "output_bytes": record.output_bytes,
        "error": record.error,
        "created_at": record.created_at.isoformat(),
        "started_at": None
        if record.started_at is None
        else record.started_at.isoformat(),
        "finished_at": None
        if record.finished_at is None
        else record.finished_at.isoformat(),
    }


def install_process_service(
    manager: ProcessManager,
    repository: ServiceRepository,
    registry: ServiceRegistry,
) -> None:
    service = repository.ensure_service(
        service_key="ai2apps.process",
        package_id="ai2apps.process",
        package_version="1.0.0",
        display_name="AI2Apps Sandboxed Process Service",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
        capabilities=("process", "sandbox", "host-broker"),
    )
    instance = repository.ensure_instance(
        service_id=service.id,
        provider_key="builtin:process",
        status=ServiceInstanceStatus.RUNNING,
        endpoint="/v1/platform/sessions/{session_id}/processes",
        health={"status": "ok", "sandbox": manager.sandbox.name},
    )

    async def call(operation, *args, **kwargs):
        try:
            return await operation(*args, **kwargs)
        except ProcessServiceError as error:
            raise ToolProviderError(f"{error.code}: {error}") from error

    async def process_start(arguments, context):
        session_id, run_id = _scope(context)
        await context.report_progress("Starting sandboxed process", progress=0.25)
        record = await call(
            manager.start,
            session_id=session_id,
            run_id=run_id,
            caller_id=context.caller_id,
            argv=arguments["argv"],
            cwd=arguments.get("cwd", "."),
            environment=arguments.get("environment"),
            network_enabled=arguments.get("network", False),
            limits=arguments.get("limits"),
        )
        await context.report_progress(
            "Sandboxed process started",
            progress=1.0,
            content={"process_id": record.id, "status": record.status.value},
        )
        return _record(record)

    async def process_write_stdin(arguments, context):
        session_id, run_id = _scope(context)
        return _record(
            await call(
                manager.write_stdin,
                arguments["process_id"],
                arguments.get("data", ""),
                session_id=session_id,
                run_id=run_id,
                close=arguments.get("close", False),
            )
        )

    async def process_status(arguments, context):
        session_id, run_id = _scope(context)
        try:
            return _record(
                manager.status(
                    arguments["process_id"], session_id=session_id, run_id=run_id
                )
            )
        except ProcessServiceError as error:
            raise ToolProviderError(f"{error.code}: {error}") from error

    async def process_logs(arguments, context):
        session_id, run_id = _scope(context)
        try:
            logs = manager.logs(
                arguments["process_id"],
                session_id=session_id,
                run_id=run_id,
                after=arguments.get("after", 0),
                limit=arguments.get("limit", 200),
            )
        except ProcessServiceError as error:
            raise ToolProviderError(f"{error.code}: {error}") from error
        return {
            "items": [
                {
                    "sequence": item.sequence,
                    "stream": item.stream,
                    "encoding": item.encoding,
                    "content": item.content,
                    "byte_count": item.byte_count,
                    "created_at": item.created_at.isoformat(),
                }
                for item in logs
            ]
        }

    async def process_wait(arguments, context):
        session_id, run_id = _scope(context)
        await context.report_progress("Waiting for sandboxed process")
        record = await call(
            manager.wait,
            arguments["process_id"],
            session_id=session_id,
            run_id=run_id,
            timeout_ms=arguments.get("timeout_ms", 30_000),
        )
        await context.report_progress(
            f"Sandboxed process finished: {record.status.value}",
            progress=1.0,
            content={"process_id": record.id, "status": record.status.value},
        )
        return _record(record)

    async def process_cancel(arguments, context):
        session_id, run_id = _scope(context)
        await context.report_progress("Cancelling sandboxed process", progress=0.5)
        result = _record(
            await call(
                manager.cancel,
                arguments["process_id"],
                session_id=session_id,
                run_id=run_id,
            )
        )
        await context.report_progress("Sandboxed process cancelled", progress=1.0)
        return result

    process_id_schema = {
        "type": "object",
        "properties": {"process_id": {"type": "string", "minLength": 1}},
        "required": ["process_id"],
        "additionalProperties": False,
    }
    limits_properties = {
        "wall_time_seconds": {"type": "integer", "minimum": 1, "maximum": 300},
        "idle_time_seconds": {"type": "integer", "minimum": 1, "maximum": 60},
        "cpu_time_seconds": {"type": "integer", "minimum": 1, "maximum": 120},
        "memory_bytes": {"type": "integer", "minimum": 16777216, "maximum": 1073741824},
        "output_bytes": {"type": "integer", "minimum": 1024, "maximum": 4194304},
    }
    start_schema = {
        "type": "object",
        "properties": {
            "argv": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "items": {"type": "string", "minLength": 1},
            },
            "cwd": {"type": "string"},
            "environment": {
                "type": "object",
                "propertyNames": {"type": "string", "minLength": 1},
                "additionalProperties": {
                    "oneOf": [
                        {"type": "string"},
                        {
                            "type": "object",
                            "properties": {
                                "secret_ref": {"type": "string", "minLength": 1}
                            },
                            "required": ["secret_ref"],
                            "additionalProperties": False,
                        },
                    ]
                },
            },
            "network": {"type": "boolean"},
            "limits": {
                "type": "object",
                "properties": limits_properties,
                "additionalProperties": False,
            },
        },
        "required": ["argv"],
        "additionalProperties": False,
    }
    write_schema = {
        "type": "object",
        "properties": {
            "process_id": {"type": "string", "minLength": 1},
            "data": {"type": "string", "maxLength": 65536},
            "close": {"type": "boolean"},
        },
        "required": ["process_id"],
        "additionalProperties": False,
    }
    logs_schema = {
        "type": "object",
        "properties": {
            "process_id": {"type": "string", "minLength": 1},
            "after": {"type": "integer", "minimum": 0},
            "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
        },
        "required": ["process_id"],
        "additionalProperties": False,
    }
    wait_schema = {
        "type": "object",
        "properties": {
            "process_id": {"type": "string", "minLength": 1},
            "timeout_ms": {
                "type": "integer",
                "minimum": 1,
                "maximum": 300000,
            },
        },
        "required": ["process_id"],
        "additionalProperties": False,
    }
    tools = (
        (
            "process.start",
            "Start sandboxed process",
            "Start an argv-only Process in the Session workspace sandbox.",
            start_schema,
            ("process",),
            ("process.execute",),
            (
                {
                    "when": {"property": "network", "equals": True},
                    "require": ["network.outbound"],
                },
            ),
            process_start,
        ),
        (
            "process.write_stdin",
            "Write process stdin",
            "Write bounded UTF-8 input to a Process owned by this Session and Run.",
            write_schema,
            ("process",),
            ("process.execute",),
            (),
            process_write_stdin,
        ),
        (
            "process.status",
            "Get process status",
            "Read status for a Process owned by this Session and Run.",
            process_id_schema,
            (),
            ("process.execute",),
            (),
            process_status,
        ),
        (
            "process.logs",
            "Read process logs",
            "Read bounded stdout/stderr chunks for a Process.",
            logs_schema,
            (),
            ("process.execute",),
            (),
            process_logs,
        ),
        (
            "process.wait",
            "Wait for process",
            "Wait for a Process to finish without unbounded polling.",
            wait_schema,
            (),
            ("process.execute",),
            (),
            process_wait,
        ),
        (
            "process.cancel",
            "Cancel process",
            "Terminate the complete Process group owned by this Session and Run.",
            process_id_schema,
            ("process",),
            ("process.execute",),
            (),
            process_cancel,
        ),
    )
    for (
        name,
        title,
        description,
        schema,
        effects,
        capabilities,
        rules,
        handler,
    ) in tools:
        repository.ensure_tool(
            service_id=service.id,
            qualified_name=name,
            display_name=title,
            description=description,
            input_schema=schema,
            output_schema=OBJECT,
            effects=effects,
            required_capabilities=capabilities,
            capability_rules=rules,
            timeout_ms=300_000 if name == "process.wait" else 30_000,
        )
        registry.bind_tool(name, provider_key=instance.provider_key, handler=handler)
