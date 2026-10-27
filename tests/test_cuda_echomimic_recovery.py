"""Checkpoint corruption and failed-save isolation for exact CUDA recovery."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
import torch
from safetensors.torch import load_file, save_file
from safetensors import safe_open
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_echomimic_recovery import EchoRecoveryStore


def fixture(tmp_path):
    sample=torch.zeros((1,16,21,64,64))
    scheduler=SimpleNamespace(step_index=1,timesteps=torch.arange(8),sigmas=torch.arange(9).float(),
        lower_order_nums=1,this_order=1,model_outputs=[None,sample],
        timestep_list=[None,torch.tensor(7)],last_sample=sample)
    store=EchoRecoveryStore(tmp_path/'checkpoint.safetensors','a'*64)
    store.save(scheduler,sample)
    return store,scheduler,sample


def test_failed_save_preserves_previous_atomic_checkpoint(tmp_path):
    store,scheduler,sample=fixture(tmp_path)
    before=store.path.read_bytes()
    sample[0,0,0,0,0]=float('nan')
    with pytest.raises(ValueError,match='nonfinite'):store.save(scheduler,sample)
    assert store.path.read_bytes()==before
    assert list(tmp_path.iterdir())==[store.path]
    meta,tensors=store.load()
    assert meta['step']==1 and torch.isfinite(tensors['sample']).all()


@pytest.mark.parametrize('damage',['fingerprint','history','step','shape','nonfinite','extra'])
def test_reject_corrupt_checkpoint(tmp_path,damage):
    store,_,_=fixture(tmp_path)
    tensors=load_file(str(store.path))
    with safe_open(str(store.path),framework='pt') as source:meta=json.loads(source.metadata()['state'])
    if damage=='fingerprint':meta['fingerprint']='b'*64
    elif damage=='history':meta['model_outputs']=[True]
    elif damage=='step':meta['step']=9
    elif damage=='shape':tensors['sample']=torch.zeros(1)
    elif damage=='nonfinite':tensors['sample'][0,0,0,0,0]=float('inf')
    elif damage=='extra':tensors['unrecognized']=torch.ones(1)
    save_file(tensors,str(store.path),metadata={'state':json.dumps(meta)})
    with pytest.raises(ValueError):store.load()
