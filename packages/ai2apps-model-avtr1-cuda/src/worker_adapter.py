"""AVTR CUDA Worker with Host-selected weights and serialized GPU ownership."""
import asyncio
from dataclasses import dataclass
import inspect
import json
from pathlib import Path
from uuid import uuid4
from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError
from cuda_sol_lifecycle import SoLRequestOwner

MODEL_ID='ai2apps.model.avtr1-cuda/default'


def inputs(request):
    payload=dict(request.payload)
    for key in ('inputs','parameters','reference_parts'):
        if isinstance(payload.get(key),str):payload[key]=json.loads(payload[key])
    values=payload.get('inputs',{})
    params=payload.get('parameters',{k:v for k,v in payload.items() if k not in ('model','inputs','reference_parts')})
    if not isinstance(values,dict) or not isinstance(params,dict):raise ValueError('inputs/parameters must be objects')
    allowed={'seconds','duration','steps','seed','output_mode','preset','fps','framespersecond','width','height','resolution','ratio','output_format','audio_output_mode'}
    params=dict(params)
    for key in allowed:
        if key in payload:
            if key in params and params[key]!=payload[key]:
                raise ValueError('Conflicting AVTR '+key)
            params[key]=payload[key]
    refs=payload.get('reference_parts',[])
    if refs:
        if (not isinstance(refs,list) or len(refs)!=1 or not isinstance(refs[0],dict)
            or refs[0].get('kind')!='image' or not isinstance(refs[0].get('part_name'),str)
            or 'reference_image' in values):raise ValueError('One unambiguous reference image required')
        values={**values,'reference_image':{'part_name':refs[0]['part_name']}}
    def part(key,default,types):
        ref=values.get(key,{'part_name':default})
        if not isinstance(ref,dict) or not isinstance(ref.get('part_name'),str):raise ValueError('Invalid input reference')
        value=request.part(ref['part_name'])
        if value.media_type not in types:raise ValueError('Unsupported '+key+' media type')
        return value.path
    image=part('reference_image','image',{'image/png','image/jpeg','image/webp','application/octet-stream'})
    audio=part('driving_audio','audio',{'audio/wav','audio/x-wav','application/octet-stream'})
    from cuda_avtr_engine import parameters
    if set(params)-allowed:raise ValueError('Unsupported AVTR request parameters')
    if params.get('preset','standard') not in ('standard','fast'):raise ValueError('Unknown AVTR preset')
    for key in ('fps','framespersecond'):
        if key in params and (type(params[key]) is not int or params[key]!=25):raise ValueError('AVTR requires25fps')
    for key in ('width','height'):
        if key in params and (type(params[key]) is not int or params[key]!=512):raise ValueError('AVTR model resolution is512px')
    for key,expected in {'resolution':'512x512','ratio':'1:1','output_format':'mp4','audio_output_mode':'preserve_driving_audio'}.items():
        if key in params and params[key]!=expected:raise ValueError('Unsupported AVTR '+key)
    if 'seconds' in params and 'duration' in params:raise ValueError('Ambiguous duration')
    selected={k:params[k] for k in ('steps','seed','output_mode','preset') if k in params}
    selected['seconds']=params.get('seconds',params.get('duration',60))
    return image,audio,parameters(selected)



@dataclass
class Work:
    request:object
    root:Path
    image:Path
    audio:Path
    params:dict
    output:Path
    loop:object
    @property
    def request_id(self):return self.request.request_id


class CudaAVTRAdapter:
    def __init__(self,context):
        self.context=context
        self._engine=self._root=None
        self._owner=SoLRequestOwner(self._render,self._release)
    async def start(self):pass
    async def stop(self):await self._owner.stop()
    def cancel(self,request_id):self._owner.cancel(request_id)
    def _release(self):
        engine,self._engine,self._root=self._engine,None,None
        if engine is not None:engine.close()
    def _render(self,work,event):
        import torch
        from cuda_avtr_engine import CudaAVTREngine
        def check():
            if event.is_set():raise ModelWorkerError('Generation cancelled',code='generation_cancelled',status_code=499)
        async def emit(data):
            if work.request.progress:
                value=work.request.progress(data)
                if inspect.isawaitable(value):await value
        def report(phase,current,total):
            check()
            asyncio.run_coroutine_threadsafe(emit(dict(phase=phase,current=current,total=total)),work.loop).result(timeout=30)
        try:
            check()
            if self._engine is not None and self._root!=work.root:self._release()
            if self._engine is None:
                self._engine=CudaAVTREngine(work.root,check)
                self._root=work.root
            result=self._engine.generate(work.image,work.audio,work.output,work.params,check,report)
            check()
            return ModelWorkerArtifact(work.output,'video/mp4','video.mp4',metadata={
                'width':result['resolution'][0],'height':result['resolution'][1],'framespersecond':25,
                'frames':result['frames'],'audio_output_mode':'preserve_driving_audio','preset':work.params['preset'],
                'approximate':work.params['preset']=='fast','render_fallbacks':result['render_fallbacks']})
        except torch.cuda.OutOfMemoryError as error:
            self._release()
            raise ModelWorkerError('CUDA memory exhausted',code='resource_exhausted',status_code=503) from error
        except (ValueError,OSError) as error:
            raise ModelWorkerError(str(error),code='invalid_request_or_checkpoint',status_code=400) from error
    async def invoke(self,request):
        if request.operation!='video_generation':raise ModelWorkerError('Unsupported operation',code='operation_not_supported',status_code=400)
        if request.payload.get('model',MODEL_ID)!=MODEL_ID:raise ModelWorkerError('Unknown model',code='model_not_found',status_code=404)
        if request.output_root is None:raise ModelWorkerError('Controlled output root required',code='runtime_protocol_error',status_code=500)
        try:image,audio,params=inputs(request)
        except (ValueError,TypeError) as error:raise ModelWorkerError(str(error),code='invalid_request',status_code=400) from error
        checkpoint=self.context.checkpoint_for(MODEL_ID)
        if checkpoint is None or checkpoint.path is None:raise ModelWorkerError('Host checkpoint required',code='checkpoint_not_ready',status_code=409)
        output=request.output_root/('video-'+uuid4().hex+'.mp4')
        work=Work(request,Path(checkpoint.path),image,audio,params,output,asyncio.get_running_loop())
        try:return await self._owner.invoke(work)
        except BaseException:
            output.unlink(missing_ok=True)
            output.with_suffix('.encoding.mp4').unlink(missing_ok=True)
            output.with_suffix('.json').unlink(missing_ok=True)
            raise


def create_adapter(context):return CudaAVTRAdapter(context)
