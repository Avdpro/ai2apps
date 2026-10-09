"""Official audio PT layouts require an intact, immutable distribution receipt."""
import json

import pytest

from ai2apps.checkpoints import checkpoint_is_complete, model_checkpoint_is_complete


@pytest.fixture
def snapshot(tmp_path):
    payloads = {'model.pt': b'official weights fixture', 'config.yaml': b'model: sensevoice'}
    files = {}
    for name, data in payloads.items():
        path = tmp_path / name
        path.write_bytes(data)
        path.chmod(0o444)
        info = path.stat()
        files[name] = dict(device=info.st_dev, inode=info.st_ino, size=info.st_size, mtimeNs=info.st_mtime_ns)
    meta = tmp_path / '.ai2apps'
    meta.mkdir()
    digest = 'sha256:' + 'a' * 64
    (meta / 'distribution.json').write_text(json.dumps(dict(format='ai2apps-checkpoint-distribution', version=1, distributionId='dist_audio', manifestDigest=digest)))
    (meta / 'verification.json').write_text(json.dumps(dict(format='ai2apps-checkpoint-verification', version=1, manifestDigest=digest, files=files)))
    return tmp_path


@pytest.mark.parametrize('kind', ['audio_stt', 'audio_processing'])
def test_pt_audio_requires_exact_verified_distribution(snapshot, kind):
    model = dict(model_type=kind, weights=dict(distribution_id='dist_audio'))
    assert model_checkpoint_is_complete(snapshot, model)
    assert not checkpoint_is_complete(snapshot)
    assert not model_checkpoint_is_complete(snapshot, dict(model_type=kind))
    assert not model_checkpoint_is_complete(snapshot, dict(model_type=kind, weights=dict(distribution_id='wrong')))
    assert not model_checkpoint_is_complete(snapshot, dict(model_type='llm', weights=model['weights']))


@pytest.mark.parametrize('damage', ['missing', 'writable', 'modified', 'symlink', 'receipt', 'extra'])
def test_pt_audio_rejects_changed_snapshot(snapshot, damage):
    target = snapshot / 'model.pt'
    if damage == 'missing':
        target.unlink()
    elif damage == 'writable':
        target.chmod(0o644)
    elif damage == 'modified':
        target.chmod(0o644)
        target.write_bytes(b'tampered')
        target.chmod(0o444)
    elif damage == 'symlink':
        target.rename(snapshot / 'original.pt')
        target.symlink_to(snapshot / 'original.pt')
    elif damage == 'receipt':
        (snapshot / '.ai2apps/verification.json').unlink()
    else:
        (snapshot / 'unlisted.pt').write_bytes(b'unknown')
    assert not model_checkpoint_is_complete(snapshot, dict(model_type='audio_stt', weights=dict(distribution_id='dist_audio')))
