"""Fixed-audio H3 portrait generation and bounded-memory continuation.

Experimental until the corresponding signed model capability is enabled.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageOps
from scipy.signal import resample_poly

from .avatar_timeline import plan_h3_windows
from .avatar_media import save_segment, join_segments

DEFAULT_PROMPT = (
    'A continuous fixed-camera portrait shot. The person speaks naturally with '
    'precise lip movements matching the speech, subtle blinking and small head '
    'movements. Preserve identity, clothing, lighting and background. No subtitles.'
)


def _digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def generate_avatar(pipeline, image_path, audio_path, output_path, *,
                    width=512, height=512, steps=50, seed=42, prompt=DEFAULT_PROMPT,
                    window_frames=192, context_frames=39, checkpoint_identity='',
                    progress=None, cancelled=None, cache_root=None, context_image_anchor=False):
    """Generate sequential segments; keep only one window resident at a time.

    Resume requires an exact checkpoint identity and same work directory. A
    damaged/missing segment invalidates that segment and all successors.
    """
    output = Path(output_path)
    if width % 32 or height % 32 or min(width, height) < 256:
        raise ValueError('Avatar dimensions must be multiples of 32 and at least 256')
    info = sf.info(str(audio_path))
    if not 0 < info.frames <= info.samplerate * 60 or info.channels not in (1, 2):
        raise ValueError('Expected mono/stereo audio of at most 60 seconds')
    pcm, rate = sf.read(str(audio_path), dtype='float32', always_2d=True)
    if not np.isfinite(pcm).all():
        raise ValueError('Audio contains non-finite samples')
    windows = plan_h3_windows(len(pcm), rate, window_frames=window_frames, context_frames=context_frames)
    divisor = math.gcd(rate, 32000)
    conditioning = resample_poly(pcm, 32000 // divisor, rate // divisor, axis=0)
    if conditioning.shape[1] == 1:
        conditioning = np.repeat(conditioning, 2, axis=1)
    conditioning = conditioning.T
    with Image.open(image_path) as source:
        if source.width * source.height > 40_000_000:
            raise ValueError('Image exceeds 40 million pixels')
        picture = ImageOps.fit(ImageOps.exif_transpose(source).convert('RGB'), (width, height))
    identity = dict(image=_digest(image_path), audio=_digest(audio_path),
                    checkpoint=checkpoint_identity, width=width, height=height,
                    steps=steps, seed=seed, prompt=prompt, window=window_frames,
                    context=context_frames, context_image_anchor=bool(context_image_anchor), implementation='h3-avatar-v1',
                    code={name: _digest(Path(__file__).with_name(name)) for name in
                          ('avatar.py', 'avatar_timeline.py', 'avatar_media.py', 'staged_pipeline.py', 'pipeline.py')})
    signature = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if cache_root is None:
        work = output.parent / (output.stem + '.segments')
    else:
        root = Path(cache_root)
        root.mkdir(parents=True, exist_ok=True)
        work = root / signature
        if work.is_symlink():
            raise ValueError('Avatar cache cannot be a symbolic link')
        # Private intermediates survive Host request cleanup. Retain at most four
        # recent jobs; each job is bounded by the public 60-second contract.
        old = sorted((p for p in root.iterdir() if p != work and not p.is_symlink()
                      and p.is_dir() and len(p.name) == 64
                      and all(c in '0123456789abcdef' for c in p.name)),
                     key=lambda p: p.stat().st_mtime, reverse=True)
        for index, path in enumerate(old):
            if index >= 3 or time.time() - path.stat().st_mtime > 7 * 86400:
                shutil.rmtree(path)
    work.mkdir(parents=True, exist_ok=True)
    import os
    os.utime(work, None)
    previous = signature
    context = None
    reusable = bool(checkpoint_identity)
    segments = []
    for window in windows:
        if cancelled and cancelled():
            raise InterruptedError('Avatar generation cancelled')
        clip = work / f'{window.index:04d}.mp4'
        tail = work / f'{window.index:04d}.npy'
        receipt = work / f'{window.index:04d}.json'
        cached = None
        if reusable and all(p.exists() for p in (clip, tail, receipt)):
            try:
                candidate = json.loads(receipt.read_text())
                if candidate['previous'] == previous and candidate['clip'] == _digest(clip) and candidate['tail'] == _digest(tail):
                    cached = candidate
            except (ValueError, KeyError, OSError):
                pass
        if cached is None:
            reusable = False
            start, stop, padding = window.conditioning_span(conditioning.shape[1])
            audio = np.pad(conditioning[:, start:stop], ((0, 0), (0, padding)))
            result = pipeline(
                prompt, duration_seconds=window.generate_frames / 24,
                num_inference_steps=steps, seed=(seed + window.index) % 2**64,
                images=[picture] if context is None or context_image_anchor else None,
                keyframe_anchors=('first',) if context is None else (('last',) if context_image_anchor else ()),
                context_image_anchor=bool(context_image_anchor and context is not None),
                height=height, width=width, driving_audio=audio,
                video_context_latents=context, return_context_frames=context_frames, fast=False, fast_max=False, cancelled=cancelled,
            )
            if result.fps != 24 or len(result.video) != window.generate_frames:
                raise ValueError('H3 returned unexpected frame count or FPS')
            if not np.array_equal(result.audio, audio):
                raise ValueError('Fixed driving audio changed during inference')
            # The VAE decodes 17-frame chunks with a five-frame future overlap.
            # Replace the previous window's provisional final five frames with
            # this window's already-blended context tail. No second crossfade.
            overlap = 5
            begin = window.context_frames - (overlap if window.index else 0)
            end = window.context_frames + window.keep_frames
            if window.index + 1 < len(windows):
                end -= overlap
            frames = result.video[begin:end]
            temp = clip.with_name(clip.stem + '.partial.mp4')
            save_segment(temp, frames, 24)
            temp.replace(clip)
            context = np.array(result.continuation_latents, copy=True)
            expected = (1, 24, (context_frames - 5) // 17 * 5 + 2, height // 16, width // 16)
            if context.shape != expected or not np.isfinite(context).all():
                raise ValueError('H3 returned invalid continuation latents')
            np.save(tail, context, allow_pickle=False)
            cached = dict(previous=previous, clip=_digest(clip), tail=_digest(tail),
                          frames=len(frames), model_seconds=result.total_seconds)
            receipt.write_text(json.dumps(cached, indent=2))
            del result, frames
        else:
            context = np.load(tail, allow_pickle=False)
        previous = hashlib.sha256(json.dumps(cached, sort_keys=True).encode()).hexdigest()
        segments.append(clip)
        if progress:
            progress(window.index + 1, len(windows))
    if cancelled and cancelled():
        raise InterruptedError('Avatar generation cancelled')
    join_segments(segments, audio_path, output, cancelled=cancelled)
    summary = dict(identity=identity, segments=len(windows), frames=windows[-1].output_end,
                   source_samples=len(pcm), source_rate=rate, output_sha256=_digest(output))
    (work / 'result.json').write_text(json.dumps(summary, indent=2))
    return summary


def generate_avatar_window(pipeline, image_path, audio_path, output_path, state_path, *,
                           index, previous_state=None, width=512, height=512,
                           steps=50, seed=42, prompt=DEFAULT_PROMPT,
                           window_frames=192, context_frames=39, cancelled=None):
    """Generate one globally planned motion window and export its continuation.

    The full motion window is retained for face tracking and mask smoothing.
    The returned source interval excludes provisional VAE overlap frames;
    mouth refinement uses its corresponding absolute audio frame interval.
    """
    if width % 32 or height % 32 or min(width, height) < 256:
        raise ValueError('Invalid avatar window dimensions')
    info = sf.info(str(audio_path))
    if info.frames <= 0 or info.channels not in (1, 2):
        raise ValueError('Expected nonempty mono/stereo audio')
    windows = plan_h3_windows(info.frames, info.samplerate,
                             window_frames=window_frames, context_frames=context_frames)
    if type(index) is not int or not 0 <= index < len(windows):
        raise ValueError('Invalid avatar window index')
    window = windows[index]
    expected = (1, 24, (context_frames - 5) // 17 * 5 + 2, height // 16, width // 16)
    context = None
    if index:
        if previous_state is None or Path(previous_state).is_symlink():
            raise ValueError('Continuation requires a regular prior state')
        if Path(previous_state).stat().st_size > 32 * 1024 * 1024:
            raise ValueError('Continuation state exceeds size limit')
        context = np.load(previous_state, allow_pickle=False, mmap_mode="r")
        if context.shape != expected or context.dtype.kind != 'f' or not np.isfinite(context).all():
            raise ValueError('Invalid continuation state')
    elif previous_state is not None:
        raise ValueError('First window cannot have continuation state')
    if cancelled and cancelled():
        raise InterruptedError('Avatar generation cancelled')
    pcm, rate = sf.read(str(audio_path), dtype='float32', always_2d=True)
    if not np.isfinite(pcm).all():
        raise ValueError('Audio contains non-finite samples')
    divisor = math.gcd(rate, 32000)
    conditioning = resample_poly(pcm, 32000 // divisor, rate // divisor, axis=0)
    if conditioning.shape[1] == 1:
        conditioning = np.repeat(conditioning, 2, axis=1)
    conditioning = conditioning.T
    start, stop, padding = window.conditioning_span(conditioning.shape[1])
    audio = np.pad(conditioning[:, start:stop], ((0, 0), (0, padding)))
    del pcm, conditioning
    with Image.open(image_path) as source:
        if source.width * source.height > 40_000_000:
            raise ValueError('Image exceeds 40 million pixels')
        picture = ImageOps.fit(ImageOps.exif_transpose(source).convert('RGB'), (width, height))
    is_reference = str(pipeline.config.partition).lower() in {'ref2va', 'ref'}
    if is_reference:
        from .reference_media import ReferenceInput
        visual = dict(references=(ReferenceInput('image', (picture,)),))
    else:
        visual = dict(images=[picture], keyframe_anchors=('first',) if context is None else ('last',),
                      context_image_anchor=context is not None)
    result = pipeline(
        prompt, duration_seconds=window.generate_frames / 24,
        num_inference_steps=steps, seed=(seed + index) % 2**64,
        **visual,
        height=height, width=width, driving_audio=audio,
        video_context_latents=context, return_context_frames=context_frames,
        fast=False, fast_max=False, cancelled=cancelled,
    )
    if result.fps != 24 or len(result.video) != window.generate_frames:
        raise ValueError('H3 returned unexpected frame count or FPS')
    if not np.array_equal(result.audio, audio):
        raise ValueError('Fixed driving audio changed during inference')
    context = np.array(result.continuation_latents, copy=True)
    if context.shape != expected or context.dtype.kind != 'f' or not np.isfinite(context).all():
        raise ValueError('H3 returned invalid continuation state')
    if cancelled and cancelled():
        raise InterruptedError('Avatar generation cancelled')
    save_segment(Path(output_path), result.video, 24)
    with Path(state_path).open('wb') as handle:
        np.save(handle, context, allow_pickle=False)
    begin = window.context_frames - (5 if index else 0)
    end = window.context_frames + window.keep_frames - (5 if index + 1 < len(windows) else 0)
    return dict(index=index, source_start=begin, source_end=end,
                start_frame=window.start_frame + begin, end_frame=window.start_frame + end,
                segments=len(windows), motion_frames=window.generate_frames,
                model_seconds=result.total_seconds)
