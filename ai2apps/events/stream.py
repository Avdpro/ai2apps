"""SSE projection over durable Event replay and commit notifications."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from ai2apps.api.models import EventResponse
from ai2apps.events.bus import EventNotificationBus
from ai2apps.events.store import EventStore


def encode_sse_event(event) -> str:
    payload = EventResponse.from_record(event).model_dump(mode="json")
    return (
        f"id: {event.sequence}\n"
        f"event: {event.type}\n"
        f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
    )


async def stream_events(
    store: EventStore,
    notifications: EventNotificationBus,
    *,
    after_sequence: int = 0,
    session_id: str | None = None,
    app_instance_id: str | None = None,
    subject_id: str | None = None,
    heartbeat_seconds: float = 15.0,
    replay_batch_size: int = 100,
) -> AsyncIterator[str]:
    """Replay without gaps, then wait on a coalescing one-slot wake queue."""

    cursor = after_sequence
    async with notifications.subscribe() as wake_queue:
        while True:
            events = await asyncio.to_thread(
                store.list_after,
                cursor,
                session_id=session_id,
                app_instance_id=app_instance_id,
                subject_id=subject_id,
                limit=replay_batch_size,
            )
            if events:
                for event in events:
                    cursor = event.sequence
                    yield encode_sse_event(event)
                if len(events) == replay_batch_size:
                    continue
            try:
                await asyncio.wait_for(wake_queue.get(), timeout=heartbeat_seconds)
            except TimeoutError:
                yield ": heartbeat\n\n"
