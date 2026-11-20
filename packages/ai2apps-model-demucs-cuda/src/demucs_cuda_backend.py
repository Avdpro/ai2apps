"""CUDA backend for the existing Mac separation pipeline, using safe weights."""
from fractions import Fraction
import json
from pathlib import Path

from mlx_demucs.backends import TorchDemucsBackend
from demucs_safe_weights import load_converted_safetensors


class CudaDemucsBackend(TorchDemucsBackend):
    def __init__(self, checkpoint, *, cancelled=None, progress=None):
        super().__init__(device='cuda', shifts=0, overlap=.25)
        self.name = 'cuda_demucs'
        self.checkpoint = Path(checkpoint)
        self.cancelled = cancelled
        self.progress = progress

    def check_cancel(self):
        if self.cancelled is not None and self.cancelled.is_set():
            raise InterruptedError('Demucs separation cancelled')

    def _load(self):
        self.check_cancel()
        if self._model is None:
            import torch
            from demucs.htdemucs import HTDemucs
            config = json.loads((self.checkpoint/'htdemucs_config.json').read_text())
            kwargs = dict(config['kwargs'])
            if (config['model_name'] != 'htdemucs' or config['num_models'] != 1
                or kwargs['sources'] != ['drums','bass','other','vocals']
                or kwargs['samplerate'] != 44100 or kwargs['audio_channels'] != 2):
                raise ValueError('Unsupported fixed HTDemucs configuration')
            kwargs['segment'] = Fraction(kwargs['segment'])
            model = HTDemucs(*config['args'], **kwargs)
            state = {k:torch.from_numpy(v.copy()) for k,v in load_converted_safetensors(
                self.checkpoint/'htdemucs.safetensors').items()}
            model.load_state_dict(state, strict=True)
            self._model = model.eval().to('cuda')
            self._torch = torch
        self.check_cancel()
        return self._model

    def extract_sources(self, audio):
        model = self._load()
        chunks = 0
        def before_chunk(module, inputs):
            nonlocal chunks
            self.check_cancel()
            chunks += 1
            if self.progress is not None:
                self.progress(chunks)
        hook = model.register_forward_pre_hook(before_chunk)
        try:
            result = super().extract_sources(audio)
            self.check_cancel()
            return result
        finally:
            hook.remove()
