from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .models import public_url


def stamp():
    return datetime.now(timezone.utc).isoformat()


def key():
    return uuid.uuid4().hex


def fingerprint(page):
    return hashlib.sha256(' '.join(page['text'].split()).encode()).hexdigest()


class IntelligenceStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS filtered_posts(owner TEXT NOT NULL, channel TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(owner,channel,id));
                CREATE TABLE IF NOT EXISTS knowledge_exports(owner TEXT NOT NULL, channel TEXT NOT NULL, article TEXT NOT NULL, bucket TEXT NOT NULL, hash TEXT NOT NULL, status TEXT NOT NULL, item_id TEXT, error TEXT NOT NULL DEFAULT '', updated REAL NOT NULL, PRIMARY KEY(owner,article,bucket));
                CREATE TABLE IF NOT EXISTS social_limits(owner TEXT NOT NULL, site TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(owner,site));
                CREATE TABLE IF NOT EXISTS drafts(owner TEXT NOT NULL, channel TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(owner,id));
                CREATE TABLE IF NOT EXISTS preferences(owner TEXT NOT NULL, channel TEXT NOT NULL, article TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(owner,article));
                CREATE TABLE IF NOT EXISTS conversations(owner TEXT NOT NULL, channel TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(owner,channel,id));
                CREATE TABLE IF NOT EXISTS site_recipes(owner TEXT NOT NULL, key TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(owner,key));
                CREATE TABLE IF NOT EXISTS channels(id TEXT PRIMARY KEY, owner TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, owner TEXT NOT NULL, channel TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS articles(id TEXT PRIMARY KEY, owner TEXT NOT NULL, channel TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS pages(owner TEXT NOT NULL, channel TEXT NOT NULL, url TEXT NOT NULL, hash TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(owner,channel,url));
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, owner TEXT NOT NULL, channel TEXT NOT NULL, status TEXT NOT NULL, updated REAL NOT NULL, data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS source_channel ON sources(owner,channel);
                CREATE INDEX IF NOT EXISTS article_channel ON articles(owner,channel);
                CREATE INDEX IF NOT EXISTS run_channel ON runs(owner,channel,status);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / 'intelligence.sqlite3', timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def unpack(row):
        if row is None:
            raise KeyError('记录不存在或不属于当前用户')
        result = {**json.loads(row['data']), 'id': row['id']}
        if 'channel' in row.keys():
            result['channel_id'] = row['channel']
        if 'status' in row.keys():
            result['status'] = row['status']
        return result

    def get(self, table, owner, id):
        assert table in ('channels', 'sources', 'articles', 'runs')
        with self.connect() as db:
            return self.unpack(db.execute(f'SELECT * FROM {table} WHERE owner=? AND id=?', (owner, id)).fetchone())

    def snapshot(self, owner):
        self.expire(owner)
        with self.connect() as db:
            result = {table: [self.unpack(row) for row in db.execute(
                f'SELECT * FROM {table} WHERE owner=? ORDER BY rowid DESC' + (' LIMIT 100' if table == 'runs' else ''), (owner,))]
                    for table in ('channels', 'sources', 'articles', 'runs')}
            for channel in result['channels']:
                jobs = db.execute('SELECT status,error FROM knowledge_exports WHERE owner=? AND channel=?', (owner,channel['id'])).fetchall()
                channel['knowledge_sync'] = {status: sum(j['status']==status for j in jobs) for status in ('pending','synced','failed')}
                channel['knowledge_sync']['errors'] = list(dict.fromkeys(j['error'] for j in jobs if j['error']))[:3]
            return result

    def save_channel(self, owner, data, id=None):
        data = dict(data)
        if data.get('output_language') is None:
            data.pop('output_language', None)
        expected = data.pop('expected_sections', None)
        sections = data.pop('sections', None)
        with self.connect() as db:
            previous = self.unpack(db.execute('SELECT * FROM channels WHERE owner=? AND id=?', (owner, id)).fetchone()) if id else {}
            id = id or key()
            if sections is not None:
                if expected is not None and expected != previous.get('sections', []):
                    raise ValueError('栏目已被修改，请重新打开频道设置后再保存')
                if sections != previous.get('sections', []) and db.execute("SELECT 1 FROM runs WHERE owner=? AND channel=? AND status='running'", (owner, id)).fetchone():
                    raise ValueError('频道正在采集，请完成后再修改栏目')
                data['sections'] = sections
            if data.get('knowledge_bucket_ids') is None:
                data['knowledge_bucket_ids'] = previous.get('knowledge_bucket_ids', [])
            data = {**previous, **data, 'updated_at': stamp(), 'created_at': previous.get('created_at', stamp())}
            if previous.get('interval_hours') != data['interval_hours']:
                data['schedule_anchor'] = datetime.now(timezone.utc).timestamp()
            db.execute('INSERT INTO channels VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data', (id, owner, json.dumps(data)))
            if sections is not None:
                valid = {s['id'] for s in sections}
                for row in db.execute('SELECT * FROM articles WHERE owner=? AND channel=?', (owner, id)).fetchall():
                    article = self.unpack(row)
                    if article.get('section_id') and article['section_id'] not in valid:
                        article['section_id'] = None
                        db.execute('UPDATE articles SET data=? WHERE owner=? AND id=?', (json.dumps(article), owner, article['id']))
            self._queue_channel(db, owner, {**data, 'id': id})
        return self.get('channels', owner, id)

    def import_article(self, owner, channel, article, identity):
        with self.connect() as db:
            current = self.unpack(db.execute('SELECT * FROM channels WHERE owner=? AND id=?', (owner, channel)).fetchone())
            for row in db.execute('SELECT * FROM articles WHERE owner=? AND channel=?', (owner, channel)):
                existing = self.unpack(row)
                if existing.get('import_identity') == identity or any(s.get('url') == identity for s in existing.get('sources', [])):
                    if article.get('image_ai_summary') and not existing.get('image_ai_summary'):
                        existing.update({k: article[k] for k in ('title', 'summary', 'body', 'section_id', 'image_ai_summary') if k in article})
                        existing['updated_at'] = stamp()
                        db.execute('UPDATE articles SET data=? WHERE owner=? AND id=?', (json.dumps(existing), owner, existing['id']))
                        self._queue_channel(db, owner, current)
                    return existing
            id = key()
            article = {**article, 'manual_import': True, 'import_identity': identity, 'created_at': stamp(), 'updated_at': stamp(), 'read': False, 'feedback': ''}
            db.execute('INSERT INTO articles VALUES(?,?,?,?)', (id, owner, channel, json.dumps(article)))
            self._queue_channel(db, owner, current)
        return self.get('articles', owner, id)

    def reorder_sections(self, owner, channel, ids):
        with self.connect() as db:
            current = self.unpack(db.execute('SELECT * FROM channels WHERE owner=? AND id=?', (owner, channel)).fetchone())
            sections = {s['id']: s for s in current.get('sections', [])}
            if len(ids) != len(set(ids)) or set(ids) != set(sections):
                raise ValueError('栏目已变化，请刷新后重试')
            current.update(sections=[sections[id] for id in ids], updated_at=stamp())
            db.execute('UPDATE channels SET data=? WHERE owner=? AND id=?', (json.dumps(current), owner, channel))
        return current

    def initialize_sections(self, owner, channel, sections, assignments, articles):
        versions = {a['id']: a.get('updated_at') for a in articles}
        with self.connect() as db:
            current = self.unpack(db.execute('SELECT * FROM channels WHERE owner=? AND id=?', (owner, channel)).fetchone())
            if current.get('sections'):
                raise ValueError('此频道已有栏目，请刷新')
            if db.execute("SELECT 1 FROM runs WHERE owner=? AND channel=? AND status='running'", (owner, channel)).fetchone():
                raise ValueError('请等待频道更新结束后创建栏目')
            current.update(sections=sections, updated_at=stamp())
            db.execute('UPDATE channels SET data=? WHERE owner=? AND id=?', (json.dumps(current), owner, channel))
            for row in db.execute('SELECT * FROM articles WHERE owner=? AND channel=?', (owner, channel)).fetchall():
                article = self.unpack(row)
                if article['id'] not in assignments or article.get('updated_at') != versions.get(article['id']):
                    continue
                article['section_id'] = assignments[article['id']]
                db.execute('UPDATE articles SET data=? WHERE owner=? AND id=?', (json.dumps(article), owner, article['id']))
            self._queue_channel(db, owner, current)
        return self.get('channels', owner, channel)

    def site_recipe(self, owner, recipe_key):
        with self.connect() as db:
            row = db.execute('SELECT data FROM site_recipes WHERE owner=? AND key=?', (owner, recipe_key)).fetchone()
            return json.loads(row['data']) if row else None

    def invalidate_site_recipe(self, owner, recipe_key, generation_id):
        with self.connect() as db:
            row = db.execute('SELECT data FROM site_recipes WHERE owner=? AND key=?', (owner, recipe_key)).fetchone()
            record = json.loads(row['data']) if row else None
            if record and record['generation_id'] == generation_id:
                record.update(healthy=False, updated_at=stamp())
                db.execute('UPDATE site_recipes SET data=? WHERE owner=? AND key=?', (json.dumps(record), owner, recipe_key))

    def save_site_recipe(self, owner, recipe_key, data):
        with self.connect() as db:
            db.execute('INSERT INTO site_recipes VALUES(?,?,?) ON CONFLICT(owner,key) DO UPDATE SET data=excluded.data',
                       (owner, recipe_key, json.dumps({**data, 'updated_at': stamp()})))

    def save_source(self, owner, channel, data, id=None):
        self.get('channels', owner, channel)
        if id:
            previous = self.get('sources', owner, id)
            if previous['channel_id'] != channel:
                raise ValueError('信息源与频道不匹配')
            data = {**{k:v for k,v in previous.items() if k.startswith('social_')},**data}
        with self.connect() as db:
            if not id and db.execute('SELECT COUNT(*) FROM sources WHERE owner=? AND channel=?', (owner, channel)).fetchone()[0] >= 12:
                raise ValueError('第一版每个频道最多 12 个信息源')
            for row in db.execute('SELECT * FROM sources WHERE owner=? AND channel=?', (owner, channel)):
                if row['id'] != id and json.loads(row['data'])['url'] == data['url']:
                    raise ValueError('该信息源已在频道中')
            id = id or key()
            db.execute('INSERT INTO sources VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data', (id, owner, channel, json.dumps(data)))
        return self.get('sources', owner, id)

    def delete(self, table, owner, id):
        self.get(table, owner, id)
        assert table in ('sources', 'channels')
        with self.connect() as db:
            channel = id if table == 'channels' else self.unpack(db.execute('SELECT * FROM sources WHERE owner=? AND id=?', (owner, id)).fetchone())['channel_id']
            if db.execute("SELECT 1 FROM runs WHERE owner=? AND channel=? AND status='running'", (owner, channel)).fetchone():
                raise ValueError('请等待本轮更新结束后删除')
            db.execute(f'DELETE FROM {table} WHERE owner=? AND id=?', (owner, id))
            if table == 'channels':
                for child in ('sources', 'articles', 'pages', 'runs', 'knowledge_exports', 'conversations', 'preferences', 'drafts', 'filtered_posts'):
                    db.execute(f'DELETE FROM {child} WHERE owner=? AND channel=?', (owner, id))

    def expire(self, owner):
        with self.connect() as db:
            db.execute("UPDATE runs SET status='interrupted' WHERE owner=? AND status='running' AND COALESCE(json_extract(data,'$.execution_owner'),'') != 'local' AND updated < ?", (owner, datetime.now(timezone.utc).timestamp() - 600))

    def claim(self, owner, channel, scheduled=False, *, background_session=None):
        self.expire(owner)
        now = datetime.now(timezone.utc).timestamp()
        with self.connect() as db:
            current = self.unpack(db.execute('SELECT * FROM channels WHERE owner=? AND id=?', (owner, channel)).fetchone())
            if db.execute("SELECT 1 FROM runs WHERE owner=? AND channel=? AND status='running'", (owner, channel)).fetchone():
                raise ValueError('此频道已在更新中')
            if not db.execute('SELECT 1 FROM sources WHERE owner=? AND channel=? AND json_extract(data,\'$.enabled\')=1', (owner, channel)).fetchone():
                raise ValueError('请先添加并启用信息源')
            interval = current.get('interval_hours', 0) * 3600
            anchor = max(current.get('schedule_anchor', now), current.get('last_attempt', 0))
            if scheduled and (not interval or now < anchor + interval):
                raise ValueError('尚未到更新时间')
            id = key()
            data = {'started_at': stamp(), 'message': '准备采集', 'logs': [], 'scheduled': scheduled}
            if background_session:data['execution_owner'] = 'local'
            db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)', (id, owner, channel, 'running', now, json.dumps(data)))
            if background_session:
                sources = [self.unpack(row) for row in db.execute("SELECT * FROM sources WHERE owner=? AND channel=? AND json_extract(data,'$.enabled')=1", (owner,channel))]
                db.execute('INSERT INTO collection_jobs VALUES(?,?,?,?)', (id,owner,background_session,json.dumps({'sources':sources})))
                db.execute('INSERT INTO collection_schedules VALUES(?,?) ON CONFLICT(owner) DO UPDATE SET session_id=excluded.session_id', (owner,background_session))
            current['last_attempt'] = now
            db.execute('UPDATE channels SET data=? WHERE owner=? AND id=?', (json.dumps(current), owner, channel))
        return self.get('runs', owner, id)

    def progress(self, owner, id, message, status='running', logs=None):
        with self.connect() as db:
            current = self.unpack(db.execute('SELECT * FROM runs WHERE owner=? AND id=?', (owner, id)).fetchone())
            if current['status'] != 'running':
                raise ValueError('本轮更新已结束，请重新更新')
            current['message'] = message
            if logs is not None:
                current['logs'] = logs
            if status != 'running':
                current['finished_at'] = stamp()
            db.execute('UPDATE runs SET data=?,status=?,updated=? WHERE owner=? AND id=?', (json.dumps(current), status, datetime.now(timezone.utc).timestamp(), owner, id))

    def pending_candidates(self, owner, channel, candidates, seen_urls=()):
        """Filter before navigation, using only successfully committed page history."""
        self.get('channels', owner, channel)
        seen = {public_url(url) for url in seen_urls}
        urls = list(dict.fromkeys(public_url(item['url']) for item in candidates))
        if urls:
            placeholders = ','.join('?' for _ in urls)
            with self.connect() as db:
                rows = db.execute(
                    f"SELECT url,json_extract(data,'$.requested_url') AS requested_url FROM pages "
                    f"WHERE owner=? AND channel=? AND (url IN ({placeholders}) OR "
                    f"json_extract(data,'$.requested_url') IN ({placeholders}))",
                    [owner, channel, *urls, *urls])
                for row in rows:
                    seen.add(row['url'])
                    if row['requested_url']:
                        seen.add(row['requested_url'])
        pending = []
        for item in candidates:
            url = public_url(item['url'])
            if url not in seen:
                pending.append({**item, 'url': url})
                seen.add(url)
        return {'candidates': pending, 'skipped': len(candidates) - len(pending)}

    def new_pages(self, owner, channel, pages):
        self.get('channels', owner, channel)
        result = []
        seen = set()
        with self.connect() as db:
            for page in pages:
                source = self.unpack(db.execute('SELECT * FROM sources WHERE owner=? AND id=? AND channel=?', (owner, page['source_id'], channel)).fetchone())
                if not source['enabled']:
                    continue
                old = db.execute('SELECT hash FROM pages WHERE owner=? AND channel=? AND url=?', (owner, channel, page['url'])).fetchone()
                if page['url'] not in seen and (old is None or old['hash'] != fingerprint(page)):
                    result.append({**page, 'source_name': source['name'], 'retrieved_at': stamp()})
                    seen.add(page['url'])
        return result

    def finish(self, owner, run_id, pages, articles, logs):
        with self.connect() as db:
            run = self.unpack(db.execute('SELECT * FROM runs WHERE owner=? AND id=?', (owner, run_id)).fetchone())
            if run['status'] != 'running':
                raise ValueError('本轮更新已结束')
            channel = run['channel_id']
            for page in pages:
                db.execute('INSERT INTO pages VALUES(?,?,?,?,?) ON CONFLICT(owner,channel,url) DO UPDATE SET hash=excluded.hash,data=excluded.data', (owner, channel, page['url'], fingerprint(page), json.dumps(page)))
            for article in articles:
                id = article.pop('update_article_id', None) or key()
                old = db.execute('SELECT * FROM articles WHERE owner=? AND channel=? AND id=?', (owner, channel, id)).fetchone()
                if old:
                    previous = self.unpack(old)
                    if not article.get('cover_image') and previous.get('cover_image'):
                        article['cover_image'] = previous['cover_image']
                    if not article.get('images') and previous.get('images'):
                        article['images'] = previous['images']
                    article['created_at'] = previous['created_at']
                    article['read'] = False
                    article['feedback'] = previous.get('feedback', '')
                    for field in ('feedback_reasons', 'feedback_at'):
                        if field in previous:
                            article[field] = previous[field]
                    article['versions'] = (previous.get('versions', []) + [{'updated_at': previous['updated_at'], 'title': previous['title'], 'body': previous['body'], 'sources': previous['sources']}])[-5:]
                else:
                    article.update(created_at=stamp(), read=False, feedback='')
                article.update(updated_at=stamp(), run_id=run_id)
                db.execute('INSERT INTO articles VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data', (id, owner, channel, json.dumps(article)))
            current_channel = self.unpack(db.execute('SELECT * FROM channels WHERE owner=? AND id=?', (owner, channel)).fetchone())
            self._queue_channel(db, owner, current_channel)
            status = 'partial' if any(log['status'] != 'success' for log in logs) else 'completed'
            if not pages and logs and all(log['status'] not in ('success','deferred') for log in logs):
                status = 'failed'
            skipped = sum(log.get('skipped', 0) for log in logs)
            prefix = f'跳过已采集 / 重复 {skipped} 条，' if skipped else ''
            run.update(message=prefix + f'读取 {sum(x.get("pages", 0) for x in logs)} 篇，发现 {len(pages)} 篇变化，生成 / 更新 {len(articles)} 篇情报', logs=logs, finished_at=stamp(), article_count=len(articles))
            db.execute('UPDATE runs SET status=?,data=?,updated=? WHERE owner=? AND id=?', (status, json.dumps(run), datetime.now(timezone.utc).timestamp(), owner, run_id))

    def _queue_channel(self, db, owner, channel):
        from .knowledge_sync import document
        buckets = channel.get('knowledge_bucket_ids', [])
        for row in db.execute('SELECT bucket FROM knowledge_exports WHERE owner=? AND channel=?', (owner,channel['id'])).fetchall():
            if row['bucket'] not in buckets:
                db.execute('DELETE FROM knowledge_exports WHERE owner=? AND channel=? AND bucket=?', (owner,channel['id'],row['bucket']))
        if not buckets:
            return
        for row in db.execute('SELECT * FROM articles WHERE owner=? AND channel=?', (owner,channel['id'])).fetchall():
            article = self.unpack(row)
            _, digest = document(channel, article)
            for bucket in buckets:
                db.execute("""INSERT INTO knowledge_exports(owner,channel,article,bucket,hash,status,updated)
                    VALUES(?,?,?,?,?,'pending',0) ON CONFLICT(owner,article,bucket) DO UPDATE SET
                    hash=excluded.hash,status='pending',error='',updated=0 WHERE knowledge_exports.hash<>excluded.hash""",
                    (owner,channel['id'],article['id'],bucket,digest))

    def knowledge_jobs(self, owner, channel=None, retry=False):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM knowledge_exports WHERE owner=? AND (status='pending' OR (status='failed' AND updated<?))"
                + (' AND channel=?' if channel else '') + " ORDER BY updated LIMIT 50",
                [owner, datetime.now(timezone.utc).timestamp() + (1 if retry else -60), *([channel] if channel else [])])]

    def complete_knowledge_job(self, owner, job, item_id, error, digest):
        with self.connect() as db:
            db.execute("""UPDATE knowledge_exports SET status=?,item_id=COALESCE(?,item_id),error=?,updated=?
                WHERE owner=? AND article=? AND bucket=? AND hash=?""",
                ('failed' if error else ('synced' if digest==job['hash'] else 'pending'), item_id, error,
                 datetime.now(timezone.utc).timestamp(), owner,job['article'],job['bucket'],job['hash']))

    def feedback(self, owner, id, feedback=None, read=None, reasons=None, reason_signature=None):
        with self.connect() as db:
            article = self.unpack(db.execute('SELECT * FROM articles WHERE owner=? AND id=?', (owner, id)).fetchone())
            if feedback is not None:
                from .feedback import signature
                channel = self.unpack(db.execute('SELECT * FROM channels WHERE owner=? AND id=?', (owner, article['channel_id'])).fetchone())
                reasons = list(dict.fromkeys(reasons or []))
                if feedback == 'less':
                    options = article.get('feedback_options', {})
                    if (not reasons or not reason_signature or reason_signature != options.get('signature')
                        or reason_signature != signature(channel, article)
                        or any(r not in options.get('reasons', []) for r in reasons)):
                        raise ValueError('请选择当前 AI 生成的踩理由；文章变化后请重新生成')
                elif reasons:
                    raise ValueError('只有踩反馈可以包含理由')
                article['feedback'] = feedback
                article['feedback_reasons'] = reasons
                article['feedback_at'] = stamp()
                if feedback:
                    record = {'article_id':id, 'channel_id':article['channel_id'], 'channel_name':channel['name'],
                        'channel_interests':channel['interests'], 'title':article['title'], 'summary':article['summary'],
                        'section_id':article.get('section_id'), 'feedback':feedback, 'reasons':reasons,
                        'updated_at':article['feedback_at']}
                    db.execute('INSERT INTO preferences VALUES(?,?,?,?) ON CONFLICT(owner,article) DO UPDATE SET data=excluded.data',
                        (owner, article['channel_id'], id, json.dumps(record, ensure_ascii=False)))
                else:
                    db.execute('DELETE FROM preferences WHERE owner=? AND article=?', (owner,id))
            if read is not None:
                article['read'] = read
            db.execute('UPDATE articles SET data=? WHERE owner=? AND id=?', (json.dumps(article), owner, id))
        return article

    def conversation(self, owner, channel):
        self.get('channels', owner, channel)
        with self.connect() as db:
            rows = db.execute('SELECT data FROM conversations WHERE owner=? AND channel=? ORDER BY rowid DESC LIMIT 100', (owner,channel)).fetchall()
            return [json.loads(row['data']) for row in reversed(rows)]

    def conversation_turn(self, owner, channel, request_id):
        self.get('channels', owner, channel)
        with self.connect() as db:
            row = db.execute('SELECT data FROM conversations WHERE owner=? AND channel=? AND id=?', (owner,channel,request_id)).fetchone()
            return json.loads(row['data']) if row else None

    def save_conversation(self, owner, channel, turn):
        with self.connect() as db:
            self.unpack(db.execute('SELECT * FROM channels WHERE owner=? AND id=?', (owner,channel)).fetchone())
            db.execute('INSERT INTO conversations VALUES(?,?,?,?) ON CONFLICT(owner,channel,id) DO NOTHING',
                       (owner,channel,turn['id'],json.dumps(turn)))
        return self.conversation_turn(owner,channel,turn['id'])

    def save_cover(self, owner, id, source_url, image_url):
        with self.connect() as db:
            article = self.unpack(db.execute('SELECT * FROM articles WHERE owner=? AND id=?', (owner,id)).fetchone())
            if source_url not in [public_url(s['url']) for s in article.get('sources', [])]:
                raise ValueError('图片来源不属于此文章')
            if not image_url:
                raise ValueError('此网页未找到可用标题图')
            article['cover_image'] = {'url': image_url, 'source_url': source_url}
            db.execute('UPDATE articles SET data=? WHERE owner=? AND id=?', (json.dumps(article),owner,id))
        return article

    def save_topics(self, owner, channel, expected_signature, topics):
        from .topics import recent, signature
        with self.connect() as db:
            current = self.unpack(db.execute('SELECT * FROM channels WHERE owner=? AND id=?',(owner,channel)).fetchone())
            articles = recent([self.unpack(row) for row in db.execute('SELECT * FROM articles WHERE owner=? AND channel=?',(owner,channel))])
            if signature(articles) != expected_signature:
                raise ValueError('频道文章已变化，请重新整理热点')
            current['hot_topics'] = {'items':topics,'signature':expected_signature,'generated_at':stamp(),
                                     'article_count':len(articles),'window_days':7}
            db.execute('UPDATE channels SET data=? WHERE owner=? AND id=?',(json.dumps(current),owner,channel))
        return current['hot_topics']

    def save_feedback_options(self, owner, id, digest, reasons):
        from .feedback import signature
        with self.connect() as db:
            article = self.unpack(db.execute('SELECT * FROM articles WHERE owner=? AND id=?', (owner,id)).fetchone())
            channel = self.unpack(db.execute('SELECT * FROM channels WHERE owner=? AND id=?', (owner,article['channel_id'])).fetchone())
            if signature(channel,article) != digest:
                raise ValueError('频道或文章已变化，请重新生成理由')
            article['feedback_options'] = {'signature':digest,'reasons':reasons}
            db.execute('UPDATE articles SET data=? WHERE owner=? AND id=?', (json.dumps(article),owner,id))
        return article['feedback_options']

    def preferences(self, owner, channel):
        self.get('channels',owner,channel)
        with self.connect() as db:
            rows = db.execute('SELECT data FROM preferences WHERE owner=? AND channel=?', (owner,channel)).fetchall()
        return sorted([json.loads(r['data']) for r in rows], key=lambda r:r['updated_at'], reverse=True)

    def save_images(self, owner, id, source_url, images, image_url=''):
        with self.connect() as db:
            article = self.unpack(db.execute('SELECT * FROM articles WHERE owner=? AND id=?', (owner,id)).fetchone())
            if source_url not in [public_url(s['url']) for s in article.get('sources', [])]:
                raise ValueError('图片来源不属于此文章')
            incoming = ([{'url':image_url,'alt':article['title'][:300]}] if image_url else []) + images
            incoming = [i for i in incoming if i.get('url')]
            if not incoming:
                raise ValueError('此网页未找到可用图片，保留已有图片')
            seen = set()
            result = []
            for item in [{**i,'source_url':source_url} for i in incoming] + article.get('images',[]):
                if item['url'] not in seen:
                    seen.add(item['url']);result.append(item)
            article['images'] = result[:48]
            if image_url and not article.get('cover_image'):
                article['cover_image'] = {'url':image_url,'source_url':source_url}
            db.execute('UPDATE articles SET data=? WHERE owner=? AND id=?', (json.dumps(article),owner,id))
        return article

    def drafts(self, owner, channel):
        self.get('channels',owner,channel)
        with self.connect() as db:
            rows=db.execute('SELECT data FROM drafts WHERE owner=? AND channel=?',(owner,channel)).fetchall()
        items=[json.loads(r['data']) for r in rows]
        return sorted([{k:d[k] for k in ('id','channel_id','title','kind','scope','scope_label','updated_at','revision')} for d in items], key=lambda d:d['updated_at'],reverse=True)

    def draft(self, owner, id):
        with self.connect() as db:
            row=db.execute('SELECT data FROM drafts WHERE owner=? AND id=?',(owner,id)).fetchone()
            if not row:raise KeyError('稿件不存在或不属于当前用户')
            return json.loads(row['data'])

    def save_draft(self, owner, draft, expected_revision=0):
        with self.connect() as db:
            self.unpack(db.execute('SELECT * FROM channels WHERE owner=? AND id=?',(owner,draft['channel_id'])).fetchone())
            row=db.execute('SELECT data FROM drafts WHERE owner=? AND id=?',(owner,draft['id'])).fetchone()
            if (json.loads(row['data'])['revision'] if row else 0)!=expected_revision:
                raise ValueError('稿件已在其他窗口更新，请重新打开后修改')
            db.execute('INSERT INTO drafts VALUES(?,?,?,?) ON CONFLICT(owner,id) DO UPDATE SET data=excluded.data',
                (owner,draft['channel_id'],draft['id'],json.dumps(draft,ensure_ascii=False)))
        return draft

    def claim_social(self, owner, id):
        from .social import site_key
        now=datetime.now(timezone.utc).timestamp()
        with self.connect() as db:
            source=self.unpack(db.execute('SELECT * FROM sources WHERE owner=? AND id=?',(owner,id)).fetchone())
            site=site_key(source)
            if not site:raise ValueError('此信息源不是社交来源')
            if not source.get('enabled'):raise ValueError('信息源已暂停')
            row=db.execute('SELECT data FROM social_limits WHERE owner=? AND site=?',(owner,site)).fetchone()
            limit=json.loads(row['data']) if row else {}
            next_at=max(source.get('social_next_at',0),limit.get('next_at',0),limit.get('lease_until',0))
            if source.get('social_paused'):
                return {'allowed':False,'reason':'需要在原 Profile 处理验证后，点击恢复采集','next_at':next_at}
            if next_at>now:
                return {'allowed':False,'reason':'信息源或平台正在冷却，暂不访问','next_at':next_at}
            token=key();limit.update(previous_next_at=limit.get('next_at',0),previous_source_next_at=source.get('social_next_at',0),token=token,source_id=id,lease_until=now+900,next_at=now+30)
            db.execute('INSERT INTO social_limits VALUES(?,?,?) ON CONFLICT(owner,site) DO UPDATE SET data=excluded.data',(owner,site,json.dumps(limit)))
            source['social_next_at']=now+source.get('social_interval_hours',6)*3600
            db.execute('UPDATE sources SET data=? WHERE owner=? AND id=?',(json.dumps(source),owner,id))
        return {'allowed':True,'token':token,'next_at':source['social_next_at']}

    def finish_social(self, owner, id, token, outcome):
        from .social import site_key
        now=datetime.now(timezone.utc).timestamp()
        with self.connect() as db:
            source=self.unpack(db.execute('SELECT * FROM sources WHERE owner=? AND id=?',(owner,id)).fetchone())
            site=site_key(source)
            row=db.execute('SELECT data FROM social_limits WHERE owner=? AND site=?',(owner,site)).fetchone()
            limit=json.loads(row['data']) if row else {}
            if limit.get('token')!=token or limit.get('source_id')!=id:raise ValueError('采集租约已过期')
            if outcome=='not_started':
                source['social_next_at']=limit.get('previous_source_next_at',source.get('social_next_at',0))
                limit.update(lease_until=0,next_at=limit.get('previous_next_at',0),token='')
                db.execute('UPDATE social_limits SET data=? WHERE owner=? AND site=?',(json.dumps(limit),owner,site))
                db.execute('UPDATE sources SET data=? WHERE owner=? AND id=?',(json.dumps(source),owner,id))
                return {'next_at':source['social_next_at'],'paused':source.get('social_paused',False)}
            failures=0 if outcome=='success' else source.get('social_failures',0)+1
            wait=30 if not failures else min(86400,3600*(2**min(failures-1,5)))
            limit.update(lease_until=0,next_at=now+wait,token='')
            source.update(social_failures=failures,social_paused=outcome=='needs_user')
            source['social_next_at']=max(source.get('social_next_at',0),now+wait)
            db.execute('UPDATE social_limits SET data=? WHERE owner=? AND site=?',(json.dumps(limit),owner,site))
            db.execute('UPDATE sources SET data=? WHERE owner=? AND id=?',(json.dumps(source),owner,id))
        return {'next_at':source['social_next_at'],'paused':source['social_paused']}

    def resume_social(self, owner, id):
        with self.connect() as db:
            source=self.unpack(db.execute('SELECT * FROM sources WHERE owner=? AND id=?',(owner,id)).fetchone())
            source['social_paused']=False
            db.execute('UPDATE sources SET data=? WHERE owner=? AND id=?',(json.dumps(source),owner,id))
        return source

    def filtered_posts(self, owner, channel):
        self.get('channels', owner, channel)
        with self.connect() as db:
            return [json.loads(r['data']) for r in db.execute(
                'SELECT data FROM filtered_posts WHERE owner=? AND channel=? ORDER BY rowid DESC', (owner,channel))]

    def save_filtered_post(self, owner, channel, page, reason, stage):
        self.get('channels', owner, channel)
        id = hashlib.sha256(page['url'].encode()).hexdigest()
        value = dict(id=id, page=page, reason=reason, stage=stage, status='filtered', updated_at=stamp())
        with self.connect() as db:
            old = db.execute('SELECT data FROM filtered_posts WHERE owner=? AND channel=? AND id=?', (owner,channel,id)).fetchone()
            if old and json.loads(old['data']).get('status') == 'restored':
                return
            db.execute('INSERT INTO filtered_posts VALUES(?,?,?,?) ON CONFLICT(owner,channel,id) DO UPDATE SET data=excluded.data',
                       (owner,channel,id,json.dumps(value)))

    def restore_filtered_post(self, owner, channel, id):
        self.get('channels', owner, channel)
        with self.connect() as db:
            row = db.execute('SELECT data FROM filtered_posts WHERE owner=? AND channel=? AND id=?', (owner,channel,id)).fetchone()
            if row is None:
                raise KeyError('过滤记录不存在')
            value = json.loads(row['data'])
            value['status'] = 'restored'
            value['updated_at'] = stamp()
            db.execute('UPDATE filtered_posts SET data=? WHERE owner=? AND channel=? AND id=?', (json.dumps(value),owner,channel,id))
        return value
