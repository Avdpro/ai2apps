"""Thread-safe commit notification bus backed by durable Event replay."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from threading import Lock
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class _Subscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[None]


class EventNotificationBus:
    """Wake subscribers after commit; durable Events remain the source of truth."""

    def __init__(self) -> None:
        self._subscribers: dict[str, _Subscriber] = {}
        self._lock = Lock()

    @staticmethod
    def _offer(queue: asyncio.Queue[None]) -> None:
        if not queue.full():
            queue.put_nowait(None)

    def notify(self) -> None:
        with self._lock:
            subscribers = tuple(self._subscribers.values())
        for subscriber in subscribers:
            subscriber.loop.call_soon_threadsafe(self._offer, subscriber.queue)

    @asynccontextmanager
    async def subscribe(self):
        """Yield a one-slot wake queue; coalescing cannot lose durable Events."""

        subscriber_id = uuid4().hex
        subscriber = _Subscriber(
            loop=asyncio.get_running_loop(),
            queue=asyncio.Queue(maxsize=1),
        )
        with self._lock:
            self._subscribers[subscriber_id] = subscriber
        try:
            yield subscriber.queue
        finally:
            with self._lock:
                self._subscribers.pop(subscriber_id, None)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)
