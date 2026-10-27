"""Host proxy uses upstream IDs; both public identities retain checkpoint gates."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'spark'))
from cuda_rvc_adapter import CHECKPOINT, MODEL_ID, CudaRVCAdapter
from ai2apps.model_worker import ModelWorkerError


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['audio_process', 'audio_voice_training'])
@pytest.mark.parametrize('identity', [MODEL_ID, CHECKPOINT[0]])
async def test_host_identity_keeps_fixed_checkpoint_revision_gate(operation, identity):
    selected = []
    def checkpoint_for(model):
        selected.append(model)
        return SimpleNamespace(path=Path('/unused'), repo_id=CHECKPOINT[0], revision='0' * 40)
    adapter = CudaRVCAdapter(SimpleNamespace(checkpoint_for=checkpoint_for))
    request = SimpleNamespace(request_id='request', operation=operation, payload={'model': identity})
    with pytest.raises(ModelWorkerError) as error:
        await adapter.invoke(request)
    assert selected == [MODEL_ID]
    assert error.value.code == 'model_not_supported'
    assert adapter.pipeline is None and not adapter.events


@pytest.mark.asyncio
@pytest.mark.parametrize('identity', ['other/model', 'Avdpro/MLX-RVC-Serena-E70-extra'])
async def test_unknown_model_cannot_select_checkpoint(identity):
    def checkpoint_for(model):
        pytest.fail('unknown model reached checkpoint selection')
    adapter = CudaRVCAdapter(SimpleNamespace(checkpoint_for=checkpoint_for))
    with pytest.raises(ModelWorkerError) as error:
        await adapter.invoke(SimpleNamespace(request_id='request', operation='audio_process', payload={'model': identity}))
    assert error.value.code == 'model_not_found'


def test_voice_bundle_extraction_preserves_only_declared_files(tmp_path):
    import zipfile
    from cuda_rvc_adapter import extract_voice_bundle
    source = tmp_path / 'voice.zip'
    names = ['model.json', 'index.json', 'model.safetensors', 'index.safetensors']
    with zipfile.ZipFile(source, 'w') as archive:
        for name in names:
            archive.writestr(name, b'fixture')
    root = extract_voice_bundle(source, tmp_path / 'voice', lambda: None)
    assert {p.name for p in root.iterdir()} == set(names)
    assert all(p.read_bytes() == b'fixture' for p in root.iterdir())


@pytest.mark.parametrize('bad_name', ['../model.json', '/model.json', 'nested/model.json', 'model.pkl'])
def test_voice_bundle_rejects_undeclared_or_escaping_members(tmp_path, bad_name):
    import zipfile
    from cuda_rvc_adapter import extract_voice_bundle
    source = tmp_path / 'voice.zip'
    with zipfile.ZipFile(source, 'w') as archive:
        for name in ['model.json', 'index.json', 'model.safetensors', 'index.safetensors', bad_name]:
            archive.writestr(name, b'fixture')
    with pytest.raises(ValueError, match='bundle files'):
        extract_voice_bundle(source, tmp_path / 'voice', lambda: None)
    assert not (tmp_path / 'voice').exists()


@pytest.mark.asyncio
async def test_uploaded_voice_is_request_scoped_and_default_recovers(tmp_path, monkeypatch):
    import zipfile
    import numpy as np
    import soundfile as sf
    import types
    from ai2apps.model_worker import ModelWorkerRequest, ModelWorkerPart
    calls = []
    class Pipeline:
        def __init__(self, *args):
            self.voice = 'default'
        def load_trained_voice(self, folder):
            assert (folder / 'model.json').is_file()
            self.voice = 'uploaded'
        def convert_long_16khz(self, audio, **kwargs):
            calls.append(self.voice)
            return np.zeros(64, dtype=np.float32)
    class Options:
        def __init__(self, **kwargs): pass
        def validate(self): pass
    fake = types.ModuleType('cuda_rvc_pipeline')
    fake.__file__ = str(tmp_path / 'pipeline.py')
    fake.CudaRVCPipeline = Pipeline
    fake.ConversionOptions = Options
    monkeypatch.setitem(sys.modules, 'cuda_rvc_pipeline', fake)
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=SimpleNamespace(empty_cache=lambda: None)))
    source = tmp_path / 'input.wav'
    sf.write(source, np.zeros(1024), 16000)
    voice = tmp_path / 'voice.zip'
    with zipfile.ZipFile(voice, 'w') as archive:
        for name in ['model.json', 'index.json', 'model.safetensors', 'index.safetensors']:
            archive.writestr(name, b'fixture')
    def part(name, path):
        return ModelWorkerPart(name=name, path=path, media_type='application/octet-stream',
                               filename=path.name, size=path.stat().st_size, sha256='fixture')
    checkpoint = SimpleNamespace(path=tmp_path, repo_id=CHECKPOINT[0], revision=CHECKPOINT[1])
    adapter = CudaRVCAdapter(SimpleNamespace(checkpoint_for=lambda _: checkpoint))
    for index, custom in enumerate([True, False]):
        parts = {'file': part('file', source)}
        if custom: parts['voice'] = part('voice', voice)
        output = tmp_path / str(index)
        await adapter.invoke(ModelWorkerRequest(operation='audio_process', payload={'model': MODEL_ID},
                             request_id=str(index), parts=parts, output_root=output))
        if custom:
            assert adapter.pipeline is None and adapter.path is None
            assert not list(output.glob('rvc-voice-*'))
    assert calls == ['uploaded', 'default']
    assert not adapter.events
