# SPDX-License-Identifier: Apache-2.0
"""Model Package adapter for Haru using the shared Runtime duplex contract."""
import numpy as np

from .audio_duplex import AudioDuplexFrame
from .haru_duplex import HaruDuplexBackend
from .protocol import ModelWorkerError


class HaruConversation:
    def __init__(self, backend, options):
        self.backend, self.options = backend, options

    @staticmethod
    def frame(value):
        return AudioDuplexFrame(value.session_id, value.index, value.sample_start, value.playback_epoch,
                                value.audio.astype('<f4').tobytes(), value.text, value.done, value.suppressed)

    async def start(self):
        options = self.options
        return self.frame(await self.backend.start(system_prompt=options['system_prompt'],
            reference_audio=np.frombuffer(options['reference_pcm'], dtype='<f4'), seed=options['seed'],
            max_frames=options['max_frames']))

    async def step(self, pcm):
        return self.frame(await self.backend.step(np.frombuffer(pcm, dtype='<f4')))

    def interrupt_playback(self):
        return self.backend.interrupt_playback()

    def resume_playback(self):
        return self.backend.resume_playback()

    async def close(self):
        await self.backend.close()


class HaruRealtimeAdapter:
    def __init__(self, context):
        self.context = context
        self._active = None

    async def start(self):
        pass

    async def stop(self):
        if self._active is not None:
            await self._active.close()
            self._active = None

    async def invoke(self, request):
        raise ModelWorkerError('Haru uses the authenticated audio duplex session endpoint', code='unsupported_operation')

    async def open_duplex(self, model_id, options):
        model = next((m for m in self.context.models if model_id in (m['id'], m.get('upstream_id'))), None)
        checkpoint = self.context.checkpoint_for(model_id)
        if not model or model.get('model_type') != 'audio_realtime' or not checkpoint or checkpoint.path is None:
            raise ModelWorkerError('Selected realtime model checkpoint is unavailable', code='model_unavailable', status_code=503)
        # Precision is signed owner metadata, not an arbitrary client option.
        precision = model.get('metadata', {}).get('haru_precision', '8')
        if precision not in ('8', 'bf16'):
            raise ModelWorkerError('Unsupported signed Haru precision')
        if self._active is not None:
            await self._active.close()
        backend = HaruDuplexBackend(checkpoint.path, quantize=8 if precision == '8' else None)
        self._active = HaruConversation(backend, options)
        return self._active


def create_adapter(context):
    return HaruRealtimeAdapter(context)
