"""Render only known block types. Treat every authored string as text."""
import base64
import html
import re
import unicodedata

from ai2apps.intelligence.html_export import safe_link

from .models import X_LONG_POST_LIMIT, X_POST_LIMIT

CITATION = re.compile(r'\[([1-9]\d{0,2})\]')
LIST_ITEM = re.compile(r'^(?:[-*]|\d+\.) +(.+)$')
URL = re.compile(r'https?://[^\s<>]+', re.I)


def blocks(content):
    result = []
    for section in re.split(r'\n\s*\n', content.strip()):
        for line in section.splitlines():
            line = line.strip()
            if not line:
                continue
            if match := LIST_ITEM.match(line):
                if result and result[-1]['type'] == 'list':
                    result[-1]['items'].append(match[1])
                else:
                    result.append({'type': 'list', 'items': [match[1]]})
            else:
                kind = 'heading' if line.startswith(('# ', '## ', '### ')) else 'quote' if line.startswith('> ') else 'paragraph'
                result.append({'type': kind, 'text': line if kind == 'paragraph' else line.partition(' ')[2]})
    return result


def references(content, sources):
    return list(dict.fromkeys(int(n) for n in CITATION.findall(content) if int(n) in sources))


def block_images(block):
    if block['type'] == 'image':
        return [block]
    return block.get('images', [])


def block_text(block):
    if block['type'] == 'list':
        return '\n'.join('- ' + item for item in block['items'])
    prefix = {'heading': '## ', 'quote': '> '}.get(block['type'], '')
    return prefix + block['text']


def weighted_length(text):
    # Conservative v3 count. Counting emoji scalars individually may yield a
    # larger value for joined emoji. Only generated, validated links are shortened.
    return sum(1 if (n <= 4351 or 8192 <= n <= 8205 or 8208 <= n <= 8223 or 8242 <= n <= 8247)
               else 2 for n in map(ord, unicodedata.normalize('NFC', text)))


class XPostError(ValueError):
    def __init__(self, message, code, **details):
        super().__init__(message)
        self.details = {'code': code, **details}


def x_post(content, evidence, *, long=False):
    indexed = {item['evidence_id']: item for item in evidence}
    refs = references(content, indexed)
    sources = [source for n in refs for source in indexed[n]['sources']]
    source = next((item['url'] for item in sources if safe_link(item['url'])), '')
    if URL.search(content):
        raise XPostError('Use numbered citations instead of URLs in the X Post body', 'url_in_body')
    body = re.sub(r' +([,.!?，。！？])', r'\1', CITATION.sub('', content)).strip()
    if not body:
        raise XPostError('X Post body is empty', 'empty_body')
    post = body + ('\n' + source if source else '')
    if long:
        limit, count = X_LONG_POST_LIMIT, len(unicodedata.normalize('NFC', post))
        unit = 'characters'
    else:
        limit, count = X_POST_LIMIT, weighted_length(body) + (24 if source else 0)
        unit = 'weighted characters'
    if count > limit:
        raise XPostError(
            f'X Post uses {count} {unit}, including any source link. The limit is {limit}. '
            f'Shorten it by at least {count - limit} {unit}.',
            'post_too_long', count=count, limit=limit, weighted=not long,
        )
    return post


def html_document(version, images):
    escape = html.escape
    title = escape(version['title'])
    language = escape(version['language'])
    evidence = {item['evidence_id']: item for item in version['evidence']}
    refs = references(version['content'], evidence)

    def inline(text):
        return CITATION.sub(lambda m: f'<a href="#source-{m[1]}">[{m[1]}]</a>'
                            if int(m[1]) in refs else m[0], escape(text))

    def figure(image):
        data, mime = images[image['asset_id']]
        encoded = base64.b64encode(data).decode('ascii')
        alt = escape(image['alt'])
        source = safe_link(image.get('source_url'))
        caption = f'<a href="{source}" rel="noreferrer">{alt or "↗"}</a>' if source else alt
        return f'<figure><img alt="{alt}" src="data:{mime};base64,{encoded}"><figcaption>{caption}</figcaption></figure>'

    sections = []
    for block in version['blocks']:
        kind = block['type']
        if kind == 'list':
            sections.append('<ul>' + ''.join(f'<li>{inline(item)}</li>' for item in block['items']) + '</ul>')
        elif kind == 'image':
            sections.append(figure(block))
        elif kind == 'image_row':
            figures = ''.join(map(figure, block['images']))
            sections.append(figures if len(block['images']) == 1 else f'<div class="image-row">{figures}</div>')
        else:
            tag = {'heading': 'h2', 'quote': 'blockquote', 'paragraph': 'p'}[kind]
            sections.append(f'<{tag}>{inline(block["text"])}</{tag}>')
    if refs:
        sections.append('<section class="sources"><h2>' +
                        ('来源' if language.startswith('zh') else 'Sources') + '</h2>')
        for number in refs:
            item = evidence[number]
            links = ''.join(f'<li><a href="{url}" rel="noreferrer">{escape(ref["title"])}</a></li>'
                            for ref in item['sources'] if (url := safe_link(ref['url'])))
            sections.append(f'<section id="source-{number}"><h3>[{number}] {escape(item["title"])}</h3><ul>{links}</ul></section>')
        sections.append('</section>')
    return (f'<!doctype html><html lang="{language}"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'">'
            f'<title>{title}</title><style>body{{max-width:44rem;margin:3rem auto;padding:0 1.25rem;'
            'font:1.08rem/1.7 system-ui;color:#202126;overflow-wrap:anywhere}h1,h2,h3{line-height:1.22}'
            'img{display:block;max-width:100%;height:auto}figure{margin:1.5rem 0}'
            '.image-row{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);gap:1rem;margin:1.5rem 0}'
            '.image-row figure{min-width:0;margin:0}.image-row img{width:100%}p,blockquote{white-space:pre-line}'
            'figcaption,.sources{font-size:.9em}blockquote{margin-left:0;padding-left:1em;border-left:3px solid #bbb}'
            'a{color:#2454a5}</style></head>'
            f'<body><article><h1>{title}</h1>{"".join(sections)}</article></body></html>').encode()
