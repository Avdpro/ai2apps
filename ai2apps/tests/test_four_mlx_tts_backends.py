"""Contracts for the experimental offline MLX speech backends."""
import io
import json
import wave
from types import SimpleNamespace

import numpy as np
import pytest

from omlx.engine.tts import TTSEngine
from omlx.engine.tts_backends.loader import family_for


@pytest.mark.parametrize('model_type,family', [
    ('zonos3', 'zonos3'), ('fish_drama3', 'fish_drama3'),
    ('breeze_tts', 'breeze_tts'), ('moss_tts_nano', 'moss_tts_nano'),
    ('unknown', None),
])
def test_local_dispatch(tmp_path, model_type, family):
    (tmp_path / 'config.json').write_text(json.dumps({'model_type': model_type}))
    assert family_for(tmp_path) == family


def fake_engine(module, results, capture):
    class Model:
        sample_rate = 24000
        def generate(self, text, instruct=None, **kwargs):
            capture.update(text=text, instruct=instruct, **kwargs)
            return results
    Model.__module__ = module
    engine = TTSEngine('fixture')
    engine._model = Model()
    return engine


@pytest.mark.asyncio
async def test_stereo_mixed_without_doubling_duration():
    capture = {}
    engine = fake_engine('fixture', [SimpleNamespace(
        audio=np.ones((480, 2), dtype=np.float32) * .25, sample_rate=48000)], capture)
    audio = await engine.synthesize('hello')
    with wave.open(io.BytesIO(audio)) as wav:
        assert wav.getnframes() == 480
        assert wav.getframerate() == 48000
        assert wav.getnchannels() == 1


@pytest.mark.asyncio
async def test_rate_change_rejected():
    engine = fake_engine('fixture', [SimpleNamespace(audio=np.zeros(10), sample_rate=r)
                                    for r in [24000, 48000]], {})
    with pytest.raises(ValueError, match='sample rate'):
        await engine.synthesize('hello')


@pytest.mark.asyncio
async def test_drama_instruction_is_inline():
    capture = {}
    engine = fake_engine('omlx.engine.tts_backends.fish_drama3',
                         [SimpleNamespace(audio=np.zeros(10))], capture)
    await engine.synthesize('hello', instructions='happy')
    assert capture['text'] == '[happy] hello'
    assert capture['instruct'] is None


@pytest.mark.asyncio
async def test_moss_unconditional_uses_supported_mode():
    capture = {}
    engine = fake_engine('mlx_audio.tts.models.moss_tts_nano',
                         [SimpleNamespace(audio=np.zeros(10))], capture)
    await engine.synthesize('hello')
    assert capture['mode'] == 'continuation'


def test_missing_moss_codec_fails_before_loading_weights(tmp_path):
    from omlx.engine.tts_backends.loader import load_local
    (tmp_path / 'config.json').write_text(json.dumps({'model_type':'moss_tts_nano'}))
    (tmp_path / 'tokenizer.model').touch()
    with pytest.raises(FileNotFoundError, match='Host-selected'):
        load_local(tmp_path)


def test_drama_backbone_and_tower_cache_copy():
    import mlx.core as mx
    from mlx_lm.models.cache import KVCache
    from omlx.engine.tts_backends.fish_drama3.drama3 import _copy_cache
    cache = KVCache()
    cache.update_and_fetch(mx.ones((1, 1, 2, 4)), mx.ones((1, 1, 2, 4)))
    snapshot = _copy_cache(cache)
    cache.update_and_fetch(mx.zeros((1, 1, 1, 4)), mx.zeros((1, 1, 1, 4)))
    assert snapshot.offset == 2
    assert snapshot.keys.shape[-2] == 2
    assert cache.offset == 3


def test_reference_resampling_preserves_duration(tmp_path):
    from omlx.engine.tts_backends.reference_audio import load_audio
    path = tmp_path / 'reference.wav'
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(np.zeros((2400, 2), dtype=np.int16).tobytes())
    result = np.asarray(load_audio(str(path), 44100))
    assert result.shape == (4410,)
    assert np.isfinite(result).all()


def test_zonos_emotion_vectors_and_neutral():
    from omlx.engine.tts_backends.zonos3.steering import emotion_delta
    config = SimpleNamespace(dim=1024, n_layers=11)
    assert emotion_delta('neutral', 2, config) is None
    assert emotion_delta('happy', 0, config) is None
    happy = emotion_delta('happy', 2, config)[19]
    assert happy.shape == (1024,)
    assert np.isfinite(happy).all() and np.any(happy)
    np.testing.assert_array_equal(happy, emotion_delta('happy', 1, config)[19] * 2)
    np.testing.assert_array_equal(emotion_delta('fearful', 2, config)[19],
                                  emotion_delta('scared', 2, config)[19])
    assert not np.array_equal(happy, emotion_delta('angry', 2, config)[19])


@pytest.mark.parametrize('emotion,strength', [('unknown', 2), ('happy', float('nan')),
                                             ('happy', -1), ('happy', 9), ('happy', True)])
def test_zonos_invalid_emotion_rejected(emotion, strength):
    from omlx.engine.tts_backends.zonos3.steering import emotion_delta
    with pytest.raises(ValueError):
        emotion_delta(emotion, strength, SimpleNamespace(dim=1024, n_layers=11))


def test_zonos_steering_resource_hashes():
    from pathlib import Path
    import hashlib
    from omlx.engine.tts_backends.zonos3 import steering
    root=Path(steering.__file__).with_suffix('')
    manifest=json.loads((root/'manifest.json').read_text())
    for name,digest in manifest['sha256'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest() == digest


def test_local_loader_does_not_probe_checkpoint_ancestors(tmp_path, monkeypatch):
    from omlx.engine.tts_backends.loader import load_local
    (tmp_path / 'config.json').write_text(json.dumps({'model_type': 'moss_tts_nano'}))
    (tmp_path / 'tokenizer.model').touch()
    def denied(*args, **kwargs):
        raise PermissionError('ancestor metadata is outside the sandbox grant')
    monkeypatch.setattr(type(tmp_path), 'resolve', denied)
    with pytest.raises(FileNotFoundError, match='Host-selected'):
        load_local(tmp_path)
