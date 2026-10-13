"""Local lifecycle owner of queued WebAgent runs and durable browser actions.

The worker only consumes native browser interactions. Human approvals and
credentials remain durable Agent interactions, never guessed or auto-approved.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import suppress
from urllib.parse import urlsplit

from .action_journal import BrowserActionJournal
from .background_bidi import BackgroundBiDi
from .background_executor import BackgroundExecutor
from .background_page import BackgroundPage
from .profiles import BrowserProfileRepository
from .shell_window import shell_browser_profile_key, shell_browser_window_broker
from .tasks import BrowserTaskRepository

logger = logging.getLogger(__name__)


class BackgroundBrowserRunner:
    def __init__(self, runtime, *, connection_factory=BackgroundBiDi):
        self.runtime = runtime
        self.connection_factory = connection_factory
        self.journal = BrowserActionJournal(runtime.database)
        self.executor = BackgroundExecutor(runtime)
        self.tasks = BrowserTaskRepository(runtime.database, runtime.events)
        self.pages = {}
        self.input_locks = {}
        self._active = {}
        self._stop = asyncio.Event()
        self._loop_task = None
        self.worker = 'local-background'

    async def startup(self):
        if self._loop_task is not None:
            return
        self.journal.recover()
        # Existing uncertain records also need delivery after a crash between
        # recovery and committing the failure response.
        with self.runtime.database.transaction() as c:
            uncertain=[dict(r) for r in c.execute("SELECT run_id,interaction_id FROM browser_action_executions WHERE state='uncertain'")]
        for item in uncertain:
            try:
                self.deliver_failure(item['run_id'],item['interaction_id'],reason='browser_process_interrupted')
                for owner in self.tasks.owners():
                    for task in self.tasks.list(owner):
                        if task['run_id']==item['run_id'] and task['status']=='interrupted':
                            self.tasks.update(owner,task['id'],status='running',worker=self.worker,lease_until=time.time()+90)
            except Exception:
                logger.exception('Could not deliver recovered browser failure')
                with suppress(Exception):self.runtime.agent_runtime.cancel(item['run_id'])
        # Admission and AgentRun insertion can straddle a process stop. Rebind
        # the durable run if committed; otherwise no browser action could start.
        for owner in self.tasks.owners():
            for task in self.tasks.list(owner):
                if task['status'] != 'starting' or task['run_id']:
                    continue
                with self.runtime.database.transaction() as c:
                    row = c.execute("SELECT id FROM agent_runs WHERE json_extract(input_json,'$.parameters.browser_task_id')=? AND json_extract(input_json,'$.parameters.owner_user_id')=?", (task['id'], owner)).fetchone()
                if row:
                    self.tasks.update(owner, task['id'], run_id=row['id'], status='running')
                elif task['worker'] == self.worker:
                    self.tasks.update(owner, task['id'], status='queued', worker='', lease_until=0)
                else:
                    self.tasks.update(owner, task['id'], status='failed', message='Local 在创建运行前重启，请重新提交。')
        self._stop.clear()
        self._loop_task = asyncio.create_task(self._loop(), name='local-webagent-executor')

    async def shutdown(self):
        self._stop.set()
        self.runtime.notifications.notify()
        if self._loop_task:
            await self._loop_task
        self._loop_task = None
        for task in self._active.values():
            task.cancel()
        await asyncio.gather(*self._active.values(), return_exceptions=True)
        self._active.clear()
        for page in self.pages.values():
            await page.connection.close()
        self.pages.clear()

    def interaction_mode(self, owner, url):
        domain = (urlsplit(url).hostname or '').removeprefix('www.')
        with self.runtime.database.transaction() as c:
            row = c.execute('SELECT interaction_mode FROM browser_domains WHERE owner=? AND domain=?', (owner, domain)).fetchone()
        return row['interaction_mode'] if row else 'natural'

    async def page_for(self, run):
        if run.id in self.pages:
            return self.pages[run.id]
        parameters = run.input['parameters']
        owner = parameters['owner_user_id']
        context = parameters.get('browser_context') or {}
        profile_key = context.get('profile_key') or 'default'
        profile = BrowserProfileRepository(self.runtime.database).require(owner, profile_key)
        from ai2apps.helper_control import HelperControlClient
        helper = HelperControlClient.from_environment()
        if helper is not None:
            await asyncio.to_thread(helper.ensure_browser_host, actor_user_id=owner)
        connection = await self.connection_factory().connect()
        try:
            # Resolve native container identity for supplied contexts as well;
            # a caller may not bind this actor's run to another actor's tab.
            request_id = shell_browser_window_broker.enqueue(action='bind',
                profile_key=shell_browser_profile_key(owner, profile_key),
                profile_name=profile.name, is_default=profile.is_default)
            binding = await asyncio.to_thread(shell_browser_window_broker.wait, request_id)
            user_context = binding.get('user_context')
            if not user_context:
                raise RuntimeError('Browser host did not bind the requested Profile')
            reuse_scope=context.get('reuse_scope')
            if reuse_scope and not context.get('bidi_context'):
                tree=await connection.command('browsingContext.getTree', {'maxDepth':0})
                with self.runtime.database.transaction(write=True) as c:
                    candidates=c.execute("SELECT id,run_id,browser_context_json FROM browser_tasks WHERE owner=? AND profile_key=? AND status IN ('completed','failed') AND json_extract(browser_context_json,'$.reuse_scope')=? AND json_extract(browser_context_json,'$.cleanup.state')='retained' ORDER BY updated_at DESC", (owner,profile_key,reuse_scope)).fetchall()
                    for prior in candidates:
                        shared=json.loads(prior['browser_context_json'])
                        if shared.get('user_context')!=user_context or shared.get('created_by_run')!=prior['run_id']:continue
                        if not any(i['context']==shared.get('bidi_context') and i.get('userContext')==user_context for i in tree.get('contexts',[])):continue
                        context={**shared, **context, 'bidi_context':shared['bidi_context'], 'user_context':user_context, 'created_by_run':run.id, 'cleanup':{'state':'pending'}}
                        row=c.execute('SELECT input_json FROM agent_runs WHERE id=?',(run.id,)).fetchone()
                        current=json.loads(row['input_json']);current['parameters']['browser_context']=context
                        c.execute('UPDATE agent_runs SET input_json=? WHERE id=?',(json.dumps(current),run.id))
                        # Transfer ownership atomically; only the new run may close the page.
                        shared.update(created_by_run='',owned_contexts={},cleanup={'state':'verified','transferred_to':run.id})
                        c.execute('UPDATE browser_tasks SET browser_context_json=? WHERE id=?',(json.dumps(shared),prior['id']))
                        old=c.execute('SELECT input_json FROM agent_runs WHERE id=?',(prior['run_id'],)).fetchone()
                        if old:
                            previous=json.loads(old['input_json']);previous['parameters']['browser_context']=shared
                            c.execute('UPDATE agent_runs SET input_json=? WHERE id=?',(json.dumps(previous),prior['run_id']))
                        break
            if context.get('bidi_context'):
                tree = await connection.command('browsingContext.getTree', {'maxDepth': 0})
                matched = next((item for item in tree.get('contexts', []) if item['context'] == context['bidi_context']), None)
                if not matched or matched.get('userContext') != user_context:
                    raise RuntimeError('Run context is closed or belongs to another Profile')
                if not context.get('user_context'):
                    context['user_context'] = user_context
                    with self.runtime.database.transaction(write=True) as c:
                        row = c.execute('SELECT input_json FROM agent_runs WHERE id=?', (run.id,)).fetchone()
                        current = json.loads(row['input_json'])
                        current['parameters']['browser_context']['user_context'] = user_context
                        c.execute('UPDATE agent_runs SET input_json=? WHERE id=?', (json.dumps(current), run.id))
            else:
                tree = await connection.command('browsingContext.getTree', {'maxDepth': 0})
                reference = next((item['context'] for item in tree.get('contexts', [])
                                  if item.get('userContext') == user_context), None)
                # A cold native Profile may have no content tab yet. Bootstrap
                # its first window in the existing BiDi host, never a process.
                create = {'type':'tab' if reference else 'window',
                          'userContext':user_context, 'background':True}
                if reference:create['referenceContext'] = reference
                created = await connection.command('browsingContext.create', create)
                created_tree = await connection.command('browsingContext.getTree', {'root': created['context'], 'maxDepth': 0})
                if not created_tree.get('contexts') or created_tree['contexts'][0].get('userContext') != user_context:
                    raise RuntimeError('Native browser created a context in the wrong Profile')
                context = {**context, 'bidi_context': created['context'], 'profile_key': profile_key, 'user_context': user_context,
                           'created_by_run': run.id}
                with self.runtime.database.transaction(write=True) as c:
                    row = c.execute('SELECT input_json FROM agent_runs WHERE id=?', (run.id,)).fetchone()
                    current = json.loads(row['input_json'])
                    prior = current['parameters'].get('browser_context') or {}
                    if prior.get('bidi_context'):
                        raise RuntimeError('Run context was already bound')
                    current['parameters']['browser_context'] = context
                    c.execute('UPDATE agent_runs SET input_json=? WHERE id=?', (json.dumps(current), run.id))
                for task in self.tasks.list(owner):
                    if task['run_id'] == run.id:
                        self.tasks.update(owner, task['id'], browser_context_json=json.dumps(context))
            page = BackgroundPage(connection, context['bidi_context'],
                interaction_mode=lambda url: 'natural' if str(parameters.get('caller_app_id', '')).endswith(':ai2apps.shopping-pro') or (parameters.get('caller_app_id') == 'ai2apps.intelligence' and (urlsplit(url).hostname or '') in ('x.com','www.x.com')) else self.interaction_mode(owner, url))
            from .processing_pool import InputLock
            if not hasattr(self,'input_locks'):self.input_locks={}
            page.input_lock=self.input_locks.setdefault((owner,profile_key),InputLock())
            page.owner = owner
            page.database = self.runtime.database
            page.profile_key = profile_key
            async def publish_search_progress(result):
                from .search_progress import publish
                with self.runtime.database.transaction() as c:
                    task=c.execute('SELECT id FROM browser_tasks WHERE owner=? AND run_id=?',(owner,run.id)).fetchone()
                if task:
                    publish(self.tasks,owner,task['id'],result)
            page.search_progress = publish_search_progress
            page.user_context = context.get('user_context')
            page.created_contexts.update(context.get('owned_contexts', {}))
            await page.validate_context()
            self.pages[run.id] = page
            return page
        except BaseException:
            await connection.close()
            raise

    async def release_page(self, run, page):
        """Every terminal WebAgent verifies cleanup; user-owned tabs are excluded."""
        parameters = run.input.get('parameters', {})
        context = parameters.get('browser_context') or {}
        if run.status.value not in ('completed', 'failed', 'cancelled'):
            return
        owned = set(page.created_contexts) | set(context.get('owned_contexts', {}))
        if context.get('created_by_run') == run.id:
            owned.add(context['bidi_context'])
        reason = str(context.get('retain_pages_reason') or '').strip()
        if context.get('reuse_scope'):
            from .task_tree import TaskTreeRepository
            scope=TaskTreeRepository(self.runtime.database).get(parameters['owner_user_id'],context['reuse_scope'])
            reason='供当前来源后续采集复用' if scope['status']=='running' and run.status.value=='completed' else ''
        tree = await page.connection.command('browsingContext.getTree', {'maxDepth': 0})
        # A retained result needs an explicit caller-provided purpose. It is not
        # inferred from webpage text or a model's generic completion message.
        for item in tree.get('contexts', []):
            if not reason and item['context'] in owned and item.get('userContext') == context.get('user_context'):
                with suppress(Exception):
                    await page.connection.command('browsingContext.close', {'context': item['context']})
        verified = await page.connection.command('browsingContext.getTree', {'maxDepth': 0})
        remaining = sorted(item['context'] for item in verified.get('contexts', []) if item['context'] in owned)
        result = {'state': 'retained' if reason else 'pending' if remaining else 'verified',
                  'remaining': remaining, 'reason': reason, 'checked_at': time.time()}
        self.save_page_state(run, page, cleanup=result)
        if remaining and not reason:
            raise RuntimeError('WebAgent page cleanup is incomplete; reconciliation will retry')
        await page.connection.close()

    def save_page_state(self, run, page, *, cleanup=None):
        with self.runtime.database.transaction(write=True) as c:
            row = c.execute('SELECT input_json FROM agent_runs WHERE id=?', (run.id,)).fetchone()
            current = json.loads(row['input_json'])
            context = current['parameters'].setdefault('browser_context', {})
            context['owned_contexts'] = dict(page.created_contexts)
            if cleanup is not None:
                context['cleanup'] = cleanup
            c.execute('UPDATE agent_runs SET input_json=? WHERE id=?', (json.dumps(current), run.id))
        parameters = current['parameters']
        task_id = parameters.get('browser_task_id')
        if task_id:
            values = {'browser_context_json': json.dumps(context)}
            if cleanup is not None:
                values['message'] = ('任务页面已关闭并核验' if cleanup['state'] == 'verified' else
                    '任务页面保留：'+cleanup['reason'] if cleanup['state'] == 'retained' else '任务已结束，页面清理待重试')
            self.tasks.update(parameters['owner_user_id'], task_id, **values)

    def dispatch_queue(self):
        from ai2apps.agent_builder.compiler import compile_source
        from ai2apps.agent_builder.service import create_ir_run
        for owner in self.tasks.owners():
            for _ in range(16):
                task = self.tasks.claim(owner, self.worker)
                if task is None:
                    break
                try:
                    if not task['session_id']:
                        raise ValueError('Task has no authenticated session; enqueue it again')
                    program, caller = self.tasks.program(owner, task['id'])
                    source = {'agent_type': 'web', 'site_scope': [], 'steps': [{
                        'name': 'call', 'desc': 'Run queued capability', 'operation': 'agent.call',
                        'arguments': {'agent_id': task['agent_id'],
                                      **({'capability': task['capability']} if task['capability'] else {}),
                                      'generation_id': task['generation_id'], 'parameters': task['input']},
                        'on': {'success': 'done', 'failed': 'failed'}}]}
                    compiled = None if program else compile_source(source)
                    if compiled is not None and not compiled.valid:
                        raise ValueError('Queued capability failed compilation preflight')
                    create_ir_run(self.runtime, session_id=task['session_id'], ir=program or compiled.ir,
                                  invocation_input=task['input'] if program else {}, browser_context={
                                      'profile_key': task['profile_key'],
                                      'parallel_limit': task.get('browser_context',{}).get('parallel_limit',1),
                                      'model_profile': task.get('browser_context', {}).get('model_profile', 'normal'),
                                      'retain_pages_reason': task.get('browser_context', {}).get('retain_pages_reason', ''),
                                      'reuse_scope': task.get('browser_context', {}).get('reuse_scope', '')},
                                  caller_app_id=caller, owner_user_id=owner, idempotency_key=task['id'])
                except Exception as error:
                    logger.exception('Could not start queued browser task %s', task['id'])
                    self.tasks.update(owner, task['id'], status='failed', message=str(error)[:1000])

    async def recover_cleanup(self):
        # Terminal runs can outlive Local. Reattach only to clean recorded IDs;
        # never create or navigate a replacement page during reconciliation.
        with self.runtime.database.transaction() as c:
            rows = c.execute("""SELECT id FROM agent_runs WHERE status IN ('completed','failed','cancelled')
                AND json_extract(input_json,'$.parameters.execution_owner')='local'
                AND (json_extract(input_json,'$.parameters.browser_context.created_by_run')=id
                     OR json_extract(input_json,'$.parameters.browser_context.owned_contexts') IS NOT NULL)
                AND (COALESCE(json_extract(input_json,'$.parameters.browser_context.cleanup.state'),'pending')='pending' OR (json_extract(input_json,'$.parameters.browser_context.cleanup.state')='retained' AND json_extract(input_json,'$.parameters.browser_context.reuse_scope') IN (SELECT id FROM task_nodes WHERE status!='running')))
                LIMIT 20""").fetchall()
        for row in rows:
            if row['id'] in self.pages or row['id'] in self._active:
                continue
            run = self.runtime.agents.get_run(row['id'])
            context = run.input['parameters']['browser_context']
            connection = await self.connection_factory().connect()
            try:
                page = BackgroundPage(connection, context['bidi_context'])
                page.created_contexts.update(context.get('owned_contexts', {}))
                await self.release_page(run, page)
            finally:
                await connection.close()

    def renew_leases(self):
        for owner in self.tasks.owners():
            for task in self.tasks.list(owner):
                if task['worker'] == self.worker and task['status'] in ('starting', 'running', 'waiting_input'):
                    self.tasks.update(owner, task['id'], lease_until=time.time() + 90)

    def pending(self):
        with self.runtime.database.transaction() as c:
            rows = c.execute("""SELECT i.id,i.run_id FROM agent_interactions i
                JOIN agent_runs r ON r.id=i.run_id
                WHERE i.status='pending' AND r.status='waiting_input'
                AND json_extract(i.request_json,'$.control')='browser_bidi_action'
                AND json_extract(r.input_json,'$.parameters.execution_owner')='local'
                ORDER BY i.created_at LIMIT 100""").fetchall()
        return [dict(row) for row in rows]

    def deliver_failure(self, run_id, interaction_id, *, reason, error=None):
        record=self.journal.lookup(interaction_id)
        evidence={'reason':reason,'message':'浏览器命令失败；已发送的操作可能生效，请先检查当前页面再决定恢复，勿盲目重复点击或提交。',
            'action_outcome_unknown':bool(record),'automatic_replay_allowed':False}
        if error is not None:
            evidence['error_type']=type(error).__name__
            if getattr(error,'method',None):
                evidence['method']=error.method
                evidence['message']='浏览器命令 '+error.method+' 未收到响应；请先检查页面结果，勿盲目重复点击或提交。'
            if getattr(error,'timeout',None):evidence['timeout_seconds']=error.timeout
            if getattr(error,'navigation_attempts',None):evidence['navigation_attempts']=error.navigation_attempts
        response={'outcome':'failed','evidence':evidence}
        if record:
            response=self.journal.report_failure(interaction_id,response)
        run=self.runtime.agents.get_run(run_id)
        status=getattr(getattr(run,'status',None),'value',None)
        if status in ('completed','failed','cancelled'):return
        self.runtime.agents.respond_interaction(run_id,interaction_id,response=response,response_id='local-browser:'+interaction_id)
        self.runtime.agent_runtime.wake()

    async def execute_interaction(self, item):
        run = self.runtime.agents.get_run(item['run_id'])
        interaction = next(value for value in self.runtime.agents.list_interactions(run.id) if value.id == item['id'])
        owner = run.input['parameters']['owner_user_id']
        page = None
        initial_contexts = None
        try:
            record = self.journal.lookup(interaction.id)
            if record and record['state'] == 'completed':
                context = run.input['parameters'].get('browser_context') or {}
                record, _ = self.journal.claim(run_id=run.id, interaction_id=interaction.id,
                    owner=owner, context_id=context.get('bidi_context'), request=interaction.request)
                self.runtime.agents.respond_interaction(run.id, interaction.id,
                    response=json.loads(record['response_json']), response_id='local-browser:' + interaction.id)
                self.runtime.agent_runtime.wake()
                return
            api_only = interaction.request.get('step', {}).get('operation') == 'search.api'
            if not api_only:
                page = await self.page_for(run)
                initial_contexts = {item['context'] for item in (await page.connection.command(
                    'browsingContext.getTree', {'maxDepth': 0})).get('contexts', [])}
            record, admitted = self.journal.claim(run_id=run.id, interaction_id=interaction.id,
                owner=owner, context_id=page.context_id if page else None, request=interaction.request)
            if not admitted:
                if record['state'] == 'completed':
                    response = json.loads(record['response_json'])
                else:
                    self.deliver_failure(run.id,interaction.id,reason='browser_action_outcome_unknown')
                    return
            else:
                response = await self.executor.execute(page, interaction.request, run)
                self.journal.complete(interaction.id, response)
            self.runtime.agents.respond_interaction(run.id, interaction.id, response=response,
                                                    response_id='local-browser:' + interaction.id)
            self.runtime.agent_runtime.wake()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # Feed the failure to the Agent's normal transitions. Never replay
            # the command merely because its response was lost.
            logger.exception('Background browser action failed for run %s',run.id)
            try:
                self.deliver_failure(run.id,interaction.id,
                    reason='browser_command_timeout' if isinstance(error,TimeoutError) else 'browser_command_failed',error=error)
            except Exception:
                logger.exception('Browser failure delivery failed for run %s',run.id)
                # Failure to deliver must also terminate visibly, not wait forever.
                self.runtime.agent_runtime.cancel(run.id)
                for task in self.tasks.list(owner):
                    if task['run_id']==run.id:
                        self.tasks.update(owner,task['id'],status='cancelling',message='浏览器命令失败且无法交回 Agent，正在结束任务。')
        finally:
            if page is not None:
                if initial_contexts is not None:
                    with suppress(Exception):
                        tree = (await page.connection.command('browsingContext.getTree', {'maxDepth': 0})).get('contexts', [])
                        related = {page.context_id, *page.created_contexts}
                        while True:
                            added = {i['context']: i['originalOpener'] for i in tree
                                     if i['context'] not in initial_contexts and i['context'] not in related
                                     and i.get('originalOpener') in related}
                            if not added:
                                break
                            page.created_contexts.update(added)
                            related.update(added)
                self.save_page_state(run, page)

    async def _loop(self):
        async with self.runtime.notifications.subscribe() as wake:
            last_cleanup = 0
            while not self._stop.is_set():
                for key, task in list(self._active.items()):
                    if task.done():
                        with suppress(Exception): task.result()
                        del self._active[key]
                try:
                    self.renew_leases()
                    self.dispatch_queue()
                    for item in self.pending():
                        if item['run_id'] not in self._active:
                            self._active[item['run_id']] = asyncio.create_task(self.execute_interaction(item))
                    for run_id, page in list(self.pages.items()):
                        run = self.runtime.agents.get_run(run_id)
                        if run.status.value in ('completed', 'failed', 'cancelled') and run_id not in self._active:
                            await self.release_page(run, page)
                            del self.pages[run_id]
                    if time.monotonic() - last_cleanup > 15:
                        last_cleanup = time.monotonic()
                        await self.recover_cleanup()
                except Exception:
                    logger.exception('Background browser reconciliation failed; retrying reconciliation only')
                with suppress(TimeoutError):
                    await asyncio.wait_for(wake.get(), timeout=1)
