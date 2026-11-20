"""Regression cases found by the pinned Qwen3-ASR Spark acceptance."""
import importlib.util
from pathlib import Path
import wave
import sys
import types

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cuda_asr_adapter', ROOT / 'packages/ai2apps-model-qwen3-asr-0.6b-cuda/src/worker_adapter.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Adapter = module.CudaQwen3ASRAdapter


@pytest.fixture(autouse=True)
def language_mapping(monkeypatch):
    # Mac's MLX environment has an older Transformers. The complete mapping
    # is exercised by check_asr_worker.py in the actual CUDA Runtime.
    processor_module = types.ModuleType('processing_qwen3_asr')
    processor_module.LANGUAGE_CODE_TO_NAME = {'en': 'English', 'zh': 'Chinese'}
    monkeypatch.setitem(sys.modules, 'transformers.models.qwen3_asr.processing_qwen3_asr', processor_module)


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / 'sample.wav'
    with wave.open(str(path), 'wb') as wav:
        wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        wav.writeframes(b'\0\0' * 16000)
    return path


def test_empty_audio_is_rejected(tmp_path):
    path = tmp_path / 'empty.wav'
    with wave.open(str(path), 'wb') as wav:
        wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
    with pytest.raises(module.ModelWorkerError) as error:
        Adapter._read_wav(str(path))
    assert error.value.code == 'invalid_audio'
    assert error.value.status_code == 400


class Inputs(dict):
    def to(self, *args):
        return self


class Processor:
    """Pinned template supports generation prompts, not assistant continuation."""
    def apply_chat_template(self, messages, **kwargs):
        assert kwargs['add_generation_prompt'] is True
        return Inputs(input_ids=torch.tensor([[10, 11]]), attention_mask=torch.ones(1, 2, dtype=torch.long))

    def apply_transcription_request(self, **kwargs):
        raise ValueError('Pinned template drops assistant prefill')

    def tokenizer(self, text, **kwargs):
        assert text == 'language English<asr_text>'
        return {'input_ids': torch.tensor([[12, 13]])}

    def decode(self, tokens, **kwargs):
        assert tokens.tolist() == [[14]]
        if kwargs.get('return_format') == 'parsed':
            return [{'language': 'English', 'transcription': 'A real transcription.'}]
        assert kwargs['skip_special_tokens'] is True
        return ['A real transcription.']


class Model:
    device = 'cpu'
    dtype = torch.float32

    def generate(self, **kwargs):
        self.inputs = kwargs
        assert kwargs['attention_mask'].shape == kwargs['input_ids'].shape
        return torch.cat((kwargs['input_ids'], torch.tensor([[14]])), dim=1)


@pytest.mark.parametrize('language,expected_ids', [('en', [10, 11, 12, 13]), ('auto', [10, 11])])
def test_forced_language_prefill_and_auto_mode(audio, language, expected_ids):
    model = Model()
    result = Adapter._transcribe(model, Processor(), str(audio), {'language': language})
    assert model.inputs['input_ids'].tolist() == [expected_ids]
    assert result == {'text': 'A real transcription.', 'language': 'English'}


def test_unknown_language_is_a_request_error(audio):
    with pytest.raises(module.ModelWorkerError) as error:
        Adapter._transcribe(Model(), Processor(), str(audio), {'language': 'not-a-language'})
    assert error.value.status_code == 400
