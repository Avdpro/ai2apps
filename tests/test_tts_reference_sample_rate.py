import pytest
from ai2apps.model_worker.audio_capabilities import (
    AudioCapabilitiesError, default_audio_capabilities,
    reference_audio_sample_rate, validate_audio_capabilities,
)


def test_legacy_and_official_fish_reference_rates():
    assert reference_audio_sample_rate(None)==24000
    caps=default_audio_capabilities('audio_tts')
    assert reference_audio_sample_rate(caps)==24000
    caps['tts']['voice_profiles']['reference_sample_rate']=44100
    normalized=validate_audio_capabilities(caps,model_type='audio_tts')
    assert reference_audio_sample_rate(normalized)==44100


@pytest.mark.parametrize('value',[True,None,'44100',44100.0,0,7999,192001])
def test_invalid_declared_reference_rate_rejected(value):
    caps=default_audio_capabilities('audio_tts')
    caps['tts']['voice_profiles']['reference_sample_rate']=value
    with pytest.raises(AudioCapabilitiesError,match='reference_sample_rate'):
        validate_audio_capabilities(caps,model_type='audio_tts')


@pytest.mark.asyncio
async def test_package_host_preserves_declared_reference_contract(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from omlx.api import audio_routes as routes
    from omlx.api.audio_models import AudioSpeechRequest
    caps={'tts':{'voice_profiles':{'reference_sample_rate':44100,'reference_transcript':'optional'}}}
    model=SimpleNamespace(id='fish',model_type='audio_tts',audio_capabilities=caps)
    normalize=AsyncMock(return_value=b'normalized-wav')
    invocation=SimpleNamespace(invoke_foreground_multipart=AsyncMock(return_value=object()))
    monkeypatch.setattr(routes,'_package_model',lambda _:model)
    monkeypatch.setattr(routes,'_normalize_audio_bytes',normalize)
    monkeypatch.setattr(routes,'_model_invocations',lambda:invocation)
    monkeypatch.setattr(routes,'_audio_invocation_context',lambda:None)
    monkeypatch.setattr(routes,'_package_speech_response',AsyncMock(return_value='ok'))
    assert await routes.create_speech(AudioSpeechRequest(model='fish',input='Hello',ref_audio='YQ=='))=='ok'
    assert normalize.call_args.kwargs['sample_rate']==44100
    data=invocation.invoke_foreground_multipart.call_args.kwargs
    assert 'ref_audio' not in data['data']
    assert data['files']['reference_audio'][1]==b'normalized-wav'


def test_legacy_reference_transcript_still_required():
    from fastapi import HTTPException
    from omlx.api.audio_routes import _decode_ref_audio_base64
    from omlx.api.audio_models import AudioSpeechRequest
    with pytest.raises(HTTPException) as error:
        _decode_ref_audio_base64(AudioSpeechRequest(model='legacy',input='Hello',ref_audio='YQ=='))
    assert error.value.status_code==400
