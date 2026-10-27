"""Durable Local collection coordinator. All browsing uses shared WebAgent Tasks."""
from __future__ import annotations
import asyncio
import json
import logging
import re
import time
from contextlib import suppress
from urllib.parse import urlsplit

from ai2apps.browser.invocation import WebAgentInvocation
from ai2apps.browser.tasks import BrowserTaskRepository
from .store import IntelligenceStore
from .models import Candidate, Page
from . import service, site_agents, entity_categories, post_filter, knowledge_sync, topics, entities, social
from . import notifications as channel_notifications

logger = logging.getLogger(__name__)


class SourceBlocked(Exception):
    """Stop this source without retrying an uncertain browser action."""


class IntelligenceCollector:
    watchdog_poll_seconds = 5

    def __init__(self, runtime):
        self.runtime = runtime
        self.store = IntelligenceStore(runtime.config.paths.artifacts_path / 'intelligence')
        self.invocations = WebAgentInvocation(runtime)
        self.tasks = self.invocations.tasks
        from ai2apps.browser.task_tree import TaskTreeRepository
        self.tree = TaskTreeRepository(runtime.database, runtime.events)
        self.active = {}
        self.browser_activity = {}
        self.stop = asyncio.Event()
        self.loop_task = None
        with self.store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS collection_jobs(run_id TEXT PRIMARY KEY, owner TEXT NOT NULL, session_id TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS collection_schedules(owner TEXT PRIMARY KEY, session_id TEXT NOT NULL);
            ''')

    def execution_session(self, owner):
        from ai2apps.system_tasks.sessions import execution_session
        return execution_session(self.runtime, owner, 'ai2apps.intelligence')

    def submit(self, principal, channel_id, session_id=None, scheduled=False, source_id=None, *, _system_managed=False, request_key=None):
        owner = principal.actor_user_id
        self.store.get('channels', owner, channel_id)
        if request_key:
            with self.store.connect() as db:
                existing=db.execute("SELECT * FROM runs WHERE owner=? AND json_extract(data,'$.request_key')=?", (owner,request_key)).fetchone()
            if existing:
                old=self.store.unpack(existing)
                if old['channel_id']!=channel_id or old.get('source_id')!=source_id:
                    raise ValueError('Refresh request parameters changed')
                if old['status']!='running':return old
        system=getattr(self.runtime,'system_tasks',None)
        if system is not None and not _system_managed:
            existing=system.active_for(owner,'ai2apps.intelligence','schedule:intelligence:'+channel_id)
            if existing:
                run_id=existing['checkpoint'].get('run_id') or existing['payload'].get('run_id')
                if run_id:
                    active_run=self.store.get('runs',owner,run_id)
                    if request_key and active_run.get('request_key')!=request_key:
                        raise ValueError('此频道已有其他刷新任务，请等待完成后重试')
                    return active_run
                raise ValueError('此频道已排队更新')
        session_id = self.execution_session(owner)
        run = self.store.claim(owner, channel_id, scheduled, background_session=session_id, source_id=source_id, request_key=request_key)
        channel = self.store.get('channels', owner, channel_id)
        self.tree.create(owner, 'collection:'+run['id'], '刷新情报 · '+channel['name'], kind='collection')
        with self.store.connect() as db:
            job = dict(db.execute('SELECT * FROM collection_jobs WHERE run_id=?', (run['id'],)).fetchone())
        self.ensure_source_nodes(job)
        # Manual and scheduled refreshes share the same evidence recovery path.
        self.recover_editorial(owner,channel,job)
        if system is not None:
            if isinstance(_system_managed,str):
                with self.store.connect() as db:db.execute("UPDATE collection_jobs SET data=json_set(data,'$.system_task_id',?) WHERE run_id=?",(_system_managed,run['id']))
            if not _system_managed:self.register_system_job(owner,run['id'],channel)
            self.sync_system_schedules(owner)
        with self.store.connect() as db:
            current=json.loads(db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(run['id'],)).fetchone()['data'])
            current['ready']=True
            db.execute('UPDATE collection_jobs SET data=? WHERE run_id=?',(json.dumps(current),run['id']))
        self.changed(owner, run['id'])
        self.runtime.notifications.notify()
        return self.store.get('runs', owner, run['id'])

    def register_system_job(self,owner,run_id,channel):
        run=self.store.get('runs',owner,run_id)
        task=self.runtime.system_tasks.submit(owner,'ai2apps.intelligence','intelligence.refresh',
            '刷新情报 · '+channel['name'],{'channel_id':channel['id'],'run_id':run_id,'source_id':run.get('source_id')},
            dedup_key='schedule:intelligence:'+channel['id'])
        with self.store.connect() as db:
            db.execute("UPDATE collection_jobs SET data=json_set(data,'$.system_task_id',?) WHERE run_id=? AND owner=?",(task['id'],run_id,owner))
        return task

    def sync_system_schedules(self,owner):
        system=self.runtime.system_tasks
        channels=self.store.snapshot(owner)['channels']
        active=[]
        for channel in channels:
            interval=channel.get('interval_hours',0)*3600
            if not interval:continue
            key='intelligence:'+channel['id'];active.append(key)
            due=max(channel.get('schedule_anchor',time.time()),channel.get('last_attempt',0))+interval
            system.schedule(owner,'ai2apps.intelligence',key,'intelligence.refresh',
                '刷新情报 · '+channel['name'],{'channel_id':channel['id']},next_run=due,interval_seconds=interval)
        system.disable_missing_schedules(owner,'ai2apps.intelligence',active)

    @staticmethod
    def editorial_context(channel):
        return {k:channel.get(k) for k in ('name','interests','excluded','sections','output_language','post_filter_level','post_filter_guidance')}

    def recover_editorial(self,owner,channel,job):
        with self.store.connect() as db:
            old=db.execute("SELECT id,status,data,updated FROM runs WHERE owner=? AND channel=? AND status IN ('failed','partial','completed') AND id!=? AND updated>? ORDER BY updated DESC LIMIT 1",
                (owner,channel['id'],job['run_id'],time.time()-86400)).fetchone()
            prior=db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(old['id'],)).fetchone() if old else None
        if not old or old['status']=='completed' or not prior:return
        previous=json.loads(prior['data']);current=json.loads(job['data'])
        evidence_at=previous.get('retry_evidence_at',old['updated'])
        if evidence_at<=time.time()-86400:return
        phase=(json.loads(old['data']).get('progress') or {}).get('phase')
        if previous.get('editorial_complete') or phase not in ('digest','planning','writing','saving'):return
        # Older releases lacked editorial_complete. A final partial result can
        # be caused only by source failures after every planned article saved.
        state=previous.get('editorial',{}).get('state',{})
        plan=state.get('plan')
        if old['status']=='partial' and json.loads(old['data']).get('article_count') is not None and plan is not None and all(str(i) in state.get('articles',{}) for i in range(len(plan.get('events',[])))):return
        fields=('id','url','kind','profile_key','x_mode','x_values','x_sort','xiaohongshu_sort','list_agent_generation_id','article_agent_generation_id','interaction_mode')
        configured={source['id']:source for source in previous['sources']}
        if any(source['id'] not in configured or any(source.get(k)!=configured[source['id']].get(k) for k in fields) for source in current['sources']):return
        cached=[];logs=[]
        saved_pages=previous.get('retry_pages',[])
        for source in current['sources']:
            result=None
            if saved_pages:
                result={'pages':[p for p in saved_pages if p['source_id']==source['id']],
                        'log':next((log for log in previous.get('retry_logs',[]) if log.get('source_id')==source['id']),None)}
            else:
                with self.runtime.database.transaction() as native:
                    node=native.execute('SELECT result_json FROM task_nodes WHERE owner=? AND id=?',(owner,'collection:'+old['id']+':source:'+source['id'])).fetchone()
                if node and node['result_json']:
                    try:result=json.loads(node['result_json'])
                    except (TypeError,ValueError):return
            if not result or not result.get('log'):return
            cached.extend(result.get('pages',[]));logs.append(result['log'])
        if not cached:return
        current.update(retry_pages=cached,retry_logs=logs,retry_from_run_id=old['id'],retry_evidence_at=evidence_at)
        # Preserve evidence numbering and completed articles only when their
        # complete evidence scope and editorial settings are unchanged.
        if previous.get('editorial') and previous.get('editorial_context')==self.editorial_context(channel) and {s['id'] for s in current['sources']}==set(configured):
            current['editorial_origin_run_id']=previous.get('editorial_origin_run_id',old['id'])
            current['editorial']=previous['editorial']
            current['editorial_context']=previous['editorial_context']
        with self.store.connect() as db:db.execute('UPDATE collection_jobs SET data=? WHERE run_id=?',(json.dumps(current),job['run_id']))

    def regroup_posts(self, principal, channel_id, session_id):
        owner=principal.actor_user_id
        self.store.get('channels', owner, channel_id)
        session_id = self.execution_session(owner)
        with self.store.connect() as db:
            pages=[json.loads(r['data']) for r in db.execute("SELECT data FROM pages WHERE owner=? AND channel=? AND json_extract(data,'$.platform')='x' ORDER BY rowid DESC LIMIT 40",(owner,channel_id))]
        if not pages:raise ValueError('No saved X posts to reorganize')
        run=self.store.claim(owner,channel_id,False,background_session=session_id)
        self.tree.create(owner,'collection:'+run['id'],'重新整理 X 原帖',kind='collection')
        with self.store.connect() as db:
            row=db.execute('SELECT * FROM collection_jobs WHERE run_id=?',(run['id'],)).fetchone();job=dict(row);data=json.loads(row['data'])
            logs=[dict(source_id=s['id'],name=s['name'],status='success',pages=sum(p.get('source_id')==s['id'] for p in pages),skipped=0,message='重新整理已保存帖子，不重复访问 X') for s in data['sources']]
            data.update(retry_pages=pages,retry_logs=logs,rebuild_posts=True,editorial={'pages':pages,'state':{}},ready=False)
            db.execute('UPDATE collection_jobs SET data=? WHERE run_id=?',(json.dumps(data),run['id']))
        job['data']=json.dumps(data);self.ensure_source_nodes(job)
        with self.store.connect() as db:db.execute("UPDATE collection_jobs SET data=json_set(data,'$.ready',json('true')) WHERE run_id=?",(run['id'],))
        self.changed(owner,run['id']);self.runtime.notifications.notify()
        return run

    def ensure_source_nodes(self, job):
        root = 'collection:'+job['run_id']
        for source in json.loads(job['data'])['sources']:
            self.tree.create(job['owner'], root+':source:'+source['id'], '刷新 '+source['name'], parent_id=root, kind='source')

    def cancel(self, owner, run_id):
        system=getattr(self.runtime,'system_tasks',None)
        if system is not None:
            with self.store.connect() as db:
                row=db.execute('SELECT data FROM collection_jobs WHERE owner=? AND run_id=?',(owner,run_id)).fetchone()
            task_id=json.loads(row['data']).get('system_task_id') if row else None
            if task_id:
                task=system.get(owner,task_id)
                if task['status'] not in ('cancelling','cancelled','completed','partial','failed','interrupted'):
                    system.cancel(owner,task_id)
        with suppress(KeyError):
            if self.store.get('runs',owner,run_id)['status']=='running':self.store.progress(owner,run_id,'已停止','cancelled')
        with suppress(KeyError):
            for run in self.tree.cancel(owner, 'collection:'+run_id):
                self.runtime.agent_runtime.cancel(run)
        active = self.active.get(run_id)
        if active is not None:
            active.cancel()
        self.runtime.notifications.notify()

    def changed(self, owner, run_id):
        self.runtime.events.append(event_type='intelligence.collection.changed',
            subject_id=BrowserTaskRepository.event_subject(owner), payload={'collection_run_id': run_id})

    def progress(self, owner, run_id, message, logs=None, details=None):
        current = self.store.get('runs', owner, run_id)
        if current['status'] != 'running':
            return
        if details is not None:
            details=dict(details)
            if run_id in self.browser_activity:details['active_pages']=list(self.browser_activity[run_id].values())
            old=current.get('progress',{})
            if any(isinstance(details.get(k),(int,float)) and details[k]>old.get(k,0) for k in ('pages_read','articles_extracted','articles_saved','sources_completed')):
                from datetime import datetime, timezone
                details['last_effective_progress_at']=datetime.now(timezone.utc).isoformat()
            identity=('phase','source_id','event_index','model_attempt','browser_task_id','waiting')
            if any(k in details and old.get(k)!=details[k] for k in identity):
                from datetime import datetime, timezone
                details['phase_started_at']=datetime.now(timezone.utc).isoformat()
        details_changed=details is not None and any(current.get('progress',{}).get(k)!=v for k,v in details.items())
        if current.get('message')==message and logs is None and not details_changed:return
        self.store.progress(owner, run_id, message, logs=logs, details=details)
        if current.get('message') != message or logs is not None or details_changed:
            self.changed(owner, run_id)

    async def startup(self):
        from ai2apps.browser import progress_watchdog
        logger.info('Intelligence queue-aware watchdog loaded from %s; collector=%s',
                    progress_watchdog.__file__, __file__)
        logger.info('Intelligence new-article push bridge loaded from %s', channel_notifications.__file__)
        from ai2apps.system_tasks import sessions as task_sessions
        logger.info('Intelligence Local execution Session resolver loaded from %s', task_sessions.__file__)
        self.stop.clear()
        # A Local restart may interrupt submission before its admission flag.
        with self.store.connect() as db:
            db.execute("UPDATE collection_jobs SET data=json_set(data,'$.ready',json('true')) WHERE json_extract(data,'$.ready')=0")
        # Upgrade existing schedules without requiring an open Intelligence UI.
        from ai2apps.identity import IdentityRepository
        with self.store.connect() as db:
            owners = [r['owner'] for r in db.execute("SELECT DISTINCT owner FROM channels WHERE json_extract(data,'$.interval_hours') > 0")]
        for owner in owners:
            try:
                session = self.execution_session(owner)
                with self.store.connect() as db:db.execute('INSERT OR IGNORE INTO collection_schedules VALUES(?,?)',(owner,session))
            except Exception:logger.exception('Existing intelligence schedule requires active identity')
        if self.loop_task is None:
            self.loop_task = asyncio.create_task(self.loop(), name='intelligence-local-collector')

    async def shutdown(self):
        self.stop.set();self.runtime.notifications.notify()
        if self.loop_task:
            await self.loop_task
        self.loop_task = None
        for task in self.active.values():task.cancel()
        await asyncio.gather(*self.active.values(), return_exceptions=True)
        self.active.clear()

    async def loop(self):
        async with self.runtime.notifications.subscribe() as wake:
            last_schedule = 0
            while not self.stop.is_set():
                try:
                    from . import projections
                    projections.flush(self)
                    with self.store.connect() as db:
                        jobs = [dict(r) for r in db.execute("SELECT j.*, r.status AS run_status FROM collection_jobs j JOIN runs r ON r.id=j.run_id WHERE r.status IN ('running','completed') AND COALESCE(json_extract(j.data,'$.ready'),1)=1")]
                        schedules = [dict(r) for r in db.execute('SELECT * FROM collection_schedules')]
                    for job in jobs:
                        if job['run_status'] == 'completed':
                            try:
                                node = self.tree.get(job['owner'], 'collection:'+job['run_id']+':organize')
                            except KeyError:
                                continue
                            if node['status'] != 'running':
                                continue
                        system=getattr(self.runtime,'system_tasks',None)
                        if system is not None:
                            data=json.loads(job['data'])
                            if not data.get('system_task_id'):
                                channel=self.store.get('channels',job['owner'],self.store.get('runs',job['owner'],job['run_id'])['channel_id'])
                                self.register_system_job(job['owner'],job['run_id'],channel)
                            continue
                        if job['run_id'] not in self.active:
                            task = asyncio.create_task(self.guarded_collect(job), name='intelligence-'+job['run_id'])
                            self.active[job['run_id']] = task
                            task.add_done_callback(lambda _, id=job['run_id']: self.active.pop(id, None))
                    if time.monotonic() - last_schedule > 30:
                        last_schedule = time.monotonic()
                        from ai2apps.identity import IdentityRepository
                        for schedule in schedules:
                            try:
                                principal = IdentityRepository(self.runtime.database).local_principal_for(schedule['owner'])
                                if getattr(self.runtime,'system_tasks',None) is not None:
                                    self.sync_system_schedules(schedule['owner'])
                                    continue
                                for channel in self.store.snapshot(schedule['owner'])['channels']:
                                    now = time.time();interval = channel.get('interval_hours', 0)*3600
                                    if interval and now >= max(channel.get('schedule_anchor', now), channel.get('last_attempt', 0))+interval:
                                        with suppress(ValueError):self.submit(principal, channel['id'], schedule['session_id'], True)
                            except Exception:
                                logger.exception('Intelligence schedule owner unavailable')
                except Exception:
                    logger.exception('Intelligence coordinator failed')
                try:
                    producer = getattr(getattr(self.runtime, 'remote', None), 'notifications', None)
                    if producer is not None:
                        await producer.refresh_policy(force=True)
                    await asyncio.to_thread(channel_notifications.enqueue_refresh_notifications, self.store, producer)
                except Exception:
                    logger.exception('Intelligence notification enqueue failed')
                with suppress(TimeoutError):await asyncio.wait_for(wake.get(), timeout=5)

    async def browser(self, job, source, key, *, recipe=None, program=None, parameters=None):
        import hashlib
        root = 'collection:'+job['run_id']
        self.tree.create(job['owner'], root, '更新频道', kind='collection')
        parent = root+':source:'+source['id']
        self.tree.create(job['owner'], parent, '刷新 '+source['name'], parent_id=root, kind='source')
        task_key = 'intelligence:'+job['run_id']+':'+source['id']+':'+key
        task_id = 'btask_'+hashlib.sha256((job['owner']+'\0'+task_key).encode()).hexdigest()
        if not social.site_key(source) and re.fullmatch(r'article-(?:rule-)?\d+',key) and not (recipe or {}).get('explicit'):
            if recipe:recipe = self.resolve_article_recipe(job['owner'],recipe)
            program = self.article_pipeline(source, program, recipe, parameters)
            recipe = None
        try:task = self.tasks.get(job['owner'],task_id)
        except KeyError:task = self.invocations.submit(owner=job['owner'], session_id=job['session_id'],
            profile=source.get('profile_key', 'default'), name=source['name']+' · '+key,
            key=task_key,
            caller_app_id='ai2apps.intelligence', agent_id=(recipe or {}).get('draft_id', ''),
            generation_id=(recipe or {}).get('generation_id', ''), capability=(recipe or {}).get('capability', ''),
            parameters=parameters or {}, source=program, parent_task_id=parent,
            reuse_page=(bool(source.get('x_mode')) and 'feed' in key and 'validate' not in key) or 'list' in key,
            # Source workflows await their own list/validation steps, and each
            # owns a distinct reuse scope. A list must not serialize other
            # sources (or their article readers) in the shared root/Profile.
            parallel_limit=3 if source.get('x_mode') else 1 if social.site_key(source) else 3)
        requested=(parameters or {}).get('url') or next((step.get('arguments',{}).get('url') for step in (program or {}).get('steps',[]) if step.get('arguments',{}).get('url')),source['url'])
        validation='validate' in key
        phase='validation' if validation else 'list' if any(v in key for v in ('list','feed','landing')) else 'article'
        async with self.runtime.notifications.subscribe() as wake:
            while True:
                current = self.store.get('runs', job['owner'], job['run_id'])
                if current['status'] != 'running':
                    if task.get('run_id'):self.runtime.agent_runtime.cancel(task['run_id'])
                    self.tasks.update(job['owner'], task['id'], status='cancelling' if task.get('run_id') else 'cancelled')
                    raise asyncio.CancelledError()
                task = self.tasks.get(job['owner'], task['id'])
                if task['status'] == 'completed':
                    run = self.runtime.agents.get_run(task['run_id'])
                    result=(run.output or {}).get('result', {})
                    seen=current.get('progress',{}).get('read_task_ids',[])
                    if not validation and task_id not in seen:seen=[*seen,task_id]
                    self.browser_activity.get(job['run_id'],{}).pop(task_id,None)
                    self.progress(job['owner'],job['run_id'],'已读取页面：'+source['name'],details={'read_task_ids':seen,'pages_read':len(seen),'active_pages':[]})
                    return result
                if task['status'] in ('failed', 'cancelled'):
                    self.browser_activity.get(job['run_id'],{}).pop(task_id,None)
                    raise RuntimeError(task.get('message') or 'WebAgent Task '+task['status'])
                waiting = task['status'] == 'interrupted'
                if task['status'] == 'waiting_input' and task.get('run_id'):
                    from ai2apps.browser.task_presentation import browser_task_wait_presentation
                    waiting = browser_task_wait_presentation(self.runtime.agents.list_interactions(task['run_id']))['status_label'] in ('等待协助','等待确认')
                if waiting:
                    self.browser_activity.get(job['run_id'],{}).pop(task_id,None)
                    reason=task.get('message') or '信息源需要登录、验证或确认，请处理后重新更新此源'
                    if task.get('run_id'):self.runtime.agent_runtime.cancel(task['run_id'])
                    self.tasks.update(job['owner'],task['id'],status='cancelling' if task.get('run_id') else 'cancelled')
                    raise SourceBlocked(reason+'；已跳过此信息源，其它信息源继续更新')
                self.browser_activity.setdefault(job['run_id'],{})[task_id]={'url':requested,'status':task['status'],'source_name':source['name']}
                self.progress(job['owner'], job['run_id'],
                    ('请在 AI 浏览器任务栏处理：' if waiting else '后台采集中：')+source['name'], logs=None,
                    details={'source_id':source['id'],'source_name':source['name'],'phase':phase,'waiting':waiting,'browser_task_id':task['id'],'browser_task_name':task.get('name',''),'browser_status':task['status'],'active_pages':[{'url':requested,'status':task['status']}]})
                with suppress(TimeoutError):await asyncio.wait_for(wake.get(), timeout=10)

    def resolve_article_recipe(self, owner, recipe):
        """Resolve the immutable generation's entry before compiling agent.call.

        Old learned recipes have no capability field. Direct invocation can fill
        it in, but a composed preload program must contain it at compile time.
        Never trust the cached copy of IR to select an executable entry.
        """
        from ai2apps.agent_builder.compiler import COMPILER_VERSION
        from ai2apps.agent_builder.service import capability_ir
        generation = self.runtime.agent_builder.get_generation(recipe['generation_id'],owner)
        if (generation.draft_id != recipe['draft_id'] or generation.status.value != 'active'
                or generation.compiler_version != COMPILER_VERSION):
            raise ValueError('Article WebAgent generation is not active or compatible for this owner')
        exports = generation.ir.get('capability_exports') or []
        capability = recipe.get('capability')
        if capability:
            if exports and not any(item.get('name') == capability for item in exports):
                raise ValueError('Unknown article WebAgent capability')
        elif len(exports)>1:
            raise ValueError('Select an explicit article WebAgent capability')
        else:
            capability = exports[0]['name'] if exports else f"agent.{generation.draft_id}.run"
        capability_ir(generation.ir,capability)
        return {**recipe,'capability':capability}

    @classmethod
    def article_pipeline(cls, source, program, recipe, parameters):
        url = (parameters or {}).get('url') or (program or {}).get('steps',[{}])[0].get('arguments',{}).get('url')
        if recipe:
            if not recipe.get('capability'):
                raise ValueError('Article WebAgent capability must be resolved before composing preload')
            program = cls.program(source,'agent.call',{'agent_id':recipe['draft_id'],
                'generation_id':recipe['generation_id'],
                **({'capability':recipe['capability']} if recipe.get('capability') else {}),
                'parameters':parameters or {}})
        if not url or not program:return program
        import copy
        result=copy.deepcopy(program)
        first=result['steps'][0]['name']
        result['steps'].insert(0,dict(name='preload_article',operation='open',execution='compiled',
            desc='Open article in background, then read when ready',arguments={'url':url,'preload':True},
            on={'success':first,'failed':'failed'}))
        return result

    @staticmethod
    def program(source, operation, arguments):
        # Scope the document; only read operations, no arbitrary application code.
        origin = site_agents.scope_url(source['url'])
        scopes = [origin+'/**']
        if source.get('x_mode'):scopes = ['https://x.com/**', 'https://www.x.com/**']
        if social.site_key(source) == 'weibo.com':scopes = ['https://weibo.com/**', 'https://www.weibo.com/**', 'https://s.weibo.com/**']
        return {'agent_type': 'web', 'site_scope': scopes, 'steps': [{
            'name': 'collect', 'operation': operation, 'execution': 'compiled',
            'desc': 'Read source evidence', 'arguments': arguments,
            'on': {'success': 'done', 'failed': 'failed'}}]}

    def recipe(self, owner, source, kind):
        if source.get(kind+'_agent_generation_id'):
            return site_agents.selected_agent(self.runtime, owner, source[kind+'_agent_generation_id'])
        record = self.store.site_recipe(owner, site_agents.recipe_key(source, kind))
        if not record or not record.get('healthy', True):return None
        from ai2apps.agent_builder.compiler import COMPILER_VERSION
        try:
            generation = self.runtime.agent_builder.get_generation(record['generation_id'], owner)
            if generation.status.value == 'active' and generation.compiler_version == COMPILER_VERSION:return record
        except Exception:pass
        return None

    async def read(self, job, source, key, url, **options):
        args = {'url': url, 'new_tab': False, 'close_tab': False, 'delay_ms': 1200,
                'allow_preview': True, 'max_chars': 20000, 'include_cover': True, 'include_images': True, 'observe_regions': not bool(social.site_key(source)), **options}
        if options.get('x'):
            return await self.read_x(job, source, key, args)
        return await self.browser(job, source, key, program=self.program(source, 'read_page', args))

    async def read_x(self, job, source, key, args):
        from . import x_agents
        from ai2apps.identity import IdentityRepository
        from ai2apps.agent_builder.models import StepOutcome
        owner=job['owner'];kind='x-list' if args['x']=='feed' else 'x-article'
        recipe_key=site_agents.recipe_key(source,kind)
        previous=self.store.site_recipe(owner,recipe_key)
        record=self.recipe(owner,source,kind)
        page=None
        if record:
            try:
                page=await self.browser(job,source,key+'-rule',recipe=record,parameters={'url':args['url']})
                if page.get('x_rule_valid'):return page
            except RuntimeError:
                pass
            self.store.invalidate_site_recipe(owner,recipe_key,record['generation_id'])
        if page is None:
            page=await self.browser(job,source,key,program=self.program(source,'read_page',args))
        if not page.get('x_observed'):return page
        # One bounded repair per source/template per update, never one model call per post.
        repair_key=source['id']+':'+kind
        with self.store.connect() as db:
            data=json.loads(db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(job['run_id'],)).fetchone()['data'])
            attempted=data.setdefault('x_repair_attempts',[])
            if repair_key in attempted:return page
            attempted.append(repair_key)
            db.execute('UPDATE collection_jobs SET data=? WHERE run_id=?',(json.dumps(data),job['run_id']))
        try:
            principal=IdentityRepository(self.runtime.database).local_principal_for(owner)
            self.progress(owner,job['run_id'],'正在学习采集规则：'+source['name'],details={'phase':'validation','active_pages':[]})
            candidate=await x_agents.learn(self.runtime,principal,source,args['x'],args['url'],page['x_observed'],previous)
            result=await self.browser(job,source,key+'-validate-rule',program=self.program(source,'read_page',{**args,'x_extraction':candidate['rule']}))
            if not (result.get('x_rule_valid') and result.get('x_rule_compared')) and not x_agents.matches(page,result,args['x']):return page
            repo=self.runtime.agent_builder
            repo.add_evidence(draft_id=candidate['draft_id'],owner_user_id=owner,step_name='extract',generation_id=candidate['generation_id'],
                outcome=StepOutcome.SUCCESS,evidence={'validation':'x-observed-post-comparison','mode':args['x']})
            repo.activate_generation(candidate['draft_id'],candidate['generation_id'],owner)
            self.store.save_site_recipe(owner,recipe_key,candidate)
            return result
        except Exception:
            logger.exception('X rule repair failed; retaining observed post evidence')
            return page

    async def read_list(self, job, source, key='list'):
        sort = {'xiaohongshu_sort':source.get('xiaohongshu_sort', 'latest'), 'search_provider':'xiaohongshu', 'news_scan':False} if social.xiaohongshu_search_url(source['url']) else {}
        return await self.browser(job, source, key, program={
            **self.program(source, 'open', {'url': source['url']}),
            'steps': [dict(name='open', operation='open', execution='compiled', desc='Open source',
                          arguments={'url': source['url'], 'delay_ms':1200, 'reuse_current_page':True}, on={'success':'extract','failed':'failed'}),
                      dict(name='extract',operation='extract_list',execution='compiled',desc='Read article list',
                           arguments={'limit':40,'observe_regions':True,'news_scan':True,**sort},on={'success':'done','failed':'failed'})]})

    @staticmethod
    def list_needs_check(result):
        # Healthy compiled rules already carry validation evidence. Re-scan only
        # suspicious results; missing/drifted rules take the learning path.
        urls = {item.get('url') or item.get('href') for item in result.get('items', [])
                if isinstance(item, dict)} - {None, ''}
        return len(urls) < 3 or bool(result.get('extraction_fallback')) or result.get('outcome') in ('failed', 'not_found')

    @staticmethod
    def list_undercovered(result, baseline):
        expected = {i.get('url') or i.get('href') for i in baseline.get('items', [])} - {None, ''}
        actual = {i.get('url') or i.get('href') for i in result.get('items', [])} - {None, ''}
        return len(expected) >= 3 and len(actual & expected) / len(expected) < .8

    async def ensure_images(self, job, source, page, url, key, stats):
        """Every extraction path receives one bounded image recovery attempt."""
        from .models import cover_url
        page = dict(page)
        def usable(value):
            return isinstance(value, dict) and bool(cover_url(value.get('url', '')))
        def normalize(value):
            images = [i for i in value.get('images', []) if usable(i)]
            cover = value.get('cover_image')
            if not usable(cover):
                cover = images[0] if images else None
            if cover and not any(i['url'] == cover['url'] for i in images):
                images.insert(0, {'url': cover['url'], 'alt': ''})
            value['images'] = images[:24]
            value['cover_image'] = cover
            return bool(cover)
        if normalize(page):
            return page
        stats['image_retries'] = stats.get('image_retries', 0) + 1
        try:
            site = social.site_key(source)
            if site:
                await asyncio.sleep(5)
            opts = {'youtube': 'video'} if site == 'youtube.com' else {'weibo': 'detail', 'social_source_url': source['url']} if site == 'weibo.com' else {}
            recovered = await self.read(job, source, key, url, **opts)
            if normalize(recovered):
                page['images'] = recovered['images']
                page['cover_image'] = recovered['cover_image']
                stats['image_recovered'] = stats.get('image_recovered', 0) + 1
            else:
                stats['image_missing'] = stats.get('image_missing', 0) + 1
        except Exception:
            logger.exception('Image recovery failed; retaining article text')
            stats['image_failed'] = stats.get('image_failed', 0) + 1
        return page

    @staticmethod
    def evidence(source, page, requested):
        data = {k: page[k] for k in ('platform', 'post_id', 'author', 'published_at', 'coverage',
            'content_type', 'duration_seconds', 'page_count', 'access_reason', 'extraction_method', 'fallback_reason',
            'extracted_chars', 'returned_chars', 'extraction_limit', 'non_content_nodes_removed', 'truncated', 'source_blocks') if page.get(k) is not None}
        data['truncated'] = bool(data.get('truncated') or len(page.get('text', '')) > 20000)
        data['returned_chars'] = min(len(page.get('text', '')), 20000)
        return Page.model_validate({**data, 'source_id': source['id'], 'url': page['url'], 'requested_url': requested,
            'title': page.get('title') or source['name'], 'text': page.get('text', '')[:20000],
            'image_url': (page.get('cover_image') or {}).get('url', ''), 'images': page.get('images', [])[:24]}).model_dump()

    async def learn(self, job, source, principal, kind, baseline, key, stats):
        regions = baseline.get('observed_regions')
        if isinstance(regions, dict):regions = regions.get('regions', [])
        if not regions or baseline.get('coverage') == 'preview':return
        try:
            stats['learning_calls'] += 1
            body = site_agents.LearnRequest(kind=kind, url=baseline.get('url') or source['url'], regions=regions[:40])
            candidate = await site_agents.learn(self.runtime, None, principal, source, body,
                self.store.site_recipe(job['owner'], site_agents.recipe_key(source,kind)))
            ir = candidate['ir']
            # Candidate is not active yet. Validate its extraction using a queued
            # program, then activate only with evidence matching generic results.
            step = ir['steps'][0]
            args = {**step['arguments']}
            if kind == 'article':args['url'] = body.url
            steps = []
            if kind == 'list':steps.append(dict(name='open',operation='open',execution='compiled',desc='Open validation page',arguments={'url':body.url,'reuse_current_page':True},on={'success':'extract','failed':'failed'}))
            steps.append(dict(name='extract',operation=step['operation'],execution='compiled',desc='Validate observed region',arguments=args,on={'success':'done','failed':'failed'}))
            result = await self.browser(job,source,key,program={'agent_type':'web','site_scope':[site_agents.scope_url(body.url)+'/**'],'steps':steps})
            if kind == 'list':
                expected = {item['url'] for item in baseline.get('items', []) if item.get('url')}
                actual = {item['url'] for item in result.get('items', []) if item.get('url')}
                samples, matched = len(expected), len(expected & actual)
            else:
                text = ' '.join(baseline.get('text','').split())
                chunks = [text[i:i+min(100,len(text)//3)] for i in (0,len(text)//3,2*len(text)//3)]
                samples, matched = 3, sum(bool(chunk) and chunk in ' '.join(result.get('text','').split()) for chunk in chunks)
            if kind == 'list':
                if samples < 3 or matched < 3 or matched/samples < .8:return
            elif not samples or matched < min(2,samples) or matched/samples < .6:return
            from ai2apps.agent_builder.models import StepOutcome
            repository = self.runtime.agent_builder
            repository.add_evidence(draft_id=candidate['draft_id'],owner_user_id=job['owner'],step_name='extract',generation_id=candidate['generation_id'],outcome=StepOutcome.SUCCESS,
                evidence={'samples':samples,'matched':matched,'validation':'background-generic-extraction-comparison'})
            repository.activate_generation(candidate['draft_id'],candidate['generation_id'],job['owner'])
            self.store.save_site_recipe(job['owner'],site_agents.recipe_key(source,kind),candidate)
            stats['learned'] = stats.get('learned',0)+1
        except Exception:
            logger.exception('Background site learning failed; generic evidence retained')

    async def guarded_collect(self, job):
        """Stop a stuck coordinator without replaying uncertain browser actions."""
        from ai2apps.browser.progress_watchdog import NO_PROGRESS_SECONDS, ProgressDeadline, completed_steps, browser_activity
        owner,id=job['owner'],job['run_id']
        root='collection:'+id
        def signature():
            run=self.store.get('runs',owner,id)
            p=run.get('progress',{})
            counts=tuple(p.get(k,0) for k in ('pages_read','articles_extracted','articles_saved','sources_completed','projections_completed'))+(p.get('projection_stage'),)
            with self.store.connect() as db:
                row=db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(id,)).fetchone()
            state=json.loads(row['data']).get('editorial',{}).get('state',{}) if row else {}
            return (counts,entities.signature(state),completed_steps(self.runtime.database,owner=owner,root_id=root))
        watch=ProgressDeadline(signature())
        task=asyncio.create_task(self.collect(job))
        try:
            while not task.done():
                done,_=await asyncio.wait({task},timeout=self.watchdog_poll_seconds)
                if done:break
                run=self.store.get('runs',owner,id)
                # Final projections still own the channel slot after article
                # persistence. They must retain a progress deadline as well.
                if run['status'] not in ('running','completed','partial'):continue
                p=run.get('progress',{})
                # Give a stalled leaf its own deadline and bounded cleanup grace
                # before cancelling the whole collection and healthy siblings.
                activity=browser_activity(self.runtime,owner=owner,root_id=root)
                active_child=activity['running']>0
                scheduler=getattr(self.runtime,'worker_scheduler',None)
                if scheduler is not None:
                    model_activity=await scheduler.scoped_activity(actor_id=owner,
                        app_id='ai2apps.intelligence',session_id='intelligence-'+run['channel_id'])
                    activity={key:activity[key]+model_activity[key] for key in activity}
                waiting=not activity['running'] and (activity['blocked']>0 or bool(p.get('waiting')))
                watch.timeout=NO_PROGRESS_SECONDS+(30 if active_child else 0)
                if not watch.observe(signature(),waiting=waiting):continue
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)
                reason='连续 5 分钟无有效进展；最后阶段：'+str(p.get('phase') or '准备采集')
                if p.get('source_name'):reason+='；信息源：'+p['source_name']
                for child_run in self.tree.cancel(owner,root):self.runtime.agent_runtime.cancel(child_run)
                self.tree.finish(owner,root,'failed',{'code':'no_progress_timeout','message':reason})
                self.store.fail_finalization(owner,id,reason+'；已保存内容保留，可重试')
                self.changed(owner,id)
                return
            await task
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)

    async def collect(self, job):
        owner, id = job['owner'], job['run_id']
        pages, logs = [], []
        from ai2apps.identity import IdentityRepository
        try:
            from ai2apps.system_tasks.sessions import execution_principal
            principal = execution_principal(self.runtime, owner)
            run = self.store.get('runs', owner, id);channel = self.store.get('channels', owner, run['channel_id'])
            # Re-resolve on execution/restart: old persisted jobs may carry a
            # Mobile owner-home Chat Session. Do not weaken its scope guard.
            session_id = self.execution_session(owner)
            job = {**job, 'session_id': session_id}
            with self.store.connect() as db:
                db.execute('UPDATE collection_jobs SET session_id=? WHERE owner=? AND run_id=?', (session_id, owner, id))
                db.execute('UPDATE collection_schedules SET session_id=? WHERE owner=?', (session_id, owner))
            self.tree.create(owner, 'collection:'+id, '刷新情报 · '+channel['name'], kind='collection')
            self.ensure_source_nodes(job)
            saved_job=json.loads(job['data'])
            if saved_job.get('retry_pages') and saved_job.get('rebuild_posts'):
                pages=saved_job['retry_pages'];logs=saved_job['retry_logs']
                for source in saved_job['sources']:
                    own=[p for p in pages if p['source_id']==source['id']]
                    log=next(l for l in logs if l.get('source_id')==source['id'])
                    self.tree.finish(owner,'collection:'+id+':source:'+source['id'],result={'pages':own,'log':log,'source_id':source['id']})
                self.progress(owner,id,'使用已采集内容重试 AI 整理',logs,details={'phase':'digest','active_pages':[],'articles_extracted':len(pages)})
                await self.finish(principal,channel,id,pages,logs)
                self.tree.finish(owner,'collection:'+id,result={'collection_run_id':id,'sources':logs})
                return
            if saved_job.get('retry_pages') and not saved_job.get('recovery_complete'):
                await self.recover_then_refresh(principal,channel,job,saved_job)
            async def collect_source(source):
                pages=[]
                source_node = 'collection:'+id+':source:'+source['id']
                node = self.tree.get(owner, source_node)
                cached = json.loads(node['result_json'])
                cached = cached.get('result', cached)
                if node['status'] in ('completed','failed','finishing') and 'pages' in cached:
                    pages.extend(cached['pages']);logs.append(cached['log'])
                    return pages
                source_start = len(pages)
                count, skipped, lease = 0, 0, None
                started = time.monotonic();stats = {'reused': 0, 'fallback': 0, 'learning_calls': 0}
                try:
                    site = social.site_key(source)
                    if site:
                        # Persist the cooldown admission alongside the job; restart never claims twice.
                        lease_key = 'lease:'+source['id']
                        with self.store.connect() as db:
                            data = json.loads(db.execute('SELECT data FROM collection_jobs WHERE run_id=?', (id,)).fetchone()['data'])
                        lease = data.get(lease_key)
                        if lease is None:
                            lease = self.store.claim_social(owner, source['id'], manual=not run.get('scheduled', False))
                            data[lease_key] = lease
                            with self.store.connect() as db:db.execute('UPDATE collection_jobs SET data=? WHERE run_id=?', (json.dumps(data), id))
                        if not lease['allowed']:
                            log = dict(source_id=source['id'], name=source['name'], status='deferred', pages=0, skipped=0, message=lease['reason'])
                            logs.append(log)
                            self.tree.finish(owner, source_node, result={'source_id':source['id'], 'pages':[], 'log':log})
                            return pages
                    record = self.recipe(owner, source, 'list') if not social.xiaohongshu_search_url(source['url']) and not source.get('x_mode') and (source.get('list_agent_generation_id') or not site) else None
                    landing = None
                    baseline = None
                    if record:
                        try:
                            result = await self.browser(job, source, 'list-rule', recipe=record, parameters={'url': source['url']})
                            if not isinstance(result.get('items'), list):raise RuntimeError('列表 WebAgent 必须返回 items 数组')
                            stats['reused'] += 1
                        except RuntimeError:
                            if record.get('explicit'):raise
                            self.store.invalidate_site_recipe(owner, site_agents.recipe_key(source, 'list'), record['generation_id'])
                            record = None;stats['fallback'] += 1
                    if record and not record.get('explicit') and not site and self.list_needs_check(result):
                        baseline = await self.read_list(job, source, 'list-coverage')
                        if self.list_undercovered(result, baseline):
                            self.store.invalidate_site_recipe(owner, site_agents.recipe_key(source, 'list'), record['generation_id'])
                            record = None
                            result = baseline
                            stats['fallback'] += 1
                    if not record:
                        if source.get('x_mode'):
                            _, feeds = social.x_targets(source['x_mode'], source['x_values'], source.get('x_sort','latest'))
                            combined = {}
                            for index, url in enumerate(feeds):
                                feed = await self.read(job, source, 'x-feed-'+str(index), url, x='feed')
                                for item in feed.get('items', []):combined[item.get('post_id') or item['url']] = item
                            result = {'items':list(combined.values())}
                        elif site == 'youtube.com':
                            if urlsplit(source['url']).path == '/watch':result = {'items': [{'url': source['url'], 'title': source['name']}]}
                            else:result = await self.read(job, source, 'feed', source['url'], youtube='feed')
                        elif site == 'weibo.com':result = await self.read(job, source, 'feed', source['url'], weibo='feed')
                        else:
                            result = baseline if baseline is not None else await self.read_list(job, source)
                    if not record and not site:
                        await self.learn(job,source,principal,'list',result,'validate-list',stats)
                    if result.get('discovery'):
                        stats['list_discovery'] = result['discovery']
                    candidates = []
                    for item in (result.get('items', []) if source.get('x_mode') else result.get('items', [])[:40]):
                        with suppress(ValueError):candidates.append(Candidate.model_validate({'url': item.get('url') or item.get('href'), 'title':str(item.get('title',''))[:500], 'text':str(item.get('text') or item.get('summary') or '')[:1500]}).model_dump())
                    pending = self.store.pending_candidates(owner, channel['id'], candidates, [u for p in pages for u in (p['url'],p['requested_url'])])
                    skipped = pending['skipped'];targets = pending['candidates']
                    if site == 'weibo.com':
                        history = {r['page']['url']:r for r in self.store.filtered_posts(owner, channel['id'])}
                        eligible = [p for p in targets if p['url'] not in history]
                        decisions = await post_filter.review(self.runtime, None, principal, channel, eligible, self.store.preferences(owner,channel['id']), 'list')
                        rejected = set()
                        for p,d in zip(eligible,decisions):
                            if d.reject:self.store.save_filtered_post(owner,channel['id'],{**p,'source_id':source['id']},d.reason,'list');rejected.add(p['url'])
                        targets = [p for p in targets if p['url'] not in rejected and history.get(p['url'],{}).get('status') != 'filtered']
                    if not candidates and not site and urlsplit(source['url']).path in ('', '/'):
                        raise RuntimeError('No article links extracted from source homepage; homepage was not imported as an article')
                    if not candidates and not site and not (record or {}).get('explicit') and landing is None:
                        landing = await self.browser(job, source, 'landing', recipe=self.recipe(owner,source,'article'), parameters={'url':source['url']}) if source.get('article_agent_generation_id') else await self.read(job, source, 'landing', source['url'])
                    if not candidates and landing:
                        landing = await self.ensure_images(job, source, landing, source['url'], 'landing-images', stats)
                        pages.append(self.evidence(source, landing, source['url']));count += 1
                    batch_limit = len(targets) if source.get('x_mode') else 2 if site else 10
                    stats['post_failures'] = []
                    stats['pending_remaining'] = max(0, len(targets)-batch_limit)
                    async def read_article(pair):
                        n,item=pair
                        if site:await asyncio.sleep(5)
                        article = self.recipe(owner, source, 'article') if not source.get('x_mode') and (source.get('article_agent_generation_id') or not site) else None
                        if article:
                            try:
                                page = await self.browser(job, source, 'article-rule-'+str(n), recipe=article, parameters={'url':item['url']})
                                if article.get('explicit') and (not isinstance(page.get('text'), str) or not page['text'].strip()):raise RuntimeError('内容 WebAgent 必须返回非空 text')
                                if page.get('extraction_fallback'):raise RuntimeError('site_rule_drift')
                                stats['reused'] += 1
                            except RuntimeError:
                                if article.get('explicit'):raise
                                self.store.invalidate_site_recipe(owner,site_agents.recipe_key(source,'article'),article['generation_id'])
                                stats['fallback'] += 1;article = None
                        if not article:
                            opts = {'x':'detail'} if source.get('x_mode') else {'youtube':'video'} if site == 'youtube.com' else {'weibo':'detail','social_source_url':source['url']} if site == 'weibo.com' else {}
                            try:
                                page = await self.read(job, source, 'article-'+str(n), item['url'], **opts)
                                if source.get('x_mode') and (page.get('outcome') == 'failed' or not page.get('text', '').strip()):
                                    raise RuntimeError(page.get('reason') or 'x_post_body_not_visible')
                            except RuntimeError as error:
                                if not source.get('x_mode'):raise
                                stats['post_failures'].append({'url':item['url'], 'reason':str(error)[:300]})
                                self.progress(owner,id,'单篇读取失败，继续采集：'+source['name'],logs=None)
                                return None
                            if not site and n==0:await self.learn(job,source,principal,'article',page,'validate-article-'+str(n),stats)
                        if not source.get('x_mode'):
                            page = await self.ensure_images(job, source, page, item['url'], 'article-images-'+str(n), stats)
                        evidence=self.evidence(source,page,item['url'])
                        total=self.store.get('runs',owner,id).get('progress',{}).get('articles_extracted',0)+1
                        self.progress(owner,id,'已提取文章：'+source['name'],details={'articles_extracted':total})
                        return evidence
                    async def collect_article(pair):
                        try:return await read_article(pair)
                        except asyncio.CancelledError:raise
                        except Exception as error:
                            stats['post_failures'].append({'url':pair[1]['url'],'reason':str(error)[:300]})
                            self.progress(owner,id,'单篇读取失败，继续采集：'+source['name'])
                            return None
                    from ai2apps.browser.processing_pool import ordered_pool
                    extracted=await ordered_pool(enumerate(targets[:batch_limit]),collect_article,3 if source.get('x_mode') else 1 if site else 3)
                    pages.extend(p for p in extracted if p is not None);count+=sum(p is not None for p in extracted)
                    log = dict(source_id=source['id'],name=source['name'],status='failed' if stats['post_failures'] else 'success',pages=count,skipped=skipped,
                        message=f'检查 {len(candidates)} 条，跳过 {skipped} 条，读取 {count} 篇，单篇失败 {len(stats["post_failures"])} 篇，剩余 {stats.get("pending_remaining",0)} 篇待下次更新；补图成功 {stats.get("image_recovered",0)}，未发现图片 {stats.get("image_missing",0)}，补图失败 {stats.get("image_failed",0)}；通过统一后台 Task 执行')
                except Exception as error:
                    logger.exception('Intelligence source collection failed')
                    log = dict(source_id=source['id'],name=source['name'],status='failed',pages=count,skipped=skipped,message=str(error)[:500])
                if lease and lease.get('allowed'):
                    with suppress(ValueError):self.store.finish_social(owner,source['id'],lease['token'],'success' if stats.get('post_failures') and count else log['status'])
                log['agent_stats'] = {**stats, 'source_ms':round((time.monotonic()-started)*1000)}
                logs.append(log);self.progress(owner,id,'已读取 '+source['name'],logs,details={'sources_completed':len(logs),'active_pages':[]})
                self.tree.finish(owner, source_node, 'failed' if log['status']=='failed' else 'completed', result={'source_id':source['id'], 'pages':pages[source_start:], 'log':log})
                return pages
            from ai2apps.browser.processing_pool import ordered_pool
            batches=await ordered_pool(saved_job['sources'],collect_source,2)
            seen=set()
            for batch in batches:
                for page in batch:
                    if page['url'] not in seen:pages.append(page);seen.add(page['url'])
            self.progress(owner,id,'后台正在比较新内容并生成情报',logs,details={'phase':'digest','active_pages':[],'articles_extracted':len(pages)})
            await self.finish(principal, channel, id, pages, logs)
            self.tree.finish(owner, 'collection:'+id, 'failed' if any(log['status']=='failed' for log in logs) else 'completed', result={'collection_run_id':id, 'sources':logs})
            if self.tree.get(owner,'collection:'+id)['status'] in ('completed','failed','cancelled'):
                self.store.complete_pending(owner,id)
        except asyncio.CancelledError:raise
        except Exception as error:
            logger.exception('Intelligence background collection failed')
            with suppress(KeyError):
                for source in json.loads(job['data'])['sources']:
                    with suppress(KeyError):self.tree.finish(owner, 'collection:'+id+':source:'+source['id'], 'failed')
                self.tree.finish(owner, 'collection:'+id, 'failed', {'error':str(error)[:400]})
            with suppress(ValueError,KeyError):self.store.progress(owner,id,'后台更新失败：'+(str(getattr(error,'detail',error)) or ('AI 整理等待超时，可使用已采集内容重试' if isinstance(error,TimeoutError) else type(error).__name__))[:400]+'；内容未标为已处理','partial' if self.store.get('runs',owner,id).get('progress',{}).get('cache_articles_saved') else 'failed',logs=logs)
        finally:
            self.browser_activity.pop(id,None)
            self.changed(owner,id)

    async def recover_then_refresh(self,principal,channel,job,saved_job):
        owner,id=job['owner'],job['run_id']
        node='collection:'+id+':recover'
        self.tree.create(owner,node,'补齐缓存情报',parent_id='collection:'+id,kind='organize')
        self.progress(owner,id,'先整理上次缓存，随后采集最新内容',details={'phase':'digest','refresh_stage':'cache','cached_pages':len(saved_job['retry_pages']),'active_pages':[]})
        try:
            summary=await self._finish(principal,channel,id,saved_job['retry_pages'],[],recovery=True)
        except Exception as error:
            self.tree.finish(owner,node,'failed',{'error':str(error) or type(error).__name__})
            raise
        self.tree.finish(owner,node,result=summary)
        with self.store.connect() as db:
            current=json.loads(db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(id,)).fetchone()['data'])
            current['recovered_editorial']=current.get('editorial',{})
            current.update(recovery_complete=True,recovery_summary=summary,editorial_complete=False)
            for key in ('retry_pages','retry_logs','editorial','editorial_context','editorial_origin_run_id'):
                current.pop(key,None)
            db.execute('UPDATE collection_jobs SET data=? WHERE run_id=?',(json.dumps(current),id))
        self.progress(owner,id,'缓存整理完成，正在采集最新内容',[],details={'phase':'collecting','refresh_stage':'fresh','cache_articles_saved':summary['articles'],'articles_saved':summary['articles'],'articles_extracted':0,'sources_completed':0,'active_pages':[]})

    async def finish(self, principal, channel, id, pages, logs):
        owner = principal.actor_user_id
        root = 'collection:'+id
        self.tree.create(owner, root, '刷新情报 · '+channel['name'], kind='collection')
        organize = root+':organize'
        node = self.tree.create(owner, organize, '整理情报：去重、翻译、摘要与保存', parent_id=root, kind='organize')
        if node['status'] == 'completed':
            return
        try:
            await self._finish(principal, channel, id, pages, logs)
        except asyncio.CancelledError:
            # Local shutdown preserves this node for recovery; user cancellation
            # has already marked the whole tree as cancelling.
            raise
        except Exception as error:
            self.tree.finish(owner, organize, 'failed', {'error':str(error)[:400]})
            raise
        else:
            self.tree.finish(owner, organize, result={'collection_run_id':id})

    async def _finish(self, principal, channel, id, pages, logs, *, recovery=False):
        owner = principal.actor_user_id
        run = self.store.get('runs', owner, id)
        articles = [a for a in self.store.snapshot(owner)['articles'] if a['channel_id']==channel['id']]
        if run['status'] == 'running' and not run.get('pending_status'):
            history = self.store.filtered_posts(owner,channel['id'])
            enabled = {s['id'] for s in self.store.snapshot(owner)['sources'] if s['enabled']}
            if run.get('source_id'):enabled &= {run['source_id']}
            restored = [r['page'] for r in history if r['status']=='restored' and r['stage']=='detail' and r['page']['source_id'] in enabled]
            fresh = self.store.new_pages(owner,channel['id'],restored+pages)
            limited, budget = [], 0
            for page in fresh:
                if budget+len(page['text']) > 120000:break
                limited.append(page);budget += len(page['text'])
            approved = {r['page']['url'] for r in history if r['status']=='restored'}
            posts = [p for p in limited if post_filter.is_post(p) and p['url'] not in approved]
            decisions = await post_filter.review(self.runtime,None,principal,channel,posts,self.store.preferences(owner,channel['id']))
            rejected = set()
            for p,d in zip(posts,decisions):
                if d.reject:self.store.save_filtered_post(owner,channel['id'],p,d.reason,'detail');rejected.add(p['url'])
            limited = [p for p in limited if p['url'] not in rejected]
            all_previous = [a for a in self.store.snapshot(owner)['articles'] if a['channel_id']==channel['id']]
            from .source_history import source_key
            incoming_urls = {source_key(p) for p in limited}
            matching_previous = [a for a in all_previous if any(source_key(s) in incoming_urls for s in a.get('sources',[]))]
            previous = matching_previous + [a for a in all_previous if a not in matching_previous][:40]
            with self.store.connect() as db:
                row = db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(id,)).fetchone()
                job_data = json.loads(row['data']) if row else {}
            rebuild=bool(job_data.get('rebuild_posts'))
            if rebuild:previous=[a for a in previous if not a.get('manual_import') and any(ref.get('platform')=='x' for ref in a.get('sources',[]))][:12]
            # Freeze the evidence numbering across restart and partial retry.
            editorial = job_data.get('editorial') or {'pages':limited,'state':{}}
            limited = editorial['pages']
            def checkpoint(state):
                editorial['state']=state
                if row:
                    with self.store.connect() as db:
                        current=json.loads(db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(id,)).fetchone()['data'])
                        current['editorial']=editorial
                        db.execute('UPDATE collection_jobs SET data=? WHERE run_id=?',(json.dumps(current),id))
            job_data['editorial_context']=self.editorial_context(channel)
            if row:
                with self.store.connect() as db:
                    current=json.loads(db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(id,)).fetchone()['data'])
                    current['editorial_context']=job_data['editorial_context']
                    db.execute('UPDATE collection_jobs SET data=? WHERE run_id=?',(json.dumps(current),id))
            checkpoint(editorial['state'])
            def save_article(index,article):
                import hashlib,copy
                article['update_article_id']=article.get('update_article_id') or 'article_'+hashlib.sha256((job_data.get('editorial_origin_run_id',id)+':'+str(index)).encode()).hexdigest()[:32]
                self.store.finish(owner,id,[],[copy.deepcopy(article)],[],final=False)
                self.changed(owner,id)
                self.progress(owner,id,'正在逐篇生成并保存情报',details={'articles_saved':len(editorial['state'].get('articles',{}))+1+int(run.get('progress',{}).get('cache_articles_saved',0))})
            def editorial_progress(details):
                labels={'planning':'正在合并重复报道、规划新事件','writing':'正在整理、翻译并生成文章','saving':'正在保存情报'}
                phase=details.get('phase',self.store.get('runs',owner,id).get('progress',{}).get('phase'))
                self.progress(owner,id,labels.get(phase,'正在整理情报'),details={**details,'waiting':False,'active_pages':[]})
            articles = await service.digest(self.runtime,None,principal,channel,limited,previous,
                checkpoint=editorial['state'],save_checkpoint=checkpoint,on_article=save_article,on_progress=editorial_progress,**({'rebuild':True} if rebuild else {}))
            exclusions=editorial['state'].get('plan',{}).get('excluded_pages',[])
            if exclusions:
                logs=[*logs,{'source_id':'','name':'网页收录审核','status':'success','pages':0,
                    'message':'；'.join(limited[e['evidence_id']-1].get('title','')+'：'+e['reason'] for e in exclusions)}]
            failed_urls=getattr(articles,'failed_urls',set())
            failures=getattr(articles,'failures',[])
            if failures:logs=[*logs,{'source_id':'','name':'AI 整理','status':'failed','pages':0,'message':f'{len(failures)} 个事件整理失败，已保存其它文章；失败内容可重试'}]
            import copy
            self.store.finish(owner,id,[p for p in limited if p['url'] not in failed_urls],copy.deepcopy(articles),logs,final=not recovery,defer_completion=not recovery)
            if recovery:
                from . import projections
                projections.after_collection(self,owner,channel['id'])
                if failures:raise RuntimeError('部分缓存情报整理失败，已保存结果保留，可重试')
                return {'pages':len(pages),'changed':len(limited),'articles':len(articles)}
            if row:
                with self.store.connect() as db:
                    current=json.loads(db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(id,)).fetchone()['data'])
                    current['editorial_complete']=not bool(failures)
                    db.execute('UPDATE collection_jobs SET data=? WHERE run_id=?',(json.dumps(current),id))
            self.changed(owner,id)
        # Derived work has durable, independent System Tasks. Collection only
        # commits its outbox request and proceeds to browser-tree cleanup.
        from . import projections
        projections.after_collection(self,owner,channel['id'])
        self.progress(owner,id,'文章已保存，正在清理页面',details={'phase':'finalizing','projection_stage':'cleanup','active_pages':[]})
