# SPDX-License-Identifier: Apache-2.0
"""Offline duplex smoke/benchmark: recordings in, continuous model frames out.

Run from the Git root: python -m ai2apps.model_worker.haru_duplex_cli --help.
This does not request a microphone or start an unauthenticated model server.
"""
import argparse
import asyncio
import json
import hashlib
from pathlib import Path
import platform
import time

import numpy as np

from .haru_duplex import CHECKPOINT_REVISION, UPSTREAM_COMMIT, HaruDuplexBackend, FRAME_SAMPLES, SAMPLE_RATE
from .haru_mlx.audio import load_audio, prepare_reference, save_audio
from .haru_mlx.prompt import card_templates, render_card


async def benchmark(args):
    audio = load_audio(args.input)
    if args.input_seconds is not None:
        audio = audio[:int(args.input_seconds * SAMPLE_RATE)]
    reference = prepare_reference(load_audio(args.reference_voice))
    if args.tail_seconds:
        audio = np.concatenate([audio, np.zeros(int(args.tail_seconds * SAMPLE_RATE), dtype=np.float32)])
    if not len(audio):
        raise ValueError('Input recording is empty')
    audio = np.pad(audio, (0, (-len(audio)) % FRAME_SAMPLES))
    frames = len(audio) // FRAME_SAMPLES
    if frames + 1 > 27000:
        raise ValueError('Input exceeds the one-hour session budget')
    template = card_templates()['templates'][args.language]
    prompt = render_card({'name': 'Haru', 'persona': args.persona}, template)
    backend = HaruDuplexBackend(args.checkpoint, quantize=8 if args.quantize == '8' else None)
    digest = hashlib.sha256()
    with (backend.checkpoint / 'model.safetensors').open('rb') as weights:
        for chunk in iter(lambda: weights.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    outputs, timings, texts, indices = [], [], [], []
    started = time.perf_counter()
    try:
        await backend.load()
        load_seconds = time.perf_counter() - started
        first = await backend.start(system_prompt=prompt, reference_audio=reference, seed=args.seed,
                                    max_frames=frames + 1, speak_first=args.speak_first)
        outputs.append(first.audio)
        texts.append(first.text)
        indices.append(first.index)
        overlaps = 0
        stream_started = time.perf_counter()
        for i, block in enumerate(audio.reshape(-1, FRAME_SAMPLES)):
            if args.realtime:
                await asyncio.sleep(max(0, stream_started + i * FRAME_SAMPLES / SAMPLE_RATE - time.perf_counter()))
            frame = await backend.step(block)
            outputs.append(frame.audio)
            timings.append(frame.compute_seconds)
            texts.append(frame.text)
            indices.append(frame.index)
            if np.sqrt(np.mean(block ** 2)) > .01 and np.sqrt(np.mean(frame.audio ** 2)) > .01:
                overlaps += 1
        import mlx.core as mx
        peak = mx.get_peak_memory()
        report = {
            'model': 'higurashi-ai/Haru-4B', 'upstream_commit': UPSTREAM_COMMIT,
            'checkpoint_revision_expected': CHECKPOINT_REVISION, 'checkpoint_path': str(backend.checkpoint),
            'checkpoint_sha256': digest.hexdigest(), 'device': mx.device_info(),
            'host': platform.platform(), 'machine': platform.machine(), 'precision': args.quantize,
            'sample_rate': SAMPLE_RATE, 'frame_samples': FRAME_SAMPLES,
            'input_frames': frames, 'output_frames': len(outputs),
            'sequential_frames': indices == list(range(frames + 1)),
            'model_load_seconds': load_seconds, 'prefill_seconds': first.compute_seconds,
            'steady_frame_p50_ms': float(np.percentile(timings, 50) * 1000),
            'steady_frame_p95_ms': float(np.percentile(timings, 95) * 1000),
            'steady_compute_rtf': float(sum(timings) / (len(audio) / SAMPLE_RATE)),
            'frames_over_133ms': sum(t > FRAME_SAMPLES / SAMPLE_RATE for t in timings),
            'paced_to_realtime': args.realtime, 'overlap_non_silent_frames': overlaps,
            'mlx_peak_bytes': peak, 'text': ''.join(texts),
            'input_kind': 'offline_recording', 'live_microphone_verified': False,
            'tool_calls': False, 'async_result_injection': False,
        }
        save_audio(args.output, np.concatenate(outputs))
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
        return report
    finally:
        await backend.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True, help='Installed local checkpoint directory; no implicit downloads')
    parser.add_argument('--input', required=True)
    parser.add_argument('--reference-voice', required=True, help='A voice reference you are authorized to use')
    parser.add_argument('--output', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--language', choices=tuple(card_templates()['templates']), default='zh')
    parser.add_argument('--persona', default='你是一位友好、简洁的中文对话伙伴。')
    parser.add_argument('--quantize', choices=('none', '8'), default='8')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--input-seconds', type=float)
    parser.add_argument('--tail-seconds', type=float, default=5)
    parser.add_argument('--speak-first', action='store_true')
    parser.add_argument('--realtime', action='store_true', help='Feed recorded frames at the live audio cadence')
    args = parser.parse_args()
    if args.tail_seconds < 0 or (args.input_seconds is not None and args.input_seconds <= 0):
        parser.error('Audio durations must be positive (tail may be zero)')
    asyncio.run(benchmark(args))


if __name__ == '__main__':
    main()
