"""Development SenseVoice CUDA adapter with an explicitly pinned CPU VAD helper."""
from __future__ import annotations
import asyncio
import gc
import math
import os
import re
import threading
import traceback
from math import gcd

from ai2apps.model_worker.protocol import ModelWorkerError

def fail(message, code='invalid_request', status=400):
    raise ModelWorkerError(message, code=code, status_code=status)

def release_exception_frames(error):
    """Keep text diagnostics; traceback frames can retain Torch closure cells."""
    seen=set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if error.__traceback__ is not None:
            locations=''.join(traceback.format_tb(error.__traceback__))
            traceback.clear_frames(error.__traceback__)
            error.__traceback__=None
            error.add_note('Released native worker traceback:\n'+locations)
        error=error.__cause__ or error.__context__


class CudaSenseVoiceAdapter:
    def __init__(self, context):
        self.context=context
        self.model=None
        self.path=None
        self.vad=None
        self.vad_path=None
        self.lock=asyncio.Lock()
        self.events={}
        self.lifecycle=asyncio.Lock()
        self.stopping=False

    async def start(self):
        async with self.lifecycle:
            async with self.lock: self.stopping=False

    def cancel(self, request_id):
        if event:=self.events.get(request_id): event.set()

    @staticmethod
    def check(event):
        if event.is_set(): fail('Transcription cancelled','request_cancelled',499)

    async def stop(self):
        async with self.lifecycle:
            self.stopping=True
            for event in self.events.values(): event.set()
            async with self.lock:
                self.model=None;self.path=None;self.vad=None;self.vad_path=None;gc.collect()
                import torch
                torch.cuda.empty_cache()

    async def invoke(self, request):
        if self.stopping: fail('Worker is stopping','model_unavailable',503)
        if getattr(request,'request_id',None) in self.events: fail('Duplicate request ID','duplicate_request',409)
        if request.operation!='audio_transcription': fail('Unsupported operation','operation_not_supported')
        body=dict(request.payload)
        language=body.get('language') or 'auto'
        if language not in ('auto','zh','en','ja','ko','yue'): fail('Unsupported language')
        def boolean(value):
            if value in (True,'true','1'): return True
            if value in (None,False,'false','0',''): return False
            fail('Boolean option required')
        for key in ('stream','diarization','speaker_recognition','emotion_recognition','speech_rate_analysis'):
            if boolean(body.get(key)): fail(f'{key} is not supported','unsupported_feature')
        if body.get('prompt') or body.get('_ai2apps_model_settings'):
            fail('Prompt/runtime settings are not supported','unsupported_feature')
        if body.get('response_format','json') not in ('json','verbose_json'): fail('JSON response required')
        words_requested=boolean(body.get('word_timestamps'))
        use_itn=boolean(body.get('use_itn',True))
        checkpoint=self.context.checkpoint_for(str(body.get('model') or ''))
        if checkpoint is None or checkpoint.path is None: fail('Checkpoint unavailable','model_unavailable',503)
        if checkpoint.repo_id!='FunAudioLLM/SenseVoiceSmall' or checkpoint.revision!='3847d57b6bdf2dd8875cb1508d2af43d80a16bf7':
            fail('Unsupported checkpoint','model_not_supported')
        part=request.part('file')
        event=threading.Event();self.events[request.request_id]=event
        def transcribe():
            import numpy as np
            import soundfile as sf
            import torch
            from scipy.signal import resample_poly
            from funasr import AutoModel
            from funasr.utils.postprocess_utils import rich_transcription_postprocess
            self.check(event)
            try: audio,rate=sf.read(part.path,dtype='float32',always_2d=True)
            except (OSError,RuntimeError,ValueError) as error: fail(str(error),'invalid_audio')
            if not len(audio) or audio.shape[1]>2 or not np.isfinite(audio).all(): fail('Invalid audio','invalid_audio')
            duration=len(audio)/rate
            if duration>3600: fail('Audio exceeds one hour','audio_too_large',413)
            features={'timestamps':{
                'requested':'word' if words_requested else 'segment',
                'effective':'word' if words_requested else 'segment',
                'status':'pipeline' if duration>30 else 'native',
                'provider':self.context.service_id,'revision':checkpoint.revision}}
            audio=audio.mean(axis=1)
            if rate!=16000:
                divisor=gcd(rate,16000)
                audio=resample_poly(audio,16000//divisor,rate//divisor).astype(np.float32)
            runs=[(0,len(audio))]
            if duration>30:
                vad_checkpoint=self.context.checkpoint_for('funasr/fsmn-vad')
                if vad_checkpoint is None or vad_checkpoint.path is None:
                    fail('Pinned VAD checkpoint required for long audio','model_unavailable',503)
                if vad_checkpoint.repo_id!='funasr/fsmn-vad' or vad_checkpoint.revision!='df20e6b30c653645fa4ff125cacfcabd1020a669':
                    fail('Unsupported VAD checkpoint','model_not_supported')
                if self.vad_path!=vad_checkpoint.path:
                    os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD']='1'
                    self.vad=AutoModel(model=str(vad_checkpoint.path),device='cpu',trust_remote_code=False,
                        disable_update=True,disable_pbar=True,check_latest=False,max_single_segment_time=30000)
                    if self.vad.model.vad_opts.max_single_segment_time!=30000:
                        fail('VAD segment limit mismatch','inference_failed',500)
                    self.vad_path=vad_checkpoint.path
                self.check(event)
                handles=[m.register_forward_pre_hook(lambda *_:self.check(event)) for m in self.vad.model.modules()]
                try:
                    spans=self.vad.generate(input=audio,cache={},fs=16000)[0]['value']
                finally:
                    for handle in handles: handle.remove()
                runs=[];previous_end=0
                for span in spans:
                    start,end=map(float,span)
                    if not all(map(math.isfinite,(start,end))) or not 0<=previous_end<=start<end<=duration*1000+30 or end-start>30000:
                        fail('Invalid VAD segmentation','inference_failed',500)
                    runs.append((round(start*16),min(round(end*16),len(audio))))
                    previous_end=end
                if not runs:
                    return {'text':'','duration':duration,'language':language,'segments':[],
                            'features':features,**({'words':[]} if words_requested else {})}
            if self.path!=checkpoint.path:
                self.model=None;self.path=None;gc.collect();torch.cuda.empty_cache()
                os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD']='1'
                self.model=AutoModel(model=str(checkpoint.path),device='cuda:0',trust_remote_code=False,
                                     disable_update=True,disable_pbar=True,check_latest=False)
                if next(self.model.model.parameters()).device.type!='cuda': fail('CUDA unavailable','model_unavailable',503)
                self.path=checkpoint.path
            self.check(event)
            handles=[]
            try:
                for module in self.model.model.modules():
                    handles.append(module.register_forward_pre_hook(lambda *_:self.check(event)))
                results=[]
                for start,end in runs:
                    self.check(event)
                    result=self.model.generate(input=audio[start:end],cache={},language=language,use_itn=use_itn,
                                               output_timestamp=True,fs=16000,batch_size_s=30)[0]
                    results.append((start/16000,end/16000,result))
            finally:
                for handle in handles: handle.remove()
            self.check(event)
            texts=[];segments=[];all_words=[];languages=[]
            for offset,end,result in results:
                text=rich_transcription_postprocess(result['text'])
                texts.append(text)
                detected=re.match(r'<\|([^|]+)\|>',result['text'])
                languages.append(detected[1] if detected else language)
                if duration>30:
                    segments.append({'start':offset,'end':end,'text':text})
                stamps=result.get('timestamp',[]);words=result.get('words',[])
                if len(stamps)!=len(words): fail('Timestamp alignment mismatch','inference_failed',500)
                previous=0.
                for word,span in zip(words,stamps):
                    word_start,word_end=map(lambda n:float(n)/1000,span)
                    length=end-offset
                    if not all(map(math.isfinite,(word_start,word_end))) or not 0<=previous<=word_start<=word_end<=length+.1 or word_start>length:
                        fail('Invalid native timestamps','inference_failed',500)
                    all_words.append({'word':word,'start':offset+word_start,'end':min(offset+word_end,end)})
                    previous=word_start
            output={'text':' '.join(texts),'duration':duration,'language':languages[0] if len(set(languages))==1 else 'mixed'}
            if duration<=30 and all_words:
                segments=[{'start':all_words[0]['start'],'end':all_words[-1]['end'],'text':output['text']}]
            output['segments']=segments
            output['features']=features
            if words_requested: output['words']=all_words
            return output
        try:
            async with self.lock:
                self.check(event)
                task=asyncio.create_task(asyncio.to_thread(transcribe))
                try: return await asyncio.shield(task)
                except asyncio.CancelledError:
                    event.set()
                    while not task.done():
                        try: await asyncio.shield(task)
                        except asyncio.CancelledError: continue
                        except Exception: break
                    if not task.cancelled(): release_exception_frames(task.exception())
                    raise
                except ModelWorkerError as error:
                    release_exception_frames(error)
                    raise
                except Exception as error:
                    import torch
                    # CUDA 13 may report allocation failure as AcceleratorError
                    # rather than the allocator's OutOfMemoryError subtype.
                    accelerator_error = getattr(torch, 'AcceleratorError', ())
                    is_oom = isinstance(error, torch.OutOfMemoryError) or (
                        isinstance(error, accelerator_error)
                        and str(error).startswith('CUDA error: out of memory')
                    )
                    if not is_oom:
                        release_exception_frames(error)
                        raise
                    self.model=None;self.path=None;self.vad=None;self.vad_path=None
                    # Finished AutoModel construction frames can retain partially
                    # CUDA-loaded layers even while the public 503 is retained.
                    release_exception_frames(error)
                    gc.collect()
                    try: torch.cuda.empty_cache()
                    except RuntimeError: pass  # Preserve the allocation error.
                    raise ModelWorkerError('CUDA memory exhausted during transcription',
                        code='resource_exhausted',status_code=503) from error
        finally: self.events.pop(request.request_id,None)

def create_adapter(context): return CudaSenseVoiceAdapter(context)
