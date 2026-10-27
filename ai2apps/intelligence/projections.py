"""Durable App-owned derived work; article collection never awaits model projections."""
from __future__ import annotations
import asyncio
import json
import logging
from . import entities, entity_categories, topics, knowledge_sync

log = logging.getLogger(__name__)
LABELS = {'entities':'实体与参数', 'categories':'实体分类', 'topics':'热点话题',
          'opportunities':'监控线索', 'knowledge':'知识库同步'}


def initialize(store):
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS projection_requests(owner TEXT NOT NULL, channel TEXT NOT NULL, revision TEXT NOT NULL, kind TEXT NOT NULL, dispatched INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(owner,channel,revision,kind))')


def articles(store, owner, channel):
    with store.connect() as db:
        return [store.unpack(r) for r in db.execute('SELECT * FROM articles WHERE owner=? AND channel=? ORDER BY id',(owner,channel))]


def request(collector, owner, channel, kinds=None):
    """Outbox survives a crash between article commit and System Task submission."""
    store=collector.store
    initialize(store)
    config=store.get('channels',owner,channel)
    manual=kinds is not None
    if kinds is None:
        kinds=('knowledge', 'topics') if topics.automatic_due(store,owner,config) else ('knowledge',)
    saved=articles(store,owner,channel)
    revision=entities.signature([[a['id'],entities.extraction_signature(a)] for a in saved])
    derived_revision=None
    if any(k in ('categories','opportunities') for k in kinds):
        snapshot=entities.Repository(store).snapshot(owner)
        derived_revision=entities.signature([{k:e.get(k) for k in ('id','name','kind','aliases','facts','watched','rule')}
            for e in snapshot['entities'] if channel in e['channel_ids'] or e.get('manual')])
    with store.connect() as db:
        for kind in kinds:
            digest=derived_revision if kind in ('categories','opportunities') else revision
            if manual:digest='manual:'+digest
            elif kind=='topics':
                import time
                digest='auto-day:'+str(int(time.time()//topics.AUTOMATIC_INTERVAL))+':'+digest
            db.execute('INSERT OR IGNORE INTO projection_requests(owner,channel,revision,kind) VALUES(?,?,?,?)',(owner,channel,digest,kind))
    flush(collector)


def after_collection(collector, owner, channel):
    # The article commit is authoritative. Projection dispatch cannot turn saved
    # evidence back into an unprocessed collection or trigger a recollection.
    try:request(collector,owner,channel)
    except Exception:log.exception('Articles saved; derived work dispatch deferred')


def flush(collector):
    service=getattr(collector.runtime,'system_tasks',None)
    if service is None:return
    initialize(collector.store)
    with collector.store.connect() as db:
        pending=[dict(r) for r in db.execute('SELECT * FROM projection_requests WHERE dispatched=0 LIMIT 30')]
    for row in pending:
        kind=row['kind']
        if 'intelligence.derive.'+kind not in service.handlers:continue
        try:
            channel=collector.store.get('channels',row['owner'],row['channel'])
            if kind in ('entities','categories','opportunities'):
                # New explicit requests carry a revision marker; legacy automatic
                # outbox entries must not resume model extraction after upgrade.
                if not row['revision'].startswith('manual:'):
                    with collector.store.connect() as db:
                        db.execute('UPDATE projection_requests SET dispatched=1 WHERE owner=? AND channel=? AND revision=? AND kind=?',
                            (row['owner'],row['channel'],row['revision'],kind))
                    continue
            service.submit(row['owner'],'ai2apps.intelligence','intelligence.derive.'+kind,
                LABELS[kind]+' · '+channel['name'],{'channel_id':row['channel'], 'manual':row['revision'].startswith('manual:')},
                dedup_key='derive:'+kind+':'+row['channel']+':'+row['revision'],priority=-10)
            with collector.store.connect() as db:
                db.execute('UPDATE projection_requests SET dispatched=1 WHERE owner=? AND channel=? AND revision=? AND kind=?',
                    (row['owner'],row['channel'],row['revision'],kind))
        except Exception:
            log.exception('Derived Task dispatch deferred; durable request retained')


def register(runtime, principal_for, authorize):
    from ai2apps.system_tasks.service import TaskHandler
    collector=runtime.intelligence_collector
    initialize(collector.store)
    locks={}

    async def execute(ctx,kind):
        channel_id=ctx.payload['channel_id'];store=collector.store
        # Entity extraction, taxonomy and watched facts share one channel-owned
        # revision domain. Topics and knowledge may run independently.
        group='entities' if kind in ('entities','categories','opportunities') else kind
        lock=locks.setdefault((ctx.owner,channel_id,group),asyncio.Lock())
        if lock.locked():ctx.report(state='waiting_resource',message='等待同频道派生任务')
        async with lock:
            authorize(ctx.owner,ctx.payload)
            principal=principal_for(ctx.owner)
            channel=store.get('channels',ctx.owner,channel_id)
            ctx.report(message=LABELS[kind]+'：检查变化')
            saved=articles(store,ctx.owner,channel_id)
            if kind in ('entities','categories','opportunities') and not ctx.payload.get('manual'):
                return {'skipped':True,'reason':'manual_only'}
            if kind=='entities':
                repo=entities.Repository(store);pending=repo.pending(ctx.owner,saved)
                failures=[];completed=0
                for article in pending:
                    ctx.report(message='提取实体与参数',progress={'completed':completed,'total':len(pending),'article_id':article['id']})
                    try:
                        plan=await entities.extract_or_review(runtime,None,principal,article,repo)
                        repo.ingest(ctx.owner,article,plan)
                        completed+=1
                        ctx.report(checkpoint={'completed':completed},progress={'completed':completed,'total':len(pending)})
                    except Exception as error:
                        failures.append({'article_id':article['id'],'error':str(error)[:300]})
                # Persistent per-article extraction signatures are the checkpoints;
                # retries re-read current articles and skip successful ingestions.
                request(collector,ctx.owner,channel_id,('categories','opportunities'))
                if failures:return {'_status':'partial' if completed else 'failed','completed':completed,'failures':failures}
                return {'completed':completed,'skipped':len(saved)-len(pending)}
            if kind=='categories':
                repo=entities.Repository(store)
                if not any(channel_id in e['channel_ids'] or e.get('manual') for e in repo.snapshot(ctx.owner)['entities']):return {'skipped':True}
                await entity_categories.organize(runtime,None,principal,store,channel_id)
            elif kind=='topics':
                return await topics.refresh(runtime,None,principal,store,channel_id,automatic=not ctx.payload.get('manual'))
            elif kind=='opportunities':
                repo=entities.Repository(store);snapshot=repo.snapshot(ctx.owner)
                for entity in snapshot['entities']:
                    if channel_id not in entity['channel_ids'] or not entity['watched'] or not entity['rule'].strip():continue
                    signature=entities.signature([entity['rule'],[(f['id'],f['historical']) for f in entity['facts']]])
                    if entity.get('evaluated_signature')==signature:continue
                    ctx.report(message='检查监控线索',progress={'entity_id':entity['id']})
                    lead=await entities.opportunity(runtime,None,principal,entity,[l for l in snapshot['opportunities'] if l['entity_id']==entity['id']])
                    repo.save_lead(ctx.owner,entity,signature,lead)
            elif kind=='knowledge':
                await asyncio.to_thread(knowledge_sync.sync_pending,store,runtime.knowledge,principal,channel_id)
            return {'completed':True}

    for kind in LABELS:
        async def handler(ctx,kind=kind):return await execute(ctx,kind)
        runtime.system_tasks.register('intelligence.derive.'+kind,
            TaskHandler('ai2apps.intelligence',handler,authorize=authorize,resumable=True))
