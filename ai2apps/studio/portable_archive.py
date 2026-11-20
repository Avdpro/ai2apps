"""Bounded, inert JSON + image ZIP transport; project semantics belong to owners."""
import hashlib
import io
import json
import re
import stat
import zipfile
from PIL import Image

SCHEMA = 'ai2apps.portable-project/v1'
MAX_BYTES = 512 * 1024 * 1024
MAX_JSON = 8 * 1024 * 1024
MAX_ASSETS = 2000
MAX_IMAGE = 20 * 1024 * 1024
KEY = re.compile(r'^[A-Za-z0-9_-]{1,100}$')


def validate_image(data):
    if not 0 < len(data) <= MAX_IMAGE:
        raise ValueError('Image exceeds 20 MiB')
    with Image.open(io.BytesIO(data)) as image:
        if image.format not in ('PNG', 'JPEG', 'WEBP') or image.width * image.height > 25000000:
            raise ValueError('Unsupported image format or dimensions')
        image.verify()


def encode(document, assets):
    if not isinstance(document, dict) or len(assets) > MAX_ASSETS:
        raise ValueError('Invalid archive document or image count')
    entries = []
    files = {}
    total = 0
    for key, data in assets.items():
        if not KEY.fullmatch(key): raise ValueError('Invalid image key')
        validate_image(data)
        digest = hashlib.sha256(data).hexdigest()
        path = f'images/{digest}'
        if path not in files:
            total += len(data)
            files[path] = data
        if total > MAX_BYTES: raise ValueError('Archive exceeds 512 MiB')
        entries.append(dict(key=key, path=path, sha256=digest, size=len(data)))
    manifest = json.dumps(dict(schema=SCHEMA, document=document, assets=entries), ensure_ascii=False, allow_nan=False).encode()
    if len(manifest) > MAX_JSON: raise ValueError('Archive metadata exceeds 8 MiB')
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('manifest.json', manifest)
        for path, data in files.items(): archive.writestr(path, data)
    result = out.getvalue()
    if len(result) > MAX_BYTES: raise ValueError('Archive exceeds 512 MiB')
    return result


def decode(data):
    if not 0 < len(data) <= MAX_BYTES: raise ValueError('ZIP must be between 1 byte and 512 MiB')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if len(names) > MAX_ASSETS + 1 or len(set(names)) != len(names) or 'manifest.json' not in names:
                raise ValueError('Invalid ZIP entries')
            if sum(i.file_size for i in infos) > MAX_BYTES: raise ValueError('Expanded ZIP exceeds 512 MiB')
            for info in infos:
                if (info.flag_bits & 1 or stat.S_ISLNK(info.external_attr >> 16)
                    or info.filename != 'manifest.json' and not re.fullmatch(r'images/[0-9a-f]{64}', info.filename)):
                    raise ValueError('Unsafe ZIP entry')
                if info.file_size > (MAX_JSON if info.filename == 'manifest.json' else MAX_IMAGE):
                    raise ValueError('ZIP entry too large')
            manifest = json.loads(archive.read('manifest.json'))
            if manifest.get('schema') != SCHEMA or not isinstance(manifest.get('document'), dict):
                raise ValueError('Unsupported archive format')
            entries = manifest.get('assets')
            if not isinstance(entries, list) or len(entries) > MAX_ASSETS: raise ValueError('Invalid image inventory')
            assets = {}; used = {'manifest.json'}; cached = {}
            for entry in entries:
                key, path = entry.get('key'), entry.get('path')
                if not isinstance(key, str) or not KEY.fullmatch(key) or key in assets or path not in names or path == 'manifest.json':
                    raise ValueError('Invalid image inventory')
                if path not in cached:
                    image = archive.read(path); validate_image(image); cached[path] = image
                image = cached[path]; digest = hashlib.sha256(image).hexdigest()
                if entry.get('sha256') != digest or path != 'images/' + digest or entry.get('size') != len(image):
                    raise ValueError('Image checksum mismatch')
                assets[key] = image; used.add(path)
            if used != set(names): raise ValueError('Unexpected ZIP content')
            return manifest['document'], assets
    except (zipfile.BadZipFile, KeyError, TypeError, AttributeError, UnicodeError, json.JSONDecodeError, OSError) as error:
        raise ValueError('Invalid or damaged project ZIP') from error
