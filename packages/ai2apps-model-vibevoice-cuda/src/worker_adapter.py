"""Official VibeVoice on the shared speech Worker/Host contract."""
import gc,io,threading,wave
from pathlib import Path
from ai2apps.model_worker import ModelWorkerError
from ai2apps.model_worker.cuda_audio import CudaQwenTTSAdapter,CudaQwenTTSEngine

MODEL_ID='ai2apps.model.vibevoice-cuda/realtime-bf16'
CHECKPOINT=('microsoft/VibeVoice-Realtime-0.5B','6bce5f06044837fe6d2c5d7a71a84f0416bd57e4')

def reject(message,code='invalid_request_error',status=400):
    raise ModelWorkerError(message,code=code,status_code=status)

class CudaVibeVoiceSpeechEngine(CudaQwenTTSEngine):
    def __init__(self,checkpoint,assets):super().__init__(checkpoint);self.assets=assets
    def check(self):
        if self.cancelled.is_set():reject('Speech generation cancelled','request_cancelled',499)
    async def start(self):
        def load():
            from cuda_vibevoice_engine import CudaVibeVoiceEngine
            self.check();self.model=CudaVibeVoiceEngine(self.assets,checkpoint_path=self.checkpoint.path);self.check()
        try:await self._run(load)
        except BaseException:await self.stop();raise
    async def stop(self):
        self.cancelled.set()
        def release():
            model,self.model=self.model,None
            if model is not None:model.close()
            del model;gc.collect()
            import torch
            torch.cuda.empty_cache()
        await self._run(release)
    async def synthesize(self,text,*,voice=None,ref_audio=None,ref_text=None,language=None,speed=1.,instructions=None,seed=1234,**options):
        if ref_audio or ref_text or instructions or speed!=1. or language not in (None,'auto','en'):reject('Unsupported VibeVoice controls','unsupported_feature')
        if any(options.get(k) is not None for k in ('temperature','top_k','top_p','repetition_penalty')):reject('Codec sampling controls unsupported','unsupported_feature')
        if self.model is None:await self.start()
        def generate():
            import numpy as np
            self.check();audio=self.model.generate(text,voice or 'en-Carter_man',seed=seed,max_new_tokens=options.get('max_tokens'),check=self.check);self.check()
            stream=io.BytesIO()
            with wave.open(stream,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(np.clip(audio*32767,-32768,32767).astype('<i2').tobytes())
            self.check();return stream.getvalue()
        return await self._run(generate)

class CudaVibeVoiceAdapter(CudaQwenTTSAdapter):
    def __init__(self,context):super().__init__(context);self.stopped=False
    async def start(self):self.stopped=False
    async def stop(self):self.stopped=True;await super().stop()
    async def invoke(self,request):
        if self.stopped:reject('Worker stopped','worker_stopping',503)
        if request.request_id in self._cancellations:reject('Request already active','request_conflict',409)
        body=request.payload
        if body.get('model') not in (MODEL_ID,CHECKPOINT[0]):reject('Unknown VibeVoice model','model_not_found',404)
        for name,default,maximum in [('seed',1234,2**32-1),('max_tokens',None,8192)]:
            value=body.get(name,default)
            if value is None:value=default
            if name=='max_tokens' and value is None:continue
            if type(value) is not int or not (0 if name=='seed' else 1)<=value<=maximum:reject('Invalid '+name)
        return await super().invoke(request)
    async def create_engine(self,checkpoint,runtime_options=None):
        if checkpoint.model_id!=MODEL_ID or (checkpoint.repo_id,checkpoint.revision)!=CHECKPOINT or checkpoint.path is None:reject('Pinned official checkpoint required','checkpoint_not_ready',409)
        if runtime_options:reject('Unverified Runtime settings','unsupported_feature')
        engine=CudaVibeVoiceSpeechEngine(checkpoint,self.context.package_root/'resources/vibevoice');engine.cancelled=self._current_event or threading.Event();return engine
    def synthesis_options(self,model_id,body,*,speed,emotion,emotion_strength,instructions):
        return {'speed':speed,'instructions':instructions,'language':body.get('language'),'seed':body.get('seed') if body.get('seed') is not None else 1234}

def create_adapter(context):return CudaVibeVoiceAdapter(context)
