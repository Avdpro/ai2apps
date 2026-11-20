"""Project handoff assembled from owner-scoped, saved Intelligence records."""
import hashlib
from urllib.parse import urlsplit

from ai2apps.storage.records import canonical_json
from . import html_export
from .models import public_url

SOURCE_APP = 'ai2apps.intelligence'
SCHEMA = 'ai2apps.doc-studio.material-pack/v1'


def _source(ref):
    try:
        url = public_url(ref.get('url', ''))
    except (ValueError, TypeError, AttributeError):
        return None
    return {
        'url': url, 'title': ref.get('title') or ref.get('source_name') or url,
        'retrieved_at': ref.get('retrieved_at'), 'coverage': ref.get('coverage'),
    }


def _article_entry(article, originals):
    cover = article.get('cover_image') or {}
    anchors = {}
    paragraphs = []
    paragraph = ''
    ordinal = 0
    for block in article.get('content_blocks') or []:
        if block.get('type') == 'paragraph':
            paragraph = block.get('id') or 'paragraph-' + str(len(paragraphs) + 1)
            paragraphs.append({'id': paragraph, 'text': block['text']})
        elif block.get('type') == 'image':
            anchors[block.get('image_id')] = block.get('paragraph_id') or paragraph
    images = {}
    for image in [cover, *(article.get('images') or [])]:
        url = image.get('url')
        if not url:
            continue
        if url in images:
            existing = images[url]
            existing['anchor'] = existing['anchor'] or anchors.get(image.get('id')) or ''
            existing['alt'] = existing['alt'] or image.get('alt') or ''
            existing['source_url'] = existing['source_url'] or image.get('source_url') or ''
            continue
        images[url] = {
            'url': url, 'alt': image.get('alt') or '', 'source_url': image.get('source_url') or '',
            'cover': url == cover.get('url'), 'anchor': anchors.get(image.get('id')) or '',
        }
    original = article.get('original_content') or {}
    return {
        'source_app': SOURCE_APP, 'source_id': article['id'], 'title': article['title'],
        'body': article.get('body') or article.get('summary') or '',
        'summary': article.get('summary') or '', 'updated_at': article.get('updated_at') or '',
        'sources': [source for ref in article.get('sources', []) if (source := _source(ref))],
        'images': list(images.values()), 'paragraphs': paragraphs,
        'original_content': {'title': original.get('title'), 'body': original['body']}
        if original.get('body') else None,
        'source_originals': originals,
    }


def digest(data):
    return hashlib.sha256(canonical_json(data).encode()).hexdigest()


def snapshot(store, owner, article_ids):
    with store.connect() as db:
        articles = [
            store.unpack(db.execute(
                'SELECT * FROM articles WHERE owner=? AND id=?', (owner, article_id),
            ).fetchone())
            for article_id in sorted(set(article_ids))
        ]
        return snapshot_articles(db, owner, articles)


def snapshot_articles(db, owner, articles):
    """Use only source text already cached for the selected article's channel."""
    cached = {}
    entries = []
    for article in articles:
        post_texts = {post['url']: post.get('text') for post in article.get('post_evidence', []) if post.get('url')}
        originals = []
        for ref in article.get('sources', []):
            source = _source(ref)
            if not source:
                continue
            url = ref['url']
            key = (article['channel_id'], url)
            if key not in cached:
                cached[key] = db.execute(
                    "SELECT json_extract(data,'$.text') FROM pages WHERE owner=? AND channel=? AND url=?",
                    (owner, *key),
                ).fetchone()
            row = cached[key]
            body = (row[0] if row else None) or post_texts.get(url)
            if body:
                originals.append({**source, 'body': body})
        entries.append(_article_entry(article, originals))
    return manifest(entries)


def manifest(entries):
    entries = sorted(entries, key=lambda item: (item['updated_at'], item['source_id']), reverse=True)
    identity = digest([SCHEMA, SOURCE_APP, sorted(item['source_id'] for item in entries)])
    return {'schema': SCHEMA, 'pack_key': identity, 'version': digest(entries), 'entries': entries}


def load_image(store, owner, reference):
    # Local imports and remote images use Intelligence's existing owner and
    # public-network checks, byte limits and safe raster re-encoding.
    url = reference['url']
    if urlsplit(url).fragment:
        url = url.split('#', 1)[0]
    return html_export.image_bytes(store, owner, url, 'reading')
