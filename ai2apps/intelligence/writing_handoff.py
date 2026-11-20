"""Prepare saved Intelligence material for Gallery or a Doc Studio project."""
import asyncio
import io
import zipfile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ai2apps.doc_studio.models import Id
from ai2apps.doc_studio.repository import Repository
from ai2apps.gallery import GalleryRepository
from ai2apps.storage.records import canonical_json

from . import doc_studio_pack
from .html_export import image_failure

MAX_ARTICLES = 20
MAX_GALLERY_IMAGES = 24
GALLERY_IMAGE_BUDGET = 24 * 1024 * 1024
IMAGE_EXTENSIONS = {'image/jpeg': 'jpg', 'image/webp': 'webp'}


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scope: Literal['article', 'section', 'channel', 'topic', 'selection']
    scope_id: str = Field(default='', max_length=256)
    article_ids: list[Id] = Field(default_factory=list, max_length=MAX_ARTICLES)


def prepare(runtime, store, owner, channel_id, selection):
    with store.connect() as db:
        channel = store.unpack(db.execute(
            'SELECT * FROM channels WHERE owner=? AND id=?', (owner, channel_id),
        ).fetchone())
        title = channel['name']
        filters = ['owner=?', 'channel=?']
        values = [owner, channel_id]
        scope_id = selection.scope_id
        if selection.scope == 'selection':
            if not selection.article_ids:
                raise ValueError('请至少选择一篇文章')
            filters.append('id IN (SELECT value FROM json_each(?))')
            values.append(canonical_json(selection.article_ids))
        elif selection.scope == 'article':
            filters.append('id=?')
            values.append(scope_id)
        elif selection.scope == 'section':
            sections = {item['id']: item['name'] for item in channel.get('sections', [])}
            if scope_id == 'unassigned':
                title = '待归类'
                filters.append("coalesce(json_extract(data,'$.section_id'),'') NOT IN (SELECT value FROM json_each(?))")
                values.append(canonical_json(list(sections)))
            elif scope_id in sections:
                title = sections[scope_id]
                filters.append("json_extract(data,'$.section_id')=?")
                values.append(scope_id)
            else:
                raise KeyError('栏目不存在')
        elif selection.scope == 'topic':
            topic = next((item for item in (channel.get('hot_topics') or {}).get('items', [])
                          if item['id'] == scope_id), None)
            if not topic:
                raise KeyError('热点已变化，请刷新后重新选择')
            title = topic['title']
            filters.append('id IN (SELECT value FROM json_each(?))')
            values.append(canonical_json(topic['article_ids']))
        elif scope_id and scope_id != channel_id:
            raise ValueError('频道范围不匹配')
        rows = db.execute(
            'SELECT * FROM articles WHERE ' + ' AND '.join(filters)
            + " ORDER BY coalesce(json_extract(data,'$.updated_at'),'') DESC,id DESC LIMIT ?",
            (*values, MAX_ARTICLES + 1),
        ).fetchall()
        if selection.scope == 'selection' and len(rows) != len(set(selection.article_ids)):
            raise KeyError('所选文章已移除或不属于当前频道')
        if not rows:
            raise ValueError('当前范围暂无文章，请先采集情报')
        articles = [store.unpack(row) for row in rows[:MAX_ARTICLES]]
        manifest = doc_studio_pack.snapshot_articles(db, owner, articles)
    if selection.scope in ('article', 'selection') and len(articles) == 1:
        title = articles[0]['title']
    pack = Repository(runtime.database).save_pack(owner, manifest)
    return {
        'id': pack['id'], 'title': title[:160], 'limited': len(rows) > MAX_ARTICLES,
        'articles': [{'title': entry['title'], 'images': len(entry['images'])} for entry in pack['entries']],
    }


async def _gallery_archive(store, owner, pack):
    urls = {}
    # Embed covers before inline images when the byte or time budget is reached.
    for cover in (True, False):
        for entry in pack['entries']:
            for image in entry['images']:
                if image['cover'] == cover:
                    urls.setdefault(image['url'], image)

    selected = list(urls.items())[:MAX_GALLERY_IMAGES]
    semaphore = asyncio.Semaphore(4)

    async def load(image):
        async with semaphore:
            try:
                return await asyncio.to_thread(doc_studio_pack.load_image, store, owner, image)
            except Exception as error:
                return image_failure(error)

    tasks = {url: asyncio.create_task(load(image)) for url, image in selected}
    if tasks:
        try:
            await asyncio.wait(tasks.values(), timeout=18)
        finally:
            for task in tasks.values():
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks.values(), return_exceptions=True)

    archive = io.BytesIO()
    attachments, failures, used = {}, {}, 0
    with zipfile.ZipFile(archive, 'w') as output:
        for url in urls:
            task = tasks.get(url)
            if task is None or task.cancelled():
                failures[url] = 'image_count_limit' if task is None else 'image_timeout'
                continue
            result = task.result()
            if isinstance(result, str):
                failures[url] = result
                continue
            data, mime = result
            extension = IMAGE_EXTENSIONS.get(mime)
            if not extension or used + len(data) > GALLERY_IMAGE_BUDGET:
                failures[url] = 'unsupported_image' if not extension else 'image_byte_limit'
                continue
            path = f'images/{len(attachments) + 1:03}.{extension}'
            output.writestr(zipfile.ZipInfo(path), data)
            attachments[url] = path
            used += len(data)
        output.writestr(zipfile.ZipInfo('manifest.json'), canonical_json({
            **pack, 'attachments': attachments, 'unembedded_images': failures,
        }), compress_type=zipfile.ZIP_DEFLATED)
    archive.seek(0)
    return archive, len(failures)


async def save_gallery(runtime, store, owner, pack_id):
    pack = Repository(runtime.database).pack(owner, pack_id)
    gallery = GalleryRepository(runtime.database, runtime.config.paths.artifacts_path / 'gallery', runtime.events)
    archive, missing = await _gallery_archive(store, owner, pack)
    asset, created = await asyncio.to_thread(
        gallery.import_stream, owner, archive,
        name=f'Article materials-{pack_id[:12]}-{pack_id[-8:]}.zip',
        media_type='application/zip', source_app_id=doc_studio_pack.SOURCE_APP, source_ref=pack_id,
        metadata={'material_pack_id': pack_id, 'material_pack_schema': pack['schema'],
                  'article_count': len(pack['entries']), 'missing_images': missing},
    )
    return {'asset': asset, 'created': created, 'missing_images': missing}
