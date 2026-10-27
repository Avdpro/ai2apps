"""Source-bound article image placement; plain body remains canonical."""
import hashlib
import re
from .models import cover_url

SCHEMA = 'ai2apps.article-content/v1'


def paragraphs(body):
    return [text.strip() for text in re.split(r'\n\s*\n', body.strip()) if text.strip()]


def image_id(source_url, url):
    return 'img_' + hashlib.sha256((source_url + '\n' + url).encode()).hexdigest()[:24]


def image_catalog(pages):
    result = {}
    for evidence_id, page in enumerate(pages, 1):
        source_paragraphs={b.get('id'):b.get('text','') for b in page.get('source_blocks',[]) if b.get('type')=='paragraph'}
        nearby={b.get('url'):source_paragraphs.get(b.get('paragraph_id'),'')[:300] for b in page.get('source_blocks',[]) if b.get('type')=='image'}
        candidates = ([{'url':page['image_url'], 'alt':page.get('title','')}] if page.get('image_url') else []) + page.get('images',[])
        for item in candidates:
            try:
                url = cover_url(item.get('url',''))
            except ValueError:
                continue
            if not url:
                continue
            key = image_id(page['url'],url)
            result.setdefault(key, {'id':key, 'url':url, 'alt':str(item.get('alt',''))[:300],
                                    'source_url':page['url'], 'evidence_id':evidence_id,'near_text':nearby.get(url,'')})
    return result


def validate_placements(article, catalog):
    parts = paragraphs(article.body)
    if article.image_placements and len(parts)+len(article.image_placements)>128:
        raise ValueError('At most 128 paragraph/image blocks per article')
    used, urls = set(), set()
    for placement in article.image_placements:
        image = catalog.get(placement.image_id)
        if image is None:
            raise ValueError('image_placements must reference a supplied image_id; do not invent IDs or URLs')
        if image['evidence_id'] not in article.evidence_ids:
            raise ValueError('Inline image source must be included in this article evidence_ids')
        if placement.after_paragraph >= len(parts):
            raise ValueError('after_paragraph is a zero-based paragraph index in body')
        if image['evidence_id'] not in {int(n) for n in re.findall(r'\[(\d+)\]',parts[placement.after_paragraph])}:
            raise ValueError('The paragraph receiving an image must cite that image source evidence_id')
        if placement.image_id in used or image['url'] in urls:
            raise ValueError('Do not repeat an inline image')
        used.add(placement.image_id)
        urls.add(image['url'])


def assemble(body, placements, catalog, images):
    by_url = {image['url']:image for image in images}
    by_paragraph = {}
    for placement in placements:
        item = catalog[placement['image_id']]
        # Resolve to the server-owned image record, never a model URL/caption.
        record = by_url.get(item['url'])
        if not record or record['source_url'] != item['source_url']:
            raise ValueError('Inline image is absent from the article image pool')
        by_paragraph.setdefault(placement['after_paragraph'], []).append(record['id'])
    blocks = []
    for index, text in enumerate(paragraphs(body)):
        blocks.append({'type':'paragraph', 'text':text})
        blocks.extend({'type':'image', 'image_id':key} for key in by_paragraph.get(index,[]))
    return blocks


def validate_content(article):
    blocks = article.get('content_blocks')
    if not blocks:
        return
    v2=article.get('content_schema')=='ai2apps.article-content/v2'
    if article.get('content_schema') not in (SCHEMA,'ai2apps.article-content/v2') or len(blocks)>128:
        raise ValueError('Unsupported article content schema')
    source_order = [s['url'] for s in article.get('sources',[])]
    sources = set(source_order)
    images = {i.get('id'):i for i in article.get('images',[]) if i.get('id')}
    text, used,paragraph_ids = [], set(),set()
    section_ids={s['id'] for s in article.get('editorial_sections',[])}
    last_paragraph=None
    for block in blocks:
        if block.get('type')=='paragraph' and set(block)==({'type','text','id','section_id'} if v2 else {'type','text'}) and isinstance(block['text'],str):
            if v2:
                if not re.fullmatch(r'p_[0-9a-f]{24}',block['id']) or block['id'] in paragraph_ids or block['section_id'] not in section_ids:raise ValueError('Invalid paragraph/section identity')
                paragraph_ids.add(block['id']);last_paragraph=block['id']
            text.append(block['text'])
        elif block.get('type')=='image' and set(block)==({'type','image_id','paragraph_id'} if v2 else {'type','image_id'}):
            if v2 and block['paragraph_id']!=last_paragraph:raise ValueError('Image must be attached to its preceding paragraph ID')
            key = block['image_id']; image = images.get(key)
            if not image or image.get('source_url') not in sources or key in used:
                raise ValueError('Inline image must belong to a current article source and appear once')
            citations = {int(n) for n in re.findall(r'\[(\d+)\]',text[-1])} if text else set()
            if source_order.index(image['source_url'])+1 not in citations:
                raise ValueError('Inline image must follow a paragraph citing its source')
            url = cover_url(image['url'])
            if not url or key != image_id(image['source_url'],url):
                raise ValueError('Inline image identity does not match source')
            used.add(key)
        else:
            raise ValueError('Invalid article content block')
    if text != paragraphs(article['body']):
        raise ValueError('Content paragraphs must exactly match the canonical plain body')
    if len(used)>24:
        raise ValueError('At most 24 inline images per article')
