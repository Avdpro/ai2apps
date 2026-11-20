"""Protect CFG branch ownership and cleanup around the pinned upstream cache."""
from pathlib import Path
import sys
import torch
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_echomimic_teacache import EchoTeaCacheBridge

class Cache:
    def __init__(self,coefficients,steps,threshold,skip,offload):
        self.num_steps=steps;self.should_calc=True
    def reset(self):
        raise AssertionError('Upstream mid-pair reset must be suppressed')

class Model:
    def __init__(self):self.teacache=None;self.observed=[]
    def forward(self,*,t,cond_flag=True):
        cache=self.teacache
        self.observed.append((cache.cnt,cond_flag,float(t)))
        cache.should_calc=cache.cnt<2
        cache.previous_residual_cond=torch.ones(1)
        cache.cnt+=1
        if cache.cnt==cache.num_steps:cache.reset()
        return t


def test_eight_steps_have_two_distinct_branches_and_one_counter():
    model=Model()
    with EchoTeaCacheBridge(model,Cache) as bridge:
        for step in range(8):
            for _ in range(2):model.forward(t=torch.tensor(999-step))
    assert model.observed==[(step,branch==0,float(999-step)) for step in range(8) for branch in range(2)]
    assert bridge.calls==16 and len(bridge.decisions)==8
    assert model.teacache is None and 'forward' not in model.__dict__
    assert bridge.cache.previous_residual_cond is None


def test_mismatched_pair_rejected_and_forward_restored():
    model=Model()
    with pytest.raises(RuntimeError,match='different timesteps'):
        with EchoTeaCacheBridge(model,Cache):
            model.forward(t=torch.tensor(999))
            model.forward(t=torch.tensor(998))
    assert model.teacache is None and 'forward' not in model.__dict__


def test_cancellation_preserves_original_error_and_cleans_cache():
    model=Model()
    with pytest.raises(InterruptedError):
        with EchoTeaCacheBridge(model,Cache):
            model.forward(t=torch.tensor(999))
            raise InterruptedError('cancel')
    assert model.teacache is None and 'forward' not in model.__dict__


def test_short_window_is_not_silently_accepted():
    model=Model()
    with pytest.raises(RuntimeError,match='every CFG pair'):
        with EchoTeaCacheBridge(model,Cache):pass
    assert model.teacache is None


def test_distance_uses_float32_like_mac():
    model=Model();bridge=EchoTeaCacheBridge(model,Cache)
    a=torch.tensor([.1,2.5],dtype=torch.bfloat16);b=torch.tensor([.11,2.6],dtype=torch.bfloat16)
    expected=float((abs(b.float()-a.float()).mean()/abs(a.float()).mean()).item())
    assert bridge.cache.compute_rel_l1_distance(a,b)==expected
