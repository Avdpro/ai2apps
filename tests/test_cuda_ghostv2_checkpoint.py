import hashlib
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('ghost_checkpoint', Path(__file__).parents[1]/'spark/cuda_ghostv2_checkpoint.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture_weights(monkeypatch, tmp_path):
    data = b'x' * (1024 * 1024 + 17)
    (tmp_path/'weight').write_bytes(data)
    monkeypatch.setattr(m, 'WEIGHTS', {'test': ('weight', len(data), hashlib.sha256(data).hexdigest())})
    return {'test': tmp_path}


def test_same_size_corruption_rejected(monkeypatch, tmp_path):
    roots=fixture_weights(monkeypatch,tmp_path)
    with (tmp_path/'weight').open('r+b') as f:f.write(b'z')
    with pytest.raises(ValueError,match='digest mismatch'):m.verify_checkpoints(roots)


def test_cancel_mid_file(monkeypatch, tmp_path):
    roots=fixture_weights(monkeypatch,tmp_path);calls=[]
    def check():
        calls.append(1)
        if len(calls)==3:raise InterruptedError('cancel')
    with pytest.raises(InterruptedError):m.verify_checkpoints(roots,check=check)
    assert len(calls)==3


def test_strict_bindings_and_size(monkeypatch,tmp_path):
    roots=fixture_weights(monkeypatch,tmp_path)
    assert m.verify_checkpoints(roots)=={'test':tmp_path/'weight'}
    with pytest.raises(ValueError,match='exactly'):m.verify_checkpoints({**roots,'extra':tmp_path})
    (tmp_path/'weight').write_bytes(b'x')
    with pytest.raises(ValueError,match='size mismatch'):m.verify_checkpoints(roots)


def test_close_attempts_all_and_drops_pipeline():
    calls=[]
    class Component:
        def __init__(self,name,fail=False):self.name,self.fail=name,fail
        def close(self):
            calls.append(self.name)
            if self.fail:raise RuntimeError('close failed')
    owner=m.GhostV2Components.__new__(m.GhostV2Components)
    owner.pipeline=object();owner._owned=[Component('first'),Component('last',True)]
    with pytest.raises(RuntimeError,match='close failed'):owner.close()
    assert owner.pipeline is None and owner._owned==[] and calls==['last','first']
    owner.close()


@pytest.mark.parametrize('failure', [None, 'occlusion', 'pipeline', 'cancel'])
def test_optional_occlusion_ownership_and_unwind(monkeypatch, failure):
    import sys
    import types
    closed = []
    made = []
    def check():
        if failure == 'cancel' and len(made) == 5:
            raise InterruptedError('cancel')
    def component(name):
        def construct(*args, **kwargs):
            assert kwargs['check'] is check
            if failure == name:
                raise RuntimeError(name)
            obj = types.SimpleNamespace(close=lambda: closed.append(name))
            made.append(obj)
            return obj
        return construct
    monkeypatch.setattr(m, 'verify_checkpoints', lambda roots, **kw: {
        role: Path(role) for role in ('generator', 'identity', 'detector', 'landmarks', 'restoration', 'occlusion')
    })
    def pipeline(*args, **kwargs):
        assert kwargs['occluder'] is made[-1]
        assert kwargs['check'] is check
        if failure == 'pipeline':
            raise RuntimeError('pipeline')
        return object()
    for name, attributes in {
        'cuda_ghostv2_engine': {'CudaGhostV2': component('engine')},
        'cuda_ghostv2_restoration': {'CudaGhostV2Restorer': component('restoration')},
        'cuda_ghostv2_occlusion': {'CudaXSegOccluder': component('occlusion')},
        'cuda_ghostv2_official_pipeline': {
            'CudaRetinaFace': component('detector'), 'CudaGhostLandmarks': component('landmarks'),
            'CudaGhostV2OfficialPipeline': pipeline,
        },
    }.items():
        monkeypatch.setitem(sys.modules, name, types.SimpleNamespace(**attributes))
    if failure:
        with pytest.raises((RuntimeError, InterruptedError)):
            m.GhostV2Components({}, occlusion=True, check=check)
    else:
        owner = m.GhostV2Components({}, occlusion=True, check=check)
        assert owner.pipeline is not None
        owner.close()
        owner.close()
    expected = ['restoration', 'landmarks', 'detector', 'engine']
    if failure != 'occlusion':
        expected.insert(0, 'occlusion')
    assert closed == expected
