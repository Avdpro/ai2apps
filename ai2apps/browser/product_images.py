"""Bounded public Amazon thumbnails from already observed Task image URLs."""
import asyncio
import base64
import io
from urllib.parse import urlsplit

import httpx
from PIL import Image

HOSTS = frozenset({'m.media-amazon.com', 'images-na.ssl-images-amazon.com', 'images-eu.ssl-images-amazon.com'})


def allowed(url):
    try:
        u=urlsplit(url)
        return u.scheme=='https' and u.hostname in HOSTS and not u.username and not u.password and u.port in (None,443) and u.path.startswith('/images/')
    except ValueError:
        return False


def thumbnail(content):
    with Image.open(io.BytesIO(content)) as image:
        if image.width*image.height>16_000_000:
            raise ValueError('Image too large')
        image.thumbnail((160,200))
        out=io.BytesIO();image.convert('RGB').save(out,format='JPEG',quality=80)
    if len(out.getvalue())>60_000:
        raise ValueError('Thumbnail too large')
    return 'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode()


async def product_images(items):
    semaphore=asyncio.Semaphore(4)
    loaded=[]
    async with httpx.AsyncClient(timeout=8,follow_redirects=False,trust_env=False) as client:
        async def load(item):
            if not allowed(item.get('image_url','')):return None
            try:
                async with semaphore:
                    async with client.stream('GET',item['image_url']) as response:
                        if response.status_code!=200 or not response.headers.get('content-type','').startswith('image/'):
                            return None
                        content=bytearray()
                        async for chunk in response.aiter_bytes():
                            content.extend(chunk)
                            if len(content)>2_000_000:return None
                    data=await asyncio.to_thread(thumbnail,bytes(content))
                    result={'id':item['id'],'image_data_url':data}
                    loaded.append(result)
                    return result
            except (httpx.HTTPError, OSError, ValueError, Image.DecompressionBombError):
                return None
        try:
            await asyncio.wait_for(asyncio.gather(*(load(item) for item in items[:50])),timeout=20)
        except asyncio.TimeoutError:
            pass
        return loaded
