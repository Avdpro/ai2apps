"""Durable consumer execution for trusted Hook registrations, not a model loop."""
from __future__ import annotations
import asyncio
from contextlib import contextmanager
from dataclasses import replace
import json
import logging
import time
from ai2apps.services import ToolCallContext, ToolGatewayError
from ai2apps.apps.access import has_app_capability
from uuid import uuid4
from ai2apps.system_tasks.service import TaskHandler
from ai2apps.system_tasks.sessions import execution_principal, execution_session
from .causality import current_delivery, cause_scope
from .hooks import HookError, digest

TERMINAL={'completed','partial','failed','cancelled','interrupted','timed_out'}


class HookExecution:
    def __init__(self,runtime):
        self.runtime=runtime;self.hooks=runtime.event_hooks;self.db=runtime.database
        self.task=None
        logging.getLogger(__name__).info('Hook execution loaded; source=%s',__file__)
        runtime.tools.execution_guards.append(self)
        runtime.app_capability_router.execution_guards.append(self)

    def register(self,consumer):
        if consumer.execute is None:return
        async def execute(ctx):
            delivery=ctx.payload['delivery_id']
            try:
                work=self.work(delivery)
                work.check()
                with self.db.transaction(write=True) as db:
                    db.execute("UPDATE hook_executions SET state='running',started=COALESCE(started,?),updated=? WHERE delivery_id=?",(time.time(),time.time(),delivery))
                with cause_scope(work.cause,delivery):
                    result=await consumer.execute(work,ctx)
                work.check()
                self.settle(delivery,'needs_user' if result and result.get('status')=='needs_user' else 'succeeded',result)
                return result
            except asyncio.CancelledError:
                if not self.runtime.system_tasks.stopping:self.settle(delivery,'cancelled',error='cancelled')
                raise
            except Exception as exc:
                from .actions import OutcomeUnknown
                with self.db.transaction(write=True) as db:
                    db.execute("UPDATE hook_action_steps SET state='outcome_unknown',updated=? WHERE delivery_id=? AND state='executing'",(time.time(),delivery))
                    states={r[0]:r[1] for r in db.execute('SELECT state,count(*) FROM hook_action_steps WHERE delivery_id=? GROUP BY state',(delivery,))}
                state='outcome_unknown' if isinstance(exc,OutcomeUnknown) or states.get('outcome_unknown') else 'partial' if states.get('succeeded') else 'failed'
                self.settle(delivery,state,result={'completed_action_count':states.get('succeeded',0)},error=str(exc)[:500]);raise
        def authorize(actor,payload):
            work=self.work(payload['delivery_id'])
            if work.actor!=actor:raise PermissionError('Hook task owner mismatch')
        async def cancel(ctx,force):
            with self.db.transaction() as db:
                runs=[r[0] for r in db.execute('SELECT run_id FROM hook_run_bindings WHERE delivery_id=?',(ctx.payload['delivery_id'],))]
            for rid in runs:
                run=self.runtime.agents.get_run(rid)
                if run.status.value not in TERMINAL:self.runtime.agents.request_cancel(rid);self.runtime.agent_runtime.wake();return False
            self.settle(ctx.payload['delivery_id'],'cancelled',error='cancelled')
            return True
        self.runtime.system_tasks.register('hook:'+consumer.id,TaskHandler(consumer.app_id,execute,cancel,authorize,resumable=True))

    def work(self,delivery):
        with self.db.transaction() as db:
            row=db.execute('''SELECT d.*,r.owner,r.status AS rule_status,v.spec_json FROM hook_deliveries d
                JOIN hook_rules r ON r.id=d.rule_id JOIN hook_rule_revisions v ON v.rule_id=d.rule_id AND v.revision=d.rule_revision
                WHERE d.id=?''',(delivery,)).fetchone()
        if row is None:raise PermissionError('Hook delivery unavailable')
        return HookWork(self,dict(row))

    def settle(self,delivery,state,result=None,error=None):
        value=json.dumps(result,ensure_ascii=False,allow_nan=False) if result is not None else None
        if value and len(value.encode())>96000:raise ValueError('Hook result too large')
        with self.db.transaction(write=True) as db:
            db.execute('UPDATE hook_executions SET state=?,result_json=?,error=?,updated=? WHERE delivery_id=?',
                       (state,value,error,time.time(),delivery))

    async def startup(self):
        if self.task is None:self.task=asyncio.create_task(self.loop(),name='hook-execution-admission')

    async def shutdown(self):
        if self.task:
            self.task.cancel();await asyncio.gather(self.task,return_exceptions=True);self.task=None

    async def loop(self):
        while True:
            worker=asyncio.create_task(asyncio.to_thread(self.admit))
            try:await asyncio.shield(worker)
            except asyncio.CancelledError:
                await asyncio.gather(worker,return_exceptions=True);raise
            except Exception:logging.getLogger(__name__).exception('Hook admission failed')
            await asyncio.sleep(1)

    def admit(self):
        with self.db.transaction() as db:
            rows=[r[0] for r in db.execute('''SELECT d.id FROM hook_deliveries d JOIN hook_rule_revisions v ON v.rule_id=d.rule_id AND v.revision=d.rule_revision
                LEFT JOIN hook_executions e ON e.delivery_id=d.id
                WHERE json_extract(v.spec_json,'$.mode')='background' AND (e.delivery_id IS NULL OR e.state='admitting') ORDER BY d.event_sequence LIMIT 50''')]
        for delivery in rows:
            try:
                work=self.work(delivery)
                if work.spec.get('mode')!='background':continue
                work.check()
                consumer=self.hooks.consumers[work.spec['consumer']['registration']]
                if consumer.execute is None:raise ValueError('Consumer has no registered execution entry')
                with self.db.transaction(write=True) as db:
                    old=db.execute('SELECT * FROM hook_executions WHERE delivery_id=?',(delivery,)).fetchone()
                    if old is not None and old['state']!='admitting':continue
                    prior=db.execute('''SELECT 1 FROM hook_deliveries d LEFT JOIN hook_executions e ON e.delivery_id=d.id
                        WHERE d.rule_id=? AND d.rule_revision=? AND d.event_sequence<?
                        AND (e.state IS NULL OR e.state IN ('admitting','queued','running','needs_user','partial','outcome_unknown')) LIMIT 1''',
                        (work.row['rule_id'],work.row['rule_revision'],work.row['event_sequence'])).fetchone()
                    if prior:continue

                    if old is None:
                        root=work.parent
                        repeated=db.execute('SELECT 1 FROM hook_root_claims WHERE owner=? AND root_id=? AND rule_id=?',(work.actor,root['root_id'],work.row['rule_id'])).fetchone()
                        count=db.execute('SELECT count(*) FROM hook_root_claims WHERE owner=? AND root_id=?',(work.actor,root['root_id'])).fetchone()[0]
                        reason='rule_reentry' if repeated or work.row['rule_id'] in root['ancestry'] else 'cause_budget' if root['depth']>=8 or count>=20 else None
                        db.execute("INSERT INTO hook_executions(delivery_id,state,task_id,result_json,error,created,updated) VALUES(?,?,NULL,NULL,?,?,?)",(delivery,'suppressed' if reason else 'admitting',reason,time.time(),time.time()))
                        if reason:continue
                        db.execute('INSERT INTO hook_root_claims VALUES(?,?,?,?)',(work.actor,root['root_id'],work.row['rule_id'],delivery))
                task=self.runtime.system_tasks.submit(work.actor,consumer.app_id,'hook:'+consumer.id,'Hook · '+consumer.kind,
                    {'delivery_id':delivery},receipt_key='hook:'+delivery)
                with self.db.transaction(write=True) as db:
                    db.execute("UPDATE hook_executions SET task_id=?,state=CASE WHEN state='admitting' THEN 'queued' ELSE state END,updated=? WHERE delivery_id=?",(task['id'],time.time(),delivery))
                if task['status'] in TERMINAL:
                    self.settle(delivery,'succeeded' if task['status']=='completed' else 'needs_user' if task['status']=='partial' else task['status'],task.get('result'),task.get('message') or None)
            except Exception as exc:
                # Read-only facts remain; an invalid delegation never becomes an effectful retry.
                with self.db.transaction(write=True) as db:
                    db.execute("INSERT OR IGNORE INTO hook_executions(delivery_id,state,task_id,result_json,error,created,updated) VALUES(?,'failed',NULL,NULL,?,?,?)",(delivery,str(exc)[:500],time.time(),time.time()))
                    db.execute("UPDATE hook_executions SET state='failed',error=? WHERE delivery_id=? AND state='admitting'",(str(exc)[:500],delivery))

    def binding(self,context):
        delivery=current_delivery.get()
        if not delivery and context.trace_id:
            with self.db.transaction() as db:
                row=db.execute('SELECT delivery_id FROM hook_run_bindings WHERE run_id=?',(context.trace_id,)).fetchone()
            if row:delivery=row[0]
        return self.work(delivery) if delivery else None

    def visible(self,context,name):
        work=self.binding(context)
        return work is None or name=='agent.ask_user' or bool(work.detail_binding and name==work.detail_binding[0])

    def authorize(self,context,name,args):
        work=self.binding(context)
        if work is None:return
        work.check()
        if context.actor_user_id!=work.actor or context.installation_id!=work.plan['installation_id']:
            raise ToolGatewayError('hook_scope_denied','Hook execution identity mismatch')
        if name=='agent.ask_user':return
        payload={k:v for k,v in args.items() if k not in ('provider','parameters')};payload.update(args.get('parameters',{}))
        if not work.detail_binding or name!=work.detail_binding[0] or payload!={'event_id':work.row['event_id']}:
            raise ToolGatewayError('hook_effect_denied','This delegation permits only its exact event detail read')
        if args.get('provider',work.detail_binding[1])!=work.detail_binding[1]:
            raise ToolGatewayError('hook_scope_denied','Hook provider cannot be changed')
        provider=self.runtime.app_capability_router.providers.get(work.detail_binding[1])
        if provider is None or provider.version!=work.detail_binding[2]:raise PermissionError('Hook details provider changed')

    @contextmanager
    def scope(self,context):
        work=self.binding(context)
        if work is None:yield;return
        # Gateway and direct Router share the same receipt. Nested policy checks
        # never debit a second time for one invocation.
        with self.db.transaction(write=True) as db:
            step='tool:'+(context.invocation_id or uuid4().hex)
            count=db.execute("SELECT count(*) FROM hook_steps WHERE delivery_id=? AND step LIKE 'tool:%'",(work.row['id'],)).fetchone()[0]
            old=db.execute('SELECT 1 FROM hook_steps WHERE delivery_id=? AND step=?',(work.row['id'],step)).fetchone()
            if not old and count>=work.plan['policy']['max_tool_calls']:raise PermissionError('Hook tool budget exhausted')
            db.execute("INSERT OR IGNORE INTO hook_steps VALUES(?,?,?,'null')",(work.row['id'],step,''))
        with cause_scope(work.cause,work.row['id']):yield


class HookWork:
    def __init__(self,service,row):
        self.service,self.runtime,self.row=service,service.runtime,row
        self.actor=row['owner'];self.spec=json.loads(row['spec_json'])
        self.plan=self.spec.get('execution',{})
        self.event=self.runtime.business_events.read(self.actor,row['event_id'])
        parent=self.event.get('cause')
        if not parent or parent.get('unknown'):raise PermissionError('Unknown event causality cannot activate a consumer')
        self.cause={**parent,'depth':parent['depth']+1,'ancestry':[*parent['ancestry'],row['rule_id']]}
        # Parent ancestry is used by admission; the child envelope is used for newly published facts.
        self.parent=parent
        definition=self.runtime.business_events.types[self.spec['event_type']]
        self.detail_binding=tuple(self.plan['details_binding']) if self.plan.get('details_binding') else None

    def check(self):
        with self.service.db.transaction() as db:
            rule=db.execute('SELECT status,revision FROM hook_rules WHERE id=?',(self.row['rule_id'],)).fetchone()
        if not rule or rule['status']!='active' or rule['revision']!=self.row['rule_revision']:
            raise PermissionError('Hook delegation was paused, edited or revoked')
        self.runtime.event_hooks._validate(self.actor,self.spec)
        principal=execution_principal(self.runtime,self.actor)
        consumer=self.runtime.event_hooks.consumers[self.spec['consumer']['registration']]
        if not all(has_app_capability(principal,c) for c in consumer.background_capabilities):raise PermissionError('Background authority revoked')
        if self.plan.get('installation_id')!=principal.installation_id or self.plan.get('expires_at',0)<=self.runtime.event_hooks.clock():
            raise PermissionError('Background delegation expired or installation changed')
        consumer=self.runtime.event_hooks.consumers[self.spec['consumer']['registration']]
        required=consumer.needs_details(self.plan['settings']) if consumer.needs_details else True
        definition=self.runtime.business_events.types[self.spec['event_type']]
        if (required and tuple(definition.details or ())!=self.detail_binding) or (not required and self.detail_binding is not None):
            raise PermissionError('Event detail binding changed')
        if self.detail_binding:
            router=self.runtime.app_capability_router
            provider=router.providers.get(self.detail_binding[1])
            if (provider is None or (provider.capability,provider.id,provider.version)!=tuple(self.detail_binding)
                    or provider.id in router.disabled(self.actor,principal.installation_id)):
                raise PermissionError('Event detail Provider changed or was disabled')
            if not self.runtime.services.get_tool(self.detail_binding[0]).enabled:raise PermissionError('Event detail Tool disabled')
        if time.time()-self.row['created']>self.plan['policy']['max_seconds']:
            raise PermissionError('Hook execution time budget exhausted')
        if self.plan.get('actions'):
            from datetime import datetime,timezone
            age=datetime.now(timezone.utc).timestamp()-datetime.fromisoformat(self.event['occurred_at'].replace('Z','+00:00')).timestamp()
            if age< -60 or age>86400:raise PermissionError('Effectful event is outside its 24-hour freshness window')
        return principal

    async def details(self):
        principal=self.check();key='details'
        if not self.detail_binding:raise PermissionError('This delegation does not allow detail reads')
        with self.service.db.transaction() as db:
            old=db.execute('SELECT result_json FROM hook_steps WHERE delivery_id=? AND step=?',(self.row['id'],key)).fetchone()
        if old:return json.loads(old[0])
        consumer=self.runtime.event_hooks.consumers[self.spec['consumer']['registration']]
        session=consumer.session(self) if consumer.session else execution_session(self.runtime,self.actor,consumer.app_id)
        context=replace(ToolCallContext.from_principal(principal,caller_id='hook:details',session_id=session),pinned_provider=tuple(self.detail_binding))
        output=await self.runtime.tools.execute(self.detail_binding[0],{'event_id':self.row['event_id'],'provider':self.detail_binding[1]},context=context)
        body=json.dumps(output.output,ensure_ascii=False,allow_nan=False)
        if len(body.encode())>48000:raise ValueError('Event details exceed approved context bound')
        with self.service.db.transaction(write=True) as db:
            db.execute('INSERT OR IGNORE INTO hook_steps VALUES(?,?,?,?)',(self.row['id'],key,digest(self.detail_binding),body))
        return json.loads(body)

    def report(self,value):
        self.check();body=json.dumps(value,ensure_ascii=False,allow_nan=False)
        if len(body.encode())>64000:raise ValueError('Consumer report too large')
        with self.service.db.transaction(write=True) as db:
            old=db.execute('SELECT result_json FROM hook_reports WHERE delivery_id=?',(self.row['id'],)).fetchone()
            if old:
                if old[0]!=body:raise ValueError('Consumer report receipt conflict')
            else:db.execute('INSERT INTO hook_reports VALUES(?,?,?,?,?)',(self.row['id'],self.actor,json.dumps(self.spec['consumer']),body,time.time()))
        return value
