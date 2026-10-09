"""System-owned Codex sessions and interactive requests, independent of Todo."""
import asyncio
import inspect
import uuid
from pathlib import Path
from datetime import datetime, timezone
from .transport import CodexDesktop
from .result_report import request_report, parse_report, turn_report


def now_text():
    return datetime.now(timezone.utc).isoformat()


async def _emit_update(callback, status, **fields):
    """Keep synchronous persistence callbacks off the server event loop."""
    if inspect.iscoroutinefunction(callback):
        await callback(status, **fields)
    else:
        write = asyncio.create_task(asyncio.to_thread(callback, status, **fields))
        try:
            result = await asyncio.shield(write)
        except asyncio.CancelledError:
            # A thread cannot be cancelled. Finish this write before the caller
            # persists its cancelled state, preserving update ordering.
            await write
            raise
        if inspect.isawaitable(result):
            await result


class CodexManager:
    def __init__(self):
        self.desktop_requests = {}
        self.desktop_threads = set()
        self.jobs = set()
        self.stopping = False

    async def projects(self):
        from .projects import saved_projects
        saved = await asyncio.to_thread(saved_projects)
        if saved:
            return {'data':saved, 'truncated':False, 'source':'desktop'}
        async with CodexDesktop() as client:
            projects = {}; cursor = None
            for _ in range(20):
                page = await client.threads(cursor=cursor)
                for thread in page['data']:
                    cwd = thread.get('cwd')
                    if cwd: projects[cwd] = {'path':cwd, 'name':Path(cwd).name}
                cursor = page.get('nextCursor')
                if not cursor: break
            return {'data':list(projects.values()), 'truncated':bool(cursor), 'source':'conversations'}

    async def threads(self, cwd=None, cursor=None):
        async with CodexDesktop() as client:
            return await client.threads(cwd, cursor)

    async def shutdown(self):
        self.stopping = True
        jobs = list(self.jobs)
        for job in jobs: job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)

    async def execute(self, id, owner, **options):
        """Await one turn; caller owns scheduling, authorization and durable records.

        Cancellation interrupts the turn before releasing its conversation lock.
        Callbacks must not block; on_thread is awaited before starting a new turn.
        """
        if self.stopping: raise ValueError('Codex service is stopping')
        cwd = Path(options['cwd'])
        if not cwd.is_absolute() or not cwd.is_dir():
            raise ValueError('Choose an existing local project directory')
        job = asyncio.current_task()
        self.jobs.add(job)
        try:
            return await self._execute(id, owner, **options)
        finally:
            self.jobs.discard(job)

    async def _execute(self, id, owner, *, cwd, title, prompt, thread_id=None, model="", writable_roots=(), on_update, on_thread):
        from .transport import CodexDesktop
        turn_id = None
        acquired = False
        subscribed = False
        finished = False
        output = ''
        last_output_update = 0.0
        last_agent_message = ''
        if thread_id:
            if thread_id in self.desktop_threads:
                raise ValueError('This Codex conversation is already running in AI2Apps')
            self.desktop_threads.add(thread_id)
            try:
                async with CodexDesktop() as client:
                    info = await client.call('thread/read', {'threadId':thread_id, 'includeTurns':False})
                    if Path(info['thread'].get('cwd','')).resolve() != Path(cwd).resolve():
                        raise ValueError('The selected conversation belongs to another directory')
                return await self.native_run(id, thread_id, prompt, model, on_update)
            finally:
                self.desktop_threads.discard(thread_id)
        prompt = request_report(prompt, id)
        async with CodexDesktop() as client:
            try:
                result = await client.call('thread/start', {'cwd':cwd, 'approvalPolicy':'on-request', 'sandbox':'workspace-write'})
                thread_id = result['thread']['id']
                subscribed = True
                self.desktop_threads.add(thread_id); acquired = True
                await client.call('thread/name/set', {'threadId':thread_id, 'name':title})
                await on_thread(thread_id)
                await _emit_update(on_update, 'running', codex_thread_id=thread_id, log='Connected to Codex conversation')
                params = {'threadId':thread_id, 'cwd':cwd, 'approvalPolicy':'on-request', 'input':[{'type':'text','text':prompt}]}
                params['sandboxPolicy'] = {'type':'workspaceWrite','writableRoots':[cwd, *map(str, writable_roots)],'networkAccess':False,'excludeTmpdirEnvVar':False,'excludeSlashTmp':False}
                if model: params['model']=model
                result = await client.call('turn/start', params)
                turn_id = result['turn']['id']
                await _emit_update(on_update, 'running', codex_turn_id=turn_id)
                while True:
                    message = await client.events.get()
                    method, values = message.get('method',''), message.get('params',{})
                    if method == 'connection/closed': raise ValueError('Codex connection closed before completion')
                    if values.get('threadId') and values['threadId'] != thread_id: continue
                    if 'id' in message:
                        supported = method in ('item/commandExecution/requestApproval','item/fileChange/requestApproval','item/tool/requestUserInput')
                        if not supported:
                            await client.send({'id':message['id'],'error':{'code':-32601,'message':'Unsupported request in AI2Apps; stop and continue in Codex Desktop'}})
                            raise ValueError('Codex needs an unsupported interaction: '+method)
                        token = uuid.uuid4().hex
                        future = asyncio.get_running_loop().create_future()
                        self.desktop_requests[token] = (owner, id, method, values, future)
                        await _emit_update(on_update, 'waiting_input' if method.endswith('requestUserInput') else 'waiting_capability', output=output, desktop_request={'token':token,'method':method,'params':values})
                        try: response = await future
                        finally: self.desktop_requests.pop(token,None)
                        await client.send({'id':message['id'],'result':response})
                        await _emit_update(on_update, 'running', desktop_request=None)
                    elif method in ('item/agentMessage/delta','item/commandExecution/outputDelta'):
                        output = (output + str(values.get('delta','')))[-100000:]
                        timestamp = asyncio.get_running_loop().time()
                        if timestamp - last_output_update >= 0.25:
                            await _emit_update(on_update, 'running', output=output)
                            last_output_update = asyncio.get_running_loop().time()
                    elif method in ('item/started','item/completed'):
                        item = values.get('item',{})
                        if method == 'item/completed' and item.get('type') == 'agentMessage':
                            last_agent_message = item.get('text','')
                        await _emit_update(on_update, 'running', output=output, log=str(item.get('command') or item.get('type') or method)[:2000])
                    elif method == 'turn/completed' and values.get('turn',{}).get('id') == turn_id:
                        finished = True
                        turn = values['turn']; status = turn.get('status')
                        await _emit_update(on_update, 'ended' if status=='completed' else 'cancelled' if status=='interrupted' else 'failed',
                            output=output, error=turn.get('error'), log='Codex turn ended; review results.', desktop_request=None, finished_at=now_text(),
                            **parse_report(last_agent_message, id))
                        return
            finally:
                if turn_id and not finished:
                    try: await client.call('turn/interrupt', {'threadId':thread_id,'turnId':turn_id}, timeout=5)
                    except Exception: pass
                if subscribed:
                    try: await client.call('thread/unsubscribe', {'threadId':thread_id}, timeout=5)
                    except Exception: pass
                if acquired:
                    self.desktop_threads.discard(thread_id)

    async def native_run(self, id, thread_id, prompt, model, on_update):
        from .native_queue import enqueue, DeliveryRejected
        marker = f'[AI2Apps run:{id}]'
        # Write intent before spawning the CLI: restart must never blindly resend.
        await _emit_update(on_update, 'running', desktop_native=True,
            codex_thread_id=thread_id, native_marker=marker, native_delivery='pending',
            log='Preparing delivery to Codex Desktop')
        try:
            message_id = await enqueue(thread_id, marker+'\n'+request_report(prompt, id), model)
        except asyncio.CancelledError:
            raise
        except DeliveryRejected as error:
            await _emit_update(on_update, 'failed', native_delivery='rejected', error=str(error),
                log='Codex Desktop rejected delivery', finished_at=now_text())
            return
        except Exception as error:
            await _emit_update(on_update, 'waiting_input', native_delivery='unknown',
                error=str(error), log='Desktop delivery is unconfirmed; checking for receipt. Do not resend automatically.')
        else:
            await _emit_update(on_update, 'queued', native_delivery='queued',
                native_message_id=message_id, log='Queued in Codex Desktop; waiting for this message to start')
        await self.watch_native(thread_id, marker, on_update)

    async def resume_native(self, thread_id, marker, on_update):
        job = asyncio.current_task()
        self.jobs.add(job)
        self.desktop_threads.add(thread_id)
        try:
            await self.watch_native(thread_id, marker, on_update)
        finally:
            self.jobs.discard(job)
            self.desktop_threads.discard(thread_id)

    async def watch_native(self, thread_id, marker, on_update):
        from .native_queue import find_turn, progress
        turn_id = None
        while True:
            try:
                async with CodexDesktop() as client:
                    while True:
                        turn = await find_turn(client, thread_id, marker, turn_id)
                        if turn:
                            turn_id = turn['id']
                            status, output, step = progress(turn)
                            fields = dict(codex_turn_id=turn_id, native_delivery='received',
                                          output=output, log=step, error=turn.get('error'))
                            if status in ('ended','cancelled','failed'):
                                fields['finished_at']=now_text()
                                report_id = marker.removeprefix('[AI2Apps run:').removesuffix(']')
                                fields.update(turn_report(turn, report_id))
                            await _emit_update(on_update, status, **fields)
                            if status in ('ended','cancelled','failed'): return
                        await asyncio.sleep(3)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                await _emit_update(on_update, 'waiting_input',
                    log='Desktop monitoring disconnected; reconnecting. Execution may continue in Desktop.',
                    error=str(error))
                await asyncio.sleep(5)

    def reply(self, owner, token, decision=None, answers=None):
        request = self.desktop_requests.get(token)
        if not request or request[0] != owner: raise ValueError('This request is no longer pending')
        _, _, method, params, future = request
        if future.done(): raise ValueError('Request already answered')
        if method.endswith('requestUserInput'):
            expected = {q['id'] for q in params.get('questions',[])}
            if not answers or set(answers) != expected: raise ValueError('Answer each question')
            result = {'answers':{k:{'answers':[v]} for k,v in answers.items()}}
        else:
            if decision not in ('approve','deny'): raise ValueError('Choose approve or deny')
            result = {'decision':'accept' if decision=='approve' else 'decline'}
        future.set_result(result)
        return {'ok':True}
