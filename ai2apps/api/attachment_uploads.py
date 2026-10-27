"""Bounded, sequential Session uploads into the owning user's Gallery.

Chunks fit authenticated Mobile request signing bounds. There is deliberately no
cross-client resume or automatic retry; the completed asset is the durable unit.
"""
import asyncio
import json
import re
import shutil
import time
import uuid
import weakref
from pathlib import Path

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ai2apps.api.documents import _attachment
from ai2apps.gallery import GalleryRepository

MAX_BYTES = 8 * 1024**3
CHUNK_BYTES = 4 * 1024**2
_LOCKS = weakref.WeakValueDictionary()


class StartUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=512)
    media_type: str = Field(default='application/octet-stream', max_length=255)
    size_bytes: int = Field(gt=0, le=MAX_BYTES)


def install(router, runtime_provider, principal_provider):
    dep = Depends(principal_provider)

    def state(runtime, session_id, identifier, principal):
        if not re.fullmatch(r'[0-9a-f]{32}', identifier):
            raise HTTPException(404, 'Upload not found')
        root = runtime.documents.root / 'pending-uploads' / identifier
        try:
            value = json.loads((root / 'state.json').read_text())
        except (OSError, ValueError):
            raise HTTPException(404, 'Upload not found') from None
        if (value['session_id'], value['owner']) != (session_id, principal.actor_user_id):
            raise HTTPException(404, 'Upload not found')
        if time.time() - value['created'] > 86400:
            shutil.rmtree(root, ignore_errors=True)
            raise HTTPException(410, 'Upload expired; select the file again')
        return root, value

    @router.post('/uploads', status_code=201)
    async def start(session_id: str, body: StartUpload, principal=dep):
        runtime = runtime_provider()
        if not Path(body.filename).name.strip() or Path(body.filename).name in {'.','..'}:
            raise HTTPException(422, 'Choose a named file')
        root = runtime.documents.root / 'pending-uploads' / uuid.uuid4().hex
        root.mkdir(parents=True, mode=0o700)
        value = {**body.model_dump(), 'owner': principal.actor_user_id,
                 'session_id': session_id, 'created': time.time()}
        (root / 'state.json').write_text(json.dumps(value))
        (root / 'source').touch(mode=0o600)
        return {'id': root.name, 'chunk_bytes': CHUNK_BYTES, 'received_bytes': 0}

    @router.put('/uploads/{upload_id}')
    async def chunk(session_id: str, upload_id: str, request: Request, offset: int, principal=dep):
        runtime = runtime_provider()
        async with _LOCKS.setdefault(upload_id, asyncio.Lock()):
            root, value = state(runtime, session_id, upload_id, principal)
            if value.get('attachment_id'):
                raise HTTPException(409, 'Upload already completed')
            source = root / 'source'
            if offset < 0 or offset != source.stat().st_size:
                raise HTTPException(409, 'Upload offset mismatch; select the file again')
            received = 0
            with source.open('ab') as output:
                try:
                    async for data in request.stream():
                        received += len(data)
                        if received > CHUNK_BYTES or offset + received > value['size_bytes']:
                            raise HTTPException(413, 'Upload chunk exceeds declared bounds')
                        await asyncio.to_thread(output.write, data)
                    if not received:
                        raise HTTPException(422, 'Empty upload chunk')
                except BaseException:
                    output.truncate(offset)
                    raise
            return {'id': upload_id, 'received_bytes': offset + received}

    @router.post('/uploads/{upload_id}/complete')
    async def complete(session_id: str, upload_id: str, principal=dep):
        runtime = runtime_provider()
        async with _LOCKS.setdefault(upload_id, asyncio.Lock()):
            root, value = state(runtime, session_id, upload_id, principal)
            if value.get('attachment_id'):
                return _attachment(runtime.documents.get(session_id, value['attachment_id']))
            source = root / 'source'
            if not value.get('gallery_asset_id'):
                if source.stat().st_size != value['size_bytes']:
                    raise HTTPException(409, 'Upload is incomplete')
                gallery = GalleryRepository(runtime.database, runtime.config.paths.artifacts_path / 'gallery', runtime.events)
                def adopt():
                    with source.open('rb') as stream:
                        return gallery.import_stream(principal.actor_user_id, stream,
                            name=value['filename'], media_type=None if value['media_type']=='application/octet-stream' else value['media_type'],
                            source_app_id='ai2apps.general-chat', source_ref='upload:' + upload_id,
                            metadata={'surface': 'mobile', 'session_id': session_id},
                            max_bytes=MAX_BYTES, _adopt_path=source)[0]
                asset = await asyncio.to_thread(adopt)
                value['gallery_asset_id'] = asset['id']
                (root / 'state.json').write_text(json.dumps(value))
            gallery = GalleryRepository(runtime.database, runtime.config.paths.artifacts_path / 'gallery')
            asset, path = gallery.asset_path(principal.actor_user_id, value['gallery_asset_id'])
            item = runtime.documents.create_reference(session_id, path, filename=asset['name'],
                media_type=asset['media_type'], source='gallery_upload',
                gallery_asset_id=asset['id'], owner_user_id=principal.actor_user_id)
            value['attachment_id'] = item.id
            (root / 'state.json').write_text(json.dumps(value))
            return _attachment(item)

    @router.post('/uploads/{upload_id}/cancel')
    async def cancel(session_id: str, upload_id: str, principal=dep):
        runtime = runtime_provider()
        async with _LOCKS.setdefault(upload_id, asyncio.Lock()):
            root, value = state(runtime, session_id, upload_id, principal)
            if value.get('gallery_asset_id'):
                raise HTTPException(409, 'Completed material is managed in Gallery')
            shutil.rmtree(root)
            return {'status': 'cancelled'}
