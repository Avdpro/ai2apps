import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'spark'))
from cuda_cosyvoice_original_adapter import CudaCosyVoiceOriginalAdapter, CHECKPOINT, MODEL_ID
from ai2apps.model_worker import ModelWorkerError, ModelWorkerRequest
from ai2apps.model_worker.cuda_audio import CudaQwenTTSAdapter


@pytest.mark.asyncio
async def test_host_upstream_alias_reaches_shared_request_path(monkeypatch):
    seen = []
    async def capture(self, request):
        seen.append(request.payload)
        return 'accepted'
    monkeypatch.setattr(CudaQwenTTSAdapter, 'invoke', capture)
    adapter = CudaCosyVoiceOriginalAdapter(SimpleNamespace())
    for identity in (MODEL_ID, CHECKPOINT[0]):
        result = await adapter.invoke(ModelWorkerRequest(
            'audio_speech', {'model': identity, 'seed': '42'}, 'host'))
        assert result == 'accepted'
    assert all(row['seed'] == 42 for row in seen)
    with pytest.raises(ModelWorkerError) as error:
        await adapter.invoke(ModelWorkerRequest('audio_speech', {'model': 'other'}, 'bad'))
    assert error.value.code == 'model_not_found'
    assert len(seen) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value', [('repo_id', 'other'), ('revision', '0'*40),
                                       ('model_id', CHECKPOINT[0]), ('path', None)])
async def test_upstream_alias_does_not_relax_host_checkpoint_binding(field, value):
    adapter = CudaCosyVoiceOriginalAdapter(SimpleNamespace())
    values = dict(model_id=MODEL_ID, repo_id=CHECKPOINT[0], revision=CHECKPOINT[1],
                  path=Path('/tmp/fixed-checkpoint'))
    values[field] = value
    with pytest.raises(ModelWorkerError) as error:
        await adapter.create_engine(SimpleNamespace(**values))
    assert error.value.code == 'checkpoint_not_ready'

@pytest.mark.parametrize('speed', [0.5, 0.8, 1.0, 1.25, 2.0])
def test_original_speed_remains_numeric_without_style_prompt(speed):
    adapter = CudaCosyVoiceOriginalAdapter(SimpleNamespace())
    result = adapter.synthesis_options(MODEL_ID, {'seed': 17}, speed=speed,
        emotion=None, emotion_strength=1.0, instructions='Speak softly.')
    assert result['speed'] == speed
    assert result['instructions'] == 'Speak softly.'
    assert result['seed'] == 17
