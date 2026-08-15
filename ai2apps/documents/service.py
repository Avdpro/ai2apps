"""Read-only attachment and document tools for Agents."""

from __future__ import annotations

import asyncio
import base64

from ai2apps.services import (
    ServiceInstanceStatus,
    ServiceRegistry,
    ServiceRepository,
    ServiceRuntimeMode,
    ToolCallContext,
    ToolProviderError,
)
from ai2apps.workspace import WorkspaceRepository

from .pdf_generator import PdfGenerator
from .repository import DocumentRepository


def install_document_service(
    documents: DocumentRepository,
    workspace: WorkspaceRepository,
    repository: ServiceRepository,
    registry: ServiceRegistry,
) -> None:
    pdf_generator = PdfGenerator()
    service = repository.ensure_service(
        service_key="ai2apps.documents",
        package_id="ai2apps.documents",
        package_version="1.0.0",
        display_name="AI2Apps Documents",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
        capabilities=("attachments", "documents"),
    )
    instance = repository.ensure_instance(
        service_id=service.id,
        provider_key="builtin:documents",
        status=ServiceInstanceStatus.RUNNING,
        endpoint="/v1/platform/sessions/{session_id}/attachments",
        health={"status": "ok"},
    )

    def session(context: ToolCallContext) -> str:
        if context.session_id is None:
            raise ToolProviderError("Document Tools require a Session")
        return context.session_id

    def attachment_json(item):
        return {
            "id": item.id,
            "filename": item.filename,
            "media_type": item.media_type,
            "size_bytes": item.size_bytes,
            "sha256": item.sha256,
            "status": item.status.value,
            "error": item.error,
            "metadata": item.metadata,
        }

    def block_json(item):
        return {
            "id": item.id,
            "ordinal": item.ordinal,
            "kind": item.kind,
            "text": item.text,
            "page": item.page,
            "section": item.section,
            "sheet": item.sheet,
            "slide": item.slide,
            "cell_range": item.cell_range,
            "metadata": item.metadata or {},
        }

    async def attachment_list(_arguments, context):
        return {
            "items": [
                attachment_json(item) for item in documents.list(session(context))
            ]
        }

    async def attachment_status(arguments, context):
        return attachment_json(
            documents.get(session(context), arguments["attachment_id"])
        )

    async def document_read(arguments, context):
        items = documents.blocks(
            session(context),
            arguments["attachment_id"],
            offset=arguments.get("offset", 0),
            limit=arguments.get("limit", 50),
        )
        return {"items": [block_json(item) for item in items]}

    async def document_info(arguments, context):
        item = documents.get(session(context), arguments["attachment_id"])
        blocks = documents.blocks(session(context), item.id, limit=200)
        return {
            **attachment_json(item),
            "block_count_at_least": len(blocks),
            "locations": sorted(
                {
                    key
                    for block in blocks
                    for key, value in {
                        "page": block.page,
                        "slide": block.slide,
                        "sheet": block.sheet,
                        "section": block.section,
                        "cell_range": block.cell_range,
                    }.items()
                    if value is not None
                }
            ),
        }

    async def document_preview(arguments, context):
        limit = arguments.get("max_chars", 8000)
        blocks = documents.blocks(
            session(context), arguments["attachment_id"], limit=20
        )
        text = "\n\n".join(item.text for item in blocks)
        return {
            "text": text[:limit],
            "truncated": len(text) > limit,
            "blocks": len(blocks),
        }

    async def document_search(arguments, context):
        items = documents.search(
            session(context),
            arguments["attachment_id"],
            arguments["query"],
            limit=arguments.get("limit", 20),
        )
        return {
            "items": [block_json(item) for item in items],
            "query": arguments["query"],
        }

    async def document_create_pdf(arguments, context):
        session_id = session(context)
        await context.report_progress("Laying out PDF", progress=0.2)
        generated = await asyncio.to_thread(
            pdf_generator.generate,
            arguments["content"],
            title=arguments.get("title", "Document"),
            author=arguments.get("author", "AI2Apps"),
            page_size=arguments.get("page_size", "a4"),
            header=arguments.get("header"),
            footer=arguments.get("footer"),
        )
        output_path = arguments.get("output_path", "output/pdf/document.pdf")
        if not output_path.lower().endswith(".pdf"):
            raise ToolProviderError("PDF output_path must end with .pdf")
        await context.report_progress("Saving and verifying PDF", progress=0.75)
        written = workspace.write(
            session_id,
            output_path,
            base64.b64encode(generated.data).decode("ascii"),
            encoding="base64",
        )
        artifact = workspace.create_artifact(
            session_id,
            output_path,
            arguments.get("artifact_name"),
            run_id=(
                context.trace_id
                if context.trace_id and context.trace_id.startswith("run_")
                else None
            ),
            media_type="application/pdf",
            metadata={
                "generator": "ai2apps.documents.pdf",
                "generator_version": pdf_generator.version,
                "pages": generated.pages,
                "render_checked": generated.render_checked,
                "font": generated.font,
            },
        )
        await context.report_progress("PDF artifact ready", progress=1.0)
        return {
            "path": written["path"],
            "artifact": {
                "id": artifact.id,
                "uri": artifact.uri,
                "name": artifact.name,
                "media_type": artifact.media_type,
                "content_hash": artifact.content_hash,
                "size_bytes": artifact.size_bytes,
            },
            "pages": generated.pages,
            "extracted_chars": generated.extracted_chars,
            "render_checked": generated.render_checked,
            "font": generated.font,
        }

    definitions = (
        (
            "attachment.list",
            "List attachments",
            "List the files attached to this Session.",
            {"type": "object", "properties": {}, "additionalProperties": False},
            attachment_list,
        ),
        (
            "attachment.status",
            "Attachment status",
            "Inspect attachment metadata and parsing status.",
            {
                "type": "object",
                "properties": {"attachment_id": {"type": "string"}},
                "required": ["attachment_id"],
                "additionalProperties": False,
            },
            attachment_status,
        ),
        (
            "document.read",
            "Read document",
            "Read ordered structured blocks from an attached document. Blocks include page, slide, sheet, section, and cell coordinates when available.",
            {
                "type": "object",
                "properties": {
                    "attachment_id": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                },
                "required": ["attachment_id"],
                "additionalProperties": False,
            },
            document_read,
        ),
        (
            "document.info",
            "Document information",
            "Inspect parsed document status, metadata, and available source-location types.",
            {
                "type": "object",
                "properties": {"attachment_id": {"type": "string"}},
                "required": ["attachment_id"],
                "additionalProperties": False,
            },
            document_info,
        ),
        (
            "document.preview",
            "Preview document",
            "Read a short bounded preview of an attached document.",
            {
                "type": "object",
                "properties": {
                    "attachment_id": {"type": "string"},
                    "max_chars": {"type": "integer", "minimum": 100, "maximum": 20000},
                },
                "required": ["attachment_id"],
                "additionalProperties": False,
            },
            document_preview,
        ),
        (
            "document.search",
            "Search document",
            "Search text inside one attached document and return source-located blocks.",
            {
                "type": "object",
                "properties": {
                    "attachment_id": {"type": "string"},
                    "query": {"type": "string", "minLength": 1},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": ["attachment_id", "query"],
                "additionalProperties": False,
            },
            document_search,
        ),
        (
            "document.create_pdf",
            "Create PDF",
            "Create a polished PDF Artifact from Markdown or plain text. Supports headings, paragraphs, lists, code blocks, tables, page breaks, headers, footers, page numbers, and multilingual text. The result is structurally verified and rendered when Poppler is available.",
            {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "minLength": 1, "maxLength": 500000},
                    "title": {"type": "string", "maxLength": 200},
                    "author": {"type": "string", "maxLength": 120},
                    "page_size": {"enum": ["a4", "letter"]},
                    "header": {"type": "string", "maxLength": 100},
                    "footer": {"type": "string", "maxLength": 100},
                    "output_path": {"type": "string", "maxLength": 512},
                    "artifact_name": {"type": "string", "maxLength": 255},
                },
                "required": ["content"],
                "additionalProperties": False,
            },
            document_create_pdf,
        ),
    )
    for name, title, description, schema, handler in definitions:
        is_pdf_create = name == "document.create_pdf"
        repository.ensure_tool(
            service_id=service.id,
            qualified_name=name,
            display_name=title,
            description=description,
            input_schema=schema,
            output_schema={"type": "object"},
            effects=("write",) if is_pdf_create else (),
            required_capabilities=(
                ("workspace.write", "artifact.create") if is_pdf_create else ()
            ),
            timeout_ms=120_000 if is_pdf_create else 30_000,
        )
        registry.bind_tool(name, provider_key=instance.provider_key, handler=handler)
