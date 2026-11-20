"""Replace static PDF labels while leaving the AcroForm and its appearances intact."""
from dataclasses import dataclass
from io import BytesIO
import re

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.utils import simpleSplit

from ai2apps.documents.pdf_generator import PdfGenerator

SHOW = {b'Tj', b'TJ', b"'", b'"'}


@dataclass
class Label:
    operators: list[int]
    text: str
    x: float
    y: float
    size: float
    width: float
    lines: int = 1


class FormLayout:
    def __init__(self, data):
        import pdfplumber

        self.data = data
        self.labels = []
        self.pages = []
        try:
            pdf = PdfReader(BytesIO(data))
            fields = pdf.get_fields() or {}
            if (not fields or len(pdf.pages) > 100 or pdf.trailer['/Root']['/AcroForm'].get('/XFA')
                    or any(field.get('/FT') == '/Sig' and field.get('/V') for field in fields.values())):
                raise ValueError('需要带可填写字段的 PDF，不支持 XFA 或已签名表单 / Use an unsigned AcroForm PDF.')
            with pdfplumber.open(BytesIO(data)) as geometry:
                for page, metrics in zip(pdf.pages, geometry.pages, strict=True):
                    labels = self._labels(page, metrics)
                    self.pages.append(labels)
                    self.labels.extend(labels)
        except ValueError:
            raise
        except Exception as error:
            raise ValueError('无法读取 PDF 表单 / Could not read the PDF form.') from error
        if not self.labels:
            raise ValueError('找不到可替换的表单标签 / No replaceable PDF form labels found.')

    @staticmethod
    def _labels(page, metrics):
        # The main content stream contains static labels. Widget appearances
        # and field values stay in the original PDF and are never extracted.
        operator, labels, callbacks = -1, [], {}
        if page.rotation or float(page.mediabox.left) or float(page.mediabox.bottom):
            raise ValueError('不支持旋转或偏移页面 / Rotated or offset pages are unsupported.')

        def operand(op, args, cm, tm):
            nonlocal operator
            operator += 1

        def visit(text, cm, tm, font, size):
            if text.strip() and operator >= 0:
                callbacks.setdefault(operator, []).append((text.strip(), cm[:], tm[:], size))

        page.extract_text(visitor_operand_before=operand, visitor_text=visit)
        content = page.get_contents()
        if content is None:
            return []
        for index, (args, op) in enumerate(content.operations):
            if op not in {b'Tj', b'TJ'}:
                continue
            following = index + 1
            if following >= len(content.operations) or content.operations[following][1] not in {b'ET', b'T*'}:
                continue
            results = callbacks.get(following, [])
            if len(results) != 1:
                continue
            text, cm, tm, size = results[0]
            if (not any(char.isalpha() for char in text) or cm[1] or cm[2] or tm[1] or tm[2]
                    or cm[0] * tm[0] <= 0 or cm[3] * tm[3] <= 0):
                continue
            x = cm[0] * tm[4] + cm[4]
            y = cm[3] * tm[5] + cm[5]
            size = cm[3] * tm[3] * size
            if size <= 0:
                continue
            labels.append(Label([index], text, x, y, size, 0))
        if not labels:
            return []
        height = float(page.mediabox.height)
        edges = [edge['x1'] for edge in metrics.edges if edge['x1'] < metrics.width - 15]
        right = max(edges, default=metrics.width - 24)
        widgets = [list(map(float, item.get_object()['/Rect'])) for item in page.get('/Annots', [])
                   if item.get_object().get('/Subtype') == '/Widget']
        for label in labels:
            top = height - label.y
            limits = [right, float(page.mediabox.width) - 12]
            limits.extend(peer.x - 3 for peer in labels if peer.x > label.x + 4 and abs(peer.y - label.y) < 3)
            limits.extend(x0 - 2 for x0, y0, _, y1 in widgets if x0 > label.x + 5 and y0 - 2 <= label.y <= y1 + 2)
            limits.extend(edge['x0'] - 1 for edge in metrics.horizontal_edges
                          if edge['x0'] > label.x + 5 and abs(edge['top'] - top) < 4)
            limits.extend(edge['x0'] - 2 for edge in metrics.vertical_edges
                          if edge['x0'] > label.x + 5 and edge['top'] <= top <= edge['bottom'])
            if re.fullmatch(r'[（(]日[）)]/[（(]月[）)]/[（(]年[）)]', label.text):
                # Date hints sit below the fill line, outside the widget text.
                limits = [max(min(limits), label.x + 55)]
            label.width = max(7, min(limits) - label.x)
        # Group adjacent prose lines of matching size. Short labels and
        # labels beside fields stay separate so their anchors cannot move.
        groups = []
        for label in sorted(labels, key=lambda item: (-item.y, item.x)):
            previous = next((item for item in reversed(groups)
                             if abs(item.x - label.x) < 14
                             and abs(item.size - label.size) < .5
                             and item.size * .95 <= (item.y - label.y) / item.lines <= item.size * 1.28
                             and len(item.text) > 30 and label.width > 220
                             and not re.match(r'^[●•*]', label.text)), None)
            if previous:
                previous.text += (' ' if previous.text[-1].isascii() and label.text[0].isascii() else '') + label.text
                previous.operators.extend(label.operators)
                previous.lines += 1
            else:
                groups.append(label)
        return groups

    def passages(self):
        # Reuse identical labels, including checkbox labels, throughout.
        return list(dict.fromkeys(label.text for label in self.labels))

    def render(self, translated, language):
        values = dict(zip(self.passages(), translated, strict=True))
        writer = PdfWriter(clone_from=PdfReader(BytesIO(self.data)))
        font = ('Helvetica' if language in {'en','fr','de','es','pt-BR'} else PdfGenerator._register_font())
        for page, labels in zip(writer.pages, self.pages, strict=True):
            if not labels:
                continue
            removed = {operator for label in labels for operator in label.operators}
            stream = ContentStream(page.get_contents(), writer)
            stream.operations = [(args, op) for index, (args, op) in enumerate(stream.operations)
                                 if index not in removed or op not in SHOW]
            page.replace_contents(stream)
            buffer = BytesIO()
            canvas = Canvas(buffer, pagesize=(float(page.mediabox.width), float(page.mediabox.height)))
            for label in labels:
                value = ' '.join(values[label.text].split())
                size = label.size
                if label.lines > 1:
                    lines = simpleSplit(value, font, size, label.width)
                    while len(lines) > label.lines and size > 4:
                        size -= .25
                        lines = simpleSplit(value, font, size, label.width)
                else:
                    lines = [value]
                if len(lines) > label.lines:
                    raise ValueError('译文无法放入原标签区域，请缩短译文 / Translation does not fit the original label area.')
                for index, line in enumerate(lines):
                    text = canvas.beginText(label.x, label.y - index * label.size * 1.16)
                    natural = stringWidth(line, font, size)
                    fitted = max(size * .72, min(size, size * label.width / max(natural, 1)))
                    text.setFont(font, fitted)
                    natural = stringWidth(line, font, fitted)
                    if natural > label.width:
                        text.setHorizScale(100 * label.width / natural)
                    text.textOut(line)
                    canvas.drawText(text)
            canvas.showPage()
            canvas.save()
            page.merge_page(PdfReader(BytesIO(buffer.getvalue())).pages[0])
        output = BytesIO()
        writer.write(output)
        return output.getvalue()
