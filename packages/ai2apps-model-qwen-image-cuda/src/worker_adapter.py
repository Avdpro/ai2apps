# SPDX-License-Identifier: Apache-2.0
"""Development Qwen Image / Z-Image Worker adapter; not a published Package."""
from __future__ import annotations

import asyncio
import base64
import gc
import io
import math
import threading

from ai2apps.model_worker.protocol import ModelWorkerError

QWEN_IMAGE_21 = 'Qwen/Qwen-Image-2.1'


class CudaImageGenerationAdapter:
    operation = 'image_generation'
    revisions = {'Tongyi-MAI/Z-Image':'04cc4abb7c5069926f75c9bfde9ef43d49423021',
                 'Tongyi-MAI/Z-Image-Turbo':'f332072aa78be7aecdf3ee76d5c247082da564a6',
                 'Qwen/Qwen-Image-2512':'25468b98e3276ca6700de15c6628e51b7de54a26'}

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
    def parameters(payload, upstream):
        z = upstream == 'Tongyi-MAI/Z-Image-Turbo'
        z_base = upstream == 'Tongyi-MAI/Z-Image'
        prompt = payload.get('prompt')
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 8192:
            raise ValueError('prompt must contain 1-8192 characters')
        def integer(value):
            if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
                raise ValueError('integer parameter required')
            return int(value)
        width, height = [integer(n) for n in str(payload.get('size') or '1024x1024').lower().split('x')]
        multiple = 32 if z or z_base else 16
        if not all(256 <= n <= 2048 and n % multiple == 0 for n in (width,height)):
            raise ValueError('unsupported image dimensions')
        steps = integer(payload.get('num_inference_steps',payload.get('steps',9 if z else 30 if z_base else 20)))
        guidance = payload.get('guidance',payload.get('guidance_scale',0. if z else 4.))
        if isinstance(guidance,bool): raise ValueError('guidance must be numeric')
        guidance = float(guidance)
        seed = integer(payload.get('seed',0))
        if not 1 <= steps <= 50 or not math.isfinite(guidance) or not 0 <= guidance <= 20 or not 0 <= seed < 2**32:
            raise ValueError('steps, guidance, or seed is out of range')
        if z and guidance != 0: raise ValueError('Z-Image Turbo requires guidance 0')
        negative = payload.get('negative_prompt', '')
        if not isinstance(negative, str) or len(negative) > 8192:
            raise ValueError('negative_prompt must be a string of at most 8192 characters')
        if z and negative:
            raise ValueError('Z-Image Turbo does not apply negative prompts with guidance 0')
        if str(payload.get('quantization','bf16')).lower() not in {'none','bf16'}:
            raise ValueError('CUDA image generation currently supports bf16 only')
        if payload.get('imageDataUrls') or payload.get('image_data_urls'):
            raise ValueError('This model supports generation only')
        fmt=str(payload.get('outputFormat',payload.get('output_format','png'))).lower()
        if fmt not in {'png','jpeg','webp'}: raise ValueError('unsupported output format')
        return prompt.strip(), width, height, steps, guidance, seed, fmt

    async def invoke(self, request):
        if not self.supports_operation(request.operation):
            raise ModelWorkerError('Unsupported operation', code='operation_not_supported')
        if self.stopping:
            raise ModelWorkerError('Worker is stopping', code='worker_stopping', status_code=503)
        if request.request_id in self.events:
            raise ModelWorkerError('Request already active', code='request_conflict', status_code=409)
        payload = dict(request.payload)
        checkpoint = self.context.checkpoint_for(str(payload.get('model') or ''))
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError('Model checkpoint is not installed', code='model_unavailable', status_code=503)
        expected = self.revisions
        if checkpoint.upstream_id not in expected or checkpoint.repo_id != checkpoint.upstream_id or checkpoint.revision != expected[checkpoint.upstream_id]:
            raise ModelWorkerError('Unsupported checkpoint revision', code='model_not_supported')
        upstream = checkpoint.upstream_id
        try:
            prompt, width, height, steps, guidance, seed, fmt = self.parameters(payload, upstream)
            extra_inputs = self.inputs(payload)
        except (TypeError, ValueError, OverflowError) as error:
            raise ModelWorkerError(str(error), code='invalid_request') from error
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
            factory = self.pipeline_factory(upstream)
            self.check_cancel(event)
            if self.checkpoint != checkpoint.path:
                self.pipeline = None
                self.checkpoint = None
                gc.collect()
                torch.cuda.empty_cache()
                report('loading', 0)
                self.pipeline = factory.from_pretrained(
                    str(checkpoint.path), torch_dtype=torch.bfloat16,
                    local_files_only=True).to('cuda')
                self.checkpoint = checkpoint.path
            self.check_cancel(event)

            def step_end(pipeline, step, timestep, kwargs):
                self.check_cancel(event)
                report('generating', step + 1)
                return kwargs

            render_width, render_height = self.pipeline_dimensions(width, height)
            image = self.pipeline(prompt=prompt, width=render_width, height=render_height,
                num_inference_steps=steps,
                generator=torch.Generator('cuda').manual_seed(seed),
                callback_on_step_end=step_end, **extra_inputs,
                **self.inference_options(upstream, guidance, payload)).images[0]
            self.check_cancel(event)
            if (render_width, render_height) != (width, height):
                from PIL import Image
                image = image.resize((width, height), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            self.output_image(image, fmt).save(
                buffer, format={'png':'PNG', 'jpeg':'JPEG', 'webp':'WEBP'}[fmt])
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

    @staticmethod
    def inference_options(upstream, guidance, payload):
        if upstream == 'Tongyi-MAI/Z-Image-Turbo':
            return {'guidance_scale': guidance}
        negative = str(payload.get('negative_prompt') or '')
        if upstream == 'Tongyi-MAI/Z-Image':
            return {'guidance_scale': guidance, 'negative_prompt': negative,
                    'cfg_normalization': False}
        return {'true_cfg_scale': guidance, 'negative_prompt': negative}

    @staticmethod
    def inputs(payload):
        return {}

    def supports_operation(self, operation):
        return operation == self.operation

    @staticmethod
    def output_image(image, fmt):
        return image.convert('RGB')

    @staticmethod
    def pipeline_dimensions(width, height):
        return width, height

    @staticmethod
    def pipeline_factory(upstream):
        from diffusers import QwenImagePipeline, ZImagePipeline
        return ZImagePipeline if upstream in ('Tongyi-MAI/Z-Image','Tongyi-MAI/Z-Image-Turbo') else QwenImagePipeline


class CudaQwenImageEditAdapter(CudaImageGenerationAdapter):
    operation = 'image_edit'
    revisions = {'Qwen/Qwen-Image-Edit-2511':'6f3ccc0b56e431dc6a0c2b2039706d7d26f22cb9'}

    @staticmethod
    def pipeline_dimensions(width, height):
        # Fixed-seed 512px native edits reproducibly introduced strong texture
        # artifacts; the corresponding 1024px edit preserves the source scene.
        # Keep the public output dimensions while using the verified square
        # working resolution. Other aspect ratios still require quality evals.
        if width == height and width < 1024:
            return 1024, 1024
        return width, height

    @staticmethod
    def parameters(payload, upstream):
        generation = dict(payload)
        generation.pop('imageDataUrls', None)
        generation.pop('image_data_urls', None)
        if 'steps' not in generation and 'num_inference_steps' not in generation:
            generation['steps'] = 30
        if 'guidance' not in generation and 'guidance_scale' not in generation:
            generation['guidance'] = 2.5
        return CudaImageGenerationAdapter.parameters(generation, upstream)

    @staticmethod
    def inputs(payload):
        from ai2apps.model_worker.cuda_image import CudaFlux2KleinAdapter
        references = payload.get('imageDataUrls', payload.get('image_data_urls', []))
        if not isinstance(references, list) or not 1 <= len(references) <= 3:
            raise ValueError('Qwen Image Edit requires one to three reference images')
        return {'image': CudaFlux2KleinAdapter.references(payload)}

    @staticmethod
    def pipeline_factory(upstream):
        from diffusers import QwenImageEditPlusPipeline
        return QwenImageEditPlusPipeline


class CudaQwenImage21Adapter(CudaImageGenerationAdapter):
    revisions = {QWEN_IMAGE_21: 'd26bb61231c349cf6b7896fa83353113880e1ba3'}

    def supports_operation(self, operation):
        return operation in ('image_generation', 'image_edit')

    async def invoke(self, request):
        if self.supports_operation(request.operation):
            references = request.payload.get(
                'imageDataUrls', request.payload.get('image_data_urls', []))
            if request.operation == 'image_edit':
                if not isinstance(references, list) or not 1 <= len(references) <= 3:
                    raise ModelWorkerError(
                        'Image editing requires one to three reference images', code='invalid_request')
            elif references:
                raise ModelWorkerError(
                    'Use image editing for reference images', code='invalid_request')
        return await super().invoke(request)

    @staticmethod
    def parameters(payload, upstream):
        generation = dict(payload)
        generation.pop('imageDataUrls', None)
        generation.pop('image_data_urls', None)
        generation.setdefault('steps', 40)
        if 'guidance_scale' not in generation:
            generation.setdefault('guidance', 1.0)
        return CudaImageGenerationAdapter.parameters(generation, upstream)

    @staticmethod
    def inputs(payload):
        if payload.get('imageDataUrls', payload.get('image_data_urls')):
            return CudaQwenImageEditAdapter.inputs(payload)
        return {}

    @staticmethod
    def pipeline_factory(upstream):
        from diffusers import QwenImage21Pipeline
        return QwenImage21Pipeline

    @staticmethod
    def output_image(image, fmt):
        return image.convert('RGB') if fmt == 'jpeg' else image


def create_adapter(context):
    return CudaImageGenerationAdapter(context)


def create_edit_adapter(context):
    return CudaQwenImageEditAdapter(context)


class CudaQwenImageAdapter:
    """One service owns generation/editing, with at most one resident pipeline."""

    def __init__(self, context):
        self.context = context
        self.adapters = {
            'image_generation': CudaImageGenerationAdapter(context),
            'image_edit': CudaQwenImageEditAdapter(context),
            QWEN_IMAGE_21: CudaQwenImage21Adapter(context),
        }
        self.lock = asyncio.Lock()
        self.pending = {}
        self.active = None
        self.stopping = False

    async def start(self):
        self.stopping = False

    def cancel(self, request_id):
        if event := self.pending.get(request_id):
            event.set()
        for adapter in self.adapters.values():
            adapter.cancel(request_id)

    async def invoke(self, request):
        if self.stopping:
            raise ModelWorkerError('Worker is stopping', code='worker_stopping', status_code=503)
        if request.request_id in self.pending:
            raise ModelWorkerError('Request already active', code='request_conflict', status_code=409)
        expected = {'image_generation': 'Qwen/Qwen-Image-2512',
                    'image_edit': 'Qwen/Qwen-Image-Edit-2511'}
        if request.operation not in expected:
            raise ModelWorkerError('Unsupported operation', code='operation_not_supported', status_code=400)
        checkpoint = self.context.checkpoint_for(str(request.payload.get('model') or ''))
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError('Model checkpoint is not installed', code='model_unavailable', status_code=503)
        if checkpoint.upstream_id not in (expected[request.operation], QWEN_IMAGE_21):
            raise ModelWorkerError('Model does not support this operation', code='operation_not_supported', status_code=400)
        event = self.pending[request.request_id] = threading.Event()
        try:
            async with self.lock:
                CudaImageGenerationAdapter.check_cancel(event)
                if self.stopping:
                    raise ModelWorkerError('Worker is stopping', code='worker_stopping', status_code=503)
                adapter_key = QWEN_IMAGE_21 if checkpoint.upstream_id == QWEN_IMAGE_21 else request.operation
                selected = self.adapters[adapter_key]
                if self.active is not selected:
                    if self.active is not None:
                        await self.active.stop()
                    self.active = None
                    CudaImageGenerationAdapter.check_cancel(event)
                    await selected.start()
                    self.active = selected
                return await selected.invoke(request)
        finally:
            self.pending.pop(request.request_id, None)

    async def stop(self):
        self.stopping = True
        for request_id in tuple(self.pending):
            self.cancel(request_id)
        async with self.lock:
            if self.active is not None:
                await self.active.stop()
                self.active = None


def create_qwen_adapter(context):
    return CudaQwenImageAdapter(context)
