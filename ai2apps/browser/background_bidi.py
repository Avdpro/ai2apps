"""Private Local SDK transport on the same native BiDi session as the Gateway.

No method catalog, browser semantics, endpoint or credential is exposed to HTML.
Closing an SDK attachment must never end the browser's shared native session.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import suppress

from .shell_bidi_gateway import ShellBiDiEndpoint, attach_shell_bidi_session, shell_bidi_descriptor_path


class BackgroundBiDi:
    def __init__(self):
        self._attachment = None
        self._upstream = None
        self._reader = None
        self._pending = {}
        self._next_id = 0
        self._send_lock = asyncio.Lock()

    async def connect(self):
        from websockets.asyncio.client import connect
        deadline = asyncio.get_running_loop().time() + 15
        while True:
            try:
                endpoint = ShellBiDiEndpoint.load(shell_bidi_descriptor_path())
            except (OSError, ValueError, RuntimeError):
                if asyncio.get_running_loop().time() >= deadline:
                    raise
                await asyncio.sleep(.25)
                continue
            self._attachment = attach_shell_bidi_session(endpoint, connect)
            try:
                _session, self._upstream = await self._attachment.__aenter__()
                break
            except Exception as error:
                # Cold native launch publishes its identity before the listener
                # accepts connections. No browser action has been sent yet.
                self._attachment = None
                if not isinstance(error, (OSError, asyncio.TimeoutError)) and not isinstance(
                        error.__cause__, (OSError, asyncio.TimeoutError)):
                    raise
                if asyncio.get_running_loop().time() >= deadline:
                    raise
                await asyncio.sleep(.25)
        self._reader = asyncio.create_task(self._read(), name='webagent-native-bidi')
        return self

    async def _read(self):
        failure = RuntimeError('Browser transport disconnected; action outcome may be unknown')
        try:
            async for message in self._upstream:
                value = json.loads(message)
                future = self._pending.get(value.get('id'))
                if future is None or future.done():
                    continue
                if value.get('type') == 'error' or 'error' in value:
                    future.set_exception(RuntimeError(f"{value.get('error')}: {value.get('message', '')}"))
                else:
                    future.set_result(value.get('result', {}))
        except Exception as error:
            failure = error
        finally:
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(failure)

    async def command(self, method, params, timeout=30):
        if self._reader is None or self._reader.done():
            raise RuntimeError('Browser transport is not connected')
        self._next_id += 1
        command_id = self._next_id
        future = asyncio.get_running_loop().create_future()
        self._pending[command_id] = future
        try:
            async with self._send_lock:
                await self._upstream.send(json.dumps({'id': command_id, 'method': method, 'params': params}))
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending.pop(command_id, None)

    async def close(self):
        if self._reader is not None:
            self._reader.cancel()
            with suppress(asyncio.CancelledError):
                await self._reader
        if self._attachment is not None:
            await self._attachment.__aexit__(None, None, None)
        self._reader = self._attachment = self._upstream = None
