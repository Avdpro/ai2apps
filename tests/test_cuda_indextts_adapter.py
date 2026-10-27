import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'spark'))
from cuda_indextts_adapter import CudaIndexTTSAdapter, CudaIndexSpeechEngine, MODEL_ID, CHECKPOINT
from ai2apps.model_worker import ModelWorkerError


def setup():
    obj = CudaIndexTTSAdapter(SimpleNamespace())
    checkpoint = SimpleNamespace(model_id=MODEL_ID, repo_id=CHECKPOINT[0],
                                 revision=CHECKPOINT[1], path=Path('/tmp/model'))
    return obj, checkpoint


@pytest.mark.asyncio
async def test_fixed_host_checkpoint_binding():
    obj, checkpoint = setup()
    assert isinstance(await obj.create_engine(checkpoint), CudaIndexSpeechEngine)
    checkpoint.revision = '0' * 40
    with pytest.raises(ModelWorkerError) as error:
        await obj.create_engine(checkpoint)
    assert error.value.code == 'checkpoint_not_ready'


@pytest.mark.asyncio
async def test_reference_required_before_loading():
    engine = CudaIndexSpeechEngine(None)
    with pytest.raises(ModelWorkerError) as error:
        await engine.synthesize('hello')
    assert error.value.code == 'invalid_reference_audio' and engine.model is None


@pytest.mark.asyncio
async def test_duplicate_request_does_not_replace_owner():
    obj, _ = setup()
    owner = object()
    obj._cancellations['same'] = owner
    with pytest.raises(ModelWorkerError) as error:
        await obj.invoke(SimpleNamespace(request_id='same', payload={}))
    assert error.value.code == 'request_conflict' and obj._cancellations['same'] is owner


@pytest.mark.asyncio
async def test_stopping_rejects_new_work():
    obj, _ = setup()
    await obj.stop()
    with pytest.raises(ModelWorkerError) as error:
        await obj.invoke(SimpleNamespace(request_id='new', payload={}))
    assert error.value.code == 'worker_stopping'


@pytest.mark.asyncio
@pytest.mark.parametrize('seed', [True, -1, 2**32, '1e3'])
async def test_invalid_seed_rejected_before_loading(seed):
    obj, _ = setup()
    with pytest.raises(ModelWorkerError) as error:
        await obj.invoke(SimpleNamespace(request_id='bad', payload={'model': MODEL_ID, 'seed': seed},
                                         parts={'reference_audio': object()}))
    assert error.value.status_code == 400


def test_controls_match_actual_mac_package():
    path = ROOT / 'packages/omlx-model-indextts25/src/worker_adapter.py'
    spec = importlib.util.spec_from_file_location('mac_indextts_contract', path)
    mac = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mac)
    obj, _ = setup()
    other = mac.IndexTTS25Adapter(SimpleNamespace())
    for emotion in ('neutral', 'happy', 'angry', 'sad', 'surprised', 'calm'):
        for speed in (.5, 1., 2.):
            body = {'input': '你好', 'language': 'auto'}
            args = dict(speed=speed, emotion=emotion, emotion_strength=.7, instructions=None)
            expected = other.synthesis_options(MODEL_ID, body, **args)
            actual = obj.synthesis_options(MODEL_ID, body, **args)
            assert expected['emotion_vector'] == actual['emotion_vector']
            assert expected['emotion_strength'] == actual['emotion_strength']
            assert expected['language'] == actual['language']
            assert expected['duration_factor'] == 1 / actual['speed']
