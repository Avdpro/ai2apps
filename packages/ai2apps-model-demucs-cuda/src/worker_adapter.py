"""Development CUDA Demucs adapter for the shared audio_process contract."""
import asyncio
import gc
import inspect
import math
from pathlib import Path
import threading
import zipfile
from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError
from mlx_demucs.audio import read_audio
from mlx_demucs.pipeline import SeparationConfig, separate_audio
from demucs_cuda_backend import CudaDemucsBackend

class CudaDemucsAdapter:
    def __init__(self, context):
        self.context=context
        self.lock=asyncio.Lock()
        self.events={}
        self.backend=None
        self.checkpoint=None
        self.stopping=False

    async def start(self):
        self.stopping=False

    def cancel(self, request_id):
        if event:=self.events.get(request_id):event.set()

    async def stop(self):
        self.stopping=True
        for event in self.events.values():event.set()
        async with self.lock:
            self.backend=None;self.checkpoint=None
            gc.collect()
            import torch
            torch.cuda.empty_cache()

    async def invoke(self, request):
        if self.stopping:
            raise ModelWorkerError('Worker is stopping',code='worker_stopping',status_code=503)
        if request.request_id in self.events:
            raise ModelWorkerError('Request already active',code='request_conflict',status_code=409)
        if request.operation!='audio_process':
            raise ModelWorkerError('Unsupported operation',code='operation_not_supported')
        payload=dict(request.payload)
        if payload.get('task','source_separation')!='source_separation':
            raise ModelWorkerError('Unsupported audio task',code='invalid_request')
        profile=payload.get('profile','dialogue_background')
        if profile not in {'music_4stem','vocals_instrumental','dialogue_background'}:
            raise ModelWorkerError('Unsupported separation profile',code='unsupported_profile')
        float32=payload.get('float32_wav',False)
        if type(float32) is not bool:
            if float32 not in ('true','false'):raise ModelWorkerError('float32_wav must be boolean',code='invalid_request')
            float32=float32=='true'
        checkpoint=self.context.checkpoint_for(str(payload.get('model') or ''))
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError('Checkpoint not installed',code='model_unavailable',status_code=503)
        if checkpoint.repo_id!='mlx-community/demucs-mlx' or checkpoint.revision!='d4519e24ddc2dd4a11d56a193092433d852c3961':
            raise ModelWorkerError('Unsupported checkpoint',code='model_not_supported')
        source=request.part('file').path
        if request.output_root is None:raise ModelWorkerError('Controlled output root is required',code='runtime_protocol_error')
        event=threading.Event();self.events[request.request_id]=event
        loop=asyncio.get_running_loop()
        async def report(phase,current,total=1):
            if request.progress:
                value=request.progress({'phase':phase,'current':current,'total':total})
                if inspect.isawaitable(value):await value
        def separate():
            if event.is_set():raise InterruptedError('cancelled')
            if self.checkpoint!=checkpoint.path:
                self.backend=CudaDemucsBackend(checkpoint.path)
                self.checkpoint=checkpoint.path
            self.backend.cancelled=event
            audio=read_audio(source)
            if not audio.frames or audio.channels>2:
                raise ValueError('Non-empty mono or stereo input is required')
            total=max(1,math.ceil(audio.duration/(7.8*.75)))
            self.backend.progress=lambda count:asyncio.run_coroutine_threadsafe(report('separating',min(count-1,total),total),loop).result()
            stems=request.output_root/'stems'
            result=separate_audio(audio,stems,backend=self.backend,config=SeparationConfig(profile=profile,float32_wav=float32))
            if event.is_set():raise InterruptedError('cancelled')
            output=request.output_root/'demucs-stems.zip'
            with zipfile.ZipFile(output,'w',allowZip64=True) as archive:
                archive.write(stems/'separation.json','separation.json')
                for stem in result.stems:
                    if event.is_set():raise InterruptedError('cancelled')
                    archive.write(stems/stem.path,Path(stem.path).name,compress_type=zipfile.ZIP_STORED)
            if event.is_set():raise InterruptedError('cancelled')
            return ModelWorkerArtifact(output,media_type='application/zip',filename=output.name,
                metadata={'schema':result.schema,'profile':profile,'stems':[s.type for s in result.stems]})
        try:
            async with self.lock:
                await report('loading',0)
                task=asyncio.create_task(asyncio.to_thread(separate))
                try:return await asyncio.shield(task)
                except asyncio.CancelledError:
                    event.set()
                    while not task.done():
                        try:await asyncio.shield(task)
                        except asyncio.CancelledError:continue
                        except Exception:break
                    if not task.cancelled():task.exception()
                    raise
        except InterruptedError as error:
            raise ModelWorkerError('Separation cancelled',code='request_cancelled',status_code=499) from error
        except (ValueError,OSError) as error:
            raise ModelWorkerError(str(error),code='audio_processing_failed',status_code=422) from error
        finally:self.events.pop(request.request_id,None)

def create_adapter(context):return CudaDemucsAdapter(context)
