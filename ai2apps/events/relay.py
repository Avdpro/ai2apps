"""Recoverable Local outbox relay. The owner retains its private database."""
import asyncio
import logging

logger = logging.getLogger(__name__)


class EventRelay:
    def __init__(self, runtime):
        self.runtime, self.task, self.sources = runtime, None, []

    def register(self, flush):
        self.sources.append(flush)

    async def startup(self):
        if self.task is None:
            self.task = asyncio.create_task(self.run(), name='business-event-relay')

    async def shutdown(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None

    async def run(self):
        async with self.runtime.notifications.subscribe() as wake:
            while True:
                pending = False
                for flush in self.sources:
                    try:
                        work = asyncio.create_task(asyncio.to_thread(flush))
                        try:
                            count = await asyncio.shield(work)
                        except asyncio.CancelledError:
                            # Do not close the Runtime while its transaction worker is still writing.
                            await asyncio.gather(work,return_exceptions=True)
                            raise
                        pending = pending or count == 50
                    except Exception:
                        logger.exception('Business event outbox relay failed')
                if pending:
                    await asyncio.sleep(0)
                else:
                    try:
                        await asyncio.wait_for(wake.get(),timeout=2)
                    except TimeoutError:
                        pass
