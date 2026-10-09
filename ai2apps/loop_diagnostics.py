"""Bounded, content-free diagnostics for a stalled Local event loop."""

import asyncio
import logging
import sys
import threading
import time
import traceback

logger = logging.getLogger(__name__)


class LoopDiagnostics:
    def __init__(self, threshold=1.0, report_interval=30.0):
        self.threshold = threshold
        self.report_interval = report_interval
        self._stop = threading.Event()
        self._heartbeat = time.monotonic()
        self._last_report = 0.0

    def start(self):
        self._loop = asyncio.get_running_loop()
        self._thread_id = threading.get_ident()
        self._task = self._loop.create_task(self._pulse(), name="local-loop-heartbeat")
        self._thread = threading.Thread(target=self._watch, daemon=True, name="local-loop-diagnostics")
        self._thread.start()

    async def _pulse(self):
        while not self._stop.is_set():
            self._heartbeat = time.monotonic()
            await asyncio.sleep(0.25)

    def _watch(self):
        while not self._stop.wait(0.25):
            now = time.monotonic()
            lag = now - self._heartbeat
            if lag < self.threshold or now - self._last_report < self.report_interval:
                continue
            self._last_report = now
            frame = sys._current_frames().get(self._thread_id)
            # Never capture locals, source lines, request bodies or credentials.
            stack = traceback.extract_stack(frame) if frame is not None else []
            locations = " > ".join(f"{item.filename}:{item.lineno}:{item.name}" for item in stack[-24:])
            logger.warning("Local event loop stalled %.2fs; stack=%s", lag, locations)

    async def stop(self):
        self._stop.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        await asyncio.to_thread(self._thread.join)
