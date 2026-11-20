"""CUDA LivePortrait using the shared Mac media and motion workflow.

The operation lock remains held until native work finishes, including when the
transport cancels its asyncio task. Checkpoints are selected only by the Host.
"""
import asyncio
import gc
import json
import math
import threading
from dataclasses import replace
from pathlib import Path

from ai2apps.model_worker import ModelWorkerError
from mlx_liveportrait.worker_adapter import MLXLivePortraitAdapter, UnsupportedControlError

MODEL = 'ai2apps.model.liveportrait-cuda/liveportrait'
UPSTREAM = 'KlingTeam/LivePortrait'
WEIGHTS = ('appearance_feature_extractor', 'motion_extractor', 'warping_module',
           'spade_generator', 'stitching', 'stitching_eye', 'stitching_lip')


def cancelled():
    return ModelWorkerError('LivePortrait generation was cancelled',
                            code='generation_cancelled', status_code=499)


def task_payload(request, payload):
    """Translate the durable video task envelope without weakening controls."""
    if request.operation != 'video_generation' or 'reference_parts' not in payload:
        return payload
    values = dict(payload)
    refs = values.pop('reference_parts')
    if isinstance(refs, str):
        refs = json.loads(refs)
    if not isinstance(refs, list) or len(refs) != 2:
        raise ValueError('One reference image and one reference video are required')
    inputs = dict(values.pop('inputs', {}))
    if inputs:
        raise ValueError('Conflicting inputs and reference_parts')
    for ref in refs:
        if not isinstance(ref, dict) or ref.get('kind') not in ('image', 'video'):
            raise ValueError('Invalid portrait task reference')
        role = 'reference_' + ref['kind']
        name = ref.get('part_name')
        if (role in inputs or not isinstance(name, str)
                or not name.startswith('reference_') or name == 'reference_parts'):
            raise ValueError('Ambiguous portrait task reference')
        request.part(name)
        inputs[role] = {'part_name': name}
        values.pop(name, None)  # Worker multipart filename envelope field.
    if set(inputs) != {'reference_image', 'reference_video'}:
        raise ValueError('One image and one video are required')
    for key in ('resolution', 'ratio'):
        if values.pop(key, 'source') != 'source':
            raise ValueError('LivePortrait preserves source geometry')
    preset = values.pop('preset', 'quality')
    if preset not in ('quality', 'fast'):
        raise ValueError('LivePortrait supports quality or fast preset')
    for key, expected in (('fast', preset == 'fast'), ('fast_max', False)):
        value = values.pop(key, expected)
        if isinstance(value, str) and value.lower() in ('true', 'false'):
            value = value.lower() == 'true'
        if type(value) is not bool or value != expected:
            raise ValueError('Conflicting preset flags')
    fps = values.pop('fps', None)
    rate = values.pop('framespersecond', fps)
    if fps is not None and rate is not None and float(fps) != float(rate):
        raise ValueError('Conflicting frame rates')
    if rate is not None:
        if isinstance(rate, bool) or not math.isfinite(float(rate)) or float(rate) <= 0:
            raise ValueError('Invalid driving frame rate')
        import av
        part = request.part(inputs['reference_video']['part_name'])
        with av.open(str(part.path)) as video:
            actual = video.streams.video[0].average_rate
        if actual is None or abs(float(actual) - float(rate)) > 0.001:
            raise ValueError('LivePortrait preserves driving frame rate')
    precision = 'bf16' if preset == 'fast' else 'fp32'
    params = values.pop('parameters', None)
    if params is not None:
        if not isinstance(params, dict) or set(params) & set(values):
            raise ValueError('Conflicting task controls')
        values.update(params)
    if values.get('precision', precision) != precision:
        raise ValueError('Conflicting precision and preset')
    values['precision'] = precision
    values['inputs'] = inputs
    return values


class CudaLivePortraitAdapter(MLXLivePortraitAdapter):
    def __init__(self, context):
        super().__init__(context)
        self._operation_lock = asyncio.Lock()
        self._pending = {}
        self._closing = False
        self._lifecycle_lock = asyncio.Lock()
        self._portrait_landmarks = None
        self._source_crop = "arcface5"

    @staticmethod
    def _parameters(payload, operation):
        raw = payload.get('parameters', payload)
        if not isinstance(raw, dict):
            raise ValueError('parameters must be an object')
        if operation != 'video_generation':
            return MLXLivePortraitAdapter._parameters(payload, operation)
        mode = raw.get('driving_crop_mode', 'pre_cropped')
        if mode not in ('pre_cropped', 'auto'):
            raise UnsupportedControlError('driving_crop_mode must be pre_cropped or auto')
        controls = dict(raw)
        controls.pop('driving_crop_mode', None)
        clean = dict(payload, parameters=controls) if 'parameters' in payload else controls
        result = MLXLivePortraitAdapter._parameters(clean, operation)
        result['driving_crop_mode'] = mode
        return result

    def _driving_crop(self, detector, tracker, frame, parameters):
        # Official default expects a prepared driver; repeat alignment changes
        # the driving motion. Raw videos retain the explicit automatic path.
        if parameters['driving_crop_mode'] == 'pre_cropped':
            return frame
        return super()._driving_crop(detector, tracker, frame, parameters)

    @staticmethod
    def _metadata(parameters, *, audio_applied):
        result = MLXLivePortraitAdapter._metadata(parameters, audio_applied=audio_applied)
        if 'driving_crop_mode' in parameters:
            mode = parameters['driving_crop_mode']
            result['applied_controls']['driving_crop_mode'] = {'requested': mode, 'applied': mode}
        return result

    def _ensure_checkpoint(self, model_id):
        if self._root is not None:
            return self._root
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError('Host-selected CUDA checkpoint is required',
                                   code='model_unavailable', status_code=503)
        root = Path(checkpoint.path)
        manifest = json.loads((root / 'ai2apps-checkpoint.json').read_text())
        schema = manifest.get('schema')
        if schema not in {'ai2apps.cuda-liveportrait-checkpoint/v1',
                          'ai2apps.cuda-liveportrait-checkpoint/v2'}:
            raise ValueError('Unsupported CUDA LivePortrait checkpoint layout')
        required = ['models.yaml', 'face_detection_yunet_2023mar.onnx',
                    *(name + '.safetensors' for name in WEIGHTS)]
        if schema == 'ai2apps.cuda-liveportrait-checkpoint/v2':
            if manifest.get('source_crop') != 'yunet203':
                raise ValueError('Unsupported LivePortrait source crop contract')
            required.append('landmark.onnx')
        if any(not (root / name).is_file() for name in required):
            raise ValueError('Incomplete CUDA LivePortrait checkpoint')
        self._source_crop = "yunet203" if schema.endswith("/v2") else "arcface5"
        self._root = root
        return root

    def _load(self, model_id, precision):
        from cuda_liveportrait_pipeline import CudaLivePortraitPipeline
        from liveportrait_yunet import CpuYuNet
        root = self._ensure_checkpoint(model_id)
        if self._detector is None:
            self._detector = CpuYuNet(root / 'face_detection_yunet_2023mar.onnx')
        if precision not in self._pipelines:
            # Keep only one precision resident when switching quality modes.
            self._pipelines.clear()
            gc.collect()
            self._pipelines[precision] = CudaLivePortraitPipeline(root, dtype=precision)
        return self._detector, self._pipelines[precision]

    def _crop(self, detector, image, role):
        if role != 'source image' or self._source_crop != 'yunet203':
            return super()._crop(detector, image, role)
        from liveportrait_landmark203 import PortraitLandmark203
        faces = detector.detect(image)
        if not faces:
            raise ValueError('source image does not contain a detectable face')
        if self._portrait_landmarks is None:
            self._portrait_landmarks = PortraitLandmark203(self._root / 'landmark.onnx')
        face = max(faces, key=lambda item: float(
            (item.bbox[2]-item.bbox[0]) * (item.bbox[3]-item.bbox[1])))
        return self._portrait_landmarks.crop(image, face.bbox)

    def _paste_face(self, target, generated, matrix, **kwargs):
        if self._source_crop != 'yunet203':
            return super()._paste_face(target, generated, matrix, **kwargs)
        from liveportrait_landmark203 import paste_portrait
        return paste_portrait(target, generated, matrix)

    def cancel(self, request_id):
        event = self._pending.get(request_id)
        if event is not None:
            event.set()
        super().cancel(request_id)

    async def start(self):
        async with self._lifecycle_lock:
            self._closing = False

    async def stop(self):
        async with self._lifecycle_lock:
            self._closing = True
            for request_id in tuple(self._pending):
                self.cancel(request_id)
            async with self._operation_lock:
                self._pipelines.clear()
                self._detector = self._root = None
                self._portrait_landmarks = None
                self._source_crop = "arcface5"
                gc.collect()
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

    async def invoke(self, request):
        if self._closing:
            raise ModelWorkerError('Worker is stopping', code='worker_stopping', status_code=503)
        if request.request_id in self._pending:
            raise ModelWorkerError('Request already active', code='request_conflict', status_code=409)
        payload = dict(request.payload)
        if payload.get('model') == UPSTREAM:
            payload['model'] = MODEL
        if payload.get('model') != MODEL:
            raise ModelWorkerError('Unknown CUDA LivePortrait model', code='model_not_found', status_code=404)
        for key in ('inputs', 'parameters'):
            if isinstance(payload.get(key), str):
                try:
                    payload[key] = json.loads(payload[key])
                except ValueError as error:
                    raise ModelWorkerError(f'{key} must be a JSON object', code='invalid_request') from error
        try:
            payload = task_payload(request, payload)
        except (ValueError, TypeError, KeyError, IndexError) as error:
            raise ModelWorkerError(str(error), code='invalid_request') from error
        parameters = payload.get('parameters', payload)
        if not isinstance(parameters, dict):
            raise ModelWorkerError('parameters must be an object', code='invalid_request')
        if parameters.get('precision', 'fp32') not in {'fp32', 'bf16'}:
            raise ModelWorkerError('precision must be fp32 or bf16', code='unsupported_control')
        request = replace(request, payload=payload)
        event = threading.Event()
        self._pending[request.request_id] = event
        try:
            async with self._operation_lock:
                if self._closing:
                    raise ModelWorkerError('Worker is stopping', code='worker_stopping', status_code=503)
                if event.is_set():
                    raise cancelled()
                task = asyncio.create_task(super().invoke(request))
                try:
                    result = await asyncio.shield(task)
                except asyncio.CancelledError:
                    self.cancel(request.request_id)
                    # Repeated transport cancellation must not abandon a native
                    # thread while its input/output roots are still in use.
                    while not task.done():
                        try:
                            await asyncio.shield(task)
                        except asyncio.CancelledError:
                            self.cancel(request.request_id)
                        except Exception:
                            break
                    if task.done() and not task.cancelled():
                        task.exception()
                    raise
                except ModelWorkerError as error:
                    if event.is_set() or error.code == 'generation_cancelled':
                        raise cancelled() from error
                    raise
                if event.is_set():
                    raise cancelled()
                return result
        finally:
            self._pending.pop(request.request_id, None)


def create_adapter(context):
    return CudaLivePortraitAdapter(context)
