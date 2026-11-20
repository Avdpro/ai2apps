"""AVTR request and trusted-checkpoint admission failures, without GPU loading."""
import hashlib,json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_avtr_engine import parameters,verify_weights

@pytest.mark.parametrize('values',[{'seconds':float('nan')},{'seconds':float('inf')},{'seconds':True},{'seconds':60.1},{'steps':1},{'steps':True},{'seed':-1},{'output_mode':'arbitrary'},{'checkpoint_path':'/tmp/untrusted'}])
def test_invalid_request_rejected(values):
    with pytest.raises(ValueError):parameters(values)

def fixture_lock(monkeypatch,tmp_path,content=b'fixed',relative='weights.safetensors'):
    path=tmp_path/relative;path.write_bytes(content)
    lock={'files':[{'path':relative,'size':len(content),'sha256':hashlib.sha256(content).hexdigest()}]}
    original=Path.read_text
    def read(self,*a,**kw):
        if self.name=='cuda_avtr_weights.lock.json':return json.dumps(lock)
        return original(self,*a,**kw)
    monkeypatch.setattr(Path,'read_text',read)
    return path

def test_same_size_corruption_rejected(monkeypatch,tmp_path):
    path=fixture_lock(monkeypatch,tmp_path);path.write_bytes(b'wrong')
    with pytest.raises(ValueError,match='hash mismatch'):verify_weights(tmp_path)

def test_symlink_escape_rejected(monkeypatch,tmp_path):
    root=tmp_path/'models';root.mkdir();path=fixture_lock(monkeypatch,root)
    outside=tmp_path/'outside';outside.write_bytes(b'fixed');path.unlink();path.symlink_to(outside)
    with pytest.raises(ValueError,match='file mismatch'):verify_weights(root)

def test_cancel_during_hash(monkeypatch,tmp_path):
    fixture_lock(monkeypatch,tmp_path)
    count=0
    def check():
        nonlocal count
        count+=1
        if count==2:raise InterruptedError('cancel')
    with pytest.raises(InterruptedError):verify_weights(tmp_path,check)


def test_each_request_selects_precision_and_resets_old_callback(tmp_path,monkeypatch):
    import soundfile as sf
    import torch
    from types import SimpleNamespace
    from cuda_avtr_engine import CudaAVTREngine
    monkeypatch.setattr(sf,'info',lambda _:SimpleNamespace(samplerate=16000,channels=1,duration=2))
    monkeypatch.setattr(torch.cuda,'synchronize',lambda:None)
    engine=object.__new__(CudaAVTREngine);calls=[]
    def record(mode):calls.append(mode)
    engine.pipeline=SimpleNamespace(enable_fast=lambda:record('fast'),disable_fast=lambda:record('standard'),generate=lambda *a,**kw:{'mode':calls[-1]})
    engine._request_check=lambda:(_ for _ in ()).throw(AssertionError('stale callback'))
    for i,preset in enumerate(('fast','standard','fast')):
        result=engine.generate('image','audio',tmp_path/f'{i}.mp4',{'preset':preset})
        assert result['mode']==preset
    assert calls==['fast','standard','fast']
