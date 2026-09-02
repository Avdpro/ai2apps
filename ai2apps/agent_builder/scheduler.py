"""Durable, model-free dispatcher for Agent P1 Schedules."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from .repository import AgentBuilderRepository
from .service import create_active_draft_run, create_workflow_run

logger = logging.getLogger(__name__)


class AgentScheduleRunner:
    """Turn due schedules into ordinary auditable AgentRuns."""

    def __init__(self, runtime, store: AgentBuilderRepository) -> None:
        self.runtime = runtime
        self.store = store
        self._stop = asyncio.Event()
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def startup(self) -> None:
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(
                self._loop(), name="ai2apps-agent-schedules"
            )

    async def shutdown(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._task is not None:
            await self._task
        self._task = None

    def wake(self) -> None:
        self._wake.set()

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._pass()
            except Exception:
                logger.exception("Agent Schedule dispatch pass failed")
            self._wake.clear()
            with suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout=2.0)

    def _pass(self) -> None:
        self.store.reconcile_dispatches()
        for _ in range(32):
            claimed = self.store.claim_due_schedule()
            if claimed is None:
                break
            schedule, dispatch = claimed
            try:
                common = {
                    "runtime": self.runtime,
                    "store": self.store,
                    "owner_user_id": schedule.owner_user_id,
                    "session_id": schedule.session_id,
                    "invocation_input": schedule.input,
                    "caller_app_id": "ai2apps.agents.schedule",
                    "knowledge_bucket_id": schedule.knowledge_bucket_id,
                    "idempotency_key": f"schedule:{dispatch.id}",
                    "installation_id": schedule.installation_id,
                }
                if schedule.draft_id is not None:
                    run = create_active_draft_run(
                        draft_id=schedule.draft_id, **common
                    )
                else:
                    run = create_workflow_run(
                        workflow_id=str(schedule.workflow_id), **common
                    )
                self.store.finish_dispatch(dispatch.id, run_id=run.id)
            except Exception as error:
                logger.exception("Agent Schedule %s failed", schedule.id)
                self.store.finish_dispatch(
                    dispatch.id,
                    error={"type": type(error).__name__, "message": str(error)},
                )
