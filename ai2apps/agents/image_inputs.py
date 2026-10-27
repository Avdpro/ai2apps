"""Keep uploaded originals in Session storage and bound model vision previews."""
import base64
import hashlib
import io
from pathlib import Path
import tempfile

from PIL import Image, ImageOps

MAX_IMAGE_BYTES = 20 * 1024 * 1024
PREVIEW_BYTES = 24 * 1024
MAX_PREVIEWS = 8


def project_uploaded_images(messages, workspace, session_id):
    """Never mutate archived input or fetch arbitrary URLs during projection."""
    result = []
    previews = 0
    for message in messages:
        if message.get('role') != 'user' or not isinstance(message.get('content'), list):
            result.append(message)
            continue
        content = []
        for part in message['content']:
            image = part.get('image_url') if isinstance(part, dict) else None
            url = image.get('url', '') if isinstance(image, dict) else ''
            if not isinstance(url, str) or not url.startswith('data:image/'):
                content.append(part)
                continue
            header, separator, encoded = url.partition(',')
            if not separator or not header.endswith(';base64') or len(encoded) > (MAX_IMAGE_BYTES + 2) // 3 * 4:
                raise ValueError('Uploaded image must be base64 encoded and at most 20 MiB')
            raw = base64.b64decode(encoded, validate=True)
            if len(raw) > MAX_IMAGE_BYTES:
                raise ValueError('Uploaded image exceeds 20 MiB')
            with Image.open(io.BytesIO(raw)) as original:
                fmt = original.format
                if fmt not in {'PNG', 'JPEG', 'WEBP'}:
                    raise ValueError('Agent image inputs require PNG, JPEG or WebP')
                original.load()
                preview = ImageOps.exif_transpose(original).convert('RGB')
            digest = hashlib.sha256(raw).hexdigest()
            extension = {'PNG':'png', 'JPEG':'jpg', 'WEBP':'webp'}[fmt]
            with tempfile.TemporaryDirectory(prefix='agent-image-') as directory:
                path = Path(directory) / f'uploaded-{digest}.{extension}'
                path.write_bytes(raw)
                artifact = workspace.import_artifact(session_id, path, name=path.name,
                    media_type={'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp'}[fmt],
                    metadata={'source':'agent-upload'})
            content.append({'type':'text', 'text':f'Uploaded image artifact_id={artifact.id}. Original preserved in this Session. Use this ID for image tools (including person_artifact_ids for group photos). The following preview, when present, is reduced for visual understanding; use the original artifact for generation/editing.'})
            if previews < MAX_PREVIEWS:
                preview.thumbnail((512, 512))
                while True:
                    output = io.BytesIO()
                    preview.save(output, format='JPEG', quality=65)
                    data = output.getvalue()
                    if len(data) <= PREVIEW_BYTES:
                        break
                    preview.thumbnail((max(1,preview.width*3//4), max(1,preview.height*3//4)))
                content.append({'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(data).decode(),'detail':'low'}})
                previews += 1
            else:
                content.append({'type':'text','text':'Preview omitted because this request already contains eight uploaded-image previews; the original artifact remains available.'})
        result.append({**message,'content':content})
    return result
