# SPDX-License-Identifier: Apache-2.0
"""Notification, heartbeat, backpressure, and cursor replay tests."""

from __future__ import annotations

import asyncio

import pytest

from ai2apps.events import EventNotificationBus, EventStore
from ai2apps.events.stream import stream_events
from ai2apps.storage import PlatformDatabase


@pytest.fixture
def event_runtime(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    notifications = EventNotificationBus()
    return database, notifications, EventStore(database, notifications)


@pytest.mark.asyncio
async def test_notifications_fire_only_after_commit_and_coalesce(event_runtime):
    database, notifications, events = event_runtime
    async with notifications.subscribe() as queue:
        with database.transaction(write=True) as connection:
            events.append_in_transaction(
                connection,
                event_type="test.created",
                subject_id="test",
            )
            assert queue.empty()
        await asyncio.sleep(0)
        assert queue.qsize() == 1

        for _ in range(100):
            notifications.notify()
        await asyncio.sleep(0)
        assert queue.qsize() == 1


@pytest.mark.asyncio
async def test_rollback_discards_notification_and_event(event_runtime):
    database, notifications, events = event_runtime
    async with notifications.subscribe() as queue:
        with (
            pytest.raises(RuntimeError),
            database.transaction(write=True) as connection,
        ):
            events.append_in_transaction(
                connection,
                event_type="test.rollback",
                subject_id="test",
            )
            raise RuntimeError("rollback")
        await asyncio.sleep(0)
        assert queue.empty()
        assert events.list_after() == ()


@pytest.mark.asyncio
async def test_stream_replays_cursor_then_emits_live_commit(event_runtime):
    _, notifications, events = event_runtime
    first = events.append(event_type="test.first", subject_id="first")
    second = events.append(event_type="test.second", subject_id="second")
    stream = stream_events(
        events,
        notifications,
        after_sequence=first.sequence,
        heartbeat_seconds=1,
    )

    replay = await anext(stream)
    assert f"id: {second.sequence}\n" in replay
    assert "event: test.second\n" in replay

    pending = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    third = await asyncio.to_thread(
        events.append,
        event_type="test.third",
        subject_id="third",
    )
    live = await asyncio.wait_for(pending, timeout=1)
    assert f"id: {third.sequence}\n" in live
    await stream.aclose()
    assert notifications.subscriber_count == 0


@pytest.mark.asyncio
async def test_stream_emits_heartbeat_when_idle(event_runtime):
    _, notifications, events = event_runtime
    stream = stream_events(
        events,
        notifications,
        heartbeat_seconds=0.01,
    )
    assert await anext(stream) == ": heartbeat\n\n"
    await stream.aclose()


@pytest.mark.asyncio
async def test_cancelled_stream_wait_releases_subscriber(event_runtime):
    _, notifications, events = event_runtime
    stream = stream_events(events, notifications, heartbeat_seconds=60)
    pending = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    assert notifications.subscriber_count == 1

    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    await stream.aclose()

    assert notifications.subscriber_count == 0


@pytest.mark.asyncio
async def test_stream_replays_high_volume_without_gaps(event_runtime):
    _, notifications, events = event_runtime
    for number in range(250):
        events.append(event_type="load.item", subject_id=str(number))
    stream = stream_events(
        events,
        notifications,
        heartbeat_seconds=1,
        replay_batch_size=17,
    )

    frames = [await anext(stream) for _ in range(250)]
    await stream.aclose()

    assert [int(frame.split("\n", 1)[0].removeprefix("id: ")) for frame in frames] == list(
        range(1, 251)
    )
    assert notifications.subscriber_count == 0
