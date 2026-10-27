from pathlib import Path
import sys,hashlib
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'spark'))
import cuda_ghostv2_occlusion as module


def test_hash_size_and_exact_verified_bytes(tmp_path,monkeypatch):
    data=b'a'*(1024*1024+17);p=tmp_path/'model.onnx';p.write_bytes(data)
    monkeypatch.setattr(module,'SIZE',len(data));monkeypatch.setattr(module,'SHA256',hashlib.sha256(data).hexdigest())
    assert module.verified_bytes(p)==data
    p.write_bytes(b'b'+data[1:])
    with pytest.raises(ValueError,match='digest'):module.verified_bytes(p)
    p.write_bytes(b'bad')
    with pytest.raises(ValueError,match='size'):module.verified_bytes(p)


def test_checkpoint_verification_cancellable(tmp_path,monkeypatch):
    p=tmp_path/'model.onnx';p.write_bytes(b'x'*2097152);monkeypatch.setattr(module,'SIZE',p.stat().st_size)
    calls=[]
    def cancel():
        calls.append(1)
        raise InterruptedError('cancel')
    with pytest.raises(InterruptedError):module.verified_bytes(p,cancel)
    assert len(calls)==1


def test_target_protection_preserves_masked_pixels():
    import numpy as np
    original=np.full((256,256,3),17,np.uint8);swapped=np.full_like(original,201)
    matrix=np.array([[1.,0.,0.],[0.,1.,0.]])
    mask=np.ones((256,256),np.float32);mask[:,:128]=0
    result=module.protect_target(original,swapped,matrix,mask)
    assert np.array_equal(result[:,:128],original[:,:128])
    assert np.array_equal(result[:,128:],swapped[:,128:])
    mask[0,0]=np.nan
    with pytest.raises(ValueError,match='mask'):module.protect_target(original,swapped,matrix,mask)
    mask[:]=1;matrix[:]=0
    with pytest.raises(ValueError,match='alignment'):module.protect_target(original,swapped,matrix,mask)


@pytest.mark.parametrize('initial', [(True, True), (False, True), (True, False), (False, False)])
@pytest.mark.parametrize('cancel', [False, True])
def test_scoped_fp32_policy_restores_on_failure(monkeypatch, initial, cancel):
    import sys
    from types import SimpleNamespace
    from cuda_ghostv2_occlusion import xseg_fp32_policy
    matmul = SimpleNamespace(allow_tf32=initial[0])
    cudnn = SimpleNamespace(allow_tf32=initial[1])
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(
        backends=SimpleNamespace(cuda=SimpleNamespace(matmul=matmul), cudnn=cudnn)))
    try:
        with xseg_fp32_policy():
            assert not matmul.allow_tf32 and not cudnn.allow_tf32
            if cancel:
                raise InterruptedError('cancel')
    except InterruptedError:
        assert cancel
    assert (matmul.allow_tf32, cudnn.allow_tf32) == initial
