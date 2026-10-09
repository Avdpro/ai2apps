# SPDX-License-Identifier: Apache-2.0
"""H3 CUDA adapter using a Runtime-owned private Comfy process."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import shutil
import sys
import uuid

from .h3_process import H3Process
from .h3_turbo import apply_lightx2v_4step, apply_lightx2v_8step, LORA_4STEP, LORA_8STEP
from .protocol import ModelWorkerArtifact, ModelWorkerError


class CudaH3Adapter:
    TURBO_RECIPES = {
        'lightx2v-8step-v1.0-768p': (8, LORA_8STEP, apply_lightx2v_8step),
        'lightx2v-4step-v1.2-768p': (4, LORA_4STEP, apply_lightx2v_4step),
    }

    def __init__(self, context):
        self.context=context
        self.worker=None
        self.events={}
        self.lock=asyncio.Lock()
        self.checkpoint=None
        self.stopping=False

    async def start(self):
        self.stopping=False

    def cancel(self, request_id):
        if event:=self.events.get(request_id):
            event.set()

    async def stop(self):
        self.stopping=True
        for event in self.events.values():event.set()
        async with self.lock:
            await self._stop_child()

    async def _stop_child(self):
        if self.worker:
            await self.worker.stop()
            shutil.rmtree(self.worker.root)
            self.worker=None
            self.checkpoint=None

    @staticmethod
    def parameters(payload):
        def integer(name,default):
            value=payload.get(name,default)
            if isinstance(value,bool) or isinstance(value,float) and not value.is_integer():
                raise ValueError(name+' must be an integer')
            return int(value)
        prompt=str(payload.get('prompt') or '').strip()
        if not 1<=len(prompt)<=8192:raise ValueError('prompt must contain 1–8192 characters')
        width,height=integer('width',512),integer('height',512)
        if min(width,height)<32 or width%32 or height%32 or min(width,height)>768 or max(width,height)>1344:
            raise ValueError('H3 canvas must be multiples of 32 within 768×1344')
        duration=payload.get('duration',payload.get('seconds',5))
        if isinstance(duration,bool):raise ValueError('duration must be numeric')
        duration=float(duration)
        steps,seed=integer('steps',8),integer('seed',42)
        if not math.isfinite(duration) or not .92<=duration<=15.1:raise ValueError('duration must be 0.92–15.1 seconds')
        if not 2<=steps<=50 or not 0<=seed<2**64:raise ValueError('steps or seed is out of range')
        if any(payload.get(k) not in (None,False,'false') for k in ('fast','fast_max')):
            raise ValueError('CUDA H3 fast variants are not yet installed')
        return prompt,width,height,duration,steps,seed

    def backend(self):
        path=self.worker.trusted_file('h3/H3Studio/h3_backend.py')
        name='_ai2apps_h3_'+hashlib.sha256(str(path).encode()).hexdigest()[:16]
        if name not in sys.modules:
            spec=importlib.util.spec_from_file_location(name,path)
            module=importlib.util.module_from_spec(spec)
            sys.modules[name]=module
            try:spec.loader.exec_module(module)
            except BaseException:
                sys.modules.pop(name,None)
                raise
        return sys.modules[name]

    @staticmethod
    def validate_media(path,kind):
        import av
        with av.open(str(path)) as container:
            streams=[s for s in container.streams if s.type==kind]
            if not streams:raise ValueError('Reference has no '+kind+' stream')
            stream=streams[0]
            if stream.duration is not None and stream.time_base is not None:
                seconds=float(stream.duration*stream.time_base)
            elif container.duration is not None:
                seconds=float(container.duration/av.time_base)
            else:raise ValueError('Reference must declare a bounded duration')
            if not math.isfinite(seconds) or not 0<seconds<=15.1:
                raise ValueError('Reference duration must be at most 15.1 seconds')
            if kind=='video' and stream.codec_context.width*stream.codec_context.height>16777216:
                raise ValueError('Reference video exceeds 16 megapixels')

    def resolve_model(self, identity):
        matches = [m for m in self.context.models if m['id'] == identity]
        if not matches:
            matches = [m for m in self.context.models if m.get('upstream_id') == identity]
        if len(matches) != 1:
            raise ModelWorkerError('H3 model identity is missing or ambiguous',
                                   code='model_not_supported')
        specification = dict(matches[0])
        # Host normalization retains extension fields only inside metadata.
        # Keep legacy development fixtures readable, but reject contradictory
        # values rather than silently selecting a different checkpoint recipe.
        metadata = specification.get('metadata', {})
        if not isinstance(metadata, dict):
            raise ModelWorkerError('H3 model metadata is invalid', code='model_not_supported')
        for key in ('h3_variant', 'h3_turbo', 'h3_lora_model_id'):
            if key in metadata:
                if key in specification and specification[key] != metadata[key]:
                    raise ModelWorkerError('Conflicting H3 model metadata', code='model_not_supported')
                specification[key] = metadata[key]
        # Resolve checkpoint by canonical ID; a shared repository is not a variant.
        return specification, self.context.checkpoint_for(specification['id'])

    def resolve_turbo(self, specification):
        recipe = specification.get('h3_turbo')
        if recipe is None:
            return None
        if not isinstance(recipe, str) or recipe not in self.TURBO_RECIPES or specification.get('h3_variant') != 'fl2va':
            raise ModelWorkerError('Unsupported H3 Turbo recipe', code='model_not_supported')
        identity = specification.get('h3_lora_model_id')
        if not isinstance(identity, str) or not identity:
            raise ModelWorkerError('H3 Turbo overlay identity missing', code='model_not_supported')
        overlay = self.context.checkpoint_for(identity)
        if overlay is None or overlay.path is None:
            raise ModelWorkerError('H3 Turbo checkpoint not installed', code='model_unavailable', status_code=503)
        if (overlay.repo_id != 'lightx2v/Minimax-h3-Turbo'
                or overlay.revision != '2f015e66b37c585cea9dc4ae6f1850ea8788e742'):
            raise ModelWorkerError('H3 Turbo checkpoint revision mismatch', code='model_not_supported')
        root = Path(overlay.path).resolve(strict=True)
        weight = (root / 'loras' / self.TURBO_RECIPES[recipe][1]).resolve(strict=True)
        if not weight.is_relative_to(root) or not weight.is_file():
            raise ModelWorkerError('Invalid H3 Turbo checkpoint layout', code='model_unavailable', status_code=503)
        return root

    async def invoke(self, request):
        if self.stopping:
            raise ModelWorkerError("Worker is stopping", code="worker_stopping", status_code=503)
        if request.request_id in self.events:
            raise ModelWorkerError("Request already active", code="request_conflict", status_code=409)
        if request.operation!='video_generation':
            raise ModelWorkerError('Unsupported operation',code='operation_not_supported')
        payload=dict(request.payload)
        try:parameters=self.parameters(payload)
        except (ValueError,TypeError,OverflowError) as error:
            raise ModelWorkerError(str(error),code='invalid_request') from error
        model=str(payload.get('model') or '')
        specification, checkpoint = self.resolve_model(model)
        if specification is None or checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError('H3 checkpoint not installed',code='model_unavailable',status_code=503)
        variant=specification.get('h3_variant')
        if variant not in ('fl2va','ref2va') or checkpoint.repo_id!='Comfy-Org/MiniMax-H3':
            raise ModelWorkerError('H3 variant is not supported',code='model_not_supported')
        try:
            overlay = self.resolve_turbo(specification)
        except OSError as error:
            raise ModelWorkerError('H3 Turbo checkpoint unavailable', code='model_unavailable', status_code=503) from error
        turbo = self.TURBO_RECIPES[specification['h3_turbo']] if overlay is not None else None
        if turbo is not None:
            if 'steps' not in payload:
                parameters = (*parameters[:4], turbo[0], parameters[5])
            elif parameters[4] != turbo[0]:
                raise ModelWorkerError(f'This H3 Turbo recipe requires {turbo[0]} steps', code='invalid_request')
        if request.output_root is None:
            raise ModelWorkerError('Controlled output root missing',code='runtime_protocol_error',status_code=500)
        event=asyncio.Event()
        self.events[request.request_id]=event
        token=uuid.uuid4().hex
        input_root=None
        try:
            async with self.lock:
                if event.is_set():raise asyncio.CancelledError
                checkpoint_key = (checkpoint.path, overlay)
                if self.checkpoint!=checkpoint_key:
                    await self._stop_child()
                    # This environment value is supplied by the trusted Host.
                    runtime=Path(os.environ['AI2APPS_INFERENCE_RUNTIME'])
                    options = {} if overlay is None else {'lora_checkpoint': overlay}
                    self.worker=H3Process(runtime,checkpoint.path,self.context.data_root, **options)
                    self.checkpoint=checkpoint_key
                await self.worker.start()
                backend=self.backend()
                input_root=self.worker.root/'input'/token
                input_root.mkdir()
                used=set()
                def image_part(name):
                    part=(request.parts or {}).get(name)
                    if part is None:return None
                    from PIL import Image, ImageOps
                    with Image.open(part.path) as image:
                        if image.width*image.height>16777216:raise ValueError('Reference exceeds 16 megapixels')
                        image=ImageOps.exif_transpose(image).convert('RGB')
                        target=input_root/(str(len(used))+'.png')
                        image.save(target)
                    used.add(name)
                    return target.relative_to(self.worker.root/'input').as_posix()
                def media_part(name,kind):
                    part=(request.parts or {}).get(name)
                    if part is None:raise ValueError('Missing reference part')
                    allowed={'audio':{'.wav','.mp3','.m4a','.aac','.flac'},'video':{'.mp4','.mov','.webm'}}
                    suffix=Path(part.filename).suffix.lower()
                    if suffix not in allowed[kind]:raise ValueError('Unsupported reference media format')
                    # Reference duration is independent of generated duration.
                    self.validate_media(part.path,kind)
                    target=input_root/(str(len(used))+suffix)
                    shutil.copyfile(part.path,target)
                    used.add(name)
                    return target.relative_to(self.worker.root/'input').as_posix()
                try:
                    first=image_part('image') or image_part('first_frame')
                    last=image_part('last_image') or image_part('last_frame')
                    references=payload.get('reference_parts',[])
                    if isinstance(references,str):references=json.loads(references)
                    if not isinstance(references,list):raise ValueError('reference_parts must be an array')
                    images=[]
                    media={}
                    for item in references:
                        if not isinstance(item,dict) or item.get('kind') not in ('image','audio','video'):
                            raise ValueError('Reference kind must be image, audio or video')
                        name=item.get('part_name')
                        if not isinstance(name,str) or name in used:raise ValueError('Invalid or duplicate reference part')
                        kind=item['kind']
                        if kind=='image':
                            reference=image_part(name)
                            if reference is None:raise ValueError('Missing reference part')
                            images.append(reference)
                        else:
                            if kind in media:raise ValueError('Only one '+kind+' reference is supported')
                            media[kind]=media_part(name,kind)
                    if set(request.parts or {})!=used:raise ValueError('Unsupported or duplicate request parts')
                    if variant=='ref2va' and (not images and not media or len(images)>4 or first or last):
                        raise ValueError('Ref2VA requires reference material and no first/last frames')
                    if variant=='fl2va' and (images or media):raise ValueError('Reference material requires Ref2VA')
                    use_video_audio=payload.get('include_reference_video_audio',True)
                    if use_video_audio in ('true','false'):use_video_audio=use_video_audio=='true'
                    if not isinstance(use_video_audio,bool):raise ValueError('include_reference_video_audio must be boolean')
                    prompt,width,height,duration,steps,seed=parameters
                    models=backend.ModelSet(f'minimax_h3_{variant}_pruned_int8_convrot.safetensors',
                        'qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors','minimax_h3_video_vae_fp16.safetensors','minimax_h3_audio_vae_fp32.safetensors')
                    args=(prompt,width,height,backend.snap_length(duration),models,backend.SamplingSettings(steps=steps,seed=seed),seed)
                    if variant=='ref2va':graph=backend.build_reference_graph(*args,backend.ReferenceInputs(images=images,
                        video=media.get('video'),audio=media.get('audio'),use_video_audio=use_video_audio,image_size_mode='match'),prefix=token)
                    else:graph=backend.build_video_graph(*args,first_frame=first,last_frame=last,prefix=token)
                    if overlay is not None:
                        graph = turbo[2](graph)
                except (ValueError,OSError,TypeError) as error:
                    raise ModelWorkerError(str(error),code='invalid_request') from error
                if request.progress:
                    result=request.progress({'phase':'generate','current':0,'total':1})
                    if inspect.isawaitable(result):await result
                outputs=await self.worker.run(graph,event)
                item=next(f for out in outputs.values() for f in out.get('images',[]) if f['filename'].endswith('.mp4'))
                source=self.worker.output_path(item['filename'],item.get('subfolder',''))
                target=request.output_root/(token+'.mp4')
                shutil.move(source,target)
                return ModelWorkerArtifact(target,media_type='video/mp4',filename=target.name,
                    metadata={'model':model,'attribution':'Powered by MiniMax H3'})
        except asyncio.CancelledError as error:
            raise ModelWorkerError('Video request cancelled',code='request_cancelled',status_code=499) from error
        finally:
            self.events.pop(request.request_id,None)
            if input_root:shutil.rmtree(input_root,ignore_errors=True)


def create_adapter(context):
    return CudaH3Adapter(context)
