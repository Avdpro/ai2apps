"""Non-Transformer media weights need the intact Registry acquisition receipt."""
import json
import pytest
from ai2apps.checkpoints import checkpoint_is_complete, model_checkpoint_is_complete


def snapshot(root, filename):
    path = root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'fixed weight payload')
    path.chmod(0o444)
    st = path.stat()
    meta = root / '.ai2apps'
    meta.mkdir()
    digest = 'sha256:' + 'b' * 64
    (meta / 'distribution.json').write_text(json.dumps(dict(
        format='ai2apps-checkpoint-distribution', version=1,
        distributionId='dist_media', manifestDigest=digest)))
    (meta / 'verification.json').write_text(json.dumps(dict(
        format='ai2apps-checkpoint-verification', version=1,
        manifestDigest=digest, files={filename:dict(device=st.st_dev,
        inode=st.st_ino, size=st.st_size, mtimeNs=st.st_mtime_ns)})))
    return path


CASES = [('video_generation', 'musetalkV15/unet.pth'),
         ('component', '79999_iter.pth'),
         ('component', 'pytorch_model.pt'),
         ('component', 'face_detection_yunet_2023mar.onnx')]


@pytest.mark.parametrize('kind,filename', CASES)
def test_verified_media_layouts(tmp_path, kind, filename):
    snapshot(tmp_path, filename)
    model = dict(model_type=kind, metadata={'internal':kind == 'component'},
                 weights={'distribution_id':'dist_media'})
    assert model_checkpoint_is_complete(tmp_path, model)
    assert not checkpoint_is_complete(tmp_path)
    assert not model_checkpoint_is_complete(tmp_path, dict(model, weights={}))
    assert not model_checkpoint_is_complete(tmp_path, dict(model, weights={'distribution_id':'wrong'}))
    assert not model_checkpoint_is_complete(tmp_path, dict(model, model_type='llm'))
    if kind == 'component':
        assert not model_checkpoint_is_complete(tmp_path, dict(model, metadata={'internal':False}))


@pytest.mark.parametrize('kind,filename', CASES)
@pytest.mark.parametrize('damage', ['missing','modified','writable','symlink','receipt','extra'])
def test_media_receipt_failures(tmp_path, kind, filename, damage):
    target = snapshot(tmp_path, filename)
    if damage == 'missing': target.unlink()
    elif damage == 'modified':
        target.chmod(0o644); target.write_bytes(b'changed'); target.chmod(0o444)
    elif damage == 'writable': target.chmod(0o644)
    elif damage == 'symlink':
        saved = tmp_path / 'elsewhere'; target.rename(saved); target.symlink_to(saved)
    elif damage == 'receipt': (tmp_path / '.ai2apps/verification.json').unlink()
    else: (tmp_path / 'unknown.pth').write_bytes(b'extra')
    assert not model_checkpoint_is_complete(tmp_path, dict(model_type=kind,
        metadata={'internal':kind == 'component'}, weights={'distribution_id':'dist_media'}))
