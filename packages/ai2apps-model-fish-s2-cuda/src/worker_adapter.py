"""Pinned official Fish S2 on the shared speech Worker contract."""
import gc,io,re,threading,wave
from dataclasses import replace
from ai2apps.model_worker import ModelWorkerError
from ai2apps.model_worker.cuda_audio import CudaQwenTTSAdapter,CudaQwenTTSEngine
MODEL_ID='ai2apps.model.fish-s2-cuda/bf16'
CHECKPOINT=('fishaudio/s2-pro','1de9996b6be38b745688de084d87a5633f714e4e')
EMOTIONS=('neutral','happy','sad','angry','calm','excited','surprised','whisper','shouting')


def reject(message,code='invalid_request_error',status=400):
    raise ModelWorkerError(message,code=code,status_code=status)


def integer_option(value,default,minimum,maximum,name):
    if value is None:value=default
    # Multipart fields are strings; accept bounded ASCII decimal integers only.
    if isinstance(value,str) and re.fullmatch(r'[0-9]{1,10}',value):value=int(value)
    if type(value) is not int or not minimum<=value<=maximum:reject('Invalid '+name)
    return value


def prepare_text(text,voice,instructions,emotion=None):
    if isinstance(text,list):
        if not isinstance(voice,list) or len(voice)!=len(text):reject('Dialogue voices must match turns')
        speakers={};turns=[]
        for utterance,speaker in zip(text,voice):
            if not isinstance(speaker,str) or not speaker:reject('Invalid dialogue voice')
            index=speakers.setdefault(speaker,len(speakers))
            if index>=5:reject('Fish supports at most five speakers')
            if not isinstance(utterance,str) or not utterance.strip():reject('Empty dialogue turn')
            turns.append(f'<|speaker:{index}|>{utterance}')
        text=' '.join(turns)
    elif voice:reject('Fish has no named voice presets','unsupported_feature')
    if not isinstance(text,str) or not text.strip():reject('Empty Fish text')
    if emotion is not None and emotion not in EMOTIONS:reject('Unsupported Fish emotion','unsupported_feature')
    tags=[]
    if emotion not in (None,'neutral'):tags.append(f'[{emotion}]')
    if instructions:
        if not isinstance(instructions,str):reject('Instructions must be text')
        tag=instructions.strip().strip('[]')
        if tag:tags.append(f'[{tag}]')
    if tags:
        prefix=' '.join(tags)+' '
        # Upstream speaker splitting discards text before the first speaker tag.
        # Place global style inside each turn so dialogue retains the control.
        if re.search(r'<\|speaker:\d+\|>',text):
            text=re.sub(r'(<\|speaker:\d+\|>)',lambda match:match.group(1)+prefix,text)
        else:text=prefix+text
    return text


class CudaFishS2SpeechEngine(CudaQwenTTSEngine):
    def check(self):
        if self.cancelled.is_set():reject('Speech generation cancelled','request_cancelled',499)
    async def start(self):
        def load():
            from cuda_fish_s2_loading import load_engine
            self.check();self.model,self.loading_info=load_engine(self.checkpoint.path);self.check()
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
    async def synthesize(self,text,*,voice=None,ref_audio=None,ref_text=None,language=None,speed=1.,instructions=None,emotion=None,seed=42,**options):
        if speed!=1.:reject('Fish speed control is not yet verified','unsupported_feature')
        if language not in (None,'auto'):reject('Fish uses text language automatically','unsupported_feature')
        if any(options.get(k) is not None for k in ('temperature','top_k','top_p','repetition_penalty')):
            reject('Fish custom sampling is not yet verified','unsupported_feature')
        text=prepare_text(text,voice,instructions,emotion)
        if ref_text and not ref_audio:reject('Reference transcript requires audio')
        if self.model is None:await self.start()
        def generate():
            import numpy as np
            self.check();references=[]
            if ref_audio:
                import soundfile as sf
                import torch,torchaudio
                with sf.SoundFile(ref_audio) as source:
                    if source.frames>60*source.samplerate:reject('Reference exceeds 60 seconds')
                    samples=source.read(dtype='float32',always_2d=True).mean(axis=1)
                    rate=source.samplerate
                if not len(samples) or not np.isfinite(samples).all():reject('Invalid reference audio')
                if rate!=44100:samples=torchaudio.functional.resample(torch.from_numpy(samples),rate,44100).numpy()
                references=[(samples,ref_text or '')]
            self.check();audio=self.model.generate(text,references=references,seed=seed,max_new_tokens=options.get('max_tokens') or 1024,check=self.check);self.check()
            stream=io.BytesIO()
            with wave.open(stream,'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100)
                w.writeframes(np.clip(audio*32767,-32768,32767).astype('<i2').tobytes())
            self.check();return stream.getvalue()
        return await self._run(generate)


class CudaFishS2Adapter(CudaQwenTTSAdapter):
    def __init__(self,context):super().__init__(context);self.stopped=False
    async def start(self):self.stopped=False
    async def stop(self):self.stopped=True;await super().stop()
    async def invoke(self,request):
        if self.stopped:reject('Worker stopped','worker_stopping',503)
        if request.request_id in self._cancellations:reject('Request already active','request_conflict',409)
        body=dict(request.payload)
        if body.get('model') not in (MODEL_ID,CHECKPOINT[0]):reject('Unknown Fish model','model_not_found',404)
        for name,default,maximum in [('seed',42,2**32-1),('max_tokens',1024,32768)]:
            body[name]=integer_option(body.get(name),default,0 if name=='seed' else 1,maximum,name)
        return await super().invoke(replace(request,payload=body))
    async def create_engine(self,checkpoint,runtime_options=None):
        if checkpoint.model_id!=MODEL_ID or (checkpoint.repo_id,checkpoint.revision)!=CHECKPOINT or checkpoint.path is None:
            reject('Pinned official checkpoint required','checkpoint_not_ready',409)
        if runtime_options:reject('Unverified Runtime settings','unsupported_feature')
        engine=CudaFishS2SpeechEngine(checkpoint);engine.cancelled=self._current_event or threading.Event();return engine
    def synthesis_options(self,model_id,body,*,speed,emotion,emotion_strength,instructions):
        if emotion_strength!=1.:reject('Fish has no verified numeric emotion strength','unsupported_feature')
        if emotion is not None and emotion not in EMOTIONS:reject('Unsupported Fish emotion','unsupported_feature')
        return {'speed':speed,'instructions':instructions,'emotion':emotion,'language':body.get('language'),'seed':body.get('seed') if body.get('seed') is not None else 42}


def create_adapter(context):return CudaFishS2Adapter(context)
