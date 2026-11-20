from pathlib import Path
import sys

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_ace_checkpoint import prepare_checkpoint, COMPONENTS
from patch_ace_step_schedule import patch_model


def fixture(tmp_path):
    repo=Path(__file__).resolve().parents[1]
    original=repo/'experiments/music_mlx/vendor/ACE-Step-1.5/acestep/models/turbo'
    source=tmp_path/'source'
    code=source/'acestep/models/turbo';code.mkdir(parents=True)
    (code/'modeling_acestep_v15_turbo.py').write_bytes(patch_model((original/'modeling_acestep_v15_turbo.py').read_bytes()))
    (code/'configuration_acestep_v15.py').write_bytes((original/'configuration_acestep_v15.py').read_bytes())
    weights=tmp_path/'weights'
    for name in COMPONENTS:
        directory=weights/name;directory.mkdir(parents=True)
        (directory/'weights.safetensors').write_bytes(b'fixed weights')
        (directory/'unexpected.py').write_text('raise RuntimeError("untrusted")')
    return source,weights


def test_downloaded_python_is_never_used_and_original_weights_survive_cleanup(tmp_path):
    source,weights=fixture(tmp_path)
    original=weights/'acestep-v15-turbo/modeling_acestep_v15_turbo.py'
    original.write_text('unmodified downloaded model code')
    view=prepare_checkpoint(weights,source,lambda:None,cache_root=tmp_path)
    root=Path(view.name)
    assert not list(root.rglob('unexpected.py'))
    target=root/'acestep-v15-turbo/modeling_acestep_v15_turbo.py'
    assert not target.is_symlink() and target.read_bytes()==(source/'acestep/models/turbo'/target.name).read_bytes()
    linked=root/'vae/weights.safetensors'
    assert linked.is_symlink() and linked.read_bytes()==b'fixed weights'
    view.cleanup()
    assert not root.exists() and original.read_text()=='unmodified downloaded model code'
    assert (weights/'vae/weights.safetensors').read_bytes()==b'fixed weights'


def test_changed_runtime_source_rejected_before_view_creation(tmp_path):
    source,weights=fixture(tmp_path)
    (source/'acestep/models/turbo/configuration_acestep_v15.py').write_text('changed')
    with pytest.raises(ValueError,match='verification failed'):
        prepare_checkpoint(weights,source,lambda:None,cache_root=tmp_path)
    assert not list(tmp_path.glob('ai2apps-ace-checkpoint-*'))


def test_cancellation_cleans_partial_view(tmp_path):
    source,weights=fixture(tmp_path)
    count=0
    def check():
        nonlocal count
        count+=1
        if count==3:raise InterruptedError('cancel')
    with pytest.raises(InterruptedError):prepare_checkpoint(weights,source,check,cache_root=tmp_path)
    assert not list(tmp_path.glob('ai2apps-ace-checkpoint-*'))
