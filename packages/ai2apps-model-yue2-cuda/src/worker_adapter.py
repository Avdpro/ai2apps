"""YuE2 service adapter with fixed Host checkpoints and drained native ownership."""
import asyncio
import inspect
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError
from cuda_sol_lifecycle import SoLRequestOwner
from cuda_yue2_engine import MODEL, parameters

CHECKPOINTS = (
    (MODEL, 'm-a-p/YuE2-3B', 'c044757a011169583f363168348ae380946efff8'),
    ('ai2apps.model.yue2-cuda/vae', 'm-a-p/YuE2-Vae', '152733a19ad43aa67e367f9b5503ef8075bb5126'),
)

@dataclass
class Work:
    request: object
    checkpoints: tuple
    params: dict
    output: Path
    loop: object

    @property
    def request_id(self):
        return self.request.request_id


class CudaYuE2Adapter:
    def __init__(self, context):
        self.context = context
        self._owner = SoLRequestOwner(self._render, lambda: None)

    async def start(self):
        pass

    async def stop(self):
        await self._owner.stop()

    def cancel(self, request_id):
        self._owner.cancel(request_id)

    def _render(self, work, event):
        from cuda_yue2_engine import generate
        import torch
        def check():
            if event.is_set():
                raise ModelWorkerError('Song generation cancelled', code='generation_cancelled', status_code=499)
        async def progress(phase):
            if work.request.progress:
                value = work.request.progress({'phase':phase,'current':0,'total':1})
                if inspect.isawaitable(value):
                    await value
        def report(phase):
            check()
            asyncio.run_coroutine_threadsafe(progress(phase), work.loop).result(timeout=30)
        check()
        try:
            metadata = generate(work.checkpoints, work.params, work.output, check, report)
        except torch.cuda.OutOfMemoryError as error:
            raise MemoryError("CUDA memory exhausted during YuE2 generation") from error
        check()
        return ModelWorkerArtifact(work.output, media_type='audio/wav', filename='song.wav', metadata=metadata)

    async def invoke(self, request):
        if request.operation != 'audio_generate':
            raise ModelWorkerError('Unsupported operation', code='operation_not_supported', status_code=400)
        p = parameters(request.payload, bool(request.parts))
        if request.output_root is None:
            raise ModelWorkerError('Controlled output root required', code='runtime_protocol_error', status_code=500)
        roots = []
        for model_id, repo, revision in CHECKPOINTS:
            checkpoint = self.context.checkpoint_for(model_id)
            if (checkpoint is None or checkpoint.path is None or checkpoint.repo_id != repo
                    or checkpoint.revision != revision or not Path(checkpoint.path).is_dir()):
                raise ModelWorkerError('Prepare the fixed YuE2 model and VAE checkpoints',
                                       code='checkpoint_not_ready', status_code=409)
            roots.append(Path(checkpoint.path))
        output = request.output_root / ('song-' + uuid4().hex + '.wav')
        work = Work(request, tuple(roots), p, output, asyncio.get_running_loop())
        try:
            return await self._owner.invoke(work)
        except MemoryError as error:
            output.unlink(missing_ok=True)
            raise ModelWorkerError(str(error), code="resource_exhausted", status_code=503) from error
        except BaseException:
            # Owner waits for native writer exit even after repeated cancellation.
            output.unlink(missing_ok=True)
            raise


def create_adapter(context):
    return CudaYuE2Adapter(context)
