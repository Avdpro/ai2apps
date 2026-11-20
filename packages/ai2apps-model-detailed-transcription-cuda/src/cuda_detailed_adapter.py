"""Detailed-transcription Worker controller; stage paths are trusted runtime inputs.

Runtime profile resolution and multi-format transport decoding are separate
integration gates. This controller currently accepts normalized PCM16 WAV.
"""
from __future__ import annotations
import asyncio
from pathlib import Path
import threading
from ai2apps.model_worker.protocol import ModelWorkerError
from cuda_detailed_engine import CudaDetailedEngine, DetailedCheckpoints
from cuda_detailed_process import DetailedCancelled, DetailedStageProcess

PREFIX='ai2apps.model.detailed-transcription-cuda/'
PINS={
 'compact':('Qwen/Qwen3-ASR-0.6B','5eb144179a02acc5e5ba31e748d22b0cf3e303b0'),
 'quality':('Qwen/Qwen3-ASR-1.7B','7278e1e70fe206f11671096ffdd38061171dd6e5'),
 'forced-aligner':('Qwen/Qwen3-ForcedAligner-0.6B','c7cbfc2048c462b0d63a45797104fc9db3ad62b7'),
 'diarizer':('nvidia/diar_streaming_sortformer_4spk-v2.1','cd03eee90fbec18297ac31b8c21546e596b7f71c'),
}

def fail(message,code='invalid_request',status=400):
    raise ModelWorkerError(message,code=code,status_code=status)


def enabled(value,default=False):
    if value is None:return default
    if isinstance(value,dict):return enabled(value.get('enabled'),True)
    if type(value) is bool:return value
    if isinstance(value,str):
        if value.lower() in ('true','1','yes','on'):return True
        if value.lower() in ('false','0','no','off'):return False
    fail('Invalid boolean option')


class CudaDetailedAdapter:
    def __init__(self,context,stages,*,engine_factory=CudaDetailedEngine):
        self.context,self.stages,self.engine_factory=context,stages,engine_factory
        self._owner=asyncio.Lock();self._lifecycle=asyncio.Lock()
        self._events={};self._stopping=False

    async def start(self):
        async with self._lifecycle:
            async with self._owner:self._stopping=False

    async def stop(self):
        async with self._lifecycle:
            self._stopping=True
            for event in self._events.values():event.set()
            async with self._owner:pass

    def cancel(self,request_id):
        if event:=self._events.get(request_id):event.set()

    def _checkpoint(self,variant):
        checkpoint=self.context.checkpoint_for(PREFIX+variant)
        if checkpoint is None or checkpoint.path is None:
            fail('Required checkpoint is unavailable','model_unavailable',503)
        if (checkpoint.repo_id,checkpoint.revision)!=PINS[variant]:
            fail('Unexpected detailed-transcription checkpoint','model_not_supported')
        path = Path(checkpoint.path)
        # Installed checkpoint distributions expose a snapshot directory. The
        # official NeMo restore API requires the single archive inside it.
        if variant == 'diarizer' and path.is_dir():
            path = path / 'diar_streaming_sortformer_4spk-v2.1.nemo'
            if not path.is_file():
                fail('Sortformer archive is missing from checkpoint snapshot','model_unavailable',503)
        return path

    async def invoke(self,request):
        if self._stopping:fail('Worker is stopping','worker_stopping',503)
        if request.request_id in self._events:fail('Request already active','request_conflict',409)
        if request.operation!='audio_detailed_transcription':fail('Unsupported operation','operation_not_supported')
        body=dict(request.payload);model=body.get('model')
        # The Host forwards the declared upstream ID to the Worker. Only the
        # two pinned ASR aliases are valid; helper checkpoints are not entrypoints.
        for profile in ('compact','quality'):
            if model == PINS[profile][0]:
                model = PREFIX+profile
                break
        if model not in (PREFIX+'compact',PREFIX+'quality'):fail('Unknown detailed-transcription model','model_not_found',404)
        for key in ('language','prompt'):
            if body.get(key) is not None and not isinstance(body[key],str):
                fail(f'{key} must be a string')
        for key,allowed,default in (
            ('timestamps',('word','segment'),'word'),
            ('vad',('meeting-energy','energy','none'),'meeting-energy'),
            ('unsupported_policy',('reject','compatibility'),'reject'),
            ('response_format',('json','verbose_json'),'json'),
        ):
            if (body.get(key) or default) not in allowed:fail(f'Invalid {key}')
        if enabled(body.get('stream')) or body.get('_ai2apps_model_settings'):
            fail('Streaming and custom runtime settings are unsupported','unsupported_feature')
        options={key:enabled(body.get(key),default) for key,default in (
            ('diarization',True),('speech_rate_analysis',False),('emotion_recognition',False),('speaker_recognition',False))}
        options.update(profile=model.rsplit('/',1)[1],language=body.get('language') or None,
                       prompt=body.get('prompt') or None,timestamps=body.get('timestamps') or 'word',
                       unsupported_policy=body.get('unsupported_policy') or 'reject',vad=body.get('vad') or 'meeting-energy')
        if options['speaker_recognition'] or (options['emotion_recognition'] and options['unsupported_policy']!='compatibility'):
            fail('Requested recognition feature is unsupported','unsupported_feature')
        selected=self._checkpoint(options['profile'])
        aligner=self._checkpoint('forced-aligner') if options['timestamps']=='word' else Path('.')
        diarizer=self._checkpoint('diarizer') if options['diarization'] else Path('.')
        engine=self.engine_factory(self.stages,DetailedCheckpoints(selected,selected,aligner,diarizer))
        path=request.part('file').path;event=threading.Event();self._events[request.request_id]=event
        try:
            async with self._owner:
                if event.is_set():raise DetailedCancelled('Detailed transcription cancelled')
                task=asyncio.create_task(asyncio.to_thread(engine.transcribe_wav,path,event,**options))
                try:
                    result=await asyncio.shield(task)
                except asyncio.CancelledError:
                    # Keep ownership until the thread has reaped its model process.
                    event.set()
                    while not task.done():
                        try:await asyncio.shield(task)
                        except asyncio.CancelledError:continue
                        except Exception:break
                    if task.done() and not task.cancelled():task.exception()
                    raise
                if event.is_set():raise DetailedCancelled('Detailed transcription cancelled')
                result['features']['transcription']['revision']=PINS[options['profile']][1]
                if options['timestamps']=='word':result['features']['alignment']['revision']=PINS['forced-aligner'][1]
                if options['diarization']:result['features']['diarization']['revision']=PINS['diarizer'][1]
                return result
        except DetailedCancelled as error:fail(str(error),'request_cancelled',499)
        except ValueError as error:fail(str(error))
        finally:self._events.pop(request.request_id,None)


def create_adapter(context):
    """Production entry uses only the executing Runtime's signed stage mapping."""
    import sys
    from ai2apps.model_worker import runtime_profiles
    root = Path(runtime_profiles.__file__).resolve().parents[3]
    stages = DetailedStageProcess.from_runtime(root, Path(sys.executable), context.service_id)
    return CudaDetailedAdapter(context, stages)
