"""Resolve observed Google links before giving a single origin to Web Reader."""
from urllib.parse import urlsplit, parse_qs
from .provider import SafeHttpClient, WebProviderError

GOOGLE_HOSTS = frozenset({'google.com', 'www.google.com'})
VIDEO_HOSTS = frozenset({'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'bilibili.com', 'www.bilibili.com'})

def google_redirect(url):
    p = urlsplit(url)
    return p.hostname in GOOGLE_HOSTS and p.path in ('/url', '/goto')

def resolve_google_url(url, client=None):
    client = client or SafeHttpClient(timeout_seconds=12, max_redirects=4)
    original = client._validate_url(url)
    p = urlsplit(original)
    if not google_redirect(original):
        return {'url': original}
    values = parse_qs(p.query)
    target = (values.get('q') or values.get('url') or [''])[0]
    # Plain destination parameters are unwrapped, never an opaque signed value.
    if target.startswith(('http://', 'https://')):
        target = client._validate_url(target)
        response = client.resolve_redirects(target)
        chain = (original, *response.redirects)
    else:
        response = client.resolve_redirects(original)
        chain = response.redirects
    final = client._validate_url(response.url)
    host = urlsplit(final).hostname or ''
    if host == 'google.com' or host.endswith('.google.com'):
        raise WebProviderError('Google redirect did not resolve to an article destination: ' + final)
    return {'url': final, 'search_url': original, 'redirect_chain': list(chain)}

def article_first(item):
    """Prefer text destinations within Google, keeping every observed result."""
    return (bool(item.get('resolution_error')), urlsplit(item['url']).hostname in VIDEO_HOSTS)
