"""Recoverable background dispatcher for staged Knowledge imports."""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor

from .store import KnowledgeStore

logger = logging.getLogger(__name__)


class KnowledgeImportManager:
    """Run bounded file imports without tying their lifetime to an HTTP request."""

    def __init__(self, store: KnowledgeStore, *, workers: int = 2) -> None:
        if not 1 <= workers <= 8:
            raise ValueError("Knowledge import workers must be between 1 and 8")
        self.store = store
        self._executor = ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="ai2apps-knowledge-import"
        )
        self._lock = threading.Lock()
        self._futures: dict[str, Future[None]] = {}
        self._closed = False

    async def startup(self) -> None:
        job_ids = await asyncio.to_thread(self.store.recover_import_jobs)
        for job_id in job_ids:
            self.enqueue(job_id)

    def enqueue(self, job_id: str) -> bool:
        with self._lock:
            if self._closed:
                return False
            current = self._futures.get(job_id)
            if current is not None and not current.done():
                return False
            future = self._executor.submit(self.store.process_import_job, job_id)
            self._futures[job_id] = future
            future.add_done_callback(
                lambda completed, key=job_id: self._done(key, completed)
            )
            return True

    def _done(self, job_id: str, future: Future[None]) -> None:
        with self._lock:
            if self._futures.get(job_id) is future:
                self._futures.pop(job_id, None)
        error = future.exception()
        if error is not None:
            logger.error(
                "Knowledge import worker failed for %s",
                job_id,
                exc_info=(type(error), error, error.__traceback__),
            )

    async def shutdown(self) -> None:
        await asyncio.to_thread(self.shutdown_sync)

    def shutdown_sync(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(True, cancel_futures=False)
