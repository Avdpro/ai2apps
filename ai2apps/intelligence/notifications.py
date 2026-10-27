"""Bridge committed channel refreshes into the host's durable push outbox.

The business DB and platform DB are separate: acknowledge only after enqueue,
and use a stable event id to close the crash window between the two commits.
Negotiated rich events contain a frozen name/count/headline snapshot, never article bodies or URLs.
"""
from __future__ import annotations

import json
import time
import unicodedata


def plain_text(value, maximum):
    value = "".join(c for c in str(value or "") if (unicodedata.category(c) not in ("Cc", "Cf", "Cs") or c in "\u200c\u200d") and c not in "<>")
    return " ".join(value.split())[:maximum].strip()


def enqueue_refresh_notifications(store, producer, *, now=None):
    if producer is None:
        return 0
    now = time.time() if now is None else now
    # Device-auth notifications currently target the Installation Owner. A
    # member's private channel must never be delivered to that Owner instead.
    try:
        owner = producer.identity()['owner_id']
    except ValueError:
        return 0
    with store.connect() as db:
        rows = [dict(row) for row in db.execute("""
            SELECT r.*, json_extract(j.data,'$.system_task_id') AS system_task_id
            FROM runs r JOIN channels c ON c.id=r.channel AND c.owner=r.owner
            JOIN collection_jobs j ON j.run_id=r.id AND j.owner=r.owner
            WHERE r.owner=? AND r.status IN ('completed','partial','failed')
              AND COALESCE(json_extract(j.data,'$.system_task_id'),'')<>''
              AND json_array_length(r.data,'$.new_article_ids')>0
              AND json_extract(r.data,'$.notification_enqueued') IS NULL
              AND COALESCE(json_extract(r.data,'$.notification_next_attempt'),0)<=?
              AND julianday(json_extract(r.data,'$.finished_at'))>=julianday(?,'unixepoch')
            ORDER BY r.updated LIMIT 20
        """, (owner, now, now - 86400))]
    enqueued = 0
    for row in rows:
        run = json.loads(row['data'])
        # New background refreshes have a real system Task target. Legacy
        # frontend-only runs are not assigned a fictitious Task deep link.
        task_id = row['system_task_id']
        event_id = 'intelligence.new_articles:' + row['id']
        try:
            if getattr(producer, 'has_event', lambda *_: False)(event_id, owner):
                pass  # A pre-upgrade or crash-window outbox event stays frozen.
            else:
                with store.connect() as db:
                    fresh = json.loads(db.execute('SELECT data FROM runs WHERE owner=? AND id=?', (owner, row['id'])).fetchone()['data'])
                    snapshot = fresh.get('notification_snapshot')
                    if snapshot is None:
                        event = dict(event_id=event_id,
                                     kind='task.failed' if row['status'] == 'failed' else 'task.completed',
                                     target_id=task_id, app_id='ai2apps.intelligence',
                                     result_count=len(set(run['new_article_ids'])))
                        if getattr(producer, 'supports_intelligence', lambda: False)():
                            channel = db.execute('SELECT data FROM channels WHERE owner=? AND id=?', (owner, row['channel'])).fetchone()
                            ids = set(run['new_article_ids'])
                            articles = [{**json.loads(a['data']), 'id': a['id']} for a in db.execute('SELECT id,data FROM articles WHERE owner=? AND channel=? AND id IN (SELECT value FROM json_each(?))', (owner, row['channel'], json.dumps(list(ids))))]
                            articles = sorted((a for a in articles if a['id'] in ids), key=lambda a: a.get('updated_at', ''), reverse=True)
                            name = plain_text(json.loads(channel['data']).get('name'), 80) if channel else ''
                            if not articles or not name:
                                raise ValueError('Notification channel or saved articles unavailable')
                            event = dict(event_id=event_id, kind='intelligence.updated',
                                         target_id=row['channel'], app_id='ai2apps.intelligence',
                                         template_params={'channel_name': name, 'new_article_count': len(articles),
                                                          'headlines': [title for a in articles if (title := plain_text(a.get('title'), 100))][:2],
                                                          'refresh_status': row['status']},
                                         metadata={'run_id': row['id'], 'system_task_id': task_id})
                        snapshot = event
                        db.execute("UPDATE runs SET data=json_set(data,'$.notification_snapshot',json(?)) WHERE owner=? AND id=?",
                                   (json.dumps(snapshot), owner, row['id']))
                producer.enqueue(**snapshot, expected_owner_id=owner)
        except Exception:
            # Enqueue is local only; binding/queue/storage failure must neither
            # roll back articles nor flood the coordinator every five seconds.
            with store.connect() as db:
                db.execute("""UPDATE runs SET data=json_set(data,'$.notification_next_attempt',?)
                              WHERE owner=? AND id=?""", (now + 60, owner, row['id']))
            continue
        with store.connect() as db:
            db.execute("""UPDATE runs SET data=json_set(data,'$.notification_enqueued',?)
                          WHERE owner=? AND id=?""", (event_id, owner, row['id']))
        enqueued += 1
    return enqueued
