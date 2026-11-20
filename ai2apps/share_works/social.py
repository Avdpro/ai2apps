"""Owner-scoped social drafts and confirmed X publication."""
import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

import httpx

from .cli import PublishError

KIND = 'share-works.publish-x'
REDNOTE = 'https://creator.rednote.com/publish/publish'
LIMIT = 128 * 1024 * 1024
MEDIA = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
         '.webp': 'image/webp', '.mp4': 'video/mp4', '.mov': 'video/quicktime'}


class XClient:
    def __init__(self):
        token = os.environ.get('AI2APPS_X_USER_ACCESS_TOKEN', '').strip()
        if not token:
            raise PublishError('x_connection_required')
        self.http = httpx.AsyncClient(base_url='https://api.x.com/2/',
                                      headers={'Authorization': f'Bearer {token}'}, timeout=45)

    async def request(self, method, path, **kwargs):
        try:
            response = await self.http.request(method, path, **kwargs)
            if not response.is_success:
                raise PublishError(f'x_http_{response.status_code}')
            payload = response.json() if response.content else {}
            if payload.get('errors'):
                raise PublishError('x_api_error')
            return payload.get('data', {})
        except (httpx.HTTPError, ValueError) as error:
            if isinstance(error, PublishError):
                raise
            raise PublishError('x_response_unavailable') from None

    async def account(self):
        data = await self.request('GET', 'users/me')
        if not (re.fullmatch(r'[0-9]{1,19}', data.get('id', '')) and
                re.fullmatch(r'[A-Za-z0-9_]{1,15}', data.get('username', ''))):
            raise PublishError('x_account_unverified')
        return {'id': data['id'], 'username': data['username']}

    async def upload(self, item, path):
        category = 'tweet_video' if item['type'] == 'video/mp4' else 'tweet_image'
        data = await self.request('POST', 'media/upload/initialize', json={
            'media_category': category, 'media_type': item['type'], 'total_bytes': item['size']})
        media_id = data.get('id', '')
        if not re.fullmatch(r'[0-9]{1,19}', media_id):
            raise PublishError('x_media_unverified')
        upload = f'media/upload/{media_id}'
        with path.open('rb') as stream:
            index = 0
            while chunk := stream.read(3 * 1024 * 1024):
                await self.request('POST', f'{upload}/append', json={
                    'media': base64.b64encode(chunk).decode(), 'segment_index': index})
                index += 1
        data = await self.request('POST', f'{upload}/finalize')
        processing = data.get('processing_info')
        if not processing:
            return media_id
        async with asyncio.timeout(180):
            while processing.get('state') in {'pending', 'in_progress'}:
                await asyncio.sleep(max(1, min(30, int(processing.get('check_after_secs', 2)))))
                data = await self.request('GET', 'media/upload',
                                          params={'command': 'STATUS', 'media_id': media_id})
                processing = data.get('processing_info') or {}
        if processing.get('state') != 'succeeded':
            raise PublishError('x_media_processing_failed')
        return media_id


class SocialWorks:
    def __init__(self, share):
        self.share = share
        self.store = share.store
        self.runtime = share.runtime
        self.x_client = XClient

    async def prepare(self, owner, destination, title, body, sources):
        self.share.authorize(owner)
        if destination not in {'x', 'rednote'}:
            raise PublishError('social_destination_invalid')
        title, body = title.strip(), body.strip()
        if len(title) > 160 or len(body) > 10000 or len(sources) > (4 if destination == 'x' else 18):
            raise PublishError('social_draft_limit')
        if destination == 'x' and title:
            raise PublishError('x_use_post_text')
        if not sources and (destination == 'rednote' or not body):
            raise PublishError('social_content_required')
        account = None
        if destination == 'x':
            client = self.x_client()
            async with client.http:
                account = await client.account()
        draft_id = uuid.uuid4().hex
        folder = self.store.path(owner, draft_id)
        draft = {'id': draft_id, 'destination': destination, 'title': title, 'body': body,
                 'account': account, 'media': [], 'created_at': time.time()}
        try:
            if sources:
                # Wait for local staging before closing caller-owned streams on cancellation.
                staging = asyncio.create_task(asyncio.to_thread(self.stage, folder, destination, sources))
                try:
                    draft['media'] = await asyncio.shield(staging)
                except asyncio.CancelledError:
                    await asyncio.gather(staging, return_exceptions=True)
                    raise
            draft['digest'] = hashlib.sha256(json.dumps(draft, sort_keys=True).encode()).hexdigest()
            self.store.save('social_drafts', owner, draft_id, draft)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return self.view(owner, draft)

    @staticmethod
    def stage(folder, destination, sources):
        folder.mkdir(parents=True, mode=0o700)
        media = []
        remaining = LIMIT
        for index, (filename, stream) in enumerate(sources):
            filename = Path(filename).name
            suffix = Path(filename).suffix.lower()
            mime = MEDIA.get(suffix)
            if not mime or destination == 'x' and suffix == '.mov':
                raise PublishError('social_media_format')
            limit = min(remaining, 5 * 1024 * 1024 if destination == 'x' and mime.startswith('image/') else LIMIT)
            name = f'{index}{suffix}'
            digest = hashlib.sha256()
            size = 0
            with (folder / name).open('xb') as output:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        raise PublishError('social_media_size')
                    digest.update(chunk)
                    output.write(chunk)
            if not size:
                raise PublishError('social_media_empty')
            remaining -= size
            media.append({'filename': filename, 'name': name, 'size': size,
                          'type': mime, 'sha256': digest.hexdigest()})
        if len(media) > 1 and any(item['type'].startswith('video/') for item in media):
            raise PublishError('social_choose_one_video_or_images')
        return media

    def draft(self, owner, draft_id):
        self.share.authorize(owner)
        return self.store.get('social_drafts', owner, draft_id)

    def view(self, owner, draft):
        try:
            record = self.store.get('social_posts', owner, draft['id'])
        except KeyError:
            record = {}
        status = record.get('status', 'pending_manual_publish' if draft['destination'] == 'rednote' else 'prepared')
        task_id = record.get('task_id')
        if task_id and status in {'queued', 'uploading', 'dispatching'}:
            try:
                task = self.runtime.system_tasks.get(owner, task_id)
                if task['status'] in {'failed', 'cancelled', 'interrupted'}:
                    status = 'outcome_unknown' if status == 'dispatching' else task['status']
            except KeyError:
                status = 'outcome_unknown' if status == 'dispatching' else 'interrupted'
        view = {**draft, 'status': status, 'url': record.get('url'), 'task_id': task_id,
                'error': record.get('error')}
        if draft['destination'] == 'rednote':
            view['editor_url'] = REDNOTE
        else:
            view['approval_parameters'] = self.approval_parameters(draft)
        return view

    @staticmethod
    def approval_parameters(draft):
        return {'draft_id': draft['id'], 'digest': draft['digest'],
                'account': '@' + draft['account']['username'], 'body': draft['body'],
                'media_summary': '\n'.join(f"{m['filename']} · {m['size']} bytes" for m in draft['media'])}

    def publish_x(self, owner, draft_id, digest, *, approved):
        if not approved:
            raise PublishError('public_confirmation_required')
        draft = self.draft(owner, draft_id)
        if draft['destination'] != 'x' or digest != draft['digest']:
            raise PublishError('social_draft_changed')
        with self.share.lock:
            try:
                record = self.store.get('social_posts', owner, draft_id)
            except KeyError:
                record = {'status': 'queued'}
                self.store.save('social_posts', owner, draft_id, record)
            if not record.get('task_id') and record['status'] == 'queued':
                key = 'social-x:' + draft_id
                with self.runtime.database.transaction() as db:
                    row = db.execute('SELECT id FROM system_tasks WHERE owner=? AND app_id=? AND kind=? AND dedup_key=? LIMIT 1',
                                     (owner, 'ai2apps.ai-browser', KIND, key)).fetchone()
                task_id = row['id'] if row else self.runtime.system_tasks.submit(
                    owner, 'ai2apps.ai-browser', KIND, 'Publish to X',
                    {'draft_id': draft_id}, dedup_key=key)['id']
                # The executor may already have updated the record.
                record = self.store.get('social_posts', owner, draft_id)
                record['task_id'] = task_id
                self.store.save('social_posts', owner, draft_id, record)
        return self.view(owner, draft)

    async def execute_x(self, ctx):
        owner, draft_id = ctx.owner, ctx.payload['draft_id']
        draft = self.draft(owner, draft_id)
        with self.share.lock:
            record = self.store.get('social_posts', owner, draft_id)
            if record['status'] != 'queued' or draft['destination'] != 'x':
                raise PublishError('social_already_attempted')
            record['status'] = 'uploading'
            self.store.save('social_posts', owner, draft_id, record)
        try:
            client = self.x_client()
            async with client.http:
                if await client.account() != draft['account']:
                    raise PublishError('x_account_changed')
                media_ids = []
                for index, item in enumerate(draft['media']):
                    ctx.report(message='Uploading media', progress={'done': index, 'total': len(draft['media'])})
                    path = self.store.path(owner, draft_id) / item['name']
                    with path.open('rb') as stream:
                        digest = await asyncio.to_thread(lambda: hashlib.file_digest(stream, 'sha256').hexdigest())
                    if digest != item['sha256']:
                        raise PublishError('social_draft_changed')
                    media_ids.append(await client.upload(item, path))
                payload = {'text': draft['body']} if draft['body'] else {}
                if media_ids:
                    payload['media'] = {'media_ids': media_ids}
                self.set_status(owner, draft_id, 'dispatching')
                ctx.report(message='Posting to X')
                data = await client.request('POST', 'tweets', json=payload)
                post_id = data.get('id', '')
                if not re.fullmatch(r'[0-9]{1,19}', post_id):
                    raise PublishError('x_post_unverified')
                url = f"https://x.com/{draft['account']['username']}/status/{post_id}"
                self.set_status(owner, draft_id, 'published', url=url)
                return {'url': url, 'post_id': post_id}
        except BaseException as error:
            record = self.store.get('social_posts', owner, draft_id)
            if record['status'] != 'published':
                status = 'failed'
                if record['status'] == 'dispatching':
                    code = getattr(error, 'code', '')
                    if not re.fullmatch(r'x_http_4[0-9]{2}', code) or code == 'x_http_408':
                        status = 'outcome_unknown'
                elif isinstance(error, asyncio.CancelledError):
                    status = 'cancelled'
                self.set_status(owner, draft_id, status, error=getattr(error, 'code', None))
            raise

    def set_status(self, owner, draft_id, status, **fields):
        with self.share.lock:
            record = self.store.get('social_posts', owner, draft_id)
            self.store.save('social_posts', owner, draft_id, {**record, **fields, 'status': status})
