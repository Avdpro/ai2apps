"""EchoMimic CUDA Worker with Host-selected weights and serialized GPU ownership."""
import asyncio
from dataclasses import dataclass
import hashlib
import inspect
import json
from pathlib import Path
from uuid import uuid4
from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError
from cuda_sol_lifecycle import SoLRequestOwner

MODEL_ID='ai2apps.model.echomimic-v3-cuda/default'


def inputs(request):
    payload=dict(request.payload)
    for key in ('inputs','parameters','reference_parts'):
        if isinstance(payload.get(key),str):payload[key]=json.loads(payload[key])
    values=payload.get('inputs',{})
    params=payload.get('parameters',payload)
    if not isinstance(values,dict) or not isinstance(params,dict):raise ValueError('inputs/parameters must be objects')
    params=dict(params)
    # Host video controls can accompany a nested model-parameters object.
    # Preserve the selected geometry rather than silently using 512 defaults.
    controls=('resolution','ratio','width','height','fps','framespersecond','seed',
              'preset','long','output_format','audio_output_mode','checkpoint_path')
    for key in controls:
        if key in payload:
            if key in params and params[key]!=payload[key]:
                raise ValueError('Conflicting '+key)
            params[key]=payload[key]
    for key,expected in (('ratio','1:1'),('output_format','mp4'),
                         ('audio_output_mode','preserve_driving_audio')):
        if params.get(key,expected)!=expected:raise ValueError('Unsupported '+key)
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
    resolution=params.get('resolution')
    if resolution is not None and resolution not in ('512x512','768x768'):
        raise ValueError('Unsupported resolution')
    side=int(resolution.split('x')[0]) if resolution is not None else 512
    width=params.get('width',side);height=params.get('height',side)
    if resolution is not None and (width!=side or height!=side):
        raise ValueError('Conflicting resolution and dimensions')
    if 'fps' in params and 'framespersecond' in params and params['fps']!=params['framespersecond']:
        raise ValueError('Conflicting frame rates')
    fps=params.get('fps',params.get('framespersecond',25));seed=params.get('seed',43)
    if any(type(v) is not int for v in (width,height,fps,seed)) or width!=height or width not in (512,768) or fps!=25 or not 0<=seed<2**32:
        raise ValueError('Expected square512/768,25fps and uint32 seed')
    long=params.get('long',False)
    if isinstance(long,str) and long.lower() in ('true','false'):long=long.lower()=='true'
    preset=params.get('preset','exact')
    if type(long) is not bool or preset not in ('exact','fast') or (long and preset=='fast'):
        raise ValueError('Invalid preset/long combination')
    if 'checkpoint_path' in params:raise ValueError('Checkpoint path is owned by the Worker')
    prompt=values.get('prompt',payload.get('prompt','A person is speaking.'))
    if not isinstance(prompt,str) or not prompt.strip():raise ValueError('Nonempty prompt required')
    return image,audio,dict(resolution=width,seed=seed,long=long,preset=preset,prompt=prompt)


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


class CudaEchoMimicAdapter:
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
        import cuda_echomimic_engine
        from cuda_echomimic_engine import CudaEchoMimicEngine
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
                # Fixed sibling source directory provided only by the trusted Runtime profile.
                source=Path(cuda_echomimic_engine.__file__).resolve().parent/'echomimic_source'
                self._engine=CudaEchoMimicEngine(work.root,source,check)
                self._root=work.root
            self._engine.generate(work.image,work.audio,work.output,work.params,check,report)
            check()
            return ModelWorkerArtifact(work.output,'video/mp4','video.mp4',metadata={
                'width':work.params['resolution'],'height':work.params['resolution'],'framespersecond':25,
                'audio_output_mode':'preserve_driving_audio','preset':work.params['preset']})
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
        if params['preset']=='exact' and not params['long']:
            key=hashlib.sha256(request.request_id.encode()).hexdigest()
            params['checkpoint_path']=str(self.context.data_root/'checkpoints'/key/'denoise.safetensors')
        output=request.output_root/('video-'+uuid4().hex+'.mp4')
        work=Work(request,Path(checkpoint.path),image,audio,params,output,asyncio.get_running_loop())
        try:return await self._owner.invoke(work)
        except BaseException:
            output.unlink(missing_ok=True)
            raise


def create_adapter(context):return CudaEchoMimicAdapter(context)
