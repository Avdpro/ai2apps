"""Durable attachment, parsing, and Session isolation contracts."""

from __future__ import annotations

import pytest

from ai2apps.chat import ChatRepository
from ai2apps.config import PlatformConfig
from ai2apps.documents import DocumentRepository, DocumentStatus, PdfGenerator
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.services import ToolCallContext


def _runtime_and_sessions(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    chat = ChatRepository(runtime.database, runtime.events)
    first, _ = chat.create_thread(title="first")
    second, _ = chat.create_thread(title="second")
    return runtime, first.session.id, second.session.id


def test_attachment_blob_is_deduplicated_but_access_is_session_scoped(tmp_path):
    runtime, first, second = _runtime_and_sessions(tmp_path)
    documents = runtime.documents
    assert isinstance(documents, DocumentRepository)

    one = documents.create(
        first,
        filename="notes.md",
        media_type="text/markdown",
        data=b"# Plan\n\nalpha beta",
    )
    two = documents.create(
        second,
        filename="copy.md",
        media_type="text/markdown",
        data=b"# Plan\n\nalpha beta",
    )

    assert one.blob_id == two.blob_id
    assert one.id != two.id
    with runtime.database.connect() as connection:
        assert (
            connection.execute("SELECT count(*) FROM document_blobs").fetchone()[0] == 1
        )
    try:
        documents.get(first, two.id)
    except Exception as exc:
        assert "attachment not found" in str(exc)
    else:
        raise AssertionError("cross-Session attachment access was allowed")


def test_text_document_parses_into_source_blocks_and_is_searchable(tmp_path):
    runtime, session_id, _ = _runtime_and_sessions(tmp_path)
    record = runtime.documents.create(
        session_id,
        filename="research.txt",
        media_type="text/plain",
        data=b"First paragraph.\n\nSecond paragraph has tornado data.",
    )
    parsed = runtime.documents.parse(session_id, record.id)
    assert parsed.status is DocumentStatus.READY
    blocks = runtime.documents.blocks(session_id, record.id)
    assert [item.ordinal for item in blocks] == [0, 1]
    matches = runtime.documents.search(session_id, record.id, "TORNADO")
    assert len(matches) == 1
    assert "tornado" in matches[0].text


def test_xlsx_document_preserves_sheet_and_cell_coordinates(tmp_path):
    from openpyxl import Workbook

    runtime, session_id, _ = _runtime_and_sessions(tmp_path)
    source = tmp_path / "metrics.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Decode"
    sheet.append(["scope", "tps"])
    sheet.append(["code", 31.5])
    workbook.save(source)
    workbook.close()

    record = runtime.documents.create(
        session_id,
        filename=source.name,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        data=source.read_bytes(),
    )
    parsed = runtime.documents.parse(session_id, record.id)
    assert parsed.status is DocumentStatus.READY
    blocks = runtime.documents.blocks(session_id, record.id)
    assert blocks[1].sheet == "Decode"
    assert blocks[1].cell_range == "A2:B2"
    assert "31.5" in blocks[1].text


def test_pdf_generator_supports_multilingual_markdown_and_verifies_output():
    result = PdfGenerator().generate(
        """# 中文报告

This is **bold** text.

- 第一项
- Second item

| 指标 | 数值 |
|---|---|
| TPS | 31.5 |
""",
        title="AI2Apps 测试报告",
        header="Local document engine",
    )
    assert result.data.startswith(b"%PDF-")
    assert result.pages == 1
    assert result.extracted_chars > 20
    assert result.font


@pytest.mark.asyncio
async def test_create_pdf_tool_writes_workspace_and_registers_artifact(tmp_path):
    runtime, session_id, _ = _runtime_and_sessions(tmp_path)
    result = await runtime.tools.execute(
        "document.create_pdf",
        {
            "content": "# Benchmark\n\n| Engine | TPS |\n|---|---|\n| Arena | 31.5 |",
            "title": "Qwen Report",
            "output_path": "output/pdf/qwen-report.pdf",
        },
        context=ToolCallContext(
            caller_id="agent:ai2apps.general-agent",
            session_id=session_id,
            granted_capabilities=frozenset({"workspace.write", "artifact.create"}),
        ),
    )
    assert result.output["pages"] == 1
    assert result.output["artifact"]["media_type"] == "application/pdf"
    workspace_pdf = runtime.workspace.read(
        session_id, "output/pdf/qwen-report.pdf", limit=1024 * 1024
    )
    assert workspace_pdf["encoding"] == "base64"
    assert workspace_pdf["bytes_returned"] > 1000
