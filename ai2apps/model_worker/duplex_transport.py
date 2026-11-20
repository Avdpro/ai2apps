# SPDX-License-Identifier: Apache-2.0
"""Authenticated Worker-only WebSocket media transport; never a browser API."""
import asyncio
import json
import secrets
import uuid

from starlette.websockets import WebSocketDisconnect

from .audio_capabilities import validate_audio_capabilities
from .audio_duplex import MAX_CONTROL_BYTES, PATH, PROTOCOL, frame_event, parse_start, validate_pcm


def install_duplex_route(app, state, context, expected_token):
    from fastapi import WebSocket
    state['duplex_cancellations'] = {}

    @app.websocket(PATH)
    async def duplex(socket: WebSocket):
        # HTTP middleware does not protect WebSocket upgrades. The trusted Host
        # supplies this worker-specific bearer; tokens in query/HTML are forbidden.
        if socket.headers.get('origin') or not secrets.compare_digest(
            socket.headers.get('authorization', ''), 'Bearer ' + expected_token
        ):
            await socket.close(code=1008)
            return
        lock = state['invocation_lock']
        if not state['accepting_requests'] or lock.locked():
            await socket.close(code=1013)
            return
        await lock.acquire()
        conversation = None
        tasks = []
        request_id = 'duplex_' + uuid.uuid4().hex
        record = None
        send_lock = asyncio.Lock()

        async def send(value):
            async with send_lock:
                await socket.send_json(value)

        try:
            await socket.accept(subprotocol=PROTOCOL if PROTOCOL in socket.scope.get('subprotocols', []) else None)
            initial = await asyncio.wait_for(socket.receive(), 10)
            text = initial.get('text')
            if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_CONTROL_BYTES:
                raise ValueError('Expected a bounded session.start message')
            message = json.loads(text)
            model_id = message.get('model') if isinstance(message, dict) else None
            model = next((m for m in context.models if model_id in (m['id'], m.get('upstream_id'))), None)
            if not model or model.get('model_type') != 'audio_realtime':
                raise ValueError('Selected model does not declare realtime audio')
            capabilities = validate_audio_capabilities(model.get('audio_capabilities'), model_type='audio_realtime')
            declaration = capabilities['duplex']
            options = parse_start(message, declaration)
            records = state['requests']
            if len(records) >= 128:
                old = next((key for key, row in records.items() if row['status'] not in ('queued', 'running')), None)
                if old is None:
                    raise ValueError('Worker request capacity exceeded')
                records.pop(old)
            record = {'request_id': request_id, 'operation': 'audio_realtime', 'model': model_id,
                      'status': 'running', 'cancel_requested': False, 'progress': None}
            records[request_id] = record
            cancel = asyncio.Event()
            state['duplex_cancellations'][request_id] = cancel
            opener = getattr(state['adapter'], 'open_duplex', None)
            if not callable(opener):
                raise ValueError('Model adapter does not implement duplex sessions')
            conversation = await opener(model_id, options)
            queue = asyncio.Queue(maxsize=2)
            ready = asyncio.Event()
            await send({'type': 'session.created', 'protocol': PROTOCOL, 'audio_format': 'pcm_f32le',
                        'request_id': request_id,
                        'sample_rate': declaration['sample_rate'], 'frame_samples': declaration['frame_samples'],
                        'max_frames': options['max_frames'], 'capabilities': declaration})

            async def receive_input():
                while True:
                    event = await asyncio.wait_for(socket.receive(), 30)
                    if event['type'] == 'websocket.disconnect':
                        return
                    pcm = event.get('bytes')
                    if pcm is not None:
                        if not ready.is_set():
                            raise ValueError('Wait for session.ready before sending audio')
                        validate_pcm(pcm, declaration['frame_samples'])
                        try:
                            queue.put_nowait(pcm)
                        except asyncio.QueueFull:
                            raise ValueError('Input frame backpressure; reconnect without replaying old audio') from None
                        continue
                    control = event.get('text', '')
                    if len(control.encode('utf-8')) > 2048:
                        raise ValueError('Oversized control message')
                    command = json.loads(control)
                    if not isinstance(command, dict) or set(command) != {'type'}:
                        raise ValueError('Invalid duplex control')
                    kind = command['type']
                    if kind == 'session.close':
                        return
                    if kind == 'playback.interrupt':
                        epoch = conversation.interrupt_playback()
                    elif kind == 'playback.resume':
                        epoch = conversation.resume_playback()
                    else:
                        raise ValueError('Unsupported duplex control')
                    await send({'type': 'playback.changed', 'playback_epoch': epoch,
                                'muted': kind == 'playback.interrupt'})

            async def inference():
                previous = -1
                frame = await conversation.start()
                ready.set()
                await send({'type': 'session.ready', 'session_id': frame.session_id})
                while True:
                    value = frame_event(frame, declaration)
                    if frame.index != previous + 1:
                        raise RuntimeError('Nonsequential model output')
                    previous = frame.index
                    await send(value)
                    if frame.done:
                        record['status'] = 'completed'
                        return
                    pcm = await queue.get()
                    frame = await conversation.step(pcm)

            tasks = [asyncio.create_task(receive_input()), asyncio.create_task(inference()),
                     asyncio.create_task(cancel.wait())]
            done, _ = await asyncio.wait(tasks, timeout=declaration['maximum_session_seconds'] + 10,
                                         return_when=asyncio.FIRST_COMPLETED)
            if not done:
                raise TimeoutError('Duplex session deadline reached')
            for task in done:
                task.result()
        except (ValueError, TimeoutError) as exc:
            if record is not None:
                record['status'] = 'failed'
            try:
                await send({'type': 'session.error', 'code': 'invalid_duplex_session', 'message': str(exc)[:240]})
            except (RuntimeError, WebSocketDisconnect):
                pass
        except WebSocketDisconnect:
            pass
        except Exception:
            if record is not None:
                record['status'] = 'failed'
            # Model/provider exceptions can contain file paths or user content.
            try:
                await send({'type': 'session.error', 'code': 'duplex_model_error', 'message': 'Duplex inference failed'})
            except (RuntimeError, WebSocketDisconnect):
                pass
        finally:
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            try:
                if conversation is not None:
                    await conversation.close()
            finally:
                state['duplex_cancellations'].pop(request_id, None)
                if record is not None and record['status'] == 'running':
                    record['status'] = 'cancelled'
                lock.release()
                try:
                    await socket.close()
                except (RuntimeError, WebSocketDisconnect):
                    pass
