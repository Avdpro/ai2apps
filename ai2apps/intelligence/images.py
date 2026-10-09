"""Bounded public Weibo CDN reads for owner-authorized article images."""
import re
import httpx
from urllib.parse import urlsplit
from fastapi import HTTPException


def weibo_image(url):
    p = urlsplit(url)
    return (p.scheme == 'https' and p.port in (None,443) and not p.username and not p.password
            and bool(re.fullmatch(r'wx[1-4]\.sinaimg\.cn',p.hostname or '')))


async def load_public_image(url):
    if not weibo_image(url):
        raise HTTPException(422, '不支持的微博正文图片地址')
    async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as client:
        async with client.stream('GET',url,headers={'Referer':'https://weibo.com/','User-Agent':'Mozilla/5.0','Accept':'image/*'}) as response:
            if response.status_code != 200:
                raise HTTPException(502, '微博图片暂时无法加载，请重新提取图片')
            chunks=[];size=0
            async for chunk in response.aiter_bytes():
                size+=len(chunk)
                if size>8*1024*1024:
                    raise HTTPException(413,'图片超过 8 MiB')
                chunks.append(chunk)
    data=b''.join(chunks)
    mime = ('image/jpeg' if data.startswith(b'\xff\xd8\xff') else
            'image/png' if data.startswith(b'\x89PNG\r\n\x1a\n') else
            'image/gif' if data.startswith((b'GIF87a',b'GIF89a')) else
            'image/webp' if data.startswith(b'RIFF') and data[8:12]==b'WEBP' else None)
    if not mime:
        raise HTTPException(502,'来源未返回可显示的图片')
    return data,mime
