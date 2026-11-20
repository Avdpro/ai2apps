"""VoxCPM2 request admission and output ownership without a GPU."""
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_voxcpm_engine import parameters,CudaVoxCPMEngine

@pytest.mark.parametrize('value',[{'seed':True},{'seed':-1},{'steps':0},{'steps':True},
    {'cfg':float('nan')},{'cfg':float('inf')},{'cfg':1.9},{'max_tokens':2001},
    {'instructions':[]},{'checkpoint_path':'/tmp/other'}])
def test_bad_parameters(value):
    with pytest.raises(ValueError):parameters('hello',value)

def engine(monkeypatch,generate):
    import torch
    monkeypatch.setattr(torch.cuda,'synchronize',lambda:None)
    obj=object.__new__(CudaVoxCPMEngine)
    obj.variant='4bit';obj._request_check=lambda:None
    obj.model=SimpleNamespace(text_tokenizer=lambda text:[1,2],config=SimpleNamespace(max_length=8192),
                              sample_rate=48000,generate=generate)
    return obj

def test_existing_output_is_preserved(monkeypatch,tmp_path):
    obj=engine(monkeypatch,lambda **kw:pytest.fail('must not generate'))
    path=tmp_path/'existing.wav';path.write_bytes(b'keep')
    with pytest.raises(FileExistsError):obj.generate('hello',path,{})
    assert path.read_bytes()==b'keep'

def test_cancel_cleans_owned_output_and_rebinds_callback(monkeypatch,tmp_path):
    import torch
    obj=engine(monkeypatch,None)
    def fail(**kw):obj._request_check()
    obj.model.generate=fail
    count=0
    def check():
        nonlocal count
        count+=1
        if count>1:raise InterruptedError('cancelled')
    output=tmp_path/'cancel.wav'
    with pytest.raises(InterruptedError):obj.generate('hello',output,{},check=check)
    assert not output.exists()
    obj._request_check()  # No stale cancelled request remains.
    obj.model.generate=lambda **kw:torch.zeros(1,4800)
    assert obj.generate('hello',tmp_path/'next.wav',{})['samples']==4800


@pytest.mark.parametrize('load_fails',[False,True])
@pytest.mark.parametrize('workspace',[None,':16:8'])
def test_quantized_settings_restored_on_close_and_load_failure(monkeypatch,load_fails,workspace):
    import os
    import torch
    from types import ModuleType
    fake=ModuleType('cuda_voxcpm_loader')
    def load(*args,**kwargs):
        assert torch.are_deterministic_algorithms_enabled()
        assert not torch.backends.cudnn.allow_tf32
        if load_fails:raise InterruptedError('cancel during load')
        return SimpleNamespace(modules=lambda:[]),{}
    fake.load_mac_checkpoint=load
    monkeypatch.setitem(sys.modules,'cuda_voxcpm_loader',fake)
    monkeypatch.setattr(torch.cuda,'synchronize',lambda:None)
    monkeypatch.setattr(torch.cuda,'empty_cache',lambda:None)
    if workspace is None:monkeypatch.delenv('CUBLAS_WORKSPACE_CONFIG',raising=False)
    else:monkeypatch.setenv('CUBLAS_WORKSPACE_CONFIG',workspace)
    def state():return (os.environ.get('CUBLAS_WORKSPACE_CONFIG'),
        torch.backends.cuda.matmul.allow_tf32,torch.backends.cudnn.allow_tf32,
        torch.backends.cudnn.benchmark,torch.backends.cudnn.deterministic,
        torch.are_deterministic_algorithms_enabled(),torch.is_deterministic_algorithms_warn_only_enabled())
    before=state()
    if load_fails:
        with pytest.raises(InterruptedError):CudaVoxCPMEngine('/unused','4bit')
    else:
        obj=CudaVoxCPMEngine('/unused','4bit');obj.close();obj.close()
    assert state()==before
