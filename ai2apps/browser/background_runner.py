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
        self._active = {}
        self._stop = asyncio.Event()
        self._loop_task = None
        self.worker = 'local-background'

    async def startup(self):
        if self._loop_task is not None:
            return
        for item in self.journal.recover():
            with suppress(Exception):
                self.runtime.agent_runtime.pause(item['run_id'])
                for owner in self.tasks.owners():
                    for task in self.tasks.list(owner):
                        if task['run_id'] == item['run_id']:
                            self.tasks.update(owner, task['id'], status='interrupted', message='Local 已重启，上一操作结果待确认，请检查页面后重新运行。')
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
            if context.get('bidi_context'):
                tree = await connection.command('browsingContext.getTree', {'maxDepth': 0})
                matched = next((item for item in tree.get('contexts', []) if item['context'] == context['bidi_context']), None)
                if not matched or matched.get('userContext') != user_context:
                    raise RuntimeError('Run context is closed or belongs to another Profile')
            else:
                tree = await connection.command('browsingContext.getTree', {'maxDepth': 0})
                reference = next((item['context'] for item in tree.get('contexts', [])
                                  if item.get('userContext') == user_context), None)
                if not reference:
                    raise RuntimeError('Native Profile host has no bound browser context')
                created = await connection.command('browsingContext.create', {
                    'type': 'tab', 'referenceContext': reference,
                    'userContext': user_context, 'background': True})
                created_tree = await connection.command('browsingContext.getTree', {'root': created['context'], 'maxDepth': 0})
                if not created_tree.get('contexts') or created_tree['contexts'][0].get('userContext') != user_context:
                    raise RuntimeError('Native browser created a context in the wrong Profile')
                context = {'bidi_context': created['context'], 'profile_key': profile_key, 'user_context': user_context}
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
                interaction_mode=lambda url: self.interaction_mode(owner, url))
            page.owner = owner
            await page.validate_context()
            self.pages[run.id] = page
            return page
        except BaseException:
            await connection.close()
            raise

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
                                  invocation_input=task['input'] if program else {}, browser_context={'profile_key': task['profile_key']},
                                  caller_app_id=caller, owner_user_id=owner, idempotency_key=task['id'])
                except Exception as error:
                    logger.exception('Could not start queued browser task %s', task['id'])
                    self.tasks.update(owner, task['id'], status='failed', message=str(error)[:1000])

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

    async def execute_interaction(self, item):
        run = self.runtime.agents.get_run(item['run_id'])
        interaction = next(value for value in self.runtime.agents.list_interactions(run.id) if value.id == item['id'])
        owner = run.input['parameters']['owner_user_id']
        page = None
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
            page = await self.page_for(run)
            record, admitted = self.journal.claim(run_id=run.id, interaction_id=interaction.id,
                owner=owner, context_id=page.context_id, request=interaction.request)
            if not admitted:
                if record['state'] == 'completed':
                    response = json.loads(record['response_json'])
                else:
                    self.runtime.agent_runtime.pause(run.id)
                    return
            else:
                response = await self.executor.execute(page, interaction.request, run)
                self.journal.complete(interaction.id, response)
            self.runtime.agents.respond_interaction(run.id, interaction.id, response=response,
                                                    response_id='local-browser:' + interaction.id)
            self.runtime.agent_runtime.wake()
        except asyncio.CancelledError:
            raise
        except Exception:
            # No automatic retry after a command may have reached the browser.
            logger.exception('Background browser action interrupted for run %s', run.id)
            with suppress(Exception):
                self.runtime.agent_runtime.pause(run.id)
            for task in self.tasks.list(owner):
                if task['run_id'] == run.id:
                    self.tasks.update(owner, task['id'], status='interrupted',
                        message='浏览器执行中断，请检查原页面与操作结果后继续。')

    async def _loop(self):
        async with self.runtime.notifications.subscribe() as wake:
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
                            # Context remains available for the result/assistance UI;
                            # detaching never closes unrelated tabs or native session.
                            await page.connection.close()
                            del self.pages[run_id]
                except Exception:
                    logger.exception('Background browser reconciliation failed; retrying reconciliation only')
                with suppress(TimeoutError):
                    await asyncio.wait_for(wake.get(), timeout=1)
