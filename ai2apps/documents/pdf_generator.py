"""Polished, bounded Markdown/text to PDF generation with verification."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

MAX_PDF_SOURCE_CHARS = 500_000
_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


@dataclass(frozen=True, slots=True)
class PdfGenerationResult:
    data: bytes
    pages: int
    extracted_chars: int
    render_checked: bool
    font: str


class PdfGenerator:
    version = "1"

    def __init__(self) -> None:
        self.font_name = self._register_font()

    @staticmethod
    def _register_font() -> str:
        for candidate in _FONT_CANDIDATES:
            path = Path(candidate)
            if not path.is_file():
                continue
            try:
                pdfmetrics.registerFont(TTFont("AI2AppsUnicode", str(path)))
                return "AI2AppsUnicode"
            except Exception:
                continue
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        return "STSong-Light"

    def generate(
        self,
        source: str,
        *,
        title: str = "Document",
        author: str = "AI2Apps",
        page_size: str = "a4",
        header: str | None = None,
        footer: str | None = None,
    ) -> PdfGenerationResult:
        if not source.strip():
            raise ValueError("PDF source must not be empty")
        if len(source) > MAX_PDF_SOURCE_CHARS:
            raise ValueError("PDF source exceeds the 500,000 character limit")
        pagesize = A4 if page_size.lower() == "a4" else LETTER
        with tempfile.TemporaryDirectory(prefix="ai2apps-pdf-") as temporary:
            output = Path(temporary) / "document.pdf"
            self._build(
                output,
                source,
                title=title.strip() or "Document",
                author=author.strip() or "AI2Apps",
                pagesize=pagesize,
                header=header,
                footer=footer,
            )
            pages, extracted_chars = self._verify_structure(output)
            render_checked = self._verify_render(output, Path(temporary))
            return PdfGenerationResult(
                data=output.read_bytes(),
                pages=pages,
                extracted_chars=extracted_chars,
                render_checked=render_checked,
                font=self.font_name,
            )

    def _styles(self):
        base = getSampleStyleSheet()
        ink = colors.HexColor("#172033")
        muted = colors.HexColor("#64748B")
        return {
            "body": ParagraphStyle(
                "AI2Body",
                parent=base["BodyText"],
                fontName=self.font_name,
                fontSize=10.5,
                leading=16,
                textColor=ink,
                spaceAfter=7,
            ),
            "title": ParagraphStyle(
                "AI2Title",
                parent=base["Title"],
                fontName=self.font_name,
                fontSize=25,
                leading=31,
                alignment=TA_LEFT,
                textColor=colors.HexColor("#0F172A"),
                spaceAfter=14,
            ),
            "h1": ParagraphStyle(
                "AI2H1",
                parent=base["Heading1"],
                fontName=self.font_name,
                fontSize=18,
                leading=24,
                textColor=colors.HexColor("#0F3D67"),
                spaceBefore=14,
                spaceAfter=8,
            ),
            "h2": ParagraphStyle(
                "AI2H2",
                parent=base["Heading2"],
                fontName=self.font_name,
                fontSize=14,
                leading=19,
                textColor=colors.HexColor("#155E75"),
                spaceBefore=11,
                spaceAfter=6,
            ),
            "h3": ParagraphStyle(
                "AI2H3",
                parent=base["Heading3"],
                fontName=self.font_name,
                fontSize=11.5,
                leading=16,
                textColor=colors.HexColor("#334155"),
                spaceBefore=8,
                spaceAfter=4,
            ),
            "code": ParagraphStyle(
                "AI2Code",
                parent=base["Code"],
                fontName="Courier",
                fontSize=8.3,
                leading=11,
                leftIndent=7,
                rightIndent=7,
                borderColor=colors.HexColor("#CBD5E1"),
                borderWidth=0.5,
                borderPadding=7,
                backColor=colors.HexColor("#F8FAFC"),
                spaceBefore=4,
                spaceAfter=9,
            ),
            "caption": ParagraphStyle(
                "AI2Caption",
                parent=base["BodyText"],
                fontName=self.font_name,
                fontSize=8.5,
                leading=11,
                textColor=muted,
                alignment=TA_CENTER,
            ),
        }

    def _build(
        self,
        output: Path,
        source: str,
        *,
        title: str,
        author: str,
        pagesize,
        header,
        footer,
    ) -> None:
        styles = self._styles()
        story = [Paragraph(self._inline(title), styles["title"]), Spacer(1, 2 * mm)]
        story.extend(self._markdown_flowables(source, styles))
        document = SimpleDocTemplate(
            str(output),
            pagesize=pagesize,
            rightMargin=19 * mm,
            leftMargin=19 * mm,
            topMargin=20 * mm,
            bottomMargin=19 * mm,
            title=title,
            author=author,
            subject="Generated by AI2Apps",
        )

        def decorate(canvas, doc):
            canvas.saveState()
            canvas.setFont(self.font_name, 8)
            canvas.setFillColor(colors.HexColor("#64748B"))
            width, height = pagesize
            if header:
                canvas.drawString(19 * mm, height - 11 * mm, str(header)[:100])
            footer_text = str(footer or title)[:90]
            canvas.drawString(19 * mm, 10 * mm, footer_text)
            canvas.drawRightString(width - 19 * mm, 10 * mm, f"{doc.page}")
            canvas.restoreState()

        document.build(story, onFirstPage=decorate, onLaterPages=decorate)

    def _markdown_flowables(self, source: str, styles) -> list:
        lines = source.replace("\r\n", "\n").split("\n")
        result: list = []
        paragraph: list[str] = []
        bullets: list[str] = []
        code: list[str] = []
        in_code = False

        def flush_paragraph():
            if paragraph:
                result.append(
                    Paragraph(self._inline(" ".join(paragraph)), styles["body"])
                )
                paragraph.clear()

        def flush_bullets():
            if bullets:
                result.append(
                    ListFlowable(
                        [
                            ListItem(Paragraph(self._inline(item), styles["body"]))
                            for item in bullets
                        ],
                        bulletType="bullet",
                        leftIndent=16,
                        bulletFontName=self.font_name,
                    )
                )
                result.append(Spacer(1, 3 * mm))
                bullets.clear()

        index = 0
        while index < len(lines):
            line = lines[index]
            if line.strip().startswith("```"):
                flush_paragraph()
                flush_bullets()
                if in_code:
                    result.append(Preformatted("\n".join(code), styles["code"]))
                    code.clear()
                in_code = not in_code
                index += 1
                continue
            if in_code:
                code.append(line)
                index += 1
                continue
            if self._is_table(lines, index):
                flush_paragraph()
                flush_bullets()
                table_lines = [line]
                index += 2
                while (
                    index < len(lines) and "|" in lines[index] and lines[index].strip()
                ):
                    table_lines.append(lines[index])
                    index += 1
                result.append(self._table(table_lines, styles))
                continue
            heading = re.match(r"^(#{1,3})\s+(.+)$", line)
            if heading:
                flush_paragraph()
                flush_bullets()
                result.append(
                    Paragraph(
                        self._inline(heading.group(2)),
                        styles[f"h{len(heading.group(1))}"],
                    )
                )
            elif re.match(r"^\s*[-*+]\s+", line):
                flush_paragraph()
                bullets.append(re.sub(r"^\s*[-*+]\s+", "", line))
            elif line.strip() == "---":
                flush_paragraph()
                flush_bullets()
                result.append(PageBreak())
            elif not line.strip():
                flush_paragraph()
                flush_bullets()
            else:
                paragraph.append(line.strip())
            index += 1
        flush_paragraph()
        flush_bullets()
        if code:
            result.append(Preformatted("\n".join(code), styles["code"]))
        return result

    @staticmethod
    def _is_table(lines: list[str], index: int) -> bool:
        return (
            index + 1 < len(lines)
            and "|" in lines[index]
            and bool(re.match(r"^\s*\|?\s*:?-{3,}", lines[index + 1]))
        )

    def _table(self, lines: list[str], styles):
        rows = [
            [
                Paragraph(self._inline(cell.strip()), styles["body"])
                for cell in line.strip().strip("|").split("|")
            ]
            for line in lines
        ]
        table = Table(rows, repeatRows=1, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#172033")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return KeepTogether([table, Spacer(1, 4 * mm)])

    @staticmethod
    def _inline(value: str) -> str:
        text = escape(value)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", text)
        text = re.sub(
            r"\[([^\]]+)\]\((https?://[^)]+)\)",
            r'<a href="\2" color="#0369A1">\1</a>',
            text,
        )
        return text

    @staticmethod
    def _verify_structure(path: Path) -> tuple[int, int]:
        reader = PdfReader(str(path))
        if not reader.pages:
            raise RuntimeError("Generated PDF contains no pages")
        extracted = "".join(page.extract_text() or "" for page in reader.pages)
        if not extracted.strip():
            raise RuntimeError("Generated PDF contains no extractable text")
        return len(reader.pages), len(extracted)

    @staticmethod
    def _verify_render(path: Path, directory: Path) -> bool:
        renderer = shutil.which("pdftoppm")
        if renderer is None:
            return False
        prefix = directory / "render"
        completed = subprocess.run(
            [renderer, "-png", "-r", "96", str(path), str(prefix)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"PDF render verification failed: {completed.stderr.decode(errors='replace')[:500]}"
            )
        pages = sorted(directory.glob("render-*.png"))
        if not pages or any(item.stat().st_size < 1000 for item in pages):
            raise RuntimeError("PDF render verification produced invalid pages")
        return True
