"""Persisted browser Task deadlines and recovery accounting; no owner semantics."""
from __future__ import annotations
import asyncio
import time
from contextlib import asynccontextmanager
from ai2apps.agent_builder.execution_policy import resolve_policy


class RecoveryBudgetExceeded(RuntimeError):
    def __init__(self,message,*,uncertain=False):
        super().__init__(message)
        self.uncertain=uncertain


class TaskExecutionBudget:
    def __init__(self, policy=None, *, deadline_at=None, state=None, checkpoint=None, clock=time.time):
        self.policy=resolve_policy(policy)
        self.deadline_at=deadline_at
        self.state=dict(state or {})
        self.checkpoint=checkpoint or (lambda state:None)
        self.clock=clock
        self.depth=0
        # A process stop cannot refund an admitted recovery. Conservatively
        # charge elapsed wall time, including downtime, before another attempt.
        active=self.state.pop('active_since',None)
        if active is not None:
            self.state['used_seconds']=self.state.get('used_seconds',0)+max(0,self.clock()-active)
            self.checkpoint(dict(self.state))

    def remaining(self):
        return None if self.deadline_at is None else max(0,self.deadline_at-self.clock())

    @asynccontextmanager
    async def recovery(self):
        if self.depth:
            yield
            return
        attempts=self.state.get('attempts',0)
        limit=self.policy['max_recovery_attempts']
        budget=self.policy['recovery_timeout_seconds']
        remaining=None if budget is None else max(0,budget-self.state.get('used_seconds',0))
        total=self.remaining()
        if total is not None:remaining=total if remaining is None else min(total,remaining)
        if (limit is not None and attempts>=limit) or (remaining is not None and remaining<=0):
            raise RecoveryBudgetExceeded('Task recovery budget exhausted')
        started=self.clock()
        self.state.update(attempts=attempts+1,active_since=started)
        self.checkpoint(dict(self.state))  # reserve before model/input dispatch
        self.depth=1
        try:
            async with asyncio.timeout(remaining):
                yield
        except TimeoutError as error:
            raise RecoveryBudgetExceeded('Task recovery time budget exhausted',uncertain=True) from error
        finally:
            self.depth=0
            self.state.pop('active_since',None)
            self.state['used_seconds']=self.state.get('used_seconds',0)+max(0,self.clock()-started)
            self.checkpoint(dict(self.state))


@asynccontextmanager
async def recovery_scope(page, *, enabled=True):
    budget=getattr(page,'execution_budget',None)
    if budget is None or not enabled:
        yield
    else:
        async with budget.recovery():yield
