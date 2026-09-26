"""Offline, independent Qwen ASR evidence checks. Never synthesizes replacement audio."""
from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from pathlib import Path

from .state import atomic_write_json


def discover_checkpoint() -> Path:
    root = Path.home() / 'Library/Caches/AI2Apps/shared/checkpoint-cache-v1/snapshots'
    candidates = []
    for config in root.glob('*/*/config.json'):
        try:
            value = json.loads(config.read_text())
            weights = list(config.parent.glob('*.safetensors'))
            if value.get('model_type') == 'qwen3_asr' and weights:
                candidates.append((sum(p.stat().st_size for p in weights), str(config.parent)))
        except (OSError, ValueError):
            continue
    if not candidates:
        raise ValueError('No local shared Qwen3-ASR checkpoint; no download was attempted')
    return Path(min(candidates)[1])


def normalized_text(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold()
                   if unicodedata.category(c)[0] in {'L', 'N'})


def compare_text(expected: str, transcript: str) -> dict:
    left, right = normalized_text(expected), normalized_text(transcript)
    if not left:
        raise ValueError('Expected speech text must not be empty')
    return {'expected': expected, 'transcript': transcript,
            'normalizedMatch': left == right,
            'status': 'matched' if left == right else 'needs-listening-review'}


def check_audio(run_dir: Path, audio: Path, checkpoint: Path, expected: str,
                language: str = 'Chinese') -> dict:
    run_dir, audio, checkpoint = run_dir.resolve(), audio.resolve(), checkpoint.resolve()
    if not audio.is_relative_to(run_dir) or not audio.is_file():
        raise ValueError('Audio must be an existing evidence file inside this Run')
    if audio.stat().st_size > 100 * 1024 * 1024:
        raise ValueError('Audio exceeds 100 MiB evidence limit')
    capture_manifest = audio.parent / 'capture.json'
    if capture_manifest.exists():
        capture = json.loads(capture_manifest.read_text())
        if capture.get('status') != 'captured' or capture.get('scope') != 'application-only':
            raise ValueError('Capture is incomplete or not application-only; do not judge TTS content')
    output = audio.with_name(audio.name + '.asr.json')
    if output.exists():
        raise ValueError('ASR evidence already exists; refusing to overwrite')
    config = json.loads((checkpoint / 'config.json').read_text())
    if config.get('model_type') != 'qwen3_asr':
        raise ValueError('Only an explicit local Qwen3-ASR checkpoint is allowed')
    if not list(checkpoint.glob('*.safetensors')):
        raise ValueError('Local Qwen3-ASR weights are missing')
    normalized = normalized_text(expected)
    if not normalized or len(expected) > 12000:
        raise ValueError('Expected text must contain 1–12000 characters')
    # No network fallback or automatic checkpoint downloads.
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    import numpy as np
    import soundfile as sf
    from mlx_audio.stt.utils import load_model

    info = sf.info(str(audio))
    if info.frames <= 0 or info.samplerate <= 0 or info.duration > 180:
        raise ValueError('Audio must contain between 0 and 180 seconds of samples')
    samples, rate = sf.read(str(audio), dtype='float32', always_2d=True)
    if not np.isfinite(samples).all():
        raise ValueError('Audio contains invalid samples')
    rms = float(np.sqrt(np.mean(samples ** 2)))
    peak = float(np.max(np.abs(samples)))
    metrics = {'durationSeconds': len(samples) / rate, 'sampleRate': rate,
               'channels': samples.shape[1], 'rms': rms, 'peak': peak,
               'clippingFraction': float(np.mean(np.abs(samples) >= 0.999))}
    result = {'schemaVersion': 1, 'audio': str(audio.relative_to(run_dir)),
              'audioSha256': hashlib.sha256(audio.read_bytes()).hexdigest(),
              'checkpoint': str(checkpoint), 'metrics': metrics,
              'checkpointConfigSha256': hashlib.sha256((checkpoint / 'config.json').read_bytes()).hexdigest(),
              'scope': 'Generated audio content only; speaker playback and voice quality are not verified'}
    if peak < 0.0001:
        result.update(status='failed', reason='silent-audio')
    else:
        model = load_model(str(checkpoint))
        # Intentionally do not supply expected speech as an ASR prompt.
        transcript = model.generate(str(audio), language=language, max_tokens=2048).text
        comparison = compare_text(expected, transcript)
        result.update(status='content-matched' if comparison['normalizedMatch'] else 'needs-listening-review',
                      comparison=comparison)
    atomic_write_json(output, result)
    evidence = [str(audio.relative_to(run_dir)), str(output.relative_to(run_dir))]
    if capture_manifest.exists():
        evidence.append(str(capture_manifest.relative_to(run_dir)))
    return {**result, 'evidence': evidence}
