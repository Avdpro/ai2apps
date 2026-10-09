import io
import wave
import numpy as np
import pytest
from ai2apps.audio_codecs import change_speech_tempo


@pytest.mark.parametrize('rate', [24000,44100,48000])
@pytest.mark.parametrize('speed', [0.5, 0.75, 1.25, 2.0])
def test_tempo_changes_duration_without_changing_pitch(speed,rate):
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        samples = (10000*np.sin(np.arange(rate*2)*2*np.pi*440/rate)).astype('<i2')
        audio.writeframes(samples.tobytes())
    result = change_speech_tempo(buffer.getvalue(), speed, sample_rate=rate)
    with wave.open(io.BytesIO(result)) as audio:
        assert audio.getframerate() == rate
        assert audio.getnframes()/rate == pytest.approx(2/speed, abs=0.06)
        values = np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2')
    frequency = np.fft.rfftfreq(len(values), 1/rate)[np.argmax(abs(np.fft.rfft(values)))]
    assert frequency == pytest.approx(440, abs=2)


def test_normal_speed_preserves_original_bytes():
    assert change_speech_tempo(b'original', 1) == b'original'


@pytest.mark.asyncio
@pytest.mark.parametrize('declared',[False,True])
async def test_host_tempo_only_rewrites_explicit_pipeline(monkeypatch,declared):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from omlx.api import audio_routes as routes
    from omlx.api.audio_models import AudioSpeechRequest
    caps={'tts':{'speed':{'mode':'pipeline' if declared else 'native','control':'host_atempo'}}}
    model=SimpleNamespace(id='fish',model_type='audio_tts',audio_capabilities=caps)
    invocation=SimpleNamespace(invoke_foreground_json=AsyncMock(return_value=object()))
    response=AsyncMock(return_value='ok')
    monkeypatch.setattr(routes,'_package_model',lambda _:model)
    monkeypatch.setattr(routes,'_model_invocations',lambda:invocation)
    monkeypatch.setattr(routes,'_audio_invocation_context',lambda:None)
    monkeypatch.setattr(routes,'_package_speech_response',response)
    assert await routes.create_speech(AudioSpeechRequest(model='fish',input='Hello',speed=1.5))=='ok'
    assert invocation.invoke_foreground_json.call_args.args[2]['speed']==(1.0 if declared else 1.5)
    assert response.call_args.kwargs['pipeline_speed']==(1.5 if declared else 1.0)


@pytest.mark.asyncio
@pytest.mark.parametrize('speed',[0.49,2.01,float('nan'),float('inf')])
async def test_invalid_host_pipeline_speed_rejected_before_inference(monkeypatch,speed):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from omlx.api import audio_routes as routes
    from omlx.api.audio_models import AudioSpeechRequest
    model=SimpleNamespace(id='fish',model_type='audio_tts',audio_capabilities={'tts':{'speed':{'mode':'pipeline','control':'host_atempo'}}})
    monkeypatch.setattr(routes,'_package_model',lambda _:model)
    def no_inference():raise AssertionError('Invalid request reached inference')
    monkeypatch.setattr(routes,'_model_invocations',no_inference)
    with pytest.raises(HTTPException) as error:
        await routes.create_speech(AudioSpeechRequest(model='fish',input='Hello',speed=speed))
    assert error.value.status_code==400
