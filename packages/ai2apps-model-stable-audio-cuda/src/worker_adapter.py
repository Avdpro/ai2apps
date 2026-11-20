"""Stable Audio Worker using Host checkpoints and serialized native ownership."""
import asyncio
from dataclasses import dataclass
import importlib.util
import inspect
from pathlib import Path
from uuid import uuid4

from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError
from ai2apps.model_worker.audio_generation import validate_audio_generation, AUDIO_GENERATION_SCHEMA
from cuda_sol_lifecycle import SoLRequestOwner

MODELS = {'ai2apps.model.stable-audio-cuda/music': ('music', 'music'),
          'ai2apps.model.stable-audio-cuda/sfx': ('sfx', 'sound_effects')}
REVISION = 'da6edc54ddba10bfd79a077102ded687f80e882b'


@dataclass
class Work:
    request: object
    root: Path
    params: dict
    output: Path
    loop: object

    @property
    def request_id(self):
        return self.request.request_id


class CudaStableAdapter:
    def __init__(self, context):
        self.context = context
        self._engine = self._root = None
        self._owner = SoLRequestOwner(self._render, self._release)

    async def start(self):
        pass

    async def stop(self):
        await self._owner.stop()

    def cancel(self, request_id):
        self._owner.cancel(request_id)

    def _release(self):
        engine, self._engine, self._root = self._engine, None, None
        if engine is not None:
            engine.close()

    @staticmethod
    def parameters(payload, has_parts=False):
        p = validate_audio_generation(payload, has_parts=has_parts)
        if p['model'] not in MODELS:
            raise ModelWorkerError('Unknown Stable Audio model',code='model_not_found',status_code=404)
        if (p.get('schema', AUDIO_GENERATION_SCHEMA) != AUDIO_GENERATION_SCHEMA
                or p['task'] != MODELS[p['model']][1] or not 1 <= p['duration'] <= 120 or p['lyrics']):
            raise ModelWorkerError('Stable Audio requires 1–120 second generation v1 without lyrics',
                                   code='invalid_audio_generation',status_code=400)
        return p

    def _render(self, work, event):
        import torch
        import psutil
        from cuda_stable_engine import CudaStableEngine
        def check():
            if event.is_set():
                raise ModelWorkerError('Audio generation cancelled',code='generation_cancelled',status_code=499)
        async def report_async(data):
            if work.request.progress:
                value = work.request.progress(data)
                if inspect.isawaitable(value):
                    await value
        def report(phase,current=0,total=1):
            check()
            asyncio.run_coroutine_threadsafe(report_async(dict(phase=phase,current=current,total=total)),work.loop).result(timeout=30)
        try:
            check()
            if self._engine is not None and self._root != (work.root, work.params['model']):
                self._release()
            memory = psutil.virtual_memory()
            free,total = torch.cuda.mem_get_info()
            shared = torch.cuda.get_device_name()=='NVIDIA GB10' and total==memory.total
            available = memory.available if shared else min(memory.available,free)
            # Development bound: native 120s measured 2.42 GB allocated plus load/CPU headroom.
            required = (4 if self._engine is not None else 8)*1024**3
            if available < required:
                raise MemoryError('Insufficient available memory for Stable Audio generation')
            report('loading')
            if self._engine is None:
                spec = importlib.util.find_spec('stable_audio_3')
                if spec is None or spec.origin is None:
                    raise RuntimeError('Stable Audio Runtime profile missing')
                self._engine = CudaStableEngine(work.root,Path(spec.origin).parent.parent,MODELS[work.params['model']][0],check)
                self._root = (work.root, work.params['model'])
            metadata = self._engine.generate(work.params,work.output,check,report)
            check()
            return ModelWorkerArtifact(work.output,media_type='audio/wav',filename='audio.wav',metadata=metadata)
        except torch.cuda.OutOfMemoryError as error:
            self._release()
            raise MemoryError('CUDA memory exhausted during audio generation') from error

    async def invoke(self, request):
        if request.operation != 'audio_generate':
            raise ModelWorkerError('Unsupported operation',code='operation_not_supported',status_code=400)
        params = self.parameters(request.payload,bool(request.parts))
        if request.output_root is None:
            raise ModelWorkerError('Controlled output root required',code='runtime_protocol_error',status_code=500)
        checkpoint = self.context.checkpoint_for(params['model'])
        if (checkpoint is None or checkpoint.path is None
                or checkpoint.repo_id != 'stabilityai/stable-audio-3-optimized' or checkpoint.revision != REVISION):
            raise ModelWorkerError('Host-selected fixed Stable Audio checkpoint required',code='checkpoint_not_ready',status_code=409)
        output = request.output_root/('audio-'+uuid4().hex+'.wav')
        work = Work(request,Path(checkpoint.path),params,output,asyncio.get_running_loop())
        try:
            return await self._owner.invoke(work)
        except MemoryError as error:
            output.unlink(missing_ok=True)
            raise ModelWorkerError(str(error),code='resource_exhausted',status_code=503) from error
        except BaseException:
            # Native owner drains the writer before deleting partial output.
            output.unlink(missing_ok=True)
            raise


def create_adapter(context):
    return CudaStableAdapter(context)
