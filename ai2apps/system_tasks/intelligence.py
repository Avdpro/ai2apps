"""Adapter: one admitted system Task owns a channel collection tree."""
from __future__ import annotations
import asyncio
import json
from .service import TaskHandler
from .sessions import execution_principal


def register_intelligence(runtime):
    service=runtime.system_tasks
    collector=runtime.intelligence_collector

    def principal_for(owner):
        return execution_principal(runtime, owner)

    def authorize(owner,payload):
        from ai2apps.apps.access import has_app_capability
        if not has_app_capability(principal_for(owner),'app.use'):
            raise ValueError('Intelligence App access is no longer available')
        collector.store.get('channels',owner,payload['channel_id'])

    async def execute(ctx):
        from ai2apps.identity import IdentityRepository
        run_id=ctx.checkpoint.get('run_id') or ctx.payload.get('run_id')
        if not run_id:
            # Cross-database recovery: submission may have persisted the business
            # record just before Local stopped, before the system checkpoint.
            with collector.store.connect() as db:
                linked=db.execute("SELECT run_id FROM collection_jobs WHERE owner=? AND json_extract(data,'$.system_task_id')=?",(ctx.owner,ctx.id)).fetchone()
            if linked:run_id=linked['run_id']
        if not run_id:
            principal=principal_for(ctx.owner)
            session=collector.execution_session(ctx.owner)
            source_id=ctx.payload.get('source_id')
            if not source_id and ctx.payload.get('retry_run_id'):
                source_id=collector.store.get('runs',ctx.owner,ctx.payload['retry_run_id']).get('source_id')
            run=collector.submit(principal,ctx.payload['channel_id'],session,
                source_id=source_id,_system_managed=ctx.id)
            run_id=run['id']
            if ctx.task['trigger']=='schedule':
                with collector.store.connect() as db:
                    db.execute("UPDATE runs SET data=json_set(data,'$.scheduled',json('true')) WHERE owner=? AND id=?",(ctx.owner,run_id))
        ctx.report(checkpoint={'run_id':run_id},progress={'root_id':'collection:'+run_id})
        with collector.store.connect() as db:
            job=dict(db.execute('SELECT * FROM collection_jobs WHERE run_id=? AND owner=?',(run_id,ctx.owner)).fetchone())
        collector.active[run_id]=asyncio.current_task()
        worker=asyncio.create_task(collector.guarded_collect(job))
        try:
            while not worker.done():
                run=collector.store.get('runs',ctx.owner,run_id)
                from ai2apps.browser.progress_watchdog import browser_activity
                activity=await asyncio.to_thread(browser_activity,runtime,owner=ctx.owner,root_id='collection:'+run_id)
                scheduler=getattr(runtime,'worker_scheduler',None)
                if scheduler is not None:
                    models=await scheduler.scoped_activity(actor_id=ctx.owner,
                        app_id='ai2apps.intelligence',session_id='intelligence-'+ctx.payload['channel_id'])
                    activity={key:activity[key]+models[key] for key in activity}
                state='waiting_user' if (run.get('progress') or {}).get('waiting') else 'waiting_resource' if activity['blocked'] and not activity['running'] else 'running'
                ctx.report(state=state,message=run.get('message',''),
                    progress={**run.get('progress',{}),'root_id':'collection:'+run_id,'collection_run_id':run_id})
                await asyncio.wait({worker},timeout=2)
            await worker
            # Browser task-tree reconciliation owns page cleanup and completion.
            while collector.tree.get(ctx.owner,'collection:'+run_id)['status'] not in ('completed','failed','cancelled'):
                ctx.report(message='等待子任务和页面清理',progress={**collector.store.get('runs',ctx.owner,run_id).get('progress',{}),'root_id':'collection:'+run_id})
                await asyncio.sleep(1)
            collector.store.complete_pending(ctx.owner,run_id)
            run=collector.store.get('runs',ctx.owner,run_id)
            ctx.report(message=run.get('message',''),progress={**run.get('progress',{}),
                'root_id':'collection:'+run_id,'collection_run_id':run_id})
            return {'_status': 'partial' if run['status']=='partial' else 'failed' if run['status']=='failed' else 'completed',
                'collection_run_id':run_id,'article_count':run.get('article_count',0)}
        finally:
            if not worker.done():worker.cancel()
            await asyncio.gather(worker,return_exceptions=True)
            collector.active.pop(run_id,None)

    async def cancel(ctx,force):
        run_id=ctx.checkpoint.get('run_id') or ctx.payload.get('run_id')
        if not run_id:
            with collector.store.connect() as db:
                linked=db.execute("SELECT run_id FROM collection_jobs WHERE owner=? AND json_extract(data,'$.system_task_id')=?",(ctx.owner,ctx.id)).fetchone()
            if linked:run_id=linked['run_id']
        if not run_id:return True
        collector.cancel(ctx.owner,run_id)
        collector.tree.reconcile()
        return collector.tree.get(ctx.owner,'collection:'+run_id)['status'] in ('completed','failed','cancelled')

    from ai2apps.intelligence.progress import refresh_progress
    service.register('intelligence.refresh',TaskHandler('ai2apps.intelligence',execute,cancel,authorize,
        resumable=True,progress_view=refresh_progress,retry_payload=lambda payload:{'channel_id':payload['channel_id'],
            'source_id':payload.get('source_id'),'retry_run_id':payload.get('run_id') or payload.get('retry_run_id')}))

    from ai2apps.intelligence import projections
    projections.register(runtime,principal_for,authorize)

    from ai2apps.intelligence import article_chat
    article_chat.register(runtime,principal_for,authorize)
