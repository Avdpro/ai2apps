import io
import base64
import pytest
from PIL import Image
from ai2apps.browser.product_images import allowed, thumbnail

@pytest.mark.parametrize('url',['http://m.media-amazon.com/images/a.jpg','https://evil.test/images/a.jpg','https://m.media-amazon.com.evil.test/images/a.jpg','https://user@media-amazon.com/images/a.jpg','https://m.media-amazon.com:8443/images/a.jpg','https://m.media-amazon.com/private/a.jpg'])
def test_thumbnail_does_not_fetch_arbitrary_urls(url):
    assert not allowed(url)

def test_amazon_cdn_and_bounded_jpeg_data_url():
    assert allowed('https://m.media-amazon.com/images/I/product.jpg')
    source=io.BytesIO();Image.new('RGB',(400,600),'white').save(source,'PNG')
    data=thumbnail(source.getvalue())
    assert data.startswith('data:image/jpeg;base64,')
    raw=base64.b64decode(data.split(',')[1]);assert len(raw)<60000
    with Image.open(io.BytesIO(raw)) as image:assert image.width<=160 and image.height<=200

def test_invalid_image_cannot_be_treated_as_a_thumbnail():
    with pytest.raises(OSError):thumbnail(b'<html>not an image</html>')
