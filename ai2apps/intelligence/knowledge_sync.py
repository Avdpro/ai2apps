"""Durable channel-to-Knowledge synchronization through the system KnowledgeStore."""
import hashlib
from datetime import datetime
from ai2apps.knowledge.models import KnowledgeScope
from ai2apps.knowledge.store import SHARED_CONTRIBUTOR_ROLES

APP_ID = 'ai2apps.intelligence'


def document(channel, article):
    section = next((s['name'] for s in channel.get('sections', []) if s['id'] == article.get('section_id')), '未分类')
    references = '\n'.join(f"[{i+1}] {s.get('title') or s.get('source_name', '')}\n{s['url']}" for i,s in enumerate(article.get('sources', [])))
    text = f"频道：{channel['name']}\n栏目：{section}\n情报更新时间：{article['updated_at']}\n\n{article['summary']}\n\n{article['body']}\n\n原始来源\n{references}\n\n本文由 AI 整理，关键事实请核对原始来源。"
    digest = hashlib.sha256((article['title']+'\n'+text).encode()).hexdigest()
    return text, digest


def available_buckets(knowledge, principal):
    return [b for b in knowledge.list_buckets(principal) if b.visibility == KnowledgeScope.PRIVATE or principal.role in SHARED_CONTRIBUTOR_ROLES]


def validate_buckets(knowledge, principal, ids):
    if not ids:
        return
    if knowledge is None:
        raise ValueError('系统知识库暂不可用')
    allowed = {b.id for b in available_buckets(knowledge, principal)}
    if set(ids) - allowed:
        raise ValueError('所选知识库不存在或当前用户没有写入权限')


def sync_pending(store, knowledge, principal, channel_id=None, retry=False):
    owner = principal.actor_user_id
    results = {'synced': 0, 'failed': 0}
    for job in store.knowledge_jobs(owner, channel_id, retry=retry):
        try:
            if knowledge is None:
                raise ValueError('系统知识库暂不可用')
            channel = store.get('channels', owner, job['channel'])
            if job['bucket'] not in channel.get('knowledge_bucket_ids', []):
                continue
            article = store.get('articles', owner, job['article'])
            buckets = {b.id: b for b in available_buckets(knowledge, principal)}
            bucket = buckets.get(job['bucket'])
            if bucket is None:
                raise ValueError('关联知识库已删除或失去写入权限，请修改频道设置')
            text, digest = document(channel, article)
            item = knowledge.create_text_item(principal, scope=bucket.visibility, kind='artifact', title=article['title'], text=text,
                source_app_id=APP_ID, source_time=datetime.fromisoformat(article['created_at']),
                source_url=next((s['url'] for s in article.get('sources', []) if s.get('url')), None),
                bucket_id=bucket.id, trusted_source_facets=(('intelligence.channel', channel['id']), ('intelligence.article', article['id'])),
                idempotency_key=article['id']+':'+bucket.id)
            if item.title != article['title'] or item.text != text:
                item = knowledge.update_text_item(principal, item.id, expected_revision=item.revision, title=article['title'], text=text,
                    generated_source_app_id=APP_ID)
            knowledge.add_item_to_bucket(principal, bucket.id, item.id)
            store.complete_knowledge_job(owner, job, item.id, '', digest)
            results['synced'] += 1
        except Exception as error:
            store.complete_knowledge_job(owner, job, None, str(error)[:300], job['hash'])
            results['failed'] += 1
    return results
