"""CUDA Lite/Pro backend behind the existing FlashHead Worker request/lifecycle contract.

The development fixture supplies flashhead_host_adapter (the Mac adapter with only
its checkpoint import redirected) and flashhead_media (unchanged shared encoder).
No implicit dependency or checkpoint downloads are permitted.
"""
from __future__ import annotations

import asyncio
import gc
import math
import traceback

from ai2apps.model_worker import ModelWorkerError
from flashhead_host_adapter import FlashHeadAdapter

SERVICE_ID = 'ai2apps.model.flashhead-cuda'


def _release_exception_frames(error):
    """Keep diagnostic locations without retaining native tensor closures."""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if error.__traceback__ is not None:
            locations = ''.join(traceback.format_tb(error.__traceback__))
            traceback.clear_frames(error.__traceback__)
            error.__traceback__ = None
            error.add_note('Released native worker traceback:\n' + locations)
        error = error.__cause__ or error.__context__


def chunk_layout(frames, variant='lite'):
    if variant not in {'lite', 'pro'}:
        raise ValueError('Unknown FlashHead variant')
    limit = 1500 if variant == 'lite' else 250
    if isinstance(frames, bool) or not isinstance(frames, int) or not 1 <= frames <= limit:
        raise ValueError('Frame count exceeds selected variant limit')
    window, overlap = 33, (9 if variant == 'lite' else 5)
    stride = window - overlap
    padded = window + max(0, math.ceil((frames - window) / stride)) * stride
    return padded, range(0, padded - window + 1, stride)


class CudaFlashHeadPipeline:
    def __init__(self, root, wav2vec, *, variant):
        import torch
        from flash_head.src.pipeline import flash_head_pipeline as implementation

        if variant not in {'lite', 'pro'}:
            raise ValueError('Unknown FlashHead variant')
        self.variant = variant
        if not torch.cuda.is_available():
            raise RuntimeError('FlashHead requires CUDA')
        implementation.COMPILE_MODEL = False
        implementation.COMPILE_VAE = False
        self.native = implementation.FlashHeadPipeline(
            str(root), variant, str(wav2vec), device='cuda', use_usp=False)
        self.native.audio_encoder.eval()

    def generate(self, image, audio, output, *, size, seed, steps, cancel_check, progress):
        import torch

        # Upstream LTX reference encoding samples its posterior using the
        # default RNG, separately from prepare_params' diffusion generator.
        # Bind both to this request and restore ambient state even on cancel.
        with torch.random.fork_rng(devices=[torch.cuda.current_device()]):
            torch.manual_seed(seed)
            return self._generate(image, audio, output, size=size, seed=seed,
                                  steps=steps, cancel_check=cancel_check,
                                  progress=progress)

    def _generate(self, image, audio, output, *, size, seed, steps, cancel_check, progress):
        import numpy as np
        import soundfile as sf
        import torch
        from flashhead_media import write_mp4_chunks_with_audio

        cancel_check()
        values, rate = sf.read(audio, dtype='float32', always_2d=True)
        if rate != 16000 or values.shape[1] != 1 or not np.isfinite(values).all():
            raise ValueError('Expected finite mono 16 kHz audio')
        frames = math.ceil(len(values) * 25 / rate)
        padded_frames, starts = chunk_layout(frames, self.variant)
        overlap = 9 if self.variant == 'lite' else 5
        padded = np.pad(values[:, 0], (0, padded_frames * rate // 25 - len(values)))
        pipeline = self.native
        # Bound cancellation by native forward boundaries without changing kernels.
        hooks = []
        try:
            for module in (pipeline.model, pipeline.audio_encoder, pipeline.vae.model):
                hooks.append(module.register_forward_pre_hook(lambda *_: cancel_check()))
            cancel_check()
            pipeline.prepare_params(str(image), target_size=(size, size), frame_num=33,
                motion_frames_num=overlap, sampling_steps=steps, seed=seed, shift=5.,
                color_correction_strength=1., use_face_crop=False)
            cancel_check()
            embedding = pipeline.preprocess_audio(padded, sr=rate, fps=25)
            if embedding is None or embedding.shape[0] != padded_frames:
                raise RuntimeError('Unexpected audio embedding length')
            indices = torch.arange(padded_frames, device=embedding.device)[:, None] + torch.arange(-2, 3, device=embedding.device)[None, :]
            embedding = embedding[indices.clamp(0, padded_frames - 1)][None].contiguous()

            def chunks():
                emitted = 0
                for index, start in enumerate(starts):
                    cancel_check()
                    sample = pipeline.generate(embedding[:, start:start + 33].contiguous())
                    if not torch.isfinite(sample).all():
                        raise RuntimeError('Non-finite video pixels')
                    sample = sample.permute(1, 2, 3, 0).clamp(-1, 1).to(torch.float32)
                    if index:
                        sample = sample[overlap:]
                    sample = sample[:frames - emitted]
                    emitted += len(sample)
                    cancel_check()
                    yield sample.cpu().numpy()
                    progress(emitted, frames)
                if emitted != frames:
                    raise RuntimeError('Unexpected video frame count')

            write_mp4_chunks_with_audio(chunks(), audio, output, fps=25, cancel_check=cancel_check)
            cancel_check()
        finally:
            for hook in hooks:
                hook.remove()


class CudaFlashHeadAdapter(FlashHeadAdapter):
    def __init__(self, context, *, pipeline_factory=None):
        super().__init__(context, pipeline_factory=pipeline_factory or CudaFlashHeadPipeline)

    def _model(self, payload):
        name = payload.get('model')
        if not isinstance(name, str):
            raise ModelWorkerError('model must be a string', code='invalid_request')
        for model in self.context.models:
            if model['id'] in {SERVICE_ID + '/lite', SERVICE_ID + '/pro'} and name in {model['id'], model.get('upstream_id')}:
                return model['id'], model['id'].rsplit('/', 1)[1]
        raise ModelWorkerError('Select installed CUDA FlashHead Lite or Pro', code='model_not_found', status_code=404)

    async def invoke(self, request):
        try:
            return await super().invoke(request)
        except asyncio.CancelledError as error:
            # The shared adapter has already joined its native thread. Its
            # completed frames may still own the work task and CUDA closures.
            _release_exception_frames(error)
            raise
        except ModelWorkerError as error:
            if error.code == 'generation_failed':
                import torch
                chain = []
                current = error
                while current is not None and all(current is not item for item in chain):
                    chain.append(current)
                    current = current.__cause__ or current.__context__
                accelerator_error = getattr(torch, 'AcceleratorError', ())
                if any(isinstance(item, torch.OutOfMemoryError) or (
                    isinstance(item, accelerator_error)
                    and str(item).startswith('CUDA error: out of memory')
                ) for item in chain):
                    # Failed constructor frames can own partially loaded CUDA
                    # modules even after the adapter fields have been cleared.
                    _release_exception_frames(error)
                    try:
                        self._unload()
                    except RuntimeError:
                        pass  # Preserve the original allocation failure.
                    raise ModelWorkerError('CUDA memory exhausted during FlashHead generation',
                        code='resource_exhausted', status_code=503) from error
            if error.code == 'generation_cancelled':
                _release_exception_frames(error)
                raise ModelWorkerError('FlashHead generation cancelled', code='request_cancelled', status_code=499) from error
            raise

    def _unload(self):
        self._pipeline = None
        self._loaded = None
        gc.collect()
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def create_adapter(context):
    return CudaFlashHeadAdapter(context)
