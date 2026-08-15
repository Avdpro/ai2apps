"""Recoverable background document parsing queue."""

from __future__ import annotations

import asyncio

from .repository import DocumentRepository


class DocumentManager:
    def __init__(self, repository: DocumentRepository) -> None:
        self.repository = repository
        self._tasks: set[asyncio.Task] = set()

    async def startup(self) -> None:
        for session_id, attachment_id in await asyncio.to_thread(
            self.repository.recover_pending
        ):
            self.enqueue(session_id, attachment_id)

    def enqueue(self, session_id: str, attachment_id: str) -> None:
        task = asyncio.create_task(
            asyncio.to_thread(self.repository.parse, session_id, attachment_id),
            name=f"document-parse:{attachment_id}",
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def shutdown(self) -> None:
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
