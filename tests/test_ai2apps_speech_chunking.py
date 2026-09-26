import asyncio
import io
import struct
import wave

import pytest
from fastapi.responses import Response
from ai2apps.readaloud.speech import split_speech_text, invoke_speech


def wav(value):
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(24000)
        out.writeframes(struct.pack('<h', value) * 240)
    return buffer.getvalue()


@pytest.mark.parametrize('text', ['你好，今天天气很好。我们一起出去走走吧！' * 50,
    'A sentence with several English words. Another sentence! ' * 50,
    'NoSpaces' * 100, '中文 English，mixed words。' * 100, '你好\n\n世界！' * 80])
def test_split_preserves_every_character_and_limits_requests(text):
    chunks = split_speech_text(text)
    assert ''.join(chunks) == text
    assert len(chunks) > 1
    assert all(len(split_speech_text(chunk)) == 1 for chunk in chunks)
    assert all(len(chunk) <= 300 for chunk in chunks)


def test_sentence_and_word_boundaries():
    assert split_speech_text('One. Two longer words here.', max_units=15) == ['One.', ' Two longer ', 'words here.']
    assert split_speech_text('短句不变。') == ['短句不变。']


@pytest.mark.asyncio
@pytest.mark.parametrize('multipart', [False, True])
async def test_sequential_generation_preserves_configuration_and_merges(multipart):
    calls = []
    text = '你好，这是一个完整的句子。' * 35
    original = {'input':text,'model':'tts','response_format':'wav','speed':0.9,'instructions':'Warm','emotion':'happy'}
    async def invoke(model, operation, payload=None, **kwargs):
        value = kwargs.get('data', payload)
        calls.append((value, kwargs))
        return Response(wav(len(calls)), media_type='audio/wav')
    options = {'request_id':'test','context':'owner'}
    if multipart: options['files']={'reference_audio':('ref.wav', b'reference', 'audio/wav')}
    response = await invoke_speech(invoke,'tts','audio_speech',**({'data':original} if multipart else {'payload':original}),**options)
    assert response.status_code == 200
    assert ''.join(value['input'] for value,_ in calls) == text
    assert len({opts['request_id'] for _,opts in calls}) == len(calls)
    assert all(value['speed']==0.9 and value['emotion']=='happy' and opts['context']=='owner' for value,opts in calls)
    if multipart: assert all(opts['files']==options['files'] for _,opts in calls)
    assert original['input']==text
    with wave.open(io.BytesIO(response.body),'rb') as audio:
        assert audio.getnframes()==240*len(calls)
        samples=struct.unpack('<'+'h'*audio.getnframes(),audio.readframes(audio.getnframes()))
        assert [samples[index*240] for index in range(len(calls))]==list(range(1,len(calls)+1))


@pytest.mark.asyncio
async def test_chunk_failure_stops_and_does_not_return_partial_audio():
    calls=[]
    async def invoke(*args,**kwargs):
        calls.append(args)
        return Response(wav(1)) if len(calls)==1 else Response(b'failed', status_code=503)
    response=await invoke_speech(invoke,'tts','audio_speech',{'input':'长文本。'*200},request_id='test')
    assert response.status_code==503 and response.body==b'failed'
    assert len(calls)==2


@pytest.mark.asyncio
async def test_cancellation_propagates():
    async def invoke(*args, **kwargs): raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await invoke_speech(invoke,'tts','audio_speech',{'input':'长文本。'*200},request_id='test')


@pytest.mark.asyncio
async def test_asr_retries_then_accepts_and_preserves_options():
    calls=[]
    async def invoke(*args,**kwargs):
        calls.append(kwargs)
        return Response(wav(len(calls)))
    async def verify(text,audio,index,attempt):
        assert text=='Hello' and index==0
        return [0.1,0.3,0.9][attempt]
    warnings=[]
    result=await invoke_speech(invoke,'tts','audio_speech',{'input':'Hello'},request_id='asr',verifier=verify,warnings=warnings)
    assert len(calls)==3 and len({item['request_id'] for item in calls})==3
    assert result.body==wav(3) and warnings==[]


@pytest.mark.asyncio
async def test_asr_exhaustion_keeps_best_and_continues_next_chunk():
    calls=[]
    async def invoke(*args,**kwargs):
        calls.append(args)
        return Response(wav(len(calls)))
    async def verify(text,audio,index,attempt):
        return [0.2,0.5,0.1][attempt] if index==0 else 1
    warnings=[]
    result=await invoke_speech(invoke,'tts','audio_speech',{'input':'a'*400},request_id='asr',verifier=verify,warnings=warnings)
    assert result.status_code==200 and len(calls)==4 and len(warnings)==1
    with wave.open(io.BytesIO(result.body)) as audio:
        frames=audio.readframes(audio.getnframes())
        assert struct.unpack('<h',frames[:2])[0]==2
        assert struct.unpack('<h',frames[480:482])[0]==4


@pytest.mark.asyncio
async def test_asr_unavailable_warns_without_losing_audio():
    async def invoke(*args,**kwargs): return Response(wav(1))
    async def verify(*args): raise RuntimeError('ASR unavailable')
    warnings=[]
    result=await invoke_speech(invoke,'tts','audio_speech',{'input':'Hello'},request_id='asr',verifier=verify,warnings=warnings)
    assert result.body==wav(1) and len(warnings)==1


@pytest.mark.asyncio
@pytest.mark.parametrize("verify", [False, True])
async def test_indextts_long_clause_is_bounded_before_generation_and_asr(verify):
    from ai2apps.readaloud.speech import speech_chunk_units
    text = "凡是有钱的单身汉，总想娶位太太，这已经成了一条举世公认的真理。这样的单身汉，每逢新搬到一个地方，四邻八舍虽然完全不了解他的性情如何，见解如何，可是，既然这样的一条真理早已在人们心目中根深蒂固，因此人们总是把他看作自己某一个女儿理所应得的一笔财产。"
    calls, checked = [], []
    async def invoke(model, operation, payload=None, **kwargs):
        calls.append(kwargs['data']['input'])
        assert kwargs['files']['reference_audio'][1] == b'reference'
        return Response(wav(1), media_type='audio/wav')
    async def verifier(expected, audio, index, attempt):
        checked.append(expected)
        return 1.0
    result = await invoke_speech(invoke, 'ai2apps.model.indextts25/fp16', 'audio_speech',
        data={'input': text}, files={'reference_audio': ('ref.wav', b'reference', 'audio/wav')},
        request_id='bounded', verifier=verifier if verify else None)
    assert result.status_code == 200
    assert ''.join(calls) == text
    assert len(calls) >= 4
    assert all(len(split_speech_text(part, max_units=120)) == 1 for part in calls)
    assert all(part.endswith(('，', '。')) for part in calls)
    if verify:
        assert checked == calls
    assert speech_chunk_units('ai2apps.model.voxcpm2/8bit') == 300


def long_wav(value=0, seconds=11):
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(struct.pack('<h', value) * (16000 * seconds))
    return buffer.getvalue()


@pytest.mark.asyncio
@pytest.mark.parametrize('empty_asr', [False, True])
async def test_indextts_blank_long_audio_recovers_with_subsegments(empty_asr):
    from ai2apps.readaloud.speech import SpeechVerification
    text = '这样的单身汉，每逢新搬到一个地方。'
    calls, verification_ids = [], []
    blank = long_wav(2000 if empty_asr else 0)
    async def invoke(model, operation, **kwargs):
        part = kwargs['data']['input']
        calls.append((part, kwargs['request_id']))
        assert kwargs['files']['reference_audio'][1] == b'reference'
        assert kwargs['data']['speed'] == 0.9
        return Response(blank if part == text else wav(2000))
    async def verify(expected, audio, index, attempt):
        verification_ids.append((index, attempt))
        return SpeechVerification(0 if expected == text else 1, no_content=empty_asr and expected == text)
    warnings = []
    result = await invoke_speech(invoke, 'ai2apps.model.indextts25/fp16', 'audio_speech',
        data={'input': text, 'speed': 0.9}, files={'reference_audio': ('ref.wav', b'reference', 'audio/wav')},
        request_id='recover', verifier=verify, warnings=warnings)
    assert result.status_code == 200 and warnings == []
    assert [part for part, _ in calls[:3]] == [text] * 3
    assert ''.join(part for part, _ in calls[3:]) == text
    assert len(set(key for _, key in calls)) == len(calls)
    assert len(set(verification_ids)) == len(verification_ids)
    with wave.open(io.BytesIO(result.body)) as audio:
        assert audio.getnframes() / audio.getframerate() < 1


@pytest.mark.asyncio
@pytest.mark.parametrize('model,seconds,value,score', [
    ('ai2apps.model.voxcpm2/8bit', 11, 0, 0),
    ('ai2apps.model.indextts25/fp16', 10, 0, 0),
    ('ai2apps.model.indextts25/fp16', 11, 2000, 0.2),
    ('ai2apps.model.indextts25/fp16', 11, 2000, 1),
])
async def test_adaptive_split_only_for_long_empty_indextts(model, seconds, value, score):
    calls = []
    audio = long_wav(value, seconds)
    async def invoke(*args, **kwargs):
        calls.append(args)
        return Response(audio)
    async def verify(*args): return score
    result = await invoke_speech(invoke, model, 'audio_speech', {'input': '你好，世界。'},
        request_id='guard', verifier=verify, warnings=[])
    assert result.body == audio
    assert len(calls) == (1 if score == 1 else 3)


@pytest.mark.asyncio
async def test_adaptive_split_is_bounded_and_continues_after_blank_audio():
    calls = []
    async def invoke(model, operation, payload, **kwargs):
        calls.append(payload['input'])
        return Response(wav(2000) if payload['input'] == '下一句。' else long_wav())
    async def verify(text, *args): return 1 if text == '下一句。' else 0
    warnings = []
    result = await invoke_speech(invoke, 'ai2apps.model.indextts25/fp16', 'audio_speech',
        {'input': '这是没有声音的长句子，需要再拆成更短的句子。下一句。'},
        request_id='bounded', verifier=verify, warnings=warnings)
    assert result.status_code == 200 and calls[-1] == '下一句。'
    assert len(calls) < 50
    assert any('细分限制' in warning for warning in warnings)


@pytest.mark.asyncio
async def test_subdivision_failure_preserves_parent_and_continues():
    text = '你好世界，这是一个句子。'
    calls = []
    async def invoke(model, operation, payload, **kwargs):
        calls.append(payload['input'])
        if payload['input'] == text:
            return Response(long_wav())
        if payload['input'] == '下一句。':
            return Response(wav(2000))
        return Response(b'failed', status_code=503)
    async def verify(text, *args): return 0
    warnings = []
    result = await invoke_speech(invoke, 'ai2apps.model.indextts25/fp16', 'audio_speech',
        {'input': text + '下一句。'}, request_id='fallback', verifier=verify, warnings=warnings)
    assert result.status_code == 200 and calls[-1] == '下一句。'
    assert any('细分生成失败' in warning for warning in warnings)


@pytest.mark.asyncio
async def test_indextts_silence_recovery_without_asr_and_cancel_propagation():
    text = '这样的单身汉，每逢新搬到一个地方。'
    calls = []
    async def invoke(model, operation, payload, **kwargs):
        calls.append(payload['input'])
        return Response(long_wav() if payload['input'] == text else wav(2000))
    result = await invoke_speech(invoke, 'ai2apps.model.indextts25/fp16', 'audio_speech',
        {'input': text}, request_id='no-asr')
    assert result.status_code == 200
    assert ''.join(calls[1:]) == text
    async def cancel(model, operation, payload, **kwargs):
        if payload['input'] == text:
            return Response(long_wav())
        raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await invoke_speech(cancel, 'ai2apps.model.indextts25/fp16', 'audio_speech',
            {'input': text}, request_id='cancel')
