# SPDX-License-Identifier: Apache-2.0
"""Offline FLUX.2 Klein CUDA Worker using the shared image JSON contract."""
from __future__ import annotations

import asyncio
import base64
import binascii
import gc
import io
import hashlib
import json
import math
from pathlib import Path
import re
import threading

from .protocol import ModelWorkerError


class CudaFlux2KleinAdapter:
    KLEIN_9B = 'black-forest-labs/FLUX.2-klein-9B'
    KLEIN_9B_REVISION = '92196c8e11f7b6cf2b7493e037d8c5345c559216'

    @classmethod
    def validate_checkpoint(cls, checkpoint):
        if checkpoint.upstream_id == 'black-forest-labs/FLUX.2-klein-4B':
            return
        if (checkpoint.upstream_id == cls.KLEIN_9B
                and checkpoint.repo_id == cls.KLEIN_9B
                and checkpoint.revision == cls.KLEIN_9B_REVISION):
            return
        raise ModelWorkerError('Unsupported CUDA Klein checkpoint identity', code='model_not_supported')

    @classmethod
    def scheduler_options(cls, checkpoint):
        if checkpoint.upstream_id != cls.KLEIN_9B:
            return {}
        # Official fixed-revision configuration omitted from the existing weight
        # distribution. Ship it with the signed Runtime; never fetch at inference.
        data = Path(__file__).with_name('flux2_klein_9b_scheduler.json').read_bytes()
        if hashlib.sha256(data).hexdigest() != '067afb012cef64553a763447d1efd93daeffcc0123ca7e25b09f8de20b90762e':
            raise ModelWorkerError('Klein scheduler configuration mismatch', code='runtime_not_ready', status_code=503)
        from diffusers import FlowMatchEulerDiscreteScheduler
        return {'scheduler': FlowMatchEulerDiscreteScheduler.from_config(json.loads(data))}

    def __init__(self, context):
        self.context = context
        self.pipeline = None
        self.checkpoint = None
        self.lock = asyncio.Lock()
        self.events = {}
        self.stopping = False

    async def start(self):
        self.stopping = False

    def cancel(self, request_id):
        if event := self.events.get(request_id):
            event.set()

    @staticmethod
    def check_cancel(event):
        if event.is_set():
            raise ModelWorkerError('Image generation cancelled', code='request_cancelled', status_code=499)

    async def stop(self):
        self.stopping = True
        for event in self.events.values():
            event.set()
        async with self.lock:
            self.pipeline = None
            self.checkpoint = None
            gc.collect()
            import torch
            torch.cuda.empty_cache()

    @staticmethod
    def parameters(payload):
        prompt = str(payload.get('prompt') or '').strip()
        if not 1 <= len(prompt) <= 8192:
            raise ValueError('prompt must contain 1-8192 characters')
        width, height = map(int, str(payload.get('size') or '1024x1024').lower().split('x'))
        if not all(256 <= n <= 2048 and n % 32 == 0 for n in (width, height)):
            raise ValueError('dimensions must be 256-2048 and divisible by 32')
        steps = int(payload.get('num_inference_steps', payload.get('steps', 4)))
        guidance = float(payload.get('guidance', payload.get('guidance_scale', 1.0)))
        seed = int(payload.get('seed', 0))
        if not 1 <= steps <= 50 or not math.isfinite(guidance) or not 0 <= guidance <= 20 or not 0 <= seed < 2**32:
            raise ValueError('steps, guidance, or seed is out of range')
        if str(payload.get('quantization', 'bf16')).lower() not in {'none', 'bf16'}:
            raise ValueError('CUDA Klein currently supports bf16 only')
        fmt = str(payload.get('outputFormat', payload.get('output_format', 'png'))).lower()
        if fmt not in {'png', 'jpeg', 'webp'}:
            raise ValueError('output format must be png, jpeg, or webp')
        return prompt, width, height, steps, guidance, seed, fmt

    @staticmethod
    def references(payload):
        from PIL import Image, UnidentifiedImageError
        values = payload.get('imageDataUrls', payload.get('image_data_urls', []))
        if not isinstance(values, list) or not 1 <= len(values) <= 4:
            raise ValueError('image editing requires one to four imageDataUrls')
        images = []
        for value in values:
            if not isinstance(value, str) or len(value) > 35 * 1024 * 1024:
                raise ValueError('reference image is too large or invalid')
            match = re.fullmatch(r'data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)', value)
            if not match:
                raise ValueError('reference images must be PNG, JPEG, or WebP data URLs')
            try:
                content = base64.b64decode(match[2], validate=True)
                if not content or len(content) > 25 * 1024 * 1024:
                    raise ValueError('reference image is empty or too large')
                with Image.open(io.BytesIO(content)) as image:
                    if image.width * image.height > 16777216:
                        raise ValueError('reference image exceeds 16 megapixels')
                    images.append(image.convert('RGB'))
            except (binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
                raise ValueError('invalid reference image') from error
        return images

    async def invoke(self, request):
        if self.stopping:
            raise ModelWorkerError('Worker is stopping', code='worker_stopping', status_code=503)
        if request.request_id in self.events:
            raise ModelWorkerError('Request already active', code='request_conflict', status_code=409)
        if request.operation not in {'image_generation', 'image_edit'}:
            raise ModelWorkerError('Unsupported operation', code='operation_not_supported')
        payload = dict(request.payload)
        try:
            prompt, width, height, steps, guidance, seed, fmt = self.parameters(payload)
            references = self.references(payload) if request.operation == 'image_edit' else None
        except (TypeError, ValueError, OverflowError) as error:
            raise ModelWorkerError(str(error), code='invalid_request') from error
        checkpoint = self.context.checkpoint_for(str(payload.get('model') or ''))
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError('Model checkpoint is not installed', code='model_unavailable', status_code=503)
        self.validate_checkpoint(checkpoint)
        event = threading.Event()
        self.events[request.request_id] = event
        loop = asyncio.get_running_loop()

        def report(phase, current):
            if request.progress:
                # Wait for the small Host-owned status update; do not enqueue
                # unbounded callbacks or let progress outlive the request.
                asyncio.run_coroutine_threadsafe(request.progress({
                    'phase': phase, 'current': current, 'total': steps}), loop).result()

        def generate():
            import torch
            from diffusers import Flux2KleinPipeline
            self.check_cancel(event)
            if self.checkpoint != checkpoint.path:
                self.pipeline = None
                self.checkpoint = None
                gc.collect()
                torch.cuda.empty_cache()
                report('loading', 0)
                self.pipeline = Flux2KleinPipeline.from_pretrained(
                    str(checkpoint.path), torch_dtype=torch.bfloat16,
                    local_files_only=True, **self.scheduler_options(checkpoint)).to('cuda')
                self.checkpoint = checkpoint.path
            self.check_cancel(event)

            def step_end(pipeline, step, timestep, kwargs):
                self.check_cancel(event)
                report('generating', step + 1)
                return kwargs

            image = self.pipeline(prompt=prompt, width=width, height=height,
                num_inference_steps=steps, guidance_scale=guidance,
                generator=torch.Generator('cuda').manual_seed(seed),
                callback_on_step_end=step_end, **({'image': references} if references else {})).images[0]
            self.check_cancel(event)
            buffer = io.BytesIO()
            image.convert('RGB').save(buffer, format={'png':'PNG', 'jpeg':'JPEG', 'webp':'WEBP'}[fmt])
            return buffer.getvalue()

        try:
            async with self.lock:
                self.check_cancel(event)
                task = asyncio.create_task(asyncio.to_thread(generate))
                try:
                    content = await asyncio.shield(task)
                except asyncio.CancelledError:
                    event.set()
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
            if request.progress:
                await request.progress({'phase':'complete', 'current':steps, 'total':steps})
            encoded = base64.b64encode(content).decode('ascii')
            return {'created':0, 'data':[{'b64_json':encoded}],
                    'image':{'dataUrl':f'data:image/{fmt};base64,{encoded}',
                             'size':f'{width}x{height}', 'format':fmt, 'quality':payload.get('quality','auto')},
                    'model':payload.get('model'), 'seed':seed, 'quantization':'bf16'}
        finally:
            self.events.pop(request.request_id, None)


def create_adapter(context):
    return CudaFlux2KleinAdapter(context)
