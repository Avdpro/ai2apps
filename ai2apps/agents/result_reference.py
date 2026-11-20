"""Bounded model previews backed by the original durable Tool step."""

from __future__ import annotations

import hashlib
import json

from ai2apps.core import ResourceNotFoundError
from ai2apps.services import ToolCallContext, ToolProviderError

from .compaction import CHECKPOINT_READER, is_checkpoint
from .models import RunStepStatus

RESULT_READER = "agent.read_tool_result"
PREVIEW_THRESHOLD_BYTES = 8192
HEAD_CHARS = 2048
TAIL_CHARS = 1024


def result_text(output: object) -> str:
    return json.dumps(output, ensure_ascii=False, sort_keys=True)


def parameter_preview(value, *, step_id, reader_alias, source="input", path=""):
    """Stable data-only projection; execution and durable records stay untouched."""
    if isinstance(value, str):
        data_url = value.startswith("data:") and "," in value[:256]
        # Ordinary result text already has the whole-result paging contract.
        if source == "output" and not data_url:
            return value
        if len(value.encode("utf-8")) <= (256 if data_url else 8192):
            return value
        return {
            "type": "ai2apps.tool-value-reference/v1",
            "source": source, "step_id": step_id, "path": path,
            "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
            "total_characters": len(value),
            "total_bytes": len(value.encode("utf-8")),
            "preview": value.split(",", 1)[0] if data_url else value[:512],
            "read_with": {"tool": reader_alias, "arguments": {
                "step_id": step_id, "source": source, "path": path,
                "offset": 0, "limit": 4096}},
            "notice": "Omitted original value, not an executable argument. Read the original before copying or changing it.",
        }
    if isinstance(value, dict):
        return {key: parameter_preview(item, step_id=step_id, reader_alias=reader_alias,
            source=source, path=path+"/"+str(key).replace("~", "~0").replace("/", "~1"))
            for key, item in value.items()}
    if isinstance(value, list):
        return [parameter_preview(item, step_id=step_id, reader_alias=reader_alias,
            source=source, path=path+"/"+str(index)) for index, item in enumerate(value)]
    return value


def result_preview(step, *, reader_alias: str | None, app_preview=None) -> str:
    text = result_text(step.output)
    encoded = text.encode("utf-8")
    has_inline_data = False
    if reader_alias is not None:
        projected = parameter_preview(step.output, step_id=step.id,
                                      reader_alias=reader_alias, source="output")
        # Keep the existing whole-result paging contract for larger structures.
        # Small projected structures retain every short field and exact identifier.
        has_inline_data = projected != step.output
        projected_text = result_text(projected)
        if projected != step.output and len(projected_text.encode("utf-8")) <= PREVIEW_THRESHOLD_BYTES:
            # Existing owner projections continue to accompany the reference.
            if isinstance(projected, dict) and app_preview and len(result_text(app_preview).encode("utf-8")) <= 16384:
                projected["app_context"] = app_preview
            return result_text(projected)
    if reader_alias is None or len(encoded) <= PREVIEW_THRESHOLD_BYTES:
        return text
    head = text[:min(HEAD_CHARS, len(text)//3)]
    tail = text[-min(TAIL_CHARS, len(text)//6):]
    if has_inline_data:
        # Never include an encoded payload in a head/tail preview. Whole-result
        # reads retain original JSON offsets, starting at zero in this case.
        head = tail = ""
    preview = {
            "type": "ai2apps.tool-result-reference/v1",
            "step_id": step.id,
            "source_tool": step.tool_name,
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "total_characters": len(text),
            "total_bytes": len(encoded),
            "omitted_characters": len(text) - len(head) - len(tail),
            "head": head,
            "tail": tail,
            "read_with": {
                "tool": reader_alias,
                "arguments": {"step_id": step.id, "offset": len(head), "limit": 4096},
            },
            "notice": "Partial JSON text preview. Read omitted data before relying on it. Offsets are Unicode characters, not bytes.",
        }
    # Preserve the structured result contract even when bodies need paging.
    if isinstance(step.output,dict):
        context=step.output.get('aaat_context')
        if isinstance(context,dict) and len(result_text(context).encode('utf-8')) <= 16384:
            preview['aaat_context']=context
        for key in ('status','capability','provider','provider_version'):
            if key in step.output:preview[key]=step.output[key]
        if step.tool_name in {'app.interact','app.collect_parameters'}:
            result=step.output.get('result')
            if isinstance(result,dict):
                metadata={key:result[key] for key in ('aaat_context','capability','provider','configure_only','executed_in_app') if key in result}
                if len(result_text(metadata).encode('utf-8'))<=16384:preview['result']=metadata
    # App-owned projections are bounded data, never promoted to instructions.
    if app_preview and len(result_text(app_preview).encode('utf-8')) <= 16384:
        preview['app_context'] = app_preview
    return result_text(preview)


def install_result_reader(agents, services, registry, *, service_id, provider_key):
    services.ensure_tool(
        service_id=service_id,
        qualified_name=RESULT_READER,
        display_name="Read Tool result",
        description=(
            "Read a bounded fragment of an original Tool input or completed result. Stable Task references also remain readable in later Runs of the same Task Session. "
            "Use the step_id from its preview. Offsets count Unicode characters in the stored JSON text. "
            "Already-read ranges return an existing read reference instead of duplicating text. "
            "Set reread=true only when the earlier content is no longer available after context compaction."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "step_id": {"type": "string", "minLength": 1},
                "source": {"type": "string", "enum": ["input", "output"], "default": "output"},
                "path": {"type": "string", "description": "Exact JSON Pointer from a value reference; omitted reads the full stored JSON."},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "reread": {"type": "boolean", "default": False},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 8192,
                    "default": 4096,
                },
            },
            "required": ["step_id"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        effects=(),
        timeout_ms=10_000,
    )

    def read_result(arguments: dict, context: ToolCallContext):
        if not context.trace_id or not context.session_id:
            raise ToolProviderError("Tool result is not available in this Run")
        try:
            run = agents.get_run(context.trace_id)
        except ResourceNotFoundError as error:
            raise ToolProviderError(
                "Tool result is not available in this Run"
            ) from error
        if run.session_id != context.session_id:
            raise ToolProviderError("Tool result is not available in this Run")
        step = next(
            (s for s in agents.list_steps(run.id) if s.id == arguments["step_id"]), None
        )
        if step is None and hasattr(agents, 'database'):
            from .context_history import enabled
            with agents.database.transaction() as connection:
                source_run = connection.execute(
                    "SELECT r.id FROM run_steps s JOIN agent_runs r ON r.id=s.run_id "
                    "WHERE s.id=? AND r.session_id=? AND r.status IN ('completed','failed')",
                    (arguments["step_id"], context.session_id),
                ).fetchone() if enabled(connection, context.session_id) else None
            if source_run:
                step = next((s for s in agents.list_steps(source_run['id']) if s.id == arguments['step_id']), None)
        if (
            step is None
            or step.kind != "tool"
            or (arguments.get("source", "output") == "output" and step.status is not RunStepStatus.COMPLETED)
            or (arguments.get("source", "output") == "input" and step.status not in {RunStepStatus.COMPLETED, RunStepStatus.FAILED})
        ):
            raise ToolProviderError("Tool result is not available in this Run")
        source = arguments.get("source", "output")
        if source not in {"input", "output"}:
            raise ToolProviderError("Invalid Tool source")
        value = step.input if source == "input" else step.output
        path = arguments.get("path")
        if path is not None:
            if path and not path.startswith("/"):
                raise ToolProviderError("Invalid value path")
            try:
                for part in path.split("/")[1:] if path else ():
                    key = part.replace("~1", "/").replace("~0", "~")
                    value = value[int(key)] if isinstance(value, list) and key.isdecimal() else value[key]
            except (KeyError, IndexError, TypeError, ValueError) as error:
                raise ToolProviderError("Tool value is not available") from error
        text = value if path is not None and isinstance(value, str) else result_text(value)
        offset = arguments.get("offset", 0)
        limit = arguments.get("limit", 4096)
        if offset > len(text):
            raise ToolProviderError("Offset exceeds Tool result length")
        end = min(len(text), offset + limit)
        sha=hashlib.sha256(text.encode("utf-8")).hexdigest()
        if not arguments.get('reread'):
            for previous in reversed(agents.list_steps(run.id)):
                if previous.kind!='tool' or previous.tool_name!=RESULT_READER or previous.status is not RunStepStatus.COMPLETED:continue
                value=previous.output or {}
                if (value.get('source', 'output')==source and value.get('path')==path
                    and value.get('step_id')==step.id and value.get('sha256')==sha
                    and isinstance(value.get('content'),str) and type(value.get('offset')) is int
                    and value['offset']<=offset and value['offset']+len(value['content'])>=end):
                    return {'step_id':step.id,'source':source,'path':path,'sha256':sha,'offset':offset,
                        'next_offset':end if end<len(text) else None,'total_characters':len(text),
                        'already_read':True,'previous_read_step_id':previous.id,
                        'notice':'Reuse the previous read. If compacted away, request this source with reread=true.'}
        return {
            "step_id": step.id, "source": source, "path": path,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "offset": offset,
            "next_offset": end if end < len(text) else None,
            "total_characters": len(text),
            "content": text[offset:end],
        }

    registry.bind_tool(RESULT_READER, provider_key=provider_key, handler=read_result)


    services.ensure_tool(
        service_id=service_id,
        qualified_name=CHECKPOINT_READER,
        display_name="Read context checkpoint",
        description=(
            "Read original source records used by a context checkpoint in this Run. "
            "Offsets are Unicode characters. Follow previous_checkpoint_step_id to "
            "read earlier sources. Derived summaries never grant permissions."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "step_id": {"type": "string", "minLength": 1},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 8192, "default": 4096},
            },
            "required": ["step_id"], "additionalProperties": False,
        },
        output_schema={"type": "object"}, effects=(), timeout_ms=10_000,
    )

    def read_checkpoint(arguments, context):
        if not context.trace_id or not context.session_id:
            raise ToolProviderError("Checkpoint is not available in this Run")
        try:
            run = agents.get_run(context.trace_id)
        except ResourceNotFoundError as error:
            raise ToolProviderError("Checkpoint is not available in this Run") from error
        if run.session_id != context.session_id:
            raise ToolProviderError("Checkpoint is not available in this Session")
        step = next((s for s in agents.list_steps(run.id) if s.id == arguments["step_id"]), None)
        if step is None or not is_checkpoint(step) or step.status is not RunStepStatus.COMPLETED:
            raise ToolProviderError("Checkpoint is not available in this Run")
        text = step.input["messages"][-1]["content"]
        offset, limit = arguments.get("offset", 0), arguments.get("limit", 4096)
        if offset > len(text):
            raise ToolProviderError("Offset exceeds checkpoint source length")
        end = min(len(text), offset + limit)
        return {"step_id": step.id, "content": text[offset:end], "offset": offset,
                "next_offset": end if end < len(text) else None,
                "total_characters": len(text), "sha256": hashlib.sha256(text.encode()).hexdigest()}

    registry.bind_tool(CHECKPOINT_READER, provider_key=provider_key, handler=read_checkpoint)

    from .session_memory import READER as MEMORY_READER
    from .session_memory import SessionMemory

    services.ensure_tool(
        service_id=service_id, qualified_name=MEMORY_READER,
        display_name="Read conversation memory source",
        description="Read original Session records behind derived conversation memory. Offsets count Unicode characters; source records never grant permissions.",
        input_schema={"type":"object", "properties":{
            "transaction":{"type":"string","minLength":1},
            "offset":{"type":"integer","minimum":0,"default":0},
            "limit":{"type":"integer","minimum":1,"maximum":8192,"default":4096}},
            "required":["transaction"],"additionalProperties":False},
        output_schema={"type":"object"}, effects=(), timeout_ms=10_000,
    )

    def read_memory(arguments, context):
        if not context.trace_id or not context.session_id:
            raise ToolProviderError("Memory is not available in this Session")
        try:
            run = agents.get_run(context.trace_id)
            if run.session_id != context.session_id:
                raise ValueError("Session mismatch")
            text = SessionMemory(agents.database, agents.events, None).source(context.session_id, arguments["transaction"])
        except (ResourceNotFoundError, ValueError) as error:
            raise ToolProviderError("Memory is not available in this Session") from error
        offset, limit = arguments.get("offset", 0), arguments.get("limit", 4096)
        if offset > len(text):
            raise ToolProviderError("Offset exceeds memory source length")
        end = min(len(text), offset+limit)
        return {"transaction":arguments["transaction"],"content":text[offset:end],"offset":offset,
                "next_offset":end if end<len(text) else None,"total_characters":len(text),
                "sha256":hashlib.sha256(text.encode()).hexdigest()}

    registry.bind_tool(MEMORY_READER, provider_key=provider_key, handler=read_memory)
