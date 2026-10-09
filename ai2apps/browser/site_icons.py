"""Small, cached website icons; no browser session or credentials are accessed."""
from __future__ import annotations

import base64
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import ProxyHandler, Request, build_opener


class IconLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.base = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'base' and not self.base:
            self.base = attrs.get('href', '')
        rel = attrs.get('rel', '').lower().split()
        if tag == 'link' and ('icon' in rel or 'apple-touch-icon' in rel):
            href = attrs.get('href', '')
            if href:
                self.links.append(href)


def _fetch(url, limit):
    # Reuse the existing public-web URL, redirect and connected-peer checks.
    from ai2apps.api.knowledge import _public_web_url, _PublicRedirectHandler, _validate_public_peer
    opener = build_opener(ProxyHandler({}), _PublicRedirectHandler())
    request = Request(_public_web_url(url), headers={'User-Agent': 'AI2Apps-SiteIcon/1.0'})
    with opener.open(request, timeout=3) as response:
        _validate_public_peer(response)
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Website icon response too large')
        return data, response.geturl()


def discover_site_icon(domain):
    """Discover declared icons, then /favicon.ico. Failure is non-fatal."""
    homepage = 'https://' + domain + '/'
    links = []
    try:
        document, final_url = _fetch(homepage, 512_000)
        parser = IconLinks()
        parser.feed(document.decode('utf-8', errors='replace'))
        base = urljoin(final_url, parser.base) if parser.base else final_url
        links = [urljoin(base, href) for href in parser.links[:2]]
    except Exception:
        pass
    links.append(urljoin(homepage, '/favicon.ico'))
    for url in dict.fromkeys(links):
        try:
            data, _ = _fetch(url, 128_000)
            # Decode and normalize to a small static PNG; never store active SVG/HTML.
            from io import BytesIO
            from PIL import Image
            with Image.open(BytesIO(data)) as image:
                if image.width * image.height > 4_000_000:
                    continue
                image.thumbnail((64, 64))
                output = BytesIO()
                image.convert('RGBA').save(output, format='PNG')
            return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')
        except Exception:
            continue
    return ''
