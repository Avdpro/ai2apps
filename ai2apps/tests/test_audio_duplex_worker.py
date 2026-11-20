"""Generic duplex Worker boundaries using unrelated model owners; no real model."""
import asyncio
import base64
from types import SimpleNamespace

from fastapi.testclient import TestClient
import numpy as np
import pytest
from starlette.websockets import WebSocketDisconnect

from ai2apps.model_worker.audio_duplex import PROTOCOL, PATH, AudioDuplexFrame
from ai2apps.model_worker.audio_capabilities import validate_audio_capabilities, AudioCapabilitiesError
from ai2apps.model_worker.server import create_app


def declaration():
    return {'schema': 'ai2apps.audio-capabilities/v1', 'operations': ['audio_realtime'],
        'languages': ['zh'], 'formats': {'input': ['pcm'], 'output': ['pcm']},
        'streaming': {'mode': 'native', 'formats': ['pcm']},
        'duplex': {'protocol': PROTOCOL, 'mode': 'native', 'sample_rate': 24000, 'frame_samples': 3200,
                   'text_output': True, 'text_input': False, 'async_result_injection': False,
                   'response_cancel': False, 'voice_reference': True, 'maximum_session_seconds': 600}}


class Conversation:
    def __init__(self):
        self.index, self.epoch, self.muted, self.closed = 0, 0, False, False

    def frame(self):
        i = self.index
        self.index += 1
        pcm = np.zeros(3200, dtype='<f4').tobytes()
        return AudioDuplexFrame('fixture-session', i, i * 3200, self.epoch, pcm, '测试', suppressed=self.muted)

    async def start(self):
        return self.frame()

    async def step(self, pcm):
        await asyncio.sleep(.03)
        return self.frame()

    def interrupt_playback(self):
        self.epoch += 1
        self.muted = True
        return self.epoch

    def resume_playback(self):
        self.epoch += 1
        self.muted = False
        return self.epoch

    async def close(self):
        self.closed = True


@pytest.fixture(params=['example.duplex', 'unrelated.voice'])
def worker(tmp_path, monkeypatch, request):
    import json
    import ai2apps.model_worker.server as server
    conv = Conversation()
    async def open_duplex(model, options):
        return conv
    async def nothing(*args):
        pass
    adapter = SimpleNamespace(start=nothing, stop=nothing, open_duplex=open_duplex)
    async def load(*args):
        return adapter
    monkeypatch.setattr(server, '_load_adapter', load)
    model = {'id': request.param + '/model', 'upstream_id': request.param, 'model_type': 'audio_realtime',
             'audio_capabilities': declaration()}
    config = tmp_path / 'worker.json'
    config.write_text(json.dumps({'protocol': 'ai2apps-model-worker/v1', 'service_id': request.param, 'package_root': str(tmp_path),
        'data_root': str(tmp_path / 'data'), 'adapter_path': str(tmp_path / 'adapter.py'),
        'adapter_factory': 'create_adapter', 'models': [model], 'checkpoints': []}))
    with TestClient(create_app(config, token='fixture-token')) as client:
        yield client, conv, model


def start(model):
    return {'type': 'session.start', 'protocol': PROTOCOL, 'model': model['id'], 'sample_rate': 24000,
        'system_prompt': '角色', 'reference_audio': base64.b64encode(np.zeros(72000, dtype='<f4').tobytes()).decode(),
        'max_frames': 10}


def connect(client):
    return client.websocket_connect(PATH, headers={'authorization': 'Bearer fixture-token'}, subprotocols=[PROTOCOL])


def ready(socket, model):
    socket.send_json(start(model))
    created = socket.receive_json()
    assert created['type'] == 'session.created'
    assert socket.receive_json()['type'] == 'session.ready'
    assert socket.receive_json()['index'] == 0
    return created


def test_authentication_and_browser_origin_are_rejected(worker):
    client, _, _ = worker
    for headers in ({}, {'authorization': 'Bearer wrong'},
                    {'authorization': 'Bearer fixture-token', 'origin': 'http://127.0.0.1'}):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(PATH, headers=headers):
                pass


def test_duplex_frames_playback_and_existing_worker_cancellation(worker):
    client, conv, model = worker
    with connect(client) as socket:
        created = ready(socket, model)
        assert client.get('/v1/status', headers={'authorization': 'Bearer fixture-token'}).json()['active_requests'] == 1
        socket.send_json({'type': 'playback.interrupt'})
        assert socket.receive_json() == {'type': 'playback.changed', 'playback_epoch': 1, 'muted': True}
        socket.send_bytes(np.zeros(3200, dtype='<f4').tobytes())
        frame = socket.receive_json()
        assert frame['index'] == 1 and frame['suppressed'] and frame['playback_epoch'] == 1
        socket.send_json({'type': 'playback.resume'})
        assert socket.receive_json()['playback_epoch'] == 2
        response = client.delete('/v1/requests/' + created['request_id'], headers={'authorization': 'Bearer fixture-token'})
        assert response.json()['cancel_requested']
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()
    assert conv.closed
    status = client.get('/v1/requests/' + created['request_id'], headers={'authorization': 'Bearer fixture-token'}).json()
    assert status['status'] == 'cancelled'


def test_invalid_frames_do_not_reach_model_and_session_releases_worker(worker):
    client, conv, model = worker
    with connect(client) as socket:
        ready(socket, model)
        socket.send_bytes(np.full(3200, np.nan, dtype='<f4').tobytes())
        assert socket.receive_json()['code'] == 'invalid_duplex_session'
    assert conv.closed and conv.index == 1
    assert client.get('/v1/status', headers={'authorization': 'Bearer fixture-token'}).json()['active_requests'] == 0


def test_no_arbitrary_paths_or_unknown_models(worker):
    client, conv, model = worker
    for extra in ({'reference_path': '/private/file'}, {'model': 'other/model'}):
        with connect(client) as socket:
            socket.send_json({**start(model), **extra})
            assert socket.receive_json()['code'] == 'invalid_duplex_session'
    assert conv.index == 0


def test_second_session_rejected_and_frame_backpressure_is_bounded(worker):
    client, conv, model = worker
    with connect(client) as socket:
        ready(socket, model)
        with pytest.raises(WebSocketDisconnect):
            with connect(client):
                pass
        pcm = np.zeros(3200, dtype='<f4').tobytes()
        for _ in range(12):
            socket.send_bytes(pcm)
        messages = [socket.receive_json() for _ in range(1)]
        while messages[-1]['type'] != 'session.error':
            messages.append(socket.receive_json())
        assert 'backpressure' in messages[-1]['message']
    assert conv.closed


def test_native_duplex_requires_explicit_capabilities():
    caps = declaration()
    assert validate_audio_capabilities(caps, model_type='audio_realtime')['duplex']['mode'] == 'native'
    for mutate in (lambda c: c.pop('duplex'), lambda c: c['duplex'].update(text_input=True),
                   lambda c: c['duplex'].update(sample_rate=True)):
        value = declaration()
        mutate(value)
        with pytest.raises(AudioCapabilitiesError):
            validate_audio_capabilities(value, model_type='audio_realtime')
