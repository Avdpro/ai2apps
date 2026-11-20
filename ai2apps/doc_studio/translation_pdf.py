"""Reflow searchable papers while retaining visual regions from the source."""
from dataclasses import dataclass
from io import BytesIO
from xml.sax.saxutils import escape
import re
import statistics
from itertools import groupby
from threading import Lock

from ai2apps.documents.pdf_generator import PdfGenerator

_RENDER_LOCK = Lock()
CAPTION = re.compile(r'^(?:Fig(?:ure)?\.?|Table)\s+\d+', re.I)
SECTION = re.compile(r'^(?:\d+(?:\.\d+)*\.?\s+[A-Z]|[IVX]+\.\s+[A-Z]|Abstract\b|References\s*$|Acknowledg)')
FORMULA = re.compile(r'^(?:.{0,20}\s=\s|[∑∫∏√])|\([0-9]+\)\s*$')


@dataclass
class Block:
    kind: str
    text: str
    page: int
    box: tuple
    wide: bool = False


def bounds(items):
    return (min(item['x0'] for item in items), min(item['top'] for item in items),
            max(item['x1'] for item in items), max(item['bottom'] for item in items))


def line_groups(lines, body_size):
    group = []
    for line in lines:
        text = line['text'].strip()
        size = line_size(line)
        caption = CAPTION.match(text)
        separate = (size > body_size * 1.12 or caption or
                    (len(text) < 95 and SECTION.match(text)) or
                    (len(text) < 140 and FORMULA.search(text)))
        if group and (separate or line['top'] - group[-1]['bottom'] > body_size * .53
                      or abs(size - line_size(group[-1])) > 1.1
                      or line['x0'] > group[-1]['x0'] + body_size * .8):
            yield group
            group = []
        group.append(line)
        if separate and not caption:
            yield group
            group = []
    if group:
        yield group


def balanced_columns(items, width, height):
    """Choose a safe split for a block of text that fits on one page."""
    from reportlab.platypus import Paragraph

    def measure(item):
        return item.wrap(width, height)[1] + item.getSpaceBefore() + item.getSpaceAfter()

    heights = [measure(item) for item in items]
    total = sum(heights)
    if len(items) < 2 or total > 2 * height:
        return None

    best = None
    left = 0

    def consider(first, second, before, after, split=False):
        nonlocal best
        if not first or not second or max(before, after) > height:
            return
        # Prefer a paragraph boundary if it costs at most one line of imbalance.
        score = (abs(before - after) + (14 if split else 0) + (14 if before < after else 0),
                 before < after)
        if best is None or score < best[0]:
            best = (score, first, second)

    for index, item in enumerate(items):
        right = total - left - heights[index]
        previous_heading = index > 0 and items[index - 1].getKeepWithNext()
        if not previous_heading:
            consider(items[:index], items[index:], left, total - left)
        if (isinstance(item, Paragraph) and item.style.name == 'body'
                and left < total / 2 < left + heights[index]):
            line = item.style.leading
            target = round((total / 2 - left) / line)
            for lines in range(target - 1, target + 3):
                if lines < 2:
                    continue
                parts = item.split(width, lines * line)
                if len(parts) != 2 or parts[1].wrap(width, height)[1] < 2 * line:
                    continue
                consider([*items[:index], parts[0]], [parts[1], *items[index + 1:]],
                         left + measure(parts[0]), right + measure(parts[1]), split=True)
        left += heights[index]
    return best[1:] if best else None


class PaperLayout:
    def __init__(self, data):
        import pdfplumber
        self.data = data
        self.blocks = []
        self.double_column = False
        self.page_sizes = []
        self.title = ''
        references = False
        try:
            with pdfplumber.open(BytesIO(data)) as document:
                if len(document.pages) > 100:
                    raise ValueError('版式 PDF 最多支持 100 页 / Layout PDF is limited to 100 pages.')
                for index, page in enumerate(document.pages):
                    self.page_sizes.append((page.width, page.height))
                    sections, columns = self._page(page, index)
                    self.double_column |= columns
                    for block in sections:
                        if re.fullmatch(r'\s*(?:\d+\.?\s*)?(?:References|Bibliography)\s*', block.text, re.I):
                            references = True
                        elif references and block.kind == 'body':
                            block.kind = 'reference'
                        self.blocks.append(block)
                    page.close()
        except ValueError:
            raise
        except Exception as error:
            raise ValueError('无法分析 PDF 版面 / Could not analyze the PDF layout.') from error
        if not any(block.kind in {'title', 'heading', 'body', 'caption'} for block in self.blocks):
            raise ValueError('PDF 需要可选文字 / The PDF requires a searchable text layer.')

    def _page(self, page, index):
        from pdfplumber.utils import extract_text
        midpoint = page.width / 2
        chars = [char for char in page.chars if char['text'].strip() and char.get('upright', True)]
        if not chars:
            return [Block('figure', '', index, tuple(page.bbox), True)], False
        body = body_font_size(chars)
        # Count text rows on both sides of a persistent gutter; then split the
        # characters before line extraction to avoid joining two columns.
        left = [char for char in chars if char['x1'] <= midpoint - 1]
        right = [char for char in chars if char['x0'] >= midpoint + 1]
        center = [char for char in chars if char['x0'] < midpoint + 1 and char['x1'] > midpoint - 1]
        left_rows = {round(char['top'] / 5) for char in left if abs(char['size'] - body) < 1}
        right_rows = {round(char['top'] / 5) for char in right if abs(char['size'] - body) < 1}
        center_rows = {round(char['top'] / 5) for char in center if abs(char['size'] - body) < 1}
        aligned = left_rows & right_rows
        two = len(aligned - center_rows) >= 6 and len(aligned - center_rows) > len(aligned) * .6
        rows = page.filter(lambda item: item['object_type'] != 'char' or item.get('upright', True)).extract_text_lines(
            return_chars=True, x_tolerance_ratio=.15, y_tolerance=2)
        if index:
            rows = [row for row in rows if row['top'] > 60 or
                    row['text'].strip().rstrip('0123456789 ').strip() != self.title]
        wide_rows = []
        side_rows = [[], []]
        for row in rows:
            glyphs = sorted((ch for ch in row['chars'] if ch['text'].strip()), key=lambda ch: ch['x0'])
            # Two independent lines can share a baseline. A gap between the
            # last left glyph and the first right glyph separates them even
            # when the right column begins slightly left of the page midpoint.
            gutter = next(((a['x1'] + b['x0']) / 2 for a, b in zip(glyphs, glyphs[1:])
                           if b['x0'] - a['x1'] > body * .85
                           and a['x1'] <= midpoint - 2 and midpoint - 5 < b['x0'] < midpoint + 35), None)
            crosses = row['x0'] < midpoint - 12 and row['x1'] > midpoint + 12 and gutter is None
            size = line_size(row)
            if not two or (crosses and (row['x1'] > midpoint + 120 or size > body * 1.3)):
                wide_rows.append(row)
            else:
                split = gutter if gutter is not None else midpoint
                for slot, side in enumerate((
                    [ch for ch in row['chars'] if (ch['x0'] + ch['x1']) / 2 < split],
                    [ch for ch in row['chars'] if (ch['x0'] + ch['x1']) / 2 >= split],
                )):
                    if side:
                        x0, top, x1, bottom = bounds(side)
                        side_rows[slot].append(dict(x0=x0, top=top, x1=x1, bottom=bottom, chars=side,
                                                    text=extract_text(side, x_tolerance_ratio=.15).strip()))
        if two:
            # A short last line of a spanning caption can end before the gutter.
            captions = [row for row in wide_rows if CAPTION.match(row['text'].strip())]
            for caption in captions:
                bottom = caption['bottom']
                continuation = sorted((row for row in [*wide_rows, *side_rows[0]]
                                       if row['top'] > caption['top']), key=lambda row: row['top'])
                for row in continuation:
                    if row['top'] - bottom > body * .65 or CAPTION.match(row['text'].strip()):
                        break
                    size = line_size(row)
                    if abs(size - line_size(caption)) > .35:
                        break
                    if row in side_rows[0] and not any(abs(peer['top'] - row['top']) < 3 for peer in side_rows[1]):
                        side_rows[0].remove(row)
                        wide_rows.append(row)
                    bottom = row['bottom']
            wide_rows.sort(key=lambda row: row['top'])
        wide = self._text_blocks(wide_rows, index, body, wide=two)
        columns = [self._text_blocks(side, index, body) for side in side_rows]
        for image in page.images:
            box = tuple(image[k] for k in ('x0', 'top', 'x1', 'bottom'))
            if box[2] - box[0] < 24 or box[3] - box[1] < 18:
                continue
            block = Block('figure', '', index, box, two and box[0] < midpoint < box[2])
            if not two or block.wide:
                wide.append(block)
            else:
                columns[int(box[0] >= midpoint)].append(block)
        self._vector_figures(page, index, two, midpoint, wide, columns)
        for sequence in [wide, *columns]:
            sequence.sort(key=lambda block: block.box[1])
        if not two:
            return wide, False
        ordered = []
        for block in wide:
            for column in columns:
                while column and column[0].box[1] < block.box[1]:
                    ordered.append(column.pop(0))
            ordered.append(block)
        return ordered + columns[0] + columns[1], True

    @staticmethod
    def _vector_figures(page, index, two, midpoint, wide, columns):
        graphics = [item for item in [*page.images, *page.curves, *page.rects, *page.lines]
                    if item['x1'] - item['x0'] >= 2 or item['bottom'] - item['top'] >= 2]
        for sequence in [wide, *columns]:
            for caption in [block for block in sequence if block.kind == 'caption']:
                x0, top, x1, bottom = caption.box
                is_table = caption.text.lower().startswith('table')
                left, right = (0, page.width) if sequence is wide else (
                    (0, midpoint) if sequence is columns[0] else (midpoint, page.width))
                candidates = [item for item in graphics if item['x0'] >= left and item['x1'] <= right and (
                    bottom <= item['top'] < bottom + 180 if is_table else top - 260 < item['bottom'] <= top
                )]
                if not candidates:
                    continue
                box = bounds(candidates)
                if box[2] - box[0] < 32 or box[3] - box[1] < 15:
                    continue
                for lane in ([wide, *columns] if sequence is wide else [sequence]):
                    lane[:] = [block for block in lane if block.kind in {'title', 'caption'}
                               or not overlap(box, block.box)]
                sequence.append(Block('figure', '', index, box, two and sequence is wide))

    def _text_blocks(self, rows, index, body, *, wide=False):
        blocks = []
        for group in line_groups(rows, body):
            box = bounds(group)
            text = '\n'.join(row['text'].strip() for row in group).strip()
            text = re.sub(r'(?<=\w)-\n(?=[a-z])', '', text).replace('\n', ' ')
            if not text or (text.isdecimal() and len(text) < 4):
                continue
            sizes = [char['size'] for row in group for char in row['chars'] if char['text'].strip()]
            size = statistics.median(sizes) if sizes else body
            if index == 0 and box[1] < 220 and size >= body * 1.43:
                kind = 'title'
                self.title = self.title + ' ' + text if self.title else text
            elif CAPTION.match(text):
                kind = 'caption'
            elif len(text) < 140 and (size > body * 1.12 or SECTION.match(text)):
                kind = 'heading'
            elif len(text) < 140 and FORMULA.search(text):
                kind = 'figure'
            elif index == 0 and box[1] < 178 and wide and self.title:
                kind = 'reference'
            else:
                kind = 'body'
            blocks.append(Block(kind, text if kind != 'figure' else '', index, box, wide))
        return blocks

    def passages(self):
        return [block.text for block in self.blocks if block.kind not in {'figure', 'reference'}]

    def render(self, translated, language):
        import pypdfium2
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import (BaseDocTemplate, Frame, FrameBreak, Image, KeepTogether,
                                       NextPageTemplate, PageTemplate, Paragraph, PageBreak)
        from pypdf import PdfReader

        font = PdfGenerator._register_font()
        width, height = 612, 792
        margin, gap = 48, 20
        inner = width - margin * 2
        column = (inner - gap) / 2
        h = height - margin * 2
        def wide_frame():
            return Frame(margin, margin, inner, h, leftPadding=0, rightPadding=0)

        def frame(x, frame_height=h):
            return Frame(x, margin, column, frame_height, leftPadding=0, rightPadding=0)

        def page_number(canvas, doc):
            canvas.setFont('Times-Roman', 8)
            canvas.drawCentredString(width / 2, 24, str(doc.page))

        output = BytesIO()
        doc = BaseDocTemplate(output, pagesize=(width, height), title=self.title or 'Translated paper')
        doc.addPageTemplates([
            PageTemplate(id='wide', frames=[wide_frame()], onPage=page_number),
            PageTemplate(id='columns', frames=[frame(margin), frame(margin + column + gap)], onPage=page_number),
        ])
        styles = {}
        for kind, size, leading, before, after in (
            ('title', 18, 23, 2, 12), ('heading', 12, 15, 8, 5), ('body', 10, 14, 0, 6),
            ('caption', 8, 11, 2, 7), ('reference', 8.5, 12, 0, 4),
        ):
            styles[kind] = ParagraphStyle(kind, fontName=font, fontSize=size, leading=leading,
                spaceBefore=before, spaceAfter=after, keepWithNext=kind in {'heading', 'title'},
                wordWrap='CJK' if language in {'zh', 'zh-TW', 'ja', 'ko'} else None,
                alignment=TA_CENTER if kind == 'title' else 0, allowOrphans=0, allowWidows=0)
        values = iter(translated)
        story, mode = [], 'wide'
        available_columns = None
        blocks = self.blocks
        if self.double_column:
            lead = []
            for block in blocks:
                if block.kind not in {'title', 'reference'} or not block.wide or block.page != 0:
                    break
                value = block.text if block.kind == 'reference' else next(values)
                lead.append(Paragraph(escape(value), styles[block.kind]))
            if lead:
                used = sum(item.wrap(inner, h)[1] + item.style.spaceAfter for item in lead) + 14
                if used < h * .45:
                    def first_page(canvas, doc):
                        page_number(canvas, doc)
                        y = height - margin
                        for item in lead:
                            y -= item.height
                            item.drawOn(canvas, margin, y)
                            y -= item.style.spaceAfter
                    doc.addPageTemplates(PageTemplate(id='front', frames=[
                        frame(margin, h - used), frame(margin + column + gap, h - used),
                    ], onPage=first_page, autoNextPageTemplate='columns'))
                    doc._firstPageTemplateIndex = 2
                    blocks = blocks[len(lead):]
                    mode = 'columns'
                    available_columns = h - used
                else:
                    values = iter(translated)
        def add_columns_below(top, suffix):
            frame_height = h - top
            name = f'below-{suffix}'
            doc.addPageTemplates(PageTemplate(id=name, frames=[
                Frame(margin, margin + frame_height, inner, top, leftPadding=0, rightPadding=0),
                frame(margin, frame_height), frame(margin + column + gap, frame_height),
            ], onPage=page_number, autoNextPageTemplate='columns'))
            return name, FrameBreak()

        # PDFium requires serialized access across concurrent document jobs.
        with _RENDER_LOCK, pypdfium2.PdfDocument(self.data) as source:
            def flowable(block, wide):
                if block.kind == 'figure':
                    return self._crop(source, block, inner if wide else column, h * .60)
                value = block.text if block.kind == 'reference' else next(values)
                return Paragraph(escape(value), styles[block.kind])

            def is_wide(block):
                return not self.double_column or block.wide or block.kind == 'title'

            for index, (wide, group) in enumerate(groupby(blocks, key=is_wide)):
                members = list(group)
                content = [flowable(block, wide) for block in members]
                if not wide:
                    fresh_height = available_columns if mode == 'columns' else h
                    if fresh_height is not None:
                        # Keep image/caption pairs indivisible when choosing a column break.
                        for pos in range(len(content) - 1):
                            a, b = members[pos:pos + 2]
                            if a.page == b.page and {a.kind, b.kind} == {'figure', 'caption'}:
                                content[pos].keepWithNext = True
                        split = balanced_columns(content, column, fresh_height - 16)
                        if split:
                            content = [*split[0], FrameBreak(), *split[1]]
                    available_columns = None
                if wide and mode == 'columns':
                    height_needed = sum(item.wrap(inner, h)[1] + item.getSpaceBefore() + item.getSpaceAfter()
                                        for item in content) + 22
                    if height_needed < h * .75:
                        name, frame_break = add_columns_below(height_needed, index)
                        story.extend([NextPageTemplate(name), PageBreak(), *content, frame_break])
                        available_columns = h - height_needed
                        continue
                new_mode = 'wide' if wide else 'columns'
                if mode != new_mode and story:
                    story.extend([NextPageTemplate(new_mode), PageBreak()])
                elif mode != new_mode:
                    doc._firstPageTemplateIndex = int(not wide)
                mode = new_mode
                story.extend(content)
            # Keep adjacent illustrations and captions together.
            for index in range(len(story) - 2, -1, -1):
                first, second = story[index:index + 2]
                if ((isinstance(first, Image) and isinstance(second, Paragraph) and second.style.name == 'caption') or
                        (isinstance(second, Image) and isinstance(first, Paragraph) and first.style.name == 'caption')):
                    story[index:index + 2] = [KeepTogether([first, second])]
            doc.build(story)
        result = output.getvalue()
        if not PdfReader(BytesIO(result)).pages:
            raise ValueError('PDF rendering produced no pages.')
        return result

    def _crop(self, source, block, max_width, max_height):
        from reportlab.platypus import Image
        page_width, page_height = self.page_sizes[block.page]
        x0, top, x1, bottom = block.box
        x0, top, x1, bottom = max(0, x0 - 2), max(0, top - 2), min(page_width, x1 + 2), min(page_height, bottom + 2)
        if x1 <= x0 or bottom <= top:
            raise ValueError('PDF contains a visual region outside the page.')
        page = source[block.page]
        try:
            scale = min(1.8, 2000 / max(x1 - x0, bottom - top))
            bitmap = page.render(scale=scale, crop=(x0, page_height - bottom, page_width - x1, top))
            try:
                buffer = BytesIO()
                bitmap.to_pil().convert('RGB').save(buffer, 'JPEG', quality=88)
            finally:
                bitmap.close()
        finally:
            page.close()
        buffer.seek(0)
        ratio = min(max_width / (x1 - x0), max_height / (bottom - top), 1)
        image = Image(buffer, width=(x1 - x0) * ratio, height=(bottom - top) * ratio)
        image.spaceAfter = 5
        return image


def body_font_size(chars):
    from collections import Counter
    return Counter(round(char['size'], 1) for char in chars).most_common(1)[0][0]


def line_size(row):
    return statistics.median(char['size'] for char in row['chars'])


def overlap(box, other):
    width = min(box[2], other[2]) - max(box[0], other[0])
    height = min(box[3], other[3]) - max(box[1], other[1])
    return width > 0 and height > 0 and width * height > (other[2] - other[0]) * (other[3] - other[1]) * .35
