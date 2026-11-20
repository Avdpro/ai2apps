"""Bounded frozen-scene camera-video refinement, not general text-to-video.

Modified by AI2Apps 2026-10-09. Powered by MiniMax H3.
"""
import asyncio
import gc
import json
import threading
from fractions import Fraction

import av
import mlx.core as mx
import numpy as np
from PIL import Image, ImageOps
from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError
from meridian_pipeline import create_pipeline
from minimax_h3_mlx.reference_media import ReferenceInput

FRAME_COUNTS=(73,90,107,124,141,158,175,243)


def integer(payload, name, default):
    value = payload.get(name, default)
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        value = int(value)
    if type(value) is not int:
        raise ModelWorkerError(f'{name} must be an integer', status_code=422)
    return value


def reference_paths(request):
    parts = request.parts or {}
    if 'image' in parts and 'camera_video' in parts:
        return parts['image'].path, parts['camera_video'].path
    descriptors = request.payload.get('reference_parts')
    if isinstance(descriptors, str):
        try:
            descriptors = json.loads(descriptors)
        except ValueError as exc:
            raise ModelWorkerError('Invalid reference_parts JSON', status_code=422) from exc
    if not isinstance(descriptors, list) or len(descriptors) != 2:
        raise ModelWorkerError('One source image and one camera video are required', status_code=422)
    selected = {}
    for item in descriptors:
        if not isinstance(item, dict) or item.get('kind') not in {'image','video'}:
            raise ModelWorkerError('Only image/video reference parts are supported', status_code=422)
        kind, name = item['kind'], item.get('part_name')
        if kind in selected or name not in parts:
            raise ModelWorkerError('Missing or duplicate reference part', status_code=422)
        selected[kind] = parts[name].path
    return selected['image'], selected['video']


def read_references(image_path, video_path, num_frames=73):
    if num_frames not in FRAME_COUNTS:
        raise ValueError('Unsupported Meridian frame count')
    with Image.open(image_path) as image:
        if image.width * image.height > 16_000_000:
            raise ValueError('Source image exceeds 16 megapixels')
        source = ImageOps.exif_transpose(image).convert('RGB')
    frames = []
    with av.open(str(video_path)) as container:
        stream = next((s for s in container.streams if s.type == 'video'), None)
        if stream is None:
            raise ValueError('Camera reference has no video stream')
        if not 32 <= stream.width <= 768 or not 32 <= stream.height <= 768:
            raise ValueError('Camera reference axes must be between 32 and 768')
        if stream.width % 32 or stream.height % 32:
            raise ValueError('Camera reference axes must be multiples of 32')
        if stream.average_rate != Fraction(24):
            raise ValueError('Camera reference must be 24 fps')
        size = (stream.width, stream.height)
        for frame in container.decode(stream):
            if len(frames) >= num_frames or (frame.width, frame.height) != size:
                raise ValueError(f'Camera reference must contain exactly {num_frames} equal-sized frames')
            frames.append(frame.to_image().convert('RGB'))
    if len(frames) != num_frames:
        raise ValueError(f'Camera reference must contain exactly {num_frames} frames')
    # Fit without stretching or cropping source content. The Host must render
    # geometry using this same padded canvas.
    source = ImageOps.pad(source, size, method=Image.Resampling.LANCZOS, color=(0, 0, 0))
    return (ReferenceInput('video', (source,) * num_frames), ReferenceInput('video', tuple(frames)))


def write_video(path, video, num_frames=73):
    if num_frames not in FRAME_COUNTS or video.dtype != np.uint8 or video.ndim != 4 or video.shape[0] != num_frames or video.shape[-1] != 3:
        raise ValueError('Invalid Meridian output')
    with av.open(str(path), 'w', format='mp4') as container:
        container.metadata['comment'] = 'AI-generated camera motion. Powered by MiniMax H3; Meridian by Viggle.'
        stream = container.add_stream('libx264', rate=24)
        stream.width, stream.height = video.shape[2], video.shape[1]
        stream.pix_fmt = 'yuv420p'
        stream.options = {'crf': '18', 'preset': 'fast'}
        for index, rgb in enumerate(video):
            frame = av.VideoFrame.from_ndarray(rgb, format='rgb24')
            frame.pts, frame.time_base = index, Fraction(1, 24)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


class MeridianAdapter:
    def __init__(self, context):
        self.context = context
        self.pipeline = None

    async def start(self):
        pass

    async def stop(self):
        self.pipeline = None
        gc.collect()
        mx.clear_cache()

    async def invoke(self, request):
        if request.operation != 'video_generation':
            raise ModelWorkerError('Only camera-video refinement is supported', status_code=422)
        payload = request.payload
        checkpoint = self.context.checkpoint_for(payload.get('model'))
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError('Meridian checkpoint is not installed', status_code=503)
        base_checkpoint = self.context.checkpoint_for('ai2apps.model.minimax-h3/fl2va-8bit')
        if base_checkpoint is None or base_checkpoint.path is None:
            raise ModelWorkerError('The required H3 Package FL2VA 8-bit checkpoint is not installed', status_code=503)
        width, height = integer(payload, 'width', 768), integer(payload, 'height', 768)
        seed = integer(payload, 'seed', 42)
        if (type(width) is not int or type(height) is not int or
                min(width, height) < 256 or max(width, height) > 768 or width % 32 or height % 32):
            raise ModelWorkerError('Output axes must be multiples of 32 between 256 and 768', status_code=422)
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ModelWorkerError('Seed must be an unsigned 32-bit integer', status_code=422)
        num_frames=integer(payload,'num_frames',73)
        if integer(payload, 'steps', 3) != 3 or num_frames not in FRAME_COUNTS:
            raise ModelWorkerError('Meridian requires 3 steps and a supported frame count: '+str(FRAME_COUNTS), status_code=422)
        if str(payload.get('prompt', '')).strip():
            raise ModelWorkerError('Meridian uses fixed trained embeddings, not a text prompt', status_code=422)
        for field in ('duration', 'seconds'):
            if field in payload:
                try:
                    duration = float(payload[field])
                except (TypeError, ValueError) as exc:
                    raise ModelWorkerError('Invalid duration', status_code=422) from exc
                if not abs(duration - num_frames/24) < 0.001:
                    raise ModelWorkerError('Meridian duration must match num_frames / 24', status_code=422)
        image_path, video_path = reference_paths(request)
        output = request.output_root / 'meridian.mp4'
        cancelled = threading.Event()

        def generate():
            references = read_references(image_path, video_path, num_frames)
            if abs(width / height - references[1].frames[0].width / references[1].frames[0].height) > 0.05:
                raise ValueError('Output and camera-reference aspect ratios must match')
            mx.set_cache_limit(8 * 1024**3)
            if self.pipeline is None:
                self.pipeline = create_pipeline(checkpoint.path, base_checkpoint.path)
            self.pipeline.meridian_num_frames=num_frames
            result = self.pipeline('', duration_seconds=num_frames/24, height=height, width=width,
                num_inference_steps=3, seed=seed, references=references, fast=False,
                fused_kernels=False, optimize_denoise=True, clear_step_cache=True,
                verbose=False, cancelled=cancelled.is_set)
            if cancelled.is_set():
                raise InterruptedError('Meridian request cancelled')
            write_video(output, result.video, num_frames)
            gc.collect()
            mx.clear_cache()

        task = asyncio.create_task(asyncio.to_thread(generate))
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled.set()
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if not task.cancelled():
                task.exception()
            raise
        except ValueError as exc:
            raise ModelWorkerError(str(exc), status_code=422) from exc
        return ModelWorkerArtifact(output, 'video/mp4', output.name,
            metadata={'frames': num_frames, 'fps': 24, 'attribution': 'Powered by MiniMax H3; Meridian by Viggle',
                      'limitations': '8-bit experimental port; fixed embeddings; camera reference required'})


def create_adapter(context):
    return MeridianAdapter(context)
