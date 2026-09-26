"""Shared bounded speech synthesis for every Voice Studio producer."""
from __future__ import annotations

import asyncio
import array
import json
import sys
from dataclasses import dataclass
import re
import wave
from io import BytesIO

from fastapi.responses import JSONResponse, Response
from ai2apps.audio_codecs import decode_audio_to_wav

MAX_SPEECH_UNITS = 300  # About 100 CJK characters or 300 Latin characters.
MAX_AUDIO_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class SpeechVerification:
    score: float
    no_content: bool = False


def speech_verifier(invoke, model_id, *, request_id, context=None):
    async def verify(expected, audio, index, attempt):
        from ai2apps.studio.capability_broker import _speech_text_similarity
        result = await asyncio.wait_for(invoke(
            model_id, 'audio_transcription', data={'model': model_id, 'response_format': 'json'},
            files={'file': ('speech.wav', audio, 'audio/wav')},
            request_id=f'{request_id}-asr-{index}-{attempt}',
            **({'context': context} if context is not None else {})), timeout=120)
        if result.status_code >= 400:
            raise ValueError('ASR request failed')
        transcript = json.loads(result.body)
        recognized = transcript.get('text') or ' '.join(item.get('text', '') for item in transcript.get('segments', []))
        return SpeechVerification(_speech_text_similarity(expected, recognized),
                                  no_content=not any(c.isalnum() for c in recognized))
    return verify


def _long_empty_audio(content: bytes, *, no_content: bool) -> bool:
    """Only classify decoded audio, never infer duration from compressed byte size."""
    try:
        normalized = decode_audio_to_wav(content, input_format='wav', sample_rate=16000, max_duration_seconds=600)
        with wave.open(BytesIO(normalized), 'rb') as source:
            if source.getnframes() / source.getframerate() <= 10:
                return False
            if no_content:
                return True
            samples = array.array('h', source.readframes(source.getnframes()))
        if sys.byteorder != 'little':
            samples.byteswap()
        # Less than 0.1% of samples above -50 dBFS: near-silent, not merely quiet speech.
        return bool(samples) and sum(abs(value) > 104 for value in samples) / len(samples) < 0.001
    except (ValueError, EOFError, wave.Error):
        return False


def speech_chunk_units(model_id: str) -> int:
    # Use the registered Package model identity, never a user-editable display name.
    if str(model_id).startswith("ai2apps.model.indextts25/"):
        return 120  # Approximately 40 CJK characters; keep clauses together.
    return MAX_SPEECH_UNITS


def split_speech_text(text: str, *, max_units: int = MAX_SPEECH_UNITS) -> list[str]:
    """Preserve text verbatim, preferring sentence, clause, then word boundaries."""
    if max_units < 3:
        raise ValueError('Speech chunk limit must be at least 3')
    chunks = []
    while text:
        units = 0
        end = 0
        for character in text:
            weight = 3 if '\u2e80' <= character <= '\ua4cf' or '\uac00' <= character <= '\ud7af' or ord(character) >= 0x20000 else 1
            if units + weight > max_units:
                break
            units += weight
            end += 1
        if end == len(text):
            chunks.append(text)
            break
        window = text[:end]
        # Decimal points and abbreviations without following whitespace are not breaks.
        boundaries = list(re.finditer(r'[。！？!?；;\n]+[”’"\u300d\u300f]*|\.(?=\s)', window))
        if not boundaries:
            boundaries = list(re.finditer(r'[,，、：:]|\s+', window))
        cut = boundaries[-1].end() if boundaries else end
        # Avoid producing whitespace-only requests while conserving the original text.
        if not text[:cut].strip():
            cut = end
        chunks.append(text[:cut])
        text = text[cut:]
    return chunks


def _join_audio(parts: list[bytes]) -> bytes:
    output = BytesIO()
    with wave.open(output, 'wb') as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(24000)
        for part in parts:
            normalized = decode_audio_to_wav(part, input_format='wav', sample_rate=24000, max_duration_seconds=600)
            with wave.open(BytesIO(normalized), 'rb') as source:
                if not source.getnframes():
                    raise ValueError('Empty speech chunk')
                target.writeframes(source.readframes(source.getnframes()))
            if output.tell() > MAX_AUDIO_BYTES:
                raise ValueError('Combined speech output exceeds 64 MiB')
    return output.getvalue()


async def invoke_speech(invoke, model_id, operation, payload=None, *, data=None, verifier=None, warnings=None, _split_depth=0, _chunk_units=None, **options):
    """Only publish a complete result. Failure/cancellation never exposes partial audio."""
    original = data if data is not None else payload
    is_indextts = str(model_id).startswith("ai2apps.model.indextts25/")
    max_units = _chunk_units or speech_chunk_units(model_id)
    chunks = split_speech_text(original['input'], max_units=max_units)
    if verifier is not None:
        sentences = re.findall(r'.+?(?:[。！？!?]+[”’"]*|\.(?=\s)|$)', original['input'], flags=re.S)
        chunks = [chunk for sentence in sentences for chunk in split_speech_text(sentence, max_units=max_units)]
    if len(chunks) <= 1 and verifier is None and not is_indextts:
        if data is not None:
            return await invoke(model_id, operation, data=data, **options)
        return await invoke(model_id, operation, payload, **options)
    parts = []
    total = 0
    for index, text in enumerate(chunks):
        if not text.strip():
            continue
        chunk = {**original, 'input': text}
        chunk_options = {**options, 'request_id': f"{options['request_id']}-part-{index + 1}"}
        best_response, best_score = None, -1.0
        best_no_content = False
        segment_warnings = []
        for attempt in range(3 if verifier else 1):
            attempt_options = {**chunk_options, 'request_id': chunk_options['request_id'] + f'-try-{attempt + 1}'}
            response = (await invoke(model_id, operation, data=chunk, **attempt_options) if data is not None
                        else await invoke(model_id, operation, chunk, **attempt_options))
            if response.status_code >= 400:
                if best_response is None:
                    return response
                if warnings is not None:
                    segment_warnings.append(f'第 {index + 1} 段重新生成失败，保留此前音频；请试听确认。')
                break
            if verifier is None:
                best_response = response
                break
            try:
                verification = await verifier(text, bytes(response.body), index, attempt)
                score = verification.score if isinstance(verification, SpeechVerification) else verification
            except Exception:
                best_response = best_response or response
                if warnings is not None:
                    segment_warnings.append(f'第 {index + 1} 段 ASR 校验不可用，已保留音频并继续；请试听确认。')
                break
            if score > best_score:
                best_response, best_score = response, score
                best_no_content = isinstance(verification, SpeechVerification) and verification.no_content
            if score >= 0.62:
                break
            if attempt == 2 and warnings is not None:
                segment_warnings.append(f'第 {index + 1} 段生成 3 次仍未通过 ASR 校验，已保留匹配度最高的音频；请试听确认。')
        response = best_response
        if (is_indextts and best_score < 0.62
                and await asyncio.to_thread(_long_empty_audio, bytes(response.body), no_content=best_no_content)):
            # Halve the actual text budget, so even a short but blank sentence gets split.
            units = sum(3 if '\u2e80' <= c <= '\ua4cf' or '\uac00' <= c <= '\ud7af' or ord(c) >= 0x20000 else 1 for c in text)
            smaller = max(3, min(max_units // 2, units // 2))
            subchunks = [part for part in split_speech_text(text, max_units=smaller) if part.strip()]
            if _split_depth < 2 and len(subchunks) > 1:
                async def subverifier(expected, audio, subindex, attempt):
                    return await verifier(expected, audio, f'{index}.{subindex}', attempt)
                recovery_warnings = []
                recovery = await invoke_speech(
                    invoke, model_id, operation,
                    **({'data': chunk} if data is not None else {'payload': chunk}),
                    verifier=subverifier if verifier else None, warnings=recovery_warnings,
                    _split_depth=_split_depth + 1, _chunk_units=smaller,
                    **{**options, 'request_id': chunk_options['request_id'] + '-split'},
                )
                if recovery.status_code < 400:
                    response = recovery
                    segment_warnings = recovery_warnings
                else:
                    segment_warnings.append(f'第 {index + 1} 段细分生成失败，已保留此前音频并继续；请试听确认。')
            else:
                segment_warnings.append(f'第 {index + 1} 段仍有超过 10 秒的无内容音频，已达到细分限制并保留音频；请试听确认。')
        if warnings is not None:
            warnings.extend(segment_warnings)
        content = bytes(response.body)
        total += len(content)
        if not content or total > MAX_AUDIO_BYTES:
            return JSONResponse({'error': {'message': 'Invalid or oversized speech chunk output'}}, status_code=502)
        parts.append(content)
    try:
        content = parts[0] if len(parts) == 1 else await asyncio.to_thread(_join_audio, parts)
    except (ValueError, EOFError, wave.Error) as error:
        return JSONResponse({'error': {'message': f'Could not merge speech chunks: {error}'}}, status_code=502)
    return Response(content, media_type='audio/wav')
