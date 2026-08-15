"""Built-in Workspace and Artifact Service Tool descriptors and handlers."""

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

from .models import LocatorKind
from .repository import WorkspaceRepository

OBJECT = {"type": "object"}


def install_workspace_service(
    workspace: WorkspaceRepository,
    repository: ServiceRepository,
    registry: ServiceRegistry,
) -> None:
    service = repository.ensure_service(
        service_key="ai2apps.workspace",
        package_id="ai2apps.workspace",
        package_version="1.0.0",
        display_name="AI2Apps Workspace & Artifacts",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
        capabilities=("workspace", "resources", "artifacts"),
    )
    instance = repository.ensure_instance(
        service_id=service.id,
        provider_key="builtin:workspace",
        status=ServiceInstanceStatus.RUNNING,
        endpoint="/v1/platform/sessions/{session_id}/workspace",
        health={"status": "ok"},
    )

    def session(context: ToolCallContext) -> str:
        if context.session_id is None:
            raise ToolProviderError("Workspace Tools require a Session")
        return context.session_id

    async def workspace_list(arguments, context):
        return workspace.list(
            session(context),
            arguments.get("path", "."),
            offset=arguments.get("offset", 0),
            limit=arguments.get("limit", 200),
        )

    async def workspace_stat(arguments, context):
        return workspace.stat(session(context), arguments["path"])

    async def workspace_read(arguments, context):
        return workspace.read(
            session(context),
            arguments["path"],
            offset=arguments.get("offset", 0),
            limit=arguments.get("limit", 1024 * 1024),
        )

    async def workspace_search(arguments, context):
        return workspace.search(
            session(context),
            arguments["query"],
            path=arguments.get("path", "."),
            limit=arguments.get("limit", 100),
        )

    async def workspace_write(arguments, context):
        await context.report_progress("Writing workspace file", progress=0.25)
        result = workspace.write(
            session(context),
            arguments["path"],
            arguments["content"],
            encoding=arguments.get("encoding", "utf-8"),
        )
        await context.report_progress("Workspace file written", progress=1.0)
        return result

    async def workspace_patch(arguments, context):
        await context.report_progress("Applying workspace patch", progress=0.25)
        result = workspace.apply_patch(
            session(context), arguments["path"], arguments["replacements"]
        )
        await context.report_progress("Workspace patch applied", progress=1.0)
        return result

    async def resource_read(arguments, context):
        session_id = session(context)
        handle = workspace.get_handle(
            session_id, arguments["resource"], capability="read"
        )
        if handle.locator_kind is not LocatorKind.WORKSPACE:
            raise ToolProviderError(
                "This ResourceHandle is not readable through Workspace"
            )
        result = workspace.read(
            session_id,
            handle.locator,
            offset=arguments.get("offset", 0),
            limit=arguments.get("limit", 1024 * 1024),
        )
        return {**result, "resource": handle.uri, "display_name": handle.display_name}

    async def artifact_create(arguments, context):
        artifact = workspace.create_artifact(
            session(context),
            arguments["path"],
            arguments.get("name"),
            run_id=(
                context.trace_id
                if context.trace_id and context.trace_id.startswith("run_")
                else None
            ),
            media_type=arguments.get("media_type"),
            metadata=arguments.get("metadata"),
        )
        return _artifact_json(artifact)

    async def artifact_list(_arguments, context):
        return {
            "items": [
                _artifact_json(item)
                for item in workspace.list_artifacts(session(context))
            ]
        }

    async def artifact_preview(arguments, context):
        return workspace.preview_artifact(
            session(context),
            arguments["artifact_id"],
            arguments.get("limit", 256 * 1024),
        )

    async def artifact_export(arguments, context):
        return workspace.export_artifact(
            session(context),
            arguments["artifact_id"],
            arguments["destination_handle"],
            arguments.get("name"),
        )

    common_path = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
        "additionalProperties": False,
    }
    tools: tuple[
        tuple[str, str, str, dict[str, Any], tuple[str, ...], tuple[str, ...], Any], ...
    ] = (
        (
            "workspace.list",
            "List workspace",
            "List a Session workspace directory with pagination.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
                },
                "additionalProperties": False,
            },
            (),
            (),
            workspace_list,
        ),
        (
            "workspace.stat",
            "Stat workspace path",
            "Inspect a Session workspace path.",
            common_path,
            (),
            (),
            workspace_stat,
        ),
        (
            "workspace.read",
            "Read workspace file",
            "Read bounded file content from the Session workspace.",
            _read_schema("path"),
            (),
            (),
            workspace_read,
        ),
        (
            "workspace.search",
            "Search workspace",
            "Search bounded UTF-8 files in the Session workspace.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1},
                    "path": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            (),
            (),
            workspace_search,
        ),
        (
            "workspace.write",
            "Write workspace file",
            "Atomically write within the Session workspace quota.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "encoding": {"enum": ["utf-8", "base64"]},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
            ("write",),
            ("workspace.write",),
            workspace_write,
        ),
        (
            "workspace.apply_patch",
            "Patch workspace file",
            "Atomically apply exact text replacements.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "replacements": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "old": {"type": "string", "minLength": 1},
                                "new": {"type": "string"},
                                "count": {"type": "integer", "minimum": 1},
                            },
                            "required": ["old", "new"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["path", "replacements"],
                "additionalProperties": False,
            },
            ("write",),
            ("workspace.write",),
            workspace_patch,
        ),
        (
            "resource.read",
            "Read selected resource",
            "Read a user-selected opaque ResourceHandle.",
            _read_schema("resource"),
            (),
            (),
            resource_read,
        ),
        (
            "artifact.create",
            "Create artifact",
            "Create an immutable Artifact from a workspace file.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "name": {"type": "string"},
                    "media_type": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            ("write",),
            ("artifact.create",),
            artifact_create,
        ),
        (
            "artifact.list",
            "List artifacts",
            "List active Artifacts owned by the Session.",
            {"type": "object", "additionalProperties": False},
            (),
            (),
            artifact_list,
        ),
        (
            "artifact.preview",
            "Preview artifact",
            "Read a bounded Artifact preview.",
            {
                "type": "object",
                "properties": {
                    "artifact_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 1048576},
                },
                "required": ["artifact_id"],
                "additionalProperties": False,
            },
            (),
            (),
            artifact_preview,
        ),
        (
            "artifact.export",
            "Export artifact",
            "Atomically export through an authorized directory handle.",
            {
                "type": "object",
                "properties": {
                    "artifact_id": {"type": "string"},
                    "destination_handle": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["artifact_id", "destination_handle"],
                "additionalProperties": False,
            },
            ("external_write",),
            ("artifact.export",),
            artifact_export,
        ),
    )
    for name, title, description, schema, effects, capabilities, handler in tools:
        repository.ensure_tool(
            service_id=service.id,
            qualified_name=name,
            display_name=title,
            description=description,
            input_schema=schema,
            output_schema=OBJECT,
            effects=effects,
            required_capabilities=capabilities,
            timeout_ms=30_000,
        )
        registry.bind_tool(name, provider_key=instance.provider_key, handler=handler)


def _read_schema(field: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            field: {"type": "string", "minLength": 1},
            "offset": {"type": "integer", "minimum": 0},
            "limit": {"type": "integer", "minimum": 1, "maximum": 1048576},
        },
        "required": [field],
        "additionalProperties": False,
    }


def _artifact_json(artifact) -> dict[str, Any]:
    return {
        "id": artifact.id,
        "uri": artifact.uri,
        "name": artifact.name,
        "media_type": artifact.media_type,
        "content_hash": artifact.content_hash,
        "size_bytes": artifact.size_bytes,
        "metadata": artifact.metadata,
    }
