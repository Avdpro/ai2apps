"""Real codec/media preservation regressions, with model inference fixtures."""
import io
from pathlib import Path
from types import SimpleNamespace as NS
import wave
import numpy as np
import pytest
from fastapi.responses import Response
from ai2apps.audio_codecs import decode_audio_to_wav,AudioCodecError
from ai2apps.identity import RequestPrincipal
from ai2apps.studio.media_workflows import _wav,_read_audio,mix_replaced_speaker
from ai2apps.studio.capability_broker import StudioCapabilityBroker,MountedMiniApp


def stereo():
    t=np.arange(4800)/48000
    return _wav(np.stack([.15*np.sin(2*np.pi*220*t),.2*np.sin(2*np.pi*330*t)],axis=1),48000)


def test_codec_explicit_stereo_path_retains_distinct_channels_and_mono_default(tmp_path):
    source=tmp_path/'audio.wav';source.write_bytes(stereo())
    preserved=decode_audio_to_wav(source,input_format='wav',sample_rate=48000,channels=2)
    with wave.open(io.BytesIO(preserved)) as w:assert w.getnchannels()==2 and w.getnframes()==4800
    assert np.allclose(_read_audio(preserved)[0],_read_audio(source.read_bytes())[0],atol=1/32767)
    with wave.open(io.BytesIO(decode_audio_to_wav(source,input_format='wav'))) as w:assert w.getnchannels()==1
    for bad in [0,3,True,'2']:
        with pytest.raises(AudioCodecError):decode_audio_to_wav(source,channels=bad)
    raw=b'\0\0'*160
    with wave.open(io.BytesIO(decode_audio_to_wav(raw,input_format='pcm',channels=2))) as w:assert w.getnchannels()==2 and w.getnframes()==160


@pytest.mark.asyncio
async def test_video_extraction_keeps_stereo_before_nested_speaker_workflow(monkeypatch):
    broker=StudioCapabilityBroker(NS(extension_manager=NS()));caps=frozenset({'media.video_speaker_voice_replacement','audio.speaker_voice_replacement','media.audio.extract','media.video.audio_mux'})
    monkeypatch.setattr(broker,'mounted_mini_app',lambda *a,**kw:MountedMiniApp({}, {}, caps))
    monkeypatch.setattr('ai2apps.studio.capability_broker.validate_video_media',lambda *a:None)
    async def nested(*a,**kw):
        with wave.open(io.BytesIO(kw['content'])) as w:assert w.getnchannels()==2
        assert np.allclose(_read_audio(kw['content'])[0],_read_audio(stereo())[0],atol=1/32767)
        return Response(b'{}',media_type='application/json')
    monkeypatch.setattr(broker,'audio_speaker_replacement',nested)
    result=await broker.video_speaker_replacement('studio','mount',principal=RequestPrincipal.legacy_local(),content=stereo(),filename='source.mp4',media_type='video/mp4',action='analyze',target_speaker=None,reference=None,reference_filename=None,reference_media_type=None,conversion_profile='timbre_fast',consent=False)
    assert result.media_type=='application/json'


@pytest.mark.asyncio
async def test_separation_sends_stereo_to_declared_model(monkeypatch):
    captured=[]
    async def invoke(*a,**kw):captured.append(kw);return Response(b'zip')
    runtime=NS(extension_manager=NS(),model_invocations=NS(invoke_foreground_multipart=invoke))
    broker=StudioCapabilityBroker(runtime)
    monkeypatch.setattr(broker,'mounted_mini_app',lambda *a,**kw:MountedMiniApp({'app_instance_id':'owner'},{'id':'declared.mini'},frozenset({'audio.source_separation'})))
    monkeypatch.setattr(broker,'_separation_models',lambda *a:[NS(id='declared.model')])
    monkeypatch.setattr(broker,'_separation_profiles',lambda *a:{'dialogue_background'})
    monkeypatch.setattr(broker,'_model_stack_ready',lambda *a:True)
    await broker.source_separation('studio','mount',principal=RequestPrincipal.legacy_local(),content=stereo(),filename='source.wav',media_type='audio/wav',profile='dialogue_background')
    wav=captured[0]['files']['file'][1]
    with wave.open(io.BytesIO(wav)) as w:assert w.getnchannels()==2
    assert np.allclose(_read_audio(wav)[0],_read_audio(stereo())[0],atol=1/32767)


def test_loud_target_does_not_normalize_untouched_voice_or_stereo_background():
    rate=48000;n=rate
    bg=np.tile(np.array([.2,-.1],np.float32),(n,1));dialogue=np.zeros((n,2),np.float32)
    dialogue[24000:36000]=.25
    converted=np.ones((n,2),np.float32)*.98
    result=mix_replaced_speaker(_wav(dialogue,rate),_wav(bg,rate),_wav(converted,rate),[{'speaker':'A','start':.1,'end':.4},{'speaker':'B','start':.5,'end':.75}],target_speaker='A')
    values,_=_read_audio(result)
    assert np.allclose(values[24000:36000],(bg+dialogue)[24000:36000],atol=3/32767)
    assert np.allclose(values[40000:],bg[40000:],atol=3/32767)
    assert values[12000,0]>.95 and np.max(np.abs(values))<=1
