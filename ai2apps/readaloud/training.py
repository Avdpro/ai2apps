"""Model-specific, owner-authorized voice reference preparation."""
from __future__ import annotations

from io import BytesIO
import wave
from typing import Any

from ai2apps.audio_codecs import decode_audio_to_wav, infer_audio_format


def requirements(model) -> dict[str, Any] | None:
    caps = model.audio_capabilities or {}
    reference = caps.get('tts', {}).get('voice_profiles', {})
    training = caps.get('processing', {}).get('voice_training', {})
    if reference.get('mode', 'unsupported') != 'unsupported':
        feature, method = reference, 'reference'
    elif training.get('mode', 'unsupported') != 'unsupported':
        feature, method = training, 'training'
    else:
        return None
    declared = feature.get('reference_requirements', {})
    # The current TTS transport accepts one reference_audio part. Multiple
    # source clips can be stored without pretending that this is model training.
    return {
        'method': method,
        'transcript': feature.get('reference_transcript', 'unknown'),
        'minSamples': declared.get('min_samples', 1),
        'maxSamples': declared.get('max_samples', 1 if method == 'reference' else None),
        'minSeconds': declared.get('min_seconds'),
        'maxSeconds': declared.get('max_seconds'),
        'minTotalSeconds': declared.get('min_total_seconds'),
        'maxTotalSeconds': declared.get('max_total_seconds'),
        'executable': method == 'reference' and declared.get('max_samples', 1) == 1,
        'revision': str((getattr(model, 'weights', None) or {}).get('revision') or ''),
    }


def prepare(model, samples: list[dict], gallery, owner: str, *, for_execution=False):
    spec = requirements(model)
    if spec is None:
        raise ValueError('This model does not support voice references or training.')
    if not samples:
        raise ValueError('Add at least one audio sample.')
    selected = [sample for sample in samples if sample.get('selected', True)]
    merging = spec['method'] == 'reference' and spec['maxSamples'] == 1 and len(selected) > 1
    if len(selected) < spec['minSamples'] or (not merging and spec['maxSamples'] is not None and len(selected) > spec['maxSamples']):
        raise ValueError('The number of selected samples does not meet this model’s requirements.')
    prepared, files, total, aggregate_bytes = [], {}, 0.0, 0
    seen = set()
    for sample in samples:
        asset_id = sample['asset_id']
        if asset_id in seen:
            raise ValueError('Each audio sample must be unique.')
        seen.add(asset_id)
        asset, path = gallery.asset_path(owner, asset_id)
        if not asset['media_type'].startswith('audio/'):
            raise ValueError('Reference material must be audio.')
        aggregate_bytes += path.stat().st_size
        if aggregate_bytes > 64 * 1024 * 1024:
            raise ValueError('Reference materials exceed the 64 MiB request limit.')
        wav = decode_audio_to_wav(path.read_bytes(), input_format=infer_audio_format(asset['name'], asset['media_type']), max_duration_seconds=600)
        with wave.open(BytesIO(wav)) as audio:
            seconds = audio.getnframes() / audio.getframerate()
        text = sample.get('transcript', '').strip()
        enabled = sample.get('selected', True)
        confirmed = bool(sample.get('confirmed', False))
        if enabled:
            total += seconds
            if seconds <= 0 or (not merging and spec['minSeconds'] is not None and seconds < spec['minSeconds']) or (spec['maxSeconds'] is not None and seconds > spec['maxSeconds']):
                raise ValueError('A selected sample does not meet this model’s duration requirements.')
            if for_execution and spec['transcript'] == 'required' and (not text or not confirmed):
                raise ValueError('Review and confirm the transcript for every selected sample.')
            if for_execution and text and not confirmed:
                raise ValueError('Confirm the reference transcript before using it.')
            files[asset_id] = wav
        prepared.append({'asset_id': asset_id, 'name': asset['name'], 'transcript': text,
                         'confirmed': confirmed, 'selected': enabled, 'duration': seconds,
                         'content_hash': asset['content_hash']})
    if (spec['minTotalSeconds'] is not None and total < spec['minTotalSeconds']) or (spec['maxTotalSeconds'] is not None and total > spec['maxTotalSeconds']):
        raise ValueError('The selected audio duration does not meet this model’s requirements.')
    if merging:
        if total > 600 or (spec['minSeconds'] is not None and total < spec['minSeconds']) or (spec['maxSeconds'] is not None and total > spec['maxSeconds']):
            raise ValueError('The merged reference duration does not meet this model’s duration requirements.')
        texts = [sample['transcript'] for sample in prepared if sample['selected']]
        if for_execution and any(texts) and not all(texts):
            raise ValueError('Provide and confirm text for every merged clip, or leave all transcripts empty when optional.')
    return spec, prepared, files


def combined_reference(samples: list[dict], files: dict[str, bytes]) -> tuple[bytes, str]:
    """Concatenate normalized references in selection order without altering originals."""
    selected = [sample for sample in samples if sample['selected']]
    text = '\n'.join(sample['transcript'] for sample in selected).strip()
    if len(selected) == 1:
        return files[selected[0]['asset_id']], text
    output = BytesIO()
    with wave.open(output, 'wb') as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        for sample in selected:
            with wave.open(BytesIO(files[sample['asset_id']]), 'rb') as source:
                target.writeframesraw(source.readframes(source.getnframes()))
    return output.getvalue(), text
