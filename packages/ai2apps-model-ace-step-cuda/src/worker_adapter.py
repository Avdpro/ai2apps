"""ACE-Step music Worker using Host checkpoints and serialized native ownership."""
import asyncio
from dataclasses import dataclass
import importlib.util
import inspect
import os
from pathlib import Path
from uuid import uuid4

from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError
from ai2apps.model_worker.audio_generation import validate_audio_generation, AUDIO_GENERATION_SCHEMA
from cuda_sol_lifecycle import SoLRequestOwner

MODEL = 'ai2apps.model.ace-step-cuda/turbo'
UPSTREAM = 'ace-step-1.5-turbo'
REVISION = '19671f406d603126926c1b7e2adc169acbcade22'


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


class CudaAceAdapter:
    def __init__(self, context):
        self.context = context
        self._engine = self._root = None
        self._owner = SoLRequestOwner(self._render, self._release)
        self._workspace_configured = False
        self._workspace_before = None
        self._stop_task = None

    async def start(self):
        if self._workspace_configured:
            return
        import torch
        previous = os.environ.get('CUBLAS_WORKSPACE_CONFIG')
        if previous not in (None, ':4096:8'):
            raise ModelWorkerError('ACE-Step requires CUBLAS_WORKSPACE_CONFIG=:4096:8',
                                   code='runtime_configuration_error', status_code=503)
        if previous is None and torch.cuda.is_initialized():
            raise ModelWorkerError('ACE-Step deterministic workspace must be configured before CUDA initialization',
                                   code='runtime_configuration_error', status_code=503)
        self._workspace_before = previous
        os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
        self._workspace_configured = True

    async def stop(self):
        if self._stop_task is None:
            self._stop_task = asyncio.create_task(self._stop())
        # A cancelled waiter must not skip restoration or cancel native cleanup.
        await asyncio.shield(self._stop_task)

    async def _stop(self):
        try:
            await self._owner.stop()
        finally:
            if self._workspace_configured:
                if self._workspace_before is None:
                    os.environ.pop('CUBLAS_WORKSPACE_CONFIG', None)
                else:
                    os.environ['CUBLAS_WORKSPACE_CONFIG'] = self._workspace_before
                self._workspace_configured = False

    def cancel(self, request_id):
        self._owner.cancel(request_id)

    def _release(self):
        engine, self._engine, self._root = self._engine, None, None
        if engine is not None:
            engine.close()

    @staticmethod
    def parameters(payload, has_parts=False):
        p = validate_audio_generation(payload, has_parts=has_parts)
        if p['model'] not in (MODEL, UPSTREAM):
            raise ModelWorkerError('Unknown ACE-Step model',code='model_not_found',status_code=404)
        p['model'] = MODEL
        if (p.get('schema', AUDIO_GENERATION_SCHEMA) != AUDIO_GENERATION_SCHEMA
                or p['task'] != 'music' or not 10 <= p['duration'] <= 120):
            raise ModelWorkerError('ACE-Step requires fixed 10–120 second music generation v1',
                                   code='invalid_audio_generation',status_code=400)
        return p

    def _render(self, work, event):
        import torch
        import psutil
        from cuda_ace_engine import CudaAceEngine
        def check():
            if event.is_set():
                raise ModelWorkerError('Music generation cancelled',code='generation_cancelled',status_code=499)
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
            if self._engine is not None and self._root != work.root:
                self._release()
            memory = psutil.virtual_memory()
            free,total = torch.cuda.mem_get_info()
            shared = torch.cuda.get_device_name()=='NVIDIA GB10' and total==memory.total
            available = memory.available if shared else min(memory.available,free)
            # Development bound: measured <=11.64 GB total at120s, plus loading/CPU/headroom.
            required = (12 if self._engine is not None else 28)*1024**3
            if available < required:
                raise MemoryError('Insufficient available memory for ACE-Step generation')
            report('loading')
            if self._engine is None:
                spec = importlib.util.find_spec('acestep')
                if spec is None or spec.origin is None:
                    raise RuntimeError('ACE-Step Runtime profile missing')
                self._engine = CudaAceEngine(work.root,Path(spec.origin).parent.parent,check)
                self._root = work.root
            metadata = self._engine.generate(work.params,work.output,check,report)
            check()
            return ModelWorkerArtifact(work.output,media_type='audio/wav',filename='music.wav',metadata=metadata)
        except torch.cuda.OutOfMemoryError as error:
            self._release()
            raise MemoryError('CUDA memory exhausted during music generation') from error

    async def invoke(self, request):
        if request.operation != 'audio_generate':
            raise ModelWorkerError('Unsupported operation',code='operation_not_supported',status_code=400)
        params = self.parameters(request.payload,bool(request.parts))
        if request.output_root is None:
            raise ModelWorkerError('Controlled output root required',code='runtime_protocol_error',status_code=500)
        checkpoint = self.context.checkpoint_for(MODEL)
        if (checkpoint is None or checkpoint.path is None
                or checkpoint.repo_id != 'ACE-Step/Ace-Step1.5' or checkpoint.revision != REVISION):
            raise ModelWorkerError('Host-selected fixed ACE-Step checkpoint required',code='checkpoint_not_ready',status_code=409)
        output = request.output_root/('music-'+uuid4().hex+'.wav')
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
    return CudaAceAdapter(context)
