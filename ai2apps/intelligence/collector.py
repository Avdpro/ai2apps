"""Durable Local collection coordinator. All browsing uses shared WebAgent Tasks."""
from __future__ import annotations
import asyncio
import json
import logging
import time
from contextlib import suppress
from urllib.parse import urlsplit

from ai2apps.browser.invocation import WebAgentInvocation
from ai2apps.browser.tasks import BrowserTaskRepository
from .store import IntelligenceStore
from .models import Candidate, Page
from . import service, site_agents, entity_categories, post_filter, knowledge_sync, topics, entities, social

logger = logging.getLogger(__name__)


class IntelligenceCollector:
    def __init__(self, runtime):
        self.runtime = runtime
        self.store = IntelligenceStore(runtime.config.paths.artifacts_path / 'intelligence')
        self.invocations = WebAgentInvocation(runtime)
        self.tasks = self.invocations.tasks
        self.active = {}
        self.stop = asyncio.Event()
        self.loop_task = None
        with self.store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS collection_jobs(run_id TEXT PRIMARY KEY, owner TEXT NOT NULL, session_id TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS collection_schedules(owner TEXT PRIMARY KEY, session_id TEXT NOT NULL);
            ''')

    def submit(self, principal, channel_id, session_id, scheduled=False):
        owner = principal.actor_user_id
        run = self.store.claim(owner, channel_id, scheduled, background_session=session_id)
        self.changed(owner, run['id'])
        self.runtime.notifications.notify()
        return self.store.get('runs', owner, run['id'])

    def changed(self, owner, run_id):
        self.runtime.events.append(event_type='intelligence.collection.changed',
            subject_id=BrowserTaskRepository.event_subject(owner), payload={'collection_run_id': run_id})

    def progress(self, owner, run_id, message, logs=None):
        current = self.store.get('runs', owner, run_id)
        self.store.progress(owner, run_id, message, logs=logs)
        if current.get('message') != message or logs is not None:
            self.changed(owner, run_id)

    async def startup(self):
        self.stop.clear()
        # Upgrade existing schedules without requiring an open Intelligence UI.
        from ai2apps.identity import IdentityRepository
        from ai2apps.api.agent_platform import _session
        with self.store.connect() as db:
            owners = [r['owner'] for r in db.execute("SELECT DISTINCT owner FROM channels WHERE json_extract(data,'$.interval_hours') > 0")]
        for owner in owners:
            try:
                principal = IdentityRepository(self.runtime.database).local_principal_for(owner)
                session = _session(self.runtime, principal, None)
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
                    with self.store.connect() as db:
                        jobs = [dict(r) for r in db.execute("SELECT j.* FROM collection_jobs j JOIN runs r ON r.id=j.run_id WHERE r.status='running'")]
                        schedules = [dict(r) for r in db.execute('SELECT * FROM collection_schedules')]
                    for job in jobs:
                        if job['run_id'] not in self.active:
                            task = asyncio.create_task(self.collect(job), name='intelligence-'+job['run_id'])
                            self.active[job['run_id']] = task
                            task.add_done_callback(lambda _, id=job['run_id']: self.active.pop(id, None))
                    if time.monotonic() - last_schedule > 30:
                        last_schedule = time.monotonic()
                        from ai2apps.identity import IdentityRepository
                        for schedule in schedules:
                            try:
                                principal = IdentityRepository(self.runtime.database).local_principal_for(schedule['owner'])
                                for channel in self.store.snapshot(schedule['owner'])['channels']:
                                    now = time.time();interval = channel.get('interval_hours', 0)*3600
                                    if interval and now >= max(channel.get('schedule_anchor', now), channel.get('last_attempt', 0))+interval:
                                        with suppress(ValueError):self.submit(principal, channel['id'], schedule['session_id'], True)
                            except Exception:
                                logger.exception('Intelligence schedule owner unavailable')
                except Exception:
                    logger.exception('Intelligence coordinator failed')
                with suppress(TimeoutError):await asyncio.wait_for(wake.get(), timeout=5)

    async def browser(self, job, source, key, *, recipe=None, program=None, parameters=None):
        import hashlib
        task_key = 'intelligence:'+job['run_id']+':'+source['id']+':'+key
        task_id = 'btask_'+hashlib.sha256((job['owner']+'\0'+task_key).encode()).hexdigest()
        try:task = self.tasks.get(job['owner'],task_id)
        except KeyError:task = self.invocations.submit(owner=job['owner'], session_id=job['session_id'],
            profile=source.get('profile_key', 'default'), name=source['name']+' · '+key,
            key=task_key,
            caller_app_id='ai2apps.intelligence', agent_id=(recipe or {}).get('draft_id', ''),
            generation_id=(recipe or {}).get('generation_id', ''), capability=(recipe or {}).get('capability', ''),
            parameters=parameters or {}, source=program)
        async with self.runtime.notifications.subscribe() as wake:
            while True:
                current = self.store.get('runs', job['owner'], job['run_id'])
                if current['status'] != 'running':
                    if task.get('run_id'):self.runtime.agent_runtime.cancel(task['run_id'])
                    self.tasks.update(job['owner'], task['id'], status='cancelled')
                    raise asyncio.CancelledError()
                task = self.tasks.get(job['owner'], task['id'])
                if task['status'] == 'completed':
                    run = self.runtime.agents.get_run(task['run_id'])
                    return (run.output or {}).get('result', {})
                if task['status'] in ('failed', 'cancelled'):
                    raise RuntimeError(task.get('message') or 'WebAgent Task '+task['status'])
                waiting = task['status'] == 'interrupted'
                if task['status'] == 'waiting_input' and task.get('run_id'):
                    from ai2apps.browser.task_presentation import browser_task_wait_presentation
                    waiting = browser_task_wait_presentation(self.runtime.agents.list_interactions(task['run_id']))['status_label'] in ('等待协助','等待确认')
                self.progress(job['owner'], job['run_id'],
                    ('请在 AI 浏览器任务栏处理：' if waiting else '后台采集中：')+source['name'], logs=None)
                with suppress(TimeoutError):await asyncio.wait_for(wake.get(), timeout=10)

    @staticmethod
    def program(source, operation, arguments):
        # Scope the document; only read operations, no arbitrary application code.
        origin = site_agents.scope_url(source['url'])
        scopes = [origin+'/**']
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
                'max_chars': 10000, 'include_cover': True, 'include_images': True, 'observe_regions': not bool(social.site_key(source)), **options}
        return await self.browser(job, source, key, program=self.program(source, 'read_page', args))

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
            'content_type', 'duration_seconds', 'page_count') if page.get(k) is not None}
        return Page.model_validate({**data, 'source_id': source['id'], 'url': page['url'], 'requested_url': requested,
            'title': page.get('title') or source['name'], 'text': page.get('text', '')[:20000],
            'image_url': (page.get('cover_image') or {}).get('url', ''), 'images': page.get('images', [])[:24]}).model_dump()

    async def learn(self, job, source, principal, kind, baseline, key, stats):
        regions = baseline.get('observed_regions')
        if isinstance(regions, dict):regions = regions.get('regions', [])
        if not regions:return
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
            if kind == 'list':steps.append(dict(name='open',operation='open',execution='compiled',desc='Open validation page',arguments={'url':body.url},on={'success':'extract','failed':'failed'}))
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
            if not samples or matched < min(2,samples) or matched/samples < .6:return
            from ai2apps.agent_builder.models import StepOutcome
            repository = self.runtime.agent_builder
            repository.add_evidence(draft_id=candidate['draft_id'],owner_user_id=job['owner'],step_name='extract',generation_id=candidate['generation_id'],outcome=StepOutcome.SUCCESS,
                evidence={'samples':samples,'matched':matched,'validation':'background-generic-extraction-comparison'})
            repository.activate_generation(candidate['draft_id'],candidate['generation_id'],job['owner'])
            self.store.save_site_recipe(job['owner'],site_agents.recipe_key(source,kind),candidate)
            stats['learned'] = stats.get('learned',0)+1
        except Exception:
            logger.exception('Background site learning failed; generic evidence retained')

    async def collect(self, job):
        owner, id = job['owner'], job['run_id']
        pages, logs = [], []
        from ai2apps.identity import IdentityRepository
        try:
            principal = IdentityRepository(self.runtime.database).local_principal_for(owner)
            run = self.store.get('runs', owner, id);channel = self.store.get('channels', owner, run['channel_id'])
            for source in json.loads(job['data'])['sources']:
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
                            lease = self.store.claim_social(owner, source['id'])
                            data[lease_key] = lease
                            with self.store.connect() as db:db.execute('UPDATE collection_jobs SET data=? WHERE run_id=?', (json.dumps(data), id))
                        if not lease['allowed']:
                            logs.append(dict(source_id=source['id'], name=source['name'], status='deferred', pages=0, skipped=0, message=lease['reason']));continue
                    record = self.recipe(owner, source, 'list') if source.get('list_agent_generation_id') or not site else None
                    landing = None
                    if record:
                        try:
                            result = await self.browser(job, source, 'list-rule', recipe=record, parameters={'url': source['url']})
                            if not isinstance(result.get('items'), list):raise RuntimeError('列表 WebAgent 必须返回 items 数组')
                            stats['reused'] += 1
                        except RuntimeError:
                            if record.get('explicit'):raise
                            self.store.invalidate_site_recipe(owner, site_agents.recipe_key(source, 'list'), record['generation_id'])
                            record = None;stats['fallback'] += 1
                    if not record:
                        if site == 'youtube.com':
                            if urlsplit(source['url']).path == '/watch':result = {'items': [{'url': source['url'], 'title': source['name']}]}
                            else:result = await self.read(job, source, 'feed', source['url'], youtube='feed')
                        elif site == 'weibo.com':result = await self.read(job, source, 'feed', source['url'], weibo='feed')
                        else:
                            result = await self.browser(job, source, 'list', program={
                                **self.program(source, 'open', {'url': source['url'], 'delay_ms': 1200}),
                                'steps': [dict(name='open', operation='open', execution='compiled', desc='Open source', arguments={'url': source['url'], 'delay_ms':1200}, on={'success':'extract','failed':'failed'}),
                                    dict(name='extract',operation='extract_list',execution='compiled',desc='Read article list',arguments={'limit':20,'observe_regions':True},on={'success':'done','failed':'failed'})]})
                    if not record and not site:
                        await self.learn(job,source,principal,'list',result,'validate-list',stats)
                    candidates = []
                    for item in result.get('items', [])[:40]:
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
                    if not candidates and not site and not (record or {}).get('explicit') and landing is None:
                        landing = await self.browser(job, source, 'landing', recipe=self.recipe(owner,source,'article'), parameters={'url':source['url']}) if source.get('article_agent_generation_id') else await self.read(job, source, 'landing', source['url'])
                    if not candidates and landing:
                        landing = await self.ensure_images(job, source, landing, source['url'], 'landing-images', stats)
                        pages.append(self.evidence(source, landing, source['url']));count += 1
                    for n,item in enumerate(targets[:2 if site else 3]):
                        if site:await asyncio.sleep(5)
                        article = self.recipe(owner, source, 'article') if source.get('article_agent_generation_id') or not site else None
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
                            opts = {'youtube':'video'} if site == 'youtube.com' else {'weibo':'detail','social_source_url':source['url']} if site == 'weibo.com' else {}
                            page = await self.read(job, source, 'article-'+str(n), item['url'], **opts)
                            if not site:await self.learn(job,source,principal,'article',page,'validate-article-'+str(n),stats)
                        page = await self.ensure_images(job, source, page, item['url'], 'article-images-'+str(n), stats)
                        pages.append(self.evidence(source, page, item['url']));count += 1
                    log = dict(source_id=source['id'],name=source['name'],status='success',pages=count,skipped=skipped,
                        message=f'检查 {len(candidates)} 条，跳过 {skipped} 条，读取 {count} 篇；补图成功 {stats.get("image_recovered",0)}，未发现图片 {stats.get("image_missing",0)}，补图失败 {stats.get("image_failed",0)}；通过统一后台 Task 执行')
                except Exception as error:
                    logger.exception('Intelligence source collection failed')
                    log = dict(source_id=source['id'],name=source['name'],status='failed',pages=count,skipped=skipped,message=str(error)[:500])
                if lease and lease.get('allowed'):
                    with suppress(ValueError):self.store.finish_social(owner,source['id'],lease['token'],log['status'])
                log['agent_stats'] = {**stats, 'source_ms':round((time.monotonic()-started)*1000)}
                logs.append(log);self.progress(owner,id,'已读取 '+source['name'],logs)
            self.progress(owner,id,'后台正在比较新内容并生成情报',logs)
            await self.finish(principal, channel, id, pages, logs)
        except asyncio.CancelledError:raise
        except Exception as error:
            logger.exception('Intelligence background collection failed')
            with suppress(ValueError,KeyError):self.store.progress(owner,id,'后台更新失败：'+str(getattr(error,'detail',error))[:400]+'；内容未标为已处理','failed',logs=logs)
        finally:self.changed(owner,id)

    async def finish(self, principal, channel, id, pages, logs):
        owner = principal.actor_user_id
        history = self.store.filtered_posts(owner,channel['id'])
        enabled = {s['id'] for s in self.store.snapshot(owner)['sources'] if s['enabled']}
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
        previous = [a for a in self.store.snapshot(owner)['articles'] if a['channel_id']==channel['id']][:40]
        articles = await service.digest(self.runtime,None,principal,channel,limited,previous)
        self.store.finish(owner,id,limited,articles,logs)
        self.changed(owner,id)
        # These projections can fail independently without undoing collected evidence.
        try:
            await asyncio.to_thread(knowledge_sync.sync_pending,self.store,self.runtime.knowledge,principal,channel['id'])
            if articles:
                repo = entities.Repository(self.store)
                saved = [a for a in self.store.snapshot(owner)['articles'] if a['channel_id']==channel['id']]
                for article in repo.pending(owner,saved)[:8]:
                    repo.ingest(owner,article,await entities.extract_or_review(self.runtime,None,principal,article,repo))
                await entity_categories.organize(self.runtime,None,principal,self.store,channel['id'])
                recent = topics.recent(saved)
                self.store.save_topics(owner,channel['id'],topics.signature(recent),await topics.summarize(self.runtime,None,principal,channel,recent))
                snapshot = repo.snapshot(owner)
                for entity in snapshot['entities']:
                    if not entity['watched'] or not entity['rule'].strip():continue
                    signature = entities.signature([entity['rule'],[(f['id'],f['historical']) for f in entity['facts']]])
                    if entity.get('evaluated_signature') == signature:continue
                    lead = await entities.opportunity(self.runtime,None,principal,entity,[l for l in snapshot['opportunities'] if l['entity_id']==entity['id']])
                    repo.save_lead(owner,entity,signature,lead)
        except Exception:logger.exception('Intelligence saved; derived projection needs retry')
