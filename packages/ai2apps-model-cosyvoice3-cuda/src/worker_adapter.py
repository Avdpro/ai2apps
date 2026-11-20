"""Original-checkpoint variant on the existing CosyVoice3 Worker contract."""
from dataclasses import replace
import re
import threading

from ai2apps.model_worker.cuda_audio import CudaQwenTTSAdapter, CudaQwenTTSEngine
from cuda_cosyvoice_adapter import CudaCosySpeechEngine, CudaCosyVoiceAdapter, invalid

MODEL_ID = 'ai2apps.model.cosyvoice3-cuda/original-fp32'
CHECKPOINT = ('FunAudioLLM/Fun-CosyVoice3-0.5B-2512',
              '29e01c4e8d000f4bcd70751be16fa94bf3d85a18')


class CudaCosyOriginalSpeechEngine(CudaCosySpeechEngine):
    native_speed = True
    def __init__(self, checkpoint):
        CudaQwenTTSEngine.__init__(self, checkpoint)

    async def start(self):
        def load():
            from cuda_cosyvoice_original_engine import CudaCosyVoiceOriginalEngine
            self._check()
            self.model = CudaCosyVoiceOriginalEngine(
                self.checkpoint.path, fp16=False, check=self._check)
        try:
            await self._run(load)
        except BaseException:
            await self.stop()
            raise


class CudaCosyVoiceOriginalAdapter(CudaCosyVoiceAdapter):
    async def invoke(self, request):
        if self._stopping:
            invalid('Worker is stopping', 'worker_stopping', 503)
        if request.request_id in self._cancellations:
            invalid('Request already active', 'request_conflict', 409)
        if request.payload.get('model') not in (MODEL_ID, CHECKPOINT[0]):
            invalid('Unknown original CosyVoice3 model', 'model_not_found', 404)
        body = dict(request.payload)
        seed = body.get('seed', 42)
        if isinstance(seed, str) and re.fullmatch(r'[0-9]{1,10}', seed):
            seed = int(seed)
        if type(seed) is not int or not 0 <= seed < 2**32:
            invalid('seed must be uint32')
        body['seed'] = seed
        # Keep the shared lock/cancellation/transport path; skip the quantized
        # adapter's model whitelist, which intentionally excludes this variant.
        return await CudaQwenTTSAdapter.invoke(self, replace(request, payload=body))

    def synthesis_options(self, model_id, body, *, speed, emotion, emotion_strength, instructions):
        # Official non-streaming speed interpolates mel frames before HiFT.
        # Keep the numerical factor; do not translate it into a style prompt.
        values = CudaQwenTTSAdapter.synthesis_options(
            self, model_id, body, speed=speed, emotion=emotion,
            emotion_strength=emotion_strength, instructions=instructions)
        values['seed'] = body.get('seed', 42)
        return values

    async def create_engine(self, checkpoint, runtime_options=None):
        if (checkpoint.model_id != MODEL_ID or checkpoint.path is None
                or (checkpoint.repo_id, checkpoint.revision) != CHECKPOINT):
            invalid('Host-selected original checkpoint required', 'checkpoint_not_ready', 409)
        if runtime_options:
            invalid('Unsupported original CosyVoice3 runtime settings', 'unsupported_feature')
        engine = CudaCosyOriginalSpeechEngine(checkpoint)
        engine.cancelled = self._current_event or threading.Event()
        return engine


def create_adapter(context):
    return CudaCosyVoiceOriginalAdapter(context)
