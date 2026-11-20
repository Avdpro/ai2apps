"""SAM2.1 CUDA Worker with shared Mac mask controls and encoding."""
import asyncio
import gc
import hashlib
import json
import threading
from pathlib import Path

import numpy as np
from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError
from sam21_mac_adapter import SAM21Adapter

MODEL = 'ai2apps.model.sam21-cuda/small'
WEIGHTS_SHA = 'f3e03d4ec31315e9feea2ca161ce7cb9f9a932e545ab63e40e7fb4da19c3b813'
ORIGINAL_WEIGHTS_SHA = '6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38'


def check_cancel(event):
    if event.is_set():
        raise ModelWorkerError('SAM2 generation cancelled', code='generation_cancelled', status_code=499)


class CudaSAM21Adapter(SAM21Adapter):
    def __init__(self, context):
        super().__init__(context)
        self._pending = {}
        self._closing = False

    def cancel(self, request_id):
        event = self._pending.get(request_id)
        if event is not None:
            event.set()

    async def stop(self):
        self._closing = True
        for event in self._pending.values():
            event.set()
        async with self._lock:
            self._predictor = self._checkpoint = None
            gc.collect()
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    @staticmethod
    def checkpoint_state(checkpoint):
        """Only the two pinned Meta-format representations are accepted."""
        original = checkpoint.name == 'sam2.1_hiera_small.pt'
        if not original and checkpoint.name != 'sam2.1_hiera_small.safetensors':
            raise ModelWorkerError('Unsupported SAM2 checkpoint format', code='invalid_checkpoint', status_code=503)
        with checkpoint.open('rb') as stream:
            expected = ORIGINAL_WEIGHTS_SHA if original else WEIGHTS_SHA
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                raise ModelWorkerError('Unexpected SAM2.1 checkpoint', code='invalid_checkpoint', status_code=503)
            if original:
                import torch
                stream.seek(0)
                # Same verified file descriptor; never use unrestricted pickle.
                value = torch.load(stream, map_location='cpu', weights_only=True)
                state = value.get('model') if isinstance(value, dict) else None
                if not isinstance(state, dict) or len(state) != 519 or not all(torch.is_tensor(v) for v in state.values()):
                    raise ModelWorkerError('Invalid SAM2 tensor state', code='invalid_checkpoint', status_code=503)
                return state
        from safetensors.torch import load_file
        return load_file(str(checkpoint))

    def _load(self, checkpoint):
        if self._predictor is not None and self._checkpoint == checkpoint:
            return self._predictor
        import torch
        from sam2.build_sam import build_sam2_video_predictor
        state = self.checkpoint_state(checkpoint)
        if not torch.cuda.is_available():
            raise ModelWorkerError('CUDA is required', code='runtime_unavailable', status_code=503)
        model = build_sam2_video_predictor('configs/sam2.1/sam2.1_hiera_s.yaml',
                                          device='cpu', apply_postprocessing=False)
        model.load_state_dict(state, strict=True)
        self._predictor = model.eval().requires_grad_(False).to('cuda')
        self._checkpoint = checkpoint
        return self._predictor

    @staticmethod
    def _validate(payload):
        raw = payload.get('parameters', payload)
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, dict):
            raise ValueError('parameters must be an object')
        allowed = {'prompt_frame', 'points', 'threshold', 'feather'}
        if raw is payload:
            allowed |= {'model', 'parameters'}
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError('Unsupported controls: ' + ', '.join(sorted(unknown)))
        result = SAM21Adapter._parameters({'parameters': raw})
        if not np.isfinite(result[1]).all():
            raise ValueError('Point coordinates must be finite')
        return result

    def _render(self, request, parameters, checkpoint, event):
        import torch
        check_cancel(event)
        prompt_frame, points, labels, threshold, feather = parameters
        try:
            frames, rate = self._decode(request.part('video').path)
            height, width = frames.shape[1:3]
            if len(frames) / float(rate) > 18.75:
                raise ValueError('Video exceeds 18.75 seconds')
            if prompt_frame >= len(frames):
                raise ValueError('prompt_frame is outside the source video')
            if (points < 0).any() or (points[:, 0] >= width).any() or (points[:, 1] >= height).any():
                raise ValueError('Point coordinates must be inside the video frame')
        except (ValueError, TypeError, OSError) as error:
            raise ModelWorkerError(str(error), code='invalid_request') from error
        check_cancel(event)
        predictor = self._load(checkpoint)
        hooks = [module.register_forward_pre_hook(lambda _module, _inputs: check_cancel(event))
                 for module in predictor.modules()]
        state = None
        try:
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                state = predictor.init_state(frames, offload_video_to_cpu=True)
                check_cancel(event)
                predictor.add_new_points_or_box(state, frame_idx=prompt_frame, obj_id=1,
                                                 points=points, labels=labels)
                collected = [np.full((height, width), -30, np.float32) for _ in range(prompt_frame)]
                for index, ids, logits in predictor.propagate_in_video(state, start_frame_idx=prompt_frame):
                    check_cancel(event)
                    if index != len(collected) or ids != [1]:
                        raise RuntimeError('Unexpected SAM2 frame/object order')
                    mask = logits[0, 0].float().cpu().numpy()
                    if not np.isfinite(mask).all():
                        raise RuntimeError('Nonfinite SAM2 mask')
                    collected.append(mask)
                if len(collected) != len(frames):
                    raise RuntimeError('SAM2 did not return every frame')
            check_cancel(event)
            output = request.output_root / 'sam21-mask.mp4'
            self._write_masks(output, collected, rate, threshold, feather)
            check_cancel(event)
            return ModelWorkerArtifact(output, media_type='video/mp4', filename=output.name,
                metadata={'kind':'video_mask', 'frames':len(collected), 'soft':True,
                          'prompt_frame':prompt_frame, 'precision':'bf16_autocast'})
        finally:
            for hook in hooks:
                hook.remove()
            if state is not None:
                predictor.reset_state(state)

    async def invoke(self, request):
        if request.operation != 'video_segmentation':
            raise ModelWorkerError('Unsupported operation', code='operation_not_supported')
        if request.payload.get('model') != MODEL:
            raise ModelWorkerError('Unknown SAM2.1 CUDA model', code='model_not_found', status_code=404)
        if request.output_root is None:
            raise ModelWorkerError('Missing controlled output root', code='runtime_protocol_error', status_code=500)
        try:
            parameters = self._validate(dict(request.payload))
            request.part('video')
        except (ValueError, TypeError) as error:
            raise ModelWorkerError(str(error), code='invalid_request') from error
        selected = self.context.checkpoint_for(MODEL)
        if selected is None or selected.path is None:
            raise ModelWorkerError('Host-selected SAM2.1 checkpoint required', code='model_unavailable', status_code=503)
        checkpoint = Path(selected.path) / 'sam2.1_hiera_small.safetensors'
        if not checkpoint.is_file():
            checkpoint = Path(selected.path) / 'sam2.1_hiera_small.pt'
        if not checkpoint.is_file():
            raise ModelWorkerError('Missing SAM2.1 checkpoint', code='checkpoint_incomplete', status_code=503)
        event = threading.Event()
        self._pending[request.request_id] = event
        try:
            async with self._lock:
                if self._closing:
                    raise ModelWorkerError('Worker is stopping', code='worker_stopping', status_code=503)
                check_cancel(event)
                task = asyncio.create_task(asyncio.to_thread(self._render, request, parameters, checkpoint, event))
                try:
                    return await asyncio.shield(task)
                except asyncio.CancelledError:
                    event.set()
                    while not task.done():
                        try:
                            await asyncio.shield(task)
                        except asyncio.CancelledError:
                            event.set()
                        except Exception:
                            break
                    if task.done() and not task.cancelled():
                        task.exception()
                    raise
        finally:
            self._pending.pop(request.request_id, None)


def create_adapter(context):
    return CudaSAM21Adapter(context)
