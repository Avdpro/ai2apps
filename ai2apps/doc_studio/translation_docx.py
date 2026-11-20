"""Translate text in OOXML paragraphs without rebuilding the Word package."""
import io
import re
import zipfile

from lxml import etree

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'
PART = re.compile(r'word/(?:document|header\d+|footer\d+|footnotes|endnotes)\.xml')
ANCHOR = re.compile(r'⟦(\d+)⟧')
EAST_ASIA = {'zh': 'zh-CN', 'zh-TW': 'zh-TW', 'ja': 'ja-JP', 'ko': 'ko-KR'}
EAST_ASIA_FONTS = {'zh': 'SimSun', 'zh-TW': 'PMingLiU', 'ja': 'Yu Mincho', 'ko': 'Batang'}


def empty_body_paragraph(node):
    if node.tag != W + 'p':
        return False
    # Ignore formatting and run containers, but preserve fields, drawings, tables,
    # bookmarks, manual breaks, tabs and other body content.
    for child in node:
        if child.tag == W + 'pPr':
            continue
        if child.tag != W + 'r' or any(
                item.tag != W + 'rPr' and (item.tag != W + 't' or (item.text or '').strip())
                for item in child):
            return False
    return True


def polish_pagination(body):
    if body is None:
        return
    empty = True
    first = True
    for node in body:
        section = node if node.tag == W + 'sectPr' else node.find(W + 'pPr/' + W + 'sectPr')
        if node is not section:
            empty = empty and empty_body_paragraph(node)
        if section is None:
            continue
        section_type = section.find(W + 'type')
        # An implicit next-page start on a section without body content can
        # create a page showing just a repeated header and footer.
        if (empty and not first and section_type is None and
                all(section.find(W + tag) is None for tag in ('pgNumType', 'titlePg', 'sectPrChange'))):
            section_type = etree.Element(W + 'type')
            geometry = next((item for item in section if item.tag not in {W + 'headerReference',
                            W + 'footerReference', W + 'footnotePr', W + 'endnotePr'}), None)
            if geometry is None:
                section.append(section_type)
            else:
                geometry.addprevious(section_type)
            section_type.set(W + 'val', 'continuous')
        empty = True
        first = False


def check_archive(archive):
    entries = archive.infolist()
    names = {item.filename for item in entries}
    if (len(entries) > 2000 or len(names) != len(entries)
            or sum(item.file_size for item in entries) > 60 * 1024 * 1024):
        raise ValueError('Word 文档结构无效或解压后过大 / Invalid or oversized Word package.')
    if 'word/document.xml' not in names or 'word/vbaProject.bin' in names:
        raise ValueError('请提供不含宏的 DOCX / Supply a DOCX without macros.')


class WordLayout:
    def __init__(self, data):
        self.data = data
        self.parts = {}
        self.paragraphs = []
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                check_archive(archive)
                parts = sorted((name for name in archive.namelist() if PART.fullmatch(name)),
                               key=lambda name: (name != 'word/document.xml', name))
                for name in parts:
                    root = etree.fromstring(archive.read(name), etree.XMLParser(
                        resolve_entities=False, load_dtd=False, no_network=True))
                    if root.getroottree().docinfo.doctype:
                        raise ValueError('Word XML contains an unsupported document type declaration.')
                    self.parts[name] = root
                    self.paragraphs.extend(groups for paragraph in root.iter(W + 'p')
                                           if (groups := self._groups(paragraph)))
        except (zipfile.BadZipFile, etree.XMLSyntaxError, RuntimeError) as error:
            raise ValueError('无法读取 DOCX / Could not read the DOCX package.') from error

    @staticmethod
    def _groups(paragraph):
        groups, previous = [], None
        barrier = {W + name for name in ('tab', 'br', 'cr', 'drawing', 'pict', 'footnoteReference',
                                         'endnoteReference', 'fldChar', 'instrText')}
        field_depth = 0
        for node in paragraph.iter():
            # Nested text boxes have their own paragraph in the outer traversal.
            if next(node.iterancestors(W + 'p'), None) is not paragraph:
                continue
            if node.tag in barrier:
                previous = None
            if node.tag == W + 'fldChar':
                kind = node.get(W + 'fldCharType')
                if kind == 'begin':
                    field_depth += 1
                elif kind == 'end':
                    field_depth = max(0, field_depth - 1)
            if node.tag != W + 't' or not node.text or field_depth:
                continue
            run = node.getparent()
            props = run.find(W + 'rPr')
            key = (run.getparent(), etree.tostring(props, method='c14n', exclusive=True) if props is not None else b'')
            if key != previous:
                groups.append([])
            groups[-1].append(node)
            previous = key
        if not any(node.text.strip() for group in groups for node in group):
            return []
        return groups

    def passages(self):
        passages = []
        for groups in self.paragraphs:
            parts = [''.join(node.text for node in group) for group in groups]
            if any(ANCHOR.search(part) for part in parts):
                raise ValueError('Word 文本含保留的版式标记 / Word text contains a reserved formatting marker.')
            passages.append(''.join((f'⟦{index}⟧' if index else '') + part for index, part in enumerate(parts)))
        return passages

    def render(self, translated, language=None):
        if len(translated) != len(self.paragraphs):
            raise ValueError('Word paragraph count changed.')
        with zipfile.ZipFile(io.BytesIO(self.data)) as source:
            has_east_asian_defaults = 'word/styles.xml' in source.namelist() and bool(
                re.search(rb'\b(?:eastAsia|eastAsiaTheme)=', source.read('word/styles.xml')))
        for groups, text in zip(self.paragraphs, translated):
            values = ANCHOR.split(text)[::2]
            if len(values) != len(groups):
                raise ValueError('Word formatting marker count changed.')
            for group, value in zip(groups, values):
                original = ''.join(node.text for node in group)
                if not original.strip():
                    continue
                leading = original[:len(original) - len(original.lstrip())]
                trailing = original[len(original.rstrip()):]
                group[0].text = leading + value.strip() + trailing
                group[0].set(XML_SPACE, 'preserve')
                if language in EAST_ASIA:
                    run = group[0].getparent()
                    props = run.find(W + 'rPr')
                    if props is None:
                        props = etree.Element(W + 'rPr')
                        run.insert(0, props)
                    lang = props.find(W + 'lang')
                    if lang is None:
                        lang = etree.SubElement(props, W + 'lang')
                    lang.set(W + 'eastAsia', EAST_ASIA[language])
                    fonts = props.find(W + 'rFonts')
                    if not has_east_asian_defaults and (fonts is None or not (
                            fonts.get(W + 'eastAsia') or fonts.get(W + 'eastAsiaTheme'))):
                        if fonts is None:
                            fonts = etree.Element(W + 'rFonts')
                            props.insert(0, fonts)
                        fonts.set(W + 'eastAsia', EAST_ASIA_FONTS[language])
                for node in group[1:]:
                    node.text = ''
        polish_pagination(self.parts['word/document.xml'].find(W + 'body'))
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.data)) as source, zipfile.ZipFile(output, 'w') as result:
            for entry in source.infolist():
                root = self.parts.get(entry.filename)
                value = source.read(entry) if root is None else etree.tostring(root, encoding='UTF-8', xml_declaration=True)
                result.writestr(entry, value)
        return output.getvalue()
