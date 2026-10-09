from io import BytesIO
from PIL import Image
from ai2apps.browser import site_icons


def test_declared_relative_icon_is_extracted_and_normalized(monkeypatch):
    output = BytesIO()
    Image.new('RGB', (128, 128), 'red').save(output, format='PNG')
    urls = []
    def fetch(url, limit):
        urls.append(url)
        if len(urls) == 1:
            return b'<base href="/assets/"><link rel="shortcut icon" href="logo.png">', 'https://example.com/home'
        return output.getvalue(), url
    monkeypatch.setattr(site_icons, '_fetch', fetch)
    result = site_icons.discover_site_icon('example.com')
    assert urls == ['https://example.com/', 'https://example.com/assets/logo.png']
    import base64
    with Image.open(BytesIO(base64.b64decode(result.split(',')[1]))) as image:
        assert image.size == (64, 64)
        assert image.format == 'PNG'


def test_favicon_fallback_and_invalid_content_fail_without_blocking_domain(monkeypatch):
    urls = []
    def fetch(url, limit):
        urls.append(url)
        return b'<html>unavailable</html>', url
    monkeypatch.setattr(site_icons, '_fetch', fetch)
    assert site_icons.discover_site_icon('example.com') == ''
    assert urls == ['https://example.com/', 'https://example.com/favicon.ico']
