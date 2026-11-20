"""Standard SoL CUDA image/video Worker, with resident serialized model ownership."""
import asyncio
import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError
from cuda_sol_lifecycle import SoLRequestOwner, check_cancel

MODEL = 'ai2apps.model.sol-refiner-cuda/ltx23-one-step'
CUSTOM_MODEL = 'ai2apps.model.sol-refiner-cuda/ltx23-custom-prompt'
DEFAULT_PROMPT = 'A high quality video with natural details and consistent motion.'


@dataclass
class Work:
    request: object
    root: Path
    model: str
    output: Path
    prompt: str
    seed: int
    loop: object

    @property
    def request_id(self):
        return self.request.request_id


class CudaSoLAdapter:
    def __init__(self, context):
        self.context = context
        self._runner = self._root = self._model = None
        self._owner = SoLRequestOwner(self._render, self._release)

    async def start(self):
        pass

    def cancel(self, request_id):
        self._owner.cancel(request_id)

    async def stop(self):
        await self._owner.stop()

    def _release(self):
        runner, self._runner, self._root = self._runner, None, None
        self._model = None
        if runner is not None:
            runner.close()

    @staticmethod
    def parameters(payload):
        if payload.get('model') not in (MODEL,CUSTOM_MODEL):
            raise ModelWorkerError('Unknown SoL CUDA model', code='model_not_found', status_code=404)
        raw = payload.get('parameters', payload)
        if isinstance(raw, str): raw = json.loads(raw)
        if not isinstance(raw, dict): raise ValueError('parameters must be an object')
        allowed = {'scale','seed','prompt'} | ({'model','parameters'} if raw is payload else set())
        if set(raw)-allowed: raise ValueError('Unsupported upscaling controls')
        scale, seed = raw.get('scale',2), raw.get('seed',0)
        if scale == '2': scale = 2
        if isinstance(seed,str) and seed.isdecimal(): seed = int(seed)
        if type(scale) is not int or scale != 2: raise ValueError('This model supports 2x upscaling')
        if type(seed) is not int or not 0 <= seed < 2**32: raise ValueError('Invalid seed')
        prompt = raw.get('prompt',DEFAULT_PROMPT)
        if not isinstance(prompt,str) or len(prompt)>2048: raise ValueError('Invalid prompt')
        prompt = prompt.strip() or DEFAULT_PROMPT
        if prompt != DEFAULT_PROMPT and payload.get('model') != CUSTOM_MODEL:
            raise ValueError('Custom prompts require the Custom Prompts model')
        return prompt, seed

    def _render(self, work, event):
        import torch
        try:
            return self._render_engine(work, event)
        except torch.cuda.OutOfMemoryError as error:
            self._release()
            raise MemoryError('CUDA memory exhausted during whole-clip upscaling') from error

    def _ensure_runner(self, work, width, height, frames, check, admit, standard_factory, custom_factory):
        if self._runner is not None and (self._root,self._model) != (work.root,work.model):
            self._release()
        check()
        admit(width,height,frames,resident=self._runner is not None,custom=work.model==CUSTOM_MODEL)
        check()
        if self._runner is None:
            factory = custom_factory if work.model==CUSTOM_MODEL else standard_factory
            self._runner = factory(work.root,check)
            self._root,self._model = work.root,work.model
        check()

    def _render_engine(self, work, event):
        from cuda_sol_resources import admit
        from cuda_sol_pipeline import CudaStandardRefiner, CudaCustomRefiner
        from cuda_sol_image import upscale_image
        from cuda_sol_video import upscale_video, _frames
        from sol_mac_image_engine import load_image
        request = work.request
        check = lambda: check_cancel(event)
        check()
        image = request.operation == 'image_upscaling'
        source = request.part('image' if image else 'video').path
        if image:
            rgb, alpha = load_image(source)
            h, w = rgb.shape[:2]
            frames = 1
            del rgb, alpha
        else:
            info = None
            for _, info in _frames(source, check): pass
            if info is None: raise ValueError('Input has no video frames')
            w,h,frames = info['width'],info['height'],info['frames']
        self._ensure_runner(work,w,h,frames,check,admit,CudaStandardRefiner,CudaCustomRefiner)
        async def report(data):
            if request.progress:
                result = request.progress(data)
                if inspect.isawaitable(result): await result
        def progress(data):
            check()
            asyncio.run_coroutine_threadsafe(report(data),work.loop).result(timeout=30)
        if image:
            metadata = upscale_image(source,work.output,work.prompt,work.seed,check,progress,self._runner)
        else:
            self.context.data_root.mkdir(parents=True,exist_ok=True)
            metadata = upscale_video(source,work.output,work.prompt,work.seed,self.context.data_root,
                                     check,progress,self._runner,
                                     lambda w,h,f:admit(w,h,f,resident=True,custom=work.model==CUSTOM_MODEL))
        check()
        return ModelWorkerArtifact(work.output,media_type='image/png' if image else 'video/mp4',
                                   filename='upscaled.png' if image else 'upscaled.mp4',metadata=metadata)

    async def invoke(self, request):
        if request.operation not in {'image_upscaling','video_upscaling'}:
            raise ModelWorkerError('Unsupported operation',code='operation_not_supported')
        if request.output_root is None:
            raise ModelWorkerError('Missing controlled output root',code='runtime_protocol_error',status_code=500)
        image = request.operation == 'image_upscaling'
        try:
            prompt,seed = self.parameters(request.payload)
            source = request.part('image' if image else 'video')
            if not (source.media_type.startswith('image/' if image else 'video/') or source.media_type=='application/octet-stream'):
                raise ValueError('Unsupported media type')
        except (ValueError,TypeError) as error:
            raise ModelWorkerError(str(error),code='invalid_request') from error
        selected_model = request.payload['model']
        checkpoint = self.context.checkpoint_for(selected_model)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError('Host-selected SoL checkpoint required',code='model_unavailable',status_code=503)
        root = Path(checkpoint.path)
        if not all((root/name).is_file() for name in ('model_index.json','context-metadata.json','default-prompt-context.safetensors')):
            raise ModelWorkerError('Incomplete SoL checkpoint',code='checkpoint_incomplete',status_code=503)
        if selected_model == CUSTOM_MODEL and not all((root/name).is_file() for name in (
                'text_encoder/config.json','connectors/config.json','tokenizer/tokenizer_config.json')):
            raise ModelWorkerError('Incomplete Custom Prompts components',code='checkpoint_incomplete',status_code=503)
        output = request.output_root/('upscaled-'+uuid4().hex+('.png' if image else '.mp4'))
        work = Work(request,root,selected_model,output,prompt,seed,asyncio.get_running_loop())
        try:
            return await self._owner.invoke(work)
        except MemoryError as error:
            output.unlink(missing_ok=True)
            raise ModelWorkerError(str(error),code='resource_exhausted',status_code=503) from error
        except (ValueError,OSError) as error:
            output.unlink(missing_ok=True)
            raise ModelWorkerError(str(error),code='invalid_image' if image else 'invalid_video') from error
        except BaseException:
            # The owner drains native work before this request can remove files.
            output.unlink(missing_ok=True)
            raise


def create_adapter(context):
    return CudaSoLAdapter(context)
