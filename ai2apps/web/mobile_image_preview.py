"""Fixed, bounded Mobile image previews; originals and their authorization stay owned."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import HTTPException
from starlette.responses import Response

MAX_SOURCE=64*1024*1024
MAX_PIXELS=64_000_000
MAX_EDGE=960
MAX_PREVIEW=160*1024
_POOL=ThreadPoolExecutor(max_workers=2,thread_name_prefix='mobile-image-preview')
RASTER=frozenset(('image/jpeg','image/png','image/webp','image/avif','image/gif'))


def _encode(content):
    if not content or len(content)>MAX_SOURCE:raise HTTPException(413,'Image too large for Mobile preview')
    try:
        with Image.open(BytesIO(content)) as source:
            if source.width*source.height>MAX_PIXELS:raise HTTPException(413,'Image dimensions exceed preview limit')
            source.seek(0)
            # Apply orientation, flatten alpha on white, and omit EXIF/location metadata.
            image=ImageOps.exif_transpose(source)
            image.thumbnail((MAX_EDGE,MAX_EDGE),Image.Resampling.LANCZOS)
            if image.mode in ('RGBA','LA') or 'transparency' in image.info:
                rgba=image.convert('RGBA');rgb=Image.new('RGB',rgba.size,'white');rgb.paste(rgba,mask=rgba.getchannel('A'));image=rgb
            else:image=image.convert('RGB')
            quality=58
            while True:
                out=BytesIO();image.save(out,format='JPEG',quality=quality,optimize=True,progressive=True,exif=b'')
                result=out.getvalue()
                if len(result)<=MAX_PREVIEW:return result
                if quality>35:quality-=12
                else:image.thumbnail((max(64,int(image.width*.75)),max(64,int(image.height*.75))),Image.Resampling.LANCZOS)
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError) as error:
        raise HTTPException(422,'Raster image cannot be previewed') from error


@lru_cache(maxsize=128)
def _file(path,mtime,size):
    if size>MAX_SOURCE:raise HTTPException(413,'Image too large for Mobile preview')
    return _encode(Path(path).read_bytes())


async def preview_bytes(content):
    return await asyncio.get_running_loop().run_in_executor(_POOL,_encode,content)


async def preview_file(path):
    path=Path(path);stat=path.stat()
    return await asyncio.get_running_loop().run_in_executor(_POOL,_file,str(path.resolve()),stat.st_mtime_ns,stat.st_size)


def response(content):
    return Response(content,media_type='image/jpeg',headers={'Cache-Control':'no-store',
        'X-Content-Type-Options':'nosniff','X-AI2Apps-Image-Variant':'mobile-preview'})
