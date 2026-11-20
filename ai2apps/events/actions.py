"""Trusted effect adapters with immutable plans and durable per-step receipts.

Models provide evidence, never action registrations or authority. Owners implement
validation, business idempotency and actual success receipts. Unknown effects are
never retried automatically, including after a Local restart.
"""
from dataclasses import dataclass
import asyncio
import json
import time
import logging
from typing import Callable
from .hooks import digest


class OutcomeUnknown(RuntimeError):pass

@dataclass(frozen=True)
class HookAction:
    id: str
    version: str
    title: str
    prepare: Callable
    execute: Callable
    recoverable: bool = False


class HookActions:
    def __init__(self,runtime):
        self.runtime=runtime;self.db=runtime.database;self.types={}
        logging.getLogger(__name__).info('Hook effect registry loaded; source=%s',__file__)

    def register(self,action):
        if action.id in self.types:raise ValueError('Duplicate Hook action')
        self.types[action.id]=action
        logging.getLogger(__name__).info('Hook action registered; registration=%s source=%s',action.id,action.execute.__code__.co_filename)

    def catalog(self):
        return [{'registration':a.id,'version':a.version,'title':a.title,'recoverable':a.recoverable} for a in self.types.values()]

    def prepare(self,actor,values):
        if not isinstance(values,list) or len(values)>4:raise ValueError('At most four explicitly approved actions')
        result=[]
        for value in values:
            if not isinstance(value,dict) or set(value)-{'registration','version','arguments'}:raise ValueError('Invalid action declaration')
            action=self.types.get(value.get('registration'))
            if action is None or value.get('version',action.version)!=action.version:raise PermissionError('Hook action unavailable or changed')
            result.append({'registration':action.id,'version':action.version,'arguments':action.prepare(actor,value.get('arguments',{}))})
        return result

    async def execute(self,work,plans,evidence,*,skip=False):
        if plans!=work.plan.get('actions',[]):raise PermissionError('Action plan is outside this delegation')
        results=[]
        for number,plan in enumerate(plans):
            work.check()
            if self.prepare(work.actor,[plan])!=[plan]:raise PermissionError('Action authorization changed')
            key='action:'+str(number);signature=digest(plan);action=self.types[plan['registration']]
            with self.db.transaction(write=True) as db:
                old=db.execute('SELECT * FROM hook_action_steps WHERE delivery_id=? AND step=?',(work.row['id'],key)).fetchone()
                if old:
                    if old['signature']!=signature:raise PermissionError('Frozen action receipt conflict')
                    if old['state'] in ('succeeded','skipped'):
                        results.append(json.loads(old['result_json']));continue
                    if old['state']=='outcome_unknown' or not action.recoverable:
                        db.execute("UPDATE hook_action_steps SET state='outcome_unknown',updated=? WHERE delivery_id=? AND step=?",(time.time(),work.row['id'],key))
                        unknown=True
                    else:unknown=False
                else:
                    unknown=False
                    db.execute('INSERT INTO hook_action_steps VALUES(?,?,?,?,?,?,NULL,NULL,?,?)',
                        (work.row['id'],key,signature,plan['registration'],plan['version'],'executing',time.time(),time.time()))
                if not unknown:
                    db.execute("UPDATE hook_action_steps SET state='executing',error=NULL,updated=? WHERE delivery_id=? AND step=?",(time.time(),work.row['id'],key))
            if unknown:raise OutcomeUnknown('An action has an uncertain result; verify its original receipt before continuing')
            try:
                work.check()
                if skip:value={'status':'skipped','reason':'condition_not_met'}
                else:
                    value=await action.execute(work,plan['arguments'],evidence,'hook:'+work.row['id']+':'+key)
                    if not isinstance(value,dict) or not isinstance(value.get('receipt_id'),str):raise ValueError('Owner action must return its actual persistent receipt')
                body=json.dumps(value,ensure_ascii=False,allow_nan=False)
                if len(body.encode())>20000:raise ValueError('Action receipt too large')
                with self.db.transaction(write=True) as db:
                    db.execute('UPDATE hook_action_steps SET state=?,result_json=?,updated=? WHERE delivery_id=? AND step=?',
                        ('skipped' if skip else 'succeeded',body,time.time(),work.row['id'],key))
                results.append(value)
            except BaseException as exc:
                # A safe adapter can reconcile via its original operation key.
                # No adapter may receive a new key to hide an uncertain effect.
                state='interrupted' if isinstance(exc,asyncio.CancelledError) and action.recoverable else 'failed' if action.recoverable else 'outcome_unknown'
                with self.db.transaction(write=True) as db:
                    db.execute('UPDATE hook_action_steps SET state=?,error=?,updated=? WHERE delivery_id=? AND step=?',
                        (state,type(exc).__name__+': '+str(exc)[:500],time.time(),work.row['id'],key))
                if state=='outcome_unknown' and not isinstance(exc,asyncio.CancelledError):raise OutcomeUnknown('Action result is unknown; automatic resend is denied') from exc
                raise
        return results
