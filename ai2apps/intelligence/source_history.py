"""Retain event provenance independently of the bounded revision history."""
from urllib.parse import urlsplit, urlunsplit


def source_key(source):
    try:
        p = urlsplit(source.get('url', ''))
        if p.scheme not in ('http', 'https') or not p.netloc:
            return ''
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or '/', p.query, ''))
    except ValueError:
        return ''


def other_sources(article, previous):
    seen = {source_key(s) for s in article.get('sources', [])}
    result = []
    candidates = list(previous.get('sources', []))
    for version in reversed(previous.get('versions', [])):
        candidates.extend(version.get('sources', []))
    candidates.extend(previous.get('related_sources', []))
    for source in candidates:
        key = source_key(source)
        if key and key not in seen:
            seen.add(key)
            result.append(dict(source))
    return result
