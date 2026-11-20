"""VoxCPM2 on the existing TTS protocol and serialized CUDA request lifecycle."""
from pathlib import Path
from dataclasses import replace
import re
import tempfile
import threading

from ai2apps.model_worker import ModelWorkerError
from ai2apps.model_worker.cuda_audio import CudaQwenTTSAdapter,CudaQwenTTSEngine

MODELS={
    'ai2apps.model.voxcpm2-cuda/bf16':('bf16','openbmb/VoxCPM2','32279effe8c19989596f05d353d1447f51d9e915'),
    'ai2apps.model.voxcpm2-cuda/4bit':('4bit','mlx-community/VoxCPM2-4bit','dc9e5c187858da5f4a13dc4c247e297339216381'),
    'ai2apps.model.voxcpm2-cuda/8bit':('8bit','mlx-community/VoxCPM2-8bit','d52725898a0675703f7f9ddc5a4d1a3cdbb99032'),
}
EMOTIONS={'happy':'sound genuinely happy and warm','sad':'sound subdued and sad',
          'angry':'sound controlled but clearly angry','calm':'sound calm and composed',
          'excited':'sound energetic and excited','surprised':'sound naturally surprised'}


class CudaVoxSpeechEngine(CudaQwenTTSEngine):
    def _check(self):
        if self.cancelled.is_set():
            raise ModelWorkerError('Speech generation cancelled',code='request_cancelled',status_code=499)

    async def start(self):
        def load():
            self._check()
            variant=MODELS[self.checkpoint.model_id][0]
            if variant=='bf16':
                from cuda_voxcpm_original_engine import CudaVoxCPMOriginalEngine
                self.model=CudaVoxCPMOriginalEngine(self.checkpoint.path,self._check)
            else:
                from cuda_voxcpm_engine import CudaVoxCPMEngine
                self.model=CudaVoxCPMEngine(self.checkpoint.path,variant,self._check)
        try:await self._run(load)
        except BaseException:
            await self.stop()
            raise

    async def stop(self):
        self.cancelled.set()
        def release():
            model,self.model=self.model,None
            if model is not None:model.close()
        await self._run(release)

    async def synthesize(self,text,*,voice=None,ref_audio=None,ref_text=None,
                         language=None,speed=1.0,instructions=None,**options):
        if voice or speed!=1.0 or language not in (None,'auto','zh','en'):
            raise ModelWorkerError('Unsupported VoxCPM2 voice/speed/language',code='unsupported_feature',status_code=400)
        if any(options.get(k) is not None for k in ('temperature','top_k','top_p','repetition_penalty')):
            raise ModelWorkerError('VoxCPM2 does not use codec sampling controls',code='unsupported_feature',status_code=400)
        if self.model is None:await self.start()
        def generate():
            import torch
            self._check()
            # The common TTS protocol returns WAV bytes; its Host owns format
            # conversion and output retention. No separate output history.
            with tempfile.TemporaryDirectory(prefix='voxcpm-request-') as directory:
                path=Path(directory)/'speech.wav'
                values={'instructions':instructions,'max_tokens':2000 if options.get('max_tokens') is None else options['max_tokens'],
                        'seed':options.get('seed',42)}
                try:
                    self.model.generate(text,path,values,reference=ref_audio,check=self._check)
                except torch.cuda.OutOfMemoryError as error:
                    model,self.model=self.model,None
                    model.close()
                    raise ModelWorkerError('CUDA memory exhausted during speech generation',
                        code='resource_exhausted',status_code=503) from error
                self._check()
                return path.read_bytes()
        return await self._run(generate)


class CudaVoxCPMAdapter(CudaQwenTTSAdapter):
    def __init__(self,context):
        super().__init__(context);self._stopping=False

    async def start(self):self._stopping=False

    async def stop(self):
        self._stopping=True
        await super().stop()

    async def invoke(self,request):
        if self._stopping:
            raise ModelWorkerError('Worker is stopping',code='worker_stopping',status_code=503)
        if request.request_id in self._cancellations:
            raise ModelWorkerError('Request already active',code='request_conflict',status_code=409)
        model_id=request.payload.get('model')
        if model_id not in MODELS:
            model_id=next((key for key, spec in MODELS.items() if spec[1]==model_id),None)
        if model_id is None:
            raise ModelWorkerError('Unknown VoxCPM2 model',code='model_not_found',status_code=404)
        from cuda_voxcpm_engine import parameters
        body=dict(request.payload)
        body['model']=model_id
        for name in ('seed','max_tokens'):
            if isinstance(body.get(name),str) and re.fullmatch(r'[0-9]{1,10}',body[name]):
                body[name]=int(body[name])
        values={k:body[k] for k in ('seed','max_tokens') if body.get(k) is not None}
        try:parameters(request.payload.get('input'),values)
        except ValueError as error:
            raise ModelWorkerError(str(error),code='invalid_request_error',status_code=400) from error
        return await super().invoke(replace(request,payload=body))

    async def create_engine(self,checkpoint,runtime_options=None):
        spec=MODELS.get(checkpoint.model_id)
        if spec is None or (checkpoint.repo_id,checkpoint.revision)!=spec[1:] or checkpoint.path is None:
            raise ModelWorkerError('Host-selected fixed VoxCPM2 checkpoint required',code='checkpoint_not_ready',status_code=409)
        if runtime_options:
            raise ModelWorkerError('Unsupported VoxCPM2 runtime settings',code='unsupported_feature',status_code=400)
        engine=CudaVoxSpeechEngine(checkpoint)
        engine.cancelled=self._current_event or threading.Event()
        return engine

    def synthesis_options(self,model_id,body,*,speed,emotion,emotion_strength,instructions):
        # Match the Mac Package's qualitative controls and precedence exactly.
        mandatory=[]
        if emotion and emotion.lower()!='neutral':mandatory.append(EMOTIONS[emotion.lower()])
        rate=('speak much more slowly than normal' if speed<.75 else
              'speak more slowly than normal' if speed<.95 else
              'speak much faster than normal' if speed>1.5 else
              'speak faster than normal' if speed>1.05 else None)
        if rate:mandatory.append(rate)
        parts=[instructions.strip()] if instructions and instructions.strip() else []
        if mandatory:parts.append('Mandatory delivery controls override conflicting earlier style: '+'; '.join(mandatory)+'.')
        return {'speed':1.0,'instructions':' '.join(parts) or None,
                'language':body.get('language') or None,'seed':body.get('seed',42)}


def create_adapter(context):return CudaVoxCPMAdapter(context)
