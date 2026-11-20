"""Serialized CUDA Seed-VC Worker with pinned checkpoint and cancellation."""
import asyncio
import gc
import math
import threading
from pathlib import Path
from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError

MODEL_ID = 'ai2apps.model.seed-vc-v2-cuda/default'
CHECKPOINT = ('Avdpro/MLX-Seed-VC-v2', '2122cee1aff2b0e17a843dfa7cdc0464271c43b4')
PROFILES = {'timbre_fast': ('timbre', 10), 'timbre_quality': ('timbre', 30), 'voice_quality': ('voice', 30)}

def invalid(message, code='invalid_request', status=400):
    raise ModelWorkerError(message, code=code, status_code=status)

def number(payload, key, default, integral=False):
    value = payload.get(key, default)
    if value is None or value == '':value = default
    if isinstance(value, bool):invalid(key + ' must be numeric')
    try:
        result = float(value)
        if not math.isfinite(result) or (integral and result != int(result)):raise ValueError()
        return int(result) if integral else result
    except (TypeError, ValueError, OverflowError):invalid('invalid ' + key)

class CudaSeedVCAdapter:
    def __init__(self, context):
        self.context=context;self.lock=asyncio.Lock();self.events={};self.pipeline=None;self.path=None;self.stopped=False

    async def start(self):self.stopped=False

    def cancel(self, request_id):
        if request_id in self.events:self.events[request_id].set()

    async def stop(self):
        self.stopped=True
        for event in self.events.values():event.set()
        async with self.lock:
            self.pipeline=None;self.path=None;gc.collect()
            import torch
            torch.cuda.empty_cache()

    async def invoke(self, request):
        if self.stopped:invalid('Seed-VC Worker stopped','model_unavailable',503)
        if request.request_id in self.events:invalid('Duplicate active request id','request_conflict',409)
        if request.operation!='audio_process':invalid('Unsupported operation','operation_not_supported')
        payload=dict(request.payload)
        if not isinstance(payload.get('model'),str) or payload['model'] not in {MODEL_ID,CHECKPOINT[0]}:invalid('Unsupported Seed-VC model','model_not_found',404)
        if payload.get('task','voice_conversion')!='voice_conversion':invalid('Unsupported audio task')
        checkpoint=self.context.checkpoint_for(MODEL_ID)
        if checkpoint is None or checkpoint.path is None:invalid('Checkpoint not installed','model_unavailable',503)
        if (checkpoint.repo_id,checkpoint.revision)!=CHECKPOINT:invalid('Unsupported checkpoint','model_not_supported')
        profile=payload.get('profile') or 'timbre_quality'
        if not isinstance(profile,str) or profile not in PROFILES:invalid('Unsupported voice conversion profile')
        default_mode,default_steps=PROFILES[profile]
        mode=payload.get('mode') or default_mode
        if mode not in ('timbre','voice'):invalid('mode must be timbre or voice')
        steps=number(payload,'diffusion_steps',default_steps,True)
        guidance=(number(payload,'guidance_intelligibility',.5),number(payload,'guidance_similarity',.5))
        length=number(payload,'length_adjust',1.)
        seed=number(payload,'seed',0,True)
        if not 1<=steps<=100 or not all(0<=x<=5 for x in guidance) or not .5<=length<=2 or not 0<=seed<2**32:
            invalid('Voice conversion controls out of range')
        if request.output_root is None:invalid('Controlled output root required','runtime_protocol_error')
        try:source=request.part('file').path;reference=request.part('reference').path
        except (KeyError,ValueError):invalid('Source and reference audio are required')
        output=Path(request.output_root);output.mkdir(parents=True,exist_ok=True)
        event=threading.Event();self.events[request.request_id]=event
        def check():
            if event.is_set() or self.stopped:raise InterruptedError('Seed-VC request cancelled')
        def run():
            import numpy as np
            import soundfile as sf
            from scipy.signal import resample_poly
            from cuda_seed_vc_pipeline import CudaSeedVCV2
            import torch
            # Match the fixed FP32 parity baseline inside this dedicated Worker process.
            torch.backends.cuda.matmul.allow_tf32=False
            torch.backends.cudnn.allow_tf32=False
            torch.backends.cudnn.benchmark=False
            torch.backends.cudnn.deterministic=True
            def read(path):
                audio,rate=sf.read(path,dtype='float32')
                if audio.ndim==2:audio=audio.mean(axis=1)
                if rate!=22050:
                    divisor=math.gcd(rate,22050);audio=resample_poly(audio,22050//divisor,rate//divisor).astype(np.float32)
                if audio.ndim!=1 or len(audio)<1024 or not np.isfinite(audio).all():raise ValueError('Invalid or too-short audio')
                return audio
            check();audio=read(source);target_audio=read(reference);check()
            if self.pipeline is None or self.path!=checkpoint.path:
                self.pipeline=CudaSeedVCV2(checkpoint.path);self.path=checkpoint.path
            wave=self.pipeline.convert(audio,target_audio,mode=mode,diffusion_steps=steps,guidance=guidance,length_adjust=length,seed=seed,check=check)
            check();target=output/'voice-converted.wav'
            try:
                with target.open('xb') as stream:sf.write(stream,wave,22050,format='WAV',subtype='PCM_16')
                check()
            except FileExistsError:raise
            except BaseException:target.unlink(missing_ok=True);raise
            return ModelWorkerArtifact(target,media_type='audio/wav',filename=target.name)
        try:
            async with self.lock:
                check();task=asyncio.create_task(asyncio.to_thread(run))
                try:return await asyncio.shield(task)
                except asyncio.CancelledError:
                    event.set()
                    while not task.done():
                        try:await asyncio.shield(task)
                        except asyncio.CancelledError:continue
                        except Exception:break
                    if not task.cancelled():task.exception()
                    raise
        except InterruptedError as exc:invalid(str(exc),'request_cancelled',499)
        except (ValueError,OSError) as exc:invalid(str(exc),'audio_processing_failed',422)
        except RuntimeError as exc:invalid(str(exc),'audio_processing_failed',422)
        finally:self.events.pop(request.request_id,None)

def create_adapter(context):return CudaSeedVCAdapter(context)
