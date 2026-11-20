"""CosyVoice3 on the shared Host speech protocol and serialized CUDA runner."""
from dataclasses import replace
from pathlib import Path
import re,tempfile,threading
from ai2apps.model_worker import ModelWorkerError
from ai2apps.model_worker.cuda_audio import CudaQwenTTSAdapter,CudaQwenTTSEngine

MODELS={
 'ai2apps.model.cosyvoice3-cuda/4bit':('4bit','mlx-community/Fun-CosyVoice3-0.5B-2512-4bit','55a6713d54751f1ec2645aa11294676f2067202a'),
 'ai2apps.model.cosyvoice3-cuda/8bit':('8bit','mlx-community/Fun-CosyVoice3-0.5B-2512-8bit','177baf277ac75e04e810f7db7f0d9c0ce5a17854'),
}
S3_ID='ai2apps.model.cosyvoice3-cuda/s3tokenizer-v3'
S3_SPEC=('mlx-community/S3TokenizerV3','b143914b3e912278104824da706edc9c2d317c4e')


def invalid(message,code='invalid_request_error',status=400):
    raise ModelWorkerError(message,code=code,status_code=status)


class CudaCosySpeechEngine(CudaQwenTTSEngine):
    native_speed = False
    def __init__(self,checkpoint,tokenizer_checkpoint):
        super().__init__(checkpoint);self.tokenizer_checkpoint=tokenizer_checkpoint

    def _check(self):
        if self.cancelled.is_set():invalid('Speech generation cancelled','request_cancelled',499)

    async def start(self):
        def load():
            from cuda_cosyvoice_engine import CudaCosyVoiceEngine
            self._check()
            self.model=CudaCosyVoiceEngine(self.checkpoint.path,self.tokenizer_checkpoint.path,
                MODELS[self.checkpoint.model_id][0],self._check)
        try:await self._run(load)
        except BaseException:
            await self.stop();raise

    async def stop(self):
        self.cancelled.set()
        def release():
            model,self.model=self.model,None
            if model is not None:model.close()
        await self._run(release)

    async def synthesize(self,text,*,voice=None,ref_audio=None,ref_text=None,
                         language=None,speed=1.0,instructions=None,**options):
        if voice or (speed!=1.0 and not self.native_speed) or language not in (None,'auto','zh','en','ja','ko','de','fr','ru','it','es'):
            invalid('Unsupported CosyVoice3 voice/speed/language','unsupported_feature')
        if not ref_audio:invalid('CosyVoice3 requires reference_audio')
        if any(options.get(k) is not None for k in ('temperature','top_k','top_p','repetition_penalty','max_tokens')):
            invalid('CosyVoice3 uses fixed validated sampling and text-length limits','unsupported_feature')
        if self.model is None:await self.start()
        def generate():
            import torch
            self._check()
            with tempfile.TemporaryDirectory(prefix='cosyvoice-request-') as directory:
                output=Path(directory)/'speech.wav'
                try:self.model.generate(text,ref_audio,output,reference_text=ref_text or '',
                    instruction=instructions or '',seed=options.get('seed',42),check=self._check,
                    **({'speed':speed} if self.native_speed else {}))
                except ValueError as error:invalid(str(error))
                except torch.cuda.OutOfMemoryError as error:
                    model,self.model=self.model,None;model.close()
                    raise ModelWorkerError('CUDA memory exhausted during speech generation',code='resource_exhausted',status_code=503) from error
                self._check();return output.read_bytes()
        return await self._run(generate)


class CudaCosyVoiceAdapter(CudaQwenTTSAdapter):
    def __init__(self,context):super().__init__(context);self._stopping=False
    async def start(self):self._stopping=False
    async def stop(self):self._stopping=True;await super().stop()

    async def invoke(self,request):
        if self._stopping:invalid('Worker is stopping','worker_stopping',503)
        if request.request_id in self._cancellations:invalid('Request already active','request_conflict',409)
        if request.payload.get('model') not in MODELS:invalid('Unknown CosyVoice3 model','model_not_found',404)
        body=dict(request.payload);seed=body.get('seed',42)
        if isinstance(seed,str) and re.fullmatch(r'[0-9]{1,10}',seed):seed=int(seed)
        if type(seed) is not int or not 0<=seed<2**32:invalid('seed must be uint32')
        body['seed']=seed
        return await super().invoke(replace(request,payload=body))

    async def create_engine(self,checkpoint,runtime_options=None):
        spec=MODELS.get(checkpoint.model_id)
        if spec is None or checkpoint.path is None or (checkpoint.repo_id,checkpoint.revision)!=spec[1:]:
            invalid('Host-selected fixed CosyVoice3 checkpoint required','checkpoint_not_ready',409)
        if runtime_options:invalid('Unsupported CosyVoice3 runtime settings','unsupported_feature')
        declaration=self.model_declaration(checkpoint.model_id)
        required=declaration.get('metadata',{}).get('required_model_ids',[])
        if required!=[S3_ID]:invalid('Exact S3Tokenizer dependency declaration required','checkpoint_not_ready',409)
        s3=self.context.checkpoint_for(S3_ID)
        if s3 is None or s3.path is None or (s3.repo_id,s3.revision)!=S3_SPEC:
            invalid('Host-selected fixed S3Tokenizer checkpoint required','checkpoint_not_ready',409)
        engine=CudaCosySpeechEngine(checkpoint,s3);engine.cancelled=self._current_event or threading.Event()
        return engine

    def synthesis_options(self,model_id,body,*,speed,emotion,emotion_strength,instructions):
        # Host shared contract already implements Mac qualitative speed/emotion.
        values=super().synthesis_options(model_id,body,speed=speed,emotion=emotion,
            emotion_strength=emotion_strength,instructions=instructions)
        rate=('Speak much more slowly than normal.' if speed<.75 else
              'Speak more slowly than normal.' if speed<.95 else
              'Speak much faster than normal.' if speed>1.5 else
              'Speak faster than normal.' if speed>1.05 else None)
        if rate:values['instructions']=' '.join(x for x in (values['instructions'],rate) if x)
        values['speed']=1.0
        values['seed']=body.get('seed',42)
        return values


def create_adapter(context):return CudaCosyVoiceAdapter(context)
